#!/usr/bin/env python3
"""Phase 3A decomposition preflight inventory and gates."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from tools.lib.fs import atomic_write_bytes, atomic_write_json, atomic_write_text
from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
BASELINE_DIR = REPO_ROOT / "architecture" / "baselines" / "structure_remediation"
BLUEPRINT_PATH = REPO_ROOT / "docs" / "plans" / "active" / "DECOMPOSITION_BLUEPRINT.md"
DYNAMIC_IMPORTS_PATH = REPO_ROOT / "architecture" / "dynamic_imports.toml"
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
    "polisyos.scientist.decision_validity": (
        "polisyos.scientist.validation.decision_validity",
        "Decision-validity checks belong with the Scientist validation package.",
    ),
    "polisyos.scientist.error_semantics": (
        "polisyos.scientist.orchestration.engine.error_semantics",
        "Engine error normalization is used by checkpoint/resume flows.",
    ),
    "polisyos.scientist.evidence_sources": (
        "polisyos.scientist.evidence.sources",
        "Evidence source configuration belongs with the evidence package.",
    ),
    "polisyos.scientist.feedback": (
        "polisyos.scientist.feedback.core",
        "Feedback loop logic becomes a package with explicit core/utils modules.",
    ),
    "polisyos.scientist.feedback_utils": (
        "polisyos.scientist.feedback.utils",
        "Feedback helpers should move next to the feedback implementation.",
    ),
    "polisyos.scientist.frontier_runtime": (
        "polisyos.scientist.orchestration.engine.frontier_runtime",
        "Runtime capability glue is engine-owned and should not shadow top-level runtime.",
    ),
    "polisyos.scientist.latent_separation": (
        "polisyos.scientist.methods.causal.latent_separation",
        "Latent-separation diagnostics are causal-readiness concerns.",
    ),
    "polisyos.scientist.llm_cycle": (
        "polisyos.scientist.orchestration.llm.cycle",
        "LLM orchestration belongs under the Scientist LLM package.",
    ),
    "polisyos.scientist.publisher": (
        "polisyos.scientist.orchestration.orchestrator.publisher",
        "Publisher orchestration should live with decision-card orchestration.",
    ),
    "polisyos.scientist.reliability_scorecard": (
        "polisyos.scientist.validation.reliability_scorecard",
        "Reliability scoring is validation/reporting surface.",
    ),
    "polisyos.scientist.remediation_status": (
        "polisyos.scientist.governance.remediation_status",
        "Remediation status is governance evidence, not a package-root module.",
    ),
    "polisyos.scientist.replay_backend": (
        "polisyos.scientist.replay.backend",
        "Replay backend belongs with replay comparators and verification.",
    ),
    "polisyos.foundry.agent_metrics": (
        "polisyos.foundry.agent_sim.agent_metrics",
        "Agent-specific metrics belong with agent_sim.",
    ),
    "polisyos.foundry.agents": (
        "polisyos.foundry.agent_sim.agents",
        "Agent declarations belong with agent_sim.",
    ),
    "polisyos.foundry.conflict_checker": (
        "polisyos.foundry.validation.conflict_checker",
        "Conflict checking is validation surface.",
    ),
    "polisyos.foundry.constraints_engine": (
        "polisyos.foundry.validation.constraints_engine",
        "Constraint validation belongs under foundry.validation.",
    ),
    "polisyos.foundry.cost_model": (
        "polisyos.foundry.methods.cost_model",
        "Cost modeling is method-selection evidence.",
    ),
    "polisyos.foundry.executor": (
        "polisyos.foundry.execute.executor",
        "The root executor becomes an execute package implementation.",
    ),
    "polisyos.foundry.layout": (
        "polisyos.foundry.methods.layout",
        "Slot layout is method/catalog metadata.",
    ),
    "polisyos.foundry.loss": (
        "polisyos.foundry.methods.loss",
        "Loss helpers are method execution primitives.",
    ),
    "polisyos.foundry.mechanism_design": (
        "polisyos.foundry.mechanisms.design",
        "Mechanism-design helpers belong with mechanisms.",
    ),
    "polisyos.foundry.merge_engine": (
        "polisyos.foundry.methods.components.merge_engine",
        "Method merge contracts belong with the methods package.",
    ),
    "polisyos.foundry.patch_vm": (
        "polisyos.foundry.execute.patch_vm",
        "Patch VM is an execution backend.",
    ),
    "polisyos.foundry.profiles": (
        "polisyos.foundry.runtime.profiles",
        "Profiles are runtime configuration, not root API.",
    ),
    "polisyos.foundry.queue": (
        "polisyos.foundry.execute.queue",
        "Execution queueing belongs under execute.",
    ),
    "polisyos.foundry.quickstart": (
        "polisyos.foundry._quickstart",
        "Quickstart remains importable through the facade but leaves the root.",
    ),
    "polisyos.foundry.registry": (
        "polisyos.foundry._registry",
        "Package-level registry remains internal behind explicit facade exports.",
    ),
    "polisyos.foundry.release_acceptance": (
        "polisyos.foundry.validation.release_acceptance",
        "Release acceptance checks are validation contracts.",
    ),
    "polisyos.foundry.social_weights": (
        "polisyos.foundry.welfare.social_weights",
        "Social weights belong with welfare analysis.",
    ),
    "polisyos.foundry.specs": (
        "polisyos.foundry.contracts.specs",
        "Specs are Foundry contract models.",
    ),
    "polisyos.foundry.trace": (
        "polisyos.foundry.runtime.trace",
        "Tracing helpers belong with runtime support.",
    ),
    "polisyos.foundry.utils": (
        "polisyos.foundry._internal.utils",
        "Root utils are internal helpers and should not be a public root module.",
    ),
    "polisyos.foundry.welfare_bounds": (
        "polisyos.foundry.welfare.bounds",
        "Welfare bounds deserve an explicit welfare package.",
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


def _rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


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
    except (OSError, SyntaxError, UnicodeDecodeError):
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


def _call_pattern(node: ast.Call) -> tuple[str, str, list[str]]:
    call_name = _imported_module_name(node.func)
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


def _owner_for_path(path: Path) -> str:
    rel = _rel(path)
    if "/scientist/" in rel or rel.startswith("src/polisyos/scientist"):
        return "team-scientist"
    if "/foundry/" in rel or rel.startswith("src/polisyos/foundry"):
        return "team-foundry"
    if rel.startswith("tools/"):
        return "team-devx"
    if rel.startswith(("apps/", "packages/")):
        return "team-frontend"
    return "team-architecture"


def collect_dynamic_imports() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in _iter_text_files("src", "tools", "apps", "packages"):
        if path.suffix != ".py":
            continue
        tree = _parse_python(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _imported_module_name(node.func)
            if call_name not in DYNAMIC_CALL_NAMES:
                continue
            resolved_call, pattern, allowed_targets = _call_pattern(node)
            rel_path = _rel(path)
            identity = f"{rel_path}:{node.lineno}:{resolved_call}:{pattern}"
            entries.append(
                {
                    "id": f"dynamic-{_sha(identity)}",
                    "pattern": pattern,
                    "source_file": rel_path,
                    "line": node.lineno,
                    "call": resolved_call,
                    "owner": _owner_for_path(path),
                    "target": pattern,
                    "verifier": "tools/quality/validation/decomposition_preflight.py::validate_dynamic_imports",
                    "allowed_targets": allowed_targets,
                    "notes": _dynamic_notes(rel_path, pattern, allowed_targets),
                }
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


def render_dynamic_imports_toml(entries: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "[dynamic_imports]",
        "version = 1",
        'status = "fail_closed"',
        'owner = "team-architecture"',
        'phase = "3A"',
        'review_owner = "team-architecture"',
        'reviewed_at = "2026-05-06"',
        'review_expires = "2026-08-04"',
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


def collect_public_surface_snapshot() -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    root = SRC_ROOT / "polisyos"
    for package_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if not (package_dir / "__init__.py").exists():
            continue
        package = f"polisyos.{package_dir.name}"
        modules: list[dict[str, Any]] = []
        for path in sorted(package_dir.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = _parse_python(path)
            if tree is None:
                continue
            module_fqn = module_fqn_from_path(path)
            exports = _literal_all(tree)
            objects: list[dict[str, Any]] = []
            for node in tree.body:
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not node.name.startswith("_"):
                    objects.append(
                        {
                            "kind": "function"
                            if isinstance(node, ast.FunctionDef)
                            else "async_function",
                            "name": node.name,
                            "fqn": f"{module_fqn}.{node.name}",
                            "signature": _signature(node),
                            "line": node.lineno,
                        }
                    )
                elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    bases = (
                        sorted(set().union(*(_base_names(base) for base in node.bases)))
                        if node.bases
                        else []
                    )
                    objects.append(
                        {
                            "kind": "class",
                            "name": node.name,
                            "fqn": f"{module_fqn}.{node.name}",
                            "bases": bases,
                            "pydantic": "BaseModel" in bases,
                            "line": node.lineno,
                        }
                    )
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


def collect_import_graph() -> dict[str, Any]:
    roots = [SRC_ROOT / "polisyos" / "scientist", SRC_ROOT / "polisyos" / "foundry"]
    module_paths = {
        module_fqn_from_path(path): path
        for root in roots
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    }
    module_names = set(module_paths)
    edges: dict[str, set[str]] = {module: set() for module in module_names}
    for module, path in module_paths.items():
        tree = _parse_python(path)
        if tree is None:
            continue
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
    return {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "collector": "tools.quality.validation.decomposition_preflight.collect_import_graph",
        "collector_mode": "internal_ast_import_graph",
        "pydeps_available": shutil.which("pydeps") is not None,
        "import_linter_available": importlib.util.find_spec("importlinter") is not None
        or importlib.util.find_spec("import_linter") is not None,
        "notes": (
            "Phase 3A uses a deterministic AST import graph collector because pydeps/import-linter "
            "are not required dev dependencies in this workspace."
        ),
        "module_count": len(module_names),
        "edge_count": len(edge_rows),
        "cycles": cycle_rows,
        "edges": edge_rows,
    }


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
        'notes = "Allowed pre-decomposition lazy SCCs. New SCC signatures fail import_cycles_gate."',
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
    findings: list[Finding] = []
    data = tomllib.loads(DYNAMIC_IMPORTS_PATH.read_text(encoding="utf-8"))
    registered = {
        (
            str(entry["source_file"]),
            int(entry["line"]),
            str(entry["call"]),
            str(entry["pattern"]),
        )
        for entry in data.get("pattern", [])
    }
    current = {
        (
            str(entry["source_file"]),
            int(entry["line"]),
            str(entry["call"]),
            str(entry["pattern"]),
        )
        for entry in collect_dynamic_imports()
    }
    for missing in sorted(current - registered):
        findings.append(
            Finding("dynamic_imports_gate", "dynamic import call is not registered", repr(missing))
        )
    for stale in sorted(registered - current):
        findings.append(
            Finding(
                "dynamic_imports_gate",
                "registered dynamic import call no longer exists",
                repr(stale),
            )
        )
    for entry in data.get("pattern", []):
        for target in entry.get("allowed_targets", []):
            module = str(target).split(":", 1)[0]
            try:
                found = importlib.util.find_spec(module)
            except (ImportError, ModuleNotFoundError, ValueError):
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


def validate_import_cycles() -> list[Finding]:
    findings: list[Finding] = []
    if not LAZY_IMPORTS_PATH.exists():
        return [
            Finding(
                "import_cycles_gate", "lazy import registry is missing", _rel(LAZY_IMPORTS_PATH)
            )
        ]
    data = tomllib.loads(LAZY_IMPORTS_PATH.read_text(encoding="utf-8"))
    allowed = {tuple(sorted(entry["modules"])) for entry in data.get("allowed_cycle", [])}
    current_graph = collect_import_graph()
    current = {tuple(sorted(cycle["modules"])) for cycle in current_graph.get("cycles", [])}
    for cycle in sorted(current - allowed):
        findings.append(
            Finding("import_cycles_gate", "new non-lazy import cycle", ", ".join(cycle))
        )
    return findings


def validate_public_surface_snapshot() -> list[Finding]:
    return _compare_json_snapshot(
        "public_surface_snapshot_gate",
        PUBLIC_SURFACE_BASELINE_PATH,
        collect_public_surface_snapshot(),
        ignore_keys={"generated_at"},
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
    gate: str, baseline_path: Path, current: Mapping[str, Any], *, ignore_keys: set[str]
) -> list[Finding]:
    if not baseline_path.exists():
        return [Finding(gate, "baseline snapshot is missing", _rel(baseline_path))]
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if _normalize_snapshot(baseline, ignore_keys) != _normalize_snapshot(current, ignore_keys):
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


def generate_blueprint() -> str:
    move_map = collect_move_map()
    move_paths = [REPO_ROOT / item["source_path"] for item in move_map]
    importers = collect_external_importers(move_map)
    pydantic_models = collect_pydantic_models(move_paths)
    schema_usage = collect_openapi_model_usage(pydantic_models)
    registrations = collect_registration_audit(move_paths)
    pickle_inventory = collect_pickle_inventory()
    import_graph = collect_import_graph()
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
            "- Registry: `architecture/dynamic_imports.toml`",
            "",
            "## Import Cycles",
            "",
            f"- Modules in scientist/foundry graph: {import_graph['module_count']}",
            f"- Edges in graph: {import_graph['edge_count']}",
            f"- Pre-existing lazy SCCs: {len(import_graph['cycles'])}",
            "- Allowed lazy cycles are frozen in `architecture/imports/lazy.toml`.",
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


def write_phase3a_artifacts(*, import_runs: int = 10, include_import_time: bool = True) -> None:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / "architecture" / "imports").mkdir(parents=True, exist_ok=True)
    dynamic_entries = collect_dynamic_imports()
    import_graph = collect_import_graph()
    create_checkpoint_fixtures()
    atomic_write_text(DYNAMIC_IMPORTS_PATH, render_dynamic_imports_toml(dynamic_entries))
    atomic_write_text(LAZY_IMPORTS_PATH, render_lazy_toml(import_graph))
    atomic_write_json(IMPORT_GRAPH_BASELINE_PATH, import_graph)
    atomic_write_json(PICKLE_INVENTORY_PATH, collect_pickle_inventory())
    atomic_write_json(PUBLIC_SURFACE_BASELINE_PATH, collect_public_surface_snapshot())
    atomic_write_json(SCHEMA_BASELINE_PATH, collect_schema_baseline())
    if include_import_time:
        atomic_write_json(IMPORT_TIME_BASELINE_PATH, measure_import_time(runs=import_runs))
    elif not IMPORT_TIME_BASELINE_PATH.exists():
        atomic_write_json(IMPORT_TIME_BASELINE_PATH, {"version": 1, "runs": 0})
    atomic_write_text(BLUEPRINT_PATH, generate_blueprint())


def run_all_gates(*, live_import_time: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(validate_dynamic_imports())
    findings.extend(validate_pickle_fixtures())
    findings.extend(validate_public_surface_snapshot())
    findings.extend(validate_import_cycles())
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
        write_phase3a_artifacts(
            import_runs=args.import_runs,
            include_import_time=not args.skip_import_time,
        )
        print("Phase 3A decomposition preflight artifacts generated.")
        return 0

    findings = run_all_gates(live_import_time=args.live_import_time)
    payload = {
        "status": "failed" if findings else "passed",
        "finding_count": len(findings),
        "findings": [
            {"gate": finding.gate, "message": finding.message, "detail": finding.detail}
            for finding in findings
        ],
    }
    if args.output_json is not None:
        atomic_write_json(args.output_json, payload)
    if findings:
        print("Phase 3A decomposition preflight gates FAILED:")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1
    print("Phase 3A decomposition preflight gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
