from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .rules import Decision, decide_path


ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
MANIFEST_NAME = "MANIFEST.txt"
CHECKSUMS_NAME = "SHA256SUMS"


class PacklightError(Exception):
    """Raised when Packlight refuses to produce an invalid artifact."""


@dataclass(frozen=True)
class PacklightOptions:
    source: Path
    output: Optional[Path] = None
    root_name: Optional[str] = None
    verified: bool = False
    release: bool = False
    audit_files: bool = False
    strict: bool = False
    dry_run: bool = False
    force: bool = False
    allow_patterns: Tuple[str, ...] = ()
    exclude_patterns: Tuple[str, ...] = ()

    @property
    def verified_effective(self) -> bool:
        return self.verified or self.release or self.audit_files

    @property
    def strict_effective(self) -> bool:
        return self.strict or self.verified_effective


@dataclass
class FileRecord:
    rel_path: str
    size: int
    sha256: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {"path": self.rel_path, "size": self.size, "sha256": self.sha256}


@dataclass
class SourceFile:
    source_path: Path
    rel_path: str
    size: int


@dataclass
class SkippedItem:
    rel_path: str
    reason: str
    rule: str
    risky: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.rel_path,
            "reason": self.reason,
            "rule": self.rule,
            "risky": self.risky,
        }


@dataclass
class VerificationResult:
    ok: bool
    checks: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {"ok": self.ok, "checks": self.checks, "errors": self.errors}


@dataclass
class BuildResult:
    source: str
    output: Optional[str]
    root_name: str
    verified: bool
    release: bool
    audit_files: bool
    dry_run: bool
    files: List[FileRecord]
    skipped: List[SkippedItem]
    verification: Optional[VerificationResult] = None

    @property
    def total_bytes(self) -> int:
        return sum(record.size for record in self.files)

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "output": self.output,
            "root_name": self.root_name,
            "verified": self.verified,
            "release": self.release,
            "audit_files": self.audit_files,
            "dry_run": self.dry_run,
            "file_count": len(self.files),
            "total_bytes": self.total_bytes,
            "files": [record.to_dict() for record in self.files],
            "skipped": [item.to_dict() for item in self.skipped],
            "verification": self.verification.to_dict() if self.verification else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass
class ScanResult:
    files: List[SourceFile]
    dirs: List[str]
    skipped: List[SkippedItem]


def build_clean_zip(options: PacklightOptions) -> BuildResult:
    try:
        return _build_clean_zip(options)
    except PacklightError:
        raise
    except OSError as error:
        raise PacklightError(f"Filesystem error while building ZIP: {error}") from error
    except zipfile.BadZipFile as error:
        raise PacklightError(f"ZIP verification failed: {error}") from error


def _build_clean_zip(options: PacklightOptions) -> BuildResult:
    source = options.source.expanduser().resolve()
    if not source.exists():
        raise PacklightError(f"Source does not exist: {source}")
    if not source.is_dir():
        raise PacklightError(f"Source must be a directory: {source}")

    root_name = _resolve_root_name(source, options.root_name)
    output = _resolve_output_path(source, options.output)
    verified = options.verified_effective

    if output and output.exists() and not options.force and not options.dry_run:
        raise PacklightError(f"Output already exists. Re-run with --force to replace it: {output}")

    scan = scan_source(source, options)
    risky = [item for item in scan.skipped if item.risky]
    if options.strict_effective and risky:
        details = "\n".join(f"- {item.rel_path}: {item.reason}" for item in risky[:20])
        more = "" if len(risky) <= 20 else f"\n...and {len(risky) - 20} more"
        raise PacklightError(f"Refusing to build because risky files were found:\n{details}{more}")

    if options.audit_files:
        generated_conflicts = sorted(
            item.rel_path for item in scan.files if item.rel_path in {MANIFEST_NAME, CHECKSUMS_NAME}
        )
        if generated_conflicts:
            names = ", ".join(generated_conflicts)
            raise PacklightError(f"Audit files reserve generated file name(s): {names}")

    if not scan.files:
        raise PacklightError("No files would be included in the ZIP.")

    planned_records = [
        FileRecord(rel_path=item.rel_path, size=item.size, sha256="")
        for item in scan.files
    ]
    if options.audit_files:
        planned_records.extend(
            [
                FileRecord(rel_path=MANIFEST_NAME, size=0, sha256=""),
                FileRecord(rel_path=CHECKSUMS_NAME, size=0, sha256=""),
            ]
        )

    if options.dry_run:
        return BuildResult(
            source=str(source),
            output=str(output) if output else None,
            root_name=root_name,
            verified=verified,
            release=verified,
            audit_files=options.audit_files,
            dry_run=True,
            files=planned_records,
            skipped=scan.skipped,
            verification=None,
        )

    with tempfile.TemporaryDirectory(prefix="packlight-stage-") as temp_root:
        staging_parent = Path(temp_root)
        staging_root = staging_parent / root_name
        staging_root.mkdir(parents=True)

        for rel_dir in scan.dirs:
            (staging_root / rel_dir).mkdir(parents=True, exist_ok=True)

        payload_records = _copy_payload(scan.files, staging_root)
        final_records = list(payload_records)

        if options.audit_files:
            manifest_record = _write_manifest(staging_root, root_name, payload_records)
            final_records.append(manifest_record)
            checksums_record = _write_checksums(staging_root, final_records)
            final_records.append(checksums_record)

        _write_zip(staging_root, output, root_name)
        verification = None
        if verified:
            verification = verify_zip(
                output,
                expected_root=root_name,
                audit_files=options.audit_files,
                allow_patterns=options.allow_patterns,
                exclude_patterns=options.exclude_patterns,
            )
            if not verification.ok:
                raise PacklightError("Verification failed:\n" + "\n".join(verification.errors))

    return BuildResult(
        source=str(source),
        output=str(output),
        root_name=root_name,
        verified=verified,
        release=verified,
        audit_files=options.audit_files,
        dry_run=False,
        files=final_records,
        skipped=scan.skipped,
        verification=verification,
    )


def scan_source(source: Path, options: PacklightOptions) -> ScanResult:
    files: List[SourceFile] = []
    dirs: List[str] = []
    skipped: List[SkippedItem] = []

    for current_root, dir_names, file_names in os.walk(
        source,
        topdown=True,
        followlinks=False,
        onerror=_raise_walk_error,
    ):
        current = Path(current_root)
        kept_dirs = []

        for dir_name in sorted(dir_names):
            full_path = current / dir_name
            rel_path = _relative_posix(full_path, source)
            if full_path.is_symlink():
                skipped.append(SkippedItem(rel_path, "symlinked directory", "symlink", risky=True))
                continue

            decision = decide_path(
                rel_path,
                is_dir=True,
                allow_patterns=options.allow_patterns,
                exclude_patterns=options.exclude_patterns,
            )
            if decision.is_include:
                kept_dirs.append(dir_name)
                dirs.append(rel_path)
            else:
                skipped.append(_skipped_from_decision(rel_path, decision))

        dir_names[:] = kept_dirs

        for file_name in sorted(file_names):
            full_path = current / file_name
            rel_path = _relative_posix(full_path, source)
            if full_path.is_symlink():
                skipped.append(SkippedItem(rel_path, "symlinked file", "symlink", risky=True))
                continue

            decision = decide_path(
                rel_path,
                is_dir=False,
                allow_patterns=options.allow_patterns,
                exclude_patterns=options.exclude_patterns,
            )
            if decision.is_include:
                files.append(SourceFile(full_path, rel_path, full_path.stat().st_size))
            else:
                skipped.append(_skipped_from_decision(rel_path, decision))

    files.sort(key=lambda item: item.rel_path)
    dirs.sort()
    skipped.sort(key=lambda item: item.rel_path)
    return ScanResult(files=files, dirs=dirs, skipped=skipped)


def verify_zip(
    zip_path: Path,
    *,
    expected_root: str,
    audit_files: bool = False,
    release: Optional[bool] = None,
    allow_patterns: Sequence[str] = (),
    exclude_patterns: Sequence[str] = (),
) -> VerificationResult:
    if release is not None:
        audit_files = release

    checks: List[str] = []
    errors: List[str] = []

    if not zip_path.exists():
        return VerificationResult(False, errors=[f"ZIP was not created: {zip_path}"])

    with zipfile.ZipFile(zip_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member:
            errors.append(f"ZIP integrity check failed at {bad_member}")
        else:
            checks.append("zip-integrity")

        names = archive.namelist()
        top_levels = _top_level_names(names)
        if top_levels == {expected_root}:
            checks.append("single-root-folder")
        else:
            errors.append(f"Expected one top-level folder {expected_root!r}, found {sorted(top_levels)!r}")

        for name in names:
            entry_error = _validate_zip_entry_name(name)
            if entry_error:
                errors.append(entry_error)
                continue
            rel_inside_root = _strip_root(name, expected_root)
            if not rel_inside_root:
                continue
            decision = decide_path(
                rel_inside_root,
                is_dir=name.endswith("/"),
                allow_patterns=allow_patterns,
                exclude_patterns=exclude_patterns,
            )
            generated = rel_inside_root in {MANIFEST_NAME, CHECKSUMS_NAME}
            if not generated and not decision.is_include:
                errors.append(f"Forbidden ZIP entry survived: {name} ({decision.reason})")

        if errors:
            return VerificationResult(False, checks=checks, errors=errors)

        with tempfile.TemporaryDirectory(prefix="packlight-extract-") as temp_root:
            extract_root = Path(temp_root)
            _safe_extract(archive, extract_root)
            checks.append("test-extract")

            package_root = extract_root / expected_root
            if not package_root.is_dir():
                errors.append(f"Extracted root folder missing: {expected_root}")
            elif audit_files:
                errors.extend(_verify_audit_files(package_root))
                if not errors:
                    checks.append("audit-files")

    return VerificationResult(ok=not errors, checks=checks, errors=errors)


def _copy_payload(files: Iterable[SourceFile], staging_root: Path) -> List[FileRecord]:
    records: List[FileRecord] = []
    for source_file in files:
        destination = staging_root / source_file.rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file.source_path, destination)
        records.append(
            FileRecord(
                rel_path=source_file.rel_path,
                size=destination.stat().st_size,
                sha256=_sha256_file(destination),
            )
        )
    records.sort(key=lambda item: item.rel_path)
    return records


def _write_manifest(staging_root: Path, root_name: str, payload_records: Sequence[FileRecord]) -> FileRecord:
    manifest_path = staging_root / MANIFEST_NAME
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    total_bytes = sum(record.size for record in payload_records)

    lines = [
        "Packlight Manifest",
        f"Root: {root_name}",
        f"Generated: {generated}",
        "Mode: verified",
        f"Files: {len(payload_records)}",
        f"Bytes: {total_bytes}",
        f"Checksums: {CHECKSUMS_NAME}",
        "",
        "SHA-256                                                           Bytes  Path",
    ]
    for record in payload_records:
        lines.append(f"{record.sha256}  {record.size:>10}  {record.rel_path}")
    lines.append("")

    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return FileRecord(
        rel_path=MANIFEST_NAME,
        size=manifest_path.stat().st_size,
        sha256=_sha256_file(manifest_path),
    )


def _write_checksums(staging_root: Path, records: Sequence[FileRecord]) -> FileRecord:
    checksums_path = staging_root / CHECKSUMS_NAME
    lines = [f"{record.sha256}  {record.rel_path}" for record in records]
    checksums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return FileRecord(
        rel_path=CHECKSUMS_NAME,
        size=checksums_path.stat().st_size,
        sha256=_sha256_file(checksums_path),
    )


def _write_zip(staging_root: Path, output: Path, root_name: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(output.name + ".tmp")
    if temp_output.exists():
        temp_output.unlink()

    try:
        with zipfile.ZipFile(temp_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            _write_directory_entry(archive, f"{root_name}/")

            all_dirs = []
            all_files = []
            for path in staging_root.rglob("*"):
                rel = path.relative_to(staging_root).as_posix()
                if path.is_dir():
                    all_dirs.append(rel)
                elif path.is_file():
                    all_files.append(rel)

            for rel in sorted(all_dirs):
                _write_directory_entry(archive, f"{root_name}/{rel}/")

            for rel in sorted(all_files):
                _write_file_entry(archive, staging_root / rel, f"{root_name}/{rel}")

        os.replace(temp_output, output)
    finally:
        if temp_output.exists():
            temp_output.unlink()


def _write_directory_entry(archive: zipfile.ZipFile, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, date_time=ZIP_EPOCH)
    info.external_attr = (0o755 << 16) | 0x10
    archive.writestr(info, b"")


def _write_file_entry(archive: zipfile.ZipFile, source: Path, arcname: str) -> None:
    mode = source.stat().st_mode & 0o777
    info = zipfile.ZipInfo(arcname, date_time=ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = mode << 16
    with source.open("rb") as input_file:
        with archive.open(info, "w") as output_file:
            shutil.copyfileobj(input_file, output_file)


def _verify_audit_files(package_root: Path) -> List[str]:
    errors: List[str] = []
    package_root = package_root.resolve()
    manifest = package_root / MANIFEST_NAME
    checksums = package_root / CHECKSUMS_NAME
    if not manifest.is_file():
        errors.append(f"Missing {MANIFEST_NAME}")
    if not checksums.is_file():
        errors.append(f"Missing {CHECKSUMS_NAME}")
        return errors

    for line_number, line in enumerate(checksums.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        if len(line) < 67 or line[64:66] != "  ":
            errors.append(f"Malformed checksum line {line_number}")
            continue
        expected = line[:64]
        rel_path = line[66:]
        if any(char not in "0123456789abcdef" for char in expected):
            errors.append(f"Malformed checksum digest on line {line_number}")
            continue
        target = (package_root / rel_path).resolve()
        try:
            target.relative_to(package_root)
        except ValueError:
            errors.append(f"Unsafe checksum path on line {line_number}: {rel_path}")
            continue
        if not target.is_file():
            errors.append(f"Checksum target missing: {rel_path}")
            continue
        actual = _sha256_file(target)
        if actual != expected:
            errors.append(f"Checksum mismatch for {rel_path}")
    return errors


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        try:
            target.relative_to(destination)
        except ValueError:
            raise PacklightError(f"Refusing unsafe ZIP path during verification: {member.filename}")
        archive.extract(member, destination)


def _validate_zip_entry_name(name: str) -> Optional[str]:
    pure = PurePosixPath(name)
    if name.startswith("/") or "\\" in name:
        return f"Unsafe ZIP entry path: {name}"
    if any(part == ".." for part in pure.parts):
        return f"Unsafe ZIP entry traversal: {name}"
    return None


def _top_level_names(names: Iterable[str]) -> set:
    top_levels = set()
    for name in names:
        stripped = name.strip("/")
        if not stripped:
            continue
        top_levels.add(stripped.split("/", 1)[0])
    return top_levels


def _strip_root(name: str, root_name: str) -> str:
    prefix = root_name.rstrip("/") + "/"
    if name == root_name or name == prefix:
        return ""
    if name.startswith(prefix):
        return name[len(prefix) :].rstrip("/")
    return name


def _resolve_root_name(source: Path, requested: Optional[str]) -> str:
    root_name = (source.name or "package") if requested is None else requested
    root_name = root_name.strip()
    if not root_name:
        raise PacklightError("Root folder name cannot be empty.")
    if "/" in root_name or "\\" in root_name:
        raise PacklightError("Root folder name cannot contain path separators.")
    if any(ord(char) < 32 for char in root_name):
        raise PacklightError("Root folder name cannot contain control characters.")
    if root_name in {".", ".."}:
        raise PacklightError("Root folder name cannot be '.' or '..'.")
    return root_name


def _resolve_output_path(source: Path, requested: Optional[Path]) -> Path:
    if requested:
        return requested.expanduser().resolve()
    return source.with_suffix(".zip").resolve()


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _skipped_from_decision(rel_path: str, decision: Decision) -> SkippedItem:
    return SkippedItem(
        rel_path=rel_path,
        reason=decision.reason,
        rule=decision.rule,
        risky=decision.is_risky,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raise_walk_error(error: OSError) -> None:
    raise error
