# Finder Quick Action

Packlight V1 uses a Finder Quick Action backed by the same `packlight` CLI engine used in Terminal.

## Normal Install

Run the installer from a downloaded or cloned checkout:

```bash
macos/install-packlight.command
```

The installer:

- installs Packlight with `python3 -m pip install --user .`
- installs `~/Library/Services/Create Packlight ZIP.workflow`
- writes a workflow configuration pointing at the discovered `packlight` command
- keeps the Automator setup out of the normal user path

Confirm the workflow exists:

```bash
test -d "$HOME/Library/Services/Create Packlight ZIP.workflow"
```

## Use In Finder

1. Right-click a folder in Finder.
2. Choose Quick Actions or Services.
3. Choose "Create Packlight ZIP".

The Quick Action creates a release-mode ZIP next to each selected folder and replaces any existing ZIP at that destination only after the new ZIP passes its checks. If Packlight stops because risky files are present, the existing ZIP is not replaced.

Finder menu placement varies by macOS version and user settings. The action may appear under Quick Actions, under Services, or directly in the contextual menu.

## Command Discovery

The workflow runs `macos/create-packlight-zip.sh`. The wrapper chooses the Packlight command in this order:

1. explicit `PACKLIGHT_EXECUTABLE` written by the installer into the workflow configuration
2. installed `packlight` found on the workflow `PATH`
3. `python3 -m packlight`, only when the module is importable
4. `PACKLIGHT_PROJECT_ROOT` for development checkouts

The wrapper seeds `PATH` with common macOS install locations, including the Python user scripts directory, `/usr/local/bin`, and `/opt/homebrew/bin`.

## Behavior

- receives folders from Finder
- supports multiple selected folders
- rejects selected non-folders with readable messages
- uses `--release --force`
- includes `MANIFEST.txt` and `SHA256SUMS`
- verifies the ZIP before returning success
- refuses risky files such as `.env`, keys, certificates, provisioning profiles, and symlinks in release mode
- shows a readable Finder alert when Packlight stops because risky files are present
- returns control to Finder after showing the alert, while direct Terminal wrapper runs still return nonzero on failure

## Troubleshooting

If Packlight stops because of risky files such as `.env`, keys, certificates, provisioning profiles, or symlinks, remove those files from the folder you are sending or build a different handoff folder. Finder should show a readable message, and existing good ZIPs are not replaced when Packlight stops.

If Finder appears stuck after Packlight stops, relaunch Finder and report an issue with the folder name, macOS version, and any message you saw.

Exact Finder menu placement varies by macOS version and user settings. Look under Quick Actions and Services.

## Manual Or Developer Setup

The installer is the supported V1 path. Manual setup is useful only when editing the workflow during development.

1. Open Automator.
2. Create a new Quick Action.
3. Set "Workflow receives current" to "folders" in "Finder".
4. Add "Run Shell Script".
5. Set "Shell" to `/bin/zsh` and "Pass input" to "as arguments".
6. Use `macos/create-packlight-zip.sh` as the shell body, or invoke that wrapper from a generated workflow.
7. Save as "Create Packlight ZIP".

For local checkout testing without installing the package, set `PACKLIGHT_PROJECT_ROOT` to the checkout before invoking the wrapper.

## Manual Finder Test

Finder and Automator should be verified manually after installation because Services refresh timing and contextual menu placement vary by macOS version and user settings.

Recommended release check:

1. Run `macos/install-packlight.command`.
2. Confirm `~/Library/Services/Create Packlight ZIP.workflow` exists.
3. Right-click a test folder in Finder.
4. Choose "Create Packlight ZIP" from Quick Actions or Services.
5. Confirm the ZIP appears next to the folder and opens with a single top-level folder.
