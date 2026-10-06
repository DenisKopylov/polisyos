#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import contextlib
import datetime as dt
import difflib
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tools.lib.fs import (
    admitted_file_digest,
    admitted_is_file,
    admitted_read_bytes,
    measure_file_reads,
)
from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
DEFAULT_PUBLIC_MANIFEST = REPO_ROOT / "architecture" / "public_surface" / "contract.toml"
DEFAULT_PUBLIC_JSON = REPO_ROOT / "architecture" / "public_surface" / "inventory.json"
DEFAULT_PUBLIC_MD = REPO_ROOT / "docs" / "reference" / "public-surface.md"
DEFAULT_GENERATED_MANIFEST = REPO_ROOT / "architecture" / "generated_artifacts.toml"
DEFAULT_GENERATED_MD = REPO_ROOT / "docs" / "reference" / "generated-artifacts.md"
DEFAULT_DEEP_IMPORT_BASELINE = REPO_ROOT / "architecture" / "baselines" / "imports" / "deep_import.json"
DEFAULT_EXCEPTION_FILE = REPO_ROOT / "architecture" / "exceptions" / "guardrails.toml"
DEFAULT_EXCEPTION_REGISTRY = REPO_ROOT / "architecture" / "guardrail_exceptions_registry.md"
DEFAULT_MODULE_SIZE_BUDGET = REPO_ROOT / "architecture" / "module_size_budget.toml"
DEFAULT_MAX_EXPIRY_DAYS = 90
STATUS_RETIREMENT_STANDALONE_NOTICE = (
    "Standalone Atlas gate: "
    "architecture/atlas_surfaces/check_status_retirement_inventory.py is not run by "
    "`uv run polisyos-tools architecture guardrails check`; run it explicitly or "
    "through architecture/atlas_surfaces/check_atlas_enforcement.py."
)
RUNTIME_OPENAPI_CLIENT_SOURCE = "schemas/runtime_api_v1.openapi.json"
FRESHNESS_PATTERNS = (
    re.compile(r"^- Last updated:\s+\d{4}-\d{2}-\d{2}$", flags=re.MULTILINE),
    re.compile(r"^- Последнее обновление:\s+\d{4}-\d{2}-\d{2}$", flags=re.MULTILINE),
)
WHERE_TO_START_PATTERNS = (
    "## Where to Start",
    "## Где начать",
)
WORKFLOW_BASELINE_REQUIREMENTS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "ops/ci/templates/workflows/arch.yml": (
        (
            "python_baseline",
            'python-version: "3.14"',
            "Architecture workflow must use the Python 3.14 contributor baseline.",
        ),
        (
            "node_baseline",
            'node-version: "22"',
            "Architecture workflow must use the Node 22 contributor baseline.",
        ),
        (
            "uv_sync",
            "uv sync --frozen --extra lint --extra test --extra runtime --extra causal-discovery",
            "Architecture workflow must install Python dependencies via the canonical `uv sync` baseline.",
        ),
        (
            "pnpm_install",
            "corepack pnpm install --frozen-lockfile",
            "Architecture workflow must use the canonical `corepack pnpm` frontend install.",
        ),
        (
            "uv_guardrails",
            "uv run polisyos-tools architecture guardrails check",
            "Architecture workflow must run the architecture guardrails inside the synced `uv` environment.",
        ),
    ),
}
WORKFLOW_RUN_REQUIREMENTS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "ops/ci/templates/workflows/arch.yml": (
        (
            "trust_claim_posture",
            "import-gate",
            "uv run pytest tests/repo_quality/tools/test_trust_claim_posture.py -q",
            "Architecture workflow must run the trust-claim posture semantic guardrail.",
        ),
    ),
}
WORKFLOW_BASELINE_FORBIDDEN: dict[str, tuple[tuple[str, str, str], ...]] = {
    "ops/ci/templates/workflows/arch.yml": (
        (
            "legacy_pip_install",
            'pip install -e ".[dev,test,causal-discovery]"',
            "Architecture workflow must not bootstrap repo dependencies with `pip install -e`; use `uv sync` instead.",
        ),
        (
            "legacy_npm_ci",
            "run: npm ci",
            "Architecture workflow must not use `npm ci`; use `corepack pnpm install --frozen-lockfile` instead.",
        ),
        (
            "legacy_npm_install",
            "run: npm install",
            "Architecture workflow must not use `npm install`; use `corepack pnpm install --frozen-lockfile` instead.",
        ),
    ),
}


@dataclass(frozen=True)
class PackagePolicy:
    module: str
    classification: str
    facade_mode: str
    owner: str
    readme: Path
    reference_doc: Path
    supported_entrypoints: tuple[str, ...]
    major_subsystem: bool
    notes: str


@dataclass(frozen=True)
class SupportedEntrypointInventory:
    """Resolved source and exports for one declared public entrypoint."""

    module: str
    facade_mode_observed: str
    export_count: int | None
    known_export_count: int
    exports: tuple[str, ...]
    has___getattr__: bool
    has___dir__: bool
    source_file: str
    summary: str
    export_resolution: dict[str, Any]


@dataclass(frozen=True)
class PackageInventory:
    module: str
    classification: str
    facade_mode_expected: str
    facade_mode_observed: str
    owner: str
    readme: str
    reference_doc: str
    supported_entrypoints: tuple[str, ...]
    major_subsystem: bool
    export_count: int | None
    known_export_count: int
    exports: tuple[str, ...]
    has___getattr__: bool
    has___dir__: bool
    source_file: str
    summary: str
    notes: str
    entrypoints: tuple[SupportedEntrypointInventory, ...]


@dataclass(frozen=True)
class DeepImportEdge:
    source_module: str
    source_root: str
    source_file: str
    target_module: str
    target_root: str

    @property
    def key(self) -> str:
        return f"{self.source_module}->{self.target_module}"


@dataclass(frozen=True)
class GuardrailException:
    exception_id: str
    check: str
    owner: str
    reason: str
    expires: dt.date
    subject_glob: str
    detail_glob: str
    source_module_glob: str
    target_module_glob: str


@dataclass(frozen=True)
class GuardrailViolation:
    check: str
    subject: str
    message: str
    detail: str = ""
    source_module: str = ""
    target_module: str = ""


@dataclass(frozen=True)
class UnrunGeneratedCheck:
    """A required measurement whose producer could not complete."""

    family_id: str
    phase: str
    diagnostic: str


class GeneratedArtifactCheckUnrunError(RuntimeError):
    """Carry unavailable measurements separately from completed artifact findings."""

    def __init__(
        self,
        unrun_checks: Sequence[UnrunGeneratedCheck],
        violations: Sequence[GuardrailViolation] = (),
    ) -> None:
        self.unrun_checks = tuple(unrun_checks)
        self.violations = tuple(violations)
        super().__init__(
            "UNRUN: "
            + "; ".join(
                f"{item.family_id} [{item.phase}]: {item.diagnostic}" for item in self.unrun_checks
            )
        )


class _RetainedFreshnessWorkspaceError(RuntimeError):
    """The caller-selected retained workspace could not be safely created."""


@dataclass(frozen=True)
class ReadmeGateSubject:
    module: str
    readme: str
    major_subsystem: bool
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class GeneratedArtifactFamily:
    family_id: str
    label: str
    owner: str
    approval_owner: str
    lifecycle: str
    generator: str
    verifier: str
    promotion_target: str
    stale_output_behavior: str
    source_of_truth: str
    outputs: tuple[Path, ...]
    regenerate_commands: tuple[str, ...]
    commit_policy: str
    freshness_rule: str
    drift_gate: str
    workflow: Path | None
    check_cwd: Path | None
    check_command: tuple[str, ...] | None
    check_git_diff_paths: tuple[Path, ...]
    default_freshness_check: bool
    output_probe_command: tuple[str, ...] | None
    retention_days: int | None


@dataclass(frozen=True)
class PublicGeneratedArtifactFamily:
    family_id: str
    owner: str
    regenerate: str
    stale_output_behavior: str
    outputs: tuple[str, ...]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render and validate architecture guardrail inventories."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync", help="Render inventories and baseline files.")
    _add_common_args(sync)
    sync.add_argument(
        "--skip-deep-import-baseline",
        action="store_true",
        help="Do not rewrite the deep-import baseline JSON.",
    )

    check = subparsers.add_parser("check", help="Validate manifests, inventories, and baselines.")
    _add_common_args(check)
    generated_check_mode = check.add_mutually_exclusive_group()
    generated_check_mode.add_argument(
        "--all-generated-checks",
        action="store_true",
        help=(
            "Run optional generated-artifact checks in addition to the required default "
            "freshness checks."
        ),
    )
    generated_check_mode.add_argument(
        "--skip-generated-checks",
        action="store_true",
        help="Explicitly skip even the required default generated-artifact freshness checks.",
    )
    check.add_argument(
        "--generated-expected-root",
        type=Path,
        default=REPO_ROOT,
        help=(
            "Compare generator-observed candidates with a mirrored expected-output root "
            "instead of the worktree."
        ),
    )
    check.add_argument(
        "--generated-freshness-workspace-root",
        type=Path,
        help=(
            "Retain the generated-freshness source, private environment, and outputs under "
            "a new per-run directory. Existing paths are rejected and never removed."
        ),
    )
    check.add_argument(
        "--generated-freshness-uv-cache-dir",
        type=Path,
        help=(
            "Use this existing uv cache offline for a retained generated-freshness run. "
            "Required together with --generated-freshness-workspace-root."
        ),
    )
    check.add_argument(
        "--max-expiry-days",
        type=int,
        default=DEFAULT_MAX_EXPIRY_DAYS,
        help="Maximum allowed exception lifetime in days.",
    )

    return parser.parse_args()


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--public-manifest", type=Path, default=DEFAULT_PUBLIC_MANIFEST)
    parser.add_argument("--public-json", type=Path, default=DEFAULT_PUBLIC_JSON)
    parser.add_argument("--public-md", type=Path, default=DEFAULT_PUBLIC_MD)
    parser.add_argument("--generated-manifest", type=Path, default=DEFAULT_GENERATED_MANIFEST)
    parser.add_argument("--generated-md", type=Path, default=DEFAULT_GENERATED_MD)
    parser.add_argument("--deep-import-baseline", type=Path, default=DEFAULT_DEEP_IMPORT_BASELINE)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTION_FILE)
    parser.add_argument("--exceptions-registry", type=Path, default=DEFAULT_EXCEPTION_REGISTRY)


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _ensure_relative(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else REPO_ROOT / path


def _parse_check_command(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return tuple(shlex.split(value))
    if isinstance(value, Sequence):
        return tuple(str(part) for part in value)
    return (str(value),)


def _parse_public_surface(path: Path) -> list[PackagePolicy]:
    data = _read_toml(path)
    packages = data.get("package", [])
    results: list[PackagePolicy] = []
    for item in packages:
        module = str(item["module"])
        results.append(
            PackagePolicy(
                module=module,
                classification=str(item["classification"]),
                facade_mode=str(item["facade_mode"]),
                owner=str(item["owner"]),
                readme=_ensure_relative(str(item["readme"])),
                reference_doc=_ensure_relative(str(item["reference_doc"])),
                supported_entrypoints=tuple(item.get("supported_entrypoints", [])),
                major_subsystem=bool(item.get("major_subsystem", False)),
                notes=str(item.get("notes", "")),
            )
        )
    return results


def _parse_public_generated_artifact_families(path: Path) -> list[PublicGeneratedArtifactFamily]:
    data = _read_toml(path)
    families = data.get("generated_artifact_family", [])
    results: list[PublicGeneratedArtifactFamily] = []
    for item in families:
        results.append(
            PublicGeneratedArtifactFamily(
                family_id=str(item["id"]),
                owner=str(item["owner"]),
                regenerate=str(item["regenerate"]),
                stale_output_behavior=str(item["stale_output_behavior"]),
                outputs=tuple(str(output) for output in item.get("outputs", [])),
            )
        )
    return results


def _parse_generated_artifacts(path: Path | bytes) -> list[GeneratedArtifactFamily]:
    """Parse generated-family records from an owner path or already-admitted bytes."""
    data = (
        tomllib.loads(path.decode("utf-8"))
        if isinstance(path, bytes)
        else _read_toml(path)
    )
    families = data.get("family", [])
    results: list[GeneratedArtifactFamily] = []
    for item in families:
        workflow_raw = item.get("workflow")
        check_cwd_raw = item.get("check_cwd")
        check_command_raw = item.get("check_command")
        results.append(
            GeneratedArtifactFamily(
                family_id=str(item["id"]),
                label=str(item["label"]),
                owner=str(item["owner"]),
                approval_owner=str(item["approval_owner"]),
                lifecycle=str(item.get("lifecycle", "")),
                generator=str(item.get("generator", "")),
                verifier=str(item.get("verifier", "")),
                promotion_target=str(item.get("promotion_target", "")),
                stale_output_behavior=str(item.get("stale_output_behavior", "")),
                source_of_truth=str(item["source_of_truth"]),
                outputs=tuple(_ensure_relative(output) for output in item.get("outputs", [])),
                regenerate_commands=tuple(
                    str(command) for command in item.get("regenerate_commands", [])
                ),
                commit_policy=str(item["commit_policy"]),
                freshness_rule=str(item["freshness_rule"]),
                drift_gate=str(item["drift_gate"]),
                workflow=_ensure_relative(str(workflow_raw)) if workflow_raw else None,
                check_cwd=_ensure_relative(str(check_cwd_raw)) if check_cwd_raw else None,
                check_command=_parse_check_command(check_command_raw),
                check_git_diff_paths=tuple(
                    Path(part) for part in item.get("check_git_diff_paths", [])
                ),
                default_freshness_check=bool(item.get("default_freshness_check", False)),
                output_probe_command=_parse_check_command(item.get("output_probe_command")),
                retention_days=(
                    int(item["retention_days"]) if item.get("retention_days") is not None else None
                ),
            )
        )
    return results


def _parse_guardrail_exceptions(path: Path) -> list[GuardrailException]:
    if not path.exists():
        return []
    data = _read_toml(path)
    entries = data.get("exception", [])
    results: list[GuardrailException] = []
    for item in entries:
        results.append(
            GuardrailException(
                exception_id=str(item["id"]),
                check=str(item["check"]),
                owner=str(item["owner"]),
                reason=str(item["reason"]),
                expires=dt.date.fromisoformat(str(item["expires"])),
                subject_glob=str(item.get("subject_glob", "*")),
                detail_glob=str(item.get("detail_glob", "*")),
                source_module_glob=str(item.get("source_module_glob", "*")),
                target_module_glob=str(item.get("target_module_glob", "*")),
            )
        )
    return results


def _module_name_for_path(file_path: Path) -> tuple[str, bool] | None:
    relative = file_path.relative_to(SRC_ROOT)
    parts = list(relative.parts)
    if not parts or parts[0] != "polisyos":
        return None
    if parts[-1] == "__init__.py":
        return ".".join(parts[:-1]), True
    parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts), False


def _iter_py_files() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _root_for_module(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "polisyos":
        return None
    return parts[1]


def _resolve_import_module(
    current_module: str, is_package: bool, node: ast.ImportFrom
) -> str | None:
    if node.level == 0:
        return node.module
    package_parts = current_module.split(".")
    if not is_package:
        package_parts = package_parts[:-1]
    if node.level - 1 > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        base_parts += node.module.split(".")
    return ".".join(base_parts)


def _string_list_value(node: ast.AST) -> tuple[str, ...] | None:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return None
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return None


def _module_level_nodes(tree: ast.AST) -> Iterator[ast.AST]:
    """Traverse import-time expressions, including executable class bodies."""
    for node in ast.iter_child_nodes(tree):
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            outer_expressions = [*node.args.defaults, *node.args.kw_defaults]
            if not isinstance(node, ast.Lambda):
                outer_expressions += node.decorator_list
            for expression in outer_expressions:
                if expression is not None:
                    yield expression
                    yield from _module_level_nodes(expression)
        elif isinstance(node, ast.ClassDef):
            yield from _module_level_nodes(node)
        else:
            yield from _module_level_nodes(node)


def _symbol_binding_nodes(tree: ast.Module, symbol: str) -> Iterator[ast.AST]:
    """Name every module-level binding or mutation that can affect a selector."""
    for node in _module_level_nodes(tree):
        targets: list[ast.AST] = []
        if isinstance(node, (ast.Assign, ast.Delete)):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.TypeAlias)):
            targets = [node.target if hasattr(node, "target") else node.name]
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
        if any(
            isinstance(child, ast.Name) and child.id == symbol
            for target in targets for child in ast.walk(target)
        ):
            yield node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                yield node
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name == symbol:
            yield node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if any(
                alias.name == "*" or (alias.asname or alias.name.split(".")[0]) == symbol
                for alias in node.names
            ):
                yield node
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == symbol:
                yield node


class _UnresolvedExportDeclarationError(ValueError):
    """An intentional refusal by the bounded static export grammar."""


class _StaticExportResolver:
    """Resolve declared export names without importing or executing facade code.

    The finite grammar covers literal sequences/mapping keys, named declarations,
    named imports, concatenation and sorted/list/tuple over those declarations.
    An unsupported expression is undecided, never an empty export manifest.
    """

    def __init__(self, source_file: Path, tree: ast.Module) -> None:
        self._trees = {source_file: tree}
        self._active: set[tuple[Path, str]] = set()
        self._resolved: dict[tuple[Path, str], int] = {}
        self._allowed_reads: set[tuple[Path, int]] = set()
        self._allowed_calls: set[tuple[Path, int]] = set()

    def _tree(self, source: Path) -> ast.Module:
        if source not in self._trees:
            self._trees[source] = ast.parse(admitted_read_bytes(source, REPO_ROOT))
        return self._trees[source]

    def resolve(self, source: Path, symbol: str) -> object:
        key = (source, symbol)
        if key in self._active:
            raise _UnresolvedExportDeclarationError(f"Unresolved export declaration cycle: {source}:{symbol}")
        self._active.add(key)
        try:
            tree = self._tree(source)
            direct_nodes = {id(node) for node in tree.body}
            for node in _symbol_binding_nodes(tree, symbol):
                supported_assignment = (
                    isinstance(node, (ast.Assign, ast.AnnAssign))
                    and any(
                        isinstance(target, ast.Name) and target.id == symbol
                        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                    )
                )
                supported_import = isinstance(node, ast.ImportFrom) and all(
                    alias.name != "*" for alias in node.names
                )
                if id(node) not in direct_nodes or not (supported_assignment or supported_import):
                    raise _UnresolvedExportDeclarationError(f"Unresolved conditional/mutated exports: {source}:{symbol}")
            declarations: list[ast.AST] = []
            imported: list[tuple[ast.ImportFrom, str]] = []
            for node in tree.body:
                if (
                    isinstance(node, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == symbol
                        for target in node.targets
                    )
                ) or (
                    isinstance(node, ast.AnnAssign)
                    and isinstance(node.target, ast.Name)
                    and node.target.id == symbol
                    and node.value is not None
                ):
                    declarations.append(node.value)
                elif isinstance(node, ast.ImportFrom):
                    imported.extend(
                        (node, alias.name)
                        for alias in node.names
                        if (alias.asname or alias.name) == symbol
                    )
                elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                    if node.target.id == symbol:
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved mutated export declaration: {source}:{symbol}"
                        )
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    function = node.value.func
                    if (
                        isinstance(function, ast.Attribute)
                        and isinstance(function.value, ast.Name)
                        and function.value.id == symbol
                    ):
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved mutated export declaration: {source}:{symbol}"
                        )
            if len(declarations) == 1 and not imported:
                value = self._value(source, declarations[0])
                self._resolved[key] = declarations[0].end_lineno
                return value
            if len(imported) == 1 and not declarations:
                node, imported_name = imported[0]
                info = _module_name_for_path(source)
                if info is None:
                    raise _UnresolvedExportDeclarationError(f"Unresolved export import source: {source}")
                module = _resolve_import_module(*info, node)
                if module is None or not module.startswith("polisyos."):
                    raise _UnresolvedExportDeclarationError(f"Unresolved export import: {source}:{symbol}")
                value = self.resolve(_facade_source_for(module), imported_name)
                self._resolved[key] = node.end_lineno
                return value
            raise _UnresolvedExportDeclarationError(f"Unresolved or ambiguous export declaration: {source}:{symbol}")
        finally:
            self._active.remove(key)

    def _value(self, source: Path, node: ast.AST) -> object:
        if isinstance(node, ast.Name):
            self._allowed_reads.add((source, id(node)))
            return self.resolve(source, node.id)
        if isinstance(node, ast.Dict):
            # Only keys contribute to iterating/sorting a manifest map. Its values
            # identify runtime owners, which this static reader does not execute.
            keys: dict[str, None] = {}
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None:
                    mapping = self._value(source, value)
                    if not isinstance(mapping, dict):
                        raise _UnresolvedExportDeclarationError(f"Unresolved export mapping expansion: {source}")
                    keys.update(mapping)
                elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys[key.value] = None
                else:
                    raise _UnresolvedExportDeclarationError(f"Unresolved export mapping key: {source}")
            return keys
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self._value(source, node.left), self._value(source, node.right)
            if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
                return [*left, *right]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"sorted", "list", "tuple"}
            and len(node.args) == 1
            and not node.keywords
        ):
            if any(_symbol_binding_nodes(self._tree(source), node.func.id)):
                raise _UnresolvedExportDeclarationError(f"Unresolved shadowed export builtin: {source}:{node.func.id}")
            value = self._value(source, node.args[0])
            if isinstance(value, (dict, list, tuple)) and all(
                isinstance(item, str) for item in value
            ):
                self._allowed_calls.add((source, id(node)))
                return sorted(value) if node.func.id == "sorted" else list(value)
        strings = _string_list_value(node)
        if strings is not None:
            return strings
        raise _UnresolvedExportDeclarationError(f"Unresolved export expression: {source}:{ast.unparse(node)}")

    @staticmethod
    def _passive_container(node: ast.AST) -> bool:
        if isinstance(node, (ast.Constant, ast.Name)):
            return True
        if isinstance(node, (ast.List, ast.Tuple)):
            return all(_StaticExportResolver._passive_container(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return all(
                isinstance(key, ast.Constant) and _StaticExportResolver._passive_container(value)
                for key, value in zip(node.keys, node.values, strict=True)
            )
        return False

    def _admit_passive_alias(self, source: Path, read: ast.Name) -> bool:
        tree = self._tree(source)
        for declaration in tree.body:
            if not isinstance(declaration, (ast.Assign, ast.AnnAssign)):
                continue
            value = declaration.value
            if value is None or not any(node is read for node in ast.walk(value)):
                continue
            targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
            if not all(isinstance(target, ast.Name) for target in targets):
                return False
            if not self._passive_container(value):
                return False
            for target in targets:
                bindings = list(_symbol_binding_nodes(tree, target.id))
                if len(bindings) != 1 or bindings[0] is not declaration:
                    return False
            for target in targets:
                self._resolved[(source, target.id)] = declaration.end_lineno
            self._allowed_reads.add((source, id(read)))
            return True
        return False

    def audit_consumers(self) -> None:
        """A finite binding must not escape the selected declaration grammar."""
        for source in {path for path, _ in self._resolved}:
            # Passive aliases/containers are finite only if their own complete
            # module-level consumer closure is audited as well.
            while True:
                symbols = {symbol for path, symbol in self._resolved if path == source}
                changed = False
                for node in _module_level_nodes(self._tree(source)):
                    if (
                        isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                        and node.id in symbols and (source, id(node)) not in self._allowed_reads
                    ):
                        if not self._admit_passive_alias(source, node):
                            raise _UnresolvedExportDeclarationError(f"Unresolved export binding consumer: {source}:{node.id}")
                        changed = True
                if not changed:
                    break
            symbols = {symbol for path, symbol in self._resolved if path == source}
            first_bound_line = min(
                line for (path, _), line in self._resolved.items() if path == source
            )
            for node in _module_level_nodes(self._tree(source)):
                if (
                    isinstance(node, ast.Call) and node.lineno >= first_bound_line
                    and (source, id(node)) not in self._allowed_calls
                ):
                    raise _UnresolvedExportDeclarationError(f"Unresolved call after export binding: {source}:{ast.unparse(node)}")
                if (
                    isinstance(node, ast.ClassDef) and node.lineno >= first_bound_line
                    and (node.bases or node.keywords or node.decorator_list)
                ):
                    raise _UnresolvedExportDeclarationError(f"Unresolved class construction after export binding: {source}:{node.name}")


class _IncompleteExportDeclarationError(_UnresolvedExportDeclarationError):
    """A literal prefix is readable, but its extension has no static total."""

    def __init__(self, prefix: tuple[str, ...]) -> None:
        super().__init__("Unresolved __all__.extend; literal prefix only, total unknown")
        self.prefix = prefix


def _literal_prefix_before_extensions(tree: ast.Module) -> tuple[str, ...] | None:
    """Retain only a direct literal prefix followed solely by standalone extends."""
    bindings = list(_symbol_binding_nodes(tree, "__all__"))
    declarations = [node for node in bindings if isinstance(node, (ast.Assign, ast.AnnAssign))]
    if len(declarations) != 1 or len(bindings) < 2:
        return None
    declaration = declarations[0]
    targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
    if declaration not in tree.body or len(targets) != 1:
        return None
    if not isinstance(targets[0], ast.Name) or targets[0].id != "__all__":
        return None
    prefix = _string_list_value(declaration.value)
    if prefix is None:
        return None
    standalone_calls = {
        id(node.value) for node in _module_level_nodes(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    }
    allowed_names = {id(targets[0])}
    allowed_calls: set[int] = set()
    for node in bindings:
        if node is declaration:
            continue
        if not (
            isinstance(node, ast.Call)
            and id(node) in standalone_calls
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "__all__"
            and node.func.attr == "extend"
            and len(node.args) == 1
            and not isinstance(node.args[0], ast.Starred)
            and not node.keywords
            and node.lineno > declaration.end_lineno
        ):
            return None
        allowed_names.add(id(node.func.value))
        allowed_calls.add(id(node))
    # An alias or other use may mutate the prefix indirectly; do not claim it.
    if any(
        isinstance(node, ast.Name) and node.id == "__all__" and id(node) not in allowed_names
        for node in _module_level_nodes(tree)
    ):
        return None
    if any(
        isinstance(node, ast.Call) and node.lineno > declaration.end_lineno
        and id(node) not in allowed_calls for node in _module_level_nodes(tree)
    ):
        return None
    if any(
        isinstance(node, ast.ClassDef) and node.lineno > declaration.end_lineno
        and (node.bases or node.keywords or node.decorator_list)
        for node in _module_level_nodes(tree)
    ):
        return None
    return prefix


def _extract_exports(tree: ast.Module, source_file: Path | None = None) -> tuple[str, ...]:
    if not any(_symbol_binding_nodes(tree, "__all__")):
        return ()
    prefix = _literal_prefix_before_extensions(tree)
    if prefix is not None:
        raise _IncompleteExportDeclarationError(prefix)
    source = source_file or SRC_ROOT / "polisyos" / "__static_exports__.py"
    resolver = _StaticExportResolver(source, tree)
    exports = resolver.resolve(source, "__all__")
    resolver.audit_consumers()
    if not isinstance(exports, (tuple, list)) or not all(isinstance(item, str) for item in exports):
        raise _UnresolvedExportDeclarationError(f"Export declaration must resolve to string sequence: {source}")
    return tuple(exports)


def _observed_facade_mode(*, exports: tuple[str, ...], has_getattr: bool) -> str:
    if exports and has_getattr:
        return "lazy_facade"
    if exports:
        return "eager_exports"
    return "module_doc_only"


def _facade_source_for(module: str) -> Path:
    relative = Path(*module.split("."))
    candidates = (
        (SRC_ROOT / relative).with_suffix(".py"),
        SRC_ROOT / relative / "__init__.py",
    )
    resolved = tuple(path for path in candidates if admitted_is_file(path, REPO_ROOT))
    if len(resolved) != 1:
        rendered = ", ".join(str(path) for path in candidates)
        raise FileNotFoundError(
            f"Public surface entrypoint `{module}` must resolve to exactly one facade source; "
            f"found {len(resolved)} across: {rendered}"
        )
    return resolved[0]


def _entrypoint_inventory(module: str) -> SupportedEntrypointInventory:
    incomplete_reason = None
    exports_scope = None
    with measure_file_reads(REPO_ROOT) as reads:
        try:
            source_file = _facade_source_for(module)
            tree = ast.parse(admitted_read_bytes(source_file, REPO_ROOT))
            try:
                exports = _extract_exports(tree, source_file)
            except _IncompleteExportDeclarationError as exc:
                exports = exc.prefix
                incomplete_reason = str(exc)
                exports_scope = "direct unconditional literal prefix; extensions unresolved"
            except _UnresolvedExportDeclarationError as exc:
                exports = ()
                incomplete_reason = str(exc)
                exports_scope = "no names proven by the bounded parser; not an empty runtime namespace"
        except (OSError, ValueError, SyntaxError, TypeError) as exc:
            exc.add_note(json.dumps(reads.snapshot(complete_verdict=False), sort_keys=True))
            raise
        export_resolution = reads.snapshot(complete_verdict=incomplete_reason is None)
    export_resolution["complete"] = incomplete_reason is None
    if incomplete_reason is not None:
        export_resolution["reason"] = incomplete_reason
        export_resolution["exports_scope"] = exports_scope
    export_resolution["selector"] = (
        "Declared __all__; literal sequences/mapping keys, named/imported declarations, "
        "concatenation and sorted/list/tuple. No module execution or runtime dispatch."
    )
    function_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    summary = (ast.get_docstring(tree) or "").strip().splitlines()
    return SupportedEntrypointInventory(
        module=module,
        facade_mode_observed=(
            "unresolved_exports" if incomplete_reason is not None and not exports
            else _observed_facade_mode(exports=exports, has_getattr="__getattr__" in function_names)
        ),
        export_count=len(exports) if incomplete_reason is None else None,
        known_export_count=len(exports),
        exports=exports,
        has___getattr__="__getattr__" in function_names,
        has___dir__="__dir__" in function_names,
        source_file=str(source_file.relative_to(REPO_ROOT)),
        summary=summary[0] if summary else "",
        export_resolution=export_resolution,
    )


def build_public_surface_inventory(policies: list[PackagePolicy]) -> list[PackageInventory]:
    inventory: list[PackageInventory] = []
    for policy in policies:
        entrypoints = tuple(
            _entrypoint_inventory(entrypoint) for entrypoint in policy.supported_entrypoints
        )
        root_entrypoint = next(
            (entrypoint for entrypoint in entrypoints if entrypoint.module == policy.module),
            None,
        )
        if root_entrypoint is None:
            raise ValueError(
                f"Public surface policy `{policy.module}` must declare its package root entrypoint"
            )
        inventory.append(
            PackageInventory(
                module=policy.module,
                classification=policy.classification,
                facade_mode_expected=policy.facade_mode,
                facade_mode_observed=root_entrypoint.facade_mode_observed,
                owner=policy.owner,
                readme=str(policy.readme.relative_to(REPO_ROOT)),
                reference_doc=str(policy.reference_doc.relative_to(REPO_ROOT)),
                supported_entrypoints=policy.supported_entrypoints,
                major_subsystem=policy.major_subsystem,
                export_count=root_entrypoint.export_count,
                known_export_count=root_entrypoint.known_export_count,
                exports=root_entrypoint.exports,
                has___getattr__=root_entrypoint.has___getattr__,
                has___dir__=root_entrypoint.has___dir__,
                source_file=root_entrypoint.source_file,
                summary=root_entrypoint.summary,
                notes=policy.notes,
                entrypoints=entrypoints,
            )
        )
    return inventory


def collect_deep_import_edges(policies: list[PackagePolicy]) -> list[DeepImportEdge]:
    allowed_entrypoints: dict[str, set[str]] = {}
    for policy in policies:
        root = _root_for_module(policy.module)
        if root is None:
            continue
        allowed_entrypoints.setdefault(root, set()).update(policy.supported_entrypoints)

    edges: dict[str, DeepImportEdge] = {}
    for file_path in _iter_py_files():
        module_info = _module_name_for_path(file_path)
        if module_info is None:
            continue
        source_module, is_package = module_info
        source_root = _root_for_module(source_module)
        if source_root is None:
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            target_module: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target_module = alias.name
                    _maybe_add_deep_import(
                        edges=edges,
                        allowed_entrypoints=allowed_entrypoints,
                        source_module=source_module,
                        source_root=source_root,
                        source_file=file_path,
                        target_module=target_module,
                    )
            elif isinstance(node, ast.ImportFrom):
                target_module = _resolve_import_module(source_module, is_package, node)
                if target_module:
                    _maybe_add_deep_import(
                        edges=edges,
                        allowed_entrypoints=allowed_entrypoints,
                        source_module=source_module,
                        source_root=source_root,
                        source_file=file_path,
                        target_module=target_module,
                    )
    return sorted(edges.values(), key=lambda edge: (edge.source_module, edge.target_module))


def _maybe_add_deep_import(
    *,
    edges: dict[str, DeepImportEdge],
    allowed_entrypoints: dict[str, set[str]],
    source_module: str,
    source_root: str,
    source_file: Path,
    target_module: str,
) -> None:
    if target_module == "polisyos" or not target_module.startswith("polisyos."):
        return
    target_root = _root_for_module(target_module)
    if target_root is None or target_root == source_root:
        return
    if target_module == f"polisyos.{target_root}":
        return
    if target_module in allowed_entrypoints.get(target_root, set()):
        return
    edge = DeepImportEdge(
        source_module=source_module,
        source_root=source_root,
        source_file=str(source_file.relative_to(REPO_ROOT)),
        target_module=target_module,
        target_root=target_root,
    )
    edges[edge.key] = edge


def _parse_registry_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        first = parts[1].strip().strip("`")
        if not first or first in {"id", "---", "_no-active-exceptions_", "-"}:
            continue
        ids.add(first)
    return ids


def render_public_surface_json(
    inventory: list[PackageInventory],
    *,
    generated_artifact_families: list[PublicGeneratedArtifactFamily] | None = None,
) -> str:
    payload = {
        "version": 1,
        "internal_rule": "Any polisyos module path not listed here is internal by default.",
        "generated_artifact_families": [
            {
                "id": item.family_id,
                "owner": item.owner,
                "regenerate": item.regenerate,
                "stale_output_behavior": item.stale_output_behavior,
                "outputs": list(item.outputs),
            }
            for item in (generated_artifact_families or [])
        ],
        "packages": [
            {
                "module": item.module,
                "classification": item.classification,
                "facade_mode_expected": item.facade_mode_expected,
                "facade_mode_observed": item.facade_mode_observed,
                "owner": item.owner,
                "readme": item.readme,
                "reference_doc": item.reference_doc,
                "supported_entrypoints": list(item.supported_entrypoints),
                "major_subsystem": item.major_subsystem,
                "export_count": item.export_count,
                "known_export_count": item.known_export_count,
                "exports": list(item.exports),
                "has___getattr__": item.has___getattr__,
                "has___dir__": item.has___dir__,
                "source_file": item.source_file,
                "summary": item.summary,
                "notes": item.notes,
                "entrypoints": [
                    {
                        "module": entrypoint.module,
                        "facade_mode_observed": entrypoint.facade_mode_observed,
                        "export_count": entrypoint.export_count,
                        "known_export_count": entrypoint.known_export_count,
                        "exports": list(entrypoint.exports),
                        "has___getattr__": entrypoint.has___getattr__,
                        "has___dir__": entrypoint.has___dir__,
                        "source_file": entrypoint.source_file,
                        "summary": entrypoint.summary,
                        "export_resolution": entrypoint.export_resolution,
                    }
                    for entrypoint in item.entrypoints
                ],
            }
            for item in inventory
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def _export_count_display(count: int | None, known_count: int) -> str:
    if count is not None:
        return str(count)
    return f"unknown ({known_count} known prefix)" if known_count else "unknown (no names proven)"


def render_public_surface_markdown(inventory: list[PackageInventory]) -> str:
    lines = [
        "# Public Surface",
        "",
        "> Generated from `architecture/public_surface/contract.toml` and module/package facades under `src/polisyos/**/*.py`.",
        "",
        "Canonical regeneration command:",
        "",
        "```bash",
        "uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline",
        "```",
        "",
        "Supported entrypoints are intentionally explicit. Any `polisyos.*` path not listed on this page is **internal** and may change without compatibility guarantees.",
        "",
        "Classification policy:",
        "",
        "- `public_stable`: supported entrypoint with normal compatibility, release-note, and migration expectations.",
        "- `public_experimental`: documented entrypoint that should stay visible in docs and release notes when touched, but it does not promise long-term compatibility.",
        "- `internal`: any `polisyos.*` path not listed here; keep it out of public docs and release notes unless operators must care.",
        "",
        "## Policy Design Case Generated Audit Surfaces",
        "",
        "`layer3_g4_shadow_to_governed_promotion_surface` is a generated",
        "PUBLIC/REVIEWER/EXPERT/MACHINE Policy Design Case audit surface documented in",
        "`docs/reference/policy-design-case-layer3-promotion-gate.md`. It is",
        "projection-only for public export: `layer3_g4_public_export_projection_refs.json`",
        "records `out_of_scope_reference_only` rather than a runtime public-export route.",
        "",
        "`layer3_g5_first_proving_ground_conversion_surface` is a generated",
        "PUBLIC/REVIEWER/EXPERT/MACHINE Policy Design Case audit surface documented in",
        "`docs/reference/policy-design-case-layer3-proving-ground-conversion.md`. It",
        "publishes conversion-record refs, blocker/limitation refs, and projection-only",
        "public refs; `layer3_g5_public_export_projection_refs.json` records",
        "`out_of_scope_reference_only` and does not register a public-export bundle route.",
        "",
        "`layer3_g6_bounded_agent_surface` is a generated PUBLIC/REVIEWER/EXPERT/MACHINE",
        "Policy Design Case audit surface documented in",
        "`docs/reference/policy-design-case-layer3-bounded-agent.md`. It publishes",
        "agent-run refs, policy-grammar projection refs, G5 invocation refs,",
        "search-ledger refs, replay-manifest refs, orchestration-continuity refs,",
        "candidate DesignRecord handoff refs, orchestration-choice audit refs, and",
        "projection-only public refs;",
        "`layer3_g6_public_export_projection_refs.json` records",
        "`authority_preserving_public_export`, registers a redacted public-export bundle",
        "route, and emits only the owner-recomputed safe summary or governed refusal.",
        "",
        "`layer3_g7_region_widening_surface` is a generated",
        "PUBLIC/REVIEWER/EXPERT/MACHINE Policy Design Case audit surface documented here",
        "until the region-widening reference page graduates. It publishes region",
        "scorecard refs, conversion status matrix refs, S12/S13/S14 projection status,",
        "replay-manifest refs, orchestration-continuity refs, route registry refs, and",
        "projection-only public refs; `layer3_g7_public_export_projection_refs.json`",
        "records `out_of_scope_reference_only`, does not register a public-export bundle",
        "route, and does not publish universal authority.",
        "",
        "`layer3_g8_health_metric_governance_surface` is a generated EXPERT/MACHINE",
        "Policy Design Case audit surface documented here until the health-metric",
        "governance reference page graduates. It publishes metric registry refs,",
        "normalized metric signal refs, cross-metric diagnosis refs, D4.4 re-basing",
        "receipt refs, replay-manifest refs, route registry refs, blocker-specific",
        "search-health classifications for seed corpus, pinned request, current blocker,",
        "and production readiness, and",
        "`layer3_g8_closeout_signal_consumer_gate.json` refs. PUBLIC/REVIEWER access is",
        "projection-only through `layer3_g8_public_export_projection_refs.json`, which",
        "records `out_of_scope_reference_only` and does not register a public-export",
        "bundle route.",
        "",
        "`layer3_gx_universal_free_growth_hardening_surface` is a generated",
        "EXPERT/MACHINE Policy Design Case hardening audit surface documented here",
        "until the GX reference page graduates. It publishes data-home refs, runtime",
        "literal lint refs, reducer/provenance refs, measurement replay refs, vertical",
        "pinned-route refs, provisional and final Task 12 outcome/audit refs, data",
        "mutation free-growth refs, and expected-red refs. PUBLIC/REVIEWER access is",
        "out of scope until a dedicated GX public-export projection is produced; the",
        "surface does not register a public-export bundle route and does not publish",
        "production, closeout, domain-ceiling, recommendation, or useful-design",
        "authority.",
        "",
        "`layer3_gy_generated_artifact_lifecycle_surface` is a generated",
        "MACHINE/EXPERT Policy Design Case lifecycle audit surface documented in",
        "`architecture/policy_design_case/layer3_gy_task0_audit/` and",
        "`docs/reference/generated-artifacts.md`. It publishes the GY-M1 class",
        "invariant for generated-artifact family registration: every committed GY",
        "artifact must resolve to exactly one registered family output, and missing",
        "or duplicate family claims fail closed. PUBLIC/REVIEWER access is audit-only;",
        "the surface does not register a public-export bundle route and does not",
        "publish recommendation, rollout, closeout, or policy-design authority.",
        "",
        "| Package | Classification | Facade | Exports | Owner | README |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in inventory:
        readme_rel = item.readme
        lines.append(
            f"| `{item.module}` | `{item.classification}` | `{item.facade_mode_observed}` | {_export_count_display(item.export_count, item.known_export_count)} | `{item.owner}` | `{readme_rel}` |"
        )

    for item in inventory:
        lines.extend(
            [
                "",
                f"## `{item.module}`",
                "",
                f"- Classification: `{item.classification}`",
                f"- Supported entrypoints: {', '.join(f'`{entry}`' for entry in item.supported_entrypoints)}",
                f"- Facade policy: expected `{item.facade_mode_expected}`, observed `{item.facade_mode_observed}`",
                f"- Owner: `{item.owner}`",
                f"- README: `{item.readme}`",
                f"- Reference doc: `{item.reference_doc}`",
                f"- Notes: {item.notes}",
            ]
        )
        if item.summary:
            lines.append(f"- Summary: {item.summary}")
        lines.extend(
            [
                "",
                "### Resolved supported entrypoints",
                "",
                "| Entrypoint | Source | Facade | Exports |",
                "| --- | --- | --- | ---: |",
                *(
                    f"| `{entrypoint.module}` | `{entrypoint.source_file}` | "
                    f"`{entrypoint.facade_mode_observed}` | {_export_count_display(entrypoint.export_count, entrypoint.known_export_count)} |"
                    for entrypoint in item.entrypoints
                ),
            ]
        )
        for entrypoint in item.entrypoints:
            lines.extend(
                [
                    "",
                    f"#### `{entrypoint.module}`",
                    "",
                    f"- Source: `{entrypoint.source_file}`",
                    f"- Facade: `{entrypoint.facade_mode_observed}`",
                ]
            )
            if entrypoint.summary:
                lines.append(f"- Summary: {entrypoint.summary}")
            if entrypoint.export_count is None:
                lines.append(f"- Export resolution incomplete: {entrypoint.export_resolution['reason']}.")
            if entrypoint.known_export_count:
                label = (
                    f"Known literal prefix ({entrypoint.known_export_count}; total unknown)"
                    if entrypoint.export_count is None else f"Entrypoint exports ({entrypoint.export_count})"
                )
                lines.extend(
                    [
                        "",
                        f"<details><summary>{label}</summary>",
                        "",
                        "```text",
                        *entrypoint.exports,
                        "```",
                        "",
                        "</details>",
                    ]
                )
        if item.known_export_count:
            label = (
                f"Known literal prefix ({item.known_export_count}; total unknown)"
                if item.export_count is None else f"Supported exports ({item.export_count})"
            )
            lines.extend(
                [
                    "",
                    f"<details><summary>{label}</summary>",
                    "",
                    "```text",
                    *item.exports,
                    "```",
                    "",
                    "</details>",
                ]
            )
        elif item.export_count is None:
            lines.append("Export total is unknown; the static reader cannot resolve the extension.")
        else:
            lines.extend(
                [
                    "",
                    "This package does not expose a package-level `__all__` facade. Treat the module root itself as the only documented entrypoint.",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def render_deep_import_baseline_json(edges: list[DeepImportEdge]) -> str:
    payload = {
        "version": 1,
        "rule": "Cross-package imports should prefer documented supported entrypoints. This baseline freezes existing deep-import edges so new creep fails review.",
        "edges": [
            {
                "source_module": edge.source_module,
                "source_root": edge.source_root,
                "source_file": edge.source_file,
                "target_module": edge.target_module,
                "target_root": edge.target_root,
            }
            for edge in edges
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def render_generated_artifacts_markdown(families: list[GeneratedArtifactFamily]) -> str:
    lines = [
        "# Generated Artifacts",
        "",
        "> Generated from `architecture/generated_artifacts.toml`.",
        "> Regenerate this page with `uv run polisyos-tools architecture guardrails sync`.",
        "> Validate drift with `uv run polisyos-tools architecture guardrails check`.",
        "",
        "Every committed generated artifact family must have a source of truth, a regeneration command, a freshness rule, and an approval owner.",
        "",
        "| Family | Lifecycle | Commit policy | Drift gate | Owner | Outputs |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for family in families:
        outputs = "<br/>".join(f"`{_repo_display_path(path)}`" for path in family.outputs)
        lines.append(
            f"| `{family.label}` | `{family.lifecycle}` | `{family.commit_policy}` | `{family.drift_gate}` | `{family.owner}` | {outputs} |"
        )

    for family in families:
        lines.extend(
            [
                "",
                f"## `{family.label}`",
                "",
                f"- Family id: `{family.family_id}`",
                f"- Lifecycle: `{family.lifecycle}`",
                f"- Source of truth: {family.source_of_truth}",
                f"- Generator: {family.generator}",
                f"- Verifier: {family.verifier}",
                f"- Promotion target: {family.promotion_target}",
                f"- Commit policy: `{family.commit_policy}`",
                f"- Freshness rule: {family.freshness_rule}",
                f"- Stale output behavior: `{family.stale_output_behavior}`",
                f"- Drift gate: `{family.drift_gate}`",
                f"- Owner: `{family.owner}`",
                f"- Approval owner: `{family.approval_owner}`",
            ]
        )
        if family.retention_days is not None:
            lines.append(f"- Retention: `{family.retention_days}` days")
        if family.workflow is not None:
            lines.append(f"- Related workflow/config: `{_repo_display_path(family.workflow)}`")
        if family.default_freshness_check:
            lines.append("- Required in default freshness check: `true`")
        if family.output_probe_command is not None:
            lines.append(
                "- Generator-observed output probe: `"
                + shlex.join(family.output_probe_command)
                + "`"
            )
        lines.extend(
            [
                "- Outputs:",
                *[f"  - `{_repo_display_path(output)}`" for output in family.outputs],
                "",
                "Canonical regeneration commands:",
                "",
                "```bash",
                *family.regenerate_commands,
                "```",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _repo_display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path, REPO_ROOT)


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def _diff(label: str, expected: str, current: str) -> str:
    lines = difflib.unified_diff(
        current.splitlines(),
        expected.splitlines(),
        fromfile=f"{label} (current)",
        tofile=f"{label} (expected)",
        lineterm="",
    )
    return "\n".join(lines)


def _readme_gate_subjects(inventory: list[PackageInventory]) -> list[ReadmeGateSubject]:
    subjects: dict[tuple[str, str], ReadmeGateSubject] = {}
    for item in inventory:
        subjects[(item.module, item.readme)] = ReadmeGateSubject(
            module=item.module,
            readme=item.readme,
            major_subsystem=item.major_subsystem,
            reason=f"public_surface:{item.classification}",
        )

    if DEFAULT_MODULE_SIZE_BUDGET.exists():
        budget = _read_toml(DEFAULT_MODULE_SIZE_BUDGET)
        for item in budget.get("budget", []):
            path = Path(str(item.get("path", "")))
            if len(path.parts) < 3 or path.parts[:2] != ("src", "polisyos"):
                continue
            module = f"polisyos.{path.parts[2]}"
            readme = f"src/polisyos/{path.parts[2]}/README.md"
            key = (module, readme)
            existing = subjects.get(key)
            reason = "high_complexity"
            if existing is not None:
                reason = f"{existing.reason},high_complexity"
            subjects[key] = ReadmeGateSubject(
                module=module,
                readme=readme,
                major_subsystem=existing.major_subsystem if existing else False,
                reason=reason,
                detail=path.as_posix(),
            )

    return sorted(subjects.values(), key=lambda subject: (subject.readme, subject.module))


def _check_readmes(inventory: list[PackageInventory]) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for item in _readme_gate_subjects(inventory):
        readme_path = REPO_ROOT / item.readme
        if not readme_path.exists():
            violations.append(
                GuardrailViolation(
                    check="readme_policy",
                    subject=item.readme,
                    detail=item.reason,
                    message=(
                        f"Missing package README for {item.module}: {item.readme} "
                        f"({item.reason})"
                    ),
                )
            )
            continue
        text = readme_path.read_text(encoding="utf-8")
        if not any(pattern.search(text) for pattern in FRESHNESS_PATTERNS):
            violations.append(
                GuardrailViolation(
                    check="readme_policy",
                    subject=item.readme,
                    detail=f"freshness_marker:{item.reason}",
                    message=(
                        f"{item.readme} is missing a README freshness marker "
                        f"(`Last updated` / `Последнее обновление`) for {item.reason}."
                    ),
                )
            )
        if item.major_subsystem and not any(marker in text for marker in WHERE_TO_START_PATTERNS):
            violations.append(
                GuardrailViolation(
                    check="readme_policy",
                    subject=item.readme,
                    detail=f"where_to_start:{item.reason}",
                    message=f"{item.readme} must include a `Where to Start` section.",
                )
            )
    return violations


def _check_public_surface_contracts(inventory: list[PackageInventory]) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for item in inventory:
        for entrypoint in item.entrypoints:
            if entrypoint.export_count is None:
                violations.append(
                    GuardrailViolation(
                        check="public_surface",
                        subject=entrypoint.module,
                        detail="incomplete_exports",
                        message=(
                            f"{entrypoint.module} export total is unresolved: "
                            f"{entrypoint.export_resolution['reason']}."
                        ),
                    )
                )
        if item.export_count is not None and item.facade_mode_expected != item.facade_mode_observed:
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="facade_mode",
                    message=(
                        f"{item.module} facade drift: expected `{item.facade_mode_expected}`, "
                        f"observed `{item.facade_mode_observed}`."
                    ),
                )
            )
        if item.facade_mode_expected == "lazy_facade" and not item.has___getattr__:
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="lazy_facade_getattr",
                    message=f"{item.module} is expected to be lazy but has no `__getattr__` facade.",
                )
            )
        if item.facade_mode_expected in {"lazy_facade", "eager_exports"} and item.export_count == 0:
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="missing_exports",
                    message=f"{item.module} must expose a non-empty `__all__` surface.",
                )
            )
        if not (REPO_ROOT / item.reference_doc).exists():
            violations.append(
                GuardrailViolation(
                    check="public_surface",
                    subject=item.module,
                    detail="reference_doc",
                    message=f"Reference doc missing for {item.module}: {item.reference_doc}",
                )
            )
    return violations


def _check_generated_artifact_manifest(
    families: list[GeneratedArtifactFamily],
) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    seen_ids: set[str] = set()
    allowed_lifecycles = {
        "source_committed",
        "generated_committed",
        "generated_ignored",
        "runtime_ignored",
        "scratch_ignored",
    }
    allowed_stale_behaviors = {
        "fail",
        "warn",
        "cleanup_eligible",
        "ignored_by_policy",
        "block_release",
    }
    for family in families:
        if family.family_id in seen_ids:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="duplicate_family_id",
                    message=f"Duplicate generated artifact family id: {family.family_id}",
                )
            )
        seen_ids.add(family.family_id)
        for field, value in (
            ("lifecycle", family.lifecycle),
            ("generator", family.generator),
            ("verifier", family.verifier),
            ("promotion_target", family.promotion_target),
            ("stale_output_behavior", family.stale_output_behavior),
        ):
            if not value.strip():
                violations.append(
                    GuardrailViolation(
                        check="generated_artifact",
                        subject=family.family_id,
                        detail=f"missing_{field}",
                        message=f"{family.family_id} must declare `{field}`.",
                    )
                )
        if family.lifecycle and family.lifecycle not in allowed_lifecycles:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="invalid_lifecycle",
                    message=f"{family.family_id} has invalid lifecycle `{family.lifecycle}`.",
                )
            )
        if (
            family.stale_output_behavior
            and family.stale_output_behavior not in allowed_stale_behaviors
        ):
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="invalid_stale_output_behavior",
                    message=(
                        f"{family.family_id} has invalid stale_output_behavior "
                        f"`{family.stale_output_behavior}`."
                    ),
                )
            )
        if family.commit_policy == "local_ignored" and family.lifecycle == "generated_committed":
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="commit_policy_lifecycle_mismatch",
                    message=(
                        f"{family.family_id} cannot be local_ignored with "
                        "generated_committed lifecycle."
                    ),
                )
            )
        if family.commit_policy == "committed" and family.lifecycle in {
            "generated_ignored",
            "runtime_ignored",
            "scratch_ignored",
        }:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="commit_policy_lifecycle_mismatch",
                    message=(
                        f"{family.family_id} committed family must not use ignored lifecycle "
                        f"`{family.lifecycle}`."
                    ),
                )
            )
        if family.workflow is not None and not family.workflow.exists():
            violations.append(
                GuardrailViolation(
                    check="workflow_config",
                    subject=_repo_display_path(family.workflow),
                    detail=family.family_id,
                    message=(
                        f"Workflow/config drift: missing file {_repo_display_path(family.workflow)}"
                    ),
                )
            )
        if not family.regenerate_commands:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="missing_regeneration_command",
                    message=f"{family.family_id} must declare at least one regeneration command.",
                )
            )
        is_runtime_openapi_client = (
            family.source_of_truth == RUNTIME_OPENAPI_CLIENT_SOURCE
        )
        if is_runtime_openapi_client and not family.default_freshness_check:
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="missing_default_freshness_check",
                    message=(
                        f"{family.family_id} is derived from {RUNTIME_OPENAPI_CLIENT_SOURCE} "
                        "and cannot opt out of the default freshness check."
                    ),
                )
            )
        if _requires_default_generated_freshness(family):
            if family.stale_output_behavior != "fail":
                violations.append(
                    GuardrailViolation(
                        check="generated_artifact",
                        subject=family.family_id,
                        detail="default_freshness_check_requires_fail",
                        message=(
                            f"{family.family_id} is required in the default freshness check "
                            "and must declare stale_output_behavior = `fail`."
                        ),
                    )
                )
            if family.output_probe_command is None:
                violations.append(
                    GuardrailViolation(
                        check="generated_artifact",
                        subject=family.family_id,
                        detail="missing_output_probe_command",
                        message=(
                            f"{family.family_id} is required in the default freshness check "
                            "and must declare output_probe_command."
                        ),
                    )
                )
            elif sum(
                part.count("{output_root}") for part in family.output_probe_command
            ) != 1:
                violations.append(
                    GuardrailViolation(
                        check="generated_artifact",
                        subject=family.family_id,
                        detail="invalid_output_probe_command",
                        message=(
                            f"{family.family_id} output_probe_command must contain exactly one "
                            "`{output_root}` placeholder."
                        ),
                    )
                )
        if family.commit_policy == "committed":
            for output in family.outputs:
                if not output.exists():
                    violations.append(
                        GuardrailViolation(
                            check="generated_artifact",
                            subject=family.family_id,
                            detail=_repo_display_path(output),
                            message=(
                                f"{family.family_id} declares committed output "
                                f"{_repo_display_path(output)} but the path is missing."
                            ),
                        )
                    )
    return violations


def _run_declared_generated_artifact_checks(
    families: list[GeneratedArtifactFamily],
) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for family in families:
        if family.check_command is None:
            continue
        cwd = family.check_cwd or REPO_ROOT
        before_outputs: dict[Path, bytes | None] = {}
        for path in family.check_git_diff_paths:
            absolute = cwd / path
            before_outputs[path] = absolute.read_bytes() if absolute.exists() else None
        result = subprocess.run(
            list(family.check_command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            output = (result.stdout or "") + (result.stderr or "")
            violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail="automated_drift_check",
                    message=f"{family.family_id} automated drift check failed:\n{output.strip()}",
                )
            )
            continue
        if family.check_git_diff_paths:
            changed_paths: list[str] = []
            for path in family.check_git_diff_paths:
                absolute = cwd / path
                before = before_outputs.get(path)
                after = absolute.read_bytes() if absolute.exists() else None
                if before != after:
                    changed_paths.append(str(path))
            if changed_paths:
                violations.append(
                    GuardrailViolation(
                        check="generated_artifact",
                        subject=family.family_id,
                        detail="git_diff_drift",
                        message=(
                            f"{family.family_id} regeneration changed "
                            f"{', '.join(changed_paths)}. Re-run the canonical generation command and commit the refreshed outputs."
                        ),
                    )
                )
    return violations


def _relative_generated_output(output: Path) -> str | None:
    try:
        return output.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None


def _requires_default_generated_freshness(family: GeneratedArtifactFamily) -> bool:
    return (
        family.default_freshness_check
        or family.source_of_truth == RUNTIME_OPENAPI_CLIENT_SOURCE
    )


def _path_content_state(path: Path, *, admitted_root: Path | None = None) -> str:
    if path.is_symlink():
        return f"symlink:{os.readlink(path)}"
    if admitted_root is not None:
        if not admitted_is_file(path, admitted_root):
            return "missing" if not path.exists() else "non-file"
        mode, hexdigest = admitted_file_digest(path, admitted_root)
        return f"file:{mode:o}:{hexdigest}"
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "non-file"
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    mode = path.stat().st_mode & 0o777
    return f"file:{mode:o}:{digest.hexdigest()}"


def _snapshot_git_visible_worktree(repo_root: Path) -> dict[str, str]:
    git_binary = shutil.which("git")
    if git_binary is None:
        return _snapshot_filesystem_tree(repo_root)
    top_level = subprocess.run(
        [git_binary, "-C", str(repo_root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if top_level.returncode == 0:
        worktree_root = Path(top_level.stdout.strip()).resolve()
        listed = subprocess.run(
            [
                git_binary,
                "-C",
                str(worktree_root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if listed.returncode == 0:
            return {
                relative: _path_content_state(
                    worktree_root / relative,
                    admitted_root=worktree_root,
                )
                for relative in listed.stdout.split("\0")
                if relative
            }

    return _snapshot_filesystem_tree(repo_root)


def _snapshot_filesystem_tree(repo_root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in repo_root.rglob("*"):
        if ".git" in path.parts:
            continue
        relative = path.relative_to(repo_root).as_posix()
        if path.is_symlink() or admitted_is_file(path, repo_root):
            snapshot[relative] = _path_content_state(path, admitted_root=repo_root)
    return snapshot


def _copy_isolated_probe_source(repo_root: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git",
        ".cache",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "_build",
        "_cache",
        "node_modules",
        "production_data",
    )
    shutil.copytree(repo_root, destination, symlinks=True, ignore=ignored)
    for relative in (
        Path("node_modules"),
        Path("packages/runtime-api-client/node_modules"),
        Path("apps/runtime-dashboard/node_modules"),
    ):
        source = repo_root / relative
        if not source.exists():
            continue
        linked = destination / relative
        linked.parent.mkdir(parents=True, exist_ok=True)
        linked.symlink_to(source, target_is_directory=True)


def _isolated_probe_environment(
    source_root: Path,
    *,
    uv_cache_dir: Path | None = None,
    offline: bool = False,
) -> dict[str, str]:
    """Bind probe imports, private environment, and selected cache to copied source."""
    private_environment = source_root.parent / "environment"
    cache_root = uv_cache_dir or source_root.parent / "uv-cache"
    environment = os.environ.copy()
    for name in (
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "PYTHONHOME",
        "UV_PROJECT_ENVIRONMENT",
        "UV_NO_SYNC",
        "UV_NO_CONFIG",
        "UV_CONFIG_FILE",
        "UV_ENV_FILE",
        "UV_ISOLATED",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "UV_FROZEN": "1",
            "UV_PROJECT": str(source_root),
            "UV_PROJECT_ENVIRONMENT": str(private_environment),
            "UV_CACHE_DIR": str(cache_root),
            "UV_WORKING_DIR": str(source_root),
            "UV_PYTHON": sys.executable,
            "UV_NO_ENV_FILE": "1",
            "PYTHONPATH": os.pathsep.join((str(source_root / "src"), str(source_root))),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PATH": os.pathsep.join(
                (str(private_environment / "bin"), environment.get("PATH", ""))
            ),
        }
    )
    if offline:
        environment["UV_OFFLINE"] = "1"
    return environment


def _create_retained_generated_freshness_workspace(workspace_root: Path) -> Path:
    """Create a new caller-owned run directory without reusing or removing any path."""
    requested_root = workspace_root.expanduser()
    if requested_root.exists() or requested_root.is_symlink():
        raise FileExistsError(
            f"Retained generated-freshness workspace already exists: {requested_root}"
        )
    retained_root = requested_root.resolve()
    if retained_root.exists() or retained_root.is_symlink():
        raise FileExistsError(
            f"Retained generated-freshness workspace resolves to an existing path: "
            f"{retained_root}"
        )

    repository_root = REPO_ROOT.resolve()
    if retained_root.is_relative_to(repository_root):
        raise ValueError(
            "Retained generated-freshness workspace must be outside the repository root."
        )
    production_data = REPO_ROOT / "production_data"
    if production_data.exists() and retained_root.is_relative_to(production_data.resolve()):
        raise ValueError(
            "Retained generated-freshness workspace must be outside production_data."
        )
    retained_root.mkdir(parents=True, exist_ok=False)
    print(f"Generated-artifact measurement workspace retained at {retained_root}.")
    return retained_root


@contextlib.contextmanager
def _generated_freshness_workspace(workspace_root: Path | None) -> Iterator[Path]:
    """Preserve the existing temporary default or yield a retained caller-owned workspace."""
    if workspace_root is None:
        with tempfile.TemporaryDirectory(prefix="polisyos_generated_freshness_") as name:
            yield Path(name)
        return
    try:
        retained_root = _create_retained_generated_freshness_workspace(workspace_root)
    except (OSError, ValueError) as error:
        raise _RetainedFreshnessWorkspaceError(str(error)) from error
    yield retained_root


def _verify_isolated_python_import_origins(
    source_root: Path,
    *,
    python_executable: Path,
    environment: dict[str, str],
) -> None:
    """Import the copied product/tool packages and reject canonical-checkout origins."""
    if not (source_root / "src/polisyos").is_dir() or not (source_root / "tools").is_dir():
        raise FileNotFoundError(
            "Copied source is missing the product or tools package required for import-origin "
            "preflight."
        )
    preflight = """\
import importlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
for name, allowed_root in (("polisyos", root / "src"), ("tools", root)):
    module = importlib.import_module(name)
    origins = []
    module_file = getattr(module, "__file__", None)
    if module_file is not None:
        origins.append(pathlib.Path(module_file).resolve())
    module_path = getattr(module, "__path__", ())
    origins.extend(pathlib.Path(item).resolve() for item in module_path)
    if not origins or any(not origin.is_relative_to(allowed_root) for origin in origins):
        rendered = ", ".join(str(origin) for origin in origins) or "<no origin>"
        raise SystemExit(f"canonical_source_origin: {name} imported from {rendered}")
"""
    subprocess.run(
        [str(python_executable), "-c", preflight, str(source_root)],
        cwd=source_root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )


def _prepare_isolated_probe_environment(source_root: Path, environment: dict[str, str]) -> None:
    """Provision a private interpreter before any family's output measurement."""
    private_environment = Path(environment["UV_PROJECT_ENVIRONMENT"])
    uv_binary = shutil.which("uv", path=environment["PATH"])
    if uv_binary is None:
        raise FileNotFoundError("uv is required to provision the locked probe environment")
    # uv preserves the managed interpreter's loader binding. Copying its binary
    # with EnvBuilder can detach macOS libpython before any check starts.
    subprocess.run(
        [uv_binary, "venv", "--python", sys.executable, str(private_environment)],
        cwd=source_root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    (source_root / ".venv").symlink_to(private_environment, target_is_directory=True)
    if (source_root / "pyproject.toml").is_file():
        subprocess.run(
            [uv_binary, "sync", "--frozen"],
            cwd=source_root,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )


def _changed_snapshot_paths(
    before: dict[str, str],
    after: dict[str, str],
) -> list[str]:
    return sorted(
        relative
        for relative in before.keys() | after.keys()
        if before.get(relative) != after.get(relative)
    )


def _expected_output_snapshot(
    families: list[GeneratedArtifactFamily],
    *,
    expected_root: Path,
) -> dict[str, bytes | None]:
    relative_outputs = {
        relative
        for family in families
        for output in family.outputs
        if (relative := _relative_generated_output(output)) is not None
    }
    return {
        relative: (
            (expected_root / relative).read_bytes()
            if (expected_root / relative).is_file()
            else None
        )
        for relative in relative_outputs
    }


def _summarize_changed_paths(paths: list[str], *, limit: int = 12) -> str:
    displayed = paths[:limit]
    suffix = f" (+{len(paths) - limit} more)" if len(paths) > limit else ""
    return ", ".join(displayed) + suffix


@dataclass
class _GeneratedArtifactMeasurementCursor:
    """Track completed, active, and pending freshness work for one gate run."""

    required_families: tuple[GeneratedArtifactFamily, ...]
    violations: list[GuardrailViolation]
    unrun_checks: list[UnrunGeneratedCheck]
    _state: tuple[int, int | None, str | None, str] = (0, None, None, "selection")

    @property
    def completed_index(self) -> int:
        """Return the first required-family index not recorded as completed."""
        return self._state[0]

    @property
    def active_family_index(self) -> int | None:
        """Return the active family index, if a family phase has begun."""
        return self._state[1]

    @property
    def active_phase(self) -> str | None:
        """Return the current active family phase, when present."""
        return self._state[2]

    @property
    def run_phase(self) -> str:
        """Return the gate-wide phase around family work."""
        return self._state[3]

    @run_phase.setter
    def run_phase(self, phase: str) -> None:
        self._state = (
            self.completed_index,
            self.active_family_index,
            self.active_phase,
            phase,
        )

    def begin_family(self, family_index: int) -> None:
        if family_index != self.completed_index:
            raise AssertionError("generated-family cursor advanced out of order")
        self._state = (family_index, family_index, "family_setup", "dispatch")

    def set_active_phase(self, phase: str) -> None:
        self._state = (
            self.completed_index,
            self.active_family_index,
            phase,
            self.run_phase,
        )

    def complete_family(self, family_index: int) -> None:
        if self.active_family_index != family_index:
            raise AssertionError("generated-family cursor completed a non-active family")
        self._state = (family_index + 1, None, None, "dispatch")


def _finalize_interrupted_generated_artifact_measurement(
    cursor: _GeneratedArtifactMeasurementCursor,
) -> GeneratedArtifactCheckUnrunError:
    """Return one UNRUN verdict while preserving completed findings and cursors."""
    unrun_checks = list(cursor.unrun_checks)
    required_families = cursor.required_families

    if cursor.active_family_index is not None:
        active_index = cursor.active_family_index
        active = required_families[active_index]
        phase = cursor.active_phase or "measurement"
        unrun_checks.append(
            UnrunGeneratedCheck(
                active.family_id,
                phase,
                f"KeyboardInterrupt: interrupted during {phase}.",
            )
        )
        for pending in required_families[max(cursor.completed_index, active_index + 1) :]:
            unrun_checks.append(
                UnrunGeneratedCheck(
                    pending.family_id,
                    "not_started",
                    f"Not started after interruption in {active.family_id} during {phase}.",
                )
            )
    elif cursor.completed_index < len(required_families):
        pending_families = required_families[cursor.completed_index :]
        if cursor.run_phase == "dispatch" and cursor.completed_index > 0:
            previous = required_families[cursor.completed_index - 1]
            unrun_checks.extend(
                UnrunGeneratedCheck(
                    pending.family_id,
                    "not_started",
                    f"Not started after {previous.family_id} completed.",
                )
                for pending in pending_families
            )
        else:
            phase = cursor.run_phase if cursor.run_phase != "selection" else "measurement"
            unrun_checks.extend(
                UnrunGeneratedCheck(
                    pending.family_id,
                    phase,
                    f"KeyboardInterrupt before this family began; run phase was {phase}.",
                )
                for pending in pending_families
            )
    else:
        phase = cursor.run_phase
        if phase not in {"scratch_cleanup", "aggregate_verdict"}:
            phase = "measurement"
        unrun_checks.append(
            UnrunGeneratedCheck(
                "required_freshness_measurement",
                phase,
                "KeyboardInterrupt after all required family attempts completed; "
                "the overall measurement verdict could not be finalized.",
            )
        )

    return GeneratedArtifactCheckUnrunError(unrun_checks, cursor.violations)


def _measure_required_generated_artifact_family(
    family: GeneratedArtifactFamily,
    *,
    family_index: int,
    cursor: _GeneratedArtifactMeasurementCursor,
    family_scratch_root: Path,
    isolated_repo_root: Path,
    environment: dict[str, str],
    expected_root: Path,
    expected_outputs: dict[str, bytes | None],
    declared_owners: dict[str, list[str]],
) -> None:
    """Measure one family and advance the run-wide cursor after its attempt."""
    cursor.begin_family(family_index)
    family_violation_start = len(cursor.violations)
    probe_command = family.output_probe_command
    if probe_command is None:
        cursor.unrun_checks.append(
            UnrunGeneratedCheck(
                family.family_id, "generator", "No generator-observed output probe."
            )
        )
        cursor.complete_family(family_index)
        return

    rendered_command = [
        part.replace("{output_root}", str(family_scratch_root)) for part in probe_command
    ]
    cursor.set_active_phase("worktree_snapshot_before")
    worktree_before = _snapshot_git_visible_worktree(REPO_ROOT)
    cursor.set_active_phase("isolated_snapshot_before")
    isolated_before = _snapshot_filesystem_tree(isolated_repo_root)
    cursor.set_active_phase("generator")
    try:
        result = subprocess.run(
            rendered_command,
            cwd=isolated_repo_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        cursor.unrun_checks.append(
            UnrunGeneratedCheck(family.family_id, "generator", str(error))
        )
        cursor.complete_family(family_index)
        return

    cursor.set_active_phase("worktree_snapshot_after")
    worktree_after = _snapshot_git_visible_worktree(REPO_ROOT)
    cursor.set_active_phase("isolated_snapshot_after")
    isolated_after = _snapshot_filesystem_tree(isolated_repo_root)
    escaped_paths = _changed_snapshot_paths(worktree_before, worktree_after)
    escaped_paths.extend(
        f"isolated-source/{relative}"
        for relative in _changed_snapshot_paths(isolated_before, isolated_after)
    )
    cursor.set_active_phase("oracle_snapshot")
    for relative, frozen_bytes in expected_outputs.items():
        current = expected_root / relative
        current_bytes = current.read_bytes() if current.is_file() else None
        if current_bytes != frozen_bytes:
            escaped_paths.append(current.as_posix())
    escaped_paths = sorted(set(escaped_paths))
    if escaped_paths:
        cursor.violations.append(
            GuardrailViolation(
                check="generated_artifact",
                subject=family.family_id,
                detail="output_probe_worktree_escape",
                message=(
                    f"{family.family_id} output probe changed paths outside its assigned "
                    f"scratch root: {_summarize_changed_paths(escaped_paths)}."
                ),
            )
        )
    if result.returncode != 0:
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        cursor.unrun_checks.append(
            UnrunGeneratedCheck(
                family.family_id, "generator", f"exit={result.returncode}\n{output}"
            )
        )
        cursor.complete_family(family_index)
        return

    cursor.set_active_phase("output_census")
    observed_outputs = {
        candidate.relative_to(family_scratch_root).as_posix()
        for candidate in family_scratch_root.rglob("*")
        if candidate.is_file()
    }
    declared_outputs = {
        relative
        for output in family.outputs
        if (relative := _relative_generated_output(output)) is not None
    }

    cursor.set_active_phase("output_comparison")
    for relative in sorted(observed_outputs):
        owners = sorted(declared_owners.get(relative, []))
        if not owners:
            cursor.violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail=relative,
                    message=(
                        f"{family.family_id} emitted {relative} but it is not registered "
                        "under any generated-artifact family."
                    ),
                )
            )
            continue
        if len(owners) > 1:
            cursor.violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail=relative,
                    message=(
                        f"{family.family_id} emitted {relative}, but it is registered by "
                        f"multiple families: {', '.join(owners)}."
                    ),
                )
            )
            continue
        if owners[0] != family.family_id:
            cursor.violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail=relative,
                    message=(
                        f"{family.family_id} emitted {relative}, but it is registered to "
                        f"{owners[0]}."
                    ),
                )
            )
            continue

        candidate = family_scratch_root / relative
        expected = expected_root / relative
        frozen_expected = expected_outputs.get(relative)
        if frozen_expected is None:
            cursor.violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail=relative,
                    message=(
                        f"{family.family_id} expected output is missing: "
                        f"{expected.as_posix()}."
                    ),
                )
            )
        elif candidate.read_bytes() != frozen_expected:
            cursor.violations.append(
                GuardrailViolation(
                    check="generated_artifact",
                    subject=family.family_id,
                    detail=relative,
                    message=(
                        f"{family.family_id} generated output {relative} does not match "
                        f"{expected.as_posix()}."
                    ),
                )
            )

    for relative in sorted(declared_outputs - observed_outputs):
        cursor.violations.append(
            GuardrailViolation(
                check="generated_artifact",
                subject=family.family_id,
                detail=relative,
                message=(
                    f"{family.family_id} declares {relative}, but its generator did not "
                    "emit that output."
                ),
            )
        )

    if len(cursor.violations) == family_violation_start:
        cursor.set_active_phase("verdict_receipt")
        print(
            "Generated artifact freshness clean: "
            f"{family.family_id} ({len(observed_outputs)} generator-observed outputs)."
        )
    cursor.complete_family(family_index)


def _run_required_generated_artifact_checks(
    families: list[GeneratedArtifactFamily],
    *,
    expected_root: Path,
    retained_workspace_root: Path | None = None,
    uv_cache_dir: Path | None = None,
) -> list[GuardrailViolation]:
    required_families = tuple(
        family for family in families if _requires_default_generated_freshness(family)
    )
    cursor = _GeneratedArtifactMeasurementCursor(
        required_families=required_families,
        violations=[],
        unrun_checks=[],
    )
    try:
        return _measure_required_generated_artifacts(
            families,
            expected_root=expected_root,
            cursor=cursor,
            retained_workspace_root=retained_workspace_root,
            uv_cache_dir=uv_cache_dir,
        )
    except GeneratedArtifactCheckUnrunError:
        raise
    except KeyboardInterrupt as error:
        raise _finalize_interrupted_generated_artifact_measurement(cursor) from error
    except Exception as error:
        # An unexpected measurement failure is unavailable execution, never an artifact
        # finding. Keep accumulated facts and mark only work that did not finish.
        cursor.unrun_checks.append(
            UnrunGeneratedCheck(
                "required_freshness_measurement",
                "measurement",
                f"{type(error).__name__}: {error}",
            )
        )
        raise GeneratedArtifactCheckUnrunError(
            cursor.unrun_checks,
            cursor.violations,
        ) from error


def _measure_required_generated_artifacts_in_workspace(
    *,
    scratch_root: Path,
    required_families: tuple[GeneratedArtifactFamily, ...],
    cursor: _GeneratedArtifactMeasurementCursor,
    expected_root: Path,
    expected_outputs: dict[str, bytes | None],
    declared_owners: dict[str, list[str]],
    uv_cache_dir: Path | None,
    offline: bool,
) -> None:
    isolated_repo_root = scratch_root / "source"
    output_root = scratch_root / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        _copy_isolated_probe_source(REPO_ROOT, isolated_repo_root)
        environment = _isolated_probe_environment(
            isolated_repo_root,
            uv_cache_dir=uv_cache_dir,
            offline=offline,
        )
        _prepare_isolated_probe_environment(isolated_repo_root, environment)
        if (REPO_ROOT / "src/polisyos").is_dir():
            _verify_isolated_python_import_origins(
                isolated_repo_root,
                python_executable=Path(environment["UV_PROJECT_ENVIRONMENT"])
                / "bin/python",
                environment=environment,
            )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = (
            ((error.stdout or "") + (error.stderr or "")).strip()
            if isinstance(error, subprocess.CalledProcessError)
            else str(error)
        )
        cursor.unrun_checks.extend(
            UnrunGeneratedCheck(family.family_id, "environment", detail)
            for family in required_families
        )
        raise GeneratedArtifactCheckUnrunError(
            cursor.unrun_checks,
            cursor.violations,
        ) from error

    for family_index, family in enumerate(required_families):
        _measure_required_generated_artifact_family(
            family,
            family_index=family_index,
            cursor=cursor,
            family_scratch_root=output_root / family.family_id,
            isolated_repo_root=isolated_repo_root,
            environment=environment,
            expected_root=expected_root,
            expected_outputs=expected_outputs,
            declared_owners=declared_owners,
        )


def _measure_required_generated_artifacts(
    families: list[GeneratedArtifactFamily],
    *,
    expected_root: Path,
    cursor: _GeneratedArtifactMeasurementCursor,
    retained_workspace_root: Path | None,
    uv_cache_dir: Path | None,
) -> list[GuardrailViolation]:
    required_families = cursor.required_families
    if not required_families:
        return []
    declared_owners: dict[str, list[str]] = {}
    for family in families:
        for output in family.outputs:
            relative = _relative_generated_output(output)
            if relative is None:
                continue
            declared_owners.setdefault(relative, []).append(family.family_id)
    cursor.run_phase = "expected_output_snapshot"
    expected_outputs = _expected_output_snapshot(
        required_families,
        expected_root=expected_root,
    )

    cursor.run_phase = "environment"
    try:
        if (retained_workspace_root is None) != (uv_cache_dir is None):
            raise ValueError(
                "Retained generated-freshness workspace and uv cache must be supplied together."
            )
        resolved_cache_dir: Path | None = None
        if uv_cache_dir is not None:
            resolved_cache_dir = uv_cache_dir.expanduser().resolve()
            if not resolved_cache_dir.is_dir():
                raise NotADirectoryError(
                    f"Existing uv cache directory is required: {resolved_cache_dir}"
                )
            if resolved_cache_dir.is_relative_to(REPO_ROOT.resolve()):
                raise ValueError("The uv cache used by this gate must be outside the repository.")
            production_data = REPO_ROOT / "production_data"
            if (
                production_data.exists()
                and resolved_cache_dir.is_relative_to(production_data.resolve())
            ):
                raise ValueError("The uv cache must be outside production_data.")
        resolved_workspace_root = (
            retained_workspace_root.expanduser().resolve()
            if retained_workspace_root is not None
            else None
        )
        if resolved_workspace_root is not None and resolved_cache_dir is not None:
            if (
                resolved_workspace_root.is_relative_to(resolved_cache_dir)
                or resolved_cache_dir.is_relative_to(resolved_workspace_root)
            ):
                raise ValueError(
                    "Retained workspace and existing uv cache must be separate paths."
                )
    except (OSError, ValueError) as error:
        detail = str(error)
        cursor.unrun_checks.extend(
            UnrunGeneratedCheck(family.family_id, "environment", detail)
            for family in required_families
        )
        raise GeneratedArtifactCheckUnrunError(
            cursor.unrun_checks,
            cursor.violations,
        ) from error

    try:
        with _generated_freshness_workspace(retained_workspace_root) as scratch_root:
            _measure_required_generated_artifacts_in_workspace(
                scratch_root=scratch_root,
                required_families=required_families,
                cursor=cursor,
                expected_root=expected_root,
                expected_outputs=expected_outputs,
                declared_owners=declared_owners,
                uv_cache_dir=resolved_cache_dir,
                offline=retained_workspace_root is not None,
            )
            cursor.run_phase = (
                "scratch_cleanup"
                if retained_workspace_root is None
                else "aggregate_verdict"
            )
    except _RetainedFreshnessWorkspaceError as error:
        cursor.unrun_checks.extend(
            UnrunGeneratedCheck(family.family_id, "environment", str(error))
            for family in required_families
        )
        raise GeneratedArtifactCheckUnrunError(
            cursor.unrun_checks,
            cursor.violations,
        ) from error

    cursor.run_phase = "aggregate_verdict"
    if cursor.unrun_checks:
        raise GeneratedArtifactCheckUnrunError(cursor.unrun_checks, cursor.violations)
    return cursor.violations


def _check_workflow_toolchain_guardrails() -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    workflow_paths = sorted(
        set(WORKFLOW_BASELINE_REQUIREMENTS)
        | set(WORKFLOW_RUN_REQUIREMENTS)
        | set(WORKFLOW_BASELINE_FORBIDDEN)
    )
    for workflow_rel in workflow_paths:
        workflow_path = REPO_ROOT / workflow_rel
        if not workflow_path.exists():
            violations.append(
                GuardrailViolation(
                    check="workflow_config",
                    subject=workflow_rel,
                    detail="missing_workflow",
                    message=f"Workflow/config drift: missing file {workflow_rel}",
                )
            )
            continue
        text = workflow_path.read_text(encoding="utf-8")
        for detail, snippet, message in WORKFLOW_BASELINE_REQUIREMENTS.get(
            workflow_rel, ()
        ):
            if snippet not in text:
                violations.append(
                    GuardrailViolation(
                        check="workflow_config",
                        subject=workflow_rel,
                        detail=detail,
                        message=f"{message} Expected snippet: `{snippet}`",
                    )
                )
        run_requirements = WORKFLOW_RUN_REQUIREMENTS.get(workflow_rel, ())
        if run_requirements:
            try:
                payload = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                violations.append(
                    GuardrailViolation(
                        check="workflow_config",
                        subject=workflow_rel,
                        detail="invalid_yaml",
                        message=f"Workflow/config YAML is invalid: {exc}",
                    )
                )
                payload = None
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            for detail, job_id, command, message in run_requirements:
                job = jobs.get(job_id) if isinstance(jobs, dict) else None
                job_gates = (
                    isinstance(job, dict)
                    and "if" not in job
                    and job.get("continue-on-error", False) is False
                )
                steps = job.get("steps", ()) if isinstance(job, dict) else ()
                command_gates = any(
                    isinstance(step, dict)
                    and step.get("run") == command
                    and "if" not in step
                    and step.get("continue-on-error", False) is False
                    for step in steps
                )
                if not job_gates or not command_gates:
                    violations.append(
                        GuardrailViolation(
                            check="workflow_config",
                            subject=workflow_rel,
                            detail=detail,
                            message=(
                                f"{message} Expected unconditional gating run command in job "
                                f"`{job_id}`: `{command}`"
                            ),
                        )
                    )
        for detail, snippet, message in WORKFLOW_BASELINE_FORBIDDEN.get(
            workflow_rel, ()
        ):
            if snippet in text:
                violations.append(
                    GuardrailViolation(
                        check="workflow_config",
                        subject=workflow_rel,
                        detail=detail,
                        message=f"{message} Found forbidden snippet: `{snippet}`",
                    )
                )
    return violations


def _validate_guardrail_exceptions(
    exceptions_path: Path,
    registry_path: Path,
    *,
    max_expiry_days: int,
) -> list[str]:
    violations: list[str] = []
    try:
        registry_label = str(registry_path.relative_to(REPO_ROOT))
    except ValueError:
        registry_label = str(registry_path)
    try:
        exceptions_label = str(exceptions_path.relative_to(REPO_ROOT))
    except ValueError:
        exceptions_label = str(exceptions_path)
    if not exceptions_path.exists():
        violations.append(f"Guardrail exceptions file not found: {exceptions_label}")
        return violations
    registry_ids = _parse_registry_ids(registry_path)
    today = dt.date.today()
    max_expiry = today + dt.timedelta(days=max_expiry_days)
    seen_ids: set[str] = set()
    for exception in _parse_guardrail_exceptions(exceptions_path):
        if exception.exception_id in seen_ids:
            violations.append(f"Duplicate guardrail exception id: {exception.exception_id}")
        seen_ids.add(exception.exception_id)
        if exception.expires < today:
            violations.append(f"Guardrail exception `{exception.exception_id}` is expired.")
        if exception.expires > max_expiry:
            violations.append(
                f"Guardrail exception `{exception.exception_id}` exceeds {max_expiry_days}-day max expiry window."
            )
        if exception.exception_id not in registry_ids:
            violations.append(
                f"Guardrail exception `{exception.exception_id}` is missing from {registry_label}."
            )
    return violations


def _load_deep_import_baseline(path: Path) -> dict[str, DeepImportEdge]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results: dict[str, DeepImportEdge] = {}
    for item in payload.get("edges", []):
        edge = DeepImportEdge(
            source_module=str(item["source_module"]),
            source_root=str(item["source_root"]),
            source_file=str(item["source_file"]),
            target_module=str(item["target_module"]),
            target_root=str(item["target_root"]),
        )
        results[edge.key] = edge
    return results


def _exception_matches_violation(
    exception: GuardrailException,
    violation: GuardrailViolation,
) -> bool:
    if exception.check != violation.check:
        return False
    if violation.check == "deep_import":
        return fnmatch.fnmatch(
            violation.source_module, exception.source_module_glob
        ) and fnmatch.fnmatch(violation.target_module, exception.target_module_glob)
    return fnmatch.fnmatch(violation.subject, exception.subject_glob) and fnmatch.fnmatch(
        violation.detail or "", exception.detail_glob
    )


def _apply_guardrail_exceptions(
    violations: list[GuardrailViolation],
    exceptions: list[GuardrailException],
) -> list[str]:
    emitted: list[str] = []
    for violation in violations:
        if any(_exception_matches_violation(exception, violation) for exception in exceptions):
            continue
        emitted.append(violation.message)
    return emitted


def _check_deep_import_creep(
    *,
    baseline_path: Path,
    current_edges: list[DeepImportEdge],
) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    if not baseline_path.exists():
        return [
            GuardrailViolation(
                check="deep_import",
                subject=str(baseline_path.relative_to(REPO_ROOT)),
                detail="missing_baseline",
                message=f"Deep-import baseline file not found: {baseline_path.relative_to(REPO_ROOT)}",
            )
        ]
    baseline_edges = _load_deep_import_baseline(baseline_path)
    current_by_key = {edge.key: edge for edge in current_edges}

    for key, edge in sorted(current_by_key.items()):
        if key in baseline_edges:
            continue
        violations.append(
            GuardrailViolation(
                check="deep_import",
                subject=edge.source_module,
                detail=edge.target_module,
                source_module=edge.source_module,
                target_module=edge.target_module,
                message=(
                    "New deep-import creep detected: "
                    f"{edge.source_module} -> {edge.target_module} "
                    f"({edge.source_file}). Add a stable facade, update the baseline intentionally, "
                    "or register a temporary exception."
                ),
            )
        )
    return violations


def run_sync(args: argparse.Namespace) -> int:
    public_policies = _parse_public_surface(args.public_manifest)
    public_generated_families = _parse_public_generated_artifact_families(args.public_manifest)
    public_inventory = build_public_surface_inventory(public_policies)
    families = _parse_generated_artifacts(args.generated_manifest)
    deep_import_edges = collect_deep_import_edges(public_policies)

    _write_if_changed(
        args.public_json,
        render_public_surface_json(
            public_inventory,
            generated_artifact_families=public_generated_families,
        ),
    )
    _write_if_changed(args.public_md, render_public_surface_markdown(public_inventory))
    if not args.skip_deep_import_baseline:
        _write_if_changed(
            args.deep_import_baseline,
            render_deep_import_baseline_json(deep_import_edges),
        )
    _write_if_changed(args.generated_md, render_generated_artifacts_markdown(families))
    print("Architecture guardrail inventories updated.")
    return 0


def run_check(args: argparse.Namespace) -> int:
    violations: list[str] = []
    unrun_checks: tuple[UnrunGeneratedCheck, ...] = ()

    public_policies = _parse_public_surface(args.public_manifest)
    public_generated_families = _parse_public_generated_artifact_families(args.public_manifest)
    public_inventory = build_public_surface_inventory(public_policies)
    expected_public_json = render_public_surface_json(
        public_inventory,
        generated_artifact_families=public_generated_families,
    )
    expected_public_md = render_public_surface_markdown(public_inventory)
    expected_deep_import_baseline = render_deep_import_baseline_json(
        collect_deep_import_edges(public_policies)
    )
    families = _parse_generated_artifacts(args.generated_manifest)
    expected_generated_md = render_generated_artifacts_markdown(families)
    guardrail_exceptions = _parse_guardrail_exceptions(args.exceptions)

    if not args.public_json.exists():
        violations.append(
            f"Missing public surface inventory JSON: {args.public_json.relative_to(REPO_ROOT)}"
        )
    elif args.public_json.read_text(encoding="utf-8") != expected_public_json:
        violations.append(
            "Public surface inventory JSON drift detected.\n"
            + _diff(
                str(args.public_json.relative_to(REPO_ROOT)),
                expected_public_json,
                args.public_json.read_text(encoding="utf-8"),
            )
        )

    if not args.public_md.exists():
        violations.append(
            f"Missing public surface reference doc: {args.public_md.relative_to(REPO_ROOT)}"
        )
    elif args.public_md.read_text(encoding="utf-8") != expected_public_md:
        violations.append(
            "Public surface reference doc drift detected.\n"
            + _diff(
                str(args.public_md.relative_to(REPO_ROOT)),
                expected_public_md,
                args.public_md.read_text(encoding="utf-8"),
            )
        )

    if not args.generated_md.exists():
        violations.append(
            f"Missing generated-artifacts reference doc: {args.generated_md.relative_to(REPO_ROOT)}"
        )
    elif args.generated_md.read_text(encoding="utf-8") != expected_generated_md:
        violations.append(
            "Generated-artifacts reference doc drift detected.\n"
            + _diff(
                str(args.generated_md.relative_to(REPO_ROOT)),
                expected_generated_md,
                args.generated_md.read_text(encoding="utf-8"),
            )
        )

    if not args.deep_import_baseline.exists():
        violations.append(
            f"Missing deep-import baseline: {args.deep_import_baseline.relative_to(REPO_ROOT)}"
        )
    elif args.deep_import_baseline.read_text(encoding="utf-8") != expected_deep_import_baseline:
        violations.append(
            "Deep-import baseline drift detected. Re-run "
            "`uv run polisyos-tools architecture guardrails sync` only when intentionally "
            "accepting the new baseline.\n"
            + _diff(
                str(args.deep_import_baseline.relative_to(REPO_ROOT)),
                expected_deep_import_baseline,
                args.deep_import_baseline.read_text(encoding="utf-8"),
            )
        )

    violations.extend(
        _apply_guardrail_exceptions(
            _check_public_surface_contracts(public_inventory),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_readmes(public_inventory),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _validate_guardrail_exceptions(
            args.exceptions, args.exceptions_registry, max_expiry_days=args.max_expiry_days
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_deep_import_creep(
                baseline_path=args.deep_import_baseline,
                current_edges=collect_deep_import_edges(public_policies),
            ),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_generated_artifact_manifest(families),
            guardrail_exceptions,
        )
    )
    violations.extend(
        _apply_guardrail_exceptions(
            _check_workflow_toolchain_guardrails(),
            guardrail_exceptions,
        )
    )

    if not args.skip_generated_checks:
        expected_root = args.generated_expected_root
        if not expected_root.is_absolute():
            expected_root = (Path.cwd() / expected_root).resolve()
        retained_workspace_root = args.generated_freshness_workspace_root
        if retained_workspace_root is not None and not retained_workspace_root.is_absolute():
            retained_workspace_root = (Path.cwd() / retained_workspace_root).resolve()
        uv_cache_dir = args.generated_freshness_uv_cache_dir
        if uv_cache_dir is not None and not uv_cache_dir.is_absolute():
            uv_cache_dir = (Path.cwd() / uv_cache_dir).resolve()
        try:
            generated_violations = _run_required_generated_artifact_checks(
                families,
                expected_root=expected_root,
                retained_workspace_root=retained_workspace_root,
                uv_cache_dir=uv_cache_dir,
            )
        except GeneratedArtifactCheckUnrunError as error:
            unrun_checks = error.unrun_checks
            generated_violations = list(error.violations)
        violations.extend(_apply_guardrail_exceptions(generated_violations, guardrail_exceptions))
    else:
        print(
            "SCOPE LIMITED: required generated-artifact freshness checks explicitly omitted "
            "(--skip-generated-checks); no freshness verdict."
        )
    if args.all_generated_checks:
        optional_families = [
            family for family in families if not _requires_default_generated_freshness(family)
        ]
        violations.extend(
            _apply_guardrail_exceptions(
                _run_declared_generated_artifact_checks(optional_families),
                guardrail_exceptions,
            )
        )

    print(STATUS_RETIREMENT_STANDALONE_NOTICE)
    if unrun_checks:
        print(
            "Architecture guardrail check UNRUN: required measurements unavailable; "
            "no complete verdict."
        )
        for item in unrun_checks:
            print(f"- UNRUN {item.family_id} [{item.phase}]: {item.diagnostic}")
        if violations:
            print("Completed artifact findings (partial coverage):")
            for violation in violations:
                print(f"- {violation}")
        return 2
    if violations:
        print("Architecture guardrail check FAILED:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print(
        "Architecture guardrail check passed (freshness explicitly omitted)."
        if args.skip_generated_checks
        else "Architecture guardrail check passed."
    )
    return 0


def main() -> int:
    args = _parse_args()
    if args.command == "sync":
        return run_sync(args)
    return run_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
