from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    if argv != ["packlight"]:
        print("Usage: ./scripts/release-loop packlight", file=sys.stderr)
        return 2

    REPORTS_DIR.mkdir(exist_ok=True)
    report = {
        "project": "packlight",
        "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "steps": [],
    }

    tests = _run_step([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    report["steps"].append(tests)
    if tests["returncode"] != 0:
        return _finish(report, 1)

    with tempfile.TemporaryDirectory(prefix="packlight-loop-") as temp_root:
        temp_root_path = Path(temp_root)
        fixture = temp_root_path / "Loop Fixture"
        _write_ugly_fixture(fixture)
        output = REPORTS_DIR / "latest-demo.zip"
        if output.exists():
            output.unlink()

        build = _run_step(
            [
                sys.executable,
                "-m",
                "packlight",
                str(fixture),
                "--output",
                str(output),
                "--verified",
                "--force",
                "--json",
            ]
        )
        report["steps"].append(build)
        if build["returncode"] != 0:
            return _finish(report, 1)

        inspect = _inspect_zip(output)
        report["steps"].append(inspect)
        if inspect["returncode"] != 0:
            return _finish(report, 1)

    return _finish(report, 0)


def _run_step(command):
    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "name": _public_text(" ".join(command)),
        "returncode": completed.returncode,
        "stdout": _public_text(completed.stdout),
        "stderr": _public_text(completed.stderr),
    }


def _inspect_zip(output: Path):
    errors = []
    entries = []
    try:
        with zipfile.ZipFile(output) as archive:
            entries = archive.namelist()
            forbidden_markers = [".DS_Store", "__MACOSX", "__pycache__", ".git", ".env", "debug.log", "old.zip"]
            for entry in entries:
                if any(marker in entry for marker in forbidden_markers):
                    errors.append(f"Forbidden entry survived: {entry}")
            roots = {entry.split("/", 1)[0] for entry in entries if entry.strip("/")}
            if roots != {"Loop Fixture"}:
                errors.append(f"Unexpected top-level roots: {sorted(roots)}")
            if "Loop Fixture/MANIFEST.txt" in entries:
                errors.append("Unexpected manifest")
            if "Loop Fixture/SHA256SUMS" in entries:
                errors.append("Unexpected checksums")
    except Exception as error:  # pragma: no cover - loop reporting path
        errors.append(str(error))

    return {
        "name": _public_text(f"inspect {output}"),
        "returncode": 1 if errors else 0,
        "stdout": json.dumps({"entries": entries}, indent=2),
        "stderr": _public_text("\n".join(errors)),
    }


def _finish(report, code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report["ok"] = code == 0
    report_path = REPORTS_DIR / "latest-loop.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    public_report_path = _public_text(str(report_path))
    if code == 0:
        print(f"Packlight loop passed. Report: {public_report_path}")
    else:
        print(f"Packlight loop failed. Report: {public_report_path}", file=sys.stderr)
        for step in report["steps"]:
            if step["returncode"] != 0:
                print(step["stderr"], file=sys.stderr)
                break
    return code


def _write_ugly_fixture(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / "README.md").write_text("Loop fixture\n", encoding="utf-8")
    (root / "customer demo.txt").write_text("ship this\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "terms.txt").write_text("terms\n", encoding="utf-8")
    (root / ".DS_Store").write_text("finder\n", encoding="utf-8")
    (root / "__MACOSX").mkdir()
    (root / "__MACOSX" / "sidecar").write_text("junk\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "module.pyc").write_bytes(b"\0")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "debug.log").write_text("debug\n", encoding="utf-8")
    (root / "old.zip").write_bytes(b"PK")
    (root / "notes.tmp").write_text("tmp\n", encoding="utf-8")


def _public_text(value: str) -> str:
    replacements = {
        str(PROJECT_ROOT): "<project-root>",
        sys.executable: "<python>",
        tempfile.gettempdir(): "<temp-dir>",
        os.path.realpath(tempfile.gettempdir()): "<temp-dir>",
    }
    for local_path, public_name in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        value = value.replace(local_path, public_name)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
