#!/usr/bin/env python3
from __future__ import annotations

import argparse
import plistlib
import shutil
import shlex
import stat
from pathlib import Path


WORKFLOW_BUNDLE_NAME = "Create Packlight ZIP.workflow"
SERVICE_NAME = "Create Packlight ZIP"
WRAPPER_NAME = "create-packlight-zip.sh"
BUNDLE_IDENTIFIER = "org.packlight.create-zip.workflow"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Packlight Finder Quick Action workflow.")
    parser.add_argument("--output", required=True, help="destination .workflow bundle")
    parser.add_argument("--wrapper", help="path to create-packlight-zip.sh")
    parser.add_argument("--packlight-executable", default="", help="explicit packlight executable path")
    parser.add_argument("--python", default="", help="python3 executable to use for module fallback")
    parser.add_argument("--project-root", default="", help="development checkout fallback path")
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    wrapper = Path(args.wrapper).expanduser().resolve() if args.wrapper else script_dir / WRAPPER_NAME
    output = Path(args.output).expanduser()

    if output.name != WORKFLOW_BUNDLE_NAME:
        raise SystemExit(f"workflow must be named {WORKFLOW_BUNDLE_NAME!r}: {output}")
    if not wrapper.is_file():
        raise SystemExit(f"wrapper script not found: {wrapper}")

    build_workflow(
        output=output,
        wrapper=wrapper,
        packlight_executable=args.packlight_executable,
        python=args.python,
        project_root=args.project_root,
    )
    return 0


def build_workflow(
    *,
    output: Path,
    wrapper: Path,
    packlight_executable: str = "",
    python: str = "",
    project_root: str = "",
) -> None:
    if output.exists():
        if not output.is_dir():
            raise SystemExit(f"workflow destination exists and is not a directory: {output}")
        shutil.rmtree(output)

    contents = output / "Contents"
    resources = contents / "Resources"
    resources.mkdir(parents=True)

    installed_wrapper = resources / WRAPPER_NAME
    shutil.copy2(wrapper, installed_wrapper)
    installed_wrapper.chmod(installed_wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (resources / "packlight.conf").write_text(
        _config_text(
            packlight_executable=packlight_executable,
            python=python,
            project_root=project_root,
        ),
        encoding="utf-8",
    )

    _write_plist(contents / "Info.plist", _info_plist())
    _write_plist(contents / "document.wflow", _document_workflow())


def _config_text(*, packlight_executable: str, python: str, project_root: str) -> str:
    return "\n".join(
        [
            "# Written by the Packlight installer.",
            _shell_assignment("PACKLIGHT_EXECUTABLE", packlight_executable),
            _shell_assignment("PACKLIGHT_PYTHON", python),
            _shell_assignment("PACKLIGHT_PROJECT_ROOT", project_root),
            "",
        ]
    )


def _shell_assignment(name: str, value: str) -> str:
    if not value:
        return f"{name}=''"

    home = Path.home()
    try:
        relative = Path(value).expanduser().resolve().relative_to(home)
    except (OSError, ValueError):
        return f"{name}={shlex.quote(value)}"

    escaped = str(relative)
    escaped = escaped.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("$", "\\$")
    escaped = escaped.replace("`", "\\`")
    return f'{name}="$HOME/{escaped}"'


def _info_plist() -> dict[str, object]:
    return {
        "CFBundleDevelopmentRegion": "English",
        "CFBundleIdentifier": BUNDLE_IDENTIFIER,
        "CFBundleName": SERVICE_NAME,
        "CFBundlePackageType": "BNDL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "NSServices": [
            {
                "NSMenuItem": {"default": SERVICE_NAME},
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
                "NSReturnTypes": [],
                "NSSendFileTypes": ["public.folder"],
                "NSSendTypes": ["public.file-url"],
            }
        ],
    }


def _document_workflow() -> dict[str, object]:
    return {
        "AMApplicationBuild": "521",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": False,
                        "Types": ["com.apple.cocoa.path"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": [{"id": "com.apple.Automator", "name": "Automator"}],
                    "AMParameterProperties": {
                        "COMMAND_STRING": {},
                        "CheckedForUserDefaultShell": {},
                        "inputMethod": {},
                        "shell": {},
                        "source": {},
                    },
                    "AMProvides": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": _workflow_shell_script(),
                        "CheckedForUserDefaultShell": True,
                        "inputMethod": 1,
                        "shell": "/bin/zsh",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": False,
                    "Category": ["AMCategoryUtilities"],
                },
                "isViewVisible": True,
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleIDsByPath": {
                "/System/Library/CoreServices/Finder.app": "com.apple.finder"
            },
            "applicationPaths": ["/System/Library/CoreServices/Finder.app"],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "processesInput": True,
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": True,
            "useAutomaticInputType": False,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }


def _workflow_shell_script() -> str:
    return "\n".join(
        [
            "set -euo pipefail",
            'workflow="${PACKLIGHT_WORKFLOW_PATH:-$HOME/Library/Services/Create Packlight ZIP.workflow}"',
            'resources="$workflow/Contents/Resources"',
            'export PACKLIGHT_CONFIG="$resources/packlight.conf"',
            'export PACKLIGHT_FINDER_ACTION=1',
            'exec "$resources/create-packlight-zip.sh" "$@"',
            "",
        ]
    )


def _write_plist(path: Path, value: dict[str, object]) -> None:
    with path.open("wb") as handle:
        plistlib.dump(value, handle, fmt=plistlib.FMT_XML, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
