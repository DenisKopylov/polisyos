#!/usr/bin/env python3
"""
CLI tool for batch migration of PolicySurfaceIR files to Trinity format.

Usage:
    python tools/migrate_to_trinity.py data/policies/ --dry-run
    python tools/migrate_to_trinity.py data/policies/ --backup --verify
    python tools/migrate_to_trinity.py policy.yaml --output trinity_policy.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Iterator

import yaml

from polisyos.ir.loaders import load_trinity_bundle
from polisyos.ir.legacy.migrations.surface_to_trinity import (
    is_legacy_trinity_bundle_payload,
    is_trinity_bundle_payload,
    migrate_trinity_to_surface_ir,
)


class MigrationReport:
    """Track migration results for reporting."""

    def __init__(self) -> None:
        self.total = 0
        self.migrated = 0
        self.skipped = 0
        self.failed = 0
        self.errors: list[tuple[Path, str]] = []
        self.warnings: list[tuple[Path, str]] = []

    def add_success(self, path: Path) -> None:
        self.total += 1
        self.migrated += 1

    def add_skip(self, path: Path, reason: str) -> None:
        self.total += 1
        self.skipped += 1
        self.warnings.append((path, reason))

    def add_failure(self, path: Path, error: str) -> None:
        self.total += 1
        self.failed += 1
        self.errors.append((path, error))

    def summary(self) -> str:
        lines = [
            "\n" + "=" * 60,
            "MIGRATION REPORT",
            "=" * 60,
            f"Total files processed: {self.total}",
            f"  Migrated: {self.migrated}",
            f"  Skipped:  {self.skipped}",
            f"  Failed:   {self.failed}",
        ]

        if self.warnings:
            lines.append(f"\nWarnings ({len(self.warnings)}):")
            for path, reason in self.warnings[:10]:
                lines.append(f"  - {path}: {reason}")
            if len(self.warnings) > 10:
                lines.append(f"  ... and {len(self.warnings) - 10} more")

        if self.errors:
            lines.append(f"\nErrors ({len(self.errors)}):")
            for path, error in self.errors:
                lines.append(f"  - {path}: {error}")

        return "\n".join(lines)


def find_policy_files(root: Path, recursive: bool = True) -> Iterator[Path]:
    """Find all YAML/JSON policy files."""
    patterns = ["*.yaml", "*.yml", "*.json"]

    if recursive:
        for pattern in patterns:
            yield from root.rglob(pattern)
    else:
        for pattern in patterns:
            yield from root.glob(pattern)


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_file(path: Path) -> dict:
    """Load YAML or JSON file."""
    content = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(content)
    return yaml.safe_load(content)


def save_file(path: Path, data: dict, format: str = "yaml") -> None:
    """Save data to YAML or JSON file."""
    if format == "json" or path.suffix == ".json":
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        content = yaml.dump(data, allow_unicode=True, sort_keys=False)
    path.write_text(content, encoding="utf-8")


def verify_migration(original_data: dict, trinity_data: dict) -> tuple[bool, str]:
    """
    Verify migration by round-tripping and comparing semantic fingerprints.

    Returns:
        (success, message) tuple
    """
    from polisyos.ir.legacy.surface import PolicySurfaceIR
    from polisyos.ir.trinity import TrinityBundle

    try:
        # Load original
        original_ir = PolicySurfaceIR.model_validate(original_data)
        original_fingerprint = original_ir.semantic_fingerprint_payload()

        # Load migrated and merge back
        bundle = TrinityBundle.model_validate(trinity_data)
        merged_ir, _ = migrate_trinity_to_surface_ir(bundle)
        merged_fingerprint = merged_ir.semantic_fingerprint_payload()

        # Compare semantic fingerprints
        if original_fingerprint == merged_fingerprint:
            return True, "Semantic fingerprints match"

        # Detailed diff for debugging
        diff_keys = []
        for key in set(original_fingerprint) | set(merged_fingerprint):
            if original_fingerprint.get(key) != merged_fingerprint.get(key):
                diff_keys.append(key)

        return False, f"Fingerprint mismatch in: {', '.join(diff_keys)}"
    except Exception as exc:
        return False, f"Verification error: {exc}"


def migrate_file(
    input_path: Path,
    output_path: Path | None,
    *,
    dry_run: bool = False,
    backup: bool = False,
    verify: bool = False,
    report: MigrationReport,
) -> bool:
    """Migrate a single file to Trinity format."""
    try:
        data = load_file(input_path)

        # Check if already canonical Trinity bundle
        if is_trinity_bundle_payload(data) and not is_legacy_trinity_bundle_payload(data):
            report.add_skip(input_path, "Already in canonical Trinity format")
            return True

        # Check if it is a policy file
        if not (
            "semantic" in data
            or "schema_version" in data
            or is_trinity_bundle_payload(data)
            or is_legacy_trinity_bundle_payload(data)
        ):
            report.add_skip(input_path, "Not a PolicySurfaceIR file")
            return True

        # Perform migration (legacy surface or legacy bundle)
        bundle, _migration_report = load_trinity_bundle(data)
        trinity_data = bundle.model_dump()

        # Verify if requested
        if verify:
            success, message = verify_migration(data, trinity_data)
            if not success:
                report.add_failure(input_path, f"Verification failed: {message}")
                return False

        if dry_run:
            print(f"[DRY-RUN] Would migrate: {input_path}")
            report.add_success(input_path)
            return True

        # Determine output path
        out = output_path or input_path

        # Create backup if requested
        if backup and out == input_path:
            backup_path = input_path.with_suffix(f"{input_path.suffix}.bak")
            shutil.copy2(input_path, backup_path)

        # Save migrated file
        save_file(out, trinity_data)
        report.add_success(input_path)
        return True
    except Exception as exc:
        report.add_failure(input_path, str(exc))
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate PolicySurfaceIR files to Trinity format",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input file or directory",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file (for single file) or directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create .bak backup before overwriting",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration via round-trip comparison",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        default=True,
        help="Process directories recursively (default: True)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_false",
        dest="recursive",
        help="Do not process directories recursively",
    )

    args = parser.parse_args()
    report = MigrationReport()

    if args.input.is_file():
        migrate_file(
            args.input,
            args.output,
            dry_run=args.dry_run,
            backup=args.backup,
            verify=args.verify,
            report=report,
        )
    elif args.input.is_dir():
        for policy_file in find_policy_files(args.input, args.recursive):
            # Determine output path for batch mode
            if args.output:
                rel_path = policy_file.relative_to(args.input)
                out_path = args.output / rel_path
                out_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_path = None

            migrate_file(
                policy_file,
                out_path,
                dry_run=args.dry_run,
                backup=args.backup,
                verify=args.verify,
                report=report,
            )
    else:
        print(f"Error: {args.input} does not exist", file=sys.stderr)
        sys.exit(1)

    print(report.summary())
    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
