#!/usr/bin/env python3
"""Fail-closed gate for Foundry methods namespace cutover."""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any

from repository_structure_phase0 import collect_gate_findings

METHOD_DOMAINS = (
    "bayesian",
    "causal",
    "dependence",
    "econometrics",
    "microsim",
    "ml",
    "network",
    "optimization",
    "spatial",
)

SCAN_ROOTS = ("src", "tests", "benchmarks", "tools")

IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".benchmarks",
    ".basedpyright",
    ".cache",
    ".uv-cache",
    ".venv",
    ".polisyos",
    "_cache",
    "__pycache__",
    "node_modules",
    "_build",
}

ALLOWED_DEEP_IMPORT_PROBES = {
    "tests/unit/foundry/methods/test_foundry_v2_migration.py",
    "tests/unit/foundry/methods/catalog/causal/test_synthetic_control_imports.py",
}

FLAT_FACADE_ROOT = Path("src") / "polisyos" / "foundry" / "methods"


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_python_files(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for root_name in SCAN_ROOTS:
        scan_root = repo_root / root_name
        if not scan_root.exists():
            continue
        for current, dir_names, file_names in os.walk(scan_root):
            dir_names[:] = [
                name
                for name in dir_names
                if name not in IGNORED_DIR_NAMES and not name.startswith(".")
            ]
            for file_name in file_names:
                if not file_name.endswith(".py"):
                    continue
                path = Path(current) / file_name
                resolved = path.resolve()
                if resolved not in seen:
                    paths.append(path)
                    seen.add(resolved)

    for path in sorted(repo_root.glob("*.py")):
        resolved = path.resolve()
        if resolved not in seen:
            paths.append(path)
            seen.add(resolved)
    return sorted(paths)


def _match_foundry_domain_module(module_name: str) -> tuple[str, str] | None:
    prefix = "polisyos.foundry.methods."
    if not module_name.startswith(prefix):
        return None
    suffix = module_name[len(prefix) :]
    if not suffix:
        return None
    parts = suffix.split(".")
    domain = parts[0]
    if domain not in METHOD_DOMAINS:
        return None
    kind = "facade" if len(parts) == 1 else "deep"
    return domain, kind


def _imported_names(node: ast.ImportFrom) -> list[str]:
    return [alias.asname or alias.name for alias in node.names]


def _call_module_literal(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first_arg = node.args[0]
    if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
        return None
    if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
        return first_arg.value
    if isinstance(node.func, ast.Name) and node.func.id == "__import__":
        return first_arg.value
    return None


def _record_importer(
    *,
    importers: list[dict[str, Any]],
    repo_root: Path,
    path: Path,
    lineno: int,
    module_name: str,
    usage: str,
    names: list[str] | None = None,
) -> None:
    match = _match_foundry_domain_module(module_name)
    if match is None:
        return
    domain, kind = match
    importers.append(
        {
            "path": _rel(path, repo_root),
            "line": lineno,
            "module": module_name,
            "domain": domain,
            "kind": kind,
            "usage": usage,
            "imported_names": sorted(names or []),
        }
    )


def collect_foundry_methods_external_importers(repo_root: Path) -> list[dict[str, Any]]:
    """Inventory imports that target the old flat Foundry method domain names."""
    repo_root = repo_root.resolve()
    importers: list[dict[str, Any]] = []
    for path in _iter_python_files(repo_root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _record_importer(
                        importers=importers,
                        repo_root=repo_root,
                        path=path,
                        lineno=node.lineno,
                        module_name=alias.name,
                        usage="import",
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                _record_importer(
                    importers=importers,
                    repo_root=repo_root,
                    path=path,
                    lineno=node.lineno,
                    module_name=node.module,
                    usage="from",
                    names=_imported_names(node),
                )
            elif isinstance(node, ast.Call):
                module_name = _call_module_literal(node)
                if module_name is not None:
                    _record_importer(
                        importers=importers,
                        repo_root=repo_root,
                        path=path,
                        lineno=node.lineno,
                        module_name=module_name,
                        usage="importlib_literal",
                    )
    return sorted(
        importers,
        key=lambda item: (
            item["path"],
            item["line"],
            item["module"],
            item["usage"],
            ",".join(item["imported_names"]),
        ),
    )


def _is_allowed_deep_import_probe(importer: dict[str, Any]) -> bool:
    return (
        importer["path"] in ALLOWED_DEEP_IMPORT_PROBES and importer["usage"] == "importlib_literal"
    )


def _deep_import_findings(importers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for importer in importers:
        if importer["kind"] != "deep" or _is_allowed_deep_import_probe(importer):
            continue
        findings.append(
            {
                "gate": "empty_namespace_gate",
                "severity": "error",
                "message": (
                    "Deep legacy Foundry methods import bypasses the Phase 1A "
                    "catalog/facade cutover."
                ),
                "path": importer["path"],
                "line": importer["line"],
                "module": importer["module"],
                "domain": importer["domain"],
                "usage": importer["usage"],
            }
        )
    return findings


def _flat_facade_wildcard_findings(repo_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for domain in METHOD_DOMAINS:
        path = repo_root / FLAT_FACADE_ROOT / f"{domain}.py"
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        except (OSError, SyntaxError) as exc:
            findings.append(
                {
                    "gate": "empty_namespace_gate",
                    "severity": "error",
                    "message": f"Flat Foundry method facade could not be parsed: {exc}",
                    "path": _rel(path, repo_root),
                    "domain": domain,
                }
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                findings.append(
                    {
                        "gate": "empty_namespace_gate",
                        "severity": "error",
                        "message": "Flat Foundry method facade must use explicit re-exports, not import *.",
                        "path": _rel(path, repo_root),
                        "line": node.lineno,
                        "domain": domain,
                    }
                )
    return findings


def _write_inventory(importers: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(importers, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--json", action="store_true", help="Emit JSON findings.")
    parser.add_argument(
        "--inventory-output",
        type=Path,
        help="Write the Foundry methods external-importer inventory to this JSON path.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    importers = collect_foundry_methods_external_importers(repo_root)
    findings = [
        *collect_gate_findings(repo_root, "empty_namespace"),
        *_deep_import_findings(importers),
        *_flat_facade_wildcard_findings(repo_root),
    ]
    if args.inventory_output is not None:
        output_path = args.inventory_output
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        _write_inventory(importers, output_path)
    if args.json:
        print(
            json.dumps(
                {
                    "mode": "fail-closed",
                    "findings": findings,
                    "external_importers": importers,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"empty_namespace_gate: {len(findings)} finding(s) [fail-closed]")
        for finding in findings:
            location = finding["path"]
            if "line" in finding:
                location = f"{location}:{finding['line']}"
            print(f"- {location}: {finding['message']}")
        if args.inventory_output is not None:
            print(f"external importer inventory: {len(importers)} import(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
