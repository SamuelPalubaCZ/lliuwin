#!/usr/bin/env bash
# Ubuntu image builder; derived from the LliureX Team's 2023 generator.
set -Eeuo pipefail
[[ $EUID == 0 && $(uname -m) == x86_64 ]] || { echo 'Run on Linux amd64 as root' >&2; exit 1; }
[[ $# == 1 && ! -e $1 ]] || { echo 'Usage: sudo ./generate_lliuwin_img.sh NEW_OUTPUT_DIRECTORY' >&2; exit 1; }
source_root=$(cd -- "$(dirname -- "$0")" && pwd)
source_commit=$(git -c safe.directory="$source_root" -C "$source_root" rev-parse HEAD)
mkdir -p -- "$1"
out=$(realpath -- "$1")
work=$(mktemp -d)
cleanup() {
    status=$?
    trap - EXIT
    if mountpoint -q "$work/root"; then
        umount -R "$work/root" || { echo "Unmount failed: $work/root" >&2; exit 1; }
    fi
    rmdir "$work/root" "$work" 2>/dev/null || true
    exit "$status"
}
trap cleanup EXIT
mkdir "$work/root"
truncate -s 20G "$out/root.disk"
mkfs.ext4 -F -L lliuwin-root "$out/root.disk"
mount -o loop "$out/root.disk" "$work/root"
root=$work/root
debootstrap --include=ca-certificates --arch=amd64 --keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg noble "$root" https://archive.ubuntu.com/ubuntu
cat > "$root/etc/apt/sources.list" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse
SOURCES
# Boot ownership stays with the Windows installer, including during kernel updates.
cat > "$root/etc/apt/preferences.d/lliuwin-boot-ownership" <<'PINS'
Package: grub-pc grub-efi-amd64 grub-efi-ia32
Pin: version *
Pin-Priority: -1
PINS
for dir in dev proc sys; do mount --rbind "/$dir" "$root/$dir"; mount --make-rslave "$root/$dir"; done
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod +x "$root/usr/sbin/policy-rc.d"
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive bash -eux <<'CHROOT'
apt-get update
apt-get -y dist-upgrade
apt-get install -y ubuntu-desktop linux-generic initramfs-tools gnome-initial-setup ntfs-3g e2fsprogs
passwd -l root
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8
printf 'lliuwin\n' > /etc/hostname
printf '127.0.0.1 localhost\n127.0.1.1 lliuwin\n' > /etc/hosts
mkdir -p /host /etc/gdm3
sed -i '/^[[:space:]]*InitialSetupEnable=/d' /etc/gdm3/custom.conf
sed -i '/^\[daemon\]/a InitialSetupEnable=true' /etc/gdm3/custom.conf
printf 'tmpfs /tmp tmpfs defaults,nosuid,nodev 0 0\n' > /etc/fstab
systemctl set-default graphical.target
CHROOT
# apt's transitional browser packages skip snap installation in a chroot.
# Native snap image preparation verifies assertions and this explicit dependency set.
# A changed upstream base/provider fails the build rather than publishing an incomplete desktop.
snap prepare-image --classic --arch=amd64 --validation=enforce \
    --snap=firefox --snap=thunderbird --snap=snap-store \
    --snap=core24 --snap=core22 --snap=bare --snap=mesa-2404 \
    --snap=gnome-46-2404 --snap=gnome-42-2204 --snap=gtk-common-themes "" "$root"
test -s "$root/var/lib/snapd/seed/seed.yaml"
cp "$root/var/lib/snapd/seed/seed.yaml" "$out/snaps.yaml"
install -m 755 "$source_root/tools/image/lliuwin-loop" "$root/etc/initramfs-tools/hooks/lliuwin-loop"
install -m 755 "$source_root/tools/image/grow-root" "$root/usr/local/sbin/lliuwin-grow-root"
install -m 644 "$source_root/tools/image/lliuwin-grow-root.service" "$root/etc/systemd/system/lliuwin-grow-root.service"
mkdir -p "$root/etc/systemd/system/gdm3.service.d"
printf '[Unit]\nRequires=lliuwin-grow-root.service\nAfter=lliuwin-grow-root.service\n' > "$root/etc/systemd/system/gdm3.service.d/lliuwin.conf"
chroot "$root" systemctl enable lliuwin-grow-root.service
chroot "$root" update-initramfs -u -k all
chroot "$root" bash -eux <<'CHROOT'
! dpkg-query -W -f='${db:Status-Status}\n' grub-pc grub-efi-amd64 grub-efi-ia32 2>/dev/null | grep '^installed$'
test -e /boot/vmlinuz
test -e /boot/initrd.img
test -x /usr/libexec/gnome-initial-setup
passwd -S root | grep '^root L '
grep -q '^InitialSetupEnable=true$' /etc/gdm3/custom.conf
! awk -F: '$3 >= 1000 && $3 < 65534 {found=1} END {exit !found}' /etc/passwd
for initrd in /boot/initrd.img-*; do
    lsinitramfs "$initrd" | grep -q 'scripts/local'
    lsinitramfs "$initrd" | grep -q 'ntfs3.ko'
    check=$(mktemp -d)
    unmkinitramfs "$initrd" "$check"
    grep -F 'LOOPDEV=$(losetup' "$check/main/scripts/local"
    rm -rf "$check"
done
apt-get clean
rm /usr/sbin/policy-rc.d
rm -f /var/lib/dbus/machine-id
: > /etc/machine-id
rm -f /etc/ssh/ssh_host_*
CHROOT
chroot "$root" dpkg-query -W > "$out/packages.txt"
printf '%s\n' "$source_commit" > "$out/source-commit.txt"
umount -R "$root"
e2fsck -fn "$out/root.disk"
echo "Image built: $out/root.disk"
