#!/usr/bin/env python3
"""Read-only Phase 0.1 inventory for last-mile repository regressions."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "repository.last_mile_inventory.v1"
PHASE = "0.1"
GENERATED_AT = "2026-05-07T00:00:00Z"
LAST_REVIEWED = "2026-05-07"
DEFAULT_BASELINE_DIR = (
    REPO_ROOT / "architecture" / "baselines" / "repository_best_in_class_last_mile"
)
DEFAULT_INVENTORY = DEFAULT_BASELINE_DIR / "inventory.json"
PLAN_PATH = Path("docs/plans/active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md")

EXPECTED_FINDING_IDS = tuple(f"LM-{index:03d}" for index in range(1, 27))
REQUIRED_FINDING_FIELDS = {
    "path",
    "paths",
    "count",
    "kind",
    "owner",
    "package",
    "finding_id",
    "suggested_target",
    "current_status",
}
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
TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PACKAGE_OWNER = {
    "berl": "team-berl",
    "calibration": "team-foundry",
    "common": "team-core",
    "core": "team-core",
    "data_forge": "team-data-forge",
    "ddm": "team-runtime",
    "fabric": "team-fabric",
    "foundry": "team-foundry",
    "ir": "team-ir",
    "lex": "team-lex",
    "runtime": "team-runtime",
    "schemas": "team-architecture",
    "scholar": "team-scholar",
    "scientist": "team-scientist",
}
SEMANTIC_DUPLICATE_PAIRS = (
    ("src/polisyos/scientist/evidence", "src/polisyos/scientist/evidence_sources.py"),
    ("src/polisyos/scientist/feedback", "src/polisyos/scientist/feedback_utils.py"),
    ("src/polisyos/scientist/replay", "src/polisyos/scientist/replay_backend.py"),
    ("src/polisyos/scientist/llm", "src/polisyos/scientist/llm_cycle.py"),
)
SCIENTIST_PARALLEL_FAMILIES = SEMANTIC_DUPLICATE_PAIRS + (
    ("src/polisyos/scientist/orchestration", "src/polisyos/scientist/orchestrator"),
    ("src/polisyos/scientist/engine/error_semantics.py", "src/polisyos/scientist/error_semantics.py"),
    ("src/polisyos/scientist/engine/frontier_runtime.py", "src/polisyos/scientist/frontier_runtime.py"),
    ("src/polisyos/scientist/governance/remediation_status.py", "src/polisyos/scientist/remediation_status.py"),
    ("src/polisyos/scientist/causal/latent_separation.py", "src/polisyos/scientist/latent_separation.py"),
)
CROSS_CUTTING_NAMES = {
    "adapters",
    "cache",
    "contracts",
    "discovery",
    "governance",
    "llm",
    "observability",
    "provenance",
    "registry",
    "runtime",
    "security",
    "trace",
}
GOVERNANCE_AUDIT_NAMES = CROSS_CUTTING_NAMES | {
    "calibration",
    "config",
    "connectors",
    "errors",
    "extensions",
    "migrations",
    "quality",
    "schemas",
    "validation",
}
LOCAL_JUNK_NAMES = {
    ".DS_Store",
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
PHASE0_4_ALLOWED_NAME_DECISIONS = {
    "scoped_ok",
    "rename",
    "merge",
    "canonical_home_with_adapters",
    "sunset_shim",
}
PHASE0_4_ALLOWED_SCIENTIST_ACTIONS = {
    "wave2_move",
    "wave2_merge",
    "wave2_shim",
    "explicit_non_overlap",
}
PHASE0_4_REQUIRED_CONCERNS = (
    "observability",
    "security",
    "registry",
    "discovery",
    "configuration",
    "tracing",
    "telemetry",
    "calibration",
)
PHASE0_4_CONCERN_ALIASES = {
    "observability": ("observability",),
    "security": ("security",),
    "registry": ("registry",),
    "discovery": ("discovery",),
    "configuration": ("config", "configuration"),
    "tracing": ("trace", "tracing"),
    "telemetry": ("telemetry",),
    "calibration": ("calibration",),
}
PHASE0_4_REQUIRED_SCIENTIST_FAMILIES = {
    "workflows_orchestration_orchestrator_research_dag",
    "methods_legacy_search_discovery_research_roots",
    "extensions_package_registries",
    "governance_validation_verification_policy_verified",
}
REMOVED_ARCHITECTURE_TEST_ROOT = "/".join(("tests", "architecture"))
CANONICAL_ARCHITECTURE_TEST_ROOT = "/".join(
    ("tests", "repo_quality", "architecture")
)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as stream:
        payload = tomllib.load(stream)
    return payload if isinstance(payload, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _tracked_paths(repo_root: Path) -> set[str]:
    paths = _git_lines(repo_root, "ls-files")
    if paths:
        return set(paths)
    measured: set[str] = set()
    for current, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        ]
        for filename in filenames:
            measured.add(_rel(Path(current) / filename, repo_root))
    return measured


def _existing_paths(repo_root: Path, paths: Sequence[str]) -> list[str]:
    return [path for path in paths if (repo_root / path).exists()]


def _source_package_dirs(repo_root: Path) -> list[Path]:
    source_root = repo_root / "src" / "polisyos"
    if not source_root.exists():
        return []
    return sorted(
        child
        for child in source_root.iterdir()
        if child.is_dir()
        and child.name not in IGNORED_DIR_NAMES
        and (child / "__init__.py").exists()
    )


def _package_name(path: Path) -> str:
    return path.name


def _direct_python_files(package_dir: Path) -> list[Path]:
    return sorted(path for path in package_dir.glob("*.py") if path.is_file())


def _collect_loose_root_modules(repo_root: Path) -> dict[str, Any]:
    by_package: dict[str, list[str]] = {}
    for package_dir in _source_package_dirs(repo_root):
        paths = [
            _rel(path, repo_root)
            for path in _direct_python_files(package_dir)
            if path.name != "__init__.py"
        ]
        if paths:
            by_package[_package_name(package_dir)] = paths
    return {"by_package": by_package, "paths": by_package.get("scientist", [])}


def _single_file_shell_policy(repo_root: Path) -> dict[str, Any]:
    layout = _load_toml(repo_root / "architecture" / "packages" / "layout.toml")
    policy = layout.get("single_file_shell_package_policy", {})
    if not isinstance(policy, Mapping):
        policy = {}
    scope_roots = [
        str(item).rstrip("/")
        for item in policy.get(
            "scope_roots",
            ["src/polisyos/fabric", "src/polisyos/ir"],
        )
        if item
    ]
    max_python_files = int(policy.get("max_python_files") or 1)
    return {
        "scope_roots": scope_roots,
        "max_python_files": max_python_files,
    }


def _is_single_file_shell_package(directory: Path, *, max_python_files: int) -> bool:
    if not (directory / "__init__.py").is_file():
        return False
    python_files = sorted(directory.glob("*.py"))
    if len(python_files) > max_python_files:
        return False
    child_dirs = [
        child
        for child in directory.iterdir()
        if child.is_dir() and child.name not in IGNORED_DIR_NAMES
    ]
    return not child_dirs


def _collect_single_file_shell_packages(repo_root: Path) -> dict[str, Any]:
    policy = _single_file_shell_policy(repo_root)
    by_package: dict[str, list[str]] = {}
    for scope in policy["scope_roots"]:
        root = repo_root / str(scope)
        if not root.exists():
            continue
        candidates = [root, *sorted(path for path in root.rglob("*") if path.is_dir())]
        for directory in candidates:
            if not _is_single_file_shell_package(
                directory,
                max_python_files=int(policy["max_python_files"]),
            ):
                continue
            rel_path = _rel(directory, repo_root)
            package = _src_package_for_relpath(rel_path)
            by_package.setdefault(package, []).append(rel_path)
    paths: list[str] = []
    for package in ("fabric", "ir"):
        paths.extend(by_package.get(package, []))
    return {
        "by_package": {package: sorted(paths) for package, paths in sorted(by_package.items())},
        "paths": sorted(paths),
        "policy": policy,
    }


def _collect_semantic_pairs(repo_root: Path) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left, right in SEMANTIC_DUPLICATE_PAIRS:
        paths = _existing_paths(repo_root, (left, right))
        if len(paths) == 2:
            pairs.append(
                {
                    "paths": [left, right],
                    "suggested_target": left,
                    "current_status": "observed",
                }
            )
    return pairs


def _collect_scientist_parallel_families(repo_root: Path) -> list[dict[str, Any]]:
    families: list[dict[str, Any]] = []
    for left, right in SCIENTIST_PARALLEL_FAMILIES:
        paths = _existing_paths(repo_root, (left, right))
        if len(paths) == 2:
            families.append(
                {
                    "paths": [left, right],
                    "suggested_target": left,
                    "current_status": "observed",
                }
            )
    return families


def _first_level_name_index(repo_root: Path) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for package_dir in _source_package_dirs(repo_root):
        package = _package_name(package_dir)
        for child in sorted(package_dir.iterdir()):
            if not child.is_dir() or child.name in IGNORED_DIR_NAMES:
                continue
            index[child.name].append({"package": package, "path": _rel(child, repo_root)})
        for file_path in _direct_python_files(package_dir):
            if file_path.name == "__init__.py":
                continue
            index[file_path.stem].append({"package": package, "path": _rel(file_path, repo_root)})
    return index


def _repeated_name_groups(
    repo_root: Path,
    names: set[str] | None = None,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for name, rows in sorted(_first_level_name_index(repo_root).items()):
        if names is not None and name not in names:
            continue
        packages = sorted({row["package"] for row in rows})
        if len(packages) < 2:
            continue
        paths = sorted({row["path"] for row in rows})
        groups.append({"name": name, "packages": packages, "paths": paths})
    return groups


def _package_from_location(location: str) -> str | None:
    prefix = "src/polisyos/"
    if not location.startswith(prefix):
        return None
    package = location.removeprefix(prefix).split("/", 1)[0]
    return package or None


def _phase0_4_name_decisions(repo_root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    payload = _load_toml(repo_root / "architecture" / "name_registry.toml")
    decisions: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    for entry in payload.get("phase0_4_name_decision", []):
        if not isinstance(entry, Mapping):
            continue
        name = str(entry.get("name", ""))
        decision = str(entry.get("decision", ""))
        if not name:
            findings.append(
                {
                    "severity": "error",
                    "name": "",
                    "message": "Phase 0.4 name decision is missing name.",
                }
            )
            continue
        if name in decisions:
            findings.append(
                {
                    "severity": "error",
                    "name": name,
                    "message": "Phase 0.4 name decision is duplicated.",
                }
            )
        if decision not in PHASE0_4_ALLOWED_NAME_DECISIONS:
            findings.append(
                {
                    "severity": "error",
                    "name": name,
                    "message": "Phase 0.4 name decision uses an unsupported decision.",
                    "decision": decision,
                }
            )
        for field in ("owner", "target_phase", "rationale"):
            if not entry.get(field):
                findings.append(
                    {
                        "severity": "error",
                        "name": name,
                        "message": "Phase 0.4 name decision is missing required metadata.",
                        "missing_field": field,
                    }
                )
        decisions[name] = dict(entry)
    return decisions, findings


def _phase0_4_registry_coverage(repo_root: Path, name: str) -> set[str]:
    payload = _load_toml(repo_root / "architecture" / "name_registry.toml")
    covered: set[str] = set()
    for entry in payload.get("shared_name", []):
        if isinstance(entry, Mapping) and entry.get("name") == name:
            covered.update(str(package) for package in entry.get("allowed_in", []))
    for entry in payload.get("rename_backlog", []):
        if not isinstance(entry, Mapping) or entry.get("name") != name:
            continue
        covered.update(str(package) for package in entry.get("packages", []))
        for location in entry.get("locations", []):
            if isinstance(location, str):
                package = _package_from_location(location)
                if package is not None:
                    covered.add(package)
    return covered


def _phase0_4_first_level_directory_index(repo_root: Path) -> dict[str, dict[str, list[str]]]:
    index: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for package_dir in _source_package_dirs(repo_root):
        package = _package_name(package_dir)
        index[package][package].append(_rel(package_dir, repo_root))
        for child in sorted(package_dir.iterdir()):
            if not child.is_dir() or child.name in IGNORED_DIR_NAMES:
                continue
            index[child.name][package].append(_rel(child, repo_root))
    return index


def _collect_phase0_4_name_collisions(repo_root: Path) -> dict[str, Any]:
    decisions, findings = _phase0_4_name_decisions(repo_root)
    repeated: list[dict[str, Any]] = []
    for name, package_map in sorted(_phase0_4_first_level_directory_index(repo_root).items()):
        if len(package_map) < 2:
            continue
        packages = set(package_map)
        decision = decisions.get(name, {})
        covered = _phase0_4_registry_coverage(repo_root, name)
        if not decision:
            findings.append(
                {
                    "severity": "error",
                    "name": name,
                    "message": "Repeated first-level name has no Phase 0.4 decision.",
                    "packages": sorted(packages),
                }
            )
        if covered and not packages.issubset(covered):
            findings.append(
                {
                    "severity": "error",
                    "name": name,
                    "message": "Repeated first-level name is not fully covered by shared registry or rename backlog.",
                    "packages": sorted(packages),
                    "covered_packages": sorted(covered),
                    "uncovered_packages": sorted(packages - covered),
                }
            )
        repeated.append(
            {
                "name": name,
                "decision": str(decision.get("decision", "")),
                "owner": str(decision.get("owner", "")),
                "target_phase": str(decision.get("target_phase", "")),
                "rationale": str(decision.get("rationale", "")),
                "sunset": str(decision.get("sunset", "none")),
                "packages": [
                    {"package": package, "locations": sorted(locations)}
                    for package, locations in sorted(package_map.items())
                ],
            }
        )
    return {
        "schema_version": "repository.last_mile_inventory.phase0_4.name_collisions.v1",
        "scope": "src/polisyos first-level package directories plus top-level package roots",
        "registry": "architecture/name_registry.toml",
        "allowed_decisions": sorted(PHASE0_4_ALLOWED_NAME_DECISIONS),
        "repeated_first_level_names": repeated,
        "findings": sorted(findings, key=lambda row: (row.get("name", ""), row.get("message", ""))),
    }


def _phase0_4_concern_contracts(repo_root: Path) -> dict[str, dict[str, Any]]:
    payload = _load_toml(repo_root / "architecture" / "policies" / "cross_cutting_concerns.toml")
    return {
        str(entry.get("name", "")): dict(entry)
        for entry in payload.get("concern", [])
        if isinstance(entry, Mapping)
    }


def _src_package_for_relpath(rel_path: str) -> str:
    parts = rel_path.split("/")
    if len(parts) >= 3 and parts[0] == "src" and parts[1] == "polisyos":
        return parts[2]
    return ""


def _walk_source_paths(repo_root: Path) -> tuple[list[Path], list[Path]]:
    source_root = repo_root / "src" / "polisyos"
    dirs: list[Path] = []
    files: list[Path] = []
    if not source_root.exists():
        return dirs, files
    for current, dirnames, filenames in os.walk(source_root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        ]
        current_path = Path(current)
        dirs.append(current_path)
        files.extend(current_path / filename for filename in filenames)
    return sorted(dirs), sorted(files)


def _collect_phase0_4_cross_cutting_concerns(repo_root: Path) -> dict[str, Any]:
    source_root = repo_root / "src" / "polisyos"
    dirs, files = _walk_source_paths(repo_root)
    contracts = _phase0_4_concern_contracts(repo_root)
    concerns: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for concern_name in PHASE0_4_REQUIRED_CONCERNS:
        aliases = set(PHASE0_4_CONCERN_ALIASES[concern_name])
        locations: list[dict[str, str]] = []
        for directory in dirs:
            if directory == source_root or directory.name not in aliases:
                continue
            rel_path = _rel(directory, repo_root)
            locations.append(
                {
                    "path": rel_path,
                    "kind": "package",
                    "package": _src_package_for_relpath(rel_path),
                }
            )
        for file_path in files:
            if file_path.suffix != ".py" or file_path.stem not in aliases:
                continue
            rel_path = _rel(file_path, repo_root)
            locations.append(
                {
                    "path": rel_path,
                    "kind": "module",
                    "package": _src_package_for_relpath(rel_path),
                }
            )

        contract = contracts.get(concern_name, {})
        canonical_home = str(
            contract.get("canonical_home")
            or contract.get("canonical_interface")
            or contract.get("canonical_package")
            or ""
        )
        adapter_policy = str(contract.get("adapter_policy") or contract.get("import_rule") or "")
        proposed_before_wave = str(contract.get("proposed_before_wave", ""))
        if not contract:
            findings.append(
                {
                    "severity": "error",
                    "name": concern_name,
                    "message": "Cross-cutting concern is missing from the concern contract.",
                }
            )
        for field_name, value in (
            ("canonical_home", canonical_home),
            ("adapter_policy", adapter_policy),
            ("proposed_before_wave", proposed_before_wave),
        ):
            if not value:
                findings.append(
                    {
                        "severity": "error",
                        "name": concern_name,
                        "message": "Cross-cutting concern contract is missing required Phase 0.4 metadata.",
                        "missing_field": field_name,
                    }
                )
        concerns.append(
            {
                "name": concern_name,
                "canonical_home": canonical_home,
                "adapter_policy": adapter_policy,
                "proposed_before_wave": proposed_before_wave,
                "decision": str(contract.get("decision", "")),
                "implementation_locations": sorted(
                    locations,
                    key=lambda row: (row["path"], row["kind"]),
                ),
            }
        )

    return {
        "schema_version": "repository.last_mile_inventory.phase0_4.cross_cutting_concerns.v1",
        "contract": "architecture/policies/cross_cutting_concerns.toml",
        "concerns": concerns,
        "findings": sorted(findings, key=lambda row: (row.get("name", ""), row.get("message", ""))),
    }


def _phase0_4_existing_locations(repo_root: Path, candidates: Sequence[str]) -> list[str]:
    return [path for path in candidates if (repo_root / path).exists()]


def _collect_phase0_4_scientist_parallel_implementations(repo_root: Path) -> dict[str, Any]:
    definitions = (
        {
            "family_id": "workflows_orchestration_orchestrator_research_dag",
            "label": "Scientist workflow/orchestration/orchestrator/research DAG roots",
            "current_locations": (
                "src/polisyos/scientist/workflows",
                "src/polisyos/scientist/orchestration",
                "src/polisyos/scientist/orchestration/workflows",
                "src/polisyos/scientist/orchestrator",
                "src/polisyos/scientist/orchestration/orchestrator",
                "src/polisyos/scientist/research_dag",
                "src/polisyos/scientist/methods/workflows",
                "src/polisyos/scientist/methods/research_dag",
            ),
            "canonical_home": "polisyos.scientist.orchestration",
            "action": "wave2_merge",
            "rationale": (
                "Wave 2 keeps orchestration as the active implementation boundary, "
                "merges workflow builders below orchestration/workflows, and keeps old "
                "workflow/orchestrator/research_dag roots only as smoke-tested shims if import evidence requires it."
            ),
        },
        {
            "family_id": "methods_legacy_search_discovery_research_roots",
            "label": "Scientist methods versus legacy search/discovery/research roots",
            "current_locations": (
                "src/polisyos/scientist/methods",
                "src/polisyos/scientist/methods/search",
                "src/polisyos/scientist/methods/discovery",
                "src/polisyos/scientist/methods/research_dag",
                "src/polisyos/scientist/discovery",
                "src/polisyos/scientist/research_dag",
                "src/polisyos/scientist/causal",
                "src/polisyos/scientist/methods/causal",
                "src/polisyos/scientist/autotune",
                "src/polisyos/scientist/methods/autotune",
                "src/polisyos/scientist/backtesting",
                "src/polisyos/scientist/methods/backtesting",
                "src/polisyos/scientist/doe",
                "src/polisyos/scientist/methods/doe",
            ),
            "canonical_home": "polisyos.scientist.methods",
            "action": "wave2_move",
            "rationale": (
                "Wave 2 moves active search, discovery, research DAG, causal, autotune, "
                "backtesting, and DOE implementations below methods; first-level roots become registered shims only where import evidence requires them."
            ),
        },
        {
            "family_id": "extensions_package_registries",
            "label": "Scientist extensions versus repository extension registries",
            "current_locations": (
                "src/polisyos/scientist/extensions",
                "src/polisyos/data_forge/extensions",
                "src/polisyos/fabric/extensions",
                "src/polisyos/foundry/extensions",
                "src/polisyos/lex/extensions",
                "src/polisyos/runtime/extensions",
                "src/polisyos/scientist/engine/registry.py",
                "src/polisyos/scientist/agent/tools/registry.py",
                "architecture/extension_points.toml",
            ),
            "canonical_home": "architecture/extension_points.toml plus package-local extension modules",
            "action": "explicit_non_overlap",
            "rationale": (
                "Extension packages are package-scoped authoring surfaces, while architecture/extension_points.toml "
                "owns cross-package entry-point policy; Scientist registry modules remain local implementation registries unless promoted by a later ABI decision."
            ),
        },
        {
            "family_id": "governance_validation_verification_policy_verified",
            "label": "Scientist governance, validation, verification, and policy-verified roots",
            "current_locations": (
                "src/polisyos/scientist/governance",
                "src/polisyos/scientist/governance/continuous",
                "src/polisyos/scientist/governance/human_review",
                "src/polisyos/scientist/continuous_governance",
                "src/polisyos/scientist/human_review",
                "src/polisyos/scientist/validation",
                "src/polisyos/scientist/verification",
                "src/polisyos/scientist/validation/verification",
                "src/polisyos/scientist/policy_verified",
                "src/polisyos/scientist/validation/policy_verified",
            ),
            "canonical_home": "polisyos.scientist.governance and polisyos.scientist.validation",
            "action": "wave2_shim",
            "rationale": (
                "Wave 2 moves continuous governance and human review below governance, moves verification and policy_verified below validation, "
                "and leaves current first-level roots as dated compatibility shims only where import evidence requires them."
            ),
        },
    )
    families = [
        {
            "family_id": str(definition["family_id"]),
            "label": str(definition["label"]),
            "wave": "2",
            "action": str(definition["action"]),
            "canonical_home": str(definition["canonical_home"]),
            "current_locations": _phase0_4_existing_locations(
                repo_root,
                definition["current_locations"],
            ),
            "rationale": str(definition["rationale"]),
        }
        for definition in definitions
    ]
    findings = [
        {
            "severity": "error",
            "family_id": family["family_id"],
            "message": "Scientist parallel implementation family has no current locations.",
        }
        for family in families
        if not family["current_locations"]
    ]
    return {
        "schema_version": "repository.last_mile_inventory.phase0_4.scientist_parallel_implementations.v1",
        "scope": "Scientist old/new implementation families scheduled for Wave 2 closeout",
        "families": families,
        "findings": findings,
    }


def _collect_schema_residue(repo_root: Path) -> list[str]:
    schema_root = repo_root / "schemas"
    if not schema_root.exists():
        return []
    residue: list[str] = []
    for current, dirnames, filenames in os.walk(schema_root):
        if "__pycache__" in dirnames:
            residue.append(_rel(Path(current) / "__pycache__", repo_root))
        for filename in filenames:
            path = Path(current) / filename
            if path.suffix in {".py", ".pyc", ".pyo"}:
                residue.append(_rel(path, repo_root))
    return sorted(set(residue))


def _extract_sunset(readme_path: Path, repo_root: Path) -> dict[str, Any]:
    text = _read_text(readme_path)
    date_match = None
    for line in text.splitlines():
        if "sunset" not in line.lower():
            continue
        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", line)
        if date_match:
            break
    return {
        "metadata_present": date_match is not None,
        "sunset_date": date_match.group(1) if date_match else None,
        "source": _rel(readme_path, repo_root) if readme_path.exists() else None,
    }


def _merge_sunsets(repo_root: Path, paths: Sequence[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    dates: list[str] = []
    for path in paths:
        readme = repo_root / path / "README.md"
        sunset = _extract_sunset(readme, repo_root)
        rows.append({"path": path, **sunset})
        if sunset["sunset_date"]:
            dates.append(str(sunset["sunset_date"]))
    return {
        "metadata_present": any(row["metadata_present"] for row in rows),
        "sunset_date": sorted(set(dates))[0] if dates else None,
        "source": rows[0]["source"] if len(rows) == 1 else None,
        "rows": rows,
    }


def _collect_large_modules(repo_root: Path) -> dict[str, Any]:
    contract = _load_toml(repo_root / "architecture" / "module_size_budget.toml")
    rows: list[dict[str, Any]] = []
    for item in contract.get("budget", []):
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("path", ""))
        current = int(item.get("current_lines") or item.get("baseline_lines") or 0)
        target = int(item.get("target_lines") or 0)
        if path and current > target:
            rows.append(
                {
                    "path": path,
                    "package": str(item.get("package", "")),
                    "owner": str(item.get("owner", "")),
                    "current_lines": current,
                    "target_lines": target,
                    "sunset": str(item.get("sunset", "")),
                }
            )
    return {"rows": rows, "paths": [row["path"] for row in rows]}


def _collect_mirror_regression_packages(repo_root: Path) -> dict[str, Any]:
    target_packages = {"scientist", "fabric", "foundry", "ir", "core", "berl", "lex", "scholar"}
    payload = _load_json(
        repo_root
        / "architecture"
        / "baselines"
        / "repository_best_in_class_phase0_4"
        / "verification_inventory.json"
    )
    rows: list[dict[str, Any]] = []
    for row in payload.get("ratchet_starting_points", []):
        if not isinstance(row, Mapping) or row.get("package") not in target_packages:
            continue
        package = str(row["package"])
        path = f"architecture/packages/{package}.toml"
        rows.append(
            {
                "path": path,
                "package": package,
                "mirror_floor": row.get("mirror_floor"),
                "property_file_floor": row.get("property_file_floor"),
                "unit_test_file_floor": row.get("unit_test_file_floor"),
            }
        )
    return {"rows": rows, "paths": [row["path"] for row in rows]}


def _collect_local_ignored_residue(repo_root: Path) -> list[str]:
    residue: set[str] = set()
    for path in _git_lines(repo_root, "ls-files", "-o", "-i", "--exclude-standard"):
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "_build" and parts[1].startswith("phase7-local-junk"):
            residue.add("/".join(parts[:2]))
            continue
        if parts and parts[0] in LOCAL_JUNK_NAMES:
            residue.add(parts[0])
    return sorted(residue)


def _collect_architecture_gate_split(repo_root: Path) -> list[str]:
    root_files = sorted(
        _rel(path, repo_root)
        for path in (repo_root / "architecture").glob("*gate*.toml")
        if path.is_file()
    )
    gate_files = sorted(
        _rel(path, repo_root)
        for path in (repo_root / "architecture" / "gates").rglob("*")
        if path.is_file()
    )
    return root_files + gate_files


def _collect_entry_point_example_gaps(repo_root: Path) -> dict[str, Any]:
    pyproject = _load_toml(repo_root / "pyproject.toml")
    project = pyproject.get("project", {}) if isinstance(pyproject.get("project"), Mapping) else {}
    groups = project.get("entry-points", {}) if isinstance(project.get("entry-points"), Mapping) else {}
    group_name = "polisyos.scientist_governance_passes"
    entries = groups.get(group_name, {}) if isinstance(groups.get(group_name), Mapping) else {}
    example_paths = [
        path
        for path in _tracked_paths(repo_root)
        if path.startswith("examples/") and "scientist" in path.lower()
    ]
    paths = ["pyproject.toml"]
    paths.extend(example_paths)
    return {
        "paths": sorted(set(paths)),
        "entry_point_group": group_name,
        "entry_point_count": len(entries),
        "scientist_example_count": len(example_paths),
    }


def _collect_adr_index_paths(repo_root: Path) -> list[str]:
    paths = [
        "docs/adr/index.toml",
        "docs/adr/index.md",
        "tools/quality/validation/generate_adr_index.py",
    ]
    return _existing_paths(repo_root, paths)


def _collect_operability_bundle_paths(repo_root: Path) -> list[str]:
    component_root = repo_root / "ops" / "components"
    if not component_root.exists():
        return []
    required = ("alerts.yml", "dashboard.json", "retention-policy.toml", "runtime-contract.toml", "slo.yaml")
    paths: list[str] = ["ops/components/index.toml"] if (component_root / "index.toml").exists() else []
    for child in sorted(component_root.iterdir()):
        if not child.is_dir():
            continue
        missing = [name for name in required if not (child / name).exists()]
        if missing:
            paths.append(_rel(child, repo_root))
    return sorted(set(paths))


def _collect_tool_budget_paths(repo_root: Path) -> dict[str, Any]:
    contract = _load_toml(repo_root / "architecture" / "module_size_budget.toml")
    budgets = contract.get("budget", [])
    budget_paths = {
        str(item.get("path"))
        for item in budgets
        if isinstance(item, Mapping) and str(item.get("path", "")).startswith("tools/quality/validation/")
    }
    new_tool = "tools/quality/validation/repository_last_mile_inventory.py"
    return {
        "paths": [new_tool, "architecture/module_size_budget.toml"],
        "budget_registered": new_tool in budget_paths,
    }


def _collect_test_helper_paths(repo_root: Path) -> list[str]:
    tracked = _tracked_paths(repo_root)
    paths = [
        path
        for path in tracked
        if path.startswith("tests/_helpers/")
        or (path.startswith("tests/") and path.endswith("/conftest.py"))
    ]
    return sorted(paths)


def _collect_frontend_mentions(repo_root: Path) -> list[str]:
    paths: list[str] = []
    for rel_path in sorted(_tracked_paths(repo_root)):
        if rel_path.startswith(("frontend/", "_build/", "_cache/", ".venv/")):
            continue
        path = repo_root / rel_path
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = _read_text(path)
        if "frontend/" in text or "`frontend`" in text or "frontend path" in text.lower():
            paths.append(rel_path)
    return paths


def _collect_taxonomy_paths(repo_root: Path) -> list[str]:
    architecture_root = repo_root / "architecture"
    concern_terms = ("taxonomy", "concept", "gate", "concern")
    return sorted(
        _rel(path, repo_root)
        for path in architecture_root.glob("*.toml")
        if path.is_file() and any(term in path.stem for term in concern_terms)
    )


def _finding(
    *,
    finding_id: str,
    kind: str,
    owner: str,
    package: str,
    paths: Sequence[str],
    suggested_target: str,
    current_status: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    sunset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    unique_paths = sorted(dict.fromkeys(paths))
    row: dict[str, Any] = {
        "finding_id": finding_id,
        "kind": kind,
        "owner": owner,
        "package": package,
        "path": unique_paths[0] if unique_paths else "",
        "paths": unique_paths,
        "count": len(unique_paths),
        "suggested_target": suggested_target,
        "current_status": current_status or ("observed" if unique_paths else "not_observed"),
    }
    if metadata is not None:
        row["metadata"] = dict(metadata)
    if sunset is not None:
        row["sunset"] = dict(sunset)
    return row


def collect_inventory(
    repo_root: Path = REPO_ROOT,
    *,
    include_local_ignored_residue: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    loose = _collect_loose_root_modules(repo_root)
    shells = _collect_single_file_shell_packages(repo_root)
    semantic_pairs = _collect_semantic_pairs(repo_root)
    scientist_families = _collect_scientist_parallel_families(repo_root)
    concern_groups = _repeated_name_groups(repo_root, CROSS_CUTTING_NAMES)
    repeated_groups = _repeated_name_groups(repo_root, GOVERNANCE_AUDIT_NAMES)
    large_modules = _collect_large_modules(repo_root)
    mirror = _collect_mirror_regression_packages(repo_root)
    shims = _existing_paths(repo_root, ("src/polisyos/ddm_15_7", "src/polisyos/synthetic_world"))
    local_residue = (
        _collect_local_ignored_residue(repo_root) if include_local_ignored_residue else []
    )
    entry_examples = _collect_entry_point_example_gaps(repo_root)
    tool_budget = _collect_tool_budget_paths(repo_root)

    findings = [
        _finding(
            finding_id="LM-001",
            kind="package_root_loose_python",
            owner="team-scientist",
            package="scientist",
            paths=loose["paths"],
            suggested_target="src/polisyos/scientist/<domain>/",
            metadata={"by_package": loose["by_package"]},
        ),
        _finding(
            finding_id="LM-002",
            kind="single_file_shell_package",
            owner="team-fabric,team-ir",
            package="fabric,ir",
            paths=shells["paths"],
            suggested_target="package-local implementation module or dated facade exception",
            metadata={"by_package": shells["by_package"], "policy": shells["policy"]},
        ),
        _finding(
            finding_id="LM-003",
            kind="near_duplicate_sibling_package",
            owner="team-ir",
            package="ir",
            paths=_existing_paths(repo_root, ("src/polisyos/ir/references", "src/polisyos/ir/refs")),
            suggested_target="src/polisyos/ir/references",
        ),
        _finding(
            finding_id="LM-004",
            kind="near_duplicate_sibling_package",
            owner="team-scientist",
            package="scientist",
            paths=_existing_paths(
                repo_root,
                ("src/polisyos/scientist/orchestration", "src/polisyos/scientist/orchestrator"),
            ),
            suggested_target="src/polisyos/scientist/orchestration",
        ),
        _finding(
            finding_id="LM-005",
            kind="semantic_duplicate_pair",
            owner="team-scientist",
            package="scientist",
            paths=[path for pair in semantic_pairs for path in pair["paths"]],
            suggested_target="scientist domain packages with root-file compatibility shims",
            metadata={"semantic_pairs": semantic_pairs},
        ),
        _finding(
            finding_id="LM-006",
            kind="compatibility_wrapper_sunset",
            owner="team-architecture",
            package="ddm_15_7,synthetic_world",
            paths=shims,
            suggested_target="src/polisyos/ddm and src/polisyos/foundry/agent_sim/world",
            sunset=_merge_sunsets(repo_root, shims),
        ),
        _finding(
            finding_id="LM-007",
            kind="large_module_ratchet",
            owner="owning-package-teams",
            package="foundry,data_forge,scientist,runtime",
            paths=large_modules["paths"],
            suggested_target="architecture/module_size_budget.toml extraction_sequence",
            metadata={"modules": large_modules["rows"]},
        ),
        _finding(
            finding_id="LM-008",
            kind="mirror_coverage_regression_baseline",
            owner="team-quality",
            package="scientist,fabric,foundry,ir,core,berl,lex,scholar",
            paths=mirror["paths"],
            suggested_target="architecture/tests/ratchets.toml",
            metadata={"packages": mirror["rows"]},
        ),
        _finding(
            finding_id="LM-009",
            kind="local_ignored_residue",
            owner="team-devx",
            package="repository",
            paths=local_residue,
            suggested_target="_build/.tmp or remove after evidence capture",
            metadata={"known_junk_names": sorted(LOCAL_JUNK_NAMES)},
        ),
        _finding(
            finding_id="LM-010",
            kind="redirect_only_directory",
            owner="team-quality",
            package="tests",
            paths=_existing_paths(repo_root, (REMOVED_ARCHITECTURE_TEST_ROOT,)),
            suggested_target=CANONICAL_ARCHITECTURE_TEST_ROOT,
            sunset=_merge_sunsets(
                repo_root,
                _existing_paths(repo_root, (REMOVED_ARCHITECTURE_TEST_ROOT,)),
            ),
        ),
        _finding(
            finding_id="LM-011",
            kind="integration_bridge_coverage_gap",
            owner="team-quality",
            package="tests",
            paths=sorted(
                path
                for path in _tracked_paths(repo_root)
                if path.startswith("tests/integration/") and path.endswith(".py")
            ),
            suggested_target="tests/integration/<package_bridge>/",
            current_status="needs_review",
        ),
        _finding(
            finding_id="LM-012",
            kind="redirect_only_directory",
            owner="team-frontend",
            package="frontend",
            paths=_existing_paths(repo_root, ("frontend",)),
            suggested_target="apps/ and packages/",
            sunset=_merge_sunsets(repo_root, _existing_paths(repo_root, ("frontend",))),
        ),
        _finding(
            finding_id="LM-013",
            kind="architecture_gate_split",
            owner="team-architecture",
            package="architecture",
            paths=_collect_architecture_gate_split(repo_root),
            suggested_target="architecture/gates/** or registered root-level exception",
        ),
        _finding(
            finding_id="LM-014",
            kind="directory_role_review",
            owner="team-data-forge",
            package="data_forge",
            paths=_existing_paths(repo_root, ("data/policy-engine-local",)),
            suggested_target="data/<documented-local-role>",
        ),
        _finding(
            finding_id="LM-015",
            kind="cross_cutting_concern_duplicate",
            owner="team-architecture",
            package="multiple",
            paths=[path for group in concern_groups for path in group["paths"]],
            suggested_target="architecture/contracts/cross_cutting_concerns.toml",
            metadata={"repeated_names": concern_groups},
        ),
        _finding(
            finding_id="LM-016",
            kind="scientist_parallel_family",
            owner="team-scientist",
            package="scientist",
            paths=[path for family in scientist_families for path in family["paths"]],
            suggested_target="src/polisyos/scientist/<canonical-family>/",
            metadata={"families": scientist_families},
        ),
        _finding(
            finding_id="LM-017",
            kind="repeated_cross_package_name",
            owner="team-architecture",
            package="multiple",
            paths=[path for group in repeated_groups for path in group["paths"]],
            suggested_target="architecture/name_registry.toml",
            metadata={"repeated_names": repeated_groups},
        ),
        _finding(
            finding_id="LM-018",
            kind="public_entrypoint_example_gap",
            owner="team-devx",
            package="examples",
            paths=entry_examples["paths"],
            suggested_target="examples/scientist_governance_passes/",
            current_status="needs_review",
            metadata=entry_examples,
        ),
        _finding(
            finding_id="LM-019",
            kind="adr_thematic_index_gap",
            owner="team-docs",
            package="docs",
            paths=_collect_adr_index_paths(repo_root),
            suggested_target="docs/adr/index.md generated from docs/adr/index.toml",
        ),
        _finding(
            finding_id="LM-020",
            kind="operability_bundle_completeness",
            owner="team-ops",
            package="ops",
            paths=_collect_operability_bundle_paths(repo_root),
            suggested_target="ops/components/<component>/ complete bundle",
            current_status="needs_review",
        ),
        _finding(
            finding_id="LM-021",
            kind="validation_tool_budget_gap",
            owner="team-devx",
            package="tools",
            paths=tool_budget["paths"],
            suggested_target="architecture/module_size_budget.toml",
            current_status="needs_review",
            metadata=tool_budget,
        ),
        _finding(
            finding_id="LM-022",
            kind="top_level_schema_python_cache_residue",
            owner="team-architecture",
            package="schemas",
            paths=_collect_schema_residue(repo_root),
            suggested_target="src/polisyos/schemas or generated schema artifacts",
        ),
        _finding(
            finding_id="LM-023",
            kind="test_helper_duplication_surface",
            owner="team-quality",
            package="tests",
            paths=_collect_test_helper_paths(repo_root),
            suggested_target="tests/_helpers contract and layer-local conftest policy",
            current_status="needs_review",
        ),
        _finding(
            finding_id="LM-024",
            kind="shim_sunset_caller_report_gap",
            owner="team-architecture",
            package="compatibility-shims",
            paths=shims + ["architecture/tests/ratchets.toml"],
            suggested_target="caller report for each sunset shim",
            current_status="needs_review",
            sunset=_merge_sunsets(repo_root, shims),
        ),
        _finding(
            finding_id="LM-025",
            kind="stale_frontend_path_reference",
            owner="team-frontend",
            package="frontend",
            paths=_collect_frontend_mentions(repo_root),
            suggested_target="apps/ and packages/ references",
            current_status="needs_review",
        ),
        _finding(
            finding_id="LM-026",
            kind="architecture_taxonomy_closure",
            owner="team-architecture",
            package="architecture",
            paths=_collect_taxonomy_paths(repo_root),
            suggested_target="architecture/conceptual_groups.toml and concern taxonomy closure",
            current_status="needs_review",
        ),
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "generated_at": GENERATED_AT,
        "last_reviewed": LAST_REVIEWED,
        "mode": "read_only_inventory",
        "plan": PLAN_PATH.as_posix(),
        "name_collisions": _collect_phase0_4_name_collisions(repo_root),
        "cross_cutting_concerns": _collect_phase0_4_cross_cutting_concerns(repo_root),
        "scientist_parallel_implementations": _collect_phase0_4_scientist_parallel_implementations(
            repo_root
        ),
        "finding_ids": list(EXPECTED_FINDING_IDS),
        "findings": findings,
        "summary": {
            "finding_count": len(findings),
            "observed_count": sum(1 for finding in findings if finding["current_status"] == "observed"),
            "needs_review_count": sum(
                1 for finding in findings if finding["current_status"] == "needs_review"
            ),
            "not_observed_count": sum(
                1 for finding in findings if finding["current_status"] == "not_observed"
            ),
            "path_count": sum(int(finding["count"]) for finding in findings),
        },
    }


def validate_inventory(inventory: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for section in (
        "name_collisions",
        "cross_cutting_concerns",
        "scientist_parallel_implementations",
    ):
        if not isinstance(inventory.get(section), Mapping):
            errors.append(f"inventory.{section} must be an object")

    name_collisions = inventory.get("name_collisions")
    if isinstance(name_collisions, Mapping):
        for finding in name_collisions.get("findings", []):
            if isinstance(finding, Mapping):
                errors.append(
                    f"name collision: {finding.get('name')}: {finding.get('message')}"
                )

    concerns_payload = inventory.get("cross_cutting_concerns")
    if isinstance(concerns_payload, Mapping):
        for finding in concerns_payload.get("findings", []):
            if isinstance(finding, Mapping):
                errors.append(f"concern: {finding.get('name')}: {finding.get('message')}")
        concern_names = {
            row.get("name")
            for row in concerns_payload.get("concerns", [])
            if isinstance(row, Mapping)
        }
        missing_concerns = sorted(set(PHASE0_4_REQUIRED_CONCERNS) - concern_names)
        if missing_concerns:
            errors.append(f"missing Phase 0.4 concerns: {', '.join(missing_concerns)}")

    scientist_payload = inventory.get("scientist_parallel_implementations")
    if isinstance(scientist_payload, Mapping):
        for finding in scientist_payload.get("findings", []):
            if isinstance(finding, Mapping):
                errors.append(
                    f"scientist: {finding.get('family_id')}: {finding.get('message')}"
                )
        family_ids = {
            row.get("family_id")
            for row in scientist_payload.get("families", [])
            if isinstance(row, Mapping)
        }
        missing_families = sorted(PHASE0_4_REQUIRED_SCIENTIST_FAMILIES - family_ids)
        if missing_families:
            errors.append(f"missing Scientist families: {', '.join(missing_families)}")
        for row in scientist_payload.get("families", []):
            if isinstance(row, Mapping) and row.get("action") not in PHASE0_4_ALLOWED_SCIENTIST_ACTIONS:
                errors.append(f"unsupported Scientist action: {row.get('family_id')}")

    findings = inventory.get("findings")
    if not isinstance(findings, list):
        return ["inventory.findings must be a list"]
    observed_ids = [finding.get("finding_id") for finding in findings if isinstance(finding, Mapping)]
    if set(observed_ids) != set(EXPECTED_FINDING_IDS):
        errors.append(
            "inventory findings must report exactly "
            f"{', '.join(EXPECTED_FINDING_IDS)}"
        )
    if len(observed_ids) != len(set(observed_ids)):
        errors.append("inventory findings must not contain duplicate finding_id values")
    for finding in findings:
        if not isinstance(finding, Mapping):
            errors.append("inventory findings must be objects")
            continue
        finding_id = str(finding.get("finding_id", "<missing>"))
        missing = REQUIRED_FINDING_FIELDS - set(finding)
        if missing:
            errors.append(f"{finding_id}: missing fields {sorted(missing)}")
        paths = finding.get("paths")
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            errors.append(f"{finding_id}: paths must be a list of strings")
            continue
        if finding.get("count") != len(paths):
            errors.append(f"{finding_id}: count must equal len(paths)")
        if finding.get("current_status") not in {"observed", "not_observed", "needs_review"}:
            errors.append(f"{finding_id}: invalid current_status")
        if "sunset" in finding and not isinstance(finding["sunset"], Mapping):
            errors.append(f"{finding_id}: sunset must be an object when present")
    return errors


def dump_json(inventory: Mapping[str, Any]) -> str:
    return json.dumps(inventory, indent=2, sort_keys=True) + "\n"


def write_phase0_4_baselines(
    inventory: Mapping[str, Any],
    baseline_dir: Path = DEFAULT_BASELINE_DIR,
) -> None:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    snapshots = {
        "name_collisions.json": inventory["name_collisions"],
        "cross_cutting_concerns.json": inventory["cross_cutting_concerns"],
        "scientist_parallel_implementations.json": inventory[
            "scientist_parallel_implementations"
        ],
    }
    for filename, payload in snapshots.items():
        (baseline_dir / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def check_artifacts(repo_root: Path = REPO_ROOT, baseline_path: Path = DEFAULT_INVENTORY) -> list[str]:
    baseline_path = baseline_path if baseline_path.is_absolute() else repo_root / baseline_path
    current = dump_json(collect_inventory(repo_root))
    if not baseline_path.exists():
        return [f"missing baseline: {_rel(baseline_path, repo_root)}"]
    expected = baseline_path.read_text(encoding="utf-8")
    if current != expected:
        return [f"baseline drift: {_rel(baseline_path, repo_root)}"]
    return []


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--include-local-ignored-residue",
        action="store_true",
        help=(
            "Include ignored local residue in LM-009. The committed baseline omits "
            "this local-only state so clean checkouts remain stable."
        ),
    )
    parser.add_argument(
        "--write-phase0-4-baselines",
        action="store_true",
        help="Refresh committed Phase 0.4 section baseline JSON files.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the committed baseline drifts")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    inventory = collect_inventory(
        repo_root,
        include_local_ignored_residue=args.include_local_ignored_residue,
    )
    errors = validate_inventory(inventory)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    payload = dump_json(inventory)
    if args.write_phase0_4_baselines:
        write_phase0_4_baselines(inventory, repo_root / DEFAULT_BASELINE_DIR)
        print(
            "Wrote Phase 0.4 last-mile baseline JSON files: "
            f"{_rel(repo_root / DEFAULT_BASELINE_DIR, repo_root)}"
        )
    if args.json_output:
        output = args.json_output if args.json_output.is_absolute() else repo_root / args.json_output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        print(f"Wrote last-mile inventory JSON: {_rel(output, repo_root)}")
    else:
        print(payload, end="")
    if args.check:
        drift = check_artifacts(repo_root)
        if drift:
            for error in drift:
                print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
