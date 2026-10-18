#!/usr/bin/env python3
"""Phase 0 repository-structure inventory and fail-closed gates."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    import tomli as tomllib  # type: ignore[no-redef]

if __package__:
    _inventory_owner = import_module(f"{__package__}.repository_structure_phase0_inventory")
else:
    try:
        _inventory_owner = import_module(
            "tools.quality.validation.repository_structure_phase0_inventory"
        )
    except ModuleNotFoundError as exc:
        if exc.name not in {"tools", "tools.quality", "tools.quality.validation"}:
            raise
        _inventory_owner = import_module("repository_structure_phase0_inventory")


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
    "_build",
    "_cache",
    "__pycache__",
    "node_modules",
    ".next",
    ".turbo",
}

LEGACY_CACHE_OR_ENV_NAMES = (
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".benchmarks",
    ".cache",
    ".basedpyright",
    ".uv-cache",
    ".polisyos-tools",
)

CACHE_OR_ENV_NAMES = (
    *LEGACY_CACHE_OR_ENV_NAMES,
    "_cache",
    ".venv",
    ".polisyos",
)

PRODUCT_BUILD_OUTPUT_NAMES = (
    "_build",
    "out",
    "output",
    "dist",
    "site",
    "release",
    "release-fragments",
    "benchmark-results",
    ".tmp",
    "logs",
    "tmp",
)

FRONTEND_BUILD_OUTPUT_NAMES = (
    "coverage",
    "dist",
    "playwright-report",
    "output",
    "storybook-static",
    "test-results",
)

LOCKFILE_NAMES = (
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "bun.lockb",
    "turbo.json",
    "pnpm-workspace.yaml",
)

DEFAULT_ALLOWED_ROOT_PY = ("__init__.py", "api.py", "_api.py")
DEFAULT_MAX_ROOT_PY_FILES = 5
DEFAULT_MAX_TOP_LEVEL_ENTRIES = 250
DEFAULT_MAX_PYPROJECT_LINES = 300
DEFAULT_EXCEPTION_REGISTRY = Path("architecture/exceptions/structure_remediation.toml")
REQUIRED_SHARED_NAME_FIELDS = (
    "name",
    "allowed_in",
    "semantic_axis",
    "disambiguation",
    "owner",
    "target_phase",
    "sunset",
)
REQUIRED_RENAME_BACKLOG_FIELDS = (
    "name",
    "packages",
    "locations",
    "action",
    "owner",
    "target_phase",
    "sunset",
)
REQUIRED_EXCEPTION_FIELDS = ("id", "gate", "owner", "sunset", "reason", "match")


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _git_root(path: Path) -> Path:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return path
    return Path(completed.stdout.strip()).resolve()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_ignored(git_root: Path, path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(git_root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", rel],
        cwd=git_root,
        check=False,
    )
    return result.returncode == 0


def _included(path: Path, tracked_paths: set[Path] | None) -> bool:
    return tracked_paths is None or path.absolute() in tracked_paths


def _tracked_entries(git_root: Path) -> set[Path]:
    """Enumerate tracked files and their directories, refusing incomplete checkouts."""
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=git_root,
        check=True,
        capture_output=True,
    )
    entries: set[Path] = {git_root}
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        path = git_root / os.fsdecode(raw)
        if not path.exists():
            raise OSError(f"Tracked input is unavailable: {path.relative_to(git_root)}")
        entries.add(path)
        entries.update(parent for parent in path.parents if parent.is_relative_to(git_root))
    return entries


def _walk_dirs(root: Path, tracked_paths: set[Path] | None = None) -> list[Path]:
    dirs: list[Path] = []
    if not root.exists():
        return dirs
    for current, names, _files in os.walk(root):
        names[:] = [
            name
            for name in names
            if name not in IGNORED_DIR_NAMES
            and not name.startswith(".")
            and _included(Path(current) / name, tracked_paths)
        ]
        dirs.append(Path(current))
    return dirs


def _child_dirs(path: Path, tracked_paths: set[Path] | None = None) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        child
        for child in path.iterdir()
        if child.is_dir()
        and child.name not in IGNORED_DIR_NAMES
        and not child.name.startswith(".")
        and _included(child, tracked_paths)
    )


def _meaningful_entries(path: Path, tracked_paths: set[Path] | None = None) -> list[str]:
    entries: list[str] = []
    for child in path.iterdir():
        if (
            child.name in IGNORED_DIR_NAMES
            or child.name.startswith(".")
            or not _included(child, tracked_paths)
        ):
            continue
        entries.append(child.name)
    return sorted(entries)


def _read_input(path: Path, tracked_paths: set[Path] | None = None) -> str:
    if not _included(path, tracked_paths):
        raise OSError(f"Required input is not tracked: {path.name}")
    return path.read_text(encoding="utf-8")


def _line_count(path: Path, tracked_paths: set[Path] | None = None) -> int:
    return len(_read_input(path, tracked_paths).splitlines())


def _load_toml(path: Path, tracked_paths: set[Path] | None = None) -> dict[str, Any]:
    if not path.exists() or not _included(path, tracked_paths):
        return {}
    return tomllib.loads(_read_input(path, tracked_paths))


def _top_level_packages(src_root: Path, tracked_paths: set[Path] | None = None) -> list[Path]:
    if not src_root.exists():
        return []
    return sorted(
        path
        for path in src_root.iterdir()
        if path.is_dir()
        and path.name not in IGNORED_DIR_NAMES
        and not path.name.startswith(".")
        and _included(path, tracked_paths)
    )


def collect_inventory(repo_root: Path, *, tracked_paths: set[Path] | None = None) -> dict[str, Any]:
    """Collect the Phase 0 inventory through the current facade bindings."""
    dependencies = _inventory_owner.InventoryDependencies(
        git_root=_git_root,
        top_level_packages=_top_level_packages,
        walk_dirs=_walk_dirs,
        included=_included,
        meaningful_entries=_meaningful_entries,
        rel=_rel,
        is_ignored=_is_ignored,
        line_count=_line_count,
        read_input=_read_input,
        child_dirs=_child_dirs,
        default_allowed_root_py=DEFAULT_ALLOWED_ROOT_PY,
        cache_or_env_names=CACHE_OR_ENV_NAMES,
        product_build_output_names=PRODUCT_BUILD_OUTPUT_NAMES,
        frontend_build_output_names=FRONTEND_BUILD_OUTPUT_NAMES,
        ignored_dir_names=frozenset(IGNORED_DIR_NAMES),
        lockfile_names=LOCKFILE_NAMES,
    )
    return _inventory_owner.collect_inventory(
        repo_root,
        tracked_paths=tracked_paths,
        dependencies=dependencies,
    )


def _load_package_layout(repo_root: Path, tracked_paths: set[Path] | None = None) -> dict[str, Any]:
    payload = _load_toml(repo_root / "architecture" / "packages" / "layout.toml", tracked_paths)
    defaults = payload.get("defaults", {})
    return {
        "max_root_py_files": int(defaults.get("max_root_py_files", DEFAULT_MAX_ROOT_PY_FILES)),
        "max_top_level_entries": int(
            defaults.get(
                "max_top_level_entries",
                defaults.get("max_package_files", DEFAULT_MAX_TOP_LEVEL_ENTRIES),
            )
        ),
        "allowed_root_py_files": tuple(
            defaults.get("allowed_root_py_files", DEFAULT_ALLOWED_ROOT_PY)
        ),
    }


def _load_registered_python_shim_sources(
    repo_root: Path, tracked_paths: set[Path] | None = None
) -> set[str]:
    payload = _load_toml(repo_root / "architecture" / "shims.toml", tracked_paths)
    sources: set[str] = set()
    for shim in payload.get("shim", []):
        source_path = str(shim.get("source_path", "")).strip()
        if shim.get("type") != "python_reexport" or not source_path.endswith(".py"):
            continue
        path = repo_root / source_path
        try:
            relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            relative = source_path
        sources.add(relative)
    return sources


def _missing_fields(entry: dict[str, Any], required_fields: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        value = entry.get(field)
        if value is None or value == "" or value == []:
            missing.append(field)
    return missing


def _package_from_location(location: str) -> str | None:
    prefix = "src/polisyos/"
    if not location.startswith(prefix):
        return None
    remainder = location[len(prefix) :]
    package = remainder.split("/", 1)[0]
    return package or None


@dataclass(frozen=True)
class _GateFindingResult:
    findings: list[dict[str, Any]]
    integrity_findings: list[dict[str, Any]]


def _load_name_registry(repo_root: Path, tracked_paths: set[Path] | None = None) -> dict[str, Any]:
    payload = _load_toml(repo_root / "architecture" / "name_registry.toml", tracked_paths)
    registry: dict[str, set[str]] = {}
    registry_findings: list[dict[str, Any]] = []
    seen_shared_names: set[str] = set()
    for entry in payload.get("shared_name", []):
        name = entry.get("name")
        allowed_in = entry.get("allowed_in", [])
        if isinstance(name, str):
            if name in seen_shared_names:
                registry_findings.append(
                    {
                        "gate": "name_collision_gate",
                        "severity": "error",
                        "message": "Shared name registry entry is duplicated.",
                        "name": name,
                    }
                )
            seen_shared_names.add(name)
            registry[name] = {str(package) for package in allowed_in}
            missing = _missing_fields(entry, REQUIRED_SHARED_NAME_FIELDS)
            if missing:
                registry_findings.append(
                    {
                        "gate": "name_collision_gate",
                        "severity": "error",
                        "message": "Shared name registry entry is missing required Phase 1C metadata.",
                        "name": name,
                        "missing_fields": missing,
                    }
                )

    rename_backlog: dict[str, set[str]] = {}
    for entry in payload.get("rename_backlog", []):
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        packages = {str(package) for package in entry.get("packages", [])}
        for location in entry.get("locations", []):
            if isinstance(location, str):
                package = _package_from_location(location)
                if package is not None:
                    packages.add(package)
        rename_backlog.setdefault(name, set()).update(packages)
        missing = _missing_fields(entry, REQUIRED_RENAME_BACKLOG_FIELDS)
        if missing:
            registry_findings.append(
                {
                    "gate": "name_collision_gate",
                    "severity": "error",
                    "message": "Rename backlog entry is missing required Phase 1C metadata.",
                    "name": name,
                    "missing_fields": missing,
                }
            )

    return {
        "shared_names": registry,
        "rename_backlog": rename_backlog,
        "registry_findings": registry_findings,
    }


def gate_empty_namespace(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "gate": "empty_namespace_gate",
            "severity": "warning",
            "message": "Empty foundry methods namespace shadows populated catalog peer.",
            "path": entry["path"],
            "catalog_peer": entry["catalog_peer"],
        }
        for entry in inventory["foundry_methods_empty_placeholders"]
        if entry["catalog_peer_exists"]
    ]


def gate_loose_files(
    repo_root: Path, inventory: dict[str, Any], tracked_paths: set[Path] | None = None
) -> list[dict[str, Any]]:
    layout = _load_package_layout(repo_root, tracked_paths)
    registered_python_shims = _load_registered_python_shim_sources(repo_root, tracked_paths)
    findings: list[dict[str, Any]] = []
    allowed = set(layout["allowed_root_py_files"])
    for entry in inventory["loose_root_modules"]:
        modules = [
            module for module in entry["modules"] if module["path"] not in registered_python_shims
        ]
        non_allowed = [module for module in modules if Path(module["path"]).name not in allowed]
        if len(modules) > layout["max_root_py_files"]:
            findings.append(
                {
                    "gate": "loose_files_gate",
                    "severity": "warning",
                    "message": "Top-level package has too many root .py files.",
                    "package": entry["package"],
                    "root_py_count": len(modules),
                    "max_root_py_files": layout["max_root_py_files"],
                    "non_allowed": [module["path"] for module in non_allowed],
                }
            )
    counts = {entry["package"]: entry for entry in inventory["package_file_counts"]}
    for package, entry in sorted(counts.items()):
        if entry["top_level_entry_count"] > layout["max_top_level_entries"]:
            findings.append(
                {
                    "gate": "loose_files_gate",
                    "severity": "warning",
                    "message": "Top-level package exceeds top-level entry budget.",
                    "package": package,
                    "top_level_entry_count": entry["top_level_entry_count"],
                    "max_top_level_entries": layout["max_top_level_entries"],
                }
            )
    return findings


def _gate_name_collision_findings(
    repo_root: Path, inventory: dict[str, Any], tracked_paths: set[Path] | None = None
) -> _GateFindingResult:
    decisions = _load_name_registry(repo_root, tracked_paths)
    registry: dict[str, set[str]] = decisions["shared_names"]
    rename_backlog: dict[str, set[str]] = decisions["rename_backlog"]
    findings: list[dict[str, Any]] = []
    for entry in inventory["repeated_directory_names"]:
        name = entry["name"]
        packages = {package_entry["package"] for package_entry in entry["packages"]}
        allowed = registry.get(name)
        backlog_packages = rename_backlog.get(name, set())
        covered = (allowed or set()) | backlog_packages

        if not packages.issubset(covered):
            findings.append(
                {
                    "gate": "name_collision_gate",
                    "severity": "error",
                    "message": (
                        "Repeated directory name is not declared in name_registry.toml "
                        "or covered by a rename backlog item."
                    ),
                    "name": name,
                    "packages": sorted(packages),
                    "allowed_in": sorted(allowed) if allowed is not None else [],
                    "backlog_packages": sorted(backlog_packages),
                    "unresolved_packages": sorted(packages - covered),
                }
            )
    return _GateFindingResult(findings, list(decisions["registry_findings"]))


def gate_name_collision(
    repo_root: Path, inventory: dict[str, Any], tracked_paths: set[Path] | None = None
) -> list[dict[str, Any]]:
    result = _gate_name_collision_findings(repo_root, inventory, tracked_paths)
    return [*result.integrity_findings, *result.findings]


def gate_pyproject_size(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    pyproject = inventory["pyproject"]
    findings: list[dict[str, Any]] = []
    if pyproject["line_count"] > DEFAULT_MAX_PYPROJECT_LINES:
        findings.append(
            {
                "gate": "pyproject_size_gate",
                "severity": "warning",
                "message": "pyproject.toml exceeds target line budget.",
                "line_count": pyproject["line_count"],
                "max_lines": DEFAULT_MAX_PYPROJECT_LINES,
            }
        )
    return findings


def gate_cache_dir(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    findings = [
        {
            "gate": "cache_dir_gate",
            "severity": "warning",
            "message": "Cache/environment state appears at more than one workspace level.",
            "name": entry["name"],
            "paths": entry["paths"],
        }
        for entry in inventory["duplicated_cache_or_env"]
    ]
    findings.extend(
        {
            "gate": "cache_dir_gate",
            "severity": "warning",
            "message": "Legacy cache/tool state is outside canonical _cache/ umbrella.",
            "name": entry["name"],
            "path": entry["path"],
            "ignored": entry["ignored"],
        }
        for entry in inventory["cache_and_env_paths"]
        if entry["name"] in LEGACY_CACHE_OR_ENV_NAMES
    )
    return findings


def gate_build_output(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for entry in inventory["build_outputs"]:
        if entry["path"] not in {"policy-engine/_build", "_build"} and not (
            entry["path"].startswith("policy-engine/_build/") or "/_build/" in entry["path"]
        ):
            findings.append(
                {
                    "gate": "build_output_gate",
                    "severity": "warning",
                    "message": "Generated/build output is outside canonical _build/ umbrella.",
                    "path": entry["path"],
                    "ignored": entry["ignored"],
                }
            )
    return findings


GATE_FUNCTIONS = {
    "empty_namespace": lambda repo_root, inventory, tracked_paths: gate_empty_namespace(inventory),
    "loose_files": gate_loose_files,
    "name_collision": _gate_name_collision_findings,
    "pyproject_size": lambda repo_root, inventory, tracked_paths: gate_pyproject_size(inventory),
    "cache_dir": lambda repo_root, inventory, tracked_paths: gate_cache_dir(inventory),
    "build_output": lambda repo_root, inventory, tracked_paths: gate_build_output(inventory),
}

GATE_ALIASES = {
    **{gate: gate for gate in GATE_FUNCTIONS},
    **{f"{gate}_gate": gate for gate in GATE_FUNCTIONS},
    "all": "all",
}


def _filter_gate_findings(
    findings: list[dict[str, Any]],
    *,
    package: str | None = None,
    scope: str = "all",
) -> list[dict[str, Any]]:
    filtered = findings
    if package is not None:
        filtered = [finding for finding in filtered if finding.get("package") == package]
    if scope == "root":
        filtered = [
            finding
            for finding in filtered
            if "root_py_count" in finding or "non_allowed" in finding
        ]
    elif scope == "package-files":
        filtered = [
            finding
            for finding in filtered
            if "top_level_entry_count" in finding and "max_top_level_entries" in finding
        ]
    return filtered


def _load_structure_exceptions(
    repo_root: Path, tracked_paths: set[Path] | None = None
) -> list[dict[str, Any]]:
    path = repo_root / DEFAULT_EXCEPTION_REGISTRY
    if not path.exists():
        return []
    payload = _load_toml(path, tracked_paths)
    return list(payload.get("exception", []))


def _exception_registry_findings(
    exceptions: list[dict[str, Any]],
    current_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    today = date.today()
    for entry in exceptions:
        exception_id = str(entry.get("id", ""))
        missing = _missing_fields(entry, REQUIRED_EXCEPTION_FIELDS)
        if missing:
            findings.append(
                {
                    "gate": "structure_exception_registry",
                    "severity": "error",
                    "message": "Structure remediation exception is missing required metadata.",
                    "id": exception_id,
                    "missing_fields": missing,
                }
            )
        if exception_id in seen:
            findings.append(
                {
                    "gate": "structure_exception_registry",
                    "severity": "error",
                    "message": "Structure remediation exception id is duplicated.",
                    "id": exception_id,
                }
            )
        seen.add(exception_id)
        sunset = str(entry.get("sunset", ""))
        sunset_valid = True
        active = False
        try:
            active = sunset == "none" or date.fromisoformat(sunset) >= today
            if sunset != "none" and not active:
                findings.append(
                    {
                        "gate": "structure_exception_registry",
                        "severity": "error",
                        "message": "Structure remediation exception is expired.",
                        "id": exception_id,
                        "sunset": sunset,
                    }
                )
        except ValueError:
            sunset_valid = False
            findings.append(
                {
                    "gate": "structure_exception_registry",
                    "severity": "error",
                    "message": "Structure remediation exception sunset must be ISO date or 'none'.",
                    "id": exception_id,
                    "sunset": sunset,
                }
            )
        match = entry.get("match", {})
        match_valid = isinstance(match, dict) and bool(match)
        if not match_valid:
            findings.append(
                {
                    "gate": "structure_exception_registry",
                    "severity": "error",
                    "message": "Structure remediation exception must provide a non-empty match table.",
                    "id": exception_id,
                }
            )
        if not missing and sunset_valid and active and match_valid:
            if not any(_finding_matches_exception(item, entry) for item in current_findings):
                findings.append(
                    {
                        "gate": "structure_exception_registry",
                        "severity": "error",
                        "message": "Structure remediation exception matches no current gate finding.",
                        "id": exception_id,
                        "exception_gate": str(entry["gate"]),
                        "match": match,
                    }
                )
    return findings


def _finding_matches_exception(finding: dict[str, Any], exception: dict[str, Any]) -> bool:
    if finding.get("gate") != exception.get("gate"):
        return False
    match = exception.get("match", {})
    if not isinstance(match, dict) or not match:
        return False
    for key, expected in match.items():
        if str(finding.get(key, "")) != str(expected):
            return False
    return True


def _apply_structure_exceptions_with_integrity(
    findings: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    *,
    current_findings: list[dict[str, Any]] | None = None,
) -> _GateFindingResult:
    integrity_findings = _exception_registry_findings(
        exceptions,
        findings if current_findings is None else current_findings,
    )
    if integrity_findings:
        return _GateFindingResult(findings, integrity_findings)
    active = [
        entry
        for entry in exceptions
        if str(entry.get("sunset", "")) == "none"
        or date.fromisoformat(str(entry["sunset"])) >= date.today()
    ]
    filtered: list[dict[str, Any]] = []
    for finding in findings:
        if any(_finding_matches_exception(finding, exception) for exception in active):
            continue
        filtered.append(finding)
    return _GateFindingResult(filtered, [])


def _apply_structure_exceptions(
    findings: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    *,
    current_findings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    result = _apply_structure_exceptions_with_integrity(
        findings,
        exceptions,
        current_findings=current_findings,
    )
    return [*result.findings, *result.integrity_findings]


def collect_gate_findings(
    repo_root: Path,
    gate: str,
    *,
    package: str | None = None,
    scope: str = "all",
) -> list[dict[str, Any]]:
    findings, _ = _collect_gate_measurement(repo_root, gate, package=package, scope=scope)
    return findings


def _collect_gate_measurement(
    repo_root: Path,
    gate: str,
    *,
    package: str | None = None,
    scope: str = "all",
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    gate = GATE_ALIASES.get(gate, gate)
    findings: list[dict[str, Any]] = []
    integrity_findings: list[dict[str, Any]] = []
    try:
        tracked_paths = _tracked_entries(_git_root(repo_root.resolve()))
        inventory = collect_inventory(repo_root, tracked_paths=tracked_paths)
        current_findings: list[dict[str, Any]] = []
        for gate_id, gate_function in GATE_FUNCTIONS.items():
            gate_result = gate_function(repo_root, inventory, tracked_paths)
            if isinstance(gate_result, _GateFindingResult):
                gate_findings = gate_result.findings
                integrity_findings.extend(gate_result.integrity_findings)
            else:
                gate_findings = gate_result
            current_findings.extend(gate_findings)
            if gate == "all" or gate_id == gate:
                findings.extend(gate_findings)
        exception_result = _apply_structure_exceptions_with_integrity(
            findings,
            _load_structure_exceptions(repo_root, tracked_paths),
            current_findings=current_findings,
        )
        findings = exception_result.findings
        integrity_findings.extend(exception_result.integrity_findings)
    except (OSError, UnicodeError, subprocess.CalledProcessError, tomllib.TOMLDecodeError) as exc:
        findings.append({"gate": "repository_input", "severity": "error", "message": str(exc)})
        return findings, None
    local_findings = _filter_gate_findings(findings, package=package, scope=scope)
    return [*local_findings, *integrity_findings], inventory


def render_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Repository Structure Remediation Phase 0 Inventory",
        "",
        "Generated by `tools/quality/validation/repository_structure_phase0.py`.",
        "",
        "## Summary",
        "",
        f"- Empty `__init__.py`-only packages: {len(inventory['empty_init_only_packages'])}",
        f"- `foundry/methods` empty placeholders: {len(inventory['foundry_methods_empty_placeholders'])}",
        f"- Top-level package roots inventoried: {len(inventory['loose_root_modules'])}",
        f"- Repeated directory names across packages: {len(inventory['repeated_directory_names'])}",
        f"- Duplicate cache/env buckets: {len(inventory['duplicated_cache_or_env'])}",
        f"- Build output directories found: {len(inventory['build_outputs'])}",
        f"- `pyproject.toml` lines: {inventory['pyproject']['line_count']}",
        f"- `[tool.*]` sections: {inventory['pyproject']['tool_section_count']}",
        "",
        "## Empty Namespace Packages",
        "",
    ]
    for entry in inventory["empty_init_only_packages"]:
        lines.append(f"- `{entry['path']}`")

    lines.extend(["", "## Foundry Methods Placeholders", ""])
    for entry in inventory["foundry_methods_empty_placeholders"]:
        peer = entry["catalog_peer"] or "missing"
        lines.append(f"- `{entry['path']}` -> catalog peer `{peer}`")

    lines.extend(["", "## Root Python Modules By Package", ""])
    lines.append(
        "| Package | Root .py | Non-facade .py | Top-level entries | Package files | Python files |"
    )
    lines.append(
        "| ------- | -------- | -------------- | ----------------- | ------------- | ------------ |"
    )
    counts = {entry["package"]: entry for entry in inventory["package_file_counts"]}
    for entry in inventory["loose_root_modules"]:
        count = counts.get(
            entry["package"],
            {"top_level_entry_count": 0, "file_count": 0, "python_file_count": 0},
        )
        lines.append(
            f"| `{entry['package']}` | {entry['root_py_count']} | "
            f"{entry['non_facade_root_py_count']} | {count['top_level_entry_count']} | "
            f"{count['file_count']} | {count['python_file_count']} |"
        )

    lines.extend(["", "### Root Module LoC", ""])
    for entry in inventory["loose_root_modules"]:
        modules = entry["modules"]
        if not modules:
            lines.append(f"- `{entry['package']}`: no root `.py` files")
            continue
        module_details = "; ".join(
            f"`{module['path']}` ({module['lines']} LoC)" for module in modules
        )
        lines.append(f"- `{entry['package']}`: {module_details}")

    lines.extend(["", "## Repeated Directory Names", ""])
    for entry in inventory["repeated_directory_names"]:
        lines.append(f"- `{entry['name']}`")
        for item in entry["packages"]:
            locations = ", ".join(f"`{location}`" for location in item["locations"])
            lines.append(f"  - (`{entry['name']}`, `{item['package']}`): {locations}")

    lines.extend(["", "## Cache / Environment Duplicates", ""])
    for entry in inventory["duplicated_cache_or_env"]:
        paths = ", ".join(f"`{item['path']}`" for item in entry["paths"])
        lines.append(f"- `{entry['name']}`: {paths}")

    lines.extend(["", "## Build Outputs", ""])
    for entry in inventory["build_outputs"]:
        ignored = "ignored" if entry["ignored"] else "not ignored"
        lines.append(f"- `{entry['path']}` ({entry['scope']}, {ignored})")

    lines.extend(["", "## Pyproject Tool Sections", ""])
    lines.append("| Section | Lines | LoC |")
    lines.append("| ------- | ----- | --- |")
    for section in inventory["pyproject"]["tool_section_details"]:
        lines.append(
            f"| `{section['header']}` | {section['line_start']}-{section['line_end']} | "
            f"{section['line_count']} |"
        )

    lines.extend(["", "## Tests Topology", ""])
    for entry in inventory["tests"]["top_level_dirs"]:
        lines.append(
            f"- `{entry['path']}`: {entry['test_file_count']} test files, "
            f"{entry['conftest_count']} conftest files"
        )

    lines.extend(["", "## Frontend Workspace Signals", ""])
    lines.append("Lockfiles/workspace managers:")
    for entry in inventory["frontend"]["lockfiles"]:
        lines.append(f"- `{entry['path']}`")
    lines.append("")
    lines.append("Frontend build-output placement:")
    for entry in inventory["frontend"]["build_outputs"]:
        ignored = "ignored" if entry["ignored"] else "not ignored"
        lines.append(f"- `{entry['path']}` ({ignored})")
    lines.append("")
    lines.append("Source duplicate candidates:")
    for entry in inventory["frontend"]["source_duplicate_candidates"]:
        status = "both exist" if entry["both_exist"] else "not both present"
        paths = ", ".join(f"`{path}`" for path in entry["paths"])
        lines.append(f"- `{entry['pair']}`: {status}; {paths}")

    return "\n".join(lines) + "\n"


def write_baselines(inventory: dict[str, Any], baseline_dir: Path) -> None:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    snapshots = {
        "inventory.json": inventory,
        "empty_init_only_packages.json": inventory["empty_init_only_packages"],
        "foundry_methods_empty_placeholders.json": inventory["foundry_methods_empty_placeholders"],
        "loose_root_modules.json": inventory["loose_root_modules"],
        "repeated_directory_names.json": inventory["repeated_directory_names"],
        "cache_and_env_paths.json": inventory["cache_and_env_paths"],
        "build_outputs.json": inventory["build_outputs"],
        "pyproject_sections.json": inventory["pyproject"],
        "tests_topology.json": inventory["tests"],
        "frontend_workspace_signals.json": inventory["frontend"],
    }
    for name, payload in snapshots.items():
        (baseline_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Path to the policy-engine product root.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Collect Phase 0 inventory.")
    inventory.add_argument("--json-output", type=Path, default=None)
    inventory.add_argument("--markdown-output", type=Path, default=None)
    inventory.add_argument("--baseline-dir", type=Path, default=None)

    gate = subparsers.add_parser("gate", help="Run report-only/fail-closed gates.")
    gate.add_argument(
        "--gate",
        choices=tuple(sorted(GATE_ALIASES.keys())),
        default="all",
    )
    gate.add_argument(
        "--mode",
        choices=("report-only", "fail-closed"),
        default="fail-closed",
    )
    gate.add_argument(
        "--package",
        default=None,
        help="Restrict package-scoped findings; global input and registry refusals remain visible.",
    )
    gate.add_argument(
        "--scope",
        choices=("all", "root", "package-files"),
        default="all",
        help=(
            "Restrict loose_files findings to root .py or recursive package-file budget scope; "
            "global input and registry refusals remain visible."
        ),
    )
    gate.add_argument("--json", action="store_true", help="Emit JSON findings.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    if args.command == "inventory":
        inventory = collect_inventory(repo_root)
        if args.json_output is not None:
            args.json_output.parent.mkdir(parents=True, exist_ok=True)
            args.json_output.write_text(
                json.dumps(inventory, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if args.markdown_output is not None:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(render_markdown(inventory), encoding="utf-8")
        if args.baseline_dir is not None:
            write_baselines(inventory, args.baseline_dir)
        print(json.dumps(inventory, indent=2, sort_keys=True))
        return 0

    findings, inventory = _collect_gate_measurement(
        repo_root,
        args.gate,
        package=args.package,
        scope=args.scope,
    )
    complete = inventory is not None
    status = "UNRUN" if not complete else "FAILED" if findings else "passed"
    measurement: dict[str, Any] = {
        "measures": "Selected structural predicates over tracked repository inputs.",
        "not_measured": "runtime behavior, semantic correctness, or untracked station files",
        "selected_gate": GATE_ALIASES[args.gate],
    }
    if GATE_ALIASES[args.gate] in {"all", "pyproject_size"}:
        measurement["measures"] += " Pyproject physical lines include comments and blank lines."
        measurement["not_measured"] += (
            ", configuration complexity, dependency correctness, resolver cost, or TOML validity"
        )
        measurement["pyproject_physical_lines"] = (
            inventory["pyproject"]["line_count"] if inventory is not None else None
        )
        measurement["pyproject_max_lines"] = DEFAULT_MAX_PYPROJECT_LINES
    if args.json:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "package": args.package,
                    "scope": args.scope,
                    "findings": findings,
                    "status": status,
                    "complete_verdict": complete,
                    "finding_coverage": "complete" if complete else "partial",
                    "measurement": measurement,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        verdict = (
            status if complete else "UNRUN: no complete verdict; findings are partial coverage"
        )
        print(f"repository-structure {args.gate}: {verdict} [{args.mode}]")
        print(f"Measured scope: {measurement['measures']}")
        print(f"Not measured: {measurement['not_measured']}.")
        for finding in findings:
            print(f"- {finding['gate']}: {finding['message']}")
    if not complete:
        return 2
    if args.mode == "fail-closed" and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
