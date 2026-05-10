from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.loop import _public_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Build marker strings from fragments so this source file does not contain
# the forbidden literals it scans for.
def _forbidden_markers():
    return (
        "Clean" + "Zip",
        "clean" + "zip",
        "CLEAN" + "ZIP",
        "Next" + "stead",
        "next" + "stead",
        "/" + "Users" + "/" + "c",
        "Her" + "mes",
        "next" + "stead" + "/" + "product",
    )


class PacklightReleaseSurfaceTests(unittest.TestCase):
    def test_module_entrypoints_use_packlight(self):
        for flag in ("--version", "--help", "--rules"):
            with self.subTest(flag=flag):
                completed = subprocess.run(
                    [sys.executable, "-m", "packlight", flag],
                    cwd=PROJECT_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                combined = completed.stdout + completed.stderr
                self.assertNotIn("Clean" + "Zip", combined)
                self.assertNotIn("clean" + "zip", combined)

        version = subprocess.run(
            [sys.executable, "-m", "packlight", "--version"],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertIn("packlight", version.stdout)

    def test_help_uses_recipient_ready_positioning(self):
        completed = subprocess.run(
            [sys.executable, "-m", "packlight", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("packlight", completed.stdout)
        self.assertIn("recipient-ready ZIP archives", completed.stdout)

    def test_finder_wrapper_uses_packlight_command_and_env(self):
        script = (PROJECT_ROOT / "macos" / "create-packlight-zip.sh").read_text(encoding="utf-8")
        self.assertIn("PACKLIGHT_EXECUTABLE", script)
        self.assertIn("PACKLIGHT_FINDER_ACTION", script)
        self.assertIn("command -v packlight", script)
        self.assertIn("PACKLIGHT_PROJECT_ROOT", script)
        self.assertIn("-m packlight", script)
        self.assertIn("--release --force", script)
        self.assertIn("/usr/bin/osascript", script)
        self.assertIn("Packlight could not create the ZIP", script)
        self.assertIn("risky files", script)
        self.assertNotIn("CLEAN" + "ZIP_PROJECT_ROOT", script)
        self.assertNotIn("clean" + "zip", script)

    def test_installer_and_uninstaller_use_packlight_names(self):
        for relative_path in (
            "macos/install-packlight.command",
            "macos/uninstall-packlight.command",
        ):
            with self.subTest(path=relative_path):
                text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("Packlight", text)
                self.assertIn("packlight", text)
                self.assertIn("Create Packlight ZIP.workflow", text)
                for marker in _forbidden_markers():
                    self.assertNotIn(marker, text)

    def test_quick_action_generator_uses_packlight_names(self):
        text = (PROJECT_ROOT / "macos" / "build-quick-action.py").read_text(encoding="utf-8")
        self.assertIn("Create Packlight ZIP.workflow", text)
        self.assertIn("Create Packlight ZIP", text)
        self.assertIn("PACKLIGHT_EXECUTABLE", text)
        self.assertIn("PACKLIGHT_PROJECT_ROOT", text)
        for marker in _forbidden_markers():
            self.assertNotIn(marker, text)

    def test_checked_in_finder_workflow_is_packlight_quick_action(self):
        workflow = PROJECT_ROOT / "macos" / "Create Packlight ZIP.workflow"
        info_path = workflow / "Contents" / "Info.plist"
        document_path = workflow / "Contents" / "document.wflow"
        wrapper_path = workflow / "Contents" / "Resources" / "create-packlight-zip.sh"
        config_path = workflow / "Contents" / "Resources" / "packlight.conf"

        self.assertTrue(info_path.is_file())
        self.assertTrue(document_path.is_file())
        self.assertTrue(wrapper_path.is_file())
        self.assertTrue(config_path.is_file())

        info = plistlib.loads(info_path.read_bytes())
        service = info["NSServices"][0]
        self.assertEqual(service["NSMenuItem"]["default"], "Create Packlight ZIP")
        self.assertIn("public.folder", service["NSSendFileTypes"])
        self.assertEqual(service["NSRequiredContext"]["NSApplicationIdentifier"], "com.apple.finder")

        document = plistlib.loads(document_path.read_bytes())
        action = document["actions"][0]["action"]
        parameters = action["ActionParameters"]
        self.assertEqual(action["BundleIdentifier"], "com.apple.RunShellScript")
        self.assertEqual(parameters["shell"], "/bin/zsh")
        self.assertEqual(parameters["inputMethod"], 1)
        self.assertIn("create-packlight-zip.sh", parameters["COMMAND_STRING"])
        self.assertIn("packlight.conf", parameters["COMMAND_STRING"])
        self.assertIn("PACKLIGHT_FINDER_ACTION=1", parameters["COMMAND_STRING"])

        config = config_path.read_text(encoding="utf-8")
        self.assertIn("PACKLIGHT_EXECUTABLE", config)
        self.assertIn("PACKLIGHT_PROJECT_ROOT", config)
        self.assertEqual(
            wrapper_path.read_text(encoding="utf-8"),
            (PROJECT_ROOT / "macos" / "create-packlight-zip.sh").read_text(encoding="utf-8"),
        )

    def test_docs_make_installer_the_primary_finder_path(self):
        docs = "\n".join(
            [
                (PROJECT_ROOT / "README.md").read_text(encoding="utf-8"),
                (PROJECT_ROOT / "docs" / "FINDER_QUICK_ACTION.md").read_text(encoding="utf-8"),
            ]
        )
        self.assertIn("macos/install-packlight.command", docs)
        self.assertIn("Create Packlight ZIP.workflow", docs)
        self.assertIn("Quick Actions or Services", docs)
        self.assertNotIn("under Compress", docs)
        self.assertNotIn("under macOS Compress", docs)

    def test_shell_scripts_pass_zsh_syntax_check(self):
        zsh = shutil.which("zsh")
        if not zsh:
            self.skipTest("zsh is not available")

        for relative_path in (
            "macos/create-packlight-zip.sh",
            "macos/install-packlight.command",
            "macos/uninstall-packlight.command",
        ):
            with self.subTest(path=relative_path):
                completed = subprocess.run(
                    [zsh, "-n", str(PROJECT_ROOT / relative_path)],
                    cwd=PROJECT_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_finder_wrapper_runs_with_limited_path(self):
        zsh = shutil.which("zsh")
        if not zsh:
            self.skipTest("zsh is not available")

        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Finder Test Ω"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / "nested").mkdir()
            (source / "nested" / "file.txt").write_text("nested\n", encoding="utf-8")
            (source / "unicode").mkdir()
            (source / "unicode" / "résumé.txt").write_text("unicode\n", encoding="utf-8")
            (source / ".DS_Store").write_text("finder\n", encoding="utf-8")
            (source / "old.zip").write_bytes(b"PK")

            env = {
                "HOME": str(Path.home()),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "PACKLIGHT_PYTHON": sys.executable,
                "PACKLIGHT_PROJECT_ROOT": str(PROJECT_ROOT),
            }
            completed = subprocess.run(
                [zsh, str(PROJECT_ROOT / "macos" / "create-packlight-zip.sh"), str(source)],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            output = source.with_suffix(".zip")
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

            self.assertEqual({name.split("/", 1)[0] for name in names if name.strip("/")}, {"Finder Test Ω"})
            self.assertIn("Finder Test Ω/README.md", names)
            self.assertIn("Finder Test Ω/nested/file.txt", names)
            self.assertIn("Finder Test Ω/unicode/résumé.txt", names)
            self.assertIn("Finder Test Ω/MANIFEST.txt", names)
            self.assertIn("Finder Test Ω/SHA256SUMS", names)
            self.assertNotIn("Finder Test Ω/.DS_Store", names)
            self.assertNotIn("Finder Test Ω/old.zip", names)

    def test_direct_wrapper_failure_returns_nonzero_and_keeps_existing_zip(self):
        zsh = shutil.which("zsh")
        if not zsh:
            self.skipTest("zsh is not available")

        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Finder Test"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / ".env").write_text("SECRET=1\n", encoding="utf-8")
            output = source.with_suffix(".zip")
            original_zip = b"existing good zip"
            output.write_bytes(original_zip)

            env = {
                "HOME": str(Path.home()),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "PACKLIGHT_PYTHON": sys.executable,
                "PACKLIGHT_PROJECT_ROOT": str(PROJECT_ROOT),
            }
            completed = subprocess.run(
                [zsh, str(PROJECT_ROOT / "macos" / "create-packlight-zip.sh"), str(source)],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )

            combined = completed.stdout + completed.stderr
            self.assertEqual(completed.returncode, 1, combined)
            self.assertIn("risky files were found", combined)
            self.assertIn(".env: secret-like configuration file", combined)
            self.assertEqual(output.read_bytes(), original_zip)

    def test_finder_gui_mode_failure_returns_zero_and_keeps_existing_zip(self):
        zsh = shutil.which("zsh")
        if not zsh:
            self.skipTest("zsh is not available")

        with tempfile.TemporaryDirectory() as temp_root:
            good_source = Path(temp_root) / "Good Folder"
            risky_source = Path(temp_root) / "Risky Folder"
            good_source.mkdir()
            risky_source.mkdir()
            (good_source / "README.md").write_text("good\n", encoding="utf-8")
            (risky_source / "README.md").write_text("risky\n", encoding="utf-8")
            (risky_source / ".env").write_text("SECRET=1\n", encoding="utf-8")
            risky_output = risky_source.with_suffix(".zip")
            original_zip = b"existing good zip"
            risky_output.write_bytes(original_zip)

            env = {
                "HOME": str(Path.home()),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "PACKLIGHT_PYTHON": sys.executable,
                "PACKLIGHT_PROJECT_ROOT": str(PROJECT_ROOT),
                "PACKLIGHT_FINDER_ACTION": "1",
                "PACKLIGHT_SUPPRESS_ALERT": "1",
            }
            completed = subprocess.run(
                [
                    zsh,
                    str(PROJECT_ROOT / "macos" / "create-packlight-zip.sh"),
                    str(good_source),
                    str(risky_source),
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )

            combined = completed.stdout + completed.stderr
            self.assertEqual(completed.returncode, 0, combined)
            self.assertIn("Packlight could not create the ZIP", combined)
            self.assertIn("Packlight stopped because risky files were found", combined)
            self.assertIn("No ZIP was created or replaced", combined)
            self.assertIn("risky files were found", combined)
            self.assertIn(".env: secret-like configuration file", combined)
            self.assertTrue(good_source.with_suffix(".zip").is_file())
            self.assertEqual(risky_output.read_bytes(), original_zip)

    def test_public_source_has_no_old_branding(self):
        excluded_dirs = {".git", ".venv", "__pycache__", "build", "dist", "reports"}
        forbidden_markers = _forbidden_markers()
        hits = []
        for path in PROJECT_ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in excluded_dirs or part.endswith(".egg-info") for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for marker in forbidden_markers:
                if marker in text:
                    hits.append(f"{path.relative_to(PROJECT_ROOT)}: {marker}")

        self.assertEqual(hits, [])

    def test_loop_report_text_sanitizes_local_paths(self):
        text = " ".join(
            [
                str(PROJECT_ROOT / "reports" / "latest-loop.json"),
                sys.executable,
                tempfile.gettempdir(),
                str(Path(tempfile.gettempdir()).resolve()),
            ]
        )
        public = _public_text(text)
        self.assertNotIn(str(PROJECT_ROOT), public)
        self.assertNotIn(sys.executable, public)
        self.assertNotIn(tempfile.gettempdir(), public)
        self.assertNotIn(str(Path(tempfile.gettempdir()).resolve()), public)


if __name__ == "__main__":
    unittest.main()
