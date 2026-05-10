# Packlight

Packlight creates clean, recipient-ready ZIP archives from local folders, leaving out common metadata, transient clutter, and risky file types.

Packlight is built for macOS users who want to Control-click or right-click a folder in Finder and create a ZIP that omits macOS metadata, hidden files, transient artifacts, and secret-like files. The Finder Quick Action is the V1 user experience; the `packlight` CLI remains the underlying engine.

Packlight uses only the Python standard library at runtime.

## What Packlight Does

- creates a single-root ZIP archive from a selected folder
- skips macOS metadata such as `.DS_Store`, `__MACOSX`, AppleDouble files, Spotlight state, Trash state, and Finder state
- skips development clutter, caches, transient files, old archive files, and hidden paths unless allowed explicitly
- refuses release-mode archives when risky files such as `.env`, keys, certificates, provisioning profiles, or symlinks are present
- adds `MANIFEST.txt` and `SHA256SUMS` in release mode, then verifies the archive

## Install On Mac

Download or clone Packlight, then run the installer:

```bash
macos/install-packlight.command
```

You can also double-click `macos/install-packlight.command` in Finder.

The installer:

- installs the Python package with `python3 -m pip install --user .`
- installs the user-facing `packlight` command
- creates `~/Library/Services` if needed
- installs `~/Library/Services/Create Packlight ZIP.workflow`
- configures the Finder Quick Action to find the installed command even when Finder has a smaller `PATH` than Terminal

If Python installs scripts into a directory that is not on `PATH`, the installer prints a warning. The Finder Quick Action still uses the configured command path, but Terminal may need a `PATH` update before `packlight` works directly.

## Use From Finder

1. In Finder, Control-click or right-click a folder.
2. Choose Quick Actions or Services.
3. Choose "Create Packlight ZIP".

Packlight creates a release-mode ZIP next to the selected folder and replaces an existing ZIP at that destination only after the new archive passes its checks. If Packlight stops because risky files are present, the existing ZIP is not replaced.

Finder menu placement varies by macOS version and user settings. The action may appear under Quick Actions, under Services, or directly in the contextual menu.

## Use From Terminal

Create a recipient-ready ZIP archive:

```bash
packlight ./my-release --release --force
```

Choose an explicit output path:

```bash
packlight ./my-release --output ./my-release.zip --release --force
```

Preview first:

```bash
packlight ./my-release --dry-run --explain
```

Allow an intentional public dotfile:

```bash
packlight ./site --release --allow .gitignore --allow ".well-known/*"
```

Use the module entry point from a checkout:

```bash
python3 -m packlight ./handoff --dry-run --explain
```

Show the default rules:

```bash
packlight --rules
```

## What Packlight Leaves Out

- macOS metadata such as `.DS_Store`, `__MACOSX`, AppleDouble files, Spotlight state, Trash state, and Finder state files
- development clutter such as VCS folders, virtualenvs, caches, `node_modules`, and Python bytecode
- transient artifacts such as logs, temp files, backups, and old archive files
- hidden files and folders unless explicitly allowed
- secret-like files and symlinks in default mode

## What Makes Packlight Stop

Release and strict modes refuse to build if risky paths are present, including:

- `.env`, `.env.*`, `.npmrc`, `.pypirc`, private-key names, certificates, provisioning profiles, and credential-like suffixes such as `.pem`, `.key`, `.p12`, `.pfx`, `.cer`, and `.crt`
- symlinks
- unsafe root folder names such as empty names, `.`, `..`, names with path separators, or names with control characters
- generated release-file conflicts with `MANIFEST.txt` or `SHA256SUMS`
- ZIP verification, extraction, manifest, or checksum failures

User `--allow` patterns can restore benign hidden paths such as `.gitignore` or `.well-known/*`, but release and strict modes still refuse risky files if they are present in the source tree. Risky files cannot be hidden with `--allow` or `--exclude`.

## Uninstall

Run:

```bash
macos/uninstall-packlight.command
```

The uninstaller removes:

```text
~/Library/Services/Create Packlight ZIP.workflow
```

If the script is running interactively, it asks before uninstalling the Python package. To remove the package manually:

```bash
python3 -m pip uninstall packlight
```

## Troubleshooting

If the Quick Action does not appear immediately, open System Settings and check Keyboard > Keyboard Shortcuts > Services, or log out and back in. Finder sometimes refreshes Services after a delay.

If Finder can run Packlight but Terminal says `packlight: command not found`, add the Python user scripts directory to your shell `PATH`:

```bash
USER_BIN="$(python3 -m site --user-base)/bin"
export PATH="$USER_BIN:$PATH"
packlight --version
```

If the Quick Action says Packlight is not installed, run `macos/install-packlight.command` again. Finder has a smaller `PATH` than many Terminal sessions, so the workflow stores an explicit command path during installation.

If Packlight stops because of risky files such as `.env`, keys, certificates, provisioning profiles, or symlinks, the Finder Quick Action should show a readable message and leave any existing ZIP in place. Remove those files from the folder you are sending, or build a separate handoff folder. Release mode refuses those paths even if they match `--allow` or `--exclude`.

If Finder does not refresh after Packlight stops, relaunch Finder and report an issue with the folder name, macOS version, and any message you saw.

Exact Finder menu placement varies by macOS version and user settings. Look under Quick Actions and Services.

## Developer Verification

Run the unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Run the local release loop:

```bash
./scripts/release-loop packlight
```

The loop builds an intentionally messy fixture, creates a release ZIP, verifies archive entries, test-extracts it, checks manifest/checksum behavior, and writes ignored report artifacts under `reports/`.

Finder GUI verification is a manual release step: run `macos/install-packlight.command`, confirm `~/Library/Services/Create Packlight ZIP.workflow` exists, then Control-click or right-click a real folder in Finder and choose "Create Packlight ZIP" from Quick Actions or Services.

## License

Apache-2.0. See `LICENSE`.
