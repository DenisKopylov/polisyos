#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.ir.schema_catalog import (  # noqa: E402
    IRPublicStatus,
    IRSchemaCatalog,
    IRTypeInfo,
    abi_snapshot_path,
    get_ir_schema_catalog,
)

IR_REFERENCE_PATH = REPO_ROOT / "docs" / "reference" / "ir" / "schema-catalog.md"
SCHEMA_REFERENCE_PATH = REPO_ROOT / "docs" / "reference" / "schemas.md"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or verify docs/reference pages that are backed by the "
            "IR reflection catalog and ABI snapshot registry."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated docs differ from committed files.",
    )
    return parser.parse_args()


def generate_reference_docs(*, check: bool = False) -> list[str]:
    catalog = get_ir_schema_catalog()
    targets = {
        IR_REFERENCE_PATH: render_ir_schema_catalog(catalog),
        SCHEMA_REFERENCE_PATH: render_schema_reference(catalog),
    }
    errors: list[str] = []
    for path, content in targets.items():
        if check:
            if not path.exists():
                errors.append(f"missing generated reference: {path}")
                continue
            current = path.read_text(encoding="utf-8")
            if current != content:
                errors.append(f"generated reference out of date: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return errors


def _md_cell(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br/>")


def render_ir_schema_catalog(catalog: IRSchemaCatalog) -> str:
    lines: list[str] = [
        "# IR Schema Catalog",
        "",
        "Related reference: [Schemas](../schemas.md).",
        "",
        "> This page is generated from `polisyos.ir.schema_catalog` "
        "and the current package facades.",
        "",
        "Canonical regeneration command (snapshots + reference docs):",
        "",
        "```bash",
        "PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py",
        "```",
        "",
        "## Summary",
        "",
        f"- Total IR types: `{len(catalog.types)}`.",
        f"- Public/root-or-package facade types: `{len(catalog.public_types)}`.",
        f"- ABI snapshot-backed types: `{len(catalog.snapshot_types)}`.",
    ]

    export_counts = Counter(entry.package for entry in catalog.exports)
    if export_counts:
        lines.extend(
            [
                "- Export enumeration covers these public packages:",
                "",
                "| Package | Export count |",
                "| ------- | ------------ |",
            ]
        )
        for package in sorted(export_counts):
            lines.append(f"| `{_md_cell(package)}` | {export_counts[package]} |")
        lines.append("")

    lines.extend(
        [
            "## Section Summary",
            "",
            "| Section | Type count | Public types | Snapshot-backed |",
            "| ------- | ---------- | ------------ | ---------------- |",
        ]
    )
    for section in catalog.sections:
        entries = catalog.list(section=section)
        public_count = sum(entry.public_status is not IRPublicStatus.INTERNAL for entry in entries)
        snapshot_count = sum(entry.abi_key is not None for entry in entries)
        lines.append(
            f"| `{_md_cell(section)}` | {len(entries)} | {public_count} | {snapshot_count} |"
        )
    lines.append("")

    for section in catalog.sections:
        section_entries = catalog.list(section=section)
        lines.extend(_render_section(section, section_entries))

    return "\n".join(lines).rstrip() + "\n"


def render_schema_reference(catalog: IRSchemaCatalog) -> str:
    lines: list[str] = [
        "# JSON Schema Catalog",
        "",
        "Related reference: [IR Schema Catalog](ir/schema-catalog.md).",
        "",
        "> This page is generated from the ABI snapshot registry and the IR reflection catalog.",
        "",
        "Canonical regeneration command (snapshots + reference docs):",
        "",
        "```bash",
        "PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py",
        "```",
        "",
    ]

    snapshot_manifest = _load_manifest(
        REPO_ROOT / "schemas" / "snapshots" / "ir" / "_manifest.json"
    )
    fabric_manifest = _load_manifest(
        REPO_ROOT / "schemas" / "snapshots" / "fabric" / "_manifest.json"
    )
    if snapshot_manifest is not None or fabric_manifest is not None:
        lines.extend(["## Snapshot Summary", ""])
        if snapshot_manifest is not None:
            lines.append(
                f"- IR snapshot: `{len(snapshot_manifest.get('models', {}))}` schemas, generated "
                f"`{snapshot_manifest.get('generated_at', 'unknown')}`."
            )
        if fabric_manifest is not None:
            lines.append(
                f"- Fabric world ABI snapshot: "
                f"`{len(fabric_manifest.get('models', {}))}` schemas, generated "
                f"`{fabric_manifest.get('generated_at', 'unknown')}`."
            )
        lines.append(
            "- Direct-read compatibility is declared in "
            "`polisyos.ir.migrations.schema_registry` and surfaced below."
        )
        lines.append("")

    lines.extend(
        [
            "## ABI-backed IR Schemas",
            "",
            "| Schema | Type | Section | Version | Priority | Compatibility | "
            "Public status | Docs | Raw path |",
            "| ------ | ---- | ------- | ------- | -------- | ------------- | "
            "------------- | ---- | -------- |",
        ]
    )

    for entry in catalog.snapshot_types:
        snapshot_path = abi_snapshot_path(entry) or "—"
        compat = entry.compat_mode.value if entry.compat_mode is not None else "—"
        docs_link = f"[{entry.name}](ir/{entry.docs_link})"
        version = entry.schema_version or "—"
        priority = entry.abi_priority or "—"
        lines.append(
            "| "
            f"`{_md_cell(entry.abi_key)}` | `{_md_cell(entry.fqn)}` | "
            f"`{_md_cell(entry.section)}` | `{_md_cell(version)}` | "
            f"`{_md_cell(priority)}` | `{_md_cell(compat)}` | "
            f"`{_md_cell(entry.public_status.value)}` | {docs_link} | "
            f"`{_md_cell(snapshot_path)}` |"
        )

    connector_snapshot = REPO_ROOT / "schemas" / "snapshots" / "connectors" / "contracts.json"
    if connector_snapshot.exists():
        lines.extend(
            [
                "",
                "## Non-JSON-Schema Snapshot",
                "",
                "- `schemas/snapshots/connectors/contracts.json` remains part "
                "of the compatibility baseline, "
                "but it is a connector contract snapshot rather than a JSON Schema bundle.",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _render_section(section: str, entries: Iterable[IRTypeInfo]) -> list[str]:
    lines = [
        f"## {section.title()}",
        "",
    ]
    for entry in entries:
        lines.extend(_render_type(entry))
    return lines


def _render_type(entry: IRTypeInfo) -> list[str]:
    snapshot_path = abi_snapshot_path(entry) or "—"
    refs = ", ".join(f"`{ref}`" for ref in entry.refs) if entry.refs else "—"
    exports = (
        ", ".join(f"`{value}`" for value in entry.exported_from) if entry.exported_from else "—"
    )
    compat = entry.compat_mode.value if entry.compat_mode is not None else "—"
    anchor = entry.docs_link.split("#", 1)[1]
    lines = [
        f"### `{entry.fqn}` {{ #{anchor} }}",
        "",
        f"- Kind: `{entry.kind.value}`",
        f"- Public status: `{entry.public_status.value}`",
        f"- Current version: `{entry.schema_version or '—'}`",
        f"- Exported from: {exports}",
        f"- ABI snapshot: `{entry.abi_key or '—'}` / `{snapshot_path}`",
        f"- Compatibility mode: `{compat}`",
        f"- References: {refs}",
    ]
    if entry.summary:
        lines.append(f"- Summary: {entry.summary}")
    if entry.compat_readable_versions:
        lines.append(f"- Declared readable versions: `{', '.join(entry.compat_readable_versions)}`")
    if entry.compat_writable_versions:
        lines.append(f"- Declared writable versions: `{', '.join(entry.compat_writable_versions)}`")
    lines.append("")

    if entry.enum_values:
        lines.extend(
            [
                "| Enum values |",
                "| ----------- |",
            ]
        )
        lines.extend(f"| `{_md_cell(value)}` |" for value in entry.enum_values)
        lines.append("")

    if entry.fields:
        lines.extend(
            [
                "| Field | Type | Required | Default | IR refs |",
                "| ----- | ---- | -------- | ------- | ------- |",
            ]
        )
        for field in entry.fields:
            refs = (
                ", ".join(f"`{_md_cell(ref)}`" for ref in field.references)
                if field.references
                else "—"
            )
            lines.append(
                f"| `{_md_cell(field.name)}` | `{_md_cell(field.annotation)}` | "
                f"`{'yes' if field.required else 'no'}` | "
                f"`{_md_cell(field.default or '—')}` | {refs} |"
            )
        lines.append("")
    return lines


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = _parse_args()
    errors = generate_reference_docs(check=args.check)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
