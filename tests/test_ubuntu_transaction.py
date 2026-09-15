"""Portable failure injection for Windows ownership and rollback."""
import contextlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
sys.path.insert(0, os.path.abspath('src/wubi/backends/common'))
import image
# The transaction itself is portable; replace only platform imports.
for name in ('wubi', 'wubi.backends', 'wubi.backends.common', 'wubi.backends.common.utils'):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
sys.modules['wubi.backends.common'].image = image
sys.modules['wubi.backends.common.utils'].run_command = lambda command: ''
ubuntu = types.ModuleType('ubuntu_transaction')
with open('src/wubi/backends/win32/ubuntu.py') as source:
    eval(compile(source.read(), source.name, 'exec'), ubuntu.__dict__)

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.directory = os.path.join(self.base, 'lliuwin')
        os.mkdir(self.directory)
        self.state = dict(schema=1, id='a'*32, bcd='{11111111-1111-1111-1111-111111111111}', efi=True)
        self.original_esp = ubuntu.mounted_esp
        self.original_tool = ubuntu.system_tool
        ubuntu.system_tool = lambda name: name
        @contextlib.contextmanager
        def esp(run):
            yield self.base
        ubuntu.mounted_esp = esp
    def tearDown(self):
        ubuntu.mounted_esp = self.original_esp
        ubuntu.system_tool = self.original_tool
        shutil.rmtree(self.base)
    def test_journal_and_invalid_ownership(self):
        ubuntu.save_state(self.directory, self.state)
        self.assertEqual(ubuntu.read_state(self.directory), self.state)
        self.state['id'] = '../Microsoft'
        ubuntu.save_state(self.directory, self.state)
        self.assertRaises(ValueError, ubuntu.read_state, self.directory)
    def test_bcd_failure_preserves_recovery_files(self):
        calls = []
        def run(command):
            calls.append(command)
            if '/enum' in command:
                return self.state['bcd']
            raise RuntimeError('BCD deletion failed')
        self.assertRaises(RuntimeError, ubuntu.remove_boot, self.state, run)
        self.assertEqual(len(calls), 2)
        self.assertTrue(os.path.isdir(self.directory))
    def test_absent_bcd_entry_is_idempotent(self):
        self.state['efi'] = False
        calls = []
        ubuntu.remove_boot(self.state, lambda command: calls.append(command) or '')
        self.assertEqual(len(calls), 1)
    def test_efi_mount_failure_propagates(self):
        @contextlib.contextmanager
        def failing(run):
            raise RuntimeError('EFI unavailable')
            yield
        ubuntu.mounted_esp = failing
        self.state['bcd'] = None
        self.assertRaises(RuntimeError, ubuntu.remove_boot, self.state)

class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.directory = os.path.join(self.base, 'lliuwin')
        os.mkdir(self.directory)
        self.neighbor = os.path.join(self.base, 'existing-lliurex.txt')
        with open(self.neighbor, 'w') as f:
            f.write('preserve')
        ubuntu.save_state(self.directory, dict(schema=1, id='a'*32, bcd=None, efi=False))
        self.original_remove = ubuntu.remove_boot
        self.calls = []
        ubuntu.remove_boot = lambda state: self.calls.append('boot')
        self.backend = types.ModuleType('backend')
        self.backend.info = types.ModuleType('info')
        self.backend.info.previous_target_dir = self.directory
        self.backend.remove_registry_key = lambda: self.calls.append('registry')
    def tearDown(self):
        ubuntu.remove_boot = self.original_remove
        shutil.rmtree(self.base)
    def test_removes_only_owned_directory(self):
        ubuntu.uninstall(self.backend)
        self.assertFalse(os.path.exists(self.directory))
        self.assertTrue(os.path.isfile(self.neighbor))
        self.assertEqual(self.calls, ['boot', 'registry'])
    def test_invalid_journal_does_not_mutate(self):
        ubuntu.save_state(self.directory, dict(schema=1, id='../other'))
        self.assertRaises(ValueError, ubuntu.uninstall, self.backend)
        self.assertTrue(os.path.isdir(self.directory))
        self.assertEqual(self.calls, [])
    def test_boot_failure_preserves_disk_and_registry(self):
        def fail(state):
            raise RuntimeError('BCD unavailable')
        ubuntu.remove_boot = fail
        self.assertRaises(RuntimeError, ubuntu.uninstall, self.backend)
        self.assertTrue(os.path.isdir(self.directory))
        self.assertEqual(self.calls, [])

class InstallFailureTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.directory = os.path.join(self.base, 'lliuwin')
        self.saved = (ubuntu.preflight, image.load_manifest, image.download_part, ubuntu.remove_boot)
        self.events = []
        class Info(object):
            pass
        info = Info()
        info.data_dir = self.base
        info.target_dir = self.directory
        info.installation_size_mb = 32 * 1024
        info.target_drive = Info()
        info.target_drive.get_space = lambda: (100 * image.GIB, 100 * image.GIB)
        self.backend = Info()
        self.backend.info = info
        self.backend.select_target_dir = lambda: self.events.append('select')
        self.backend.uncompress_target_dir = lambda task: None
        self.backend.remove_registry_key = lambda: self.events.append('registry')
        ubuntu.preflight = lambda backend: None
        image.load_manifest = lambda path: dict(minimum_disk_bytes=32 * image.GIB, release='v1', parts=[dict(name='part', bytes=10)])
        def fail(*args):
            raise IOError('Interrupted download')
        image.download_part = fail
        ubuntu.remove_boot = lambda state: self.events.append('boot')
    def tearDown(self):
        ubuntu.preflight, image.load_manifest, image.download_part, ubuntu.remove_boot = self.saved
        shutil.rmtree(self.base)
    def test_download_failure_rolls_back_owned_directory(self):
        self.assertRaises(IOError, ubuntu.install, self.backend)
        self.assertEqual(self.events, ['select', 'boot', 'registry'])
        self.assertFalse(os.path.exists(self.directory))
    def test_insufficient_space_never_mutates(self):
        self.backend.info.target_drive.get_space = lambda: (100 * image.GIB, image.GIB)
        self.assertRaises(ValueError, ubuntu.install, self.backend)
        self.assertEqual(self.events, [])
        self.assertFalse(os.path.exists(self.directory))
    def test_rollback_failure_keeps_journal(self):
        def fail(state):
            raise RuntimeError('Cannot remove EFI entry')
        ubuntu.remove_boot = fail
        self.assertRaises(RuntimeError, ubuntu.install, self.backend)
        self.assertTrue(os.path.isfile(os.path.join(self.directory, 'installation.json')))
        self.assertNotIn('registry', self.events)

if __name__ == '__main__':
    unittest.main()
