#!/usr/bin/env python3
"""Generate Phase 0.3 caller evidence for last-mile import compatibility shims."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "repository.last_mile.shim_callers.v1"
PHASE = "0.3"
GENERATED_AT = "2026-05-07T00:00:00Z"
DEFAULT_OUTPUT = REPO_ROOT / "_build" / ".tmp" / "last-mile" / "shim_callers.json"
SOURCE_CONTRACT = "architecture/shims.toml#last_mile_import_compatibility_map"
REMOVAL_RULE = (
    "A shim may be removed only when caller_count is zero or all remaining callers "
    "are examples/tests intentionally exercising compatibility."
)
IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".basedpyright",
    ".cache",
    ".uv-cache",
    ".venv",
    "_build",
    "_cache",
    "__pycache__",
    "node_modules",
    ".next",
    ".turbo",
}


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as stream:
        payload = tomllib.load(stream)
    return payload if isinstance(payload, dict) else {}


def _iter_python_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        ]
        current_path = Path(current)
        for filename in filenames:
            if filename.endswith(".py"):
                files.append(current_path / filename)
    return sorted(files)


def _caller_role(rel_path: str) -> str:
    if rel_path.startswith("src/"):
        return "source"
    if rel_path.startswith("tests/"):
        return "test"
    if rel_path.startswith("examples/"):
        return "example"
    if rel_path.startswith("tools/"):
        return "tool"
    if rel_path.startswith("docs/"):
        return "doc"
    return "repository"


def _is_intentional_compatibility_exercise(rel_path: str) -> bool:
    filename = rel_path.rsplit("/", 1)[-1]
    return rel_path.startswith(("tests/", "examples/")) and (
        "shim" in filename
        or "facade" in filename
        or "last_mile_import_map" in filename
        or "root_facade" in filename
    )


def _planned_retained_shims(repo_root: Path) -> dict[str, dict[str, str]]:
    payload = _read_toml(repo_root / "architecture" / "shims.toml")
    entries: dict[str, dict[str, str]] = {}
    for entry in payload.get("planned_source_move", []):
        if not isinstance(entry, Mapping) or entry.get("decision") == "removed":
            continue
        shim_id = str(entry.get("id", ""))
        source_fqn = str(entry.get("source_fqn", ""))
        target_fqn = str(entry.get("target_fqn", ""))
        if not shim_id or not source_fqn or not target_fqn:
            continue
        entries[shim_id] = {
            "source_fqn": source_fqn,
            "migration_target": target_fqn,
        }
    return dict(sorted(entries.items()))


def _matching_source(import_name: str, source_by_fqn: Mapping[str, str]) -> str | None:
    for source_fqn in sorted(source_by_fqn, key=len, reverse=True):
        if import_name == source_fqn or import_name.startswith(f"{source_fqn}."):
            return source_fqn
    return None


def _record(
    rows: dict[str, list[dict[str, Any]]],
    *,
    source_fqn: str,
    shim_id_by_source: Mapping[str, str],
    migration_target_by_source: Mapping[str, str],
    importer_path: str,
    import_kind: str,
    import_name: str,
    line: int,
) -> None:
    shim_id = shim_id_by_source[source_fqn]
    rows[shim_id].append(
        {
            "importer_path": importer_path,
            "import_kind": import_kind,
            "import_name": import_name,
            "line": line,
            "migration_target": migration_target_by_source[source_fqn],
            "caller_role": _caller_role(importer_path),
            "intentional_compatibility_exercise": _is_intentional_compatibility_exercise(
                importer_path
            ),
        }
    )


def _scan_ast_imports(
    tree: ast.AST,
    *,
    rows: dict[str, list[dict[str, Any]]],
    importer_path: str,
    source_by_fqn: Mapping[str, str],
    shim_id_by_source: Mapping[str, str],
    migration_target_by_source: Mapping[str, str],
) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                source_fqn = _matching_source(alias.name, source_by_fqn)
                if source_fqn is None:
                    continue
                _record(
                    rows,
                    source_fqn=source_fqn,
                    shim_id_by_source=shim_id_by_source,
                    migration_target_by_source=migration_target_by_source,
                    importer_path=importer_path,
                    import_kind="import",
                    import_name=alias.name,
                    line=node.lineno,
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            source_fqn = _matching_source(module, source_by_fqn)
            if source_fqn is not None:
                _record(
                    rows,
                    source_fqn=source_fqn,
                    shim_id_by_source=shim_id_by_source,
                    migration_target_by_source=migration_target_by_source,
                    importer_path=importer_path,
                    import_kind="from_import"
                    if module == source_fqn
                    else "from_import_submodule",
                    import_name=module,
                    line=node.lineno,
                )
            for alias in node.names:
                if alias.name == "*":
                    continue
                import_name = f"{module}.{alias.name}" if module else alias.name
                alias_source_fqn = _matching_source(import_name, source_by_fqn)
                if alias_source_fqn is None:
                    continue
                _record(
                    rows,
                    source_fqn=alias_source_fqn,
                    shim_id_by_source=shim_id_by_source,
                    migration_target_by_source=migration_target_by_source,
                    importer_path=importer_path,
                    import_kind="from_import_submodule",
                    import_name=import_name,
                    line=node.lineno,
                )


def _scan_dynamic_strings(
    text: str,
    *,
    rows: dict[str, list[dict[str, Any]]],
    importer_path: str,
    source_by_fqn: Mapping[str, str],
    shim_id_by_source: Mapping[str, str],
    migration_target_by_source: Mapping[str, str],
) -> None:
    pattern = re.compile(r"['\"](polisyos(?:\.[A-Za-z_][A-Za-z0-9_]*)+)['\"]")
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in pattern.finditer(line):
            import_name = match.group(1)
            source_fqn = _matching_source(import_name, source_by_fqn)
            if source_fqn is None:
                continue
            _record(
                rows,
                source_fqn=source_fqn,
                shim_id_by_source=shim_id_by_source,
                migration_target_by_source=migration_target_by_source,
                importer_path=importer_path,
                import_kind="dynamic_string",
                import_name=import_name,
                line=lineno,
            )


def _dedupe_callers(callers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, int]] = set()
    deduped: list[dict[str, Any]] = []
    for caller in callers:
        key = (
            str(caller.get("importer_path", "")),
            str(caller.get("import_kind", "")),
            str(caller.get("import_name", "")),
            int(caller.get("line") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(caller))
    return sorted(
        deduped,
        key=lambda row: (
            str(row["importer_path"]),
            int(row["line"]),
            str(row["import_kind"]),
            str(row["import_name"]),
        ),
    )


def collect_shim_callers(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    retained = _planned_retained_shims(repo_root)
    shim_id_by_source = {
        row["source_fqn"]: shim_id for shim_id, row in retained.items()
    }
    migration_target_by_source = {
        row["source_fqn"]: row["migration_target"] for row in retained.values()
    }
    source_by_fqn = {row["source_fqn"]: shim_id for shim_id, row in retained.items()}
    rows: dict[str, list[dict[str, Any]]] = {shim_id: [] for shim_id in retained}

    for path in _iter_python_files(repo_root):
        rel_path = _rel(path, repo_root)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(text, filename=rel_path)
        except SyntaxError:
            tree = ast.Module(body=[], type_ignores=[])
        _scan_ast_imports(
            tree,
            rows=rows,
            importer_path=rel_path,
            source_by_fqn=source_by_fqn,
            shim_id_by_source=shim_id_by_source,
            migration_target_by_source=migration_target_by_source,
        )
        _scan_dynamic_strings(
            text,
            rows=rows,
            importer_path=rel_path,
            source_by_fqn=source_by_fqn,
            shim_id_by_source=shim_id_by_source,
            migration_target_by_source=migration_target_by_source,
        )

    shims: dict[str, Any] = {}
    total_callers = 0
    shims_with_source_callers = 0
    zero_caller_shims: list[str] = []
    for shim_id, entry in retained.items():
        callers = _dedupe_callers(rows[shim_id])
        total_callers += len(callers)
        if any(caller["caller_role"] == "source" for caller in callers):
            shims_with_source_callers += 1
        if not callers:
            zero_caller_shims.append(shim_id)
        shims[shim_id] = {
            "source_fqn": entry["source_fqn"],
            "migration_target": entry["migration_target"],
            "caller_count": len(callers),
            "callers": callers,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "generated_at": GENERATED_AT,
        "source_contract": SOURCE_CONTRACT,
        "scan": {
            "ast_imports": True,
            "text_fallback_dynamic_strings": True,
            "ignored_directories": sorted(IGNORED_DIR_NAMES),
        },
        "removal_policy": {"phase_2_3": REMOVAL_RULE},
        "summary": {
            "shim_count": len(shims),
            "caller_count": total_callers,
            "zero_caller_shim_count": len(zero_caller_shims),
            "zero_caller_shims": zero_caller_shims,
            "shims_with_first_party_source_callers": shims_with_source_callers,
        },
        "shims": shims,
    }


def validate_report(report: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append("unexpected schema_version")
    if report.get("phase") != PHASE:
        errors.append("unexpected phase")
    shims = report.get("shims")
    if not isinstance(shims, Mapping):
        return [*errors, "report.shims must be an object"]
    for shim_id, row in shims.items():
        if not isinstance(row, Mapping):
            errors.append(f"{shim_id}: shim row must be an object")
            continue
        for field in ("source_fqn", "migration_target", "caller_count", "callers"):
            if field not in row:
                errors.append(f"{shim_id}: missing {field}")
        callers = row.get("callers", [])
        if not isinstance(callers, list):
            errors.append(f"{shim_id}: callers must be a list")
            continue
        if row.get("caller_count") != len(callers):
            errors.append(f"{shim_id}: caller_count must equal len(callers)")
        for caller in callers:
            if not isinstance(caller, Mapping):
                errors.append(f"{shim_id}: caller must be an object")
                continue
            for field in (
                "importer_path",
                "import_kind",
                "import_name",
                "line",
                "migration_target",
                "caller_role",
                "intentional_compatibility_exercise",
            ):
                if field not in caller:
                    errors.append(f"{shim_id}: caller missing {field}")
            if caller.get("import_kind") not in {
                "import",
                "from_import",
                "from_import_submodule",
                "dynamic_string",
            }:
                errors.append(f"{shim_id}: unsupported import_kind")
            if caller.get("migration_target") != row.get("migration_target"):
                errors.append(f"{shim_id}: caller migration_target mismatch")
    return errors


def dump_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Validate the generated report")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    report = collect_shim_callers(repo_root)
    errors = validate_report(report) if args.check else []
    if errors:
        for error in errors:
            print(error, file=sys.stderr)  # noqa: T201
        return 1
    output = args.json_output if args.json_output.is_absolute() else repo_root / args.json_output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dump_json(report), encoding="utf-8")
    print(f"Wrote last-mile shim caller report JSON: {_rel(output, repo_root)}")  # noqa: T201
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
