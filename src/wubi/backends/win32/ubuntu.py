"""Ubuntu-on-NTFS transaction; Windows changes are journalled and owned."""
from __future__ import division
import ctypes
import json
import os
import re
import shutil
import uuid
from contextlib import contextmanager
from wubi.backends.common import image
from wubi.backends.common.utils import run_command

GUID = re.compile(r'^\{[0-9a-fA-F-]{36}\}$')


def system_tool(name):
    root = os.environ['SystemRoot']
    native = os.path.join(root, 'Sysnative', name)
    return native if os.path.isfile(native) else os.path.join(root, 'System32', name)


def preflight(backend):
    info = backend.info
    arch = os.environ.get('PROCESSOR_ARCHITEW6432', os.environ.get('PROCESSOR_ARCHITECTURE', ''))
    if arch.upper() != 'AMD64' or int(info.windows_build) < 19045:
        raise ValueError('Windows 10 22H2 or Windows 11 on Intel/AMD x64 is required.')
    firmware = ctypes.c_uint()
    if not ctypes.windll.kernel32.GetFirmwareType(ctypes.byref(firmware)) or firmware.value != 2:
        raise ValueError('UEFI firmware is required.')
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('Run LLiuWin as administrator.')
    if info.target_drive.type != 'hd' or info.target_drive.filesystem != 'ntfs':
        raise ValueError('Select a local, unencrypted NTFS volume.')
    target = info.target_drive.path.upper()
    if not re.match(r'^[A-Z]:$', target):
        raise ValueError('Invalid target drive')
    attributes = ctypes.windll.kernel32.GetFileAttributesW(unicode(target + '\\'))
    if attributes == -1 or attributes & 0x4000:
        raise ValueError('The target directory is unreadable or uses EFS encryption.')
    # Numeric CIM properties avoid parsing translated manage-bde output.
    script = r'''$ErrorActionPreference='Stop';
    $drives=@('%s',$env:SystemDrive) | Select-Object -Unique;
    $volumes=@(Get-CimInstance -Namespace root/cimv2/security/MicrosoftVolumeEncryption -ClassName Win32_EncryptableVolume);
    foreach($d in $drives) {
      $v=@($volumes | Where-Object DriveLetter -eq $d);
      if($v.Count -ne 1){throw "Cannot determine encryption status for $d"};
      $s=Invoke-CimMethod -InputObject $v[0] -MethodName GetConversionStatus;
      if($s.ReturnValue -ne 0 -or $s.ConversionStatus -ne 0){throw "Decrypt $d before installation (suspending BitLocker is insufficient)"};
      $l=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$d'";
      if($null -eq $l.VolumeDirty -or $l.VolumeDirty){throw "Volume $d requires a Windows disk check"}
    };
    $fast=(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -ErrorAction Stop).HiberbootEnabled;
    if($fast -ne 0 -or (Test-Path ($env:SystemDrive+'\hiberfil.sys'))){throw 'Disable Windows hibernation and Fast Startup with powercfg /h off, then restart Windows'};
    'OK' ''' % target
    result = run_command([system_tool(r'WindowsPowerShell\v1.0\powershell.exe'), '-NoProfile', '-NonInteractive', '-Command', script])
    if result.strip() != 'OK':
        raise ValueError('Windows preflight did not complete')


@contextmanager
def mounted_esp(run=run_command):
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    if not mask:
        raise ValueError("Cannot determine mounted Windows volumes")
    letters = [chr(n + 65) for n in range(25, 3, -1) if not mask & (1 << n)]
    if not letters:
        raise ValueError('No free drive letter for the EFI system partition')
    drive = letters[0] + ':'
    run([system_tool('mountvol.exe'), drive, '/s'])
    try:
        yield drive
    finally:
        run([system_tool('mountvol.exe'), drive, '/d'])


def save_state(directory, state):
    path = os.path.join(directory, 'installation.json')
    with open(path + '.tmp', 'w') as stream:
        json.dump(state, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    if os.name == 'nt':
        if not ctypes.windll.kernel32.MoveFileExW(unicode(path + '.tmp'), unicode(path), 9):
            raise ctypes.WinError()
    else:
        os.rename(path + '.tmp', path)


def read_state(directory):
    with open(os.path.join(directory, 'installation.json')) as stream:
        state = json.load(stream)
    if state.get('schema') != 1 or not re.match(r'^[a-f0-9]{32}$', state.get('id', '')):
        raise ValueError('Installation ownership record is invalid; no files removed')
    if state.get('bcd') and not GUID.match(state['bcd']):
        raise ValueError('Invalid recorded BCD identifier')
    if os.path.basename(os.path.normpath(directory)).lower() != 'lliuwin':
        raise ValueError('Unexpected installation directory')
    return state


def validate_owned_tree(directory):
    # Python 2 rmtree follows Windows junctions; reject them before deleting anything.
    for parent, directories, files in os.walk(directory):
        paths = [parent] + [os.path.join(parent, name) for name in directories + files]
        for path in paths:
            if os.path.islink(path) or (os.name == 'nt' and
                    ctypes.windll.kernel32.GetFileAttributesW(unicode(path)) & 0x400):
                raise ValueError('Installation contains an unreadable path or reparse point; no files removed')


def remove_boot(state, run=run_command):
    if state.get('bcd'):
        bcdedit = system_tool('bcdedit.exe')
        entries = run([bcdedit, '/enum', 'all'])
        if state['bcd'].lower() in entries.lower():
            run([bcdedit, '/delete', state['bcd'], '/f'])
    if state.get('efi'):
        with mounted_esp(run) as drive:
            folder = os.path.join(drive + '\\', 'EFI', 'lliuwin-' + state['id'])
            if os.path.isdir(folder):
                shutil.rmtree(folder)


def install(backend, associated_task=None):
    info = backend.info
    manifest = image.load_manifest(os.path.join(info.data_dir, 'image.json'))
    preflight(backend)
    disk_bytes = int(info.installation_size_mb) * 1024 ** 2
    required = image.required_space(manifest, disk_bytes)
    if info.target_drive.get_space()[1] < required:
        raise ValueError('Insufficient free space for the disk, download and temporary archive')
    backend.select_target_dir()
    directory = info.target_dir
    os.mkdir(directory)
    state = {'schema': 1, 'id': uuid.uuid4().hex, 'bcd': None, 'efi': False, 'complete': False}
    save_state(directory, state)
    def progress(current, total):
        if associated_task and associated_task.set_progress(current, total + 1, unit='bytes'):
            raise RuntimeError('Installation cancelled')
    try:
        backend.uncompress_target_dir(associated_task)
        staging = os.path.join(directory, 'download')
        os.mkdir(staging)
        base = 'https://github.com/SamuelPalubaCZ/lliuwin/releases/download/' + manifest['release'] + '/'
        for part in manifest['parts']:
            image.download_part(base + part['name'], os.path.join(staging, part['name']), part, progress)
        archive = os.path.join(staging, 'image.tar.gz')
        with open(archive, 'wb') as output:
            for part in manifest['parts']:
                with open(os.path.join(staging, part['name']), 'rb') as source:
                    shutil.copyfileobj(source, output, 1024 * 1024)
        disks = os.path.join(directory, 'disks')
        os.mkdir(disks)
        root = os.path.join(disks, 'root.disk')
        image.extract_image(archive, root, manifest, progress)
        with open(root, 'r+b') as stream:
            stream.truncate(disk_bytes)
        # A unique marker prevents GRUB selecting a leftover install on another disk.
        marker = 'lliuwin-' + state['id']
        open(os.path.join(directory, marker), 'w').close()
        with mounted_esp() as drive:
            destination = os.path.join(drive + '\\', 'EFI', marker)
            if os.path.exists(destination):
                raise ValueError('EFI destination already exists')
            state['efi'] = True
            save_state(directory, state)
            shutil.copytree(os.path.join(info.root_dir, 'winboot', 'EFI'), destination)
            cfg = '''search --no-floppy --file --set=host /lliuwin/%s
probe --set=hostuuid --fs-uuid ($host)
loopback loopw0 ($host)/lliuwin/disks/root.disk
set root=(loopw0)
linux /boot/vmlinuz root=UUID=$hostuuid loop=/lliuwin/disks/root.disk rootfstype=ntfs3 loopfstype=ext4 rw quiet splash
initrd /boot/initrd.img
boot
''' % marker
            with open(os.path.join(destination, 'grub.cfg'), 'w') as stream:
                stream.write(cfg)
            bcdedit = system_tool('bcdedit.exe')
            state['bcd'] = '{' + str(uuid.uuid4()) + '}'
            save_state(directory, state)
            run_command([bcdedit, '/create', state['bcd'], '/d', 'Ubuntu (LLiuWin)', '/application', 'BOOTAPP'])
            run_command([bcdedit, '/set', state['bcd'], 'device', 'partition=' + drive])
            run_command([bcdedit, '/set', state['bcd'], 'path', '\\EFI\\' + marker + '\\shimx64.efi'])
            run_command([bcdedit, '/set', '{fwbootmgr}', 'displayorder', state['bcd'], '/addlast'])
        shutil.copyfile(info.application_icon, info.icon)
        backend.create_uninstaller(associated_task)
        with open(os.path.join(directory, 'Start Ubuntu.cmd'), 'w') as stream:
            stream.write('@echo off\r\nbcdedit /set {fwbootmgr} bootsequence %s && shutdown /r /t 0\r\n' % state['bcd'])
        shutil.rmtree(staging)
        state['complete'] = True
        save_state(directory, state)
    except BaseException:
        # Keep journal and disk if rollback fails; never silently delete recovery data.
        validate_owned_tree(directory)
        remove_boot(state)
        backend.remove_registry_key()
        shutil.rmtree(directory)
        raise


def uninstall(backend, associated_task=None):
    directory = backend.info.previous_target_dir
    state = read_state(directory)
    validate_owned_tree(directory)
    remove_boot(state)
    shutil.rmtree(directory)
    backend.remove_registry_key()
