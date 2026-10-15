#!/usr/bin/env python3
"""Generate the Fabric best-in-class baseline inventory.

The inventory is intentionally read-only: it inspects repository files, emits a
machine-readable manifest, and renders the matching reference page. Phase 0 is
report-only, so ``--check`` only detects artifact drift and malformed accepted
risk records; it does not fail on ``missing`` or ``partial`` surfaces.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import (
    FileReadMeasurement,
    measure_file_reads,
    measured_is_dir,
    measured_is_file,
    measured_read_text,
)
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.fabric.io.atomic import atomic_write_text  # noqa: E402

SCHEMA_VERSION = "fabric.best_in_class_manifest.v1"
GENERATED_AT = "2026-04-26T00:00:00Z"
PHASE = 0
OWNER = "@fabric-owners"

STATUS_VALUES = (
    "implemented",
    "partial",
    "missing",
    "not_applicable",
    "accepted_risk",
    "blocked_by_research",
)
PRIORITY_VALUES = ("P0", "P1", "P2", "P3")
PLANES = ("source", "evidence", "semantics", "world", "trust")

DEFAULT_MANIFEST = (
    REPO_ROOT / "tools" / "quality" / "validation" / "fabric_best_in_class_manifest.json"
)
DEFAULT_REPORT = REPO_ROOT / "docs" / "reference" / "fabric" / "best-in-class-inventory.md"

FOLLOW_UP_PLACEHOLDER = "Follow-up placeholder: create a tracked issue before ratchet mode."


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--docs-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true", help="Fail if generated artifacts drift")
    parser.add_argument("--update", action="store_true", help="Rewrite manifest and report")
    return parser.parse_args(argv)


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _path_exists(path: Path) -> bool:
    """Probe whether a repository path is a file or directory, with a receipt."""
    return measured_is_file(path) or measured_is_dir(path)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path) -> str:
    if not _path_exists(path):
        return ""
    return measured_read_text(path, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not _path_exists(path):
        return {}
    try:
        payload = json.loads(measured_read_text(path, encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _contract_ids(path: Path) -> list[str]:
    return sorted(_contract_records(path))


def _contract_records(path: Path) -> dict[str, dict[str, Any]]:
    contracts = _load_json(path).get("contracts", {})
    if not isinstance(contracts, dict):
        return {}
    return {
        str(contract_id): meta for contract_id, meta in contracts.items() if isinstance(meta, dict)
    }


def _snapshot_records(path: Path, key: str) -> dict[str, dict[str, Any]]:
    records = _load_json(path).get(key, {})
    if not isinstance(records, dict):
        return {}
    return {str(record_id): meta for record_id, meta in records.items() if isinstance(meta, dict)}


def _source_contract_field_ids(contract: Mapping[str, Any]) -> set[str]:
    schema = contract.get("schema", {})
    if not isinstance(schema, Mapping):
        return set()
    fields = schema.get("fields", [])
    if not isinstance(fields, list):
        return set()
    field_ids: set[str] = set()
    for field in fields:
        if not isinstance(field, Mapping):
            continue
        field_id = field.get("field_id") or field.get("name")
        if field_id:
            field_ids.add(str(field_id))
    return field_ids


def _source_contract_field_policy_ids(contract: Mapping[str, Any]) -> set[str]:
    security = contract.get("security", {})
    if not isinstance(security, Mapping):
        return set()
    policies = security.get("field_policies", [])
    if not isinstance(policies, list):
        return set()
    return {
        str(policy.get("field_id"))
        for policy in policies
        if isinstance(policy, Mapping) and policy.get("field_id")
    }


def _source_contract_has_complete_field_policy_coverage(
    contract: Mapping[str, Any],
) -> bool:
    policy_ids = _source_contract_field_policy_ids(contract)
    if not policy_ids:
        return False
    if "*" in policy_ids:
        return True
    field_ids = _source_contract_field_ids(contract)
    return bool(field_ids) and field_ids.issubset(policy_ids)


def _source_contract_files(contract_id: str, connector_id: str) -> list[str]:
    module_by_connector = {
        "eurostat.data": ("eurostat.py", "eurostat_contracts.py"),
        "sdmx.source": ("sdmx_source.py", "sdmx_contracts.py"),
        "ukons.datasets": ("ukons.py", "ukons_contracts.py"),
        "worldbank.wdi": ("world_bank.py", "world_bank_contracts.py"),
        "wvs.wave7": ("wvs.py", "wvs_contracts.py"),
    }
    source_module, contract_module = module_by_connector.get(
        connector_id, ("__init__.py", "__init__.py")
    )
    return [
        f"src/polisyos/fabric/connectors/sources/{source_module}",
        f"src/polisyos/fabric/connectors/sources/_contracts/{contract_module}",
        "schemas/snapshots/fabric/connector_contract_registry.json",
    ]


def _parse_ast(path: Path) -> ast.Module | None:
    if not _path_exists(path):
        return None
    try:
        return ast.parse(measured_read_text(path, encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None


def _string_list_assignment(path: Path, name: str) -> list[str]:
    tree = _parse_ast(path)
    if tree is None:
        return []

    def _matches(target: ast.AST) -> bool:
        return isinstance(target, ast.Name) and target.id == name

    for node in tree.body:
        value: ast.AST | None = None
        is_named_assign = isinstance(node, ast.Assign) and any(
            _matches(target) for target in node.targets
        )
        is_named_annotated_assign = isinstance(node, ast.AnnAssign) and _matches(node.target)
        if is_named_assign or is_named_annotated_assign:
            value = node.value
        if isinstance(value, (ast.List, ast.Tuple)):
            return [
                item.value
                for item in value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
    return []


def _assigned_target_names(target: ast.AST) -> set[str]:
    """Return names bound by a simple assignment target."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_assigned_target_names(item) for item in target.elts))
    if isinstance(target, ast.Starred):
        return _assigned_target_names(target.value)
    return set()


def _literal_string_list(tree: ast.Module | None, name: str) -> tuple[list[str], bool, str]:
    """Return literal members, completeness, and a bounded reason when unresolved."""
    if tree is None:
        return [], False, "dynamic_or_non_string_public_export_list"
    assignments: list[ast.AST] = []
    target_node_ids: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            node_targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            node_targets = [node.target]
        else:
            continue
        matching_targets = [
            target for target in node_targets if name in _assigned_target_names(target)
        ]
        if matching_targets:
            assignments.append(node)
            target_node_ids.update(
                id(target)
                for matching_target in matching_targets
                for target in ast.walk(matching_target)
                if isinstance(target, ast.Name)
                and target.id == name
                and isinstance(target.ctx, ast.Store)
            )
    if len(assignments) != 1:
        return [], False, "dynamic_or_non_string_public_export_list"

    assignment = assignments[0]
    targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
    if len(targets) != 1 or not isinstance(targets[0], ast.Name) or targets[0].id != name:
        return [], False, "aliased_or_multi_target_public_export_assignment"

    uses_are_closed = all(
        isinstance(node.ctx, ast.Store) and id(node) in target_node_ids
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == name
    )
    if not uses_are_closed:
        return [], False, "dynamic_or_non_string_public_export_list"

    for node in tree.body:
        value: ast.AST | None = None
        targets: Sequence[ast.AST] = ()
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
            value = node.value
        if not any(name in _assigned_target_names(target) for target in targets):
            continue
        if not isinstance(value, (ast.List, ast.Tuple)):
            return [], False, "dynamic_or_non_string_public_export_list"
        members = [
            item.value
            for item in value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        complete = len(members) == len(value.elts)
        return members, complete, "" if complete else "dynamic_or_non_string_public_export_list"
    return [], False, "dynamic_or_non_string_public_export_list"


def _parse_ast_detail(path: Path) -> tuple[ast.Module | None, str | None]:
    if not _path_exists(path):
        return None, "file_missing"
    try:
        return ast.parse(measured_read_text(path, encoding="utf-8"), filename=str(path)), None
    except SyntaxError:
        return None, "syntax_error"
    except (OSError, UnicodeError) as error:
        return None, f"unreadable:{type(error).__name__}"


def _module_file(repo_root: Path, module_name: str) -> tuple[Path | None, str | None]:
    if not module_name.startswith("polisyos"):
        return None, "external_module"
    parts = module_name.split(".")
    source_root = repo_root / "src"
    if parts[0] != "polisyos":
        return None, "module_outside_source_root"
    stem = source_root.joinpath(*parts)
    candidates = [stem.with_suffix(".py"), stem / "__init__.py"]
    present = [path for path in candidates if _path_exists(path)]
    if len(present) == 1:
        return present[0], None
    if not present:
        return candidates[0], "module_missing"
    return None, "ambiguous_module_path"


def _import_bindings(
    tree: ast.Module, module_name: str, module_path: Path
) -> dict[str, tuple[str, str]]:
    """Map top-level import aliases to their statically named targets."""
    bindings: dict[str, tuple[str, str]] = {}
    is_package = module_path.name == "__init__.py"
    package = module_name if is_package else module_name.rpartition(".")[0]
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.level:
                package_parts = package.split(".")
                keep = max(0, len(package_parts) - node.level + 1)
                target_parts = package_parts[:keep]
                if node.module:
                    target_parts.extend(node.module.split("."))
                target_module = ".".join(target_parts)
            else:
                target_module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                bindings[alias.asname or alias.name] = (
                    "symbol",
                    f"{target_module}.{alias.name}" if target_module else alias.name,
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                bindings[local_name] = ("module", alias.name)
    return bindings


class _ModuleBindingVisitor(ast.NodeVisitor):
    """Collect statically visible module-scope bindings without executing source."""

    def __init__(self, symbol_name: str) -> None:
        self.symbol_name = symbol_name
        self.bindings: list[str] = []
        self.has_star_import = False

    def _record(self, name: str, kind: str) -> None:
        if name == self.symbol_name:
            self.bindings.append(kind)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._record(node.id, "assignment")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.asname or alias.name.split(".", 1)[0], "import")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                self.has_star_import = True
            else:
                self._record(alias.asname or alias.name, "import")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node.name, "class")
        for expression in (*node.decorator_list, *node.bases):
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node.name, "function")
        for expression in (*node.decorator_list, *node.args.defaults, *node.args.kw_defaults):
            if expression is not None:
                self.visit(expression)
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            if argument.annotation is not None:
                self.visit(argument.annotation)
        if node.args.vararg and node.args.vararg.annotation is not None:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation is not None:
            self.visit(node.args.kwarg.annotation)
        if node.returns is not None:
            self.visit(node.returns)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in (*node.args.defaults, *node.args.kw_defaults):
            if expression is not None:
                self.visit(expression)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self._record(node.name, "assignment")
        if node.type is not None:
            self.visit(node.type)
        for statement in node.body:
            self.visit(statement)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name is not None:
            self._record(node.name, "assignment")
        if node.pattern is not None:
            self.visit(node.pattern)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name is not None:
            self._record(node.name, "assignment")

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest is not None:
            self._record(node.rest, "assignment")
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # Comprehension targets have their own scope; walrus expressions in
        # the iterables/filters still execute in the containing module scope.
        self.visit(node.iter)
        for expression in node.ifs:
            self.visit(expression)


def _resolve_class_symbol(
    repo_root: Path,
    module_name: str,
    symbol_name: str,
    module_cache: dict[str, tuple[Path | None, ast.Module | None, str | None]],
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[str, Path | None, ast.Module | None, ast.ClassDef | None, str | None]:
    """Resolve an exported symbol through literal Python imports without importing code."""
    key = (module_name, symbol_name)
    if key in seen:
        return "unknown", None, None, None, "import_cycle"
    module = module_cache.get(module_name)
    if module is None:
        module_path, path_error = _module_file(repo_root, module_name)
        if module_path is None:
            module = (None, None, path_error or "module_unresolved")
        else:
            tree, parse_error = _parse_ast_detail(module_path)
            module = (module_path, tree, parse_error)
        module_cache[module_name] = module
    module_path, tree, module_error = module
    if module_error or module_path is None or tree is None:
        return "unknown", module_path, tree, None, module_error or "module_unreadable"

    binding_visitor = _ModuleBindingVisitor(symbol_name)
    binding_visitor.visit(tree)
    if binding_visitor.has_star_import:
        return "unknown", module_path, tree, None, "star_import_may_bind_symbol"
    if len(binding_visitor.bindings) > 1:
        return "unknown", module_path, tree, None, "symbol_rebound_in_module"

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == symbol_name:
            return "class", module_path, tree, node, None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol_name:
            return "function", module_path, tree, None, None
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if any(isinstance(target, ast.Name) and target.id == symbol_name for target in targets):
                return "unknown", module_path, tree, None, "assigned_symbol_alias_unresolved"

    bindings = _import_bindings(tree, module_name, module_path)
    binding = bindings.get(symbol_name)
    if binding is None:
        return "unknown", module_path, tree, None, "symbol_unresolved"
    kind, target = binding
    if kind != "symbol" or "." not in target:
        return "unknown", module_path, tree, None, "module_alias_not_class_symbol"
    target_module, target_symbol = target.rsplit(".", 1)
    return _resolve_class_symbol(
        repo_root,
        target_module,
        target_symbol,
        module_cache,
        seen | {key},
    )


def _base_target(
    expression: ast.expr,
    *,
    module_name: str,
    module_path: Path,
    tree: ast.Module,
) -> tuple[str | None, str | None]:
    while isinstance(expression, ast.Subscript):
        expression = expression.value
    if isinstance(expression, ast.Name):
        name = expression.id
        bindings = _import_bindings(tree, module_name, module_path)
        binding = bindings.get(name)
        if binding is not None:
            kind, target = binding
            if kind == "symbol":
                return target, None
            return target, None
        if name in {"object", "Protocol"}:
            return f"builtins.{name}" if name == "object" else "typing.Protocol", None
        return None, f"base_name_unresolved:{name}"
    if isinstance(expression, ast.Attribute):
        parts: list[str] = []
        current: ast.expr = expression
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None, "dynamic_base_expression"
        parts.append(current.id)
        dotted = ".".join(reversed(parts))
        first, _, remainder = dotted.partition(".")
        binding = _import_bindings(tree, module_name, module_path).get(first)
        if binding is None:
            return None, f"base_attribute_unresolved:{dotted}"
        kind, target = binding
        if kind == "module":
            return f"{target}.{remainder}" if remainder else target, None
        return f"{target}.{remainder}" if remainder else target, None
    return None, "dynamic_base_expression"


def _declared_class_slots(class_node: ast.ClassDef) -> set[str]:
    declared: set[str] = set()
    for node in class_node.body:
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.value is not None:
                declared.add(node.target.id)
        elif isinstance(node, ast.Assign):
            declared.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return declared


def _base_connector_ancestry(
    repo_root: Path,
    module_name: str,
    module_path: Path,
    tree: ast.Module,
    class_node: ast.ClassDef,
    *,
    base_connector: str,
    module_cache: dict[str, tuple[Path | None, ast.Module | None, str | None]],
    seen: frozenset[str] = frozenset(),
) -> tuple[bool, list[str]]:
    class_fqn = f"{module_name}.{class_node.name}"
    if class_fqn in seen:
        return False, [f"inheritance_cycle:{class_fqn}"]
    unresolved: list[str] = []
    for expression in class_node.bases:
        target, target_error = _base_target(
            expression,
            module_name=module_name,
            module_path=module_path,
            tree=tree,
        )
        if target_error:
            unresolved.append(target_error)
            continue
        if target == base_connector:
            return True, unresolved
        if target is None or target in {"builtins.object", "typing.Protocol", "typing.Generic"}:
            continue
        if target.startswith("typing.") or target.startswith("typing_extensions."):
            continue
        if not target.startswith("polisyos."):
            unresolved.append(f"external_base_not_inspected:{target}")
            continue
        base_module, _, base_symbol = target.rpartition(".")
        kind, base_path, base_tree, base_node, resolve_error = _resolve_class_symbol(
            repo_root,
            base_module,
            base_symbol,
            module_cache,
        )
        if (
            resolve_error
            or kind != "class"
            or base_path is None
            or base_tree is None
            or base_node is None
        ):
            unresolved.append(f"base_class_unresolved:{target}:{resolve_error or kind}")
            continue
        inherited, inherited_unresolved = _base_connector_ancestry(
            repo_root,
            base_module,
            base_path,
            base_tree,
            base_node,
            base_connector=base_connector,
            module_cache=module_cache,
            seen=seen | {class_fqn},
        )
        if inherited:
            return True, unresolved + inherited_unresolved
        unresolved.extend(inherited_unresolved)
    return False, unresolved


def _source_connector_exports(
    repo_root: Path,
    source_init: Path,
) -> tuple[list[str], dict[str, Any]]:
    """Resolve literal public exports to statically declared BaseConnector classes."""
    source_module = "polisyos.fabric.connectors.sources"
    base_module = "polisyos.fabric.connectors.base"
    module_cache: dict[str, tuple[Path | None, ast.Module | None, str | None]] = {}
    unresolved: list[dict[str, str]] = []
    source_tree, source_error = _parse_ast_detail(source_init)
    exports, literal_exports_complete, literal_exports_error = _literal_string_list(
        source_tree, "__all__"
    )
    if source_error:
        unresolved.append({"export": "__all__", "reason": source_error})
    elif not literal_exports_complete:
        unresolved.append({"export": "__all__", "reason": literal_exports_error})
    if len(set(exports)) != len(exports):
        unresolved.append({"export": "__all__", "reason": "duplicate_public_export_name"})

    base_path, base_path_error = _module_file(repo_root, base_module)
    base_tree: ast.Module | None = None
    if base_path is not None:
        base_tree, base_parse_error = _parse_ast_detail(base_path)
        base_path_error = base_parse_error
    interface_slots: set[str] = set()
    base_connector_name = ""
    interface_found = False
    if base_tree is not None and base_path is not None:
        for node in base_tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "SourceConnector":
                interface_found = True
                interface_slots = {
                    item.target.id
                    for item in node.body
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
                }
            elif isinstance(node, ast.ClassDef) and node.name == "BaseConnector":
                base_connector_name = node.name
    if base_path_error or not interface_found or not interface_slots or not base_connector_name:
        unresolved.append(
            {
                "export": "SourceConnector/BaseConnector interface",
                "reason": base_path_error or "canonical_connector_interface_unresolved",
            }
        )

    concrete: set[str] = set()
    excluded: list[dict[str, str]] = []
    for export in exports:
        kind, module_path, tree, class_node, resolve_error = _resolve_class_symbol(
            repo_root,
            source_module,
            export,
            module_cache,
        )
        if resolve_error:
            unresolved.append({"export": export, "reason": resolve_error})
            continue
        if kind != "class" or module_path is None or tree is None or class_node is None:
            excluded.append(
                {
                    "export": export,
                    "reason": f"resolved_symbol_is_{kind}",
                }
            )
            continue
        resolved_module = next(
            (
                module_name
                for module_name, cached in module_cache.items()
                if cached[0] == module_path and cached[1] is tree
            ),
            source_module,
        )
        is_connector, base_errors = _base_connector_ancestry(
            repo_root,
            resolved_module,
            module_path,
            tree,
            class_node,
            base_connector=f"{base_module}.{base_connector_name}",
            module_cache=module_cache,
        )
        if base_errors:
            unresolved.extend({"export": export, "reason": error} for error in base_errors)
        if not is_connector:
            if base_errors:
                continue
            excluded.append(
                {
                    "export": export,
                    "reason": "class_not_descendant_of_canonical_BaseConnector",
                }
            )
            continue
        missing_slots = sorted(interface_slots - _declared_class_slots(class_node))
        if missing_slots:
            excluded.append(
                {
                    "export": export,
                    "reason": "missing_declared_SourceConnector_slots:" + ",".join(missing_slots),
                }
            )
        else:
            concrete.add(export)

    unresolved = sorted(unresolved, key=lambda item: (item["export"], item["reason"]))
    excluded = sorted(excluded, key=lambda item: (item["export"], item["reason"]))
    complete = literal_exports_complete and not unresolved
    return sorted(exports), {
        "declared_exports": sorted(exports),
        "concrete_connector_count": len(concrete),
        "concrete_connectors": sorted(concrete),
        "excluded_exports": excluded,
        "inventory_complete": complete,
        "unresolved_exports": unresolved,
        "selection": "literal sources.__all__ entries resolving to classes that inherit the canonical BaseConnector and declare SourceConnector identity slots",
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _source_profile_ids(path: Path) -> list[str]:
    tree = _parse_ast(path)
    if tree is None:
        return []
    profile_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != "SourceProfile":
            continue
        for keyword in node.keywords:
            if keyword.arg == "profile_id" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    profile_ids.append(keyword.value.value)
                    break
    return sorted(profile_ids)


def _fabric_connector_entrypoints(path: Path) -> dict[str, str]:
    if not _path_exists(path):
        return {}
    try:
        payload = tomllib.loads(measured_read_text(path, encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}
    project = payload.get("project", {})
    if not isinstance(project, dict):
        return {}
    entry_points = project.get("entry-points", {})
    if not isinstance(entry_points, dict):
        return {}
    raw = entry_points.get("polisyos.fabric_connectors", {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in sorted(raw.items())}


def _existing_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    return [path for path in paths if _path_exists(repo_root / path)]


def _python_files(
    repo_root: Path,
    directory: str,
    *,
    reads: FileReadMeasurement,
) -> list[str]:
    root = repo_root / directory
    if not measured_is_dir(root):
        return []
    try:
        matches = sorted(root.glob("*.py"))
    except OSError as error:
        reads.record(
            root,
            "glob",
            status="unreadable",
            pattern="*.py",
            error=type(error).__name__,
        )
        raise
    selected = [path for path in matches if path.name != "__init__.py"]
    reads.record(
        root,
        "glob",
        status="read",
        pattern="*.py",
        matched_paths=[_rel(path, repo_root) for path in matches],
        excluded_paths=[_rel(path, repo_root) for path in matches if path.name == "__init__.py"],
        selected_paths=[_rel(path, repo_root) for path in selected],
    )
    return [_rel(path, repo_root) for path in selected]


def _python_files_recursive(
    repo_root: Path,
    directory: str,
    *,
    reads: FileReadMeasurement,
) -> list[str]:
    root = repo_root / directory
    if not measured_is_dir(root):
        return []
    try:
        matches = sorted(root.rglob("*.py"))
    except OSError as error:
        reads.record(
            root,
            "rglob",
            status="unreadable",
            pattern="**/*.py",
            error=type(error).__name__,
        )
        raise
    selected = [_rel(path, repo_root) for path in matches]
    reads.record(
        root,
        "rglob",
        status="read",
        pattern="**/*.py",
        matched_paths=selected,
        excluded_paths=[],
        selected_paths=selected,
    )
    return selected


def _has_token(path: Path, token: str) -> bool:
    return token in _read_text(path)


def _client_operation_token(operation_id: str) -> str:
    parts = operation_id.split("_")
    return "".join(
        part if index == 0 else part[:1].upper() + part[1:] for index, part in enumerate(parts)
    )


def _surface(
    *,
    surface_id: str,
    plane: str,
    status: str,
    priority: str,
    title: str,
    description: str,
    source_files: Iterable[str] = (),
    tests: Iterable[str] = (),
    docs: Iterable[str] = (),
    evidence: Mapping[str, Any] | None = None,
    follow_up: str | None = None,
    accepted_risk: Mapping[str, Any] | None = None,
    owner: str = OWNER,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": surface_id,
        "plane": plane,
        "status": status,
        "priority": priority,
        "severity": priority,
        "phase": PHASE,
        "owner": owner,
        "title": title,
        "description": description,
        "source_files": sorted(source_files),
        "tests": sorted(tests),
        "docs": sorted(docs),
        "evidence": dict(evidence or {}),
    }
    if status in {"partial", "missing", "blocked_by_research"}:
        row["follow_up"] = follow_up or FOLLOW_UP_PLACEHOLDER
    elif follow_up:
        row["follow_up"] = follow_up
    if status == "accepted_risk":
        row["accepted_risk"] = dict(accepted_risk or {})
    return row


def _status_if(condition: bool, *, partial_when_false: bool = False) -> str:
    if condition:
        return "implemented"
    return "partial" if partial_when_false else "missing"


def _status_counts(surfaces: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(STATUS_VALUES, 0)
    for surface in surfaces:
        status = str(surface.get("status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def _plane_counts(surfaces: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(PLANES, 0)
    for surface in surfaces:
        plane = str(surface.get("plane", ""))
        if plane in counts:
            counts[plane] += 1
    return counts


def _input_receipt_digest(receipt: Mapping[str, Any]) -> str:
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _input_receipt_summary(receipt: Mapping[str, Any]) -> str:
    inputs = receipt.get("inputs", [])
    input_rows = inputs if isinstance(inputs, list) else []
    return (
        f"sha256={_input_receipt_digest(receipt)}; explicit_operations={len(input_rows)}; "
        f"complete_verdict={str(receipt.get('complete_verdict', False)).lower()}"
    )


def _input_receipt_snapshot(
    reads: FileReadMeasurement,
    *,
    scope: str = "Manifest derivation records explicit filesystem reads, file/directory probes, "
    "and selected Python glob results.",
) -> dict[str, Any]:
    receipt = reads.snapshot(complete_verdict=False)
    receipt["scope"] = scope
    receipt["selector"] = (
        "Connector export inventory is bounded to literal names in "
        "src/polisyos/fabric/connectors/sources/__init__.py::__all__."
    )
    receipt["unresolved_by_construction"].extend(
        [
            "Runtime imports, plugin entry-point execution, Git/subprocess reads, and external "
            "services are not observed; the connector count is a static source declaration, "
            "not proof of installed or operational connectors.",
            "JSON, TOML, and Python AST readers consume only the structures and fields named "
            "by this inventory; unselected document semantics are not validated here.",
        ]
    )
    return receipt


def _paths(repo_root: Path) -> dict[str, Path]:
    return {
        "pyproject": repo_root / "pyproject.toml",
        "fabric_contract_snapshot": repo_root
        / "schemas"
        / "snapshots"
        / "fabric"
        / "connector_contract_registry.json",
        "legacy_contract_snapshot": repo_root
        / "schemas"
        / "snapshots"
        / "connectors"
        / "contracts.json",
        "source_contract_v2": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "contracts"
        / "source_contract.py",
        "source_contract_schema": repo_root / "schemas" / "fabric" / "source_contract.schema.json",
        "processing_guarantees": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "quality"
        / "processing_guarantees.py",
        "processing_guarantee_schema": repo_root
        / "schemas"
        / "fabric"
        / "processing_guarantee.schema.json",
        "processing_guarantees_validator": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_processing_guarantees.py",
        "processing_guarantees_doc": repo_root
        / "docs"
        / "reference"
        / "fabric"
        / "processing-guarantees.md",
        "catalog_discovery": repo_root / "src" / "polisyos" / "fabric" / "catalog" / "discovery.py",
        "entity_resolution_models": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "entity_resolution"
        / "models.py",
        "entity_resolution_store": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "entity_resolution"
        / "store.py",
        "discovery_intelligence_validator": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_discovery_intelligence.py",
        "discovery_eval_fixture": repo_root / "tests" / "_data" / "fabric" / "discovery_eval.json",
        "discovery_intelligence_doc": repo_root
        / "docs"
        / "reference"
        / "fabric"
        / "discovery-intelligence.md",
        "source_scorecard_schema": repo_root
        / "schemas"
        / "fabric"
        / "source_scorecard.schema.json",
        "source_contract_snapshot_v2": repo_root
        / "schemas"
        / "snapshots"
        / "fabric"
        / "source_contracts_v2.json",
        "source_scorecard_snapshot": repo_root
        / "schemas"
        / "snapshots"
        / "fabric"
        / "source_scorecards.json",
        "source_contracts_validator": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_source_contracts.py",
        "wave2_strict_validator": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_wave2_strict_closure.py",
        "connector_sdk": repo_root / "src" / "polisyos" / "fabric" / "connectors" / "sdk",
        "conformance_v2": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "testing"
        / "conformance.py",
        "scorecard": repo_root / "src" / "polisyos" / "fabric" / "connectors" / "scorecard.py",
        "decision_data": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "evidence"
        / "decision_data.py",
        "trust_envelope_schema": repo_root / "schemas" / "fabric" / "trust_envelope.schema.json",
        "decision_data_coverage": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_decision_data_coverage.py",
        "decision_data_coverage_report": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_decision_data_coverage.json",
        "product_integration": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "product_integration"
        / "__init__.py",
        "compatibility": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "_internal"
        / "compatibility.py",
        "product_integration_validator": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_product_integration.py",
        "product_integration_doc": repo_root
        / "docs"
        / "reference"
        / "fabric"
        / "product-api-integration.md",
        "runtime_openapi": repo_root / "schemas" / "runtime_api_v1.openapi.json",
        "runtime_client_ts": repo_root
        / "packages"
        / "runtime-api-client"
        / "canonicalRuntimeApiClient.ts",
        "dashboard_fixture_registry": repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "test"
        / "contracts"
        / "runtimeContractFixtures.ts",
        "dashboard_validators": repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "api"
        / "validators.ts",
        "dashboard_fabric_decision_adapter": repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "shared"
        / "ui"
        / "quantity"
        / "fabric-decision-data.ts",
        "dashboard_fabric_decision_hook": repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "api"
        / "hooks"
        / "useRunFabricDecisionData.ts",
        "dashboard_fixture_dir": repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "test"
        / "contracts"
        / "fixtures",
        "source_platform_doc": repo_root / "docs" / "reference" / "fabric" / "source-platform.md",
        "source_init": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "sources"
        / "__init__.py",
        "builtin_profiles": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "profiles"
        / "builtin_profiles.py",
        "quality": repo_root / "src" / "polisyos" / "fabric" / "quality" / "__init__.py",
        "fitness_report": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "fitness_report"
        / "__init__.py",
        "observability": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "_adapters"
        / "observability.py",
        "core_metrics_base": repo_root
        / "src"
        / "polisyos"
        / "core"
        / "observability"
        / "_metrics_registry_base.py",
        "core_metrics_parts": repo_root
        / "src"
        / "polisyos"
        / "core"
        / "observability"
        / "metrics_parts.py",
        "connector_governance_metadata": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "governance_metadata.py",
        "connector_quality": repo_root / "src" / "polisyos" / "fabric" / "connectors" / "quality",
        "quality_evidence": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "quality"
        / "evidence.py",
        "scientist_quality_gate": repo_root
        / "src"
        / "polisyos"
        / "scientist"
        / "governance"
        / "passes"
        / "quality_gate_pass.py",
        "schema_governance": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_schema_governance.py",
        "streaming": repo_root / "src" / "polisyos" / "fabric" / "data_plane" / "streaming.py",
        "benchmarks": repo_root / "src" / "polisyos" / "fabric" / "data_plane" / "benchmarks.py",
        "orchestrator": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "data_plane"
        / "orchestrator.py",
        "replay_store": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "data_plane"
        / "replay_store.py",
        "quarantine": repo_root / "src" / "polisyos" / "fabric" / "data_plane" / "quarantine.py",
        "evidence": repo_root / "src" / "polisyos" / "fabric" / "evidence" / "__init__.py",
        "lineage": repo_root / "src" / "polisyos" / "fabric" / "provenance" / "lineage.py",
        "provo": repo_root / "src" / "polisyos" / "fabric" / "provenance" / "export_provo.py",
        "world_query": repo_root / "src" / "polisyos" / "fabric" / "world" / "query.py",
        "snapshots": repo_root / "src" / "polisyos" / "fabric" / "world" / "store" / "snapshots.py",
        "world_segments": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "world"
        / "store"
        / "segments.py",
        "world_emit": repo_root / "src" / "polisyos" / "fabric" / "world" / "store" / "emit.py",
        "world_kuzu": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "world"
        / "materialize"
        / "kuzu.py",
        "retention": repo_root / "src" / "polisyos" / "fabric" / "security" / "retention.py",
        "world_branch_schema": repo_root / "schemas" / "fabric" / "world_branch.schema.json",
        "scenario_branch_schema": repo_root / "schemas" / "fabric" / "scenario_branch.schema.json",
        "world_duckdb_ddl": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "world"
        / "ddl"
        / "duckdb_world.sql",
        "temporal_route": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "routes"
        / "temporal.py",
        "temporal_service": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "temporal.py",
        "runs_route": repo_root / "src" / "polisyos" / "runtime" / "http" / "routes" / "runs.py",
        "lineage_route": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "routes"
        / "lineage.py",
        "lineage_service": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "lineage.py",
        "fabric_route": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "routes"
        / "fabric.py",
        "fabric_service": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "fabric.py",
        "scientist_fabric_trust_gate": repo_root
        / "src"
        / "polisyos"
        / "scientist"
        / "governance"
        / "passes"
        / "fabric_trust_gate_pass.py",
        "scientist_readiness": repo_root
        / "src"
        / "polisyos"
        / "scientist"
        / "methods"
        / "search"
        / "readiness.py",
        "scholar_provenance": repo_root / "src" / "polisyos" / "scholar" / "provenance.py",
        "lex_provenance": repo_root / "src" / "polisyos" / "lex" / "provenance.py",
        "foundry_calibration_fabric": repo_root
        / "src"
        / "polisyos"
        / "foundry"
        / "calibration"
        / "fabric_quality.py",
        "foundry_uncertainty_fabric": repo_root
        / "src"
        / "polisyos"
        / "foundry"
        / "uncertainty"
        / "fabric_quality.py",
        "access_control": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "security"
        / "access_control.py",
        "column_mask": repo_root / "src" / "polisyos" / "fabric" / "security" / "column_mask.py",
        "pii_stage": repo_root / "src" / "polisyos" / "fabric" / "pii" / "stage.py",
        "fabric_facade": repo_root / "src" / "polisyos" / "fabric" / "__init__.py",
        "ir_connectors": repo_root / "src" / "polisyos" / "ir" / "connectors" / "__init__.py",
    }


def _tests_by_plane(repo_root: Path) -> dict[str, list[str]]:
    raw = {
        "source": [
            "tests/unit/fabric/connectors/test_contract_system.py",
            "tests/unit/fabric/connectors/test_protocol_compliance.py",
            "tests/unit/fabric/connectors/test_registry.py",
            "tests/unit/fabric/connectors/test_source_contract_v2.py",
            "tests/unit/fabric/connectors/profiles/test_source_profiles.py",
            "tests/unit/fabric/data_plane/test_processing_guarantees.py",
            "tests/repo_quality/tools/test_fabric_schema_governance.py",
            "tests/repo_quality/tools/test_fabric_source_contracts.py",
            "tests/repo_quality/tools/test_fabric_processing_guarantees.py",
        ],
        "evidence": [
            "tests/unit/fabric/data_plane/test_record_replay.py",
            "tests/unit/fabric/data_plane/test_quarantine.py",
            "tests/unit/fabric/data_plane/test_streaming_runtime.py",
            "tests/unit/fabric/data_plane/test_processing_guarantees.py",
            "tests/unit/fabric/data_plane/test_benchmarks.py",
            "tests/unit/fabric/data_plane/test_orchestrator.py",
            "tests/unit/fabric/test_ingestion_quarantine.py",
            "tests/unit/fabric/test_provenance.py",
            "tests/unit/fabric/connectors/test_source_contract_v2.py",
            "tests/repo_quality/tools/test_fabric_source_contracts.py",
            "tests/repo_quality/tools/test_fabric_processing_guarantees.py",
        ],
        "semantics": [
            "tests/unit/fabric/test_quality_indicators.py",
            "tests/unit/fabric/connectors/test_quality_system.py",
            "tests/unit/fabric/connectors/test_quality_statistics.py",
            "tests/unit/fabric/connectors/test_schema_system.py",
            "tests/unit/fabric/connectors/test_source_contract_v2.py",
            "tests/unit/fabric/test_discovery_intelligence.py",
            "tests/unit/fabric/test_entity_resolution.py",
            "tests/repo_quality/tools/test_fabric_schema_governance.py",
            "tests/repo_quality/tools/test_fabric_source_contracts.py",
            "tests/repo_quality/tools/test_fabric_discovery_intelligence.py",
        ],
        "world": [
            "tests/unit/fabric/test_world_time_travel.py",
            "tests/unit/fabric/test_world_materialization.py",
            "tests/unit/fabric/test_world_branch_governance.py",
            "tests/unit/fabric/test_world_temporal_capabilities.py",
            "tests/unit/fabric/test_entity_resolution.py",
            "tests/unit/fabric/test_world_query_multibackend.py",
            "tests/unit/runtime/http/test_temporal_api.py",
            "tests/unit/runtime/http/test_temporal_routes.py",
        ],
        "trust": [
            "tests/unit/fabric/test_lineage.py",
            "tests/unit/fabric/test_decision_data_envelope.py",
            "tests/unit/fabric/test_fabric_observability.py",
            "tests/unit/fabric/test_observability_governance_quality_phase4.py",
            "tests/unit/fabric/test_provenance.py",
            "tests/unit/fabric/test_discovery_intelligence.py",
            "tests/unit/fabric/test_entity_resolution.py",
            "tests/unit/fabric/test_access_control.py",
            "tests/unit/fabric/test_duckdb_storage_access_control.py",
            "tests/unit/fabric/test_world_query_column_masking.py",
            "tests/unit/fabric/connectors/test_source_contract_v2.py",
            "tests/unit/runtime/http/test_lineage_api.py",
            "tests/unit/runtime/http/test_lineage_routes.py",
            "tests/repo_quality/tools/test_fabric_source_contracts.py",
            "tests/repo_quality/tools/test_fabric_decision_data_coverage.py",
            "tests/repo_quality/tools/test_fabric_discovery_intelligence.py",
            "tests/repo_quality/tools/test_fabric_product_integration.py",
            "tests/unit/fabric/test_product_integration.py",
            "tests/unit/runtime/http/test_fabric_integration_routes.py",
            "tests/unit/scientist/governance/test_fabric_trust_gate_pass.py",
            "tests/unit/scholar/test_fabric_provenance.py",
            "tests/unit/lex/test_fabric_provenance.py",
            "tests/unit/foundry/calibration/test_fabric_quality.py",
            "tests/unit/foundry/uncertainty/test_fabric_quality.py",
        ],
    }
    return {plane: _existing_paths(repo_root, paths) for plane, paths in raw.items()}


def _build_surfaces(
    repo_root: Path,
    *,
    reads: FileReadMeasurement,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = _paths(repo_root)
    fabric_contract_records = _contract_records(paths["fabric_contract_snapshot"])
    fabric_contract_ids = _contract_ids(paths["fabric_contract_snapshot"])
    legacy_contract_ids = _contract_ids(paths["legacy_contract_snapshot"])
    source_contract_v2_records = _contract_records(paths["source_contract_snapshot_v2"])
    source_contract_v2_ids = sorted(source_contract_v2_records)
    source_scorecard_records = _snapshot_records(paths["source_scorecard_snapshot"], "scorecards")
    source_contract_v2_payloads = [
        record.get("contract", {}) for record in source_contract_v2_records.values()
    ]
    source_v2_replay_fixture_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("replay"), Mapping)
        and contract["replay"].get("fixture_ref")
    )
    source_v2_non_replayable_reason_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("replay"), Mapping)
        and contract["replay"].get("non_replayable_reason")
    )
    source_v2_classification_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("security"), Mapping)
        and contract["security"].get("classification")
    )
    source_v2_field_policy_contract_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping) and bool(_source_contract_field_policy_ids(contract))
    )
    source_v2_field_policy_count = sum(
        len(_source_contract_field_policy_ids(contract))
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
    )
    source_v2_field_policy_coverage_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and _source_contract_has_complete_field_policy_coverage(contract)
    )
    source_v2_bounded_read_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("quality"), Mapping)
        and "bounded_reads"
        in {str(check).casefold() for check in contract["quality"].get("required_checks", [])}
    )
    source_v2_processing_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("processing"), Mapping)
        and contract["processing"].get("guarantee")
    )
    source_v2_dedupe_window_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("processing"), Mapping)
        and isinstance(contract["processing"].get("idempotency"), Mapping)
        and int(contract["processing"]["idempotency"].get("dedupe_window_seconds") or 0) > 0
    )
    source_v2_replay_retention_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("processing"), Mapping)
        and isinstance(contract["processing"].get("idempotency"), Mapping)
        and int(contract["processing"]["idempotency"].get("replay_retention_days") or 0) > 0
    )
    source_v2_owner_reviewer_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping) and contract.get("owner") and contract.get("reviewer")
    )
    entrypoints = _fabric_connector_entrypoints(paths["pyproject"])
    source_exports, connector_export_inventory = _source_connector_exports(
        repo_root,
        paths["source_init"],
    )
    source_tree_files = _python_files_recursive(
        repo_root,
        "src/polisyos/fabric/connectors/sources",
        reads=reads,
    )
    concrete_connectors = connector_export_inventory["concrete_connectors"]
    profile_ids = _source_profile_ids(paths["builtin_profiles"])
    quality_modules = _python_files(
        repo_root,
        "src/polisyos/fabric/connectors/quality",
        reads=reads,
    )
    public_exports = _string_list_assignment(paths["fabric_facade"], "__all__")
    tests_by_plane = _tests_by_plane(repo_root)

    source_contract_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/connectors/test_contract_system.py",
            "tests/unit/fabric/connectors/test_schema_system.py",
            "tests/unit/fabric/connectors/test_source_contract_v2.py",
            "tests/repo_quality/tools/test_fabric_schema_governance.py",
            "tests/repo_quality/tools/test_fabric_source_contracts.py",
        ],
    )
    source_platform_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/connectors/test_source_contract_v2.py",
            "tests/repo_quality/tools/test_fabric_source_contracts.py",
        ],
    )
    processing_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/data_plane/test_processing_guarantees.py",
            "tests/unit/fabric/data_plane/test_streaming_runtime.py",
            "tests/unit/fabric/data_plane/test_benchmarks.py",
            "tests/unit/fabric/data_plane/test_orchestrator.py",
            "tests/repo_quality/tools/test_fabric_processing_guarantees.py",
        ],
    )
    discovery_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/test_discovery_intelligence.py",
            "tests/unit/fabric/test_entity_resolution.py",
            "tests/repo_quality/tools/test_fabric_discovery_intelligence.py",
        ],
    )
    profile_tests = _existing_paths(
        repo_root, ["tests/unit/fabric/connectors/profiles/test_source_profiles.py"]
    )
    quality_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/test_quality_indicators.py",
            "tests/unit/fabric/connectors/test_quality_system.py",
            "tests/unit/fabric/connectors/test_quality_statistics.py",
        ],
    )
    phase4_tests = _existing_paths(
        repo_root,
        ["tests/unit/fabric/test_observability_governance_quality_phase4.py"],
    )
    lineage_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/test_lineage.py",
            "tests/unit/fabric/test_fabric_observability.py",
        ],
    )
    temporal_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/test_world_time_travel.py",
            "tests/unit/fabric/test_world_materialization.py",
            "tests/unit/fabric/test_world_branch_governance.py",
            "tests/unit/fabric/test_world_temporal_capabilities.py",
            "tests/unit/runtime/http/test_temporal_api.py",
            "tests/unit/runtime/http/test_temporal_routes.py",
        ],
    )
    replay_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/data_plane/test_record_replay.py",
            "tests/unit/fabric/data_plane/test_quarantine.py",
            "tests/unit/fabric/test_ingestion_quarantine.py",
        ],
    )
    access_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/test_access_control.py",
            "tests/unit/fabric/test_duckdb_storage_access_control.py",
            "tests/unit/fabric/test_world_query_column_masking.py",
        ],
    )
    facade_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/test_connector_bridge.py",
            "tests/unit/fabric/test_world_query_multibackend.py",
            "tests/unit/runtime/http/test_e2e_ingestion.py",
        ],
    )
    decision_data_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/fabric/test_decision_data_envelope.py",
            "tests/unit/runtime/http/test_lineage_routes.py",
            "tests/unit/runtime/http/test_temporal_routes.py",
            "tests/repo_quality/tools/test_fabric_decision_data_coverage.py",
        ],
    )
    product_integration_tests = _existing_paths(
        repo_root,
        [
            "tests/unit/runtime/http/test_fabric_integration_routes.py",
            "tests/repo_quality/tools/test_fabric_product_integration.py",
            "tests/unit/fabric/test_product_integration.py",
            "tests/unit/scientist/governance/test_fabric_trust_gate_pass.py",
            "tests/unit/scientist/search/test_phase_b_policy_runtime.py",
            "tests/unit/scholar/test_fabric_provenance.py",
            "tests/unit/lex/test_fabric_provenance.py",
            "tests/unit/foundry/calibration/test_fabric_quality.py",
            "tests/unit/foundry/uncertainty/test_fabric_quality.py",
        ],
    )
    product_fixture_names = [
        "run-quantities.json",
        "run-fabric-decision-data.json",
        "lineage.json",
        "lineage-batch.json",
        "temporal-capabilities.json",
        "compare-run.json",
        "counterfactual-metrics.json",
        "fabric-source-scorecards.json",
        "fabric-quality-batch.json",
        "fabric-trust-batch.json",
        "fabric-replay.json",
        "fabric-impact.json",
    ]
    product_fixture_count = sum(
        1 for name in product_fixture_names if _path_exists(paths["dashboard_fixture_dir"] / name)
    )
    product_runtime_operation_ids = [
        "get_fabric_source_scorecards",
        "get_fabric_quality_batch",
        "get_fabric_trust_batch",
        "get_fabric_run_replay",
        "analyze_fabric_impact",
    ]
    runtime_product_status = _status_if(
        _path_exists(paths["fabric_route"])
        and _path_exists(paths["fabric_service"])
        and all(
            _has_token(paths["fabric_route"], operation)
            for operation in product_runtime_operation_ids
        )
        and all(
            _has_token(paths["runtime_openapi"], operation)
            for operation in product_runtime_operation_ids
        )
        and all(
            _has_token(paths["runtime_client_ts"], _client_operation_token(operation))
            for operation in product_runtime_operation_ids
        )
        and "tests/unit/runtime/http/test_fabric_integration_routes.py" in product_integration_tests
    )
    frontend_product_status = _status_if(
        product_fixture_count == len(product_fixture_names)
        and all(
            _has_token(paths["dashboard_fixture_registry"], name) for name in product_fixture_names
        )
        and _has_token(paths["dashboard_validators"], "fabricImpactAnalysisSchema")
        and _has_token(
            paths["dashboard_fabric_decision_adapter"], "fabricDecisionDataToQuantityValue"
        )
        and _has_token(paths["dashboard_fabric_decision_adapter"], "fabric_trust_envelope")
        and _has_token(paths["dashboard_fabric_decision_hook"], "useRunFabricDecisionData")
    )
    scientist_product_status = _status_if(
        _path_exists(paths["scientist_fabric_trust_gate"])
        and _has_token(paths["scientist_fabric_trust_gate"], "FabricTrustGatePass")
        and _has_token(paths["scientist_readiness"], "fabric_readiness_cap")
        and "tests/unit/scientist/governance/test_fabric_trust_gate_pass.py"
        in product_integration_tests
    )
    product_adapter_status = _status_if(
        _path_exists(paths["product_integration"])
        and _path_exists(paths["scholar_provenance"])
        and _path_exists(paths["lex_provenance"])
        and _path_exists(paths["foundry_calibration_fabric"])
        and _path_exists(paths["foundry_uncertainty_fabric"])
        and _has_token(paths["product_integration"], "FabricProductEvidencePath")
        and _has_token(paths["scholar_provenance"], "ScholarFabricCitation")
        and _has_token(paths["lex_provenance"], "LexFabricEvidencePath")
        and _has_token(paths["foundry_calibration_fabric"], "FabricCalibrationContext")
        and _has_token(paths["foundry_uncertainty_fabric"], "FabricUncertaintyContext")
    )
    compatibility_status = _status_if(
        _path_exists(paths["compatibility"])
        and _has_token(paths["compatibility"], "FABRIC_COMPATIBILITY_BRIDGES")
        and _has_token(paths["compatibility"], "sunset_date")
        and _has_token(paths["compatibility"], "migration_issue")
        and _path_exists(paths["product_integration_validator"])
        and _path_exists(paths["product_integration_doc"])
    )
    decision_data_report = _load_json(paths["decision_data_coverage_report"])
    decision_data_status = (
        "implemented"
        if _path_exists(paths["decision_data"])
        and _path_exists(paths["trust_envelope_schema"])
        and _path_exists(paths["decision_data_coverage"])
        and decision_data_report.get("summary", {}).get("status") == "implemented"
        else "missing"
    )
    discovery_eval_payload = _load_json(paths["discovery_eval_fixture"])
    discovery_eval_cases = discovery_eval_payload.get("cases", [])
    discovery_eval_case_count = (
        len(discovery_eval_cases) if isinstance(discovery_eval_cases, list) else 0
    )

    surfaces = [
        _surface(
            surface_id="source_contracts.fabric_registry_snapshot",
            plane="source",
            status=_status_if(bool(fabric_contract_ids)),
            priority="P1",
            title="Fabric connector contract registry snapshot",
            description="Committed source-contract snapshot used by schema governance.",
            source_files=[
                _rel(paths["fabric_contract_snapshot"], repo_root),
                "src/polisyos/fabric/connectors/sources/_contracts/__init__.py",
            ],
            tests=source_contract_tests,
            docs=["docs/reference/fabric/schema-compatibility.md"],
            evidence={
                "contract_snapshot": _rel(paths["fabric_contract_snapshot"], repo_root),
                "contract_count": len(fabric_contract_ids),
                "contract_ids": fabric_contract_ids,
            },
        ),
        _surface(
            surface_id="source_contracts.legacy_connector_snapshot",
            plane="source",
            status=_status_if(bool(legacy_contract_ids)),
            priority="P2",
            title="Legacy connector contract snapshot",
            description="Compatibility snapshot still checked by legacy connector tooling.",
            source_files=[_rel(paths["legacy_contract_snapshot"], repo_root)],
            tests=source_contract_tests,
            docs=["docs/reference/fabric/schema-compatibility.md"],
            evidence={
                "contract_snapshot": _rel(paths["legacy_contract_snapshot"], repo_root),
                "contract_count": len(legacy_contract_ids),
                "contract_ids": legacy_contract_ids,
            },
        ),
        _surface(
            surface_id="source.source_contract_v2_platform",
            plane="source",
            status=_status_if(
                _path_exists(paths["source_contract_v2"])
                and _path_exists(paths["source_contract_schema"])
                and bool(source_contract_v2_ids)
                and source_v2_bounded_read_count == len(source_contract_v2_ids)
                and source_v2_replay_fixture_count == len(source_contract_v2_ids)
                and source_v2_non_replayable_reason_count == 0
                and source_v2_field_policy_coverage_count == len(source_contract_v2_ids)
                and _path_exists(paths["source_contracts_validator"])
                and bool(source_platform_tests)
            ),
            priority="P1",
            title="SourceContract v2 production source platform",
            description=(
                "Contract-first source evidence covering schema, profile, quality, replay, "
                "lineage, access, retention, SLO, owner, reviewer, and docs."
            ),
            source_files=[
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_contract_schema"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
                _rel(paths["source_contracts_validator"], repo_root),
            ],
            tests=source_platform_tests,
            docs=[
                "docs/reference/fabric/source-platform.md",
                "docs/reference/fabric/connectors.md",
            ],
            evidence={
                "schema": _rel(paths["source_contract_schema"], repo_root),
                "snapshot": _rel(paths["source_contract_snapshot_v2"], repo_root),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "source_contract_v2_ids": source_contract_v2_ids,
                "bounded_read_evidence_count": source_v2_bounded_read_count,
                "replay_fixture_count": source_v2_replay_fixture_count,
                "non_replayable_reason_count": source_v2_non_replayable_reason_count,
                "field_policy_coverage_count": source_v2_field_policy_coverage_count,
            },
        ),
        _surface(
            surface_id="source.processing_guarantee_contracts",
            plane="source",
            status=_status_if(
                _path_exists(paths["processing_guarantees"])
                and _path_exists(paths["processing_guarantee_schema"])
                and _path_exists(paths["processing_guarantees_validator"])
                and source_v2_processing_count == len(source_contract_v2_ids)
                and source_v2_dedupe_window_count == len(source_contract_v2_ids)
                and source_v2_replay_retention_count == len(source_contract_v2_ids)
                and bool(processing_tests)
            ),
            priority="P1",
            title="Processing guarantee, dedupe, and replay-retention contracts",
            description=(
                "SourceContract v2 carries honest batch/stream/CDC/replay guarantee "
                "labels plus idempotency, dedupe-window, replay-retention, "
                "backpressure, and out-of-order policies."
            ),
            source_files=[
                _rel(paths["processing_guarantees"], repo_root),
                _rel(paths["processing_guarantee_schema"], repo_root),
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
                _rel(paths["processing_guarantees_validator"], repo_root),
            ],
            tests=processing_tests,
            docs=[
                "docs/reference/fabric/processing-guarantees.md",
                "docs/reference/fabric/source-platform.md",
            ],
            evidence={
                "processing_contract_count": source_v2_processing_count,
                "dedupe_window_count": source_v2_dedupe_window_count,
                "replay_retention_count": source_v2_replay_retention_count,
                "schema": _rel(paths["processing_guarantee_schema"], repo_root),
                "validator": _rel(paths["processing_guarantees_validator"], repo_root),
            },
        ),
        _surface(
            surface_id="source.connector_sdk_authoring_helpers",
            plane="source",
            status=_status_if(_path_exists(paths["connector_sdk"]) and bool(source_platform_tests)),
            priority="P1",
            title="Connector SDK authoring helpers",
            description=(
                "Scaffold helpers derive source, profile, contract, replay, quality, "
                "and docs ids before a connector becomes production-visible."
            ),
            source_files=_python_files_recursive(
                repo_root,
                "src/polisyos/fabric/connectors/sdk",
                reads=reads,
            ),
            tests=source_platform_tests,
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "sdk_package": _rel(paths["connector_sdk"], repo_root),
                "profile_matrix": "build_source_profile_matrix",
            },
        ),
        _surface(
            surface_id="source.conformance_harness_v2",
            plane="source",
            status=_status_if(
                _path_exists(paths["conformance_v2"]) and bool(source_platform_tests)
            ),
            priority="P1",
            title="Connector conformance harness v2",
            description=(
                "Harness reuses connector testing v1 and checks SourceContract v2, profile, "
                "schema, quality, replay, lineage, access, retention, and SLO evidence."
            ),
            source_files=[_rel(paths["conformance_v2"], repo_root)],
            tests=source_platform_tests
            + _existing_paths(
                repo_root, ["tests/unit/fabric/connectors/test_protocol_compliance.py"]
            ),
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "validator": "validate_source_conformance_v2",
                "harness": "ConnectorConformanceHarnessV2",
                "bounded_read_check": _has_token(paths["conformance_v2"], "bounded_reads"),
                "report_count": len(source_contract_v2_ids),
            },
        ),
        _surface(
            surface_id="source.connector_entrypoints",
            plane="source",
            status=_status_if(bool(entrypoints)),
            priority="P1",
            title="Production connector entry points",
            description="Install-time discovery surface for production connector components.",
            source_files=["pyproject.toml"],
            tests=_existing_paths(
                repo_root,
                [
                    "tests/unit/fabric/connectors/test_registry.py",
                    "tests/unit/fabric/connectors/test_protocol_compliance.py",
                ],
            ),
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "entrypoint_group": "polisyos.fabric_connectors",
                "entrypoint_count": len(entrypoints),
                "entrypoints": entrypoints,
            },
        ),
        _surface(
            surface_id="source.connector_public_exports",
            plane="source",
            status=_status_if(
                bool(concrete_connectors) and connector_export_inventory["inventory_complete"],
                partial_when_false=not connector_export_inventory["inventory_complete"],
            ),
            priority="P1",
            title="Concrete connector public exports",
            description="Concrete connector classes exported from the source package.",
            source_files=[_rel(paths["source_init"], repo_root)],
            tests=_existing_paths(
                repo_root,
                [
                    "tests/unit/fabric/connectors/test_protocol_compliance.py",
                    "tests/unit/fabric/connectors/test_registry.py",
                ],
            ),
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "export_count": len(source_exports),
                **connector_export_inventory,
            },
        ),
        _surface(
            surface_id="source.connector_source_modules",
            plane="source",
            status=_status_if(bool(source_tree_files)),
            priority="P2",
            title="Connector source module tree",
            description="Recursive inventory of source connector modules and source-contract modules.",
            source_files=source_tree_files,
            tests=_existing_paths(
                repo_root,
                [
                    "tests/unit/fabric/connectors/test_protocol_compliance.py",
                    "tests/unit/fabric/connectors/test_registry.py",
                    "tests/unit/fabric/connectors/test_contract_system.py",
                ],
            ),
            docs=[
                "docs/reference/fabric/connectors.md",
                "docs/reference/fabric/schema-compatibility.md",
            ],
            evidence={
                "source_tree": "src/polisyos/fabric/connectors/sources/**",
                "source_module_count": len(source_tree_files),
                "source_modules": source_tree_files,
            },
        ),
        _surface(
            surface_id="source.entrypoint_coverage.direct_import_families",
            plane="source",
            status="partial",
            priority="P2",
            title="Connector-family contract identity mapping",
            description=(
                "Connector and SourceContract v2 counts plus validator presence are "
                "observed, but a semantic contract-ID-to-connector-ID mapping is not "
                "established; connector-family identity remains partial."
            ),
            source_files=[
                "pyproject.toml",
                _rel(paths["source_init"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
                _rel(paths["source_contracts_validator"], repo_root),
            ],
            tests=_existing_paths(
                repo_root,
                [
                    "tests/unit/fabric/connectors/test_connector_family_expansion.py",
                    "tests/unit/fabric/connectors/test_registry.py",
                    "tests/repo_quality/tools/test_fabric_best_in_class_inventory.py",
                ],
            ),
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "entrypoint_count": len(entrypoints),
                "concrete_connector_count": len(concrete_connectors),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "source_contracts_validator_present": _path_exists(
                    paths["source_contracts_validator"]
                ),
                "mapped_identity_status": "not_established",
                "source_family_state": "partial",
                "identity_binding_gap": (
                    "contract-ID-to-connector-ID semantic binding and a positive test "
                    "are not established"
                ),
            },
        ),
        _surface(
            surface_id="source.builtin_source_profiles",
            plane="source",
            status=_status_if(bool(profile_ids)),
            priority="P1",
            title="Built-in source profile catalog",
            description="Curated profile catalog for source execution policies and connector defaults.",
            source_files=[_rel(paths["builtin_profiles"], repo_root)],
            tests=profile_tests,
            docs=["docs/reference/fabric/profiles.md"],
            evidence={
                "profile_count": len(profile_ids),
                "profile_ids": profile_ids,
            },
        ),
        _surface(
            surface_id="source.http_runtime_base_contract",
            plane="source",
            status="not_applicable",
            priority="P3",
            title="Shared HTTP runtime as production source",
            description=(
                "HTTPConnectorBase and HTTPResilienceProfile are exported runtime primitives, "
                "not standalone production source connectors."
            ),
            source_files=[_rel(paths["source_init"], repo_root)],
            tests=[],
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "non_connector_exports": [
                    export
                    for export in source_exports
                    if export in {"HTTPConnectorBase", "HTTPResilienceProfile"}
                ]
            },
        ),
        _surface(
            surface_id="evidence.record_replay_store",
            plane="evidence",
            status=_status_if(_path_exists(paths["replay_store"]) and bool(replay_tests)),
            priority="P1",
            title="Record/replay persistence surface",
            description="Data-plane replay store and tests for deterministic ingestion replay.",
            source_files=[_rel(paths["replay_store"], repo_root)],
            tests=replay_tests,
            docs=["docs/reference/fabric/data-plane.md"],
            evidence={
                "replay_store": _path_exists(paths["replay_store"]),
                "record_replay_tests": "tests/unit/fabric/data_plane/test_record_replay.py"
                in replay_tests,
            },
        ),
        _surface(
            surface_id="evidence.quarantine_replay_surface",
            plane="evidence",
            status=_status_if(_path_exists(paths["quarantine"]) and bool(replay_tests)),
            priority="P1",
            title="Quarantine/DLQ replay surface",
            description="Quarantine records, replay hooks, and DLQ operational coverage.",
            source_files=[_rel(paths["quarantine"], repo_root)],
            tests=replay_tests,
            docs=[
                "docs/reference/fabric/data-plane.md",
                "docs/runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md",
            ],
            evidence={
                "quarantine_module": _path_exists(paths["quarantine"]),
                "quarantine_tests": "tests/unit/fabric/data_plane/test_quarantine.py"
                in replay_tests,
            },
        ),
        _surface(
            surface_id="evidence.production_source_replay_fixtures",
            plane="evidence",
            status=_status_if(
                bool(source_contract_v2_ids)
                and source_v2_replay_fixture_count == len(source_contract_v2_ids)
                and source_v2_non_replayable_reason_count == 0,
                partial_when_false=True,
            ),
            priority="P1",
            title="Production source replay fixture matrix",
            description=(
                "Every production SourceContract v2 carries a deterministic replay "
                "fixture; non-replayable reasons are excluded from strict Wave 2 closure."
            ),
            source_files=[
                _rel(paths["replay_store"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
            ],
            tests=replay_tests + source_platform_tests,
            docs=[
                "docs/reference/fabric/data-plane.md",
                "docs/reference/fabric/source-platform.md",
            ],
            evidence={
                "production_entrypoint_count": len(entrypoints),
                "contract_snapshot_count": len(fabric_contract_ids),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "replay_fixture_count": source_v2_replay_fixture_count,
                "non_replayable_reason_count": source_v2_non_replayable_reason_count,
                "record_replay_tests_present": bool(replay_tests),
            },
            follow_up=(
                None
                if source_v2_replay_fixture_count == len(source_contract_v2_ids)
                and source_v2_non_replayable_reason_count == 0
                else "Strict Wave 2: replace non-replayable reasons with replay fixtures."
            ),
        ),
        _surface(
            surface_id="evidence.streaming_scale_semantics",
            plane="evidence",
            status=_status_if(
                _path_exists(paths["streaming"])
                and _has_token(paths["streaming"], "processing_contract_snapshot")
                and _has_token(paths["streaming"], "_apply_out_of_order_policy")
                and _has_token(paths["streaming"], "classify_cdc_schema_change")
                and bool(processing_tests)
            ),
            priority="P1",
            title="Streaming, CDC, backpressure, and out-of-order semantics",
            description=(
                "Streaming runtime persists the effective processing contract on "
                "chunks, windows, checkpoints, cursors, and CDC events while "
                "counting late/dropped/quarantined rows."
            ),
            source_files=[
                _rel(paths["streaming"], repo_root),
                _rel(paths["processing_guarantees"], repo_root),
            ],
            tests=processing_tests,
            docs=["docs/reference/fabric/processing-guarantees.md"],
            evidence={
                "processing_artifact_metadata": _has_token(
                    paths["streaming"], "processing_contract_snapshot"
                ),
                "out_of_order_policy": _has_token(paths["streaming"], "_apply_out_of_order_policy"),
                "cdc_compatibility": _has_token(paths["streaming"], "classify_cdc_schema_change"),
                "backpressure_contract": _has_token(paths["streaming"], "backpressure.strategy"),
            },
        ),
        _surface(
            surface_id="evidence.distributed_execution_trust_gate",
            plane="evidence",
            status=_status_if(
                _path_exists(paths["orchestrator"])
                and _has_token(paths["orchestrator"], "DistributedExecutionTrustContract")
                and _has_token(paths["orchestrator"], "_validate_distributed_execution_trust")
                and "tests/unit/fabric/data_plane/test_orchestrator.py" in processing_tests
            ),
            priority="P1",
            title="Distributed execution trust gate",
            description=(
                "Dask/Ray/Celery partition execution fails closed unless lineage, "
                "quality, access, and replay/non-replayable evidence are present."
            ),
            source_files=[_rel(paths["orchestrator"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/unit/fabric/data_plane/test_orchestrator.py"]),
            docs=["docs/reference/fabric/processing-guarantees.md"],
            evidence={
                "trust_contract": _has_token(
                    paths["orchestrator"], "DistributedExecutionTrustContract"
                ),
                "fail_closed_gate": _has_token(
                    paths["orchestrator"], "_validate_distributed_execution_trust"
                ),
            },
        ),
        _surface(
            surface_id="evidence.fabric_scale_benchmark_suite",
            plane="evidence",
            status=_status_if(
                _path_exists(paths["benchmarks"])
                and _has_token(paths["benchmarks"], "latency_quantiles_ms")
                and _has_token(paths["benchmarks"], "correctness_counters")
                and _has_token(paths["benchmarks"], "benchmark_query_execution")
                and "tests/unit/fabric/data_plane/test_benchmarks.py" in processing_tests
            ),
            priority="P2",
            title="Scale benchmark reports for ingestion, streaming, materialization, and query",
            description=(
                "Benchmark reports include p50/p95/p99 latency, memory, and "
                "correctness counters for Fabric scale paths."
            ),
            source_files=[_rel(paths["benchmarks"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/unit/fabric/data_plane/test_benchmarks.py"]),
            docs=["docs/reference/fabric/processing-guarantees.md"],
            evidence={
                "latency_quantiles": _has_token(paths["benchmarks"], "latency_quantiles_ms"),
                "correctness_counters": _has_token(paths["benchmarks"], "correctness_counters"),
                "query_benchmark": _has_token(paths["benchmarks"], "benchmark_query_execution"),
            },
        ),
        _surface(
            surface_id="evidence.cas_evidence_bundle",
            plane="evidence",
            status="implemented"
            if _path_exists(paths["evidence"])
            and "tests/unit/fabric/test_provenance.py" in tests_by_plane["evidence"]
            else "partial",
            priority="P2",
            title="CAS-backed evidence bundle persistence",
            description="Evidence bundle helpers that persist provenance payloads into governed artifact storage.",
            source_files=[_rel(paths["evidence"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/unit/fabric/test_provenance.py"]),
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "evidence_module": _path_exists(paths["evidence"]),
                "provenance_bundle_tests": "tests/unit/fabric/test_provenance.py"
                in tests_by_plane["evidence"],
            },
        ),
        _surface(
            surface_id="semantics.quality_indicators",
            plane="semantics",
            status=_status_if(_path_exists(paths["quality"]) and bool(quality_tests)),
            priority="P1",
            title="Metric-level quality indicators",
            description="Quality indicator scoring, finite-value guards, and metric fitness reports.",
            source_files=[
                _rel(paths["quality"], repo_root),
                _rel(paths["fitness_report"], repo_root),
            ],
            tests=quality_tests,
            docs=["docs/reference/fabric/quality.md"],
            evidence={
                "quality_module": _path_exists(paths["quality"]),
                "fitness_report_module": _path_exists(paths["fitness_report"]),
                "quality_tests": quality_tests,
            },
        ),
        _surface(
            surface_id="semantics.connector_quality_validators",
            plane="semantics",
            status=_status_if(bool(quality_modules) and bool(quality_tests)),
            priority="P1",
            title="Connector-level quality validators",
            description="Completeness, consistency, freshness, statistics, and validator modules for source outputs.",
            source_files=quality_modules,
            tests=quality_tests,
            docs=["docs/reference/fabric/quality.md"],
            evidence={
                "quality_module_count": len(quality_modules),
                "quality_modules": quality_modules,
            },
        ),
        _surface(
            surface_id="semantics.source_quality_contract_coverage",
            plane="semantics",
            status=_status_if(
                bool(source_contract_v2_ids)
                and _path_exists(paths["source_contracts_validator"])
                and bool(source_platform_tests),
                partial_when_false=True,
            ),
            priority="P1",
            title="Quality-contract coverage by source contract/profile",
            description=(
                "SourceContract v2 snapshot carries quality-contract refs and "
                "required quality checks for production source contracts."
            ),
            source_files=[
                _rel(paths["quality"], repo_root),
                _rel(paths["builtin_profiles"], repo_root),
                _rel(paths["fabric_contract_snapshot"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
            ],
            tests=quality_tests + source_contract_tests + source_platform_tests,
            docs=[
                "docs/reference/fabric/quality.md",
                "docs/reference/fabric/profiles.md",
                "docs/reference/fabric/source-platform.md",
            ],
            evidence={
                "contract_count": len(fabric_contract_ids),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "profile_count": len(profile_ids),
                "quality_validator_module_count": len(quality_modules),
            },
            follow_up=("Phase 6: propagate source quality states into decision-data envelopes."),
        ),
        _surface(
            surface_id="semantics.source_scorecards",
            plane="semantics",
            status=_status_if(
                _path_exists(paths["scorecard"])
                and _path_exists(paths["source_scorecard_schema"])
                and bool(source_scorecard_records)
                and bool(source_platform_tests)
            ),
            priority="P1",
            title="Generated source scorecards",
            description=(
                "Scorecards summarize freshness, reliability, schema drift, quality, "
                "contract violations, quarantine, replay, latency, and source trust."
            ),
            source_files=[
                _rel(paths["scorecard"], repo_root),
                _rel(paths["source_scorecard_schema"], repo_root),
                _rel(paths["source_scorecard_snapshot"], repo_root),
            ],
            tests=source_platform_tests,
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "schema": _rel(paths["source_scorecard_schema"], repo_root),
                "snapshot": _rel(paths["source_scorecard_snapshot"], repo_root),
                "scorecard_count": len(source_scorecard_records),
                "required_dimensions": [
                    "freshness",
                    "reliability",
                    "schema_drift",
                    "quality",
                    "replay_success",
                ],
            },
        ),
        _surface(
            surface_id="semantics.semantic_dataset_catalog",
            plane="semantics",
            status=_status_if(
                _path_exists(paths["catalog_discovery"])
                and _has_token(paths["catalog_discovery"], "class SemanticDatasetCatalog")
                and _has_token(paths["catalog_discovery"], "DatasetDiscoveryEvidence")
                and _has_token(paths["catalog_discovery"], "SourceContract")
                and _path_exists(paths["discovery_intelligence_doc"])
                and bool(discovery_tests)
            ),
            priority="P1",
            title="SourceContract-backed semantic dataset catalog",
            description=(
                "Offline-first catalog builds one explainable discovery document per "
                "production SourceContract and carries source, profile, quality, access, "
                "trust, owner, and reviewer evidence on each ranked candidate."
            ),
            source_files=[
                _rel(paths["catalog_discovery"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
                _rel(paths["discovery_intelligence_validator"], repo_root),
            ],
            tests=discovery_tests,
            docs=["docs/reference/fabric/discovery-intelligence.md"],
            evidence={
                "source_contract_v2_count": len(source_contract_v2_ids),
                "embedding_model": "hashing-bow-dataset-v1",
                "llm_calls": 0,
                "candidate_evidence": _has_token(
                    paths["catalog_discovery"], "DatasetDiscoveryEvidence"
                ),
            },
        ),
        _surface(
            surface_id="semantics.stale_embedding_invalidation",
            plane="semantics",
            status=_status_if(
                _path_exists(paths["catalog_discovery"])
                and _has_token(paths["catalog_discovery"], "def mark_stale")
                and _has_token(paths["catalog_discovery"], "def refresh")
                and _has_token(paths["catalog_discovery"], "fingerprint")
                and _has_token(paths["catalog_discovery"], "stale_filter")
                and bool(discovery_tests)
            ),
            priority="P1",
            title="Stale semantic-vector invalidation",
            description=(
                "Dataset vectors are rebuilt when SourceContract, source metadata, profile, "
                "quality, access, or trust evidence changes; stale entries are filtered by "
                "default and labelled when explicitly requested."
            ),
            source_files=[_rel(paths["catalog_discovery"], repo_root)],
            tests=discovery_tests,
            docs=["docs/reference/fabric/discovery-intelligence.md"],
            evidence={
                "mark_stale": _has_token(paths["catalog_discovery"], "def mark_stale"),
                "refresh": _has_token(paths["catalog_discovery"], "def refresh"),
                "fingerprint": _has_token(paths["catalog_discovery"], "fingerprint"),
                "stale_filter": _has_token(paths["catalog_discovery"], "stale_filter"),
            },
        ),
        _surface(
            surface_id="semantics.nl_to_dataset_resolution_eval",
            plane="semantics",
            status=_status_if(
                _path_exists(paths["catalog_discovery"])
                and _path_exists(paths["discovery_intelligence_validator"])
                and _path_exists(paths["discovery_eval_fixture"])
                and discovery_eval_case_count > 0
                and _has_token(paths["catalog_discovery"], "DatasetResolutionPlan")
                and _has_token(paths["catalog_discovery"], "evaluate_benchmark")
                and bool(discovery_tests)
            ),
            priority="P1",
            title="Explainable NL-to-dataset resolution and eval pack",
            description=(
                "Natural-language discovery returns ranked candidates with deterministic "
                "lexical fallback, no LLM calls, relevance cases, and false-positive budget."
            ),
            source_files=[
                _rel(paths["catalog_discovery"], repo_root),
                _rel(paths["discovery_eval_fixture"], repo_root),
                _rel(paths["discovery_intelligence_validator"], repo_root),
            ],
            tests=discovery_tests,
            docs=["docs/reference/fabric/discovery-intelligence.md"],
            evidence={
                "eval_case_count": discovery_eval_case_count,
                "minimum_pass_rate": discovery_eval_payload.get("minimum_pass_rate"),
                "maximum_false_positive_failures": discovery_eval_payload.get(
                    "maximum_false_positive_failures"
                ),
                "llm_calls": 0,
            },
        ),
        _surface(
            surface_id="semantics.schema_governance_snapshot_gate",
            plane="semantics",
            status=_status_if(
                _path_exists(paths["schema_governance"]) and bool(source_contract_tests)
            ),
            priority="P1",
            title="Schema governance snapshot gate",
            description="Governance check for connector contract evolution and committed snapshots.",
            source_files=[
                _rel(paths["schema_governance"], repo_root),
                _rel(paths["fabric_contract_snapshot"], repo_root),
            ],
            tests=source_contract_tests,
            docs=["docs/reference/fabric/schema-compatibility.md"],
            evidence={
                "validator": _rel(paths["schema_governance"], repo_root),
                "contract_snapshot": _rel(paths["fabric_contract_snapshot"], repo_root),
            },
        ),
        _surface(
            surface_id="semantics.fabric_quality_governance_evidence",
            plane="semantics",
            status=_status_if(
                _path_exists(paths["quality_evidence"])
                and _path_exists(paths["scientist_quality_gate"])
                and bool(phase4_tests)
            ),
            priority="P1",
            title="Fabric quality evidence propagation",
            description=(
                "Normalized Fabric quality evidence is exported from quality reports "
                "and attached to Scientist governance state."
            ),
            source_files=[
                _rel(paths["quality_evidence"], repo_root),
                _rel(paths["scientist_quality_gate"], repo_root),
            ],
            tests=phase4_tests,
            docs=[
                "docs/reference/fabric/quality.md",
                "docs/reference/fabric/observability-governance.md",
            ],
            evidence={
                "quality_evidence_builder": _has_token(
                    paths["quality_evidence"],
                    "build_fabric_quality_governance_evidence",
                ),
                "scientist_state_key": _has_token(
                    paths["scientist_quality_gate"],
                    "fabric_quality_evidence",
                ),
            },
        ),
        _surface(
            surface_id="world.bitemporal_world_query",
            plane="world",
            status=_status_if(
                _path_exists(paths["world_query"])
                and _has_token(paths["world_query"], "as_of_tx_time")
                and _has_token(paths["world_query"], "as_of_valid_time")
                and bool(temporal_tests)
            ),
            priority="P1",
            title="Bitemporal world-query support",
            description="World queries support transaction-time and valid-time filters.",
            source_files=[_rel(paths["world_query"], repo_root)],
            tests=temporal_tests,
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "as_of_tx_time": _has_token(paths["world_query"], "as_of_tx_time"),
                "as_of_valid_time": _has_token(paths["world_query"], "as_of_valid_time"),
                "temporal_tests": temporal_tests,
            },
        ),
        _surface(
            surface_id="world.snapshot_branch_surface",
            plane="world",
            status=_status_if(
                _path_exists(paths["snapshots"])
                and _has_token(paths["snapshots"], "create_world_branch")
                and _has_token(paths["snapshots"], "merge_world_branch")
                and _has_token(paths["snapshots"], "update_world_branch_head")
                and _has_token(paths["snapshots"], "delete_world_branch")
                and _path_exists(paths["world_branch_schema"])
                and _path_exists(paths["scenario_branch_schema"])
                and _has_token(paths["snapshots"], "_validate_snapshot_retention_governance")
                and _has_token(paths["retention"], "SnapshotDeletionImpact")
            ),
            priority="P1",
            title="Snapshot, branch, merge, governance, and retention surface",
            description=(
                "World snapshot store supports retained snapshots, governed branches, "
                "merge policy, scenario contracts, and GC metadata."
            ),
            source_files=[
                _rel(paths["snapshots"], repo_root),
                _rel(paths["retention"], repo_root),
                _rel(paths["world_branch_schema"], repo_root),
                _rel(paths["scenario_branch_schema"], repo_root),
            ],
            tests=temporal_tests,
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "create_world_branch": _has_token(paths["snapshots"], "create_world_branch"),
                "merge_world_branch": _has_token(paths["snapshots"], "merge_world_branch"),
                "update_world_branch_head": _has_token(
                    paths["snapshots"], "update_world_branch_head"
                ),
                "delete_world_branch": _has_token(paths["snapshots"], "delete_world_branch"),
                "export_world_branch_governance": _has_token(
                    paths["snapshots"], "export_world_branch_governance"
                ),
                "gc_world_snapshots": _has_token(paths["snapshots"], "gc_world_snapshots"),
                "world_branch_schema": _path_exists(paths["world_branch_schema"]),
                "scenario_branch_schema": _path_exists(paths["scenario_branch_schema"]),
                "legal_hold_encryption_gate": _has_token(
                    paths["snapshots"], "_validate_snapshot_retention_governance"
                ),
                "deletion_impact_record": _has_token(paths["retention"], "SnapshotDeletionImpact"),
            },
        ),
        _surface(
            surface_id="world.correction_revocation_mutations",
            plane="world",
            status=_status_if(
                _path_exists(paths["world_segments"])
                and _has_token(paths["world_segments"], "WorldMutationKind")
                and _has_token(paths["world_segments"], "parse_world_mutation_notes")
                and _has_token(paths["world_emit"], "mutation_kind")
            ),
            priority="P1",
            title="Append-only correction and revocation metadata",
            description=(
                "World fact emission can attach typed correction, revocation, branch, "
                "and scenario mutation metadata without overwriting prior facts."
            ),
            source_files=[
                _rel(paths["world_segments"], repo_root),
                _rel(paths["world_emit"], repo_root),
            ],
            tests=_existing_paths(repo_root, ["tests/unit/fabric/test_world_branch_governance.py"]),
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "mutation_enum": _has_token(paths["world_segments"], "WorldMutationKind"),
                "correction_required_fields": _has_token(
                    paths["world_segments"], "WorldMutationKind.CORRECTION"
                ),
                "revocation_required_fields": _has_token(
                    paths["world_segments"], "WorldMutationKind.REVOCATION"
                ),
                "emitter_support": _has_token(paths["world_emit"], "mutation_kind"),
            },
        ),
        _surface(
            surface_id="world.temporal_runtime_adapter",
            plane="world",
            status=_status_if(
                _path_exists(paths["temporal_route"])
                and _path_exists(paths["temporal_service"])
                and "tests/unit/runtime/http/test_temporal_routes.py" in temporal_tests
                and _has_token(paths["temporal_service"], "slow_query_evidence")
            ),
            priority="P1",
            title="Runtime temporal API adapter",
            description="HTTP service/route adapter maps API temporal scopes to Fabric world-query kwargs.",
            source_files=[
                _rel(paths["temporal_route"], repo_root),
                _rel(paths["temporal_service"], repo_root),
            ],
            tests=_existing_paths(
                repo_root,
                [
                    "tests/unit/runtime/http/test_temporal_api.py",
                    "tests/unit/runtime/http/test_temporal_routes.py",
                    "tests/unit/fabric/test_world_temporal_capabilities.py",
                ],
            ),
            docs=["docs/reference/fabric/time-travel.md", "docs/reference/api/index.md"],
            evidence={
                "route": _path_exists(paths["temporal_route"]),
                "service": _path_exists(paths["temporal_service"]),
                "supported_tables": _has_token(paths["temporal_service"], "supported_tables"),
                "slow_query_evidence": _has_token(paths["temporal_service"], "slow_query_evidence"),
                "branch_support": _has_token(paths["temporal_service"], "branch_support"),
            },
        ),
        _surface(
            surface_id="world.kuzu_temporal_scope_capability",
            plane="world",
            status="partial"
            if _path_exists(paths["world_kuzu"])
            and _has_token(paths["world_kuzu"], "WorldKuzuTemporalCapability")
            and _has_token(
                paths["world_kuzu"],
                'graph_temporal_scope: Literal["full", "partial", "unsupported"]',
            )
            else "missing",
            priority="P2",
            title="Kuzu temporal graph parity marker",
            description=(
                "Kuzu exports carry edge valid/tx metadata, while full bitemporal graph "
                "traversal is explicitly labelled partial and linked to R3."
            ),
            source_files=[_rel(paths["world_kuzu"], repo_root)],
            tests=_existing_paths(
                repo_root, ["tests/unit/fabric/test_world_temporal_capabilities.py"]
            ),
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "temporal_capability": _has_token(
                    paths["world_kuzu"], "WorldKuzuTemporalCapability"
                ),
                "partial_scope": _has_token(paths["world_kuzu"], "graph_temporal_scope"),
                "research_track": _has_token(paths["world_kuzu"], "R3"),
            },
            follow_up="R3: prove full bitemporal Kuzu traversal semantics before marking implemented.",
        ),
        _surface(
            surface_id="world.discovery_graph_reasoning",
            plane="world",
            status=_status_if(
                _path_exists(paths["world_kuzu"])
                and _has_token(paths["world_kuzu"], "query_world_origin_trace")
                and _has_token(paths["world_kuzu"], "query_world_source_overlap")
                and _has_token(paths["world_kuzu"], "query_world_conflict_neighborhood")
                and _has_token(paths["world_kuzu"], "query_world_policy_impact")
                and _has_token(paths["world_kuzu"], "query_world_entity_neighborhood")
                and bool(discovery_tests)
            ),
            priority="P1",
            title="Discovery graph reasoning helpers",
            description=(
                "World graph helpers answer origin, source-overlap, conflict-neighborhood, "
                "source-to-policy impact, and entity-neighborhood questions over in-memory "
                "fixtures and live Kuzu traversals."
            ),
            source_files=[_rel(paths["world_kuzu"], repo_root)],
            tests=discovery_tests,
            docs=[
                "docs/reference/fabric/discovery-intelligence.md",
                "docs/reference/fabric/time-travel.md",
            ],
            evidence={
                "origin_trace": _has_token(paths["world_kuzu"], "query_world_origin_trace"),
                "source_overlap": _has_token(paths["world_kuzu"], "query_world_source_overlap"),
                "conflict_neighborhood": _has_token(
                    paths["world_kuzu"], "query_world_conflict_neighborhood"
                ),
                "policy_impact": _has_token(paths["world_kuzu"], "query_world_policy_impact"),
                "entity_neighborhood": _has_token(
                    paths["world_kuzu"], "query_world_entity_neighborhood"
                ),
                "kuzu_helpers": _has_token(paths["world_kuzu"], "query_world_kuzu_origin_trace"),
            },
        ),
        _surface(
            surface_id="world.future_table_snapshot_adapters",
            plane="world",
            status="not_applicable",
            priority="P2",
            title="External table-format adapters excluded from Wave 2 production",
            description=(
                "Iceberg/Delta-style adapters are metadata-only future surfaces. Wave 2 "
                "strict closure proves they are not production-visible and local runtime "
                "create/query paths fail closed."
            ),
            source_files=[
                _rel(paths["snapshots"], repo_root),
                _rel(paths["world_query"], repo_root),
            ],
            tests=temporal_tests,
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "adapter_registry_present": _has_token(
                    paths["snapshots"], "list_world_snapshot_adapters"
                ),
                "runtime_rejection_test": "tests/unit/fabric/test_world_time_travel.py"
                in temporal_tests,
                "production_visible": False,
                "strict_wave2_scope": "not_applicable",
            },
        ),
        _surface(
            surface_id="world.temporal_graph_reasoning",
            plane="world",
            status="blocked_by_research",
            priority="P2",
            title="Temporal graph reasoning over world snapshots",
            description=(
                "Advanced temporal graph semantics are intentionally deferred to the "
                "research wave before being converted into runtime acceptance gates."
            ),
            source_files=[_rel(paths["world_query"], repo_root), _rel(paths["lineage"], repo_root)],
            tests=[],
            docs=["docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md"],
            evidence={"research_wave": "Wave R / R3 temporal graph semantics"},
            follow_up="Wave R R3: define acceptance semantics before implementation.",
        ),
        _surface(
            surface_id="trust.fabric_slo_error_budget_gate",
            plane="trust",
            status=_status_if(
                _path_exists(paths["observability"])
                and _path_exists(paths["core_metrics_base"])
                and _path_exists(paths["core_metrics_parts"])
                and bool(phase4_tests)
            ),
            priority="P1",
            title="Fabric SLI/SLO and error-budget gate",
            description=(
                "Fabric defines the release-blocking SLI set, evaluates SLO burn, "
                "records SLI/burn metrics, and blocks P0/P1 feature expansion."
            ),
            source_files=[
                _rel(paths["observability"], repo_root),
                _rel(paths["core_metrics_base"], repo_root),
                _rel(paths["core_metrics_parts"], repo_root),
            ],
            tests=phase4_tests
            + _existing_paths(repo_root, ["tests/unit/fabric/test_fabric_observability.py"]),
            docs=["docs/reference/fabric/observability-governance.md"],
            evidence={
                "sli_enum": _has_token(paths["observability"], "class FabricSLIName"),
                "slo_targets": _has_token(paths["observability"], "DEFAULT_FABRIC_SLO_TARGETS"),
                "error_budget_gate": _has_token(
                    paths["observability"],
                    "assert_fabric_feature_expansion_allowed",
                ),
                "sli_metric": _has_token(paths["core_metrics_base"], "polisyos_fabric_sli_value"),
                "burn_metric": _has_token(
                    paths["core_metrics_base"],
                    "polisyos_fabric_error_budget_burn_ratio",
                ),
            },
        ),
        _surface(
            surface_id="trust.connector_governance_metadata",
            plane="trust",
            status=_status_if(
                _path_exists(paths["connector_governance_metadata"])
                and _path_exists(paths["ir_connectors"])
                and bool(phase4_tests)
            ),
            priority="P1",
            title="Production connector governance metadata",
            description=(
                "Production connectors expose schema, quality, SLA, access classification, "
                "and owner metadata with a validator-backed inventory check."
            ),
            source_files=[
                _rel(paths["connector_governance_metadata"], repo_root),
                _rel(paths["ir_connectors"], repo_root),
            ],
            tests=phase4_tests
            + _existing_paths(
                repo_root,
                ["tests/unit/fabric/connectors/test_protocol_compliance.py"],
            ),
            docs=[
                "docs/reference/fabric/connectors.md",
                "docs/reference/fabric/observability-governance.md",
            ],
            evidence={
                "metadata_validator": _has_token(
                    paths["connector_governance_metadata"],
                    "validate_connector_governance_metadata",
                ),
                "schema_governance": _has_token(paths["ir_connectors"], "schema_governance"),
                "quality_governance": _has_token(paths["ir_connectors"], "quality_governance"),
                "sla": _has_token(paths["ir_connectors"], "ConnectorSLASpec"),
            },
        ),
        _surface(
            surface_id="trust.source_contract_access_retention_slo",
            plane="trust",
            status=_status_if(
                bool(source_contract_v2_ids)
                and source_v2_classification_count == len(source_contract_v2_ids)
                and source_v2_owner_reviewer_count == len(source_contract_v2_ids)
                and bool(source_platform_tests)
            ),
            priority="P1",
            title="SourceContract access, retention, owner, reviewer, and SLO metadata",
            description=(
                "Production SourceContract v2 records carry classification, retention, "
                "owner/reviewer, and source SLO metadata before production visibility."
            ),
            source_files=[
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
                _rel(paths["source_contracts_validator"], repo_root),
            ],
            tests=source_platform_tests + phase4_tests,
            docs=[
                "docs/reference/fabric/source-platform.md",
                "docs/reference/fabric/observability-governance.md",
            ],
            evidence={
                "source_contract_v2_count": len(source_contract_v2_ids),
                "classification_count": source_v2_classification_count,
                "owner_reviewer_count": source_v2_owner_reviewer_count,
            },
        ),
        _surface(
            surface_id="trust.source_deprecation_sunset_policy",
            plane="trust",
            status=_status_if(
                _has_token(paths["source_contract_v2"], "SourceDeprecationPolicy")
                and _has_token(paths["source_platform_doc"], "Deprecation And Sunset Policy")
                and bool(source_platform_tests)
            ),
            priority="P2",
            title="Source deprecation and sunset policy",
            description=(
                "SourceContract v2 models deprecated/sunset status with owner-reviewed "
                "reason, migration note, replacement, and retained historical replay."
            ),
            source_files=[
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_platform_doc"], repo_root),
            ],
            tests=source_platform_tests,
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "deprecation_model": _has_token(
                    paths["source_contract_v2"], "SourceDeprecationPolicy"
                ),
                "sunset_doc": _has_token(
                    paths["source_platform_doc"], "Deprecation And Sunset Policy"
                ),
            },
        ),
        _surface(
            surface_id="trust.lineage_nodes_edges",
            plane="trust",
            status=_status_if(_path_exists(paths["lineage"]) and bool(lineage_tests)),
            priority="P1",
            title="Lineage graph nodes, edges, trace, and impact APIs",
            description="FabricLineageTracker records source, schema, dataset, transform, query, and claim lineage.",
            source_files=[_rel(paths["lineage"], repo_root)],
            tests=lineage_tests,
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "trace_value_origin": _has_token(paths["lineage"], "trace_value_origin"),
                "trace_column_lineage": _has_token(paths["lineage"], "trace_column_lineage"),
                "impact_analysis": _has_token(paths["lineage"], "impact_analysis"),
            },
        ),
        _surface(
            surface_id="trust.openlineage_export",
            plane="trust",
            status=_status_if(
                _path_exists(paths["lineage"])
                and _has_token(paths["lineage"], "export_openlineage_json")
                and "tests/unit/fabric/test_lineage.py" in lineage_tests
            ),
            priority="P2",
            title="OpenLineage export",
            description="OpenLineage-shaped export for Fabric provenance graphs.",
            source_files=[_rel(paths["lineage"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/unit/fabric/test_lineage.py"]),
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "export_openlineage_json": _has_token(paths["lineage"], "export_openlineage_json")
            },
        ),
        _surface(
            surface_id="trust.prov_export",
            plane="trust",
            status=_status_if(
                _path_exists(paths["provo"])
                and "tests/unit/fabric/test_provenance.py" in tests_by_plane["trust"]
            ),
            priority="P2",
            title="W3C PROV export",
            description="PROV-O JSON-LD and PROV-JSON export surface for governed provenance.",
            source_files=[_rel(paths["provo"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/unit/fabric/test_provenance.py"]),
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "prov_o_export": _has_token(paths["provo"], "PROV-O"),
                "prov_json_export": _has_token(paths["provo"], "PROV-JSON"),
            },
        ),
        _surface(
            surface_id="trust.runtime_lineage_adapter",
            plane="trust",
            status=_status_if(
                _path_exists(paths["lineage_route"])
                and _path_exists(paths["lineage_service"])
                and "tests/unit/runtime/http/test_lineage_api.py" in tests_by_plane["trust"]
            ),
            priority="P1",
            title="Runtime lineage API adapter",
            description="HTTP route/service adapter for trace and impact lookup over Fabric lineage.",
            source_files=[
                _rel(paths["lineage_route"], repo_root),
                _rel(paths["lineage_service"], repo_root),
            ],
            tests=_existing_paths(repo_root, ["tests/unit/runtime/http/test_lineage_api.py"]),
            docs=["docs/reference/fabric/lineage.md", "docs/reference/api/index.md"],
            evidence={
                "route": _path_exists(paths["lineage_route"]),
                "service": _path_exists(paths["lineage_service"]),
            },
        ),
        _surface(
            surface_id="trust.entity_resolution_override_governance",
            plane="trust",
            status=_status_if(
                _path_exists(paths["entity_resolution_models"])
                and _path_exists(paths["entity_resolution_store"])
                and _has_token(paths["entity_resolution_models"], "EntityOverrideAuditRecord")
                and _has_token(paths["entity_resolution_models"], "EntityOverrideEnvelope")
                and _has_token(paths["entity_resolution_store"], "merge_governance_ref")
                and _has_token(paths["entity_resolution_store"], "list_override_audit")
                and bool(discovery_tests)
            ),
            priority="P1",
            title="Entity override provenance and merge governance",
            description=(
                "Entity matches remain candidates until an accepted/rejected override is "
                "persisted with actor, reason, provenance, append-only audit evidence, "
                "and merge-governance reference for accepted canonical writes."
            ),
            source_files=[
                _rel(paths["entity_resolution_models"], repo_root),
                _rel(paths["entity_resolution_store"], repo_root),
            ],
            tests=discovery_tests,
            docs=["docs/reference/fabric/discovery-intelligence.md"],
            evidence={
                "override_audit_model": _has_token(
                    paths["entity_resolution_models"], "EntityOverrideAuditRecord"
                ),
                "override_envelope": _has_token(
                    paths["entity_resolution_models"], "EntityOverrideEnvelope"
                ),
                "merge_governance_required": _has_token(
                    paths["entity_resolution_store"], "merge_governance_ref"
                ),
                "append_only_index": _has_token(
                    paths["entity_resolution_store"], "entity_resolution_overrides.jsonl"
                ),
            },
        ),
        _surface(
            surface_id="trust.access_classification",
            plane="trust",
            status=_status_if(
                _path_exists(paths["access_control"])
                and _path_exists(paths["column_mask"])
                and _path_exists(paths["pii_stage"])
                and bool(source_contract_v2_ids)
                and source_v2_field_policy_coverage_count == len(source_contract_v2_ids)
                and bool(access_tests)
            ),
            priority="P1",
            title="Field-level access classification and masking inventory",
            description=(
                "Access policies, column masking, PII staging, and SourceContract v2 "
                "field policies prove classification coverage for every production "
                "schema field or a wildcard template surface."
            ),
            source_files=[
                _rel(paths["access_control"], repo_root),
                _rel(paths["column_mask"], repo_root),
                _rel(paths["pii_stage"], repo_root),
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
            ],
            tests=access_tests,
            docs=["docs/reference/fabric/time-travel.md", "docs/reference/fabric/quality.md"],
            evidence={
                "access_control_module": _path_exists(paths["access_control"]),
                "column_mask_module": _path_exists(paths["column_mask"]),
                "pii_stage_module": _path_exists(paths["pii_stage"]),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "field_access_policy_contract_count": source_v2_field_policy_contract_count,
                "field_access_policy_count": source_v2_field_policy_count,
                "field_policy_coverage_count": source_v2_field_policy_coverage_count,
                "access_tests": access_tests,
            },
        ),
        _surface(
            surface_id="trust.fabric_decision_envelope",
            plane="trust",
            status=decision_data_status,
            priority="P1",
            title="Fabric decision envelope",
            description=(
                "Fabric-level envelope binding source, quality, lineage, replay, temporal, "
                "and access state into a single decision-bearing contract."
            ),
            source_files=[
                _rel(paths["decision_data"], repo_root),
                _rel(paths["trust_envelope_schema"], repo_root),
                _rel(paths["runs_route"], repo_root),
                _rel(paths["lineage_service"], repo_root),
            ],
            tests=decision_data_tests,
            docs=[
                "docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md",
                "docs/reference/fabric/best-in-class-inventory.md",
            ],
            evidence={
                "coverage_report": _rel(paths["decision_data_coverage_report"], repo_root),
                "required_contracts": decision_data_report.get("required_contracts", {}),
            },
            follow_up=(
                None
                if decision_data_status == "implemented"
                else "Phase 6: define and gate Fabric decision-envelope contract."
            ),
        ),
        _surface(
            surface_id="trust.fabric_decision_reason_codes",
            plane="trust",
            status=decision_data_status,
            priority="P2",
            title="Reason codes for decision-bearing unknown states",
            description=(
                "Decision-bearing untraced, unknown_quality, restricted, non_replayable, "
                "and unsupported_temporal_scope states carry required reason metadata."
            ),
            source_files=[
                _rel(paths["decision_data"], repo_root),
                _rel(paths["decision_data_coverage"], repo_root),
            ],
            tests=decision_data_tests,
            docs=["docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md"],
            evidence={
                "typed_gap_states": decision_data_report.get("typed_gap_states", []),
                "naked_decision_values": decision_data_report.get("naked_decision_values", []),
            },
            follow_up=(
                None
                if decision_data_status == "implemented"
                else "Phase 6 ratchet: add reason-code taxonomy and CI check."
            ),
        ),
        _surface(
            surface_id="trust.runtime_fabric_product_api",
            plane="trust",
            status=runtime_product_status,
            priority="P1",
            title="Runtime Fabric product API endpoints",
            description=(
                "Runtime exposes source scorecards, quality/trust batch lookup, replay, "
                "and impact analysis through additive Fabric endpoints published in "
                "OpenAPI and the generated client."
            ),
            source_files=[
                _rel(paths["fabric_route"], repo_root),
                _rel(paths["fabric_service"], repo_root),
                _rel(paths["runtime_openapi"], repo_root),
                _rel(paths["runtime_client_ts"], repo_root),
            ],
            tests=product_integration_tests,
            docs=["docs/reference/fabric/product-api-integration.md"],
            evidence={
                "operation_ids": product_runtime_operation_ids,
                "route": _path_exists(paths["fabric_route"]),
                "service": _path_exists(paths["fabric_service"]),
                "openapi": _path_exists(paths["runtime_openapi"]),
                "client": _path_exists(paths["runtime_client_ts"]),
            },
        ),
        _surface(
            surface_id="trust.frontend_fabric_contract_fixtures",
            plane="trust",
            status=frontend_product_status,
            priority="P1",
            title="Frontend Fabric product contract fixtures",
            description=(
                "Dashboard contract fixtures cover Quantity, provenance hover, Trust "
                "View, temporal scrubber, policy diff, counterfactual layer, scorecards, "
                "replay, and impact analysis payloads."
            ),
            source_files=[
                _rel(paths["dashboard_fixture_registry"], repo_root),
                _rel(paths["dashboard_validators"], repo_root),
                _rel(paths["dashboard_fabric_decision_adapter"], repo_root),
                _rel(paths["dashboard_fabric_decision_hook"], repo_root),
            ],
            tests=_existing_paths(
                repo_root,
                [
                    "apps/runtime-dashboard/src/test/contracts/contractFixtures.test.ts",
                    "apps/runtime-dashboard/src/shared/ui/quantity/fabric-decision-data.test.tsx",
                    "apps/runtime-dashboard/src/api/hooks/useRunFabricDecisionData.test.tsx",
                ],
            ),
            docs=["docs/reference/fabric/product-api-integration.md"],
            evidence={
                "fixture_count": product_fixture_count,
                "required_fixture_count": len(product_fixture_names),
                "fixtures": product_fixture_names,
                "fabric_decision_data_adapter": _has_token(
                    paths["dashboard_fabric_decision_adapter"],
                    "fabricDecisionDataToQuantityValue",
                ),
                "fabric_decision_data_hook": _has_token(
                    paths["dashboard_fabric_decision_hook"], "useRunFabricDecisionData"
                ),
            },
        ),
        _surface(
            surface_id="trust.scientist_fabric_trust_governance",
            plane="trust",
            status=scientist_product_status,
            priority="P1",
            title="Scientist readiness cap from Fabric trust metadata",
            description=(
                "Scientist governance consumes Fabric quality, lineage, freshness, "
                "access, and source-trust metadata to cap decision readiness."
            ),
            source_files=[
                _rel(paths["scientist_fabric_trust_gate"], repo_root),
                _rel(paths["scientist_readiness"], repo_root),
            ],
            tests=product_integration_tests,
            docs=["docs/reference/fabric/product-api-integration.md"],
            evidence={
                "pass": _path_exists(paths["scientist_fabric_trust_gate"]),
                "readiness_cap": _has_token(paths["scientist_readiness"], "fabric_readiness_cap"),
            },
        ),
        _surface(
            surface_id="trust.product_evidence_adapters",
            plane="trust",
            status=product_adapter_status,
            priority="P2",
            title="Scholar, Lex, and Foundry Fabric evidence adapters",
            description=(
                "Shared Fabric evidence paths feed Scholar citations, Lex evidence, "
                "Foundry calibration weights, and uncertainty inflation."
            ),
            source_files=[
                _rel(paths["product_integration"], repo_root),
                _rel(paths["scholar_provenance"], repo_root),
                _rel(paths["lex_provenance"], repo_root),
                _rel(paths["foundry_calibration_fabric"], repo_root),
                _rel(paths["foundry_uncertainty_fabric"], repo_root),
            ],
            tests=product_integration_tests,
            docs=["docs/reference/fabric/product-api-integration.md"],
            evidence={
                "fabric_evidence_path": _has_token(
                    paths["product_integration"], "FabricProductEvidencePath"
                ),
                "scholar": _has_token(paths["scholar_provenance"], "ScholarFabricCitation"),
                "lex": _has_token(paths["lex_provenance"], "LexFabricEvidencePath"),
                "foundry_calibration": _has_token(
                    paths["foundry_calibration_fabric"], "FabricCalibrationContext"
                ),
                "foundry_uncertainty": _has_token(
                    paths["foundry_uncertainty_fabric"], "FabricUncertaintyContext"
                ),
            },
        ),
        _surface(
            surface_id="trust.fabric_compatibility_bridges",
            plane="trust",
            status=compatibility_status,
            priority="P2",
            title="Fabric compatibility bridge governance",
            description=(
                "Temporary product/API bridges carry owner, reason, sunset date, and "
                "migration issue metadata while root Fabric facade exports stay stable."
            ),
            source_files=[
                _rel(paths["compatibility"], repo_root),
                _rel(paths["product_integration_validator"], repo_root),
                _rel(paths["product_integration_doc"], repo_root),
            ],
            tests=product_integration_tests,
            docs=["docs/reference/fabric/product-api-integration.md"],
            evidence={
                "bridge_registry": _has_token(
                    paths["compatibility"], "FABRIC_COMPATIBILITY_BRIDGES"
                ),
                "sunset_dates": _has_token(paths["compatibility"], "sunset_date"),
                "migration_issues": _has_token(paths["compatibility"], "migration_issue"),
                "root_facade_unchanged": not _has_token(
                    paths["fabric_facade"], "FabricProductEvidencePath"
                ),
            },
        ),
        _surface(
            surface_id="trust.public_facade_exports",
            plane="trust",
            status=_status_if(
                {
                    "WorldQueryError",
                    "WorldQueryRequest",
                    "execute_world_query",
                    "fabric_get_data",
                    "query_claims",
                    "query_events",
                    "query_world_table",
                    "run_connectors_ingestion",
                    "world",
                }.issubset(public_exports)
            ),
            priority="P2",
            title="Stable public facade exports",
            description="Root Fabric package exports the supported ingestion and world-query facade.",
            source_files=[_rel(paths["fabric_facade"], repo_root)],
            tests=facade_tests,
            docs=["docs/reference/fabric/index.md"],
            evidence={
                "export_count": len(public_exports),
                "exports": public_exports,
            },
        ),
    ]

    for contract_id, meta in sorted(fabric_contract_records.items()):
        connector_id = str(meta.get("connector_id", "unknown"))
        dataset_id = str(meta.get("dataset_id", "unknown"))
        surfaces.append(
            _surface(
                surface_id=f"source_contracts.{contract_id}",
                plane="source",
                status="implemented",
                priority="P1",
                title=f"Source contract: {contract_id}",
                description=(
                    "Addressable committed connector contract from the Fabric governance snapshot."
                ),
                source_files=_existing_paths(
                    repo_root, _source_contract_files(contract_id, connector_id)
                ),
                tests=source_contract_tests,
                docs=[
                    "docs/reference/fabric/connectors.md",
                    "docs/reference/fabric/schema-compatibility.md",
                    "docs/reference/fabric/best-in-class-inventory.md",
                ],
                evidence={
                    "contract_snapshot": _rel(paths["fabric_contract_snapshot"], repo_root),
                    "contract_id": contract_id,
                    "connector_id": connector_id,
                    "dataset_id": dataset_id,
                    "schema_id": str(meta.get("schema_id", contract_id)),
                    "schema_version": str(meta.get("schema_version", "unknown")),
                    "content_hash": str(meta.get("content_hash", "")),
                },
            )
        )

    coverage = {
        "source_contracts": {
            "status": "implemented" if fabric_contract_ids and legacy_contract_ids else "missing",
            "fabric_registry_contracts": len(fabric_contract_ids),
            "legacy_connector_contracts": len(legacy_contract_ids),
            "source_contract_v2_contracts": len(source_contract_v2_ids),
            "contract_ids": sorted(set(fabric_contract_ids) | set(legacy_contract_ids)),
            "tests": source_contract_tests,
        },
        "source_platform": {
            "status": "implemented"
            if source_contract_v2_ids
            and len(source_scorecard_records) == len(source_contract_v2_ids)
            and source_v2_bounded_read_count == len(source_contract_v2_ids)
            and source_v2_replay_fixture_count == len(source_contract_v2_ids)
            and source_v2_non_replayable_reason_count == 0
            and source_v2_field_policy_coverage_count == len(source_contract_v2_ids)
            and _path_exists(paths["source_contracts_validator"])
            else "missing",
            "source_contract_v2_count": len(source_contract_v2_ids),
            "source_scorecard_count": len(source_scorecard_records),
            "replay_fixture_count": source_v2_replay_fixture_count,
            "non_replayable_reason_count": source_v2_non_replayable_reason_count,
            "classification_count": source_v2_classification_count,
            "field_access_policy_contract_count": source_v2_field_policy_contract_count,
            "field_access_policy_count": source_v2_field_policy_count,
            "field_policy_coverage_count": source_v2_field_policy_coverage_count,
            "bounded_read_evidence_count": source_v2_bounded_read_count,
            "tests": source_platform_tests,
        },
        "processing_guarantees": {
            "status": "implemented"
            if source_contract_v2_ids
            and source_v2_processing_count == len(source_contract_v2_ids)
            and source_v2_dedupe_window_count == len(source_contract_v2_ids)
            and source_v2_replay_retention_count == len(source_contract_v2_ids)
            and _path_exists(paths["processing_guarantees_validator"])
            else "missing",
            "processing_contract_count": source_v2_processing_count,
            "dedupe_window_count": source_v2_dedupe_window_count,
            "replay_retention_count": source_v2_replay_retention_count,
            "streaming_runtime": _path_exists(paths["streaming"]),
            "distributed_trust_gate": _has_token(
                paths["orchestrator"], "DistributedExecutionTrustContract"
            ),
            "benchmark_suite": _has_token(paths["benchmarks"], "benchmark_query_execution"),
            "tests": processing_tests,
        },
        "source_profiles": {
            "status": "implemented" if profile_ids else "missing",
            "profile_count": len(profile_ids),
            "profile_ids": profile_ids,
            "tests": profile_tests,
        },
        "replay_fixtures": {
            "status": "implemented"
            if source_contract_v2_ids
            and source_v2_replay_fixture_count == len(source_contract_v2_ids)
            and source_v2_non_replayable_reason_count == 0
            else "partial",
            "record_replay_store": _path_exists(paths["replay_store"]),
            "quarantine_module": _path_exists(paths["quarantine"]),
            "production_entrypoint_count": len(entrypoints),
            "contract_snapshot_count": len(fabric_contract_ids),
            "source_contract_v2_count": len(source_contract_v2_ids),
            "replay_fixture_count": source_v2_replay_fixture_count,
            "non_replayable_reason_count": source_v2_non_replayable_reason_count,
            "tests": replay_tests + source_platform_tests,
        },
        "quality_contracts": {
            "status": "implemented" if source_contract_v2_ids else "partial",
            "quality_module": _path_exists(paths["quality"]),
            "connector_quality_module_count": len(quality_modules),
            "profile_count": len(profile_ids),
            "contract_count": len(fabric_contract_ids),
            "source_contract_v2_count": len(source_contract_v2_ids),
            "tests": quality_tests + source_platform_tests,
        },
        "lineage_nodes_edges": {
            "status": "implemented" if _path_exists(paths["lineage"]) else "missing",
            "lineage_module": _path_exists(paths["lineage"]),
            "openlineage_export": _has_token(paths["lineage"], "export_openlineage_json"),
            "prov_export": _path_exists(paths["provo"]),
            "tests": lineage_tests
            + _existing_paths(repo_root, ["tests/unit/fabric/test_provenance.py"]),
        },
        "temporal_support": {
            "status": "implemented"
            if _path_exists(paths["world_query"]) and _path_exists(paths["snapshots"])
            else "missing",
            "world_query": _path_exists(paths["world_query"]),
            "snapshot_store": _path_exists(paths["snapshots"]),
            "runtime_temporal_adapter": _path_exists(paths["temporal_route"])
            and _path_exists(paths["temporal_service"]),
            "tests": temporal_tests,
        },
        "access_classification": {
            "status": "implemented"
            if _path_exists(paths["access_control"])
            and _path_exists(paths["column_mask"])
            and _path_exists(paths["pii_stage"])
            and source_contract_v2_ids
            and source_v2_field_policy_coverage_count == len(source_contract_v2_ids)
            else "partial",
            "access_control_module": _path_exists(paths["access_control"]),
            "column_mask_module": _path_exists(paths["column_mask"]),
            "pii_stage_module": _path_exists(paths["pii_stage"]),
            "source_contract_v2_count": len(source_contract_v2_ids),
            "field_access_policy_contract_count": source_v2_field_policy_contract_count,
            "field_access_policy_count": source_v2_field_policy_count,
            "field_policy_coverage_count": source_v2_field_policy_coverage_count,
            "tests": access_tests,
        },
        "observability_governance": {
            "status": "implemented"
            if _path_exists(paths["observability"])
            and _path_exists(paths["connector_governance_metadata"])
            and _path_exists(paths["quality_evidence"])
            else "missing",
            "slo_contract": _path_exists(paths["observability"]),
            "connector_governance_metadata": _path_exists(paths["connector_governance_metadata"]),
            "quality_evidence": _path_exists(paths["quality_evidence"]),
            "tests": phase4_tests,
        },
        "decision_data_envelope": {
            "status": decision_data_status,
            "decision_data_module": _path_exists(paths["decision_data"]),
            "trust_envelope_schema": _path_exists(paths["trust_envelope_schema"]),
            "coverage_report": _path_exists(paths["decision_data_coverage_report"]),
            "naked_decision_values": decision_data_report.get("summary", {}).get(
                "naked_decision_value_count"
            ),
            "typed_gap_states": [
                row.get("state")
                for row in decision_data_report.get("typed_gap_states", [])
                if isinstance(row, Mapping)
            ],
            "tests": decision_data_tests,
        },
        "discovery_intelligence": {
            "status": "implemented"
            if _path_exists(paths["catalog_discovery"])
            and _path_exists(paths["entity_resolution_models"])
            and _path_exists(paths["entity_resolution_store"])
            and _path_exists(paths["discovery_intelligence_validator"])
            and _path_exists(paths["discovery_eval_fixture"])
            and _path_exists(paths["discovery_intelligence_doc"])
            and bool(discovery_tests)
            else "missing",
            "semantic_catalog": _path_exists(paths["catalog_discovery"]),
            "source_contract_v2_count": len(source_contract_v2_ids),
            "eval_case_count": discovery_eval_case_count,
            "stale_invalidation": _has_token(paths["catalog_discovery"], "stale_filter"),
            "entity_override_audit": _has_token(
                paths["entity_resolution_models"], "EntityOverrideAuditRecord"
            )
            and _has_token(paths["entity_resolution_store"], "list_override_audit"),
            "graph_reasoning": _has_token(paths["world_kuzu"], "query_world_origin_trace")
            and _has_token(paths["world_kuzu"], "query_world_policy_impact"),
            "llm_calls": 0,
            "tests": discovery_tests,
        },
        "product_api_integration": {
            "status": "implemented"
            if all(
                status == "implemented"
                for status in (
                    runtime_product_status,
                    frontend_product_status,
                    scientist_product_status,
                    product_adapter_status,
                    compatibility_status,
                )
            )
            else "missing",
            "runtime_endpoints": product_runtime_operation_ids,
            "frontend_fixture_count": product_fixture_count,
            "required_frontend_fixture_count": len(product_fixture_names),
            "scientist_trust_gate": _path_exists(paths["scientist_fabric_trust_gate"]),
            "product_adapters": product_adapter_status,
            "compatibility_bridges": compatibility_status,
            "validator": _rel(paths["product_integration_validator"], repo_root),
            "tests": product_integration_tests,
        },
        "public_facade_exports": {
            "status": "implemented" if public_exports else "missing",
            "export_count": len(public_exports),
            "exports": public_exports,
            "tests": facade_tests,
        },
        "tests_by_plane": tests_by_plane,
    }
    return (sorted(surfaces, key=lambda row: str(row["id"])), coverage)


def build_manifest(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    with measure_file_reads(repo_root) as reads:
        surfaces, coverage = _build_surfaces(repo_root, reads=reads)
        input_receipt = _input_receipt_snapshot(reads)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "phase": PHASE,
        "phase_owner": OWNER,
        "status_model": {
            "allowed_statuses": list(STATUS_VALUES),
            "allowed_priorities": list(PRIORITY_VALUES),
            "allowed_severities": list(PRIORITY_VALUES),
            "planes": list(PLANES),
            "accepted_risk_required_fields": [
                "owner",
                "reason",
                "review_date",
                "expiry_date",
            ],
            "report_only_until": "Wave 1 hardening ratchet",
        },
        "ratchet_mode": {
            "phase_0": "report_only",
            "after_wave_1": (
                "P0/P1 missing entries fail CI unless they carry accepted_risk metadata."
            ),
            "after_phase_6": (
                "decision-bearing untraced, unknown_quality, and non_replayable statuses "
                "require reason codes."
            ),
        },
        "summary": {
            "surface_count": len(surfaces),
            "status_counts": _status_counts(surfaces),
            "plane_counts": _plane_counts(surfaces),
        },
        "coverage": coverage,
        "input_receipt": input_receipt,
        "surfaces": surfaces,
    }


def validate_manifest_payload(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be fabric.best_in_class_manifest.v1")
    if payload.get("phase") != PHASE:
        errors.append("phase must be 0")

    status_model = payload.get("status_model", {})
    if not isinstance(status_model, Mapping):
        errors.append("status_model must be an object")
    else:
        statuses = status_model.get("allowed_statuses", [])
        priorities = status_model.get("allowed_priorities", [])
        severities = status_model.get("allowed_severities", [])
        planes = status_model.get("planes", [])
        if list(statuses) != list(STATUS_VALUES):
            errors.append("status_model.allowed_statuses is out of date")
        if list(priorities) != list(PRIORITY_VALUES):
            errors.append("status_model.allowed_priorities is out of date")
        if list(severities) != list(PRIORITY_VALUES):
            errors.append("status_model.allowed_severities is out of date")
        if list(planes) != list(PLANES):
            errors.append("status_model.planes is out of date")

    surfaces = payload.get("surfaces", [])
    if not isinstance(surfaces, list):
        return errors + ["surfaces must be a list"]

    seen_ids: set[str] = set()
    required_surface_fields = {
        "id",
        "plane",
        "status",
        "priority",
        "severity",
        "phase",
        "owner",
        "source_files",
        "tests",
        "docs",
        "evidence",
    }
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, Mapping):
            errors.append(f"surfaces[{index}] must be an object")
            continue
        surface_id = str(surface.get("id", f"surfaces[{index}]"))
        missing_fields = sorted(required_surface_fields - set(surface))
        if missing_fields:
            errors.append(f"{surface_id}: missing fields: {', '.join(missing_fields)}")
        if surface_id in seen_ids:
            errors.append(f"{surface_id}: duplicate surface id")
        seen_ids.add(surface_id)

        status = surface.get("status")
        priority = surface.get("priority")
        severity = surface.get("severity")
        plane = surface.get("plane")
        if status not in STATUS_VALUES:
            errors.append(f"{surface_id}: invalid status {status!r}")
        if priority not in PRIORITY_VALUES:
            errors.append(f"{surface_id}: invalid priority {priority!r}")
        if severity not in PRIORITY_VALUES:
            errors.append(f"{surface_id}: invalid severity {severity!r}")
        if plane not in PLANES:
            errors.append(f"{surface_id}: invalid plane {plane!r}")
        if surface.get("phase") != PHASE:
            errors.append(f"{surface_id}: phase must be 0")

        for field in ("source_files", "tests", "docs"):
            if not isinstance(surface.get(field), list):
                errors.append(f"{surface_id}: {field} must be a list")
        if not isinstance(surface.get("evidence"), Mapping):
            errors.append(f"{surface_id}: evidence must be an object")

        if status in {"partial", "missing", "blocked_by_research"}:
            if not surface.get("owner") and not surface.get("follow_up"):
                errors.append(f"{surface_id}: gap surfaces require owner or follow_up")
            if not surface.get("follow_up"):
                errors.append(f"{surface_id}: gap surfaces require a follow_up placeholder")

        if status == "accepted_risk":
            risk = surface.get("accepted_risk")
            if not isinstance(risk, Mapping):
                errors.append(f"{surface_id}: accepted_risk metadata is required")
            else:
                for field in ("owner", "reason", "review_date", "expiry_date"):
                    if not risk.get(field):
                        errors.append(f"{surface_id}: accepted_risk.{field} is required")

    summary = payload.get("summary", {})
    if isinstance(summary, Mapping):
        status_counts = summary.get("status_counts", {})
        if isinstance(status_counts, Mapping):
            for status in STATUS_VALUES:
                if status not in status_counts:
                    errors.append(f"summary.status_counts missing {status}")
    return errors


def dump_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def _md_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _md_code_text(value: object) -> str:
    """Render source text literally as Markdown code, preserving visible line breaks."""
    text = str(value)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rendered: list[str] = []
    for line in lines:
        longest_backtick_run = 0
        current_backtick_run = 0
        for character in line:
            if character == "`":
                current_backtick_run += 1
                longest_backtick_run = max(longest_backtick_run, current_backtick_run)
            else:
                current_backtick_run = 0
        delimiter = "`" * (longest_backtick_run + 1)
        padding = " " if line.startswith(("`", " ")) or line.endswith(("`", " ")) else ""
        rendered.append(f"{delimiter}{padding}{line}{padding}{delimiter}")
    return "<br>".join(rendered)


def _md_code_list(values: Iterable[str], *, limit: int = 5) -> str:
    rows = [f"`{value}`" for value in values]
    if not rows:
        return "-"
    if len(rows) <= limit:
        return ", ".join(rows)
    return ", ".join(rows[:limit]) + f", +{len(rows) - limit} more"


def _evidence_summary(evidence: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for key, value in evidence.items():
        if isinstance(value, bool):
            rows.append(f"{_md_code_text(key)}={str(value).lower()}")
        elif isinstance(value, int):
            rows.append(f"{_md_code_text(key)}={value}")
        elif isinstance(value, str):
            rows.append(f"{_md_code_text(key)}={_md_code_text(value)}")
        elif isinstance(value, (Mapping, list)):
            rows.append(f"{_md_code_text(key)}={len(value)}")
        if len(rows) == 4:
            break
    return _md_escape("; ".join(rows) if rows else "-")


def _plane_title(plane: str) -> str:
    return {
        "source": "Source",
        "evidence": "Evidence",
        "semantics": "Semantics",
        "world": "World",
        "trust": "Trust",
    }[plane]


def render_markdown(manifest: Mapping[str, Any]) -> str:
    surfaces = [surface for surface in manifest.get("surfaces", []) if isinstance(surface, Mapping)]
    summary = manifest.get("summary", {})
    coverage = manifest.get("coverage", {})
    input_receipt = manifest.get("input_receipt", {})
    status_counts = summary.get("status_counts", {}) if isinstance(summary, Mapping) else {}
    plane_counts = summary.get("plane_counts", {}) if isinstance(summary, Mapping) else {}
    receipt = input_receipt if isinstance(input_receipt, Mapping) else {}
    receipt_inputs = receipt.get("inputs", [])
    receipt_count = len(receipt_inputs) if isinstance(receipt_inputs, list) else 0
    unresolved = receipt.get("unresolved_by_construction", [])
    unresolved_count = len(unresolved) if isinstance(unresolved, list) else 0

    lines = [
        "# Fabric Best-in-Class Inventory",
        "",
        "Freshness: 2026-04-26.",
        f"Owner: `{OWNER}`",
        "Source of truth: `tools/quality/validation/fabric_best_in_class_inventory.py`, "
        "`tools/quality/validation/fabric_best_in_class_manifest.json`, and repository "
        "source inputs listed in the manifest's `input_receipt`.",
        "Phase: 0 baseline inventory.",
        "",
        "This page is generated from "
        "`tools/quality/validation/fabric_best_in_class_manifest.json` by "
        "`tools/quality/validation/fabric_best_in_class_inventory.py`.",
        "",
        "Phase 0 is report-only: `--check` fails only when the committed manifest "
        "or report drift from the current repository inventory. It does not fail "
        "because a surface is `partial`, `missing`, `accepted_risk`, or "
        "`blocked_by_research`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| ------ | ----- |",
        f"| Schema version | `{manifest.get('schema_version')}` |",
        f"| Generated at | `{manifest.get('generated_at')}` |",
        f"| Surface count | {summary.get('surface_count', 0) if isinstance(summary, Mapping) else 0} |",
    ]
    for status in STATUS_VALUES:
        lines.append(f"| `{status}` | {status_counts.get(status, 0)} |")
    for plane in PLANES:
        lines.append(f"| `{plane}` plane surfaces | {plane_counts.get(plane, 0)} |")

    lines.extend(
        [
            "",
            "## Input Receipt",
            "",
            f"Scope: {_md_code_text(receipt.get('scope', 'not recorded'))}",
            f"Selector: {_md_code_text(receipt.get('selector', 'not recorded'))}",
            f"Explicit filesystem operations: {receipt_count}; "
            f"complete verdict: `{str(receipt.get('complete_verdict', False)).lower()}`; "
            f"unresolved boundary classes: {unresolved_count}.",
            f"Receipt SHA-256: `{_input_receipt_digest(receipt)}`.",
            "The full path, operation, status, selector, and content-hash receipt is in "
            "`tools/quality/validation/fabric_best_in_class_manifest.json` under "
            "`input_receipt`; the Markdown view binds it without duplicating its records.",
        ]
    )

    lines.extend(
        [
            "",
            "## Coverage Report",
            "",
            "| Coverage Area | Status | Evidence |",
            "| ------------- | ------ | -------- |",
        ]
    )
    if isinstance(coverage, Mapping):
        for key in (
            "source_contracts",
            "source_platform",
            "processing_guarantees",
            "source_profiles",
            "replay_fixtures",
            "quality_contracts",
            "lineage_nodes_edges",
            "temporal_support",
            "access_classification",
            "observability_governance",
            "decision_data_envelope",
            "discovery_intelligence",
            "product_api_integration",
            "public_facade_exports",
        ):
            item = coverage.get(key, {})
            if not isinstance(item, Mapping):
                continue
            lines.append(
                f"| `{key}` | `{item.get('status', 'missing')}` | {_evidence_summary(item)} |"
            )

        tests_by_plane = coverage.get("tests_by_plane", {})
        if isinstance(tests_by_plane, Mapping):
            lines.extend(
                [
                    "",
                    "## Tests By Plane",
                    "",
                    "| Plane | Tests |",
                    "| ----- | ----- |",
                ]
            )
            for plane in PLANES:
                tests = tests_by_plane.get(plane, [])
                values = [str(test) for test in tests] if isinstance(tests, list) else []
                lines.append(f"| {_plane_title(plane)} | {_md_code_list(values, limit=8)} |")

    for plane in PLANES:
        plane_surfaces = [surface for surface in surfaces if surface.get("plane") == plane]
        lines.extend(
            [
                "",
                f"## {_plane_title(plane)} Plane",
                "",
                "| ID | Status | Priority | Title | Evidence | Follow-up |",
                "| -- | ------ | -------- | ----- | -------- | --------- |",
            ]
        )
        for surface in plane_surfaces:
            follow_up = surface.get("follow_up", "")
            if surface.get("status") == "accepted_risk":
                risk = surface.get("accepted_risk", {})
                if isinstance(risk, Mapping):
                    follow_up = (
                        f"accepted risk: {_md_code_text(risk.get('reason', '-'))}; "
                        f"review {risk.get('review_date', '-')}; "
                        f"expires {risk.get('expiry_date', '-')}"
                    )
            lines.append(
                "| "
                f"`{surface.get('id')}` | "
                f"`{surface.get('status')}` | "
                f"`{surface.get('priority')}` | "
                f"{_md_escape(surface.get('title', ''))} | "
                f"{_evidence_summary(surface.get('evidence', {}))} | "
                f"{_md_escape(follow_up or '-')} |"
            )

    gap_surfaces = [
        surface
        for surface in surfaces
        if surface.get("status") in {"partial", "missing", "accepted_risk", "blocked_by_research"}
    ]
    gap_surfaces.sort(
        key=lambda surface: (
            str(surface.get("priority", "")),
            str(surface.get("status", "")),
            str(surface.get("id", "")),
        )
    )
    lines.extend(
        [
            "",
            "## Gaps By Phase And Priority",
            "",
            "| Priority | Phase | Status | ID | Owner | Follow-up / Risk |",
            "| -------- | ----- | ------ | -- | ----- | ---------------- |",
        ]
    )
    for surface in gap_surfaces:
        follow_up = surface.get("follow_up", "")
        if surface.get("status") == "accepted_risk":
            risk = surface.get("accepted_risk", {})
            if isinstance(risk, Mapping):
                follow_up = (
                    f"{_md_code_text(risk.get('reason', '-'))}; "
                    f"review {risk.get('review_date', '-')}; "
                    f"expires {risk.get('expiry_date', '-')}"
                )
        lines.append(
            "| "
            f"`{surface.get('priority')}` | "
            f"{surface.get('phase')} | "
            f"`{surface.get('status')}` | "
            f"`{surface.get('id')}` | "
            f"`{surface.get('owner')}` | "
            f"{_md_escape(follow_up or FOLLOW_UP_PLACEHOLDER)} |"
        )

    lines.extend(
        [
            "",
            "## Ratchet Mode",
            "",
            "| Stage | Behavior |",
            "| ----- | -------- |",
            "| First PR | Report-only drift check for manifest/report freshness. |",
            "| After Wave 1 hardening | P0/P1 `missing` entries fail CI unless they carry `accepted_risk`. |",
            "| After Phase 6 | Decision-bearing `untraced`, `unknown_quality`, and `non_replayable` statuses require reason codes. |",
            "",
            "## Validation",
            "",
            "```bash",
            "uv run python tools/quality/validation/fabric_wave2_strict_closure.py --check",
            "uv run python tools/quality/validation/fabric_best_in_class_inventory.py --check",
            "uv run bash tools/quality/validation/run_fabric_best_in_class_inventory.sh",
            "uv run pytest tests/repo_quality/tools/test_fabric_best_in_class_inventory.py -q",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def check_artifacts(
    *,
    repo_root: Path,
    manifest_path: Path,
    docs_path: Path,
) -> list[str]:
    manifest = build_manifest(repo_root)
    errors = validate_manifest_payload(manifest)
    if errors:
        return errors

    expected_manifest = dump_json(manifest)
    expected_report = render_markdown(manifest)

    drift: list[str] = []
    if not _path_exists(manifest_path):
        drift.append(f"manifest missing: {_rel(manifest_path, repo_root)}")
    elif measured_read_text(manifest_path, encoding="utf-8") != expected_manifest:
        drift.append(f"manifest out of date: {_rel(manifest_path, repo_root)}")

    if not _path_exists(docs_path):
        drift.append(f"report missing: {_rel(docs_path, repo_root)}")
    elif measured_read_text(docs_path, encoding="utf-8") != expected_report:
        drift.append(f"report out of date: {_rel(docs_path, repo_root)}")
    return drift


def update_artifacts(
    *,
    repo_root: Path,
    manifest_path: Path,
    docs_path: Path,
) -> dict[str, Any]:
    manifest = build_manifest(repo_root)
    errors = validate_manifest_payload(manifest)
    if errors:
        raise ValueError("\n".join(errors))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path, dump_json(manifest))
    atomic_write_text(docs_path, render_markdown(manifest))
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.check and args.update:
        print("ERROR: --check and --update are mutually exclusive")
        return 2

    repo_root = args.repo_root.resolve()
    manifest_path = _resolve_path(args.manifest, repo_root)
    docs_path = _resolve_path(args.docs_out, repo_root)

    if args.update:
        try:
            manifest = update_artifacts(
                repo_root=repo_root,
                manifest_path=manifest_path,
                docs_path=docs_path,
            )
        except ValueError as exc:
            print("Fabric best-in-class inventory update FAILED")
            print(exc)
            return 1
        print(f"Updated Fabric best-in-class manifest: {_rel(manifest_path, repo_root)}")
        print(f"Updated Fabric best-in-class report: {_rel(docs_path, repo_root)}")
        print(
            "Input receipt: "
            + _input_receipt_summary(manifest["input_receipt"])
            + "; full receipt is in the manifest."
        )
        return 0

    if args.check:
        with measure_file_reads(repo_root) as reads:
            drift = check_artifacts(
                repo_root=repo_root,
                manifest_path=manifest_path,
                docs_path=docs_path,
            )
            check_receipt = _input_receipt_snapshot(
                reads,
                scope=(
                    "Artifact check includes manifest derivation plus explicit reads and "
                    "probes of the checked manifest and Markdown report."
                ),
            )
        if drift:
            print("Fabric best-in-class inventory check FAILED")
            for row in drift:
                print(f"- {row}")
            print(
                "Run: uv run python tools/quality/validation/"
                "fabric_best_in_class_inventory.py --update"
            )
            print("Input receipt (explicit operations; incomplete by construction):")
            print(dump_json(check_receipt), end="")
            return 1
        print("Fabric best-in-class inventory check PASSED (report-only)")
        print("Input receipt (explicit operations; incomplete by construction):")
        print(dump_json(check_receipt), end="")
        return 0

    manifest = build_manifest(repo_root)
    errors = validate_manifest_payload(manifest)
    if errors:
        print("Fabric best-in-class inventory is invalid", file=sys.stderr)
        for row in errors:
            print(f"- {row}", file=sys.stderr)
        return 1
    print(dump_json(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
