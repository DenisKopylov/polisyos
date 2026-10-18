"""Owner for Phase 0 repository inventory collection."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InventoryDependencies:
    """Typed facade-provided helpers and policy constants for one inventory call."""

    git_root: Callable[[Path], Path]
    top_level_packages: Callable[[Path, set[Path] | None], list[Path]]
    walk_dirs: Callable[[Path, set[Path] | None], list[Path]]
    included: Callable[[Path, set[Path] | None], bool]
    meaningful_entries: Callable[[Path, set[Path] | None], list[str]]
    rel: Callable[[Path, Path], str]
    is_ignored: Callable[[Path, Path], bool]
    line_count: Callable[[Path, set[Path] | None], int]
    read_input: Callable[[Path, set[Path] | None], str]
    child_dirs: Callable[[Path, set[Path] | None], list[Path]]
    default_allowed_root_py: tuple[str, ...]
    cache_or_env_names: tuple[str, ...]
    product_build_output_names: tuple[str, ...]
    frontend_build_output_names: tuple[str, ...]
    ignored_dir_names: frozenset[str]
    lockfile_names: tuple[str, ...]


def collect_inventory(
    repo_root: Path,
    *,
    tracked_paths: set[Path] | None = None,
    dependencies: InventoryDependencies,
) -> dict[str, Any]:
    """Collect the Phase 0 inventory using the facade current at call time."""
    repo_root = repo_root.resolve()
    git_root = dependencies.git_root(repo_root)
    workspace_root = repo_root.parent
    src_root = repo_root / "src" / "polisyos"
    top_packages = dependencies.top_level_packages(src_root, tracked_paths)

    empty_packages: list[dict[str, Any]] = []
    for directory in dependencies.walk_dirs(src_root, tracked_paths):
        init_file = directory / "__init__.py"
        if (
            init_file.exists()
            and dependencies.included(init_file, tracked_paths)
            and dependencies.meaningful_entries(directory, tracked_paths) == ["__init__.py"]
        ):
            empty_packages.append(
                {
                    "path": dependencies.rel(directory, repo_root),
                    "package": directory.name,
                }
            )

    foundry_methods = src_root / "foundry" / "methods"
    foundry_catalog = foundry_methods / "catalog"
    foundry_method_placeholders: list[dict[str, Any]] = []
    if foundry_methods.exists() and foundry_catalog.exists():
        for child in sorted(foundry_methods.iterdir()):
            if (
                not child.is_dir()
                or child.name in dependencies.ignored_dir_names
                or child.name == "catalog"
                or not dependencies.included(child, tracked_paths)
            ):
                continue
            catalog_peer = foundry_catalog / child.name
            if (child / "__init__.py").exists() and dependencies.meaningful_entries(
                child, tracked_paths
            ) == ["__init__.py"]:
                foundry_method_placeholders.append(
                    {
                        "name": child.name,
                        "path": dependencies.rel(child, repo_root),
                        "catalog_peer": dependencies.rel(catalog_peer, repo_root)
                        if catalog_peer.exists()
                        else None,
                        "catalog_peer_exists": catalog_peer.exists()
                        and dependencies.included(catalog_peer, tracked_paths),
                    }
                )

    loose_root_modules: list[dict[str, Any]] = []
    package_file_counts: list[dict[str, Any]] = []
    for package_dir in top_packages:
        direct_py = sorted(
            path for path in package_dir.glob("*.py") if dependencies.included(path, tracked_paths)
        )
        loose_root_modules.append(
            {
                "package": package_dir.name,
                "root_py_count": len(direct_py),
                "non_facade_root_py_count": len(
                    [
                        path
                        for path in direct_py
                        if path.name not in dependencies.default_allowed_root_py
                    ]
                ),
                "modules": [
                    {
                        "path": dependencies.rel(path, repo_root),
                        "lines": dependencies.line_count(path, tracked_paths),
                        "facade_allowed": path.name in dependencies.default_allowed_root_py,
                    }
                    for path in direct_py
                ],
            }
        )
        top_level_entries = dependencies.meaningful_entries(package_dir, tracked_paths)
        package_file_counts.append(
            {
                "package": package_dir.name,
                "top_level_entry_count": len(top_level_entries),
                "top_level_entries": top_level_entries,
                "file_count": sum(
                    1
                    for path in package_dir.rglob("*")
                    if path.is_file()
                    and not any(part in dependencies.ignored_dir_names for part in path.parts)
                    and dependencies.included(path, tracked_paths)
                ),
                "python_file_count": sum(
                    1
                    for path in package_dir.rglob("*.py")
                    if path.is_file()
                    and not any(part in dependencies.ignored_dir_names for part in path.parts)
                    and dependencies.included(path, tracked_paths)
                ),
            }
        )

    directory_names: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for package_dir in top_packages:
        directory_names[package_dir.name][package_dir.name].append(
            dependencies.rel(package_dir, repo_root)
        )
        for directory in dependencies.walk_dirs(package_dir, tracked_paths):
            if directory == package_dir:
                continue
            directory_names[directory.name][package_dir.name].append(
                dependencies.rel(directory, repo_root)
            )
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
    for name in dependencies.cache_or_env_names:
        for root_label, root in (("workspace_root", workspace_root), ("product_root", repo_root)):
            path = root / name
            if path.exists() and dependencies.included(path, tracked_paths):
                cache_and_env_paths.append(
                    {
                        "name": name,
                        "scope": root_label,
                        "path": dependencies.rel(path, git_root),
                        "ignored": dependencies.is_ignored(git_root, path),
                    }
                )
    duplicated_cache_or_env = [
        {
            "name": name,
            "paths": [entry for entry in cache_and_env_paths if entry["name"] == name],
        }
        for name in dependencies.cache_or_env_names
        if len([entry for entry in cache_and_env_paths if entry["name"] == name]) > 1
    ]

    build_outputs: list[dict[str, Any]] = []
    for name in dependencies.product_build_output_names:
        for root_label, root in (("workspace_root", workspace_root), ("product_root", repo_root)):
            path = root / name
            if path.exists() and dependencies.included(path, tracked_paths):
                build_outputs.append(
                    {
                        "name": name,
                        "scope": root_label,
                        "path": dependencies.rel(path, git_root),
                        "ignored": dependencies.is_ignored(git_root, path),
                    }
                )
    for workspace_root in (repo_root / "apps", repo_root / "packages"):
        for app_dir in sorted(workspace_root.glob("*")) if workspace_root.exists() else []:
            if not app_dir.is_dir() or not dependencies.included(app_dir, tracked_paths):
                continue
            for name in dependencies.frontend_build_output_names:
                path = app_dir / name
                if path.exists() and dependencies.included(path, tracked_paths):
                    build_outputs.append(
                        {
                            "name": name,
                            "scope": "frontend_workspace",
                            "path": dependencies.rel(path, git_root),
                            "ignored": dependencies.is_ignored(git_root, path),
                        }
                    )

    pyproject_path = repo_root / "pyproject.toml"
    pyproject_lines = dependencies.read_input(pyproject_path, tracked_paths).splitlines()
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
            "path": dependencies.rel(path, repo_root),
            "test_file_count": sum(1 for item in path.rglob("test_*.py") if item.is_file()),
            "conftest_count": sum(1 for item in path.rglob("conftest.py") if item.is_file()),
        }
        for path in dependencies.child_dirs(tests_root)
    ]
    unit_packages = sorted(path.name for path in dependencies.child_dirs(tests_root / "unit"))
    integration_packages = sorted(
        path.name for path in dependencies.child_dirs(tests_root / "integration")
    )
    property_packages = sorted(
        path.name for path in dependencies.child_dirs(tests_root / "property")
    )

    lockfiles: list[dict[str, Any]] = []
    for root_text, dirs, files in os.walk(workspace_root):
        dirs[:] = [
            name
            for name in dirs
            if name not in dependencies.ignored_dir_names and not name.startswith(".")
        ]
        root = Path(root_text)
        for name in dependencies.lockfile_names:
            if name in files:
                path = root / name
                lockfiles.append({"name": name, "path": dependencies.rel(path, git_root)})

    runtime_dashboard_src = repo_root / "apps" / "runtime-dashboard" / "src"
    frontend_source_duplicates = [
        {
            "pair": "lib_vs_shared_lib",
            "paths": [
                dependencies.rel(runtime_dashboard_src / "lib", repo_root),
                dependencies.rel(runtime_dashboard_src / "shared" / "lib", repo_root),
            ],
            "both_exist": (runtime_dashboard_src / "lib").exists()
            and (runtime_dashboard_src / "shared" / "lib").exists(),
        },
        {
            "pair": "i18n_vs_shared_i18n",
            "paths": [
                dependencies.rel(runtime_dashboard_src / "i18n", repo_root),
                dependencies.rel(runtime_dashboard_src / "shared" / "i18n", repo_root),
            ],
            "both_exist": (runtime_dashboard_src / "i18n").exists()
            and (runtime_dashboard_src / "shared" / "i18n").exists(),
        },
        {
            "pair": "app_state_vs_app_providers",
            "paths": [
                dependencies.rel(runtime_dashboard_src / "app" / "state", repo_root),
                dependencies.rel(runtime_dashboard_src / "app" / "providers", repo_root),
            ],
            "both_exist": (runtime_dashboard_src / "app" / "state").exists()
            and (runtime_dashboard_src / "app" / "providers").exists(),
        },
    ]

    return {
        "version": 1,
        "phase": "repository_structure_remediation_phase_0",
        "repo_root": dependencies.rel(repo_root, git_root),
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
            "path": dependencies.rel(pyproject_path, repo_root),
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
