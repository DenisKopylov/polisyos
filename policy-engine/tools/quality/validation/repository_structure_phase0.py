#!/usr/bin/env python3
"""Phase 0 repository-structure inventory and fail-closed gates."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    import tomli as tomllib  # type: ignore[no-redef]


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


def _walk_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    if not root.exists():
        return dirs
    for current, names, _files in os.walk(root):
        names[:] = [
            name for name in names if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        ]
        dirs.append(Path(current))
    return dirs


def _child_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        child
        for child in path.iterdir()
        if child.is_dir() and child.name not in IGNORED_DIR_NAMES and not child.name.startswith(".")
    )


def _meaningful_entries(path: Path) -> list[str]:
    entries: list[str] = []
    for child in path.iterdir():
        if child.name in IGNORED_DIR_NAMES or child.name.startswith("."):
            continue
        entries.append(child.name)
    return sorted(entries)


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _top_level_packages(src_root: Path) -> list[Path]:
    if not src_root.exists():
        return []
    return sorted(
        path
        for path in src_root.iterdir()
        if path.is_dir() and path.name not in IGNORED_DIR_NAMES and not path.name.startswith(".")
    )


def collect_inventory(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    git_root = _git_root(repo_root)
    workspace_root = repo_root.parent
    src_root = repo_root / "src" / "polisyos"
    top_packages = _top_level_packages(src_root)

    empty_packages: list[dict[str, Any]] = []
    for directory in _walk_dirs(src_root):
        init_file = directory / "__init__.py"
        if init_file.exists() and _meaningful_entries(directory) == ["__init__.py"]:
            empty_packages.append(
                {
                    "path": _rel(directory, repo_root),
                    "package": directory.name,
                }
            )

    foundry_methods = src_root / "foundry" / "methods"
    foundry_catalog = foundry_methods / "catalog"
    foundry_method_placeholders: list[dict[str, Any]] = []
    if foundry_methods.exists() and foundry_catalog.exists():
        for child in sorted(foundry_methods.iterdir()):
            if not child.is_dir() or child.name in IGNORED_DIR_NAMES or child.name == "catalog":
                continue
            catalog_peer = foundry_catalog / child.name
            if (child / "__init__.py").exists() and _meaningful_entries(child) == ["__init__.py"]:
                foundry_method_placeholders.append(
                    {
                        "name": child.name,
                        "path": _rel(child, repo_root),
                        "catalog_peer": _rel(catalog_peer, repo_root)
                        if catalog_peer.exists()
                        else None,
                        "catalog_peer_exists": catalog_peer.exists(),
                    }
                )

    loose_root_modules: list[dict[str, Any]] = []
    package_file_counts: list[dict[str, Any]] = []
    for package_dir in top_packages:
        direct_py = sorted(package_dir.glob("*.py"))
        loose_root_modules.append(
            {
                "package": package_dir.name,
                "root_py_count": len(direct_py),
                "non_facade_root_py_count": len(
                    [path for path in direct_py if path.name not in DEFAULT_ALLOWED_ROOT_PY]
                ),
                "modules": [
                    {
                        "path": _rel(path, repo_root),
                        "lines": _line_count(path),
                        "facade_allowed": path.name in DEFAULT_ALLOWED_ROOT_PY,
                    }
                    for path in direct_py
                ],
            }
        )
        top_level_entries = _meaningful_entries(package_dir)
        package_file_counts.append(
            {
                "package": package_dir.name,
                "top_level_entry_count": len(top_level_entries),
                "top_level_entries": top_level_entries,
                "file_count": sum(
                    1
                    for path in package_dir.rglob("*")
                    if path.is_file() and not any(part in IGNORED_DIR_NAMES for part in path.parts)
                ),
                "python_file_count": sum(
                    1
                    for path in package_dir.rglob("*.py")
                    if path.is_file() and not any(part in IGNORED_DIR_NAMES for part in path.parts)
                ),
            }
        )

    directory_names: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for package_dir in top_packages:
        directory_names[package_dir.name][package_dir.name].append(_rel(package_dir, repo_root))
        for directory in _walk_dirs(package_dir):
            if directory == package_dir:
                continue
            directory_names[directory.name][package_dir.name].append(_rel(directory, repo_root))
    repeated_directory_names = [
        {
            "name": name,
            "packages": [
                {"package": package, "locations": sorted(locations)}
                for package, locations in sorted(package_map.items())
            ],
        }
        for name, package_map in sorted(directory_names.items())
        if len(package_map) >= 2
    ]

    cache_and_env_paths: list[dict[str, Any]] = []
    for name in CACHE_OR_ENV_NAMES:
        for root_label, root in (("workspace_root", workspace_root), ("product_root", repo_root)):
            path = root / name
            if path.exists():
                cache_and_env_paths.append(
                    {
                        "name": name,
                        "scope": root_label,
                        "path": _rel(path, git_root),
                        "ignored": _is_ignored(git_root, path),
                    }
                )
    duplicated_cache_or_env = [
        {
            "name": name,
            "paths": [entry for entry in cache_and_env_paths if entry["name"] == name],
        }
        for name in CACHE_OR_ENV_NAMES
        if len([entry for entry in cache_and_env_paths if entry["name"] == name]) > 1
    ]

    build_outputs: list[dict[str, Any]] = []
    for name in PRODUCT_BUILD_OUTPUT_NAMES:
        for root_label, root in (("workspace_root", workspace_root), ("product_root", repo_root)):
            path = root / name
            if path.exists():
                build_outputs.append(
                    {
                        "name": name,
                        "scope": root_label,
                        "path": _rel(path, git_root),
                        "ignored": _is_ignored(git_root, path),
                    }
                )
    for workspace_root in (repo_root / "apps", repo_root / "packages"):
        for app_dir in sorted(workspace_root.glob("*")) if workspace_root.exists() else []:
            if not app_dir.is_dir():
                continue
            for name in FRONTEND_BUILD_OUTPUT_NAMES:
                path = app_dir / name
                if path.exists():
                    build_outputs.append(
                        {
                            "name": name,
                            "scope": "frontend_workspace",
                            "path": _rel(path, git_root),
                            "ignored": _is_ignored(git_root, path),
                        }
                    )

    pyproject_path = repo_root / "pyproject.toml"
    pyproject_lines = pyproject_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    section_re = re.compile(r"^\[\[?([^\]\s]+)\]\]?$")
    section_headers: list[dict[str, Any]] = []
    for line_number, line in enumerate(pyproject_lines, start=1):
        match = section_re.match(line.strip())
        if match:
            section_headers.append(
                {
                    "name": match.group(1),
                    "header": line.strip(),
                    "line_start": line_number,
                }
            )
    tool_section_details: list[dict[str, Any]] = []
    for index, header in enumerate(section_headers):
        name = header["name"]
        if not name.startswith("tool."):
            continue
        next_start = (
            section_headers[index + 1]["line_start"]
            if index + 1 < len(section_headers)
            else len(pyproject_lines) + 1
        )
        line_end = next_start - 1
        tool_section_details.append(
            {
                "name": name.removeprefix("tool."),
                "header": header["header"],
                "line_start": header["line_start"],
                "line_end": line_end,
                "line_count": line_end - header["line_start"] + 1,
            }
        )

    tests_root = repo_root / "tests"
    top_test_dirs = [
        {
            "name": path.name,
            "path": _rel(path, repo_root),
            "test_file_count": sum(1 for item in path.rglob("test_*.py") if item.is_file()),
            "conftest_count": sum(1 for item in path.rglob("conftest.py") if item.is_file()),
        }
        for path in _child_dirs(tests_root)
    ]
    unit_packages = sorted(path.name for path in _child_dirs(tests_root / "unit"))
    integration_packages = sorted(path.name for path in _child_dirs(tests_root / "integration"))
    property_packages = sorted(path.name for path in _child_dirs(tests_root / "property"))

    lockfiles: list[dict[str, Any]] = []
    for root_text, dirs, files in os.walk(workspace_root):
        dirs[:] = [
            name for name in dirs if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        ]
        root = Path(root_text)
        for name in LOCKFILE_NAMES:
            if name in files:
                path = root / name
                lockfiles.append({"name": name, "path": _rel(path, git_root)})

    runtime_dashboard_src = repo_root / "apps" / "runtime-dashboard" / "src"
    frontend_source_duplicates = [
        {
            "pair": "lib_vs_shared_lib",
            "paths": [
                _rel(runtime_dashboard_src / "lib", repo_root),
                _rel(runtime_dashboard_src / "shared" / "lib", repo_root),
            ],
            "both_exist": (runtime_dashboard_src / "lib").exists()
            and (runtime_dashboard_src / "shared" / "lib").exists(),
        },
        {
            "pair": "i18n_vs_shared_i18n",
            "paths": [
                _rel(runtime_dashboard_src / "i18n", repo_root),
                _rel(runtime_dashboard_src / "shared" / "i18n", repo_root),
            ],
            "both_exist": (runtime_dashboard_src / "i18n").exists()
            and (runtime_dashboard_src / "shared" / "i18n").exists(),
        },
        {
            "pair": "app_state_vs_app_providers",
            "paths": [
                _rel(runtime_dashboard_src / "app" / "state", repo_root),
                _rel(runtime_dashboard_src / "app" / "providers", repo_root),
            ],
            "both_exist": (runtime_dashboard_src / "app" / "state").exists()
            and (runtime_dashboard_src / "app" / "providers").exists(),
        },
    ]

    return {
        "version": 1,
        "phase": "repository_structure_remediation_phase_0",
        "repo_root": _rel(repo_root, git_root),
        "git_root": ".",
        "empty_init_only_packages": empty_packages,
        "foundry_methods_empty_placeholders": foundry_method_placeholders,
        "loose_root_modules": loose_root_modules,
        "package_file_counts": package_file_counts,
        "repeated_directory_names": repeated_directory_names,
        "cache_and_env_paths": cache_and_env_paths,
        "duplicated_cache_or_env": duplicated_cache_or_env,
        "build_outputs": build_outputs,
        "pyproject": {
            "path": _rel(pyproject_path, repo_root),
            "line_count": len(pyproject_lines),
            "tool_section_count": len(tool_section_details),
            "tool_sections": sorted(entry["name"] for entry in tool_section_details),
            "tool_section_details": tool_section_details,
        },
        "tests": {
            "top_level_dirs": top_test_dirs,
            "unit_packages": unit_packages,
            "integration_packages": integration_packages,
            "property_packages": property_packages,
            "fixture_path_exists": (tests_root / "fixtures").exists(),
        },
        "frontend": {
            "lockfiles": sorted(lockfiles, key=lambda entry: entry["path"]),
            "source_duplicate_candidates": frontend_source_duplicates,
            "build_outputs": [
                entry for entry in build_outputs if entry["scope"] == "frontend_workspace"
            ],
        },
    }


def _load_package_layout(repo_root: Path) -> dict[str, Any]:
    payload = _load_toml(repo_root / "architecture" / "packages" / "layout.toml")
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


def _load_registered_python_shim_sources(repo_root: Path) -> set[str]:
    payload = _load_toml(repo_root / "architecture" / "shims.toml")
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


def _load_name_registry(repo_root: Path) -> dict[str, Any]:
    payload = _load_toml(repo_root / "architecture" / "name_registry.toml")
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


def gate_loose_files(repo_root: Path, inventory: dict[str, Any]) -> list[dict[str, Any]]:
    layout = _load_package_layout(repo_root)
    registered_python_shims = _load_registered_python_shim_sources(repo_root)
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


def gate_name_collision(repo_root: Path, inventory: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = _load_name_registry(repo_root)
    registry: dict[str, set[str]] = decisions["shared_names"]
    rename_backlog: dict[str, set[str]] = decisions["rename_backlog"]
    findings: list[dict[str, Any]] = list(decisions["registry_findings"])
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
    return findings


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
    "empty_namespace": lambda repo_root, inventory: gate_empty_namespace(inventory),
    "loose_files": gate_loose_files,
    "name_collision": gate_name_collision,
    "pyproject_size": lambda repo_root, inventory: gate_pyproject_size(inventory),
    "cache_dir": lambda repo_root, inventory: gate_cache_dir(inventory),
    "build_output": lambda repo_root, inventory: gate_build_output(inventory),
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


def _load_structure_exceptions(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / DEFAULT_EXCEPTION_REGISTRY
    if not path.exists():
        return []
    payload = _load_toml(path)
    return list(payload.get("exception", []))


def _exception_registry_findings(exceptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        try:
            if sunset != "none" and date.fromisoformat(sunset) < today:
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
        if not isinstance(match, dict) or not match:
            findings.append(
                {
                    "gate": "structure_exception_registry",
                    "severity": "error",
                    "message": "Structure remediation exception must provide a non-empty match table.",
                    "id": exception_id,
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


def _apply_structure_exceptions(
    findings: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    registry_findings = _exception_registry_findings(exceptions)
    if registry_findings:
        return [*findings, *registry_findings]
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
    return filtered


def collect_gate_findings(
    repo_root: Path,
    gate: str,
    *,
    package: str | None = None,
    scope: str = "all",
) -> list[dict[str, Any]]:
    gate = GATE_ALIASES.get(gate, gate)
    inventory = collect_inventory(repo_root)
    gates = GATE_FUNCTIONS.keys() if gate == "all" else (gate,)
    findings: list[dict[str, Any]] = []
    for gate_id in gates:
        findings.extend(GATE_FUNCTIONS[gate_id](repo_root, inventory))
    findings = _apply_structure_exceptions(findings, _load_structure_exceptions(repo_root))
    return _filter_gate_findings(findings, package=package, scope=scope)


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
        default="report-only",
    )
    gate.add_argument(
        "--package",
        default=None,
        help="Restrict findings to one top-level package.",
    )
    gate.add_argument(
        "--scope",
        choices=("all", "root", "package-files"),
        default="all",
        help="Restrict loose_files findings to root .py or recursive package-file budget scope.",
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

    findings = collect_gate_findings(
        repo_root,
        args.gate,
        package=args.package,
        scope=args.scope,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "package": args.package,
                    "scope": args.scope,
                    "findings": findings,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"repository-structure {args.gate}: {len(findings)} finding(s) [{args.mode}]")
        for finding in findings:
            print(f"- {finding['gate']}: {finding['message']}")
    if args.mode == "fail-closed" and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
