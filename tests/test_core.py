from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from packlight.core import CHECKSUMS_NAME, MANIFEST_NAME, PacklightError, PacklightOptions, build_clean_zip


class PacklightTests(unittest.TestCase):
    def test_verified_builds_clean_verified_zip(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Client Release"
            _write_fixture(source, include_secret=False)
            output = Path(temp_root) / "client-release.zip"

            result = build_clean_zip(PacklightOptions(source=source, output=output, verified=True))

            self.assertTrue(output.is_file())
            self.assertTrue(result.verification.ok)
            self.assertTrue(result.verified)
            self.assertEqual(result.root_name, "Client Release")
            self.assertFalse(result.audit_files)
            self.assertNotIn("audit-files", result.verification.checks)

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

            self.assertEqual({name.split("/", 1)[0] for name in names if name.strip("/")}, {"Client Release"})
            self.assertNotIn(f"Client Release/{MANIFEST_NAME}", names)
            self.assertNotIn(f"Client Release/{CHECKSUMS_NAME}", names)
            self.assertIn("Client Release/README.md", names)
            self.assertIn("Client Release/docs/contract notes.txt", names)
            self.assertNotIn("Client Release/.DS_Store", names)
            self.assertNotIn("Client Release/__MACOSX/ignored", names)
            self.assertNotIn("Client Release/__pycache__/module.pyc", names)
            self.assertNotIn("Client Release/debug.log", names)
            self.assertNotIn("Client Release/old.zip", names)

    def test_audit_files_are_opt_in(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Client Release"
            _write_fixture(source, include_secret=False)
            output = Path(temp_root) / "client-release.zip"

            result = build_clean_zip(PacklightOptions(source=source, output=output, verified=True, audit_files=True))

            self.assertTrue(output.is_file())
            self.assertTrue(result.verification.ok)
            self.assertTrue(result.verified)
            self.assertTrue(result.audit_files)
            self.assertIn("audit-files", result.verification.checks)

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

            self.assertIn(f"Client Release/{MANIFEST_NAME}", names)
            self.assertIn(f"Client Release/{CHECKSUMS_NAME}", names)

    def test_verified_refuses_secret_like_files(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Risky"
            _write_fixture(source, include_secret=True)
            output = Path(temp_root) / "risky.zip"

            with self.assertRaises(PacklightError) as context:
                build_clean_zip(PacklightOptions(source=source, output=output, verified=True))

            self.assertIn(".env", str(context.exception))
            self.assertFalse(output.exists())

    def test_verified_refuses_env_even_when_allowed(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "AllowedRisk"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
            output = Path(temp_root) / "allowed-risk.zip"

            with self.assertRaises(PacklightError) as context:
                build_clean_zip(
                    PacklightOptions(
                        source=source,
                        output=output,
                        verified=True,
                        allow_patterns=(".env",),
                    )
                )

            self.assertIn(".env", str(context.exception))
            self.assertFalse(output.exists())

    def test_verified_refuses_env_even_when_excluded(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "ExcludedRisk"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
            output = Path(temp_root) / "excluded-risk.zip"

            with self.assertRaises(PacklightError) as context:
                build_clean_zip(
                    PacklightOptions(
                        source=source,
                        output=output,
                        verified=True,
                        exclude_patterns=(".env",),
                    )
                )

            self.assertIn(".env", str(context.exception))
            self.assertFalse(output.exists())

    def test_verified_refuses_credential_like_file_even_when_allowed(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "CredentialRisk"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / "secrets").mkdir()
            (source / "secrets" / "client.pem").write_text("private key\n", encoding="utf-8")
            output = Path(temp_root) / "credential-risk.zip"

            with self.assertRaises(PacklightError) as context:
                build_clean_zip(
                    PacklightOptions(
                        source=source,
                        output=output,
                        verified=True,
                        allow_patterns=("secrets/*",),
                    )
                )

            self.assertIn("client.pem", str(context.exception))
            self.assertFalse(output.exists())

    def test_default_mode_skips_secret_like_files_without_failing(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Default"
            _write_fixture(source, include_secret=True)
            output = Path(temp_root) / "default.zip"

            result = build_clean_zip(PacklightOptions(source=source, output=output))

            self.assertTrue(output.exists())
            self.assertIsNone(result.verification)
            self.assertTrue(any(item.rel_path == ".env" and item.risky for item in result.skipped))
            with zipfile.ZipFile(output) as archive:
                self.assertNotIn("Default/.env", archive.namelist())

    def test_python_package_metadata_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Package"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / "src").mkdir()
            (source / "src" / "app.py").write_text("print('clean')\n", encoding="utf-8")
            egg_info = source / "src" / "poa_validator_foundation.egg-info"
            egg_info.mkdir()
            (egg_info / "PKG-INFO").write_text("generated metadata\n", encoding="utf-8")
            dist_info = source / "src" / "poa_validator_foundation-0.1.0.dist-info"
            dist_info.mkdir()
            (dist_info / "WHEEL").write_text("generated metadata\n", encoding="utf-8")
            eggs = source / ".eggs"
            eggs.mkdir()
            (eggs / "dependency.egg").write_text("generated metadata\n", encoding="utf-8")
            wheel_metadata = source / "pip-wheel-metadata"
            wheel_metadata.mkdir()
            (wheel_metadata / "packlight.json").write_text("{}\n", encoding="utf-8")
            (source / "src" / "packlight.egg-link").write_text("../packlight\n", encoding="utf-8")
            output = Path(temp_root) / "package.zip"

            result = build_clean_zip(PacklightOptions(source=source, output=output, verified=True))

            skipped = {item.rel_path: item.rule for item in result.skipped}
            self.assertEqual(skipped["src/poa_validator_foundation.egg-info"], "dev-directory")
            self.assertEqual(skipped["src/poa_validator_foundation-0.1.0.dist-info"], "dev-directory")
            self.assertEqual(skipped[".eggs"], "dev-directory")
            self.assertEqual(skipped["pip-wheel-metadata"], "dev-directory")
            self.assertEqual(skipped["src/packlight.egg-link"], "transient-artifact")
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

            self.assertIn("Package/src/app.py", names)
            self.assertNotIn("Package/src/poa_validator_foundation.egg-info/", names)
            self.assertNotIn("Package/src/poa_validator_foundation.egg-info/PKG-INFO", names)
            self.assertNotIn("Package/src/poa_validator_foundation-0.1.0.dist-info/", names)
            self.assertNotIn("Package/src/poa_validator_foundation-0.1.0.dist-info/WHEEL", names)
            self.assertNotIn("Package/.eggs/", names)
            self.assertNotIn("Package/.eggs/dependency.egg", names)
            self.assertNotIn("Package/pip-wheel-metadata/", names)
            self.assertNotIn("Package/pip-wheel-metadata/packlight.json", names)
            self.assertNotIn("Package/src/packlight.egg-link", names)

    def test_allow_pattern_can_include_intentional_dotfile(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Allowed"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / ".gitignore").write_text("*.zip\n", encoding="utf-8")
            (source / ".well-known").mkdir()
            (source / ".well-known" / "assetlinks.json").write_text("{}\n", encoding="utf-8")
            output = Path(temp_root) / "allowed.zip"

            build_clean_zip(
                PacklightOptions(
                    source=source,
                    output=output,
                    verified=True,
                    allow_patterns=(".gitignore", ".well-known/*"),
                )
            )

            with zipfile.ZipFile(output) as archive:
                self.assertIn("Allowed/.gitignore", archive.namelist())
                self.assertIn("Allowed/.well-known/assetlinks.json", archive.namelist())

    def test_dry_run_does_not_write_zip(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Dry"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            output = Path(temp_root) / "dry.zip"

            result = build_clean_zip(PacklightOptions(source=source, output=output, dry_run=True, verified=True))

            self.assertTrue(result.dry_run)
            self.assertTrue(result.verified)
            self.assertFalse(output.exists())
            self.assertFalse(result.audit_files)
            self.assertEqual([record.rel_path for record in result.files], ["README.md"])

    def test_dry_run_with_audit_files_lists_generated_files(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Dry"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            output = Path(temp_root) / "dry.zip"

            result = build_clean_zip(
                PacklightOptions(source=source, output=output, dry_run=True, verified=True, audit_files=True)
            )

            self.assertTrue(result.dry_run)
            self.assertTrue(result.verified)
            self.assertTrue(result.audit_files)
            self.assertFalse(output.exists())
            self.assertEqual([record.rel_path for record in result.files], ["README.md", MANIFEST_NAME, CHECKSUMS_NAME])

    def test_verified_allows_existing_manifest_names(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Conflict"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / MANIFEST_NAME).write_text("existing manifest\n", encoding="utf-8")
            (source / CHECKSUMS_NAME).write_text("existing checksums\n", encoding="utf-8")
            output = Path(temp_root) / "manifest-names.zip"

            build_clean_zip(PacklightOptions(source=source, output=output, verified=True))

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

            self.assertIn(f"Conflict/{MANIFEST_NAME}", names)
            self.assertIn(f"Conflict/{CHECKSUMS_NAME}", names)

    def test_audit_files_refuse_generated_name_conflicts(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Conflict"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            (source / MANIFEST_NAME).write_text("existing manifest\n", encoding="utf-8")
            output = Path(temp_root) / "conflict.zip"

            with self.assertRaises(PacklightError) as context:
                build_clean_zip(PacklightOptions(source=source, output=output, verified=True, audit_files=True))

            self.assertIn(MANIFEST_NAME, str(context.exception))
            self.assertFalse(output.exists())

    def test_legacy_release_option_still_enables_verified_checks(self):
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Legacy"
            _write_fixture(source, include_secret=True)
            output = Path(temp_root) / "legacy.zip"

            with self.assertRaises(PacklightError) as context:
                build_clean_zip(PacklightOptions(source=source, output=output, release=True))

            self.assertIn(".env", str(context.exception))
            self.assertFalse(output.exists())

    def test_invalid_root_names_raise_packlight_error_without_writing_zip(self):
        invalid_names = ("", "   ", "bad/name", "bad\\name", "bad\nname", ".", "..")
        with tempfile.TemporaryDirectory() as temp_root:
            source = Path(temp_root) / "Root"
            source.mkdir()
            (source / "README.md").write_text("hello\n", encoding="utf-8")

            for root_name in invalid_names:
                output = Path(temp_root) / f"root-{len(root_name)}-{abs(hash(root_name))}.zip"
                with self.subTest(root_name=root_name):
                    with self.assertRaises(PacklightError):
                        build_clean_zip(PacklightOptions(source=source, output=output, root_name=root_name))
                    self.assertFalse(output.exists())


def _write_fixture(root: Path, *, include_secret: bool) -> None:
    root.mkdir(parents=True)
    (root / "README.md").write_text("Release notes\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "contract notes.txt").write_text("recipient material\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('clean')\n", encoding="utf-8")
    unicode_name = "unicode-\\u00e9-name.txt".encode("utf-8").decode("unicode_escape")
    (root / unicode_name).write_text("ok\n", encoding="utf-8")
    (root / ".DS_Store").write_text("finder junk\n", encoding="utf-8")
    (root / "__MACOSX").mkdir()
    (root / "__MACOSX" / "ignored").write_text("metadata\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "module.pyc").write_bytes(b"\0\0")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "debug.log").write_text("trace\n", encoding="utf-8")
    (root / "old.zip").write_bytes(b"PK")
    (root / "notes.tmp").write_text("temp\n", encoding="utf-8")
    if include_secret:
        (root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
