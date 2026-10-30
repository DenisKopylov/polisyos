#!/usr/bin/env python3
"""Phase 3A decomposition preflight inventory and gates."""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import importlib.util
import inspect
import json
import os
import pickle
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from dataclasses import fields as dataclass_fields
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median
from typing import Any, Literal

from tools.lib.fs import atomic_write_bytes, atomic_write_json, atomic_write_text
from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
BASELINE_DIR = REPO_ROOT / "architecture" / "baselines" / "structure_remediation"
BLUEPRINT_PATH = REPO_ROOT / "docs" / "plans" / "active" / "DECOMPOSITION_BLUEPRINT.md"
DYNAMIC_IMPORTS_PATH = REPO_ROOT / "architecture" / "imports" / "dynamic.toml"
LAZY_IMPORTS_PATH = REPO_ROOT / "architecture" / "imports" / "lazy.toml"
SCHEMA_BASELINE_PATH = BASELINE_DIR / "schema_diff_pre_decomp.json"
PUBLIC_SURFACE_BASELINE_PATH = BASELINE_DIR / "public_surface_pre_decomp.json"
IMPORT_GRAPH_BASELINE_PATH = BASELINE_DIR / "import_graph_pre_decomp.json"
IMPORT_TIME_BASELINE_PATH = BASELINE_DIR / "import_time_pre_decomp.json"
PICKLE_INVENTORY_PATH = BASELINE_DIR / "pickle_checkpoint_inventory.json"
TESTS_BASELINE_PATH = BASELINE_DIR / "tests_baseline.txt"
CHECKPOINT_FIXTURE_ROOT = REPO_ROOT / "tests" / "_data" / "checkpoint_compat"

AUDIT_SCOPES = ("src", "tests", "tools", "apps", "packages")
TEXT_SUFFIXES = {
    ".py",
    ".pyi",
    ".md",
    ".rst",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
}
DYNAMIC_CALL_NAMES = {
    "importlib.import_module",
    "__import__",
    "pkgutil.iter_modules",
    "pkgutil.walk_packages",
    "importlib.resources.files",
    "importlib.metadata.entry_points",
    "metadata.entry_points",
    "pkg_resources.iter_entry_points",
    "list_entry_points",
}
EXTENSION_ENTRY_POINT_GROUP_NAMES = {
    "polisyos.fabric_connectors",
    "polisyos.scientist_governance_passes",
    "polisyos.foundry_methods",
    "polisyos.scientist_nodes",
    "polisyos.data_forge_domains",
    "polisyos.lex_normpacks",
    "polisyos.runtime_middlewares",
    "polisyos.norm_pack_providers",
}
PICKLE_PATTERNS = (
    "pickle.dump",
    "pickle.load",
    "pickle.dumps",
    "pickle.loads",
    "cloudpickle",
    "joblib.dump",
    "joblib.load",
    "torch.save",
    "torch.load",
    "dill",
)
REGISTRATION_PATTERNS = (
    "jax.tree_util.register_pytree_node",
    "jax.tree_util.register_pytree_node_class",
    "register_pytree_node",
    "register_pytree_node_class",
    "register_dataclass",
    "model_rebuild",
    "update_forward_refs",
    "discriminator",
)
PUBLIC_FACADE_FILES = {"__init__.py", "api.py", "_api.py"}

MOVE_TARGETS: Mapping[str, tuple[str, str]] = {
    "polisyos.scientist.feedback": (
        "polisyos.scientist.feedback.core",
        "Feedback loop logic becomes a package with explicit core/utils modules.",
    ),
}


@dataclass(frozen=True)
class Finding:
    gate: str
    message: str
    detail: str = ""

    def render(self) -> str:
        suffix = f" :: {self.detail}" if self.detail else ""
        return f"[{self.gate}] {self.message}{suffix}"


@dataclass(frozen=True)
class _ImportSourceSnapshot:
    """One immutable observation of the source files used by the cycle gate."""

    module_paths: dict[str, Path]
    trees: dict[str, ast.Module]
    input_manifest: tuple[dict[str, Any], ...]
    discovery_errors: tuple[dict[str, Any], ...]


class ImportGraphInputError(RuntimeError):
    """Raised when a complete import graph cannot be built from selected source."""

    def __init__(self, message: str, *, source_snapshot: _ImportSourceSnapshot) -> None:
        super().__init__(message)
        self.source_snapshot = source_snapshot


class DynamicImportCollectionError(RuntimeError):
    """Raised when selected source cannot be completely inventoried."""


class DynamicImportReviewMetadataError(ValueError):
    """Raised when owner-supplied dynamic import review metadata is invalid."""


class DynamicImportSourcePathError(DynamicImportCollectionError):
    """Raised when a selected source path cannot be safely labeled in-repository."""


def _import_source_path(path: Path) -> str:
    """Return a lexical, repository-relative label without resolving symlinks."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _read_import_source_bytes(path: Path) -> bytes:
    """Read one selected source file so the same bytes can be hashed and parsed."""
    return path.read_bytes()


def _collect_import_source_snapshot() -> _ImportSourceSnapshot:
    """Enumerate and parse every source selected by the import-cycle gate."""
    roots = [SRC_ROOT / "polisyos" / "scientist", SRC_ROOT / "polisyos" / "foundry"]
    module_paths: dict[str, Path] = {}
    trees: dict[str, ast.Module] = {}
    manifest: list[dict[str, Any]] = []
    discovery_errors: list[dict[str, Any]] = []

    def record_walk_error(error: OSError, *, root: Path) -> None:
        filename = Path(error.filename) if error.filename else root
        discovery_errors.append(
            {
                "path": _import_source_path(filename),
                "outcome": "discovery_error",
                "error_type": type(error).__name__,
                "error": error.strerror or str(error),
            }
        )

    for root in roots:
        if not root.is_dir():
            discovery_errors.append(
                {
                    "path": _import_source_path(root),
                    "outcome": "root_unavailable",
                    "error_type": "FileNotFoundError",
                    "error": "selected import root is absent or is not a directory",
                }
            )
            continue

        def onerror(error: OSError, *, selected_root: Path = root) -> None:
            record_walk_error(error, root=selected_root)

        for directory, dirnames, filenames in os.walk(root, onerror=onerror):
            dirnames[:] = sorted(name for name in dirnames if name != "__pycache__")
            for filename in sorted(filenames):
                if Path(filename).suffix != ".py":
                    continue
                path = Path(directory) / filename
                label = _import_source_path(path)
                try:
                    if not stat.S_ISREG(path.stat().st_mode):
                        continue
                except OSError as error:
                    discovery_errors.append(
                        {
                            "path": label,
                            "outcome": "stat_error",
                            "error_type": type(error).__name__,
                            "error": error.strerror or str(error),
                        }
                    )
                    continue
                try:
                    raw = _read_import_source_bytes(path)
                except OSError as error:
                    manifest.append(
                        {
                            "path": label,
                            "sha256": None,
                            "outcome": "read_error",
                            "error_type": type(error).__name__,
                            "error": error.strerror or str(error),
                        }
                    )
                    continue
                digest = hashlib.sha256(raw).hexdigest()
                try:
                    module = module_fqn_from_path(path)
                except (OSError, ValueError) as error:
                    manifest.append(
                        {
                            "path": label,
                            "sha256": digest,
                            "outcome": "identity_error",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    )
                    continue
                if module in module_paths:
                    manifest.append(
                        {
                            "path": label,
                            "sha256": digest,
                            "outcome": "duplicate_module_identity",
                            "module": module,
                            "error_type": "ValueError",
                            "error": f"selected source maps to existing module {module}",
                        }
                    )
                    continue
                module_paths[module] = path
                try:
                    text = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as error:
                    manifest.append(
                        {
                            "path": label,
                            "sha256": digest,
                            "outcome": "decode_error",
                            "encoding": "utf-8",
                            "start": error.start,
                            "end": error.end,
                            "error": error.reason,
                        }
                    )
                    continue
                try:
                    tree = ast.parse(text, filename=label)
                except SyntaxError as error:
                    manifest.append(
                        {
                            "path": label,
                            "sha256": digest,
                            "outcome": "parse_error",
                            "error_type": type(error).__name__,
                            "line": error.lineno,
                            "offset": error.offset,
                            "error": error.msg,
                        }
                    )
                    continue
                except (ValueError, RecursionError) as error:
                    manifest.append(
                        {
                            "path": label,
                            "sha256": digest,
                            "outcome": "parse_error",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    )
                    continue
                trees[module] = tree
                manifest.append({"path": label, "sha256": digest, "outcome": "parsed"})

    manifest.sort(key=lambda item: str(item["path"]))
    discovery_errors.sort(key=lambda item: (str(item["path"]), str(item["outcome"])))
    return _ImportSourceSnapshot(
        module_paths=module_paths,
        trees=trees,
        input_manifest=tuple(manifest),
        discovery_errors=tuple(discovery_errors),
    )


def _import_source_errors(snapshot: _ImportSourceSnapshot) -> list[dict[str, Any]]:
    errors = [dict(item) for item in snapshot.discovery_errors]
    errors.extend(dict(item) for item in snapshot.input_manifest if item["outcome"] != "parsed")
    return errors


def _import_graph_input_receipt(snapshot: _ImportSourceSnapshot) -> dict[str, Any]:
    """Build the complete, content-bound receipt for a deciding cycle-gate run."""
    selector = {
        "roots": [
            _import_source_path(SRC_ROOT / "polisyos" / "scientist"),
            _import_source_path(SRC_ROOT / "polisyos" / "foundry"),
        ],
        "recursive": True,
        "filename_suffix": ".py",
        "regular_files_only": True,
        "symlink_file_policy": "follow-target",
        "follow_symlink_directories": False,
        "excluded_directory_names": ["__pycache__"],
        "encoding": "utf-8-strict",
        "parser": "ast.parse",
    }
    inputs = [dict(item) for item in snapshot.input_manifest]
    discovery_errors = [dict(item) for item in snapshot.discovery_errors]
    hashed_payload = {
        "selector": selector,
        "input_manifest": inputs,
        "discovery_errors": discovery_errors,
    }
    manifest_hash = hashlib.sha256(
        json.dumps(
            hashed_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    counts: dict[str, int] = {}
    for item in inputs:
        outcome = str(item["outcome"])
        counts[outcome] = counts.get(outcome, 0) + 1
    errors = _import_source_errors(snapshot)
    full_graph = collect_import_graph(source_snapshot=snapshot, allow_incomplete=True)
    eager_graph = collect_import_graph(
        runtime_only=True, source_snapshot=snapshot, allow_incomplete=True
    )
    return {
        "selector": selector,
        "selected_count": len(inputs),
        "outcome_counts": dict(sorted(counts.items())),
        "discovery_errors": discovery_errors,
        "input_manifest_sha256": manifest_hash,
        "input_manifest": inputs,
        "coverage_status": "complete" if not errors else "partial",
        "observed_graphs": {
            "full_ast": {
                "module_count": full_graph["module_count"],
                "edge_count": full_graph["edge_count"],
                "cycles": full_graph["cycles"],
            },
            "module_initialization": {
                "module_count": eager_graph["module_count"],
                "edge_count": eager_graph["edge_count"],
                "cycles": eager_graph["cycles"],
                "dispatch_resolution": eager_graph["dispatch_resolution"],
            },
        },
    }


def _rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _diagnostic_path(path: Path) -> str:
    """Format a path for diagnostics without weakening repository containment checks.

    Validators may be given temporary paths by tests or callers. Keep `_rel`
    strict for inventory identities, but make an out-of-repository diagnostic
    useful instead of raising while handling the original input error.
    """
    try:
        return _rel(path)
    except OSError, RuntimeError, ValueError:
        return path.as_posix()


def _sha(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _iter_text_files(*scopes: str) -> Iterable[Path]:
    ignored_parts = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "_build",
        "_cache",
        ".venv",
        "node_modules",
    }
    for scope in scopes:
        root = REPO_ROOT / scope
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            if ignored_parts.intersection(path.parts):
                continue
            yield path


def _parse_python(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except OSError, SyntaxError, UnicodeDecodeError:
        return None


def _shim_source_python_path(path: Path) -> Path:
    if path.is_dir():
        return path / "__init__.py"
    return path


def module_fqn_from_path(path: Path) -> str:
    rel = path.resolve().relative_to(SRC_ROOT).with_suffix("")
    parts = rel.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def path_from_module_fqn(module: str) -> Path:
    parts = module.split(".")
    if parts[0] != "polisyos":
        raise ValueError(f"Only polisyos modules are supported: {module}")
    return SRC_ROOT.joinpath(*parts).with_suffix(".py")


def loose_root_modules(package: str) -> list[dict[str, Any]]:
    root = SRC_ROOT / "polisyos" / package
    modules: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.py")):
        if path.name in PUBLIC_FACADE_FILES:
            continue
        source_fqn = module_fqn_from_path(path)
        target_fqn, reasoning = MOVE_TARGETS.get(
            source_fqn,
            (f"polisyos.{package}._internal.{path.stem.lstrip('_')}", "Default internal bucket."),
        )
        modules.append(
            {
                "package": package,
                "source_fqn": source_fqn,
                "target_fqn": target_fqn,
                "type": "internal" if path.stem.startswith("_") else "public",
                "source_path": _rel(path),
                "target_path": _rel(path_from_module_fqn(target_fqn)),
                "lines": len(path.read_text(encoding="utf-8").splitlines()),
                "reasoning": reasoning,
            }
        )
    return modules


def collect_move_map() -> list[dict[str, Any]]:
    return [*loose_root_modules("scientist"), *loose_root_modules("foundry")]


def _imported_module_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _imported_module_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_pattern(
    node: ast.Call,
    *,
    call_name: str | None = None,
    first_argument_binding: _DynamicImportBinding | None = None,
) -> tuple[str, str, list[str]]:
    call_name = call_name or _imported_module_name(node.func)
    first_arg = _literal_string(node.args[0]) if node.args else None
    keyword_group = next(
        (_literal_string(keyword.value) for keyword in node.keywords if keyword.arg == "group"),
        None,
    )
    if first_arg is not None:
        pattern = first_arg
    elif keyword_group is not None:
        pattern = f"group:{keyword_group}"
    else:
        try:
            pattern = ast.unparse(node.args[0]) if node.args else ast.unparse(node)
        except Exception:
            pattern = "<dynamic>"
    allowed_targets = _allowed_targets_for_pattern(call_name, pattern)
    if not allowed_targets and first_argument_binding is not None:
        alternatives = _dynamic_binding_alternatives(first_argument_binding)
        if alternatives is not None and alternatives:
            values: list[str] = []
            for item in alternatives:
                if (
                    item.kind != "string"
                    or item.name is None
                    or not item.name.startswith("polisyos.")
                ):
                    values = []
                    break
                values.append(item.name.split(":", 1)[0])
            if values:
                allowed_targets = sorted(set(values))
    return call_name, pattern, allowed_targets


def _entry_point_targets(group: str) -> list[str]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    groups = pyproject.get("project", {}).get("entry-points", {})
    raw = groups.get(group, {})
    targets: list[str] = []
    if isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, str):
                module = value.split(":", 1)[0]
                if module.startswith("polisyos."):
                    targets.append(module)
    return sorted(set(targets))


def _allowed_targets_for_pattern(call_name: str, pattern: str) -> list[str]:
    if pattern.startswith("group:"):
        return _entry_point_targets(pattern.removeprefix("group:"))
    if pattern in EXTENSION_ENTRY_POINT_GROUP_NAMES:
        return _entry_point_targets(pattern)
    if call_name.endswith("entry_points") and pattern.startswith("polisyos."):
        return _entry_point_targets(pattern)
    if pattern.startswith("polisyos."):
        return [pattern.split(":", 1)[0]]
    return []


def _owner_for_path(path: Path, *, relative_path: str | None = None) -> str:
    rel = relative_path or _rel(path)
    if "/scientist/" in rel or rel.startswith("src/polisyos/scientist"):
        return "team-scientist"
    if "/foundry/" in rel or rel.startswith("src/polisyos/foundry"):
        return "team-foundry"
    if rel.startswith("tools/"):
        return "team-devx"
    if rel.startswith(("apps/", "packages/")):
        return "team-frontend"
    return "team-architecture"


_DYNAMIC_IMPORT_GUARDED_ROOTS = frozenset(
    {"importlib", "metadata", "pkgutil", "pkg_resources", "__import__", "list_entry_points"}
)
_DYNAMIC_IMPORT_MODULE_PREFIXES = frozenset(
    {
        "importlib",
        "importlib.metadata",
        "importlib.resources",
        "metadata",
        "pkgutil",
        "pkg_resources",
    }
)
_DYNAMIC_IMPORT_CALLABLE_NAMES = frozenset(
    {
        "import_module",
        "__import__",
        "iter_modules",
        "walk_packages",
        "files",
        "entry_points",
        "iter_entry_points",
        "list_entry_points",
    }
)
_DYNAMIC_IMPORT_TEMPORAL_CALLABLES = DYNAMIC_CALL_NAMES | frozenset(
    {
        "builtins.eval",
        "builtins.exec",
        "builtins.getattr",
        "builtins.globals",
        "builtins.locals",
        "builtins.vars",
    }
)
_DYNAMIC_ITERABLE_CONSTRUCTORS = frozenset({"frozenset", "list", "set", "sorted", "tuple"})
_DYNAMIC_CAPABILITY_PREDICATES = frozenset({"callable", "isinstance", "issubclass"})
_DYNAMIC_MODULE_NAMESPACE_FACTORIES = frozenset(
    {"builtins.globals", "builtins.locals", "builtins.vars"}
)
_DYNAMIC_COMPREHENSION_VALUE_LIMIT = 1024


@dataclass(frozen=True, slots=True)
class _DynamicSourceCodeOrigin:
    """Selected immutable code identity, separate from a mutable function object."""

    identity: str
    context_identity: str
    content_sha256: str
    source_module: str
    relative_path: str
    node: ast.FunctionDef
    free_variables: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _DynamicImportBinding:
    """A bounded source-level binding fact for the dynamic-import collector."""

    kind: Literal[
        "module",
        "callable",
        "source_function",
        "source_method",
        "source_code",
        "reconstructed_function",
        "source_closure",
        "unknown",
        "other",
        "ambiguous",
        "sequence",
        "iterable",
        "mapping",
        "union",
        "string",
        "namespace",
        "object",
        "pathlib_path",
        "builtin_int",
        "builtin_float",
        "builtin_bytes",
        "builtin_str",
        "os_stat_result",
        "argument_parser",
        "type",
        "boolean",
        "none",
    ]
    name: str | None = None
    guarded: bool = False
    items: tuple[_DynamicImportBinding, ...] | None = None
    values: tuple[_DynamicImportBinding, ...] | None = None
    receiver: _DynamicImportBinding | None = None
    boolean: bool | None = None
    component_names: tuple[str | None, ...] | None = None
    origin_name: str | None = None
    immutable: bool = False
    literal_key: object | None = None
    literal_key_known: bool = False
    element: _DynamicImportBinding | None = None
    sequence_type: Literal["list", "tuple"] | None = None
    source_arguments: tuple[_DynamicImportBinding, ...] | None = None
    source_keyword_names: tuple[str | None, ...] | None = None
    importer_origins: tuple[str, ...] = ()
    namespace_origins: tuple[str, ...] = ()
    unresolved_importer_origins: tuple[str, ...] = ()
    temporal_callable_origins: tuple[str, ...] = ()
    module_registry_origins: tuple[str, ...] = ()
    module_registry_names: tuple[str, ...] | None = ()
    module_registry_complete: bool = True
    code_origin: _DynamicSourceCodeOrigin | None = None
    globals_owner: str | None = None
    function_builtins: _DynamicImportBinding | None = None
    closure_names: tuple[str, ...] = ()
    source_execution_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self._normalize_negative_execution()

    def _normalize_negative_execution(self) -> None:
        """Make executable uncertainty visible to every existing guarded transfer.

        This is negative capability only. Exact code admission still belongs to the
        selected-source constructor/invocation checks. A guarded unknown has no
        trustworthy body identity, including when a legacy fallback discarded it.
        """
        executable_kinds = {
            "source_method",
            "source_code",
            "reconstructed_function",
            "source_closure",
        }
        origins = set(self.source_execution_origins)
        if self.kind in executable_kinds:
            origin = self.code_origin
            origins.add(
                f"{origin.context_identity}:{origin.identity}" if origin is not None else self.kind
            )
        # Derive the entire carrier set from the dataclass, not a second hand-maintained
        # list of binding fields. All normal construction and replace() pass here.
        pending = [getattr(self, field.name) for field in dataclass_fields(self)]
        seen: set[int] = {id(self)}
        while pending:
            value = pending.pop()
            if isinstance(value, _DynamicImportBinding):
                if id(value) in seen:
                    continue
                seen.add(id(value))
                origins.update(value.source_execution_origins)
                if value.kind in executable_kinds:
                    origin = value.code_origin
                    origins.add(
                        f"{origin.context_identity}:{origin.identity}"
                        if origin is not None
                        else value.kind
                    )
                pending.extend(getattr(value, field.name) for field in dataclass_fields(value))
            elif isinstance(value, (tuple, list)):
                pending.extend(value)
            elif isinstance(value, dict):
                pending.extend(value.keys())
                pending.extend(value.values())
        if origins:
            object.__setattr__(self, "guarded", True)
        if self.guarded and self.kind in {"unknown", "ambiguous"}:
            # Existing guarded fallbacks deliberately erase exact identity. Preserve
            # their negative meaning, without inventing an importer/body authority.
            origins.add("guarded_unknown")
        if origins:
            object.__setattr__(self, "source_execution_origins", tuple(sorted(origins)))


@dataclass(frozen=True, slots=True)
class _DynamicNamespaceOwnerResolution:
    """Classify a namespace receiver against the selected source context."""

    kind: Literal["selected", "nonselected", "unresolved", "not_namespace"]
    module: str | None = None


def _dynamic_source_class_origins(
    binding: _DynamicImportBinding,
) -> frozenset[str]:
    """Find source class objects carried by one bounded binding value."""
    origins: set[str] = set()
    pending = [binding]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if (
            current.kind == "other"
            and current.origin_name is not None
            and current.origin_name.startswith("polisyos.")
        ):
            origins.add(current.origin_name)
        pending.extend(current.items or ())
        pending.extend(current.values or ())
        if current.receiver is not None:
            pending.append(current.receiver)
    return frozenset(origins)


def _dynamic_source_object_origins(
    binding: _DynamicImportBinding,
) -> frozenset[str]:
    """Find source class identities whose constructed instances are carried by a value."""
    origins: set[str] = set()
    pending = [binding]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if current.kind == "object" and current.origin_name is not None:
            origins.add(current.origin_name)
        pending.extend(current.items or ())
        pending.extend(current.values or ())
        if current.receiver is not None:
            pending.append(current.receiver)
    return frozenset(origins)


@dataclass(frozen=True, slots=True)
class _DynamicImportSite:
    """A source-owned dynamic importer call with its exact AST identity."""

    node: ast.Call
    call_name: str


@dataclass(frozen=True, slots=True)
class _PendingDynamicImportScope:
    node: ast.AST
    environment_at_definition: Mapping[str, _DynamicImportBinding]
    importer_binding_mutations: Mapping[str, int]


class _DefinitionTimeCallVisitor(ast.NodeVisitor):
    """Find calls evaluated while a deferred source scope is being defined."""

    def __init__(self, *, future_annotations: bool) -> None:
        self.future_annotations = future_annotations
        self.found_call = False
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        self.found_call = True
        self.calls.append(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_definition_expressions(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_definition_expressions(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_defaults(node.args)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        if node.generators:
            self.visit(node.generators[0].iter)

    def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
        # PEP 695 alias values are lazy and do not execute at this statement.
        del node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self.future_annotations:
            self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def _visit_function_definition_expressions(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._visit_defaults(node.args)
        if not self.future_annotations:
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                *((node.args.vararg,) if node.args.vararg else ()),
                *((node.args.kwarg,) if node.args.kwarg else ()),
            ):
                if argument.annotation is not None:
                    self.visit(argument.annotation)
            if node.returns is not None:
                self.visit(node.returns)

    def _visit_defaults(self, arguments: ast.arguments) -> None:
        for expression in (*arguments.defaults, *arguments.kw_defaults):
            if expression is not None:
                self.visit(expression)


@dataclass(frozen=True, slots=True)
class _DynamicImportFunctionSummary:
    """A module-local function and its exact definition-time default values."""

    node: ast.FunctionDef | ast.AsyncFunctionDef
    defaults: Mapping[str, _DynamicImportBinding]


_DYNAMIC_UNKNOWN = _DynamicImportBinding("unknown")
_DYNAMIC_OTHER = _DynamicImportBinding("other")
_DYNAMIC_AMBIGUOUS = _DynamicImportBinding("ambiguous", guarded=True)
_DYNAMIC_DEFERRED = _DynamicImportBinding("ambiguous")
_DYNAMIC_NONE = _DynamicImportBinding("none")
_DYNAMIC_PATH = _DynamicImportBinding("pathlib_path", "pathlib.Path")
_DYNAMIC_BUILTIN_INT = _DynamicImportBinding("builtin_int")
_DYNAMIC_BUILTIN_FLOAT = _DynamicImportBinding("builtin_float")
_DYNAMIC_BUILTIN_BYTES = _DynamicImportBinding("builtin_bytes")
_DYNAMIC_BUILTIN_STR = _DynamicImportBinding("builtin_str")
_DYNAMIC_STAT_RESULT = _DynamicImportBinding("os_stat_result", "os.stat_result")
_DYNAMIC_PATH_METHOD_RESULTS: Mapping[str, _DynamicImportBinding] = {
    "absolute": _DYNAMIC_PATH,
    "expanduser": _DYNAMIC_PATH,
    "relative_to": _DYNAMIC_PATH,
    "resolve": _DYNAMIC_PATH,
    "with_name": _DYNAMIC_PATH,
    "with_stem": _DYNAMIC_PATH,
    "with_suffix": _DYNAMIC_PATH,
    "stat": _DYNAMIC_STAT_RESULT,
    "chmod": _DYNAMIC_NONE,
    "write_bytes": _DYNAMIC_BUILTIN_INT,
    "write_text": _DYNAMIC_BUILTIN_INT,
    "read_bytes": _DYNAMIC_BUILTIN_BYTES,
    "read_text": _DYNAMIC_BUILTIN_STR,
    "mkdir": _DYNAMIC_NONE,
}
_DYNAMIC_PATH_METHOD_ARGUMENTS: Mapping[str, tuple[frozenset[str], ...]] = {
    "absolute": (),
    "expanduser": (),
    "relative_to": (frozenset({"pathlib_path", "string", "builtin_str"}),),
    "resolve": (),
    "with_name": (frozenset({"string", "builtin_str"}),),
    "with_stem": (frozenset({"string", "builtin_str"}),),
    "with_suffix": (frozenset({"string", "builtin_str"}),),
    "stat": (),
    "chmod": (frozenset({"builtin_int"}),),
    "write_bytes": (frozenset({"builtin_bytes"}),),
    "write_text": (frozenset({"string", "builtin_str"}),),
    "read_bytes": (),
    "read_text": (),
    "mkdir": (),
}
_DYNAMIC_PATH_METHOD_KEYWORDS: Mapping[str, Mapping[str, frozenset[str]]] = {
    "resolve": {"strict": frozenset({"boolean"})},
    "mkdir": {
        "mode": frozenset({"builtin_int"}),
        "parents": frozenset({"boolean"}),
        "exist_ok": frozenset({"boolean"}),
    },
    "stat": {"follow_symlinks": frozenset({"boolean"})},
    "chmod": {"follow_symlinks": frozenset({"boolean"})},
    "write_text": {
        "encoding": frozenset({"string", "builtin_str", "none"}),
        "errors": frozenset({"string", "builtin_str", "none"}),
        "newline": frozenset({"string", "builtin_str", "none"}),
    },
    "read_text": {
        "encoding": frozenset({"string", "builtin_str", "none"}),
        "errors": frozenset({"string", "builtin_str", "none"}),
        "newline": frozenset({"string", "builtin_str", "none"}),
    },
}


def _dynamic_join_with_guarded_origin(
    bindings: Sequence[_DynamicImportBinding],
    result: _DynamicImportBinding,
    *,
    trusted_result: bool = False,
) -> _DynamicImportBinding:
    """Keep distinct importer, namespace, candidate, and temporal provenance."""
    if trusted_result:
        return result
    execution_origins = {
        origin
        for binding in bindings
        for current in _dynamic_binding_nodes(binding)
        for origin in current.source_execution_origins
    }
    execution_origins.update(
        f"{current.code_origin.context_identity}:{current.code_origin.identity}"
        if current.code_origin is not None
        else current.kind
        for binding in bindings
        for current in _dynamic_binding_nodes(binding)
        if current.kind
        in {"source_method", "source_code", "reconstructed_function", "source_closure"}
    )
    importer_origins = {
        origin for binding in bindings for origin in _dynamic_importer_origins(binding)
    }
    namespace_origins = {
        origin for binding in bindings for origin in _dynamic_import_namespace_origins(binding)
    }
    unresolved_origins = {
        origin for binding in bindings for origin in _dynamic_unresolved_importer_origins(binding)
    }
    temporal_origins = {
        origin for binding in bindings for origin in _dynamic_temporal_callable_origins(binding)
    }
    module_registry_origins = {
        origin for binding in bindings for origin in binding.module_registry_origins
    }
    module_registry_names: set[str] = set()
    module_registry_unknown = any(
        binding.module_registry_origins and binding.module_registry_names is None
        for binding in bindings
    )
    for binding in bindings:
        if binding.module_registry_origins:
            module_registry_names.update(binding.module_registry_names or ())

    def retain_provenance(value: _DynamicImportBinding) -> _DynamicImportBinding:
        if execution_origins:
            value = replace(
                value,
                source_execution_origins=tuple(
                    sorted(set(value.source_execution_origins) | execution_origins)
                ),
            )
        registry_origins = set(value.module_registry_origins) | module_registry_origins
        registry_names = set(value.module_registry_names or ()) | module_registry_names
        registry_selection = (
            None
            if module_registry_unknown or value.module_registry_names is None
            else tuple(sorted(registry_names))
        )
        registry_complete = value.module_registry_complete and all(
            binding.module_registry_complete
            for binding in bindings
            if binding.module_registry_origins
        )
        if value.kind not in {
            "ambiguous",
            "iterable",
            "mapping",
            "module",
            "namespace",
            "object",
            "sequence",
            "unknown",
            "union",
        }:
            if not registry_origins:
                return value
            return replace(
                value,
                module_registry_origins=tuple(sorted(registry_origins)),
                module_registry_names=registry_selection,
                module_registry_complete=registry_complete,
            )
        return replace(
            value,
            importer_origins=tuple(sorted(set(value.importer_origins) | importer_origins)),
            namespace_origins=tuple(sorted(set(value.namespace_origins) | namespace_origins)),
            unresolved_importer_origins=tuple(
                sorted(set(value.unresolved_importer_origins) | unresolved_origins)
            ),
            temporal_callable_origins=tuple(
                sorted(set(value.temporal_callable_origins) | temporal_origins)
            ),
            module_registry_origins=tuple(sorted(registry_origins)),
            module_registry_names=registry_selection,
            module_registry_complete=registry_complete,
        )

    result = retain_provenance(result)
    if result.guarded or result.kind == "ambiguous":
        return result
    if not any(binding.guarded or binding.kind == "ambiguous" for binding in bindings):
        return result
    if result.kind in {"sequence", "iterable", "mapping", "object", "union"}:
        return retain_provenance(replace(result, guarded=True))
    return retain_provenance(_DYNAMIC_AMBIGUOUS)


_DYNAMIC_TYPE_CHECKING_MODULE_ORIGIN = "typing-type-checking-module"
_DYNAMIC_TYPE_CHECKING_VALUE_ORIGIN = "typing-type-checking-value"
_DYNAMIC_TYPE_CHECKING_MODULES = frozenset({"typing", "typing_extensions"})


def _dynamic_type_checking_module_binding(module: str) -> _DynamicImportBinding:
    return _DynamicImportBinding("module", module, origin_name=_DYNAMIC_TYPE_CHECKING_MODULE_ORIGIN)


def _dynamic_type_checking_value_binding(module: str) -> _DynamicImportBinding:
    return _DynamicImportBinding(
        "boolean",
        boolean=False,
        origin_name=f"{_DYNAMIC_TYPE_CHECKING_VALUE_ORIGIN}:{module}",
    )


def _dynamic_type_checking_kind(binding: _DynamicImportBinding) -> str | None:
    if (
        binding.kind == "boolean"
        and binding.boolean is False
        and binding.origin_name is not None
        and binding.origin_name.startswith(f"{_DYNAMIC_TYPE_CHECKING_VALUE_ORIGIN}:")
    ):
        return "type_checking"
    if (
        binding.kind == "module"
        and binding.name in _DYNAMIC_TYPE_CHECKING_MODULES
        and binding.origin_name == _DYNAMIC_TYPE_CHECKING_MODULE_ORIGIN
    ):
        return "typing_module"
    return None


def _dynamic_type_checking_module_owner(binding: _DynamicImportBinding) -> str | None:
    return binding.name if _dynamic_type_checking_kind(binding) == "typing_module" else None


def _dynamic_call_name(name: str) -> str:
    if name == "builtins.__import__":
        return "__import__"
    if name == "importlib.metadata.entry_points":
        return "metadata.entry_points"
    return name


def _dynamic_binding_for_import(module: str, name: str | None = None) -> _DynamicImportBinding:
    imported = module if name is None else f"{module}.{name}"
    if module == "pathlib":
        if name is None:
            return _DynamicImportBinding("module", "pathlib")
        if name == "Path":
            return _DynamicImportBinding("callable", "pathlib.Path")
    if module == "argparse":
        if name is None:
            return _DynamicImportBinding("module", "argparse")
        if name == "ArgumentParser":
            return _DynamicImportBinding("callable", "argparse.ArgumentParser")
    if module == "tempfile":
        if name is None:
            return _DynamicImportBinding("module", "tempfile")
        if name == "mkdtemp":
            return _DynamicImportBinding("callable", "tempfile.mkdtemp")
    if module == "os":
        if name is None:
            return _DynamicImportBinding("module", "os")
        if name == "stat_result":
            return _DynamicImportBinding("type", "os.stat_result")
    if module in _DYNAMIC_TYPE_CHECKING_MODULES:
        if name is None:
            return _dynamic_type_checking_module_binding(module)
        if name == "TYPE_CHECKING":
            return _dynamic_type_checking_value_binding(module)
    canonical = _dynamic_call_name(imported)
    if module == "builtins" and name is not None:
        return _dynamic_builtin_binding(name)
    if module == "sys" and name == "modules":
        return _dynamic_sys_modules_binding()
    if module == "types" and name == "FunctionType":
        return _DynamicImportBinding(
            "callable", "types.FunctionType", temporal_callable_origins=("types.FunctionType",)
        )
    if module == "types" and name == "MappingProxyType":
        return _DynamicImportBinding("callable", "types.MappingProxyType")
    if module == "types" and name is None:
        return _DynamicImportBinding("module", "types")
    if canonical == "metadata":
        return _DYNAMIC_OTHER
    if canonical in DYNAMIC_CALL_NAMES:
        return _DynamicImportBinding("callable", canonical, guarded=True)
    if module.startswith("polisyos.") and name == "list_entry_points":
        return _DynamicImportBinding("callable", "list_entry_points", guarded=True)
    if any(call_name.startswith(canonical + ".") for call_name in DYNAMIC_CALL_NAMES):
        return _DynamicImportBinding("module", canonical, guarded=True)
    if canonical in {"importlib.metadata", "importlib.resources"}:
        return _DynamicImportBinding("module", canonical, guarded=True)
    if canonical == "builtins":
        return _DynamicImportBinding("module", canonical, guarded=True)
    if canonical == "sys":
        return _DynamicImportBinding("module", canonical, guarded=True)
    return _DYNAMIC_OTHER


def _dynamic_binding_nodes(
    binding: _DynamicImportBinding,
) -> tuple[_DynamicImportBinding, ...]:
    """Return the bounded values reachable from one abstract binding."""
    nodes: list[_DynamicImportBinding] = []
    pending = [binding]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        nodes.append(current)
        pending.extend(current.items or ())
        pending.extend(current.values or ())
        pending.extend(current.source_arguments or ())
        if current.receiver is not None:
            pending.append(current.receiver)
        if current.element is not None:
            pending.append(current.element)
    return tuple(nodes)


def _dynamic_is_importer_namespace_name(name: str) -> bool:
    """Return whether a module name identifies a supported importer namespace."""
    return name == "builtins" or any(
        name == prefix or name.startswith(f"{prefix}.")
        for prefix in _DYNAMIC_IMPORT_MODULE_PREFIXES
    )


def _dynamic_importer_origins(binding: _DynamicImportBinding) -> frozenset[str]:
    """Return exact dynamic-import callable identities carried by a value."""
    origins: set[str] = set()
    for current in _dynamic_binding_nodes(binding):
        origins.update(current.importer_origins)
        if current.kind == "callable" and current.guarded and current.name in DYNAMIC_CALL_NAMES:
            origins.add(str(current.name))
    return frozenset(origins)


def _dynamic_import_namespace_origins(
    binding: _DynamicImportBinding,
) -> frozenset[str]:
    """Return importer module namespaces without treating general taint as identity."""
    origins: set[str] = set()
    for current in _dynamic_binding_nodes(binding):
        origins.update(current.namespace_origins)
        if (
            current.guarded
            and current.kind in {"module", "namespace"}
            and current.name is not None
            and _dynamic_is_importer_namespace_name(current.name)
        ):
            origins.add(current.name)
    return frozenset(origins)


def _dynamic_unresolved_importer_origins(
    binding: _DynamicImportBinding,
) -> frozenset[str]:
    """Return importer-candidate identities whose members are not yet resolved."""
    return frozenset(
        origin
        for current in _dynamic_binding_nodes(binding)
        for origin in current.unresolved_importer_origins
    )


def _dynamic_temporal_callable_origins(
    binding: _DynamicImportBinding,
) -> frozenset[str]:
    """Return guarded reflection or code-execution callables used by this analysis."""
    temporal_callables = _DYNAMIC_IMPORT_TEMPORAL_CALLABLES - DYNAMIC_CALL_NAMES
    origins: set[str] = set()
    for current in _dynamic_binding_nodes(binding):
        origins.update(current.temporal_callable_origins)
        if current.kind == "callable" and current.guarded and current.name in temporal_callables:
            origins.add(str(current.name))
    return frozenset(origins)


def _is_guarded_importer_binding(binding: _DynamicImportBinding) -> bool:
    """Return whether a value carries an importer, unresolved candidate, or temporal callable."""
    return bool(
        _dynamic_importer_origins(binding)
        or _dynamic_unresolved_importer_origins(binding)
        or _dynamic_temporal_callable_origins(binding)
    )


def _dynamic_has_source_execution(binding: _DynamicImportBinding) -> bool:
    """Keep executable source values fail-closed at unsupported escape boundaries."""
    return any(
        item.source_execution_origins
        or item.kind in {"source_method", "source_code", "reconstructed_function", "source_closure"}
        for item in _dynamic_binding_nodes(binding)
    )


def _is_unresolved_importer_binding(binding: _DynamicImportBinding) -> bool:
    """Return whether an unknown value may be an importer or a guarded temporal callable."""
    if (
        binding.kind == "union"
        and binding.items
        and all(
            item.kind in {"source_function", "reconstructed_function", "source_closure"}
            for item in binding.items
        )
    ):
        return False
    return binding.kind in {"ambiguous", "unknown", "union"} and (
        _is_guarded_importer_binding(binding) or _dynamic_has_source_execution(binding)
    )


def _dynamic_unresolved_importer_binding(
    origins: Sequence[str],
    *,
    name: str | None = None,
) -> _DynamicImportBinding:
    """Build a fail-closed value for a computed importer candidate."""
    return _DynamicImportBinding(
        "ambiguous",
        name=name,
        guarded=True,
        unresolved_importer_origins=tuple(sorted(set(origins))),
    )


def _dynamic_function_has_unmodeled_implicit_dispatch(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    environment: Mapping[str, _DynamicImportBinding],
) -> bool:
    """Detect callable bodies whose implicit Python dispatch is outside the summary."""
    for node in ast.walk(function):
        if isinstance(
            node,
            (
                ast.AsyncFor,
                ast.AsyncWith,
                ast.Await,
                ast.BinOp,
                ast.Compare,
                ast.For,
                ast.GeneratorExp,
                ast.IfExp,
                ast.ListComp,
                ast.Match,
                ast.SetComp,
                ast.Subscript,
                ast.UnaryOp,
                ast.While,
                ast.With,
                ast.YieldFrom,
            ),
        ):
            return True
        if isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name):
                return True
            receiver = environment.get(node.value.id, _DYNAMIC_UNKNOWN)
            if receiver.kind not in {"module", "none"} and not (
                receiver.kind == "other"
                and receiver.literal_key_known
                and receiver.literal_key is None
            ):
                return True
        if isinstance(node, ast.If) and (
            not isinstance(node.test, ast.Constant) or not isinstance(node.test.value, bool)
        ):
            return True
    return False


def _dynamic_builtin_binding(name: str) -> _DynamicImportBinding:
    """Resolve the bounded built-in capability names used by source reflection."""
    canonical = _dynamic_call_name(f"builtins.{name}")
    if canonical in DYNAMIC_CALL_NAMES:
        return _DynamicImportBinding("callable", canonical, guarded=True)
    if name in _DYNAMIC_ITERABLE_CONSTRUCTORS:
        return _DynamicImportBinding("callable", f"builtins.{name}")
    if name in _DYNAMIC_CAPABILITY_PREDICATES:
        return _DynamicImportBinding("callable", f"builtins.{name}")
    if name in {"setattr", "delattr"}:
        return _DynamicImportBinding("callable", f"builtins.{name}")
    if name in {"type", "int", "float", "str", "bytes", "bool", "dict", "object"}:
        return _DynamicImportBinding("type", f"builtins.{name}")
    if name in {"getattr", "globals", "locals", "vars"}:
        return _DynamicImportBinding("callable", f"builtins.{name}", guarded=True)
    if name in {"eval", "exec"}:
        return _DynamicImportBinding("callable", f"builtins.{name}", guarded=True)
    return _DYNAMIC_OTHER


def _dynamic_string_binding(value: str) -> _DynamicImportBinding:
    return _DynamicImportBinding(
        "string",
        value,
        literal_key=value,
        literal_key_known=True,
    )


def _dynamic_builtin_namespace_binding() -> _DynamicImportBinding:
    names = {
        "__import__",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "setattr",
        "type",
        "vars",
    }
    names.update(_DYNAMIC_ITERABLE_CONSTRUCTORS)
    names.update(_DYNAMIC_CAPABILITY_PREDICATES)
    keys = tuple(_dynamic_string_binding(name) for name in sorted(names))
    values = tuple(_dynamic_builtin_binding(name) for name in sorted(names))
    return replace(
        _dynamic_mapping_binding(keys, values),
        namespace_origins=("builtins",),
    )


def _dynamic_builtin_dual_namespace_binding() -> _DynamicImportBinding:
    mapping = _dynamic_builtin_namespace_binding()
    return _DynamicImportBinding(
        "namespace",
        "builtins",
        guarded=True,
        items=mapping.items,
        values=mapping.values,
        namespace_origins=("builtins",),
    )


def _dynamic_module_namespace_binding(module: str) -> _DynamicImportBinding:
    if module == "builtins":
        return _dynamic_builtin_namespace_binding()
    if module == "sys":
        return _dynamic_mapping_binding(
            (_dynamic_string_binding("modules"),),
            (_dynamic_sys_modules_binding(),),
        )
    module_binding = _dynamic_binding_for_import(module)
    attributes = {
        call_name[len(module) + 1 :].split(".", 1)[0]
        for call_name in DYNAMIC_CALL_NAMES
        if call_name.startswith(module + ".")
    }
    keys = tuple(_dynamic_string_binding(name) for name in sorted(attributes))
    values = tuple(_dynamic_attribute_binding(module_binding, name) for name in sorted(attributes))
    return replace(
        _dynamic_mapping_binding(keys, values, guarded=module_binding.guarded),
        origin_name=f"module_namespace:{module}",
        namespace_origins=((module,) if _dynamic_is_importer_namespace_name(module) else ()),
    )


def _dynamic_sys_modules_binding() -> _DynamicImportBinding:
    module_names = {"builtins", "sys"}
    for call_name in DYNAMIC_CALL_NAMES:
        for module_path in {call_name, _dynamic_call_name(call_name)}:
            parts = module_path.split(".")
            if len(parts) > 1 and parts[0] != "__import__":
                module_names.update(".".join(parts[:index]) for index in range(1, len(parts)))
    keys = tuple(_dynamic_string_binding(name) for name in sorted(module_names))
    values = tuple(_dynamic_binding_for_import(name) for name in sorted(module_names))
    return replace(
        _dynamic_mapping_binding(keys, values),
        origin_name="sys.modules",
        module_registry_origins=("sys.modules",),
        module_registry_names=(),
    )


def _dynamic_scope_mapping(
    environment: Mapping[str, _DynamicImportBinding],
    *,
    scope_name: Literal["globals", "locals"] = "locals",
) -> _DynamicImportBinding:
    values = dict(environment)
    values.setdefault("__builtins__", _dynamic_builtin_dual_namespace_binding())
    keys = tuple(_dynamic_string_binding(name) for name in sorted(values))
    bindings = tuple(values[name] for name in sorted(values))
    return replace(_dynamic_mapping_binding(keys, bindings), origin_name=f"scope:{scope_name}")


def _dynamic_mapping_lookup(
    mapping: _DynamicImportBinding,
    key: _DynamicImportBinding,
    *,
    default: _DynamicImportBinding = _DYNAMIC_OTHER,
) -> _DynamicImportBinding:
    if mapping.kind == "unknown":
        # A declaration-only parameter may implement __getitem__ with arbitrary
        # behavior. Keep the result unknown until a source-backed call summary
        # can re-evaluate the access with the actual receiver and key. In
        # particular, this is not proof that the result is a non-importer.
        return _dynamic_join_with_guarded_origin((mapping, key), _DYNAMIC_UNKNOWN)
    if mapping.kind not in {"mapping", "namespace", "object"}:
        return _dynamic_join_with_guarded_origin(
            (mapping, key),
            _DYNAMIC_OTHER,
        )
    if mapping.items is None or mapping.values is None:
        return _dynamic_join_with_guarded_origin(
            (mapping, key),
            _DYNAMIC_UNKNOWN,
        )
    candidates = _dynamic_binding_alternatives(key)
    if candidates is None:
        if not mapping.immutable or mapping.values is None:
            return _dynamic_join_with_guarded_origin(
                (mapping, key),
                _DYNAMIC_UNKNOWN,
            )
        possible_values = list(mapping.values)
        if default.kind != "other":
            possible_values.append(default)
        result = _dynamic_union_binding(possible_values)
        return _dynamic_join_with_guarded_origin((mapping, key, default), result)
    possible_values: list[_DynamicImportBinding] = []
    has_unmatched_candidate = False
    for candidate_key in candidates:
        matched = False
        for index, registered_key in enumerate(mapping.items):
            if _dynamic_mapping_keys_may_match(candidate_key, registered_key):
                possible_values.append(mapping.values[index])
                matched = True
                if not _dynamic_key_is_exact(registered_key):
                    has_unmatched_candidate = True
        if not matched or not _dynamic_key_is_exact(candidate_key):
            has_unmatched_candidate = True
    if has_unmatched_candidate:
        possible_values.append(default)
    result = _join_dynamic_bindings(possible_values)
    exact_key_selection = all(_dynamic_key_is_exact(candidate) for candidate in candidates) and all(
        _dynamic_key_is_exact(registered_key) for registered_key in mapping.items
    )
    return _dynamic_join_with_guarded_origin(
        (mapping, key, default),
        result,
        trusted_result=exact_key_selection,
    )


def _dynamic_namespace_member_candidate(
    binding: _DynamicImportBinding,
    attribute: str,
) -> _DynamicImportBinding | None:
    """Derive typed unresolved call candidates from supported namespace provenance."""
    possible_origins = set(_dynamic_import_namespace_origins(binding))
    possible_origins.update(_dynamic_unresolved_importer_origins(binding))
    importer_candidates: set[str] = set()
    temporal_candidates: set[str] = set()
    temporal_callables = _DYNAMIC_IMPORT_TEMPORAL_CALLABLES - DYNAMIC_CALL_NAMES
    for origin in possible_origins:
        candidate = _dynamic_call_name(f"{origin}.{attribute}")
        if (
            candidate in DYNAMIC_CALL_NAMES
            or candidate in _DYNAMIC_IMPORT_MODULE_PREFIXES
            or any(call_name.startswith(candidate + ".") for call_name in DYNAMIC_CALL_NAMES)
        ):
            importer_candidates.add(candidate)
        if candidate in temporal_callables:
            temporal_candidates.add(candidate)
    if not importer_candidates and not temporal_candidates:
        return None
    return _DynamicImportBinding(
        "ambiguous",
        name=next(iter(importer_candidates)) if len(importer_candidates) == 1 else None,
        guarded=True,
        unresolved_importer_origins=tuple(sorted(importer_candidates)),
        temporal_callable_origins=tuple(sorted(temporal_candidates)),
    )


def _dynamic_attribute_binding(
    binding: _DynamicImportBinding,
    attribute: str,
) -> _DynamicImportBinding:
    if binding.kind in {
        "source_function",
        "source_method",
        "source_code",
        "reconstructed_function",
        "source_closure",
    }:
        return _dynamic_unresolved_importer_binding(("source-executable-introspection",))
    if attribute == "__dict__" and binding.module_registry_origins:
        return _DynamicImportBinding(
            "namespace",
            guarded=binding.guarded,
            module_registry_origins=binding.module_registry_origins,
            module_registry_names=binding.module_registry_names,
        )
    if binding.kind == "unknown":
        candidate = _dynamic_namespace_member_candidate(binding, attribute)
        if candidate is not None:
            return candidate
        # An unknown receiver can define arbitrary attribute behavior. Preserve
        # that uncertainty until a source-backed call summary has the actual
        # receiver; do not turn an unobserved attribute into a safe value.
        return _dynamic_join_with_guarded_origin((binding,), _DYNAMIC_UNKNOWN)
    if binding.kind == "pathlib_path":
        if attribute == "parent":
            return _DYNAMIC_PATH
        if attribute == "parents":
            return _DynamicImportBinding(
                "sequence",
                "pathlib.Path.parents",
                element=_DYNAMIC_PATH,
            )
        if attribute in _DYNAMIC_PATH_METHOD_RESULTS:
            return _DynamicImportBinding("callable", f"pathlib.Path.{attribute}", receiver=binding)
        return _DYNAMIC_OTHER
    if binding.kind == "os_stat_result":
        if attribute == "st_mode":
            return _DYNAMIC_BUILTIN_INT
        return _DYNAMIC_OTHER
    if binding.kind in {"string", "builtin_str"} and attribute == "split":
        return _DynamicImportBinding("callable", "builtins.str.split", receiver=binding)
    if binding.kind == "argument_parser":
        if attribute in {"add_argument", "parse_args"}:
            return _DynamicImportBinding(
                "callable", f"argparse.ArgumentParser.{attribute}", receiver=binding
            )
        return _DYNAMIC_OTHER
    if binding.kind == "module" and binding.name == "os" and attribute == "environ":
        return replace(_dynamic_mapping_binding((), ()), origin_name="os.environ")
    if binding.kind == "module" and binding.name is not None:
        if attribute == "__dict__":
            return _dynamic_module_namespace_binding(binding.name)
        if binding.name == "sys" and attribute == "modules":
            return _dynamic_sys_modules_binding()
        if binding.name == "builtins":
            return _dynamic_join_with_guarded_origin(
                (binding,),
                _dynamic_builtin_binding(attribute),
                trusted_result=True,
            )
        return _dynamic_join_with_guarded_origin(
            (binding,),
            _dynamic_binding_for_import(binding.name, attribute),
        )
    if binding.kind == "namespace":
        return _dynamic_mapping_lookup(binding, _dynamic_string_binding(attribute))
    if binding.kind == "object":
        return _dynamic_mapping_lookup(
            binding,
            _dynamic_string_binding(attribute),
            default=_DYNAMIC_AMBIGUOUS,
        )
    if binding.kind == "mapping":
        if attribute in {
            "get",
            "__getitem__",
            "keys",
            "items",
            "pop",
            "setdefault",
            "values",
            "update",
            "clear",
            "popitem",
        }:
            return _DynamicImportBinding(
                "callable",
                "mapping.get" if attribute in {"get", "__getitem__"} else f"mapping.{attribute}",
                guarded=binding.guarded,
                receiver=binding,
            )
        return _DYNAMIC_AMBIGUOUS if binding.guarded else _DYNAMIC_OTHER
    if binding.kind == "ambiguous":
        candidate = _dynamic_namespace_member_candidate(binding, attribute)
        if candidate is not None:
            return candidate
    if binding.kind == "ambiguous" and binding.name is not None:
        candidate = _dynamic_call_name(f"{binding.name}.{attribute}")
        if candidate in DYNAMIC_CALL_NAMES or candidate in _DYNAMIC_IMPORT_MODULE_PREFIXES:
            return _dynamic_unresolved_importer_binding((candidate,), name=candidate)
        if any(call_name.startswith(candidate + ".") for call_name in DYNAMIC_CALL_NAMES):
            return _dynamic_unresolved_importer_binding((candidate,), name=candidate)
        return _dynamic_join_with_guarded_origin((binding,), _DYNAMIC_OTHER)
    return _dynamic_join_with_guarded_origin((binding,), _DYNAMIC_OTHER)


def _dynamic_source_object_field(
    binding: _DynamicImportBinding,
    attribute: str,
    value: _DynamicImportBinding,
) -> _DynamicImportBinding:
    """Return a source instance with one exact constructor-derived field."""
    if binding.kind != "object" or binding.origin_name is None:
        return _DYNAMIC_AMBIGUOUS
    if binding.items is None or binding.values is None:
        fields: dict[str, _DynamicImportBinding] = {}
    else:
        if len(binding.items) != len(binding.values):
            return _DYNAMIC_AMBIGUOUS
        fields = {}
        for key, field_value in zip(binding.items, binding.values, strict=True):
            if key.kind != "string" or key.name is None:
                return _DYNAMIC_AMBIGUOUS
            fields[key.name] = field_value
    fields[attribute] = value
    if len(fields) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
        return _DYNAMIC_AMBIGUOUS
    names = tuple(fields)
    values = tuple(fields[name] for name in names)
    return replace(
        binding,
        guarded=binding.guarded or value.guarded,
        items=tuple(_dynamic_string_binding(name) for name in names),
        values=values,
    )


def _join_dynamic_bindings(
    bindings: Sequence[_DynamicImportBinding],
) -> _DynamicImportBinding:
    if not bindings:
        return _DYNAMIC_UNKNOWN
    source_bindings = tuple(bindings)
    expanded = tuple(
        item
        for binding in source_bindings
        for item in (
            binding.items if binding.kind == "union" and binding.items is not None else (binding,)
        )
    )
    if expanded != source_bindings:
        bindings = expanded
    first = bindings[0]
    if all(binding == first for binding in bindings[1:]):
        return _dynamic_join_with_guarded_origin(source_bindings, first)
    if all(binding.kind == first.kind for binding in bindings[1:]) and first.kind in {
        "sequence",
        "iterable",
        "mapping",
    }:
        item_lists = [binding.items for binding in bindings]
        if all(items is not None for items in item_lists):
            concrete_item_lists = [items for items in item_lists if items is not None]
            if all(len(items) == len(concrete_item_lists[0]) for items in concrete_item_lists):
                items = tuple(
                    _join_dynamic_bindings(tuple(values))
                    for values in zip(*concrete_item_lists, strict=True)
                )
                if first.kind in {"sequence", "iterable"}:
                    sequence_types = {binding.sequence_type for binding in bindings}
                    result = _dynamic_sequence_binding(
                        items,
                        kind=first.kind,
                        sequence_type=(
                            next(iter(sequence_types)) if len(sequence_types) == 1 else None
                        ),
                    )
                    return _dynamic_join_with_guarded_origin(source_bindings, result)
                value_lists = [binding.values for binding in bindings]
                if all(values is not None for values in value_lists):
                    concrete_value_lists = [values for values in value_lists if values is not None]
                    if all(
                        len(values) == len(concrete_value_lists[0])
                        for values in concrete_value_lists
                    ):
                        values = tuple(
                            _join_dynamic_bindings(tuple(joined_values))
                            for joined_values in zip(*concrete_value_lists, strict=True)
                        )
                        result = _dynamic_mapping_binding(items, values)
                        return _dynamic_join_with_guarded_origin(source_bindings, result)
    if all(
        (binding.kind == "source_function" and binding.origin_name is not None)
        or (
            binding.kind
            in {"source_method", "source_code", "reconstructed_function", "source_closure"}
            and binding.code_origin is not None
        )
        for binding in bindings
    ):
        return _dynamic_join_with_guarded_origin(source_bindings, _dynamic_union_binding(bindings))
    guarded_names = {
        binding.name
        for binding in bindings
        if binding.name is not None
        and (
            binding.guarded
            or (binding.kind != "string" and binding.name in _DYNAMIC_IMPORT_GUARDED_ROOTS)
            or binding.kind == "ambiguous"
        )
    }
    if len(guarded_names) == 1:
        result = _DynamicImportBinding("ambiguous", next(iter(guarded_names)), guarded=True)
        return _dynamic_join_with_guarded_origin(source_bindings, result)
    if any(binding.guarded or binding.kind == "ambiguous" for binding in bindings):
        return _dynamic_join_with_guarded_origin(source_bindings, _DYNAMIC_AMBIGUOUS)
    return _dynamic_join_with_guarded_origin(source_bindings, _dynamic_union_binding(bindings))


def _dynamic_sequence_binding(
    items: Sequence[_DynamicImportBinding] | None,
    *,
    kind: Literal["sequence", "iterable"] = "sequence",
    guarded: bool = False,
    component_names: tuple[str | None, ...] | None = None,
    sequence_type: Literal["list", "tuple"] | None = None,
) -> _DynamicImportBinding:
    """Return an iterable value whose importer provenance stays attached to its items."""
    materialized = tuple(items) if items is not None else None
    has_guarded_item = any(item.guarded or item.kind == "ambiguous" for item in materialized or ())
    return _DynamicImportBinding(
        kind,
        guarded=guarded or has_guarded_item,
        items=materialized,
        component_names=component_names,
        immutable=sequence_type == "tuple",
        sequence_type=sequence_type,
    )


def _dynamic_union_binding(
    bindings: Sequence[_DynamicImportBinding],
    *,
    component_names: tuple[str | None, ...] | None = None,
    origin_name: str | None = None,
) -> _DynamicImportBinding:
    """Represent a bounded finite set of possible abstract values."""
    source_bindings = tuple(bindings)
    flattened: list[_DynamicImportBinding] = []
    for binding in source_bindings:
        candidates = (
            binding.items if binding.kind == "union" and binding.items is not None else (binding,)
        )
        for candidate in candidates:
            if candidate not in flattened:
                flattened.append(candidate)

    registry_members = [item for item in flattened if item.module_registry_origins]

    def retain_registry_projection(value: _DynamicImportBinding) -> _DynamicImportBinding:
        if not registry_members:
            return value
        registry_origins = {
            origin for item in registry_members for origin in item.module_registry_origins
        }
        registry_complete = len(registry_members) == len(flattened) and all(
            item.module_registry_complete for item in registry_members
        )
        registry_names = (
            None
            if not registry_complete
            or any(item.module_registry_names is None for item in registry_members)
            else tuple(
                sorted(
                    {name for item in registry_members for name in item.module_registry_names or ()}
                )
            )
        )
        return replace(
            value,
            module_registry_origins=tuple(sorted(registry_origins)),
            module_registry_names=registry_names,
            module_registry_complete=registry_complete,
        )

    if not flattened:
        return _dynamic_join_with_guarded_origin(source_bindings, _DYNAMIC_UNKNOWN)
    if len(flattened) == 1:
        result = replace(
            flattened[0],
            component_names=component_names or flattened[0].component_names,
            origin_name=origin_name or flattened[0].origin_name,
        )
        return _dynamic_join_with_guarded_origin(
            source_bindings,
            retain_registry_projection(result),
        )
    if len(flattened) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
        result = (
            _DYNAMIC_AMBIGUOUS
            if any(item.guarded or item.kind == "ambiguous" for item in flattened)
            else _DYNAMIC_UNKNOWN
        )
        return _dynamic_join_with_guarded_origin(
            source_bindings,
            retain_registry_projection(result),
        )
    if any(item.kind in {"unknown", "ambiguous"} for item in flattened):
        result = (
            _DYNAMIC_AMBIGUOUS
            if any(item.guarded or item.kind == "ambiguous" for item in flattened)
            else _DYNAMIC_UNKNOWN
        )
        return _dynamic_join_with_guarded_origin(
            source_bindings,
            retain_registry_projection(result),
        )
    result = _DynamicImportBinding(
        "union",
        guarded=any(item.guarded for item in flattened),
        items=tuple(flattened),
        component_names=component_names,
        origin_name=origin_name,
    )
    return _dynamic_join_with_guarded_origin(
        source_bindings,
        retain_registry_projection(result),
    )


def _dynamic_binding_alternatives(
    binding: _DynamicImportBinding,
) -> tuple[_DynamicImportBinding, ...] | None:
    if _dynamic_key_is_exact(binding):
        return (replace(binding, component_names=None, origin_name=None),)
    if binding.kind == "source_function":
        return (binding,) if binding.origin_name is not None else None
    if binding.kind == "union":
        return binding.items
    if binding.kind in {"unknown", "ambiguous"}:
        return None
    if binding.kind == "sequence" and binding.items is not None:
        if all(_dynamic_binding_is_exact(item) for item in binding.items):
            return (replace(binding, component_names=None, origin_name=None),)
    if binding.kind == "string" and binding.name is not None:
        return (replace(binding, component_names=None, origin_name=None),)
    if binding.kind in {
        "other",
        "boolean",
        "type",
        "module",
        "callable",
        "namespace",
    }:
        return (replace(binding, component_names=None, origin_name=None),)
    return None


def _dynamic_binding_is_exact(binding: _DynamicImportBinding) -> bool:
    if binding.kind in {"unknown", "ambiguous"}:
        return False
    if _dynamic_key_is_exact(binding):
        return True
    if binding.kind == "union":
        return binding.items is not None and all(
            _dynamic_binding_is_exact(item) for item in binding.items
        )
    if binding.kind == "sequence":
        return binding.items is not None and all(
            _dynamic_binding_is_exact(item) for item in binding.items
        )
    if binding.kind == "mapping":
        return (
            binding.items is not None
            and binding.values is not None
            and all(_dynamic_binding_is_exact(item) for item in (*binding.items, *binding.values))
        )
    if binding.kind == "string":
        return binding.name is not None
    if binding.kind == "source_function":
        return binding.origin_name is not None
    return binding.kind in {"other", "boolean", "type", "module", "callable", "namespace"}


def _dynamic_bindings_may_equal(
    left: _DynamicImportBinding,
    right: _DynamicImportBinding,
) -> bool:
    """Return whether two bounded values can denote the same mapping key."""
    if left.kind == "union":
        return left.items is None or any(
            _dynamic_bindings_may_equal(item, right) for item in left.items
        )
    if right.kind == "union":
        return right.items is None or any(
            _dynamic_bindings_may_equal(left, item) for item in right.items
        )
    if left.kind in {"unknown", "ambiguous"} or right.kind in {"unknown", "ambiguous"}:
        return True
    if left.kind != right.kind:
        return False
    if left.kind == "sequence":
        if left.items is None or right.items is None:
            return True
        return len(left.items) == len(right.items) and all(
            _dynamic_bindings_may_equal(left_item, right_item)
            for left_item, right_item in zip(left.items, right.items, strict=True)
        )
    if left.kind == "string":
        return left.name == right.name
    if left.kind in {"module", "callable", "type"}:
        return left.name == right.name
    if left.kind == "source_function":
        return left.origin_name == right.origin_name
    if left.kind == "boolean":
        return left.boolean == right.boolean
    return left.kind == "other"


def _dynamic_value_is_safe_hashable_literal(value: object) -> bool:
    """Return whether value is a closed builtin hashable literal, without user code."""
    scalar_types = (str, bytes, int, float, complex, bool, type(None))
    if type(value) is tuple:
        if not all(_dynamic_value_is_safe_hashable_literal(item) for item in value):
            return False
    elif type(value) not in scalar_types and value is not Ellipsis:
        return False
    try:
        hash(value)
    except TypeError:
        return False
    return True


def _dynamic_ast_literal_key_value(node: ast.AST) -> tuple[bool, object | None]:
    """Read one exact builtin hashable literal from AST without evaluating source."""
    try:
        value: object = ast.literal_eval(node)
    except (MemoryError, RecursionError, SyntaxError, TypeError, ValueError):
        return False, None
    if not _dynamic_value_is_safe_hashable_literal(value):
        return False, None
    return True, value


def _dynamic_binding_literal_key_value(
    binding: _DynamicImportBinding,
) -> tuple[bool, object | None]:
    """Return an exact literal key carried by an abstract source binding."""
    if binding.literal_key_known:
        if _dynamic_value_is_safe_hashable_literal(binding.literal_key):
            return True, binding.literal_key
        return False, None
    if binding.kind == "string" and binding.name is not None:
        return True, binding.name
    return False, None


def _dynamic_binding_is_same_module_namespace_refinement(
    before: _DynamicImportBinding,
    after: _DynamicImportBinding,
) -> bool:
    """Recognize namespace provenance added while resolving the same module value."""
    if before.kind != "module" or before.name is None or after.kind != "module":
        return False
    if before.name != after.name:
        return False
    refined_origins = tuple(sorted(set(before.namespace_origins) | {before.name}))
    return after == replace(before, namespace_origins=refined_origins)


def _dynamic_binding_is_proven_nonimporter(binding: _DynamicImportBinding) -> bool:
    """Prove a bounded builtin value cannot carry a dynamic importer."""
    if binding.guarded or binding.kind == "ambiguous" or _dynamic_has_source_execution(binding):
        return False
    if binding.kind in {
        "string",
        "boolean",
        "none",
        "builtin_int",
        "builtin_float",
        "builtin_bytes",
        "builtin_str",
        "pathlib_path",
        "os_stat_result",
        "argument_parser",
        "type",
    }:
        return True
    if (
        binding.kind == "other"
        and binding.origin_name is not None
        and binding.origin_name.startswith("polisyos.")
    ):
        return True
    literal_known, _ = _dynamic_binding_literal_key_value(binding)
    if literal_known:
        return True
    if binding.kind in {"sequence", "iterable"} and binding.items is not None:
        return all(_dynamic_binding_is_proven_nonimporter(item) for item in binding.items)
    if binding.kind in {"sequence", "iterable"} and binding.element is not None:
        return _dynamic_binding_is_proven_nonimporter(binding.element)
    if binding.kind == "mapping" and binding.items is not None and binding.values is not None:
        return all(
            _dynamic_binding_is_proven_nonimporter(item)
            for item in (*binding.items, *binding.values)
        )
    if binding.kind == "union" and binding.items is not None:
        return all(_dynamic_binding_is_proven_nonimporter(item) for item in binding.items)
    if (
        binding.kind == "object"
        and binding.name == "argparse.Namespace"
        and binding.items is not None
        and binding.values is not None
    ):
        return all(
            _dynamic_binding_is_proven_nonimporter(item)
            for item in (*binding.items, *binding.values)
        )
    return False


def _dynamic_key_is_exact(binding: _DynamicImportBinding) -> bool:
    """Return whether a finite registry key has a fully known hashable value."""
    return _dynamic_binding_literal_key_value(binding)[0]


def _dynamic_keys_equal_exact(
    left: _DynamicImportBinding,
    right: _DynamicImportBinding,
) -> bool:
    """Compare exact finite keys using Python's builtin value equality semantics."""
    left_known, left_value = _dynamic_binding_literal_key_value(left)
    right_known, right_value = _dynamic_binding_literal_key_value(right)
    return left_known and right_known and left_value == right_value


def _dynamic_mapping_keys_may_match(
    left: _DynamicImportBinding,
    right: _DynamicImportBinding,
) -> bool:
    """Match exact mapping keys precisely and retain conservative abstract matching."""
    if _dynamic_key_is_exact(left) and _dynamic_key_is_exact(right):
        return _dynamic_keys_equal_exact(left, right)
    return _dynamic_bindings_may_equal(left, right)


def _dynamic_mapping_binding(
    keys: Sequence[_DynamicImportBinding] | None,
    values: Sequence[_DynamicImportBinding] | None,
    *,
    guarded: bool = False,
    immutable: bool = False,
) -> _DynamicImportBinding:
    """Return a mapping value while retaining key iteration and value provenance."""
    materialized_keys = tuple(keys) if keys is not None else None
    materialized_values = tuple(values) if values is not None else None
    members = tuple(materialized_keys or ()) + tuple(materialized_values or ())
    if (
        materialized_keys is not None
        and materialized_values is not None
        and max(len(materialized_keys), len(materialized_values))
        > _DYNAMIC_COMPREHENSION_VALUE_LIMIT
    ):
        materialized_keys = None
        materialized_values = None
    return _DynamicImportBinding(
        "mapping",
        guarded=guarded or any(item.guarded or item.kind == "ambiguous" for item in members),
        items=materialized_keys,
        values=materialized_values,
        immutable=immutable,
    )


def _dynamic_normalize_literal_mapping_binding(
    mapping: _DynamicImportBinding,
    *,
    immutable: bool = False,
) -> _DynamicImportBinding:
    """Collapse source-known literal keys with Python dict insertion semantics."""
    if mapping.kind != "mapping" or mapping.items is None or mapping.values is None:
        return _DYNAMIC_AMBIGUOUS
    if len(mapping.items) != len(mapping.values):
        return _DYNAMIC_AMBIGUOUS

    effective_keys: list[_DynamicImportBinding] = []
    effective_values: list[_DynamicImportBinding] = []
    key_indexes: dict[object, int] = {}
    for key, value in zip(mapping.items, mapping.values, strict=True):
        key_known, key_value = _dynamic_binding_literal_key_value(key)
        if not key_known:
            return _DYNAMIC_AMBIGUOUS
        if key_value in key_indexes:
            # Python dict equality lets True/1 and equal tuple components collide.
            # Updating a key replaces its value while retaining the first key's
            # object and insertion position.
            effective_values[key_indexes[key_value]] = value
        else:
            key_indexes[key_value] = len(effective_keys)
            effective_keys.append(key)
            effective_values.append(value)
    return _dynamic_mapping_binding(
        effective_keys,
        effective_values,
        guarded=mapping.guarded,
        immutable=immutable,
    )


def _dynamic_immutable_literal_mapping_binding(
    mapping: _DynamicImportBinding,
) -> _DynamicImportBinding:
    """Normalize a source-exact immutable mapping with Python literal-key semantics."""
    return _dynamic_normalize_literal_mapping_binding(mapping, immutable=True)


@dataclass(frozen=True)
class _DynamicImportSourceMember:
    """One selected source file and its exact parsed input bytes."""

    path: Path
    relative_path: str
    content_sha256: str
    tree: ast.Module


@dataclass(frozen=True)
class _DynamicImportSourceContext:
    """Invocation-local identity and effects for a complete selected source set."""

    identity: str
    members: tuple[_DynamicImportSourceMember, ...]
    type_checking_effects: tuple[tuple[str, frozenset[str]], ...] | None = None
    source_class_effects: frozenset[str] | None = None
    module_namespace_effects: tuple[tuple[str, tuple[str, ...] | None], ...] | None = None
    source_mapping_effects: frozenset[str] | None = None


@dataclass(frozen=True)
class _DynamicImportModuleExecutionSnapshot:
    """Immutable post-module namespace for one exact selected source member."""

    hook: _DynamicImportBinding | None
    namespace: tuple[tuple[str, _DynamicImportBinding], ...]
    namespace_complete: bool
    written_names: frozenset[str]


class _DynamicHookRuntimeReadCollector(ast.NodeVisitor):
    """Collect names read while a hook body executes, excluding postponed annotations."""

    def __init__(self, *, future_annotations: bool) -> None:
        self.future_annotations = future_annotations
        self.scope_kind = "function"
        self.read_names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.read_names.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_definition(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_definition(node)

    def _visit_function_definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expression in (*node.decorator_list, *node.args.defaults):
            self.visit(expression)
        for expression in node.args.kw_defaults:
            if expression is not None:
                self.visit(expression)
        if not self.future_annotations:
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                *((node.args.vararg,) if node.args.vararg else ()),
                *((node.args.kwarg,) if node.args.kwarg else ()),
            ):
                if argument.annotation is not None:
                    self.visit(argument.annotation)
            if node.returns is not None:
                self.visit(node.returns)
        previous_scope = self.scope_kind
        self.scope_kind = "function"
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self.scope_kind = previous_scope

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for expression in (*node.decorator_list, *node.bases):
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)
        previous_scope = self.scope_kind
        self.scope_kind = "class"
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self.scope_kind = previous_scope

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self.scope_kind == "class" and not self.future_annotations:
            self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in (*node.args.defaults, *node.args.kw_defaults):
            if expression is not None:
                self.visit(expression)
        self.visit(node.body)

    def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
        # Type alias values are lazy and do not execute while the hook body runs.
        del node


def _dynamic_hook_global_names(
    hook: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    future_annotations: bool,
) -> frozenset[str]:
    """Return module names read by a PEP 562 hook body under its annotation mode."""
    local_names, global_names, nonlocal_names = _scope_local_bindings(hook.body)
    local_names.update(
        argument.arg
        for argument in (
            *hook.args.posonlyargs,
            *hook.args.args,
            *hook.args.kwonlyargs,
            *((hook.args.vararg,) if hook.args.vararg else ()),
            *((hook.args.kwarg,) if hook.args.kwarg else ()),
        )
    )
    collector = _DynamicHookRuntimeReadCollector(future_annotations=future_annotations)
    for statement in hook.body:
        collector.visit(statement)
    return frozenset((collector.read_names - local_names - nonlocal_names) | global_names)


def _dynamic_read_source_context(paths: Sequence[Path]) -> _DynamicImportSourceContext:
    """Read and parse every selected source member once for this collector call."""
    members: list[_DynamicImportSourceMember] = []
    identity = hashlib.sha256()
    for path in paths:
        relative_path = _dynamic_source_label(path)
        try:
            content = path.read_bytes()
            source = content.decode("utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeError, ValueError, RecursionError) as error:
            raise DynamicImportCollectionError(
                f"{relative_path}: {type(error).__name__}: {error}"
            ) from error
        digest = hashlib.sha256(content).hexdigest()
        identity.update(relative_path.encode("utf-8"))
        identity.update(b"\0")
        identity.update(bytes.fromhex(digest))
        members.append(_DynamicImportSourceMember(path, relative_path, digest, tree))
    return _DynamicImportSourceContext(identity.hexdigest(), tuple(members))


_DYNAMIC_LAZY_EXPORT_RESOLVER_FQN = "polisyos.ir.api.resolve_lazy_export"
_DYNAMIC_LAZY_DIR_FQN = "polisyos.ir.api.lazy_dir"


def _dynamic_lazy_dir_contract_matches(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Check the source-owned lazy directory reader's bounded read-only contract."""
    if (
        not isinstance(node, ast.FunctionDef)
        or node.name != "lazy_dir"
        or node.decorator_list
        or getattr(node, "type_params", ())
        or node.args.posonlyargs
        or [argument.arg for argument in node.args.args] != ["namespace", "exports"]
        or node.args.kwonlyargs
        or node.args.vararg is not None
        or node.args.kwarg is not None
        or node.args.defaults
        or any(default is not None for default in node.args.kw_defaults)
    ):
        return False
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    expected = ast.parse(
        """\\
def lazy_dir(namespace, exports):
    return sorted(set(namespace) | set(exports))
"""
    ).body[0]
    return ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False) == ast.dump(
        ast.Module(body=expected.body, type_ignores=[]), include_attributes=False
    )


_DYNAMIC_SOURCE_CLASS_SAFE_EXTERNAL_BASES = frozenset({"pydantic.BaseModel", "typing.Generic"})
_DYNAMIC_SOURCE_CLASS_HOOKS = frozenset(
    {
        "__call__",
        "__delattr__",
        "__get__",
        "__getattribute__",
        "__getattr__",
        "__init__",
        "__init_subclass__",
        "__new__",
        "__set__",
        "__setattr__",
        "__delete__",
        "model_post_init",
    }
)


def _dynamic_lazy_export_resolver_contract_matches(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Check the source-owned lazy export resolver's bounded lookup contract."""
    if (
        not isinstance(node, ast.FunctionDef)
        or node.name != "resolve_lazy_export"
        or node.decorator_list
        or getattr(node, "type_params", ())
        or node.args.posonlyargs
        or [argument.arg for argument in node.args.args] != ["name"]
        or [argument.arg for argument in node.args.kwonlyargs] != ["namespace", "exports"]
        or node.args.vararg is not None
        or node.args.kwarg is not None
        or node.args.defaults
        or any(default is not None for default in node.args.kw_defaults)
    ):
        return False

    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    expected = ast.parse(
        """\
def resolve_lazy_export(name, *, namespace, exports):
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value
"""
    ).body[0]
    return ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False) == ast.dump(
        ast.Module(body=expected.body, type_ignores=[]), include_attributes=False
    )


def _dynamic_is_source_lazy_export_map(
    module: str,
    name: str,
    expression: ast.AST,
    binding: _DynamicImportBinding,
) -> bool:
    """Recognize a source-owned literal export map without importing its owner."""
    if (
        not module.startswith("polisyos.")
        or not name
        or not isinstance(expression, ast.Dict)
        or binding.kind != "mapping"
        or binding.guarded
        or binding.items is None
        or binding.values is None
    ):
        return False
    for key, value in zip(expression.keys, expression.values, strict=True):
        if (
            not isinstance(key, ast.Constant)
            or not isinstance(key.value, str)
            or not isinstance(value, ast.Tuple)
            or len(value.elts) != 2
            or any(
                not isinstance(item, ast.Constant) or not isinstance(item.value, str)
                for item in value.elts
            )
        ):
            return False
    return True


def _dynamic_is_source_lazy_export_map_binding(
    binding: _DynamicImportBinding,
    selected_modules: Iterable[str],
) -> bool:
    origin = binding.origin_name
    owner, separator, symbol = origin.rpartition(".") if origin is not None else ("", "", "")
    return (
        binding.kind == "mapping"
        and not binding.guarded
        and binding.items is not None
        and binding.values is not None
        and separator == "."
        and bool(symbol)
        and owner in selected_modules
    )


def _dynamic_source_lazy_export_map_entries(
    binding: _DynamicImportBinding,
) -> tuple[tuple[str, tuple[str, str]], ...] | None:
    if binding.kind != "mapping" or binding.items is None or binding.values is None:
        return None
    if len(binding.items) != len(binding.values):
        return None
    entries: list[tuple[str, tuple[str, str]]] = []
    for key, value in zip(binding.items, binding.values, strict=True):
        key_known, key_value = _dynamic_binding_literal_key_value(key)
        if (
            not key_known
            or not isinstance(key_value, str)
            or value.kind != "sequence"
            or value.sequence_type != "tuple"
            or not value.immutable
            or value.items is None
            or len(value.items) != 2
        ):
            return None
        pair: list[str] = []
        for item in value.items:
            item_known, item_value = _dynamic_binding_literal_key_value(item)
            if not item_known or not isinstance(item_value, str):
                return None
            pair.append(item_value)
        entries.append((key_value, (pair[0], pair[1])))
    return tuple(entries)


class _DynamicImportSourceBindings:
    """Resolve bounded source-owned exports without importing or executing source."""

    def __init__(
        self,
        source_paths: Sequence[Path],
        *,
        source_context: _DynamicImportSourceContext | None = None,
    ) -> None:
        self.source_paths = tuple(source_paths)
        self.source_context = source_context
        self._module_execution_snapshots: dict[
            str, _DynamicImportModuleExecutionSnapshot | None
        ] = {}
        self._module_execution_scans_in_progress: set[str] = set()
        self._cross_module_namespace_writes: dict[str, set[str] | None] = {}
        self._source_mapping_effects = set(
            source_context.source_mapping_effects or () if source_context is not None else ()
        )
        self.module_paths: dict[str, Path] = {}
        self.ambiguous_modules: set[str] = set()
        self.trees: dict[str, ast.Module | None] = {}
        self.environments: dict[str, dict[str, _DynamicImportBinding] | None] = {}
        self.invalidated_source_classes: set[str] = set(
            source_context.source_class_effects or () if source_context is not None else ()
        )
        self._source_root_model_effects: dict[str, bool] = {}
        self._source_root_model_effects_in_progress: set[str] = set()
        self.source_trees_by_path = (
            {member.path: member.tree for member in source_context.members}
            if source_context is not None
            else {}
        )
        source_root = SRC_ROOT.resolve()
        for path in self.source_paths:
            try:
                path.resolve().relative_to(source_root)
                module = module_fqn_from_path(path)
            except OSError, RuntimeError, ValueError:
                continue
            if module in self.module_paths:
                self.ambiguous_modules.add(module)
            else:
                self.module_paths[module] = path

    def _selected_source_module_names(self) -> frozenset[str]:
        selected_paths = (
            {member.path for member in self.source_context.members}
            if self.source_context is not None
            else None
        )
        return frozenset(
            module
            for module, path in self.module_paths.items()
            if module not in self.ambiguous_modules
            and (selected_paths is None or path in selected_paths)
        )

    def invalidate_source_classes(self, source_names: Iterable[str]) -> None:
        """Discard field summaries after source-visible class effects or escapes."""
        invalidated = {
            source_name for source_name in source_names if source_name.startswith("polisyos.")
        }
        self.invalidated_source_classes.update(invalidated)
        for source_name in invalidated:
            self._source_root_model_effects.pop(source_name, None)

    def record_source_mapping_effect(self, binding: _DynamicImportBinding) -> None:
        """Record a selected-source map mutation or opaque escape by owner identity."""
        if (
            _dynamic_is_source_lazy_export_map_binding(
                binding,
                self._selected_source_module_names(),
            )
            and binding.origin_name is not None
        ):
            self._source_mapping_effects.add(binding.origin_name)

    def import_binding(
        self,
        module: str,
        name: str | None,
        *,
        current_module: str | None = None,
        is_package: bool = False,
        stack: tuple[tuple[str, str], ...] = (),
    ) -> _DynamicImportBinding:
        """Resolve one imported value, conservatively bounding internal sources."""
        target_module = module
        if module.startswith("."):
            if current_module is None:
                return _DYNAMIC_AMBIGUOUS
            level = len(module) - len(module.lstrip("."))
            target_module = _runtime_relative_import(
                current_module,
                module[level:] or None,
                level,
                is_package=is_package,
            )
        if target_module == "polisyos" and name:
            child_module = f"{target_module}.{name}"
            if self._has_module(child_module):
                return _DynamicImportBinding("module", child_module)
            return _DYNAMIC_AMBIGUOUS
        if target_module.startswith("polisyos."):
            if name is None:
                return (
                    _DynamicImportBinding("module", target_module)
                    if self._has_module(target_module)
                    else _DYNAMIC_AMBIGUOUS
                )
            return self._export_binding(target_module, name, stack=stack)
        binding = _dynamic_binding_for_import(target_module, name)
        return self._module_namespace_effect_binding(target_module, name, binding)

    def _lazy_export_call_contract(
        self,
        node: ast.Call,
        environment: Mapping[str, _DynamicImportBinding],
        module: str,
        stack: tuple[tuple[str, str], ...],
        *,
        callee: _DynamicImportBinding | None = None,
    ) -> tuple[_DynamicImportBinding, _DynamicImportBinding] | None:
        """Prove a lazy-export call uses the owner resolver and its source-owned map."""
        if callee is None:
            callee = self._expression_binding(node.func, environment, module, stack)
        if (
            callee.kind != "callable"
            or callee.name != _DYNAMIC_LAZY_EXPORT_RESOLVER_FQN
            or len(node.args) != 1
            or isinstance(node.args[0], ast.Starred)
            or any(keyword.arg is None for keyword in node.keywords)
        ):
            return None

        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        if len(keywords) != len(node.keywords) or set(keywords) != {"namespace", "exports"}:
            return None

        name_node = node.args[0]
        if not isinstance(name_node, ast.Name | ast.Constant) or (
            isinstance(name_node, ast.Constant) and not isinstance(name_node.value, str)
        ):
            return None

        namespace = keywords["namespace"]
        if (
            not isinstance(namespace, ast.Call)
            or not isinstance(namespace.func, ast.Name)
            or namespace.func.id != "globals"
            or namespace.args
            or namespace.keywords
        ):
            return None
        namespace_callee = self._expression_binding(namespace.func, environment, module, stack)
        if namespace_callee.kind != "callable" or namespace_callee.name != "builtins.globals":
            return None

        exports = self._expression_binding(keywords["exports"], environment, module, stack)
        if (
            exports.kind != "mapping"
            or exports.guarded
            or exports.items is None
            or exports.values is None
            or not self._source_literal_mapping_is_current(exports)
        ):
            return None
        return self._expression_binding(name_node, environment, module, stack), exports

    def _lazy_dir_call_contract(
        self,
        node: ast.Call,
        environment: Mapping[str, _DynamicImportBinding],
        module: str,
        stack: tuple[tuple[str, str], ...],
        *,
        callee: _DynamicImportBinding | None = None,
    ) -> _DynamicImportBinding | None:
        if callee is None:
            callee = self._expression_binding(node.func, environment, module, stack)
        if (
            callee.kind != "other"
            or callee.origin_name != _DYNAMIC_LAZY_DIR_FQN
            or len(node.args) != 2
            or node.keywords
            or any(isinstance(argument, ast.Starred) for argument in node.args)
        ):
            return None
        namespace = node.args[0]
        if (
            not isinstance(namespace, ast.Call)
            or not isinstance(namespace.func, ast.Name)
            or namespace.func.id != "globals"
            or namespace.args
            or namespace.keywords
        ):
            return None
        namespace_callee = self._expression_binding(namespace.func, environment, module, stack)
        if namespace_callee.kind != "callable" or namespace_callee.name != "builtins.globals":
            return None
        owner = _DYNAMIC_LAZY_DIR_FQN.rpartition(".")[0]
        if owner not in self._selected_source_module_names():
            return None
        tree = self._module_tree(owner)
        if tree is None:
            return None
        definitions = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
            and statement.name == "lazy_dir"
        ]
        if len(definitions) != 1 or not _dynamic_lazy_dir_contract_matches(definitions[0]):
            return None
        exports = self._expression_binding(node.args[1], environment, module, stack)
        return exports if self._source_literal_mapping_is_current(exports) else None

    def _source_literal_mapping_is_current(self, binding: _DynamicImportBinding) -> bool:
        if not _dynamic_is_source_lazy_export_map_binding(
            binding,
            self._selected_source_module_names(),
        ):
            return False
        origin = binding.origin_name
        if origin is None or origin in self._source_mapping_effects:
            return False
        owner, separator, symbol = origin.rpartition(".")
        if separator != "." or not symbol:
            return False
        if self.source_context is not None:
            namespace_effects = dict(self.source_context.module_namespace_effects or ())
            if owner in namespace_effects:
                written_names = namespace_effects[owner]
                if written_names is None or symbol in written_names:
                    return False
        snapshot = self._module_execution_snapshot(owner)
        if snapshot is None or not snapshot.namespace_complete:
            return False
        current = dict(snapshot.namespace).get(symbol)
        return (
            current is not None
            and current.kind == "mapping"
            and not current.guarded
            and _dynamic_source_lazy_export_map_entries(current)
            == _dynamic_source_lazy_export_map_entries(binding)
        )

    def _resolve_lazy_export_call(
        self,
        node: ast.Call,
        environment: Mapping[str, _DynamicImportBinding],
        module: str,
        stack: tuple[tuple[str, str], ...],
        *,
        callee: _DynamicImportBinding | None = None,
    ) -> _DynamicImportBinding:
        """Resolve one verified call through the source-owned lazy export map."""
        contract = self._lazy_export_call_contract(
            node,
            environment,
            module,
            stack,
            callee=callee,
        )
        if contract is None:
            return _DYNAMIC_AMBIGUOUS
        name, exports = contract
        if name.kind != "string" or name.name is None:
            return _DYNAMIC_AMBIGUOUS

        target = _dynamic_mapping_lookup(exports, name, default=_DYNAMIC_NONE)
        if target.kind == "none":
            return _DYNAMIC_NONE
        if target.kind not in {"sequence", "iterable"} or target.items is None:
            return _DYNAMIC_AMBIGUOUS
        if len(target.items) != 2:
            return _DYNAMIC_AMBIGUOUS
        target_module, target_symbol = target.items
        if (
            target_module.kind != "string"
            or target_module.name is None
            or target_symbol.kind != "string"
            or target_symbol.name is None
        ):
            return _DYNAMIC_AMBIGUOUS
        path = self.module_paths.get(module)
        if path is None:
            return _DYNAMIC_AMBIGUOUS
        return self.import_binding(
            target_module.name,
            target_symbol.name,
            current_module=module,
            is_package=path.name == "__init__.py",
            stack=stack,
        )

    def _has_module(self, module: str) -> bool:
        return module in self.module_paths and module not in self.ambiguous_modules

    def _module_tree(self, module: str) -> ast.Module | None:
        if module in self.trees:
            return self.trees[module]
        path = self.module_paths.get(module)
        if path is None or module in self.ambiguous_modules:
            self.trees[module] = None
            return None
        if path in self.source_trees_by_path:
            tree = self.source_trees_by_path[path]
            self.trees[module] = tree
            return tree
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=_dynamic_source_label(path))
        except OSError, SyntaxError, UnicodeError, ValueError, RecursionError:
            tree = None
        self.trees[module] = tree
        return tree

    def _source_function_definition(
        self, source_name: str
    ) -> tuple[str, Path, ast.FunctionDef | ast.AsyncFunctionDef] | None:
        """Resolve one selected, unshadowed top-level source function identity."""
        source_module, separator, function_name = source_name.rpartition(".")
        if not separator or not source_module.startswith("polisyos."):
            return None
        path = self.module_paths.get(source_module)
        if path is None or path not in self.source_trees_by_path:
            return None
        environment = self._module_environment(source_module, ())
        if environment is None:
            return None
        binding = environment.get(function_name)
        if binding is None or binding.kind != "other" or binding.origin_name != source_name:
            return None
        tree = self._module_tree(source_module)
        if tree is None:
            return None
        definitions = [
            statement
            for statement in tree.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == function_name
        ]
        if len(definitions) != 1:
            return None
        return source_module, path, definitions[0]

    def _source_import_identity(
        self,
        module: str,
        name: str,
        *,
        before_statement: ast.stmt | None = None,
    ) -> str | None:
        """Resolve one module binding at a source statement boundary."""
        tree = self._module_tree(module)
        path = self.module_paths.get(module)
        if tree is None or path is None:
            return None
        identity: str | None = None
        is_package = path.name == "__init__.py"
        found_boundary = before_statement is None
        for statement in tree.body:
            if statement is before_statement:
                found_boundary = True
                break
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    bound_name = alias.asname or alias.name.split(".", 1)[0]
                    if bound_name == name:
                        identity = alias.name if alias.asname else alias.name.split(".", 1)[0]
            elif isinstance(statement, ast.ImportFrom):
                imported_module = _runtime_relative_import(
                    module,
                    statement.module or "",
                    statement.level,
                    is_package=is_package,
                )
                for alias in statement.names:
                    if alias.name == "*":
                        continue
                    if (alias.asname or alias.name) == name:
                        identity = f"{imported_module}.{alias.name}"
            else:
                bound_names, global_names, _ = _scope_local_bindings((statement,))
                if name in bound_names or name in global_names:
                    identity = None
        return identity if found_boundary else None

    @staticmethod
    def _source_class_name_is_unshadowed(
        class_node: ast.ClassDef,
        name: str,
        before_statement: ast.stmt,
    ) -> bool:
        """Check class-namespace bindings established before one body statement."""
        local_names: set[str] = set()
        global_names: set[str] = set()
        for statement in class_node.body:
            if statement is before_statement:
                return name not in local_names and name not in global_names
            bound_names, statement_globals, _ = _scope_local_bindings((statement,))
            local_names.update(bound_names)
            global_names.update(statement_globals)
        return False

    def _source_class_import_identity(
        self,
        module: str,
        class_node: ast.ClassDef,
        name: str,
        before_statement: ast.stmt,
        expected_identity: str,
    ) -> bool:
        """Require a module import to remain the class-body name at its use point."""
        return self._source_import_identity(
            module,
            name,
            before_statement=class_node,
        ) == expected_identity and self._source_class_name_is_unshadowed(
            class_node,
            name,
            before_statement,
        )

    def _source_class_definition(
        self,
        source_name: str,
        *,
        current_module: str,
        current_environment: Mapping[str, _DynamicImportBinding],
        stack: tuple[tuple[str, str], ...],
    ) -> tuple[str, ast.ClassDef, Mapping[str, _DynamicImportBinding]] | None:
        """Find a unique, still-bound source class by its fully qualified name."""
        if source_name in self.invalidated_source_classes:
            return None
        return self._source_class_identity_definition(
            source_name,
            current_module=current_module,
            current_environment=current_environment,
            stack=stack,
        )

    def _source_class_identity_definition(
        self,
        source_name: str,
        *,
        current_module: str,
        current_environment: Mapping[str, _DynamicImportBinding],
        stack: tuple[tuple[str, str], ...],
    ) -> tuple[str, ast.ClassDef, Mapping[str, _DynamicImportBinding]] | None:
        """Resolve nominal source identity without admitting mutable field summaries."""
        source_module, separator, class_name = source_name.rpartition(".")
        if not separator or not self._has_module(source_module):
            return None
        tree = self._module_tree(source_module)
        if tree is None:
            return None
        definitions = [
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if len(definitions) != 1:
            return None
        environment = (
            current_environment
            if source_module == current_module
            else self.environments.get(source_module)
        )
        if environment is None:
            environment = self._module_environment(
                source_module,
                (*stack, (source_module, class_name)),
            )
        if environment is None:
            return None
        binding = environment.get(class_name)
        if binding is None or binding.origin_name != source_name:
            return None
        return source_module, definitions[0], environment

    def _source_static_json_schema_value(
        self,
        module: str,
        node: ast.AST,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> tuple[bool, object | None]:
        """Resolve bounded JSON literals and exact source constants without execution."""
        if sum(1 for _ in ast.walk(node)) > 4096:
            return False, None
        remaining = [4096]

        def resolve(current: ast.AST, depth: int) -> tuple[bool, object | None]:
            remaining[0] -= 1
            if remaining[0] < 0 or depth > 32:
                return False, None
            if isinstance(current, ast.Constant):
                value = current.value
                if value is None or type(value) in {bool, int, float, str}:
                    return True, value
                return False, None
            if isinstance(current, ast.Name):
                binding = environment.get(current.id)
                if binding is None:
                    return False, None
                known, value = _dynamic_binding_literal_key_value(binding)
                if known and (value is None or type(value) in {bool, int, float, str}):
                    return True, value
                return False, None
            if isinstance(current, ast.Dict):
                resolved: dict[str, object] = {}
                for key_node, value_node in zip(current.keys, current.values, strict=True):
                    if key_node is None:
                        return False, None
                    key_known, key = resolve(key_node, depth + 1)
                    value_known, value = resolve(value_node, depth + 1)
                    if not key_known or type(key) is not str or not value_known:
                        return False, None
                    resolved[key] = value
                return True, resolved
            if isinstance(current, ast.List | ast.Tuple):
                items: list[object] = []
                for child in current.elts:
                    known, value = resolve(child, depth + 1)
                    if not known:
                        return False, None
                    items.append(value)
                return True, items
            return False, None

        return resolve(node, 0)

    def _source_pydantic_json_schema_metadata(
        self,
        module: str,
        class_node: ast.ClassDef,
        environment: Mapping[str, _DynamicImportBinding],
        metadata: ast.AST,
    ) -> bool:
        """Prove one annotation metadata item changes JSON Schema only."""
        if (
            not isinstance(metadata, ast.Call)
            or not isinstance(metadata.func, ast.Name)
            or metadata.func.id != "WithJsonSchema"
            or self._source_import_identity(
                module,
                "WithJsonSchema",
                before_statement=class_node,
            )
            != "pydantic.WithJsonSchema"
            or len(metadata.args) != 1
            or not isinstance(metadata.args[0], ast.Dict)
        ):
            return False
        schema_known, schema = self._source_static_json_schema_value(
            module,
            metadata.args[0],
            environment,
        )
        if not schema_known or type(schema) is not dict:
            return False
        modes: list[str | None] = []
        for keyword in metadata.keywords:
            if keyword.arg != "mode" or not isinstance(keyword.value, ast.Constant):
                return False
            if keyword.value.value not in {"validation", "serialization", None}:
                return False
            modes.append(keyword.value.value)
        return len(modes) <= 1

    def _source_pydantic_schema_only_model_config(
        self,
        module: str,
        class_node: ast.ClassDef,
        environment: Mapping[str, _DynamicImportBinding],
        statement: ast.stmt,
    ) -> bool:
        """Recognize only ConfigDict's schema-only source callback configuration."""
        if (
            not isinstance(statement, ast.Assign)
            or len(statement.targets) != 1
            or not isinstance(statement.targets[0], ast.Name)
            or statement.targets[0].id != "model_config"
            or not isinstance(statement.value, ast.Call)
            or not isinstance(statement.value.func, ast.Name)
            or statement.value.func.id != "ConfigDict"
            or not self._source_class_import_identity(
                module,
                class_node,
                "ConfigDict",
                statement,
                "pydantic.ConfigDict",
            )
            or statement.value.args
            or len(statement.value.keywords) != 1
            or statement.value.keywords[0].arg != "json_schema_extra"
            or not isinstance(statement.value.keywords[0].value, ast.Name)
        ):
            return False
        callback = statement.value.keywords[0].value.id
        callback_environment = self._module_environment(
            module,
            (),
            before_statement=class_node,
        )
        binding = callback_environment.get(callback) if callback_environment is not None else None
        tree = self._module_tree(module)
        if (
            binding is None
            or binding.kind != "other"
            or binding.origin_name != f"{module}.{callback}"
            or tree is None
            or not self._source_class_name_is_unshadowed(
                class_node,
                callback,
                before_statement=statement,
            )
        ):
            return False
        callback_functions = [
            (index, node)
            for index, node in enumerate(tree.body)
            if isinstance(node, ast.FunctionDef) and node.name == callback
        ]
        class_index = next(
            (index for index, node in enumerate(tree.body) if node is class_node),
            None,
        )
        return (
            len(callback_functions) == 1
            and class_index is not None
            and callback_functions[0][0] < class_index
            and not callback_functions[0][1].decorator_list
        )

    def _source_pydantic_root_model_str_argument(
        self,
        module: str,
        class_node: ast.ClassDef,
        argument: ast.AST,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> bool:
        """Prove a RootModel argument is builtin str or JSON-Schema-only Annotated[str]."""
        if isinstance(argument, ast.Name):
            return argument.id == "str" and argument.id not in environment
        if (
            not isinstance(argument, ast.Subscript)
            or not isinstance(argument.value, ast.Name)
            or argument.value.id != "Annotated"
            or self._source_import_identity(
                module,
                "Annotated",
                before_statement=class_node,
            )
            != "typing.Annotated"
        ):
            return False
        items = argument.slice.elts if isinstance(argument.slice, ast.Tuple) else (argument.slice,)
        return (
            len(items) >= 2
            and isinstance(items[0], ast.Name)
            and items[0].id == "str"
            and items[0].id not in environment
            and all(
                self._source_pydantic_json_schema_metadata(
                    module,
                    class_node,
                    environment,
                    metadata,
                )
                for metadata in items[1:]
            )
        )

    def _source_pydantic_classvar_string(
        self,
        module: str,
        class_node: ast.ClassDef,
        module_environment: Mapping[str, _DynamicImportBinding],
        statement: ast.AnnAssign,
    ) -> bool:
        """Recognize the actual string ClassVar declaration without local shadowing."""
        annotation = statement.annotation
        return (
            isinstance(statement.target, ast.Name)
            and statement.target.id == "prefix"
            and isinstance(annotation, ast.Subscript)
            and isinstance(annotation.value, ast.Name)
            and annotation.value.id == "ClassVar"
            and isinstance(annotation.slice, ast.Name)
            and annotation.slice.id == "str"
            and "str" not in module_environment
            and self._source_class_import_identity(
                module,
                class_node,
                "ClassVar",
                statement,
                "typing.ClassVar",
            )
            and self._source_class_name_is_unshadowed(
                class_node,
                "str",
                before_statement=statement,
            )
            and (
                statement.value is None
                or (
                    isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                )
            )
        )

    def _source_class_constant_string_attribute(
        self,
        source_name: str,
        attribute: str,
    ) -> _DynamicImportBinding | None:
        """Resolve only a stable literal string ClassVar on its owning source class."""
        if attribute != "prefix" or source_name in self.invalidated_source_classes:
            return None
        module, separator, _ = source_name.rpartition(".")
        if not separator or not self._has_module(module):
            return None
        module_environment = self._module_environment(module, ())
        if module_environment is None:
            return None
        definition = self._source_class_definition(
            source_name,
            current_module=module,
            current_environment=module_environment,
            stack=(),
        )
        if definition is None:
            return None
        _, class_node, _ = definition
        class_environment = self._module_environment(
            module,
            (),
            before_statement=class_node,
        )
        if class_environment is None:
            return None
        declarations = [
            (index, statement)
            for index, statement in enumerate(class_node.body)
            if isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == attribute
        ]
        if len(declarations) != 1:
            return None
        declaration_index, declaration = declarations[0]
        if (
            not self._source_pydantic_classvar_string(
                module,
                class_node,
                class_environment,
                declaration,
            )
            or not isinstance(declaration.value, ast.Constant)
            or not isinstance(declaration.value.value, str)
        ):
            return None
        for statement in class_node.body[declaration_index + 1 :]:
            bound_names, _, _ = _scope_local_bindings((statement,))
            if attribute in bound_names:
                return None
        return _dynamic_string_binding(declaration.value.value)

    def _source_class_builtin_is_unshadowed(
        self,
        module_environment: Mapping[str, _DynamicImportBinding],
        class_node: ast.ClassDef,
        name: str,
        statement: ast.stmt,
    ) -> bool:
        """Require a builtin decorator name to be unbound in both active namespaces."""
        return name not in module_environment and self._source_class_name_is_unshadowed(
            class_node,
            name,
            before_statement=statement,
        )

    def _source_pydantic_root_model_candidate(self, source_name: str) -> bool:
        """Identify source classes whose unproved RootModel value must stay unresolved."""
        source_module, separator, class_name = source_name.rpartition(".")
        if not separator or not self._has_module(source_module):
            return False
        tree = self._module_tree(source_module)
        if tree is None:
            return False
        definitions = [
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if len(definitions) != 1:
            return False
        return any(
            isinstance(base, ast.Subscript)
            and isinstance(base.value, ast.Name)
            and base.value.id == "RootModel"
            for base in definitions[0].bases
        )

    def _source_pydantic_root_model_class_effects_are_safe(
        self,
        source_name: str,
    ) -> bool:
        """Require source callbacks and methods to preserve their protected model identity."""
        if source_name in self.invalidated_source_classes:
            return False
        cached = self._source_root_model_effects.get(source_name)
        if cached is not None:
            return cached
        if source_name in self._source_root_model_effects_in_progress:
            return False
        self._source_root_model_effects_in_progress.add(source_name)
        try:
            safe = self._source_pydantic_root_model_class_effects_are_safe_uncached(source_name)
        except DynamicImportCollectionError:
            safe = False
        finally:
            self._source_root_model_effects_in_progress.discard(source_name)
        self._source_root_model_effects[source_name] = safe
        return safe

    def _source_pydantic_root_model_class_effects_are_safe_uncached(
        self,
        source_name: str,
    ) -> bool:
        """Run accepted callbacks with the actual source class as a protected argument."""
        module, separator, class_name = source_name.rpartition(".")
        if not separator or not self._has_module(module):
            return False
        source_path = self.module_paths.get(module)
        tree = self._module_tree(module)
        if source_path is None or tree is None:
            return False
        class_definitions = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.ClassDef) and statement.name == class_name
        ]
        if len(class_definitions) != 1:
            return False
        class_node = class_definitions[0]
        scanner = _DynamicImportSourceScanner(
            source_path,
            relative_path=_dynamic_source_label(source_path),
            source_bindings=self,
            source_context=self.source_context,
        )
        scanner.scan(tree)
        if source_name in self.invalidated_source_classes:
            return False
        scanner._source_root_model_string_classes.add(source_name)
        module_environment = scanner._module_environment
        class_binding = module_environment.get(class_name)
        if (
            class_binding is None
            or class_binding.kind != "other"
            or class_binding.origin_name != source_name
        ):
            return False
        class_environment = self._module_environment(
            module,
            (),
            before_statement=class_node,
        )
        if class_environment is None:
            return False

        for statement in class_node.body:
            if (
                not isinstance(statement, ast.Assign)
                or len(statement.targets) != 1
                or not isinstance(statement.targets[0], ast.Name)
                or statement.targets[0].id != "model_config"
                or not isinstance(statement.value, ast.Call)
                or not isinstance(statement.value.func, ast.Name)
                or statement.value.func.id != "ConfigDict"
            ):
                continue
            callbacks = [
                keyword.value
                for keyword in statement.value.keywords
                if keyword.arg == "json_schema_extra"
            ]
            for callback_node in callbacks:
                if not isinstance(callback_node, ast.Name):
                    return False
                callback_name = callback_node.id
                callback_binding = class_environment.get(callback_name)
                if (
                    callback_binding is None
                    or callback_binding.kind != "other"
                    or callback_binding.origin_name != f"{module}.{callback_name}"
                ):
                    return False
                callback_definitions = [
                    (index, candidate)
                    for index, candidate in enumerate(tree.body)
                    if isinstance(candidate, ast.FunctionDef) and candidate.name == callback_name
                ]
                class_index = next(
                    (index for index, candidate in enumerate(tree.body) if candidate is class_node),
                    None,
                )
                if (
                    len(callback_definitions) != 1
                    or class_index is None
                    or callback_definitions[0][0] >= class_index
                ):
                    return False
                callback = callback_definitions[0][1]
                positional = (*callback.args.posonlyargs, *callback.args.args)
                if (
                    callback.decorator_list
                    or len(positional) != 2
                    or callback.args.vararg is not None
                    or callback.args.kwarg is not None
                    or callback.args.kwonlyargs
                    or callback.args.defaults
                    or callback.args.kw_defaults
                ):
                    return False
                parameters = {
                    positional[0].arg: _dynamic_mapping_binding((), ()),
                    positional[1].arg: class_binding,
                }
                scanner._scan_function(
                    callback,
                    {},
                    module_environment,
                    return_bindings=[],
                    parameter_bindings=parameters,
                )
                if source_name in self.invalidated_source_classes:
                    return False

        for statement in class_node.body:
            if not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if isinstance(statement, ast.AsyncFunctionDef):
                return False
            positional = (*statement.args.posonlyargs, *statement.args.args)
            staticmethod = any(
                isinstance(decorator, ast.Name)
                and decorator.id == "staticmethod"
                and self._source_class_builtin_is_unshadowed(
                    module_environment,
                    class_node,
                    "staticmethod",
                    statement,
                )
                for decorator in statement.decorator_list
            )
            parameters = {
                argument.arg: (
                    class_binding if index == 0 and not staticmethod else _DYNAMIC_UNKNOWN
                )
                for index, argument in enumerate(positional)
            }
            for argument in (
                *statement.args.kwonlyargs,
                *((statement.args.vararg,) if statement.args.vararg else ()),
                *((statement.args.kwarg,) if statement.args.kwarg else ()),
            ):
                parameters[argument.arg] = _DYNAMIC_UNKNOWN
            scanner._scan_function(
                statement,
                {},
                module_environment,
                return_bindings=[],
                parameter_bindings=parameters,
            )
            if source_name in self.invalidated_source_classes:
                return False
        return True

    def _source_pydantic_root_model_string(
        self,
        source_name: str,
    ) -> tuple[str, ast.ClassDef, Mapping[str, _DynamicImportBinding]] | None:
        """Recognize an exact source class whose Pydantic root schema is builtin ``str``."""
        module = source_name.rpartition(".")[0]
        environment = self._module_environment(module, ())
        if environment is None:
            return None
        definition = self._source_class_definition(
            source_name,
            current_module=module,
            current_environment=environment,
            stack=(),
        )
        if definition is None:
            return None
        _, class_node, _ = definition
        class_environment = self._module_environment(
            module,
            (),
            before_statement=class_node,
        )
        if class_environment is None or class_node.decorator_list or class_node.keywords:
            return None
        if (
            self._source_import_identity(
                module,
                "RootModel",
                before_statement=class_node,
            )
            != "pydantic.RootModel"
        ):
            return None
        if "str" in class_environment:
            return None
        bases = [
            base
            for base in class_node.bases
            if isinstance(base, ast.Subscript)
            and isinstance(base.value, ast.Name)
            and base.value.id == "RootModel"
        ]
        if (
            len(class_node.bases) != 1
            or len(bases) != 1
            or not self._source_pydantic_root_model_str_argument(
                module,
                class_node,
                bases[0].slice,
                class_environment,
            )
        ):
            return None
        unsafe_overrides = {
            "__get_pydantic_core_schema__",
            "__get_pydantic_json_schema__",
            "__get_validators__",
            "__getattribute__",
            "__getattr__",
            "__init__",
            "__new__",
            "__setattr__",
            "model_construct",
            "model_post_init",
            "model_validate",
            "root",
        }
        for statement in class_node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if statement.name in unsafe_overrides:
                    return None
                for decorator in statement.decorator_list:
                    decorated = decorator.func if isinstance(decorator, ast.Call) else decorator
                    if (
                        isinstance(decorated, ast.Name)
                        and decorated.id in {"classmethod", "staticmethod", "property"}
                        and self._source_class_builtin_is_unshadowed(
                            class_environment,
                            class_node,
                            decorated.id,
                            statement,
                        )
                    ):
                        continue
                    if (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Name)
                        and self._source_class_import_identity(
                            module,
                            class_node,
                            decorator.func.id,
                            statement,
                            "pydantic.field_validator",
                        )
                        and len(decorator.args) == 1
                        and isinstance(decorator.args[0], ast.Constant)
                        and decorator.args[0].value == "root"
                        and len(decorator.keywords) == 1
                        and decorator.keywords[0].arg == "mode"
                        and isinstance(decorator.keywords[0].value, ast.Constant)
                        and decorator.keywords[0].value.value == "before"
                    ):
                        # A before-validator still passes through the declared
                        # RootModel[str] core schema; after/wrap/plain validators
                        # can replace the value after that type check.
                        continue
                    return None
            if isinstance(statement, ast.AnnAssign):
                if isinstance(statement.target, ast.Name):
                    if statement.target.id == "root":
                        return None
                    if statement.target.id == "model_config" and not (
                        self._source_pydantic_schema_only_model_config(
                            module,
                            class_node,
                            class_environment,
                            statement,
                        )
                    ):
                        return None
                    if statement.target.id == "prefix" and not (
                        self._source_pydantic_classvar_string(
                            module,
                            class_node,
                            class_environment,
                            statement,
                        )
                    ):
                        return None
            if isinstance(statement, ast.Assign):
                assigned_names = {
                    name
                    for target in statement.targets
                    for name in self._simple_target_names(target)
                }
                if assigned_names.intersection(unsafe_overrides):
                    return None
                if "model_config" in assigned_names and not (
                    self._source_pydantic_schema_only_model_config(
                        module,
                        class_node,
                        class_environment,
                        statement,
                    )
                ):
                    return None
        if self._source_class_has_effect(
            source_name,
            current_module=module,
            current_environment=environment,
            stack=(),
        ):
            return None
        if not self._source_pydantic_root_model_class_effects_are_safe(source_name):
            return None
        return module, class_node, environment

    def _source_pydantic_root_model_instance(
        self,
        source_name: str,
    ) -> _DynamicImportBinding | None:
        """Bind Pydantic ``model_validate`` to the exact source root-model identity."""
        if self._source_pydantic_root_model_string(source_name) is None:
            return None
        base = _DynamicImportBinding(
            "object", source_name, origin_name=source_name, items=(), values=()
        )
        return _dynamic_source_object_field(base, "root", _DYNAMIC_BUILTIN_STR)

    def source_method_definition(
        self,
        source_name: str,
        method_name: str,
        *,
        allow_property: bool = False,
        allow_root_model: bool = False,
    ) -> (
        tuple[
            str,
            ast.ClassDef,
            ast.FunctionDef | ast.AsyncFunctionDef,
            Mapping[str, _DynamicImportBinding],
        ]
        | None
    ):
        """Find one ordinary method on the still-bound source class identity."""
        source_module = source_name.rpartition(".")[0]
        source_environment = self._module_environment(source_module, ())
        if source_environment is None:
            return None
        definition = self._source_class_definition(
            source_name,
            current_module=source_module,
            current_environment=source_environment,
            stack=(),
        )
        if definition is None:
            return None
        module, class_node, environment = definition
        if (
            class_node.decorator_list
            or class_node.keywords
            or (
                not allow_root_model
                and any(
                    not (isinstance(base, ast.Name) and base.id == "object")
                    for base in class_node.bases
                )
            )
        ):
            return None
        if any(
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name in {"__getattr__", "__getattribute__", "__new__", "__call__"}
            for statement in class_node.body
        ):
            return None
        methods = [
            statement
            for statement in class_node.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == method_name
        ]
        if len(methods) != 1:
            return None
        method = methods[0]
        property_decorator = (
            allow_property
            and len(method.decorator_list) == 1
            and isinstance(method.decorator_list[0], ast.Name)
            and method.decorator_list[0].id == "property"
            and "property" not in environment
        )
        if (method.decorator_list and not property_decorator) or isinstance(
            method, ast.AsyncFunctionDef
        ):
            return None
        return module, class_node, method, environment

    @staticmethod
    def _source_method_arguments(
        method: ast.FunctionDef | ast.AsyncFunctionDef,
        receiver: _DynamicImportBinding,
        call_node: ast.Call | None,
        argument_bindings: Sequence[_DynamicImportBinding],
    ) -> dict[str, _DynamicImportBinding] | None:
        """Bind one statically spelled call to a source method's declared parameters."""
        parameters = (*method.args.posonlyargs, *method.args.args)
        if not parameters or parameters[0].arg != "self":
            return None
        if method.args.vararg is not None or method.args.kwarg is not None:
            return None
        result = {parameters[0].arg: receiver}
        if call_node is None:
            if argument_bindings:
                return None
            return result
        if any(keyword.arg is None for keyword in call_node.keywords):
            return None
        positional = argument_bindings[: len(call_node.args)]
        keyword_values = argument_bindings[len(call_node.args) :]
        if len(positional) != len(call_node.args) or len(keyword_values) != len(call_node.keywords):
            return None
        method_positional = parameters[1:]
        if len(positional) > len(method_positional):
            return None
        result.update(
            (parameter.arg, binding)
            for parameter, binding in zip(method_positional, positional, strict=False)
        )
        keyword_only = {argument.arg for argument in method.args.kwonlyargs}
        allowed = {argument.arg for argument in method_positional} | keyword_only
        for keyword, binding in zip(call_node.keywords, keyword_values, strict=True):
            if keyword.arg not in allowed or keyword.arg in result:
                return None
            result[keyword.arg] = binding
        return result

    def _source_method_summary(
        self,
        source_name: str,
        method_name: str,
        receiver: _DynamicImportBinding,
        *,
        call_node: ast.Call | None = None,
        argument_bindings: Sequence[_DynamicImportBinding] = (),
        required_fields: frozenset[str] | None = None,
        summary_stack: tuple[tuple[str, str], ...] = (),
        allow_property: bool = False,
        allow_root_model: bool = False,
    ) -> tuple[_DynamicImportBinding, _DynamicImportBinding] | None:
        """Interpret one bounded source method with its actual receiver and arguments."""
        key = (source_name, method_name)
        if key in summary_stack or len(summary_stack) >= 24:
            return None
        definition = self.source_method_definition(
            source_name,
            method_name,
            allow_property=allow_property,
            allow_root_model=allow_root_model,
        )
        if definition is None:
            return None
        module, _, method, environment = definition
        source_path = self.module_paths.get(module)
        if source_path is None:
            return None
        parameter_bindings = self._source_method_arguments(
            method,
            receiver,
            call_node,
            argument_bindings,
        )
        if parameter_bindings is None:
            return None
        body_scanner = _DynamicImportSourceScanner(source_path, source_bindings=self)
        body_scanner._module_environment = dict(environment)
        tree = self._module_tree(module)
        if tree is not None:
            body_scanner.future_annotations = _future_annotations_enabled(tree)
        body_scanner._source_instance_summary = True
        body_scanner._source_summary_fields = required_fields
        body_scanner._source_summary_locals = self._summary_required_locals(
            method,
            required_fields or frozenset(),
        )
        body_scanner._source_summary_stack = (*summary_stack, key)
        returned: list[_DynamicImportBinding] = []
        final_environments: list[dict[str, _DynamicImportBinding]] = []
        body_scanner._scan_function(
            method,
            {},
            environment,
            return_bindings=returned,
            parameter_bindings=parameter_bindings,
            final_environments=final_environments,
        )
        actual_result = _join_dynamic_bindings(returned or (_DYNAMIC_NONE,))
        updated_receiver = (
            final_environments[0].get("self", receiver) if final_environments else receiver
        )
        return actual_result, updated_receiver

    def source_property_return_binding(
        self,
        source_name: str,
        property_name: str,
        receiver: _DynamicImportBinding,
    ) -> _DynamicImportBinding | None:
        """Resolve a source ``@property`` body over an exact Pydantic ``RootModel[str]``."""
        if self._source_pydantic_root_model_string(source_name) is None:
            return None
        definition = self.source_method_definition(
            source_name,
            property_name,
            allow_property=True,
            allow_root_model=True,
        )
        if definition is None or receiver.origin_name != source_name:
            return None
        _, _, method, _ = definition
        required_fields = frozenset(
            child.attr
            for child in ast.walk(method)
            if isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
            and isinstance(child.ctx, ast.Load)
        )
        summary = self._source_method_summary(
            source_name,
            property_name,
            receiver,
            required_fields=required_fields,
            allow_property=True,
            allow_root_model=True,
        )
        if summary is None:
            return _DYNAMIC_AMBIGUOUS
        result, _ = summary
        if result.kind != "builtin_str" or not _dynamic_binding_is_proven_nonimporter(result):
            return _DYNAMIC_AMBIGUOUS
        return result

    @staticmethod
    def _summary_target_names(target: ast.AST) -> tuple[set[str], set[str]]:
        """Return simple local names and direct ``self.field`` targets."""
        names: set[str] = set()
        fields: set[str] = set()
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id == "self":
                fields.add(target.attr)
        elif isinstance(target, ast.Tuple | ast.List):
            for item in target.elts:
                child_names, child_fields = _DynamicImportSourceBindings._summary_target_names(item)
                names.update(child_names)
                fields.update(child_fields)
        return names, fields

    @classmethod
    def _summary_required_locals(
        cls,
        method: ast.FunctionDef | ast.AsyncFunctionDef,
        required_fields: frozenset[str],
    ) -> frozenset[str]:
        """Close local-name dependencies for requested constructor fields."""
        relevant: set[str] = set()
        assignments = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr)
        ]
        for _ in range(min(len(assignments) + 1, 65)):
            changed = False
            for assignment in assignments:
                targets = (
                    assignment.targets
                    if isinstance(assignment, ast.Assign)
                    else (assignment.target,)
                )
                target_names: set[str] = set()
                target_fields: set[str] = set()
                for target in targets:
                    names, fields = cls._summary_target_names(target)
                    target_names.update(names)
                    target_fields.update(fields)
                if not target_fields.intersection(
                    required_fields
                ) and not target_names.intersection(relevant):
                    continue
                value = assignment.value
                if value is None:
                    continue
                for child in ast.walk(value):
                    if (
                        isinstance(child, ast.Name)
                        and isinstance(child.ctx, ast.Load)
                        and child.id != "self"
                        and child.id not in relevant
                    ):
                        relevant.add(child.id)
                        changed = True
            if not changed:
                break
        return frozenset(relevant)

    @classmethod
    def _summary_block_writes_relevant(
        cls,
        block: Sequence[ast.stmt],
        required_fields: frozenset[str],
        required_locals: frozenset[str],
    ) -> bool:
        """Check whether a control-flow branch can change a requested field input."""
        for statement in block:
            for node in ast.walk(statement):
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(
                    node,
                    ast.AnnAssign | ast.AugAssign | ast.NamedExpr | ast.For | ast.AsyncFor,
                ):
                    targets = (node.target,)
                else:
                    continue
                names: set[str] = set()
                fields: set[str] = set()
                for target in targets:
                    child_names, child_fields = cls._summary_target_names(target)
                    names.update(child_names)
                    fields.update(child_fields)
                if fields.intersection(required_fields) or names.intersection(required_locals):
                    return True
        return False

    def _source_constructor_required_fields(
        self,
        source_name: str,
        requested_fields: frozenset[str],
    ) -> frozenset[str] | None:
        """Close field requirements through source-owned initializer calls and stores."""
        module = source_name.rpartition(".")[0]
        environment = self._module_environment(module, ())
        if environment is None:
            return None
        definition = self._source_class_definition(
            source_name,
            current_module=module,
            current_environment=environment,
            stack=(),
        )
        if definition is None:
            return None
        _, class_node, _ = definition
        methods = {
            statement.name: statement
            for statement in class_node.body
            if isinstance(statement, ast.FunctionDef)
        }
        if len(methods) > 128:
            return None
        required = set(requested_fields)
        pending_methods = ["__init__"]
        seen_methods: set[str] = set()
        while pending_methods:
            method_name = pending_methods.pop()
            if method_name in seen_methods:
                continue
            seen_methods.add(method_name)
            method = methods.get(method_name)
            if method is None:
                continue
            if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                and node is not method
                for statement in method.body
                for node in ast.walk(statement)
            ):
                return None
            for node in ast.walk(method):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self"
                    and node.func.attr in methods
                ):
                    pending_methods.append(node.func.attr)
                if not isinstance(node, ast.Assign | ast.AnnAssign):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                assigned_fields = {
                    target.attr
                    for target in targets
                    if isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                }
                if not assigned_fields.intersection(required):
                    continue
                value = node.value
                if value is None:
                    continue
                required.update(
                    child.attr
                    for child in ast.walk(value)
                    if isinstance(child, ast.Attribute)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "self"
                    and isinstance(child.ctx, ast.Load)
                )
                if len(required) > 64:
                    return None
            if len(seen_methods) > 32:
                return None
        return frozenset(required)

    def _source_constructor_field_summary(
        self,
        source_name: str,
        receiver: _DynamicImportBinding,
        *,
        required_fields: frozenset[str],
        summary_stack: tuple[tuple[str, str], ...],
    ) -> _DynamicImportBinding | None:
        """Derive only requested fields through the exact source initializer chain."""
        if (
            receiver.kind != "object"
            or receiver.origin_name != source_name
            or receiver.source_arguments is None
            or receiver.source_keyword_names is None
            or len(receiver.source_arguments) != len(receiver.source_keyword_names)
        ):
            return None
        module = source_name.rpartition(".")[0]
        environment = self._module_environment(module, ())
        if environment is None or self._source_class_has_effect(
            source_name,
            current_module=module,
            current_environment=environment,
            stack=(),
        ):
            return None
        fields = self._source_constructor_required_fields(source_name, required_fields)
        if fields is None:
            return None
        init_definition = self.source_method_definition(source_name, "__init__")
        if init_definition is None:
            return receiver
        positional = [
            binding
            for binding, name in zip(
                receiver.source_arguments,
                receiver.source_keyword_names,
                strict=True,
            )
            if name is None
        ]
        keywords = [
            (binding, name)
            for binding, name in zip(
                receiver.source_arguments,
                receiver.source_keyword_names,
                strict=True,
            )
            if name is not None
        ]
        dummy_call = ast.Call(
            func=ast.Name(id="__init__", ctx=ast.Load()),
            args=[ast.Constant(value=None) for _ in positional],
            keywords=[
                ast.keyword(arg=name, value=ast.Constant(value=None)) for _, name in keywords
            ],
        )
        ordered_bindings = [*positional, *(binding for binding, _ in keywords)]
        summary = self._source_method_summary(
            source_name,
            "__init__",
            replace(receiver, items=(), values=()),
            call_node=dummy_call,
            argument_bindings=ordered_bindings,
            required_fields=fields,
            summary_stack=summary_stack,
        )
        if summary is None:
            return None
        result, updated = summary
        if result.kind != "none" or updated.kind != "object":
            return None
        return updated

    def source_method_return_binding(
        self,
        source_name: str,
        method_name: str,
        *,
        receiver: _DynamicImportBinding | None = None,
        call_node: ast.Call | None = None,
        argument_bindings: Sequence[_DynamicImportBinding] = (),
        required_fields: frozenset[str] | None = None,
        summary_stack: tuple[tuple[str, str], ...] = (),
    ) -> tuple[_DynamicImportBinding, _DynamicImportBinding] | None:
        """Resolve a source method result and its body-derived receiver state."""
        definition = self.source_method_definition(source_name, method_name)
        if definition is None:
            return None
        module, _, method, environment = definition
        annotation = method.returns
        declared_result: _DynamicImportBinding | None = None
        if isinstance(annotation, ast.Name):
            if (
                annotation.id == "Path"
                and self._source_import_identity(module, "Path") == "pathlib.Path"
            ):
                declared_result = _DYNAMIC_PATH
            elif annotation.id == "int" and annotation.id not in environment:
                declared_result = _DYNAMIC_BUILTIN_INT
            elif annotation.id == "float" and annotation.id not in environment:
                declared_result = _DYNAMIC_BUILTIN_FLOAT
            elif annotation.id == "bytes" and annotation.id not in environment:
                declared_result = _DYNAMIC_BUILTIN_BYTES
            elif annotation.id == "str" and annotation.id not in environment:
                declared_result = _DYNAMIC_BUILTIN_STR
            elif annotation.id == "None" and annotation.id not in environment:
                declared_result = _DYNAMIC_NONE
        if isinstance(annotation, ast.Attribute) and isinstance(annotation.value, ast.Name):
            if (
                annotation.value.id == "os"
                and annotation.attr == "stat_result"
                and self._source_import_identity(module, "os") == "os"
            ):
                declared_result = _DYNAMIC_STAT_RESULT
            elif (
                annotation.value.id == "argparse"
                and annotation.attr == "Namespace"
                and self._source_import_identity(module, "argparse") == "argparse"
            ):
                declared_result = _DynamicImportBinding("object", "argparse.Namespace")
        if isinstance(annotation, ast.Constant) and annotation.value is None:
            declared_result = _DYNAMIC_NONE
        if receiver is None:
            receiver = _DynamicImportBinding("object", source_name, origin_name=source_name)
        if required_fields is None:
            required_fields = frozenset(
                child.attr
                for child in ast.walk(method)
                if isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and child.value.id == "self"
                and isinstance(child.ctx, ast.Load)
            )
        if (
            receiver.source_arguments is not None
            and not receiver.items
            and not any(owner == source_name for owner, _ in summary_stack)
        ):
            materialized = self._source_constructor_field_summary(
                source_name,
                receiver,
                required_fields=required_fields,
                summary_stack=summary_stack,
            )
            if materialized is None:
                return _DYNAMIC_AMBIGUOUS
            receiver = materialized
        summary = self._source_method_summary(
            source_name,
            method_name,
            receiver,
            call_node=call_node,
            argument_bindings=argument_bindings,
            required_fields=required_fields,
            summary_stack=summary_stack,
        )
        if summary is None:
            return _DYNAMIC_AMBIGUOUS
        actual_result, updated_receiver = summary
        if not _dynamic_binding_is_proven_nonimporter(actual_result):
            if declared_result is not None and not _is_guarded_importer_binding(actual_result):
                return _dynamic_unresolved_importer_binding(tuple(sorted(DYNAMIC_CALL_NAMES)))
            return _DYNAMIC_AMBIGUOUS
        if declared_result is not None and (
            actual_result.kind != declared_result.kind
            or (actual_result.kind == "object" and actual_result.name != declared_result.name)
        ):
            # A declaration describes a promised type, not the value returned by an
            # external or otherwise unmodeled factory. Keep the result as a possible
            # dynamic importer so a later call cannot treat that promise as source proof.
            if _is_guarded_importer_binding(actual_result):
                return _DYNAMIC_AMBIGUOUS
            return _dynamic_unresolved_importer_binding(tuple(sorted(DYNAMIC_CALL_NAMES)))
        # A resolved annotation constrains the body result. An unresolved runtime
        # annotation is not needed when the bounded body itself proves the transfer.
        return actual_result, updated_receiver

    def _source_class_has_effect(
        self,
        source_name: str,
        *,
        current_module: str,
        current_environment: Mapping[str, _DynamicImportBinding],
        stack: tuple[tuple[str, str], ...],
        seen: frozenset[str] = frozenset(),
        unknown_is_effect: bool = False,
    ) -> bool:
        """Check a finite source-base closure, conservatively bounding unknown effects."""
        if source_name in self.invalidated_source_classes:
            return True
        if source_name in seen or len(seen) >= 24:
            return True
        definition = self._source_class_definition(
            source_name,
            current_module=current_module,
            current_environment=current_environment,
            stack=stack,
        )
        if definition is None:
            return unknown_is_effect
        module, class_node, environment = definition
        if unknown_is_effect and (class_node.decorator_list or class_node.keywords):
            return True
        next_seen = seen | {source_name}
        for base in class_node.bases:
            base_expression = base.value if isinstance(base, ast.Subscript) else base
            binding = self._expression_binding(base_expression, environment, module, stack)
            alternatives = _dynamic_binding_nodes(binding)
            if unknown_is_effect and (
                len(alternatives) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT
                or any(
                    item.kind not in {"other", "union"}
                    or (item.kind == "union" and not item.items)
                    or (
                        item.kind == "other"
                        and (
                            item.origin_name is None or not item.origin_name.startswith("polisyos.")
                        )
                    )
                    for item in alternatives
                )
            ):
                return True
            for alternative in alternatives:
                origin = alternative.origin_name
                if (
                    alternative.kind == "other"
                    and origin is not None
                    and origin.startswith("polisyos.")
                    and self._source_class_has_effect(
                        origin,
                        current_module=module,
                        current_environment=environment,
                        stack=stack,
                        seen=next_seen,
                        unknown_is_effect=unknown_is_effect,
                    )
                ):
                    return True
        return False

    @staticmethod
    def _plain_dict_value_name(annotation: ast.AST | None) -> str | None:
        """Return a plain ``dict`` value name without evaluating annotations."""
        if (
            not isinstance(annotation, ast.Subscript)
            or not isinstance(annotation.value, ast.Name)
            or annotation.value.id != "dict"
            or not isinstance(annotation.slice, ast.Tuple)
            or len(annotation.slice.elts) != 2
            or not isinstance(annotation.slice.elts[1], ast.Name)
        ):
            return None
        return annotation.slice.elts[1].id

    def _source_class_dict_field(
        self,
        source_name: str,
        field_name: str,
        *,
        current_module: str,
        current_environment: Mapping[str, _DynamicImportBinding],
        stack: tuple[tuple[str, str], ...],
    ) -> tuple[ast.AST, str, Mapping[str, _DynamicImportBinding]] | None:
        """Resolve a declared plain-dict field on a source-owned class."""
        definition = self._source_class_definition(
            source_name,
            current_module=current_module,
            current_environment=current_environment,
            stack=stack,
        )
        if definition is None:
            return None
        module, class_node, environment = definition
        if "dict" in environment:
            return None
        annotation = next(
            (
                statement.annotation
                for statement in class_node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == field_name
            ),
            None,
        )
        if self._plain_dict_value_name(annotation) is None:
            return None
        return annotation, module, environment

    def _source_validator_loop_value_classes(
        self,
        module: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_node: ast.ClassDef,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> dict[str, str]:
        """Track loop values yielded by fields typed as source-owned dictionaries."""
        class_name = f"{module}.{class_node.name}"
        local_classes: dict[str, str] = {}
        loops = sorted(
            (
                child
                for statement in node.body
                for child in ast.walk(statement)
                if isinstance(child, ast.For)
            ),
            key=lambda child: (child.lineno, child.col_offset),
        )
        for _ in range(min(len(loops), 24)):
            changed = False
            for loop in loops:
                if (
                    not isinstance(loop.target, ast.Tuple | ast.List)
                    or len(loop.target.elts) != 2
                    or not all(isinstance(item, ast.Name) for item in loop.target.elts)
                    or not isinstance(loop.iter, ast.Call)
                    or not isinstance(loop.iter.func, ast.Attribute)
                    or loop.iter.func.attr != "items"
                    or loop.iter.args
                    or loop.iter.keywords
                    or not isinstance(loop.iter.func.value, ast.Attribute)
                    or not isinstance(loop.iter.func.value.value, ast.Name)
                ):
                    continue
                receiver = loop.iter.func.value
                owner = receiver.value.id
                if owner == node.args.args[0].arg:
                    owner_class = class_name
                else:
                    owner_class = local_classes.get(owner)
                if owner_class is None:
                    continue
                field = self._source_class_dict_field(
                    owner_class,
                    receiver.attr,
                    current_module=module,
                    current_environment=environment,
                    stack=(),
                )
                if field is None:
                    continue
                annotation, _, owner_environment = field
                value_name = self._plain_dict_value_name(annotation)
                if value_name is None:
                    continue
                value_binding = owner_environment.get(value_name)
                if (
                    value_binding is None
                    or value_binding.origin_name is None
                    or not value_binding.origin_name.startswith("polisyos.")
                ):
                    continue
                value_variable = loop.target.elts[1]
                if local_classes.get(value_variable.id) != value_binding.origin_name:
                    local_classes[value_variable.id] = value_binding.origin_name
                    changed = True
            if not changed:
                break

        stores: dict[str, int] = {}
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                stores[child.id] = stores.get(child.id, 0) + 1
        return {
            name: source_name
            for name, source_name in local_classes.items()
            if stores.get(name) == 1
        }

    def _source_boolean_helper_is_safe(
        self,
        module: str,
        name: str,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> bool:
        """Admit only a pure, source-local boolean regex check used by a validator."""
        tree = self._module_tree(module)
        if tree is None:
            return False
        definitions = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.FunctionDef) and statement.name == name
        ]
        if len(definitions) != 1:
            return False
        helper = definitions[0]
        if (
            helper.decorator_list
            or getattr(helper, "type_params", ())
            or helper.args.posonlyargs
            or len(helper.args.args) != 1
            or helper.args.kwonlyargs
            or helper.args.vararg is not None
            or helper.args.kwarg is not None
            or helper.args.defaults
            or helper.args.kw_defaults
            or not isinstance(helper.returns, ast.Name)
            or helper.returns.id != "bool"
            or len(helper.body) != 2
            or not isinstance(helper.body[0], ast.Import)
            or len(helper.body[0].names) != 1
            or helper.body[0].names[0].name != "re"
            or helper.body[0].names[0].asname is not None
            or not isinstance(helper.body[1], ast.Return)
            or not isinstance(helper.body[1].value, ast.Call)
        ):
            return False
        returned = helper.body[1].value
        if (
            not isinstance(returned.func, ast.Name)
            or returned.func.id != "bool"
            or "bool" in environment
            or len(returned.args) != 1
            or returned.keywords
        ):
            return False
        match_call = returned.args[0]
        if (
            not isinstance(match_call, ast.Call)
            or not isinstance(match_call.func, ast.Attribute)
            or not isinstance(match_call.func.value, ast.Name)
            or match_call.func.value.id != "re"
            or match_call.func.attr not in {"match", "fullmatch", "search"}
            or len(match_call.args) not in {2, 3}
            or match_call.keywords
            or not isinstance(match_call.args[-1], ast.Name)
            or match_call.args[-1].id != helper.args.args[0].arg
        ):
            return False
        pattern = self._expression_binding(match_call.args[0], environment, module, ())
        if pattern.kind != "string" or pattern.name is None:
            return False
        return len(match_call.args) == 2 or (
            isinstance(match_call.args[2], ast.Constant) and type(match_call.args[2].value) is int
        )

    def _source_validator_is_value_preserving(
        self,
        module: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_node: ast.ClassDef,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> bool:
        """Accept a narrow after-validator that returns its input without mutation."""
        if (
            isinstance(node, ast.AsyncFunctionDef)
            or len(node.decorator_list) != 1
            or not isinstance(node.decorator_list[0], ast.Call)
            or not isinstance(node.decorator_list[0].func, ast.Name)
            or self._source_import_identity(module, node.decorator_list[0].func.id)
            != "pydantic.model_validator"
            or len(node.args.posonlyargs) + len(node.args.args) != 1
            or node.args.kwonlyargs
            or node.args.vararg is not None
            or node.args.kwarg is not None
            or node.args.defaults
            or node.args.kw_defaults
        ):
            return False
        decorator = node.decorator_list[0]
        if (
            len(decorator.args) != 0
            or len(decorator.keywords) != 1
            or decorator.keywords[0].arg != "mode"
            or not isinstance(decorator.keywords[0].value, ast.Constant)
            or decorator.keywords[0].value.value != "after"
        ):
            return False
        parameter = (*node.args.posonlyargs, *node.args.args)[0].arg
        body = ast.Module(body=node.body, type_ignores=[])
        if any(
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
            for statement in node.body
            for child in ast.walk(statement)
            if child is not statement
        ):
            return False
        returns = [child for child in ast.walk(body) if isinstance(child, ast.Return)]
        if not returns or any(
            not isinstance(statement.value, ast.Name) or statement.value.id != parameter
            for statement in returns
        ):
            return False
        field_annotations = {
            statement.target.id: statement.annotation
            for statement in class_node.body
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
        }
        loop_value_classes = self._source_validator_loop_value_classes(
            module,
            node,
            class_node,
            environment,
        )
        for child in ast.walk(body):
            if isinstance(
                child, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Delete)
            ):
                return False
            if isinstance(child, ast.Assign) and any(
                not isinstance(target, ast.Name) for target in child.targets
            ):
                return False
            if isinstance(child, ast.AnnAssign) and not isinstance(child.target, ast.Name):
                return False
            if isinstance(child, ast.AugAssign) and not isinstance(child.target, ast.Name):
                return False
            if isinstance(child, ast.NamedExpr) and not isinstance(child.target, ast.Name):
                return False
            if not isinstance(child, ast.Call):
                continue
            function = child.func
            if isinstance(function, ast.Name):
                if function.id == "ValueError" and function.id not in environment:
                    continue
                if function.id in {"isinstance", "set", "sorted", "len", "bool"}:
                    if function.id in environment:
                        return False
                    continue
                helper = next(
                    (
                        statement
                        for statement in self._module_tree(module).body
                        if isinstance(statement, ast.FunctionDef) and statement.name == function.id
                    ),
                    None,
                )
                if helper is not None and self._source_boolean_helper_is_safe(
                    module,
                    function.id,
                    environment,
                ):
                    continue
                return False
            if isinstance(function, ast.Attribute) and function.attr == "items":
                receiver = function.value
                if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name):
                    if receiver.value.id == parameter:
                        annotation = field_annotations.get(receiver.attr)
                        if (
                            "dict" not in environment
                            and self._plain_dict_value_name(annotation) is not None
                            and not child.args
                            and not child.keywords
                        ):
                            continue
                    elif receiver.value.id in loop_value_classes:
                        if (
                            self._source_class_dict_field(
                                loop_value_classes[receiver.value.id],
                                receiver.attr,
                                current_module=module,
                                current_environment=environment,
                                stack=(),
                            )
                            is not None
                            and not child.args
                            and not child.keywords
                        ):
                            continue
            return False
        return True

    def _source_class_is_summarizable(
        self,
        source_name: str,
        *,
        current_module: str,
        current_environment: Mapping[str, _DynamicImportBinding],
        stack: tuple[tuple[str, str], ...],
        seen: frozenset[str] = frozenset(),
    ) -> bool:
        """Verify a source class hierarchy has no opaque construction/access hooks."""
        if source_name in seen or len(seen) >= 24:
            return False
        definition = self._source_class_definition(
            source_name,
            current_module=current_module,
            current_environment=current_environment,
            stack=stack,
        )
        if definition is None:
            return False
        module, class_node, environment = definition
        if class_node.decorator_list or class_node.keywords:
            return False
        for statement in class_node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if statement.name in _DYNAMIC_SOURCE_CLASS_HOOKS:
                    return False
                if statement.decorator_list and not self._source_validator_is_value_preserving(
                    module,
                    statement,
                    class_node,
                    environment,
                ):
                    return False
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
                targets = (
                    statement.targets
                    if isinstance(statement, ast.Assign | ast.Delete)
                    else (statement.target,)
                )
                if any(
                    name in _DYNAMIC_SOURCE_CLASS_HOOKS
                    for target in targets
                    for name in self._simple_target_names(target)
                ):
                    return False

        next_seen = seen | {source_name}
        for base in class_node.bases:
            base_expression = base.value if isinstance(base, ast.Subscript) else base
            if isinstance(base, ast.Subscript) and any(
                isinstance(node, (ast.Call, ast.Lambda, ast.NamedExpr, ast.Await, ast.Yield))
                for node in ast.walk(base.slice)
            ):
                return False
            binding = self._expression_binding(
                base_expression,
                environment,
                module,
                stack,
            )
            if binding.origin_name is not None and binding.origin_name.startswith("polisyos."):
                if not self._source_class_is_summarizable(
                    binding.origin_name,
                    current_module=module,
                    current_environment=environment,
                    stack=stack,
                    seen=next_seen,
                ):
                    return False
                continue
            if isinstance(base_expression, ast.Name) and base_expression.id == "object":
                if base_expression.id not in environment:
                    continue
            imported_base = (
                self._source_import_identity(module, base_expression.id)
                if isinstance(base_expression, ast.Name)
                else None
            )
            if imported_base not in _DYNAMIC_SOURCE_CLASS_SAFE_EXTERNAL_BASES:
                return False
        return True

    def _source_class_field_defaults(
        self,
        source_name: str,
        *,
        current_module: str,
        current_environment: Mapping[str, _DynamicImportBinding],
        stack: tuple[tuple[str, str], ...],
        seen: frozenset[str] = frozenset(),
    ) -> dict[str, _DynamicImportBinding] | None:
        """Collect source-declared instance fields and defaults through safe bases."""
        if source_name in seen or len(seen) >= 24:
            return None
        definition = self._source_class_definition(
            source_name,
            current_module=current_module,
            current_environment=current_environment,
            stack=stack,
        )
        if definition is None:
            return None
        module, class_node, environment = definition
        result: dict[str, _DynamicImportBinding] = {}
        next_seen = seen | {source_name}
        for base in class_node.bases:
            base_expression = base.value if isinstance(base, ast.Subscript) else base
            binding = self._expression_binding(base_expression, environment, module, stack)
            if binding.origin_name is not None and binding.origin_name.startswith("polisyos."):
                inherited = self._source_class_field_defaults(
                    binding.origin_name,
                    current_module=module,
                    current_environment=environment,
                    stack=stack,
                    seen=next_seen,
                )
                if inherited is None:
                    return None
                result.update(inherited)
        for statement in class_node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(
                statement.target, ast.Name
            ):
                continue
            result[statement.target.id] = self._source_model_field_default(
                statement.value,
                environment=environment,
                module=module,
                stack=stack,
            )
        return result

    def _source_model_field_default(
        self,
        expression: ast.AST | None,
        *,
        environment: Mapping[str, _DynamicImportBinding],
        module: str,
        stack: tuple[tuple[str, str], ...],
    ) -> _DynamicImportBinding:
        """Summarize literal Pydantic field defaults without evaluating factories."""
        if expression is None:
            return _DYNAMIC_AMBIGUOUS
        if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Name):
            return self._expression_binding(expression, environment, module, stack)
        if (
            self._source_import_identity(module, expression.func.id) != "pydantic.Field"
            or expression.func.id not in environment
            or (expression.args and expression.keywords)
        ):
            return _DYNAMIC_AMBIGUOUS
        if expression.args:
            default = expression.args[0]
            if isinstance(default, ast.Constant) and default.value is Ellipsis:
                return _DYNAMIC_AMBIGUOUS
            return self._expression_binding(default, environment, module, stack)
        keyword_defaults = [keyword for keyword in expression.keywords if keyword.arg == "default"]
        if len(keyword_defaults) == 1:
            return self._expression_binding(
                keyword_defaults[0].value,
                environment,
                module,
                stack,
            )
        factories = [keyword for keyword in expression.keywords if keyword.arg == "default_factory"]
        if len(factories) != 1 or not isinstance(factories[0].value, ast.Name):
            return _DYNAMIC_AMBIGUOUS
        factory = factories[0].value.id
        if factory == "dict" and factory not in environment:
            return _dynamic_mapping_binding((), ())
        if factory in {"list", "tuple", "set", "frozenset"} and factory not in environment:
            return _dynamic_sequence_binding(
                (),
                kind="iterable" if factory in {"set", "frozenset"} else "sequence",
            )
        return _DYNAMIC_AMBIGUOUS

    def _deferred_source_class_instance_binding(
        self,
        node: ast.Call,
        source_name: str,
        environment: Mapping[str, _DynamicImportBinding],
        module: str,
        stack: tuple[tuple[str, str], ...],
        *,
        argument_values: Mapping[str, _DynamicImportBinding] | None = None,
        argument_bindings: Sequence[_DynamicImportBinding] | None = None,
    ) -> _DynamicImportBinding:
        """Keep unknown source-class fields unresolved until a consumer selects one."""
        if argument_bindings is None:
            values = [
                self._expression_binding(argument, environment, module, stack)
                for argument in node.args
            ]
            values.extend(
                self._expression_binding(keyword.value, environment, module, stack)
                for keyword in node.keywords
            )
        else:
            values = list(argument_bindings)

        fields: dict[str, _DynamicImportBinding] = {}
        positional_count = len(node.args)
        for index, keyword in enumerate(node.keywords):
            if keyword.arg is None:
                continue
            value = (
                argument_values[keyword.arg]
                if argument_values is not None and keyword.arg in argument_values
                else values[positional_count + index]
            )
            fields[keyword.arg] = replace(
                _DYNAMIC_DEFERRED,
                name=value.name,
                guarded=value.guarded,
                origin_name=value.origin_name,
            )

        keys = tuple(_dynamic_string_binding(name) for name in fields)
        return _DynamicImportBinding(
            "object",
            source_name,
            guarded=any(value.guarded for value in values),
            items=keys,
            values=tuple(fields.values()),
        )

    def _source_class_instance_binding(
        self,
        node: ast.Call,
        source_name: str,
        environment: Mapping[str, _DynamicImportBinding],
        module: str,
        stack: tuple[tuple[str, str], ...],
        *,
        argument_values: Mapping[str, _DynamicImportBinding] | None = None,
        argument_bindings: Sequence[_DynamicImportBinding] | None = None,
    ) -> _DynamicImportBinding:
        """Summarize named fields, deferring opaque source-class fields to use sites."""
        if not source_name.startswith("polisyos."):
            return _DYNAMIC_AMBIGUOUS
        if (
            node.args
            or any(keyword.arg is None for keyword in node.keywords)
            or self._expression_binding(node.func, environment, module, stack).guarded
            or not self._source_class_is_summarizable(
                source_name,
                current_module=module,
                current_environment=environment,
                stack=stack,
            )
        ):
            return self._deferred_source_class_instance_binding(
                node,
                source_name,
                environment,
                module,
                stack,
                argument_values=argument_values,
                argument_bindings=argument_bindings,
            )
        fields = self._source_class_field_defaults(
            source_name,
            current_module=module,
            current_environment=environment,
            stack=stack,
        )
        if fields is None:
            return self._deferred_source_class_instance_binding(
                node,
                source_name,
                environment,
                module,
                stack,
                argument_values=argument_values,
                argument_bindings=argument_bindings,
            )
        explicit: dict[str, _DynamicImportBinding] = {}
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg not in fields or keyword.arg in explicit:
                return self._deferred_source_class_instance_binding(
                    node,
                    source_name,
                    environment,
                    module,
                    stack,
                    argument_values=argument_values,
                    argument_bindings=argument_bindings,
                )
            explicit[keyword.arg] = (
                argument_values[keyword.arg]
                if argument_values is not None and keyword.arg in argument_values
                else self._expression_binding(keyword.value, environment, module, stack)
            )
            if argument_values is not None and keyword.arg not in argument_values:
                return _DYNAMIC_AMBIGUOUS
        fields.update(explicit)
        names = tuple(fields)
        values = tuple(fields[name] for name in names)
        return _DynamicImportBinding(
            "object",
            source_name,
            guarded=any(value.guarded for value in values),
            items=tuple(_dynamic_string_binding(name) for name in names),
            values=values,
            origin_name=source_name,
        )

    def _export_binding(
        self,
        module: str,
        symbol: str,
        *,
        stack: tuple[tuple[str, str], ...],
    ) -> _DynamicImportBinding:
        key = (module, symbol)
        if key in stack or len(stack) >= 32:
            return _DYNAMIC_AMBIGUOUS
        if module in self.environments:
            environment = self.environments[module]
        else:
            environment = self._module_environment(module, (*stack, key))
        if environment is None:
            # Namespace packages have no module file whose exports can be
            # inspected. A direct child selected from the same source root is
            # still an exact module import; do not infer arbitrary attributes.
            child_module = f"{module}.{symbol}"
            if module not in self.module_paths and self._has_module(child_module):
                return _DynamicImportBinding("module", child_module)
            return _DYNAMIC_AMBIGUOUS
        if symbol in environment:
            value = environment[symbol]
            if value.kind != "ambiguous":
                return value
            # A module-level PEP 562 export may be a bounded branch over a
            # literal name and a statically imported module. Resolve that narrow
            # source contract without executing the hook.
            lazy_value = self._module_getattr_export(module, symbol, stack=stack)
            return lazy_value if lazy_value is not None else value
        child_module = f"{module}.{symbol}"
        if self._has_module(child_module):
            return _DynamicImportBinding("module", child_module)
        lazy_value = self._module_getattr_export(module, symbol, stack=stack)
        return lazy_value if lazy_value is not None else _DYNAMIC_AMBIGUOUS

    def _module_execution_snapshot(
        self, module: str
    ) -> _DynamicImportModuleExecutionSnapshot | None:
        """Return an immutable namespace snapshot after selected module-time calls."""
        if module in self._module_execution_scans_in_progress:
            return None
        if module in self._module_execution_snapshots:
            return self._module_execution_snapshots[module]

        path = self.module_paths.get(module)
        if path is None:
            self._module_execution_snapshots[module] = None
            return None
        member = (
            next(
                (candidate for candidate in self.source_context.members if candidate.path == path),
                None,
            )
            if self.source_context is not None
            else None
        )
        if self.source_context is not None and member is None:
            self._module_execution_snapshots[module] = None
            return None
        tree = member.tree if member is not None else self._module_tree(module)
        if tree is None:
            self._module_execution_snapshots[module] = None
            return None
        relative_path = member.relative_path if member is not None else _dynamic_source_label(path)

        self._module_execution_scans_in_progress.add(module)
        try:
            # Replays use isolated mutable namespaces. Only immutable snapshots
            # and the recursion guard are shared across these exact source bytes.
            isolated_bindings = _DynamicImportSourceBindings(
                self.source_paths,
                source_context=self.source_context,
            )
            isolated_bindings._module_execution_snapshots = self._module_execution_snapshots
            # Keep the exact selected AST snapshot, including an explicit overlay
            # used by tests or the source context, while isolating mutable bindings.
            isolated_bindings.trees = dict(self.trees)
            isolated_bindings._module_execution_scans_in_progress = (
                self._module_execution_scans_in_progress
            )
            isolated_bindings._cross_module_namespace_writes = self._cross_module_namespace_writes
            isolated_bindings._source_mapping_effects = self._source_mapping_effects
            scanner = _DynamicImportSourceScanner(
                path,
                relative_path=relative_path,
                source_bindings=isolated_bindings,
                source_context=self.source_context,
            )
            scanner.scan(tree)
            snapshot = _DynamicImportModuleExecutionSnapshot(
                hook=scanner._module_environment.get("__getattr__"),
                namespace=tuple(sorted(scanner._module_environment.items())),
                namespace_complete=scanner._module_namespace_complete,
                written_names=frozenset(scanner._module_namespace_written_names),
            )
        except DynamicImportCollectionError:
            snapshot = None
        finally:
            self._module_execution_scans_in_progress.remove(module)
        self._module_execution_snapshots[module] = snapshot
        return snapshot

    def _module_getattr_export(
        self,
        module: str,
        symbol: str,
        *,
        stack: tuple[tuple[str, str], ...],
    ) -> _DynamicImportBinding | None:
        tree = self._module_tree(module)
        path = self.module_paths.get(module)
        if tree is None or path is None:
            return None
        future_annotations = _future_annotations_enabled(tree)

        class _ModuleGetattrBindings(ast.NodeVisitor):
            """Find the effective module hook and source-visible rebinding."""

            def __init__(self) -> None:
                self.hooks: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
                self.rebound = False
                self.namespace_aliases: set[str] = set()

            def _namespace_expression(self, node: ast.AST, aliases: set[str]) -> bool:
                if isinstance(node, ast.Name):
                    return node.id in aliases
                if not isinstance(node, ast.Call):
                    return False
                binding = self_outer._expression_binding(node.func, environment, module, stack)
                if binding.kind != "callable":
                    return False
                if binding.name == "builtins.vars":
                    # ``vars(module)`` and zero-argument ``vars()`` both expose
                    # a namespace mapping; keep the receiver opaque here and
                    # let the effect checks fail closed on a relevant write.
                    return len(node.args) <= 1 and not node.keywords
                if binding.name == "builtins.getattr":
                    return (
                        len(node.args) >= 2
                        and isinstance(node.args[1], ast.Constant)
                        and node.args[1].value == "__dict__"
                        and not node.keywords
                    )
                return (
                    binding.name in _DYNAMIC_MODULE_NAMESPACE_FACTORIES
                    and not node.args
                    and not node.keywords
                )

            def _namespace_value(self, node: ast.AST) -> bool:
                """Return whether an expression carries the module namespace mapping."""
                if self._namespace_expression(node, self.namespace_aliases):
                    return True
                if isinstance(node, ast.Call):
                    return any(self._namespace_value(argument) for argument in node.args) or any(
                        self._namespace_value(keyword.value) for keyword in node.keywords
                    )
                if isinstance(node, ast.Attribute):
                    return self._namespace_value(node.value)
                return any(self._namespace_value(child) for child in ast.iter_child_nodes(node))

            def _record_namespace_assignment(self, target: ast.AST, value: ast.AST) -> None:
                direct_alias = self._namespace_expression(value, self.namespace_aliases) or (
                    isinstance(value, ast.Name) and value.id in self.namespace_aliases
                )
                if direct_alias and isinstance(target, ast.Name):
                    self.namespace_aliases.add(target.id)
                elif self._namespace_value(value):
                    # Aliasing through a container, property, or unsupported
                    # expression escapes the bounded namespace-flow grammar.
                    self.rebound = True

            @staticmethod
            def _literal_key(node: ast.AST) -> str | None:
                return (
                    node.value
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    else None
                )

            def _check_namespace_target(self, target: ast.AST) -> None:
                if isinstance(target, ast.Attribute) and target.attr == "__getattr__":
                    self.rebound = True
                    return
                if isinstance(target, ast.Subscript) and self._namespace_expression(
                    target.value, self.namespace_aliases
                ):
                    key = self._literal_key(target.slice)
                    if key is None or key == "__getattr__":
                        self.rebound = True

            def _check_namespace_call(self, node: ast.Call) -> None:
                function = node.func
                if not isinstance(function, ast.Attribute) or not self._namespace_expression(
                    function.value, self.namespace_aliases
                ):
                    return
                if function.attr in {"get", "keys", "values", "items", "copy"}:
                    return
                if function.attr in {"clear", "popitem"}:
                    self.rebound = True
                    return
                if function.attr in {"setdefault", "pop"}:
                    key = self._literal_key(node.args[0]) if node.args else None
                    if key is None or key == "__getattr__":
                        self.rebound = True
                    return
                if function.attr == "update":
                    if node.keywords and any(keyword.arg is None for keyword in node.keywords):
                        self.rebound = True
                        return
                    keys: set[str] = {keyword.arg for keyword in node.keywords if keyword.arg}
                    if node.args:
                        source = node.args[0]
                        if isinstance(source, ast.Dict) and all(
                            key is not None
                            and isinstance(key, ast.Constant)
                            and isinstance(key.value, str)
                            for key in source.keys
                        ):
                            keys.update(
                                key.value for key in source.keys if isinstance(key, ast.Constant)
                            )
                        else:
                            binding = self_outer._expression_binding(
                                source, environment, module, stack
                            )
                            if (
                                binding.kind != "mapping"
                                or binding.items is None
                                or not binding.immutable
                                or any(
                                    item.kind != "string" or item.name is None
                                    for item in binding.items
                                )
                            ):
                                self.rebound = True
                                return
                            keys.update(
                                item.name for item in binding.items if item.name is not None
                            )
                    if "__getattr__" in keys:
                        self.rebound = True
                    return
                # An unknown mutating operation on a module namespace cannot
                # establish that the original hook is still installed.
                self.rebound = True

            def visit_Name(self, node: ast.Name) -> None:
                if isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == "__getattr__":
                    self.rebound = True

            def visit_Import(self, node: ast.Import) -> None:
                if any(
                    (alias.asname or alias.name.split(".", 1)[0]) == "__getattr__"
                    for alias in node.names
                ):
                    self.rebound = True

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if any((alias.asname or alias.name) == "__getattr__" for alias in node.names):
                    self.rebound = True

            def visit_Assign(self, node: ast.Assign) -> None:
                for target in node.targets:
                    self._record_namespace_assignment(target, node.value)
                    self._check_namespace_target(target)
                self.generic_visit(node)

            def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                if node.value is not None:
                    self._record_namespace_assignment(node.target, node.value)
                self._check_namespace_target(node.target)
                self.generic_visit(node)

            def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
                self._record_namespace_assignment(node.target, node.value)
                self._check_namespace_target(node.target)
                self.generic_visit(node)

            def visit_AugAssign(self, node: ast.AugAssign) -> None:
                if isinstance(node.target, ast.Name) and node.target.id in self.namespace_aliases:
                    self.rebound = True
                self._check_namespace_target(node.target)
                self.generic_visit(node)

            def visit_Delete(self, node: ast.Delete) -> None:
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in self.namespace_aliases:
                        self.namespace_aliases.remove(target.id)
                    else:
                        self._check_namespace_target(target)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:
                self._check_namespace_call(node)
                callee = self_outer._expression_binding(node.func, environment, module, stack)
                lazy_export_contract = (
                    self_outer._lazy_export_call_contract(
                        node,
                        environment,
                        module,
                        stack,
                        callee=callee,
                    )
                    if callee.kind == "callable"
                    and callee.name == _DYNAMIC_LAZY_EXPORT_RESOLVER_FQN
                    else None
                )
                passes_namespace = any(
                    self._namespace_value(argument) for argument in node.args
                ) or any(self._namespace_value(keyword.value) for keyword in node.keywords)
                if (
                    callee.kind == "callable"
                    and callee.name == _DYNAMIC_LAZY_EXPORT_RESOLVER_FQN
                    and lazy_export_contract is None
                ) or (passes_namespace and lazy_export_contract is None):
                    self.rebound = True
                if callee.kind == "callable" and callee.name in {
                    "builtins.eval",
                    "builtins.exec",
                }:
                    self.rebound = True
                if callee.kind == "callable" and callee.name in {
                    "builtins.setattr",
                    "builtins.delattr",
                }:
                    key = self._literal_key(node.args[1]) if len(node.args) > 1 else None
                    if key is None or key == "__getattr__":
                        self.rebound = True
                self.generic_visit(node)

            def visit_Attribute(self, node: ast.Attribute) -> None:
                if node.attr == "__dict__":
                    namespace = self_outer._expression_binding(
                        node.value, environment, module, stack
                    )
                    if namespace.kind in {"module", "namespace", "unknown", "ambiguous"}:
                        # A module namespace reached through __dict__ is outside
                        # the local globals/locals transfer grammar.
                        self.rebound = True
                self.generic_visit(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                if node.name == "__getattr__":
                    self.hooks.append(node)
                self._visit_definition_expressions(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                if node.name == "__getattr__":
                    self.hooks.append(node)
                self._visit_definition_expressions(node)

            def _visit_definition_expressions(
                self, node: ast.FunctionDef | ast.AsyncFunctionDef
            ) -> None:
                for expression in (*node.decorator_list, *node.args.defaults):
                    if self._namespace_value(expression):
                        self.rebound = True
                    self.visit(expression)
                for expression in node.args.kw_defaults:
                    if expression is not None:
                        if self._namespace_value(expression):
                            self.rebound = True
                        self.visit(expression)
                if not future_annotations:
                    for argument in (
                        *node.args.posonlyargs,
                        *node.args.args,
                        *node.args.kwonlyargs,
                        *((node.args.vararg,) if node.args.vararg else ()),
                        *((node.args.kwarg,) if node.args.kwarg else ()),
                    ):
                        if argument.annotation is not None:
                            if self._namespace_value(argument.annotation):
                                self.rebound = True
                            self.visit(argument.annotation)
                    if node.returns is not None:
                        if self._namespace_value(node.returns):
                            self.rebound = True
                        self.visit(node.returns)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                if node.name == "__getattr__":
                    self.rebound = True
                for expression in (*node.decorator_list, *node.bases, *node.keywords):
                    if self._namespace_value(expression):
                        self.rebound = True
                    self.visit(expression)

        self_outer = self
        environment = self.environments.get(module) or {}
        bindings = _ModuleGetattrBindings()
        bindings.visit(tree)

        def unresolved_module_getattr_export() -> _DynamicImportBinding:
            return _dynamic_unresolved_importer_binding((f"{module}.__getattr__",))

        if not bindings.hooks:
            return unresolved_module_getattr_export() if bindings.rebound else None
        if len(bindings.hooks) != 1 or bindings.rebound:
            return unresolved_module_getattr_export()
        hook = bindings.hooks[0]
        snapshot = self._module_execution_snapshot(module)
        expected_hook_identity = f"{_dynamic_source_label(path)}:{hook.lineno}:{hook.col_offset}"
        if (
            snapshot is None
            or not snapshot.namespace_complete
            or snapshot.hook is None
            or snapshot.hook.kind != "source_function"
            or snapshot.hook.origin_name != expected_hook_identity
        ):
            return unresolved_module_getattr_export()

        hook_globals = _dynamic_hook_global_names(
            hook,
            future_annotations=future_annotations,
        )
        external_effects = (
            dict(self.source_context.module_namespace_effects or ())
            if self.source_context is not None
            else {}
        )
        if module in external_effects:
            changed_names = external_effects[module]
            if (
                changed_names is None
                or {"__getattr__"} & set(changed_names)
                or (hook_globals & set(changed_names))
            ):
                return unresolved_module_getattr_export()

        initial_environment = environment
        environment = dict(snapshot.namespace)
        observed_hook_globals: set[str] = set()

        def record_hook_global_reads(node: ast.AST) -> None:
            if isinstance(node, ast.Assign):
                expressions = [*node.targets, node.value]
            elif isinstance(node, ast.AnnAssign):
                expressions = [node.target]
                if node.value is not None:
                    expressions.append(node.value)
                if not future_annotations:
                    expressions.append(node.annotation)
            elif isinstance(node, ast.AugAssign):
                expressions = [node.target, node.value]
            elif isinstance(node, ast.Raise):
                expressions = [node.exc]
                if node.cause is not None:
                    expressions.append(node.cause)
            elif isinstance(node, ast.expr):
                expressions = [node]
            else:
                expressions = []

            for expression in expressions:
                expression_scope = ast.Lambda(
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=None,
                        defaults=[],
                    ),
                    body=expression,
                )
                reads, _, _ = _dynamic_scope_read_dependencies(
                    expression_scope,
                    future_annotations=future_annotations,
                )
                observed_hook_globals.update(hook_globals.intersection(reads))

        positional_arguments = [*hook.args.posonlyargs, *hook.args.args]
        if (
            isinstance(hook, ast.AsyncFunctionDef)
            or hook.decorator_list
            or len(positional_arguments) != 1
            or hook.args.defaults
            or hook.args.vararg is not None
            or hook.args.kwarg is not None
            or hook.args.kwonlyargs
            or any(default is not None for default in hook.args.kw_defaults)
            or getattr(hook, "type_params", ())
            or any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(hook))
        ):
            return _DYNAMIC_AMBIGUOUS
        if not future_annotations:
            annotations = [
                argument.annotation
                for argument in positional_arguments
                if argument.annotation is not None
            ]
            if hook.returns is not None:
                annotations.append(hook.returns)
            if any(
                not isinstance(annotation, (ast.Name, ast.Constant)) for annotation in annotations
            ):
                return _DYNAMIC_AMBIGUOUS
        parameter = positional_arguments[0].arg
        environment = dict(environment)
        environment[parameter] = _dynamic_string_binding(symbol)

        def condition_result(
            node: ast.expr,
            local_environment: Mapping[str, _DynamicImportBinding],
        ) -> bool | None:
            record_hook_global_reads(node)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                value = condition_result(node.operand, local_environment)
                return None if value is None else not value
            if isinstance(node, ast.BoolOp):
                values = [condition_result(value, local_environment) for value in node.values]
                if isinstance(node.op, ast.And):
                    if False in values:
                        return False
                    return True if all(value is True for value in values) else None
                if True in values:
                    return True
                return False if all(value is False for value in values) else None
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                return None
            left, right = node.left, node.comparators[0]
            operation = node.ops[0]
            left_binding = self._expression_binding(left, local_environment, module, stack)
            right_binding = self._expression_binding(right, local_environment, module, stack)
            if isinstance(operation, (ast.In, ast.NotIn)):
                found: bool | None = None
                source_owned_export_map = (
                    isinstance(right, ast.Name)
                    and right.id in local_environment
                    and self._source_literal_mapping_is_current(right_binding)
                )
                if right_binding.kind == "mapping" and (
                    right_binding.immutable or source_owned_export_map
                ):
                    lookup = _dynamic_mapping_lookup(
                        right_binding,
                        left_binding,
                        default=_DYNAMIC_NONE,
                    )
                    if lookup.kind == "none":
                        found = False
                    elif lookup.kind not in {"unknown", "ambiguous"}:
                        found = True
                elif (
                    right_binding.kind in {"sequence", "iterable"}
                    and right_binding.items is not None
                ):
                    candidates = _dynamic_binding_alternatives(left_binding)
                    if candidates is not None:
                        possible = [
                            _dynamic_bindings_may_equal(candidate, item)
                            for candidate in candidates
                            for item in right_binding.items
                        ]
                        found = any(possible) if possible else False
                if found is None:
                    return None
                return not found if isinstance(operation, ast.NotIn) else found
            equal: bool | None = None
            if left_binding.kind == right_binding.kind == "none":
                equal = True
            elif (
                left_binding.kind == "none"
                and right_binding.kind
                in {"callable", "iterable", "mapping", "module", "sequence", "string", "type"}
            ) or (
                right_binding.kind == "none"
                and left_binding.kind
                in {"callable", "iterable", "mapping", "module", "sequence", "string", "type"}
            ):
                equal = False
            elif (
                left_binding.kind == right_binding.kind == "string"
                and left_binding.name is not None
                and right_binding.name is not None
            ):
                equal = left_binding.name == right_binding.name
            if equal is None:
                return None
            if isinstance(operation, (ast.Eq, ast.Is)):
                return equal
            if isinstance(operation, (ast.NotEq, ast.IsNot)):
                return not equal
            return None

        def assign_target(
            target: ast.AST,
            value: _DynamicImportBinding,
            local_environment: dict[str, _DynamicImportBinding],
        ) -> bool:
            if isinstance(target, ast.Name):
                local_environment[target.id] = value
                return True
            if isinstance(target, (ast.Tuple, ast.List)):
                if (
                    value.kind not in {"sequence", "iterable"}
                    or value.items is None
                    or len(target.elts) != len(value.items)
                ):
                    return False
                return all(
                    assign_target(item, item_value, local_environment)
                    for item, item_value in zip(target.elts, value.items, strict=True)
                )
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Call)
                and isinstance(target.value.func, ast.Name)
                and target.value.func.id == "globals"
                and not target.value.args
                and not target.value.keywords
                and isinstance(target.slice, ast.Name)
                and target.slice.id == parameter
                and value.kind not in {"unknown", "ambiguous"}
            ):
                # PEP 562 facades commonly cache the proven export in their
                # module namespace. The exact requested export name is the
                # only admitted global write; it cannot alter the source map.
                return True
            return False

        def execute(
            statements: Sequence[ast.stmt],
            local_environment: dict[str, _DynamicImportBinding],
        ) -> _DynamicImportBinding | None:
            remaining = statements
            if (
                remaining
                and isinstance(remaining[0], ast.Expr)
                and isinstance(remaining[0].value, ast.Constant)
                and isinstance(remaining[0].value.value, str)
            ):
                # A function docstring has no import-binding effect. This is
                # the only expression statement admitted by the bounded hook
                # evaluator; arbitrary expressions remain unresolved.
                remaining = remaining[1:]
            for statement in remaining:
                if isinstance(statement, ast.If):
                    selected = condition_result(statement.test, local_environment)
                    if selected is None:
                        return _DYNAMIC_AMBIGUOUS
                    result = execute(
                        statement.body if selected else statement.orelse,
                        local_environment,
                    )
                    if result is not None:
                        return result
                elif isinstance(statement, ast.Import):
                    for alias in statement.names:
                        bound_name = alias.asname or alias.name.split(".", 1)[0]
                        imported_module = (
                            alias.name if alias.asname else alias.name.split(".", 1)[0]
                        )
                        local_environment[bound_name] = self.import_binding(
                            imported_module,
                            None,
                            current_module=module,
                            is_package=path.name == "__init__.py",
                            stack=stack,
                        )
                elif isinstance(statement, ast.ImportFrom):
                    imported_module = ("." * statement.level) + (statement.module or "")
                    if any(alias.name == "*" for alias in statement.names):
                        return _DYNAMIC_AMBIGUOUS
                    for alias in statement.names:
                        bound_name = alias.asname or alias.name
                        local_environment[bound_name] = self.import_binding(
                            imported_module,
                            alias.name,
                            current_module=module,
                            is_package=path.name == "__init__.py",
                            stack=stack,
                        )
                elif isinstance(statement, ast.Assign):
                    record_hook_global_reads(statement)
                    value = self._expression_binding(
                        statement.value, local_environment, module, stack
                    )
                    if not all(
                        assign_target(target, value, local_environment)
                        for target in statement.targets
                    ):
                        return _DYNAMIC_AMBIGUOUS
                elif isinstance(statement, ast.AnnAssign):
                    record_hook_global_reads(statement)
                    if statement.value is not None:
                        value = self._expression_binding(
                            statement.value, local_environment, module, stack
                        )
                        if not assign_target(statement.target, value, local_environment):
                            return _DYNAMIC_AMBIGUOUS
                elif isinstance(statement, ast.Return):
                    if statement.value is None:
                        return _DYNAMIC_OTHER
                    record_hook_global_reads(statement.value)
                    return self._expression_binding(
                        statement.value, local_environment, module, stack
                    )
                elif isinstance(statement, ast.Raise):
                    record_hook_global_reads(statement)
                    if (
                        isinstance(statement.exc, ast.Call)
                        and isinstance(statement.exc.func, ast.Name)
                        and statement.exc.func.id == "AttributeError"
                    ):
                        return _DYNAMIC_NONE
                    return _DYNAMIC_AMBIGUOUS
                elif isinstance(statement, ast.Pass):
                    continue
                else:
                    return _DYNAMIC_AMBIGUOUS
            return None

        resolved = execute(hook.body, environment)
        for name in observed_hook_globals:
            before = initial_environment.get(name, _DYNAMIC_UNKNOWN)
            after = environment.get(name, _DYNAMIC_UNKNOWN)
            if (before != after or name in snapshot.written_names) and not (
                _dynamic_importer_origins(after)
                or _dynamic_unresolved_importer_origins(after)
                or _dynamic_binding_is_proven_nonimporter(after)
                or _dynamic_binding_is_same_module_namespace_refinement(before, after)
                or self._source_literal_mapping_is_current(after)
            ):
                return unresolved_module_getattr_export()
        return None if resolved is not None and resolved.kind == "none" else resolved

    @staticmethod
    def _literal_string_choices(node: ast.AST) -> frozenset[str] | None:
        if isinstance(node, ast.Name):
            return None
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values: list[str] = []
            for item in node.elts:
                if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                    return None
                values.append(item.value)
            return frozenset(values)
        return None

    def record_module_namespace_write(self, module: str, name: str | None) -> None:
        """Record a reached module namespace write for cross-module source replay."""
        prior = self._cross_module_namespace_writes.get(module)
        if module not in self._cross_module_namespace_writes:
            self._cross_module_namespace_writes[module] = set()
            prior = self._cross_module_namespace_writes[module]
        if name is None:
            self._cross_module_namespace_writes[module] = None
        elif prior is not None:
            prior.add(name)

    def _module_namespace_effect_binding(
        self,
        module: str,
        name: str | None,
        binding: _DynamicImportBinding,
    ) -> _DynamicImportBinding:
        """Guard importer members changed through any selected module namespace."""
        if name is None or self.source_context is None:
            return binding
        effects = dict(self.source_context.module_namespace_effects or ())
        if module not in effects:
            return binding
        changed_names = effects[module]
        if changed_names is not None and name not in changed_names:
            return binding
        importer_origins = (
            set(_dynamic_importer_origins(binding))
            | set(_dynamic_unresolved_importer_origins(binding))
            | set(_dynamic_import_namespace_origins(binding))
        )
        if (
            binding.kind == "module"
            and binding.name is not None
            and _dynamic_is_importer_namespace_name(binding.name)
        ):
            importer_origins.add(binding.name)
        importer_origins.update(_dynamic_temporal_callable_origins(binding))
        if not importer_origins:
            return binding
        return _dynamic_unresolved_importer_binding(
            sorted(importer_origins),
            name=binding.name,
        )

    def module_namespace_effects(self) -> tuple[tuple[str, tuple[str, ...] | None], ...]:
        """Return immutable module namespace effects from this selected scan."""
        return tuple(
            (
                module,
                None if names is None else tuple(sorted(names)),
            )
            for module, names in sorted(self._cross_module_namespace_writes.items())
        )

    def _module_environment(
        self,
        module: str,
        stack: tuple[tuple[str, str], ...],
        *,
        before_statement: ast.stmt | None = None,
    ) -> dict[str, _DynamicImportBinding] | None:
        tree = self._module_tree(module)
        path = self.module_paths.get(module)
        if tree is None or path is None:
            return None
        statements = tree.body
        if before_statement is not None:
            boundary = next(
                (
                    index
                    for index, statement in enumerate(tree.body)
                    if statement is before_statement
                ),
                None,
            )
            if boundary is None:
                return None
            statements = tree.body[:boundary]
        environment: dict[str, _DynamicImportBinding] = {}
        saw_star_import = False
        global_rebindings: set[str] = set()
        for statement in statements:
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    bound_name = alias.asname or alias.name.split(".", 1)[0]
                    imported_module = alias.name if alias.asname else alias.name.split(".", 1)[0]
                    value = self.import_binding(
                        imported_module,
                        None,
                        current_module=module,
                        is_package=path.name == "__init__.py",
                        stack=stack,
                    )
                    environment[bound_name] = value
            elif isinstance(statement, ast.ImportFrom):
                imported_module = ("." * statement.level) + (statement.module or "")
                if any(alias.name == "*" for alias in statement.names):
                    saw_star_import = True
                    continue
                for alias in statement.names:
                    bound_name = alias.asname or alias.name
                    environment[bound_name] = self.import_binding(
                        imported_module,
                        alias.name,
                        current_module=module,
                        is_package=path.name == "__init__.py",
                        stack=stack,
                    )
            elif isinstance(statement, ast.Assign):
                value = self._expression_binding(statement.value, environment, module, stack)
                for target in statement.targets:
                    for bound_name in self._simple_target_names(target):
                        if (
                            module in self._selected_source_module_names()
                            and _dynamic_is_source_lazy_export_map(
                                module,
                                bound_name,
                                statement.value,
                                value,
                            )
                        ):
                            value = replace(value, origin_name=f"{module}.{bound_name}")
                        environment[bound_name] = value
            elif isinstance(statement, ast.AnnAssign):
                if statement.value is not None:
                    value = self._expression_binding(statement.value, environment, module, stack)
                    for bound_name in self._simple_target_names(statement.target):
                        if (
                            module in self._selected_source_module_names()
                            and _dynamic_is_source_lazy_export_map(
                                module,
                                bound_name,
                                statement.value,
                                value,
                            )
                        ):
                            value = replace(value, origin_name=f"{module}.{bound_name}")
                        environment[bound_name] = value
            elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if module == "polisyos.ir.api" and statement.name == "resolve_lazy_export":
                    environment[statement.name] = (
                        _DynamicImportBinding("callable", _DYNAMIC_LAZY_EXPORT_RESOLVER_FQN)
                        if _dynamic_lazy_export_resolver_contract_matches(statement)
                        else _DYNAMIC_AMBIGUOUS
                    )
                elif isinstance(statement, ast.ClassDef):
                    environment[statement.name] = replace(
                        _DYNAMIC_OTHER,
                        origin_name=f"{module}.{statement.name}",
                    )
                else:
                    environment[statement.name] = replace(
                        _DYNAMIC_OTHER,
                        origin_name=f"{module}.{statement.name}",
                    )
            elif isinstance(
                statement,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.Try,
                    ast.With,
                    ast.AsyncWith,
                    ast.Match,
                ),
            ):
                for bound_name in self._nested_module_names(statement):
                    environment[bound_name] = _DYNAMIC_AMBIGUOUS
            elif isinstance(statement, ast.Delete):
                for target in statement.targets:
                    for bound_name in self._simple_target_names(target):
                        environment[bound_name] = _DYNAMIC_AMBIGUOUS
            elif isinstance(statement, ast.AugAssign):
                for bound_name in self._simple_target_names(statement.target):
                    environment[bound_name] = _DYNAMIC_AMBIGUOUS

        for statement in statements:
            for node in ast.walk(statement):
                if isinstance(node, ast.Global):
                    global_rebindings.update(node.names)
        for name in global_rebindings:
            if name in environment:
                environment[name] = _DYNAMIC_AMBIGUOUS
        if saw_star_import:
            return None
        if before_statement is None:
            self.environments[module] = environment
        return environment

    @staticmethod
    def _simple_target_names(target: ast.AST) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, (ast.Tuple, ast.List)):
            return set().union(
                *(_DynamicImportSourceBindings._simple_target_names(item) for item in target.elts)
            )
        return set()

    @staticmethod
    def _nested_module_names(statement: ast.AST) -> set[str]:
        names: set[str] = set()
        stack = [statement]
        while stack:
            node = stack.pop()
            if node is not statement and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
            ):
                names.add(node.name) if hasattr(node, "name") else None
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                names.add(node.id)
            elif isinstance(node, ast.Import):
                names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.update(
                    alias.asname or alias.name for alias in node.names if alias.name != "*"
                )
            stack.extend(ast.iter_child_nodes(node))
        return names

    def _expression_binding(
        self,
        node: ast.AST,
        environment: Mapping[str, _DynamicImportBinding],
        module: str,
        stack: tuple[tuple[str, str], ...],
    ) -> _DynamicImportBinding:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return _dynamic_string_binding(node.value)
            return _DYNAMIC_NONE if node.value is None else _DYNAMIC_OTHER
        if isinstance(node, ast.Name):
            if node.id in environment:
                return environment[node.id]
            if node.id in {
                "__import__",
                "eval",
                "exec",
                "getattr",
                "globals",
                "locals",
                "setattr",
                "delattr",
                "type",
                "vars",
                *_DYNAMIC_ITERABLE_CONSTRUCTORS,
                *_DYNAMIC_CAPABILITY_PREDICATES,
            }:
                return _dynamic_builtin_binding(node.id)
            return _DYNAMIC_AMBIGUOUS
        if isinstance(node, ast.Attribute):
            base = self._expression_binding(node.value, environment, module, stack)
            if (
                node.attr == "TYPE_CHECKING"
                and _dynamic_type_checking_kind(base) == "typing_module"
            ):
                return _dynamic_type_checking_value_binding(str(base.name))
            value = _dynamic_attribute_binding(base, node.attr)
            for module_name in {
                binding.name
                for binding in _dynamic_binding_nodes(base)
                if binding.kind == "module" and binding.name is not None
            }:
                value = self._module_namespace_effect_binding(
                    module_name,
                    node.attr,
                    value,
                )
            return value
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            if any(isinstance(item, ast.Starred) for item in node.elts):
                return _DYNAMIC_AMBIGUOUS
            items = tuple(
                self._expression_binding(item, environment, module, stack) for item in node.elts
            )
            if any(item.kind in {"unknown", "ambiguous"} for item in items):
                return _DYNAMIC_AMBIGUOUS
            return _dynamic_sequence_binding(
                items,
                kind="iterable" if isinstance(node, ast.Set) else "sequence",
                component_names=(
                    tuple(item.id if isinstance(item, ast.Name) else None for item in node.elts)
                    if isinstance(node, ast.Tuple)
                    else None
                ),
                sequence_type=(
                    "tuple"
                    if isinstance(node, ast.Tuple)
                    else "list"
                    if isinstance(node, ast.List)
                    else None
                ),
            )
        if isinstance(node, ast.Dict):
            keys: list[_DynamicImportBinding] = []
            values: list[_DynamicImportBinding] = []
            for key_node, value_node in zip(node.keys, node.values, strict=True):
                value = self._expression_binding(value_node, environment, module, stack)
                if key_node is None:
                    if value.kind != "mapping" or value.items is None or value.values is None:
                        return _DYNAMIC_AMBIGUOUS
                    keys.extend(value.items)
                    values.extend(value.values)
                    continue
                key = self._expression_binding(key_node, environment, module, stack)
                if key.kind in {"unknown", "ambiguous"} or value.kind in {"unknown", "ambiguous"}:
                    return _DYNAMIC_AMBIGUOUS
                keys.append(key)
                values.append(value)
            if len(keys) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                return _DYNAMIC_AMBIGUOUS
            return _dynamic_mapping_binding(keys, values)
        if isinstance(node, ast.Call):
            callee = self._expression_binding(node.func, environment, module, stack)
            if _is_unresolved_importer_binding(callee):
                origins = (
                    set(_dynamic_importer_origins(callee))
                    | set(_dynamic_unresolved_importer_origins(callee))
                    | set(_dynamic_import_namespace_origins(callee))
                )
                return _dynamic_unresolved_importer_binding(
                    sorted(origins),
                    name=callee.name,
                )
            if callee.kind == "other" and callee.origin_name is not None:
                return self._source_class_instance_binding(
                    node,
                    callee.origin_name,
                    environment,
                    module,
                    stack,
                )
            if callee.kind == "callable" and callee.name == _DYNAMIC_LAZY_EXPORT_RESOLVER_FQN:
                return self._resolve_lazy_export_call(node, environment, module, stack)
            if callee.kind == "callable" and callee.name == "mapping.get":
                mapping = callee.receiver
                if (
                    mapping is None
                    or mapping.kind != "mapping"
                    or not mapping.immutable
                    or len(node.args) not in {1, 2}
                    or node.keywords
                ):
                    return _DYNAMIC_AMBIGUOUS
                key = self._expression_binding(node.args[0], environment, module, stack)
                default = (
                    self._expression_binding(node.args[1], environment, module, stack)
                    if len(node.args) == 2
                    else _DYNAMIC_NONE
                )
                result = _dynamic_mapping_lookup(mapping, key, default=default)
                return _DYNAMIC_AMBIGUOUS if result.kind in {"unknown", "ambiguous"} else result
            if callee.kind == "callable" and callee.name == "importlib.import_module":
                if len(node.args) != 1 or node.keywords:
                    return _DYNAMIC_AMBIGUOUS
                module_name = self._expression_binding(node.args[0], environment, module, stack)
                if module_name.kind != "string" or module_name.name is None:
                    return _DYNAMIC_AMBIGUOUS
                return self.import_binding(module_name.name, None, stack=stack)
            if callee.kind == "callable" and callee.name == "builtins.getattr":
                if len(node.args) < 2:
                    return _DYNAMIC_AMBIGUOUS
                base = self._expression_binding(node.args[0], environment, module, stack)
                name = self._expression_binding(node.args[1], environment, module, stack)
                if (
                    base.kind == "module"
                    and base.name is not None
                    and name.kind == "string"
                    and name.name is not None
                ):
                    return self.import_binding(base.name, name.name, stack=stack)
                if base.kind in {"unknown", "ambiguous"}:
                    if _is_guarded_importer_binding(base):
                        origins = (
                            set(_dynamic_importer_origins(base))
                            | set(_dynamic_unresolved_importer_origins(base))
                            | set(_dynamic_import_namespace_origins(base))
                        )
                        return _dynamic_unresolved_importer_binding(
                            sorted(origins),
                            name=base.name,
                        )
                    return _DYNAMIC_AMBIGUOUS
                return _DYNAMIC_OTHER
            if (
                callee.kind == "callable"
                and callee.name == "types.MappingProxyType"
                and len(node.args) == 1
                and not node.keywords
            ):
                mapping = self._expression_binding(node.args[0], environment, module, stack)
                if mapping.kind != "mapping" or mapping.items is None or mapping.values is None:
                    return _DYNAMIC_AMBIGUOUS
                if not isinstance(node.args[0], ast.Dict) and not mapping.immutable:
                    return _DYNAMIC_AMBIGUOUS
                return replace(mapping, immutable=True)
            return _DYNAMIC_AMBIGUOUS
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._expression_binding(node.left, environment, module, stack)
            right = self._expression_binding(node.right, environment, module, stack)
            if (
                left.kind == right.kind == "string"
                and left.name is not None
                and right.name is not None
            ):
                combined = left.name + right.name
                if len(combined) <= 4096:
                    return _dynamic_string_binding(combined)
            return _DYNAMIC_AMBIGUOUS
        if isinstance(node, ast.Subscript):
            mapping = self._expression_binding(node.value, environment, module, stack)
            key = self._expression_binding(node.slice, environment, module, stack)
            result = _dynamic_mapping_lookup(mapping, key)
            return _DYNAMIC_AMBIGUOUS if result.kind in {"unknown", "ambiguous"} else result
        return _DYNAMIC_AMBIGUOUS


class _DynamicImportScopeNames(ast.NodeVisitor):
    """Collect lexical bindings without crossing function/class/comprehension scopes."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.names.add(alias.asname or alias.name)

    def visit_Global(self, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocals.update(node.names)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name:
            self.names.add(node.name)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest:
            self.names.add(node.rest)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)
        self._visit_definition_expressions(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)
        self._visit_definition_expressions(node)

    def _visit_definition_expressions(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        for expression in (*node.decorator_list, *node.args.defaults):
            self.visit(expression)
        for expression in node.args.kw_defaults:
            if expression is not None:
                self.visit(expression)
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ):
            if argument.annotation is not None:
                self.visit(argument.annotation)
        for argument in (node.args.vararg, node.args.kwarg):
            if argument is not None and argument.annotation is not None:
                self.visit(argument.annotation)
        if node.returns is not None:
            self.visit(node.returns)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in (*node.args.defaults, *node.args.kw_defaults):
            if expression is not None:
                self.visit(expression)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)
        for expression in (*node.decorator_list, *node.bases):
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_outer_bindings(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_outer_bindings(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_outer_bindings(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_outer_bindings(node)

    def _visit_comprehension_outer_bindings(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    ) -> None:
        generators = node.generators
        if generators:
            self.visit(generators[0].iter)
        stack = list(ast.iter_child_nodes(node))
        while stack:
            child = stack.pop()
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(child, ast.NamedExpr):
                self.names.update(
                    name.id for name in ast.walk(child.target) if isinstance(name, ast.Name)
                )
                stack.extend(ast.iter_child_nodes(child.value))
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                continue
            stack.extend(ast.iter_child_nodes(child))


def _scope_local_bindings(nodes: Sequence[ast.stmt]) -> tuple[set[str], set[str], set[str]]:
    collector = _DynamicImportScopeNames()
    for node in nodes:
        collector.visit(node)
    locals_ = collector.names - collector.globals - collector.nonlocals
    return locals_, collector.globals, collector.nonlocals


class _DynamicImportScopeReadCollector(ast.NodeVisitor):
    """Collect direct reads and child scopes without executing them."""

    def __init__(self, *, future_annotations: bool = False) -> None:
        self.future_annotations = future_annotations
        self.read_names: set[str] = set()
        self.calls: list[ast.Call] = []
        self.child_scopes: list[ast.AST] = []

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.read_names.add(node.id)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.child_scopes.append(node)
        self._visit_definition_expressions(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.child_scopes.append(node)
        self._visit_definition_expressions(node)

    def _visit_definition_expressions(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expression in (*node.decorator_list, *node.args.defaults):
            self.visit(expression)
        for expression in node.args.kw_defaults:
            if expression is not None:
                self.visit(expression)
        if not self.future_annotations:
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                *((node.args.vararg,) if node.args.vararg else ()),
                *((node.args.kwarg,) if node.args.kwarg else ()),
            ):
                if argument.annotation is not None:
                    self.visit(argument.annotation)
            if node.returns is not None:
                self.visit(node.returns)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.child_scopes.append(node)
        for expression in (*node.decorator_list, *node.bases):
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)
        for statement in node.body:
            self.visit(statement)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.child_scopes.append(node)
        for expression in (*node.args.defaults, *node.args.kw_defaults):
            if expression is not None:
                self.visit(expression)


def _dynamic_scope_read_dependencies(
    scope: ast.AST,
    *,
    future_annotations: bool = False,
) -> tuple[frozenset[str], tuple[ast.Call, ...], tuple[ast.AST, ...]]:
    """Return free reads, calls, and deferred children for one source scope."""
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        statements = scope.body
        local_names, _, _ = _scope_local_bindings(statements)
        local_names.update(
            arg.arg
            for arg in (
                *scope.args.posonlyargs,
                *scope.args.args,
                *scope.args.kwonlyargs,
                *((scope.args.vararg,) if scope.args.vararg else ()),
                *((scope.args.kwarg,) if scope.args.kwarg else ()),
            )
        )
    elif isinstance(scope, ast.ClassDef):
        statements = scope.body
        local_names, _, _ = _scope_local_bindings(statements)
    elif isinstance(scope, ast.Lambda):
        statements = [ast.Expr(value=scope.body)]
        local_names = {
            arg.arg
            for arg in (
                *scope.args.posonlyargs,
                *scope.args.args,
                *scope.args.kwonlyargs,
                *((scope.args.vararg,) if scope.args.vararg else ()),
                *((scope.args.kwarg,) if scope.args.kwarg else ()),
            )
        }
    else:
        return frozenset(), (), ()

    collector = _DynamicImportScopeReadCollector(future_annotations=future_annotations)
    for statement in statements:
        collector.visit(statement)
    return (
        frozenset(collector.read_names - local_names),
        tuple(collector.calls),
        tuple(collector.child_scopes),
    )


def _dynamic_source_paths(*scopes: str) -> list[Path]:
    """Enumerate all selected Python paths, surfacing missing roots and walk errors."""
    ignored_parts = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "_build",
        "_cache",
        ".venv",
        "node_modules",
    }
    selected: list[Path] = []
    for scope in scopes:
        root = REPO_ROOT / scope
        try:
            root_mode = os.lstat(root).st_mode
        except OSError as error:
            raise DynamicImportCollectionError(
                f"source root {scope!r} is unavailable: {type(error).__name__}: {error}"
            ) from error
        if stat.S_ISLNK(root_mode):
            raise DynamicImportCollectionError(f"source root {scope!r} is a directory symlink")
        if not stat.S_ISDIR(root_mode):
            raise DynamicImportCollectionError(f"source root {scope!r} is unavailable")
        walk_errors: list[OSError] = []

        def record_walk_error(error: OSError, errors: list[OSError] = walk_errors) -> None:
            errors.append(error)

        for current, directories, filenames in os.walk(
            root,
            topdown=True,
            onerror=record_walk_error,
            followlinks=False,
        ):
            selected_directories: list[str] = []
            for name in sorted(directories):
                if name in ignored_parts:
                    continue
                directory_path = Path(current) / name
                try:
                    directory_mode = os.lstat(directory_path).st_mode
                except OSError as error:
                    raise DynamicImportCollectionError(
                        "source directory inspection failed under "
                        f"{scope!r}: {_import_source_path(directory_path)}: "
                        f"{type(error).__name__}: {error}"
                    ) from error
                if stat.S_ISLNK(directory_mode):
                    raise DynamicImportCollectionError(
                        "non-ignored directory symlink under "
                        f"{scope!r}: {_import_source_path(directory_path)}"
                    )
                selected_directories.append(name)
            directories[:] = selected_directories
            for filename in sorted(filenames):
                if Path(filename).suffix == ".py":
                    selected.append(Path(current) / filename)
        if walk_errors:
            error = walk_errors[0]
            raise DynamicImportCollectionError(
                f"source traversal failed under {scope!r}: {type(error).__name__}: {error}"
            ) from error
    return sorted(selected)


def _dynamic_source_label(path: Path) -> str:
    """Validate a selected source path and return its lexical repository label.

    Source symlinks are permitted only when their resolved target remains inside the
    repository. Keeping the label lexical preserves the selected path in diagnostics,
    while the resolved containment check prevents reading through an external link.
    """
    repository = REPO_ROOT.absolute()
    try:
        lexical_path = path.absolute().relative_to(repository)
    except ValueError as error:
        raise DynamicImportSourcePathError(
            f"selected source path is outside repository: {path.as_posix()}"
        ) from error

    try:
        resolved_repository = REPO_ROOT.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
        resolved_path.relative_to(resolved_repository)
    except ValueError as error:
        raise DynamicImportSourcePathError(
            f"{lexical_path.as_posix()}: selected source resolves outside repository"
        ) from error
    except (OSError, RuntimeError) as error:
        raise DynamicImportSourcePathError(
            f"{lexical_path.as_posix()}: selected source path cannot be resolved: "
            f"{type(error).__name__}: {error}"
        ) from error
    return lexical_path.as_posix()


def _dynamic_scope_cross_writes(
    scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> tuple[set[str], set[str]]:
    """Return possible global/nonlocal writes across one deferred scope tree."""
    global_writes: set[str] = set()
    nonlocal_writes: set[str] = set()
    scope_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def own_writes(statements: Sequence[ast.stmt]) -> tuple[set[str], set[str]]:
        collector = _DynamicImportScopeNames()
        for statement in statements:
            collector.visit(statement)
        return collector.names & collector.globals, collector.names & collector.nonlocals

    def nested_scopes(
        statements: Sequence[ast.stmt],
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
        found: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = []
        stack: list[ast.AST] = list(reversed(statements))
        while stack:
            node = stack.pop()
            if isinstance(node, scope_types):
                found.append(node)
                continue
            stack.extend(reversed(list(ast.iter_child_nodes(node))))
        return found

    pending = [scope]
    while pending:
        current = pending.pop()
        own_global, own_nonlocal = own_writes(current.body)
        global_writes.update(own_global)
        nonlocal_writes.update(own_nonlocal)
        pending.extend(nested_scopes(current.body))
    return global_writes, nonlocal_writes


def _dynamic_sys_modules_mapping(
    node: ast.AST,
    environment: Mapping[str, _DynamicImportBinding],
) -> bool:
    if isinstance(node, ast.Name):
        binding = environment.get(node.id)
        return binding is not None and binding.origin_name == "sys.modules"
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "modules"
        and isinstance(node.value, ast.Name)
    ):
        binding = environment.get(node.value.id)
        return binding is not None and binding.kind == "module" and binding.name == "sys"
    return False


def _dynamic_sys_modules_write_owners(
    node: ast.AST,
    environment: Mapping[str, _DynamicImportBinding],
) -> set[str]:
    if not isinstance(node, ast.Subscript) or not _dynamic_sys_modules_mapping(
        node.value, environment
    ):
        return set()
    key_known, key_value = _dynamic_ast_literal_key_value(node.slice)
    if key_known and isinstance(key_value, str) and key_value in _DYNAMIC_TYPE_CHECKING_MODULES:
        return {key_value}
    return set(_DYNAMIC_TYPE_CHECKING_MODULES)


def _dynamic_module_object_owners(
    node: ast.AST,
    environment: Mapping[str, _DynamicImportBinding],
) -> set[str]:
    """Find source-bound typing modules that an expression can carry or expose."""
    if isinstance(node, ast.Name):
        binding = environment.get(node.id)
        owner = _dynamic_type_checking_module_owner(binding) if binding is not None else None
        return {owner} if owner in _DYNAMIC_TYPE_CHECKING_MODULES else set()
    if isinstance(node, ast.Attribute):
        if node.attr == "__dict__":
            return _dynamic_module_object_owners(node.value, environment)
        return set()
    if isinstance(node, ast.Call):
        owners: set[str] = set()
        if isinstance(node.func, ast.Attribute):
            owners.update(_dynamic_module_object_owners(node.func.value, environment))
        for argument in (*node.args, *(keyword.value for keyword in node.keywords)):
            owners.update(_dynamic_module_object_owners(argument, environment))
        return owners
    if isinstance(node, ast.Subscript):
        if _dynamic_sys_modules_mapping(node.value, environment):
            key_known, key_value = _dynamic_ast_literal_key_value(node.slice)
            if (
                key_known
                and isinstance(key_value, str)
                and key_value in _DYNAMIC_TYPE_CHECKING_MODULES
            ):
                return {key_value}
            return set(_DYNAMIC_TYPE_CHECKING_MODULES)
        return _dynamic_module_object_owners(node.value, environment)
    if isinstance(node, ast.Lambda):
        parameters = {
            argument.arg
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                *((node.args.vararg,) if node.args.vararg else ()),
                *((node.args.kwarg,) if node.args.kwarg else ()),
            )
        }
        outer = {name: value for name, value in environment.items() if name not in parameters}
        return _dynamic_module_object_owners(node.body, outer)
    owners: set[str] = set()
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            owners.update(_dynamic_module_object_owners(child, environment))
    return owners


def _dynamic_scope_statement_nodes(statements: Sequence[ast.stmt]) -> tuple[ast.stmt, ...]:
    """Walk one lexical block while leaving nested scopes for their own summary."""
    found: list[ast.stmt] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                found.append(child)
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
            visit(child)

    for statement in statements:
        found.append(statement)
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            visit(statement)
    return tuple(found)


def _dynamic_scope_module_environment(
    scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    outer: Mapping[str, _DynamicImportBinding],
) -> tuple[dict[str, _DynamicImportBinding], tuple[ast.stmt, ...]]:
    """Resolve only source-owned typing module aliases in one lexical scope."""
    statements = _dynamic_scope_statement_nodes(scope.body)
    environment = dict(outer)
    local_names, global_names, nonlocal_names = _scope_local_bindings(scope.body)
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arguments = scope.args
        parameter_names = {
            argument.arg
            for argument in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                *((arguments.vararg,) if arguments.vararg else ()),
                *((arguments.kwarg,) if arguments.kwarg else ()),
            )
        }
        local_names.update(parameter_names)
    for name in local_names - global_names - nonlocal_names:
        environment[name] = _DYNAMIC_UNKNOWN

    for statement in statements:
        if isinstance(statement, ast.Import):
            for imported in statement.names:
                bound = imported.asname or imported.name.split(".", 1)[0]
                module = imported.name if imported.asname else imported.name.split(".", 1)[0]
                environment[bound] = _dynamic_binding_for_import(module)
        elif isinstance(statement, ast.ImportFrom):
            module = ("." * statement.level) + (statement.module or "")
            for imported in statement.names:
                if imported.name == "*":
                    continue
                bound = imported.asname or imported.name
                environment[bound] = _dynamic_binding_for_import(module, imported.name)
        elif isinstance(statement, ast.Assign):
            value: _DynamicImportBinding | None = None
            if isinstance(statement.value, ast.Name):
                value = environment.get(statement.value.id)
                if value is None:
                    value = (
                        _dynamic_builtin_dual_namespace_binding()
                        if statement.value.id == "__builtins__"
                        else _dynamic_builtin_binding(statement.value.id)
                    )
            elif (
                isinstance(statement.value, ast.Attribute)
                and statement.value.attr == "modules"
                and isinstance(statement.value.value, ast.Name)
            ):
                owner = environment.get(statement.value.value.id)
                if owner is not None and owner.kind == "module" and owner.name == "sys":
                    value = _dynamic_sys_modules_binding()
            for target in statement.targets:
                if isinstance(target, ast.Name) and value is not None:
                    environment[target.id] = value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if isinstance(statement.value, ast.Name):
                value = environment.get(statement.value.id)
                if value is None:
                    value = _dynamic_builtin_binding(statement.value.id)
                environment[statement.target.id] = value
            elif statement.value is not None:
                environment[statement.target.id] = _DYNAMIC_UNKNOWN
    return environment, statements


def _dynamic_statement_expression_roots(node: ast.stmt) -> tuple[ast.AST, ...]:
    """Return expressions evaluated by a statement, excluding nested bodies."""
    roots: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        roots.extend(node.targets)
        roots.append(node.value)
    elif isinstance(node, ast.AnnAssign):
        roots.append(node.target)
        roots.append(node.annotation)
        if node.value is not None:
            roots.append(node.value)
    elif isinstance(node, ast.AugAssign):
        roots.extend((node.target, node.value))
    elif isinstance(node, ast.Delete):
        roots.extend(node.targets)
    elif isinstance(node, ast.Expr):
        roots.append(node.value)
    elif isinstance(node, ast.If):
        roots.append(node.test)
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        roots.extend((node.target, node.iter))
    elif isinstance(node, ast.While):
        roots.append(node.test)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        roots.extend(node.decorator_list)
        roots.extend(node.args.defaults)
        roots.extend(value for value in node.args.kw_defaults if value is not None)
        roots.extend(
            node.args.args[i].annotation
            for i in range(len(node.args.args))
            if node.args.args[i].annotation is not None
        )
        roots.extend(
            argument.annotation
            for argument in (*node.args.posonlyargs, *node.args.kwonlyargs)
            if argument.annotation is not None
        )
        roots.extend(
            argument.annotation
            for argument in (node.args.vararg, node.args.kwarg)
            if argument is not None and argument.annotation is not None
        )
        if node.returns is not None:
            roots.append(node.returns)
    elif isinstance(node, ast.ClassDef):
        roots.extend((*node.decorator_list, *node.bases))
        roots.extend(keyword.value for keyword in node.keywords)
    elif isinstance(node, ast.Return) and node.value is not None:
        roots.append(node.value)
    elif isinstance(node, ast.Raise):
        roots.extend(value for value in (node.exc, node.cause) if value is not None)
    elif isinstance(node, ast.Assert):
        roots.append(node.test)
        if node.msg is not None:
            roots.append(node.msg)
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        for item in node.items:
            roots.append(item.context_expr)
            if item.optional_vars is not None:
                roots.append(item.optional_vars)
    elif isinstance(node, ast.Match):
        roots.append(node.subject)
        roots.extend(case.guard for case in node.cases if case.guard is not None)
    return tuple(roots)


def _dynamic_type_checking_module_effects(
    node: ast.stmt,
    environment: Mapping[str, _DynamicImportBinding],
) -> set[str]:
    """Find source-visible mutation or escape of a proven typing module object."""
    invalidated: set[str] = set()
    for root in _dynamic_statement_expression_roots(node):
        for child in ast.walk(root):
            if isinstance(child, ast.Attribute) and (
                child.attr == "__dict__" or isinstance(child.ctx, (ast.Store, ast.Del))
            ):
                invalidated.update(_dynamic_module_object_owners(child.value, environment))
            elif isinstance(child, ast.Subscript) and isinstance(child.ctx, (ast.Store, ast.Del)):
                invalidated.update(_dynamic_sys_modules_write_owners(child, environment))
            elif isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    invalidated.update(
                        set(_DYNAMIC_TYPE_CHECKING_MODULES)
                        if _dynamic_sys_modules_mapping(child.func.value, environment)
                        else set()
                    )
                for argument in (*child.args, *(keyword.value for keyword in child.keywords)):
                    if _dynamic_sys_modules_mapping(argument, environment):
                        invalidated.update(_DYNAMIC_TYPE_CHECKING_MODULES)
                callee: _DynamicImportBinding | None = None
                if isinstance(child.func, ast.Name):
                    callee = environment.get(child.func.id)
                    if callee is None:
                        callee = _dynamic_builtin_binding(child.func.id)
                elif isinstance(child.func, ast.Attribute) and isinstance(
                    child.func.value, ast.Name
                ):
                    base = environment.get(child.func.value.id)
                    if base is not None and base.kind == "module" and base.name == "builtins":
                        callee = _dynamic_builtin_binding(child.func.attr)
                if callee is not None and callee.name in {
                    "builtins.eval",
                    "builtins.exec",
                    "builtins.globals",
                    "builtins.locals",
                    "builtins.vars",
                }:
                    invalidated.update(
                        owner
                        for binding in environment.values()
                        if (owner := _dynamic_type_checking_module_owner(binding)) is not None
                    )
                invalidated.update(_dynamic_module_object_owners(child, environment))
            elif isinstance(child, (ast.Yield, ast.YieldFrom)) and child.value is not None:
                invalidated.update(_dynamic_module_object_owners(child.value, environment))

    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        value = node.value
        if value is not None:
            owners = _dynamic_module_object_owners(value, environment)
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if owners and (
                not isinstance(value, ast.Name)
                or any(not isinstance(target, ast.Name) for target in targets)
            ):
                invalidated.update(owners)
    elif isinstance(node, ast.Return) and node.value is not None:
        invalidated.update(_dynamic_module_object_owners(node.value, environment))
    return invalidated


def _dynamic_reflection_callee(
    node: ast.Call,
    environment: Mapping[str, _DynamicImportBinding],
) -> _DynamicImportBinding | None:
    if isinstance(node.func, ast.Name):
        binding = environment.get(node.func.id)
        return binding if binding is not None else _dynamic_builtin_binding(node.func.id)
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        base = environment.get(node.func.value.id)
        if base is not None and base.kind == "module" and base.name == "builtins":
            return _dynamic_builtin_binding(node.func.attr)
    return None


def _dynamic_type_checking_namespace_reflection(
    node: ast.stmt,
    environment: Mapping[str, _DynamicImportBinding],
) -> bool:
    """Detect source-bound builtins that can rewrite or expose namespace bindings."""
    reflective_names = {
        "builtins.eval",
        "builtins.exec",
        "builtins.globals",
        "builtins.locals",
        "builtins.vars",
    }
    for root in _dynamic_statement_expression_roots(node):
        for child in ast.walk(root):
            if isinstance(child, ast.Name) and child.id == "__builtins__":
                binding = environment.get(child.id, _dynamic_builtin_dual_namespace_binding())
                if binding.kind == "namespace" and binding.name == "builtins":
                    return True
            if isinstance(child, ast.Attribute) and child.attr == "__dict__":
                if isinstance(child.value, ast.Name):
                    binding = environment.get(child.value.id)
                    if (
                        binding is not None
                        and binding.kind == "module"
                        and binding.name == "builtins"
                    ):
                        return True
            if isinstance(child, ast.Call):
                callee = _dynamic_reflection_callee(child, environment)
                if callee is not None and callee.name in reflective_names:
                    return True
    return False


def _dynamic_deferred_scope_namespace_reflection(
    scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    outer: Mapping[str, _DynamicImportBinding],
) -> bool:
    environment, statements = _dynamic_scope_module_environment(scope, outer)
    for statement in statements:
        if _dynamic_type_checking_namespace_reflection(statement, environment):
            return True
        if isinstance(
            statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and _dynamic_deferred_scope_namespace_reflection(statement, environment):
            return True
    return False


def _dynamic_deferred_scope_module_effects(
    scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    outer: Mapping[str, _DynamicImportBinding],
) -> set[str]:
    """Summarize module-object effects throughout deferred lexical scopes."""
    environment, statements = _dynamic_scope_module_environment(scope, outer)
    invalidated: set[str] = set()
    nested: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = []
    for statement in statements:
        invalidated.update(_dynamic_type_checking_module_effects(statement, environment))
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nested.append(statement)
    for child in nested:
        invalidated.update(_dynamic_deferred_scope_module_effects(child, environment))
    return invalidated


class _DynamicImportSourceScanner:
    """Collect dynamic calls with statically proven importer provenance.

    Resolves import statements, direct and chained aliases, same-origin joins, lexical
    closures, built-in reflection, and known sequence/mapping transfers. Guarded provenance
    is retained across recognized value flows; an unsupported expression or boundary that
    could carry it fails closed. Arbitrary callables supplied by callers or returned by
    unmodeled calls remain outside the static inventory guarantee.
    """

    def __init__(
        self,
        source_path: Path,
        *,
        relative_path: str | None = None,
        source_bindings: _DynamicImportSourceBindings | None = None,
        source_context: _DynamicImportSourceContext | None = None,
        source_function_scanners: dict[str, _DynamicImportSourceScanner] | None = None,
        source_function_module_stack: list[str] | None = None,
    ) -> None:
        self.source_path = source_path
        self.relative_path = relative_path or _dynamic_source_label(source_path)
        self.entries: list[dict[str, Any]] = []
        self.sink_sites: list[_DynamicImportSite] = []
        self._module_environment: dict[str, _DynamicImportBinding] = {}
        self.source_context = source_context
        self.future_annotations = False
        self._type_checking_invalidated_modules: set[str] = set()
        if source_context is None or source_context.type_checking_effects is None:
            # A one-file scan has not established the shared singleton's
            # complete source-visible effects, so TYPE_CHECKING is not authority.
            self._type_checking_invalidated_modules.update(_DYNAMIC_TYPE_CHECKING_MODULES)
        else:
            self._type_checking_invalidated_modules.update(
                module
                for module, source_paths in source_context.type_checking_effects
                if source_paths - {self.relative_path}
            )
        self._type_checking_namespace_unknown = False
        self._module_scope_info: Mapping[str, set[str]] = {}
        self._module_possible_rebindings: set[str] = set()
        self._active_function_returns: list[list[_DynamicImportBinding]] = []
        self._module_function_summaries: dict[str, _DynamicImportFunctionSummary] = {}
        self._invalidated_function_code: set[str] = set()
        self._source_code_depth = 0
        self._source_code_opaque_effect = False
        self._active_code_builtins: _DynamicImportBinding | None = None
        self._module_time_proven_scope_ids: set[int] = set()
        self._active_module_function_stack: list[str] = []
        self._active_module_function_invocation_states: list[
            tuple[
                str,
                tuple[
                    tuple[tuple[str, _DynamicImportBinding], ...],
                    tuple[tuple[str, _DynamicImportBinding], ...],
                ],
            ]
        ] = []
        self._active_module_environment: dict[str, _DynamicImportBinding] | None = None
        self._recorded_entry_ids: set[str] = set()
        self._recorded_sink_sites: set[tuple[int, str]] = set()
        self._module_execution_active = False
        self._module_namespace_complete = True
        self._module_namespace_written_names: set[str] = set()
        self._module_initializer_call_ids: set[int] = set()
        self._pending_temporal_invocations: list[
            tuple[
                ast.AST,
                dict[str, _DynamicImportBinding],
                dict[str, int],
                frozenset[str],
                str,
            ]
        ] = []
        self._importer_binding_revisions: dict[str, int] = {}
        self._importer_binding_mutations: dict[str, int] = {}
        self._observed_importer_binding_names: set[str] = set()
        self.source_bindings = source_bindings
        self._source_function_scanners = (
            source_function_scanners if source_function_scanners is not None else {}
        )
        self._source_function_module_stack = (
            source_function_module_stack if source_function_module_stack is not None else []
        )
        self._source_instance_summary = False
        self._source_summary_fields: frozenset[str] | None = None
        self._source_summary_locals: frozenset[str] = frozenset()
        self._source_summary_stack: tuple[tuple[str, str], ...] = ()
        self._source_root_model_string_classes: set[str] = set()
        if source_bindings is not None and source_context is not None:
            source_bindings.invalidate_source_classes(source_context.source_class_effects or ())
        try:
            source_path.resolve().relative_to(SRC_ROOT.resolve())
            self.module_name: str | None = module_fqn_from_path(source_path)
        except OSError, RuntimeError, ValueError:
            self.module_name = None

    def scan_with_sites(
        self, tree: ast.Module
    ) -> tuple[list[dict[str, Any]], tuple[_DynamicImportSite, ...]]:
        """Return the existing inventory plus exact source-owned importer call nodes."""
        entries = self.scan(tree)
        return entries, tuple(self.sink_sites)

    def scan(self, tree: ast.Module) -> list[dict[str, Any]]:
        self.future_annotations = _future_annotations_enabled(tree)
        self._module_function_summaries.clear()
        self._module_time_proven_scope_ids.clear()
        self._active_module_function_stack.clear()
        self._active_module_function_invocation_states.clear()
        self._active_module_environment = None
        self._module_execution_active = False
        self._module_namespace_complete = True
        self._module_namespace_written_names.clear()
        self._module_initializer_call_ids = {
            id(statement.value)
            for statement in tree.body
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
        }
        self._pending_temporal_invocations.clear()
        self._importer_binding_revisions.clear()
        self._importer_binding_mutations.clear()
        self._observed_importer_binding_names.clear()
        locals_, _, _ = _scope_local_bindings(tree.body)
        environment = {name: self._unknown_binding(name) for name in locals_}
        self._module_environment = environment
        module_scope_info: dict[str, set[str]] = {
            "globals": set(),
            "nonlocals": set(),
            "_effectful": set(),
        }
        self._module_scope_info = module_scope_info
        pending: list[_PendingDynamicImportScope] = []
        self._module_execution_active = True
        try:
            environment = self._scan_statements(
                tree.body,
                environment,
                locals_,
                module_scope_info,
                pending,
                {},
            )
        finally:
            self._module_execution_active = False
        self._module_environment = environment
        self._raise_for_unproven_temporal_invocations(environment, pending)
        for deferred in pending:
            scope = deferred.node
            # Module names are globals resolved at call time, not closure cells.
            closure = environment
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._scan_function(scope, closure, environment)
            elif isinstance(scope, ast.ClassDef):
                self._scan_class(scope, closure, environment)
            elif isinstance(scope, ast.Lambda):
                self._scan_function(scope, closure, environment)
            elif isinstance(scope, ast.TypeAlias):
                self._scan_type_parameter_fields(scope, environment, pending)
        return self.entries

    def _invalidate_type_checking_modules(
        self,
        modules: set[str],
        environment: dict[str, _DynamicImportBinding],
    ) -> None:
        if not modules:
            return
        self._type_checking_invalidated_modules.update(modules)
        for target_environment in (environment, self._module_environment):
            for name, binding in tuple(target_environment.items()):
                if _dynamic_type_checking_module_owner(binding) in modules:
                    target_environment[name] = self._unknown_binding(name)

    def _invalidate_type_checking_namespace_bindings(
        self,
        environment: dict[str, _DynamicImportBinding],
    ) -> None:
        self._type_checking_namespace_unknown = True
        self._type_checking_invalidated_modules.update(_DYNAMIC_TYPE_CHECKING_MODULES)
        for target_environment in (environment, self._module_environment):
            for name, binding in tuple(target_environment.items()):
                if _dynamic_type_checking_kind(binding) is not None:
                    target_environment[name] = self._unknown_binding(name)

    def _type_checking_bindings(
        self, environment: Mapping[str, _DynamicImportBinding]
    ) -> dict[str, str]:
        return {
            name: kind
            for name, binding in environment.items()
            if (kind := _dynamic_type_checking_kind(binding)) is not None
        }

    def _bind_name(
        self,
        name: str,
        value: _DynamicImportBinding,
        environment: dict[str, _DynamicImportBinding],
        scope_info: Mapping[str, set[str]],
    ) -> None:
        module_target = scope_info is self._module_scope_info or name in scope_info.get(
            "globals", set()
        )
        if _dynamic_type_checking_kind(value) is not None:
            effectful = scope_info.get("_effectful", set())
            if name in effectful or (module_target and name in self._module_possible_rebindings):
                value = self._unknown_binding(name)
        if module_target:
            self._note_importer_binding_write(
                name,
                environment.get(name, self._unknown_binding(name)),
                value,
            )
        environment[name] = value

    def _note_importer_binding_write(
        self,
        name: str,
        prior: _DynamicImportBinding,
        value: _DynamicImportBinding,
    ) -> None:
        """Track module/global stores that can change guarded importer resolution."""
        prior_has_importer_identity = _is_guarded_importer_binding(prior) or bool(
            _dynamic_import_namespace_origins(prior)
        )
        value_has_importer_identity = _is_guarded_importer_binding(value) or bool(
            _dynamic_import_namespace_origins(value)
        )
        if (
            name not in _DYNAMIC_IMPORT_GUARDED_ROOTS
            and name not in self._observed_importer_binding_names
            and not prior_has_importer_identity
            and not value_has_importer_identity
        ):
            return
        if prior != value and prior_has_importer_identity:
            self._importer_binding_mutations[name] = (
                self._importer_binding_mutations.get(name, 0) + 1
            )
        self._observed_importer_binding_names.add(name)
        self._importer_binding_revisions[name] = self._importer_binding_revisions.get(name, 0) + 1

    def _register_deferred_scope_effects(
        self,
        global_writes: set[str],
        nonlocal_writes: set[str],
        environment: dict[str, _DynamicImportBinding],
        scope_info: Mapping[str, set[str]],
        closure_env: Mapping[str, _DynamicImportBinding],
    ) -> None:
        """Make any cross-scope rebinding of a proven TYPE_CHECKING value unknown."""
        self._module_possible_rebindings.update(global_writes)
        for name in global_writes:
            module_value = self._module_environment.get(name, self._unknown_binding(name))
            if _dynamic_type_checking_kind(module_value) is not None:
                unknown = self._unknown_binding(name)
                self._note_importer_binding_write(name, module_value, unknown)
                self._module_environment[name] = unknown
                if scope_info is self._module_scope_info or name in scope_info.get(
                    "globals", set()
                ):
                    environment[name] = self._unknown_binding(name)

        effectful = scope_info.get("_effectful")
        if isinstance(effectful, set):
            effectful.update(nonlocal_writes)
        nonlocal_environment = closure_env if "_class" in scope_info else environment
        for name in nonlocal_writes:
            value = nonlocal_environment.get(name, self._unknown_binding(name))
            if _dynamic_type_checking_kind(value) is not None:
                if isinstance(nonlocal_environment, dict):
                    nonlocal_environment[name] = self._unknown_binding(name)
                if "_class" not in scope_info and name in environment:
                    environment[name] = self._unknown_binding(name)

    @staticmethod
    def _unknown_binding(_name: str) -> _DynamicImportBinding:
        return _DYNAMIC_UNKNOWN

    def _reject_guarded_escape(
        self, binding: _DynamicImportBinding, node: ast.AST, boundary: str
    ) -> None:
        self._invalidate_source_function_code((binding,))
        if _is_guarded_importer_binding(binding) or _dynamic_has_source_execution(binding):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{getattr(node, 'lineno', 1)}: guarded importer value "
                f"escapes through {boundary}; value flow at this boundary is unsupported"
            )

    def _check_annotation(
        self,
        node: ast.expr,
        environment: dict[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
        boundary: str,
    ) -> None:
        """Keep deferred annotation names from acting like runtime value escapes.

        The expression is still analyzed for importer calls a later annotation resolver
        could evaluate, while guarded names are rejected only when the definition evaluates
        the annotation immediately.
        """
        binding = self._expression_binding(node, environment, pending, scope_info)
        if not self.future_annotations:
            self._reject_guarded_escape(binding, node, boundary)

    def _scan_type_parameter_fields(
        self,
        owner: ast.AST,
        environment: Mapping[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
    ) -> None:
        """Scan every expression-bearing AST field in a PEP 695 type-parameter scope."""
        owner_fields = dict(ast.iter_fields(owner))
        if "type_params" not in owner_fields:
            return
        parameters = owner_fields["type_params"]
        if not isinstance(parameters, (list, tuple)):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{getattr(owner, 'lineno', 1)}: unsupported type parameter collection"
            )
        parameter_types = tuple(
            node_type
            for node_type in (
                getattr(ast, "TypeVar", None),
                getattr(ast, "ParamSpec", None),
                getattr(ast, "TypeVarTuple", None),
            )
            if isinstance(node_type, type)
        )
        parameters = tuple(parameters)
        parameter_names: list[str] = []
        for parameter in parameters:
            if not isinstance(parameter, parameter_types):
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{getattr(owner, 'lineno', 1)}: unsupported type parameter AST carrier {type(parameter).__name__}"
                )
            name = getattr(parameter, "name", None)
            if not isinstance(name, str) or not name:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{getattr(owner, 'lineno', 1)}: unsupported type parameter name"
                )
            parameter_names.append(name)

        annotation_environment = dict(environment)
        for name in parameter_names:
            # PEP 695 names shadow same-spelled outer bindings in annotation scopes.
            annotation_environment[name] = _DYNAMIC_OTHER

        inert_ast_markers = (
            ast.expr_context,
            ast.operator,
            ast.unaryop,
            ast.boolop,
            ast.cmpop,
        )

        def expression_roots(value: object) -> list[ast.expr]:
            roots: list[ast.expr] = []
            stack = [value]
            while stack:
                current = stack.pop()
                if isinstance(current, ast.expr):
                    roots.append(current)
                    continue
                if isinstance(current, (list, tuple)):
                    stack.extend(reversed(current))
                    continue
                if not isinstance(current, ast.AST):
                    # Names, flags, and other scalar fields are syntax metadata.
                    continue
                if isinstance(current, inert_ast_markers):
                    continue
                if isinstance(current, (ast.stmt, ast.pattern, ast.mod)):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{getattr(owner, 'lineno', 1)}: unsupported executable AST carrier in type parameter"
                    )
                children = [child for _, child in ast.iter_fields(current)]
                if not children:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{getattr(owner, 'lineno', 1)}: unsupported type parameter AST carrier {type(current).__name__}"
                    )
                stack.extend(reversed(children))
            return roots

        for parameter in parameters:
            # Field discovery is intentionally generic: new expression-bearing PEP 695
            # fields flow through the same transfer domain without another spelling list.
            for _, value in ast.iter_fields(parameter):
                for expression in expression_roots(value):
                    binding = self._expression_binding(
                        expression,
                        annotation_environment,
                        pending,
                        {},
                    )
                    self._reject_guarded_escape(
                        binding,
                        expression,
                        "a type parameter bound, constraint, or default",
                    )

    def _lookup(
        self, name: str, environment: Mapping[str, _DynamicImportBinding]
    ) -> _DynamicImportBinding:
        if name in environment:
            return environment[name]
        if name == "__name__" and self.module_name is not None:
            return _dynamic_string_binding(self.module_name)
        if name == "__builtins__" and self._active_code_builtins is not None:
            return _dynamic_builtin_dual_namespace_binding()
        if self._active_code_builtins is not None:
            return _dynamic_mapping_lookup(
                self._active_code_builtins, _dynamic_string_binding(name), default=_DYNAMIC_OTHER
            )
        if name == "__import__":
            return _DynamicImportBinding("callable", "__import__", guarded=True)
        if name == "__builtins__":
            return _dynamic_builtin_dual_namespace_binding()
        if name in {
            "eval",
            "exec",
            "getattr",
            "globals",
            "locals",
            "setattr",
            "delattr",
            *_DYNAMIC_ITERABLE_CONSTRUCTORS,
            *_DYNAMIC_CAPABILITY_PREDICATES,
            "type",
            "vars",
            "int",
            "float",
            "str",
            "bytes",
            "bool",
            "dict",
            "object",
        }:
            return _dynamic_builtin_binding(name)
        return _DYNAMIC_OTHER

    def _invalidate_source_function_code(
        self,
        bindings: Iterable[_DynamicImportBinding],
    ) -> None:
        """Invalidate mutable function identities at any unsupported exposure or mutation."""
        self._invalidated_function_code.update(
            item.origin_name
            for binding in bindings
            for item in _dynamic_binding_nodes(binding)
            if item.kind in {"source_function", "source_method"} and item.origin_name is not None
        )

    def _invalidate_source_class_effects(
        self,
        bindings: Iterable[_DynamicImportBinding],
    ) -> None:
        """Invalidate summaries whenever source class identities cross a call or store."""
        if self.source_bindings is None:
            return
        origins = frozenset(
            origin for binding in bindings for origin in _dynamic_source_class_origins(binding)
        )
        if origins:
            self.source_bindings.invalidate_source_classes(origins)

    def _module_registry_lookup_result(
        self,
        mapping: _DynamicImportBinding,
        key: _DynamicImportBinding,
        result: _DynamicImportBinding,
    ) -> _DynamicImportBinding:
        """Retain exact or unresolved sys.modules selection through lookup."""
        origins = set(mapping.module_registry_origins)
        if mapping.origin_name == "sys.modules":
            origins.add("sys.modules")
        if not origins:
            return result

        candidates = _dynamic_binding_alternatives(key)
        names: tuple[str, ...] | None
        if candidates is None:
            names = None
        else:
            selected_names: set[str] = set()
            for candidate in candidates:
                key_known, key_value = _dynamic_binding_literal_key_value(candidate)
                if not key_known or not isinstance(key_value, str):
                    names = None
                    break
                selected_names.add(key_value)
            else:
                names = tuple(sorted(selected_names))

        if (
            names is not None
            and len(names) == 1
            and self.source_bindings is not None
            and names[0] in self.source_bindings.module_paths
        ):
            result = _DynamicImportBinding("module", names[0])
        return replace(
            result,
            module_registry_origins=tuple(sorted(origins)),
            module_registry_names=names,
            module_registry_complete=mapping.module_registry_complete,
        )

    def _invalidate_mutable_mapping_aliases(
        self,
        mapping: _DynamicImportBinding,
        environment: Mapping[str, _DynamicImportBinding],
        *,
        include_namespace: bool = False,
    ) -> None:
        if (
            mapping.kind != "mapping" and not (include_namespace and mapping.kind == "namespace")
        ) or mapping.immutable:
            return
        if mapping.kind == "mapping" and self.source_bindings is not None:
            self.source_bindings.record_source_mapping_effect(mapping)
        target_environments = [environment, self._module_environment]
        if self._active_module_environment is not None:
            target_environments.append(self._active_module_environment)
        seen: set[int] = set()
        for target in target_environments:
            if id(target) in seen or not isinstance(target, dict):
                continue
            seen.add(id(target))
            for name, existing in tuple(target.items()):
                if existing == mapping:
                    target[name] = self._unknown_binding(name)

    def _invalidate_unmodeled_source_mapping_inputs(
        self,
        bindings: Iterable[_DynamicImportBinding],
        environment: Mapping[str, _DynamicImportBinding],
        *,
        include_namespace: bool = False,
    ) -> None:
        """Record map effects before a lossy transfer drops nested input identity."""
        seen: set[int] = set()
        for binding in bindings:
            for nested in _dynamic_binding_nodes(binding):
                identity = id(nested)
                if identity in seen:
                    continue
                seen.add(identity)
                if nested.kind == "mapping" or (include_namespace and nested.kind == "namespace"):
                    self._invalidate_mutable_mapping_aliases(
                        nested,
                        environment,
                        include_namespace=include_namespace,
                    )

    def _update_local_mapping_slot(
        self,
        target: ast.Subscript,
        mapping: _DynamicImportBinding,
        key: _DynamicImportBinding,
        value: _DynamicImportBinding,
        environment: dict[str, _DynamicImportBinding],
        *,
        delete: bool = False,
    ) -> bool:
        """Model an exact slot update on a complete local mapping binding."""
        if (
            not isinstance(target.value, ast.Name)
            or mapping.kind != "mapping"
            or mapping.origin_name is not None
            or mapping.immutable
            or mapping.items is None
            or mapping.values is None
            or environment.get(target.value.id) is not mapping
            or len(mapping.items) != len(mapping.values)
        ):
            return False
        key_known, _ = _dynamic_binding_literal_key_value(key)
        if not key_known or any(
            not _dynamic_binding_literal_key_value(registered_key)[0]
            for registered_key in mapping.items
        ):
            return False
        matches = [
            index
            for index, registered_key in enumerate(mapping.items)
            if _dynamic_keys_equal_exact(key, registered_key)
        ]
        if len(matches) > 1:
            return False

        keys = list(mapping.items)
        values = list(mapping.values)
        if delete:
            if not matches:
                return False
            del keys[matches[0]]
            del values[matches[0]]
        elif matches:
            values[matches[0]] = value
        else:
            if len(keys) >= _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                return False
            keys.append(key)
            values.append(value)

        updated = _dynamic_mapping_binding(keys, values, guarded=mapping.guarded)
        memo: dict[int, tuple[_DynamicImportBinding, bool]] = {id(mapping): (updated, True)}

        def replace_container_reference(
            binding: _DynamicImportBinding,
        ) -> tuple[_DynamicImportBinding, bool]:
            cached = memo.get(id(binding))
            if cached is not None:
                return cached
            memo[id(binding)] = (binding, False)
            if binding.kind in {"mapping", "namespace", "object", "sequence", "iterable", "union"}:
                old_items = binding.items
                new_items = old_items
                changed = False
                if old_items is not None:
                    replaced_items = tuple(replace_container_reference(item) for item in old_items)
                    new_items = tuple(item for item, _ in replaced_items)
                    changed = any(item_changed for _, item_changed in replaced_items)
                old_values = binding.values
                new_values = old_values
                if old_values is not None and binding.kind in {"mapping", "namespace", "object"}:
                    replaced_values = tuple(
                        replace_container_reference(item) for item in old_values
                    )
                    new_values = tuple(item for item, _ in replaced_values)
                    changed = changed or any(item_changed for _, item_changed in replaced_values)
                old_element = binding.element
                new_element = old_element
                if old_element is not None and binding.kind in {"sequence", "iterable"}:
                    new_element, element_changed = replace_container_reference(old_element)
                    changed = changed or element_changed
                result = (
                    replace(binding, items=new_items, values=new_values, element=new_element)
                    if changed
                    else binding
                )
                memo[id(binding)] = (result, changed)
                return result, changed
            return binding, False

        targets: list[dict[str, _DynamicImportBinding]] = [environment, self._module_environment]
        if self._active_module_environment is not None:
            targets.append(self._active_module_environment)
        seen_targets: set[int] = set()
        for target_environment in targets:
            if id(target_environment) in seen_targets:
                continue
            seen_targets.add(id(target_environment))
            for name, existing in tuple(target_environment.items()):
                replacement, changed = replace_container_reference(existing)
                if changed:
                    target_environment[name] = replacement
        return True

    def _module_namespace_owner_resolution(
        self,
        binding: _DynamicImportBinding,
        scope_info: Mapping[str, set[str]],
    ) -> _DynamicNamespaceOwnerResolution:
        if binding.origin_name == "scope:globals":
            return _DynamicNamespaceOwnerResolution(
                "selected", binding.globals_owner or self.module_name
            )
        if binding.origin_name == "scope:locals":
            if scope_info is self._module_scope_info:
                return _DynamicNamespaceOwnerResolution("selected", self.module_name)
            return _DynamicNamespaceOwnerResolution("not_namespace")
        if binding.origin_name is not None and binding.origin_name.startswith("module_namespace:"):
            module = binding.origin_name.removeprefix("module_namespace:")
            if self.source_bindings is not None and module in self.source_bindings.module_paths:
                return _DynamicNamespaceOwnerResolution("selected", module)
            return _DynamicNamespaceOwnerResolution("nonselected", module)
        if binding.kind == "module" and binding.name is not None:
            if (
                self.source_bindings is not None
                and binding.name in self.source_bindings.module_paths
            ):
                return _DynamicNamespaceOwnerResolution("selected", binding.name)
            return _DynamicNamespaceOwnerResolution("nonselected", binding.name)
        if binding.module_registry_origins:
            names = binding.module_registry_names
            if not binding.module_registry_complete or names is None:
                return _DynamicNamespaceOwnerResolution("unresolved")
            if not names:
                return _DynamicNamespaceOwnerResolution("not_namespace")
            selected_names = {
                name
                for name in names
                if self.source_bindings is not None and name in self.source_bindings.module_paths
            }
            if len(names) == 1 and selected_names:
                return _DynamicNamespaceOwnerResolution(
                    "selected",
                    next(iter(selected_names)),
                )
            if selected_names:
                return _DynamicNamespaceOwnerResolution("unresolved")
            return _DynamicNamespaceOwnerResolution("nonselected")
        return _DynamicNamespaceOwnerResolution("not_namespace")

    def _module_namespace_owner(
        self,
        binding: _DynamicImportBinding,
        scope_info: Mapping[str, set[str]],
    ) -> str | None:
        """Return a selected owner and refuse reached unresolved registry owners."""
        resolution = self._module_namespace_owner_resolution(binding, scope_info)
        if resolution.kind == "unresolved" and (
            self._module_execution_active or self._active_module_function_stack
        ):
            raise DynamicImportCollectionError(
                f"{self.relative_path}: reached module namespace write has an unresolved "
                "sys.modules owner"
            )
        if resolution.kind in {"selected", "nonselected"}:
            return resolution.module
        return None

    def _module_namespace_write(
        self,
        module: str,
        name: str | None,
        value: _DynamicImportBinding | None,
    ) -> bool:
        """Transfer one reached namespace write or retain a bounded cross-module effect."""
        if not (self._module_execution_active or self._active_module_function_stack):
            return False
        if self.source_bindings is None:
            return False
        if module not in self.source_bindings.module_paths:
            self.source_bindings.record_module_namespace_write(module, name)
            return True
        execution_root = (
            self._source_function_module_stack[0]
            if self._source_function_module_stack
            else self.module_name
        )
        if module != execution_root or module != self.module_name:
            self.source_bindings.record_module_namespace_write(module, name)
            return True
        if name is None:
            self._module_namespace_complete = False
            return True
        target_environment = self._active_module_environment or self._module_environment
        self._module_namespace_written_names.add(name)
        self._bind_name(
            name,
            value if value is not None else self._unknown_binding(name),
            target_environment,
            self._module_scope_info,
        )
        return True

    def _record_module_namespace_mapping_update(
        self,
        module: str,
        update: _DynamicImportBinding,
        expression: ast.expr,
    ) -> None:
        """Record exact namespace keys only from proof-preserving finite updates."""
        alternatives = update.items if update.kind == "union" else (update,)
        if alternatives is None:
            self._module_namespace_write(module, None, None)
            return

        direct_dict = isinstance(expression, ast.Dict) and all(
            key is not None for key in expression.keys
        )
        direct_set = isinstance(expression, ast.Set)
        entries: list[tuple[_DynamicImportBinding, _DynamicImportBinding]] = []
        for alternative in alternatives:
            if alternative.kind == "mapping":
                if (
                    not direct_dict
                    or alternative.items is None
                    or alternative.values is None
                    or len(alternative.items) != len(alternative.values)
                ):
                    self._module_namespace_write(module, None, None)
                    return
                entries.extend(zip(alternative.items, alternative.values, strict=True))
                continue
            if alternative.kind in {"sequence", "iterable"} and alternative.items is not None:
                immutable_tuple = (
                    alternative.kind == "sequence"
                    and alternative.sequence_type == "tuple"
                    and alternative.immutable
                )
                fresh_set = direct_set and alternative.kind == "iterable"
                if not immutable_tuple and not fresh_set:
                    self._module_namespace_write(module, None, None)
                    return
                for pair in alternative.items:
                    if (
                        pair.kind != "sequence"
                        or pair.sequence_type != "tuple"
                        or not pair.immutable
                        or pair.items is None
                        or len(pair.items) != 2
                    ):
                        self._module_namespace_write(module, None, None)
                        return
                    entries.append((pair.items[0], pair.items[1]))
                continue
            self._module_namespace_write(module, None, None)
            return

        for key, value in entries:
            key_known, key_value = _dynamic_binding_literal_key_value(key)
            if not key_known:
                self._module_namespace_write(module, None, None)
                return
            if isinstance(key_value, str):
                self._module_namespace_write(module, key_value, value)

    def _expression_binding(
        self,
        node: ast.AST,
        environment: dict[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
        *,
        comprehension_outer: dict[str, _DynamicImportBinding] | None = None,
        awaited: bool = False,
    ) -> _DynamicImportBinding:
        if isinstance(node, ast.Starred):
            return self._expression_binding(
                node.value,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
        if isinstance(node, ast.Await):
            return self._expression_binding(
                node.value,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
                awaited=isinstance(node.value, ast.Call),
            )
        if isinstance(node, ast.Constant):
            literal_key_known, literal_key = _dynamic_ast_literal_key_value(node)
            if isinstance(node.value, str):
                return _dynamic_string_binding(node.value)
            if node.value is None:
                return replace(
                    _DYNAMIC_NONE,
                    literal_key=literal_key,
                    literal_key_known=literal_key_known,
                )
            if type(node.value) is int:
                return replace(
                    _DYNAMIC_BUILTIN_INT,
                    literal_key=literal_key,
                    literal_key_known=literal_key_known,
                )
            if type(node.value) is float:
                return replace(
                    _DYNAMIC_BUILTIN_FLOAT,
                    literal_key=literal_key,
                    literal_key_known=literal_key_known,
                )
            if type(node.value) is bytes:
                return replace(
                    _DYNAMIC_BUILTIN_BYTES,
                    literal_key=literal_key,
                    literal_key_known=literal_key_known,
                )
            if type(node.value) is bool:
                return _DynamicImportBinding(
                    "boolean",
                    boolean=node.value,
                    literal_key=literal_key,
                    literal_key_known=literal_key_known,
                )
            if literal_key_known:
                return replace(
                    _DYNAMIC_OTHER,
                    literal_key=literal_key,
                    literal_key_known=True,
                )
            return _DYNAMIC_OTHER
        if isinstance(node, (ast.UnaryOp, ast.BinOp)):
            literal_key_known, literal_key = _dynamic_ast_literal_key_value(node)
            if literal_key_known:
                return replace(
                    _DYNAMIC_OTHER,
                    literal_key=literal_key,
                    literal_key_known=True,
                )
        if isinstance(node, ast.UnaryOp):
            operand = self._expression_binding(
                node.operand,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            if isinstance(node.op, ast.Not):
                return _dynamic_join_with_guarded_origin(
                    (operand,),
                    _DynamicImportBinding("boolean"),
                    trusted_result=True,
                )
            return _dynamic_join_with_guarded_origin((operand,), _DYNAMIC_AMBIGUOUS)
        if isinstance(node, ast.BinOp):
            operands = (
                self._expression_binding(
                    node.left,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                ),
                self._expression_binding(
                    node.right,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                ),
            )
            left, right = operands
            if (
                isinstance(node.op, ast.BitOr)
                and left.kind in {"type", "none"}
                and right.kind
                in {
                    "type",
                    "none",
                }
            ):
                return _dynamic_join_with_guarded_origin(
                    operands,
                    _DynamicImportBinding("type", "typing.union"),
                )
            if isinstance(node.op, ast.Div) and left.kind == "pathlib_path":
                if right.kind in {"string", "builtin_str", "pathlib_path"}:
                    return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_PATH)
            if (
                isinstance(node.op, ast.Add)
                and left.kind == right.kind == "sequence"
                and left.sequence_type is not None
                and left.sequence_type == right.sequence_type
            ):
                if left.items is None or right.items is None:
                    return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_UNKNOWN)
                if len(left.items) + len(right.items) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                    return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_UNKNOWN)
                combined = _dynamic_sequence_binding(
                    (*left.items, *right.items),
                    sequence_type=left.sequence_type,
                )
                return _dynamic_join_with_guarded_origin(operands, combined)
            if isinstance(node.op, ast.Add) and left.kind == right.kind == "string":
                if left.name is not None and right.name is not None:
                    combined = left.name + right.name
                    if len(combined) <= 4096:
                        return _dynamic_string_binding(combined)
                return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_BUILTIN_STR)
            if isinstance(node.op, ast.Add) and left.kind == right.kind == "builtin_str":
                return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_BUILTIN_STR)
            if isinstance(node.op, ast.Mult) and {
                left.kind,
                right.kind,
            } == {"string", "builtin_int"}:
                text_binding = left if left.kind == "string" else right
                integer_binding = right if left.kind == "string" else left
                if text_binding.name is not None:
                    integer_known, count = _dynamic_binding_literal_key_value(integer_binding)
                    if integer_known and type(count) is int and 0 <= count <= 4096:
                        repeated = text_binding.name * count
                        if len(repeated) <= 4096:
                            return _dynamic_string_binding(repeated)
                return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_BUILTIN_STR)
            if left.kind == right.kind == "builtin_int" and isinstance(
                node.op,
                (
                    ast.Add,
                    ast.Sub,
                    ast.Mult,
                    ast.FloorDiv,
                    ast.Mod,
                    ast.Pow,
                    ast.LShift,
                    ast.RShift,
                    ast.BitOr,
                    ast.BitXor,
                    ast.BitAnd,
                ),
            ):
                return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_BUILTIN_INT)
            if left.kind == right.kind == "builtin_float" and isinstance(
                node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
            ):
                return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_BUILTIN_FLOAT)
            if (
                isinstance(node.op, ast.Mult)
                and left.kind in {"string", "builtin_str", "builtin_bytes"}
                and right.kind == "builtin_int"
            ) or (
                isinstance(node.op, ast.Mult)
                and right.kind in {"string", "builtin_str", "builtin_bytes"}
                and left.kind == "builtin_int"
            ):
                result = (
                    _DYNAMIC_BUILTIN_BYTES
                    if "builtin_bytes" in {left.kind, right.kind}
                    else _DYNAMIC_BUILTIN_STR
                )
                return _dynamic_join_with_guarded_origin(operands, result)
            if (
                any(binding.kind == "unknown" for binding in operands)
                and not any(binding.guarded or binding.kind == "ambiguous" for binding in operands)
                and all(
                    binding.kind
                    in {
                        "unknown",
                        "string",
                        "boolean",
                        "none",
                        "builtin_int",
                        "builtin_float",
                        "builtin_bytes",
                        "builtin_str",
                        "type",
                    }
                    for binding in operands
                )
            ):
                # A declaration-only scan has no call-site value for an ordinary
                # parameter. Preserve that absence as unknown; source-method
                # summaries re-evaluate the operator with the actual receiver and
                # arguments. Known importer provenance and custom object operands
                # remain ambiguous above.
                return _DYNAMIC_UNKNOWN
            return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_AMBIGUOUS)
        if isinstance(node, ast.Name):
            return self._lookup(node.id, environment)
        if isinstance(node, ast.Attribute):
            base = self._expression_binding(
                node.value,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            if node.attr == "__code__":
                return self._capture_source_code(base, node)
            if (
                self.source_bindings is not None
                and base.kind == "other"
                and base.origin_name is not None
                and base.origin_name.startswith("polisyos.")
            ):
                method = self.source_bindings.source_method_definition(base.origin_name, node.attr)
                if method is not None and method[0] == self.module_name:
                    origin = self._selected_code_origin(method[2], node)
                    return _DynamicImportBinding(
                        "source_method", origin_name=origin.identity, code_origin=origin
                    )
            if (
                self.source_bindings is not None
                and base.kind in {"object", "other"}
                and base.origin_name in self._source_root_model_string_classes
                and node.attr == "root"
                and base.origin_name not in self.source_bindings.invalidated_source_classes
            ):
                return _DYNAMIC_BUILTIN_STR
            if (
                self.source_bindings is not None
                and base.kind in {"object", "other"}
                and base.origin_name is not None
                and base.origin_name.startswith("polisyos.")
            ):
                source_class_string = self.source_bindings._source_class_constant_string_attribute(
                    base.origin_name,
                    node.attr,
                )
                if source_class_string is not None:
                    return source_class_string
            if (
                self.source_bindings is not None
                and base.kind == "module"
                and base.name is not None
                and base.name.startswith("polisyos.")
            ):
                source_export = self.source_bindings.import_binding(
                    base.name,
                    node.attr,
                    current_module=self.module_name,
                    is_package=self.source_path.name == "__init__.py",
                )
                if source_export.kind != "ambiguous":
                    return _dynamic_join_with_guarded_origin((base,), source_export)
            if (
                self.source_bindings is not None
                and base.kind == "object"
                and base.origin_name is not None
                and base.origin_name.startswith("polisyos.")
            ):
                source_property_result = self.source_bindings.source_property_return_binding(
                    base.origin_name,
                    node.attr,
                    base,
                )
                if source_property_result is not None:
                    return _dynamic_join_with_guarded_origin((base,), source_property_result)
                if self.source_bindings.source_method_definition(base.origin_name, node.attr):
                    return _DynamicImportBinding(
                        "callable",
                        f"source-method:{base.origin_name}::{node.attr}",
                        guarded=base.guarded,
                        receiver=base,
                    )
            if (
                self.source_bindings is not None
                and base.kind == "other"
                and base.origin_name is not None
                and base.origin_name.startswith("polisyos.")
                and node.attr == "model_validate"
            ):
                if self.source_bindings._source_pydantic_root_model_string(base.origin_name):
                    return _DynamicImportBinding(
                        "callable",
                        f"source-model-validate:{base.origin_name}",
                    )
                if self.source_bindings._source_pydantic_root_model_candidate(base.origin_name):
                    return _DynamicImportBinding(
                        "callable",
                        f"unproven-source-model-validate:{base.origin_name}",
                    )
                return _DYNAMIC_AMBIGUOUS
            if (
                self.source_bindings is not None
                and self.module_name is not None
                and any(
                    self.source_bindings._source_class_has_effect(
                        origin,
                        current_module=self.module_name,
                        current_environment=environment,
                        stack=(),
                    )
                    for origin in _dynamic_source_object_origins(base)
                )
            ):
                return _DYNAMIC_AMBIGUOUS
            if (
                node.attr == "TYPE_CHECKING"
                and _dynamic_type_checking_kind(base) == "typing_module"
            ):
                owner = _dynamic_type_checking_module_owner(base)
                if (
                    self._type_checking_namespace_unknown
                    or owner in self._type_checking_invalidated_modules
                ):
                    return self._unknown_binding(node.attr)
                return _dynamic_type_checking_value_binding(str(owner))
            if base.kind in {"unknown", "ambiguous", "object", "other"}:
                self._source_code_opaque_effect = True
            value = _dynamic_attribute_binding(base, node.attr)
            if self.source_bindings is not None:
                for module_name in {
                    binding.name
                    for binding in _dynamic_binding_nodes(base)
                    if binding.kind == "module" and binding.name is not None
                }:
                    value = self.source_bindings._module_namespace_effect_binding(
                        module_name,
                        node.attr,
                        value,
                    )
            return replace(value, receiver=base)
        if isinstance(node, ast.JoinedStr):
            components = tuple(
                self._expression_binding(
                    value,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
                for value in node.values
            )
            return _dynamic_join_with_guarded_origin(
                components,
                _DYNAMIC_BUILTIN_STR,
                trusted_result=True,
            )
        if isinstance(node, ast.FormattedValue):
            components = [
                self._expression_binding(
                    node.value,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
            ]
            if node.format_spec is not None:
                components.append(
                    self._expression_binding(
                        node.format_spec,
                        environment,
                        pending,
                        scope_info,
                        comprehension_outer=comprehension_outer,
                    )
                )
            return _dynamic_join_with_guarded_origin(
                components,
                _DYNAMIC_BUILTIN_STR,
                trusted_result=True,
            )
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            items: list[_DynamicImportBinding] = []
            shape_known = True
            guarded = False
            for element in node.elts:
                if isinstance(element, ast.Starred):
                    spread = self._expression_binding(
                        element.value,
                        environment,
                        pending,
                        scope_info,
                        comprehension_outer=comprehension_outer,
                    )
                    if spread.kind in {"mapping", "namespace"}:
                        guarded = (
                            guarded
                            or (spread.items is None and spread.guarded)
                            or any(
                                item.guarded or item.kind == "ambiguous"
                                for item in spread.items or ()
                            )
                        )
                        if spread.items is not None:
                            items.extend(spread.items)
                        else:
                            shape_known = False
                    elif spread.kind in {"sequence", "iterable"}:
                        guarded = guarded or spread.guarded or spread.kind == "ambiguous"
                        if spread.items is not None:
                            items.extend(spread.items)
                        else:
                            shape_known = False
                    elif spread.kind == "string" and spread.name is not None:
                        items.extend(
                            _dynamic_string_binding(character) for character in spread.name
                        )
                    else:
                        guarded = guarded or spread.guarded or spread.kind == "ambiguous"
                        shape_known = False
                    continue
                item = self._expression_binding(
                    element,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
                items.append(item)
                guarded = guarded or item.guarded or item.kind == "ambiguous"
            kind: Literal["sequence", "iterable"] = (
                "iterable" if isinstance(node, ast.Set) else "sequence"
            )
            component_names = (
                tuple(
                    element.id if isinstance(element, ast.Name) else None for element in node.elts
                )
                if isinstance(node, ast.Tuple)
                else None
            )
            sequence = _dynamic_sequence_binding(
                items if shape_known else None,
                kind=kind,
                guarded=guarded,
                component_names=component_names,
                sequence_type=(
                    "tuple"
                    if isinstance(node, ast.Tuple)
                    else "list"
                    if isinstance(node, ast.List)
                    else None
                ),
            )
            if isinstance(node, ast.Tuple) and shape_known:
                literal_items: list[object] = []
                for item in items:
                    literal_known, literal_value = _dynamic_binding_literal_key_value(item)
                    if not literal_known:
                        break
                    literal_items.append(literal_value)
                else:
                    literal_key = tuple(literal_items)
                    if _dynamic_value_is_safe_hashable_literal(literal_key):
                        sequence = replace(
                            sequence,
                            literal_key=literal_key,
                            literal_key_known=True,
                        )
            return sequence
        if isinstance(node, ast.Dict):
            keys: list[_DynamicImportBinding] = []
            values: list[_DynamicImportBinding] = []
            shape_known = True
            guarded = False
            for key_node, value_node in zip(node.keys, node.values, strict=True):
                value = self._expression_binding(
                    value_node,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
                if key_node is None:
                    guarded = guarded or value.guarded or value.kind == "ambiguous"
                    if (
                        value.kind == "mapping"
                        and value.items is not None
                        and value.values is not None
                    ):
                        keys.extend(value.items)
                        values.extend(value.values)
                    else:
                        shape_known = False
                    continue
                key = self._expression_binding(
                    key_node,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
                literal_key_known, literal_key = _dynamic_ast_literal_key_value(key_node)
                if literal_key_known:
                    key = replace(
                        key,
                        literal_key=literal_key,
                        literal_key_known=True,
                    )
                keys.append(key)
                values.append(value)
                guarded = guarded or key.guarded or key.kind == "ambiguous"
                guarded = guarded or value.guarded or value.kind == "ambiguous"
            mapping = _dynamic_mapping_binding(
                keys if shape_known else None,
                values if shape_known else None,
                guarded=guarded,
            )
            if (
                mapping.items is not None
                and mapping.values is not None
                and all(_dynamic_binding_literal_key_value(key)[0] for key in mapping.items)
            ):
                return _dynamic_normalize_literal_mapping_binding(mapping)
            return mapping
        if isinstance(node, ast.Call):
            callee = self._expression_binding(
                node.func,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            if _is_unresolved_importer_binding(callee):
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{node.lineno}: dynamic importer binding is "
                    "ambiguous or unresolved through a call target"
                )
            argument_bindings = [
                self._expression_binding(
                    argument,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
                for argument in node.args
            ]
            argument_bindings.extend(
                self._expression_binding(
                    keyword.value,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
                for keyword in node.keywords
            )
            call_values = list(argument_bindings)
            if isinstance(node.func, ast.Attribute) and callee.receiver is not None:
                call_values.append(callee.receiver)
            if (
                callee.kind == "other"
                and isinstance(node.func, ast.Name)
                and node.func.id == "len"
                and "len" not in environment
                and len(node.args) == 1
                and not node.keywords
                and not isinstance(node.args[0], ast.Starred)
                and argument_bindings[0].kind in {"mapping", "sequence"}
            ):
                return _DYNAMIC_BUILTIN_INT
            source_method_call = (
                callee.kind == "callable"
                and callee.name is not None
                and callee.name.startswith("source-method:")
            )
            if not source_method_call and not (
                callee.kind == "callable" and callee.name == "types.FunctionType"
            ):
                self._invalidate_source_class_effects(call_values)
            self._record_call(node, callee, argument_bindings)
            if callee.kind == "callable" and callee.name == "types.FunctionType":
                return self._construct_source_function(node, argument_bindings)
            source_function_result = self._source_function_call(
                node,
                callee,
                argument_bindings,
                environment,
                scope_info,
                awaited=awaited,
            )
            if source_function_result is not None:
                return source_function_result
            if (
                callee.kind == "callable"
                and callee.name == "mapping.update"
                and self._apply_source_lazy_export_map_update(
                    node,
                    callee,
                    argument_bindings,
                    environment,
                    scope_info,
                )
            ):
                return _DYNAMIC_NONE
            if callee.kind == "callable" and callee.name in {
                "mapping.clear",
                "mapping.pop",
                "mapping.popitem",
                "mapping.setdefault",
                "mapping.update",
            }:
                receiver = callee.receiver
                receiver_state_is_modeled = receiver is not None and (
                    receiver.origin_name in {"scope:globals", "scope:locals"}
                    or self._module_namespace_owner(receiver, scope_info) is not None
                )
                if not receiver_state_is_modeled:
                    self._invalidate_unmodeled_source_mapping_inputs(call_values, environment)
            if callee.kind in {"ambiguous", "other", "unknown"}:
                read_only_map_call = (
                    self.source_bindings is not None
                    and self.module_name is not None
                    and self.source_bindings._lazy_dir_call_contract(
                        node,
                        environment,
                        self.module_name,
                        (),
                        callee=callee,
                    )
                    is not None
                )
                opaque_values = list(argument_bindings)
                if isinstance(node.func, ast.Attribute):
                    receiver = callee.receiver
                    if receiver is None:
                        receiver = self._expression_binding(
                            node.func.value,
                            environment,
                            pending,
                            scope_info,
                            comprehension_outer=comprehension_outer,
                        )
                    opaque_values.append(receiver)
                if not read_only_map_call:
                    self._invalidate_unmodeled_source_mapping_inputs(opaque_values, environment)
            if callee.kind == "callable" and callee.name == _DYNAMIC_LAZY_EXPORT_RESOLVER_FQN:
                if self.source_bindings is None or self.module_name is None:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: lazy export resolver has no "
                        "selected source owner"
                    )
                contract = self.source_bindings._lazy_export_call_contract(
                    node,
                    environment,
                    self.module_name,
                    (),
                    callee=callee,
                )
                if contract is None:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: lazy export resolver call is not "
                        "bound to its source-owned export map"
                    )
                name_binding, _ = contract
                result = (
                    self.source_bindings._resolve_lazy_export_call(
                        node,
                        environment,
                        self.module_name,
                        (),
                        callee=callee,
                    )
                    if name_binding.kind == "string"
                    else _DYNAMIC_AMBIGUOUS
                )
                if self._module_execution_active or self._active_module_function_stack:
                    self._module_namespace_write(
                        self.module_name,
                        name_binding.name if name_binding.kind == "string" else None,
                        result if name_binding.kind == "string" else None,
                    )
                return result
            if callee.kind == "callable" and callee.name in {
                "builtins.setattr",
                "builtins.delattr",
            }:
                if argument_bindings:
                    function_targets = tuple(
                        item
                        for item in _dynamic_binding_nodes(argument_bindings[0])
                        if item.kind
                        in {
                            "source_function",
                            "source_method",
                            "reconstructed_function",
                            "source_closure",
                        }
                    )
                    if function_targets:
                        if _dynamic_has_source_execution(argument_bindings[0]):
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{node.lineno}: reconstructed callable mutation is unsupported"
                            )
                        self._invalidate_source_function_code(function_targets)
                        return _DYNAMIC_NONE
                    owner = self._module_namespace_owner(argument_bindings[0], scope_info)
                    if owner is None:
                        self._source_code_opaque_effect = True
                    if owner is not None:
                        key = (
                            argument_bindings[1] if len(argument_bindings) > 1 else _DYNAMIC_UNKNOWN
                        )
                        key_known, key_value = _dynamic_binding_literal_key_value(key)
                        value = (
                            argument_bindings[2]
                            if callee.name == "builtins.setattr" and len(argument_bindings) > 2
                            else None
                        )
                        self._module_namespace_write(
                            owner,
                            key_value if key_known and isinstance(key_value, str) else None,
                            value,
                        )
                        return _DYNAMIC_NONE
            if callee.kind == "callable" and callee.name in {
                "mapping.clear",
                "mapping.popitem",
                "mapping.update",
            }:
                receiver = callee.receiver
                owner = (
                    self._module_namespace_owner(receiver, scope_info)
                    if receiver is not None
                    else None
                )
                if owner is not None:
                    if callee.name != "mapping.update":
                        self._module_namespace_write(owner, None, None)
                        return _DYNAMIC_NONE
                    updates: list[tuple[str, _DynamicImportBinding]] = []
                    valid = len(node.args) <= 1
                    if node.args:
                        mapping = argument_bindings[0]
                        if (
                            mapping.kind == "mapping"
                            and mapping.items is not None
                            and mapping.values is not None
                            and len(mapping.items) == len(mapping.values)
                        ):
                            for key_binding, item_binding in zip(
                                mapping.items, mapping.values, strict=True
                            ):
                                key_known, key_value = _dynamic_binding_literal_key_value(
                                    key_binding
                                )
                                if not key_known or not isinstance(key_value, str):
                                    valid = False
                                    break
                                updates.append((key_value, item_binding))
                        else:
                            valid = False
                    for index, keyword in enumerate(node.keywords):
                        keyword_binding = argument_bindings[len(node.args) + index]
                        if keyword.arg is None:
                            mapping = keyword_binding
                            if (
                                mapping.kind != "mapping"
                                or mapping.items is None
                                or mapping.values is None
                                or len(mapping.items) != len(mapping.values)
                            ):
                                valid = False
                                break
                            for key_binding, item_binding in zip(
                                mapping.items, mapping.values, strict=True
                            ):
                                key_known, key_value = _dynamic_binding_literal_key_value(
                                    key_binding
                                )
                                if not key_known or not isinstance(key_value, str):
                                    valid = False
                                    break
                                updates.append((key_value, item_binding))
                        else:
                            updates.append((keyword.arg, keyword_binding))
                    if valid:
                        for key, item_binding in updates:
                            self._module_namespace_write(owner, key, item_binding)
                    else:
                        self._module_namespace_write(owner, None, None)
                    return _DYNAMIC_NONE
            if callee.kind in {"other", "unknown"}:
                self._remember_unmodeled_temporal_invocation(
                    node,
                    environment,
                    scope_info,
                    "unmodeled call",
                )
                for argument_binding in argument_bindings:
                    owner = self._module_namespace_owner(argument_binding, scope_info)
                    if owner is not None:
                        self._module_namespace_write(owner, None, None)
            elif callee.kind == "callable" and callee.name == "builtins.vars":
                for argument_binding in argument_bindings:
                    if argument_binding.module_registry_origins:
                        self._module_namespace_owner(argument_binding, scope_info)
            if (
                callee.kind == "other"
                and callee.origin_name is not None
                and callee.origin_name.startswith("polisyos.")
                and self.source_bindings is not None
            ):
                source_module = callee.origin_name.rpartition(".")[0]
                source_environment = self.source_bindings._module_environment(
                    source_module,
                    (),
                )
                if source_environment is not None:
                    if self.source_bindings._source_class_has_effect(
                        callee.origin_name,
                        current_module=source_module,
                        current_environment=source_environment,
                        stack=(),
                    ):
                        return self.source_bindings._deferred_source_class_instance_binding(
                            node,
                            callee.origin_name,
                            source_environment,
                            source_module,
                            (),
                            argument_bindings=argument_bindings,
                        )
                    guarded_input = any(
                        binding.guarded or binding.kind == "ambiguous"
                        for binding in argument_bindings
                    )
                    guarded_default = False
                    if not guarded_input:
                        defaults = self.source_bindings._source_class_field_defaults(
                            callee.origin_name,
                            current_module=source_module,
                            current_environment=source_environment,
                            stack=(),
                        )
                        guarded_default = defaults is not None and any(
                            binding.guarded for binding in defaults.values()
                        )
                    if guarded_input or guarded_default:
                        keyword_values = {
                            keyword.arg: argument_bindings[len(node.args) + index]
                            for index, keyword in enumerate(node.keywords)
                            if keyword.arg is not None
                        }
                        constructed = self.source_bindings._source_class_instance_binding(
                            node,
                            callee.origin_name,
                            source_environment,
                            source_module,
                            (),
                            argument_values=keyword_values,
                            argument_bindings=argument_bindings,
                        )
                        if constructed.kind == "object":
                            return constructed
                        self._reject_guarded_escape(
                            _DYNAMIC_AMBIGUOUS,
                            node,
                            "a call argument",
                        )
                    if (
                        self.source_bindings._source_class_definition(
                            callee.origin_name,
                            current_module=source_module,
                            current_environment=source_environment,
                            stack=(),
                        )
                        is not None
                    ):
                        guarded_constructor_input = any(
                            binding.guarded or binding.kind == "ambiguous"
                            for binding in argument_bindings
                        )
                        source_class_symbol = callee.origin_name.rpartition(".")[2]
                        is_source_constructor = isinstance(node.func, ast.Name) or (
                            isinstance(node.func, ast.Attribute)
                            and node.func.attr == source_class_symbol
                        )
                        if (
                            is_source_constructor
                            and not guarded_constructor_input
                            and all(keyword.arg is not None for keyword in node.keywords)
                            and len(argument_bindings) == len(node.args) + len(node.keywords)
                        ):
                            return _DynamicImportBinding(
                                "object",
                                callee.origin_name,
                                origin_name=callee.origin_name,
                                source_arguments=tuple(argument_bindings),
                                source_keyword_names=(
                                    *((None,) * len(node.args)),
                                    *(keyword.arg for keyword in node.keywords),
                                ),
                            )
                        return _DynamicImportBinding(
                            "object",
                            callee.origin_name,
                            guarded=guarded_constructor_input,
                            origin_name=callee.origin_name,
                        )
            if source_method_call and callee.name is not None:
                receiver = callee.receiver
                method_ref = callee.name.removeprefix("source-method:")
                source_name, separator, method_name = method_ref.rpartition("::")
                if receiver is None or not separator or self.source_bindings is None:
                    return _DYNAMIC_AMBIGUOUS
                if any(binding.kind in {"unknown", "ambiguous"} for binding in argument_bindings):
                    return _DYNAMIC_AMBIGUOUS
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "a source method argument")
                transfer = self.source_bindings.source_method_return_binding(
                    source_name,
                    method_name,
                    receiver=receiver,
                    call_node=node,
                    argument_bindings=argument_bindings,
                    required_fields=(
                        self._source_summary_fields
                        if (
                            self._source_instance_summary
                            and self._source_summary_fields is not None
                            and self._source_summary_stack
                            and receiver.origin_name == self._source_summary_stack[-1][0]
                        )
                        else None
                    ),
                    summary_stack=self._source_summary_stack,
                )
                if transfer is None:
                    return _DYNAMIC_AMBIGUOUS
                if isinstance(transfer, tuple):
                    result, updated_receiver = transfer
                else:
                    result, updated_receiver = transfer, receiver
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    environment[node.func.value.id] = updated_receiver
                resolved = _dynamic_join_with_guarded_origin((receiver, *argument_bindings), result)
                if not self._source_instance_summary:
                    self._invalidate_source_class_effects((*argument_bindings, receiver))
                return resolved
            if (
                callee.kind == "callable"
                and callee.name is not None
                and callee.name.startswith("unproven-source-model-validate:")
            ):
                source_name = callee.name.removeprefix("unproven-source-model-validate:")
                return _dynamic_unresolved_importer_binding(
                    (f"unproven-root-value:{source_name}",),
                    name=source_name,
                )
            if (
                callee.kind == "callable"
                and callee.name is not None
                and callee.name.startswith("source-model-validate:")
                and self.source_bindings is not None
            ):
                source_name = callee.name.removeprefix("source-model-validate:")
                if (
                    len(node.args) != 1
                    or node.keywords
                    or isinstance(node.args[0], ast.Starred)
                    or len(argument_bindings) != 1
                ):
                    return _DYNAMIC_AMBIGUOUS
                instance = self.source_bindings._source_pydantic_root_model_instance(source_name)
                return instance if instance is not None else _DYNAMIC_AMBIGUOUS
            if (
                callee.kind == "callable"
                and callee.name == "builtins.str.split"
                and callee.receiver is not None
            ):
                if (
                    callee.receiver.kind not in {"string", "builtin_str"}
                    or callee.receiver.guarded
                    or callee.receiver.kind == "ambiguous"
                    or len(node.args) > 2
                    or any(isinstance(argument, ast.Starred) for argument in node.args)
                    or any(keyword.arg is None for keyword in node.keywords)
                ):
                    return _DYNAMIC_AMBIGUOUS
                keyword_names = [keyword.arg for keyword in node.keywords]
                if len(keyword_names) != len(set(keyword_names)) or any(
                    name not in {"sep", "maxsplit"} for name in keyword_names
                ):
                    return _DYNAMIC_AMBIGUOUS
                positional = argument_bindings[: len(node.args)]
                keyword_values = argument_bindings[len(node.args) :]
                if len(positional) != len(node.args) or len(keyword_values) != len(node.keywords):
                    return _DYNAMIC_AMBIGUOUS
                supplied: dict[str, _DynamicImportBinding] = {}
                if positional:
                    supplied["sep"] = positional[0]
                if len(positional) > 1:
                    supplied["maxsplit"] = positional[1]
                for keyword, value in zip(node.keywords, keyword_values, strict=True):
                    if keyword.arg in supplied:
                        return _DYNAMIC_AMBIGUOUS
                    supplied[str(keyword.arg)] = value
                separator = supplied.get("sep")
                maxsplit = supplied.get("maxsplit")
                if separator is not None and separator.kind not in {
                    "string",
                    "builtin_str",
                    "none",
                }:
                    return _DYNAMIC_AMBIGUOUS
                if maxsplit is not None and maxsplit.kind != "builtin_int":
                    return _DYNAMIC_AMBIGUOUS
                if any(value.guarded or value.kind == "ambiguous" for value in supplied.values()):
                    return _DYNAMIC_AMBIGUOUS
                return _DynamicImportBinding(
                    "sequence",
                    "builtins.str.split",
                    element=_DYNAMIC_BUILTIN_STR,
                )
            if callee.kind == "callable" and callee.name == "pathlib.Path":
                if any(keyword.arg is None for keyword in node.keywords):
                    return _DYNAMIC_AMBIGUOUS
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "a pathlib.Path argument")
                if any(
                    binding.kind not in {"pathlib_path", "string", "builtin_str"}
                    for binding in argument_bindings
                ):
                    return _DYNAMIC_AMBIGUOUS
                return _DYNAMIC_PATH
            if callee.kind == "callable" and callee.name == "tempfile.mkdtemp":
                if any(keyword.arg is None for keyword in node.keywords):
                    return _DYNAMIC_AMBIGUOUS
                allowed_keywords = {"suffix", "prefix", "dir"}
                if any(keyword.arg not in allowed_keywords for keyword in node.keywords):
                    return _DYNAMIC_AMBIGUOUS
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "a tempfile.mkdtemp argument")
                if any(
                    binding.kind not in {"pathlib_path", "string", "builtin_str"}
                    for binding in argument_bindings
                ):
                    return _DYNAMIC_AMBIGUOUS
                return _DYNAMIC_BUILTIN_STR
            if callee.kind == "callable" and callee.name == "argparse.ArgumentParser":
                if any(keyword.arg is None for keyword in node.keywords):
                    return _DYNAMIC_AMBIGUOUS
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "an ArgumentParser argument")
                return _DynamicImportBinding(
                    "argument_parser",
                    "argparse.ArgumentParser",
                    origin_name=f"argparse:{self.relative_path}:{node.lineno}",
                    items=(),
                    values=(),
                )
            if (
                callee.kind == "callable"
                and callee.name == "argparse.ArgumentParser.add_argument"
                and callee.receiver is not None
            ):
                parser = callee.receiver
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "an argparse argument definition")
                keyword_bindings = {
                    keyword.arg: argument_bindings[len(node.args) + index]
                    for index, keyword in enumerate(node.keywords)
                    if keyword.arg is not None
                }
                option_names = [
                    binding.name
                    for binding in argument_bindings[: len(node.args)]
                    if binding.kind == "string" and binding.name is not None
                ]
                if len(option_names) != len(node.args) or not option_names:
                    return replace(parser, guarded=True)
                dest_binding = keyword_bindings.get("dest")
                if dest_binding is not None:
                    if dest_binding.kind != "string" or dest_binding.name is None:
                        return replace(parser, guarded=True)
                    destination = dest_binding.name
                else:
                    option = next(
                        (name for name in option_names if name.startswith("--")),
                        option_names[0],
                    )
                    destination = option.lstrip("-").replace("-", "_")
                converter = keyword_bindings.get("type")
                action = keyword_bindings.get("action")
                default = keyword_bindings.get("default")
                if action is not None:
                    if action.kind != "string" or action.name is None:
                        field_binding = _DYNAMIC_AMBIGUOUS
                    elif action.name in {"store_true", "store_false"}:
                        field_binding = _DynamicImportBinding("boolean")
                    elif action.name == "count":
                        field_binding = _DYNAMIC_BUILTIN_INT
                    elif action.name != "store":
                        field_binding = _DYNAMIC_AMBIGUOUS
                    elif converter is not None:
                        field_binding = {
                            "pathlib.Path": _DYNAMIC_PATH,
                            "builtins.int": _DYNAMIC_BUILTIN_INT,
                            "builtins.float": _DYNAMIC_BUILTIN_FLOAT,
                            "builtins.str": _DYNAMIC_BUILTIN_STR,
                            "builtins.bytes": _DYNAMIC_BUILTIN_BYTES,
                        }.get(converter.name or "", _DYNAMIC_AMBIGUOUS)
                    elif default is not None:
                        field_binding = default
                    else:
                        field_binding = _DYNAMIC_BUILTIN_STR
                elif converter is not None:
                    field_binding = {
                        "pathlib.Path": _DYNAMIC_PATH,
                        "builtins.int": _DYNAMIC_BUILTIN_INT,
                        "builtins.float": _DYNAMIC_BUILTIN_FLOAT,
                        "builtins.str": _DYNAMIC_BUILTIN_STR,
                        "builtins.bytes": _DYNAMIC_BUILTIN_BYTES,
                    }.get(converter.name or "", _DYNAMIC_AMBIGUOUS)
                elif default is not None:
                    field_binding = default
                else:
                    field_binding = _DYNAMIC_BUILTIN_STR
                fields = {
                    key.name: value
                    for key, value in zip(parser.items or (), parser.values or (), strict=True)
                    if key.kind == "string" and key.name is not None
                }
                fields[destination] = (
                    _join_dynamic_bindings((fields[destination], field_binding))
                    if destination in fields
                    else field_binding
                )
                updated_parser = replace(
                    parser,
                    items=tuple(_dynamic_string_binding(name) for name in sorted(fields)),
                    values=tuple(fields[name] for name in sorted(fields)),
                )
                if parser.origin_name is not None:
                    for name, value in tuple(environment.items()):
                        if (
                            value.kind == "argument_parser"
                            and value.origin_name == parser.origin_name
                        ):
                            environment[name] = updated_parser
                return _DYNAMIC_OTHER
            if (
                callee.kind == "callable"
                and callee.name == "argparse.ArgumentParser.parse_args"
                and callee.receiver is not None
            ):
                parser = callee.receiver
                if node.args or node.keywords:
                    return _DYNAMIC_AMBIGUOUS
                return _DynamicImportBinding(
                    "object",
                    "argparse.Namespace",
                    guarded=parser.guarded,
                    items=parser.items,
                    values=parser.values,
                )
            if callee.kind in {"callable", "type"} and callee.name in {
                "builtins.int",
                "builtins.float",
                "builtins.str",
                "builtins.bytes",
                "builtins.bool",
            }:
                if len(argument_bindings) != 1 or node.keywords:
                    return _DYNAMIC_AMBIGUOUS
                argument = argument_bindings[0]
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "a builtin conversion argument")
                result = {
                    "builtins.int": _DYNAMIC_BUILTIN_INT,
                    "builtins.float": _DYNAMIC_BUILTIN_FLOAT,
                    "builtins.str": _DYNAMIC_BUILTIN_STR,
                    "builtins.bytes": _DYNAMIC_BUILTIN_BYTES,
                    "builtins.bool": _DynamicImportBinding("boolean"),
                }[callee.name]
                if argument.kind not in {
                    "string",
                    "builtin_str",
                    "builtin_int",
                    "builtin_float",
                    "builtin_bytes",
                    "pathlib_path",
                    "boolean",
                    "other",
                }:
                    return _DYNAMIC_AMBIGUOUS
                return _dynamic_join_with_guarded_origin((argument,), result)
            if (
                callee.kind == "callable"
                and callee.name is not None
                and callee.name.startswith("pathlib.Path.")
            ):
                method = callee.name.removeprefix("pathlib.Path.")
                expected = _DYNAMIC_PATH_METHOD_ARGUMENTS.get(method)
                if (
                    expected is None
                    or callee.receiver is None
                    or len(node.args) != len(expected)
                    or any(keyword.arg is None for keyword in node.keywords)
                ):
                    return _DYNAMIC_AMBIGUOUS
                allowed_keywords = _DYNAMIC_PATH_METHOD_KEYWORDS.get(method, {})
                keyword_bindings = {
                    keyword.arg: argument_bindings[len(node.args) + index]
                    for index, keyword in enumerate(node.keywords)
                    if keyword.arg is not None
                }
                if any(keyword not in allowed_keywords for keyword in keyword_bindings):
                    return _DYNAMIC_AMBIGUOUS
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "a pathlib.Path method argument")
                if any(
                    binding.kind not in allowed
                    for binding, allowed in zip(
                        argument_bindings[: len(node.args)], expected, strict=True
                    )
                ) or any(
                    binding.kind not in allowed_keywords[keyword]
                    for keyword, binding in keyword_bindings.items()
                ):
                    return _DYNAMIC_AMBIGUOUS
                return _dynamic_join_with_guarded_origin(
                    (callee.receiver, *argument_bindings),
                    _DYNAMIC_PATH_METHOD_RESULTS[method],
                )
            if callee.kind == "callable" and callee.name == "types.MappingProxyType":
                if len(argument_bindings) != 1 or node.keywords:
                    if any(_is_guarded_importer_binding(binding) for binding in argument_bindings):
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: MappingProxyType() receives "
                            "an unsupported importer-bearing mapping"
                        )
                    return _DYNAMIC_UNKNOWN
                mapping = argument_bindings[0]
                if mapping.kind != "mapping":
                    return _DYNAMIC_AMBIGUOUS
                if not isinstance(node.args[0], ast.Dict) and not mapping.immutable:
                    return _DYNAMIC_AMBIGUOUS if mapping.guarded else _DYNAMIC_UNKNOWN
                return _dynamic_immutable_literal_mapping_binding(mapping)
            if callee.kind == "callable" and callee.name == "builtins.getattr":
                if len(argument_bindings) < 2:
                    return _DYNAMIC_AMBIGUOUS
                module_binding = argument_bindings[0]
                if module_binding.kind in {"unknown", "ambiguous", "object", "other"}:
                    self._source_code_opaque_effect = True
                attribute_binding = argument_bindings[1]
                if attribute_binding.kind == "string" and attribute_binding.name is not None:
                    reflected = _dynamic_attribute_binding(module_binding, attribute_binding.name)
                    if self.source_bindings is not None:
                        for module_name in {
                            binding.name
                            for binding in _dynamic_binding_nodes(module_binding)
                            if binding.kind == "module" and binding.name is not None
                        }:
                            reflected = self.source_bindings._module_namespace_effect_binding(
                                module_name,
                                attribute_binding.name,
                                reflected,
                            )
                else:
                    candidate_origins = (
                        set(_dynamic_import_namespace_origins(module_binding))
                        | set(_dynamic_importer_origins(module_binding))
                        | set(_dynamic_unresolved_importer_origins(module_binding))
                    )
                    temporal_origins = _dynamic_temporal_callable_origins(module_binding)
                    if candidate_origins:
                        reflected = _dynamic_unresolved_importer_binding(tuple(candidate_origins))
                    elif temporal_origins:
                        reflected = replace(
                            _DYNAMIC_AMBIGUOUS,
                            temporal_callable_origins=tuple(sorted(temporal_origins)),
                        )
                    else:
                        reflected = _DYNAMIC_OTHER
                if len(argument_bindings) > 2 and not reflected.guarded:
                    reflected = _join_dynamic_bindings((reflected, argument_bindings[2]))
                reflected = _dynamic_join_with_guarded_origin(
                    argument_bindings[:2],
                    reflected,
                    trusted_result=(
                        attribute_binding.kind == "string"
                        and attribute_binding.name is not None
                        and not attribute_binding.guarded
                    ),
                )
                if _is_unresolved_importer_binding(reflected):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: computed reflection has "
                        "unresolved importer provenance"
                    )
                return reflected
            if callee.kind == "callable" and callee.name in {
                "builtins.globals",
                "builtins.locals",
            }:
                if argument_bindings:
                    return _DYNAMIC_AMBIGUOUS
                if callee.name == "builtins.globals":
                    return replace(
                        _dynamic_scope_mapping(
                            self._active_module_environment or self._module_environment,
                            scope_name="globals",
                        ),
                        globals_owner=self.module_name,
                    )
                return _dynamic_scope_mapping(environment, scope_name="locals")
            if callee.kind == "callable" and callee.name in {
                f"builtins.{name}" for name in _DYNAMIC_ITERABLE_CONSTRUCTORS
            }:
                constructor = callee.name.removeprefix("builtins.")
                if len(argument_bindings) > 1 or node.keywords:
                    if any(_is_guarded_importer_binding(binding) for binding in argument_bindings):
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: {constructor}() receives an "
                            "unsupported importer-bearing argument shape"
                        )
                    return _DYNAMIC_UNKNOWN
                if not argument_bindings:
                    if constructor == "sorted":
                        return _DYNAMIC_UNKNOWN
                    return _dynamic_sequence_binding(
                        (),
                        kind="iterable" if constructor in {"set", "frozenset"} else "sequence",
                        sequence_type=(
                            constructor
                            if constructor in {"list", "tuple"}
                            else "list"
                            if constructor == "sorted"
                            else None
                        ),
                    )
                iterable = argument_bindings[0]
                if iterable.kind in {"mapping", "namespace"}:
                    # Iterating a mapping yields keys, not its importer-bearing values.
                    items = iterable.items
                elif iterable.kind in {"sequence", "iterable"}:
                    items = iterable.items
                elif iterable.kind == "string" and iterable.name is not None:
                    items = tuple(_dynamic_string_binding(character) for character in iterable.name)
                else:
                    items = None
                if items is not None:
                    result = _dynamic_sequence_binding(
                        items,
                        kind="iterable" if constructor in {"set", "frozenset"} else "sequence",
                        sequence_type=(
                            constructor
                            if constructor in {"list", "tuple"}
                            else "list"
                            if constructor == "sorted"
                            else None
                        ),
                    )
                    return _dynamic_join_with_guarded_origin(
                        (iterable,),
                        result,
                        trusted_result=iterable.kind in {"mapping", "namespace"},
                    )
                if _is_guarded_importer_binding(iterable):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: {constructor}() receives an "
                        "unsupported importer-bearing iterable"
                    )
                return _DYNAMIC_UNKNOWN
            if callee.kind == "callable" and callee.name in {
                f"builtins.{name}" for name in _DYNAMIC_CAPABILITY_PREDICATES
            }:
                return _DynamicImportBinding("boolean")
            if callee.kind == "type" and callee.name == "builtins.type":
                if len(argument_bindings) > 1 or node.keywords:
                    if any(_is_guarded_importer_binding(binding) for binding in argument_bindings):
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: type() receives an "
                            "unsupported importer-bearing argument shape"
                        )
                return _DYNAMIC_OTHER
            if callee.kind == "callable" and callee.name == "builtins.vars":
                if not node.args:
                    return _dynamic_scope_mapping(environment, scope_name="locals")
                namespace = argument_bindings[0]
                if namespace.module_registry_origins:
                    return _DynamicImportBinding(
                        "namespace",
                        guarded=namespace.guarded,
                        module_registry_origins=namespace.module_registry_origins,
                        module_registry_names=namespace.module_registry_names,
                    )
                if namespace.kind == "module" and namespace.name is not None:
                    if namespace.name == "builtins":
                        return _dynamic_builtin_namespace_binding()
                    if namespace.name == "sys":
                        return _dynamic_module_namespace_binding("sys")
                    return _dynamic_module_namespace_binding(namespace.name)
                if namespace.kind == "mapping":
                    return namespace
                return _dynamic_join_with_guarded_origin((namespace,), _DYNAMIC_OTHER)
            if callee.kind == "callable" and callee.name == "mapping.get":
                receiver = callee.receiver
                if receiver is None or not argument_bindings:
                    return _DYNAMIC_AMBIGUOUS
                default = argument_bindings[1] if len(argument_bindings) > 1 else _DYNAMIC_NONE
                reflected = _dynamic_mapping_lookup(receiver, argument_bindings[0], default=default)
                reflected = self._module_registry_lookup_result(
                    receiver,
                    argument_bindings[0],
                    reflected,
                )
                if _is_unresolved_importer_binding(reflected):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: reflective mapping lookup "
                        "has unresolved importer provenance"
                    )
                return reflected
            if callee.kind == "callable" and callee.name == "mapping.setdefault":
                receiver = callee.receiver
                if receiver is None or not argument_bindings:
                    return _DYNAMIC_AMBIGUOUS
                owner = self._module_namespace_owner(receiver, scope_info)
                if receiver.origin_name not in {"scope:globals", "scope:locals"} and owner is None:
                    if _is_guarded_importer_binding(receiver) or any(
                        _is_guarded_importer_binding(binding) for binding in argument_bindings
                    ):
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: reflective mapping setdefault "
                            "has unresolved importer provenance"
                        )
                    return _DYNAMIC_OTHER
                key = argument_bindings[0]
                if key.kind != "string" or key.name is None or len(argument_bindings) > 2:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: scope setdefault has an "
                        "unresolved key or argument shape"
                    )
                target_environment = (
                    self._active_module_environment or self._module_environment
                    if receiver.origin_name == "scope:globals"
                    else environment
                )
                if owner is not None:
                    if owner == self.module_name and key.name in target_environment:
                        return target_environment[key.name]
                    default = (
                        argument_bindings[1] if len(argument_bindings) == 2 else _DYNAMIC_OTHER
                    )
                    self._module_namespace_write(owner, key.name, default)
                    return default
                if key.name in target_environment:
                    return target_environment[key.name]
                default = argument_bindings[1] if len(argument_bindings) == 2 else _DYNAMIC_OTHER
                target_environment[key.name] = default
                return default
            if callee.kind == "callable" and callee.name == "mapping.pop":
                receiver = callee.receiver
                if receiver is None or not argument_bindings:
                    return _DYNAMIC_AMBIGUOUS
                default = argument_bindings[1] if len(argument_bindings) > 1 else _DYNAMIC_OTHER
                reflected = _dynamic_mapping_lookup(receiver, argument_bindings[0], default=default)
                owner = self._module_namespace_owner(receiver, scope_info)
                if owner is not None:
                    key = argument_bindings[0]
                    key_known, key_value = _dynamic_binding_literal_key_value(key)
                    self._module_namespace_write(
                        owner,
                        key_value if key_known and isinstance(key_value, str) else None,
                        None,
                    )
                return reflected
            if callee.kind == "callable" and callee.name in {
                "mapping.values",
                "mapping.keys",
                "mapping.items",
            }:
                receiver = callee.receiver
                if receiver is None:
                    return _DYNAMIC_AMBIGUOUS
                if callee.name == "mapping.values":
                    result = _dynamic_sequence_binding(
                        receiver.values,
                        kind="iterable",
                        guarded=receiver.guarded,
                    )
                    return _dynamic_join_with_guarded_origin((receiver,), result)
                if callee.name == "mapping.keys":
                    result = _dynamic_sequence_binding(
                        receiver.items,
                        kind="iterable",
                    )
                    return _dynamic_join_with_guarded_origin(
                        (receiver,), result, trusted_result=True
                    )
                keys = receiver.items
                values = receiver.values
                if keys is None or values is None:
                    return _dynamic_join_with_guarded_origin((receiver,), _DYNAMIC_UNKNOWN)
                pairs = tuple(
                    _dynamic_sequence_binding((key, value))
                    for key, value in zip(keys, values, strict=True)
                )
                result = _dynamic_sequence_binding(
                    pairs,
                    kind="iterable",
                    guarded=receiver.guarded,
                )
                return _dynamic_join_with_guarded_origin((receiver,), result)
            if callee.kind == "callable" and callee.name in DYNAMIC_CALL_NAMES:
                for binding in argument_bindings:
                    self._reject_guarded_escape(binding, node, "a dynamic importer argument")
                return _DYNAMIC_OTHER
            if self._source_code_depth:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{node.lineno}: reconstructed source invocation "
                    "reaches opaque callable dispatch"
                )
            for binding in argument_bindings:
                for item in _dynamic_binding_nodes(binding):
                    if item.kind == "source_function" and item.origin_name is not None:
                        self._invalidated_function_code.add(item.origin_name)
                self._reject_guarded_escape(binding, node, "a call argument")
            return _DYNAMIC_OTHER
        if isinstance(node, ast.Subscript):
            mapping = self._expression_binding(
                node.value,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            key = self._expression_binding(
                node.slice,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            if mapping.kind in {"string", "builtin_str"}:
                if isinstance(node.slice, ast.Slice):
                    index_bindings = tuple(
                        self._expression_binding(
                            index,
                            environment,
                            pending,
                            scope_info,
                            comprehension_outer=comprehension_outer,
                        )
                        for index in (node.slice.lower, node.slice.upper, node.slice.step)
                        if index is not None
                    )
                    if any(binding.kind != "builtin_int" for binding in index_bindings):
                        return _DYNAMIC_AMBIGUOUS
                    return _dynamic_join_with_guarded_origin(
                        (mapping, *index_bindings),
                        _DYNAMIC_BUILTIN_STR,
                    )
                elif key.kind != "builtin_int":
                    return _DYNAMIC_AMBIGUOUS
                return _dynamic_join_with_guarded_origin((mapping, key), _DYNAMIC_BUILTIN_STR)
            if mapping.kind in {"sequence", "iterable"}:
                if key.kind != "builtin_int":
                    return _dynamic_join_with_guarded_origin((mapping, key), _DYNAMIC_AMBIGUOUS)
                key_known, index = _dynamic_binding_literal_key_value(key)
                if mapping.items is not None and key_known and type(index) is int:
                    try:
                        selected = mapping.items[index]
                    except IndexError:
                        return _DYNAMIC_OTHER
                    return _dynamic_join_with_guarded_origin((mapping, key), selected)
                if mapping.element is not None:
                    return _dynamic_join_with_guarded_origin((mapping, key), mapping.element)
                if mapping.items is not None and not mapping.items:
                    return _DYNAMIC_OTHER
                return _dynamic_join_with_guarded_origin((mapping, key), _DYNAMIC_UNKNOWN)
            if mapping.kind == "type" or (
                mapping.kind == "callable"
                and mapping.name in {"builtins.list", "builtins.set", "builtins.tuple"}
            ):
                if not _dynamic_binding_is_proven_nonimporter(key):
                    return _DYNAMIC_AMBIGUOUS
                return _dynamic_join_with_guarded_origin(
                    (mapping, key),
                    _DynamicImportBinding("type", "builtins.generic_alias"),
                )
            reflected = _dynamic_mapping_lookup(mapping, key)
            reflected = self._module_registry_lookup_result(mapping, key, reflected)
            if _is_unresolved_importer_binding(reflected):
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{node.lineno}: dynamic importer binding is "
                    "ambiguous or unresolved through reflective subscript access"
                )
            return reflected
        if isinstance(node, ast.NamedExpr):
            value = self._expression_binding(
                node.value,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            if not isinstance(node.target, ast.Name):
                if _is_guarded_importer_binding(value):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: guarded importer has an unsupported assignment target"
                    )
                return _DYNAMIC_OTHER
            target_name = node.target.id
            self._check_cross_scope_write(node.target, value, environment, scope_info, node.lineno)
            if comprehension_outer is not None:
                old = comprehension_outer.get(target_name, self._unknown_binding(target_name))
                if _is_guarded_importer_binding(old) or _is_guarded_importer_binding(value):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: comprehension walrus mutates a guarded importer alias"
                    )
                comprehension_outer[target_name] = value
            environment[target_name] = value
            return value
        if isinstance(node, ast.Lambda):
            for expression in (*node.args.defaults, *node.args.kw_defaults):
                if expression is not None:
                    binding = self._expression_binding(expression, environment, pending, scope_info)
                    self._reject_guarded_escape(binding, expression, "a lambda default")
            pending.append(
                _PendingDynamicImportScope(
                    node,
                    environment.copy(),
                    dict(self._importer_binding_mutations),
                )
            )
            return _DYNAMIC_OTHER
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return self._scan_comprehension(node, environment, pending, scope_info)
        if isinstance(node, ast.IfExp):
            test_value = self._expression_binding(
                node.test,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            body_env = environment.copy()
            else_env = environment.copy()
            body_outer = comprehension_outer.copy() if comprehension_outer is not None else None
            else_outer = comprehension_outer.copy() if comprehension_outer is not None else None
            body_value = self._expression_binding(
                node.body,
                body_env,
                pending,
                scope_info,
                comprehension_outer=body_outer,
            )
            else_value = self._expression_binding(
                node.orelse,
                else_env,
                pending,
                scope_info,
                comprehension_outer=else_outer,
            )
            self._join_expression_paths(environment, (body_env, else_env))
            if (
                comprehension_outer is not None
                and body_outer is not None
                and else_outer is not None
            ):
                self._join_expression_paths(comprehension_outer, (body_outer, else_outer))
            result = _join_dynamic_bindings((body_value, else_value))
            return _dynamic_join_with_guarded_origin(
                (test_value, body_value, else_value),
                result,
                trusted_result=(
                    _dynamic_binding_is_proven_nonimporter(body_value)
                    and _dynamic_binding_is_proven_nonimporter(else_value)
                ),
            )
        if isinstance(node, ast.BoolOp):
            paths: list[Mapping[str, _DynamicImportBinding]] = []
            outer_paths: list[Mapping[str, _DynamicImportBinding]] = []
            values: list[_DynamicImportBinding] = []
            for value_node in node.values:
                values.append(
                    self._expression_binding(
                        value_node,
                        environment,
                        pending,
                        scope_info,
                        comprehension_outer=comprehension_outer,
                    )
                )
                paths.append(environment.copy())
                if comprehension_outer is not None:
                    outer_paths.append(comprehension_outer.copy())
            self._join_expression_paths(environment, paths)
            if comprehension_outer is not None and outer_paths:
                self._join_expression_paths(comprehension_outer, outer_paths)
            result = _join_dynamic_bindings(values)
            return _dynamic_join_with_guarded_origin(
                values,
                result,
                trusted_result=all(
                    _dynamic_binding_is_proven_nonimporter(value) for value in values
                ),
            )
        if isinstance(node, ast.Compare):
            operands = [
                self._expression_binding(
                    node.left,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
            ]
            paths: list[Mapping[str, _DynamicImportBinding]] = []
            outer_paths: list[Mapping[str, _DynamicImportBinding]] = []
            for comparator in node.comparators:
                operands.append(
                    self._expression_binding(
                        comparator,
                        environment,
                        pending,
                        scope_info,
                        comprehension_outer=comprehension_outer,
                    )
                )
                paths.append(environment.copy())
                if comprehension_outer is not None:
                    outer_paths.append(comprehension_outer.copy())
            if paths:
                self._join_expression_paths(environment, paths)
            if comprehension_outer is not None and outer_paths:
                self._join_expression_paths(comprehension_outer, outer_paths)
            boolean_comparisons = (ast.Is, ast.IsNot, ast.In, ast.NotIn)
            result_is_boolean = bool(node.ops) and isinstance(node.ops[-1], boolean_comparisons)
            literal_operands = all(
                _dynamic_binding_literal_key_value(operand)[0] for operand in operands
            )
            if result_is_boolean or literal_operands:
                return _dynamic_join_with_guarded_origin(
                    operands,
                    _DynamicImportBinding("boolean"),
                    trusted_result=True,
                )
            return _dynamic_join_with_guarded_origin(operands, _DYNAMIC_AMBIGUOUS)
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            value_node = getattr(node, "value", None)
            value = (
                self._expression_binding(
                    value_node,
                    environment,
                    pending,
                    scope_info,
                    comprehension_outer=comprehension_outer,
                )
                if value_node is not None
                else _DYNAMIC_OTHER
            )
            self._reject_guarded_escape(value, node, "yield")
            return _DYNAMIC_OTHER

        child_values = [
            self._expression_binding(
                child,
                environment,
                pending,
                scope_info,
                comprehension_outer=comprehension_outer,
            )
            for child in ast.iter_child_nodes(node)
            if isinstance(child, ast.expr)
        ]
        if any(binding.guarded or binding.kind == "ambiguous" for binding in child_values):
            return _DYNAMIC_AMBIGUOUS
        return _DYNAMIC_OTHER

    @staticmethod
    def _source_lazy_export_comprehension_value(node: ast.AST) -> bool:
        """Return whether a comprehension value uses only finite literal bindings."""
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str)
        if isinstance(node, ast.Name):
            return isinstance(node.ctx, ast.Load)
        if isinstance(node, ast.Tuple):
            return all(
                _DynamicImportSourceScanner._source_lazy_export_comprehension_value(item)
                for item in node.elts
            )
        return False

    def _source_lazy_export_update_entries(
        self,
        expression: ast.expr,
        expression_binding: _DynamicImportBinding,
        environment: Mapping[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
    ) -> tuple[tuple[str, tuple[str, str]], ...] | None:
        """Resolve one finite mapping update used to build a source-owned lazy map."""
        if isinstance(expression, ast.Dict):
            return _dynamic_source_lazy_export_map_entries(expression_binding)
        if not isinstance(expression, ast.DictComp):
            return None
        if (
            len(expression.generators) != 1
            or expression.generators[0].is_async
            or expression.generators[0].ifs
            or not self._source_lazy_export_comprehension_value(expression.key)
            or not self._source_lazy_export_comprehension_value(expression.value)
        ):
            return None
        generator = expression.generators[0]
        iterable = self._expression_binding(
            generator.iter,
            dict(environment),
            pending,
            scope_info,
        )
        if (
            iterable.kind not in {"sequence", "iterable"}
            or iterable.items is None
            or iterable.guarded
            or len(iterable.items) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT
        ):
            return None
        local_scope: dict[str, set[str]] = {
            "globals": set(),
            "nonlocals": set(),
            "_effectful": set(),
        }
        items: dict[str, tuple[str, str]] = {}
        for item in iterable.items:
            if item.kind in {"unknown", "ambiguous"} or item.guarded:
                return None
            local_environment = dict(environment)
            self._assign_target(
                generator.target,
                item,
                local_environment,
                pending,
                local_scope,
            )
            key_binding = self._expression_binding(
                expression.key,
                local_environment,
                pending,
                local_scope,
            )
            value_binding = self._expression_binding(
                expression.value,
                local_environment,
                pending,
                local_scope,
            )
            entry = _dynamic_source_lazy_export_map_entries(
                _dynamic_mapping_binding((key_binding,), (value_binding,))
            )
            if entry is None or len(entry) != 1:
                return None
            items[entry[0][0]] = entry[0][1]
            if len(items) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                return None
        return tuple(items.items())

    def _apply_source_lazy_export_map_update(
        self,
        node: ast.Call,
        callee: _DynamicImportBinding,
        argument_bindings: Sequence[_DynamicImportBinding],
        environment: dict[str, _DynamicImportBinding],
        scope_info: Mapping[str, set[str]],
    ) -> bool:
        """Replay a finite owner-module map update before its lazy hook is defined."""
        receiver = callee.receiver
        if (
            receiver is None
            or not _dynamic_is_source_lazy_export_map_binding(
                receiver,
                self.source_bindings._selected_source_module_names()
                if self.source_bindings is not None
                else (),
            )
            or receiver.origin_name is None
            or receiver.origin_name.rpartition(".")[0] != self.module_name
            or self.source_bindings is None
            or self.module_name is None
            or scope_info is not self._module_scope_info
            or not self._module_execution_active
            or self._active_module_function_stack
            or id(node) not in self._module_initializer_call_ids
            or environment.get("__getattr__", self._unknown_binding("__getattr__")).kind
            == "source_function"
            or receiver.origin_name in self.source_bindings._source_mapping_effects
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "update"
            or len(node.args) != 1
            or node.keywords
            or (argument_bindings and len(argument_bindings) != 1)
            or isinstance(node.args[0], ast.Starred)
        ):
            return False
        current_entries = _dynamic_source_lazy_export_map_entries(receiver)
        if current_entries is None:
            return False
        update_binding = argument_bindings[0] if argument_bindings else _DYNAMIC_UNKNOWN
        update_entries = self._source_lazy_export_update_entries(
            node.args[0],
            update_binding,
            environment,
            [],
            scope_info,
        )
        if update_entries is None:
            return False
        merged = dict(current_entries)
        merged.update(update_entries)
        if len(merged) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
            return False
        updated = replace(
            _dynamic_mapping_binding(
                tuple(_dynamic_string_binding(key) for key in merged),
                tuple(
                    _dynamic_sequence_binding(
                        (_dynamic_string_binding(module_name), _dynamic_string_binding(symbol)),
                        sequence_type="tuple",
                    )
                    for module_name, symbol in merged.values()
                ),
            ),
            origin_name=receiver.origin_name,
        )
        environments = [environment, self._module_environment, self._active_module_environment]
        seen: set[int] = set()
        for target_environment in environments:
            if not isinstance(target_environment, dict) or id(target_environment) in seen:
                continue
            seen.add(id(target_environment))
            for name, existing in tuple(target_environment.items()):
                if existing.kind == "mapping" and existing.origin_name == receiver.origin_name:
                    target_environment[name] = updated
        return True

    def _scan_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        environment: dict[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
    ) -> _DynamicImportBinding:
        generators = node.generators
        if not generators:
            return _DYNAMIC_OTHER
        # Python evaluates the first iterable in the containing scope.
        first_iterable = self._expression_binding(
            generators[0].iter, environment, pending, scope_info
        )
        local_env = environment.copy()
        comp_outer = environment
        for index, generator in enumerate(generators):
            iterable = (
                first_iterable
                if index == 0
                else self._expression_binding(generator.iter, local_env, pending, scope_info)
            )
            self._assign_target(
                generator.target,
                self._iterable_element_binding(iterable),
                local_env,
                pending,
                scope_info,
            )
            for condition in generator.ifs:
                self._expression_binding(
                    condition,
                    local_env,
                    pending,
                    scope_info,
                    comprehension_outer=comp_outer,
                )
                iterable = self._filter_comprehension_values(
                    iterable,
                    generator.target,
                    condition,
                    local_env,
                    pending,
                    scope_info,
                )
                self._assign_target(
                    generator.target,
                    self._iterable_element_binding(iterable),
                    local_env,
                    pending,
                    scope_info,
                )
        if isinstance(node, ast.DictComp):
            key = self._expression_binding(
                node.key,
                local_env,
                pending,
                scope_info,
                comprehension_outer=comp_outer,
            )
            value = self._expression_binding(
                node.value,
                local_env,
                pending,
                scope_info,
                comprehension_outer=comp_outer,
            )
            return _dynamic_mapping_binding(
                None,
                None,
                guarded=key.guarded
                or key.kind == "ambiguous"
                or value.guarded
                or value.kind == "ambiguous",
            )
        else:
            element = self._expression_binding(
                node.elt,
                local_env,
                pending,
                scope_info,
                comprehension_outer=comp_outer,
            )
            return _dynamic_sequence_binding(
                None,
                kind="iterable" if isinstance(node, ast.SetComp) else "sequence",
                guarded=element.guarded or element.kind == "ambiguous",
                sequence_type="list" if isinstance(node, ast.ListComp) else None,
            )

    def _filter_comprehension_values(
        self,
        iterable: _DynamicImportBinding,
        target: ast.AST,
        condition: ast.expr,
        environment: dict[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
    ) -> _DynamicImportBinding:
        if iterable.kind not in {"mapping", "sequence", "iterable"} or iterable.items is None:
            return iterable
        if len(iterable.items) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
            return iterable
        retained: list[_DynamicImportBinding] = []
        for candidate in iterable.items:
            candidate_environment = environment.copy()
            self._assign_target(
                target,
                candidate,
                candidate_environment,
                pending,
                scope_info,
            )
            if self._known_comprehension_condition(condition, candidate_environment) is not False:
                retained.append(candidate)
        return _dynamic_sequence_binding(retained, kind="iterable")

    def _known_comprehension_condition(
        self,
        node: ast.expr,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> bool | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name):
            binding = environment.get(node.id)
            if binding is not None and binding.kind == "boolean":
                return binding.boolean
            return None
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = self._known_comprehension_condition(node.operand, environment)
            return None if value is None else not value
        if isinstance(node, ast.BoolOp):
            values = [
                self._known_comprehension_condition(value, environment) for value in node.values
            ]
            if isinstance(node.op, ast.And):
                if False in values:
                    return False
                return True if all(value is True for value in values) else None
            if True in values:
                return True
            return False if all(value is False for value in values) else None
        if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
            left_binding = self._known_comprehension_binding(node.left, environment)
            right_binding = self._known_comprehension_binding(node.comparators[0], environment)
            operation = node.ops[0]
            if isinstance(operation, ast.In | ast.NotIn):
                members = self._known_string_members(right_binding)
                if members is None or left_binding.kind != "string" or left_binding.name is None:
                    return None
                found = left_binding.name in members
                return not found if isinstance(operation, ast.NotIn) else found
            left = self._known_comprehension_value(node.left, environment)
            right = self._known_comprehension_value(node.comparators[0], environment)
            if (
                isinstance(operation, ast.Eq | ast.NotEq)
                and left is not None
                and right is not None
                and type(left) is type(right)
            ):
                found = left == right
                return not found if isinstance(operation, ast.NotEq) else found
            return None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "startswith"
            and len(node.args) == 1
            and not node.keywords
        ):
            receiver = self._known_comprehension_value(node.func.value, environment)
            prefix = self._known_comprehension_value(node.args[0], environment)
            if isinstance(receiver, str) and isinstance(prefix, str):
                return receiver.startswith(prefix)
            return None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name | ast.Attribute)
            and len(node.args) == 2
            and not node.keywords
        ):
            predicate = self._expression_binding(
                node.func,
                dict(environment),
                [],
                {},
            )
            if (
                predicate.kind == "callable"
                and predicate.name == "builtins.isinstance"
                and isinstance(node.args[1], ast.Name)
            ):
                tested_type = self._lookup(node.args[1].id, environment)
                candidate = self._known_comprehension_binding(node.args[0], environment)
                if tested_type.kind == "type" and tested_type.name == "builtins.type":
                    if candidate.kind in {
                        "callable",
                        "iterable",
                        "mapping",
                        "module",
                        "namespace",
                        "sequence",
                        "string",
                    }:
                        return False
                    if candidate.kind == "type":
                        return True
            return None
        return None

    def _known_comprehension_value(
        self,
        node: ast.expr,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> str | bool | None:
        binding = self._known_comprehension_binding(node, environment)
        if binding.kind == "string":
            return binding.name
        if binding.kind == "boolean":
            return binding.boolean
        return None

    def _known_comprehension_binding(
        self,
        node: ast.expr,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> _DynamicImportBinding:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return _dynamic_string_binding(node.value)
            if isinstance(node.value, bool):
                return _DynamicImportBinding("boolean", boolean=node.value)
            return _DYNAMIC_OTHER
        if isinstance(node, ast.Name):
            return environment.get(node.id, self._lookup(node.id, {}))
        return _DYNAMIC_UNKNOWN

    @staticmethod
    def _known_string_members(binding: _DynamicImportBinding) -> frozenset[str] | None:
        if binding.kind in {"mapping", "sequence", "iterable"}:
            items = binding.items
        else:
            return None
        if items is None or any(item.kind != "string" or item.name is None for item in items):
            return None
        return frozenset(str(item.name) for item in items)

    @staticmethod
    def _iterable_element_binding(
        binding: _DynamicImportBinding,
    ) -> _DynamicImportBinding:
        if binding.element is not None:
            return _dynamic_join_with_guarded_origin((binding,), binding.element)
        if binding.kind in {"sequence", "iterable", "mapping"}:
            if binding.items is not None:
                result = _join_dynamic_bindings(binding.items)
                return _dynamic_join_with_guarded_origin(
                    (binding,),
                    result,
                    trusted_result=binding.kind == "mapping",
                )
            return _dynamic_join_with_guarded_origin((binding,), _DYNAMIC_UNKNOWN)
        return _dynamic_join_with_guarded_origin((binding,), _DYNAMIC_UNKNOWN)

    @staticmethod
    def _refinement_expression_binding(
        node: ast.AST,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> _DynamicImportBinding | None:
        """Evaluate only side-effect-free expressions used by finite-map guards."""
        if isinstance(node, ast.Name):
            return environment.get(node.id, _DYNAMIC_UNKNOWN)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return _dynamic_string_binding(node.value)
        if isinstance(node, ast.Tuple):
            items = tuple(
                _DynamicImportSourceScanner._refinement_expression_binding(item, environment)
                for item in node.elts
            )
            if any(item is None for item in items):
                return None
            return _dynamic_sequence_binding(
                tuple(item for item in items if item is not None),
                component_names=tuple(
                    item.id if isinstance(item, ast.Name) else None for item in node.elts
                ),
            )
        return None

    def _refine_none_check_branch(
        self,
        test: ast.expr,
        environment: Mapping[str, _DynamicImportBinding],
        *,
        truthy: bool,
    ) -> dict[str, _DynamicImportBinding]:
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return self._refine_none_check_branch(test.operand, environment, truthy=not truthy)
        if not (
            isinstance(test, ast.Compare)
            and len(test.ops) == len(test.comparators) == 1
            and isinstance(test.ops[0], (ast.Is, ast.IsNot, ast.Eq, ast.NotEq))
        ):
            return dict(environment)
        left, right = test.left, test.comparators[0]
        if isinstance(left, ast.Constant) and left.value is None and isinstance(right, ast.Name):
            name = right.id
        elif isinstance(right, ast.Constant) and right.value is None and isinstance(left, ast.Name):
            name = left.id
        else:
            return dict(environment)
        is_none_branch = truthy if isinstance(test.ops[0], (ast.Is, ast.Eq)) else not truthy
        alternatives = _dynamic_binding_alternatives(environment.get(name, _DYNAMIC_UNKNOWN))
        if alternatives is None:
            return dict(environment)
        selected = tuple(item for item in alternatives if (item.kind == "none") is is_none_branch)
        if not selected:
            return dict(environment)
        refined = dict(environment)
        refined[name] = _dynamic_union_binding(selected)
        return refined

    def _refine_mapping_membership_branch(
        self,
        test: ast.expr,
        environment: Mapping[str, _DynamicImportBinding],
        *,
        truthy: bool,
    ) -> dict[str, _DynamicImportBinding]:
        """Refine a branch only when an immutable finite map proves its key domain."""
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return self._refine_mapping_membership_branch(
                test.operand,
                environment,
                truthy=not truthy,
            )
        if not (
            isinstance(test, ast.Compare)
            and len(test.ops) == len(test.comparators) == 1
            and isinstance(test.ops[0], (ast.In, ast.NotIn))
            and isinstance(test.comparators[0], ast.Name)
        ):
            return dict(environment)

        registry = environment.get(test.comparators[0].id, _DYNAMIC_UNKNOWN)
        if (
            registry.kind != "mapping"
            or not registry.immutable
            or registry.items is None
            or not all(_dynamic_key_is_exact(key) for key in registry.items)
        ):
            return dict(environment)
        key = self._refinement_expression_binding(test.left, environment)
        if key is None:
            return dict(environment)

        matching_keys = [
            registered_key
            for registered_key in registry.items
            if _dynamic_bindings_may_equal(key, registered_key)
        ]
        is_membership_branch = truthy if isinstance(test.ops[0], ast.In) else not truthy
        if is_membership_branch:
            selected_keys = matching_keys
        else:
            candidates = key.items if key.kind == "union" else (key,)
            if candidates is None or not all(_dynamic_key_is_exact(item) for item in candidates):
                return dict(environment)
            selected_keys = [
                candidate
                for candidate in candidates
                if not any(
                    _dynamic_keys_equal_exact(candidate, registered_key)
                    for registered_key in registry.items
                )
            ]

        refined_environment = dict(environment)
        if isinstance(test.left, ast.Name):
            refined_environment[test.left.id] = _dynamic_union_binding(
                selected_keys,
                component_names=key.component_names,
            )
        for index, component_name in enumerate(key.component_names or ()):
            if component_name is None:
                continue
            component_values = [
                selected.items[index]
                for selected in selected_keys
                if selected.kind == "sequence"
                and selected.items is not None
                and len(selected.items) == len(key.component_names or ())
            ]
            if len(component_values) == len(selected_keys):
                refined_environment[component_name] = _dynamic_union_binding(component_values)
        return refined_environment

    def _assign_target(
        self,
        target: ast.AST,
        value: _DynamicImportBinding,
        environment: dict[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
        *,
        delete: bool = False,
    ) -> None:
        if isinstance(target, ast.Name):
            assigned = (
                self._unknown_binding(target.id)
                if value.kind == "unknown" and not value.guarded
                else value
            )
            self._bind_name(target.id, assigned, environment, scope_info)
            if (
                self._active_module_function_stack
                and self._active_module_environment is not None
                and target.id in scope_info.get("globals", set())
                and self.module_name is not None
            ):
                if not self._module_namespace_write(
                    self.module_name,
                    target.id,
                    environment[target.id],
                ):
                    self._active_module_environment[target.id] = environment[target.id]
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            items = value.items if value.kind in {"sequence", "mapping"} else None
            if (
                items is None
                and value.kind == "sequence"
                and value.element is not None
                and not any(isinstance(element, ast.Starred) for element in target.elts)
            ):
                items = (value.element,) * len(target.elts)
            if value.kind == "union" and value.items is not None:
                alternatives = value.items
                if all(item.kind == "sequence" and item.items is not None for item in alternatives):
                    sequences = [item.items for item in alternatives if item.items is not None]
                    if sequences and len({len(items) for items in sequences}) == 1:
                        items = tuple(
                            _dynamic_union_binding(tuple(sequence[index] for sequence in sequences))
                            for index in range(len(sequences[0]))
                        )
            star_positions = [
                index
                for index, element in enumerate(target.elts)
                if isinstance(element, ast.Starred)
            ]
            if items is not None and not star_positions and len(items) == len(target.elts):
                children = tuple(zip(target.elts, items, strict=True))
            elif items is not None and len(star_positions) == 1:
                star_index = star_positions[0]
                trailing_count = len(target.elts) - star_index - 1
                if len(items) >= star_index + trailing_count:
                    children_list: list[tuple[ast.AST, _DynamicImportBinding]] = []
                    children_list.extend(
                        zip(target.elts[:star_index], items[:star_index], strict=True)
                    )
                    middle_stop = len(items) - trailing_count if trailing_count else len(items)
                    star_items = _dynamic_sequence_binding(items[star_index:middle_stop])
                    children_list.append(
                        (
                            target.elts[star_index],
                            _dynamic_join_with_guarded_origin((value,), star_items),
                        )
                    )
                    if trailing_count:
                        children_list.extend(
                            zip(
                                target.elts[star_index + 1 :],
                                items[middle_stop:],
                                strict=True,
                            )
                        )
                    children = tuple(children_list)
                else:
                    children = ()
            else:
                children = ()
            if children:
                for element, child_value in children:
                    self._assign_target(
                        element,
                        _dynamic_join_with_guarded_origin(
                            (value,),
                            child_value,
                            trusted_result=_dynamic_binding_is_proven_nonimporter(child_value),
                        ),
                        environment,
                        pending,
                        scope_info,
                        delete=delete,
                    )
                return
            child_value = _DYNAMIC_AMBIGUOUS if value.guarded else _DYNAMIC_UNKNOWN
            for element in target.elts:
                self._assign_target(
                    element.value if isinstance(element, ast.Starred) else element,
                    child_value,
                    environment,
                    pending,
                    scope_info,
                    delete=delete,
                )
            return
        if isinstance(target, ast.Starred):
            self._assign_target(
                target.value, value, environment, pending, scope_info, delete=delete
            )
            return
        if isinstance(target, ast.Attribute):
            receiver = self._expression_binding(target.value, environment, pending, scope_info)
            if receiver.kind in {"reconstructed_function", "source_closure", "source_code"}:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{target.lineno}: reconstructed callable mutation is unsupported"
                )
            if receiver.kind in {"source_function", "source_method"}:
                if receiver.origin_name is not None:
                    self._invalidated_function_code.add(receiver.origin_name)
                if target.attr == "__code__":
                    # Mutating a function cannot rewrite an already captured code object.
                    return
            self._reject_guarded_escape(value, target, "attribute storage")
            owner = self._module_namespace_owner(receiver, scope_info)
            if owner is not None and self._module_namespace_write(owner, target.attr, value):
                return
            if (
                self._source_instance_summary
                and isinstance(target.value, ast.Name)
                and (target.value.id == "self")
            ):
                current = environment.get("self")
                if (
                    current is not None
                    and current.kind == "object"
                    and current.origin_name is not None
                    and current.origin_name.startswith("polisyos.")
                ):
                    if (
                        self._source_summary_fields is not None
                        and target.attr not in self._source_summary_fields
                    ):
                        return
                    updated = _dynamic_source_object_field(current, target.attr, value)
                    if updated.kind == "object":
                        environment["self"] = updated
                        return
            self._source_code_opaque_effect = True
            self._invalidate_unmodeled_source_mapping_inputs((receiver, value), environment)
            self._invalidate_source_class_effects((receiver, value))
            return
        if isinstance(target, ast.Subscript):
            base = self._expression_binding(target.value, environment, pending, scope_info)
            key = self._expression_binding(target.slice, environment, pending, scope_info)
            self._invalidate_source_class_effects((base, value))
            if base.kind in {"mapping", "namespace"}:
                is_scope_mapping = base.origin_name is not None and base.origin_name.startswith(
                    "scope:"
                )
                if base.immutable:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{target.lineno}: mapping mutation leaves "
                        "dynamic importer provenance unresolved"
                    )
                owner_resolution = self._module_namespace_owner_resolution(base, scope_info)
                owner = self._module_namespace_owner(base, scope_info)
                external_module_namespace = (
                    base.kind in {"mapping", "namespace"}
                    and base.origin_name is not None
                    and base.origin_name.startswith("module_namespace:")
                    and owner_resolution.kind == "nonselected"
                    and owner is not None
                )
                if (
                    _is_guarded_importer_binding(base)
                    and not is_scope_mapping
                    and base.origin_name != "sys.modules"
                    and not external_module_namespace
                ):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{target.lineno}: mapping mutation leaves "
                        "dynamic importer provenance unresolved"
                    )
                key_known, key_value = _dynamic_binding_literal_key_value(key)
                local_live_write = (
                    is_scope_mapping
                    and base.globals_owner == self.module_name
                    and owner == self.module_name
                    and key_known
                    and isinstance(key_value, str)
                    and (self._module_execution_active or self._active_module_function_stack)
                )
                if not local_live_write:
                    self._reject_guarded_escape(value, target, "container storage")
                if key.guarded or key.kind == "ambiguous":
                    self._reject_guarded_escape(key, target, "container key")
                if base.origin_name == "sys.modules" and (
                    self._module_execution_active or self._active_module_function_stack
                ):
                    key_known, key_value = _dynamic_binding_literal_key_value(key)
                    if (
                        key_known
                        and isinstance(key_value, str)
                        and self.source_bindings is not None
                        and key_value in self.source_bindings.module_paths
                    ):
                        self._module_namespace_write(key_value, None, None)
                    elif not key_known:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{target.lineno}: selected module registry "
                            "write has an unresolved key"
                        )
                if owner is not None and (
                    self._module_execution_active or self._active_module_function_stack
                ):
                    key_known, key_value = _dynamic_binding_literal_key_value(key)
                    self._module_namespace_write(
                        owner,
                        key_value if key_known and isinstance(key_value, str) else None,
                        value,
                    )
                if not is_scope_mapping and base.origin_name != "sys.modules":
                    if not self._update_local_mapping_slot(
                        target,
                        base,
                        key,
                        value,
                        environment,
                        delete=delete,
                    ):
                        self._invalidate_unmodeled_source_mapping_inputs(
                            (base, key, value),
                            environment,
                            include_namespace=True,
                        )
                return
            self._source_code_opaque_effect = True
            self._reject_guarded_escape(base, target, "container mutation")
            self._reject_guarded_escape(value, target, "container storage")
            self._invalidate_unmodeled_source_mapping_inputs((base, key, value), environment)

    def _check_cross_scope_write(
        self,
        target: ast.AST,
        value: _DynamicImportBinding,
        environment: Mapping[str, _DynamicImportBinding],
        scope_info: Mapping[str, set[str]],
        line: int,
    ) -> None:
        names = {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}
        cross_scope = scope_info.get("globals", set()) | scope_info.get("nonlocals", set())
        for name in names & cross_scope:
            prior = environment.get(name, self._unknown_binding(name))
            if (
                name in _DYNAMIC_IMPORT_GUARDED_ROOTS
                or _is_guarded_importer_binding(prior)
                or _is_guarded_importer_binding(value)
            ):
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{line}: cross-scope write changes guarded importer binding {name!r}"
                )

    def _selected_code_origin(
        self,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        node: ast.AST,
        *,
        free_variables: tuple[str, ...] = (),
    ) -> _DynamicSourceCodeOrigin:
        """Bind a plain source body to the invocation-local selected byte context."""
        member = (
            next(
                (item for item in self.source_context.members if item.path == self.source_path),
                None,
            )
            if self.source_context
            else None
        )
        if (
            member is None
            or self.module_name is None
            or not isinstance(function, ast.FunctionDef)
            or function.decorator_list
            or getattr(function, "type_params", ())
            or not any(item is function for item in ast.walk(member.tree))
            or any(
                isinstance(item, ast.Name) and item.id in {"__class__", "super"}
                for item in ast.walk(function)
            )
        ):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{getattr(node, 'lineno', 1)}: selected code origin is unsupported"
            )
        identity = f"{self.relative_path}:{function.lineno}:{function.col_offset}"
        return _DynamicSourceCodeOrigin(
            identity,
            self.source_context.identity,
            member.content_sha256,
            self.module_name,
            self.relative_path,
            function,
            free_variables,
        )

    def _capture_source_code(
        self,
        binding: _DynamicImportBinding,
        node: ast.AST,
    ) -> _DynamicImportBinding:
        """Freeze code at capture; subsequent function writes invalidate only later lookups."""
        alternatives = binding.items if binding.kind == "union" else (binding,)
        captures: list[_DynamicImportBinding] = []
        for target in alternatives or ():
            if target.origin_name in self._invalidated_function_code:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{getattr(node, 'lineno', 1)}: source function code was mutated"
                )
            if target.kind == "source_function":
                summary = self._module_function_summaries.get(target.origin_name or "")
                origin = self._selected_code_origin(summary.node, node) if summary else None
            elif target.kind == "source_method":
                origin = target.code_origin
            else:
                origin = None
            if origin is None or origin.free_variables:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{getattr(node, 'lineno', 1)}: code capture lacks a "
                    "plain selected function with no free cells"
                )
            captures.append(_DynamicImportBinding("source_code", code_origin=origin))
        if not captures:
            raise DynamicImportCollectionError(
                f"{self.relative_path}: code alternatives are unresolved"
            )
        return _dynamic_union_binding(captures)

    def _construct_source_function(
        self,
        node: ast.Call,
        arguments: Sequence[_DynamicImportBinding],
    ) -> _DynamicImportBinding:
        """Admit selected code with same-origin live globals and fixed native builtins."""
        if (
            len(node.args) != 2
            or node.keywords
            or len(arguments) != 2
            or any(isinstance(item, ast.Starred) for item in node.args)
        ):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: FunctionType defaults, closure or call shape unsupported"
            )
        if self._source_code_opaque_effect:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: FunctionType construction crosses opaque source effects"
            )
        code, namespace = arguments
        if (
            namespace.kind != "mapping"
            or namespace.origin_name != "scope:globals"
            or namespace.globals_owner != self.module_name
            or self.module_name is None
            or not self._module_namespace_complete
        ):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: FunctionType requires same-origin live globals"
            )
        effects = (
            dict(self.source_context.module_namespace_effects or ()) if self.source_context else {}
        )
        if "builtins" in effects or "types" in effects or self.module_name in effects:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: FunctionType namespace has cross-module effects"
            )
        live = self._active_module_environment or self._module_environment
        native_builtins = live.get("__builtins__")
        if native_builtins is not None and not (
            native_builtins.kind in {"module", "namespace"} and native_builtins.name == "builtins"
        ):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: FunctionType construction builtins are unsupported"
            )
        builtins = _dynamic_builtin_namespace_binding()
        alternatives = code.items if code.kind == "union" else (code,)
        callables: list[_DynamicImportBinding] = []
        for value in alternatives or ():
            origin = value.code_origin
            if (
                value.kind != "source_code"
                or origin is None
                or self.source_context is None
                or origin.context_identity != self.source_context.identity
                or origin.source_module != self.module_name
                or origin.free_variables
            ):
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{node.lineno}: FunctionType code origin is unresolved"
                )
            callables.append(
                _DynamicImportBinding(
                    "reconstructed_function",
                    code_origin=origin,
                    globals_owner=self.module_name,
                    function_builtins=builtins,
                )
            )
        if not callables:
            raise DynamicImportCollectionError(
                f"{self.relative_path}: FunctionType has no selected code"
            )
        return _dynamic_union_binding(callables)

    def _source_function_scanner_for(
        self,
        source_module: str,
        node: ast.Call,
    ) -> _DynamicImportSourceScanner:
        """Get an independently scanned selected source module for one call target."""
        if source_module == self.module_name:
            return self
        if source_module in self._source_function_module_stack:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: recursive cross-module source function "
                "analysis is unresolved"
            )
        if self.source_bindings is None or self.source_context is None:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: source function target lacks a selected "
                "source context"
            )
        scanner = self._source_function_scanners.get(source_module)
        if scanner is not None:
            return scanner
        source_path = self.source_bindings.module_paths.get(source_module)
        member = next(
            (
                candidate
                for candidate in self.source_context.members
                if candidate.path == source_path
            ),
            None,
        )
        if member is None:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: source function target is outside the "
                "selected source context"
            )
        if len(self._source_function_module_stack) >= 24:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: cross-module source function depth exceeds "
                "the bounded summary limit"
            )
        self._source_function_module_stack.append(source_module)
        try:
            scanner = _DynamicImportSourceScanner(
                member.path,
                relative_path=member.relative_path,
                source_bindings=self.source_bindings,
                source_context=self.source_context,
                source_function_scanners=self._source_function_scanners,
                source_function_module_stack=self._source_function_module_stack,
            )
            scanner.scan(member.tree)
            self._source_function_scanners[source_module] = scanner
            return scanner
        finally:
            self._source_function_module_stack.pop()

    def _source_function_call(
        self,
        node: ast.Call,
        callee: _DynamicImportBinding,
        argument_bindings: Sequence[_DynamicImportBinding],
        environment: dict[str, _DynamicImportBinding],
        scope_info: Mapping[str, set[str]],
        *,
        awaited: bool,
    ) -> _DynamicImportBinding | None:
        """Join finite, selected source-function alternatives in their own namespaces."""
        alternatives = (
            callee.items
            if callee.kind == "union" and callee.items is not None
            else (callee,)
            if callee.kind in {"source_function", "reconstructed_function", "source_closure"}
            else ()
        )
        function_bindings = tuple(
            binding
            for binding in alternatives
            if binding.kind in {"source_function", "reconstructed_function", "source_closure"}
        )
        if not function_bindings:
            return None
        source_code_call = any(
            binding.kind in {"reconstructed_function", "source_closure"}
            for binding in function_bindings
        )
        if (
            scope_info is not self._module_scope_info
            and not self._active_module_function_stack
            and not source_code_call
        ):
            # Nominal source identity is not proof of an untransferred deferred effect.
            self._source_code_opaque_effect = True
            return None
        if not alternatives or len(alternatives) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: module-time local function target is unresolved"
            )

        pushed_module = self.module_name is not None and (
            not self._source_function_module_stack
            or self._source_function_module_stack[-1] != self.module_name
        )
        if pushed_module:
            if self.module_name in self._source_function_module_stack:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{node.lineno}: recursive source function module "
                    "analysis is unresolved"
                )
            self._source_function_module_stack.append(self.module_name)

        try:
            candidates: list[
                tuple[
                    _DynamicImportSourceScanner,
                    str,
                    _DynamicImportFunctionSummary,
                    _DynamicImportBinding,
                ]
            ] = []
            for binding in alternatives:
                scanner = self
                identity: str | None = None
                if binding.kind in {"reconstructed_function", "source_closure"}:
                    origin = binding.code_origin
                    if (
                        origin is None
                        or self.source_context is None
                        or origin.context_identity != self.source_context.identity
                        or origin.source_module != self.module_name
                        or binding.globals_owner != self.module_name
                    ):
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: reconstructed code context is unresolved"
                        )
                    identity = origin.identity
                elif binding.kind == "source_function":
                    identity = binding.origin_name
                    if identity in self._invalidated_function_code:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: source function code was mutated"
                        )
                elif (
                    binding.kind == "other"
                    and binding.origin_name is not None
                    and binding.origin_name.startswith("polisyos.")
                    and self.source_bindings is not None
                ):
                    resolved = self.source_bindings._source_function_definition(binding.origin_name)
                    if resolved is not None:
                        source_module, _source_path, _function = resolved
                        scanner = self._source_function_scanner_for(source_module, node)
                        symbol = binding.origin_name.rpartition(".")[2]
                        source_binding = scanner._module_environment.get(symbol)
                        if (
                            source_binding is None
                            or source_binding.kind != "source_function"
                            or source_binding.origin_name is None
                        ):
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{node.lineno}: selected source function "
                                "binding changed during independent module analysis"
                            )
                        identity = source_binding.origin_name
                if identity is None:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: module-time local function target "
                        "is ambiguous"
                    )
                summary = (
                    _DynamicImportFunctionSummary(binding.code_origin.node, {})
                    if binding.kind in {"reconstructed_function", "source_closure"}
                    and binding.code_origin is not None
                    else scanner._module_function_summaries.get(identity)
                )
                if summary is None:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: selected source function summary "
                        "is unavailable"
                    )
                candidates.append((scanner, identity, summary, binding))

            scanners = tuple(dict.fromkeys(candidate[0] for candidate in candidates))
            base_environments: dict[
                _DynamicImportSourceScanner, dict[str, _DynamicImportBinding]
            ] = {}
            for scanner in scanners:
                module_environment = (
                    (
                        self._active_module_environment or self._module_environment
                        if source_code_call
                        else self._active_module_environment or environment
                    )
                    if scanner is self
                    else scanner._module_environment
                )
                if module_environment is None:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: source module namespace snapshot "
                        "is unavailable"
                    )
                base_environments[scanner] = module_environment

            branch_states: dict[
                _DynamicImportSourceScanner, list[dict[str, _DynamicImportBinding]]
            ] = {scanner: [] for scanner in scanners}
            branch_returns: list[_DynamicImportBinding] = []
            valid_return = False
            for scanner, identity, summary, binding in candidates:
                for other_scanner in scanners:
                    if other_scanner is not scanner:
                        branch_states[other_scanner].append(dict(base_environments[other_scanner]))
                base_environment = base_environments[scanner]
                branch_environment = dict(base_environment)
                previous_active_environment = scanner._active_module_environment
                previous_builtins = scanner._active_code_builtins
                previous_code_depth = scanner._source_code_depth
                if binding.kind in {"reconstructed_function", "source_closure"}:
                    if scanner._source_code_opaque_effect:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: reconstructed invocation crosses opaque source effects"
                        )
                    if not scanner._module_namespace_complete:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: reconstructed globals have opaque writes"
                        )
                    scanner._source_code_depth += 1
                    scanner._active_code_builtins = binding.function_builtins
                scanner._active_module_environment = branch_environment
                function = summary.node
                branch_result = _DYNAMIC_OTHER
                branch_invoked = False
                pushed_target_module = scanner is not self and scanner.module_name is not None
                try:
                    if pushed_target_module:
                        if scanner.module_name in self._source_function_module_stack:
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{node.lineno}: recursive cross-module "
                                "source function analysis is unresolved"
                            )
                        self._source_function_module_stack.append(scanner.module_name)
                    if isinstance(function, ast.AsyncFunctionDef):
                        if awaited:
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{node.lineno}: awaited source async "
                                "function timing is unresolved"
                            )
                    elif function.decorator_list:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{node.lineno}: decorated source function call "
                            "timing is unresolved"
                        )
                    else:
                        parameter_bindings = scanner._source_function_parameter_bindings(
                            function,
                            node,
                            argument_bindings,
                            summary.defaults,
                        )
                        if parameter_bindings is None and scanner._source_code_depth:
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{node.lineno}: reconstructed arguments do not bind"
                            )
                        if parameter_bindings is not None:
                            invocation_state = (
                                tuple(sorted(parameter_bindings.items())),
                                tuple(sorted(branch_environment.items())),
                            )
                            repeated_invocation = any(
                                active_identity == identity and active_state == invocation_state
                                for active_identity, active_state in scanner._active_module_function_invocation_states
                            )
                            if repeated_invocation and scanner._source_code_depth:
                                raise DynamicImportCollectionError(
                                    f"{self.relative_path}:{node.lineno}: reconstructed recursion is unresolved"
                                )
                            if repeated_invocation:
                                # The active body already covers this same abstract
                                # module-time state. Close the recursive return without
                                # discarding importer provenance carried by its inputs.
                                branch_result = _dynamic_join_with_guarded_origin(
                                    tuple(parameter_bindings.values()),
                                    _DYNAMIC_UNKNOWN,
                                )
                                branch_invoked = True
                            else:
                                if len(scanner._active_module_function_stack) >= 24:
                                    raise DynamicImportCollectionError(
                                        f"{self.relative_path}:{node.lineno}: module-time function "
                                        "call depth exceeds the bounded summary limit"
                                    )
                                returned: list[_DynamicImportBinding] = []
                                scanner._active_module_function_stack.append(identity)
                                scanner._active_module_function_invocation_states.append(
                                    (identity, invocation_state)
                                )
                                try:
                                    scanner._scan_function(
                                        function,
                                        dict(
                                            zip(
                                                binding.closure_names,
                                                binding.source_arguments or (),
                                                strict=True,
                                            )
                                        )
                                        if binding.kind == "source_closure"
                                        else {},
                                        branch_environment,
                                        return_bindings=returned,
                                        parameter_bindings=parameter_bindings,
                                    )
                                    implicit = _dynamic_function_has_unmodeled_implicit_dispatch(
                                        function, branch_environment
                                    )
                                    if implicit and scanner._source_code_depth:
                                        raise DynamicImportCollectionError(
                                            f"{self.relative_path}:{node.lineno}: reconstructed source body "
                                            "has opaque implicit dispatch"
                                        )
                                    if not implicit:
                                        scanner._module_time_proven_scope_ids.add(id(function))
                                finally:
                                    scanner._active_module_function_invocation_states.pop()
                                    scanner._active_module_function_stack.pop()
                                branch_result = _join_dynamic_bindings(returned or (_DYNAMIC_NONE,))
                                branch_invoked = True
                finally:
                    scanner._active_module_environment = previous_active_environment
                    scanner._active_code_builtins = previous_builtins
                    scanner._source_code_depth = previous_code_depth
                    if pushed_target_module:
                        if self._source_function_module_stack[-1] != scanner.module_name:
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{node.lineno}: source module execution "
                                "scope was not balanced"
                            )
                        self._source_function_module_stack.pop()
                branch_states[scanner].append(
                    branch_environment if branch_invoked else dict(base_environment)
                )
                if branch_invoked:
                    branch_returns.append(branch_result)
                    valid_return = True

            for scanner, states in branch_states.items():
                if not states:
                    continue
                joined = scanner._join_environments(
                    states,
                    set().union(*(state.keys() for state in states)),
                )
                target_environment = base_environments[scanner]
                target_environment.clear()
                target_environment.update(joined)

            if not valid_return:
                return _DYNAMIC_OTHER
            return _join_dynamic_bindings(branch_returns)
        finally:
            if pushed_module:
                self._source_function_module_stack.pop()

    def _source_class_invocation_read_names(
        self,
        node: ast.Call,
        environment: Mapping[str, _DynamicImportBinding],
    ) -> set[str]:
        """Return roots read by source-known class methods invoked at this call site."""
        if self.source_bindings is None:
            return set()

        class_binding: _DynamicImportBinding | None = None
        method_names: set[str]
        if isinstance(node.func, ast.Name):
            class_binding = environment.get(node.func.id)
            method_names = {"__init__", "__new__"}
        elif isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            method_names = {node.func.attr, "__init__", "__new__"}
            if isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name):
                class_binding = environment.get(receiver.func.id)
            elif isinstance(receiver, ast.Name):
                class_binding = environment.get(receiver.id)
        else:
            return set()
        if class_binding is None:
            return set()

        names: set[str] = set()
        for source_name in _dynamic_source_class_origins(class_binding):
            source_module = source_name.rpartition(".")[0]
            if source_module == self.module_name:
                source_environment = environment
            else:
                source_environment = self.source_bindings._module_environment(source_module, ())
            if source_environment is None:
                continue
            definition = self.source_bindings._source_class_definition(
                source_name,
                current_module=source_module,
                current_environment=source_environment,
                stack=(),
            )
            if definition is None:
                continue
            _, class_node, _ = definition
            pending: list[ast.AST] = [
                method
                for method in class_node.body
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and method.name in method_names
            ]
            seen: set[int] = set()
            while pending:
                scope = pending.pop()
                if id(scope) in seen:
                    continue
                seen.add(id(scope))
                source_tree = self.source_bindings._module_tree(source_module)
                source_future_annotations = (
                    _future_annotations_enabled(source_tree) if source_tree is not None else False
                )
                reads, _, children = _dynamic_scope_read_dependencies(
                    scope,
                    future_annotations=source_future_annotations,
                )
                names.update(reads)
                pending.extend(children)
        return names

    def _remember_unmodeled_temporal_invocation(
        self,
        node: ast.AST,
        environment: Mapping[str, _DynamicImportBinding],
        scope_info: Mapping[str, set[str]],
        label: str,
    ) -> None:
        """Retain call-time namespace evidence for a module call the scanner cannot transfer."""
        self._source_code_opaque_effect = True
        if not (self._module_execution_active or self._active_module_function_stack):
            return
        if self._active_module_function_stack and self._active_module_environment is not None:
            module_environment = self._active_module_environment
        elif scope_info is self._module_scope_info:
            module_environment = environment
        else:
            # Class bodies execute during module initialization but have their own namespace.
            # Method bodies resolve importer globals in the module namespace.
            module_environment = self._module_environment
        read_names = {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
        }
        if isinstance(node, ast.Call):
            read_names.update(self._source_class_invocation_read_names(node, environment))
        observed_roots: set[str] = set()
        for name in self._observed_importer_binding_names:
            binding = module_environment.get(name, self._unknown_binding(name))
            namespace_owner = self._module_namespace_owner_resolution(binding, scope_info)
            is_source_namespace = namespace_owner.kind in {"selected", "unresolved"}
            if (
                name in read_names
                or name in _DYNAMIC_IMPORT_GUARDED_ROOTS
                or (
                    not is_source_namespace
                    and (
                        _is_guarded_importer_binding(binding)
                        or _dynamic_importer_origins(binding)
                        or _dynamic_unresolved_importer_origins(binding)
                        or _dynamic_temporal_callable_origins(binding)
                    )
                )
            ):
                observed_roots.add(name)
        observed_roots = frozenset(observed_roots)
        self._pending_temporal_invocations.append(
            (
                node,
                dict(module_environment),
                dict(self._importer_binding_revisions),
                observed_roots,
                label,
            )
        )

    def _deferred_scope_importer_names(
        self,
        deferred: _PendingDynamicImportScope,
        final_environment: Mapping[str, _DynamicImportBinding],
    ) -> frozenset[str]:
        """Resolve importer roots read by a deferred scope and known local callees."""
        relevant: set[str] = set()
        pending: list[ast.AST] = [deferred.node]
        seen: set[int] = set()
        while pending:
            scope = pending.pop()
            if id(scope) in seen:
                continue
            seen.add(id(scope))
            if len(seen) > 512:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{getattr(scope, 'lineno', 1)}: deferred source "
                    "dependency graph exceeds the bounded summary limit"
                )
            reads, calls, children = _dynamic_scope_read_dependencies(scope)
            pending.extend(children)
            for name in reads:
                before = deferred.environment_at_definition.get(name, self._unknown_binding(name))
                after = final_environment.get(name, self._unknown_binding(name))
                if (
                    name in _DYNAMIC_IMPORT_GUARDED_ROOTS
                    or name in self._observed_importer_binding_names
                    or _is_guarded_importer_binding(before)
                    or _is_guarded_importer_binding(after)
                    or _dynamic_import_namespace_origins(before)
                    or _dynamic_import_namespace_origins(after)
                ):
                    relevant.add(name)
            for call in calls:
                if not isinstance(call.func, ast.Name):
                    continue
                binding = final_environment.get(call.func.id)
                if binding is None:
                    binding = deferred.environment_at_definition.get(call.func.id)
                if binding is None:
                    continue
                alternatives = (
                    binding.items
                    if binding.kind == "union" and binding.items is not None
                    else (binding,)
                )
                has_source_function = any(item.kind == "source_function" for item in alternatives)
                for alternative in alternatives:
                    scanner = self
                    identity = alternative.origin_name
                    if alternative.kind in {"reconstructed_function", "source_closure"}:
                        if alternative.code_origin is None:
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{call.lineno}: source code origin is unavailable"
                            )
                        pending.append(alternative.code_origin.node)
                        relevant.update(self._observed_importer_binding_names)
                        relevant.update(_DYNAMIC_IMPORT_GUARDED_ROOTS)
                        continue
                    if alternative.kind == "other":
                        if self.source_context is None:
                            # The binding-only API has no selected source context
                            # for cross-module summaries. Keep every importer root
                            # relevant rather than guessing the callee's effects.
                            relevant.update(self._observed_importer_binding_names)
                            relevant.update(_DYNAMIC_IMPORT_GUARDED_ROOTS)
                            continue
                        if identity is None or not identity.startswith("polisyos."):
                            if has_source_function:
                                raise DynamicImportCollectionError(
                                    f"{self.relative_path}:{call.lineno}: deferred source function "
                                    "target has an opaque alternative; inventory is incomplete"
                                )
                            continue
                        if self.source_bindings is None:
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{call.lineno}: deferred source function "
                                "target lacks selected source bindings; inventory is incomplete"
                            )
                        resolved = self.source_bindings._source_function_definition(identity)
                        if resolved is None:
                            source_module = identity.rpartition(".")[0]
                            source_environment = self.source_bindings._module_environment(
                                source_module,
                                (),
                            )
                            class_definition = (
                                self.source_bindings._source_class_identity_definition(
                                    identity,
                                    current_module=source_module,
                                    current_environment=source_environment,
                                    stack=(),
                                )
                                if source_environment is not None
                                else None
                            )
                            if class_definition is not None:
                                if self.source_bindings._source_class_has_effect(
                                    identity,
                                    current_module=source_module,
                                    current_environment=source_environment,
                                    stack=(),
                                    unknown_is_effect=True,
                                ):
                                    # Escaping the class invalidates its mutable member
                                    # summary, not its still-bound source identity. With
                                    # unknown effects every tracked importer root matters.
                                    relevant.update(self._observed_importer_binding_names)
                                    relevant.update(_DYNAMIC_IMPORT_GUARDED_ROOTS)
                                    continue
                                relevant.update(
                                    self._source_class_invocation_read_names(
                                        call,
                                        {
                                            call.func.id: _DynamicImportBinding(
                                                "other",
                                                origin_name=identity,
                                            )
                                        },
                                    )
                                )
                                continue
                            if has_source_function:
                                raise DynamicImportCollectionError(
                                    f"{self.relative_path}:{call.lineno}: deferred source function "
                                    "target has an opaque alternative; inventory is incomplete"
                                )
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{call.lineno}: source-owned call target "
                                "is neither a selected function nor a selected class"
                            )
                        source_module, _source_path, _function = resolved
                        scanner = self._source_function_scanner_for(source_module, call)
                        symbol = identity.rpartition(".")[2]
                        source_binding = scanner._module_environment.get(symbol)
                        if (
                            source_binding is None
                            or source_binding.kind != "source_function"
                            or source_binding.origin_name is None
                        ):
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{call.lineno}: selected source function "
                                "binding changed during independent module analysis"
                            )
                        identity = source_binding.origin_name
                    elif alternative.kind != "source_function":
                        if has_source_function:
                            raise DynamicImportCollectionError(
                                f"{self.relative_path}:{call.lineno}: deferred source function "
                                "target has an opaque alternative; inventory is incomplete"
                            )
                        continue
                    if identity is None:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{call.lineno}: deferred source function "
                            "identity is missing; inventory is incomplete"
                        )
                    summary = scanner._module_function_summaries.get(identity)
                    if summary is None:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{call.lineno}: deferred source function "
                            "summary is unavailable; inventory is incomplete"
                        )
                    if scanner is self:
                        pending.append(summary.node)
        return frozenset(relevant)

    def _raise_for_unproven_temporal_invocations(
        self,
        final_environment: Mapping[str, _DynamicImportBinding],
        pending_scopes: Sequence[_PendingDynamicImportScope],
    ) -> None:
        """Fail closed when a call crosses a change to an observed importer root."""
        for deferred in pending_scopes:
            if id(deferred.node) in self._module_time_proven_scope_ids:
                continue
            mutated = [
                name
                for name in self._deferred_scope_importer_names(deferred, final_environment)
                if self._importer_binding_mutations.get(name, 0)
                > deferred.importer_binding_mutations.get(name, 0)
            ]
            if mutated:
                names = ", ".join(sorted(mutated))
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{getattr(deferred.node, 'lineno', 1)}: deferred source "
                    f"effects cross a proven importer rebind ({names}); inventory is incomplete"
                )
        for (
            node,
            call_environment,
            revisions_at_call,
            observed_roots_at_call,
            label,
        ) in self._pending_temporal_invocations:
            changed: list[str] = []
            unresolved: list[str] = []
            # The captured set already includes guarded and importer-bearing
            # roots present at invocation time, even when the call does not
            # syntactically read them. Do not add names discovered later in
            # module execution: they were not part of this call's namespace.
            for name in sorted(observed_roots_at_call):
                before = call_environment.get(name, self._unknown_binding(name))
                after = final_environment.get(name, self._unknown_binding(name))
                revision_changed = self._importer_binding_revisions.get(
                    name, 0
                ) != revisions_at_call.get(name, 0)
                if revision_changed or before != after:
                    changed.append(name)
                elif before.kind in {"unknown", "ambiguous"} and (
                    name in _DYNAMIC_IMPORT_GUARDED_ROOTS
                    or name in self._observed_importer_binding_names
                ):
                    unresolved.append(name)
            if changed or unresolved:
                names = sorted(set(changed + unresolved))
                detail = ", ".join(names) if names else "an unresolved guarded importer"
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{getattr(node, 'lineno', 1)}: {label} has an "
                    f"unproven module-time dynamic-import namespace ({detail}); inventory is incomplete"
                )

    def _source_function_parameter_bindings(
        self,
        function: ast.FunctionDef,
        call_node: ast.Call,
        argument_bindings: Sequence[_DynamicImportBinding],
        defaults: Mapping[str, _DynamicImportBinding],
    ) -> dict[str, _DynamicImportBinding] | None:
        """Bind source-known Python call shapes without executing user code."""
        if len(argument_bindings) != len(call_node.args) + len(call_node.keywords):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{call_node.lineno}: local function arguments are not source-bound"
            )

        positional: list[_DynamicImportBinding] = []
        keyword_values: dict[str, _DynamicImportBinding] = {}
        offset = 0
        for argument in call_node.args:
            value = argument_bindings[offset]
            offset += 1
            if not isinstance(argument, ast.Starred):
                positional.append(value)
                continue
            if value.kind in {"sequence", "iterable"} and value.items is not None:
                if value.kind == "iterable" and len(value.items) > 1:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{call_node.lineno}: starred local function argument order is unresolved"
                    )
                if len(positional) + len(value.items) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{call_node.lineno}: starred local function argument exceeds the bounded source limit"
                    )
                positional.extend(value.items)
                continue
            if value.kind == "string" and value.name is not None:
                if len(positional) + len(value.name) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{call_node.lineno}: starred string argument exceeds the bounded source limit"
                    )
                positional.extend(_dynamic_string_binding(character) for character in value.name)
                continue
            if value.kind == "mapping" and value.items is not None and value.origin_name is None:
                expanded_keys: list[_DynamicImportBinding] = []
                seen_keys: set[object] = set()
                for key in value.items:
                    key_known, key_value = _dynamic_binding_literal_key_value(key)
                    if not key_known:
                        raise DynamicImportCollectionError(
                            f"{self.relative_path}:{call_node.lineno}: starred mapping key is not source-known"
                        )
                    if key_value in seen_keys:
                        continue
                    seen_keys.add(key_value)
                    expanded_keys.append(key)
                if len(positional) + len(expanded_keys) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{call_node.lineno}: starred mapping argument exceeds the bounded source limit"
                    )
                positional.extend(expanded_keys)
                continue
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{call_node.lineno}: starred local function argument is not a source-bounded ordered iterable"
            )

        for keyword in call_node.keywords:
            value = argument_bindings[offset]
            offset += 1
            if keyword.arg is not None:
                name = keyword.arg
                if name in keyword_values:
                    return None
                keyword_values[name] = value
                continue
            if value.kind not in {"mapping", "namespace"} or (
                value.items is None or value.values is None
            ):
                if value.kind in {"sequence", "iterable", "string", "none", "boolean"}:
                    return None
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{call_node.lineno}: expanded local function keyword mapping is unresolved"
                )
            if len(value.items) > _DYNAMIC_COMPREHENSION_VALUE_LIMIT:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{call_node.lineno}: expanded local function keyword mapping exceeds the bounded source limit"
                )
            if len(value.items) != len(value.values):
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{call_node.lineno}: expanded local function keyword mapping has inconsistent source shape"
                )
            expanded_keywords: dict[str, _DynamicImportBinding] = {}
            for key, item in zip(value.items, value.values, strict=True):
                key_known, key_value = _dynamic_binding_literal_key_value(key)
                if not key_known:
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{call_node.lineno}: expanded local function keyword name is not source-known"
                    )
                if not isinstance(key_value, str):
                    return None
                expanded_keywords[key_value] = item
            if set(keyword_values).intersection(expanded_keywords):
                return None
            keyword_values.update(expanded_keywords)

        parameters: list[inspect.Parameter] = []
        for argument in function.args.posonlyargs:
            default = defaults.get(argument.arg, inspect.Parameter.empty)
            parameters.append(
                inspect.Parameter(
                    argument.arg,
                    inspect.Parameter.POSITIONAL_ONLY,
                    default=default,
                )
            )
        for argument in function.args.args:
            default = defaults.get(argument.arg, inspect.Parameter.empty)
            parameters.append(
                inspect.Parameter(
                    argument.arg,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=default,
                )
            )
        if function.args.vararg is not None:
            argument = function.args.vararg
            parameters.append(inspect.Parameter(argument.arg, inspect.Parameter.VAR_POSITIONAL))
        for argument in function.args.kwonlyargs:
            default = defaults.get(argument.arg, inspect.Parameter.empty)
            parameters.append(
                inspect.Parameter(
                    argument.arg,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=default,
                )
            )
        if function.args.kwarg is not None:
            argument = function.args.kwarg
            parameters.append(inspect.Parameter(argument.arg, inspect.Parameter.VAR_KEYWORD))

        try:
            signature = inspect.Signature(parameters)
            bound = signature.bind(*positional, **keyword_values)
        except (TypeError, ValueError):
            # Invalid call shapes do not execute the function body.
            return None
        bound.apply_defaults()

        result: dict[str, _DynamicImportBinding] = {}
        for parameter in parameters:
            name = parameter.name
            value = bound.arguments[name]
            if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
                result[name] = _dynamic_sequence_binding(
                    value,
                    sequence_type="tuple",
                )
            elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
                keys = tuple(_dynamic_string_binding(key) for key in value)
                result[name] = _dynamic_mapping_binding(keys, tuple(value.values()))
            else:
                if not isinstance(value, _DynamicImportBinding):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{call_node.lineno}: bound local function parameter is not a source binding"
                    )
                result[name] = value
        return result

    def _record_call(
        self,
        node: ast.Call,
        binding: _DynamicImportBinding,
        argument_bindings: Sequence[_DynamicImportBinding] = (),
    ) -> None:
        if binding.kind in {"source_code", "reconstructed_function", "source_closure"}:
            return
        if (
            binding.kind == "union"
            and binding.items
            and all(
                item.kind in {"source_function", "reconstructed_function", "source_closure"}
                for item in binding.items
            )
        ):
            return
        if binding.kind == "callable" and binding.name == "types.FunctionType":
            return
        if binding.kind == "callable" and binding.name in DYNAMIC_CALL_NAMES:
            resolved_call = str(binding.name)
        elif binding.kind == "callable" and binding.name in {
            "builtins.getattr",
            "builtins.globals",
            "builtins.locals",
            "builtins.vars",
            "mapping.get",
            "mapping.__getitem__",
            "mapping.keys",
            "mapping.values",
            "mapping.items",
            "mapping.pop",
            "mapping.setdefault",
            "mapping.update",
            "mapping.clear",
            "mapping.popitem",
        }:
            return
        elif binding.kind == "callable" and binding.name in {
            "builtins.eval",
            "builtins.exec",
        }:
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: source-visible dynamic code execution "
                f"through {binding.name} is unresolved"
            )
        elif _is_guarded_importer_binding(binding) or _dynamic_has_source_execution(binding):
            raise DynamicImportCollectionError(
                f"{self.relative_path}:{node.lineno}: dynamic importer binding is ambiguous or unresolved"
            )
        else:
            return

        first_argument_binding = argument_bindings[0] if argument_bindings else None
        resolved_call, pattern, allowed_targets = _call_pattern(
            node,
            call_name=resolved_call,
            first_argument_binding=first_argument_binding,
        )
        identity = f"{self.relative_path}:{node.lineno}:{resolved_call}:{pattern}"
        entry_id = f"dynamic-{_sha(identity)}"
        if entry_id not in self._recorded_entry_ids:
            self._recorded_entry_ids.add(entry_id)
            self.entries.append(
                {
                    "id": entry_id,
                    "pattern": pattern,
                    "source_file": self.relative_path,
                    "line": node.lineno,
                    "call": resolved_call,
                    "owner": _owner_for_path(self.source_path, relative_path=self.relative_path),
                    "target": pattern,
                    "verifier": "tools/quality/validation/decomposition_preflight.py::validate_dynamic_imports",
                    "allowed_targets": allowed_targets,
                    "notes": _dynamic_notes(self.relative_path, pattern, allowed_targets),
                }
            )
        site_identity = (id(node), resolved_call)
        if site_identity not in self._recorded_sink_sites:
            self._recorded_sink_sites.add(site_identity)
            self.sink_sites.append(_DynamicImportSite(node=node, call_name=resolved_call))

    def _import_binding(
        self, module: str, name: str | None, bound_name: str
    ) -> _DynamicImportBinding:
        if self.source_bindings is not None and (
            module.startswith(".") or module == "polisyos" or module.startswith("polisyos.")
        ):
            value = self.source_bindings.import_binding(
                module,
                name,
                current_module=self.module_name,
                is_package=self.source_path.name == "__init__.py",
            )
            if (
                module.startswith(".")
                and value.kind == "other"
                and (
                    bound_name in _DYNAMIC_IMPORT_GUARDED_ROOTS
                    or bound_name in _DYNAMIC_IMPORT_CALLABLE_NAMES
                )
            ):
                return self._unknown_binding(bound_name)
            return value
        if module in _DYNAMIC_TYPE_CHECKING_MODULES and (
            self._type_checking_namespace_unknown
            or module in self._type_checking_invalidated_modules
        ):
            return self._unknown_binding(bound_name)
        if module.startswith("."):
            if (
                bound_name in _DYNAMIC_IMPORT_GUARDED_ROOTS
                or bound_name in _DYNAMIC_IMPORT_CALLABLE_NAMES
            ):
                return self._unknown_binding(bound_name)
            return _DYNAMIC_OTHER
        binding = _dynamic_binding_for_import(module, name)
        if self.source_bindings is not None:
            binding = self.source_bindings._module_namespace_effect_binding(
                module,
                name,
                binding,
            )
        if binding.kind == "other" and (
            bound_name in _DYNAMIC_IMPORT_GUARDED_ROOTS
            or bound_name in _DYNAMIC_IMPORT_CALLABLE_NAMES
        ):
            return self._unknown_binding(bound_name)
        return binding

    def _process_statement(
        self,
        node: ast.stmt,
        environment: dict[str, _DynamicImportBinding],
        local_names: set[str],
        scope_info: Mapping[str, set[str]],
        pending: list[_PendingDynamicImportScope],
        closure_env: Mapping[str, _DynamicImportBinding],
    ) -> dict[str, _DynamicImportBinding]:
        if _dynamic_type_checking_namespace_reflection(node, environment):
            self._invalidate_type_checking_namespace_bindings(environment)
        self._invalidate_type_checking_modules(
            _dynamic_type_checking_module_effects(node, environment), environment
        )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if _dynamic_deferred_scope_namespace_reflection(node, environment):
                self._invalidate_type_checking_namespace_bindings(environment)
            self._invalidate_type_checking_modules(
                _dynamic_deferred_scope_module_effects(node, environment), environment
            )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            global_writes, nonlocal_writes = _dynamic_scope_cross_writes(node)
            self._register_deferred_scope_effects(
                global_writes, nonlocal_writes, environment, scope_info, closure_env
            )
            for expression in node.decorator_list:
                binding = self._expression_binding(expression, environment, pending, scope_info)
                self._reject_guarded_escape(binding, expression, "a function decorator")
                self._remember_unmodeled_temporal_invocation(
                    node, environment, scope_info, "implicit function decorator application"
                )
            defaults: dict[str, _DynamicImportBinding] = {}
            positional_parameters = (*node.args.posonlyargs, *node.args.args)
            default_offset = len(positional_parameters) - len(node.args.defaults)
            for index, expression in enumerate(node.args.defaults):
                binding = self._expression_binding(expression, environment, pending, scope_info)
                self._reject_guarded_escape(binding, expression, "a function default")
                defaults[positional_parameters[default_offset + index].arg] = binding
            for argument, expression in zip(
                node.args.kwonlyargs,
                node.args.kw_defaults,
                strict=True,
            ):
                if expression is not None:
                    binding = self._expression_binding(expression, environment, pending, scope_info)
                    self._reject_guarded_escape(binding, expression, "a function default")
                    defaults[argument.arg] = binding
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                *((node.args.vararg,) if node.args.vararg else ()),
                *((node.args.kwarg,) if node.args.kwarg else ()),
            ):
                if argument.annotation is not None:
                    self._check_annotation(
                        argument.annotation,
                        environment,
                        pending,
                        scope_info,
                        "a function annotation",
                    )
            if node.returns is not None:
                self._check_annotation(
                    node.returns,
                    environment,
                    pending,
                    scope_info,
                    "a function annotation",
                )
            if self._source_code_depth and scope_info is not self._module_scope_info:
                if node.decorator_list or node.args.defaults or any(node.args.kw_defaults):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: reconstructed nested callable "
                        "defaults or decorators are unsupported"
                    )
                reads, _, children = _dynamic_scope_read_dependencies(node)
                all_reads = set(reads)
                for child in children:
                    all_reads.update(_dynamic_scope_read_dependencies(child)[0])
                free = tuple(sorted(all_reads & scope_info.get("_source_lexical", set())))
                if not set(free) <= scope_info.get("_source_stable_cells", set()):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: reconstructed nested callable "
                        "has mutable or unproven closure cells"
                    )
                captures = tuple(environment[name] for name in free)
                if any(
                    value.kind in {"unknown", "ambiguous", "object", "mapping", "namespace"}
                    for value in captures
                ):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: reconstructed closure value is unresolved"
                    )
                origin = self._selected_code_origin(node, node, free_variables=free)
                environment[node.name] = _DynamicImportBinding(
                    "source_closure",
                    origin_name=origin.identity,
                    code_origin=origin,
                    globals_owner=self.module_name,
                    function_builtins=self._active_code_builtins,
                    closure_names=free,
                    source_arguments=captures,
                )
            elif scope_info is self._module_scope_info:
                identity = f"{self.relative_path}:{node.lineno}:{node.col_offset}"
                self._module_function_summaries[identity] = _DynamicImportFunctionSummary(
                    node=node,
                    defaults=defaults,
                )
                environment[node.name] = _DynamicImportBinding(
                    "source_function",
                    name=node.name,
                    origin_name=identity,
                )
            else:
                environment[node.name] = _DYNAMIC_OTHER
            pending.append(
                _PendingDynamicImportScope(
                    node,
                    environment.copy(),
                    dict(self._importer_binding_mutations),
                )
            )
            return environment
        if isinstance(node, ast.ClassDef):
            global_writes, nonlocal_writes = _dynamic_scope_cross_writes(node)
            self._register_deferred_scope_effects(
                global_writes, nonlocal_writes, environment, scope_info, closure_env
            )
            for expression in node.decorator_list:
                binding = self._expression_binding(expression, environment, pending, scope_info)
                self._reject_guarded_escape(binding, expression, "a class decorator")
                self._remember_unmodeled_temporal_invocation(
                    node, environment, scope_info, "implicit class decorator application"
                )
            for expression in node.bases:
                binding = self._expression_binding(expression, environment, pending, scope_info)
                self._reject_guarded_escape(binding, expression, "a class definition")
            for keyword in node.keywords:
                binding = self._expression_binding(keyword.value, environment, pending, scope_info)
                self._reject_guarded_escape(binding, keyword.value, "a class definition")
            source_tree = (
                self.source_bindings._module_tree(self.module_name)
                if self.source_bindings is not None and self.module_name is not None
                else None
            )
            if source_tree is not None and any(statement is node for statement in source_tree.body):
                environment[node.name] = replace(
                    _DYNAMIC_OTHER,
                    origin_name=f"{self.module_name}.{node.name}",
                )
            else:
                environment[node.name] = _DYNAMIC_OTHER
            eager_calls = _DefinitionTimeCallVisitor(future_annotations=self.future_annotations)
            eager_calls.visit(node)
            for call in eager_calls.calls:
                self._remember_unmodeled_temporal_invocation(
                    call,
                    environment,
                    scope_info,
                    "a deferred definition-time source scope",
                )
            pending.append(
                _PendingDynamicImportScope(
                    node,
                    environment.copy(),
                    dict(self._importer_binding_mutations),
                )
            )
            return environment
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                imported_module = alias.name if alias.asname else alias.name.split(".", 1)[0]
                value = self._import_binding(imported_module, None, bound_name)
                self._check_cross_scope_write(
                    ast.Name(id=bound_name, ctx=ast.Store()),
                    value,
                    environment,
                    scope_info,
                    node.lineno,
                )
                self._assign_target(
                    ast.Name(id=bound_name, ctx=ast.Store()),
                    value,
                    environment,
                    pending,
                    scope_info,
                )
            return environment
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                for name, value in tuple(environment.items()):
                    if value.guarded:
                        environment[name] = _DYNAMIC_AMBIGUOUS
                for name in _DYNAMIC_IMPORT_GUARDED_ROOTS:
                    unknown = self._unknown_binding(name)
                    self._note_importer_binding_write(
                        name, environment.get(name, self._unknown_binding(name)), unknown
                    )
                    environment[name] = unknown
                return environment
            module = ("." * node.level) + (node.module or "")
            for alias in node.names:
                bound_name = alias.asname or alias.name
                value = self._import_binding(module, alias.name, bound_name)
                self._check_cross_scope_write(
                    ast.Name(id=bound_name, ctx=ast.Store()),
                    value,
                    environment,
                    scope_info,
                    node.lineno,
                )
                self._assign_target(
                    ast.Name(id=bound_name, ctx=ast.Store()),
                    value,
                    environment,
                    pending,
                    scope_info,
                )
            return environment
        if isinstance(node, ast.Assign):
            if (
                self._source_instance_summary
                and self._source_summary_fields is not None
                and all(
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr not in self._source_summary_fields
                    for target in node.targets
                )
            ):
                return environment
            value = self._expression_binding(node.value, environment, pending, scope_info)
            if (
                scope_info is self._module_scope_info
                and self._module_execution_active
                and self.source_bindings is not None
                and self.module_name in self.source_bindings._selected_source_module_names()
                and isinstance(node.value, ast.Dict)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and _dynamic_is_source_lazy_export_map(
                    self.module_name,
                    node.targets[0].id,
                    node.value,
                    value,
                )
            ):
                value = replace(value, origin_name=f"{self.module_name}.{node.targets[0].id}")
            for target in node.targets:
                self._check_cross_scope_write(target, value, environment, scope_info, node.lineno)
                self._assign_target(target, value, environment, pending, scope_info)
            return environment
        if isinstance(node, ast.AnnAssign):
            self._check_annotation(
                node.annotation, environment, pending, scope_info, "an annotation"
            )
            if (
                self._source_instance_summary
                and self._source_summary_fields is not None
                and isinstance(node.target, ast.Attribute)
                and isinstance(node.target.value, ast.Name)
                and node.target.value.id == "self"
                and node.target.attr not in self._source_summary_fields
            ):
                return environment
            value = (
                self._expression_binding(node.value, environment, pending, scope_info)
                if node.value is not None
                else _DYNAMIC_UNKNOWN
            )
            if (
                node.value is not None
                and scope_info is self._module_scope_info
                and self._module_execution_active
                and self.source_bindings is not None
                and self.module_name in self.source_bindings._selected_source_module_names()
                and isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Dict)
                and _dynamic_is_source_lazy_export_map(
                    self.module_name,
                    node.target.id,
                    node.value,
                    value,
                )
            ):
                value = replace(value, origin_name=f"{self.module_name}.{node.target.id}")
            self._check_cross_scope_write(node.target, value, environment, scope_info, node.lineno)
            self._assign_target(node.target, value, environment, pending, scope_info)
            return environment
        if isinstance(node, ast.TypeAlias):
            value = self._expression_binding(node.value, environment, pending, scope_info)
            self._reject_guarded_escape(value, node.value, "a type alias")
            self._assign_target(node.name, _DYNAMIC_OTHER, environment, pending, scope_info)
            pending.append(
                _PendingDynamicImportScope(
                    node,
                    environment.copy(),
                    dict(self._importer_binding_mutations),
                )
            )
            return environment
        if isinstance(node, ast.NamedExpr):
            value = self._expression_binding(node.value, environment, pending, scope_info)
            self._assign_target(node.target, value, environment, pending, scope_info)
            return environment
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Yield | ast.YieldFrom) and node.value.value is not None:
                yielded = self._expression_binding(
                    node.value.value,
                    environment,
                    pending,
                    scope_info,
                )
                self._reject_guarded_escape(yielded, node.value, "yield")
                self._invalidate_source_class_effects((yielded,))
            else:
                self._expression_binding(node.value, environment, pending, scope_info)
            return environment
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._check_cross_scope_write(
                        target,
                        self._unknown_binding(target.id),
                        environment,
                        scope_info,
                        node.lineno,
                    )
                    unknown = self._unknown_binding(target.id)
                    if scope_info is self._module_scope_info or target.id in scope_info.get(
                        "globals", set()
                    ):
                        self._note_importer_binding_write(
                            target.id,
                            environment.get(target.id, self._unknown_binding(target.id)),
                            unknown,
                        )
                    environment[target.id] = unknown
                    if (
                        self._active_module_function_stack
                        and self._active_module_environment is not None
                        and target.id in scope_info.get("globals", set())
                    ):
                        self._active_module_environment[target.id] = environment[target.id]
                elif isinstance(target, ast.Attribute):
                    receiver = self._expression_binding(
                        target.value, environment, pending, scope_info
                    )
                    owner = self._module_namespace_owner(receiver, scope_info)
                    if owner is not None:
                        self._module_namespace_write(owner, target.attr, None)
                    else:
                        self._assign_target(
                            target, _DYNAMIC_OTHER, environment, pending, scope_info
                        )
                elif isinstance(target, ast.Subscript):
                    receiver = self._expression_binding(
                        target.value, environment, pending, scope_info
                    )
                    owner = self._module_namespace_owner(receiver, scope_info)
                    if owner is not None:
                        key = self._expression_binding(
                            target.slice, environment, pending, scope_info
                        )
                        key_known, key_value = _dynamic_binding_literal_key_value(key)
                        self._module_namespace_write(
                            owner,
                            key_value if key_known and isinstance(key_value, str) else None,
                            None,
                        )
                    else:
                        self._assign_target(
                            target,
                            _DYNAMIC_OTHER,
                            environment,
                            pending,
                            scope_info,
                            delete=True,
                        )
                else:
                    self._assign_target(target, _DYNAMIC_OTHER, environment, pending, scope_info)
            return environment
        if isinstance(node, ast.If):
            if (
                self._source_instance_summary
                and self._source_summary_fields is not None
                and self.source_bindings is not None
                and not self.source_bindings._summary_block_writes_relevant(
                    (*node.body, *node.orelse),
                    self._source_summary_fields,
                    self._source_summary_locals,
                )
            ):
                return environment
            condition = self._expression_binding(node.test, environment, pending, scope_info)
            if (
                condition.kind in {"unknown", "ambiguous", "object", "other"}
                and not condition.literal_key_known
            ):
                self._source_code_opaque_effect = True
            runtime_type_checking_branch = _type_checking_runtime_branch(
                node.test, bindings=self._type_checking_bindings(environment)
            )
            if runtime_type_checking_branch is not None:
                selected = node.body if runtime_type_checking_branch else node.orelse
                return self._scan_statements(
                    selected,
                    environment,
                    local_names,
                    scope_info,
                    pending,
                    closure_env,
                )
            known_branch = self._known_comprehension_condition(node.test, environment)
            if isinstance(node.test, ast.Constant) and isinstance(node.test.value, bool):
                # Ordinary source branches remain inventory candidates. Only a
                # source-proven TYPE_CHECKING sentinel above prunes a branch.
                known_branch = None
            if known_branch is not None:
                selected = node.body if known_branch else node.orelse
                return self._scan_statements(
                    selected,
                    environment,
                    local_names,
                    scope_info,
                    pending,
                    closure_env,
                )
            body_environment = self._refine_none_check_branch(node.test, environment, truthy=True)
            body_environment = self._refine_mapping_membership_branch(
                node.test, body_environment, truthy=True
            )
            body = self._scan_statements(
                node.body,
                body_environment,
                local_names,
                scope_info,
                pending,
                closure_env,
            )
            else_environment = self._refine_none_check_branch(node.test, environment, truthy=False)
            else_environment = self._refine_mapping_membership_branch(
                node.test, else_environment, truthy=False
            )
            otherwise = self._scan_statements(
                node.orelse,
                else_environment,
                local_names,
                scope_info,
                pending,
                closure_env,
            )
            if self._block_terminates(node.body):
                return otherwise
            if node.orelse and self._block_terminates(node.orelse):
                return body
            return self._join_environments((body, otherwise), local_names)
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            if isinstance(node, ast.While):
                self._expression_binding(node.test, environment, pending, scope_info)
                loop_value = _DYNAMIC_UNKNOWN
            else:
                iterable = self._expression_binding(node.iter, environment, pending, scope_info)
                loop_value = self._iterable_element_binding(iterable)
            body_env = environment.copy()
            if not isinstance(node, ast.While):
                self._check_cross_scope_write(
                    node.target,
                    loop_value,
                    body_env,
                    scope_info,
                    node.lineno,
                )
                self._assign_target(node.target, loop_value, body_env, pending, scope_info)
            body = self._scan_statements(
                node.body, body_env, local_names, scope_info, pending, closure_env
            )
            otherwise = self._scan_statements(
                node.orelse, environment.copy(), local_names, scope_info, pending, closure_env
            )
            return self._join_environments((environment, body, otherwise), local_names)
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                context = self._expression_binding(
                    item.context_expr, environment, pending, scope_info
                )
                self._reject_guarded_escape(
                    context, item.context_expr, "a context-manager boundary"
                )
                if item.optional_vars is not None:
                    self._check_cross_scope_write(
                        item.optional_vars,
                        _DYNAMIC_UNKNOWN,
                        environment,
                        scope_info,
                        node.lineno,
                    )
                    self._assign_target(
                        item.optional_vars, _DYNAMIC_UNKNOWN, environment, pending, scope_info
                    )
            return self._scan_statements(
                node.body, environment, local_names, scope_info, pending, closure_env
            )
        if isinstance(node, (ast.Try, ast.TryStar)):
            branches = [
                self._scan_statements(
                    node.body, environment.copy(), local_names, scope_info, pending, closure_env
                )
            ]
            for handler in node.handlers:
                branch = environment.copy()
                if handler.type is not None:
                    self._expression_binding(handler.type, environment, pending, scope_info)
                if handler.name:
                    branch[handler.name] = _DYNAMIC_UNKNOWN
                branches.append(
                    self._scan_statements(
                        handler.body, branch, local_names, scope_info, pending, closure_env
                    )
                )
            joined = self._join_environments(branches, local_names)
            joined = self._scan_statements(
                node.orelse, joined, local_names, scope_info, pending, closure_env
            )
            return self._scan_statements(
                node.finalbody, joined, local_names, scope_info, pending, closure_env
            )
        if isinstance(node, ast.Match):
            subject = self._expression_binding(node.subject, environment, pending, scope_info)
            branches = [environment.copy()]
            for case in node.cases:
                branch = environment.copy()
                self._bind_match_pattern(case.pattern, subject, branch, pending, scope_info)
                if case.guard is not None:
                    self._expression_binding(case.guard, branch, pending, scope_info)
                branches.append(
                    self._scan_statements(
                        case.body, branch, local_names, scope_info, pending, closure_env
                    )
                )
            return self._join_environments(branches, local_names)
        if isinstance(node, ast.Assert):
            self._expression_binding(node.test, environment, pending, scope_info)
            if node.msg is not None:
                self._expression_binding(node.msg, environment, pending, scope_info)
            return environment
        if isinstance(node, ast.Return):
            if node.value is not None:
                returned = self._expression_binding(node.value, environment, pending, scope_info)
                if _is_guarded_importer_binding(returned) or _dynamic_has_source_execution(
                    returned
                ):
                    raise DynamicImportCollectionError(
                        f"{self.relative_path}:{node.lineno}: guarded importer value escapes through a function return"
                    )
                self._invalidate_source_class_effects((returned,))
            else:
                returned = _DYNAMIC_NONE
            if self._active_function_returns:
                self._active_function_returns[-1].append(returned)
            return environment
        if isinstance(node, ast.Raise):
            for expression in (
                getattr(node, "exc", None),
                getattr(node, "cause", None),
            ):
                if expression is not None:
                    self._expression_binding(expression, environment, pending, scope_info)
            return environment
        if isinstance(node, ast.AugAssign):
            current = (
                self._lookup(node.target.id, environment)
                if isinstance(node.target, ast.Name)
                else self._expression_binding(node.target, environment, pending, scope_info)
            )
            value = self._expression_binding(node.value, environment, pending, scope_info)
            if isinstance(node.op, ast.BitOr) and current.kind in {"mapping", "namespace"}:
                module_owner = self._module_namespace_owner(current, scope_info)
                if module_owner is not None:
                    self._record_module_namespace_mapping_update(
                        module_owner,
                        value,
                        node.value,
                    )
            if current.kind == "mapping" or (
                current.kind == "sequence" and current.sequence_type != "tuple"
            ):
                self._invalidate_unmodeled_source_mapping_inputs(
                    (current, value),
                    environment,
                )
            joined = _join_dynamic_bindings((current, value))
            self._check_cross_scope_write(node.target, joined, environment, scope_info, node.lineno)
            self._assign_target(node.target, joined, environment, pending, scope_info)
            return environment
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.Pass, ast.Break, ast.Continue)):
            return environment

        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                self._expression_binding(child, environment, pending, scope_info)
        return environment

    @staticmethod
    def _pattern_names(pattern: ast.AST) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(pattern):
            if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                names.add(node.name)
            elif isinstance(node, ast.MatchMapping) and node.rest:
                names.add(node.rest)
        return names

    def _assign_match_capture(
        self,
        name: str,
        value: _DynamicImportBinding,
        pattern: ast.AST,
        environment: dict[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
    ) -> None:
        target = ast.Name(id=name, ctx=ast.Store())
        line = getattr(pattern, "lineno", 1)
        self._check_cross_scope_write(target, value, environment, scope_info, line)
        self._assign_target(target, value, environment, pending, scope_info)

    def _bind_match_pattern(
        self,
        pattern: ast.AST,
        value: _DynamicImportBinding,
        environment: dict[str, _DynamicImportBinding],
        pending: list[_PendingDynamicImportScope],
        scope_info: Mapping[str, set[str]],
    ) -> None:
        if isinstance(pattern, ast.MatchAs):
            if pattern.pattern is not None:
                self._bind_match_pattern(pattern.pattern, value, environment, pending, scope_info)
            if pattern.name is not None:
                self._assign_match_capture(
                    pattern.name,
                    value,
                    pattern,
                    environment,
                    pending,
                    scope_info,
                )
            return
        if isinstance(pattern, ast.MatchSequence):
            items = value.items if value.kind == "sequence" else None
            star_positions = [
                index
                for index, child in enumerate(pattern.patterns)
                if isinstance(child, ast.MatchStar)
            ]
            if items is not None and not star_positions and len(items) == len(pattern.patterns):
                children = tuple(zip(pattern.patterns, items, strict=True))
            elif items is not None and len(star_positions) == 1:
                star_index = star_positions[0]
                trailing_count = len(pattern.patterns) - star_index - 1
                if len(items) >= star_index + trailing_count:
                    middle_stop = len(items) - trailing_count if trailing_count else len(items)
                    children_list: list[tuple[ast.AST, _DynamicImportBinding]] = []
                    children_list.extend(
                        zip(
                            pattern.patterns[:star_index],
                            items[:star_index],
                            strict=True,
                        )
                    )
                    star_items = _dynamic_sequence_binding(items[star_index:middle_stop])
                    children_list.append(
                        (
                            pattern.patterns[star_index],
                            _dynamic_join_with_guarded_origin((value,), star_items),
                        )
                    )
                    if trailing_count:
                        children_list.extend(
                            zip(
                                pattern.patterns[star_index + 1 :],
                                items[middle_stop:],
                                strict=True,
                            )
                        )
                    children = tuple(children_list)
                else:
                    children = ()
            else:
                children = ()
            if children:
                for child_pattern, child_value in children:
                    self._bind_match_pattern(
                        child_pattern,
                        _dynamic_join_with_guarded_origin(
                            (value,),
                            child_value,
                            trusted_result=_dynamic_binding_is_proven_nonimporter(child_value),
                        ),
                        environment,
                        pending,
                        scope_info,
                    )
            elif value.guarded:
                for name in self._pattern_names(pattern):
                    self._assign_match_capture(
                        name,
                        _DYNAMIC_AMBIGUOUS,
                        pattern,
                        environment,
                        pending,
                        scope_info,
                    )
            return
        if isinstance(pattern, ast.MatchStar) and pattern.name is not None:
            self._assign_match_capture(
                pattern.name,
                value,
                pattern,
                environment,
                pending,
                scope_info,
            )
            return
        if value.guarded:
            for name in self._pattern_names(pattern):
                self._assign_match_capture(
                    name,
                    _DYNAMIC_AMBIGUOUS,
                    pattern,
                    environment,
                    pending,
                    scope_info,
                )

    def _join_environments(
        self,
        environments: Sequence[Mapping[str, _DynamicImportBinding]],
        local_names: set[str],
    ) -> dict[str, _DynamicImportBinding]:
        merged = dict(environments[0]) if environments else {}
        all_names = set().union(*(environment.keys() for environment in environments))
        for name in all_names | local_names:
            values = [
                environment.get(name, self._unknown_binding(name)) for environment in environments
            ]
            merged[name] = _join_dynamic_bindings(values)
        return merged

    def _join_expression_paths(
        self,
        destination: dict[str, _DynamicImportBinding],
        paths: Sequence[Mapping[str, _DynamicImportBinding]],
    ) -> None:
        """Join expression side effects across every possible short-circuit path."""
        if not paths:
            return
        names = set().union(*(path.keys() for path in paths))
        joined = self._join_environments(paths, names)
        destination.clear()
        destination.update(joined)

    @staticmethod
    def _block_terminates(statements: Sequence[ast.stmt]) -> bool:
        """Recognize direct terminal branches without interpreting general control flow."""
        if not statements:
            return False
        final = statements[-1]
        if isinstance(final, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        return (
            isinstance(final, ast.If)
            and bool(final.orelse)
            and _DynamicImportSourceScanner._block_terminates(final.body)
            and _DynamicImportSourceScanner._block_terminates(final.orelse)
        )

    def _scan_statements(
        self,
        statements: Sequence[ast.stmt],
        environment: dict[str, _DynamicImportBinding],
        local_names: set[str],
        scope_info: Mapping[str, set[str]],
        pending: list[_PendingDynamicImportScope],
        closure_env: Mapping[str, _DynamicImportBinding],
    ) -> dict[str, _DynamicImportBinding]:
        for statement in statements:
            environment = self._process_statement(
                statement, environment, local_names, scope_info, pending, closure_env
            )
            if scope_info is self._module_scope_info:
                self._module_environment = environment
        return environment

    def _scan_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
        parent_env: Mapping[str, _DynamicImportBinding],
        module_env: Mapping[str, _DynamicImportBinding],
        *,
        type_parameter_environment: Mapping[str, _DynamicImportBinding] | None = None,
        return_bindings: list[_DynamicImportBinding] | None = None,
        parameter_bindings: Mapping[str, _DynamicImportBinding] | None = None,
        final_environments: list[dict[str, _DynamicImportBinding]] | None = None,
    ) -> None:
        declaration_only = not self._active_module_function_stack
        previous_opaque_effect = self._source_code_opaque_effect
        body_nodes = [] if isinstance(node, ast.Lambda) else node.body
        local_names, global_names, nonlocal_names = _scope_local_bindings(body_nodes)
        inherited = dict(module_env)
        inherited.update(parent_env)
        pending: list[_PendingDynamicImportScope] = []
        if not isinstance(node, ast.Lambda):
            self._scan_type_parameter_fields(
                node,
                inherited if type_parameter_environment is None else type_parameter_environment,
                pending,
            )
        environment = inherited
        scope_info: dict[str, set[str]] = {
            "globals": global_names,
            "nonlocals": nonlocal_names,
            "_effectful": set(),
        }
        if self._source_code_depth:
            parameter_names = {
                argument.arg
                for argument in (
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                    *((node.args.vararg,) if node.args.vararg else ()),
                    *((node.args.kwarg,) if node.args.kwarg else ()),
                )
            }
            scope_info["_source_lexical"] = local_names | parameter_names | set(parent_env)
            scope_info["_source_stable_cells"] = (parameter_names - local_names) | set(parent_env)
            if nonlocal_names:
                raise DynamicImportCollectionError(
                    f"{self.relative_path}:{node.lineno}: reconstructed nonlocal cells are unsupported"
                )
        for name in global_names:
            environment[name] = self._lookup(name, module_env)
        for name in nonlocal_names:
            environment[name] = parent_env.get(name, self._unknown_binding(name))
        for name in local_names:
            environment[name] = self._unknown_binding(name)
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
            *((node.args.vararg,) if node.args.vararg else ()),
            *((node.args.kwarg,) if node.args.kwarg else ()),
        ):
            if parameter_bindings is not None and argument.arg in parameter_bindings:
                environment[argument.arg] = parameter_bindings[argument.arg]
            else:
                environment[argument.arg] = self._unknown_binding(argument.arg)
        if self._source_instance_summary and not isinstance(node, ast.Lambda):
            positional = (*node.args.posonlyargs, *node.args.args)
            default_offset = len(positional) - len(node.args.defaults)
            for index, default in enumerate(node.args.defaults):
                argument = positional[default_offset + index]
                if parameter_bindings is None or argument.arg not in parameter_bindings:
                    environment[argument.arg] = self._expression_binding(
                        default,
                        dict(module_env),
                        pending,
                        scope_info,
                    )
            for argument, default in zip(
                node.args.kwonlyargs,
                node.args.kw_defaults,
                strict=True,
            ):
                if default is not None and (
                    parameter_bindings is None or argument.arg not in parameter_bindings
                ):
                    environment[argument.arg] = self._expression_binding(
                        default,
                        dict(module_env),
                        pending,
                        scope_info,
                    )
        if return_bindings is not None:
            self._active_function_returns.append(return_bindings)
        try:
            if isinstance(node, ast.Lambda):
                returned = self._expression_binding(
                    node.body,
                    environment,
                    pending,
                    {"globals": global_names, "nonlocals": nonlocal_names},
                )
                self._reject_guarded_escape(returned, node.body, "a lambda implicit return")
                if return_bindings is not None:
                    return_bindings.append(returned)
                final_env = environment
            else:
                final_env = self._scan_statements(
                    body_nodes,
                    environment,
                    local_names,
                    scope_info,
                    pending,
                    parent_env,
                )
                if return_bindings is not None and not self._block_terminates(body_nodes):
                    return_bindings.append(_DYNAMIC_NONE)
        finally:
            if return_bindings is not None:
                self._active_function_returns.pop()
        if final_environments is not None:
            final_environments.append(final_env)
        for deferred in pending:
            scope = deferred.node
            child_parent = self._join_environments(
                (deferred.environment_at_definition, final_env), local_names
            )
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._scan_function(scope, child_parent, module_env)
            elif isinstance(scope, ast.ClassDef):
                self._scan_class(scope, child_parent, module_env)
            elif isinstance(scope, ast.Lambda):
                self._scan_function(scope, child_parent, module_env)
            elif isinstance(scope, ast.TypeAlias):
                child_parent = self._join_environments(
                    (deferred.environment_at_definition, final_env), local_names
                )
                self._scan_type_parameter_fields(scope, child_parent, pending)
        if declaration_only:
            # An uninvoked declaration's unknown effects do not mutate the module.
            # Its own later reconstructed call still sees effects earlier in that body.
            self._source_code_opaque_effect = previous_opaque_effect

    def _scan_class(
        self,
        node: ast.ClassDef,
        closure_env: Mapping[str, _DynamicImportBinding],
        module_env: Mapping[str, _DynamicImportBinding],
    ) -> None:
        local_names, global_names, nonlocal_names = _scope_local_bindings(node.body)
        environment = dict(module_env)
        environment.update(closure_env)
        for name in global_names:
            environment[name] = self._lookup(name, module_env)
        for name in nonlocal_names:
            environment[name] = closure_env.get(name, self._unknown_binding(name))
        pending: list[_PendingDynamicImportScope] = []
        self._scan_type_parameter_fields(node, environment, pending)
        for name in local_names:
            environment[name] = self._unknown_binding(name)
        class_scope_info: dict[str, set[str]] = {
            "globals": global_names,
            "nonlocals": nonlocal_names,
            "_effectful": set(),
            "_class": set(),
        }
        class_environment = self._scan_statements(
            node.body,
            environment,
            local_names,
            class_scope_info,
            pending,
            closure_env,
        )
        for name in local_names:
            self._reject_guarded_escape(
                class_environment.get(name, self._unknown_binding(name)),
                node,
                "the class namespace",
            )
        for deferred in pending:
            scope = deferred.node
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Methods do not close over class attributes.
                type_parameter_environment = self._join_environments(
                    (deferred.environment_at_definition, class_environment), local_names
                )
                self._scan_function(
                    scope,
                    closure_env,
                    module_env,
                    type_parameter_environment=type_parameter_environment,
                )
            elif isinstance(scope, ast.ClassDef):
                child_parent = self._join_environments(
                    (deferred.environment_at_definition, closure_env), local_names
                )
                self._scan_class(scope, child_parent, module_env)
            elif isinstance(scope, ast.Lambda):
                self._scan_function(scope, closure_env, module_env)
            elif isinstance(scope, ast.TypeAlias):
                child_parent = self._join_environments(
                    (deferred.environment_at_definition, class_environment), local_names
                )
                self._scan_type_parameter_fields(scope, child_parent, pending)


def collect_dynamic_imports() -> list[dict[str, Any]]:
    paths = _dynamic_source_paths("src", "tools", "apps", "packages")
    # This invocation owns one complete, byte-pinned source context. There is no
    # cross-call cache: any member or path-set change is reread before pruning.
    source_context = _dynamic_read_source_context(paths)
    source_bindings = _DynamicImportSourceBindings(paths, source_context=source_context)
    local_context = replace(source_context, type_checking_effects=())
    first_entries: list[dict[str, Any]] = []
    shared_effect_sources: dict[str, set[str]] = {}
    for member in source_context.members:
        scanner = _DynamicImportSourceScanner(
            member.path,
            relative_path=member.relative_path,
            source_bindings=source_bindings,
            source_context=local_context,
        )
        first_entries.extend(scanner.scan(member.tree))
        for module in scanner._type_checking_invalidated_modules:
            shared_effect_sources.setdefault(module, set()).add(member.relative_path)

    shared_class_effects = frozenset(source_bindings.invalidated_source_classes)
    shared_namespace_effects = source_bindings.module_namespace_effects()
    shared_source_mapping_effects = frozenset(source_bindings._source_mapping_effects)
    if (
        not shared_effect_sources
        and not shared_class_effects
        and not shared_namespace_effects
        and not shared_source_mapping_effects
    ):
        entries = first_entries
    else:
        # A different selected source module may change the process-shared
        # typing module before this module evaluates its guard. Keep effect
        # origins so a same-file, later mutation does not rewrite an earlier
        # scalar snapshot; do not guess cross-module reachability or ordering.
        effects = tuple(
            (module, frozenset(source_paths))
            for module, source_paths in sorted(shared_effect_sources.items())
        )
        complete_context = replace(
            source_context,
            type_checking_effects=effects,
            source_class_effects=shared_class_effects,
            module_namespace_effects=shared_namespace_effects,
            source_mapping_effects=shared_source_mapping_effects,
        )
        complete_bindings = _DynamicImportSourceBindings(
            paths,
            source_context=complete_context,
        )
        entries = []
        for member in source_context.members:
            entries.extend(
                _DynamicImportSourceScanner(
                    member.path,
                    relative_path=member.relative_path,
                    source_bindings=complete_bindings,
                    source_context=complete_context,
                ).scan(member.tree)
            )
    return sorted(entries, key=lambda item: (item["source_file"], item["line"], item["pattern"]))


def _dynamic_notes(source_file: str, pattern: str, allowed_targets: Sequence[str]) -> str:
    if allowed_targets:
        return "Fail-closed whitelist: every target must resolve."
    if "entry_points" in pattern or pattern.startswith("group:"):
        return "Entry-point group is registered; no in-repo target is declared in pyproject."
    if "module_name" in pattern or "args.module" in pattern:
        return "User/plugin supplied module name; call site is inventoried for review."
    if source_file.startswith("tools/"):
        return "Tooling dynamic import; inventoried but no decomposition target."
    return "Dynamic pattern has no static in-repo target."


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: Sequence[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(_toml_quote(value) for value in values) + "]"


DYNAMIC_IMPORT_REVIEW_FIELDS = ("review_owner", "reviewed_at", "review_expires")


def _valid_dynamic_import_review_field(field: str, value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if field == "review_owner":
        return True
    if field not in {"reviewed_at", "review_expires"}:
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value


def _validated_dynamic_import_review_metadata(
    metadata: Mapping[str, object],
) -> dict[str, str]:
    expected_fields = set(DYNAMIC_IMPORT_REVIEW_FIELDS)
    observed_fields = set(metadata)
    if observed_fields != expected_fields:
        missing = sorted(expected_fields - observed_fields)
        unexpected = sorted(observed_fields - expected_fields)
        raise DynamicImportReviewMetadataError(
            f"review metadata fields differ from contract: missing={missing!r}, "
            f"unexpected={unexpected!r}"
        )
    invalid = [
        field
        for field in DYNAMIC_IMPORT_REVIEW_FIELDS
        if not _valid_dynamic_import_review_field(field, metadata[field])
    ]
    if invalid:
        raise DynamicImportReviewMetadataError(f"review metadata fields are malformed: {invalid!r}")
    return {
        field: metadata[field]
        for field in DYNAMIC_IMPORT_REVIEW_FIELDS
        if isinstance(metadata[field], str)
    }


def render_dynamic_imports_toml(
    entries: Sequence[Mapping[str, Any]],
    *,
    review_metadata: Mapping[str, object] | None = None,
) -> str:
    """Render discovered rows separately from owner-supplied review metadata."""
    validated_review = (
        _validated_dynamic_import_review_metadata(review_metadata)
        if review_metadata is not None
        else None
    )
    lines = [
        "[dynamic_imports]",
        "version = 1",
        'status = "fail_closed"',
        'owner = "team-architecture"',
        'phase = "3A"',
    ]
    if validated_review is not None:
        lines.extend(
            f"{field} = {_toml_quote(validated_review[field])}"
            for field in DYNAMIC_IMPORT_REVIEW_FIELDS
        )
    lines.extend(
        [
            'exception_policy = "Dynamic imports must declare owner, target or allowed_targets, verifier, and notes; unresolved plugin slots require a dated owner review."',
            'issue = "docs/plans/archive/2026-05-07-repository-best-in-class-remediation-master-plan.md#phase-65---exception-and-sunset-cleanup"',
            'adr = "docs/adr/repository-structure-0141-dynamic-import-registry.md"',
            'notes = "Every allowed target must resolve; empty target lists are audited dynamic/plugin slots."',
            'extension_points = "architecture/extension_points.toml"',
            'new_entry_required_fields = ["owner", "target_or_allowed_targets", "verifier"]',
            'target_semantics = "target names the intended import, extension point, or builtin loader; allowed_targets lists concrete importable modules."',
            'verifier_semantics = "verifier names the gate, smoke test, or owner review that proves the dynamic edge remains intentional."',
            "",
        ]
    )
    for entry in entries:
        lines.extend(
            [
                "[[pattern]]",
                f"id = {_toml_quote(str(entry['id']))}",
                f"pattern = {_toml_quote(str(entry['pattern']))}",
                f"source_file = {_toml_quote(str(entry['source_file']))}",
                f"line = {int(entry['line'])}",
                f"call = {_toml_quote(str(entry['call']))}",
                f"owner = {_toml_quote(str(entry['owner']))}",
                f"target = {_toml_quote(str(entry['target']))}",
                f"verifier = {_toml_quote(str(entry['verifier']))}",
                f"allowed_targets = {_toml_array([str(item) for item in entry['allowed_targets']])}",
                f"notes = {_toml_quote(str(entry['notes']))}",
                "",
            ]
        )
    return "\n".join(lines)


def _read_dynamic_import_review_metadata(path: Path) -> dict[str, object] | None:
    try:
        registry_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as error:
        raise DynamicImportReviewMetadataError(
            f"cannot read existing review metadata from {path}: {type(error).__name__}: {error}"
        ) from error
    try:
        data = tomllib.loads(registry_text)
    except tomllib.TOMLDecodeError as error:
        raise DynamicImportReviewMetadataError(
            f"cannot parse existing dynamic import registry: {error}"
        ) from error
    header = data.get("dynamic_imports")
    if not isinstance(header, dict):
        return None
    present_fields = set(DYNAMIC_IMPORT_REVIEW_FIELDS) & set(header)
    if not present_fields:
        return None
    metadata = {field: header[field] for field in DYNAMIC_IMPORT_REVIEW_FIELDS if field in header}
    return _validated_dynamic_import_review_metadata(metadata)


def _render_dynamic_import_registry(
    entries: Sequence[Mapping[str, Any]],
    *,
    path: Path,
) -> str:
    return render_dynamic_imports_toml(
        entries,
        review_metadata=_read_dynamic_import_review_metadata(path),
    )


def collect_pickle_inventory() -> dict[str, Any]:
    call_sites: list[dict[str, Any]] = []
    for path in _iter_text_files("src", "tools"):
        if path.suffix != ".py":
            continue
        for line_no, line in enumerate(_read_text(path).splitlines(), start=1):
            matches = [pattern for pattern in PICKLE_PATTERNS if pattern in line]
            if matches:
                call_sites.append(
                    {
                        "path": _rel(path),
                        "line": line_no,
                        "patterns": sorted(matches),
                        "text": line.strip(),
                    }
                )
    artifact_roots = [
        REPO_ROOT / ".polisyos",
        REPO_ROOT / "tests" / "fixtures",
        CHECKPOINT_FIXTURE_ROOT,
    ]
    artifacts: list[dict[str, Any]] = []
    for root in artifact_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix in {".pkl", ".pickle", ".joblib", ".ckpt"}:
                artifacts.append({"path": _rel(path), "bytes": path.stat().st_size})
    return {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "call_sites": call_sites,
        "live_artifacts": artifacts,
        "canonical_fixture_root": _rel(CHECKPOINT_FIXTURE_ROOT),
    }


def _base_names(base: ast.expr) -> set[str]:
    names: set[str] = set()
    try:
        rendered = ast.unparse(base)
    except Exception:
        rendered = ""
    if rendered:
        names.add(rendered)
        names.add(rendered.rsplit(".", 1)[-1])
    if isinstance(base, ast.Name):
        names.add(base.id)
    elif isinstance(base, ast.Attribute):
        names.add(base.attr)
    return names


def collect_pydantic_models(paths: Sequence[Path]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for path in paths:
        tree = _parse_python(path)
        if tree is None:
            continue
        module_fqn = module_fqn_from_path(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = (
                set().union(*(_base_names(base) for base in node.bases)) if node.bases else set()
            )
            if "BaseModel" in base_names:
                models.append(
                    {
                        "fqn": f"{module_fqn}.{node.name}",
                        "module": module_fqn,
                        "name": node.name,
                        "source_file": _rel(path),
                        "line": node.lineno,
                    }
                )
    return sorted(models, key=lambda item: item["fqn"])


def collect_registration_audit(paths: Sequence[Path]) -> list[dict[str, Any]]:
    registrations: list[dict[str, Any]] = []
    for path in paths:
        for line_no, line in enumerate(_read_text(path).splitlines(), start=1):
            matches = [pattern for pattern in REGISTRATION_PATTERNS if pattern in line]
            if matches:
                registrations.append(
                    {
                        "source_file": _rel(path),
                        "line": line_no,
                        "patterns": sorted(matches),
                        "text": line.strip(),
                    }
                )
    return registrations


def collect_openapi_model_usage(models: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    schema_path = REPO_ROOT / "schemas" / "runtime_api_v1.openapi.json"
    if not schema_path.exists():
        return []
    schema_text = schema_path.read_text(encoding="utf-8")
    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError:
        schema = {}
    defs = set(schema.get("components", {}).get("schemas", {})) | set(schema.get("$defs", {}))
    usages: list[dict[str, Any]] = []
    for model in models:
        name = str(model["name"])
        fqn = str(model["fqn"])
        hits: list[str] = []
        if fqn in schema_text:
            hits.append("fqn")
        if name in defs:
            hits.append("schema_key")
        elif name in schema_text:
            hits.append("name")
        usages.append({"model_fqn": fqn, "schema_hits": hits})
    return usages


def collect_external_importers(
    move_map: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    source_fqns = [str(item["source_fqn"]) for item in move_map]
    importers: dict[str, list[dict[str, Any]]] = {fqn: [] for fqn in source_fqns}
    parent_leaf = {fqn: fqn.rsplit(".", 1) for fqn in source_fqns}
    for path in _iter_text_files(*AUDIT_SCOPES):
        rel_path = _rel(path)
        if rel_path == "tools/quality/validation/decomposition_preflight.py":
            continue
        text = _read_text(path)
        for fqn in source_fqns:
            source_path = next(
                str(item["source_path"]) for item in move_map if str(item["source_fqn"]) == fqn
            )
            if rel_path == source_path:
                continue
            if fqn in text:
                lines = [
                    index for index, line in enumerate(text.splitlines(), start=1) if fqn in line
                ]
                for line_no in lines:
                    importers[fqn].append(
                        {"path": rel_path, "line": line_no, "kind": "literal_fqn"}
                    )
        if path.suffix != ".py":
            continue
        tree = _parse_python(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for fqn, (parent, leaf) in parent_leaf.items():
                    if node.module == parent and any(alias.name == leaf for alias in node.names):
                        importers[fqn].append(
                            {
                                "path": rel_path,
                                "line": node.lineno,
                                "kind": "from_parent_import_leaf",
                            }
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in importers:
                        importers[alias.name].append(
                            {"path": rel_path, "line": node.lineno, "kind": "import_module"}
                        )
    for fqn in importers:
        seen: set[tuple[str, int, str]] = set()
        deduped: list[dict[str, Any]] = []
        for item in importers[fqn]:
            key = (str(item["path"]), int(item["line"]), str(item["kind"]))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        importers[fqn] = sorted(
            deduped, key=lambda item: (item["path"], item["line"], item["kind"])
        )
    return importers


class _PublicSurfaceBindingVisitor(ast.NodeVisitor):
    """Find names rebound by one module-scope statement without entering callables."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.names.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        for child in node.body:
            self.visit(child)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


def _public_surface_definition_record(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    *,
    name: str,
    module: str,
    line: int,
) -> dict[str, Any]:
    if isinstance(node, ast.ClassDef):
        bases = (
            sorted(set().union(*(_base_names(base) for base in node.bases))) if node.bases else []
        )
        return {
            "kind": "class",
            "name": name,
            "fqn": f"{module}.{name}",
            "bases": bases,
            "pydantic": "BaseModel" in bases,
            "line": line,
        }
    return {
        "kind": "function" if isinstance(node, ast.FunctionDef) else "async_function",
        "name": name,
        "fqn": f"{module}.{name}",
        "signature": _signature(node),
        "line": line,
    }


def _collect_public_surface_bindings(
    module: str,
    tree: ast.Module,
    bindings: dict[tuple[str, str], tuple[str, object, int]],
    *,
    is_package: bool,
) -> None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[(module, node.name)] = ("definition", node, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            imported_module = _runtime_relative_import(
                module, node.module, node.level, is_package=is_package
            )
            for alias in node.names:
                if alias.name != "*":
                    local_name = alias.asname or alias.name
                    bindings[(module, local_name)] = (
                        "import",
                        (imported_module, alias.name),
                        node.lineno,
                    )
        else:
            visitor = _PublicSurfaceBindingVisitor()
            visitor.visit(node)
            for name in visitor.names:
                bindings[(module, name)] = ("unknown", None, node.lineno)


def _resolve_public_surface_definition(
    module: str,
    name: str,
    bindings: Mapping[tuple[str, str], tuple[str, object, int]],
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None:
    key = (module, name)
    if key in seen:
        return None
    binding = bindings.get(key)
    if binding is None:
        return None
    kind, value, _ = binding
    if kind == "definition" and isinstance(
        value,
        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
    ):
        return value
    if kind == "import" and isinstance(value, tuple) and len(value) == 2:
        target_module, target_name = value
        if isinstance(target_module, str) and isinstance(target_name, str):
            return _resolve_public_surface_definition(
                target_module,
                target_name,
                bindings,
                seen | {key},
            )
    return None


def _public_surface_module_objects(
    module: str,
    tree: ast.Module,
    bindings: Mapping[tuple[str, str], tuple[str, object, int]],
) -> tuple[list[str], list[dict[str, Any]]]:
    exports = _literal_all(tree)
    objects: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                objects.append(
                    _public_surface_definition_record(
                        node,
                        name=node.name,
                        module=module,
                        line=node.lineno,
                    )
                )
    for name in exports:
        if name.startswith("_"):
            continue
        binding = bindings.get((module, name))
        if binding is None or binding[0] != "import":
            continue
        definition = _resolve_public_surface_definition(module, name, bindings)
        if definition is not None:
            objects.append(
                _public_surface_definition_record(
                    definition,
                    name=name,
                    module=module,
                    line=binding[2],
                )
            )
    objects.sort(key=lambda item: item["line"])
    return exports, objects


def collect_public_surface_snapshot() -> dict[str, Any]:
    """Snapshot public definitions and statically resolved exported aliases."""
    packages: list[dict[str, Any]] = []
    root = SRC_ROOT / "polisyos"
    module_sources: dict[str, tuple[Path, ast.Module]] = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = _parse_python(path)
        if tree is not None:
            module_sources[module_fqn_from_path(path)] = (path, tree)

    bindings: dict[tuple[str, str], tuple[str, object, int]] = {}
    for module, (path, tree) in module_sources.items():
        _collect_public_surface_bindings(
            module, tree, bindings, is_package=path.name == "__init__.py"
        )

    for package_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if not (package_dir / "__init__.py").exists():
            continue
        package = f"polisyos.{package_dir.name}"
        modules: list[dict[str, Any]] = []
        for module_fqn, (path, tree) in sorted(module_sources.items()):
            if not path.is_relative_to(package_dir):
                continue
            exports, objects = _public_surface_module_objects(module_fqn, tree, bindings)
            if exports or objects:
                modules.append(
                    {
                        "module": module_fqn,
                        "source_file": _rel(path),
                        "__all__": exports,
                        "objects": objects,
                    }
                )
        packages.append({"package": package, "modules": modules})
    return {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "packages": packages,
    }


def _literal_all(tree: ast.Module) -> list[str]:
    exports: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            continue
        if isinstance(node.value, (ast.Tuple, ast.List)):
            for item in node.value.elts:
                literal = _literal_string(item)
                if literal is not None:
                    exports.append(literal)
    return sorted(exports)


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        return f"({ast.unparse(node.args)})"
    except Exception:
        return "()"


def collect_schema_baseline() -> dict[str, Any]:
    paths = [REPO_ROOT / "schemas" / "runtime_api_v1.openapi.json"]
    schema_entries: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
        defs = sorted(
            set(payload.get("$defs", {})) | set(payload.get("components", {}).get("schemas", {}))
        )
        schema_entries.append(
            {
                "path": _rel(path),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "defs_keys": defs,
            }
        )
    return {"version": 1, "generated_at": datetime.now(UTC).isoformat(), "schemas": schema_entries}


def _resolve_relative_import(current_module: str, module: str | None, level: int) -> str:
    if level == 0:
        return module or ""
    current_parts = current_module.split(".")
    if current_parts[-1] != "__init__":
        current_parts = current_parts[:-1]
    base = current_parts[: max(0, len(current_parts) - level + 1)]
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def _runtime_relative_import(
    current_module: str,
    module: str | None,
    level: int,
    *,
    is_package: bool,
) -> str:
    """Resolve a relative import using the source path's package identity."""
    if level == 0:
        return module or ""
    current_parts = current_module.split(".")
    if not is_package:
        current_parts = current_parts[:-1]
    base = current_parts[: max(0, len(current_parts) - level + 1)]
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def _callable_definitions(
    tree: ast.Module,
    module: str,
) -> tuple[dict[tuple[str, str, int, int], ast.FunctionDef | ast.AsyncFunctionDef], set[str]]:
    """Index every function definition by module, lexical name, and source identity."""
    functions: dict[tuple[str, str, int, int], ast.FunctionDef | ast.AsyncFunctionDef] = {}
    classes: set[str] = set()

    def walk(statements: Sequence[ast.stmt], prefix: str = "") -> None:
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}.{statement.name}" if prefix else statement.name
                identity = (module, name, statement.lineno, statement.col_offset)
                functions[identity] = statement
                walk(statement.body, name)
            elif isinstance(statement, ast.ClassDef):
                name = f"{prefix}.{statement.name}" if prefix else statement.name
                classes.add(name)
                walk(statement.body, name)
            elif isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While)):
                walk(statement.body, prefix)
                walk(statement.orelse, prefix)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                walk(statement.body, prefix)
            elif isinstance(statement, (ast.Try, ast.TryStar)):
                walk(statement.body, prefix)
                walk(statement.orelse, prefix)
                walk(statement.finalbody, prefix)
                for handler in statement.handlers:
                    walk(handler.body, prefix)
            elif isinstance(statement, ast.Match):
                for case in statement.cases:
                    walk(case.body, prefix)

    walk(tree.body)
    return functions, classes


def _binding_names(target: ast.AST) -> set[str]:
    """Return names assigned by an assignment target."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return (
            set().union(*(_binding_names(item) for item in target.elts)) if target.elts else set()
        )
    if isinstance(target, ast.Starred):
        return _binding_names(target.value)
    return set()


def _binding_target_owner_names(target: ast.AST) -> set[str]:
    """Return names owning attribute or subscript targets in an assignment."""
    if isinstance(target, (ast.Tuple, ast.List)):
        return (
            set().union(*(_binding_target_owner_names(item) for item in target.elts))
            if target.elts
            else set()
        )
    if isinstance(target, ast.Starred):
        return _binding_target_owner_names(target.value)
    if isinstance(target, (ast.Attribute, ast.Subscript)):
        return _expression_owner_names(target.value)
    return set()


def _expression_owner_names(node: ast.AST) -> set[str]:
    """Find a lexical name owning a stored attribute or subscript value."""
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        return _expression_owner_names(node.value)
    return set()


def _pattern_binding_names(pattern: ast.pattern) -> set[str]:
    """Return captured names from a structural-match pattern."""
    if isinstance(pattern, ast.MatchAs):
        names = {pattern.name} if pattern.name else set()
        return names | (_pattern_binding_names(pattern.pattern) if pattern.pattern else set())
    if isinstance(pattern, ast.MatchStar):
        return {pattern.name} if pattern.name else set()
    if isinstance(pattern, ast.MatchMapping):
        names = {pattern.rest} if pattern.rest else set()
        for child in pattern.patterns:
            names.update(_pattern_binding_names(child))
        return names
    if isinstance(pattern, ast.MatchClass):
        children = [*pattern.patterns, *pattern.kwd_patterns]
        return (
            set().union(*(_pattern_binding_names(child) for child in children))
            if children
            else set()
        )
    if isinstance(pattern, ast.MatchSequence):
        return (
            set().union(*(_pattern_binding_names(child) for child in pattern.patterns))
            if pattern.patterns
            else set()
        )
    if isinstance(pattern, ast.MatchOr):
        return (
            set().union(*(_pattern_binding_names(child) for child in pattern.patterns))
            if pattern.patterns
            else set()
        )
    return set()


class _FunctionBindingCollector(ast.NodeVisitor):
    """Find bindings owned by one function scope without entering nested scopes."""

    def __init__(self) -> None:
        self.bound: set[str] = set()
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        self.bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.bound.update(alias.asname or alias.name for alias in node.names if alias.name != "*")

    def visit_Global(self, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocals.update(node.names)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.bound.add(node.name)
        if node.type is not None:
            self.visit(node.type)
        for statement in node.body:
            self.visit(statement)

    def visit_Match(self, node: ast.Match) -> None:
        self.visit(node.subject)
        for case in node.cases:
            self.bound.update(_pattern_binding_names(case.pattern))
            if case.guard is not None:
                self.visit(case.guard)
            for statement in case.body:
                self.visit(statement)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.bound.add(node.name)

    # ast.NodeVisitor requires these exact protocol spellings.
    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bound.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


def _function_scope_bindings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[str], set[str], set[str]]:
    """Return local, module-global, and enclosing-scope writes separately."""
    collector = _FunctionBindingCollector()
    arguments = function.args
    for argument in (
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
    ):
        collector.bound.add(argument.arg)
    if arguments.vararg is not None:
        collector.bound.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        collector.bound.add(arguments.kwarg.arg)
    for statement in function.body:
        collector.visit(statement)
    global_writes = collector.bound & collector.globals
    nonlocal_writes = collector.bound & collector.nonlocals
    local_names = collector.bound - collector.globals - collector.nonlocals
    return local_names, global_writes, nonlocal_writes


def _global_writes_in_statements(statements: Sequence[ast.stmt]) -> set[str]:
    """Find explicit global names assigned in one class/module statement block."""
    names: set[str] = set()
    globals_declared: set[str] = set()

    class GlobalWrites(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                names.add(node.id)

        def visit_Global(self, node: ast.Global) -> None:
            globals_declared.update(node.names)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        # ast.NodeVisitor requires these exact protocol spellings.
        visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

    visitor = GlobalWrites()
    for statement in statements:
        visitor.visit(statement)
    return names & globals_declared


def _type_checking_runtime_branch(
    node: ast.AST,
    *,
    bindings: Mapping[str, str],
) -> bool | None:
    """Classify only a still-live imported typing sentinel as a deferred branch."""
    if isinstance(node, ast.Name) and bindings.get(node.id) == "type_checking":
        return False
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "TYPE_CHECKING"
        and isinstance(node.value, ast.Name)
        and bindings.get(node.value.id) == "typing_module"
    ):
        return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        branch = _type_checking_runtime_branch(node.operand, bindings=bindings)
        return None if branch is None else not branch
    return None


def _future_annotations_enabled(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in tree.body
    )


@dataclass(frozen=True)
class _BindingTarget:
    """One source-identified possible value target in a binding."""

    kind: str
    module: str
    symbol: str | None
    line: int = -1
    column: int = -1

    def sort_key(self) -> tuple[str, str, bool, str, int, int]:
        return (
            self.kind,
            self.module,
            self.symbol is None,
            self.symbol or "",
            self.line,
            self.column,
        )


def _source_string_alternatives(binding: _DynamicImportBinding) -> tuple[str, ...]:
    """Return exact string alternatives without dropping open/non-string members."""
    if binding.kind == "string" and binding.name is not None:
        return (binding.name,)
    if binding.kind == "union" and binding.items is not None:
        return tuple(
            sorted(
                {value for member in binding.items for value in _source_string_alternatives(member)}
            )
        )
    return ()


def _source_value_is_closed_string(binding: _DynamicImportBinding) -> bool:
    """Whether every member is a concrete string with no unknown alternative."""
    if binding.kind == "string":
        return binding.name is not None
    if binding.kind == "union" and binding.items:
        return all(_source_value_is_closed_string(member) for member in binding.items)
    return False


def _source_value_add(
    left: _DynamicImportBinding,
    right: _DynamicImportBinding,
    *,
    value_limit: int = _DYNAMIC_COMPREHENSION_VALUE_LIMIT,
    character_limit: int = 4096,
) -> _DynamicImportBinding:
    """Concatenate bounded exact strings and retain unknown/non-string paths."""
    products = {
        first + second
        for first in _source_string_alternatives(left)
        for second in _source_string_alternatives(right)
    }
    overflow = len(products) > value_limit or any(
        len(value) > character_limit for value in products
    )
    if overflow:
        products.clear()
    alternatives = [_dynamic_string_binding(value) for value in sorted(products)]
    if (
        overflow
        or not _source_value_is_closed_string(left)
        or not _source_value_is_closed_string(right)
    ):
        alternatives.append(_DYNAMIC_UNKNOWN)
    return _dynamic_union_binding(alternatives)


@dataclass(frozen=True)
class _BindingKnowledge:
    """Joined targets, source-value payload, uncertainty, and provenance."""

    known_possible_targets: frozenset[_BindingTarget] = frozenset()
    possible_unknown: bool = False
    source_value_origins: frozenset[_BindingTarget] = frozenset()
    builtin_value_kinds: frozenset[str] = frozenset()
    source_value: _DynamicImportBinding | None = None

    def join(self, other: _BindingKnowledge) -> _BindingKnowledge:
        source_values = [
            value for value in (self.source_value, other.source_value) if value is not None
        ]
        if self.possible_unknown or other.possible_unknown:
            source_values.append(_DYNAMIC_UNKNOWN)
        return _BindingKnowledge(
            self.known_possible_targets | other.known_possible_targets,
            self.possible_unknown or other.possible_unknown,
            self.source_value_origins | other.source_value_origins,
            self.builtin_value_kinds | other.builtin_value_kinds,
            _join_dynamic_bindings(source_values) if source_values else None,
        )

    def targets_for(self, kind: str) -> set[_BindingTarget]:
        return {target for target in self.known_possible_targets if target.kind == kind}

    @property
    def definitely_resolved(self) -> bool:
        return bool(self.known_possible_targets) and not self.possible_unknown


@dataclass(frozen=True)
class _CapturedDefault:
    """Abstract value captured when a source function is defined."""

    knowledge: _BindingKnowledge


_GlobalEffect = tuple[_BindingKnowledge, str | None]
_SourceCallContext = tuple[tuple[str, str, int, int], tuple[tuple[str, _BindingKnowledge], ...]]


@dataclass(frozen=True)
class _EvaluatedCallFrame:
    """Values frozen in Python's order while evaluating one call expression."""

    callable_targets: frozenset[tuple[str, str, int, int]]
    class_targets: frozenset[tuple[str, str]]
    callable_knowledge: _BindingKnowledge
    receiver_knowledge: _BindingKnowledge | None
    argument_knowledge: tuple[tuple[int, _BindingKnowledge], ...]
    builtin_symbol: str | None


def _instance_class_for_target(target: _BindingTarget) -> tuple[str, str] | None:
    """Decode the class identity carried by an instance binding target."""
    if target.kind != "instance" or target.symbol is None:
        return None
    if "::" in target.symbol:
        class_module, class_symbol = target.symbol.split("::", 1)
        return class_module, class_symbol
    # Receiver parameters retain class knowledge but lack allocation identity.
    return target.module, target.symbol


class _RuntimeImportCollector(ast.NodeVisitor):
    """Collect eager edges with scope-aware, monotone call-target states."""

    def __init__(
        self,
        module: str,
        module_names: set[str],
        callable_index: set[tuple[str, str]],
        functions: Mapping[tuple[str, str, int, int], ast.FunctionDef | ast.AsyncFunctionDef],
        source_functions: Mapping[
            tuple[str, str, int, int], ast.FunctionDef | ast.AsyncFunctionDef
        ],
        classes: set[str],
        class_index: set[tuple[str, str]],
        source_class_bases: dict[tuple[str, str], set[tuple[str, str]]],
        source_class_base_unknown: set[tuple[str, str]],
        source_class_metaclasses: dict[tuple[str, str], _BindingKnowledge],
        *,
        is_package: bool,
        source_path: str,
        source_value_observation_sites: set[tuple[int, int]] | None = None,
        source_value_target_names: frozenset[str] | None = None,
    ) -> None:
        self.module = module
        self.source_path = source_path
        self.source_value_observation_sites = source_value_observation_sites or set()
        self.source_value_target_names = source_value_target_names
        self.source_value_call_observations: dict[tuple[int, int], dict[str, Any]] = {}
        self.module_names = module_names
        self.callable_index = callable_index
        self.functions = functions
        self.source_functions = source_functions
        self.classes = classes
        self.class_index = class_index
        self.source_class_bases = source_class_bases
        self.source_class_base_unknown = source_class_base_unknown
        self.source_class_metaclasses = source_class_metaclasses
        self.is_package = is_package
        self.edges: set[str] = set()
        self.called: set[tuple[str, str, int, int]] = set()
        self.called_with_bindings: set[
            tuple[
                tuple[str, str, int, int],
                tuple[tuple[str, _BindingKnowledge], ...],
            ]
        ] = set()
        # One call's possible local callees are a single alternative group. Their
        # effects must start from one snapshot and be joined, not replayed in order.
        self.pending_local_call_contexts: list[tuple[_SourceCallContext, ...]] = []
        self.global_effect_frames: list[dict[str, _GlobalEffect]] = []
        self.function_local_names_stack: list[set[str]] = []
        self.dispatch_observations: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.pending_class_constructor_calls: list[tuple[ast.Call, set[tuple[str, str]]]] = []
        self.visited_functions: set[tuple[tuple[str, str, int, int], tuple[Any, ...]]] = set()
        self.import_bindings: dict[str, set[tuple[str, str | None]]] = {}
        self.callable_aliases: dict[str, set[tuple[str, str, int, int]]] = {}
        self.class_aliases: dict[str, set[tuple[str, str]]] = {}
        self.instance_aliases: dict[str, set[tuple[str, str, int, int]]] = {}
        self.function_default_bindings: dict[
            tuple[str, str, int, int], dict[str, _BindingKnowledge]
        ] = {}
        self.external_function_default_bindings: Mapping[
            tuple[str, str, int, int], Mapping[str, _BindingKnowledge]
        ] = {}
        self.class_member_bindings: dict[str, dict[str, _BindingKnowledge]] = {}
        # Object/member state is keyed by source-identified class or allocation-site
        # identity, not by the spelling of the variable currently holding it.
        self.owner_member_bindings: dict[_BindingTarget, dict[str, _BindingKnowledge]] = {}
        self.owner_member_wildcard_overrides: dict[_BindingTarget, set[str]] = {}
        self.external_owner_member_exports: Mapping[
            str, Mapping[_BindingTarget, Mapping[str, _BindingKnowledge]]
        ] = {}
        self.external_module_exports: Mapping[str, Mapping[str, _BindingKnowledge]] = {}
        self.external_class_exports: Mapping[
            str, Mapping[str, Mapping[str, _BindingKnowledge]]
        ] = {}
        self.type_checking_bindings: dict[str, str] = {}
        self.unknown_bindings: set[str] = set()
        self.source_call_result_bindings: dict[str, set[tuple[str, str, int, int]]] = {}
        self.source_value_bindings: dict[str, _DynamicImportBinding] = {}
        self.source_value_origin_bindings: dict[str, set[_BindingTarget]] = {}
        self.builtin_value_kind_bindings: dict[str, set[str]] = {}
        self.future_annotations = False
        self.scope_kind = "module"
        self.scope_prefix = ""
        self.class_context: str | None = None

    def set_future_annotations(self, tree: ast.Module) -> None:
        self.future_annotations = _future_annotations_enabled(tree)

    def _clear_type_bindings(self, names: set[str]) -> None:
        for name in names:
            self.type_checking_bindings.pop(name, None)

    def _clear_name_bindings(self, names: set[str]) -> None:
        for name in names:
            self.import_bindings.pop(name, None)
            self.callable_aliases.pop(name, None)
            self.class_aliases.pop(name, None)
            self.instance_aliases.pop(name, None)
            self.type_checking_bindings.pop(name, None)
            self.unknown_bindings.discard(name)
            self.source_call_result_bindings.pop(name, None)
            self.source_value_bindings.pop(name, None)
            self.source_value_origin_bindings.pop(name, None)
            self.builtin_value_kind_bindings.pop(name, None)

    def _binding_knowledge(self, name: str) -> _BindingKnowledge:
        targets = {
            *(
                _BindingTarget("import", module, symbol)
                for module, symbol in self.import_bindings.get(name, set())
            ),
            *(
                _BindingTarget("callable", module, symbol, line, column)
                for module, symbol, line, column in self.callable_aliases.get(name, set())
            ),
            *(
                _BindingTarget("source_call", module, symbol, line, column)
                for module, symbol, line, column in self.source_call_result_bindings.get(
                    name, set()
                )
            ),
            *(
                _BindingTarget("class", module, symbol)
                for module, symbol in self.class_aliases.get(name, set())
            ),
            *(
                _BindingTarget("instance", module, symbol, line, column)
                for module, symbol, line, column in self.instance_aliases.get(name, set())
            ),
        }
        origins = set(self.source_value_origin_bindings.get(name, set()))
        origins.update(self._source_origins_from_targets(targets))
        return _BindingKnowledge(
            frozenset(targets),
            name in self.unknown_bindings,
            frozenset(origins),
            frozenset(self.builtin_value_kind_bindings.get(name, set())),
            self.source_value_bindings.get(
                name, _DYNAMIC_UNKNOWN if name in self.unknown_bindings else None
            ),
        )

    def _source_origins_from_targets(
        self,
        targets: Sequence[_BindingTarget] | set[_BindingTarget] | frozenset[_BindingTarget],
    ) -> set[_BindingTarget]:
        """Keep repository-owned values as provenance when later expressions transform them."""
        source_kinds = {"import", "callable", "source_call", "class", "instance"}
        return {
            target
            for target in targets
            if target.kind in source_kinds and target.module in self.module_names
        }

    def _instance_class_target(self, target: _BindingTarget) -> tuple[str, str] | None:
        """Decode the class carried by an allocation-site instance identity."""
        return _instance_class_for_target(target)

    def _owner_targets_for_knowledge(
        self, knowledge: _BindingKnowledge
    ) -> tuple[set[_BindingTarget], bool]:
        """Return stable object owners and whether the owner set is incomplete."""
        expanded = self._expand_import_bindings(knowledge)
        owners = {
            target
            for target in expanded.known_possible_targets
            if target.kind == "class"
            or (target.kind == "instance" and target.line >= 0 and target.column >= 0)
        }
        owners.update(
            _BindingTarget("class", module, symbol)
            for module, symbol in self._class_targets_from_knowledge(expanded)
        )
        owners.update(
            _BindingTarget("module", target.module, None)
            for target in expanded.targets_for("import")
            if target.symbol is None and target.module in self.module_names
        )
        unsupported_targets = any(
            target.kind == "source_call" or (target.kind == "instance" and target not in owners)
            for target in expanded.known_possible_targets
        )
        incomplete = expanded.possible_unknown or unsupported_targets
        if expanded.source_value_origins and not owners:
            incomplete = True
        return owners, incomplete

    def _owner_member_knowledge(
        self,
        owners: set[_BindingTarget],
        member: str,
    ) -> tuple[_BindingKnowledge, bool]:
        """Read exact and wildcard effects without collapsing owner identities."""
        result = _BindingKnowledge()
        found = False
        for owner in sorted(owners, key=lambda target: target.sort_key()):
            local_members = self.owner_member_bindings.get(owner, {})
            local_exact = local_members.get(member)
            local_wildcard = local_members.get("*")
            if local_exact is not None:
                result = result.join(local_exact)
                found = True
            if (
                local_wildcard is not None
                and member not in self.owner_member_wildcard_overrides.get(owner, set())
            ):
                result = result.join(local_wildcard)
                found = True

            external_knowledge = _BindingKnowledge()
            external_exact_found = False
            for source_module, owner_exports in self.external_owner_member_exports.items():
                if source_module == self.module:
                    continue
                exported_members = owner_exports.get(owner, {})
                exported_exact = exported_members.get(member)
                exported_wildcard = exported_members.get("*")
                if exported_exact is not None:
                    external_knowledge = external_knowledge.join(exported_exact)
                    external_exact_found = True
                if exported_wildcard is not None:
                    external_knowledge = external_knowledge.join(exported_wildcard)
                    found = True
            if (
                external_exact_found
                or external_knowledge.known_possible_targets
                or external_knowledge.possible_unknown
            ):
                result = result.join(external_knowledge).join(
                    _BindingKnowledge(possible_unknown=True)
                )
                found = True

            # A possible write to an unknown member does not prove that it
            # replaced an exact class-suite member. Preserve both alternatives.
            if local_exact is None and not external_exact_found:
                class_target: tuple[str, str] | None = None
                if owner.kind == "class" and owner.symbol is not None:
                    class_target = (owner.module, owner.symbol)
                elif owner.kind == "instance":
                    class_target = self._instance_class_target(owner)
                if class_target is not None and member.startswith("attr:"):
                    fallback = self._class_member_knowledge(
                        {class_target}, member.removeprefix("attr:")
                    )
                    if fallback.known_possible_targets or fallback.possible_unknown:
                        result = result.join(fallback)
                        found = True
        return result, found

    def _binding_knowledge_snapshot(self) -> dict[str, _BindingKnowledge]:
        names = (
            set(self.import_bindings)
            | set(self.callable_aliases)
            | set(self.source_call_result_bindings)
            | set(self.source_value_bindings)
            | set(self.source_value_origin_bindings)
            | set(self.builtin_value_kind_bindings)
            | set(self.class_aliases)
            | set(self.instance_aliases)
            | self.unknown_bindings
        )
        return {name: self._binding_knowledge(name) for name in names}

    def _write_binding_knowledge(self, name: str, knowledge: _BindingKnowledge) -> None:
        self.import_bindings.pop(name, None)
        self.callable_aliases.pop(name, None)
        self.unknown_bindings.discard(name)
        self.source_call_result_bindings.pop(name, None)
        self.class_aliases.pop(name, None)
        self.instance_aliases.pop(name, None)
        self.source_value_bindings.pop(name, None)
        self.source_value_origin_bindings.pop(name, None)
        self.builtin_value_kind_bindings.pop(name, None)
        for target in knowledge.known_possible_targets:
            if target.kind == "import":
                self.import_bindings.setdefault(name, set()).add((target.module, target.symbol))
            elif target.kind == "callable":
                self.callable_aliases.setdefault(name, set()).add(
                    (target.module, target.symbol or "", target.line, target.column)
                )
            elif target.kind == "source_call":
                self.source_call_result_bindings.setdefault(name, set()).add(
                    (target.module, target.symbol or "", target.line, target.column)
                )
            elif target.kind == "class":
                self.class_aliases.setdefault(name, set()).add((target.module, target.symbol or ""))
            elif target.kind == "instance":
                self.instance_aliases.setdefault(name, set()).add(
                    (target.module, target.symbol or "", target.line, target.column)
                )
        if knowledge.possible_unknown:
            self.unknown_bindings.add(name)
        if knowledge.source_value is not None:
            value = knowledge.source_value
            if knowledge.possible_unknown:
                value = _join_dynamic_bindings((value, _DYNAMIC_UNKNOWN))
            self.source_value_bindings[name] = value
        elif knowledge.possible_unknown:
            self.source_value_bindings[name] = _DYNAMIC_UNKNOWN
        if knowledge.source_value_origins:
            self.source_value_origin_bindings[name] = set(knowledge.source_value_origins)
        if knowledge.builtin_value_kinds:
            self.builtin_value_kind_bindings[name] = set(knowledge.builtin_value_kinds)

    def _install_binding_knowledge(self, bindings: Mapping[str, _BindingKnowledge]) -> None:
        self.import_bindings = {}
        self.callable_aliases = {}
        self.unknown_bindings = set()
        self.source_call_result_bindings = {}
        self.source_value_bindings = {}
        self.source_value_origin_bindings = {}
        self.builtin_value_kind_bindings = {}
        self.class_aliases = {}
        self.instance_aliases = {}
        for name, knowledge in bindings.items():
            self._write_binding_knowledge(name, knowledge)

    def _snapshot_bindings(self) -> tuple[Any, ...]:
        return (
            self._binding_knowledge_snapshot(),
            self.type_checking_bindings.copy(),
            {
                class_name: members.copy()
                for class_name, members in self.class_member_bindings.items()
            },
            {owner: members.copy() for owner, members in self.owner_member_bindings.items()},
            {
                owner: members.copy()
                for owner, members in self.owner_member_wildcard_overrides.items()
            },
            tuple(dict(frame) for frame in self.global_effect_frames),
        )

    def _restore_bindings(self, state: tuple[Any, ...]) -> None:
        bindings, type_checking, classes, owners, wildcard_overrides, global_effects = state
        self._install_binding_knowledge(bindings)
        self.type_checking_bindings = type_checking.copy()
        self.class_member_bindings = {
            class_name: members.copy() for class_name, members in classes.items()
        }
        self.owner_member_bindings = {owner: members.copy() for owner, members in owners.items()}
        self.owner_member_wildcard_overrides = {
            owner: members.copy() for owner, members in wildcard_overrides.items()
        }
        self.global_effect_frames = [dict(frame) for frame in global_effects]

    def _merge_binding_states(self, states: Sequence[tuple[Any, ...]]) -> None:
        if not states:
            return
        bindings: dict[str, _BindingKnowledge] = {}
        class_members: dict[str, dict[str, _BindingKnowledge]] = {}
        owner_members: dict[_BindingTarget, dict[str, _BindingKnowledge]] = {}
        binding_names = set().union(*(set(state[0]) for state in states))
        for name in binding_names:
            for state in states:
                knowledge = state[0].get(name)
                if knowledge is None:
                    knowledge = _BindingKnowledge(possible_unknown=True)
                bindings[name] = bindings.get(name, _BindingKnowledge()).join(knowledge)

        class_names = set().union(*(set(state[2]) for state in states))
        for class_name in class_names:
            member_names = set().union(*(set(state[2].get(class_name, {})) for state in states))
            for member in member_names:
                for state in states:
                    knowledge = state[2].get(class_name, {}).get(member)
                    if knowledge is None:
                        knowledge = _BindingKnowledge(possible_unknown=True)
                    member_map = class_members.setdefault(class_name, {})
                    member_map[member] = member_map.get(member, _BindingKnowledge()).join(knowledge)
        owner_ids = set().union(*(set(state[3]) for state in states))
        for owner in owner_ids:
            member_names = set().union(*(set(state[3].get(owner, {})) for state in states))
            for member in member_names:
                for state in states:
                    knowledge = state[3].get(owner, {}).get(member)
                    if knowledge is None:
                        # A no-write branch can still expose a class-suite value
                        # or a wildcard effect. Resolve that state before using
                        # the unknown sentinel for a genuinely absent member.
                        self._restore_bindings(state)
                        knowledge, found = self._owner_member_knowledge({owner}, member)
                        if not found:
                            knowledge = _BindingKnowledge(possible_unknown=True)
                    member_map = owner_members.setdefault(owner, {})
                    member_map[member] = member_map.get(member, _BindingKnowledge()).join(knowledge)
        override_owners = set().union(*(set(state[4]) for state in states))
        wildcard_overrides: dict[_BindingTarget, set[str]] = {}
        for owner in override_owners:
            common_members = set(states[0][4].get(owner, set()))
            for state in states[1:]:
                common_members.intersection_update(state[4].get(owner, set()))
            if common_members:
                wildcard_overrides[owner] = common_members
        self._install_binding_knowledge(bindings)
        self.class_member_bindings = class_members
        self.owner_member_bindings = owner_members
        self.owner_member_wildcard_overrides = wildcard_overrides
        common = dict(states[0][1])
        for state in states[1:]:
            common = {name: kind for name, kind in common.items() if state[1].get(name) == kind}
        self.type_checking_bindings = common

        frame_count = max((len(state[5]) for state in states), default=0)
        merged_frames: list[dict[str, _GlobalEffect]] = []
        for frame_index in range(frame_count):
            names = set().union(
                *(set(state[5][frame_index]) for state in states if frame_index < len(state[5]))
            )
            merged: dict[str, _GlobalEffect] = {}
            for name in names:
                effects: list[_GlobalEffect] = []
                for state in states:
                    frame = state[5][frame_index] if frame_index < len(state[5]) else {}
                    effect = frame.get(name)
                    if effect is None:
                        # A branch without this effect keeps its binding, while
                        # the path-sensitive write possibility remains unknown.
                        effect = (
                            state[0]
                            .get(name, _BindingKnowledge())
                            .join(_BindingKnowledge(possible_unknown=True)),
                            state[1].get(name),
                        )
                    effects.append(effect)
                knowledge = _BindingKnowledge()
                type_kinds: set[str | None] = set()
                for effect_knowledge, type_kind in effects:
                    knowledge = knowledge.join(effect_knowledge)
                    type_kinds.add(type_kind)
                type_kind = next(iter(type_kinds)) if len(type_kinds) == 1 else None
                merged[name] = (knowledge, type_kind)
            merged_frames.append(merged)
        self.global_effect_frames = merged_frames

    def _visit_binding_paths(self, paths: Sequence[Sequence[ast.AST]]) -> None:
        base = self._snapshot_bindings()
        states: list[tuple[Any, ...]] = []
        for nodes in paths:
            self._restore_bindings(base)
            for node in nodes:
                self.visit(node)
            states.append(self._snapshot_bindings())
        self._merge_binding_states(states)

    def _binding_state_key(self) -> tuple[Any, ...]:
        bindings = tuple(
            (
                name,
                tuple(sorted(target.sort_key() for target in knowledge.known_possible_targets)),
                knowledge.possible_unknown,
                tuple(sorted(target.sort_key() for target in knowledge.source_value_origins)),
                tuple(sorted(knowledge.builtin_value_kinds)),
                repr(knowledge.source_value),
            )
            for name, knowledge in sorted(self._binding_knowledge_snapshot().items())
        )
        class_members = tuple(
            (
                class_name,
                tuple(
                    (
                        member,
                        tuple(
                            sorted(target.sort_key() for target in knowledge.known_possible_targets)
                        ),
                        knowledge.possible_unknown,
                        tuple(
                            sorted(target.sort_key() for target in knowledge.source_value_origins)
                        ),
                        tuple(sorted(knowledge.builtin_value_kinds)),
                        repr(knowledge.source_value),
                    )
                    for member, knowledge in sorted(members.items())
                ),
            )
            for class_name, members in sorted(self.class_member_bindings.items())
        )
        owner_members = tuple(
            (
                owner.sort_key(),
                tuple(
                    (
                        member,
                        tuple(
                            sorted(target.sort_key() for target in knowledge.known_possible_targets)
                        ),
                        knowledge.possible_unknown,
                        tuple(
                            sorted(target.sort_key() for target in knowledge.source_value_origins)
                        ),
                        tuple(sorted(knowledge.builtin_value_kinds)),
                        repr(knowledge.source_value),
                    )
                    for member, knowledge in sorted(members.items())
                ),
            )
            for owner, members in sorted(
                self.owner_member_bindings.items(),
                key=lambda item: item[0].sort_key(),
            )
        )
        wildcard_overrides = tuple(
            (
                owner.sort_key(),
                tuple(sorted(members)),
            )
            for owner, members in sorted(
                self.owner_member_wildcard_overrides.items(),
                key=lambda item: item[0].sort_key(),
            )
        )
        merged_effects: dict[str, _GlobalEffect] = {}
        for frame in self.global_effect_frames:
            for name, (knowledge, type_kind) in frame.items():
                previous = merged_effects.get(name)
                if previous is None:
                    merged_effects[name] = (knowledge, type_kind)
                else:
                    prior_knowledge, prior_type = previous
                    merged_effects[name] = (
                        prior_knowledge.join(knowledge),
                        prior_type if prior_type == type_kind else None,
                    )
        global_effects = tuple(
            (
                name,
                tuple(sorted(target.sort_key() for target in knowledge.known_possible_targets)),
                knowledge.possible_unknown,
                tuple(sorted(target.sort_key() for target in knowledge.source_value_origins)),
                tuple(sorted(knowledge.builtin_value_kinds)),
                repr(knowledge.source_value),
                type_kind,
            )
            for name, (knowledge, type_kind) in sorted(merged_effects.items())
        )
        return (
            bindings,
            tuple(sorted(self.type_checking_bindings.items())),
            class_members,
            owner_members,
            wildcard_overrides,
            global_effects,
        )

    def _record_candidate(self, candidate: str) -> None:
        resolved = _nearest_known_module(candidate, self.module_names)
        if not resolved:
            return
        parts = resolved.split(".")
        for index in range(2, len(parts) + 1):
            parent = ".".join(parts[:index])
            if parent in self.module_names and parent != self.module:
                self.edges.add(parent)

    def _dotted_name(self, node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            return [*self._dotted_name(node.value), node.attr]
        return []

    def _local_callable_targets(self, name: str) -> set[tuple[str, str, int, int]]:
        prefixes = self.scope_prefix.split(".") if self.scope_prefix else []
        while True:
            symbol = ".".join([*prefixes, name]) if prefixes else name
            targets = self._callable_in_module(self.module, symbol)
            if targets:
                return targets
            if not prefixes:
                return set()
            prefixes.pop()

    def _local_class_symbols(self, name: str) -> set[str]:
        knowledge = self._binding_knowledge(name)
        if knowledge.targets_for("import") or knowledge.possible_unknown:
            return set()
        prefixes = self.scope_prefix.split(".") if self.scope_prefix else []
        while True:
            symbol = ".".join([*prefixes, name]) if prefixes else name
            if symbol in self.classes:
                return {symbol}
            if not prefixes:
                return set()
            prefixes.pop()

    def _expand_import_bindings(
        self,
        knowledge: _BindingKnowledge,
        seen: frozenset[tuple[str, str]] = frozenset(),
    ) -> _BindingKnowledge:
        """Preserve imported bindings while joining their complete source export."""
        expanded = knowledge
        for target in knowledge.targets_for("import"):
            if target.symbol is None:
                continue
            key = (target.module, target.symbol)
            if key in seen:
                continue
            exported = self.external_module_exports.get(target.module, {}).get(target.symbol)
            if exported is not None:
                expanded = expanded.join(self._expand_import_bindings(exported, seen | {key}))
        return expanded

    def _class_targets_from_knowledge(
        self,
        knowledge: _BindingKnowledge,
        seen: frozenset[tuple[str, str]] = frozenset(),
    ) -> set[tuple[str, str]]:
        """Resolve source class values through complete module export bindings."""
        targets: set[tuple[str, str]] = set()
        for target in knowledge.known_possible_targets:
            if target.kind == "class" and target.symbol is not None:
                targets.add((target.module, target.symbol))
            elif target.kind == "import" and target.symbol is not None:
                key = (target.module, target.symbol)
                if key in self.class_index:
                    targets.add(key)
                    continue
                if key in seen:
                    continue
                exported = self.external_module_exports.get(target.module, {}).get(target.symbol)
                if exported is not None:
                    targets.update(self._class_targets_from_knowledge(exported, seen | {key}))
        return targets

    def _class_targets(self, node: ast.AST) -> set[tuple[str, str]]:
        """Resolve source-known class values through joined binding knowledge."""
        if isinstance(node, ast.Name):
            knowledge = self._binding_knowledge(node.id)
            targets = self._class_targets_from_knowledge(knowledge)
            if (
                not targets
                and not knowledge.known_possible_targets
                and not knowledge.possible_unknown
            ):
                targets.update(
                    (self.module, symbol) for symbol in self._local_class_symbols(node.id)
                )
            return targets

        if not isinstance(node, ast.Attribute):
            return set()
        parts = self._dotted_name(node)
        if len(parts) < 2:
            return set()
        first, suffix = parts[0], parts[1:]
        knowledge = self._binding_knowledge(first)
        targets: set[tuple[str, str]] = set()
        for module, class_name in self._class_targets_from_knowledge(knowledge):
            symbol = ".".join([class_name, *suffix])
            if (module, symbol) in self.class_index:
                targets.add((module, symbol))

        for imported in knowledge.targets_for("import"):
            if imported.symbol is not None:
                symbol = ".".join([imported.symbol, *suffix])
                if (imported.module, symbol) in self.class_index:
                    targets.add((imported.module, symbol))
                exported = self.external_module_exports.get(imported.module, {}).get(symbol)
                if exported is not None:
                    targets.update(self._class_targets_from_knowledge(exported))
                if suffix:
                    candidate_module = ".".join([imported.module, imported.symbol, *suffix[:-1]])
                    resolved_module = _nearest_known_module(candidate_module, self.module_names)
                    if resolved_module:
                        candidate_symbol = suffix[-1]
                        if (resolved_module, candidate_symbol) in self.class_index:
                            targets.add((resolved_module, candidate_symbol))
                        exported = self.external_module_exports.get(resolved_module, {}).get(
                            candidate_symbol
                        )
                        if exported is not None:
                            targets.update(self._class_targets_from_knowledge(exported))
            elif suffix:
                candidate_module = ".".join([imported.module, *suffix[:-1]])
                resolved_module = _nearest_known_module(candidate_module, self.module_names)
                if resolved_module:
                    candidate_symbol = suffix[-1]
                    if (resolved_module, candidate_symbol) in self.class_index:
                        targets.add((resolved_module, candidate_symbol))
                    exported = self.external_module_exports.get(resolved_module, {}).get(
                        candidate_symbol
                    )
                    if exported is not None:
                        targets.update(self._class_targets_from_knowledge(exported))

        if not targets and not knowledge.known_possible_targets and not knowledge.possible_unknown:
            for class_symbol in self._local_class_symbols(first):
                symbol = ".".join([class_symbol, *suffix])
                if (self.module, symbol) in self.class_index:
                    targets.add((self.module, symbol))
            candidate_module = ".".join(parts[:-1])
            resolved_module = _nearest_known_module(candidate_module, self.module_names)
            if resolved_module:
                candidate_symbol = parts[-1]
                if (resolved_module, candidate_symbol) in self.class_index:
                    targets.add((resolved_module, candidate_symbol))
                exported = self.external_module_exports.get(resolved_module, {}).get(
                    candidate_symbol
                )
                if exported is not None:
                    targets.update(self._class_targets_from_knowledge(exported))
        return targets

    def _instance_class_targets(self, node: ast.AST) -> set[tuple[str, str]]:
        """Resolve instances produced by source class calls or joined aliases."""
        if isinstance(node, ast.Name):
            targets = self._binding_knowledge(node.id).targets_for("instance")
        elif isinstance(node, ast.Call):
            return self._class_targets(node.func)
        else:
            targets = self._knowledge_for_expression(node).targets_for("instance")
        return {
            class_target
            for target in targets
            if (class_target := self._instance_class_target(target)) is not None
        }

    def _class_member_knowledge(
        self,
        class_targets: set[tuple[str, str]],
        member: str,
        seen: frozenset[tuple[str, str, str]] = frozenset(),
    ) -> _BindingKnowledge:
        """Join complete member bindings, including source base-class members."""
        knowledge = _BindingKnowledge()
        found = False
        for module, class_name in class_targets:
            key = (module, class_name, member)
            if key in seen:
                knowledge = knowledge.join(_BindingKnowledge(possible_unknown=True))
                continue
            members = (
                self.class_member_bindings
                if module == self.module
                else self.external_class_exports.get(module, {})
            ).get(class_name, {})
            member_knowledge = members.get(member)
            if member_knowledge is not None:
                invocation = self._callable_targets_for_knowledge(member_knowledge)
                if not invocation.known_possible_targets:
                    direct_methods = self._indexed_source_method_targets(
                        (module, class_name), member
                    )
                    if direct_methods:
                        member_knowledge = member_knowledge.join(
                            _BindingKnowledge(
                                frozenset(
                                    _BindingTarget("callable", *reference)
                                    for reference in direct_methods
                                )
                            )
                        )
                knowledge = knowledge.join(member_knowledge)
                found = True
                continue
            direct_methods = self._indexed_source_method_targets((module, class_name), member)
            if direct_methods:
                knowledge = knowledge.join(
                    _BindingKnowledge(
                        frozenset(
                            _BindingTarget("callable", *reference) for reference in direct_methods
                        )
                    )
                )
                found = True
                continue
            bases = self.source_class_bases.get((module, class_name), set())
            if bases:
                inherited = self._class_member_knowledge(bases, member, seen | {key})
                knowledge = knowledge.join(inherited)
                found = found or bool(inherited.known_possible_targets)
                continue
            if module in self.module_names:
                knowledge = knowledge.join(_BindingKnowledge(possible_unknown=True))
        if class_targets and not found and not knowledge.possible_unknown:
            return _BindingKnowledge(possible_unknown=True)
        return knowledge

    def _callable_targets_for_knowledge(
        self,
        knowledge: _BindingKnowledge,
        seen: frozenset[tuple[str, str, str]] = frozenset(),
    ) -> _BindingKnowledge:
        """Derive callable source targets without dropping any possible value."""
        callable_targets: set[_BindingTarget] = set()
        possible_unknown = knowledge.possible_unknown
        for target in knowledge.known_possible_targets:
            if target.kind == "callable":
                callable_targets.add(target)
                continue
            if target.kind == "source_call":
                callable_targets.add(
                    _BindingTarget(
                        "callable", target.module, target.symbol, target.line, target.column
                    )
                )
                possible_unknown = True
                continue
            if target.kind == "import":
                imported_classes = self._class_targets_from_knowledge(
                    _BindingKnowledge(frozenset({target}))
                )
                if imported_classes:
                    invocation = self._callable_targets_for_knowledge(
                        _BindingKnowledge(
                            frozenset(
                                _BindingTarget("class", module, class_name)
                                for module, class_name in imported_classes
                            )
                        ),
                        seen,
                    )
                    callable_targets.update(invocation.known_possible_targets)
                    possible_unknown = possible_unknown or invocation.possible_unknown
                    continue
                resolved = self._targets_from_import(target.module, target.symbol, ())
                callable_targets.update(
                    _BindingTarget("callable", module, symbol, line, column)
                    for module, symbol, line, column in resolved
                )
                if not resolved and target.module in self.module_names:
                    possible_unknown = True
                continue
            if target.kind == "class" and target.symbol is not None:
                class_key = (target.module, target.symbol, "<call>")
                if class_key in seen:
                    possible_unknown = True
                    continue
                class_targets = {(target.module, target.symbol)}
                constructors = self._class_member_knowledge(
                    class_targets, "__new__", seen | {class_key}
                ).join(self._class_member_knowledge(class_targets, "__init__", seen | {class_key}))
                invocation = self._callable_targets_for_knowledge(constructors, seen | {class_key})
                callable_targets.update(invocation.known_possible_targets)
                possible_unknown = possible_unknown or invocation.possible_unknown
                if not constructors.known_possible_targets and not constructors.possible_unknown:
                    callable_targets.add(_BindingTarget("class_call", target.module, target.symbol))
                continue
            if target.kind == "instance" and target.symbol is not None:
                instance_class = self._instance_class_target(target)
                if instance_class is None:
                    possible_unknown = True
                    continue
                class_key = (*instance_class, "__call__")
                if class_key in seen:
                    possible_unknown = True
                    continue
                method_targets, method_incomplete = self._source_method_targets_for_class(
                    instance_class, "__call__"
                )
                callable_targets.update(
                    _BindingTarget("callable", *reference) for reference in method_targets
                )
                possible_unknown = possible_unknown or method_incomplete
                if not method_targets:
                    # A source class with no resolved __call__ can still be an
                    # unsupported callable through an unmodeled base/runtime hook.
                    possible_unknown = True
                continue
            possible_unknown = True
        return _BindingKnowledge(
            frozenset(callable_targets),
            possible_unknown,
            knowledge.source_value_origins,
        )

    def _class_method_targets(
        self,
        class_targets: set[tuple[str, str]],
        member: str,
    ) -> set[tuple[str, str, int, int]]:
        knowledge = self._class_member_knowledge(class_targets, member)
        invocation = self._callable_targets_for_knowledge(knowledge)
        targets = {
            (target.module, target.symbol or "", target.line, target.column)
            for target in invocation.known_possible_targets
            if target.kind == "callable"
        }
        for class_target in class_targets:
            source_targets, _unresolved = self._source_method_targets_for_class(
                class_target, member
            )
            targets.update(source_targets)
        return targets

    def _enclosing_class(self, callable_name: str) -> str | None:
        parts = callable_name.split(".")
        for length in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:length])
            if candidate in self.classes:
                return candidate
        return None

    def _targets_from_import(
        self,
        imported_module: str,
        imported_symbol: str | None,
        suffix: Sequence[str],
    ) -> set[tuple[str, str, int, int]]:
        if imported_symbol is not None:
            symbol = ".".join([imported_symbol, *suffix]) if suffix else imported_symbol
            if not suffix:
                exported = self.external_module_exports.get(imported_module, {}).get(symbol)
                if exported is not None:
                    invocation = self._callable_targets_for_knowledge(exported)
                    return {
                        (target.module, target.symbol or "", target.line, target.column)
                        for target in invocation.known_possible_targets
                        if target.kind == "callable"
                    }
            return self._callable_in_module(imported_module, symbol)
        if not suffix:
            return set()
        module_candidate = ".".join([imported_module, *suffix[:-1]])
        resolved_module = _nearest_known_module(module_candidate, self.module_names)
        if resolved_module is None:
            return set()
        exported = self.external_module_exports.get(resolved_module, {}).get(suffix[-1])
        if exported is not None:
            invocation = self._callable_targets_for_knowledge(exported)
            return {
                (target.module, target.symbol or "", target.line, target.column)
                for target in invocation.known_possible_targets
                if target.kind == "callable"
            }
        return self._callable_in_module(resolved_module, suffix[-1])

    def _callable_target(self, node: ast.AST) -> set[tuple[str, str, int, int]]:
        targets: set[tuple[str, str, int, int]] = set()
        if isinstance(node, ast.Call):
            invocation = self._callable_targets_for_knowledge(self._knowledge_for_expression(node))
            return {
                (target.module, target.symbol or "", target.line, target.column)
                for target in invocation.known_possible_targets
                if target.kind == "callable"
            }
        if isinstance(node, ast.Attribute):
            receiver_classes = self._instance_class_targets(node.value)
            receiver_classes.update(self._class_targets(node.value))
            targets.update(self._class_method_targets(receiver_classes, node.attr))
        parts = self._dotted_name(node)
        if not parts:
            return targets
        if len(parts) == 1:
            name = parts[0]
            knowledge = self._binding_knowledge(name)
            invocation = self._callable_targets_for_knowledge(knowledge)
            targets.update(
                (target.module, target.symbol or "", target.line, target.column)
                for target in invocation.known_possible_targets
                if target.kind == "callable"
            )
            for imported in knowledge.targets_for("import"):
                targets.update(self._targets_from_import(imported.module, imported.symbol, ()))
            if (
                not targets
                and not knowledge.targets_for("import")
                and not knowledge.possible_unknown
            ):
                targets.update(self._local_callable_targets(name))
            return targets

        first = parts[0]
        suffix = parts[1:]
        knowledge = self._binding_knowledge(first)
        for target in knowledge.targets_for("callable"):
            if len(suffix) == 1:
                targets.update(
                    self._callable_in_module(target.module, f"{target.symbol}.{suffix[0]}")
                )
        for imported in knowledge.targets_for("import"):
            targets.update(self._targets_from_import(imported.module, imported.symbol, suffix))
        if not targets and not knowledge.targets_for("import") and not knowledge.possible_unknown:
            for class_symbol in self._local_class_symbols(first):
                targets.update(
                    self._callable_in_module(
                        self.module,
                        f"{class_symbol}.{'.'.join(suffix)}",
                    )
                )
            module_candidate = ".".join(parts[:-1])
            resolved_module = _nearest_known_module(module_candidate, self.module_names)
            if resolved_module is not None:
                targets.update(self._callable_in_module(resolved_module, parts[-1]))
        return targets

    def _callable_in_module(self, module: str, symbol: str) -> set[tuple[str, str, int, int]]:
        if module == self.module:
            if "." in symbol:
                class_name, _, member = symbol.rpartition(".")
                knowledge = self.class_member_bindings.get(class_name, {}).get(member)
                if knowledge is not None:
                    invocation = self._callable_targets_for_knowledge(knowledge)
                    return {
                        (target.module, target.symbol or "", target.line, target.column)
                        for target in invocation.known_possible_targets
                        if target.kind == "callable"
                    }
            else:
                targets = self.callable_aliases.get(symbol)
                if targets:
                    return set(targets)
            direct = {reference for reference in self.functions if reference[1] == symbol}
            if direct:
                return direct
            constructor = f"{symbol}.__init__"
            return {reference for reference in self.functions if reference[1] == constructor}
        if "." in symbol:
            class_name, _, member = symbol.rpartition(".")
            knowledge = self.external_class_exports.get(module, {}).get(class_name, {}).get(member)
            if knowledge is not None:
                invocation = self._callable_targets_for_knowledge(knowledge)
                return {
                    (target.module, target.symbol or "", target.line, target.column)
                    for target in invocation.known_possible_targets
                    if target.kind == "callable"
                }
        if (module, symbol) in self.callable_index:
            return {(module, symbol, -1, -1)}
        constructor = f"{symbol}.__init__"
        if (module, constructor) in self.callable_index:
            return {(module, constructor, -1, -1)}
        return set()

    def _record_targets(self, targets: set[tuple[str, str, int, int]]) -> None:
        for target in sorted(targets):
            if target[0] == self.module and target[2] >= 0:
                self.visit_callable(target)
            else:
                self.called.add(target)

    def _record_callable(self, node: ast.AST) -> None:
        self._record_targets(self._callable_target(node))

    def _record_class_constructors(
        self,
        node: ast.AST,
        call: ast.Call,
        *,
        class_targets: set[tuple[str, str]] | None = None,
        knowledge: _BindingKnowledge | None = None,
    ) -> None:
        class_targets = self._class_targets(node) if class_targets is None else class_targets
        knowledge = self._knowledge_for_expression(node) if knowledge is None else knowledge
        if class_targets:
            if knowledge.possible_unknown:
                constructor_targets = set().union(
                    *(
                        self._class_method_targets({(module, class_name)}, method)
                        for module, class_name in class_targets
                        for method in ("__new__", "__init__")
                    )
                )
                self._record_dispatch_observation(
                    call,
                    receiver_form="Call",
                    class_targets=class_targets,
                    callable_targets=constructor_targets,
                    reasons={"source_possible_unknown_target"},
                    binding_knowledge=self._observation_knowledge(
                        knowledge,
                        class_targets,
                        constructor_targets,
                        {"source_possible_unknown_target"},
                    ),
                )
            self.pending_class_constructor_calls.append((call, class_targets))
        for module, class_name in sorted(class_targets):
            for method in ("__new__", "__init__"):
                self._record_targets(self._class_method_targets({(module, class_name)}, method))

    def _inherited_source_method_targets(
        self,
        class_target: tuple[str, str],
        method: str,
        seen: set[tuple[str, str]] | None = None,
    ) -> set[tuple[str, str, int, int]]:
        seen = set() if seen is None else seen
        if class_target in seen:
            return set()
        seen.add(class_target)
        targets: set[tuple[str, str, int, int]] = set()
        for base in sorted(self.source_class_bases.get(class_target, set())):
            direct = self._callable_in_module(base[0], f"{base[1]}.{method}")
            if direct:
                targets.update(direct)
            else:
                targets.update(self._inherited_source_method_targets(base, method, seen))
        return targets

    def resolve_pending_class_constructor_calls(self) -> bool:
        pending = self.pending_class_constructor_calls
        self.pending_class_constructor_calls = []
        for call, class_targets in pending:
            inherited_targets: set[tuple[str, str, int, int]] = set()
            for target in class_targets:
                for method in ("__new__", "__init__"):
                    if self._callable_in_module(target[0], f"{target[1]}.{method}"):
                        continue
                    inherited_targets.update(self._inherited_source_method_targets(target, method))
            if not inherited_targets:
                continue
            for target in sorted(inherited_targets):
                self._record_targets({target})
            self._record_dispatch_observation(
                call,
                receiver_form="Call",
                class_targets=class_targets,
                callable_targets=inherited_targets,
                reasons={"source_class_base_constructor_lookup_not_summarized"},
                binding_knowledge=self._observation_knowledge(
                    _BindingKnowledge(),
                    class_targets,
                    inherited_targets,
                    {"source_class_base_constructor_lookup_not_summarized"},
                ),
            )
        return bool(pending)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record_candidate(alias.name)
            bound_name = alias.asname or alias.name.split(".")[0]
            bound_module = alias.name if alias.asname else alias.name.split(".")[0]
            self._clear_name_bindings({bound_name})
            self.import_bindings[bound_name] = {(bound_module, None)}
            if alias.name in {"typing", "typing_extensions"}:
                self.type_checking_bindings[bound_name] = "typing_module"

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = _runtime_relative_import(
            self.module,
            node.module,
            node.level,
            is_package=self.is_package,
        )
        if base:
            self._record_candidate(base)
        for alias in node.names:
            if alias.name == "*":
                self.type_checking_bindings.clear()
                continue
            candidate = f"{base}.{alias.name}" if base else alias.name
            self._record_candidate(candidate)
            resolved_candidate = _nearest_known_module(candidate, self.module_names)
            bound_name = alias.asname or alias.name
            self._clear_name_bindings({bound_name})
            if node.module in {"typing", "typing_extensions"} and alias.name == "TYPE_CHECKING":
                self.type_checking_bindings[bound_name] = "type_checking"
            if resolved_candidate == candidate:
                self.import_bindings[bound_name] = {(candidate, None)}
            else:
                resolved_base = _nearest_known_module(base, self.module_names) if base else None
                self.import_bindings[bound_name] = {(resolved_base or base, alias.name)}

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        runtime_branch = _type_checking_runtime_branch(
            node.test,
            bindings=self.type_checking_bindings,
        )
        if runtime_branch is False:
            for statement in node.orelse:
                self.visit(statement)
            return
        if runtime_branch is True:
            for statement in node.body:
                self.visit(statement)
            return
        self._visit_binding_paths((node.body, node.orelse))

    def visit_Match(self, node: ast.Match) -> None:
        subject_knowledge = self._knowledge_for_expression(node.subject)
        self.visit(node.subject)
        base = self._snapshot_bindings()
        states = [base]
        for case in node.cases:
            self._restore_bindings(base)
            self._bind_pattern_values(
                case.pattern, node.subject, subject_knowledge=subject_knowledge
            )
            if case.guard is not None:
                self.visit(case.guard)
            for statement in case.body:
                self.visit(statement)
            states.append(self._snapshot_bindings())
        self._merge_binding_states(states)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                self._record_callable(decorator)
            self.visit(decorator)
        qualified_name = f"{self.scope_prefix}.{node.name}" if self.scope_prefix else node.name
        reference = (self.module, qualified_name, node.lineno, node.col_offset)
        default_bindings: dict[str, _BindingKnowledge] = {}
        positional = [*node.args.posonlyargs, *node.args.args]
        first_default = len(positional) - len(node.args.defaults)
        for parameter, default in zip(positional[first_default:], node.args.defaults, strict=True):
            default_bindings[parameter.arg] = self._knowledge_for_expression(default)
            self.visit(default)
        for parameter, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
            if default is not None:
                default_bindings[parameter.arg] = self._knowledge_for_expression(default)
                self.visit(default)
        if default_bindings:
            previous_defaults = self.function_default_bindings.get(reference, {})
            joined_defaults = dict(previous_defaults)
            for parameter, knowledge in default_bindings.items():
                joined_defaults[parameter] = joined_defaults.get(
                    parameter, _BindingKnowledge()
                ).join(knowledge)
            self.function_default_bindings[reference] = joined_defaults
        if not self.future_annotations:
            annotation_arguments = [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
            if node.args.vararg is not None:
                annotation_arguments.append(node.args.vararg)
            if node.args.kwarg is not None:
                annotation_arguments.append(node.args.kwarg)
            for argument in annotation_arguments:
                if argument.annotation is not None:
                    self.visit(argument.annotation)
            if node.returns is not None:
                self.visit(node.returns)
        self._clear_name_bindings({node.name})
        self.callable_aliases[node.name] = {
            (self.module, qualified_name, node.lineno, node.col_offset)
        }

    # ast.NodeVisitor requires these exact protocol spellings.
    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

    def visit_Lambda(self, node: ast.Lambda) -> None:
        defaults = [*node.args.defaults, *(item for item in node.args.kw_defaults if item)]
        for default in defaults:
            self.visit(default)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        saved_bindings = self._snapshot_bindings()
        saved_scope_kind = self.scope_kind
        saved_scope_prefix = self.scope_prefix
        saved_class_context = self.class_context
        base_targets: set[tuple[str, str]] = set()
        unknown_base = False
        metaclass_knowledge: _BindingKnowledge | None = None
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                self._record_callable(decorator)
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
            resolved_bases = self._class_targets(base)
            base_targets.update(resolved_bases)
            if not resolved_bases and not self._is_known_builtin_class_expression(base):
                unknown_base = True
        for keyword in node.keywords:
            if keyword.arg == "metaclass":
                if self._known_builtin_symbol(keyword.value) != "type":
                    metaclass_knowledge = self._knowledge_for_expression(keyword.value)
                self._record_callable(keyword.value)
            self.visit(keyword.value)
        qualified_name = f"{self.scope_prefix}.{node.name}" if self.scope_prefix else node.name
        class_target = (self.module, qualified_name)
        if unknown_base:
            self.source_class_base_unknown.add(class_target)
        if metaclass_knowledge is not None:
            self.source_class_metaclasses[class_target] = self.source_class_metaclasses.get(
                class_target, _BindingKnowledge()
            ).join(metaclass_knowledge)
        if base_targets:
            self.source_class_bases.setdefault((self.module, qualified_name), set()).update(
                base_targets
            )
        class_global_writes = _global_writes_in_statements(node.body)
        class_scope_collector = _FunctionBindingCollector()
        for statement in node.body:
            class_scope_collector.visit(statement)
        class_bound_names = class_scope_collector.bound - class_global_writes
        self.scope_prefix = qualified_name
        self.scope_kind = "class"
        self.class_context = qualified_name
        self.function_local_names_stack.append(class_bound_names)
        self.global_effect_frames.append({})
        for statement in node.body:
            self.visit(statement)
        class_bindings = self._snapshot_bindings()
        class_effects = dict(class_bindings[5][-1])
        for global_name in class_global_writes:
            class_effects[global_name] = (
                class_bindings[0].get(global_name, _BindingKnowledge()),
                class_bindings[1].get(global_name),
            )
        self._restore_bindings(saved_bindings)
        self.function_local_names_stack.pop()
        self.owner_member_bindings = {
            owner: members.copy() for owner, members in class_bindings[3].items()
        }
        self.owner_member_wildcard_overrides = {
            owner: members.copy() for owner, members in class_bindings[4].items()
        }
        self.scope_kind = saved_scope_kind
        self.scope_prefix = saved_scope_prefix
        self.class_context = saved_class_context
        self._clear_name_bindings({node.name} | class_global_writes)
        (
            class_knowledge,
            _class_type_checking,
            _class_member_exports,
            _class_owner_members,
            _class_wildcard_overrides,
            _class_global_effect_frames,
        ) = class_bindings
        self.class_member_bindings[qualified_name] = {
            name: knowledge
            for name, knowledge in class_knowledge.items()
            if name in class_bound_names
        }
        constructor_targets = self._callable_in_module(self.module, f"{qualified_name}.__init__")
        class_knowledge = _BindingKnowledge(
            frozenset(
                {
                    _BindingTarget("class", self.module, qualified_name),
                    *(
                        _BindingTarget("callable", module, symbol, line, column)
                        for module, symbol, line, column in constructor_targets
                    ),
                }
            )
        )
        self._write_binding_knowledge(node.name, class_knowledge)
        caller_locals = (
            self.function_local_names_stack[-1] if self.function_local_names_stack else set()
        )
        for global_name, effect in class_effects.items():
            self._apply_global_effect(global_name, effect, shadowed_names=caller_locals)

    def _bind_knowledge_to_names(self, names: set[str], knowledge: _BindingKnowledge) -> None:
        """Write one complete binding lattice through the shared assignment sink."""
        self._clear_name_bindings(names)
        for name in names:
            self._write_binding_knowledge(name, knowledge)

    def _bind_pattern_values(
        self,
        pattern: ast.pattern,
        subject: ast.AST,
        *,
        subject_knowledge: _BindingKnowledge | None = None,
    ) -> None:
        """Carry subject provenance into captures without inventing element types."""
        names = _pattern_binding_names(pattern)
        if not names:
            return
        if subject_knowledge is None:
            subject_knowledge = self._knowledge_for_expression(subject)
        self._bind_unknown(names, source_value_origins=subject_knowledge.source_value_origins)
        # A top-level MatchAs captures the subject itself. Nested captures may
        # select an element or attribute, so retain provenance but not its type.
        if isinstance(pattern, ast.MatchAs) and pattern.name:
            self._bind_knowledge_to_names({pattern.name}, subject_knowledge)

    def visit_Assign(self, node: ast.Assign) -> None:
        knowledge = self._knowledge_for_expression(node.value)
        self.visit(node.value)
        for target in node.targets:
            self.visit(target)
            self._bind_target_knowledge(target, knowledge)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        knowledge = self._knowledge_for_expression(node.value) if node.value is not None else None
        self.visit(node.target)
        if self.scope_kind != "function" and not self.future_annotations:
            self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
        if knowledge is None:
            self._bind_unknown(_binding_names(node.target))
        else:
            self._bind_target_knowledge(node.target, knowledge)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        prior = self._knowledge_for_expression(node.target)
        right = self._knowledge_for_expression(node.value)
        origins = set(prior.source_value_origins | right.source_value_origins)
        origins.update(self._source_value_origins_for_expression(node.target))
        origins.update(self._source_value_origins_for_expression(node.value))
        self.visit(node.target)
        self.visit(node.value)
        if isinstance(node.target, ast.Name):
            old_value = prior.source_value or _DYNAMIC_UNKNOWN
            right_value = right.source_value or _DYNAMIC_UNKNOWN
            source_value = (
                _source_value_add(old_value, right_value)
                if isinstance(node.op, ast.Add)
                else _DYNAMIC_UNKNOWN
            )
            self._bind_target_knowledge(
                node.target,
                replace(prior.join(right), source_value=source_value),
            )
        else:
            self._bind_unknown_target(node.target, origins)

    def _storage_targets(self, target: ast.AST) -> list[ast.AST]:
        if isinstance(target, (ast.Tuple, ast.List)):
            return [stored for item in target.elts for stored in self._storage_targets(item)]
        if isinstance(target, ast.Starred):
            return self._storage_targets(target.value)
        return [target] if isinstance(target, (ast.Attribute, ast.Subscript)) else []

    def _storage_member_name(self, target: ast.AST) -> str | None:
        if isinstance(target, ast.Attribute):
            return f"attr:{target.attr}"
        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
            value = target.slice.value
            if value is None or isinstance(value, (bool, int, str, bytes)):
                return f"sub:{type(value).__name__}:{value!r}"
        return None

    def _record_unresolved_storage(
        self, target: ast.AST, origins: Iterable[_BindingTarget]
    ) -> None:
        self._record_dispatch_observation(
            target,
            receiver_form="BindingTarget",
            class_targets=set(),
            callable_targets=set(),
            reasons={"source_derived_binding_target_not_summarized"},
            binding_knowledge=_BindingKnowledge(
                possible_unknown=True,
                source_value_origins=frozenset(origins),
            ),
            record_unresolved_value=True,
        )

    def _apply_owner_member_effect(
        self,
        node: ast.AST,
        owner_knowledge: _BindingKnowledge,
        member: str | None,
        value_knowledge: _BindingKnowledge,
        *,
        must_apply: bool,
    ) -> None:
        """Transfer one possible/guaranteed write without erasing prior origins."""
        owners, owner_incomplete = self._owner_targets_for_knowledge(owner_knowledge)
        origins = set(owner_knowledge.source_value_origins)
        origins.update(value_knowledge.source_value_origins)
        effect_is_exact = (
            must_apply and not owner_incomplete and len(owners) == 1 and member is not None
        )

        # Exact owner/key state can retain a possible effect without producing a
        # premature gate finding: a later source-member read observes the joined
        # value. Untrackable owners and dynamic keys need an explicit observation.
        exact_builtin_dict_storage = (
            owner_knowledge.builtin_value_kinds == frozenset({"dict"})
            and not owner_knowledge.possible_unknown
            and member is not None
            and member.startswith("sub:")
        )
        if (
            origins
            and (not owners or owner_incomplete or member is None)
            and not exact_builtin_dict_storage
        ):
            self._record_unresolved_storage(node, origins)

        effect_knowledge = (
            value_knowledge
            if effect_is_exact
            else value_knowledge.join(_BindingKnowledge(possible_unknown=True))
        )
        for owner in owners:
            member_map = self.owner_member_bindings.setdefault(owner, {})
            if member is None:
                member_map["*"] = member_map.get("*", _BindingKnowledge()).join(effect_knowledge)
                self.owner_member_wildcard_overrides.pop(owner, None)
            elif effect_is_exact:
                member_map[member] = effect_knowledge
                self.owner_member_wildcard_overrides.setdefault(owner, set()).add(member)
            else:
                prior, _found = self._owner_member_knowledge({owner}, member)
                member_map[member] = prior.join(effect_knowledge)

    def _bind_target_knowledge(
        self,
        target: ast.AST,
        knowledge: _BindingKnowledge,
        *,
        member_effect_must_apply: bool = True,
    ) -> None:
        """Write lexical bindings and transfer the complete owner/member effect."""
        names = _binding_names(target)
        if names:
            self._bind_knowledge_to_names(names, knowledge)

        for owner_name in _binding_target_owner_names(target):
            owner_knowledge = self._binding_knowledge(owner_name).join(
                _BindingKnowledge(source_value_origins=knowledge.source_value_origins)
            )
            self._bind_knowledge_to_names({owner_name}, owner_knowledge)

        storage_targets = self._storage_targets(target)
        unpacked = isinstance(target, (ast.Tuple, ast.List, ast.Starred))
        for stored in storage_targets:
            owner_expression = stored.value
            owner_knowledge = self._knowledge_for_expression(owner_expression)
            stored_knowledge = (
                _BindingKnowledge(
                    possible_unknown=True,
                    source_value_origins=knowledge.source_value_origins,
                )
                if unpacked
                else knowledge
            )
            self._apply_owner_member_effect(
                stored,
                owner_knowledge,
                self._storage_member_name(stored),
                stored_knowledge,
                must_apply=member_effect_must_apply,
            )

    def _bind_unknown_target(
        self,
        target: ast.AST,
        source_value_origins: Iterable[_BindingTarget] = (),
        *,
        member_effect_must_apply: bool = True,
    ) -> None:
        """Bind unknown values while retaining whether the member write is certain."""
        self._bind_target_knowledge(
            target,
            _BindingKnowledge(
                possible_unknown=True,
                source_value_origins=frozenset(source_value_origins),
            ),
            member_effect_must_apply=member_effect_must_apply,
        )

    def _bind_unknown(
        self,
        names: set[str],
        *,
        source_value_origins: Iterable[_BindingTarget] = (),
    ) -> None:
        self._bind_knowledge_to_names(
            names,
            _BindingKnowledge(
                possible_unknown=True,
                source_value_origins=frozenset(source_value_origins),
            ),
        )

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        knowledge = self._knowledge_for_expression(node.value)
        self.visit(node.value)
        self._bind_target_knowledge(node.target, knowledge)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            origins = self._source_value_origins_for_expression(target)
            self._bind_unknown_target(target, origins)
            self.visit(target)

    def visit_For(self, node: ast.For) -> None:
        iter_knowledge = self._knowledge_for_expression(node.iter)
        self.visit(node.iter)
        self._bind_target_knowledge(
            node.target,
            _BindingKnowledge(
                possible_unknown=True,
                source_value_origins=iter_knowledge.source_value_origins,
                builtin_value_kinds=self._iterated_builtin_value_kinds(iter_knowledge),
            ),
            member_effect_must_apply=False,
        )
        self._visit_binding_paths(((), (*node.body, *node.orelse)))

    # ast.NodeVisitor requires these exact protocol spellings.
    visit_AsyncFor = visit_For  # noqa: N815

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)
        self._visit_binding_paths(((), (*node.body, *node.orelse)))

    def visit_Try(self, node: ast.Try) -> None:
        base = self._snapshot_bindings()
        states = []
        self._restore_bindings(base)
        for statement in (*node.body, *node.orelse, *node.finalbody):
            self.visit(statement)
        states.append(self._snapshot_bindings())
        for handler in node.handlers:
            self._restore_bindings(base)
            handler_origins = (
                self._source_value_origins_for_expression(handler.type)
                if handler.type is not None
                else set()
            )
            if handler.type is not None:
                self.visit(handler.type)
            if handler.name:
                self._bind_unknown({handler.name}, source_value_origins=handler_origins)
            for statement in (*handler.body, *node.finalbody):
                self.visit(statement)
            if handler.name:
                self._bind_unknown({handler.name})
            states.append(self._snapshot_bindings())
        self._merge_binding_states(states)

    # ast.NodeVisitor requires these exact protocol spellings.
    visit_TryStar = visit_Try  # noqa: N815

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        handler_origins = (
            self._source_value_origins_for_expression(node.type) if node.type is not None else set()
        )
        if node.type is not None:
            self.visit(node.type)
        if node.name:
            self._bind_unknown({node.name}, source_value_origins=handler_origins)
        for statement in node.body:
            self.visit(statement)
        if node.name:
            self._bind_unknown({node.name})

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            context_origins = self._source_value_origins_for_expression(item.context_expr)
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind_unknown_target(item.optional_vars, context_origins)
        for statement in node.body:
            self.visit(statement)

    # ast.NodeVisitor requires these exact protocol spellings.
    visit_AsyncWith = visit_With  # noqa: N815

    def _visit_comprehension(
        self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
    ) -> None:
        generators = node.generators
        target_names = (
            set().union(*(_binding_names(generator.target) for generator in generators))
            if generators
            else set()
        )
        previous_bindings = self._binding_knowledge_snapshot()
        previous_type_bindings = self.type_checking_bindings.copy()
        try:
            for generator in generators:
                iter_knowledge = self._knowledge_for_expression(generator.iter)
                self.visit(generator.iter)
                self._bind_target_knowledge(
                    generator.target,
                    _BindingKnowledge(
                        possible_unknown=True,
                        source_value_origins=iter_knowledge.source_value_origins,
                        builtin_value_kinds=self._iterated_builtin_value_kinds(iter_knowledge),
                    ),
                    member_effect_must_apply=False,
                )
                for condition in generator.ifs:
                    self.visit(condition)
            if isinstance(node, ast.DictComp):
                self.visit(node.key)
                self.visit(node.value)
            else:
                self.visit(node.elt)
        finally:
            for name in target_names:
                self._clear_name_bindings({name})
                if name in previous_bindings:
                    self._write_binding_knowledge(name, previous_bindings[name])
                if name in previous_type_bindings:
                    self.type_checking_bindings[name] = previous_type_bindings[name]

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node)

    # ast.NodeVisitor requires these exact protocol spellings.
    visit_SetComp = visit_ListComp  # noqa: N815
    # ast.NodeVisitor requires these exact protocol spellings.
    visit_DictComp = visit_ListComp  # noqa: N815
    # ast.NodeVisitor requires these exact protocol spellings.
    visit_GeneratorExp = visit_ListComp  # noqa: N815

    @staticmethod
    def _binding_knowledge_is_unbound(knowledge: _BindingKnowledge) -> bool:
        """Prove a name has no binding in any channel of the joined state."""
        return knowledge == _BindingKnowledge()

    @staticmethod
    def _binding_knowledge_is_exact_import(
        knowledge: _BindingKnowledge,
        *,
        module: str,
        symbol: str | None,
    ) -> bool:
        """Prove every retained binding channel names exactly one import target."""
        target = _BindingTarget("import", module, symbol)
        return knowledge == _BindingKnowledge(known_possible_targets=frozenset({target}))

    def _known_builtin_symbol(self, node: ast.AST) -> str | None:
        """Resolve only a wholly unbound builtin or an exact ``builtins`` import."""
        if isinstance(node, ast.Name):
            knowledge = self._binding_knowledge(node.id)
            imports = knowledge.targets_for("import")
            if imports:
                if len(imports) == 1:
                    imported = next(iter(imports))
                    if (
                        imported.module == "builtins"
                        and imported.symbol is not None
                        and self._binding_knowledge_is_exact_import(
                            knowledge,
                            module="builtins",
                            symbol=imported.symbol,
                        )
                    ):
                        return imported.symbol
                return None
            if self._binding_knowledge_is_unbound(knowledge) and hasattr(builtins, node.id):
                return node.id
            return None
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            knowledge = self._binding_knowledge(node.value.id)
            if self._binding_knowledge_is_exact_import(
                knowledge,
                module="builtins",
                symbol=None,
            ):
                return node.attr
        return None

    def _is_known_builtin_class_expression(self, node: ast.AST) -> bool:
        """Return whether an expression resolves to a real builtin class object."""
        symbol = self._known_builtin_symbol(node)
        return symbol is not None and isinstance(getattr(builtins, symbol, None), type)

    def _effective_metaclass_knowledge(
        self,
        class_target: tuple[str, str],
        seen: frozenset[tuple[str, str]] = frozenset(),
    ) -> _BindingKnowledge:
        """Resolve a source class's inherited metaclass without using syntax presence."""
        if class_target in seen:
            return _BindingKnowledge(possible_unknown=True)
        explicit = self.source_class_metaclasses.get(class_target)
        if explicit is not None:
            if class_target in self.source_class_base_unknown:
                return explicit.join(_BindingKnowledge(possible_unknown=True))
            return explicit
        if class_target in self.source_class_base_unknown:
            inherited = _BindingKnowledge()
            for base in sorted(self.source_class_bases.get(class_target, set())):
                inherited = inherited.join(
                    self._effective_metaclass_knowledge(base, seen | {class_target})
                )
            return inherited.join(_BindingKnowledge(possible_unknown=True))
        bases = self.source_class_bases.get(class_target, set())
        if not bases:
            if class_target not in self.class_index:
                return _BindingKnowledge(possible_unknown=True)
            return _BindingKnowledge(builtin_value_kinds=frozenset({"type"}))

        inherited = _BindingKnowledge()
        for base in sorted(bases):
            inherited = inherited.join(
                self._effective_metaclass_knowledge(base, seen | {class_target})
            )
        candidates = self._class_targets_from_knowledge(inherited)
        if not candidates:
            if (
                inherited.builtin_value_kinds == frozenset({"type"})
                and not inherited.possible_unknown
            ):
                return inherited
            return inherited.join(_BindingKnowledge(possible_unknown=True))
        most_derived = {
            candidate
            for candidate in candidates
            if all(
                candidate == other or self._source_class_is_subclass(candidate, other)
                for other in candidates
            )
        }
        if len(most_derived) != 1:
            return inherited.join(_BindingKnowledge(possible_unknown=True))
        selected = next(iter(most_derived))
        return _BindingKnowledge(
            frozenset({_BindingTarget("class", *selected)}),
            inherited.possible_unknown,
            inherited.source_value_origins,
        )

    def _indexed_source_method_targets(
        self, class_target: tuple[str, str], member: str
    ) -> set[tuple[str, str, int, int]]:
        """Return all source definitions with this class-member identity."""
        module, class_name = class_target
        qualified_name = f"{class_name}.{member}"
        return {
            reference
            for reference in self.source_functions
            if reference[0] == module and reference[1] == qualified_name
        }

    def _source_method_targets_for_class(
        self,
        class_target: tuple[str, str],
        member: str,
        seen: frozenset[tuple[str, str]] = frozenset(),
    ) -> tuple[set[tuple[str, str, int, int]], bool]:
        """Resolve a source method through its complete source-base lineage."""
        if class_target in seen:
            return set(), True
        module, class_name = class_target
        members = (
            self.class_member_bindings
            if module == self.module
            else self.external_class_exports.get(module, {})
        ).get(class_name, {})
        member_knowledge = members.get(member)
        if member_knowledge is not None:
            invocation = self._callable_targets_for_knowledge(member_knowledge)
            targets = {
                (target.module, target.symbol or "", target.line, target.column)
                for target in invocation.known_possible_targets
                if target.kind == "callable"
            }
            if not targets:
                targets.update(self._indexed_source_method_targets(class_target, member))
            return targets, invocation.possible_unknown or not bool(targets)

        indexed = self._indexed_source_method_targets(class_target, member)
        if indexed:
            return indexed, False
        direct = self._callable_in_module(module, f"{class_name}.{member}")
        if direct:
            return direct, False
        if class_target in self.source_class_base_unknown:
            return set(), True
        bases = self.source_class_bases.get(class_target, set())
        if not bases:
            return set(), class_target not in self.class_index

        targets: set[tuple[str, str, int, int]] = set()
        unresolved = False
        for base in sorted(bases):
            inherited, incomplete = self._source_method_targets_for_class(
                base, member, seen | {class_target}
            )
            targets.update(inherited)
            unresolved = unresolved or incomplete
        return targets, unresolved

    def _function_returns_exact_builtin_strings(self, reference: tuple[str, str, int, int]) -> bool:
        """Prove a hook returns only literal, exact builtin strings on all returns."""
        function = self.source_functions.get(reference)
        if function is None or function.decorator_list or not function.body:
            return False
        if not isinstance(function.body[-1], ast.Return):
            return False
        return_nodes: list[ast.Return] = []

        class _Returns(ast.NodeVisitor):
            def visit_Return(self, node: ast.Return) -> None:
                return_nodes.append(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                if node is function:
                    for statement in node.body:
                        self.visit(statement)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                if node is function:
                    for statement in node.body:
                        self.visit(statement)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                return

        _Returns().visit(function)
        if not return_nodes:
            return False
        for return_node in return_nodes:
            value = return_node.value
            if not isinstance(value, (ast.List, ast.Tuple)):
                return False
            if any(
                not isinstance(element, ast.Constant) or type(element.value) is not str
                for element in value.elts
            ):
                return False
        return True

    def _builtin_dir_hook_summary(
        self,
        node: ast.Call,
        *,
        receiver_knowledge: _BindingKnowledge | None = None,
    ) -> tuple[
        set[tuple[str, str, int, int]],
        bool,
        set[_BindingTarget],
        set[tuple[str, str]],
    ]:
        """Resolve source hooks and uncertainty behind the builtin ``dir`` call."""
        hooks: set[tuple[str, str, int, int]] = set()
        unresolved = False
        origins: set[_BindingTarget] = set()
        class_targets: set[tuple[str, str]] = set()
        if not node.args:
            return hooks, unresolved, origins, class_targets

        receiver = node.args[0]
        knowledge = (
            receiver_knowledge
            if receiver_knowledge is not None
            else self._knowledge_for_expression(receiver)
        )
        origins.update(knowledge.source_value_origins)
        origins.update(self._source_origins_from_targets(knowledge.known_possible_targets))

        for target in knowledge.targets_for("import"):
            if target.symbol is not None:
                continue
            if target.module not in self.module_names:
                continue
            module_binding = (
                self._binding_knowledge("__dir__")
                if target.module == self.module
                else self.external_module_exports.get(target.module, {}).get(
                    "__dir__", _BindingKnowledge()
                )
            )
            if not module_binding.known_possible_targets and not module_binding.possible_unknown:
                continue
            invocation = self._callable_targets_for_knowledge(module_binding)
            module_hooks = {
                (item.module, item.symbol or "", item.line, item.column)
                for item in invocation.known_possible_targets
                if item.kind == "callable"
            }
            hooks.update(module_hooks)
            unresolved = unresolved or invocation.possible_unknown or not bool(module_hooks)

        instance_classes = {
            class_target
            for target in knowledge.targets_for("instance")
            if (class_target := _instance_class_for_target(target)) is not None
        }
        for instance_class in sorted(instance_classes):
            method_hooks, incomplete = self._source_method_targets_for_class(
                instance_class, "__dir__"
            )
            hooks.update(method_hooks)
            unresolved = unresolved or incomplete
            class_targets.add(instance_class)

        class_object_targets = self._class_targets_from_knowledge(knowledge)
        class_targets.update(class_object_targets)
        for class_target in sorted(class_object_targets):
            metaclass = self._effective_metaclass_knowledge(class_target)
            metaclass_classes = self._class_targets_from_knowledge(metaclass)
            if metaclass.possible_unknown:
                unresolved = True
            if not metaclass_classes:
                if "type" not in metaclass.builtin_value_kinds:
                    unresolved = True
                continue
            for metaclass_class in sorted(metaclass_classes):
                method_hooks, incomplete = self._source_method_targets_for_class(
                    metaclass_class, "__dir__"
                )
                hooks.update(method_hooks)
                unresolved = unresolved or incomplete

        if not class_targets and not any(
            target.kind == "import" and target.symbol is None and target.module in self.module_names
            for target in knowledge.known_possible_targets
        ):
            if knowledge.source_value_origins or self._source_origins_from_targets(
                knowledge.known_possible_targets
            ):
                unresolved = True
        origins.update(
            _BindingTarget("source_call", module, symbol, line, column)
            for module, symbol, line, column in hooks
            if module in self.module_names
        )
        return hooks, unresolved, origins, class_targets

    def _builtin_dir_result_knowledge(self, node: ast.Call) -> _BindingKnowledge | None:
        """Keep exact builtin-name results distinct from source-defined values."""
        if self._known_builtin_symbol(node.func) != "dir":
            return None
        if not node.args:
            return _BindingKnowledge(builtin_value_kinds=frozenset({"sequence[str]"}))
        hooks, unresolved, origins, _class_targets = self._builtin_dir_hook_summary(node)
        if not hooks and not unresolved:
            return _BindingKnowledge(builtin_value_kinds=frozenset({"sequence[str]"}))
        if (
            hooks
            and not unresolved
            and all(self._function_returns_exact_builtin_strings(reference) for reference in hooks)
        ):
            return _BindingKnowledge(builtin_value_kinds=frozenset({"sequence[str]"}))
        return _BindingKnowledge(
            possible_unknown=True,
            source_value_origins=frozenset(origins),
            builtin_value_kinds=frozenset({"sequence[unknown]"}),
        )

    def _builtin_call_result_kinds(self, node: ast.Call) -> frozenset[str]:
        """Return only result kinds established by source and builtin identity."""
        result = self._builtin_dir_result_knowledge(node)
        return result.builtin_value_kinds if result is not None else frozenset()

    def _iterated_builtin_value_kinds(self, knowledge: _BindingKnowledge) -> frozenset[str]:
        """Transfer known element kinds from builtin string sequences."""
        if (
            "sequence[str]" in knowledge.builtin_value_kinds
            or "str" in knowledge.builtin_value_kinds
        ):
            return frozenset({"str"})
        return frozenset()

    def _source_value_origins_for_expression(self, node: ast.AST) -> set[_BindingTarget]:
        """Carry source-owned expression ancestry through every visited AST form."""
        if isinstance(node, ast.Call):
            builtin_result = self._builtin_dir_result_knowledge(node)
            if builtin_result is not None:
                return set(builtin_result.source_value_origins)
        if isinstance(node, ast.Name):
            knowledge = self._binding_knowledge(node.id)
            origins = set(knowledge.source_value_origins)
            origins.update(self._source_origins_from_targets(knowledge.known_possible_targets))
            return origins

        origins = set().union(
            *(
                self._source_value_origins_for_expression(child)
                for child in ast.iter_child_nodes(node)
            )
        )
        if isinstance(node, ast.Call):
            class_targets = self._class_targets(node.func)
            if class_targets:
                origins.update(
                    _BindingTarget(
                        "instance",
                        self.module,
                        f"{module}::{class_name}",
                        node.lineno,
                        node.col_offset,
                    )
                    for module, class_name in class_targets
                )
            else:
                origins.update(
                    _BindingTarget("source_call", module, symbol, line, column)
                    for module, symbol, line, column in self._callable_target(node.func)
                    if module in self.module_names
                )
        return origins

    def _source_value_for_expression(self, node: ast.AST) -> _DynamicImportBinding:
        """Evaluate bounded string/container values; all unsupported forms refuse."""
        if isinstance(node, ast.Constant):
            return (
                _dynamic_string_binding(node.value)
                if isinstance(node.value, str)
                else _DYNAMIC_OTHER
            )
        if isinstance(node, ast.Name):
            knowledge = self._binding_knowledge(node.id)
            value = knowledge.source_value or _DYNAMIC_UNKNOWN
            return (
                _join_dynamic_bindings((value, _DYNAMIC_UNKNOWN))
                if knowledge.possible_unknown
                else value
            )
        if isinstance(node, (ast.NamedExpr, ast.Starred)):
            return self._source_value_for_expression(node.value)
        if isinstance(node, ast.BinOp):
            left = self._source_value_for_expression(node.left)
            right = self._source_value_for_expression(node.right)
            return (
                _source_value_add(left, right) if isinstance(node.op, ast.Add) else _DYNAMIC_UNKNOWN
            )
        if isinstance(node, ast.IfExp):
            return _dynamic_union_binding(
                (
                    self._source_value_for_expression(node.body),
                    self._source_value_for_expression(node.orelse),
                )
            )
        if isinstance(node, ast.BoolOp):
            return _dynamic_union_binding(
                tuple(self._source_value_for_expression(value) for value in node.values)
            )
        if isinstance(node, (ast.Tuple, ast.List)):
            return _dynamic_sequence_binding(
                tuple(self._source_value_for_expression(value) for value in node.elts)
            )
        if isinstance(node, ast.Set):
            return _dynamic_sequence_binding(
                tuple(self._source_value_for_expression(value) for value in node.elts),
                kind="iterable",
            )
        if isinstance(node, ast.Dict):
            keys: list[_DynamicImportBinding] = []
            values: list[_DynamicImportBinding] = []
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None:
                    return _DYNAMIC_UNKNOWN
                keys.append(self._source_value_for_expression(key))
                values.append(self._source_value_for_expression(value))
            return _dynamic_mapping_binding(keys, values)
        if isinstance(node, ast.Subscript):
            value = self._source_value_for_expression(node.value)
            index = node.slice.value if isinstance(node.slice, ast.Constant) else None
            if value.kind in {"sequence", "iterable"} and value.items is not None:
                if isinstance(index, int) and -len(value.items) <= index < len(value.items):
                    return value.items[index]
                return _DYNAMIC_UNKNOWN
            if value.kind == "mapping" and value.items is not None and value.values is not None:
                key_value = self._source_value_for_expression(node.slice)
                matches = [
                    item
                    for key, item in zip(value.items, value.values, strict=True)
                    if _dynamic_bindings_may_equal(key_value, key)
                ]
                return _dynamic_union_binding(matches) if matches else _DYNAMIC_UNKNOWN
            return _DYNAMIC_UNKNOWN
        if isinstance(node, ast.UnaryOp):
            return _DYNAMIC_OTHER if isinstance(node.op, ast.Not) else _DYNAMIC_UNKNOWN
        if isinstance(node, ast.Compare):
            return _DYNAMIC_OTHER
        if isinstance(node, (ast.JoinedStr, ast.FormattedValue, ast.Call, ast.Attribute)):
            return _DYNAMIC_UNKNOWN
        # Unknown AST expression kinds fail closed; the coverage receipt must
        # reconcile all encountered classes against this dispatcher.
        return _DYNAMIC_UNKNOWN

    def _knowledge_for_expression(self, node: ast.AST) -> _BindingKnowledge:
        knowledge = self._target_knowledge_for_expression(node)
        return replace(knowledge, source_value=self._source_value_for_expression(node))

    def _target_knowledge_for_expression(self, node: ast.AST) -> _BindingKnowledge:
        if isinstance(node, ast.Name):
            return self._expand_import_bindings(self._binding_knowledge(node.id))

        origins = frozenset(self._source_value_origins_for_expression(node))
        if isinstance(node, (ast.Dict, ast.DictComp)):
            # Dictionary literals/comprehensions construct exact builtin dicts.
            # Their contents may be source-derived, but that does not make key
            # storage an unknown dispatch operation.
            return _BindingKnowledge(
                source_value_origins=origins,
                builtin_value_kinds=frozenset({"dict"}),
            )
        if isinstance(node, ast.Call):
            builtin_result = self._builtin_dir_result_knowledge(node)
            if builtin_result is not None:
                return builtin_result
        if isinstance(node, ast.Attribute):
            receiver_knowledge = self._knowledge_for_expression(node.value)
            if (
                receiver_knowledge.builtin_value_kinds == frozenset({"str"})
                and not receiver_knowledge.known_possible_targets
                and not receiver_knowledge.source_value_origins
            ):
                # Exact builtin strings cannot resolve to source-defined methods.
                return _BindingKnowledge(builtin_value_kinds=frozenset({"builtin_member"}))
            receiver_classes = self._instance_class_targets(node.value)
            receiver_classes.update(self._class_targets(node.value))
            owner_targets, owner_incomplete = self._owner_targets_for_knowledge(receiver_knowledge)
            stored_member, stored_found = self._owner_member_knowledge(
                owner_targets, f"attr:{node.attr}"
            )
            if stored_found:
                if owner_incomplete:
                    stored_member = stored_member.join(_BindingKnowledge(possible_unknown=True))
                return stored_member.join(_BindingKnowledge(source_value_origins=origins))
            if receiver_classes:
                member_knowledge = self._class_member_knowledge(receiver_classes, node.attr)
                if receiver_knowledge.possible_unknown or owner_incomplete:
                    member_knowledge = member_knowledge.join(
                        _BindingKnowledge(possible_unknown=True)
                    )
                return member_knowledge.join(_BindingKnowledge(source_value_origins=origins))
            parts = self._dotted_name(node)
            if len(parts) > 1:
                root = self._binding_knowledge(parts[0])
                suffix = parts[1:]
                resolved = _BindingKnowledge()
                for imported in root.targets_for("import"):
                    if imported.symbol is not None:
                        symbol = ".".join([imported.symbol, *suffix])
                        exported = self.external_module_exports.get(imported.module, {}).get(symbol)
                        if exported is not None:
                            resolved = resolved.join(exported)
                    elif suffix:
                        candidate_module = ".".join([imported.module, *suffix[:-1]])
                        resolved_module = _nearest_known_module(candidate_module, self.module_names)
                        if resolved_module:
                            exported = self.external_module_exports.get(resolved_module, {}).get(
                                suffix[-1]
                            )
                            if exported is not None:
                                resolved = resolved.join(exported)
                if not resolved.known_possible_targets and not resolved.possible_unknown:
                    # Preserve exact external module-member identity. This is a
                    # call-target fact only; it does not claim the external body
                    # or its returned value is modeled.
                    for imported in root.targets_for("import"):
                        if imported.module in self.module_names:
                            continue
                        symbol = ".".join(part for part in (imported.symbol, *suffix) if part)
                        if symbol:
                            resolved = resolved.join(
                                _BindingKnowledge(
                                    frozenset({_BindingTarget("import", imported.module, symbol)})
                                )
                            )
                if resolved.known_possible_targets or resolved.possible_unknown:
                    if root.possible_unknown:
                        resolved = resolved.join(_BindingKnowledge(possible_unknown=True))
                    return resolved.join(_BindingKnowledge(source_value_origins=origins))
            return _BindingKnowledge(possible_unknown=True, source_value_origins=origins)

        if isinstance(node, ast.Subscript):
            owner_knowledge = self._knowledge_for_expression(node.value)
            owner_targets, owner_incomplete = self._owner_targets_for_knowledge(owner_knowledge)
            member = self._storage_member_name(node)
            if member is not None:
                stored_member, stored_found = self._owner_member_knowledge(owner_targets, member)
                if stored_found:
                    if owner_incomplete:
                        stored_member = stored_member.join(_BindingKnowledge(possible_unknown=True))
                    return stored_member.join(_BindingKnowledge(source_value_origins=origins))
            return _BindingKnowledge(possible_unknown=True, source_value_origins=origins)

        if isinstance(node, ast.Call):
            callee_knowledge = self._knowledge_for_expression(node.func)
            class_targets = self._class_targets(node.func)
            if class_targets:
                allocation_unknown = any(
                    self._callable_in_module(module, f"{class_name}.__new__")
                    for module, class_name in class_targets
                )
                return _BindingKnowledge(
                    frozenset(
                        _BindingTarget(
                            "instance",
                            self.module,
                            f"{module}::{class_name}",
                            node.lineno,
                            node.col_offset,
                        )
                        for module, class_name in class_targets
                    ),
                    callee_knowledge.possible_unknown or allocation_unknown,
                    origins,
                )
            invocation = self._callable_targets_for_knowledge(callee_knowledge)
            factories = {
                _BindingTarget(
                    "source_call", target.module, target.symbol, target.line, target.column
                )
                for target in invocation.known_possible_targets
                if target.kind == "callable"
            }
            opaque_external_target = any(
                target.kind == "import"
                and not self._targets_from_import(target.module, target.symbol, ())
                for target in callee_knowledge.known_possible_targets
            )
            return _BindingKnowledge(
                frozenset(factories),
                bool(factories) or invocation.possible_unknown or opaque_external_target,
                origins,
            )

        # Subscripts, containers, operators, and other unmodeled expression forms
        # remain unknown while retaining every source-owned child origin.
        return _BindingKnowledge(possible_unknown=True, source_value_origins=origins)

    def _observation_knowledge(
        self,
        base: _BindingKnowledge,
        class_targets: set[tuple[str, str]],
        callable_targets: set[tuple[str, str, int, int]],
        reasons: set[str],
    ) -> _BindingKnowledge:
        targets = set(base.known_possible_targets)
        targets.update(
            _BindingTarget("dispatch_class", module, symbol) for module, symbol in class_targets
        )
        targets.update(
            _BindingTarget("dispatch_callable", module, symbol, line, column)
            for module, symbol, line, column in callable_targets
        )
        return _BindingKnowledge(
            frozenset(targets),
            base.possible_unknown or bool(reasons),
            base.source_value_origins,
        )

    def _record_dispatch_resolution(self, node: ast.AST, *, call: ast.Call | None = None) -> None:
        function_knowledge = self._knowledge_for_expression(node)
        invocation = self._callable_targets_for_knowledge(function_knowledge)
        callable_targets = {
            (target.module, target.symbol or "", target.line, target.column)
            for target in invocation.known_possible_targets
            if target.kind == "callable"
        }
        class_targets: set[tuple[str, str]] = set()
        source_derived_receiver = False
        receiver_knowledge = function_knowledge
        if isinstance(node, ast.Name):
            class_targets = self._class_targets(node)
            if class_targets:
                # Constructor dispatch has its own observation and allocation rules.
                return
            source_derived_receiver = invocation.possible_unknown and bool(
                function_knowledge.source_value_origins
            )
            instance_classes = self._instance_class_targets(node)
            has_unresolved_known_value = invocation.possible_unknown and bool(
                function_knowledge.known_possible_targets or function_knowledge.source_value_origins
            )
            if not instance_classes and not has_unresolved_known_value:
                return
            class_targets.update(instance_classes)
            receiver_form = "Name"
        elif isinstance(node, ast.Attribute):
            receiver = node.value
            receiver_knowledge = self._knowledge_for_expression(receiver)
            source_derived_receiver = receiver_knowledge.possible_unknown and bool(
                receiver_knowledge.source_value_origins
            )
            class_targets = self._instance_class_targets(receiver)
            class_targets.update(self._class_targets(receiver))
            callable_targets.update(self._class_method_targets(class_targets, node.attr))
            receiver_form = type(receiver).__name__
        elif isinstance(node, ast.Call):
            class_targets = self._instance_class_targets(node)
            source_derived_receiver = function_knowledge.possible_unknown and bool(
                function_knowledge.source_value_origins
            )
            receiver_form = "Call"
        else:
            return

        reasons: set[str] = set()
        if invocation.possible_unknown:
            if source_derived_receiver:
                reason = (
                    "source_callable_return_not_summarized"
                    if any(
                        target.kind == "source_call"
                        for target in receiver_knowledge.source_value_origins
                    )
                    else "source_derived_receiver_not_summarized"
                )
                reasons.add(reason)
            else:
                reasons.add(
                    "source_member_call_target_not_summarized"
                    if not function_knowledge.possible_unknown
                    and function_knowledge.known_possible_targets
                    else "source_possible_unknown_target"
                )
        if class_targets and not callable_targets and not invocation.possible_unknown:
            reasons.add("source_class_method_lookup_not_summarized")
        if not class_targets and not callable_targets and not source_derived_receiver:
            return
        observation_base = (
            function_knowledge.join(receiver_knowledge)
            if source_derived_receiver
            else function_knowledge
        )
        binding_knowledge = self._observation_knowledge(
            observation_base, class_targets, callable_targets, reasons
        )
        self._record_dispatch_observation(
            call or node,
            receiver_form=receiver_form,
            class_targets=class_targets,
            callable_targets=callable_targets,
            reasons=reasons,
            binding_knowledge=binding_knowledge,
            record_unresolved_value=source_derived_receiver,
        )

    def _record_dispatch_observation(
        self,
        node: ast.AST,
        *,
        receiver_form: str,
        class_targets: set[tuple[str, str]],
        callable_targets: set[tuple[str, str, int, int]],
        reasons: set[str],
        binding_knowledge: _BindingKnowledge,
        record_unresolved_value: bool = False,
    ) -> None:
        if not class_targets and not callable_targets and not record_unresolved_value:
            return
        try:
            expression = ast.unparse(node)
        except AttributeError, ValueError:
            expression = f"{type(node).__name__}@{node.lineno}:{node.col_offset}"
        source_targets = sorted(
            [f"{module}.{symbol}" for module, symbol in class_targets]
            + [
                f"{module}.{symbol}@{line}:{column}"
                for module, symbol, line, column in callable_targets
            ]
        )
        resolved = binding_knowledge.definitely_resolved and not reasons
        status = "resolved" if resolved else "not_established"
        reason = sorted(reasons)[0] if reasons else "source_target_resolved"
        row = {
            "status": status,
            "source_path": self.source_path,
            "source_module": self.module,
            "line": node.lineno,
            "column": node.col_offset,
            "expression": expression,
            "receiver_form": receiver_form,
            "reason": reason,
            "known_source_targets": source_targets,
            "source_value_origins": sorted(
                f"{target.module}.{target.symbol or ''}@{target.line}:{target.column}"
                for target in binding_knowledge.source_value_origins
                if target.module in self.module_names
            ),
        }
        key = (
            node.lineno,
            node.col_offset,
            expression,
            status,
            reason,
            tuple(source_targets),
        )
        self.dispatch_observations[key] = row

    def _builtin_owner_mutators(
        self,
        function: ast.AST,
        *,
        function_knowledge: _BindingKnowledge | None = None,
        attribute_receiver_knowledge: _BindingKnowledge | None = None,
    ) -> tuple[frozenset[str], bool]:
        """Return possible builtin effects and whether that effect is guaranteed."""
        known_targets: set[_BindingTarget] = set()
        possible_unknown = False
        implicit_builtin: str | None = None
        if isinstance(function, ast.Name):
            knowledge = function_knowledge or self._binding_knowledge(function.id)
            known_targets = set(knowledge.known_possible_targets)
            possible_unknown = knowledge.possible_unknown
            if function.id in {"setattr", "delattr"}:
                if not known_targets and not possible_unknown:
                    implicit_builtin = function.id
                elif possible_unknown:
                    # An unknown branch may be the unshadowed builtin name.
                    implicit_builtin = function.id
        elif isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            if function.attr not in {"setattr", "delattr"}:
                return frozenset(), False
            module_knowledge = (
                attribute_receiver_knowledge
                if attribute_receiver_knowledge is not None
                else self._binding_knowledge(function.value.id)
            )
            known_targets = set(module_knowledge.known_possible_targets)
            possible_unknown = module_knowledge.possible_unknown
            if possible_unknown:
                implicit_builtin = function.attr

        mutators = {
            target.symbol
            for target in known_targets
            if target.kind == "import"
            and target.module == "builtins"
            and target.symbol in {"setattr", "delattr"}
        }
        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            if any(
                target.kind == "import" and target.module == "builtins" and target.symbol is None
                for target in known_targets
            ):
                mutators.add(function.attr)
        if implicit_builtin is not None:
            mutators.add(implicit_builtin)
        exact_builtin = (
            len(mutators) == 1
            and not possible_unknown
            and (
                implicit_builtin == next(iter(mutators))
                or (
                    len(known_targets) == 1
                    and next(iter(known_targets)).kind == "import"
                    and next(iter(known_targets)).module == "builtins"
                    and next(iter(known_targets)).symbol == next(iter(mutators))
                )
                or (
                    isinstance(function, ast.Attribute)
                    and len(known_targets) == 1
                    and next(iter(known_targets)).kind == "import"
                    and next(iter(known_targets)).module == "builtins"
                    and next(iter(known_targets)).symbol is None
                )
            )
        )
        return frozenset(mutators), exact_builtin

    def _record_unresolved_builtin_override(
        self, node: ast.Call, knowledge: _BindingKnowledge, class_targets: set[tuple[str, str]]
    ) -> None:
        reason = "source_builtin_override_not_summarized"
        self._record_dispatch_observation(
            node,
            receiver_form="BuiltinOverride",
            class_targets=class_targets,
            callable_targets=set(),
            reasons={reason},
            binding_knowledge=self._observation_knowledge(
                knowledge, class_targets, set(), {reason}
            ),
            record_unresolved_value=True,
        )

    def _record_builtin_call_overrides(
        self,
        node: ast.Call,
        *,
        builtin_symbol: str | None = None,
        first_argument_knowledge: _BindingKnowledge | None = None,
    ) -> None:
        """Follow the evaluated builtin ``dir`` call through source class lineage."""
        resolved_symbol = (
            self._known_builtin_symbol(node.func) if builtin_symbol is None else builtin_symbol
        )
        if resolved_symbol != "dir" or not node.args:
            return
        hooks, unresolved, origins, class_targets = self._builtin_dir_hook_summary(
            node, receiver_knowledge=first_argument_knowledge
        )
        self._record_targets(hooks)
        if unresolved:
            self._record_unresolved_builtin_override(
                node,
                _BindingKnowledge(
                    possible_unknown=True,
                    source_value_origins=frozenset(origins),
                ),
                class_targets,
            )

    def _record_builtin_owner_mutation(self, node: ast.Call, *, frame: _EvaluatedCallFrame) -> None:
        mutators, mutator_is_guaranteed = self._builtin_owner_mutators(
            node.func,
            function_knowledge=frame.callable_knowledge,
            attribute_receiver_knowledge=frame.receiver_knowledge,
        )
        captured_arguments = dict(frame.argument_knowledge)

        def captured(value: ast.AST) -> _BindingKnowledge:
            knowledge = captured_arguments.get(id(value))
            if knowledge is not None:
                return knowledge
            return self._knowledge_for_expression(value)

        if not mutators:
            return

        valid_setter = "setattr" in mutators and len(node.args) == 3
        valid_deleter = "delattr" in mutators and len(node.args) == 2
        has_valid_shape = not node.keywords and (valid_setter or valid_deleter)
        owner_knowledge = (
            captured(node.args[0]) if node.args else _BindingKnowledge(possible_unknown=True)
        )
        origins = set(owner_knowledge.source_value_origins)
        for argument in node.args:
            argument_value = captured(argument)
            origins.update(argument_value.source_value_origins)
            origins.update(self._source_origins_from_targets(argument_value.known_possible_targets))

        attribute = node.args[1] if len(node.args) > 1 else None
        member = (
            f"attr:{attribute.value}"
            if isinstance(attribute, ast.Constant) and isinstance(attribute.value, str)
            else None
        )
        value_knowledge = _BindingKnowledge()
        if valid_setter:
            value_knowledge = captured(node.args[2])
        if "delattr" in mutators:
            value_knowledge = value_knowledge.join(
                _BindingKnowledge(
                    possible_unknown=True,
                    source_value_origins=owner_knowledge.source_value_origins,
                )
            )
        if not has_valid_shape:
            value_knowledge = value_knowledge.join(
                _BindingKnowledge(
                    possible_unknown=True,
                    source_value_origins=frozenset(origins),
                )
            )
            member = None
        must_apply = mutator_is_guaranteed and has_valid_shape and len(mutators) == 1
        self._apply_owner_member_effect(
            node,
            owner_knowledge,
            member,
            value_knowledge,
            must_apply=must_apply,
        )

    def _parameter_is_referenced(
        self, function: ast.FunctionDef | ast.AsyncFunctionDef, parameter: str
    ) -> bool:
        """Find formal uses in the body, including aliases and closures."""
        return any(
            isinstance(child, ast.Name) and child.id == parameter
            for statement in function.body
            for child in ast.walk(statement)
        )

    def _parameter_call_usage(
        self, function: ast.FunctionDef | ast.AsyncFunctionDef, parameter: str
    ) -> str | None:
        """Classify a formal's use as a direct or unsupported call target.

        A binding is a callback only when it is actually used as a call target.
        Mere reads (for example, ``selected = inherited``) do not make the
        imported value a callback. Calls through subscripts or attributes remain
        explicit not-established observations rather than being guessed.
        """
        direct = False
        indirect = False

        class _CallTargetUsage(ast.NodeVisitor):
            def __init__(self) -> None:
                self.nested_scope = 0

            def visit_Call(self, node: ast.Call) -> None:
                nonlocal direct, indirect
                formal_names = {
                    child.id
                    for child in ast.walk(node.func)
                    if isinstance(child, ast.Name) and child.id == parameter
                }
                if formal_names:
                    if (
                        self.nested_scope == 0
                        and isinstance(node.func, ast.Name)
                        and node.func.id == parameter
                    ):
                        direct = True
                    else:
                        indirect = True
                self.generic_visit(node)

            def _visit_nested_scope(self, node: ast.AST) -> None:
                self.nested_scope += 1
                self.generic_visit(node)
                self.nested_scope -= 1

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._visit_nested_scope(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._visit_nested_scope(node)

            def visit_Lambda(self, node: ast.Lambda) -> None:
                self._visit_nested_scope(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._visit_nested_scope(node)

        visitor = _CallTargetUsage()
        for statement in function.body:
            visitor.visit(statement)
        if indirect:
            return "indirect"
        if direct:
            return "direct"
        return None

    def _source_class_is_subclass(
        self,
        candidate: tuple[str, str],
        base: tuple[str, str],
        seen: frozenset[tuple[str, str]] = frozenset(),
    ) -> bool:
        if candidate == base:
            return True
        if candidate in seen:
            return False
        return any(
            self._source_class_is_subclass(parent, base, seen | {candidate})
            for parent in self.source_class_bases.get(candidate, set())
        )

    def _method_descriptor_symbols(
        self, function: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> tuple[set[str], bool]:
        """Resolve descriptor decorators by binding identity, not final spelling."""
        symbols: set[str] = set()
        unknown = False
        for decorator in function.decorator_list:
            resolved = self._known_builtin_symbol(decorator)
            if resolved in {"staticmethod", "classmethod"}:
                symbols.add(resolved)
            else:
                unknown = True
        return symbols, unknown

    def _method_receiver_binding(
        self,
        node: ast.Call,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        reference: tuple[str, str, int, int],
        *,
        receiver_knowledge: _BindingKnowledge | None = None,
    ) -> tuple[_BindingKnowledge | None, str | None, bool]:
        """Bind self/cls using the receiver captured before argument evaluation."""
        class_name, separator, method_name = reference[1].rpartition(".")
        if not separator or (reference[0], class_name) not in self.class_index:
            return None, None, False
        positional = [*function.args.posonlyargs, *function.args.args]
        if not positional:
            return None, None, False
        decorator_names, unknown_descriptor = self._method_descriptor_symbols(function)
        if unknown_descriptor:
            return None, None, False
        if "staticmethod" in decorator_names and "classmethod" in decorator_names:
            return None, None, False
        receiver_parameter = positional[0].arg
        if "staticmethod" in decorator_names:
            return None, receiver_parameter, True
        if not isinstance(node.func, ast.Attribute) or node.func.attr != method_name:
            return None, None, False
        receiver = (
            receiver_knowledge
            if receiver_knowledge is not None
            else self._knowledge_for_expression(node.func.value)
        )
        receiver_classes = self._class_targets_from_knowledge(receiver)
        receiver_classes.update(
            class_target
            for target in receiver.targets_for("instance")
            if (class_target := _instance_class_for_target(target)) is not None
        )
        owner_class = (reference[0], class_name)
        if "classmethod" in decorator_names:
            matching = {
                candidate
                for candidate in receiver_classes
                if self._source_class_is_subclass(candidate, owner_class)
            }
            if matching:
                bound = _BindingKnowledge(
                    frozenset(
                        _BindingTarget("class", module, symbol) for module, symbol in matching
                    ),
                    receiver.possible_unknown,
                    receiver.source_value_origins,
                )
            else:
                bound = _BindingKnowledge(
                    possible_unknown=True,
                    source_value_origins=receiver.source_value_origins,
                )
            return bound, receiver_parameter, True
        matching_instances = {
            target
            for target in receiver.targets_for("instance")
            if (class_target := _instance_class_for_target(target)) is not None
            and self._source_class_is_subclass(class_target, owner_class)
        }
        if matching_instances:
            return (
                _BindingKnowledge(
                    frozenset(matching_instances),
                    receiver.possible_unknown,
                    receiver.source_value_origins,
                ),
                receiver_parameter,
                True,
            )
        if receiver_classes:
            # Entry through Class.method is unbound: receiver is explicit, but is
            # still not a callback formal.
            return None, receiver_parameter, True
        return (
            _BindingKnowledge(
                possible_unknown=True,
                source_value_origins=receiver.source_value_origins,
            ),
            receiver_parameter,
            True,
        )

    def _visit_call_argument_expression(
        self,
        expression: ast.AST,
        captured: dict[int, _BindingKnowledge],
        *,
        expand_literal: bool = False,
    ) -> _BindingKnowledge:
        """Visit one argument and freeze any statically expanded values."""
        if expand_literal and isinstance(expression, (ast.Tuple, ast.List)):
            for item in expression.elts:
                self.visit(item)
                captured[id(item)] = self._knowledge_for_expression(item)
            knowledge = self._knowledge_for_expression(expression)
        elif expand_literal and isinstance(expression, ast.Dict):
            for key, value in zip(expression.keys, expression.values, strict=True):
                if key is not None:
                    self.visit(key)
                    captured[id(key)] = self._knowledge_for_expression(key)
                self.visit(value)
                captured[id(value)] = self._knowledge_for_expression(value)
            knowledge = self._knowledge_for_expression(expression)
        else:
            self.visit(expression)
            knowledge = self._knowledge_for_expression(expression)
        captured[id(expression)] = knowledge
        return knowledge

    def _call_argument_bindings(
        self,
        node: ast.Call,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        reference: tuple[str, str, int, int],
        *,
        bound_receiver: _BindingKnowledge | None = None,
        evaluated_argument_knowledge: Mapping[int, _BindingKnowledge] | None = None,
    ) -> tuple[dict[str, _BindingKnowledge], list[_BindingKnowledge]]:
        """Bind call inputs from their evaluated values and captured defaults."""
        captured_values = evaluated_argument_knowledge or {}

        def argument_knowledge(value: ast.AST) -> _BindingKnowledge:
            captured = captured_values.get(id(value))
            return captured if captured is not None else self._knowledge_for_expression(value)

        default_bindings = (
            self.function_default_bindings.get(reference, {})
            if reference[0] == self.module
            else self.external_function_default_bindings.get(reference, {})
        )
        parameters: list[inspect.Parameter] = []
        positional = [*function.args.posonlyargs, *function.args.args]
        positional_default_names = {
            parameter.arg
            for parameter in positional[len(positional) - len(function.args.defaults) :]
        }
        keyword_default_names = {
            parameter.arg
            for parameter, default in zip(
                function.args.kwonlyargs, function.args.kw_defaults, strict=True
            )
            if default is not None
        }

        def parameter_default(name: str, has_default: bool) -> Any:
            if not has_default:
                return inspect.Parameter.empty
            return _CapturedDefault(
                default_bindings.get(name, _BindingKnowledge(possible_unknown=True))
            )

        for argument in function.args.posonlyargs:
            parameters.append(
                inspect.Parameter(
                    argument.arg,
                    inspect.Parameter.POSITIONAL_ONLY,
                    default=parameter_default(
                        argument.arg, argument.arg in positional_default_names
                    ),
                )
            )
        for argument in function.args.args:
            parameters.append(
                inspect.Parameter(
                    argument.arg,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=parameter_default(
                        argument.arg, argument.arg in positional_default_names
                    ),
                )
            )
        if function.args.vararg is not None:
            parameters.append(
                inspect.Parameter(function.args.vararg.arg, inspect.Parameter.VAR_POSITIONAL)
            )
        for argument, default in zip(
            function.args.kwonlyargs, function.args.kw_defaults, strict=True
        ):
            parameters.append(
                inspect.Parameter(
                    argument.arg,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=parameter_default(argument.arg, argument.arg in keyword_default_names),
                )
            )
        if function.args.kwarg is not None:
            parameters.append(
                inspect.Parameter(function.args.kwarg.arg, inspect.Parameter.VAR_KEYWORD)
            )

        try:
            signature = inspect.Signature(parameters)
        except ValueError:
            # A malformed or otherwise unsupported signature cannot justify a
            # complete callback binding claim.
            all_values = [*node.args, *(keyword.value for keyword in node.keywords)]
            unbound = [argument_knowledge(value) for value in all_values]
            unbound.extend(
                default_bindings[name]
                for name in default_bindings
                if self._parameter_is_referenced(function, name)
            )
            return {}, unbound

        positional_values: list[Any] = (
            [_CapturedDefault(bound_receiver)] if bound_receiver is not None else []
        )
        keyword_values: dict[str, ast.AST] = {}
        unknown_expansion = False
        for actual in node.args:
            if not isinstance(actual, ast.Starred):
                positional_values.append(actual)
                continue
            value = actual.value
            if isinstance(value, (ast.Tuple, ast.List)) and all(
                not isinstance(item, ast.Starred) for item in value.elts
            ):
                positional_values.extend(value.elts)
            else:
                unknown_expansion = True
        for keyword in node.keywords:
            if keyword.arg is not None:
                if keyword.arg in keyword_values:
                    unknown_expansion = True
                keyword_values[keyword.arg] = keyword.value
                continue
            value = keyword.value
            if isinstance(value, ast.Dict):
                for key, item in zip(value.keys, value.values, strict=True):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value in keyword_values:
                            unknown_expansion = True
                        keyword_values[key.value] = item
                    else:
                        unknown_expansion = True
            else:
                unknown_expansion = True

        if unknown_expansion:
            all_values = [*node.args, *(keyword.value for keyword in node.keywords)]
            unbound = [argument_knowledge(value) for value in all_values]
            unbound.extend(
                default_bindings[name]
                for name in default_bindings
                if self._parameter_is_referenced(function, name)
            )
            return {}, unbound

        try:
            bound = signature.bind(*positional_values, **keyword_values)
        except TypeError:
            # Calls which fail Python's own arity/duplicate rules never enter
            # the source callee, so their arguments do not transfer callbacks.
            return {}, []
        bound.apply_defaults()

        def value_knowledge(value: Any) -> _BindingKnowledge:
            if isinstance(value, _CapturedDefault):
                return value.knowledge
            if isinstance(value, ast.AST):
                return argument_knowledge(value)
            if isinstance(value, (tuple, list)):
                child_knowledge = tuple(value_knowledge(item) for item in value)
                knowledge = _BindingKnowledge()
                for child in child_knowledge:
                    knowledge = knowledge.join(child)
                source_items = tuple(
                    child.source_value or _DYNAMIC_UNKNOWN for child in child_knowledge
                )
                return replace(knowledge, source_value=_dynamic_sequence_binding(source_items))
            if isinstance(value, dict):
                names = tuple(value)
                child_knowledge = tuple(value_knowledge(value[name]) for name in names)
                knowledge = _BindingKnowledge()
                for child in child_knowledge:
                    knowledge = knowledge.join(child)
                source_keys = tuple(_dynamic_string_binding(str(name)) for name in names)
                source_values = tuple(
                    child.source_value or _DYNAMIC_UNKNOWN for child in child_knowledge
                )
                return replace(
                    knowledge,
                    source_value=_dynamic_mapping_binding(source_keys, source_values),
                )
            return _BindingKnowledge(possible_unknown=True)

        return (
            {name: value_knowledge(value) for name, value in bound.arguments.items()},
            [],
        )

    def _record_source_call_context(
        self,
        node: ast.Call,
        *,
        frame: _EvaluatedCallFrame,
    ) -> None:
        """Queue source callees with one frozen, ordered call frame."""
        targets = set(frame.callable_targets)
        evaluated_arguments = dict(frame.argument_knowledge)
        contextual_targets: set[tuple[str, str, int, int]] = set()
        local_contexts: list[_SourceCallContext] = []
        for reference in sorted(targets):
            if reference[0] not in self.module_names:
                continue
            function = self.source_functions.get(reference)
            if function is None:
                continue
            receiver_knowledge, _receiver_parameter, descriptor_known = (
                self._method_receiver_binding(
                    node,
                    function,
                    reference,
                    receiver_knowledge=frame.receiver_knowledge,
                )
            )
            if "." in reference[1] and not descriptor_known:
                continue
            bindings, unbound = self._call_argument_bindings(
                node,
                function,
                reference,
                bound_receiver=receiver_knowledge,
                evaluated_argument_knowledge=evaluated_arguments,
            )
            if unbound:
                continue
            context = tuple(sorted(bindings.items()))
            if reference[0] == self.module:
                local_contexts.append((reference, context))
            else:
                self.called_with_bindings.add((reference, context))
            contextual_targets.add(reference)

        if local_contexts:
            self.pending_local_call_contexts.append(
                tuple(sorted(local_contexts, key=lambda item: item[0]))
            )

        # Keep existing conservative traversal for external functions, unsupported
        # descriptors, and calls whose source signature cannot be bound.
        self._record_targets(targets - contextual_targets)

    def _drain_local_call_contexts(self) -> None:
        """Join possible callees from the same evaluated call, never last-wins."""
        while self.pending_local_call_contexts:
            contexts = self.pending_local_call_contexts.pop()
            base = self._snapshot_bindings()
            branch_states: list[tuple[Any, ...]] = []
            for reference, context in contexts:
                self._restore_bindings(base)
                self.visit_callable(reference, parameter_bindings=dict(context))
                branch_states.append(self._snapshot_bindings())
            if len(branch_states) == 1:
                self._restore_bindings(branch_states[0])
            elif branch_states:
                self._merge_binding_states(branch_states)

    def _apply_global_effect(
        self, name: str, effect: _GlobalEffect, *, shadowed_names: set[str]
    ) -> None:
        knowledge, type_kind = effect
        if name not in shadowed_names:
            self._clear_name_bindings({name})
            self._write_binding_knowledge(name, knowledge)
            if type_kind is None:
                self.type_checking_bindings.pop(name, None)
            else:
                self.type_checking_bindings[name] = type_kind
        if self.global_effect_frames:
            # Calls execute in source order; later definite writes replace earlier
            # effects. Conditional writes are joined by the branch merge.
            self.global_effect_frames[-1][name] = (knowledge, type_kind)

    def _record_source_callback_argument(
        self,
        node: ast.Call,
        *,
        frame: _EvaluatedCallFrame,
    ) -> None:
        """Transfer callbacks from their frozen left-to-right call values."""
        argument_knowledge = dict(frame.argument_knowledge)

        def captured(value: ast.AST) -> _BindingKnowledge:
            knowledge = argument_knowledge.get(id(value))
            if knowledge is not None:
                return knowledge
            return self._knowledge_for_expression(value)

        references = {
            reference for reference in frame.callable_targets if reference[0] in self.module_names
        }
        if not references:
            return

        callback_values: list[_BindingKnowledge] = []
        for reference in references:
            module, symbol, _line, _column = reference
            function = self.source_functions.get(reference)
            receiver_knowledge: _BindingKnowledge | None = None
            receiver_parameter: str | None = None
            descriptor_known = False
            if function is not None:
                receiver_knowledge, receiver_parameter, descriptor_known = (
                    self._method_receiver_binding(
                        node,
                        function,
                        reference,
                        receiver_knowledge=frame.receiver_knowledge,
                    )
                )
            if function is None or ("." in symbol and not descriptor_known):
                callback_values.extend(
                    captured(argument.value if isinstance(argument, ast.Starred) else argument)
                    for argument in node.args
                )
                callback_values.extend(captured(keyword.value) for keyword in node.keywords)
                if function is not None:
                    defaults = (
                        self.function_default_bindings.get(reference, {})
                        if module == self.module
                        else self.external_function_default_bindings.get(reference, {})
                    )
                    callback_values.extend(
                        knowledge
                        for parameter, knowledge in defaults.items()
                        if self._parameter_call_usage(function, parameter) is not None
                    )
                continue

            bindings, unbound = self._call_argument_bindings(
                node,
                function,
                reference,
                bound_receiver=receiver_knowledge,
                evaluated_argument_knowledge=argument_knowledge,
            )
            callback_values.extend(unbound)
            for parameter, knowledge in bindings.items():
                if parameter == receiver_parameter:
                    continue
                usage = self._parameter_call_usage(function, parameter)
                if usage is None:
                    continue
                invocation = self._callable_targets_for_knowledge(knowledge)
                source_callbacks = {
                    target
                    for target in invocation.known_possible_targets
                    if target.kind == "callable" and target.module in self.module_names
                }
                if not source_callbacks and not knowledge.source_value_origins:
                    continue
                if (
                    usage == "direct"
                    and source_callbacks
                    and not knowledge.possible_unknown
                    and invocation.definitely_resolved
                ):
                    # The enclosing call context already carries these exact
                    # bindings into this source function. Its Call.func is then
                    # traversed as an ordinary source call with its own context.
                    continue
                # Possible targets and unmodeled subscript/member callback forms
                # remain explicit notest observations, even when known targets exist.
                callback_values.append(knowledge)

        callback_knowledge = _BindingKnowledge()
        callback_classes: set[tuple[str, str]] = set()
        callback_targets: set[tuple[str, str, int, int]] = set()
        found_callback_argument = False
        for value_knowledge in callback_values:
            invocation = self._callable_targets_for_knowledge(value_knowledge)
            source_callbacks = {
                target
                for target in invocation.known_possible_targets
                if target.kind == "callable" and target.module in self.module_names
            }
            if not source_callbacks and not value_knowledge.source_value_origins:
                continue
            found_callback_argument = True
            callback_knowledge = callback_knowledge.join(value_knowledge).join(invocation)
            callback_targets.update(
                (target.module, target.symbol or "", target.line, target.column)
                for target in source_callbacks
            )
            callback_targets.update(
                (target.module, target.symbol or "", target.line, target.column)
                for target in value_knowledge.source_value_origins
                if target.kind == "callable" and target.module in self.module_names
            )
            callback_classes.update(
                (target.module, target.symbol or "")
                for target in value_knowledge.known_possible_targets
                if target.kind == "class" and target.symbol is not None
            )
            callback_classes.update(
                instance_class
                for target in value_knowledge.known_possible_targets
                if (instance_class := _instance_class_for_target(target)) is not None
            )
        if not found_callback_argument:
            return
        reasons = {"source_callback_argument_not_summarized"}
        self._record_dispatch_observation(
            node,
            receiver_form="CallbackArgument",
            class_targets=callback_classes,
            callable_targets=callback_targets,
            reasons=reasons,
            binding_knowledge=self._observation_knowledge(
                callback_knowledge,
                callback_classes,
                callback_targets,
                reasons,
            ),
            record_unresolved_value=True,
        )

    def visit_Call(self, node: ast.Call) -> None:
        # Python evaluates the callable expression first. Visiting it also applies
        # any nested source-call effects before the outer target is captured.
        self.visit(node.func)
        callable_targets = frozenset(self._callable_target(node.func))
        class_targets = frozenset(self._class_targets(node.func))
        callable_knowledge = self._knowledge_for_expression(node.func)
        receiver_knowledge = (
            self._knowledge_for_expression(node.func.value)
            if isinstance(node.func, ast.Attribute)
            else None
        )
        builtin_symbol = self._known_builtin_symbol(node.func)
        self._record_dispatch_resolution(node.func, call=node)

        captured_arguments: dict[int, _BindingKnowledge] = {}
        actuals: list[tuple[int, int, ast.AST, str]] = []
        actuals.extend(
            (argument.lineno, argument.col_offset, argument, "positional") for argument in node.args
        )
        actuals.extend(
            (keyword.lineno, keyword.col_offset, keyword.value, "keyword")
            for keyword in node.keywords
        )
        for _line, _column, expression, kind in sorted(
            actuals, key=lambda item: (item[0], item[1])
        ):
            if kind == "positional" and isinstance(expression, ast.Starred):
                value_knowledge = self._visit_call_argument_expression(
                    expression.value,
                    captured_arguments,
                    expand_literal=True,
                )
                exact_literal = isinstance(expression.value, (ast.Tuple, ast.List)) and all(
                    not isinstance(item, ast.Starred) for item in expression.value.elts
                )
                captured_arguments[id(expression)] = (
                    value_knowledge
                    if exact_literal
                    else value_knowledge.join(_BindingKnowledge(possible_unknown=True))
                )
            elif kind == "keyword" and isinstance(expression, ast.Dict):
                self._visit_call_argument_expression(
                    expression, captured_arguments, expand_literal=True
                )
            else:
                value_knowledge = self._visit_call_argument_expression(
                    expression, captured_arguments
                )
                if kind == "keyword":
                    keyword = next(item for item in node.keywords if item.value is expression)
                    if keyword.arg is None:
                        captured_arguments[id(expression)] = value_knowledge.join(
                            _BindingKnowledge(possible_unknown=True)
                        )

        frame = _EvaluatedCallFrame(
            callable_targets=callable_targets,
            class_targets=class_targets,
            callable_knowledge=callable_knowledge,
            receiver_knowledge=receiver_knowledge,
            argument_knowledge=tuple(sorted(captured_arguments.items())),
            builtin_symbol=builtin_symbol,
        )
        site_key = (node.lineno, node.col_offset)
        if site_key in self.source_value_observation_sites:
            observed_slots: dict[str, _DynamicImportBinding] = {}
            for index, argument in enumerate(node.args):
                knowledge = captured_arguments.get(id(argument))
                observed_slots[f"positional:{index}"] = (
                    knowledge.source_value
                    if knowledge and knowledge.source_value is not None
                    else _DYNAMIC_UNKNOWN
                )
            for keyword in node.keywords:
                knowledge = captured_arguments.get(id(keyword.value))
                slot = f"keyword:{keyword.arg}" if keyword.arg is not None else "keyword:**"
                observed_slots[slot] = (
                    knowledge.source_value
                    if knowledge and knowledge.source_value is not None
                    else _DYNAMIC_UNKNOWN
                )

            targets = set(callable_knowledge.known_possible_targets)
            targets.update(_BindingTarget("callable", *reference) for reference in callable_targets)
            targets.update(
                _BindingTarget("class", module, symbol) for module, symbol in class_targets
            )
            if builtin_symbol is not None:
                targets.add(_BindingTarget("builtin", "builtins", builtin_symbol))
            target_rows = [
                {
                    "kind": target.kind,
                    "module": target.module,
                    "symbol": target.symbol,
                    "line": target.line,
                    "column": target.column,
                }
                for target in sorted(targets, key=lambda item: item.sort_key())
            ]
            if self.source_value_target_names is not None:
                value_target_names = {
                    f"{target['module']}.{target['symbol']}"
                    for target in target_rows
                    if target["kind"] in {"import", "builtin"}
                    and isinstance(target["module"], str)
                    and isinstance(target["symbol"], str)
                }
                if not (value_target_names & self.source_value_target_names):
                    observed_slots.clear()
            target_unknown = callable_knowledge.possible_unknown or not target_rows
            previous = self.source_value_call_observations.get(
                site_key, {"slots": {}, "call_targets": [], "call_target_unknown": False}
            )
            joined_slots = dict(previous.get("slots", {}))
            for slot, value in observed_slots.items():
                prior_value = joined_slots.get(slot)
                joined_slots[slot] = (
                    _join_dynamic_bindings((prior_value, value)) if prior_value else value
                )
            joined_targets = {
                (
                    str(target["kind"]),
                    str(target["module"]),
                    target.get("symbol") is None,
                    str(target.get("symbol") or ""),
                    int(target["line"]),
                    int(target["column"]),
                ): target
                for target in previous.get("call_targets", [])
            }
            for target in target_rows:
                key = (
                    str(target["kind"]),
                    str(target["module"]),
                    target.get("symbol") is None,
                    str(target.get("symbol") or ""),
                    int(target["line"]),
                    int(target["column"]),
                )
                joined_targets[key] = target
            self.source_value_call_observations[site_key] = {
                "slots": joined_slots,
                "call_targets": [joined_targets[key] for key in sorted(joined_targets)],
                "call_target_unknown": bool(
                    previous.get("call_target_unknown", False) or target_unknown
                ),
            }
        first_argument_knowledge = captured_arguments.get(id(node.args[0])) if node.args else None
        self._record_builtin_call_overrides(
            node,
            builtin_symbol=frame.builtin_symbol,
            first_argument_knowledge=first_argument_knowledge,
        )
        self._record_source_call_context(node, frame=frame)
        self._record_source_callback_argument(node, frame=frame)
        self._record_class_constructors(
            node.func,
            node,
            class_targets=set(frame.class_targets),
            knowledge=frame.callable_knowledge,
        )
        self._record_builtin_owner_mutation(node, frame=frame)
        self._drain_local_call_contexts()

    def visit_callable(
        self,
        reference: tuple[str, str, int, int],
        *,
        parameter_bindings: Mapping[str, _BindingKnowledge] | None = None,
    ) -> None:
        context_key = tuple(
            (name, knowledge) for name, knowledge in sorted((parameter_bindings or {}).items())
        )
        visit_key = (reference, (self._binding_state_key(), context_key))
        if visit_key in self.visited_functions:
            return
        function = self.functions.get(reference)
        if function is None:
            return
        name = reference[1]
        self.visited_functions.add(visit_key)
        saved_bindings = self._snapshot_bindings()
        saved_scope_kind = self.scope_kind
        saved_scope_prefix = self.scope_prefix
        saved_class_context = self.class_context
        local_names, global_writes, nonlocal_writes = _function_scope_bindings(function)
        self.function_local_names_stack.append(local_names)
        self.global_effect_frames.append({})
        self._bind_unknown(local_names)
        self.scope_kind = "function"
        # Nested functions are indexed under their complete lexical parent. Keep
        # that parent while visiting the body so direct local calls resolve.
        self.scope_prefix = name
        enclosing_class = self._enclosing_class(name)
        self.class_context = enclosing_class
        positional = [*function.args.posonlyargs, *function.args.args]
        is_direct_class_method = bool(
            enclosing_class and name.rpartition(".")[0] == enclosing_class
        )
        if is_direct_class_method and positional:
            decorator_names, unknown_descriptor = self._method_descriptor_symbols(function)
            receiver = positional[0].arg
            self._clear_name_bindings({receiver})
            if unknown_descriptor or (
                "staticmethod" in decorator_names and "classmethod" in decorator_names
            ):
                self._write_binding_knowledge(
                    receiver,
                    _BindingKnowledge(
                        possible_unknown=True,
                        source_value_origins=frozenset(
                            {
                                _BindingTarget(
                                    "instance",
                                    self.module,
                                    f"{self.module}::{enclosing_class}",
                                    function.lineno,
                                    function.col_offset,
                                )
                            }
                        ),
                    ),
                )
            elif "staticmethod" not in decorator_names:
                if "classmethod" in decorator_names:
                    self.class_aliases[receiver] = {(self.module, enclosing_class)}
                else:
                    self.instance_aliases[receiver] = {(self.module, enclosing_class, -1, -1)}
        for parameter, knowledge in (parameter_bindings or {}).items():
            self._write_binding_knowledge(parameter, knowledge)
        for statement in function.body:
            self.visit(statement)
        function_bindings = self._snapshot_bindings()
        function_global_effects = dict(function_bindings[5][-1])
        self._restore_bindings(saved_bindings)
        self.function_local_names_stack.pop()
        self.owner_member_bindings = {
            owner: members.copy() for owner, members in function_bindings[3].items()
        }
        self.owner_member_wildcard_overrides = {
            owner: members.copy() for owner, members in function_bindings[4].items()
        }
        self.scope_kind = saved_scope_kind
        self.scope_prefix = saved_scope_prefix
        self.class_context = saved_class_context
        (
            function_knowledge,
            function_type_checking,
            _function_class_exports,
            _function_owner_members,
            _function_wildcard_overrides,
            _function_global_effect_frames,
        ) = function_bindings
        for global_name in global_writes:
            # An empty binding lattice is an ordinary non-source value. Flow
            # uncertainty is represented by possible_unknown in that lattice.
            function_global_effects[global_name] = (
                function_knowledge.get(global_name, _BindingKnowledge()),
                function_type_checking.get(global_name),
            )
        for nonlocal_name in nonlocal_writes:
            knowledge = function_knowledge.get(
                nonlocal_name, _BindingKnowledge(possible_unknown=True)
            )
            self._clear_name_bindings({nonlocal_name})
            self._write_binding_knowledge(nonlocal_name, knowledge)
            type_kind = function_type_checking.get(nonlocal_name)
            if type_kind is None:
                self.type_checking_bindings.pop(nonlocal_name, None)
            else:
                self.type_checking_bindings[nonlocal_name] = type_kind
        caller_locals = (
            self.function_local_names_stack[-1] if self.function_local_names_stack else set()
        )
        for global_name, effect in function_global_effects.items():
            self._apply_global_effect(global_name, effect, shadowed_names=caller_locals)


def _collect_runtime_import_edges(
    trees: Mapping[str, ast.Module],
    module_paths: Mapping[str, Path],
    *,
    source_value_observation_sites: Mapping[str, set[tuple[int, int]]] | None = None,
    source_value_target_names: frozenset[str] | None = None,
    source_value_observations: list[dict[str, Any]] | None = None,
    include_unentered_source_functions: bool = False,
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    """Build module-eager edges using source-identified, flow-joined call targets."""
    module_names = set(module_paths)
    functions_by_module: dict[
        str, dict[tuple[str, str, int, int], ast.FunctionDef | ast.AsyncFunctionDef]
    ] = {}
    classes_by_module: dict[str, set[str]] = {}
    callable_index: set[tuple[str, str]] = set()
    for module, tree in trees.items():
        functions, classes = _callable_definitions(tree, module)
        functions_by_module[module] = functions
        classes_by_module[module] = classes
        callable_index.update((reference[0], reference[1]) for reference in functions)
    source_functions = {
        reference: function
        for module_functions in functions_by_module.values()
        for reference, function in module_functions.items()
    }
    class_index = {
        (module, class_name)
        for module, class_names in classes_by_module.items()
        for class_name in class_names
    }
    source_class_bases: dict[tuple[str, str], set[tuple[str, str]]] = {}
    source_class_base_unknown: set[tuple[str, str]] = set()
    source_class_metaclasses: dict[tuple[str, str], _BindingKnowledge] = {}

    def run_collectors(
        external_module_exports: Mapping[str, Mapping[str, _BindingKnowledge]] | None = None,
        external_class_exports: Mapping[str, Mapping[str, Mapping[str, _BindingKnowledge]]]
        | None = None,
        external_owner_member_exports: Mapping[
            str, Mapping[_BindingTarget, Mapping[str, _BindingKnowledge]]
        ]
        | None = None,
        external_function_default_bindings: Mapping[
            tuple[str, str, int, int], Mapping[str, _BindingKnowledge]
        ]
        | None = None,
    ) -> dict[str, _RuntimeImportCollector]:
        collectors = {
            module: _RuntimeImportCollector(
                module,
                module_names,
                callable_index,
                functions_by_module[module],
                source_functions,
                classes_by_module[module],
                class_index,
                source_class_bases,
                source_class_base_unknown,
                source_class_metaclasses,
                is_package=module_paths[module].name == "__init__.py",
                source_path=_import_source_path(module_paths[module]),
                source_value_observation_sites=(source_value_observation_sites or {}).get(
                    module, set()
                ),
                source_value_target_names=source_value_target_names,
            )
            for module in trees
        }
        for collector in collectors.values():
            collector.external_module_exports = external_module_exports or {}
            collector.external_class_exports = external_class_exports or {}
            collector.external_owner_member_exports = external_owner_member_exports or {}
            collector.external_function_default_bindings = external_function_default_bindings or {}
        for module, tree in trees.items():
            collectors[module].set_future_annotations(tree)
            collectors[module].visit(tree)
            if include_unentered_source_functions:
                entered_references = {
                    reference for reference, _state in collectors[module].visited_functions
                }
                for reference, function in sorted(collectors[module].functions.items()):
                    if reference in entered_references:
                        continue
                    parameters = (
                        *function.args.posonlyargs,
                        *function.args.args,
                        *function.args.kwonlyargs,
                        *((function.args.vararg,) if function.args.vararg else ()),
                        *((function.args.kwarg,) if function.args.kwarg else ()),
                    )
                    collectors[module].visit_callable(
                        reference,
                        parameter_bindings={
                            parameter.arg: _BindingKnowledge(
                                possible_unknown=True,
                                source_value=_DYNAMIC_UNKNOWN,
                            )
                            for parameter in parameters
                        },
                    )
        return collectors

    def module_binding_exports(
        selected: Mapping[str, _RuntimeImportCollector],
    ) -> dict[str, dict[str, _BindingKnowledge]]:
        return {
            module: collector._binding_knowledge_snapshot()
            for module, collector in selected.items()
        }

    def class_member_exports(
        selected: Mapping[str, _RuntimeImportCollector],
    ) -> dict[str, dict[str, dict[str, _BindingKnowledge]]]:
        return {
            module: {
                class_name: members.copy()
                for class_name, members in collector.class_member_bindings.items()
            }
            for module, collector in selected.items()
        }

    def owner_member_exports(
        selected: Mapping[str, _RuntimeImportCollector],
    ) -> dict[str, dict[_BindingTarget, dict[str, _BindingKnowledge]]]:
        return {
            module: {
                owner: members.copy() for owner, members in collector.owner_member_bindings.items()
            }
            for module, collector in selected.items()
        }

    def function_default_exports(
        selected: Mapping[str, _RuntimeImportCollector],
    ) -> dict[tuple[str, str, int, int], dict[str, _BindingKnowledge]]:
        return {
            reference: defaults.copy()
            for collector in selected.values()
            for reference, defaults in collector.function_default_bindings.items()
        }

    first_pass = run_collectors()
    first_module_exports = module_binding_exports(first_pass)
    first_class_exports = class_member_exports(first_pass)
    first_owner_member_exports = owner_member_exports(first_pass)
    first_function_default_exports = function_default_exports(first_pass)
    # Recollect with first-pass namespaces and owner/member snapshots. External
    # mutable-owner snapshots remain uncertain at reads because module execution
    # and mutation order is not established by this whole-tree export pass.
    collectors = run_collectors(
        first_module_exports,
        first_class_exports,
        first_owner_member_exports,
        first_function_default_exports,
    )
    module_exports = module_binding_exports(collectors)
    class_exports = class_member_exports(collectors)

    def resolve_reference(
        reference: tuple[str, str, int, int],
        seen: set[tuple[str, str, int, int]] | None = None,
    ) -> set[tuple[str, str, int, int]]:
        if reference[2] >= 0:
            return {reference}
        seen = set() if seen is None else seen
        if reference in seen:
            return set()
        seen.add(reference)
        module, symbol, _line, _column = reference
        class_name, separator, member = symbol.rpartition(".")
        knowledge = (
            class_exports.get(module, {}).get(class_name, {}).get(member) if separator else None
        )
        if knowledge is None:
            knowledge = module_exports.get(module, {}).get(symbol)
        if knowledge is None:
            return {reference} if (module, symbol) in callable_index else set()
        return resolve_binding_knowledge(knowledge, seen)

    def resolve_class_members(
        module: str,
        class_name: str,
        members: Sequence[str],
        seen: set[tuple[str, str, int, int]],
    ) -> set[tuple[str, str, int, int]]:
        resolved: set[tuple[str, str, int, int]] = set()
        for member in members:
            resolved.update(
                resolve_reference((module, f"{class_name}.{member}", -1, -1), seen.copy())
            )
        return resolved

    def resolve_binding_knowledge(
        knowledge: _BindingKnowledge,
        seen: set[tuple[str, str, int, int]],
    ) -> set[tuple[str, str, int, int]]:
        resolved: set[tuple[str, str, int, int]] = set()
        for target in knowledge.known_possible_targets:
            if target.kind in {"callable", "source_call"} and target.symbol is not None:
                resolved.update(
                    resolve_reference(
                        (target.module, target.symbol, target.line, target.column),
                        seen.copy(),
                    )
                )
            elif target.kind == "import" and target.symbol is not None:
                resolved.update(
                    resolve_reference((target.module, target.symbol, -1, -1), seen.copy())
                )
            elif target.kind == "class" and target.symbol is not None:
                resolved.update(
                    resolve_class_members(
                        target.module,
                        target.symbol,
                        ("__new__", "__init__"),
                        seen.copy(),
                    )
                )
            elif target.kind == "instance" and target.symbol is not None:
                instance_class = _instance_class_for_target(target)
                if instance_class is not None:
                    resolved.update(
                        resolve_class_members(
                            instance_class[0],
                            instance_class[1],
                            ("__call__",),
                            seen.copy(),
                        )
                    )
        return resolved

    visited: set[tuple[str, str, int, int]] = set()
    visited_contexts: set[
        tuple[tuple[str, str, int, int], tuple[tuple[str, _BindingKnowledge], ...]]
    ] = set()
    while True:
        finalized_constructor_calls = False
        for collector in collectors.values():
            finalized_constructor_calls = (
                collector.resolve_pending_class_constructor_calls() or finalized_constructor_calls
            )
        pending_contexts = [
            context
            for collector in collectors.values()
            for context in collector.called_with_bindings
            if context not in visited_contexts
        ]
        if pending_contexts:
            reference, context = pending_contexts.pop()
            visited_contexts.add((reference, context))
            target_collector = collectors.get(reference[0])
            if target_collector is not None:
                target_collector.visit_callable(reference, parameter_bindings=dict(context))
            continue
        pending = [
            target
            for collector in collectors.values()
            for target in collector.called
            if target not in visited
        ]
        if not pending:
            if finalized_constructor_calls:
                continue
            break
        target = pending.pop()
        for resolved_target in resolve_reference(target):
            if resolved_target in visited:
                continue
            visited.add(resolved_target)
            collector = collectors.get(resolved_target[0])
            if collector is None:
                continue
            collector.visit_callable(resolved_target)
    edges = {
        module: set(collectors[module].edges) if module in collectors else set()
        for module in module_names
    }
    if source_value_observations is not None:
        source_value_observations.clear()
        for module, collector in sorted(collectors.items()):
            for (line, column), observation in sorted(
                collector.source_value_call_observations.items()
            ):
                source_value_observations.append(
                    {
                        "module": module,
                        "source_path": collector.source_path,
                        "line": line,
                        "column": column,
                        "slots": dict(sorted(observation["slots"].items())),
                        "call_targets": list(observation["call_targets"]),
                        "call_target_unknown": bool(observation["call_target_unknown"]),
                    }
                )
    dispatch_observations = sorted(
        (
            dict(row)
            for collector in collectors.values()
            for row in collector.dispatch_observations.values()
        ),
        key=lambda row: (
            str(row["source_path"]),
            int(row["line"]),
            int(row["column"]),
            str(row["reason"]),
        ),
    )
    return edges, dispatch_observations


def collect_source_value_call_observations(
    trees: Mapping[str, ast.Module],
    module_paths: Mapping[str, Path],
    *,
    value_target_names: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join every declared AST call to the existing source/value context owner.

    The expected set is derived from the supplied complete AST trees. The existing
    runtime collector and its formal-call worklist produce targets for every call;
    `value_target_names` can restrict retained argument payloads to owner-resolved
    consumers. A call with no observation is returned as a refusal, never absence.
    """
    call_sites = {
        module: {
            (node.lineno, node.col_offset) for node in ast.walk(tree) if isinstance(node, ast.Call)
        }
        for module, tree in trees.items()
    }
    observations: list[dict[str, Any]] = []
    _collect_runtime_import_edges(
        trees,
        module_paths,
        source_value_observation_sites=call_sites,
        source_value_target_names=(
            frozenset(value_target_names) if value_target_names is not None else None
        ),
        source_value_observations=observations,
        include_unentered_source_functions=True,
    )
    observed_sites = {
        (str(row["module"]), int(row["line"]), int(row["column"])) for row in observations
    }
    missing = [
        {
            "module": module,
            "line": line,
            "column": column,
            "reason": "declared AST call has no joined R8 observation",
        }
        for module, positions in sorted(call_sites.items())
        for line, column in sorted(positions)
        if (module, line, column) not in observed_sites
    ]
    return observations, missing


def collect_source_value_sink_observations(
    trees: Mapping[str, ast.Module],
    module_paths: Mapping[str, Path],
    sink_sites: Mapping[str, set[tuple[int, int]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compatibility wrapper for callers that still declare recognized sink spans.

    New completeness consumers should use `collect_source_value_call_observations`
    so unsupported call sources cannot disappear before the consumer gate.
    """
    observations: list[dict[str, Any]] = []
    _collect_runtime_import_edges(
        trees,
        module_paths,
        source_value_observation_sites=sink_sites,
        source_value_observations=observations,
        include_unentered_source_functions=True,
    )
    observed_sites = {
        (str(row["module"]), int(row["line"]), int(row["column"])) for row in observations
    }
    missing = [
        {
            "module": module,
            "line": line,
            "column": column,
            "reason": "R8 sink site has no source-value observation",
        }
        for module, positions in sorted(sink_sites.items())
        for line, column in sorted(positions)
        if (module, line, column) not in observed_sites
    ]
    return observations, missing


def collect_import_graph(
    *,
    runtime_only: bool = False,
    source_snapshot: _ImportSourceSnapshot | None = None,
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    """Collect the full AST baseline graph or its module-initialization import graph."""
    snapshot = source_snapshot or _collect_import_source_snapshot()
    input_errors = _import_source_errors(snapshot)
    if input_errors and not allow_incomplete:
        first = input_errors[0]
        raise ImportGraphInputError(
            f"cannot build a complete import graph: {first.get('path')} [{first.get('outcome')}]",
            source_snapshot=snapshot,
        )
    module_paths = snapshot.module_paths
    trees = snapshot.trees
    module_names = set(module_paths)
    dispatch_observations: list[dict[str, Any]] = []
    if runtime_only:
        edges, dispatch_observations = _collect_runtime_import_edges(trees, module_paths)
    else:
        edges = {module: set() for module in module_names}
        for module, tree in trees.items():
            for node in ast.walk(tree):
                candidates: list[str] = []
                if isinstance(node, ast.Import):
                    candidates.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = _resolve_relative_import(module, node.module, node.level)
                    candidates.append(base)
                    candidates.extend(
                        f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
                    )
                for candidate in candidates:
                    resolved = _nearest_known_module(candidate, module_names)
                    if resolved and resolved != module:
                        edges[module].add(resolved)
    edge_rows = [
        {"source": source, "target": target}
        for source, targets in sorted(edges.items())
        for target in sorted(targets)
    ]
    cycles = _strongly_connected_components(edges)
    cycle_rows = [
        {"id": f"cycle-{_sha('|'.join(cycle))}", "modules": cycle}
        for cycle in sorted(cycles, key=lambda item: (len(item), item))
    ]
    graph: dict[str, Any] = {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "collector": "tools.quality.validation.decomposition_preflight.collect_import_graph",
        "collector_mode": (
            "internal_ast_runtime_import_graph" if runtime_only else "internal_ast_import_graph"
        ),
        "pydeps_available": shutil.which("pydeps") is not None,
        "import_linter_available": importlib.util.find_spec("importlinter") is not None
        or importlib.util.find_spec("import_linter") is not None,
        "notes": (
            "Module-eager graph includes module/class bodies and source-resolved calls within "
            "the AST binding collector's supported forms; targetless reflective/callback "
            "dispatch remains separately not_established. TYPE_CHECKING and deferred function "
            "bodies are omitted."
            if runtime_only
            else (
                "Phase 3A uses a deterministic AST import graph collector because pydeps/import-linter "
                "are not required dev dependencies in this workspace."
            )
        ),
        "module_count": len(module_names),
        "edge_count": len(edge_rows),
        "cycles": cycle_rows,
        "edges": edge_rows,
    }
    if runtime_only:
        graph["dispatch_resolution"] = {
            "scope": "source-resolved module-initialization calls supported by the AST binding collector",
            "status": "not_established"
            if any(row["status"] == "not_established" for row in dispatch_observations)
            else "resolved_within_scope",
            "resolved_count": sum(row["status"] == "resolved" for row in dispatch_observations),
            "unresolved_count": sum(
                row["status"] == "not_established" for row in dispatch_observations
            ),
            "observations": dispatch_observations,
            "unresolved": [
                row for row in dispatch_observations if row["status"] == "not_established"
            ],
            "unmodeled_dispatch_forms": [
                {
                    "form": "reflective_or_callback_valued_receiver",
                    "status": "not_established",
                    "reason": "no source-resolved target is available for enumeration",
                }
            ],
        }
    return graph


def _nearest_known_module(candidate: str, module_names: set[str]) -> str | None:
    if not candidate.startswith(("polisyos.scientist", "polisyos.foundry")):
        return None
    parts = candidate.split(".")
    while parts:
        rendered = ".".join(parts)
        if rendered in module_names:
            return rendered
        parts.pop()
    return None


def _strongly_connected_components(edges: Mapping[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in edges.get(node, set()):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] != indices[node]:
            return
        component: list[str] = []
        while True:
            target = stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target == node:
                break
        if len(component) > 1:
            components.append(sorted(component))

    for node in sorted(edges):
        if node not in indices:
            visit(node)
    return components


def render_lazy_toml(import_graph: Mapping[str, Any]) -> str:
    lines = [
        "[lazy_imports]",
        "version = 1",
        'status = "fail_closed"',
        'owner = "team-architecture"',
        'phase = "3A"',
        'notes = "Registered deferred SCCs are retained; new full-graph SCCs and source-resolved module-eager cycles fail the gate, as does source-known not-established module-time dispatch."',
        "",
    ]
    for cycle in import_graph.get("cycles", []):
        modules = [str(module) for module in cycle["modules"]]
        lines.extend(
            [
                "[[allowed_cycle]]",
                f"id = {_toml_quote(str(cycle['id']))}",
                f"modules = {_toml_array(modules)}",
                'reason = "Pre-existing lazy import cycle captured before scientist/foundry decomposition."',
                "",
            ]
        )
    return "\n".join(lines)


def measure_import_time(runs: int = 10) -> dict[str, Any]:
    packages = ("polisyos.scientist", "polisyos.foundry")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{SRC_ROOT}{os.pathsep}{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    results: dict[str, Any] = {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "runs": runs,
    }
    for package in packages:
        samples_ms: list[float] = []
        cumulative_us: list[int] = []
        for _ in range(runs):
            started = time.perf_counter()
            completed = subprocess.run(
                [sys.executable, "-X", "importtime", "-c", f"import {package}"],
                cwd=REPO_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            samples_ms.append(round(elapsed_ms, 3))
            cumulative = _parse_importtime_cumulative_us(completed.stderr, package)
            if cumulative is not None:
                cumulative_us.append(cumulative)
        sorted_samples = sorted(samples_ms)
        p95_index = min(len(sorted_samples) - 1, round((len(sorted_samples) - 1) * 0.95))
        results[package] = {
            "samples_wall_ms": samples_ms,
            "median_wall_ms": round(median(samples_ms), 3),
            "p95_wall_ms": sorted_samples[p95_index],
            "median_importtime_cumulative_us": int(median(cumulative_us))
            if cumulative_us
            else None,
        }
    return results


def _parse_importtime_cumulative_us(stderr: str, package: str) -> int | None:
    for line in reversed(stderr.splitlines()):
        if not line.rstrip().endswith(package):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 3 and parts[1].isdigit():
            return int(parts[1])
    return None


def create_checkpoint_fixtures() -> list[dict[str, Any]]:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.foundry.agent_sim.experiment import (
        ExperimentConfig,
        ExperimentResult,
        ExperimentTracker,
    )
    from polisyos.scientist.orchestration.engine.checkpoint import (
        create_checkpoint,
        load_checkpoint,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    manifests: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="phase3a-checkpoint-compat-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        foundry_config = ExperimentConfig(
            name="phase3a_agent_sim_canonical",
            description="Phase 3A canonical pickle compatibility fixture.",
            tags=["phase3a", "checkpoint_compat"],
            seed=143,
            created_at="2026-05-03T00:00:00+00:00",
        )
        foundry_result = ExperimentResult(
            config=foundry_config,
            metrics={"reward": 1.0, "loss": 0.125},
            final_state={"step": 2, "status": "ok"},
            model_path="model.eqx",
            duration_seconds=0.5,
        )
        tracker = ExperimentTracker(temp_dir / "foundry")
        with tracker.run(foundry_config) as run:
            run.log_metric("reward", 1.0)
            run.log_metric("loss", 0.125)
            run.log_artifact("agent_sim_experiment_result", foundry_result)
            produced_foundry_path = run.run_dir / "agent_sim_experiment_result.pkl"
            foundry_data = produced_foundry_path.read_bytes()

        scientist_store = FileSystemCAS(temp_dir / "scientist_cas")
        scientist_state = ExperimentState(
            run_id="phase3a_scientist_checkpoint",
            params={"status": "ok"},
        )
        created = create_checkpoint(
            scientist_store,
            run_id=scientist_state.run_id,
            state=scientist_state.model_dump(mode="python", by_alias=True, exclude_none=False),
            sequence_number=1,
            completed_node_alias="phase3a_node",
            completed_node_id="scientist.node_noop@1.0.0",
            completed_nodes=["phase3a_node"],
            workflow_id="phase3a_workflow",
            workflow_fingerprint="a" * 64,
            fsm_phase="completed",
            cache_entry_refs=[],
        )
        scientist_checkpoint = load_checkpoint(scientist_store, created.checkpoint_ref)
        scientist_data = pickle.dumps(scientist_checkpoint, protocol=4)

    fixtures: list[tuple[Path, bytes, dict[str, Any]]] = [
        (
            CHECKPOINT_FIXTURE_ROOT / "foundry" / "agent_sim_experiment_result.pkl",
            foundry_data,
            {
                "package": "foundry",
                "scenario": "agent_sim_experiment_result",
                "producer": "polisyos.foundry.agent_sim.experiment.ExperimentRun.log_artifact",
                "expected_type": "polisyos.foundry.agent_sim.experiment.ExperimentResult",
                "expected_fields": {
                    "config.name": "phase3a_agent_sim_canonical",
                    "metrics.reward": 1.0,
                },
            },
        ),
        (
            CHECKPOINT_FIXTURE_ROOT / "scientist" / "engine_checkpoint_artifact.pkl",
            scientist_data,
            {
                "package": "scientist",
                "scenario": "engine_checkpoint_artifact",
                "producer": "polisyos.scientist.orchestration.engine.checkpoint.create_checkpoint/load_checkpoint",
                "expected_type": "polisyos.scientist.orchestration.engine.checkpoint.CheckpointArtifact",
                "expected_fields": {
                    "metadata.run_id": "phase3a_scientist_checkpoint",
                    "state.params.status": "ok",
                },
            },
        ),
    ]

    for path, data, manifest in fixtures:
        atomic_write_bytes(path, data)
        manifest = {**manifest, "path": _rel(path), "bytes": len(data)}
        atomic_write_json(path.with_suffix(".json"), manifest)
        manifests.append(manifest)
    return manifests


def _lookup_field(obj: Any, dotted: str) -> Any:
    value = obj
    for part in dotted.split("."):
        if isinstance(value, Mapping):
            value = value[part]
        else:
            value = getattr(value, part)
    return value


def validate_pickle_fixtures() -> list[Finding]:
    findings: list[Finding] = []
    for manifest_path in sorted(CHECKPOINT_FIXTURE_ROOT.glob("*/*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        fixture_path = REPO_ROOT / manifest["path"]
        try:
            with fixture_path.open("rb") as stream:
                obj = pickle.load(stream)  # noqa: S301 - committed compatibility fixture.
        except Exception as exc:
            findings.append(
                Finding("pickle_compat_gate", "fixture failed to load", f"{fixture_path}: {exc}")
            )
            continue
        observed_type = f"{type(obj).__module__}.{type(obj).__qualname__}"
        if observed_type != manifest["expected_type"]:
            findings.append(
                Finding(
                    "pickle_compat_gate",
                    "fixture loaded as an unexpected type",
                    f"{fixture_path}: {observed_type}",
                )
            )
        for field, expected in manifest.get("expected_fields", {}).items():
            try:
                observed = _lookup_field(obj, field)
            except Exception as exc:
                findings.append(
                    Finding(
                        "pickle_compat_gate",
                        "fixture field missing",
                        f"{fixture_path}: {field}: {exc}",
                    )
                )
                continue
            if observed != expected:
                findings.append(
                    Finding(
                        "pickle_compat_gate",
                        "fixture field mismatch",
                        f"{fixture_path}: {field} expected {expected!r}, got {observed!r}",
                    )
                )
    return findings


def validate_dynamic_imports() -> list[Finding]:
    try:
        registry_text = DYNAMIC_IMPORTS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry is missing",
                _diagnostic_path(DYNAMIC_IMPORTS_PATH),
            )
        ]
    except (OSError, UnicodeError) as error:
        return [
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry cannot be read",
                f"{_diagnostic_path(DYNAMIC_IMPORTS_PATH)}: {type(error).__name__}: {error}",
            )
        ]
    try:
        data = tomllib.loads(registry_text)
    except tomllib.TOMLDecodeError as error:
        return [
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry is malformed",
                f"{_diagnostic_path(DYNAMIC_IMPORTS_PATH)}: {error}",
            )
        ]

    try:
        current = collect_dynamic_imports()
    except DynamicImportCollectionError as error:
        return [
            Finding(
                "dynamic_imports_gate",
                "dynamic import source inventory is incomplete",
                str(error),
            )
        ]
    try:
        canonical = tomllib.loads(render_dynamic_imports_toml(current))
    except (KeyError, TypeError, ValueError) as error:
        return [
            Finding(
                "dynamic_imports_gate",
                "canonical dynamic import inventory cannot be rendered",
                f"{type(error).__name__}: {error}",
            )
        ]

    findings: list[Finding] = []
    canonical_header = canonical.get("dynamic_imports")
    header = data.get("dynamic_imports")
    if not isinstance(canonical_header, dict):
        return [
            Finding(
                "dynamic_imports_gate",
                "canonical dynamic import header is malformed",
                "renderer did not produce a dynamic_imports table",
            )
        ]
    if not isinstance(header, dict):
        findings.append(
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry header is missing or malformed",
                "dynamic_imports",
            )
        )
        header = {}

    external_review_fields = set(DYNAMIC_IMPORT_REVIEW_FIELDS)
    for field in sorted(set(canonical_header) - set(header)):
        findings.append(
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry header field is missing",
                f"dynamic_imports.{field}",
            )
        )
    for field in sorted(set(header) - set(canonical_header) - external_review_fields):
        findings.append(
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry header has an unexpected field",
                f"dynamic_imports.{field}",
            )
        )
    for field in sorted(set(canonical_header) & set(header)):
        actual_value = header[field]
        expected_value = canonical_header[field]
        if type(actual_value) is not type(expected_value) or actual_value != expected_value:
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "dynamic import registry header field differs from canonical contract",
                    f"dynamic_imports.{field}",
                )
            )

    for field in DYNAMIC_IMPORT_REVIEW_FIELDS:
        if field not in header:
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "dynamic import registry header field is missing",
                    f"dynamic_imports.{field}",
                )
            )
        elif not _valid_dynamic_import_review_field(field, header[field]):
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "dynamic import review metadata is malformed",
                    f"dynamic_imports.{field}",
                )
            )

    for field in sorted(set(data) - {"dynamic_imports", "pattern"}):
        findings.append(
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry has an unexpected top-level field",
                field,
            )
        )

    canonical_rows = canonical.get("pattern", [])
    registered_rows = data.get("pattern", [])
    if not isinstance(canonical_rows, list):
        return findings + [
            Finding(
                "dynamic_imports_gate",
                "canonical dynamic import rows are malformed",
                "renderer did not produce an array of pattern tables",
            )
        ]
    if not isinstance(registered_rows, list):
        findings.append(
            Finding(
                "dynamic_imports_gate",
                "dynamic import registry pattern table is malformed",
                "pattern must be an array of tables",
            )
        )
        registered_rows = []

    def signature(entry: Mapping[str, Any]) -> tuple[str, int, str, str] | None:
        source_file = entry.get("source_file")
        line = entry.get("line")
        call = entry.get("call")
        pattern = entry.get("pattern")
        if (
            not isinstance(source_file, str)
            or not source_file
            or type(line) is not int
            or not isinstance(call, str)
            or not call
            or not isinstance(pattern, str)
            or not pattern
        ):
            return None
        return source_file, line, call, pattern

    canonical_by_signature: dict[tuple[str, int, str, str], list[Mapping[str, Any]]] = {}
    for index, entry in enumerate(canonical_rows):
        if not isinstance(entry, dict):
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "canonical dynamic import row is malformed",
                    f"pattern[{index}] must be a table",
                )
            )
            continue
        entry_signature = signature(entry)
        if entry_signature is None:
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "canonical dynamic import row is malformed",
                    f"pattern[{index}] has invalid source_file, line, call, or pattern",
                )
            )
            continue
        canonical_by_signature.setdefault(entry_signature, []).append(entry)

    registered_by_signature: dict[tuple[str, int, str, str], list[Mapping[str, Any]]] = {}
    for index, entry in enumerate(registered_rows):
        if not isinstance(entry, dict):
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "dynamic import registry row is malformed",
                    f"pattern[{index}] must be a table",
                )
            )
            continue
        entry_signature = signature(entry)
        if entry_signature is None:
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "dynamic import registry row is malformed",
                    f"pattern[{index}] has invalid source_file, line, call, or pattern",
                )
            )
            continue
        registered_by_signature.setdefault(entry_signature, []).append(entry)

    canonical_signatures = set(canonical_by_signature)
    registered_signatures = set(registered_by_signature)
    for missing in sorted(canonical_signatures - registered_signatures):
        findings.append(
            Finding("dynamic_imports_gate", "dynamic import call is not registered", repr(missing))
        )
    for stale in sorted(registered_signatures - canonical_signatures):
        findings.append(
            Finding(
                "dynamic_imports_gate",
                "registered dynamic import call no longer exists",
                repr(stale),
            )
        )

    for entry_signature in sorted(canonical_signatures & registered_signatures):
        expected_entries = canonical_by_signature[entry_signature]
        observed_entries = registered_by_signature[entry_signature]
        if len(expected_entries) != len(observed_entries):
            findings.append(
                Finding(
                    "dynamic_imports_gate",
                    "registered dynamic import row count differs from canonical collector",
                    f"{entry_signature!r}: expected {len(expected_entries)}, "
                    f"got {len(observed_entries)}",
                )
            )
        expected_entry = expected_entries[0]
        for observed_entry in observed_entries:
            expected_fields = set(expected_entry)
            observed_fields = set(observed_entry)
            differing_fields = sorted(
                field
                for field in expected_fields | observed_fields
                if field not in expected_fields
                or field not in observed_fields
                or type(expected_entry.get(field)) is not type(observed_entry.get(field))
                or expected_entry.get(field) != observed_entry.get(field)
            )
            if differing_fields:
                findings.append(
                    Finding(
                        "dynamic_imports_gate",
                        "registered dynamic import row differs from canonical collector",
                        f"{entry_signature!r}: fields={differing_fields!r}",
                    )
                )

    for entry in registered_rows:
        if not isinstance(entry, dict):
            continue
        allowed_targets = entry.get("allowed_targets")
        if not isinstance(allowed_targets, list) or any(
            not isinstance(target, str) for target in allowed_targets
        ):
            continue
        for target in allowed_targets:
            module = target.split(":", 1)[0]
            try:
                found = importlib.util.find_spec(module)
            except ImportError, ModuleNotFoundError, ValueError:
                found = None
            if found is None:
                findings.append(
                    Finding(
                        "dynamic_imports_gate",
                        "allowed dynamic import target does not resolve",
                        f"{entry.get('source_file')}:{entry.get('line')} -> {target}",
                    )
                )
    return findings


def validate_import_cycles(
    *, source_snapshot: _ImportSourceSnapshot | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    if not LAZY_IMPORTS_PATH.exists():
        findings.append(
            Finding(
                "import_cycles_gate", "lazy import registry is missing", _rel(LAZY_IMPORTS_PATH)
            )
        )
    else:
        data = tomllib.loads(LAZY_IMPORTS_PATH.read_text(encoding="utf-8"))
        allowed = {tuple(sorted(entry["modules"])) for entry in data.get("allowed_cycle", [])}
        snapshot = source_snapshot or _collect_import_source_snapshot()
        full_graph = collect_import_graph(source_snapshot=snapshot, allow_incomplete=True)
        eager_graph = collect_import_graph(
            runtime_only=True, source_snapshot=snapshot, allow_incomplete=True
        )
        full_cycles = {tuple(sorted(cycle["modules"])) for cycle in full_graph.get("cycles", [])}
        eager_cycles = {tuple(sorted(cycle["modules"])) for cycle in eager_graph.get("cycles", [])}

        for cycle in sorted(full_cycles - allowed):
            message = (
                "new module-eager import cycle"
                if cycle in eager_cycles
                else "new import cycle without deferred-cycle registration"
            )
            findings.append(Finding("import_cycles_gate", message, ", ".join(cycle)))
        allowed_components = {frozenset(cycle) for cycle in allowed}
        for cycle in sorted(eager_cycles):
            eager_component = frozenset(cycle)
            if any(eager_component <= registered for registered in allowed_components):
                findings.append(
                    Finding(
                        "import_cycles_gate",
                        "registered deferred-cycle signature contains a module-eager cycle",
                        ", ".join(cycle),
                    )
                )
        for dispatch in eager_graph["dispatch_resolution"]["unresolved"]:
            findings.append(
                Finding(
                    "import_cycles_gate",
                    "module-time source-known dispatch is not established",
                    (
                        f"{dispatch['source_path']}:{dispatch['line']}:{dispatch['column']} "
                        f"{dispatch['expression']} [{dispatch['reason']}]"
                    ),
                )
            )
        for error in _import_source_errors(snapshot):
            findings.append(
                Finding(
                    "import_cycles_gate",
                    "selected source input is incomplete",
                    (
                        f"{error.get('path')} [{error.get('outcome')}] "
                        f"{error.get('error_type', '')}: {error.get('error', '')}"
                    ).strip(),
                )
            )
    return findings


def validate_public_surface_snapshot() -> list[Finding]:
    return _compare_json_snapshot(
        "public_surface_snapshot_gate",
        PUBLIC_SURFACE_BASELINE_PATH,
        collect_public_surface_snapshot(),
        ignore_keys={"generated_at"},
        normalizer=_normalize_public_surface_snapshot,
    )


def validate_schema_diff() -> list[Finding]:
    baseline = json.loads(SCHEMA_BASELINE_PATH.read_text(encoding="utf-8"))
    current = collect_schema_baseline()
    if _normalize_snapshot(baseline, {"generated_at"}) == _normalize_snapshot(
        current, {"generated_at"}
    ):
        return []
    allowed_fqns = set(_blueprint_source_and_targets())
    findings: list[Finding] = []
    baseline_schemas = {entry["path"]: entry for entry in baseline.get("schemas", [])}
    for entry in current.get("schemas", []):
        old = baseline_schemas.get(entry["path"])
        if old is None:
            findings.append(Finding("schema_diff_gate", "new schema baseline path", entry["path"]))
            continue
        added = set(entry.get("defs_keys", [])) - set(old.get("defs_keys", []))
        removed = set(old.get("defs_keys", [])) - set(entry.get("defs_keys", []))
        unexpected = [key for key in sorted(added | removed) if key not in allowed_fqns]
        if unexpected:
            findings.append(
                Finding(
                    "schema_diff_gate",
                    "unexpected schema definition diff",
                    ", ".join(unexpected[:20]),
                )
            )
        elif entry.get("sha256") != old.get("sha256"):
            findings.append(
                Finding(
                    "schema_diff_gate",
                    "schema hash changed without definition-key drift",
                    str(entry["path"]),
                )
            )
    return findings


def _blueprint_source_and_targets() -> list[str]:
    return [str(item["source_fqn"]) for item in collect_move_map()] + [
        str(item["target_fqn"]) for item in collect_move_map()
    ]


def validate_reexport_shim_shapes() -> list[Finding]:
    findings: list[Finding] = []
    shims_path = REPO_ROOT / "architecture" / "shims.toml"
    if not shims_path.exists():
        return findings
    data = tomllib.loads(shims_path.read_text(encoding="utf-8"))
    for shim in data.get("shim", []):
        if shim.get("type") != "python_reexport":
            continue
        source_path = _shim_source_python_path(REPO_ROOT / str(shim.get("source_path", "")))
        tree = _parse_python(source_path)
        if tree is None:
            findings.append(
                Finding(
                    "reexport_shim_shape_gate", "shim source is not parseable", str(source_path)
                )
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                findings.append(
                    Finding(
                        "reexport_shim_shape_gate",
                        "python re-export shim uses star import",
                        f"{_rel(source_path)}:{node.lineno}",
                    )
                )
    return findings


def validate_import_time_regression(
    threshold: float = 0.15, *, live: bool = False
) -> list[Finding]:
    if not live:
        return []
    baseline = json.loads(IMPORT_TIME_BASELINE_PATH.read_text(encoding="utf-8"))
    current = measure_import_time(runs=3)
    findings: list[Finding] = []
    for package in ("polisyos.scientist", "polisyos.foundry"):
        old = float(baseline[package]["median_wall_ms"])
        new = float(current[package]["median_wall_ms"])
        if old > 0 and new > old * (1.0 + threshold):
            findings.append(
                Finding(
                    "import_time_regression_gate",
                    "import-time median regressed",
                    f"{package}: baseline={old:.3f}ms current={new:.3f}ms",
                )
            )
    return findings


def _compare_json_snapshot(
    gate: str,
    baseline_path: Path,
    current: Mapping[str, Any],
    *,
    ignore_keys: set[str],
    normalizer: Callable[[Any], Any] | None = None,
) -> list[Finding]:
    if not baseline_path.exists():
        return [Finding(gate, "baseline snapshot is missing", _rel(baseline_path))]
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_value = baseline if normalizer is None else normalizer(baseline)
    current_value = current if normalizer is None else normalizer(current)
    if _normalize_snapshot(baseline_value, ignore_keys) != _normalize_snapshot(
        current_value, ignore_keys
    ):
        return [Finding(gate, "snapshot drift detected", _rel(baseline_path))]
    return []


def _normalize_snapshot(value: Any, ignore_keys: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_snapshot(item, ignore_keys)
            for key, item in sorted(value.items())
            if key not in ignore_keys
        }
    if isinstance(value, list):
        return [_normalize_snapshot(item, ignore_keys) for item in value]
    return value


def _is_public_surface_object_record(value: Any) -> bool:
    """Return whether a v1 object row has the collector's source-coordinate shape."""
    if not isinstance(value, dict):
        return False
    line = value.get("line")
    if not isinstance(line, int) or isinstance(line, bool) or line <= 0:
        return False
    if not isinstance(value.get("name"), str) or not isinstance(value.get("fqn"), str):
        return False
    if value.get("kind") == "class":
        return isinstance(value.get("bases"), list) and isinstance(value.get("pydantic"), bool)
    return value.get("kind") in {"function", "async_function"} and isinstance(
        value.get("signature"), str
    )


def _normalize_public_surface_snapshot(value: Any) -> Any:
    """Drop only the v1 object-row source coordinate before snapshot comparison."""
    normalized = _normalize_snapshot(value, set())
    if not isinstance(normalized, dict):
        return normalized
    schema_version = normalized.get("version")
    if type(schema_version) is not int or schema_version != 1:
        return normalized
    packages = normalized.get("packages")
    if not isinstance(packages, list):
        return normalized
    for package in packages:
        if not isinstance(package, dict):
            continue
        modules = package.get("modules")
        if not isinstance(modules, list):
            continue
        for module in modules:
            if not isinstance(module, dict):
                continue
            objects = module.get("objects")
            if not isinstance(objects, list):
                continue
            for object_record in objects:
                if _is_public_surface_object_record(object_record):
                    object_record.pop("line")
    return normalized


def generate_blueprint(*, import_source_snapshot: _ImportSourceSnapshot | None = None) -> str:
    move_map = collect_move_map()
    move_paths = [REPO_ROOT / item["source_path"] for item in move_map]
    importers = collect_external_importers(move_map)
    pydantic_models = collect_pydantic_models(move_paths)
    schema_usage = collect_openapi_model_usage(pydantic_models)
    registrations = collect_registration_audit(move_paths)
    pickle_inventory = collect_pickle_inventory()
    import_graph = collect_import_graph(source_snapshot=import_source_snapshot)
    dynamic_entries = collect_dynamic_imports()
    max_lifetime_days = _max_workflow_lifetime_days()
    shim_sunset_days = max(60, 2 * max_lifetime_days)
    target_sunset = "2026-07-02" if shim_sunset_days == 60 else f"created + {shim_sunset_days} days"

    lines = [
        "---",
        "title: Decomposition Blueprint",
        "status: accepted",
        "adr: ADR-0143",
        "owner: team-scientist/team-foundry",
        "created: 2026-05-03",
        "last_verified: 2026-05-03",
        "stability: phase-3a-baseline",
        "---",
        "",
        "# Decomposition Blueprint",
        "",
        "This is the accepted Phase 3A plan-first artifact for scientist/foundry decomposition.",
        "It authorizes no physical `.py` moves in `src/polisyos/scientist/` or",
        "`src/polisyos/foundry/`; it only freezes contracts for Phase 5/6.",
        "",
        "## ADR-0143 Decision",
        "",
        "- Phase 5/6 may start only after all Phase 3A gates are green.",
        "- Current audited counts are 12 Scientist non-facade root modules and 28 Foundry",
        "  non-facade root modules. These counts supersede older draft text that mentioned",
        "  17/22 modules.",
        "- Every old source FQN gets a targeted Python re-export shim; star imports in shims",
        "  are forbidden by ADR-0144.",
        f"- Shim sunset arithmetic: max(60 days, 2 x max workflow lifetime) = {shim_sunset_days} days.",
        f"  Draft sunset date for Phase 5/6 shims: {target_sunset}.",
        "",
        "## Move Map",
        "",
        "| Source FQN | Target FQN | Type | Reasoning |",
        "| --- | --- | --- | --- |",
    ]
    for item in move_map:
        lines.append(
            f"| `{item['source_fqn']}` | `{item['target_fqn']}` | {item['type']} | {item['reasoning']} |"
        )
    lines.extend(["", "## External Importers", ""])
    for item in move_map:
        entries = importers[item["source_fqn"]]
        lines.append(f"### `{item['source_fqn']}`")
        if entries:
            for importer in entries:
                lines.append(f"- `{importer['path']}:{importer['line']}` ({importer['kind']})")
        else:
            lines.append(
                "- No external importers found in `src/`, `tests/`, `tools/`, `apps/`, or `packages/`."
            )
        lines.append("")
    lines.extend(
        [
            "## Planned Re-export Shims",
            "",
            "| Shim FQN | Target FQN | Shape | Draft sunset |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in move_map:
        lines.append(
            f"| `{item['source_fqn']}` | `{item['target_fqn']}` | targeted names only | {target_sunset} |"
        )
    lines.extend(["", "## Pydantic Models And Runtime API Schema Usage", ""])
    if pydantic_models:
        usage_by_fqn = {entry["model_fqn"]: entry["schema_hits"] for entry in schema_usage}
        lines.extend(["| Model FQN | Source | OpenAPI usage |", "| --- | --- | --- |"])
        for model in pydantic_models:
            hits = ", ".join(usage_by_fqn.get(model["fqn"], [])) or "none"
            lines.append(
                f"| `{model['fqn']}` | `{model['source_file']}:{model['line']}` | {hits} |"
            )
    else:
        lines.append("No Pydantic models were found in planned move files.")
    lines.extend(["", "## JAX/Pydantic Top-level Registrations", ""])
    if registrations:
        for registration in registrations:
            lines.append(
                f"- `{registration['source_file']}:{registration['line']}` "
                f"{', '.join(registration['patterns'])}: `{registration['text']}`"
            )
    else:
        lines.append("- No JAX/Pydantic top-level registrations were found in planned move files.")
    lines.extend(
        [
            "",
            "## Pickle And Checkpoint Inventory",
            "",
            f"- Call sites: {len(pickle_inventory['call_sites'])}",
            f"- Live artifacts: {len(pickle_inventory['live_artifacts'])}",
            f"- Canonical fixtures: `{_rel(CHECKPOINT_FIXTURE_ROOT)}`",
            "",
            "## Dynamic Imports",
            "",
            f"- Registered dynamic import patterns: {len(dynamic_entries)}",
            "- Registry: `architecture/imports/dynamic.toml`",
            "",
            "## Import Cycles",
            "",
            f"- Modules in scientist/foundry graph: {import_graph['module_count']}",
            f"- Edges in graph: {import_graph['edge_count']}",
            "- Deferred SCCs remain in the full AST baseline and the historical inventory in `architecture/imports/lazy.toml`.",
            "- The blocking gate checks source-resolved module-initialization calls supported by the deterministic AST binding collector, including direct construction, tracked instances, and joined class-member values.",
            "- Source-known calls whose factory return, inherited method, custom-`__new__` allocation, rebound receiver, or possible binding target remains unresolved produce machine-readable `not_established` rows and fail the gate.",
            "- One `_BindingKnowledge` value carries every known value variant and the possible-unknown bit through function, module, and class-member exports; joins union targets and OR uncertainty, so one known candidate cannot erase another path.",
            "- Targetless reflective or callback-valued receivers remain machine-reported as "
            "`not_established` outside the source-resolved gate scope; this collector does not "
            "claim whole-language module-eager completeness. `TYPE_CHECKING` and uncalled "
            "function bodies are deferred.",
            "- A deferred-cycle entry never suppresses a source-resolved module-eager cycle.",
            "- The baseline graph records the collector mode; this workspace uses the internal",
            "  deterministic AST graph because `pydeps`/`import-linter` are not required dev",
            "  dependencies here.",
            "",
            "## Baselines",
            "",
            "- `architecture/baselines/structure_remediation/import_graph_pre_decomp.json`",
            "- `architecture/baselines/structure_remediation/import_time_pre_decomp.json`",
            "- `architecture/baselines/structure_remediation/pickle_checkpoint_inventory.json`",
            "- `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`",
            "- `architecture/baselines/structure_remediation/schema_diff_pre_decomp.json`",
            "- `architecture/baselines/structure_remediation/tests_baseline.txt`",
            "",
            "`tests_baseline.txt` intentionally records a deferred full-suite baseline:",
            "the local `pytest tests/unit tests/integration tests/property tests/contract tests/repo_quality -q`",
            "run was not completed because of thermal load on the laptop. The full baseline",
            "must be run in cloud infrastructure during the final Phase 7 closeout; it is",
            "not a local Phase 3A prerequisite.",
            "",
            "## Phase 5/6 Entry Criteria",
            "",
            "- `dynamic_imports_gate` green.",
            "- `pickle_compat_gate` green.",
            "- `public_surface_snapshot_gate` green.",
            "- `import_cycles_gate` green.",
            "- `import_time_regression_gate` green in live CI mode.",
            "- `reexport_shim_shape_gate` green.",
            "- Full-suite baseline remains explicitly deferred to the Phase 7 cloud closeout.",
            "- No `.py` files in `src/polisyos/scientist/` or `src/polisyos/foundry/` moved during Phase 3A.",
        ]
    )
    return "\n".join(lines) + "\n"


def _max_workflow_lifetime_days() -> int:
    candidates: list[int] = []
    shims_path = REPO_ROOT / "architecture" / "shims.toml"
    if shims_path.exists():
        data = tomllib.loads(shims_path.read_text(encoding="utf-8"))
        for shim in data.get("shim", []):
            created = _parse_date(str(shim.get("created", "")))
            sunset = _parse_date(str(shim.get("sunset_date", "")))
            if created and sunset:
                candidates.append(max(1, (sunset - created).days))
    runs_root = REPO_ROOT / ".polisyos" / "runs"
    if runs_root.exists():
        for manifest in runs_root.glob("*/manifest.json"):
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            started = _parse_datetime(
                str(payload.get("created_at") or payload.get("started_at") or "")
            )
            ended = _parse_datetime(
                str(payload.get("finished_at") or payload.get("updated_at") or "")
            )
            if started and ended:
                candidates.append(max(1, (ended - started).days))
    return max(candidates or [30])


def _parse_date(value: str) -> Any:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def write_phase3a_artifacts(
    *, import_runs: int = 10, include_import_time: bool = True
) -> dict[str, Any]:
    import_source_snapshot = _collect_import_source_snapshot()
    import_graph = collect_import_graph(source_snapshot=import_source_snapshot)
    dynamic_entries = collect_dynamic_imports()
    dynamic_registry_text = _render_dynamic_import_registry(
        dynamic_entries,
        path=DYNAMIC_IMPORTS_PATH,
    )
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / "architecture" / "imports").mkdir(parents=True, exist_ok=True)
    create_checkpoint_fixtures()
    atomic_write_text(DYNAMIC_IMPORTS_PATH, dynamic_registry_text)
    atomic_write_text(LAZY_IMPORTS_PATH, render_lazy_toml(import_graph))
    atomic_write_json(IMPORT_GRAPH_BASELINE_PATH, import_graph)
    atomic_write_json(PICKLE_INVENTORY_PATH, collect_pickle_inventory())
    atomic_write_json(PUBLIC_SURFACE_BASELINE_PATH, collect_public_surface_snapshot())
    atomic_write_json(SCHEMA_BASELINE_PATH, collect_schema_baseline())
    if include_import_time:
        atomic_write_json(IMPORT_TIME_BASELINE_PATH, measure_import_time(runs=import_runs))
    elif not IMPORT_TIME_BASELINE_PATH.exists():
        atomic_write_json(IMPORT_TIME_BASELINE_PATH, {"version": 1, "runs": 0})
    atomic_write_text(
        BLUEPRINT_PATH, generate_blueprint(import_source_snapshot=import_source_snapshot)
    )
    return _import_graph_input_receipt(import_source_snapshot)


def _print_import_graph_input_receipt(receipt: Mapping[str, Any]) -> None:
    """Print selector facts and every selected path/hash/outcome for text callers."""
    print("Import graph input receipt:")
    print(
        json.dumps(
            {
                "coverage_status": receipt["coverage_status"],
                "selected_count": receipt["selected_count"],
                "outcome_counts": receipt["outcome_counts"],
                "input_manifest_sha256": receipt["input_manifest_sha256"],
                "selector": receipt["selector"],
                "dispatch_resolution": receipt["observed_graphs"]["module_initialization"][
                    "dispatch_resolution"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    for item in receipt["input_manifest"]:
        print(json.dumps(item, ensure_ascii=False, sort_keys=True))
    for error in receipt["discovery_errors"]:
        print(json.dumps(error, ensure_ascii=False, sort_keys=True))


def run_all_gates(
    *,
    live_import_time: bool = False,
    import_source_snapshot: _ImportSourceSnapshot | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(validate_dynamic_imports())
    findings.extend(validate_pickle_fixtures())
    findings.extend(validate_public_surface_snapshot())
    findings.extend(validate_import_cycles(source_snapshot=import_source_snapshot))
    findings.extend(validate_schema_diff())
    findings.extend(validate_reexport_shim_shapes())
    findings.extend(validate_import_time_regression(live=live_import_time))
    return findings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Write Phase 3A baselines and docs.")
    generate.add_argument("--import-runs", type=int, default=10)
    generate.add_argument("--skip-import-time", action="store_true")
    gate = subparsers.add_parser("gate", help="Run Phase 3A preflight gates.")
    gate.add_argument("--live-import-time", action="store_true")
    gate.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "generate":
        try:
            import_receipt = write_phase3a_artifacts(
                import_runs=args.import_runs,
                include_import_time=not args.skip_import_time,
            )
        except ImportGraphInputError as error:
            print(f"Phase 3A decomposition preflight artifacts NOT generated: {error}")
            _print_import_graph_input_receipt(_import_graph_input_receipt(error.source_snapshot))
            return 1
        except DynamicImportReviewMetadataError as error:
            print(f"Phase 3A decomposition preflight artifacts NOT generated: {error}")
            return 1
        print("Phase 3A decomposition preflight artifacts generated.")
        _print_import_graph_input_receipt(import_receipt)
        return 0

    import_source_snapshot = _collect_import_source_snapshot()
    import_receipt = _import_graph_input_receipt(import_source_snapshot)
    findings = run_all_gates(
        live_import_time=args.live_import_time,
        import_source_snapshot=import_source_snapshot,
    )
    payload = {
        "status": "failed" if findings else "passed",
        "finding_count": len(findings),
        "findings": [
            {"gate": finding.gate, "message": finding.message, "detail": finding.detail}
            for finding in findings
        ],
        "import_graph_input_receipt": import_receipt,
    }
    if args.output_json is not None:
        atomic_write_json(args.output_json, payload)
    _print_import_graph_input_receipt(import_receipt)
    if findings:
        print("Phase 3A decomposition preflight gates FAILED:")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1
    print("Phase 3A decomposition preflight gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
