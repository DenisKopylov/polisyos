#!/usr/bin/env python3
"""Report runtime-quality schema compatibility and legacy quarantine decisions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.schema_compat import (  # noqa: E402
    ReaderSchemaRange,
    evaluate_schema_compatibility,
    reader_schema_ranges,
)

SCHEMA_VERSION = "policyos.runtime_quality_schema_compatibility_report.v1"
TOOL_NAME = "quality.validation.check-runtime-quality-schema-compatibility"
GENERATED_AT = "2026-05-15T00:00:00Z"
DEFAULT_OUTPUT_DIR = Path("_build/honest-diagnostics/schema-compatibility")
DEFAULT_ROOT_PATHS = (
    "_build",
    ".polisyos",
    "docs/archive/reports",
    "tests/_golden/quality",
)
DEFAULT_READERS = (
    "scorecard",
    "readiness",
    "bundle_assembler",
    "approval_packet_builder",
)
INCLUDE_EXTENSIONS = (".json", ".jsonl")
CANDIDATE_KEYWORDS = (
    "approval",
    "bundle",
    "canary",
    "compat",
    "diagnostic",
    "evidence",
    "ledger",
    "manifest",
    "matrix",
    "quality",
    "readiness",
    "report",
    "scorecard",
    "validation",
)
EXCLUDED_PREFIXES = (
    "_build/honest-diagnostics/schema-compatibility",
    "_build/honest-diagnostics/legacy",
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--root-path",
        action="append",
        default=None,
        help="Root to scan. May be repeated. Defaults to runtime-quality evidence roots.",
    )
    parser.add_argument(
        "--reader",
        action="append",
        default=None,
        help="Reader contract to evaluate. May be repeated.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs drift")
    return parser.parse_args(argv)


def build_compatibility_report(
    *,
    repo_root: Path = REPO_ROOT,
    root_paths: Sequence[str | Path] = DEFAULT_ROOT_PATHS,
    readers: Sequence[str] = DEFAULT_READERS,
    declarations: Mapping[str, tuple[ReaderSchemaRange, ...]] | None = None,
) -> dict[str, Any]:
    """Build a metadata report for existing runtime-quality bundles and reports."""

    repo_root = repo_root.resolve()
    declarations = declarations or reader_schema_ranges()
    normalized_readers = tuple(str(reader).strip() for reader in readers if str(reader).strip())
    entries: list[dict[str, Any]] = []
    for path in _discover_candidate_files(repo_root=repo_root, root_paths=root_paths):
        payload, read_status, parse_error = _read_jsonish(path)
        migration = _embedded_migration(payload)
        for reader in normalized_readers:
            result = evaluate_schema_compatibility(
                payload if isinstance(payload, Mapping) else None,
                reader=reader,
                declarations=declarations,
                migration=migration,
            )
            gate_details = result.to_gate_details()
            entries.append(
                {
                    "path": _rel(path, repo_root),
                    "reader": reader,
                    "file_kind": _file_kind(path),
                    "read_status": read_status,
                    "parse_error": parse_error,
                    "decision": result.decision,
                    "reason": result.reason,
                    "diagnostic_readable": result.diagnostic_readable,
                    "production_closeout_allowed": result.production_closeout_allowed,
                    "migration_required": result.migration_required,
                    "migration_verified": result.migration_verified,
                    "missing_semantic_fields": list(result.missing_semantic_fields),
                    "schema": {
                        "schema_version": gate_details["schema_version"],
                        "schema_family": gate_details["schema_family"],
                        "schema_version_number": gate_details["schema_version_number"],
                        "expected_schema_families": gate_details["expected_schema_families"],
                    },
                }
            )

    decision_counts = Counter(str(row["decision"]) for row in entries)
    reason_counts = Counter(str(row["reason"]) for row in entries)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": GENERATED_AT,
        "repo_root": str(repo_root),
        "readers": list(normalized_readers),
        "source_roots": [str(root) for root in root_paths],
        "summary": {
            "entry_count": len(entries),
            "source_file_count": len({row["path"] for row in entries}),
            "production_closeout_blocked_count": sum(
                1 for row in entries if not row["production_closeout_allowed"]
            ),
            "diagnostic_readable_count": sum(
                1 for row in entries if row["diagnostic_readable"]
            ),
            "migration_required_count": sum(1 for row in entries if row["migration_required"]),
            "verified_migration_count": sum(1 for row in entries if row["migration_verified"]),
            "decision_counts": dict(sorted(decision_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
        },
        "entries": entries,
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Runtime Quality Schema Compatibility",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Entries: {summary['entry_count']}",
        f"- Source files: {summary['source_file_count']}",
        f"- Production-closeout blocked rows: {summary['production_closeout_blocked_count']}",
        f"- Verified migrations: {summary['verified_migration_count']}",
        "",
        "## Decision Counts",
        "",
        "| Decision | Count |",
        "| --- | ---: |",
    ]
    for decision, count in summary["decision_counts"].items():
        lines.append(f"| `{decision}` | {count} |")

    lines.extend(
        [
            "",
            "## Entries",
            "",
            "| Path | Reader | Decision | Reason | Schema | Migration |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["entries"]:
        schema = row["schema"]
        schema_label = schema.get("schema_version") or schema.get("schema_family") or ""
        migration_label = (
            "verified"
            if row["migration_verified"]
            else "required"
            if row["migration_required"]
            else ""
        )
        lines.append(
            "| "
            f"`{row['path']}` | "
            f"`{row['reader']}` | "
            f"`{row['decision']}` | "
            f"`{row['reason']}` | "
            f"`{schema_label}` | "
            f"`{migration_label}` |"
        )
    return "\n".join(lines) + "\n"


def check_artifacts(
    *,
    repo_root: Path = REPO_ROOT,
    root_paths: Sequence[str | Path] = DEFAULT_ROOT_PATHS,
    readers: Sequence[str] = DEFAULT_READERS,
    json_output: Path | None = None,
    markdown_output: Path | None = None,
) -> list[str]:
    repo_root = repo_root.resolve()
    json_path, markdown_path = _output_paths(
        repo_root=repo_root,
        output_dir=DEFAULT_OUTPUT_DIR,
        json_output=json_output,
        markdown_output=markdown_output,
    )
    payload = build_compatibility_report(
        repo_root=repo_root,
        root_paths=root_paths,
        readers=readers,
    )
    expected = {
        json_path: dump_json(payload),
        markdown_path: render_markdown(payload),
    }
    failures: list[str] = []
    for path, expected_content in expected.items():
        if not path.exists():
            failures.append(
                "generated schema compatibility report missing: "
                f"{_rel(path, repo_root)}"
            )
            continue
        if path.read_text(encoding="utf-8") != expected_content:
            failures.append(
                f"generated schema compatibility report out of date: {_rel(path, repo_root)}"
            )
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    root_paths = tuple(args.root_path or DEFAULT_ROOT_PATHS)
    readers = tuple(args.reader or DEFAULT_READERS)
    json_output, markdown_output = _output_paths(
        repo_root=repo_root,
        output_dir=args.output_dir,
        json_output=args.json_output,
        markdown_output=args.markdown_output,
    )

    if args.check:
        failures = check_artifacts(
            repo_root=repo_root,
            root_paths=root_paths,
            readers=readers,
            json_output=json_output,
            markdown_output=markdown_output,
        )
        if failures:
            for failure in failures:
                sys.stderr.write(f"{failure}\n")
            return 1
        return 0

    payload = build_compatibility_report(
        repo_root=repo_root,
        root_paths=root_paths,
        readers=readers,
    )
    atomic_write_text(json_output, dump_json(payload))
    atomic_write_text(markdown_output, render_markdown(payload))
    return 0


def _output_paths(
    *,
    repo_root: Path,
    output_dir: Path,
    json_output: Path | None,
    markdown_output: Path | None,
) -> tuple[Path, Path]:
    resolved_dir = _resolve(repo_root, output_dir)
    return (
        _resolve(repo_root, json_output)
        if json_output
        else resolved_dir / "runtime_quality_schema_compatibility.json",
        _resolve(repo_root, markdown_output)
        if markdown_output
        else resolved_dir / "runtime_quality_schema_compatibility.md",
    )


def _discover_candidate_files(
    *,
    repo_root: Path,
    root_paths: Sequence[str | Path],
) -> list[Path]:
    paths: list[Path] = []
    include_extensions = set(INCLUDE_EXTENSIONS)
    for root in root_paths:
        root_path = _resolve(repo_root, root)
        if not root_path.exists():
            continue
        if root_path.is_file():
            candidates: Iterable[Path] = (root_path,)
        else:
            candidates = root_path.rglob("*")
        for path in candidates:
            if not path.is_file():
                continue
            rel_path = _rel(path, repo_root)
            if _is_excluded_path(rel_path):
                continue
            if _has_hidden_part(rel_path):
                continue
            if path.suffix.lower() not in include_extensions:
                continue
            if _is_candidate_report_file(rel_path):
                paths.append(path)
    return sorted(set(paths), key=lambda item: _rel(item, repo_root))


def _read_jsonish(path: Path) -> tuple[Any, str, str | None]:
    raw = path.read_bytes()
    if path.suffix.lower() == ".jsonl":
        return _parse_first_jsonl_row(raw)
    try:
        return json.loads(raw.decode("utf-8")), "parsed", None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, "parse_error", exc.__class__.__name__


def _parse_first_jsonl_row(raw: bytes) -> tuple[Any, str, str | None]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, "parse_error", exc.__class__.__name__
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped), "parsed", None
        except json.JSONDecodeError as exc:
            return None, "parse_error", exc.__class__.__name__
    return None, "parse_error", "empty_jsonl"


def _embedded_migration(payload: object) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    for key in ("schema_migration", "migration", "migration_record"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _file_kind(path: Path) -> str:
    lowered = path.as_posix().lower()
    if "bundle" in lowered:
        return "bundle"
    if "scorecard" in lowered:
        return "scorecard"
    if "ledger" in lowered:
        return "ledger"
    if "matrix" in lowered:
        return "matrix"
    if "manifest" in lowered:
        return "manifest"
    return "report"


def _is_candidate_report_file(rel_path: str) -> bool:
    lowered = rel_path.lower()
    return any(keyword in lowered for keyword in CANDIDATE_KEYWORDS)


def _is_excluded_path(rel_path: str) -> bool:
    lowered = rel_path.lower()
    return any(
        lowered == prefix or lowered.startswith(f"{prefix}/")
        for prefix in EXCLUDED_PREFIXES
    )


def _has_hidden_part(rel_path: str) -> bool:
    return any(part.startswith(".") and part != ".polisyos" for part in Path(rel_path).parts)


def _resolve(repo_root: Path, path: Path | str | None) -> Path:
    if path is None:
        return repo_root
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
