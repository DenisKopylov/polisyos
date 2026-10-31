#!/usr/bin/env python3
from __future__ import annotations
import __future__ as _future

import argparse
import ast
import builtins
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
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterator, Sequence
from dataclasses import MISSING, dataclass
from dataclasses import field as dataclass_field
from dataclasses import fields as dataclass_fields
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, Protocol, get_args, get_origin, get_type_hints

import yaml

from polisyos.common.markdown import split_markdown_table_row
from tools.devx.architecture.conditional_exports import (
    SourceExportProfile,
    resolve_conditional_export_profiles,
)
from tools.lib.fs import (
    admitted_file_digest,
    admitted_is_dir,
    admitted_is_file,
    admitted_read_bytes,
    iter_repository_files,
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
DEFAULT_DEEP_IMPORT_BASELINE = (
    REPO_ROOT / "architecture" / "baselines" / "imports" / "deep_import.json"
)
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
    source_export_profiles: tuple[SourceExportProfile, ...] = ()


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
    resolution_status: Literal["source_resolved", "not_established"] = "source_resolved"
    resolution_reason: (
        Literal[
            "export_manifest_unresolved",
            "name_not_declared_export",
            "bound_but_unlisted",
            "declared_binding_unproven",
        ]
        | None
    ) = None

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
    family_id: str = dataclass_field(
        metadata={"toml_name": "id", "toml_required": True, "toml_nonblank": True}
    )
    label: str
    owner: str = dataclass_field(metadata={"toml_required": True, "toml_nonblank": True})
    approval_owner: str
    lifecycle: str = dataclass_field(
        metadata={
            "toml_required": True,
            "toml_nonblank": True,
            "toml_enum": (
                "source_committed",
                "generated_committed",
                "generated_ignored",
                "runtime_ignored",
                "scratch_ignored",
            ),
        }
    )
    generator: str = dataclass_field(metadata={"toml_required": True, "toml_nonblank": True})
    verifier: str = dataclass_field(metadata={"toml_required": True, "toml_nonblank": True})
    promotion_target: str = dataclass_field(metadata={"toml_required": True, "toml_nonblank": True})
    stale_output_behavior: str = dataclass_field(
        metadata={
            "toml_required": True,
            "toml_nonblank": True,
            "toml_enum": ("fail", "warn", "cleanup_eligible", "ignored_by_policy", "block_release"),
        }
    )
    source_of_truth: str
    outputs: tuple[Path, ...] = dataclass_field(metadata={"toml_required": False})
    regenerate_commands: tuple[str, ...] = dataclass_field(metadata={"toml_required": False})
    commit_policy: str
    freshness_rule: str
    drift_gate: str
    workflow: Path | None = dataclass_field(metadata={"toml_required": False})
    check_cwd: Path | None = dataclass_field(metadata={"toml_required": False})
    check_command: tuple[str, ...] | None = dataclass_field(
        metadata={"toml_required": False, "toml_command": True}
    )
    check_git_diff_paths: tuple[Path, ...] = dataclass_field(metadata={"toml_required": False})
    default_freshness_check: bool = dataclass_field(metadata={"toml_required": False})
    output_probe_command: tuple[str, ...] | None = dataclass_field(
        metadata={"toml_required": False, "toml_command": True}
    )
    retention_days: int | None = dataclass_field(metadata={"toml_required": False})
    probe_input_roots: tuple[Path, ...] = ()
    probe_required_paths: tuple[Path, ...] = ()
    probe_runtime_paths: tuple[Path, ...] = ()


class _ProbeInputFamily(Protocol):
    """Structural contract shared by manifest rows and validated family bindings."""

    family_id: str
    output_probe_command: tuple[str, ...] | None
    probe_input_roots: tuple[Path, ...]
    probe_required_paths: tuple[Path, ...]
    probe_runtime_paths: tuple[Path, ...]


@dataclass(frozen=True)
class _GeneratedArtifactTomlField:
    raw_name: str
    attribute: str
    toml_type: str
    required: bool
    nonblank: bool
    enum_values: tuple[str, ...]


class GeneratedArtifactManifestSchemaError(ValueError):
    """Raised when a generated-artifact TOML row violates the typed source contract."""


def _generated_artifact_toml_schema() -> tuple[_GeneratedArtifactTomlField, ...]:
    """Derive raw TOML validation from the normalized row dataclass and its metadata."""
    hints = get_type_hints(GeneratedArtifactFamily)
    schema: list[_GeneratedArtifactTomlField] = []
    for declaration in dataclass_fields(GeneratedArtifactFamily):
        annotation = hints[declaration.name]
        metadata = declaration.metadata
        optional = type(None) in get_args(annotation)
        defaulted = declaration.default is not MISSING or declaration.default_factory is not MISSING
        required = bool(metadata.get("toml_required", not (optional or defaulted)))
        raw_name = str(metadata.get("toml_name", declaration.name))
        if metadata.get("toml_command"):
            toml_type = "string-or-array[string]"
        else:
            annotation_args = get_args(annotation)
            base = (
                next(arg for arg in annotation_args if arg is not type(None))
                if type(None) in annotation_args
                else annotation
            )
            origin = get_origin(base)
            if base in (str, Path):
                toml_type = "string"
            elif base is bool:
                toml_type = "boolean"
            elif base is int:
                toml_type = "integer"
            elif origin is tuple and get_args(base)[0] in (str, Path):
                toml_type = "array[string]"
            else:
                raise TypeError(f"Unsupported generated-artifact TOML schema type: {annotation!r}")
        schema.append(
            _GeneratedArtifactTomlField(
                raw_name=raw_name,
                attribute=declaration.name,
                toml_type=toml_type,
                required=required,
                nonblank=bool(metadata.get("toml_nonblank", False)),
                enum_values=tuple(metadata.get("toml_enum", ())),
            )
        )
    return tuple(schema)


def _generated_artifact_field_spec(attribute: str) -> _GeneratedArtifactTomlField:
    return next(item for item in _generated_artifact_toml_schema() if item.attribute == attribute)


def _toml_value_type_name(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "table"
    return type(value).__name__


def _toml_value_matches_schema(value: object, schema_field: _GeneratedArtifactTomlField) -> bool:
    if schema_field.toml_type == "string":
        return type(value) is str
    if schema_field.toml_type == "boolean":
        return type(value) is bool
    if schema_field.toml_type == "integer":
        return type(value) is int
    if schema_field.toml_type == "array[string]":
        return type(value) is list and all(type(item) is str for item in value)
    if schema_field.toml_type == "string-or-array[string]":
        return type(value) is str or (
            type(value) is list and all(type(item) is str for item in value)
        )
    raise AssertionError(f"Unsupported generated-artifact schema type: {schema_field.toml_type}")


def _validate_generated_artifact_toml_data(data: object) -> None:
    if not isinstance(data, dict):
        raise GeneratedArtifactManifestSchemaError("manifest root must be a TOML table")
    families = data.get("family", [])
    if type(families) is not list:
        raise GeneratedArtifactManifestSchemaError("family must be an array of TOML tables")
    schema = _generated_artifact_toml_schema()
    for row_index, family in enumerate(families):
        if type(family) is not dict:
            raise GeneratedArtifactManifestSchemaError(f"family[{row_index}] must be a TOML table")
        for field in schema:
            if field.raw_name not in family:
                if field.required:
                    raise GeneratedArtifactManifestSchemaError(
                        f"family[{row_index}].{field.raw_name} is required"
                    )
                continue
            value = family[field.raw_name]
            if not _toml_value_matches_schema(value, field):
                raise GeneratedArtifactManifestSchemaError(
                    f"family[{row_index}].{field.raw_name} expected {field.toml_type}; "
                    f"got {_toml_value_type_name(value)}"
                )
            if field.nonblank and not value.strip():
                raise GeneratedArtifactManifestSchemaError(
                    f"family[{row_index}].{field.raw_name} must be a non-empty string"
                )


def _generated_artifact_allowed_values(attribute: str) -> set[str]:
    return set(_generated_artifact_field_spec(attribute).enum_values)


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
    data = tomllib.loads(path.decode("utf-8")) if isinstance(path, bytes) else _read_toml(path)
    _validate_generated_artifact_toml_data(data)
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
                probe_input_roots=tuple(
                    _ensure_relative(str(value)) for value in item.get("probe_input_roots", [])
                ),
                probe_required_paths=tuple(
                    _ensure_relative(str(value)) for value in item.get("probe_required_paths", [])
                ),
                probe_runtime_paths=tuple(
                    _ensure_relative(str(value)) for value in item.get("probe_runtime_paths", [])
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


_FUTURE_FEATURE_NAMES = frozenset(_future.all_feature_names)


def _future_import_features_are_supported(node: ast.AST) -> bool:
    """Check the interpreter-supported, named future-import grammar."""
    return (
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and node.level == 0
        and bool(node.names)
        and all(alias.name != "*" and alias.name in _FUTURE_FEATURE_NAMES for alias in node.names)
    )


def _supported_future_import_is_passive(tree: ast.Module, node: ast.AST) -> bool:
    """Admit legal top-level compiler directives without executing facade source."""
    if not _future_import_features_are_supported(node):
        return False
    index = next(
        (position for position, statement in enumerate(tree.body) if statement is node), None
    )
    if index is None:
        return False
    first = tree.body[0] if tree.body else None
    has_docstring = (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )
    prefix_start = 1 if has_docstring else 0
    return all(
        _future_import_features_are_supported(previous)
        for previous in tree.body[prefix_start:index]
    )


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
            for target in targets
            for child in ast.walk(target)
        ):
            yield node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                yield node
        elif (
            isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar))
            and node.name == symbol
        ):
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


def _module_scope_nodes(tree: ast.Module) -> Iterator[ast.AST]:
    """Walk module execution syntax while excluding function and class bodies."""
    type_checking = {
        alias.asname or alias.name
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom)
        and statement.module == "typing"
        and statement.level == 0
        for alias in statement.names
        if alias.name == "TYPE_CHECKING"
    }

    def visit(node: ast.AST) -> Iterator[ast.AST]:
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id in type_checking
        ):
            for child in node.orelse:
                yield from visit(child)
            return
        for child in ast.iter_child_nodes(node):
            yield from visit(child)

    yield from visit(tree)


def _module_scope_symbol_bindings(tree: ast.Module, symbol: str) -> Iterator[ast.AST]:
    """Find source bindings and collection writes in module execution scope."""
    mutation_methods = {
        "update",
        "extend",
        "clear",
        "pop",
        "popitem",
        "setdefault",
        "__setitem__",
        "__delitem__",
        "items",
    }
    for node in _module_scope_nodes(tree):
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
            for target in targets
            for child in ast.walk(target)
        ):
            yield node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                yield node
        elif (
            isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar))
            and node.name == symbol
        ):
            yield node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            if any(
                alias.name == "*" or (alias.asname or alias.name.split(".")[0]) == symbol
                for alias in node.names
            ):
                yield node
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in mutation_methods
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == symbol
        ):
            yield node


def _export_source_locator(source: Path) -> str:
    """Use a canonical repository locator in reproducible generated refusals."""
    return source.relative_to(REPO_ROOT).as_posix()


def _module_namespace_uses_are_closed(
    tree: ast.Module,
    source: Path | None = None,
    *,
    allowed_sequence_extensions: frozenset[int] = frozenset(),
) -> bool:
    """Accept only read-only namespace access and exact lazy-name caching.

    Export names are static evidence only when no source construct can rebind the
    module namespace behind the resolver. Every callable in the source tree is
    checked for global/nonlocal rebinding and module-attribute or subscript writes.
    The sole writable exception is the standard ``globals()[name] = value`` cache
    inside the one-argument ``__getattr__``; the route proof separately establishes
    that the selected name is finite and the returned value is the exact child.
    Unknown helpers and reflection remain fail-closed through the loader and
    namespace checks below.
    """
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    top_functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if len(top_functions) != sum(
        1 for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        return False

    def enclosing_function(node: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        parent = parents.get(node)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return parent
            parent = parents.get(parent)
        return None

    def globals_call(node: ast.AST) -> bool:
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "globals"
            and not node.args
            and not node.keywords
            and not list(_symbol_binding_nodes(tree, "globals"))
        ):
            return False
        function = enclosing_function(node)
        if function is None:
            return True
        if any(arg.arg == "globals" for arg in _function_arguments(function)):
            return False
        if any(
            isinstance(child, ast.Name)
            and child.id == "globals"
            and isinstance(child.ctx, (ast.Store, ast.Del))
            for child in ast.walk(function)
        ):
            return False
        return not any(
            isinstance(child, ast.Global) and "globals" in child.names
            for child in ast.walk(function)
        )

    def safe_dir_expression(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in {"__all__", "_SURFACE_NAMES", "_EXPORTS", "_LAZY_IMPORTS"}
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str)
        if isinstance(node, ast.Starred):
            return safe_dir_expression(node.value)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return all(safe_dir_expression(item) for item in node.elts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return safe_dir_expression(node.left) and safe_dir_expression(node.right)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):

            def is_unshadowed_set(value: ast.AST) -> bool:
                return (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "set"
                    and len(value.args) == 1
                    and not value.keywords
                    and not list(_symbol_binding_nodes(tree, "set"))
                    and safe_dir_expression(value.args[0])
                )

            return is_unshadowed_set(node.left) and is_unshadowed_set(node.right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "globals":
                return globals_call(node)
            return (
                node.func.id in {"sorted", "list", "set"}
                and len(node.args) == 1
                and not node.keywords
                and not list(_symbol_binding_nodes(tree, node.func.id))
                and safe_dir_expression(node.args[0])
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return (
                node.func.attr == "keys"
                and not node.args
                and not node.keywords
                and safe_dir_expression(node.func.value)
            )
        return globals_call(node)

    def valid_dir_function(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        if function not in tree.body or function.decorator_list or function.type_params:
            return False
        if _function_arguments(function) or function.args.defaults or function.args.kw_defaults:
            return False
        header_expressions = [function.returns]
        header_expressions.extend(arg.annotation for arg in _function_arguments(function))
        if any(
            isinstance(node, ast.Call)
            for expression in header_expressions
            if expression is not None
            for node in ast.walk(expression)
        ):
            return False
        body = list(function.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                body.pop(0)
        return (
            len(body) == 1
            and isinstance(body[0], ast.Return)
            and body[0].value is not None
            and safe_dir_expression(body[0].value)
            and not any(
                isinstance(node, ast.Call)
                and node.func is not None
                and not (
                    (
                        isinstance(node.func, ast.Name)
                        and node.func.id in {"sorted", "list", "set", "globals"}
                    )
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "keys")
                )
                for node in ast.walk(body[0].value)
            )
        )

    def valid_getattr_cache(call: ast.Call) -> bool:
        function = enclosing_function(call)
        if function is None or function is not top_functions.get("__getattr__"):
            return False
        arguments = _function_arguments(function)
        if len(arguments) != 1 or arguments[0].arg != "name":
            return False
        subscript = parents.get(call)
        statement = parents.get(subscript) if isinstance(subscript, ast.Subscript) else None
        return (
            isinstance(subscript, ast.Subscript)
            and subscript.value is call
            and isinstance(subscript.slice, ast.Name)
            and subscript.slice.id == "name"
            and isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and statement.targets[0] is subscript
            and isinstance(statement.value, ast.Name)
        )

    # A declaration cannot support a lazy-route proof if a callable can later
    # replace a module binding. Reject the entire source-language class rather
    # than naming one export table: ``global`` and ``nonlocal`` have the same
    # effect for every binding, including an immutable tuple such as ``__all__``.
    if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(tree)):
        return False
    callable_nodes = [
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if any(node not in tree.body for node in callable_nodes):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return False
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
            if not (isinstance(node.ctx, ast.Store) and valid_getattr_cache(node.value)):
                return False

    reflection_aliases = {
        "globals",
        "vars",
        "locals",
        "exec",
        "eval",
        "setattr",
        "delattr",
        "__import__",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "builtins":
            if any(alias.name in reflection_aliases for alias in node.names):
                return False
        if isinstance(node, ast.ImportFrom) and node.module == "sys":
            if any(alias.name == "modules" for alias in node.names):
                return False
        if isinstance(node, ast.Import) and any(
            alias.name in {"builtins", "sys"} for alias in node.names
        ):
            return False
        if (
            isinstance(node, ast.Name)
            and node.id == "__builtins__"
            and isinstance(node.ctx, ast.Load)
        ):
            return False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node in tree.body:
            if node.decorator_list or node.type_params:
                return False
            header_expressions = [node.returns, *node.args.defaults, *node.args.kw_defaults]
            header_expressions.extend(arg.annotation for arg in _function_arguments(node))
            if any(
                isinstance(child, ast.Call)
                for expression in header_expressions
                if expression is not None
                for child in ast.walk(expression)
            ):
                return False
        if isinstance(node, ast.Name) and node.id in reflection_aliases - {"globals"}:
            if isinstance(node.ctx, ast.Load):
                return False
        if isinstance(node, ast.Name) and node.id == "globals" and isinstance(node.ctx, ast.Load):
            if not isinstance(parents.get(node), ast.Call) or parents[node].func is not node:
                return False
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins" and (alias.asname or "builtins") in {
                    child.id for child in ast.walk(tree) if isinstance(child, ast.Name)
                }:
                    builtins_alias = alias.asname or "builtins"
                    if any(
                        isinstance(child, ast.Attribute)
                        and isinstance(child.value, ast.Name)
                        and child.value.id == builtins_alias
                        and child.attr in reflection_aliases
                        for child in ast.walk(tree)
                    ):
                        return False
                if alias.name == "sys":
                    sys_alias = alias.asname or "sys"
                    if any(
                        isinstance(child, ast.Attribute)
                        and isinstance(child.value, ast.Name)
                        and child.value.id == sys_alias
                        and child.attr == "modules"
                        for child in ast.walk(tree)
                    ):
                        return False
        if isinstance(node, ast.Attribute) and node.attr in {
            "__dict__",
            "__globals__",
            "f_globals",
            "__getattribute__",
            "__setattr__",
            "__delattr__",
        }:
            return False
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in reflection_aliases - {"globals"}:
                return False
            if isinstance(node.func, ast.Attribute) and node.func.attr in reflection_aliases:
                return False
            if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                if any(
                    isinstance(argument, ast.Constant)
                    and argument.value
                    in {"__all__", "__dict__", "__getattr__", "__getattribute__", "modules"}
                    for argument in node.args[1:]
                ):
                    return False
            if isinstance(node.func, ast.Attribute) and node.func.attr == "modules":
                return False
            if isinstance(node.func, ast.Name) and node.func.id == "globals":
                function = enclosing_function(node)
                if function is top_functions.get("__dir__"):
                    if not valid_dir_function(function):
                        return False
                elif not valid_getattr_cache(node):
                    return False
                if not globals_call(node):
                    return False
        if isinstance(node, ast.Constant) and node.value == "__dict__":
            return False
    closed_sequence_extensions = set(allowed_sequence_extensions)
    if source is not None:
        declaration_resolver = _StaticExportResolver(source, tree)
        for statement in tree.body:
            if isinstance(
                statement, ast.Expr
            ) and declaration_resolver._admit_static_sequence_extension(source, statement.value):
                closed_sequence_extensions.add(id(statement.value))
    return "__getattr__" not in top_functions or _facade_callable_effects_are_closed(
        tree,
        source,
        top_functions,
        enclosing_function,
        globals_call,
        valid_getattr_cache,
        valid_dir_function,
        frozenset(closed_sequence_extensions),
    )


def _facade_callable_effects_are_closed(
    tree: ast.Module,
    source: Path | None,
    top_functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    enclosing_function: Callable[[ast.AST], ast.FunctionDef | ast.AsyncFunctionDef | None],
    globals_call: Callable[[ast.AST], bool],
    valid_getattr_cache: Callable[[ast.Call], bool],
    valid_dir_function: Callable[[ast.FunctionDef | ast.AsyncFunctionDef], bool],
    allowed_sequence_extensions: frozenset[int] = frozenset(),
) -> bool:
    """Bound facade call effects to loader, finite-map, and read-only hook forms.

    A lazy facade is source evidence only when every callable and every import-time
    call uses the same small grammar. Unknown calls are refused even when they are
    in an otherwise-unused helper: a helper can return a mutable export table and
    mutate it through an alias without mentioning ``__all__`` at the mutation site.
    Imported helpers are accepted only when their source is bound and their existing
    read-api catalog or exact loader proof establishes the returned module.
    """
    module_info = None if source is None else _module_name_for_path(source)

    def has_static_dict_initializer(symbol: str) -> bool:
        initializers: list[ast.AST] = []
        for statement in tree.body:
            if isinstance(statement, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == symbol
                    for target in statement.targets
                ) and isinstance(statement.value, ast.Dict):
                    initializers.append(statement)
            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == symbol
                and isinstance(statement.value, ast.Dict)
            ):
                initializers.append(statement)
        return len(initializers) == 1

    def imported_surface_helper(name: str) -> bool:
        if source is None or module_info is None:
            return False
        imported = _imported_function_source(module_info[0], source, tree, name)
        if imported is None:
            return False
        imported_module, imported_source, imported_tree = imported
        if name not in {"available_surfaces", "load_surface"}:
            return False
        helper = _top_level_function(imported_tree, name)
        if (
            helper is None
            or (name == "available_surfaces" and _function_arguments(helper))
            or (name == "load_surface" and not _has_exact_positional_parameters(helper, "name"))
        ):
            return False
        records = _read_api_surface_records(imported_source, imported_tree)
        return bool(
            imported_module == "polisyos.data_forge.read_api.surfaces" and records is not None
        )

    def pure_loader_helper(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        seen: frozenset[str] = frozenset(),
    ) -> bool:
        if function.name in seen or function.name in {"__getattr__", "__dir__"}:
            return False
        if not _loader_helper_body_is_closed(function):
            return False
        arguments = _function_arguments(function)
        if (
            len(arguments) != 1
            or function.args.vararg is not None
            or function.args.kwarg is not None
            or function.args.kwonlyargs
            or len(function.args.posonlyargs) + len(function.args.args) != 1
        ):
            return False
        body = _function_body_without_docstring(function)
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            return False
        value = body[0].value
        if not isinstance(value, ast.Call) or value.keywords or len(value.args) != 1:
            return False
        if _import_module_callable_is_stdlib(tree, value.func):
            return True
        if not isinstance(value.func, ast.Name) or not isinstance(value.args[0], ast.Name):
            return False
        if value.args[0].id != arguments[0].arg:
            return False
        next_helper = top_functions.get(value.func.id)
        if next_helper is not None:
            return pure_loader_helper(next_helper, seen | {function.name})
        return imported_surface_helper(value.func.id)

    def non_hook_helpers_preserve_selector_state() -> bool:
        """Reject helper call chains that can expose or mutate facade selectors."""
        hook_names = {"__getattr__", "__dir__"}
        container_names = {"__all__"}
        for statement in tree.body:
            if isinstance(statement, ast.Assign) and isinstance(
                statement.value, (ast.List, ast.Tuple, ast.Set, ast.Dict)
            ):
                container_names.update(
                    target.id for target in statement.targets if isinstance(target, ast.Name)
                )
            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and isinstance(statement.value, (ast.List, ast.Tuple, ast.Set, ast.Dict))
            ):
                container_names.add(statement.target.id)
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        module_imports: set[str] = set()
        for statement in tree.body:
            if isinstance(statement, ast.Import):
                module_imports.update(
                    alias.asname or alias.name.split(".")[0] for alias in statement.names
                )
            elif isinstance(statement, ast.ImportFrom):
                module_imports.update(alias.asname or alias.name for alias in statement.names)
        hook_containers = set(container_names)
        for hook_name in hook_names:
            hook = top_functions.get(hook_name)
            if hook is None:
                continue
            for node in ast.walk(hook):
                if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
                    continue
                if node.id in container_names:
                    hook_containers.add(node.id)
                    continue
                if node.id not in module_imports:
                    continue
                parent = parents.get(node)
                if (
                    (isinstance(parent, ast.Subscript) and parent.value is node)
                    or (
                        isinstance(parent, ast.Compare)
                        and node in parent.comparators
                        and any(
                            isinstance(operator, (ast.In, ast.NotIn)) for operator in parent.ops
                        )
                    )
                    or (
                        isinstance(parent, ast.Attribute)
                        and parent.value is node
                        and parent.attr in {"get", "items", "keys", "values"}
                    )
                ):
                    hook_containers.add(node.id)
        mutators = {
            "add",
            "append",
            "clear",
            "discard",
            "extend",
            "pop",
            "popitem",
            "remove",
            "setdefault",
            "update",
        }
        sensitive: set[str] = set()
        calls_by_function: dict[str, set[str]] = {}
        for name, function in top_functions.items():
            if name in hook_names:
                continue
            callees: set[str] = set()
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                    and node.id in hook_containers
                ):
                    sensitive.add(name)
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id in top_functions:
                    callees.add(node.func.id)
                if any(
                    isinstance(child, ast.Name) and child.id in hook_containers
                    for argument in [*node.args, *(keyword.value for keyword in node.keywords)]
                    for child in ast.walk(argument)
                ):
                    sensitive.add(name)
                if isinstance(node.func, ast.Attribute) and node.func.attr in mutators:
                    sensitive.add(name)
            calls_by_function[name] = callees
        changed = True
        while changed:
            changed = False
            for name, callees in calls_by_function.items():
                if name not in sensitive and callees & sensitive:
                    sensitive.add(name)
                    changed = True
        return not sensitive

    def function_call_is_closed(
        call: ast.Call,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        if function is top_functions.get("__dir__"):
            return valid_dir_function(function)
        if function is top_functions.get("__getattr__"):
            if isinstance(call.func, ast.Name):
                if call.func.id == "globals":
                    return valid_getattr_cache(call) and globals_call(call)
                if call.func.id == "AttributeError":
                    return (
                        not list(_symbol_binding_nodes(tree, "AttributeError"))
                        and len(call.args) == 1
                        and not call.keywords
                    )
                if call.func.id == "getattr":
                    return (
                        not list(_symbol_binding_nodes(tree, "getattr"))
                        and len(call.args) == 2
                        and not call.keywords
                    )
                if call.func.id == "import_module":
                    return _import_module_callable_is_stdlib(tree, call.func) or any(
                        isinstance(node, ast.ImportFrom)
                        and node.level == 0
                        and node.module == "importlib"
                        and any(
                            alias.name == "import_module"
                            and (alias.asname or alias.name) == "import_module"
                            for alias in node.names
                        )
                        for node in ast.walk(function)
                    )
                if call.func.id == "load_surface":
                    return (
                        source is not None
                        and module_info is not None
                        and len(call.args) == 1
                        and isinstance(call.args[0], ast.Name)
                        and not call.keywords
                        and imported_surface_helper("load_surface")
                    )
                helper = top_functions.get(call.func.id)
                return bool(
                    helper is not None
                    and len(call.args) == 1
                    and isinstance(call.args[0], ast.Name)
                    and _function_arguments(helper)
                    and call.args[0].id == _function_arguments(helper)[0].arg
                    and not call.keywords
                    and pure_loader_helper(helper)
                )
            if isinstance(call.func, ast.Attribute):
                if call.func.attr == "import_module":
                    return (
                        _import_module_callable_is_stdlib(tree, call.func)
                        and len(call.args) == 1
                        and not call.keywords
                    )
                if call.func.attr == "get":
                    return (
                        isinstance(call.func.value, ast.Name)
                        and has_static_dict_initializer(call.func.value.id)
                        and len(call.args) == 1
                        and isinstance(call.args[0], ast.Name)
                        and call.args[0].id == "name"
                        and not call.keywords
                    )
            return False

        if function in top_functions.values():
            # The inventory measures import-time declarations. Non-hook function
            # bodies are not executed during import; their namespace writes,
            # reflection, decorators, defaults, and annotations are checked above.
            # A helper reachable from __getattr__ is still checked at its call site
            # by pure_loader_helper.
            return True
        return pure_loader_helper(function)

    def pkgutil_extend_path_is_closed(call: ast.Call) -> bool:
        if (
            not isinstance(call.func, ast.Name)
            or call.func.id != "extend_path"
            or len(call.args) != 2
            or call.keywords
            or not all(isinstance(argument, ast.Name) for argument in call.args)
            or call.args[0].id != "__path__"
            or call.args[1].id != "__name__"
        ):
            return False
        import_bindings = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.ImportFrom)
            and statement.level == 0
            and statement.module == "pkgutil"
            and len(statement.names) == 1
            and statement.names[0].name == "extend_path"
            and (statement.names[0].asname or statement.names[0].name) == "extend_path"
        ]
        path_assignments = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "__path__"
            and statement.value is call
        ]
        all_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "extend_path"
        ]
        return (
            len(import_bindings) == 1
            and list(_module_scope_symbol_bindings(tree, "extend_path")) == import_bindings
            and len(path_assignments) == 1
            and list(_module_scope_symbol_bindings(tree, "__path__")) == path_assignments
            and all_calls == [call]
        )

    def module_call_is_closed(call: ast.Call) -> bool:
        if isinstance(call.func, ast.Name):
            if call.func.id == "extend_path":
                return pkgutil_extend_path_is_closed(call)
            if call.func.id in {"frozenset", "tuple", "list", "set", "dict"}:
                return (
                    not list(_symbol_binding_nodes(tree, call.func.id))
                    and len(call.args) == 1
                    and not call.keywords
                )
            if call.func.id in {"sorted", "list", "tuple", "set"}:
                return (
                    not list(_symbol_binding_nodes(tree, call.func.id))
                    and len(call.args) == 1
                    and isinstance(call.args[0], ast.Name)
                    and has_static_dict_initializer(call.args[0].id)
                    and not call.keywords
                )
            return imported_surface_helper(call.func.id) and not call.args and not call.keywords
        if isinstance(call.func, ast.Attribute):
            receiver = call.func.value
            if not isinstance(receiver, ast.Name):
                return False
            if call.func.attr == "extend":
                return (
                    id(call) in allowed_sequence_extensions
                    and len(call.args) == 1
                    and not call.keywords
                )
            if not has_static_dict_initializer(receiver.id):
                return False
            if call.func.attr == "items":
                return not call.args and not call.keywords
            if call.func.attr == "update":
                return len(call.args) == 1 and not call.keywords
        return False

    if not non_hook_helpers_preserve_selector_state():
        return False

    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        function = enclosing_function(call)
        if function is None:
            if not module_call_is_closed(call):
                return False
        elif not function_call_is_closed(call, function):
            return False
    return True


def _function_arguments(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.arg]:
    args = function.args
    result = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg is not None:
        result.append(args.vararg)
    if args.kwarg is not None:
        result.append(args.kwarg)
    return result


def _loader_helper_body_is_closed(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Only follow a loader helper whose complete body is one pure return."""
    if (
        function.decorator_list
        or function.type_params
        or function.args.defaults
        or any(value is not None for value in function.args.kw_defaults)
    ):
        return False
    expressions = [function.returns]
    expressions.extend(arg.annotation for arg in _function_arguments(function))
    if any(
        isinstance(node, ast.Call)
        for expression in expressions
        if expression is not None
        for node in ast.walk(expression)
    ):
        return False
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body.pop(0)
    return len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None


class _UnresolvedExportDeclarationError(ValueError):
    """An intentional refusal by the bounded static export grammar."""

    def __init__(self, message: str, declared_candidates: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.declared_candidates = declared_candidates


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
        self._allowed_operations: set[tuple[Path, int]] = set()
        self._allowed_mapping_updates: set[tuple[Path, int]] = set()
        self._allowed_sequence_extensions: set[tuple[Path, int]] = set()
        self._mapping_active: set[tuple[Path, str]] = set()
        self._passive_active: set[tuple[Path, str]] = set()
        self._passive_modules: set[Path] = set()
        self._lazy_facade_cache: dict[Path, bool] = {}

    def _tree(self, source: Path) -> ast.Module:
        if source not in self._trees:
            self._trees[source] = ast.parse(admitted_read_bytes(source, REPO_ROOT))
        return self._trees[source]

    @staticmethod
    def _direct_mapping_update(tree: ast.Module, symbol: str, node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == symbol
            and len(node.args) == 1
            and not node.keywords
            and any(
                isinstance(statement, ast.Expr) and statement.value is node
                for statement in tree.body
            )
        )

    @staticmethod
    def _direct_mapping_item_assignment(tree: ast.Module, symbol: str, node: ast.AST) -> bool:
        """Recognize one literal-key write into a module-scope mapping."""
        return not (
            not isinstance(node, ast.Assign)
            or len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Subscript)
            or not isinstance(node.targets[0].value, ast.Name)
            or node.targets[0].value.id != symbol
            or not isinstance(node.targets[0].slice, ast.Constant)
            or not isinstance(node.targets[0].slice.value, str)
            or node not in tree.body
        )

    @staticmethod
    def _direct_mapping_items_iteration(tree: ast.Module, symbol: str, node: ast.AST) -> bool:
        """Admit a read-only module-level loop over a statically selected map."""
        return any(
            isinstance(statement, (ast.For, ast.AsyncFor))
            and not statement.orelse
            and statement.iter is node
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "items"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == symbol
            and not node.args
            and not node.keywords
            for statement in tree.body
        )

    @staticmethod
    def _mapping_values_are_immutable(mapping: dict[object, object]) -> bool:
        def immutable(value: object) -> bool:
            if value is None or isinstance(value, (str, int, float, bool, bytes)):
                return True
            return isinstance(value, tuple) and all(immutable(item) for item in value)

        return all(immutable(value) for value in mapping.values())

    def _closed_static_value(
        self,
        source: Path,
        node: ast.AST,
        local_values: dict[str, object],
    ) -> object:
        if isinstance(node, ast.Constant):
            return node.value
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "MappingProxyType"
            and len(node.args) == 1
            and not node.keywords
        ):
            bindings = list(_module_scope_symbol_bindings(self._tree(source), "MappingProxyType"))
            if len(bindings) != 1 or not isinstance(bindings[0], ast.ImportFrom):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved mapping wrapper: {_export_source_locator(source)}"
                )
            imported = bindings[0]
            if imported.module != "types" or not any(
                alias.name == "MappingProxyType"
                and (alias.asname or alias.name) == "MappingProxyType"
                for alias in imported.names
            ):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved mapping wrapper: {_export_source_locator(source)}"
                )
            wrapped = self._closed_static_value(source, node.args[0], local_values)
            if not isinstance(wrapped, dict):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved mapping wrapper value: {_export_source_locator(source)}"
                )
            return wrapped
        if isinstance(node, ast.Name):
            if node.id in local_values:
                return local_values[node.id]
            self._allowed_reads.add((source, id(node)))
            bindings = list(_module_scope_symbol_bindings(self._tree(source), node.id))
            if any((source, node.id) == active for active in self._mapping_active):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static mapping cycle: {_export_source_locator(source)}:{node.id}"
                )
            if (
                len(bindings) == 1
                and isinstance(bindings[0], (ast.Assign, ast.AnnAssign))
                and isinstance(bindings[0].value, ast.Dict)
            ):
                return self._closed_static_mapping(source, node.id)
            return self.resolve(source, node.id)
        if isinstance(node, ast.Tuple):
            return tuple(
                self._closed_static_value(source, item, local_values) for item in node.elts
            )
        if isinstance(node, ast.List):
            return [self._closed_static_value(source, item, local_values) for item in node.elts]
        if isinstance(node, ast.Set):
            return {self._closed_static_value(source, item, local_values) for item in node.elts}
        if isinstance(node, ast.Dict):
            mapping: dict[object, object] = {}
            for key_node, value_node in zip(node.keys, node.values, strict=True):
                if key_node is None:
                    expanded = self._closed_static_value(source, value_node, local_values)
                    if not isinstance(expanded, dict):
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved static mapping expansion: {_export_source_locator(source)}"
                        )
                    mapping.update(expanded)
                    continue
                key = self._closed_static_value(source, key_node, local_values)
                value = self._closed_static_value(source, value_node, local_values)
                try:
                    hash(key)
                except TypeError as exc:
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved unhashable static mapping key: {_export_source_locator(source)}"
                    ) from exc
                mapping[key] = value
            return mapping
        if isinstance(node, ast.JoinedStr):
            pieces: list[str] = []
            for item in node.values:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    pieces.append(item.value)
                    continue
                if (
                    not isinstance(item, ast.FormattedValue)
                    or item.conversion != -1
                    or item.format_spec is not None
                ):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved static mapping format: {_export_source_locator(source)}"
                    )
                value = self._closed_static_value(source, item.value, local_values)
                if not isinstance(value, str):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved non-string static mapping format: {_export_source_locator(source)}"
                    )
                pieces.append(value)
            return "".join(pieces)
        if isinstance(node, ast.DictComp):
            if len(node.generators) != 1 or node.generators[0].is_async or node.generators[0].ifs:
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static mapping comprehension: {_export_source_locator(source)}"
                )
            generator = node.generators[0]
            iterable = self._closed_static_value(source, generator.iter, local_values)
            if isinstance(iterable, (dict, tuple, list)):
                items = tuple(iterable)
            else:
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static mapping iteration: {_export_source_locator(source)}"
                )

            def bind_target(target: ast.AST, value: object) -> dict[str, object]:
                if isinstance(target, ast.Name):
                    return {target.id: value}
                if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (tuple, list)):
                    if len(target.elts) != len(value):
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved static mapping unpack: {_export_source_locator(source)}"
                        )
                    bound: dict[str, object] = {}
                    for child, item in zip(target.elts, value, strict=True):
                        bound.update(bind_target(child, item))
                    return bound
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static mapping target: {_export_source_locator(source)}"
                )

            mapping = {}
            for item in items:
                child_values = {**local_values, **bind_target(generator.target, item)}
                key = self._closed_static_value(source, node.key, child_values)
                value = self._closed_static_value(source, node.value, child_values)
                try:
                    hash(key)
                except TypeError as exc:
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved unhashable static mapping key: {_export_source_locator(source)}"
                    ) from exc
                mapping[key] = value
            return mapping
        raise _UnresolvedExportDeclarationError(
            f"Unresolved static mapping value: {_export_source_locator(source)}:{ast.unparse(node)}"
        )

    def _mapping_references_are_closed(
        self,
        source: Path,
        symbol: str,
        declaration: ast.AST,
        updates: list[ast.Call],
    ) -> bool:
        """Close aliases and writes in the import-time dependency slice only."""
        tree = self._tree(source)
        update_ids = {id(node) for node in updates}
        allowed_item_target_ids = {
            id(node.targets[0])
            for node in updates
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Subscript)
        }
        alias_names = {symbol}
        alias_initializers: set[int] = set()

        def is_literal_container(value: ast.AST, names: set[str]) -> bool:
            if isinstance(value, ast.Constant):
                return True
            if isinstance(value, ast.Name):
                if value.id in names:
                    return True
                bindings = list(_module_scope_symbol_bindings(tree, value.id))
                return len(bindings) == 1 and bindings[0] in tree.body
            if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                return all(is_literal_container(item, names) for item in value.elts)
            if isinstance(value, ast.Dict):
                return all(
                    key is not None
                    and is_literal_container(key, names)
                    and is_literal_container(item, names)
                    for key, item in zip(value.keys, value.values, strict=True)
                )
            return False

        module_nodes = list(_module_scope_nodes(tree))
        changed = True
        while changed:
            changed = False
            for node in module_nodes:
                if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                    continue
                if node is declaration or id(node) in alias_initializers or node.value is None:
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                    continue
                target_name = targets[0].id
                referenced = {
                    child.id
                    for child in ast.walk(node.value)
                    if isinstance(child, ast.Name)
                    and child.id in alias_names
                    and isinstance(child.ctx, ast.Load)
                }
                if not referenced:
                    continue
                if isinstance(node.value, ast.Name):
                    # A selected alias in the closed declaration dependency cone is
                    # trackable; an unselected alias could escape and mutate the map.
                    if (source, id(node.value)) in self._allowed_reads:
                        if target_name not in alias_names:
                            alias_names.add(target_name)
                            alias_initializers.add(id(node))
                            changed = True
                        continue
                    return False
                if is_literal_container(node.value, alias_names):
                    if target_name not in alias_names:
                        alias_names.add(target_name)
                        alias_initializers.add(id(node))
                        changed = True

        for node in module_nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(
                    isinstance(child, ast.Name) and child.id in alias_names
                    for target in targets
                    for child in ast.walk(target)
                ):
                    if (
                        node is declaration
                        or id(node) in update_ids
                        or id(node) in alias_initializers
                    ):
                        pass
                    else:
                        return False
                if node.value is not None:
                    reads = [
                        child
                        for child in ast.walk(node.value)
                        if isinstance(child, ast.Name)
                        and child.id in alias_names
                        and isinstance(child.ctx, ast.Load)
                    ]
                    if (
                        reads
                        and id(node) not in alias_initializers
                        and not all((source, id(child)) in self._allowed_reads for child in reads)
                    ):
                        target = (
                            node.targets[0]
                            if isinstance(node, ast.Assign) and len(node.targets) == 1
                            else None
                        )
                        map_consumer = False
                        if (
                            isinstance(target, ast.Subscript)
                            and isinstance(target.value, ast.Name)
                            and isinstance(target.slice, ast.Constant)
                            and isinstance(target.slice.value, str)
                            and isinstance(node.value, ast.Name)
                        ):
                            map_name = target.value.id
                            map_bindings = list(_module_scope_symbol_bindings(tree, map_name))
                            map_consumer = (
                                len(map_bindings) >= 1
                                and any(
                                    isinstance(binding, (ast.Assign, ast.AnnAssign))
                                    and getattr(binding, "value", None) is not None
                                    and isinstance(binding.value, ast.Dict)
                                    for binding in map_bindings
                                )
                                and all(
                                    (
                                        isinstance(binding, (ast.Assign, ast.AnnAssign, ast.Expr))
                                        or self._direct_mapping_item_assignment(
                                            tree, map_name, binding
                                        )
                                        or self._direct_mapping_update(tree, map_name, binding)
                                        or self._direct_mapping_items_iteration(
                                            tree, map_name, binding
                                        )
                                    )
                                    for binding in map_bindings
                                )
                            )
                        if not map_consumer:
                            return False
            if isinstance(node, (ast.Delete, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Delete) else [node.target]
                if any(
                    isinstance(child, ast.Name) and child.id in alias_names
                    for target in targets
                    for child in ast.walk(target)
                ):
                    return False
            if isinstance(node, ast.Call):
                if self._direct_mapping_items_iteration(tree, symbol, node):
                    continue
                receiver_reads = [
                    child
                    for child in ast.walk(node.func)
                    if isinstance(child, ast.Name)
                    and child.id in alias_names
                    and isinstance(child.ctx, ast.Load)
                ]
                if receiver_reads:
                    if (
                        id(node) in update_ids
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == symbol
                    ):
                        continue
                    return False
                argument_reads = [
                    child
                    for argument in (*node.args, *(kw.value for kw in node.keywords))
                    for child in ast.walk(argument)
                    if isinstance(child, ast.Name)
                    and child.id in alias_names
                    and isinstance(child.ctx, ast.Load)
                ]
                if argument_reads and not (
                    (
                        (source, id(node)) in self._allowed_calls
                        or (source, id(node)) in self._allowed_mapping_updates
                        or (source, id(node)) in self._allowed_sequence_extensions
                    )
                    and all((source, id(child)) in self._allowed_reads for child in argument_reads)
                ):
                    return False
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
                if (
                    any(
                        isinstance(child, ast.Name) and child.id in alias_names
                        for child in ast.walk(node.value)
                    )
                    and id(node) not in allowed_item_target_ids
                ):
                    return False
        return True

    def _closed_static_mapping(self, source: Path, symbol: str) -> dict[object, object]:
        key = (source, symbol)
        if key in self._mapping_active:
            raise _UnresolvedExportDeclarationError(
                f"Unresolved static mapping cycle: {_export_source_locator(source)}:{symbol}"
            )
        self._mapping_active.add(key)
        try:
            tree = self._tree(source)
            bindings = list(_module_scope_symbol_bindings(tree, symbol))
            if len(bindings) == 1 and isinstance(bindings[0], ast.ImportFrom):
                imported = bindings[0]
                matches = [
                    alias
                    for alias in imported.names
                    if alias.name != "*" and (alias.asname or alias.name) == symbol
                ]
                info = _module_name_for_path(source)
                module = _resolve_import_module(*info, imported) if info is not None else None
                if len(matches) != 1 or module is None or not module.startswith("polisyos."):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved imported static mapping: {_export_source_locator(source)}:{symbol}"
                    )
                self._allowed_reads.add((source, id(imported)))
                return self._closed_static_mapping(_facade_source_for(module), matches[0].name)
            updates = [
                node
                for node in bindings
                if self._direct_mapping_update(tree, symbol, node)
                or self._direct_mapping_item_assignment(tree, symbol, node)
            ]
            read_only = [
                node
                for node in bindings
                if self._direct_mapping_items_iteration(tree, symbol, node)
            ]
            base = [node for node in bindings if node not in updates and node not in read_only]
            if (
                len(base) != 1
                or base[0] not in tree.body
                or not isinstance(base[0], (ast.Assign, ast.AnnAssign))
                or (
                    isinstance(base[0], ast.Assign)
                    and (
                        len(base[0].targets) != 1
                        or not isinstance(base[0].targets[0], ast.Name)
                        or base[0].targets[0].id != symbol
                    )
                )
                or (
                    isinstance(base[0], ast.AnnAssign)
                    and (not isinstance(base[0].target, ast.Name) or base[0].target.id != symbol)
                )
                or base[0].value is None
                or not (
                    isinstance(base[0].value, ast.Dict)
                    or (
                        isinstance(base[0].value, ast.Call)
                        and isinstance(base[0].value.func, ast.Name)
                        and base[0].value.func.id == "MappingProxyType"
                        and len(base[0].value.args) == 1
                        and not base[0].value.keywords
                    )
                )
                or any(node.lineno <= base[0].end_lineno for node in updates)
            ):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static mapping declaration: {_export_source_locator(source)}:{symbol}"
                )
            mapping = self._closed_static_value(source, base[0].value, {})
            if not isinstance(mapping, dict):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static mapping declaration: {_export_source_locator(source)}:{symbol}"
                )
            for update in sorted(updates, key=lambda item: item.lineno):
                if self._direct_mapping_item_assignment(tree, symbol, update):
                    target = update.targets[0]
                    if not isinstance(target, ast.Subscript):
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved direct mapping update: {_export_source_locator(source)}:{symbol}"
                        )
                    mapping_key = ast.literal_eval(target.slice)
                    value = self._closed_static_value(source, update.value, {})
                    mapping[mapping_key] = value
                    self._allowed_mapping_updates.add((source, id(update)))
                    continue
                addition = self._closed_static_value(source, update.args[0], {})
                if not isinstance(addition, dict):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved static mapping update: {_export_source_locator(source)}:{symbol}"
                    )
                mapping.update(addition)
                self._allowed_mapping_updates.add((source, id(update)))
                self._allowed_reads.add((source, id(update.func.value)))
            if not self._mapping_values_are_immutable(mapping):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved mutable static mapping values: {_export_source_locator(source)}:{symbol}"
                )
            if not self._mapping_references_are_closed(source, symbol, base[0], updates):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static mapping consumer: {_export_source_locator(source)}:{symbol}"
                )
            return mapping
        finally:
            self._mapping_active.remove(key)

    @staticmethod
    def _direct_sequence_extension(tree: ast.Module, symbol: str, node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "extend"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == symbol
            and len(node.args) == 1
            and not node.keywords
            and any(
                isinstance(statement, ast.Expr) and statement.value is node
                for statement in tree.body
            )
        )

    def _closed_static_sequence(self, source: Path, symbol: str) -> list[str]:
        key = (source, symbol)
        if key in self._mapping_active:
            raise _UnresolvedExportDeclarationError(
                f"Unresolved static sequence cycle: {_export_source_locator(source)}:{symbol}"
            )
        self._mapping_active.add(key)
        try:
            tree = self._tree(source)
            bindings = list(_module_scope_symbol_bindings(tree, symbol))
            extensions = [
                node for node in bindings if self._direct_sequence_extension(tree, symbol, node)
            ]
            base = [node for node in bindings if node not in extensions]
            if (
                len(base) != 1
                or base[0] not in tree.body
                or not isinstance(base[0], (ast.Assign, ast.AnnAssign))
                or (
                    isinstance(base[0], ast.Assign)
                    and (
                        len(base[0].targets) != 1
                        or not isinstance(base[0].targets[0], ast.Name)
                        or base[0].targets[0].id != symbol
                    )
                )
                or (
                    isinstance(base[0], ast.AnnAssign)
                    and (not isinstance(base[0].target, ast.Name) or base[0].target.id != symbol)
                )
                or not isinstance(base[0].value, ast.List)
                or any(node.lineno <= base[0].end_lineno for node in extensions)
            ):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static sequence declaration: {_export_source_locator(source)}:{symbol}"
                )
            values = self._value(source, base[0].value)
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static export sequence: {_export_source_locator(source)}:{symbol}"
                )
            for extension in extensions:
                addition = self._value(source, extension.args[0])
                if not isinstance(addition, (list, tuple)) or not all(
                    isinstance(item, str) for item in addition
                ):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved static sequence extension: {_export_source_locator(source)}:{symbol}"
                    )
                values.extend(addition)
                self._allowed_sequence_extensions.add((source, id(extension)))
                self._allowed_reads.add((source, id(extension.func.value)))
            if not self._mapping_references_are_closed(source, symbol, base[0], extensions):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved static sequence consumer: {_export_source_locator(source)}:{symbol}"
                )
            return values
        finally:
            self._mapping_active.remove(key)

    def _admit_static_sequence_extension(self, source: Path, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            return False
        if not isinstance(node.func.value, ast.Name):
            return False
        symbol = node.func.value.id
        if not self._direct_sequence_extension(self._tree(source), symbol, node):
            return False
        try:
            self._closed_static_sequence(source, symbol)
        except (OSError, ValueError, TypeError, SyntaxError):
            return False
        self._allowed_sequence_extensions.add((source, id(node)))
        self._allowed_reads.add((source, id(node.func.value)))
        return True

    def _admit_static_mapping_update(self, source: Path, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            return False
        if not isinstance(node.func.value, ast.Name):
            return False
        symbol = node.func.value.id
        if not self._direct_mapping_update(self._tree(source), symbol, node):
            return False
        try:
            self._closed_static_mapping(source, symbol)
        except (OSError, ValueError, TypeError, SyntaxError):
            return False
        self._allowed_mapping_updates.add((source, id(node)))
        self._allowed_reads.add((source, id(node.func.value)))
        return True

    def _type_checking_uses_are_closed(self, tree: ast.Module, local_name: str) -> bool:
        guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == local_name
            and not node.orelse
            and all(
                isinstance(statement, (ast.Import, ast.ImportFrom, ast.Pass))
                and not (
                    isinstance(statement, ast.ImportFrom)
                    and any(alias.name == "*" for alias in statement.names)
                )
                for statement in node.body
            )
        ]
        uses = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and node.id == local_name
            and isinstance(node.ctx, ast.Load)
        ]
        return all(any(node is guard.test for guard in guards) for node in uses)

    def _typing_import_is_declaration_only(self, source: Path, node: ast.ImportFrom) -> bool:
        tree = self._tree(source)
        if (
            node.level != 0
            or node.module != "typing"
            or not node.names
            or any(alias.name == "*" for alias in node.names)
        ):
            return False
        future_annotations = any(
            isinstance(statement, ast.ImportFrom)
            and statement.module == "__future__"
            and any(alias.name == "annotations" for alias in statement.names)
            and _supported_future_import_is_passive(tree, statement)
            for statement in tree.body
        )
        annotation_ids: set[int] = set()
        for statement in ast.walk(tree):
            expressions: list[ast.AST | None] = []
            if isinstance(statement, ast.arg):
                expressions.append(statement.annotation)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                expressions.append(statement.returns)
            elif isinstance(statement, ast.AnnAssign):
                expressions.append(statement.annotation)
            for expression in expressions:
                if expression is not None:
                    annotation_ids.update(id(child) for child in ast.walk(expression))
        for alias in node.names:
            local_name = alias.asname or alias.name
            if alias.name == "TYPE_CHECKING":
                binding_nodes = list(_module_scope_symbol_bindings(tree, local_name))
                if (
                    len(binding_nodes) != 1
                    or binding_nodes[0] is not node
                    or not self._type_checking_uses_are_closed(tree, local_name)
                ):
                    return False
                continue
            if not future_annotations:
                return False
            if any(
                isinstance(child, ast.Name)
                and child.id == local_name
                and isinstance(child.ctx, ast.Load)
                and id(child) not in annotation_ids
                for child in ast.walk(tree)
            ):
                return False
        return True

    def _type_checking_block_is_passive(self, source: Path, node: ast.If) -> bool:
        tree = self._tree(source)
        if node not in tree.body or not isinstance(node.test, ast.Name) or node.orelse:
            return False
        local_name = node.test.id
        bindings = list(_module_scope_symbol_bindings(tree, local_name))
        if len(bindings) != 1 or not isinstance(bindings[0], ast.ImportFrom):
            return False
        binding = bindings[0]
        return (
            binding.level == 0
            and binding.module == "typing"
            and any(
                alias.name == "TYPE_CHECKING" and (alias.asname or alias.name) == local_name
                for alias in binding.names
            )
            and self._typing_import_is_declaration_only(source, binding)
        )

    def _source_is_closed_lazy_facade(self, source: Path) -> bool:
        cached = self._lazy_facade_cache.get(source)
        if cached is not None:
            return cached
        result = False
        info = _module_name_for_path(source)
        if info is not None and info[1]:
            tree = self._tree(source)
            getter = _top_level_function(tree, "__getattr__")
            exports = _static_string_collection(source, tree, "__all__")
            if (
                getter is not None
                and _has_exact_positional_parameters(getter, "name")
                and exports is not None
                and _module_namespace_uses_are_closed(tree, source)
            ):
                parents = {
                    child: parent
                    for parent in ast.walk(tree)
                    for child in ast.iter_child_nodes(parent)
                }

                def enclosing_function(
                    node: ast.AST,
                ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
                    parent = parents.get(node)
                    while parent is not None:
                        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            return parent
                        parent = parents.get(parent)
                    return None

                import_bindings: list[tuple[str, str, ast.stmt]] = []
                for statement in tree.body:
                    if isinstance(statement, ast.Import):
                        for alias in statement.names:
                            if alias.name == "importlib":
                                import_bindings.append(
                                    (alias.asname or alias.name.split(".")[0], "module", statement)
                                )
                            elif alias.name.startswith("importlib."):
                                return False
                    elif isinstance(statement, ast.ImportFrom) and statement.module == "importlib":
                        if (
                            statement.level != 0
                            or not statement.names
                            or any(alias.name != "import_module" for alias in statement.names)
                        ):
                            return False
                        import_bindings.extend(
                            (alias.asname or alias.name, "callable", statement)
                            for alias in statement.names
                        )
                calls = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and _import_module_callable_is_stdlib(tree, node.func)
                ]
                exact_calls = bool(calls) and all(
                    enclosing_function(call) is not None
                    and len(call.args) == 1
                    and not call.keywords
                    for call in calls
                )
                exact_bindings = bool(import_bindings) and len(import_bindings) == 1
                if exact_calls and exact_bindings:
                    local_name, binding_kind, import_node = import_bindings[0]
                    bound_uses_are_calls = True
                    for child in ast.walk(tree):
                        if not (
                            isinstance(child, ast.Name)
                            and child.id == local_name
                            and isinstance(child.ctx, ast.Load)
                        ):
                            continue
                        parent = parents.get(child)
                        if binding_kind == "callable":
                            valid = isinstance(parent, ast.Call) and parent.func is child
                        else:
                            valid = (
                                isinstance(parent, ast.Attribute)
                                and parent.value is child
                                and parent.attr == "import_module"
                                and isinstance(parents.get(parent), ast.Call)
                                and parents.get(parent).func is parent
                            )
                        if not valid:
                            bound_uses_are_calls = False
                            break
                    result = bound_uses_are_calls and import_node in tree.body
        self._lazy_facade_cache[source] = result
        return result

    def _lazy_facade_importlib_statement_is_closed(
        self, source: Path, node: ast.Import | ast.ImportFrom
    ) -> bool:
        if not self._source_is_closed_lazy_facade(source):
            return False
        if isinstance(node, ast.Import):
            return (
                len(node.names) == 1
                and node.names[0].name == "importlib"
                and node in self._tree(source).body
            )
        return (
            node.level == 0
            and node.module == "importlib"
            and bool(node.names)
            and all(alias.name == "import_module" for alias in node.names)
            and node in self._tree(source).body
        )

    def resolve(self, source: Path, symbol: str) -> object:
        key = (source, symbol)
        if key in self._active:
            raise _UnresolvedExportDeclarationError(
                f"Unresolved export declaration cycle: {_export_source_locator(source)}:{symbol}"
            )
        self._active.add(key)
        try:
            tree = self._tree(source)
            bindings = list(_module_scope_symbol_bindings(tree, symbol))
            extensions = [
                node for node in bindings if self._direct_sequence_extension(tree, symbol, node)
            ]
            if extensions:
                values = self._closed_static_sequence(source, symbol)
                base = [node for node in bindings if node not in extensions]
                if len(base) != 1:
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved conditional/mutated exports: {_export_source_locator(source)}:{symbol}"
                    )
                self._resolved[key] = base[0].end_lineno
                return values
            updates = [node for node in bindings if self._direct_mapping_update(tree, symbol, node)]
            if updates:
                mapping = self._closed_static_mapping(source, symbol)
                base = [node for node in bindings if node not in updates]
                if len(base) != 1:
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved conditional/mutated exports: {_export_source_locator(source)}:{symbol}"
                    )
                self._resolved[key] = base[0].end_lineno
                return dict.fromkeys(mapping)
            direct_nodes = {id(node) for node in tree.body}
            for node in _module_scope_symbol_bindings(tree, symbol):
                supported_assignment = isinstance(node, (ast.Assign, ast.AnnAssign)) and any(
                    isinstance(target, ast.Name) and target.id == symbol
                    for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                )
                supported_import = isinstance(node, ast.ImportFrom) and all(
                    alias.name != "*" for alias in node.names
                )
                if id(node) not in direct_nodes or not (supported_assignment or supported_import):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved conditional/mutated exports: {_export_source_locator(source)}:{symbol}"
                    )
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
                            f"Unresolved mutated export declaration: {_export_source_locator(source)}:{symbol}"
                        )
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    function = node.value.func
                    if (
                        isinstance(function, ast.Attribute)
                        and isinstance(function.value, ast.Name)
                        and function.value.id == symbol
                    ):
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved mutated export declaration: {_export_source_locator(source)}:{symbol}"
                        )
            if len(declarations) == 1 and not imported:
                value = self._value(source, declarations[0])
                self._resolved[key] = declarations[0].end_lineno
                return value
            if len(imported) == 1 and not declarations:
                node, imported_name = imported[0]
                info = _module_name_for_path(source)
                if info is None:
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved export import source: {_export_source_locator(source)}"
                    )
                module = _resolve_import_module(*info, node)
                if module is None or not module.startswith("polisyos."):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved export import: {_export_source_locator(source)}:{symbol}"
                    )
                value = self.resolve(_facade_source_for(module), imported_name)
                self._resolved[key] = node.end_lineno
                return value
            raise _UnresolvedExportDeclarationError(
                f"Unresolved or ambiguous export declaration: {_export_source_locator(source)}:{symbol}"
            )
        finally:
            self._active.remove(key)

    def selected_collection_consumers_are_closed(self) -> bool:
        """Validate only selected declaration collections and their import-time aliases."""
        for source, symbol in self._resolved:
            tree = self._tree(source)
            bindings = list(_module_scope_symbol_bindings(tree, symbol))
            updates = [
                node
                for node in bindings
                if (source, id(node)) in self._allowed_mapping_updates
                or (source, id(node)) in self._allowed_sequence_extensions
            ]
            base = [node for node in bindings if node not in updates]
            if len(base) != 1 or base[0] not in tree.body:
                return False
            value = self.resolve(source, symbol)
            if isinstance(
                value, (list, tuple, set, dict)
            ) and not self._mapping_references_are_closed(source, symbol, base[0], updates):
                return False
        return True

    def _value(self, source: Path, node: ast.AST) -> object:
        if isinstance(node, ast.Name):
            self._allowed_reads.add((source, id(node)))
            return self.resolve(source, node.id)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values: list[object] = []
            for item in node.elts:
                if isinstance(item, ast.Starred):
                    expanded = self._value(source, item.value)
                    if not isinstance(expanded, (list, tuple, set, frozenset, dict)):
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved export expansion: {_export_source_locator(source)}"
                        )
                    # Python iterates a mapping over its keys. Match that source
                    # declaration semantics without evaluating the mapping owner.
                    values.extend(expanded)
                else:
                    values.append(self._value(source, item))
            if not all(isinstance(item, str) for item in values):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved non-string export item: {_export_source_locator(source)}"
                )
            if isinstance(node, ast.Tuple):
                return tuple(values)
            if isinstance(node, ast.Set):
                return set(values)
            return values
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if (
                node.func.id in {"set", "frozenset"}
                and len(node.args) == 1
                and not node.keywords
                and not any(_module_scope_symbol_bindings(self._tree(source), node.func.id))
            ):
                value = self._value(source, node.args[0])
                if isinstance(value, (list, tuple, set, frozenset)) and all(
                    isinstance(item, str) for item in value
                ):
                    self._allowed_calls.add((source, id(node)))
                    return set(value) if node.func.id == "set" else frozenset(value)
        if isinstance(node, ast.Dict):
            # Only keys contribute to iterating/sorting a manifest map. Its values
            # identify runtime owners, which this static reader does not execute.
            keys: dict[str, None] = {}
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None:
                    mapping = self._value(source, value)
                    if not isinstance(mapping, dict):
                        raise _UnresolvedExportDeclarationError(
                            f"Unresolved export mapping expansion: {_export_source_locator(source)}"
                        )
                    keys.update(mapping)
                elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys[key.value] = None
                else:
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved export mapping key: {_export_source_locator(source)}"
                    )
            return keys
        if isinstance(node, ast.JoinedStr):
            pieces: list[str] = []
            for item in node.values:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    pieces.append(item.value)
                    continue
                if (
                    not isinstance(item, ast.FormattedValue)
                    or item.conversion != -1
                    or item.format_spec is not None
                ):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved export string format: {_export_source_locator(source)}"
                    )
                value = self._value(source, item.value)
                if not isinstance(value, str):
                    raise _UnresolvedExportDeclarationError(
                        f"Unresolved non-string export format: {_export_source_locator(source)}"
                    )
                pieces.append(value)
            return "".join(pieces)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self._value(source, node.left), self._value(source, node.right)
            if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
                self._allowed_operations.add((source, id(node)))
                return [*left, *right]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"sorted", "list", "tuple"}
            and len(node.args) == 1
            and not node.keywords
        ):
            if any(_module_scope_symbol_bindings(self._tree(source), node.func.id)):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved shadowed export builtin: {_export_source_locator(source)}:{node.func.id}"
                )
            value = self._value(source, node.args[0])
            if isinstance(value, (dict, list, tuple)) and all(
                isinstance(item, str) for item in value
            ):
                self._allowed_calls.add((source, id(node)))
                return sorted(value) if node.func.id == "sorted" else list(value)
        strings = _string_list_value(node)
        if strings is not None:
            return strings
        raise _UnresolvedExportDeclarationError(
            f"Unresolved export expression: {_export_source_locator(source)}:{ast.unparse(node)}"
        )

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
            targets = (
                declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
            )
            if not all(isinstance(target, ast.Name) for target in targets):
                return False
            if not self._passive_container(value):
                return False
            for target in targets:
                bindings = list(_module_scope_symbol_bindings(tree, target.id))
                if len(bindings) != 1 or bindings[0] is not declaration:
                    return False
            for target in targets:
                self._resolved[(source, target.id)] = declaration.end_lineno
            self._allowed_reads.add((source, id(read)))
            return True
        return False

    def audit_consumers(self) -> None:
        """A finite binding must not escape the selected declaration grammar."""
        for source in self._trees:
            # Passive aliases/containers are finite only if their own complete
            # module-level consumer closure is audited as well.
            while True:
                symbols = {symbol for path, symbol in self._resolved if path == source}
                changed = False
                for node in _module_level_nodes(self._tree(source)):
                    if (
                        isinstance(node, ast.Name)
                        and isinstance(node.ctx, ast.Load)
                        and node.id in symbols
                        and (source, id(node)) not in self._allowed_reads
                    ):
                        if not self._admit_passive_alias(source, node):
                            raise _UnresolvedExportDeclarationError(
                                f"Unresolved export binding consumer: {_export_source_locator(source)}:{node.id}"
                            )
                        changed = True
                if not changed:
                    break
        audited: set[Path] = set()
        while pending := set(self._trees) - audited:
            for source in sorted(pending):
                for statement in self._tree(source).body:
                    self._audit_statement(source, statement)
                audited.add(source)

    def _refuse_effect(self, source: Path, node: ast.AST) -> None:
        raise _UnresolvedExportDeclarationError(
            f"Unresolved import-time {type(node).__name__} outside pure-declaration grammar: "
            f"{_export_source_locator(source)}:{ast.unparse(node)}"
        )

    def _import_source(self, source: Path, node: ast.ImportFrom | ast.Import, name: str) -> Path:
        if isinstance(node, ast.ImportFrom):
            info = _module_name_for_path(source)
            module = _resolve_import_module(*info, node) if info is not None else None
        else:
            module = name
        # An external import may execute arbitrary owner code. No package is
        # granted purity by its name, including standard-library imports.
        if module is None or not (module == "polisyos" or module.startswith("polisyos.")):
            self._refuse_effect(source, node)
        imported = _facade_source_for(module)
        self._tree(imported)
        self._passive_modules.add(imported)
        self._read_package_initializers(module)
        return imported

    def _read_package_initializers(self, module: str) -> None:
        parts = module.split(".")
        for length in range(1, len(parts)):
            initializer = SRC_ROOT.joinpath(*parts[:length], "__init__.py")
            # Canonical namespace-package directories have no initializer. The
            # admitted stat records this bounded absence; no loader is executed.
            if admitted_is_file(initializer, REPO_ROOT):
                self._tree(initializer)
                self._passive_modules.add(initializer)

    def _passive_binding(self, source: Path, name: str, *, module_binding: bool = False) -> None:
        key = (source, name)
        if key in self._passive_active:
            raise _UnresolvedExportDeclarationError(
                f"Unresolved passive binding cycle: {_export_source_locator(source)}:{name}"
            )
        bindings = list(_module_scope_symbol_bindings(self._tree(source), name))
        if not bindings and name in vars(builtins) and not module_binding:
            return
        updates = [
            node for node in bindings if self._direct_mapping_update(self._tree(source), name, node)
        ]
        extensions = [
            node
            for node in bindings
            if self._direct_sequence_extension(self._tree(source), name, node)
        ]
        if updates and extensions:
            raise _UnresolvedExportDeclarationError(
                f"Unresolved mixed passive collection updates: {_export_source_locator(source)}:{name}"
            )
        if updates or extensions:
            mutations = updates or extensions
            base = [node for node in bindings if node not in mutations]
            if len(base) != 1 or base[0] not in self._tree(source).body:
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved passive collection binding: {_export_source_locator(source)}:{name}"
                )
            try:
                if updates:
                    self._closed_static_mapping(source, name)
                else:
                    self._closed_static_sequence(source, name)
            except (OSError, ValueError, TypeError, SyntaxError) as exc:
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved passive collection binding: {_export_source_locator(source)}:{name}"
                ) from exc
            bindings = base
        if len(bindings) != 1 or bindings[0] not in self._tree(source).body:
            raise _UnresolvedExportDeclarationError(
                f"Unresolved passive binding: {_export_source_locator(source)}:{name}"
            )
        self._passive_active.add(key)
        try:
            node = bindings[0]
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                self._audit_expression(source, node.value)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._audit_function_header(source, node)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    if not _supported_future_import_is_passive(self._tree(source), node):
                        self._refuse_effect(source, node)
                    if not any((alias.asname or alias.name) == name for alias in node.names):
                        self._refuse_effect(source, node)
                elif self._typing_import_is_declaration_only(
                    source, node
                ) or self._lazy_facade_importlib_statement_is_closed(source, node):
                    if not any((alias.asname or alias.name) == name for alias in node.names):
                        self._refuse_effect(source, node)
                else:
                    imported = self._import_source(source, node, "")
                    alias = next(
                        alias for alias in node.names if (alias.asname or alias.name) == name
                    )
                    self._passive_binding(imported, alias.name, module_binding=True)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if (alias.asname or alias.name.split(".")[0]) == name:
                        self._import_source(source, node, alias.name)
            else:
                self._refuse_effect(source, node)
        finally:
            self._passive_active.remove(key)

    def _mapping_binding(self, source: Path, node: ast.AST) -> bool:
        if not isinstance(node, ast.Name):
            return False
        bindings = list(_module_scope_symbol_bindings(self._tree(source), node.id))
        if len(bindings) != 1 or bindings[0] not in self._tree(source).body:
            return False
        binding = bindings[0]
        if isinstance(binding, (ast.Assign, ast.AnnAssign)):
            return isinstance(binding.value, ast.Dict)
        if isinstance(binding, ast.ImportFrom):
            imported = self._import_source(source, binding, "")
            alias = next(
                alias for alias in binding.names if (alias.asname or alias.name) == node.id
            )
            imported_bindings = list(
                _module_scope_symbol_bindings(self._tree(imported), alias.name)
            )
            return (
                len(imported_bindings) == 1
                and isinstance(imported_bindings[0], (ast.Assign, ast.AnnAssign))
                and isinstance(imported_bindings[0].value, ast.Dict)
            )
        return False

    def _audit_expression(self, source: Path, node: ast.AST, *, allow_calls: bool = True) -> None:
        # literal_eval admits only closed literal values, never owner code or
        # foreign protocols. A malformed literal is unresolved, not executed.
        try:
            ast.literal_eval(node)
        except (ValueError, TypeError):
            pass
        else:
            return
        if isinstance(node, ast.Name):
            self._passive_binding(source, node.id)
            return
        if isinstance(node, ast.Starred):
            if not isinstance(node.value, ast.Name):
                self._refuse_effect(source, node)
            expanded = self._value(source, node.value)
            if not isinstance(expanded, (list, tuple, set, frozenset, dict)):
                self._refuse_effect(source, node)
            return
        if isinstance(node, (ast.List, ast.Tuple)):
            for value in node.elts:
                self._audit_expression(source, value, allow_calls=allow_calls)
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None:
                    if not self._mapping_binding(source, value):
                        self._refuse_effect(source, value)
                else:
                    try:
                        hash(ast.literal_eval(key))
                    except (ValueError, TypeError):
                        self._refuse_effect(source, key)
                self._audit_expression(source, value, allow_calls=allow_calls)
            return
        if (
            allow_calls
            and isinstance(node, ast.Call)
            and (
                (source, id(node)) in self._allowed_mapping_updates
                or (source, id(node)) in self._allowed_sequence_extensions
            )
        ):
            return
        if allow_calls and isinstance(node, ast.Call) and (source, id(node)) in self._allowed_calls:
            for value in node.args:
                self._audit_expression(source, value, allow_calls=allow_calls)
            return
        if (
            allow_calls
            and isinstance(node, ast.BinOp)
            and (source, id(node)) in self._allowed_operations
        ):
            self._audit_expression(source, node.left, allow_calls=allow_calls)
            self._audit_expression(source, node.right, allow_calls=allow_calls)
            return
        self._refuse_effect(source, node)

    def _future_annotations_are_passive(self, source: Path) -> bool:
        tree = self._tree(source)
        return any(
            isinstance(statement, ast.ImportFrom)
            and statement.module == "__future__"
            and statement.level == 0
            and any(alias.name == "annotations" for alias in statement.names)
            and _supported_future_import_is_passive(tree, statement)
            for statement in tree.body
        )

    def _audit_function_header(
        self, source: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        if node.decorator_list or node.type_params:
            self._refuse_effect(source, node)
        expressions = [*node.args.defaults, *node.args.kw_defaults]
        if not self._future_annotations_are_passive(source):
            expressions.append(node.returns)
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            arguments += [arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None]
            expressions += [arg.annotation for arg in arguments]
        for expression in expressions:
            if expression is not None:
                self._audit_expression(source, expression, allow_calls=False)
        # Function bodies are deliberately outside the import-time selector.

    def _audit_statement(self, source: Path, node: ast.stmt) -> None:
        closed_lazy_facade = self._source_is_closed_lazy_facade(source)
        if source in self._passive_modules:
            bound_names = {
                child.id
                for child in _module_level_nodes(node)
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
            }
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                bound_names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bound_names.add(node.name)
            # A passive value can still be bound to a module protocol name. The
            # explicit export declaration is always allowed; exact lazy-facade
            # hooks are allowed only after their finite namespace proof succeeds.
            allowed_dunders = {"__all__"}
            if closed_lazy_facade:
                allowed_dunders.update({"__getattr__", "__dir__"})
            if any(
                name.startswith("__") and name.endswith("__") and name not in allowed_dunders
                for name in bound_names
            ):
                self._refuse_effect(source, node)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not all(isinstance(target, ast.Name) for target in targets):
                self._refuse_effect(source, node)
            if isinstance(node, ast.AnnAssign) and not self._future_annotations_are_passive(source):
                self._audit_expression(source, node.annotation, allow_calls=False)
            if node.value is not None:
                self._audit_expression(source, node.value)
        elif isinstance(node, ast.Expr):
            if self._admit_static_mapping_update(source, node.value):
                return
            if self._admit_static_sequence_extension(source, node.value):
                return
            self._audit_expression(source, node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Function bodies do not execute during import. Passive dependencies
            # may define them only inside a closed lazy package facade; decorators,
            # defaults and annotations remain subject to the import-time audit.
            if source in self._passive_modules and not closed_lazy_facade:
                self._refuse_effect(source, node)
            self._audit_function_header(source, node)
        elif isinstance(node, ast.If) and self._type_checking_block_is_passive(source, node):
            return
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__" and _supported_future_import_is_passive(
                self._tree(source), node
            ):
                return
            if self._typing_import_is_declaration_only(source, node):
                return
            if self._lazy_facade_importlib_statement_is_closed(source, node):
                return
            if any(alias.name == "*" for alias in node.names):
                self._refuse_effect(source, node)
            imported = self._import_source(source, node, "")
            for alias in node.names:
                # Named import can invoke module __getattr__ for an absent name.
                # Only an actual passive owner binding avoids that protocol.
                self._passive_binding(imported, alias.name, module_binding=True)
        elif isinstance(node, ast.Import):
            if self._lazy_facade_importlib_statement_is_closed(source, node):
                return
            for alias in node.names:
                self._import_source(source, node, alias.name)
        elif not isinstance(node, ast.Pass):
            self._refuse_effect(source, node)


class _IncompleteExportDeclarationError(_UnresolvedExportDeclarationError):
    """A verified direct literal prefix remains below an unresolved full export contract."""

    def __init__(
        self,
        prefix: tuple[str, ...],
        *,
        reason: str = "Unresolved __all__.extend; literal prefix only, total unknown",
        exports_scope: str = "direct unconditional literal prefix; extension total unresolved",
    ) -> None:
        super().__init__(reason, prefix)
        self.prefix = prefix
        self.exports_scope = exports_scope


def _literal_prefix_before_extensions(tree: ast.Module) -> tuple[str, ...] | None:
    """Retain a direct literal prefix only when selected mutation stays finite."""
    bindings = list(_module_scope_symbol_bindings(tree, "__all__"))
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
    if prefix is None or not isinstance(declaration.value, ast.List):
        return None
    allowed_names = {id(targets[0])}
    for node in bindings:
        if node is declaration:
            continue
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "__all__"
            and node.func.attr == "extend"
            and len(node.args) == 1
            and not isinstance(node.args[0], ast.Starred)
            and not node.keywords
            and node.lineno > declaration.end_lineno
            and any(
                isinstance(statement, ast.Expr) and statement.value is node
                for statement in tree.body
            )
        ):
            return None
        allowed_names.add(id(node.func.value))
    if any(
        isinstance(node, ast.Name)
        and node.id == "__all__"
        and isinstance(node.ctx, ast.Load)
        and id(node) not in allowed_names
        for node in _module_scope_nodes(tree)
    ):
        return None
    return prefix


def _export_namespace_write_may_change(
    tree: ast.Module,
    selected_names: frozenset[str],
    source: Path | None = None,
) -> bool:
    """Reject reflective writes whose key can change a selected export or route."""
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    namespace_factories = {"globals", "locals", "vars"}
    builtin_modules: set[str] = set()
    sys_modules: set[str] = set()
    module_aliases: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "builtins":
                    builtin_modules.add(local)
                if alias.name == "sys":
                    sys_modules.add(local)
                if source is not None:
                    info = _module_name_for_path(source)
                    if info is not None and alias.name == info[0]:
                        module_aliases.add(local)
        elif isinstance(statement, ast.ImportFrom):
            if statement.module == "builtins" and statement.level == 0:
                for alias in statement.names:
                    if alias.name in {"globals", "locals", "vars"}:
                        namespace_factories.add(alias.asname or alias.name)
            if statement.module == "sys" and statement.level == 0:
                for alias in statement.names:
                    if alias.name == "modules":
                        sys_modules.add(alias.asname or alias.name)

    namespace_aliases: set[str] = set()
    module_object_aliases: set[str] = set()
    module_nodes = list(_module_scope_nodes(tree))

    def module_bindings(name: str) -> tuple[list[ast.AST], bool]:
        """Return module bindings without mistaking target reads for stores."""
        bindings: list[ast.AST] = []
        wildcard_import = False
        for statement in module_nodes:
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    local = alias.asname or alias.name.split(".", 1)[0]
                    if local == name:
                        bindings.append(statement)
            elif isinstance(statement, ast.ImportFrom):
                if statement.level == 0 and any(alias.name == "*" for alias in statement.names):
                    wildcard_import = True
                for alias in statement.names:
                    if alias.name != "*" and (alias.asname or alias.name) == name:
                        bindings.append(statement)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if statement.name == name:
                    bindings.append(statement)
            elif isinstance(statement, (ast.Assign, ast.Delete)):
                targets = statement.targets
                if any(
                    isinstance(child, ast.Name)
                    and child.id == name
                    and isinstance(child.ctx, (ast.Store, ast.Del))
                    for target in targets
                    for child in ast.walk(target)
                ):
                    bindings.append(statement)
            elif isinstance(
                statement, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.TypeAlias)
            ):
                target = statement.target if hasattr(statement, "target") else statement.name
                if any(
                    isinstance(child, ast.Name)
                    and child.id == name
                    and isinstance(child.ctx, (ast.Store, ast.Del))
                    for child in ast.walk(target)
                ):
                    bindings.append(statement)
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                if any(
                    isinstance(child, ast.Name)
                    and child.id == name
                    and isinstance(child.ctx, ast.Store)
                    for child in ast.walk(statement.target)
                ):
                    bindings.append(statement)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                if any(
                    item.optional_vars is not None
                    and any(
                        isinstance(child, ast.Name)
                        and child.id == name
                        and isinstance(child.ctx, ast.Store)
                        for child in ast.walk(item.optional_vars)
                    )
                    for item in statement.items
                ):
                    bindings.append(statement)
            elif (
                isinstance(statement, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar))
                and getattr(statement, "name", None) == name
            ):
                bindings.append(statement)
        return bindings, wildcard_import

    def imported_builtin_binding(name: str, allowed: set[str]) -> bool:
        bindings, wildcard_import = module_bindings(name)
        return (
            not wildcard_import
            and len(bindings) == 1
            and isinstance(bindings[0], ast.ImportFrom)
            and bindings[0].level == 0
            and bindings[0].module == "builtins"
            and any(
                alias.name in allowed and (alias.asname or alias.name) == name
                for alias in bindings[0].names
            )
        )

    def builtin_name_is_unshadowed(name: str) -> bool:
        bindings, wildcard_import = module_bindings(name)
        return (
            not wildcard_import
            and not bindings
            and name in {"globals", "locals", "vars", "getattr"}
        )

    def direct_builtin_factory(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            name = node.id
            return builtin_name_is_unshadowed(name) or imported_builtin_binding(
                name, {"globals", "locals", "vars"}
            )
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return node.value.id in builtin_modules and node.attr in {"globals", "locals", "vars"}
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
        ):
            return (
                builtin_name_is_unshadowed("getattr")
                and len(node.args) == 2
                and not node.keywords
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in builtin_modules
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in {"globals", "locals", "vars"}
            )
        return False

    def namespace_factory_call(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and not node.args
            and not node.keywords
            and direct_builtin_factory(node.func)
        )

    def namespace_factory_candidate(node: ast.AST) -> bool:
        """Recognize a shadowed factory-shaped call conservatively at write sites."""
        return (
            isinstance(node, ast.Call)
            and not node.args
            and not node.keywords
            and isinstance(node.func, ast.Name)
            and node.func.id in namespace_factories
        )

    def sys_modules_expression(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in sys_modules
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return node.value.id in sys_modules and node.attr == "modules"
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
        ):
            return (
                builtin_name_is_unshadowed("getattr")
                and len(node.args) == 2
                and not node.keywords
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in sys_modules
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "modules"
            )
        return False

    def module_object_expression(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in module_aliases or node.id in module_object_aliases
        return (
            isinstance(node, ast.Subscript)
            and sys_modules_expression(node.value)
            and isinstance(node.slice, ast.Name)
            and node.slice.id == "__name__"
        )

    def module_namespace_dict_expression(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "__dict__"
            and module_object_expression(node.value)
        )

    def namespace_dict_expression(node: ast.AST) -> bool:
        return (
            namespace_factory_call(node)
            or namespace_factory_candidate(node)
            or (isinstance(node, ast.Name) and node.id in namespace_aliases)
        )

    def is_static_empty_mapping_loop(node: ast.AST) -> bool:
        if (
            not isinstance(node, ast.For)
            or node.orelse
            or not isinstance(node.iter, ast.Call)
            or node.iter.args
            or node.iter.keywords
            or not isinstance(node.iter.func, ast.Attribute)
            or node.iter.func.attr != "items"
            or not isinstance(node.iter.func.value, ast.Name)
        ):
            return False
        mapping_name = node.iter.func.value.id
        definitions: list[ast.Name] = []
        for statement in tree.body:
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if (
                len(targets) == 1
                and isinstance(targets[0], ast.Name)
                and targets[0].id == mapping_name
                and isinstance(statement.value, ast.Dict)
                and not statement.value.keys
            ):
                definitions.append(targets[0])
        if len(definitions) != 1:
            return False
        definition_target = definitions[0]
        loop_read = node.iter.func.value
        if any(
            isinstance(child, (ast.Global, ast.Nonlocal)) and mapping_name in child.names
            for child in ast.walk(tree)
        ):
            return False

        def is_closed_read(child: ast.Name) -> bool:
            attribute = parents.get(child)
            if not isinstance(attribute, ast.Attribute):
                return False
            call = parents.get(attribute)
            if not (
                isinstance(child.ctx, ast.Load)
                and attribute.value is child
                and isinstance(call, ast.Call)
                and call.func is attribute
                and not call.keywords
                and not any(isinstance(argument, ast.Starred) for argument in call.args)
            ):
                return False
            return (attribute.attr == "items" and not call.args) or (
                attribute.attr == "get" and 1 <= len(call.args) <= 2
            )

        return all(
            child is definition_target or child is loop_read or is_closed_read(child)
            for child in ast.walk(tree)
            if isinstance(child, ast.Name) and child.id == mapping_name
        )

    empty_mapping_loops = {node for node in ast.walk(tree) if is_static_empty_mapping_loop(node)}

    def inside_static_empty_mapping_body(node: ast.AST) -> bool:
        current = node
        while current in parents:
            parent = parents[current]
            if parent in empty_mapping_loops and any(
                current is statement for statement in parent.body
            ):
                return True
            current = parent
        return False

    changed = True
    while changed:
        changed = False
        for node in module_nodes:
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                continue
            value = node.value
            if value is None:
                continue
            target = targets[0].id
            if target not in namespace_aliases and (
                namespace_dict_expression(value)
                or (isinstance(value, ast.Name) and value.id in namespace_aliases)
            ):
                namespace_aliases.add(target)
                changed = True
            if target not in module_object_aliases and (
                module_object_expression(value)
                or (isinstance(value, ast.Name) and value.id in module_object_aliases)
            ):
                module_object_aliases.add(target)
                changed = True

    for node in ast.walk(tree):
        if isinstance(node, ast.Global) and selected_names.intersection(node.names):
            return True
        if isinstance(node, ast.Nonlocal) and selected_names.intersection(node.names):
            return True

    top_getters = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__"
    ]

    def enclosing_function(node: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        parent = parents.get(node)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return parent
            parent = parents.get(parent)
        return None

    def allowed_lazy_cache(target: ast.AST, statement: ast.AST) -> bool:
        return (
            len(top_getters) == 1
            and isinstance(target, ast.Subscript)
            and namespace_factory_call(target.value)
            and isinstance(target.slice, ast.Name)
            and target.slice.id == "name"
            and isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and statement.targets[0] is target
            and isinstance(statement.value, ast.Name)
            and enclosing_function(statement) is top_getters[0]
            and _has_exact_positional_parameters(top_getters[0], "name")
        )

    collection_aliases = {"__all__"}
    collection_helpers: set[str] = set()

    def selected_collection_expression(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in collection_aliases
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in collection_helpers
            and not node.args
            and not node.keywords
        )

    changed = True
    top_functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    while changed:
        changed = False
        for statement in tree.body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target = statement.targets[0]
                if (
                    isinstance(target, ast.Name)
                    and target.id not in collection_aliases
                    and selected_collection_expression(statement.value)
                ):
                    collection_aliases.add(target.id)
                    changed = True
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                if (
                    statement.target.id not in collection_aliases
                    and statement.value is not None
                    and selected_collection_expression(statement.value)
                ):
                    collection_aliases.add(statement.target.id)
                    changed = True
        for name, function in top_functions.items():
            if name in collection_helpers:
                continue
            if isinstance(function, ast.FunctionDef):
                returns = _function_return_expressions(function)
            else:
                returns = []
            if returns and all(selected_collection_expression(value) for value in returns):
                collection_helpers.add(name)
                changed = True

    collection_mutators = {
        "add",
        "append",
        "clear",
        "discard",
        "extend",
        "insert",
        "pop",
        "popitem",
        "remove",
        "reverse",
        "setdefault",
        "sort",
        "update",
    }
    allowed_sequence_extensions: set[int] = set()
    if source is not None:
        declaration_resolver = _StaticExportResolver(source, tree)
        allowed_sequence_extensions = {
            id(statement.value)
            for statement in tree.body
            if isinstance(statement, ast.Expr)
            and declaration_resolver._admit_static_sequence_extension(source, statement.value)
        }
    for node in ast.walk(tree):
        if inside_static_empty_mapping_body(node):
            continue
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in collection_mutators
        ):
            continue
        if selected_collection_expression(node.func.value):
            if node.func.attr == "extend" and id(node) in allowed_sequence_extensions:
                continue
            return True
        if (
            isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr in selected_names
            and module_object_expression(node.func.value.value)
        ):
            return True
        if isinstance(node, (ast.Assign, ast.Delete, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            if any(
                isinstance(target, ast.Subscript) and selected_collection_expression(target.value)
                for target in targets
            ):
                return True

    for node in ast.walk(tree):
        if inside_static_empty_mapping_body(node):
            continue
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval"}:
                return True
            if isinstance(node.func, ast.Attribute) and namespace_dict_expression(node.func.value):
                if node.func.attr in {"clear", "popitem", "__setitem__", "__delitem__"}:
                    return True
                if node.func.attr in {"update", "setdefault", "pop"}:
                    if not node.args:
                        return True
                    try:
                        value = ast.literal_eval(node.args[0])
                    except (ValueError, TypeError):
                        return True
                    keys = set(value) if isinstance(value, dict) else {value}
                    if not all(isinstance(key, str) for key in keys):
                        return True
                    if keys & selected_names:
                        return True
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in {"setattr", "delattr"}
                and len(node.args) >= 2
                and (
                    namespace_dict_expression(node.args[0])
                    or module_object_expression(node.args[0])
                )
            ):
                try:
                    attribute = ast.literal_eval(node.args[1])
                except (ValueError, TypeError):
                    return True
                if not isinstance(attribute, str) or attribute in selected_names:
                    return True

        targets: list[ast.AST] = []
        if isinstance(node, (ast.Assign, ast.Delete)):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Subscript) and (
                namespace_dict_expression(target.value)
                or module_namespace_dict_expression(target.value)
            ):
                try:
                    key = ast.literal_eval(target.slice)
                except (ValueError, TypeError):
                    if allowed_lazy_cache(target, node):
                        continue
                    return True
                if (not isinstance(key, str) or key in selected_names) and not allowed_lazy_cache(
                    target, node
                ):
                    return True
            if (
                isinstance(target, ast.Attribute)
                and target.attr in selected_names
                and (
                    namespace_dict_expression(target.value)
                    or module_object_expression(target.value)
                    or module_namespace_dict_expression(target.value)
                )
            ):
                return True
    return False


def _module_scope_binding_index(
    tree: ast.Module,
) -> tuple[dict[str, list[ast.AST]], list[ast.ImportFrom]]:
    """Index actual module bindings once for the selected export dependency slice."""
    bindings: dict[str, list[ast.AST]] = {}
    wildcard_imports: list[ast.ImportFrom] = []
    for node in _module_scope_nodes(tree):
        targets: list[ast.AST] = []
        if isinstance(node, (ast.Assign, ast.Delete)):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.TypeAlias)):
            targets = [node.target if hasattr(node, "target") else node.name]
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
        for target in targets:
            for child in ast.walk(target):
                if isinstance(child, ast.Name):
                    bindings.setdefault(child.id, []).append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or (
            isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name
        ):
            bindings.setdefault(node.name, []).append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                wildcard_imports.append(node)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or (
                    alias.name.split(".")[0] if isinstance(node, ast.Import) else alias.name
                )
                bindings.setdefault(local, []).append(node)
    return bindings, wildcard_imports


def _indexed_symbol_bindings(
    binding_index: dict[str, list[ast.AST]],
    wildcard_imports: list[ast.ImportFrom],
    symbol: str,
) -> list[ast.AST]:
    return [*binding_index.get(symbol, ()), *wildcard_imports]


def _future_public_binding(tree: ast.Module, symbol: str) -> ast.ImportFrom | None:
    """Resolve a legal named future import as its real module binding."""
    if list(_module_scope_symbol_bindings(tree, symbol)):
        return None
    matches: list[ast.ImportFrom] = []
    for statement in tree.body:
        if (
            not isinstance(statement, ast.ImportFrom)
            or statement.module != "__future__"
            or not _supported_future_import_is_passive(tree, statement)
        ):
            continue
        aliases = [
            alias
            for alias in statement.names
            if alias.name != "*" and (alias.asname or alias.name) == symbol
        ]
        if aliases:
            if len(aliases) != 1:
                return None
            matches.append(statement)
    return matches[0] if len(matches) == 1 else None


def _direct_public_binding(
    tree: ast.Module,
    symbol: str,
    bindings: list[ast.AST] | None = None,
) -> ast.AST | None:
    bindings = list(_module_scope_symbol_bindings(tree, symbol)) if bindings is None else bindings
    if not bindings:
        future_binding = _future_public_binding(tree, symbol)
        if future_binding is not None:
            return future_binding
    if len(bindings) != 1 or bindings[0] not in tree.body:
        return None
    binding = bindings[0]
    if isinstance(binding, ast.Assign):
        if (
            len(binding.targets) == 1
            and isinstance(binding.targets[0], ast.Name)
            and binding.targets[0].id == symbol
            and binding.value is not None
        ):
            return binding
        return None
    if isinstance(binding, ast.AnnAssign):
        if (
            isinstance(binding.target, ast.Name)
            and binding.target.id == symbol
            and binding.value is not None
        ):
            return binding
        return None
    if isinstance(binding, ast.ImportFrom):
        if binding.module == "__future__":
            return None
        matches = [
            alias
            for alias in binding.names
            if alias.name != "*" and (alias.asname or alias.name) == symbol
        ]
        return binding if len(matches) == 1 else None
    if isinstance(binding, ast.Import):
        matches = [
            alias for alias in binding.names if (alias.asname or alias.name.split(".")[0]) == symbol
        ]
        return binding if len(matches) == 1 else None
    if isinstance(binding, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return binding
    if isinstance(binding, ast.TypeAlias):
        return binding
    return None


def _public_alias_target_is_bound(
    tree: ast.Module,
    symbol: str,
    seen: frozenset[str] = frozenset(),
    *,
    binding_index: dict[str, list[ast.AST]] | None = None,
    wildcard_imports: list[ast.ImportFrom] | None = None,
) -> bool:
    if symbol in seen:
        return False
    if symbol in vars(builtins):
        return True
    bindings = (
        list(_module_scope_symbol_bindings(tree, symbol))
        if binding_index is None or wildcard_imports is None
        else _indexed_symbol_bindings(binding_index, wildcard_imports, symbol)
    )
    binding = _direct_public_binding(tree, symbol, bindings)
    if binding is None:
        return False
    if isinstance(binding, (ast.Assign, ast.AnnAssign)) and isinstance(binding.value, ast.Name):
        return _public_alias_target_is_bound(
            tree,
            binding.value.id,
            seen | {symbol},
            binding_index=binding_index,
            wildcard_imports=wildcard_imports,
        )
    return True


def _lazy_export_provider_is_declared(tree: ast.Module) -> bool:
    getter = _top_level_function(tree, "__getattr__")
    bindings = list(_module_scope_symbol_bindings(tree, "__getattr__"))
    return (
        getter is not None
        and len(bindings) == 1
        and bindings[0] is getter
        and _has_exact_positional_parameters(getter, "name")
    )


def _lazy_owner_map_accesses(getter: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Find finite owner maps selected by the lazy export name."""
    names: set[str] = set()
    parents = {
        child: parent for parent in ast.walk(getter) for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(getter):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and isinstance(node.slice, ast.Name)
            and node.slice.id == "name"
        ):
            names.add(node.value.id)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
            if node.left.id == "name" and len(node.ops) == len(node.comparators):
                for op, comparator in zip(node.ops, node.comparators, strict=True):
                    if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comparator, ast.Name):
                        names.add(comparator.id)
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "name"
            and not node.keywords
        ):
            names.add(node.func.value.id)
        passed_name = any(
            isinstance(argument, ast.Name) and argument.id == "name"
            for argument in (*node.args, *(keyword.value for keyword in node.keywords))
        )
        direct_return = isinstance(parents.get(node), ast.Return) and parents[node].value is node
        owner_maps = [
            keyword.value.id
            for keyword in node.keywords
            if keyword.arg in {"exports", "owner_map", "mapping"}
            and isinstance(keyword.value, ast.Name)
        ]
        if passed_name and direct_return:
            names.update(owner_maps)
    names.discard("name")
    return names


def _owner_target_is_valid(value: object, export_name: str) -> bool:
    if isinstance(value, str):
        module, symbol = value, export_name
    elif (
        isinstance(value, tuple)
        and len(value) == 2
        and all(isinstance(item, str) for item in value)
    ):
        module, symbol = value
    else:
        return False
    return (
        module.startswith("polisyos.")
        and all(part.isidentifier() for part in module.split("."))
        and bool(symbol)
        and symbol.isidentifier()
    )


def _derived_lazy_owner_map(
    source: Path,
    tree: ast.Module,
    target_symbol: str,
) -> dict[str, str] | None:
    """Unfold a closed grouped-owner map into a name-to-module lazy route."""
    info = _module_name_for_path(source)
    if info is None:
        return None
    module = info[0]
    resolver = _StaticExportResolver(source, tree)
    target_bindings = list(_module_scope_symbol_bindings(tree, target_symbol))
    base = [
        node
        for node in target_bindings
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and getattr(node, "value", None) is not None
        and isinstance(node.value, ast.Dict)
        and node in tree.body
    ]
    if len(base) != 1 or not isinstance(base[0].value, ast.Dict) or base[0].value.keys:
        return None
    loops: list[tuple[ast.For, dict[str, str]]] = []
    for outer in tree.body:
        if not isinstance(outer, ast.For) or outer.orelse:
            continue
        if (
            not isinstance(outer.target, (ast.Tuple, ast.List))
            or len(outer.target.elts) != 2
            or not all(isinstance(item, ast.Name) for item in outer.target.elts)
            or not isinstance(outer.iter, ast.Call)
            or outer.iter.args
            or outer.iter.keywords
            or not isinstance(outer.iter.func, ast.Attribute)
            or outer.iter.func.attr != "items"
            or not isinstance(outer.iter.func.value, ast.Name)
        ):
            continue
        relative_name, group_name = (item.id for item in outer.target.elts)
        group_symbol = outer.iter.func.value.id
        if len(outer.body) != 2:
            continue
        owner_assignment, inner = outer.body
        if (
            not isinstance(owner_assignment, ast.Assign)
            or len(owner_assignment.targets) != 1
            or not isinstance(owner_assignment.targets[0], ast.Name)
            or not isinstance(owner_assignment.value, ast.JoinedStr)
            or not isinstance(inner, ast.For)
            or inner.orelse
            or not isinstance(inner.target, ast.Name)
            or not isinstance(inner.iter, ast.Name)
            or inner.iter.id != group_name
            or len(inner.body) != 1
            or not isinstance(inner.body[0], ast.Assign)
            or len(inner.body[0].targets) != 1
            or not isinstance(inner.body[0].targets[0], ast.Subscript)
        ):
            continue
        target = inner.body[0].targets[0]
        if (
            not isinstance(target.value, ast.Name)
            or target.value.id != target_symbol
            or not isinstance(target.slice, ast.Name)
            or target.slice.id != inner.target.id
            or not isinstance(inner.body[0].value, ast.Name)
            or inner.body[0].value.id != owner_assignment.targets[0].id
        ):
            continue
        formatted = [
            value
            for value in owner_assignment.value.values
            if isinstance(value, ast.FormattedValue)
        ]
        constants = [
            value.value
            for value in owner_assignment.value.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        ]
        if (
            len(formatted) != 1
            or not isinstance(formatted[0].value, ast.Name)
            or formatted[0].value.id != relative_name
            or formatted[0].conversion != -1
            or formatted[0].format_spec is not None
            or "".join(constants) != module
        ):
            continue
        try:
            groups = resolver._closed_static_mapping(source, group_symbol)
        except (OSError, ValueError, TypeError, SyntaxError):
            continue
        if not groups or any(
            not isinstance(relative, str)
            or not relative.startswith(".")
            or not isinstance(names, (tuple, list))
            or not all(isinstance(name, str) and name.isidentifier() for name in names)
            for relative, names in groups.items()
        ):
            continue
        derived: dict[str, str] = {}
        invalid_owner = False
        for relative, names in groups.items():
            owner = f"{module}{relative}"
            if not all(part.isidentifier() for part in owner.split(".")):
                invalid_owner = True
                break
            for name in names:
                # Match ordered dict iteration and the facade's repeated indexed
                # assignment: the last explicit owner wins, as in Python source.
                derived[name] = owner
        if invalid_owner:
            continue
        loops.append((outer, derived))
    if len(loops) != 1:
        return None
    loop, mapping = loops[0]
    writes = [
        node
        for node in target_bindings
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr, ast.For, ast.AsyncFor))
        and node is not base[0]
    ]
    expected_writes = {id(loop)}
    inner_assign = loop.body[1].body[0]
    expected_writes.add(id(inner_assign))
    for node in tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == target_symbol
            and node.value.func.attr == "update"
        ):
            call = node.value
            if len(call.args) != 1 or call.keywords or node.lineno <= loop.end_lineno:
                return None
            try:
                addition = resolver._closed_static_value(source, call.args[0], {})
            except (OSError, ValueError, TypeError, SyntaxError):
                return None
            if not isinstance(addition, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in addition.items()
            ):
                return None
            mapping.update(addition)
            expected_writes.add(id(call))
    if any(id(node) not in expected_writes for node in writes):
        return None
    if not _StaticExportResolver._mapping_values_are_immutable(mapping):
        return None
    return mapping


def _guarded_export_names(test: ast.AST) -> frozenset[str]:
    """Read finite equality or membership guards over the lazy name parameter."""
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1):
        return frozenset()
    left, op, right = test.left, test.ops[0], test.comparators[0]
    if isinstance(left, ast.Name) and left.id == "name":
        if (
            isinstance(op, ast.Eq)
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)
        ):
            return frozenset({right.value})
        if isinstance(op, ast.In) and isinstance(right, (ast.Set, ast.List, ast.Tuple)):
            values = [item.value for item in right.elts if isinstance(item, ast.Constant)]
            if len(values) == len(right.elts) and all(isinstance(value, str) for value in values):
                return frozenset(values)
    if isinstance(left, ast.Constant) and isinstance(left.value, str) and isinstance(op, ast.In):
        if isinstance(right, ast.Name) and right.id == "name":
            return frozenset({left.value})
    return frozenset()


def _lazy_import_module_target(
    module: str, source: Path, tree: ast.Module, call: ast.Call, export_name: str
) -> str | None:
    """Resolve a literal import_module call to its requested logical module."""
    if not call.args or not _import_module_callable_is_stdlib(tree, call.func):
        return None
    if len(call.args) > 2 or any(keyword.arg != "package" for keyword in call.keywords):
        return None
    package = None
    if len(call.args) == 2 or call.keywords:
        package_node = call.args[1] if len(call.args) == 2 else call.keywords[0].value
        if not (isinstance(package_node, ast.Name) and package_node.id == "__name__"):
            return None
        package = module
    imported = _static_module_name(call.args[0], parent_module=module, alias_name=export_name)
    if imported is None:
        return None
    if imported.startswith("."):
        if package is None:
            return None
        info = _module_name_for_path(source)
        if info is None:
            return None
        suffix = imported.lstrip(".")
        level = len(imported) - len(suffix)
        return _resolve_import_module(
            module, info[1], ast.ImportFrom(module=suffix or None, names=[], level=level)
        )
    return imported if imported.startswith("polisyos.") else None


def _lazy_function_literal_mapping_routes(
    source: Path, tree: ast.Module, names: frozenset[str]
) -> frozenset[str]:
    """Resolve a local finite name-to-owner map consumed by an import/getattr route."""
    info = _module_name_for_path(source)
    getter = _top_level_function(tree, "__getattr__")
    if info is None or getter is None or not _has_exact_positional_parameters(getter, "name"):
        return frozenset()
    body = _function_body_without_docstring(getter)
    resolver = _StaticExportResolver(source, tree)
    routes: set[str] = set()
    for assignment in body:
        if (
            not isinstance(assignment, ast.Assign)
            or len(assignment.targets) != 1
            or not isinstance(assignment.targets[0], ast.Name)
            or not isinstance(assignment.value, ast.Dict)
        ):
            continue
        map_name = assignment.targets[0].id
        try:
            mapping = resolver._closed_static_value(source, assignment.value, {})
        except (OSError, ValueError, TypeError, SyntaxError):
            continue
        if (
            not isinstance(mapping, dict)
            or not mapping
            or any(
                not isinstance(key, str) or not _owner_target_is_valid(value, key)
                for key, value in mapping.items()
            )
        ):
            continue
        guards = [
            statement
            for statement in body
            if isinstance(statement, ast.If)
            and not statement.orelse
            and isinstance(statement.test, ast.Compare)
            and isinstance(statement.test.left, ast.Name)
            and statement.test.left.id == "name"
            and len(statement.test.ops) == 1
            and isinstance(statement.test.ops[0], ast.In)
            and len(statement.test.comparators) == 1
            and isinstance(statement.test.comparators[0], ast.Name)
            and statement.test.comparators[0].id == map_name
        ]
        if len(guards) != 1 or body.index(assignment) >= body.index(guards[0]):
            continue
        branch = guards[0].body
        if len(branch) not in {4, 5}:
            continue
        unpack, import_assignment, value_assignment = branch[:3]
        if (
            not isinstance(unpack, ast.Assign)
            or len(unpack.targets) != 1
            or not isinstance(unpack.targets[0], (ast.Tuple, ast.List))
            or len(unpack.targets[0].elts) != 2
            or not all(isinstance(item, ast.Name) for item in unpack.targets[0].elts)
            or not isinstance(unpack.value, ast.Subscript)
            or not isinstance(unpack.value.value, ast.Name)
            or unpack.value.value.id != map_name
            or not isinstance(unpack.value.slice, ast.Name)
            or unpack.value.slice.id != "name"
            or not isinstance(import_assignment, ast.Assign)
            or len(import_assignment.targets) != 1
            or not isinstance(import_assignment.targets[0], ast.Name)
            or not isinstance(import_assignment.value, ast.Call)
            or not isinstance(import_assignment.value.func, ast.Attribute)
            or import_assignment.value.func.attr != "import_module"
            or not isinstance(import_assignment.value.func.value, ast.Name)
            or not isinstance(value_assignment, ast.Assign)
            or len(value_assignment.targets) != 1
            or not isinstance(value_assignment.targets[0], ast.Name)
            or not isinstance(value_assignment.value, ast.Call)
            or not isinstance(value_assignment.value.func, ast.Name)
            or value_assignment.value.func.id != "getattr"
            or len(value_assignment.value.args) != 2
            or value_assignment.value.keywords
        ):
            continue
        module_name, attribute_name = (item.id for item in unpack.targets[0].elts)
        module_local = import_assignment.targets[0].id
        imported = import_assignment.value
        value_local = value_assignment.targets[0].id
        if (
            len(imported.args) != 1
            or not isinstance(imported.args[0], ast.Name)
            or imported.args[0].id != module_name
            or not isinstance(value_assignment.value.args[0], ast.Name)
            or value_assignment.value.args[0].id != module_local
            or not isinstance(value_assignment.value.args[1], ast.Name)
            or value_assignment.value.args[1].id != attribute_name
            or not isinstance(branch[-1], ast.Return)
            or not isinstance(branch[-1].value, ast.Name)
            or branch[-1].value.id != value_local
        ):
            continue
        module_importlib_imports = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.Import)
            and any(
                alias.name == "importlib" and (alias.asname or alias.name) == "importlib"
                for alias in statement.names
            )
        ]
        module_importlib_is_unique = (
            len(module_importlib_imports) == 1
            and list(_module_scope_symbol_bindings(tree, "importlib")) == module_importlib_imports
        )
        local_importlib_is_unique = _local_getter_importlib_binding(tree, getter, "importlib")
        if (
            not (module_importlib_is_unique or local_importlib_is_unique)
            or not isinstance(imported.func.value, ast.Name)
            or imported.func.value.id != "importlib"
            or list(_module_scope_symbol_bindings(tree, "getattr"))
            or any(
                isinstance(node, ast.Name)
                and node.id == "getattr"
                and isinstance(node.ctx, (ast.Store, ast.Del))
                for node in ast.walk(getter)
            )
        ):
            continue
        cache = branch[3:-1]
        if len(cache) > 1 or any(
            not isinstance(statement, ast.Assign)
            or len(statement.targets) != 1
            or not isinstance(statement.targets[0], ast.Subscript)
            or not isinstance(statement.targets[0].value, ast.Call)
            or not isinstance(statement.targets[0].value.func, ast.Name)
            or statement.targets[0].value.func.id != "globals"
            or not isinstance(statement.targets[0].slice, ast.Name)
            or statement.targets[0].slice.id != "name"
            or not isinstance(statement.value, ast.Name)
            or statement.value.id != value_local
            for statement in cache
        ):
            continue
        map_stores = [
            node
            for node in ast.walk(getter)
            if isinstance(node, ast.Name)
            and node.id == map_name
            and isinstance(node.ctx, ast.Store)
        ]
        map_loads = [
            node
            for node in ast.walk(getter)
            if isinstance(node, ast.Name) and node.id == map_name and isinstance(node.ctx, ast.Load)
        ]
        parents = {
            child: parent for parent in ast.walk(getter) for child in ast.iter_child_nodes(parent)
        }
        allowed_loads = 0
        for load in map_loads:
            parent = parents.get(load)
            if (
                isinstance(parent, ast.Compare)
                and load in parent.comparators
                and any(isinstance(op, ast.In) for op in parent.ops)
            ) or (isinstance(parent, ast.Subscript) and parent.value is load):
                allowed_loads += 1
            else:
                allowed_loads = -100
                break
        if len(map_stores) != 1 or allowed_loads != 2:
            continue
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == map_name
            for node in ast.walk(getter)
        ):
            continue
        routes.update(key for key in names if key in mapping)
    return frozenset(routes)


def _lazy_attribute_map_routes(
    source: Path, tree: ast.Module, names: frozenset[str]
) -> frozenset[str]:
    """Resolve a closed name-to-attribute map against one literal lazy module owner."""
    info = _module_name_for_path(source)
    getter = _top_level_function(tree, "__getattr__")
    if (
        info is None
        or getter is None
        or not _has_exact_positional_parameters(getter, "name")
        or list(_module_scope_symbol_bindings(tree, "getattr"))
        or any(
            isinstance(node, ast.Name)
            and node.id == "getattr"
            and isinstance(node.ctx, (ast.Store, ast.Del))
            for node in ast.walk(getter)
        )
    ):
        return frozenset()
    resolver = _StaticExportResolver(source, tree)
    for map_name in sorted(_lazy_owner_map_accesses(getter)):
        try:
            mapping = resolver._closed_static_mapping(source, map_name)
        except (OSError, ValueError, TypeError, SyntaxError):
            continue
        if (
            not isinstance(mapping, dict)
            or not mapping
            or any(
                not isinstance(key, str) or not isinstance(value, str) or not value.isidentifier()
                for key, value in mapping.items()
            )
        ):
            continue
        parents = {
            child: parent for parent in ast.walk(getter) for child in ast.iter_child_nodes(parent)
        }
        for call in ast.walk(getter):
            if (
                not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or call.func.id != "getattr"
                or len(call.args) != 2
                or call.keywords
                or not isinstance(call.args[0], ast.Name)
            ):
                continue
            selected = call.args[1]
            selected_map = (
                isinstance(selected, ast.Subscript)
                and isinstance(selected.value, ast.Name)
                and selected.value.id == map_name
                and isinstance(selected.slice, ast.Name)
                and selected.slice.id == "name"
            ) or (
                isinstance(selected, ast.Call)
                and isinstance(selected.func, ast.Attribute)
                and selected.func.attr == "get"
                and isinstance(selected.func.value, ast.Name)
                and selected.func.value.id == map_name
                and len(selected.args) == 1
                and isinstance(selected.args[0], ast.Name)
                and selected.args[0].id == "name"
                and not selected.keywords
            )
            if not selected_map:
                continue
            owner_local = call.args[0].id
            owner_assignments = [
                node
                for node in ast.walk(getter)
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == owner_local
                and isinstance(node.value, ast.Call)
                and _import_module_callable_is_stdlib(tree, node.value.func)
                and len(node.value.args) == 1
                and not node.value.keywords
                and isinstance(node.value.args[0], ast.Constant)
                and isinstance(node.value.args[0].value, str)
                and node.value.args[0].value.startswith("polisyos.")
            ]
            if len(owner_assignments) != 1:
                continue
            returned_names = {
                node.value.id
                for node in ast.walk(getter)
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Name)
            }
            parent = parents.get(call)
            if isinstance(parent, ast.Assign):
                if (
                    len(parent.targets) != 1
                    or not isinstance(parent.targets[0], ast.Name)
                    or parent.targets[0].id not in returned_names
                ):
                    continue
            elif not isinstance(parent, ast.Return):
                continue
            guarded = [
                node
                for node in ast.walk(getter)
                if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "name"
                and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.NotIn)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Name)
                and node.test.comparators[0].id == map_name
                and any(isinstance(child, ast.Raise) for child in node.body)
                and node.lineno < call.lineno
            ]
            if len(guarded) == 1:
                return frozenset(key for key in names if key in mapping)
    return frozenset()


def _guarded_literal_lazy_owner_routes(source: Path, tree: ast.Module) -> dict[str, str]:
    """Follow a closed membership guard to a literal same-name owner lookup."""
    info = _module_name_for_path(source)
    getter = _top_level_function(tree, "__getattr__")
    if (
        info is None
        or getter is None
        or getter.decorator_list
        or not _has_exact_positional_parameters(getter, "name")
    ):
        return {}
    body = _function_body_without_docstring(getter)
    if len(body) not in {3, 4}:
        return {}
    guard, assignment, returned = body[0], body[1], body[-1]
    if not (
        isinstance(guard, ast.If)
        and not guard.orelse
        and isinstance(guard.test, ast.Compare)
        and isinstance(guard.test.left, ast.Name)
        and guard.test.left.id == "name"
        and len(guard.test.ops) == 1
        and isinstance(guard.test.ops[0], ast.NotIn)
        and len(guard.test.comparators) == 1
        and isinstance(guard.test.comparators[0], ast.Name)
        and guard.test.comparators[0].id == "__all__"
        and len(guard.body) == 1
        and isinstance(guard.body[0], ast.Raise)
        and isinstance(guard.body[0].exc, ast.Call)
        and isinstance(guard.body[0].exc.func, ast.Name)
        and guard.body[0].exc.func.id == "AttributeError"
        and guard.body[0].cause is None
        and isinstance(assignment, ast.Assign)
        and len(assignment.targets) == 1
        and isinstance(assignment.targets[0], ast.Name)
        and isinstance(assignment.value, ast.Call)
        and isinstance(assignment.value.func, ast.Name)
        and assignment.value.func.id == "getattr"
        and len(assignment.value.args) == 2
        and not assignment.value.keywords
        and isinstance(assignment.value.args[0], ast.Call)
        and isinstance(assignment.value.args[1], ast.Name)
        and assignment.value.args[1].id == "name"
        and isinstance(returned, ast.Return)
        and isinstance(returned.value, ast.Name)
        and returned.value.id == assignment.targets[0].id
    ):
        return {}
    local = assignment.targets[0].id
    owner_call = assignment.value.args[0]
    if (
        not owner_call.args
        or not isinstance(owner_call.args[0], ast.Constant)
        or not isinstance(owner_call.args[0].value, str)
        or local in {"name", "__all__", "getattr", "globals", "AttributeError"}
        or any(isinstance(node, ast.Name) and node.id == local for node in ast.walk(owner_call))
        or any(
            list(_module_scope_symbol_bindings(tree, name))
            for name in ("getattr", "globals", "AttributeError")
        )
    ):
        return {}
    if len(body) == 4:
        cache = body[2]
        if not (
            isinstance(cache, ast.Assign)
            and len(cache.targets) == 1
            and isinstance(cache.targets[0], ast.Subscript)
            and isinstance(cache.targets[0].value, ast.Call)
            and isinstance(cache.targets[0].value.func, ast.Name)
            and cache.targets[0].value.func.id == "globals"
            and not cache.targets[0].value.args
            and not cache.targets[0].value.keywords
            and isinstance(cache.targets[0].slice, ast.Name)
            and cache.targets[0].slice.id == "name"
            and isinstance(cache.value, ast.Name)
            and cache.value.id == local
        ):
            return {}
    try:
        exports = _StaticExportResolver(source, tree).resolve(source, "__all__")
        if not isinstance(exports, (tuple, list)) or not all(
            isinstance(name, str) for name in exports
        ):
            return {}
        targets = {
            _lazy_import_module_target(info[0], source, tree, owner_call, name) for name in exports
        }
        if None in targets or len(targets) != 1:
            return {}
        owner = next(iter(targets))
        if owner is None:
            return {}
        owner_source = _facade_source_for(owner)
        if owner_source == source:
            return {}
        owner_tree = ast.parse(admitted_read_bytes(owner_source, REPO_ROOT))
        owner_exports = _StaticExportResolver(owner_source, owner_tree).resolve(
            owner_source, "__all__"
        )
        if not isinstance(owner_exports, (tuple, list)) or _export_namespace_write_may_change(
            owner_tree, frozenset((*exports, "__all__")), owner_source
        ):
            return {}
    except (OSError, ValueError, TypeError, SyntaxError):
        return {}
    return {
        name: owner
        for name in exports
        if name in owner_exports
        and (
            _branch_public_binding(owner_tree.body, name) is not None
            or _optional_import_export_binding(owner_tree, name)
        )
    }


def _lazy_named_owner_routes(source: Path, tree: ast.Module) -> dict[str, str]:
    """Resolve finite name-gated imports and same-name attribute loads statically."""
    info = _module_name_for_path(source)
    getter = _top_level_function(tree, "__getattr__")
    if info is None or getter is None or not _has_exact_positional_parameters(getter, "name"):
        return {}
    module = info[0]
    route_targets: dict[str, set[str]] = {
        name: {owner} for name, owner in _guarded_literal_lazy_owner_routes(source, tree).items()
    }
    for branch in _function_body_without_docstring(getter):
        if not isinstance(branch, ast.If) or branch.orelse:
            continue
        guarded = _guarded_export_names(branch.test)
        if not guarded:
            continue
        modules: dict[str, dict[str, str]] = {}
        values: dict[str, dict[str, str]] = {}
        imports: dict[str, dict[str, tuple[str, str]]] = {}
        for statement in branch.body:
            if isinstance(statement, ast.ImportFrom):
                owner = _resolve_import_module(*info, statement)
                if owner and owner.startswith("polisyos."):
                    children = (
                        _source_child_module_names(owner)
                        if statement.module is None and statement.level > 0
                        else ()
                    )
                    for alias in statement.names:
                        local = alias.asname or alias.name
                        if alias.name in (children or ()):
                            child_owner = f"{owner}.{alias.name}"
                            modules.setdefault(local, {}).update(
                                dict.fromkeys(guarded, child_owner)
                            )
                        else:
                            imports.setdefault(local, {})[alias.name] = (owner, alias.name)
            elif (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
            ):
                local = statement.targets[0].id
                value = statement.value
                if isinstance(value, ast.Call) and _import_module_callable_is_stdlib(
                    tree, value.func
                ):
                    targets = {
                        name: target
                        for name in guarded
                        if (target := _lazy_import_module_target(module, source, tree, value, name))
                        is not None
                    }
                    if targets:
                        modules.setdefault(local, {}).update(targets)
                elif (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "getattr"
                    and len(value.args) == 2
                    and isinstance(value.args[0], ast.Name)
                    and isinstance(value.args[1], ast.Name)
                    and value.args[1].id == "name"
                    and not value.keywords
                ):
                    values.setdefault(local, {}).update(modules.get(value.args[0].id, {}))
                elif isinstance(value, ast.Name):
                    values.setdefault(local, {}).update(values.get(value.id, {}))
                    modules.setdefault(local, {}).update(modules.get(value.id, {}))
                    imports.setdefault(local, {}).update(imports.get(value.id, {}))
            elif isinstance(statement, ast.Return):
                returned: dict[str, str] = {}
                value = statement.value
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "getattr"
                    and len(value.args) == 2
                    and isinstance(value.args[0], ast.Name)
                    and isinstance(value.args[1], ast.Name)
                    and value.args[1].id == "name"
                    and not value.keywords
                ):
                    returned = modules.get(value.args[0].id, {})
                elif isinstance(value, ast.Name):
                    returned = values.get(value.id, {})
                    returned.update(
                        {
                            name: owner
                            for name, owner in modules.get(value.id, {}).items()
                            if owner.rsplit(".", 1)[-1] == name
                        }
                    )
                    returned.update(
                        {
                            name: owner
                            for name, (owner, symbol) in imports.get(value.id, {}).items()
                            if name == symbol
                        }
                    )
                for name in guarded:
                    if name in returned:
                        route_targets.setdefault(name, set()).add(returned[name])
    return {name: next(iter(owners)) for name, owners in route_targets.items() if len(owners) == 1}


def _delegated_lazy_owner_routes(
    source: Path, tree: ast.Module, exports: tuple[str, ...]
) -> frozenset[str]:
    """Follow __all__ and __getattr__ imported together from one source owner."""
    info = _module_name_for_path(source)
    if info is None:
        return frozenset()
    all_bindings = list(_module_scope_symbol_bindings(tree, "__all__"))
    getter_bindings = list(_module_scope_symbol_bindings(tree, "__getattr__"))
    if (
        len(all_bindings) != 1
        or len(getter_bindings) != 1
        or not isinstance(all_bindings[0], ast.ImportFrom)
        or not isinstance(getter_bindings[0], ast.ImportFrom)
    ):
        return frozenset()
    all_import, getter_import = all_bindings[0], getter_bindings[0]
    all_alias = next((a for a in all_import.names if (a.asname or a.name) == "__all__"), None)
    getter_alias = next(
        (a for a in getter_import.names if (a.asname or a.name) == "__getattr__"), None
    )
    owner = _resolve_import_module(*info, all_import)
    if (
        all_alias is None
        or all_alias.name != "__all__"
        or getter_alias is None
        or getter_alias.name != "__getattr__"
        or owner is None
        or owner != _resolve_import_module(*info, getter_import)
        or not owner.startswith("polisyos.")
    ):
        return frozenset()
    try:
        owner_source = _facade_source_for(owner)
        owner_tree = ast.parse(admitted_read_bytes(owner_source, REPO_ROOT))
    except (OSError, ValueError, SyntaxError):
        return frozenset()
    direct, wildcard = _module_scope_binding_index(owner_tree)
    direct_names = {
        name
        for name in exports
        if _direct_public_binding(
            owner_tree, name, _indexed_symbol_bindings(direct, wildcard, name)
        )
        is not None
    }
    map_names = _lazy_exports_have_owner_routes(owner_source, owner_tree, frozenset(exports))
    branch_names = _lazy_named_owner_routes(owner_source, owner_tree)
    return frozenset(
        name
        for name in exports
        if name in direct_names or name in map_names or name in branch_names
    )


def _lazy_exports_have_owner_routes(
    source: Path,
    tree: ast.Module,
    names: frozenset[str],
) -> frozenset[str]:
    """Resolve lazy names only through a finite map selected by the getter."""
    getter = _top_level_function(tree, "__getattr__")
    if getter is None or not _has_exact_positional_parameters(getter, "name"):
        return frozenset()
    accessed_maps = _lazy_owner_map_accesses(getter)
    if not accessed_maps:
        return frozenset()
    resolver = _StaticExportResolver(source, tree)
    try:
        declaration = resolver.resolve(source, "__all__")
    except (OSError, ValueError, TypeError, SyntaxError):
        return frozenset()
    if not isinstance(declaration, (tuple, list)) or not all(
        isinstance(item, str) for item in declaration
    ):
        return frozenset()
    owner_maps: list[dict[object, object]] = []
    for symbol in sorted(accessed_maps):
        try:
            mapping = resolver._closed_static_mapping(source, symbol)
        except (OSError, ValueError, TypeError, SyntaxError):
            mapping = _derived_lazy_owner_map(source, tree, symbol)
        if mapping and all(
            isinstance(key, str) and _owner_target_is_valid(value, key)
            for key, value in mapping.items()
        ):
            owner_maps.append(mapping)
    routes: dict[str, int] = {}
    for mapping in owner_maps:
        for name in names:
            if name in mapping:
                routes[name] = routes.get(name, 0) + 1
    unique_routes = {name for name, count in routes.items() if count == 1}
    unique_routes.update(_lazy_function_literal_mapping_routes(source, tree, names))
    unique_routes.update(_lazy_attribute_map_routes(source, tree, names))
    return frozenset(unique_routes)


def _runtime_module_statements(tree: ast.Module) -> tuple[ast.stmt, ...]:
    """Return module execution statements, unwrapping the standard TYPE_CHECKING split."""
    type_checking_imports = {
        alias.asname or alias.name: statement
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom)
        and statement.module == "typing"
        and statement.level == 0
        for alias in statement.names
        if alias.name == "TYPE_CHECKING"
    }
    type_checking = {
        name
        for name, statement in type_checking_imports.items()
        if list(_module_scope_symbol_bindings(tree, name)) == [statement]
    }
    statements: list[ast.stmt] = []
    for statement in tree.body:
        if (
            isinstance(statement, ast.If)
            and isinstance(statement.test, ast.Name)
            and statement.test.id in type_checking
        ):
            statements.extend(statement.orelse)
        else:
            statements.append(statement)
    return tuple(statements)


def _branch_bindings(statements: list[ast.stmt], name: str) -> list[ast.AST]:
    """Find bindings in one straight branch without interpreting nested control flow."""
    module = ast.Module(body=statements, type_ignores=[])
    return [node for node in _module_scope_symbol_bindings(module, name) if node in statements]


def _branch_public_binding(statements: list[ast.stmt], name: str) -> ast.AST | None:
    """Resolve one unconditional binding, without claiming its runtime availability."""
    branch = ast.Module(body=statements, type_ignores=[])
    binding = _direct_public_binding(branch, name)
    if (
        isinstance(binding, (ast.Assign, ast.AnnAssign))
        and isinstance(binding.value, ast.Name)
        and not _public_alias_target_is_bound(branch, binding.value.id)
    ):
        return None
    return binding


def _optional_import_export_binding(tree: ast.Module, name: str) -> bool:
    """Prove a declared name exists in each successful optional-import outcome.

    A fallback such as ``None`` is a bound export, not proof that an optional
    backend, callable or type is available. Import resolution retains its own
    stricter owner-binding checks.
    """
    runtime = ast.Module(body=list(_runtime_module_statements(tree)), type_ignores=[])
    bindings = list(_module_scope_symbol_bindings(runtime, name))
    if len(bindings) < 2:
        return False
    for statement in runtime.body:
        if not isinstance(statement, ast.Try) or not statement.handlers:
            continue
        contained = {id(node) for node in ast.walk(statement)}
        if not all(id(binding) in contained for binding in bindings):
            continue
        try_bindings = _branch_bindings(statement.body, name)
        try_binding = _branch_public_binding(statement.body, name)
        if not isinstance(try_binding, (ast.Import, ast.ImportFrom)) or len(try_bindings) != 1:
            continue
        if _branch_bindings(statement.orelse, name) or _branch_bindings(statement.finalbody, name):
            continue
        valid_handlers = True
        for handler in statement.handlers:
            if handler.type is None:
                valid_handlers = False
                break
            exception_names: set[str] = set()
            if isinstance(handler.type, ast.Name):
                exception_names.add(handler.type.id)
            elif isinstance(handler.type, ast.Tuple) and all(
                isinstance(item, ast.Name) for item in handler.type.elts
            ):
                exception_names.update(item.id for item in handler.type.elts)
            else:
                valid_handlers = False
                break
            if (
                not exception_names
                or not exception_names
                <= {
                    "ImportError",
                    "ModuleNotFoundError",
                    "SyntaxError",
                    "IndentationError",
                }
                or any(list(_module_scope_symbol_bindings(tree, item)) for item in exception_names)
                or _branch_public_binding(handler.body, name) is None
            ):
                valid_handlers = False
                break
        if not valid_handlers:
            continue
        allowed = {id(item) for item in try_bindings}
        allowed.update(
            id(binding)
            for handler in statement.handlers
            for binding in _branch_bindings(handler.body, name)
        )
        if {id(binding) for binding in bindings} == allowed:
            return True
    return False


def _exported_names_have_bindings(source: Path, tree: ast.Module, exports: tuple[str, ...]) -> None:
    if _export_namespace_write_may_change(tree, frozenset((*exports, "__all__")), source):
        raise _UnresolvedExportDeclarationError(
            f"Unresolved reflective module-namespace write: {_export_source_locator(source)}"
        )
    lazy_routes = _lazy_exports_have_owner_routes(source, tree, frozenset(exports))
    named_routes = _lazy_named_owner_routes(source, tree)
    delegated_routes = _delegated_lazy_owner_routes(source, tree, exports)
    module_info = _module_name_for_path(source)
    module = None if module_info is None else module_info[0]
    binding_index, wildcard_imports = _module_scope_binding_index(tree)
    child_routes: set[str] = set()
    if module is not None:
        children = _source_child_module_names(module)
        if children is not None:
            for name in exports:
                if (
                    name in children
                    and _facade_lazy_child_target(module, source, tree, name) == f"{module}.{name}"
                ):
                    child_routes.add(name)
    for name in exports:
        bindings = _indexed_symbol_bindings(binding_index, wildcard_imports, name)
        binding = _direct_public_binding(tree, name, bindings)
        if binding is None and _optional_import_export_binding(tree, name):
            continue
        if binding is not None:
            if (
                isinstance(binding, (ast.Assign, ast.AnnAssign))
                and isinstance(binding.value, ast.Name)
                and not _public_alias_target_is_bound(
                    tree,
                    binding.value.id,
                    frozenset({name}),
                    binding_index=binding_index,
                    wildcard_imports=wildcard_imports,
                )
            ):
                raise _UnresolvedExportDeclarationError(
                    f"Unresolved exported alias target: {_export_source_locator(source)}:{name}"
                )
            continue
        if name in child_routes:
            continue
        if name in lazy_routes:
            continue
        if name in named_routes:
            continue
        if name in delegated_routes:
            continue
        raise _UnresolvedExportDeclarationError(
            f"Unresolved exported binding: {_export_source_locator(source)}:{name}"
        )


def _extract_exports(tree: ast.Module, source_file: Path | None = None) -> tuple[str, ...]:
    source = source_file or SRC_ROOT / "polisyos" / "__static_exports__.py"
    try:
        compile(tree, str(source), "exec", dont_inherit=True)
    except SyntaxError as exc:
        raise _UnresolvedExportDeclarationError(
            f"Invalid source syntax for public export inventory: {_export_source_locator(source)}: {exc.msg}"
        ) from exc
    resolver = _StaticExportResolver(source, tree)
    if not any(_module_scope_symbol_bindings(tree, "__all__")):
        if _export_namespace_write_may_change(tree, frozenset({"__all__"})):
            raise _UnresolvedExportDeclarationError(
                f"Unresolved reflective __all__ declaration: {_export_source_locator(source)}"
            )
        binding_index, wildcard_imports = _module_scope_binding_index(tree)
        public_names = sorted(
            name for name in binding_index if not name.startswith("_") and name != "annotations"
        )
        if wildcard_imports or public_names:
            rendered = ", ".join(public_names[:8]) or "wildcard import"
            raise _UnresolvedExportDeclarationError(
                f"Missing explicit __all__ for source-defined public bindings "
                f"({_export_source_locator(source)}: {rendered})"
            )
        return ()
    try:
        exports = resolver.resolve(source, "__all__")
    except _UnresolvedExportDeclarationError as exc:
        prefix = _literal_prefix_before_extensions(tree)
        if prefix is not None:
            try:
                _exported_names_have_bindings(source, tree, prefix)
            except _UnresolvedExportDeclarationError:
                prefix = None
        if prefix is not None:
            raise _IncompleteExportDeclarationError(prefix) from exc
        literals = [
            _string_list_value(node.value)
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            )
        ]
        candidates = literals[0] if len(literals) == 1 and literals[0] is not None else ()
        raise _UnresolvedExportDeclarationError(str(exc), candidates) from exc
    if not isinstance(exports, (tuple, list)) or not all(isinstance(item, str) for item in exports):
        raise _UnresolvedExportDeclarationError(
            f"Export declaration must resolve to string sequence: {_export_source_locator(source)}"
        )
    if len(exports) != len(set(exports)):
        raise _UnresolvedExportDeclarationError(
            f"Unresolved duplicate exported names: {_export_source_locator(source)}"
        )
    try:
        if not resolver.selected_collection_consumers_are_closed():
            raise _UnresolvedExportDeclarationError(
                f"Unresolved selected export declaration dependency: {_export_source_locator(source)}"
            )
        _exported_names_have_bindings(source, tree, tuple(exports))
    except _UnresolvedExportDeclarationError as exc:
        prefix = _literal_prefix_before_extensions(tree)
        if prefix is not None:
            try:
                _exported_names_have_bindings(source, tree, prefix)
            except _UnresolvedExportDeclarationError:
                prefix = None
        if prefix is not None:
            raise _IncompleteExportDeclarationError(
                prefix,
                reason=str(exc),
                exports_scope="verified direct literal prefix; complete selected export contract unresolved",
            ) from exc
        raise _UnresolvedExportDeclarationError(str(exc), tuple(exports)) from exc
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
    declared_candidates: tuple[str, ...] = ()
    source_profiles: tuple[SourceExportProfile, ...] = ()
    with measure_file_reads(REPO_ROOT) as reads:
        try:
            source_file = _facade_source_for(module)
            tree = ast.parse(admitted_read_bytes(source_file, REPO_ROOT))
            try:
                exports = _extract_exports(tree, source_file)
            except _IncompleteExportDeclarationError as exc:
                exports = exc.prefix
                declared_candidates = exc.declared_candidates
                incomplete_reason = str(exc)
                exports_scope = exc.exports_scope
            except _UnresolvedExportDeclarationError as exc:
                exports = ()
                declared_candidates = exc.declared_candidates
                incomplete_reason = str(exc)
                exports_scope = (
                    "no names proven by the bounded parser; not an empty runtime namespace"
                )
            if incomplete_reason is not None:
                source_profiles = resolve_conditional_export_profiles(
                    tree, lambda profile_tree: _extract_exports(profile_tree, source_file)
                )
                if source_profiles:
                    shared_names = set(source_profiles[0].exports).intersection(
                        *(set(profile.exports) for profile in source_profiles[1:])
                    )
                    exports = tuple(
                        name for name in source_profiles[0].exports if name in shared_names
                    )
                    incomplete_reason = None
        except (OSError, ValueError, SyntaxError, TypeError) as exc:
            exc.add_note(json.dumps(reads.snapshot(complete_verdict=False), sort_keys=True))
            raise
        export_resolution = reads.snapshot(complete_verdict=incomplete_reason is None)
    export_resolution["complete"] = incomplete_reason is None
    if source_profiles:
        export_resolution["exports_scope"] = (
            "Complete finite source-conditioned export profiles; exports lists only their "
            "common names. No backend condition or native availability was evaluated."
        )
    if incomplete_reason is not None:
        export_resolution["reason"] = incomplete_reason
        export_resolution["exports_scope"] = exports_scope
        export_resolution["declared_export_candidates"] = list(declared_candidates)
        export_resolution["candidate_scope"] = (
            "Names in a finite source declaration before effect audit; not proved native exports, "
            "not included in known_export_count and not a completeness verdict."
        )
    export_resolution["selector"] = (
        "Declared __all__; finite literal sequences/mapping keys and explicitly bound "
        "selected declaration dependencies are resolved without executing source. Completeness "
        "requires one closed __all__ dependency slice plus one unique direct export binding, "
        "an owner-map route visibly selected by the module lazy getter, or the exact lazy-child "
        "route. Unrelated imports and function bodies do not affect the selected export slice. "
        "Dynamic declarations, opaque writes or aliases, missing bindings, ambiguous owner maps, "
        "and unsupported lazy routes remain unresolved. Runtime __all__/getattr confirmation is "
        "separate and applies only to the exact installed artifact/environment; logical module "
        "names do not establish physical import origin."
    )
    function_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    summary = (ast.get_docstring(tree) or "").strip().splitlines()
    return SupportedEntrypointInventory(
        module=module,
        facade_mode_observed=(
            "unresolved_exports"
            if incomplete_reason is not None and not exports
            else _observed_facade_mode(exports=exports, has_getattr="__getattr__" in function_names)
        ),
        export_count=len(exports) if incomplete_reason is None and not source_profiles else None,
        known_export_count=len(exports),
        exports=exports,
        has___getattr__="__getattr__" in function_names,
        has___dir__="__dir__" in function_names,
        source_file=str(source_file.relative_to(REPO_ROOT)),
        summary=summary[0] if summary else "",
        export_resolution=export_resolution,
        source_export_profiles=source_profiles,
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


def _source_tree_for_facade(
    module: str,
    cache: dict[str, tuple[Path, ast.Module] | None],
) -> tuple[Path, ast.Module] | None:
    """Read a facade source tree without importing or executing it."""
    if module not in cache:
        try:
            source = _facade_source_for(module)
            tree = ast.parse(admitted_read_bytes(source, REPO_ROOT))
        except (FileNotFoundError, OSError, ValueError, SyntaxError):
            cache[module] = None
        else:
            cache[module] = (source, tree)
    return cache[module]


def _source_module_exists(module: str) -> bool:
    """Resolve an importable Python module candidate under the admitted source tree."""
    if not module.startswith("polisyos."):
        return False
    candidate = SRC_ROOT.joinpath(*module.split("."))
    try:
        return (
            admitted_is_file(candidate.with_suffix(".py"), REPO_ROOT)
            or admitted_is_file(candidate / "__init__.py", REPO_ROOT)
            or admitted_is_dir(candidate, REPO_ROOT)
        )
    except ValueError:
        # A source-tree symlink that escapes the admitted root is unresolved,
        # not evidence that the from-list name is only a facade attribute.
        return True


def _source_child_module_names(module: str) -> tuple[str, ...] | None:
    """List immediate importable source children, preserving an unknown read as unknown."""
    package_dir = SRC_ROOT.joinpath(*module.split("."))
    try:
        if not admitted_is_dir(package_dir, REPO_ROOT):
            return ()
        children = sorted(package_dir.iterdir(), key=lambda child: child.name)
    except (OSError, ValueError):
        return None

    names: set[str] = set()
    for child in children:
        if child.name == "__pycache__":
            continue
        try:
            if child.suffix == ".py" and child.stem != "__init__":
                if admitted_is_file(child, REPO_ROOT):
                    names.add(child.stem)
            elif admitted_is_dir(child, REPO_ROOT):
                names.add(child.name)
        except ValueError:
            # Keep the import spelling as an unresolved candidate without
            # reading a symlink target outside the product source root.
            names.add(child.stem if child.suffix == ".py" else child.name)
    return tuple(sorted(names))


def _module_level_attribute_is_bound(tree: ast.Module, symbol: str) -> bool:
    """Prove a facade binds one name directly at module level."""
    bindings = list(_symbol_binding_nodes(tree, symbol))
    if len(bindings) != 1 or bindings[0] not in tree.body:
        return False
    binding = bindings[0]
    if isinstance(binding, ast.ImportFrom):
        matches = [
            alias
            for alias in binding.names
            if alias.name != "*" and (alias.asname or alias.name) == symbol
        ]
        return len(matches) == 1
    if isinstance(binding, ast.Import):
        matches = [
            alias for alias in binding.names if (alias.asname or alias.name.split(".")[0]) == symbol
        ]
        return len(matches) == 1
    return isinstance(
        binding,
        (
            ast.Assign,
            ast.AnnAssign,
            ast.TypeAlias,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
        ),
    )


def _static_string_collection(
    source: Path,
    tree: ast.Module,
    symbol: str,
) -> tuple[str, ...] | None:
    resolver = _StaticExportResolver(source, tree)
    try:
        value = resolver.resolve(source, symbol)
    except (OSError, ValueError, TypeError, SyntaxError):
        return None
    if isinstance(value, (list, tuple, set, frozenset)) and all(
        isinstance(item, str) for item in value
    ):
        if not resolver.selected_collection_consumers_are_closed():
            return None
        return tuple(value)
    return None


def _module_level_assignment(tree: ast.Module, symbol: str) -> ast.Assign | ast.AnnAssign | None:
    bindings = list(_module_scope_symbol_bindings(tree, symbol))
    if len(bindings) != 1 or bindings[0] not in tree.body:
        return None
    binding = bindings[0]
    if (
        isinstance(binding, ast.Assign)
        and len(binding.targets) == 1
        and isinstance(binding.targets[0], ast.Name)
        and binding.targets[0].id == symbol
    ):
        return binding
    if isinstance(binding, ast.AnnAssign) and isinstance(binding.target, ast.Name):
        return binding
    return None


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(functions) != 1 or not isinstance(functions[0], ast.FunctionDef):
        return None
    function = functions[0]
    return function if not function.decorator_list else None


def _has_exact_positional_parameters(function: ast.FunctionDef, *names: str) -> bool:
    args = function.args
    return (
        [argument.arg for argument in args.posonlyargs] == []
        and [argument.arg for argument in args.args] == list(names)
        and not args.vararg
        and not args.kwonlyargs
        and not args.kwarg
        and not args.defaults
        and not any(args.kw_defaults)
    )


def _local_getter_importlib_binding(
    tree: ast.Module,
    getter: ast.FunctionDef | ast.AsyncFunctionDef,
    local_name: str,
) -> bool:
    """Prove one leading stdlib importlib binding local to the selected getter."""
    body = _function_body_without_docstring(getter)
    imports = [
        statement
        for statement in body
        if isinstance(statement, ast.Import)
        and any(
            alias.name == "importlib"
            and (alias.asname or alias.name.split(".", 1)[0]) == local_name
            for alias in statement.names
        )
    ]
    if (
        len(imports) != 1
        or body[0] is not imports[0]
        or list(_module_scope_symbol_bindings(tree, local_name))
    ):
        return False
    nested_imports = [
        node
        for node in ast.walk(getter)
        if isinstance(node, ast.Import)
        and any((alias.asname or alias.name.split(".", 1)[0]) == local_name for alias in node.names)
    ]
    if nested_imports != imports:
        return False
    parents = {
        child: parent for parent in ast.walk(getter) for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(getter):
        if not isinstance(node, ast.Name) or node.id != local_name:
            continue
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            return False
        if isinstance(node.ctx, ast.Load):
            parent = parents.get(node)
            if not (
                isinstance(parent, ast.Attribute)
                and parent.value is node
                and parent.attr == "import_module"
                and isinstance(parents.get(parent), ast.Call)
                and parents[parent].func is parent
            ):
                return False
    return True


def _import_module_callable_is_stdlib(tree: ast.Module, function: ast.AST) -> bool:
    """Resolve stdlib importlib import bindings through module or getter scope."""
    if isinstance(function, ast.Attribute) and function.attr == "import_module":
        if not isinstance(function.value, ast.Name):
            return False
        local = function.value.id
        bindings = list(_module_scope_symbol_bindings(tree, local))
        if not bindings:
            getter = _top_level_function(tree, "__getattr__")
            return getter is not None and _local_getter_importlib_binding(tree, getter, local)
        return all(
            isinstance(binding, ast.Import)
            and any(
                alias.name.split(".", 1)[0] == "importlib"
                and (alias.asname or alias.name.split(".", 1)[0]) == local
                for alias in binding.names
            )
            for binding in bindings
        )
    if isinstance(function, ast.Name):
        local = function.id
        bindings = list(_module_scope_symbol_bindings(tree, local))
        return bool(bindings) and all(
            isinstance(binding, ast.ImportFrom)
            and binding.level == 0
            and binding.module == "importlib"
            and any(
                alias.name == "import_module" and (alias.asname or alias.name) == local
                for alias in binding.names
            )
            for binding in bindings
        )
    return False


def _static_module_name(
    node: ast.AST,
    *,
    parent_module: str,
    alias_name: str,
) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
            elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
                if value.value.id == "__name__":
                    pieces.append(parent_module)
                elif value.value.id == "name":
                    pieces.append(alias_name)
                else:
                    return None
            else:
                return None
        return "".join(pieces)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_module_name(node.left, parent_module=parent_module, alias_name=alias_name)
        right = _static_module_name(node.right, parent_module=parent_module, alias_name=alias_name)
        return None if left is None or right is None else left + right
    return None


def _function_return_expressions(function: ast.FunctionDef) -> list[ast.AST]:
    body = _function_body_without_docstring(function)
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return []
    return [body[0].value]


def _function_body_without_docstring(function: ast.FunctionDef) -> list[ast.stmt]:
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body.pop(0)
    return body


def _read_api_surface_route_mappings(
    source: Path, tree: ast.Module, mapping_names: tuple[str, str]
) -> tuple[dict[str, str], dict[str, str]] | None:
    """Read the two literal route maps only from a pure local owner module."""
    info = _module_name_for_path(source)
    if info is None:
        return None
    imports: dict[str, tuple[str, str]] = {}
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom):
            continue
        module = _resolve_import_module(*info, statement)
        if module is None:
            continue
        for alias in statement.names:
            local_name = alias.asname or alias.name
            if local_name in mapping_names:
                if alias.name == "*" or local_name in imports:
                    return None
                imports[local_name] = (module, alias.name)
    if set(imports) != set(mapping_names) or len({item[0] for item in imports.values()}) != 1:
        return None
    route_module = next(iter(imports.values()))[0]
    if route_module != "polisyos.data_forge.read_api.surface_routes":
        return None
    try:
        route_source = _facade_source_for(route_module)
        route_tree = ast.parse(admitted_read_bytes(route_source, REPO_ROOT))
    except (OSError, ValueError, SyntaxError):
        return None
    remote_names = {remote for _, remote in imports.values()}
    mappings: dict[str, dict[str, str]] = {}
    for statement in route_tree.body:
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue
        if isinstance(statement, ast.ImportFrom) and statement.module == "__future__":
            if not _supported_future_import_is_passive(route_tree, statement):
                return None
            continue
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            return None
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            return None
        name = targets[0].id
        if (
            name not in remote_names
            or not isinstance(statement.value, ast.Dict)
            or name in mappings
        ):
            return None
        values: dict[str, str] = {}
        for key, value in zip(statement.value.keys, statement.value.values, strict=True):
            if key is None:
                return None
            try:
                key_value, item_value = ast.literal_eval(key), ast.literal_eval(value)
            except (ValueError, TypeError):
                return None
            if (
                not isinstance(key_value, str)
                or not isinstance(item_value, str)
                or key_value in values
            ):
                return None
            values[key_value] = item_value
        mappings[name] = values
    if set(mappings) != remote_names or len(mappings) != 2:
        return None
    first = mappings[imports[mapping_names[0]][1]]
    second = mappings[imports[mapping_names[1]][1]]
    return first, second


def _read_api_surface_records(
    source: Path,
    tree: ast.Module,
) -> dict[str, str] | None:
    """Resolve a read_api registry through its typed table and source helpers."""
    record_class = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ReadApiSurface"
        ),
        None,
    )
    dataclass_decorator = (
        record_class.decorator_list[0]
        if record_class is not None and len(record_class.decorator_list) == 1
        else None
    )
    if (
        record_class is None
        or not isinstance(dataclass_decorator, ast.Call)
        or not isinstance(dataclass_decorator.func, ast.Name)
        or dataclass_decorator.func.id != "dataclass"
        or dataclass_decorator.args
        or not any(
            keyword.arg == "frozen"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in dataclass_decorator.keywords
        )
        or any(
            keyword.arg not in {"frozen", "slots"}
            or not isinstance(keyword.value, ast.Constant)
            or keyword.value.value is not True
            for keyword in dataclass_decorator.keywords
        )
    ):
        return None
    fields = {
        node.target.id: ast.unparse(node.annotation)
        for node in record_class.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    if (
        set(fields) != {"name", "module", "summary"}
        or any(annotation != "str" for annotation in fields.values())
        or any(
            not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name))
            and not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            for node in record_class.body
        )
    ):
        return None

    surfaces_binding = _module_level_assignment(tree, "READ_API_SURFACES")
    if surfaces_binding is None or surfaces_binding.value is None:
        return None
    records_node = surfaces_binding.value
    records: dict[str, str] = {}
    expected_routes = ast.parse(
        "tuple(ReadApiSurface(name=name, module=module, summary=READ_API_SURFACE_SUMMARIES[name]) "
        "for name, module in READ_API_SURFACE_MODULES.items())",
        mode="eval",
    ).body
    if ast.dump(records_node, include_attributes=False) == ast.dump(
        expected_routes, include_attributes=False
    ):
        route_maps = _read_api_surface_route_mappings(
            source, tree, ("READ_API_SURFACE_MODULES", "READ_API_SURFACE_SUMMARIES")
        )
        if route_maps is None:
            return None
        module_routes, summaries = route_maps
        if set(module_routes) != set(summaries) or not all(
            module.startswith("polisyos.") for module in module_routes.values()
        ):
            return None
        records = dict(module_routes)
    elif isinstance(records_node, (ast.Tuple, ast.List)):
        for node in records_node.elts:
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                return None
            if node.func.id != "ReadApiSurface" or node.args:
                return None
            fields_by_name = {
                keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None
            }
            if set(fields_by_name) != {"name", "module", "summary"}:
                return None
            name_node, module_node = fields_by_name["name"], fields_by_name["module"]
            if not (
                isinstance(name_node, ast.Constant)
                and isinstance(name_node.value, str)
                and isinstance(module_node, ast.Constant)
                and isinstance(module_node.value, str)
            ):
                return None
            if name_node.value in records:
                return None
            records[name_node.value] = module_node.value
    else:
        return None

    by_name = _module_level_assignment(tree, "_SURFACES_BY_NAME")
    if by_name is None or not isinstance(by_name.value, ast.DictComp):
        return None
    expected_map = ast.parse(
        "{surface.name: surface for surface in READ_API_SURFACES}", mode="eval"
    ).body
    if ast.dump(by_name.value, include_attributes=False) != ast.dump(
        expected_map, include_attributes=False
    ):
        return None

    available = _top_level_function(tree, "available_surfaces")
    expected_names = (
        ast.parse("tuple(surface.name for surface in READ_API_SURFACES)", mode="eval").body,
        ast.parse("tuple(READ_API_SURFACE_MODULES)", mode="eval").body,
    )
    available_body = [] if available is None else _function_body_without_docstring(available)
    if (
        available is None
        or not _has_exact_positional_parameters(available)
        or len(available_body) != 1
        or not isinstance(available_body[0], ast.Return)
        or not any(
            ast.dump(available_body[0].value, include_attributes=False)
            == ast.dump(expected, include_attributes=False)
            for expected in expected_names
        )
    ):
        return None

    lookup = _top_level_function(tree, "get_surface")
    expected_lookup = ast.parse("_SURFACES_BY_NAME[name]", mode="eval").body
    lookup_body = [] if lookup is None else _function_body_without_docstring(lookup)
    if (
        lookup is None
        or not _has_exact_positional_parameters(lookup, "name")
        or len(lookup_body) != 1
        or not isinstance(lookup_body[0], ast.Try)
        or len(lookup_body[0].body) != 1
        or not isinstance(lookup_body[0].body[0], ast.Return)
        or ast.dump(lookup_body[0].body[0].value, include_attributes=False)
        != ast.dump(expected_lookup, include_attributes=False)
        or len(lookup_body[0].handlers) != 1
        or not isinstance(lookup_body[0].handlers[0].type, ast.Name)
        or lookup_body[0].handlers[0].type.id != "KeyError"
        or len(lookup_body[0].handlers[0].body) != 1
        or not isinstance(lookup_body[0].handlers[0].body[0], ast.Raise)
        or not isinstance(lookup_body[0].handlers[0].body[0].exc, ast.Call)
        or not isinstance(lookup_body[0].handlers[0].body[0].exc.func, ast.Name)
        or lookup_body[0].handlers[0].body[0].exc.func.id != "KeyError"
        or lookup_body[0].orelse
        or lookup_body[0].finalbody
    ):
        return None

    loader = _top_level_function(tree, "load_surface")
    expected_load = ast.parse("import_module(get_surface(name).module)", mode="eval").body
    expected_mapped_loader = ast.parse(
        """
try:
    module = READ_API_SURFACE_MODULES[name]
except KeyError as exc:
    raise KeyError(f"unknown Data Forge read_api surface: {name}") from exc
return import_module(module)
"""
    ).body
    loader_body = [] if loader is None else _function_body_without_docstring(loader)
    simple_loader = (
        len(loader_body) == 1
        and isinstance(loader_body[0], ast.Return)
        and ast.dump(loader_body[0].value, include_attributes=False)
        == ast.dump(expected_load, include_attributes=False)
    )
    mapped_loader = ast.dump(
        ast.Module(body=loader_body, type_ignores=[]), include_attributes=False
    ) == ast.dump(
        ast.Module(body=expected_mapped_loader, type_ignores=[]), include_attributes=False
    )
    import_call = (
        expected_load
        if simple_loader
        else loader_body[-1].value
        if mapped_loader and isinstance(loader_body[-1], ast.Return)
        else None
    )
    if (
        loader is None
        or not _has_exact_positional_parameters(loader, "name")
        or import_call is None
        or not isinstance(import_call, ast.Call)
        or not _import_module_callable_is_stdlib(tree, import_call.func)
    ):
        return None
    if not all(module.startswith("polisyos.") for module in records.values()):
        return None
    return records


def _imported_function_source(
    module: str,
    source: Path,
    tree: ast.Module,
    symbol: str,
) -> tuple[str, Path, ast.Module] | None:
    info = _module_name_for_path(source)
    if info is None:
        return None
    bindings = list(_symbol_binding_nodes(tree, symbol))
    matches: list[tuple[str, str, ast.ImportFrom]] = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        imported_module = _resolve_import_module(*info, node)
        if imported_module is None:
            continue
        matches.extend(
            (imported_module, alias.name, node)
            for alias in node.names
            if alias.name != "*" and (alias.asname or alias.name) == symbol
        )
    if (
        len(bindings) != 1
        or len(matches) != 1
        or bindings[0] is not matches[0][2]
        or not matches[0][0].startswith("polisyos.")
    ):
        return None
    imported_module, imported_symbol, _ = matches[0]
    try:
        imported_source = _facade_source_for(imported_module)
        imported_tree = ast.parse(admitted_read_bytes(imported_source, REPO_ROOT))
    except (OSError, ValueError, TypeError, SyntaxError, FileNotFoundError):
        return None
    if _top_level_function(imported_tree, imported_symbol) is None:
        return None
    return imported_module, imported_source, imported_tree


def _resolve_module_loader_expression(
    module: str,
    source: Path,
    tree: ast.Module,
    node: ast.AST,
    alias_name: str,
    *,
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> str | None:
    if isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords:
        if _import_module_callable_is_stdlib(tree, node.func):
            argument = node.args[0]
            if (
                isinstance(argument, ast.Attribute)
                and argument.attr == "module"
                and isinstance(argument.value, ast.Call)
                and isinstance(argument.value.func, ast.Name)
                and argument.value.func.id == "get_surface"
            ):
                records = _read_api_surface_records(source, tree)
                return None if records is None else records.get(alias_name)
            return _static_module_name(
                argument,
                parent_module=module,
                alias_name=alias_name,
            )
        if isinstance(node.func, ast.Name):
            helper = _top_level_function(tree, node.func.id)
            helper_module, helper_source, helper_tree = module, source, tree
            if helper is None:
                imported = _imported_function_source(module, source, tree, node.func.id)
                if imported is None:
                    return None
                helper_module, helper_source, helper_tree = imported
                helper = _top_level_function(helper_tree, node.func.id)
            if (
                helper is None
                or not _loader_helper_body_is_closed(helper)
                or not _module_namespace_uses_are_closed(helper_tree, helper_source)
                or len(node.args) != 1
                or not isinstance(node.args[0], ast.Name)
                or not _has_exact_positional_parameters(helper, node.args[0].id)
            ):
                return None
            key = (helper_module, helper.name)
            if key in seen:
                return None
            return_values = _function_return_expressions(helper)
            if not return_values:
                return None
            resolved = {
                _resolve_module_loader_expression(
                    helper_module,
                    helper_source,
                    helper_tree,
                    value,
                    alias_name,
                    seen=seen | {key},
                )
                for value in return_values
            }
            return next(iter(resolved)) if len(resolved) == 1 and None not in resolved else None
    return None


def _static_collection_for_facade(
    module: str,
    source: Path,
    tree: ast.Module,
    symbol: str,
) -> tuple[str, ...] | None:
    if symbol != "_SURFACE_NAMES":
        return _static_string_collection(source, tree, symbol)
    assignment = _module_level_assignment(tree, symbol)
    expected = ast.parse("frozenset(available_surfaces())", mode="eval").body
    if assignment is None or assignment.value is None:
        return None
    if list(_symbol_binding_nodes(tree, "frozenset")):
        return None
    if ast.dump(assignment.value, include_attributes=False) != ast.dump(
        expected, include_attributes=False
    ):
        return None
    facade_info = _imported_function_source(module, source, tree, "available_surfaces")
    loader_info = _imported_function_source(module, source, tree, "load_surface")
    if facade_info is None or loader_info is None or facade_info[0] != loader_info[0]:
        return None
    _helper_module, helper_source, helper_tree = facade_info
    records = _read_api_surface_records(helper_source, helper_tree)
    if records is None:
        return None
    return tuple(
        record_name
        for record_name, record_module in records.items()
        if record_module.startswith(f"{module}.")
    )


def _condition_for_facade_alias(
    module: str,
    source: Path,
    tree: ast.Module,
    condition: ast.AST,
    alias_name: str,
) -> bool | None:
    if (
        not isinstance(condition, ast.Compare)
        or len(condition.ops) != 1
        or len(condition.comparators) != 1
    ):
        return None
    if not isinstance(condition.left, ast.Name) or condition.left.id != "name":
        return None
    if not isinstance(condition.comparators[0], ast.Name):
        return None
    collection = _static_collection_for_facade(
        module,
        source,
        tree,
        condition.comparators[0].id,
    )
    if collection is None:
        return None
    member = alias_name in collection
    if isinstance(condition.ops[0], ast.In):
        return member
    if isinstance(condition.ops[0], ast.NotIn):
        return not member
    return None


def _block_returns_exact_child_module(
    module: str,
    source: Path,
    tree: ast.Module,
    statements: list[ast.stmt],
    alias_name: str,
    expected_module: str,
) -> bool:
    module_values: dict[str, str] = {}
    for statement in statements:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            if isinstance(statement.value.value, str):
                continue
        if isinstance(statement, ast.ImportFrom) and statement.module == "importlib":
            if (
                statement.level != 0
                or not statement.names
                or not all(alias.name == "import_module" for alias in statement.names)
            ):
                return False
            continue
        if isinstance(statement, ast.If):
            branch = _condition_for_facade_alias(module, source, tree, statement.test, alias_name)
            if branch is None:
                return False
            selected = statement.body if branch else statement.orelse
            if _block_returns_exact_child_module(
                module, source, tree, selected, alias_name, expected_module
            ):
                return True
            if selected and any(isinstance(item, (ast.Return, ast.Raise)) for item in selected):
                return False
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if value is None:
                return False
            if len(targets) == 1 and isinstance(targets[0], ast.Name):
                resolved = _resolve_module_loader_expression(
                    module, source, tree, value, alias_name
                )
                if resolved is None:
                    return False
                module_values[targets[0].id] = resolved
                continue
            if (
                len(targets) == 1
                and isinstance(targets[0], ast.Subscript)
                and isinstance(targets[0].value, ast.Call)
                and isinstance(targets[0].value.func, ast.Name)
                and targets[0].value.func.id == "globals"
                and isinstance(targets[0].slice, ast.Name)
                and targets[0].slice.id == "name"
                and isinstance(value, ast.Name)
                and module_values.get(value.id) == expected_module
            ):
                continue
            return False
        if isinstance(statement, ast.Return):
            if isinstance(statement.value, ast.Name):
                return module_values.get(statement.value.id) == expected_module
            return (
                _resolve_module_loader_expression(module, source, tree, statement.value, alias_name)
                == expected_module
            )
        if isinstance(statement, ast.Raise):
            return False
        if isinstance(statement, ast.Pass):
            continue
        return False
    return False


def _lazy_route_import_bindings_are_closed(
    tree: ast.Module,
    getter: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Keep only the stdlib loader binding used by the selected lazy getter."""
    calls = [
        node
        for node in ast.walk(getter)
        if isinstance(node, ast.Call) and _import_module_callable_is_stdlib(tree, node.func)
    ]
    loader_names: dict[str, str] = {}
    for call in calls:
        if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
            loader_names[call.func.value.id] = "module"
        elif isinstance(call.func, ast.Name):
            loader_names[call.func.id] = "callable"
        else:
            return False
    if not loader_names:
        return True

    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for local_name, kind in loader_names.items():
        bindings = list(_module_scope_symbol_bindings(tree, local_name))
        if (
            kind == "module"
            and not bindings
            and _local_getter_importlib_binding(tree, getter, local_name)
        ):
            continue
        if len(bindings) != 1:
            return False
        binding = bindings[0]
        if kind == "module":
            if not isinstance(binding, ast.Import) or not any(
                alias.name == "importlib"
                and (alias.asname or alias.name.split(".", 1)[0]) == local_name
                for alias in binding.names
            ):
                return False
        elif not (
            isinstance(binding, ast.ImportFrom)
            and binding.level == 0
            and binding.module == "importlib"
            and any(
                alias.name == "import_module" and (alias.asname or alias.name) == local_name
                for alias in binding.names
            )
        ):
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == local_name:
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    return False
                if isinstance(node.ctx, ast.Load):
                    parent = parents.get(node)
                    if kind == "module":
                        valid = (
                            isinstance(parent, ast.Attribute)
                            and parent.value is node
                            and parent.attr == "import_module"
                            and isinstance(parents.get(parent), ast.Call)
                            and parents[parent].func is parent
                        )
                    else:
                        valid = isinstance(parent, ast.Call) and parent.func is node
                    if not valid:
                        return False
            if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(
                node.ctx, (ast.Store, ast.Del)
            ):
                if any(
                    isinstance(child, ast.Name) and child.id == local_name
                    for child in ast.walk(node.value)
                ):
                    return False
    return True


def _facade_lazy_child_target(
    module: str,
    source: Path,
    tree: ast.Module,
    alias_name: str,
) -> str | None:
    """Prove a declared lazy child alias returns the exact child module object.

    The proof reads the complete static export declaration, then follows the
    facade's first applicable name gate and each source-defined loader helper to
    a standard importlib.import_module call. It never imports a candidate module.
    """
    module_info = _module_name_for_path(source)
    if module_info is None or module_info[0] != module:
        return None
    exports = _static_string_collection(source, tree, "__all__")
    if exports is None or alias_name not in exports:
        return None
    getter = _top_level_function(tree, "__getattr__")
    if (
        getter is None
        or list(_module_scope_symbol_bindings(tree, "__getattr__")) != [getter]
        or not _has_exact_positional_parameters(getter, "name")
        or _export_namespace_write_may_change(
            tree, frozenset((*exports, "__all__", "__getattr__")), source
        )
        or not _lazy_route_import_bindings_are_closed(tree, getter)
    ):
        return None
    expected_module = f"{module}.{alias_name}"
    body = _function_body_without_docstring(getter)

    for index, statement in enumerate(body):
        if not isinstance(statement, ast.If):
            return None
        branch = _condition_for_facade_alias(module, source, tree, statement.test, alias_name)
        if branch is None:
            return None
        if branch:
            if _block_returns_exact_child_module(
                module, source, tree, statement.body, alias_name, expected_module
            ):
                return expected_module
            return None
        is_declared_export_guard = (
            isinstance(statement.test, ast.Compare)
            and isinstance(statement.test.comparators[0], ast.Name)
            and statement.test.comparators[0].id == "__all__"
        )
        if not is_declared_export_guard or statement.orelse or len(statement.body) != 1:
            return None
        refusal = statement.body[0]
        if (
            not isinstance(refusal, ast.Raise)
            or not isinstance(refusal.exc, ast.Call)
            or not isinstance(refusal.exc.func, ast.Name)
            or refusal.exc.func.id != "AttributeError"
        ):
            return None
        if _block_returns_exact_child_module(
            module, source, tree, body[index + 1 :], alias_name, expected_module
        ):
            return expected_module
        return None
    return None


def _facade_star_exports(
    module: str,
    facade: tuple[Path, ast.Module] | None,
    cache: dict[str, tuple[str, ...] | None],
) -> tuple[str, ...] | None:
    """Resolve a facade's star-import names using the existing bounded export grammar."""
    if module not in cache:
        if facade is None:
            cache[module] = None
        else:
            source, tree = facade
            declared = bool(list(_module_scope_symbol_bindings(tree, "__all__")))
            dynamic_getattr = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "__getattr__"
                for node in tree.body
            )
            if not declared:
                cache[module] = None if dynamic_getattr else ()
            else:
                try:
                    cache[module] = _extract_exports(tree, source)
                except (OSError, ValueError, TypeError, SyntaxError):
                    cache[module] = None
    return cache[module]


def _maybe_add_fromlist_deep_imports(
    *,
    aliases: list[ast.alias],
    target_module: str,
    source_module: str,
    source_root: str,
    source_file: Path,
    allowed_entrypoints: dict[str, set[str]],
    edges: dict[str, DeepImportEdge],
    facade_cache: dict[str, tuple[Path, ast.Module] | None],
    star_export_cache: dict[str, tuple[str, ...] | None],
) -> None:
    """Classify child-module fallbacks hidden by a supported ImportFrom parent."""
    target_root = _root_for_module(target_module)
    if target_root is None or target_module not in allowed_entrypoints.get(target_root, set()):
        return

    facade = _source_tree_for_facade(target_module, facade_cache)
    if any(alias.name == "*" for alias in aliases):
        child_names = _source_child_module_names(target_module)
        if child_names is None:
            candidate_names = ("*",)
        else:
            exports = _facade_star_exports(target_module, facade, star_export_cache)
            candidate_names = (
                child_names
                if exports is None
                else tuple(name for name in exports if name in child_names)
            )
    else:
        candidate_names = tuple(
            alias.name
            for alias in aliases
            if _source_module_exists(f"{target_module}.{alias.name}")
        )

    facade_tree = None if facade is None else facade[1]
    declared_exports = _facade_star_exports(target_module, facade, star_export_cache)
    for name in candidate_names:
        directly_bound = (
            name != "*"
            and facade_tree is not None
            and _module_level_attribute_is_bound(facade_tree, name)
        )
        lazy_child_target = (
            _facade_lazy_child_target(target_module, facade[0], facade_tree, name)
            if name != "*" and facade is not None and facade_tree is not None
            else None
        )
        if name != "*" and (
            (declared_exports is not None and name in declared_exports and directly_bound)
            or lazy_child_target == f"{target_module}.{name}"
        ):
            continue
        if facade_tree is None or declared_exports is None:
            reason = "export_manifest_unresolved"
        elif name not in declared_exports:
            reason = "bound_but_unlisted" if directly_bound else "name_not_declared_export"
        else:
            reason = "declared_binding_unproven"
        child_module = f"{target_module}.{name}"
        _maybe_add_deep_import(
            edges=edges,
            allowed_entrypoints=allowed_entrypoints,
            source_module=source_module,
            source_root=source_root,
            source_file=source_file,
            target_module=child_module,
            resolution_status="not_established",
            resolution_reason=reason,
        )


def collect_deep_import_edges(policies: list[PackagePolicy]) -> list[DeepImportEdge]:
    allowed_entrypoints: dict[str, set[str]] = {}
    for policy in policies:
        root = _root_for_module(policy.module)
        if root is None:
            continue
        allowed_entrypoints.setdefault(root, set()).update(policy.supported_entrypoints)

    edges: dict[str, DeepImportEdge] = {}
    facade_cache: dict[str, tuple[Path, ast.Module] | None] = {}
    star_export_cache: dict[str, tuple[str, ...] | None] = {}
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
                    _maybe_add_fromlist_deep_imports(
                        aliases=node.names,
                        target_module=target_module,
                        source_module=source_module,
                        source_root=source_root,
                        source_file=file_path,
                        allowed_entrypoints=allowed_entrypoints,
                        edges=edges,
                        facade_cache=facade_cache,
                        star_export_cache=star_export_cache,
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
    resolution_status: Literal["source_resolved", "not_established"] = "source_resolved",
    resolution_reason: Literal[
        "export_manifest_unresolved",
        "name_not_declared_export",
        "bound_but_unlisted",
        "declared_binding_unproven",
    ]
    | None = None,
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
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
    )
    previous = edges.get(edge.key)
    if previous is None or (
        previous.resolution_status == "not_established"
        and edge.resolution_status == "source_resolved"
    ):
        edges[edge.key] = edge


def _parse_registry_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        cells = split_markdown_table_row(line)
        if not cells:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells):
            continue
        first = cells[0].strip().strip("`")
        if not first or first == "id" or first == "_no-active-exceptions_":
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
                        "source_export_profiles": [
                            {
                                "schema_version": profile.schema_version,
                                "conditions": [
                                    {"expression": condition.expression, "value": condition.value}
                                    for condition in profile.conditions
                                ],
                                "exports": list(profile.exports),
                                "runtime_condition_evaluation": profile.runtime_condition_evaluation,
                            }
                            for profile in entrypoint.source_export_profiles
                        ],
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


def _entrypoint_export_count_display(entrypoint: SupportedEntrypointInventory) -> str:
    if entrypoint.source_export_profiles:
        counts = sorted({len(profile.exports) for profile in entrypoint.source_export_profiles})
        return "conditional (" + "/".join(str(count) for count in counts) + ")"
    return _export_count_display(entrypoint.export_count, entrypoint.known_export_count)


def _markdown_code_span(value: str) -> str:
    backtick_runs = re.findall(r"`+", value)
    delimiter = "`" * (max((len(run) for run in backtick_runs), default=0) + 1)
    padding = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{delimiter}{padding}{value}{padding}{delimiter}"


def _markdown_fenced_literal(value: str) -> str:
    backtick_runs = re.findall(r"`+", value)
    delimiter = "`" * max(3, max((len(run) for run in backtick_runs), default=0) + 1)
    trailing_newline = "" if value.endswith("\n") else "\n"
    return f"{delimiter}text\n{value}{trailing_newline}{delimiter}"


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
                    f"`{entrypoint.facade_mode_observed}` | {_entrypoint_export_count_display(entrypoint)} |"
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
            if entrypoint.source_export_profiles:
                lines.extend(
                    [
                        "- Complete finite source-conditioned export profiles follow. "
                        "These conditions were not evaluated against a native environment.",
                        f"- Common source exports: {entrypoint.known_export_count}; "
                        "there is no single unconditional export count.",
                    ]
                )
                for profile in entrypoint.source_export_profiles:
                    conditions = "; ".join(
                        f"{_markdown_code_span(condition.expression)} = "
                        f"`{str(condition.value).lower()}`"
                        for condition in profile.conditions
                    )
                    lines.extend(
                        [
                            "",
                            f"- Source conditions: {conditions}",
                            f"- Profile schema: `{profile.schema_version}`; "
                            f"runtime condition evaluation: `{profile.runtime_condition_evaluation}`.",
                            "",
                            f"<details><summary>Conditional source exports ({len(profile.exports)})</summary>",
                            "",
                            "```text",
                            *profile.exports,
                            "```",
                            "",
                            "</details>",
                        ]
                    )
            elif entrypoint.export_count is None:
                resolution = entrypoint.export_resolution
                reason = resolution["reason"]
                if "\n" in reason:
                    lines.extend(
                        [
                            "- Export resolution incomplete; source reason follows:",
                            "",
                            _markdown_fenced_literal(reason),
                        ]
                    )
                else:
                    lines.append(f"- Export resolution incomplete: {_markdown_code_span(reason)}.")
                exports_scope = resolution.get("exports_scope")
                if exports_scope:
                    lines.append(f"- Export scope: {_markdown_code_span(exports_scope)}")
                candidates = resolution["declared_export_candidates"]
                candidate_scope = resolution.get("candidate_scope")
                if entrypoint.known_export_count == 0 and candidate_scope:
                    lines.append(f"- Candidate scope: {_markdown_code_span(candidate_scope)}")
                evidence_inputs = [
                    row for row in resolution.get("inputs", []) if row["operation"] == "read_bytes"
                ]
                if evidence_inputs:
                    lines.append(
                        f"- Source evidence: {len(evidence_inputs)} measured source reads; "
                        "full path, byte-length, and SHA-256 receipts are in the companion inventory JSON."
                    )
                else:
                    lines.append("- Source evidence reads: none recorded by the resolver.")
                if candidates:
                    lines.extend(
                        [
                            "",
                            f"<details><summary>Source-declared candidates ({len(candidates)}; native exports unproved)</summary>",
                            "",
                            "```text",
                            *candidates,
                            "```",
                            "",
                            "</details>",
                        ]
                    )
            if entrypoint.known_export_count:
                label = (
                    f"Common source exports ({entrypoint.known_export_count})"
                    if entrypoint.source_export_profiles
                    else (
                        f"Known literal prefix ({entrypoint.known_export_count}; total unknown)"
                        if entrypoint.export_count is None
                        else f"Entrypoint exports ({entrypoint.export_count})"
                    )
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
                if item.export_count is None
                else f"Supported exports ({item.export_count})"
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
            if edge.resolution_status == "source_resolved"
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
        if family.probe_input_roots:
            roots = ", ".join(f"`{_repo_display_path(path)}`" for path in family.probe_input_roots)
            lines.append(f"- Native probe input roots: {roots}")
        if family.probe_required_paths:
            required = ", ".join(
                f"`{_repo_display_path(path)}`" for path in family.probe_required_paths
            )
            lines.append(f"- Native probe required inputs: {required}")
        if family.probe_runtime_paths:
            runtime_paths = ", ".join(
                f"`{_repo_display_path(path)}`" for path in family.probe_runtime_paths
            )
            lines.append(f"- Native probe runtime links: {runtime_paths}")
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
                        f"Missing package README for {item.module}: {item.readme} ({item.reason})"
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
            if entrypoint.export_count is None and not entrypoint.source_export_profiles:
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
    allowed_lifecycles = _generated_artifact_allowed_values("lifecycle")
    allowed_stale_behaviors = _generated_artifact_allowed_values("stale_output_behavior")
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
        for schema_field in _generated_artifact_toml_schema():
            if not schema_field.nonblank:
                continue
            field = schema_field.raw_name
            value = getattr(family, schema_field.attribute)
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
        is_runtime_openapi_client = family.source_of_truth == RUNTIME_OPENAPI_CLIENT_SOURCE
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
            elif sum(part.count("{output_root}") for part in family.output_probe_command) != 1:
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
    return family.default_freshness_check or family.source_of_truth == RUNTIME_OPENAPI_CLIENT_SOURCE


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


_PROBE_RUNTIME_LINKS = frozenset(
    {
        Path("node_modules"),
        Path("packages/runtime-api-client/node_modules"),
        Path("apps/runtime-dashboard/node_modules"),
    }
)
_PROBE_DIRECTORY_CONTRACTS_PATH = Path("architecture/policies/directory_contracts.toml")
_HUGGINGFACE_CACHE_MEMBERS = ("blobs", "refs", "snapshots")


def _local_only_probe_roots(repo_root: Path) -> frozenset[Path]:
    """Read exact local-only roots from the directory owner contract."""
    contract_path, _relative = _resolve_probe_member(
        repo_root, _PROBE_DIRECTORY_CONTRACTS_PATH, required=False
    )
    if not contract_path.is_file():
        return frozenset()
    try:
        data = tomllib.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise OSError(f"unable to read local-only directory contract: {contract_path}") from error

    roots: set[Path] = set()
    for item in data.get("contract", []):
        if item.get("status") != "local_only":
            continue
        raw_path = item.get("path")
        if not isinstance(raw_path, str):
            raise OSError("local-only directory contract has a non-string path")
        local_path = Path(raw_path)
        if local_path.is_absolute() or not local_path.parts or ".." in local_path.parts:
            raise OSError(f"local-only directory contract path is unsafe: {raw_path!r}")
        roots.add(local_path)
    return frozenset(roots)


def _is_local_only_probe_path(relative: Path, local_roots: frozenset[Path]) -> bool:
    """Match owner-contract paths, never a directory basename."""
    return any(relative == local or local in relative.parents for local in local_roots)


def _resolve_probe_member(repo_root: Path, value: Path, *, required: bool) -> tuple[Path, Path]:
    """Resolve a declared member without following a symlink or escaping the checkout."""
    repository = repo_root.resolve()
    candidate = value if value.is_absolute() else repository / value
    try:
        relative = candidate.relative_to(repository)
    except ValueError as error:
        raise OSError(f"probe input is outside the repository: {candidate}") from error
    current = repository
    for component in relative.parts:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError as error:
            if required:
                raise OSError(f"required probe input is missing: {current}") from error
            break
        if stat.S_ISLNK(mode):
            raise OSError(f"probe input has a symlink component: {current}")
        if not current.resolve().is_relative_to(repository):
            raise OSError(f"probe input escapes the repository: {current}")
    if required and not candidate.exists():
        raise OSError(f"required probe input is missing: {candidate}")
    return candidate, relative


def _trust_claim_posture_compiler_inputs(repo_root: Path) -> tuple[Path, ...]:
    """Return explicit compiler reads; imports and subprocess reads stay unobserved."""
    from tools.quality.validation import check_trust_claim_posture

    with measure_file_reads(repo_root) as reads:
        check_trust_claim_posture.compile_claim_posture_register(repo_root)
    snapshot = reads.snapshot(complete_verdict=False)
    observed: set[Path] = set()
    for entry in snapshot["inputs"]:
        if (
            entry.get("operation") not in {"read_bytes", "read_text"}
            or entry.get("status") != "read"
        ):
            continue
        recorded = Path(str(entry["path"]))
        if recorded.is_absolute():
            raise OSError(f"trust compiler read outside its declared checkout: {recorded}")
        path, _relative = _resolve_probe_member(repo_root, recorded, required=True)
        observed.add(path)
    return tuple(sorted(observed))


def _locked_probe_local_path_sources(
    repo_root: Path,
    *,
    local_only_roots: frozenset[Path],
) -> tuple[tuple[Path, Path], ...]:
    """Resolve local package sources pinned by the selected Python lockfile."""
    lock_path, _lock_relative = _resolve_probe_member(
        repo_root,
        Path("uv.lock"),
        required=True,
    )
    try:
        lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise OSError(f"unable to read locked probe package sources: {lock_path}") from error

    packages = lock.get("package")
    if not isinstance(packages, list):
        raise OSError(f"uv.lock has no package table for probe source selection: {lock_path}")

    selected: dict[Path, Path] = {}
    for package in packages:
        if not isinstance(package, dict):
            raise OSError(f"uv.lock contains a malformed package entry: {lock_path}")
        source = package.get("source")
        if source is None:
            continue
        if not isinstance(source, dict):
            raise OSError(f"uv.lock contains a malformed package source: {lock_path}")
        if "path" not in source:
            continue
        raw_path = source["path"]
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise OSError(f"uv.lock contains a malformed local package path: {lock_path}")

        source_path = Path(raw_path)
        if (
            source_path.is_absolute()
            or PurePosixPath(raw_path).is_absolute()
            or PureWindowsPath(raw_path).is_absolute()
        ):
            raise OSError(
                f"locked package source path must be relative for isolated mirroring: {raw_path}"
            )
        path, relative = _resolve_probe_member(
            repo_root,
            source_path,
            required=True,
        )
        if relative == Path("."):
            raise OSError(
                "locked local package source resolves to the mirror root; "
                "the family input basis must remain bounded"
            )
        if _is_local_only_probe_path(relative, local_only_roots):
            raise OSError(f"locked package source is governed local-only state: {relative}")
        if any(
            relative == runtime or runtime in relative.parents for runtime in _PROBE_RUNTIME_LINKS
        ):
            raise OSError(f"locked package source is inside a runtime dependency tree: {relative}")
        selected[relative] = path

    return tuple(sorted(selected.items(), key=lambda item: item[0].as_posix()))


def _hatchling_wheel_probe_sources(
    repo_root: Path,
    *,
    local_only_roots: frozenset[Path],
) -> tuple[tuple[Path, Path], ...]:
    """Resolve literal source paths consumed by the active Hatchling wheel build."""
    repository = repo_root.resolve()
    pyproject_path, _pyproject_relative = _resolve_probe_member(
        repository, Path("pyproject.toml"), required=True
    )
    hatch_path, _hatch_relative = _resolve_probe_member(
        repository, Path("hatch.toml"), required=True
    )
    try:
        project_config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        external_hatch_config = tomllib.loads(hatch_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise OSError("unable to read Hatchling wheel probe configuration") from error

    build_system = project_config.get("build-system")
    if not isinstance(build_system, dict) or build_system.get("build-backend") != "hatchling.build":
        raise OSError(
            "isolated wheel source mirroring requires the standard hatchling.build backend"
        )
    backend_paths = build_system.get("backend-path", [])
    if not isinstance(backend_paths, list) or any(
        not isinstance(value, str) or not value for value in backend_paths
    ):
        raise OSError("pyproject.toml has a malformed Hatchling backend-path declaration")
    if backend_paths:
        raise OSError("custom Hatchling backend paths are not source-enumerable")

    tool_config = project_config.get("tool", {})
    if not isinstance(tool_config, dict):
        raise OSError("pyproject.toml has a malformed tool table")
    project_hatch_config = tool_config.get("hatch", {})
    if not isinstance(project_hatch_config, dict):
        raise OSError("pyproject.toml has a malformed tool.hatch table")
    if not isinstance(external_hatch_config, dict):
        raise OSError("hatch.toml must contain a table")

    # Hatchling overlays hatch.toml at the top level of tool.hatch. In particular, an
    # external `build` table replaces the project table instead of merging its children.
    hatch_config = dict(project_hatch_config)
    hatch_config.update(external_hatch_config)
    build_config = hatch_config.get("build", {})
    if not isinstance(build_config, dict):
        raise OSError("effective Hatchling build configuration must be a table")
    target_configs = build_config.get("targets", {})
    if not isinstance(target_configs, dict):
        raise OSError("effective Hatchling build targets must be a table")
    wheel_config = target_configs.get("wheel", {})
    if not isinstance(wheel_config, dict):
        raise OSError("effective Hatchling wheel target must be a table")

    # Admitted from Hatchling 1.27.0 BuilderConfig/WheelBuilderConfig. Keep the
    # selected input schema closed so a new upstream source field cannot be ignored.
    global_build_fields = frozenset(
        {
            "artifacts",
            "dependencies",
            "dev-mode-dirs",
            "dev-mode-exact",
            "directory",
            "exclude",
            "force-include",
            "hooks",
            "ignore-vcs",
            "include",
            "only-packages",
            "only-include",
            "packages",
            "reproducible",
            "require-runtime-dependencies",
            "require-runtime-features",
            "skip-excluded-dirs",
            "sources",
            "strict-naming",
            "targets",
        }
    )
    wheel_target_fields = (global_build_fields - {"targets"}) | frozenset(
        {
            "bypass-selection",
            "core-metadata-version",
            "extra-metadata",
            "macos-max-compat",
            "shared-data",
            "shared-scripts",
            "versions",
        }
    )
    for scope, config, admitted_fields in (
        ("global", build_config, global_build_fields),
        ("wheel target", wheel_config, wheel_target_fields),
    ):
        unknown_fields = set(config).difference(admitted_fields)
        if unknown_fields:
            raise OSError(
                f"Hatchling {scope} config has unsupported fields: "
                + ", ".join(sorted(unknown_fields))
            )

        for field in (
            "dependencies",
            "dev-mode-dirs",
            "exclude",
            "require-runtime-features",
            "versions",
        ):
            if field not in config:
                continue
            values = config[field]
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                raise OSError(f"Hatchling {scope} {field} must be a non-empty-string array")
            if field == "dependencies":
                for requirement in values:
                    direct_reference = requirement.strip().rsplit("@", 1)[-1].strip()
                    windows_reference = PureWindowsPath(direct_reference)
                    if (
                        direct_reference.lower().startswith(
                            ("file:", "git+file:", "./", "../", "~/", "/")
                        )
                        or windows_reference.drive
                        or windows_reference.root
                    ):
                        raise OSError(
                            "local Hatchling build dependencies are not source-enumerable"
                        )

        for field in (
            "dev-mode-exact",
            "ignore-vcs",
            "only-packages",
            "reproducible",
            "require-runtime-dependencies",
            "skip-excluded-dirs",
            "strict-naming",
            "bypass-selection",
            "macos-max-compat",
        ):
            if field in config and not isinstance(config[field], bool):
                raise OSError(f"Hatchling {scope} {field} must be a boolean")

        for field in ("directory", "core-metadata-version"):
            if field in config and not isinstance(config[field], str):
                raise OSError(f"Hatchling {scope} {field} must be a string")

        sources = config.get("sources")
        if sources is not None:
            valid_sources = (
                isinstance(sources, list)
                and all(isinstance(value, str) and value for value in sources)
            ) or (
                isinstance(sources, dict)
                and all(
                    isinstance(source, str) and isinstance(target, str)
                    for source, target in sources.items()
                )
            )
            if not valid_sources:
                raise OSError(f"Hatchling {scope} sources must be a string array or mapping")

    metadata_config = hatch_config.get("metadata", {})
    if not isinstance(metadata_config, dict):
        raise OSError("effective Hatchling metadata configuration must be a table")
    metadata_fields = frozenset({"allow-direct-references", "allow-ambiguous-features", "hooks"})
    unknown_metadata_fields = set(metadata_config).difference(metadata_fields)
    if unknown_metadata_fields:
        raise OSError(
            "Hatchling metadata config has unsupported fields: "
            + ", ".join(sorted(unknown_metadata_fields))
        )
    for field in ("allow-direct-references", "allow-ambiguous-features"):
        if field in metadata_config and not isinstance(metadata_config[field], bool):
            raise OSError(f"Hatchling metadata {field} must be a boolean")
    metadata_hooks = metadata_config.get("hooks", {})
    if not isinstance(metadata_hooks, dict):
        raise OSError("Hatchling metadata hooks must be a table")
    if metadata_hooks:
        raise OSError("Hatchling metadata hooks are not source-enumerable for isolated mirroring")

    for scope, config in (("global", build_config), ("wheel", wheel_config)):
        hooks = config.get("hooks", {})
        if not isinstance(hooks, dict):
            raise OSError(f"Hatchling {scope} build hooks must be a table")
        if hooks:
            raise OSError(
                f"Hatchling {scope} build hooks are not source-enumerable for isolated mirroring"
            )

    source_declarations: list[tuple[str, str]] = []
    for field in ("include", "packages", "only-include", "artifacts"):
        config = wheel_config if field in wheel_config else build_config
        values = config.get(field, [])
        if not isinstance(values, list):
            raise OSError(f"Hatchling wheel {field} must be an array of literal source paths")
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise OSError(f"Hatchling wheel {field} contains a malformed source path")
            source_declarations.append((field, value))

    force_include = (
        wheel_config["force-include"]
        if "force-include" in wheel_config
        else build_config.get("force-include", {})
    )
    if not isinstance(force_include, dict):
        raise OSError("Hatchling wheel force-include must be a source-to-target mapping")
    for source, target in force_include.items():
        if not isinstance(source, str) or not source.strip():
            raise OSError("Hatchling wheel force-include contains a malformed source path")
        if not isinstance(target, str) or not target.strip():
            raise OSError(f"Hatchling wheel force-include target is malformed for {source!r}")
        source_declarations.append(("force-include", source))

    for field in ("shared-data", "shared-scripts", "extra-metadata"):
        source_map = wheel_config.get(field, {})
        if not isinstance(source_map, dict):
            raise OSError(f"Hatchling wheel {field} must be a source-to-target mapping")
        for source, target in source_map.items():
            if not isinstance(source, str) or not source.strip():
                raise OSError(f"Hatchling wheel {field} contains a malformed source path")
            if not isinstance(target, str) or not target.strip():
                raise OSError(f"Hatchling wheel {field} contains a malformed target path")
            source_declarations.append((field, source))

    dev_mode_config = wheel_config if "dev-mode-dirs" in wheel_config else build_config
    for source in dev_mode_config.get("dev-mode-dirs", []):
        source_declarations.append(("dev-mode-dirs", source))

    project_metadata = project_config.get("project", {})
    if not isinstance(project_metadata, dict):
        raise OSError("pyproject.toml has a malformed project metadata table")
    dynamic_metadata = project_metadata.get("dynamic", [])
    if not isinstance(dynamic_metadata, list) or any(
        not isinstance(value, str) for value in dynamic_metadata
    ):
        raise OSError("pyproject.toml has malformed dynamic project metadata")
    if dynamic_metadata:
        raise OSError(
            "dynamic Hatchling project metadata is not source-enumerable: "
            + ", ".join(sorted(dynamic_metadata))
        )

    readme = project_metadata.get("readme")
    if isinstance(readme, str):
        source_declarations.append(("project.readme", readme))
    elif readme is not None:
        if not isinstance(readme, dict):
            raise OSError("project.readme must be a literal path or a table")
        has_file = "file" in readme
        has_text = "text" in readme
        if has_file == has_text:
            raise OSError("project.readme must declare exactly one of file or text")
        if has_file:
            value = readme["file"]
            if not isinstance(value, str) or not value.strip():
                raise OSError("project.readme.file must be a literal source path")
            source_declarations.append(("project.readme", value))
        elif not isinstance(readme["text"], str):
            raise OSError("project.readme.text must be a string")

    license_config = project_metadata.get("license")
    if isinstance(license_config, dict):
        has_file = "file" in license_config
        has_text = "text" in license_config
        if has_file == has_text:
            raise OSError("project.license must declare exactly one of file or text")
        if has_file:
            value = license_config["file"]
            if not isinstance(value, str) or not value.strip():
                raise OSError("project.license.file must be a literal source path")
            source_declarations.append(("project.license", value))
        elif not isinstance(license_config["text"], str):
            raise OSError("project.license.text must be a string")
    elif license_config is not None and not isinstance(license_config, str):
        raise OSError("project.license must be a string or a table")

    license_files: object = project_metadata.get(
        "license-files", ["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]
    )
    if isinstance(license_files, dict):
        license_files = license_files.get("globs", license_files.get("paths", []))
    if not isinstance(license_files, list):
        raise OSError("project.license-files must be an array of source paths")
    for pattern in license_files:
        if not isinstance(pattern, str) or not pattern.strip():
            raise OSError("project.license-files contains a malformed source path")
        if any(character in pattern for character in "*?[]"):
            windows_pattern = PureWindowsPath(pattern)
            if (
                "/" in pattern
                or "\\" in pattern
                or pattern.startswith("!")
                or Path(pattern).is_absolute()
                or PurePosixPath(pattern).is_absolute()
                or windows_pattern.is_absolute()
                or windows_pattern.drive
                or windows_pattern.root
                or ".." in PurePosixPath(pattern).parts
            ):
                raise OSError("license-file globs must be bounded root-level patterns: " + pattern)
            for match in sorted(repository.glob(pattern), key=lambda path: path.as_posix()):
                if match.is_file() or match.is_symlink():
                    source_declarations.append(
                        (
                            "project.license-files",
                            match.relative_to(repository).as_posix(),
                        )
                    )
        else:
            source_declarations.append(("project.license-files", pattern))

    if not source_declarations:
        raise OSError("Hatchling wheel source selection has no literal path basis")

    selected: dict[Path, Path] = {}
    for field, raw_path in source_declarations:
        windows_path = PureWindowsPath(raw_path)
        posix_path = PurePosixPath(raw_path)
        if raw_path.startswith("~"):
            raise OSError(f"Hatchling wheel source path cannot use home expansion: {raw_path}")
        if (
            Path(raw_path).is_absolute()
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or windows_path.root
        ):
            raise OSError(
                f"Hatchling wheel source path must be relative for isolated mirroring: {raw_path}"
            )
        if "\\" in raw_path or ".." in Path(raw_path).parts or ".." in posix_path.parts:
            raise OSError(
                f"Hatchling wheel source path must be a normalized relative path: {raw_path}"
            )
        if raw_path.startswith("!") or any(character in raw_path for character in "*?[]"):
            raise OSError(f"Hatchling wheel {field} requires a literal source path: {raw_path}")

        optional = field == "project.license-files"
        path, relative = _resolve_probe_member(repository, Path(raw_path), required=not optional)
        if optional and not path.is_file():
            continue
        if field in {"project.readme", "project.license"} and not path.is_file():
            raise OSError(f"Hatchling {field} source is not a file: {path}")
        if field == "dev-mode-dirs" and not path.is_dir():
            raise OSError(f"Hatchling {field} source is not a directory: {path}")
        if relative == Path("."):
            raise OSError(
                "Hatchling wheel source resolves to the mirror root; "
                "the family input basis must remain bounded"
            )
        if _is_local_only_probe_path(relative, local_only_roots):
            raise OSError(f"Hatchling wheel source is governed local-only state: {relative}")
        if any(
            relative == runtime or runtime in relative.parents for runtime in _PROBE_RUNTIME_LINKS
        ):
            raise OSError(f"Hatchling wheel source is inside a runtime dependency tree: {relative}")
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise OSError(f"Hatchling wheel source is not a file or directory: {path}")
        selected[relative] = path

    return tuple(sorted(selected.items(), key=lambda item: item[0].as_posix()))


def _selected_probe_roots(
    repo_root: Path,
    families: tuple[_ProbeInputFamily, ...],
) -> tuple[
    tuple[tuple[Path, Path], ...],
    tuple[Path, ...],
    tuple[Path, ...],
    str | None,
]:
    roots: dict[Path, Path] = {}
    required: set[Path] = set()
    runtime_links: set[Path] = set()
    local_only_roots = _local_only_probe_roots(repo_root)
    _resolve_probe_member(repo_root, _PROBE_DIRECTORY_CONTRACTS_PATH, required=True)
    for family in families:
        if (
            not family.probe_input_roots
            or not family.probe_required_paths
            or repo_root / _PROBE_DIRECTORY_CONTRACTS_PATH not in family.probe_required_paths
        ):
            raise OSError(f"{family.family_id} has no complete native probe input basis")
        uses_pnpm = family.output_probe_command is not None and any(
            "pnpm" in part for part in family.output_probe_command
        )
        if uses_pnpm and not family.probe_runtime_paths:
            raise OSError(f"{family.family_id} has no declared pnpm runtime profile")
        for value in family.probe_input_roots:
            path, relative = _resolve_probe_member(repo_root, value, required=True)
            if _is_local_only_probe_path(relative, local_only_roots):
                raise OSError(f"probe input root is governed local-only state: {relative}")
            if not path.is_dir():
                raise OSError(f"probe input root is not a directory: {path}")
            roots[relative] = path
        for value in family.probe_required_paths:
            path, relative = _resolve_probe_member(repo_root, value, required=True)
            if _is_local_only_probe_path(relative, local_only_roots):
                raise OSError(f"required probe input is governed local-only state: {relative}")
            if any(
                relative == runtime or runtime in relative.parents
                for runtime in _PROBE_RUNTIME_LINKS
            ):
                raise OSError(
                    f"required probe input is inside a runtime dependency tree: {relative}"
                )
            if path.is_dir():
                roots[relative] = path
            else:
                required.add(relative)
        for value in family.probe_runtime_paths:
            candidate = value if value.is_absolute() else repo_root / value
            try:
                relative = candidate.relative_to(repo_root.resolve())
            except ValueError as error:
                raise OSError(
                    f"probe runtime link is outside the repository: {candidate}"
                ) from error
            if relative not in _PROBE_RUNTIME_LINKS:
                raise OSError(f"probe runtime link is not an admitted package path: {relative}")
            _resolve_probe_member(repo_root, relative.parent, required=True)
            if not candidate.exists() and not candidate.is_symlink():
                raise OSError(f"required probe runtime dependency is missing: {candidate}")
            if not candidate.is_dir():
                raise OSError(f"probe runtime dependency is not a directory: {candidate}")
            try:
                resolved_runtime = candidate.resolve(strict=True)
            except OSError as error:
                raise OSError(f"probe runtime dependency is unresolved: {candidate}") from error
            if not resolved_runtime.is_relative_to(repo_root.resolve()):
                raise OSError(
                    f"probe runtime dependency resolves outside the repository: "
                    f"{candidate} -> {resolved_runtime}"
                )
            runtime_links.add(relative)
        if family.probe_runtime_paths:
            if (
                repo_root / "package.json" not in family.probe_required_paths
                or repo_root / "pnpm-lock.yaml" not in family.probe_required_paths
                or Path("node_modules")
                not in {
                    value.relative_to(repo_root)
                    for value in family.probe_runtime_paths
                    if value.is_absolute() and value.is_relative_to(repo_root)
                }
            ):
                raise OSError(
                    f"{family.family_id} runtime profile lacks the frozen pnpm input basis"
                )
        if family.family_id == "trust-claim-posture-register":
            for path in _trust_claim_posture_compiler_inputs(repo_root):
                _resolved, relative = _resolve_probe_member(repo_root, path, required=True)
                required.add(relative)
    if Path("uv.lock") in required:
        for relative, source in _locked_probe_local_path_sources(
            repo_root,
            local_only_roots=local_only_roots,
        ):
            if relative in required or any(
                relative == root or root in relative.parents for root in roots
            ):
                continue
            if source.is_dir():
                roots[relative] = source
            else:
                required.add(relative)

    if Path("hatch.toml") in required:
        for relative, source in _hatchling_wheel_probe_sources(
            repo_root, local_only_roots=local_only_roots
        ):
            if relative in required or any(
                relative == root or root in relative.parents for root in roots
            ):
                continue
            if source.is_dir():
                roots[relative] = source
            else:
                required.add(relative)

    runtime_inventory_digest = None
    if runtime_links:
        if Path("node_modules") not in runtime_links:
            raise OSError("frontend runtime profile has no root pnpm dependency link")
        runtime_inventory_digest = _verify_pnpm_install_receipt(repo_root, frozenset(runtime_links))
    return (
        tuple(sorted((path, relative) for relative, path in roots.items())),
        tuple(sorted(required)),
        tuple(sorted(runtime_links)),
        runtime_inventory_digest,
    )


def _pnpm_runtime_entry_digest(
    path: Path,
    repository: Path,
    *,
    ancestors: frozenset[Path],
    memo: dict[Path, bytes],
) -> bytes:
    """Hash one installed entry, including symlink provenance and resolved contents."""
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise OSError(f"cannot inspect pnpm runtime input: {path}") from error

    if stat.S_ISLNK(mode):
        try:
            raw_target = os.readlink(path)
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise OSError(f"pnpm runtime link is unresolved: {path}") from error
        if not resolved.is_relative_to(repository):
            raise OSError(f"pnpm runtime link resolves outside the checkout: {path} -> {resolved}")
        target_digest = _pnpm_runtime_entry_digest(
            resolved,
            repository,
            ancestors=ancestors,
            memo=memo,
        )
        return hashlib.sha256(
            b"symlink\0"
            + os.fsencode(raw_target)
            + b"\0"
            + resolved.relative_to(repository).as_posix().encode("utf-8")
            + b"\0"
            + target_digest
        ).digest()

    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise OSError(f"pnpm runtime input is unresolved: {path}") from error
    if not resolved.is_relative_to(repository):
        raise OSError(f"pnpm runtime input resolves outside the checkout: {path} -> {resolved}")
    if resolved in memo:
        return memo[resolved]

    if stat.S_ISREG(mode):
        digest = hashlib.sha256()
        digest.update(f"file\0{stat.S_IMODE(mode)}\0".encode("ascii"))
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        except OSError as error:
            raise OSError(f"cannot read pnpm runtime input: {path}") from error
        result = digest.digest()
    elif stat.S_ISDIR(mode):
        if resolved in ancestors:
            raise OSError(f"pnpm runtime directory contains a link cycle: {path}")
        digest = hashlib.sha256()
        digest.update(f"directory\0{stat.S_IMODE(mode)}\0".encode("ascii"))
        next_ancestors = ancestors | {resolved}
        try:
            children = sorted(path.iterdir(), key=lambda item: item.name)
        except OSError as error:
            raise OSError(f"cannot enumerate pnpm runtime directory: {path}") from error
        for child in children:
            digest.update(os.fsencode(child.name))
            digest.update(b"\0")
            digest.update(
                _pnpm_runtime_entry_digest(
                    child,
                    repository,
                    ancestors=next_ancestors,
                    memo=memo,
                )
            )
        result = digest.digest()
    else:
        raise OSError(f"pnpm runtime contains an unsupported special file: {path}")

    memo[resolved] = result
    return result


def _pnpm_runtime_inventory_digest(
    repo_root: Path,
    runtime_paths: frozenset[Path],
) -> str:
    """Derive a complete installed-tree digest from declared runtime paths."""
    repository = repo_root.resolve()
    if Path("node_modules") not in runtime_paths:
        raise OSError("pnpm runtime inventory has no root node_modules tree")
    inventory = hashlib.sha256()
    memo: dict[Path, bytes] = {}
    for relative in sorted(runtime_paths):
        if relative not in _PROBE_RUNTIME_LINKS:
            raise OSError(f"pnpm runtime path is not admitted: {relative}")
        candidate = repository / relative
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as error:
            raise OSError(f"pnpm runtime path is unresolved: {candidate}") from error
        if not resolved.is_relative_to(repository):
            raise OSError(f"pnpm runtime path resolves outside the checkout: {candidate}")
        if not candidate.is_dir():
            raise OSError(f"pnpm runtime path is not a directory: {candidate}")
        inventory.update(relative.as_posix().encode("utf-8"))
        inventory.update(b"\0")
        inventory.update(
            _pnpm_runtime_entry_digest(
                candidate,
                repository,
                ancestors=frozenset(),
                memo=memo,
            )
        )
    return inventory.hexdigest()


def _verify_pnpm_install_receipt(
    repo_root: Path,
    runtime_paths: frozenset[Path],
) -> str:
    """Bind lock metadata and every installed runtime target/content to this checkout."""
    package_path = repo_root / "package.json"
    lock_path = repo_root / "pnpm-lock.yaml"
    installed_lock_path = repo_root / "node_modules/.pnpm/lock.yaml"
    modules_path = repo_root / "node_modules/.modules.yaml"
    paths = (package_path, lock_path, installed_lock_path, modules_path)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise OSError(
            "pnpm runtime link has no complete install receipt: "
            + ", ".join(str(path) for path in missing)
        )
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
        install = yaml.safe_load(modules_path.read_text(encoding="utf-8"))
        frozen_lock = lock_path.read_bytes()
        installed_lock = installed_lock_path.read_bytes()
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise OSError("unable to read the pnpm lock/install receipt") from error
    package_manager = package.get("packageManager") if isinstance(package, dict) else None
    installed_manager = install.get("packageManager") if isinstance(install, dict) else None
    if (
        not isinstance(package_manager, str)
        or installed_manager != package_manager
        or installed_lock != frozen_lock
    ):
        raise OSError("pnpm node_modules does not match package.json and the frozen pnpm lockfile")
    return _pnpm_runtime_inventory_digest(repo_root, runtime_paths)


def _probe_walk_error(error: OSError) -> None:
    """Fail admission when a selected source directory cannot be enumerated."""
    raise OSError(f"unable to enumerate selected probe source: {error}") from error


def _copy_isolated_probe_source(
    repo_root: Path,
    destination: Path,
    *,
    families: tuple[_ProbeInputFamily, ...],
) -> tuple[tuple[Path, ...], str | None]:
    """Copy the family-declared source basis, including ignored files under its roots."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"isolated probe source already exists: {destination}")
    repository = repo_root.resolve()
    families = tuple(families)
    if not families:
        raise OSError("isolated probe source requires an explicit family input basis")
    roots, required_paths, runtime_links, runtime_inventory_digest = _selected_probe_roots(
        repository, families
    )
    if not roots:
        raise OSError("isolated probe source has no selected filesystem input roots")
    local_only_roots = _local_only_probe_roots(repository)
    files: dict[Path, Path] = {}
    directories: set[Path] = set()
    root_relatives = tuple(relative for _path, relative in roots)
    required_relatives = set(required_paths)

    def selected(relative: Path) -> bool:
        if _is_local_only_probe_path(relative, local_only_roots):
            return False
        return relative in required_relatives or any(
            relative == root or root in relative.parents for root in root_relatives
        )

    # A complete filesystem walk admits ignored and untracked source. Git supplies an
    # independent missing-tracked-file check; it does not define the source set.
    for tracked in iter_repository_files(repository):
        try:
            relative = tracked.relative_to(repository)
        except ValueError as error:
            raise OSError(f"tracked probe path is outside the repository: {tracked}") from error
        if selected(relative):
            if any(relative == runtime or runtime in relative.parents for runtime in runtime_links):
                continue
            path, _relative = _resolve_probe_member(repository, relative, required=True)
            if not path.is_file():
                raise OSError(f"tracked probe input is not a file: {path}")
            files[relative] = path

    root_link_relatives = set(runtime_links)
    for source_root, _root_relative in roots:
        for current, dirnames, filenames in os.walk(
            source_root,
            topdown=True,
            followlinks=False,
            onerror=_probe_walk_error,
        ):
            current_path = Path(current)
            relative_current = current_path.relative_to(repository)
            kept_directories: list[str] = []
            for name in sorted(dirnames):
                path = current_path / name
                relative = path.relative_to(repository)
                if relative in root_link_relatives:
                    continue
                if _is_local_only_probe_path(relative, local_only_roots):
                    continue
                _resolve_probe_member(repository, relative, required=True)
                if path.is_symlink():
                    raise OSError(f"probe source directory is a symlink: {path}")
                kept_directories.append(name)
                directories.add(relative)
            dirnames[:] = kept_directories
            for name in sorted(filenames):
                path = current_path / name
                relative = path.relative_to(repository)
                _resolved, _ = _resolve_probe_member(repository, relative, required=True)
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode):
                    raise OSError(f"probe source file is a symlink: {path}")
                if not stat.S_ISREG(mode):
                    raise OSError(f"probe source contains an unsupported special file: {path}")
                files[relative] = path
            directories.add(relative_current)

    for relative in required_relatives:
        path, _relative = _resolve_probe_member(repository, relative, required=True)
        if not path.is_file():
            raise OSError(f"required probe input is not a file: {path}")
        files[relative] = path

    # Preflight space before creating the destination or copying a single source byte.
    required_bytes = sum(path.stat().st_size for path in files.values())
    disk_usage_path = destination.parent
    while not disk_usage_path.exists():
        parent = disk_usage_path.parent
        if parent == disk_usage_path:
            raise OSError(f"unable to locate an existing filesystem for {destination}")
        disk_usage_path = parent
    free_bytes = shutil.disk_usage(disk_usage_path).free
    reserve = max(64 * 1024 * 1024, required_bytes // 10)
    if free_bytes < required_bytes + reserve:
        raise OSError(
            f"insufficient disk space for isolated probe source: "
            f"need {required_bytes + reserve} bytes, have {free_bytes}"
        )

    destination.mkdir(parents=True)
    for relative in sorted(directories, key=lambda item: (len(item.parts), item.as_posix())):
        (destination / relative).mkdir(parents=True, exist_ok=True)
    for relative, source in sorted(files.items(), key=lambda item: item[0].as_posix()):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    # These paths are runtime package dependencies, not family source. They stay linked
    # to the frozen workspace installation and are never copied as source.
    for relative in runtime_links:
        source = repository / relative
        if not source.exists() and not source.is_symlink():
            raise OSError(f"required probe runtime dependency disappeared: {source}")
        if not source.is_dir():
            raise OSError(f"declared probe runtime dependency is not a directory: {source}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source.resolve(), target_is_directory=True)
    return tuple(sorted(runtime_links)), runtime_inventory_digest


def _mapped_governed_artifact_root(
    repo_root: Path,
    source_root: Path,
    families: tuple[GeneratedArtifactFamily, ...],
    configured_root: str | None,
) -> str | None:
    """Map a governed-artifact root into the selected clone or refuse ambient reads."""
    if configured_root is None or not configured_root.strip():
        return None
    repository = repo_root.resolve()
    configured = Path(configured_root).expanduser()
    if not configured.is_absolute():
        configured = repository / configured
    source, relative = _resolve_probe_member(repository, configured, required=True)
    roots, required, _runtime_links, _runtime_inventory = _selected_probe_roots(
        repository, families
    )
    if not (
        relative in set(required)
        or any(
            relative == root_relative or root_relative in relative.parents
            for _path, root_relative in roots
        )
    ):
        raise OSError(f"governed artifact root is outside the selected family basis: {source}")
    mapped = source_root / relative
    if not mapped.exists():
        raise OSError(f"governed artifact root is absent from the isolated source: {mapped}")
    return str(mapped.resolve())


def _isolated_probe_environment(
    source_root: Path,
    *,
    uv_cache_dir: Path | None = None,
    offline: bool = False,
    repo_root: Path | None = None,
    families: tuple[GeneratedArtifactFamily, ...] = (),
) -> dict[str, str]:
    """Bind probe imports, private environment, and selected cache to copied source."""
    private_environment = source_root.parent / "environment"
    bytecode_cache_root = source_root.parent / "python-bytecode-cache"
    cache_root = uv_cache_dir or source_root.parent / "uv-cache"
    environment = os.environ.copy()
    governed_root = environment.pop("POLISYOS_GOVERNED_ARTIFACT_ROOT", None)
    for name in (
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "PYTHONHOME",
        "PYTHONPYCACHEPREFIX",
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
            "PYTHONPYCACHEPREFIX": str(bytecode_cache_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "POLISYOS_TOOLS_TIMING_LOG": str(source_root.parent / "diagnostics" / "timing.jsonl"),
            "PATH": os.pathsep.join(
                (str(private_environment / "bin"), environment.get("PATH", ""))
            ),
        }
    )
    mapped_governed_root = _mapped_governed_artifact_root(
        repo_root or REPO_ROOT,
        source_root,
        families,
        governed_root,
    )
    if mapped_governed_root is not None:
        environment["POLISYOS_GOVERNED_ARTIFACT_ROOT"] = mapped_governed_root
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
            f"Retained generated-freshness workspace resolves to an existing path: {retained_root}"
        )

    repository_root = REPO_ROOT.resolve()
    if retained_root.is_relative_to(repository_root):
        raise ValueError(
            "Retained generated-freshness workspace must be outside the repository root."
        )
    production_data = REPO_ROOT / "production_data"
    if production_data.exists() and retained_root.is_relative_to(production_data.resolve()):
        raise ValueError("Retained generated-freshness workspace must be outside production_data.")
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
        cursor.unrun_checks.append(UnrunGeneratedCheck(family.family_id, "generator", str(error)))
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
                        f"{family.family_id} expected output is missing: {expected.as_posix()}."
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
        runtime_paths, runtime_inventory_digest = _copy_isolated_probe_source(
            REPO_ROOT,
            isolated_repo_root,
            families=required_families,
        )
        if runtime_inventory_digest is not None:
            print(f"Native pnpm runtime input inventory SHA-256: {runtime_inventory_digest}")
        environment = _isolated_probe_environment(
            isolated_repo_root,
            uv_cache_dir=uv_cache_dir,
            offline=offline,
            repo_root=REPO_ROOT,
            families=required_families,
        )
        _prepare_isolated_probe_environment(isolated_repo_root, environment)
        if (REPO_ROOT / "src/polisyos").is_dir():
            _verify_isolated_python_import_origins(
                isolated_repo_root,
                python_executable=Path(environment["UV_PROJECT_ENVIRONMENT"]) / "bin/python",
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
    if runtime_inventory_digest is not None:
        try:
            final_runtime_digest = _verify_pnpm_install_receipt(REPO_ROOT, frozenset(runtime_paths))
        except OSError as error:
            final_runtime_digest = None
            diagnostic = f"pnpm runtime input inventory became unavailable: {error}"
        else:
            diagnostic = "pnpm runtime input inventory changed during generated-artifact probes"
        if final_runtime_digest != runtime_inventory_digest:
            affected = [
                UnrunGeneratedCheck(family.family_id, "environment", diagnostic)
                for family in required_families
                if family.probe_runtime_paths
            ]
            raise GeneratedArtifactCheckUnrunError(affected, cursor.violations)


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
            if production_data.exists() and resolved_cache_dir.is_relative_to(
                production_data.resolve()
            ):
                raise ValueError("The uv cache must be outside production_data.")
        resolved_workspace_root = (
            retained_workspace_root.expanduser().resolve()
            if retained_workspace_root is not None
            else None
        )
        if resolved_workspace_root is not None and resolved_cache_dir is not None:
            if resolved_workspace_root.is_relative_to(
                resolved_cache_dir
            ) or resolved_cache_dir.is_relative_to(resolved_workspace_root):
                raise ValueError("Retained workspace and existing uv cache must be separate paths.")
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
                "scratch_cleanup" if retained_workspace_root is None else "aggregate_verdict"
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
        for detail, snippet, message in WORKFLOW_BASELINE_REQUIREMENTS.get(workflow_rel, ()):
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
        for detail, snippet, message in WORKFLOW_BASELINE_FORBIDDEN.get(workflow_rel, ()):
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
        if edge.resolution_status == "not_established":
            violations.append(
                GuardrailViolation(
                    check="deep_import_resolution",
                    subject=edge.source_module,
                    detail=f"fromlist_resolution_{edge.resolution_reason or 'not_established'}",
                    source_module=edge.source_module,
                    target_module=edge.target_module,
                    message=(
                        "Unresolved from-list fallback candidate: "
                        f"{edge.source_module} -> {edge.target_module} "
                        f"({edge.source_file}). "
                        + {
                            "export_manifest_unresolved": (
                                "A complete facade export manifest could not be resolved; "
                                "this candidate is not baselinable."
                            ),
                            "name_not_declared_export": (
                                "The complete facade __all__ does not declare this name; "
                                "runtime lookup may still be dynamic, so this candidate is not baselinable."
                            ),
                            "bound_but_unlisted": (
                                "A unique direct module binding exists, but the complete facade "
                                "__all__ does not declare it; this candidate is not baselinable."
                            ),
                            "declared_binding_unproven": (
                                "The facade __all__ declares this name, but a unique direct "
                                "module binding was not established; this candidate is not baselinable."
                            ),
                        }.get(
                            edge.resolution_reason or "",
                            "A required facade property is not established.",
                        )
                    ),
                )
            )
            continue
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
    try:
        families = _parse_generated_artifacts(args.generated_manifest)
    except GeneratedArtifactManifestSchemaError as error:
        print(f"Generated artifact manifest schema error: {error}", file=sys.stderr)
        return 1
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
