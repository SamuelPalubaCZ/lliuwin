# Roadmap

## 1. Windows validation — required before stable release

Dependencies: a complete CI build, its exact manifest/image and a disposable Windows 10/11 x64 UEFI machine or VM with recovery media. All releases remain prereleases.

Completion checks:
- NTFS install at minimum and larger sizes; no partition changes; no shared account/password.
- Reject encryption, dirty NTFS, hibernation, legacy BIOS and unsupported architecture before mutation.
- GNOME Initial Setup creates the first user; filesystem grows before login.
- Boot Windows → Ubuntu → Windows with Secure Boot enabled and disabled.
- Update kernel, regenerate initramfs, reboot and confirm loop host/root mounts.
- Cancel download, exhaust storage, inject EFI/BCD errors, retry cleanup from the journal.
- Uninstall removes only this installation and its firmware entry; existing LliureX stays untouched.

Use upstream #336, #345, #347, #351, #356, #365, #367 and #369 as regression scenarios. Portable tests are not substitutes for these checks. Real install/restart testing is deferred by agreement.

## 2. Python 3

Depends on the Windows acceptance baseline. Evaluate CalinGH `modernize` Python 3/CIM/UAC work and BellezaEmporium `rework`; port the retained app before considering a UI rewrite. Replace the Python 2 freezer/runtime, reproduce all acceptance checks, verify packaged TLS and uninstall behavior. Complete when maintained Python builds the EXE/MSI and passes the same Windows tests.

## 3. Ubuntu 26.04 / Dracut

Depends on the Python 3 and boot validation baseline. Evaluate aurelienjsureau `spike-loopboot-2604` and upstream initramfs transition. Add a persistent Dracut loop-root module only when needed; verify signed loaders, NTFS behavior, root expansion and two consecutive kernel upgrades. No support label based on a version string or successful build alone.

## 4. Flavors and interim versions

Depends on a proven second image target. Add explicit manifests and first-user setup for each flavor; avoid a general provider system until a second tested implementation needs it. Review upstream isolist PRs #349/#360 only for applicable behavior. Completion requires per-flavor image/boot/update/uninstall checks and a documented support/EOL policy.
