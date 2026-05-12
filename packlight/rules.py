from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Iterable, Optional, Sequence


MAC_NAMES = {
    ".DS_Store",
    "__MACOSX",
    ".AppleDouble",
    ".LSOverride",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".TemporaryItems",
    ".DocumentRevisions-V100",
    ".VolumeIcon.icns",
}

DEV_DIR_NAMES = {
    ".git",
    ".eggs",
    ".hg",
    ".svn",
    "CVS",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "pip-wheel-metadata",
    ".next",
    ".parcel-cache",
    ".turbo",
    ".cache",
    "coverage",
    "htmlcov",
}

DEV_DIR_SUFFIXES = (
    ".dist-info",
    ".egg-info",
)

EXCLUDED_SUFFIXES = (
    ".egg-link",
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".temp",
    ".swp",
    ".swo",
    ".bak",
    ".orig",
    ".zip",
    ".tar",
    ".tgz",
    ".tar.gz",
    ".rar",
    ".7z",
)

RISKY_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

RISKY_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".cer",
    ".crt",
    ".mobileprovision",
)


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    rule: str

    @property
    def is_include(self) -> bool:
        return self.action == "include"

    @property
    def is_risky(self) -> bool:
        return self.action == "risky"


INCLUDE = Decision("include", "included", "default-include")


def explain_default_rules() -> Sequence[str]:
    return (
        "macOS metadata: .DS_Store, __MACOSX, AppleDouble, Spotlight, Trash, Finder state",
        "development clutter: VCS folders, virtualenvs, caches, node_modules, bytecode",
        "transient artifacts: logs, temp files, swap files, backups, old archive files",
        "hidden files and folders are excluded unless allowed explicitly",
        "secret-like files and symlinks are risky; verified/strict mode refuses them",
    )


def decide_path(
    rel_path: str,
    *,
    is_dir: bool,
    allow_patterns: Iterable[str] = (),
    exclude_patterns: Iterable[str] = (),
) -> Decision:
    rel_path = rel_path.replace("\\", "/")
    basename = PurePosixPath(rel_path).name
    parts = PurePosixPath(rel_path).parts
    lower_name = basename.lower()

    if _has_control_character(rel_path):
        return Decision("risky", "filename contains a control character", "unsafe-name")

    risky_decision = _risky_decision_for_basename(basename)
    if risky_decision:
        return risky_decision

    if _matches(rel_path, basename, exclude_patterns):
        return Decision("exclude", "matched user exclusion", "user-exclude")

    if _matches(rel_path, basename, allow_patterns) or (
        is_dir and _allows_descendant(rel_path, allow_patterns)
    ):
        return INCLUDE

    if basename.startswith("._"):
        return Decision("exclude", "AppleDouble resource-fork sidecar", "macos-appledouble")

    if basename == "Icon\r":
        return Decision("exclude", "Finder icon metadata", "macos-icon")

    for part in parts:
        if part in MAC_NAMES:
            return Decision("exclude", "macOS metadata", "macos-metadata")

    if is_dir:
        if basename in DEV_DIR_NAMES or any(lower_name.endswith(suffix) for suffix in DEV_DIR_SUFFIXES):
            return Decision("exclude", "development cache or metadata directory", "dev-directory")
        if basename.startswith("."):
            return Decision("exclude", "hidden directory", "hidden-directory")
        return INCLUDE

    if basename.startswith("."):
        return Decision("exclude", "hidden file", "hidden-file")

    if any(lower_name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return Decision("exclude", "transient or archive artifact", "transient-artifact")

    return INCLUDE


def _risky_decision_for_basename(basename: str) -> Optional[Decision]:
    lower_name = basename.lower()
    if lower_name in RISKY_NAMES or lower_name.startswith(".env."):
        return Decision("risky", "secret-like configuration file", "secret-like")
    if any(lower_name.endswith(suffix) for suffix in RISKY_SUFFIXES):
        return Decision("risky", "key, certificate, or provisioning profile", "credential-like")
    return None


def _matches(rel_path: str, basename: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        if fnmatch(rel_path, normalized) or fnmatch(basename, normalized):
            return True
    return False


def _allows_descendant(rel_path: str, patterns: Iterable[str]) -> bool:
    prefix = rel_path.rstrip("/") + "/"
    return any(pattern.replace("\\", "/").startswith(prefix) for pattern in patterns)


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 for char in value)
