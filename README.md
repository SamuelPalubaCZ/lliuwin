# LLiuWin — Ubuntu 24.04 image installer

Work in progress: Windows 10 22H2 / Windows 11 x64, UEFI and unencrypted local NTFS. Installs Ubuntu Desktop into `\lliuwin\disks\root.disk`, without repartitioning. Existing LliureX installations are not migrated.

**Prerelease only. Real dual boot, first-user setup, kernel update and uninstall testing is pending.** See [ROADMAP.md](ROADMAP.md) for the acceptance checklist and [UPSTREAM_AUDIT.md](UPSTREAM_AUDIT.md) for provenance and upstream findings.

## Build and release

- Push / PR: portable regression checks, Python 2.7.18 Wine build, EXE/MSI artifact. These development installers have no released image and refuse installation.
- Actions → **Build and prerelease** → **Run workflow**: full image + installer build, no publication. Its synthetic CI image version is for build verification only.
- Push a new `v*` tag: build and check Ubuntu, split image into 1 GiB parts, bundle its manifest into EXE/MSI, verify SHA256SUMS and publish a complete prerelease. Existing releases are never overwritten. Upload failure leaves an unpublished draft for inspection.
- MSI installs the launcher under Program Files. Run it as administrator to install Ubuntu. Remove Ubuntu using its own Windows uninstall entry before removing the MSI launcher.

The image comes from signed Ubuntu noble/noble-updates/noble-security repositories, with `ubuntu-desktop`, `linux-generic` and `initramfs-tools`. Firefox, Thunderbird and the app store are staged with signed Snap Store assertions using [native `snap prepare-image`](https://ubuntu.com/docs/imagecraft/latest/how-to/pre-install-snaps/), including their dependencies. GNOME Initial Setup is intended to create the first personal account. No shared password is embedded. Native Python 2.7.18 is retained only for this transition release.

## Development

On Ubuntu 24.04 amd64, install the dependencies listed in [.github/workflows/build.yml](.github/workflows/build.yml), then:

```sh
xvfb-run -a make build
./generate_msi.sh
python3 -m unittest discover -s tests -p test_image_transport.py -v
python3 -m unittest discover -s tests -p test_ubuntu_transaction.py -v
sudo ./generate_lliuwin_img.sh /absolute/new-output-directory
python3 tools/package_image.py /absolute/new-output-directory v24.04.1
```

For a release build, copy the generated `image.json` to `data/image.json` before building the installer. Do not mix images and manifests from different releases. The automated workflow does this explicitly.

## Installation constraints and recovery

Preflight requires fully decrypted system/target volumes, clean NTFS and hibernation/Fast Startup disabled. Unknown status blocks installation. The installer does not disable these Windows settings automatically.

The installation journal is `\lliuwin\installation.json`; it records the unique EFI directory and BCD identifier. Failed rollback preserves this directory for recovery. Do not delete the journal or manually remove unrelated EFI entries. Windows remains the normal first boot choice; use `Start Ubuntu.cmd` as administrator or select the Ubuntu firmware entry.

## License and provenance

Derived from LliureX LLiuWin, hakuna-m WubiUEFI and Wubi. Existing license and copyright headers apply to retained code. The persistent loop-allocation approach references CalinGH commit `a8465ab407d8`; no third-party fork binaries or signature-check bypasses are imported.
