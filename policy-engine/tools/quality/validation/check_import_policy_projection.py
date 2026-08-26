#!/usr/bin/env python3
"""Check whether primary package contracts can project the import allow matrix."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.quality.lint.lint_imports import ImportCollector, module_name_for_path

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = Path("architecture/imports/policy.toml")
PACKAGE_CONTRACT_ROOT = Path("architecture/packages")


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build a complete, read-only contract-to-matrix reconciliation report."""
    repo_root = repo_root.resolve()
    policy = _read_toml(repo_root / POLICY_PATH)
    policy_header = policy.get("policy", {})
    internal_prefix = str(policy_header.get("internal_prefix", "polisyos"))
    known_roots = [str(item) for item in policy.get("roots", {}).get("known", [])]
    known_root_set = set(known_roots)
    committed_allow = {
        str(source): {str(target) for target in targets}
        for source, targets in policy.get("internal", {}).get("allow", {}).items()
        if isinstance(targets, list)
    }

    configuration_errors = _policy_configuration_errors(
        known_roots=known_roots,
        committed_allow=committed_allow,
    )
    discovery = _discover_primary_contracts(
        repo_root,
        internal_prefix=internal_prefix,
    )
    root_contracts = discovery["root_contracts"]
    missing_contract_roots = sorted(known_root_set - set(root_contracts))
    contract_roots_not_in_matrix = sorted(set(root_contracts) - known_root_set)

    projected_allow: dict[str, set[str]] = {}
    unrepresentable_dependency_rules: list[dict[str, str]] = []
    granularity_collapses: list[dict[str, str]] = []
    for source_root, contract in sorted(root_contracts.items()):
        if source_root not in known_root_set:
            continue
        targets = {source_root}
        source_blocked = False
        for dependency in contract["allowed_dependencies"]:
            if not dependency.startswith(f"{internal_prefix}."):
                unrepresentable_dependency_rules.append(
                    {
                        "dependency": dependency,
                        "source_root": source_root,
                    }
                )
                source_blocked = True
                continue
            parts = dependency.split(".")
            if len(parts) < 2 or parts[1] not in known_root_set:
                unrepresentable_dependency_rules.append(
                    {
                        "dependency": dependency,
                        "source_root": source_root,
                    }
                )
                source_blocked = True
                continue
            target_root = parts[1]
            targets.add(target_root)
            if len(parts) > 2:
                granularity_collapses.append(
                    {
                        "dependency": dependency,
                        "projected_target_root": target_root,
                        "source_root": source_root,
                    }
                )
        if not source_blocked:
            projected_allow[source_root] = targets

    imports_by_pair, ambiguous_import_sources = _live_imports_by_root_pair(
        repo_root,
        known_roots=known_root_set,
        internal_prefix=internal_prefix,
    )
    pair_differences: list[dict[str, Any]] = []
    for source_root, contract_targets in sorted(projected_allow.items()):
        matrix_targets = committed_allow.get(source_root, set())
        for target_root in sorted(matrix_targets ^ contract_targets):
            live_imports = imports_by_pair.get((source_root, target_root), [])
            pair_differences.append(
                {
                    "boundary_contract_allows": target_root in contract_targets,
                    "committed_matrix_allows": target_root in matrix_targets,
                    "contract_path": root_contracts[source_root]["path"],
                    "difference": (
                        "contract_only" if target_root in contract_targets else "policy_only"
                    ),
                    "live_file_count": len({item["path"] for item in live_imports}),
                    "live_imports": live_imports,
                    "live_statement_count": len(live_imports),
                    "source_root": source_root,
                    "target_root": target_root,
                }
            )

    live_pair_differences = [item for item in pair_differences if item["live_statement_count"] > 0]
    live_files = {
        item["path"] for difference in pair_differences for item in difference["live_imports"]
    }
    blockers_present = any(
        (
            configuration_errors,
            ambiguous_import_sources,
            discovery["contract_errors"],
            discovery["duplicate_root_contracts"],
            granularity_collapses,
            missing_contract_roots,
            contract_roots_not_in_matrix,
            unrepresentable_dependency_rules,
            pair_differences,
        )
    )
    return {
        "ambiguous_import_sources": ambiguous_import_sources,
        "configuration_errors": configuration_errors,
        "contract_errors": discovery["contract_errors"],
        "contract_roots_not_in_matrix": contract_roots_not_in_matrix,
        "duplicate_root_contracts": discovery["duplicate_root_contracts"],
        "granularity_collapses": sorted(
            granularity_collapses,
            key=lambda item: (item["source_root"], item["dependency"]),
        ),
        "live_file_count": len(live_files),
        "live_pair_difference_count": len(live_pair_differences),
        "live_statement_count": sum(int(item["live_statement_count"]) for item in pair_differences),
        "matrix_root_count": len(known_roots),
        "matrix_roots": known_roots,
        "missing_contract_roots": missing_contract_roots,
        "nested_primary_contracts": discovery["nested_primary_contracts"],
        "pair_difference_count": len(pair_differences),
        "pair_differences": pair_differences,
        "policy_path": POLICY_PATH.as_posix(),
        "primary_contract_file_count": len(discovery["primary_contract_paths"]),
        "primary_contract_paths": discovery["primary_contract_paths"],
        "primary_root_contract_count": len(root_contracts),
        "primary_root_contracts": {
            root: contract["path"] for root, contract in sorted(root_contracts.items())
        },
        "source_discovery": "architecture/packages/*.toml where package.primary_contract = true",
        "status": "blocked" if blockers_present else "ready",
        "unrepresentable_dependency_rules": sorted(
            unrepresentable_dependency_rules,
            key=lambda item: (item["source_root"], item["dependency"]),
        ),
    }


def _discover_primary_contracts(
    repo_root: Path,
    *,
    internal_prefix: str,
) -> dict[str, Any]:
    root_contracts: dict[str, dict[str, Any]] = {}
    primary_contract_paths: list[str] = []
    nested_primary_contracts: list[dict[str, str]] = []
    duplicate_root_contracts: list[dict[str, Any]] = []
    contract_errors: list[dict[str, str]] = []
    duplicate_paths: dict[str, list[str]] = defaultdict(list)

    for path in sorted((repo_root / PACKAGE_CONTRACT_ROOT).glob("*.toml")):
        data = _read_toml(path)
        package = data.get("package")
        if not isinstance(package, dict) or package.get("primary_contract") is not True:
            continue
        relative_path = _relative(path, repo_root)
        primary_contract_paths.append(relative_path)
        module_value = package.get("module")
        if not isinstance(module_value, str) or not module_value:
            contract_errors.append(
                {
                    "code": "primary_module_missing_or_invalid",
                    "path": relative_path,
                }
            )
            continue
        module = module_value
        module_parts = module.split(".")
        if len(module_parts) != 2 or module_parts[0] != internal_prefix:
            nested_primary_contracts.append({"module": module, "path": relative_path})
            continue
        root = module_parts[1]
        duplicate_paths[root].append(relative_path)
        boundaries = data.get("boundaries")
        allowed_dependencies = (
            boundaries.get("allowed_dependencies") if isinstance(boundaries, dict) else None
        )
        if not isinstance(allowed_dependencies, list) or not all(
            isinstance(item, str) for item in allowed_dependencies
        ):
            contract_errors.append(
                {
                    "code": "allowed_dependencies_missing_or_invalid",
                    "path": relative_path,
                }
            )
            continue
        root_contracts[root] = {
            "allowed_dependencies": allowed_dependencies,
            "path": relative_path,
        }

    for root, paths in sorted(duplicate_paths.items()):
        if len(paths) > 1:
            duplicate_root_contracts.append({"root": root, "paths": sorted(paths)})
            root_contracts.pop(root, None)

    return {
        "contract_errors": sorted(
            contract_errors,
            key=lambda item: (item["path"], item["code"]),
        ),
        "duplicate_root_contracts": duplicate_root_contracts,
        "nested_primary_contracts": sorted(
            nested_primary_contracts,
            key=lambda item: (item["module"], item["path"]),
        ),
        "primary_contract_paths": primary_contract_paths,
        "root_contracts": root_contracts,
    }


def _policy_configuration_errors(
    *,
    known_roots: list[str],
    committed_allow: dict[str, set[str]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not known_roots:
        errors.append({"code": "empty_matrix_roots"})
    duplicates = sorted(root for root in set(known_roots) if known_roots.count(root) > 1)
    if duplicates:
        errors.append({"code": "duplicate_matrix_roots", "roots": duplicates})
    missing_rows = sorted(set(known_roots) - set(committed_allow))
    extra_rows = sorted(set(committed_allow) - set(known_roots))
    if missing_rows:
        errors.append({"code": "missing_matrix_rows", "roots": missing_rows})
    if extra_rows:
        errors.append({"code": "unknown_matrix_rows", "roots": extra_rows})
    unknown_targets = sorted(
        {
            target
            for targets in committed_allow.values()
            for target in targets
            if target not in set(known_roots)
        }
    )
    if unknown_targets:
        errors.append({"code": "unknown_matrix_targets", "roots": unknown_targets})
    return errors


def _live_imports_by_root_pair(
    repo_root: Path,
    *,
    known_roots: set[str],
    internal_prefix: str,
) -> tuple[
    dict[tuple[str, str], list[dict[str, Any]]],
    list[dict[str, str]],
]:
    imports: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    ambiguous_sources: list[dict[str, str]] = []
    source_root_path = repo_root / "src" / internal_prefix
    if not source_root_path.is_dir():
        return {}, [
            {
                "error": "SourceTreeMissing",
                "path": _relative(source_root_path, repo_root),
            }
        ]
    src_root = repo_root / "src"

    for path in sorted(source_root_path.rglob("*.py")):
        module_result = module_name_for_path(src_root, path, internal_prefix)
        if module_result is None:
            ambiguous_sources.append(
                {
                    "error": "ModuleMappingError",
                    "path": _relative(path, repo_root),
                }
            )
            continue
        source_module, is_package = module_result
        source_parts = source_module.split(".")
        if len(source_parts) < 2:
            continue
        source_root = source_parts[1]
        if source_root not in known_roots:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            ambiguous_sources.append(
                {
                    "error": type(exc).__name__,
                    "path": _relative(path, repo_root),
                }
            )
            continue
        collector = ImportCollector(
            path,
            source_module,
            is_package,
            internal_prefix,
        )
        collector.visit(tree)
        for ref in collector.imports:
            target_parts = ref.target_module.split(".")
            if (
                len(target_parts) < 2
                or target_parts[0] != internal_prefix
                or target_parts[1] not in known_roots
                or target_parts[1] == source_root
            ):
                continue
            imports[(source_root, target_parts[1])].append(
                {
                    "line": ref.lineno,
                    "path": _relative(path, repo_root),
                }
            )

    for values in imports.values():
        values.sort(key=lambda item: (item["path"], item["line"]))
    return dict(imports), sorted(
        ambiguous_sources,
        key=lambda item: (item["path"], item["error"]),
    )


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only readiness check for projecting architecture/imports/policy.toml "
            "from primary package boundary contracts."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Return non-zero when the projection is incomplete or changes a pair verdict.",
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the read-only checker and print its complete JSON report."""
    args = _parse_args(argv)
    report = build_report(args.repo_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.check and report["status"] != "ready" else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))
