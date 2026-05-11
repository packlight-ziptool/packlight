from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import PacklightError, PacklightOptions, build_clean_zip
from .rules import explain_default_rules


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.rules:
        for rule in explain_default_rules():
            print(f"- {rule}")
        return 0

    if not args.source:
        parser.error("source is required unless --rules is used")

    verified = args.verified or args.release or args.audit_files
    options = PacklightOptions(
        source=Path(args.source),
        output=Path(args.output) if args.output else None,
        root_name=args.root_name,
        verified=verified,
        release=args.release,
        audit_files=args.audit_files,
        strict=args.strict,
        dry_run=args.dry_run,
        force=args.force,
        allow_patterns=tuple(args.allow or ()),
        exclude_patterns=tuple(args.exclude or ()),
    )

    try:
        result = build_clean_zip(options)
    except PacklightError as error:
        print(f"packlight: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(result.to_json())
    else:
        print(_format_result(result, explain=args.explain))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="packlight",
        description="Create ZIP archives from local folders while skipping common clutter.",
    )
    parser.add_argument("source", nargs="?", help="folder to package")
    parser.add_argument("-o", "--output", help="destination ZIP path")
    parser.add_argument("--root-name", help="top-level folder name inside the ZIP")
    parser.add_argument("--verified", action="store_true", help="check risky paths and verify the ZIP before success")
    parser.add_argument("--release", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--audit-files",
        action="store_true",
        help="add MANIFEST.txt and SHA256SUMS inside the ZIP; also runs verified checks",
    )
    parser.add_argument("--strict", action="store_true", help="refuse risky files instead of only skipping them")
    parser.add_argument("--dry-run", action="store_true", help="show what would be packaged without writing a ZIP")
    parser.add_argument("--explain", action="store_true", help="show included and skipped paths")
    parser.add_argument("--allow", action="append", help="allow a path or glob that would otherwise be skipped")
    parser.add_argument("--exclude", action="append", help="exclude an additional path or glob")
    parser.add_argument("--force", action="store_true", help="replace an existing output ZIP")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    parser.add_argument("--rules", action="store_true", help="print the default rule summary and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _format_result(result, *, explain: bool) -> str:
    lines = []
    if result.dry_run:
        lines.append("Dry run complete. No ZIP was written.")
        lines.append(f"Output target: {result.output}")
    else:
        lines.append(f"ZIP created: {result.output}")
    lines.append(f"Root folder: {result.root_name}/")
    lines.append(f"Included files: {len(result.files)}")
    lines.append(f"Skipped items: {len(result.skipped)}")
    lines.append(f"Payload bytes: {result.total_bytes}")

    if result.verification:
        status = "passed" if result.verification.ok else "failed"
        lines.append(f"Verification: {status} ({', '.join(result.verification.checks)})")

    if explain:
        lines.append("")
        lines.append("Included:")
        for record in result.files:
            lines.append(f"  + {record.rel_path}")
        if result.skipped:
            lines.append("")
            lines.append("Skipped:")
            for item in result.skipped:
                marker = "!" if item.risky else "-"
                lines.append(f"  {marker} {item.rel_path} [{item.rule}: {item.reason}]")

    return "\n".join(lines)
