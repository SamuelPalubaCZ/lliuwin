# Validation

Validation date: 2026-09-15.

## Verified

- Python 3 portable transport and ownership tests: 18 cases pass.
- Python 2.7.18 under Wine: the same suite passes; the POSIX symlink fixture is skipped, while the Windows reparse-point branch has a separate check.
- Frozen application imports, TLS initialization and bundled manifest presence pass.
- The actual self-extracting EXE starts successfully and writes its self-test marker.
- MSI installs an EXE byte-identical to the build output, then removes it successfully under Wine.
- Ubuntu-supplied EFI files come from signed APT packages; build output lists the Canonical GRUB and Microsoft shim signing certificates.
- Preserved local icon SHA-256: `3584323350dbffa9e724fcceff94e5c870aa845da70a0fc3e79c8c79804a2592`.
- Push and PR checks: https://github.com/SamuelPalubaCZ/lliuwin/actions/runs/34977500986 and https://github.com/SamuelPalubaCZ/lliuwin/actions/runs/34977505465.

## Full image

The full Ubuntu image passed its build and inspection step in [manual run 34977506984](https://github.com/SamuelPalubaCZ/lliuwin/actions/runs/34977506984), source commit `ed5853e902e8038b4687546c620305b93c60769b`:

- Official Noble APT repositories, Ubuntu Desktop and supported generic kernel.
- Asserted Snap seeds, including browser bases and content dependencies.
- Locked root, no preconfigured human account, and GNOME Initial Setup binary/configuration.
- Persistent loop allocation and NTFS3 support survive initramfs regeneration.
- No package-managed GRUB installation that could overwrite installer-owned boot files.
- Clean read-only filesystem check after unmounting and detaching the image loop device.

The complete manual workflow passed: image packaging into 1 GiB parts, matching bundled manifest, EXE/MSI builds and tests, and SHA-256 verification. Download the `lliuwin-complete` artifact from the linked run. Publication was correctly skipped for this manual run; tag publication has not been exercised against a live release. Subsequent documentation changes do not alter the image or installer code tested at this commit.

## Deferred by agreement

Actual Windows installation, Windows/Ubuntu restarts, first-user setup interaction, Secure Boot hardware behavior, kernel-upgrade reboot and actual Windows uninstall. Build checks are not evidence that these scenarios work. All tag releases remain prereleases until this acceptance checklist is completed.
