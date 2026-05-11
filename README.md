# Packlight

Packlight creates ZIP archives from local folders and leaves out common macOS metadata, project clutter, and secret-like files.

It is a small Mac utility for making a ZIP from Finder without first cleaning the folder by hand. The Finder Quick Action is the main interface; the `packlight` CLI uses the same engine.

Packlight uses only the Python standard library at runtime.

## What Packlight Does

- creates a ZIP with one top-level folder
- leaves out macOS metadata such as `.DS_Store`, `__MACOSX`, AppleDouble files, Spotlight state, Trash state, and Finder state
- leaves out common project clutter, caches, logs, temp files, old archive files, and hidden paths unless allowed explicitly
- skips likely secret-like files and symlinks in the standard build
- with `--verified`, stops on likely secret-like files and symlinks before writing the ZIP
- with `--verified`, test-extracts the ZIP before reporting success
- does not add `MANIFEST.txt` or `SHA256SUMS` unless `--audit-files` is used

## Install On Mac

### Quick Install From GitHub

Download the latest source bundle, unpack it, and run the Mac installer:

```bash
cd ~/Downloads
curl -L -o packlight-source.zip https://github.com/packlight-ziptool/packlight/releases/latest/download/packlight-source.zip
unzip -q packlight-source.zip
cd packlight
macos/install-packlight.command
```

Or clone the public repository:

```bash
git clone https://github.com/packlight-ziptool/packlight.git
cd packlight
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

1. In Finder, right-click a folder.
2. Choose Quick Actions or Services.
3. Choose "Create Packlight ZIP".

Packlight creates a ZIP next to the selected folder. If a ZIP already exists there, Packlight replaces it only after the new file is written successfully.

Finder menu placement varies by macOS version and user settings. The action may appear under Quick Actions, under Services, or directly in the contextual menu.

## Use From Terminal

Create a ZIP archive:

```bash
packlight ./handoff --force
```

Create a ZIP with the extra verification pass:

```bash
packlight ./handoff --verified --force
```

The `--verified` flag adds stricter path checks, then test-opens and extracts the ZIP before reporting success. It does not add manifest or checksum files unless you also use `--audit-files`.

Choose an explicit output path with the extra verification pass:

```bash
packlight ./handoff --output ./handoff.zip --verified --force
```

Preview first:

```bash
packlight ./handoff --dry-run --explain
```

Allow an intentional public dotfile:

```bash
packlight ./site --verified --allow .gitignore --allow ".well-known/*"
```

Add audit files only when you explicitly need them:

```bash
packlight ./handoff --verified --audit-files --force
```

Use the module entry point from a checkout:

```bash
python3 -m packlight ./handoff --dry-run --explain
```

Show the default rules:

```bash
packlight --rules
```

## What Packlight Skips

- macOS metadata such as `.DS_Store`, `__MACOSX`, AppleDouble files, Spotlight state, Trash state, and Finder files
- development clutter such as VCS folders, virtualenvs, caches, `node_modules`, and Python bytecode
- transient artifacts such as logs, temp files, backups, and old archive files
- hidden files and folders unless explicitly allowed
- secret-like files and symlinks in default mode

## When Packlight Stops

`--verified` and `--strict` stop if these paths are present:

- `.env`, `.env.*`, `.npmrc`, `.pypirc`, private-key names, certificates, provisioning profiles, and credential-like suffixes such as `.pem`, `.key`, `.p12`, `.pfx`, `.cer`, and `.crt`
- symlinks
- unsafe root folder names such as empty names, `.`, `..`, names with path separators, or names with control characters
- `MANIFEST.txt` or `SHA256SUMS` conflicts when `--audit-files` is used
- ZIP verification or extraction failures
- checksum verification failures when `--audit-files` is used

User `--allow` patterns can restore benign hidden paths such as `.gitignore` or `.well-known/*`, but `--verified` and `--strict` still stop on likely secrets and symlinks. These files cannot be hidden with `--allow` or `--exclude`.

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

If the Quick Action does not appear immediately, open System Settings and check Keyboard > Keyboard Shortcuts > Services, or log out and back in. Finder sometimes refreshes Services lazily.

If Finder can run Packlight but Terminal says `packlight: command not found`, add the Python user scripts directory to your shell `PATH`:

```bash
USER_BIN="$(python3 -m site --user-base)/bin"
export PATH="$USER_BIN:$PATH"
packlight --version
```

If the Quick Action says Packlight is not installed, run `macos/install-packlight.command` again. Finder has a smaller `PATH` than many Terminal sessions, so the workflow stores an explicit command path during installation.

If Packlight stops because of `.env` files, keys, certificates, provisioning profiles, or symlinks, the Finder Quick Action should show a readable message and leave any existing ZIP in place. Remove those files from the folder you are zipping or build a different folder for sharing. `--verified` stops on those paths even if they match `--allow` or `--exclude`.

If Finder appears stuck after Packlight stops, relaunch Finder and report an issue with the folder name, macOS version, and any message you saw.

Exact Finder menu placement varies by macOS version and user settings. Look under Quick Actions and Services.

## Developer Verification

Run the unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Run the local verification loop:

```bash
./scripts/release-loop packlight
```

The loop builds an intentionally messy fixture, creates a ZIP, checks archive entries, test-extracts it, confirms audit files are not added by default, and writes ignored report artifacts under `reports/`.

Finder GUI verification is a manual check: run `macos/install-packlight.command`, confirm `~/Library/Services/Create Packlight ZIP.workflow` exists, then right-click a real folder in Finder and choose "Create Packlight ZIP" from Quick Actions or Services.

## License

Apache-2.0. See `LICENSE`.
