#!/usr/bin/env python3
"""Generate the Repository Best-In-Class Phase 0.4 verification inventory.

The inventory is intentionally read-only with respect to source and test
topology: it measures current mirror ratios, fixture/data layout, property-test
coverage, benchmark topology, and pytest root/conftest layering so later
ratchets can start from observed baselines.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "repository.verification_inventory.v2"
GENERATED_AT = "2026-05-05T00:00:00Z"
LAST_VERIFIED = "2026-05-05"
PHASE = "0.4"
OWNER = "team-quality"

DEFAULT_BASELINE_DIR = (
    REPO_ROOT / "architecture" / "baselines" / "repository_best_in_class_phase0_4"
)
DEFAULT_INVENTORY = DEFAULT_BASELINE_DIR / "verification_inventory.json"
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs"
    / "archive"
    / "reports"
    / "REPOSITORY_BEST_IN_CLASS_PHASE_0_4_VERIFICATION_INVENTORY.md"
)

TRACKED_PACKAGES = (
    "ir",
    "core",
    "fabric",
    "foundry",
    "scientist",
    "runtime",
    "lex",
    "scholar",
    "berl",
    "ddm",
    "data_forge",
    "calibration",
)
DATA_CONTRACT_HEAVY_PACKAGES = ("fabric", "lex", "data_forge", "ir", "runtime")
PRODUCT_BEHAVIOR_ROOTS = (
    "tests/unit",
    "tests/integration",
    "tests/property",
    "tests/performance",
    "tests/e2e",
)
PRODUCT_CONTRACT_ROOTS = ("tests/contract",)
REPOSITORY_QUALITY_ROOTS = (
    "tests/repo_quality/architecture",
    "tests/repo_quality/lint",
    "tests/repo_quality/tools",
)
DATA_LIKE_DIR_NAMES = {
    "_data",
    "_golden",
    "data",
    "fixture",
    "fixtures",
    "golden",
    "goldens",
    "golden_records",
    "samples",
    "testdata",
}
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
TEST_FILE_RE = re.compile(r"(^test_.*|.*_test)\.py$")
BENCHMARK_REPORT_HINTS = (
    "_cache/benchmarks",
    "benchmarks/_reports",
    "benchmarks/reports",
    "benchmark-results",
    "docs/benchmarks",
    "docs/archive/reports",
)
PHASE_0_4_NEW_MEASURED_FILES = frozenset(
    {
        "tests/repo_quality/tools/test_repository_verification_inventory.py",
        "tests/unit/ddm/test_delayed_label_replay.py",
        "tests/unit/ddm/test_full_acceptance.py",
        "tests/unit/ddm/test_readiness_mapping.py",
        "tests/unit/ddm/test_stationary_replay.py",
        "tests/unit/ddm/test_synthetic_drift_delay.py",
    }
)
_ELIGIBLE_FILE_CACHE: dict[Path, set[str] | None] = {}


@dataclass(frozen=True)
class FixtureDefinition:
    name: str
    path: str
    scope: str
    autouse: bool


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--inventory-output", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true", help="Fail if committed artifacts drift")
    parser.add_argument("--update", action="store_true", help="Rewrite inventory and report")
    return parser.parse_args(argv)


def _resolve(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _rel_or_none(path: Path, repo_root: Path) -> str | None:
    return _rel(path, repo_root) if path.exists() else None


def _eligible_repo_files(repo_root: Path) -> set[str] | None:
    repo_root = repo_root.resolve()
    if repo_root in _ELIGIBLE_FILE_CACHE:
        return _ELIGIBLE_FILE_CACHE[repo_root]
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        _ELIGIBLE_FILE_CACHE[repo_root] = None
        return None
    paths = {raw.decode("utf-8") for raw in completed.stdout.split(b"\0") if raw}
    phase_2_4_roots = [
        root
        for root in ("tests/_data", "tests/_golden", "tests/_helpers", "tests/repo_quality")
        if (repo_root / root).exists()
    ]
    if phase_2_4_roots:
        try:
            extra_completed = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", *phase_2_4_roots],
                cwd=repo_root,
                check=True,
                capture_output=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        else:
            paths.update(raw.decode("utf-8") for raw in extra_completed.stdout.split(b"\0") if raw)
    paths.update(path for path in PHASE_0_4_NEW_MEASURED_FILES if (repo_root / path).exists())
    _ELIGIBLE_FILE_CACHE[repo_root] = paths
    return paths


def _is_measured_file(path: Path, repo_root: Path = REPO_ROOT) -> bool:
    eligible = _eligible_repo_files(repo_root)
    if eligible is None:
        return True
    return _rel(path, repo_root) in eligible


def _walk_files(root: Path, *, suffix: str | None = None) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for current, dir_names, file_names in os.walk(root):
        dir_names[:] = [
            name for name in dir_names if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        ]
        for file_name in file_names:
            if suffix is not None and not file_name.endswith(suffix):
                continue
            path = Path(current) / file_name
            if _is_measured_file(path):
                files.append(path)
    return sorted(files)


def _walk_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    dirs: list[Path] = []
    for current, dir_names, _file_names in os.walk(root):
        dir_names[:] = [
            name for name in dir_names if name not in IGNORED_DIR_NAMES and not name.startswith(".")
        ]
        dirs.append(Path(current))
    return sorted(dirs)


def _test_files(root: Path) -> list[Path]:
    return [path for path in _walk_files(root, suffix=".py") if TEST_FILE_RE.match(path.name)]


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


def _json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _source_package_names(repo_root: Path) -> list[str]:
    src_root = repo_root / "src" / "polisyos"
    if not src_root.exists():
        return []
    return sorted(
        path.name
        for path in src_root.iterdir()
        if path.is_dir() and path.name not in IGNORED_DIR_NAMES and (path / "__init__.py").exists()
    )


def _top_package_from_repo_path(path: str) -> str | None:
    parts = Path(path).parts
    try:
        index = parts.index("polisyos")
    except ValueError:
        return None
    if len(parts) <= index + 1:
        return None
    return parts[index + 1]


def _compatibility_shim_inventory(repo_root: Path) -> tuple[list[dict[str, Any]], set[str]]:
    shims = _load_toml(repo_root / "architecture" / "shims.toml").get("shim", [])
    if not isinstance(shims, list):
        return [], set()

    rows: list[dict[str, Any]] = []
    packages: set[str] = set()
    for shim in shims:
        if not isinstance(shim, dict):
            continue
        source_path = str(shim.get("source_path", ""))
        target_path = str(shim.get("target_path", ""))
        source_package = _top_package_from_repo_path(source_path)
        target_package = _top_package_from_repo_path(target_path)
        if source_package is None and target_package is None:
            continue
        if source_package:
            packages.add(source_package)
        if target_package:
            packages.add(target_package)
        rows.append(
            {
                "id": shim.get("id"),
                "type": shim.get("type"),
                "source_path": source_path,
                "target_path": target_path,
                "source_package": source_package,
                "target_package": target_package,
                "owner": shim.get("owner"),
                "sunset_date": shim.get("sunset_date"),
                "issue": shim.get("issue"),
                "adr": shim.get("adr"),
                "reference": shim.get("issue") or shim.get("adr"),
                "has_issue_or_adr_reference": bool(shim.get("issue") or shim.get("adr")),
                "source_exists": (repo_root / source_path).exists(),
                "target_exists": (repo_root / target_path).exists(),
            }
        )
    return sorted(rows, key=lambda row: str(row["id"])), packages


def _package_measurement_order(repo_root: Path, shim_packages: set[str]) -> list[str]:
    source_names = set(_source_package_names(repo_root))
    ordered: list[str] = []
    for name in TRACKED_PACKAGES:
        if name in source_names:
            ordered.append(name)
    extras = sorted((source_names | shim_packages) - set(ordered))
    return ordered + extras


def _source_modules(package_dir: Path) -> list[Path]:
    return [path for path in _walk_files(package_dir, suffix=".py") if path.name != "__init__.py"]


def _strict_mirror_candidates(source_file: Path, package_dir: Path, unit_dir: Path) -> list[Path]:
    relative = source_file.relative_to(package_dir)
    parent = relative.parent
    stem = source_file.stem
    return [
        unit_dir / parent / f"test_{stem}.py",
        unit_dir / parent / f"{stem}_test.py",
    ]


def _mirror_package(repo_root: Path, package: str) -> dict[str, Any]:
    src_dir = repo_root / "src" / "polisyos" / package
    unit_dir = repo_root / "tests" / "unit" / package
    property_dir = repo_root / "tests" / "property" / package
    integration_dir = repo_root / "tests" / "integration" / package

    source_modules = _source_modules(src_dir)
    unit_tests = _test_files(unit_dir)
    unit_test_stems = {path.stem for path in unit_tests}

    strict_mirrored: list[Path] = []
    loose_mirrored: list[Path] = []
    missing_strict: list[str] = []
    for source_file in source_modules:
        has_strict = any(
            candidate.exists()
            for candidate in _strict_mirror_candidates(source_file, src_dir, unit_dir)
        )
        has_loose = (
            f"test_{source_file.stem}" in unit_test_stems
            or f"{source_file.stem}_test" in unit_test_stems
        )
        if has_strict:
            strict_mirrored.append(source_file)
        else:
            missing_strict.append(_rel(source_file, repo_root))
        if has_loose:
            loose_mirrored.append(source_file)

    package_fixture_dirs = [
        path
        for root in (src_dir, unit_dir)
        for path in _walk_dirs(root)
        if path.name in DATA_LIKE_DIR_NAMES
    ]

    return {
        "package": package,
        "source_path": _rel(src_dir, repo_root),
        "unit_path": _rel(unit_dir, repo_root),
        "source_exists": src_dir.exists(),
        "unit_exists": unit_dir.exists(),
        "source_module_count": len(source_modules),
        "unit_test_file_count": len(unit_tests),
        "strict_mirrored_source_count": len(strict_mirrored),
        "loose_name_mirrored_source_count": len(loose_mirrored),
        "strict_module_mirror_ratio": _ratio(len(strict_mirrored), len(source_modules)),
        "loose_name_mirror_ratio": _ratio(len(loose_mirrored), len(source_modules)),
        "unit_test_to_source_ratio": _ratio(len(unit_tests), len(source_modules)),
        "property_path": _rel(property_dir, repo_root),
        "property_exists": property_dir.exists(),
        "property_test_file_count": len(_test_files(property_dir)),
        "integration_path": _rel_or_none(integration_dir, repo_root),
        "integration_test_file_count": len(_test_files(integration_dir)),
        "package_local_data_dir_count": len(package_fixture_dirs),
        "package_local_data_dirs": [_rel(path, repo_root) for path in sorted(package_fixture_dirs)],
        "missing_strict_mirror_sample": missing_strict[:20],
    }


def _fixture_root_summary(path: Path, repo_root: Path) -> dict[str, Any]:
    files = _walk_files(path)
    extension_counts = Counter(file.suffix or "<none>" for file in files)
    return {
        "path": _rel(path, repo_root),
        "exists": path.exists(),
        "file_count": len(files),
        "python_file_count": sum(1 for file in files if file.suffix == ".py"),
        "test_file_count": len([file for file in files if TEST_FILE_RE.match(file.name)]),
        "extension_counts": dict(sorted(extension_counts.items())),
    }


def _inventory_fixtures(repo_root: Path) -> dict[str, Any]:
    roots = {
        "tests/_data": _fixture_root_summary(repo_root / "tests" / "_data", repo_root),
        "tests/_golden": _fixture_root_summary(repo_root / "tests" / "_golden", repo_root),
        "tests/_helpers": _fixture_root_summary(repo_root / "tests" / "_helpers", repo_root),
        "tests/contract": _fixture_root_summary(repo_root / "tests" / "contract", repo_root),
    }

    search_roots = (repo_root / "tests", repo_root / "src" / "polisyos", repo_root / "benchmarks")
    data_dirs = sorted(
        {
            path
            for root in search_roots
            for path in _walk_dirs(root)
            if path.name in DATA_LIKE_DIR_NAMES
        }
    )
    dir_rows: list[dict[str, Any]] = []
    collectable_tests: list[str] = []
    for path in data_dirs:
        summary = _fixture_root_summary(path, repo_root)
        if summary["test_file_count"]:
            collectable_tests.extend(_rel(test, repo_root) for test in _test_files(path))
        dir_rows.append(summary)

    return {
        "roots": roots,
        "data_like_directory_count": len(dir_rows),
        "data_like_directories": dir_rows,
        "pytest_collectable_tests_under_data_like_dirs": sorted(collectable_tests),
    }


def _root_test_summary(root: Path, repo_root: Path, role: str) -> dict[str, Any]:
    return {
        "path": _rel(root, repo_root),
        "role": role,
        "exists": root.exists(),
        "test_file_count": len(_test_files(root)),
        "python_file_count": len(_walk_files(root, suffix=".py")),
        "conftest_count": len(list(root.rglob("conftest.py"))) if root.exists() else 0,
    }


def _inventory_test_roles(repo_root: Path) -> dict[str, Any]:
    role_roots: list[dict[str, Any]] = []
    for path in PRODUCT_BEHAVIOR_ROOTS:
        role_roots.append(_root_test_summary(repo_root / path, repo_root, "product_behavior"))
    for path in PRODUCT_CONTRACT_ROOTS:
        role_roots.append(_root_test_summary(repo_root / path, repo_root, "product_contract"))
    for path in REPOSITORY_QUALITY_ROOTS:
        role_roots.append(_root_test_summary(repo_root / path, repo_root, "repository_quality"))
    return {
        "role_roots": role_roots,
        "classification": {
            "product_behavior": list(PRODUCT_BEHAVIOR_ROOTS),
            "product_contract": list(PRODUCT_CONTRACT_ROOTS),
            "repository_quality": list(REPOSITORY_QUALITY_ROOTS),
        },
    }


def _has_hypothesis_usage(path: Path) -> bool:
    text = _read_text(path)
    return "hypothesis" in text or "@given" in text


def _inventory_property_coverage(
    repo_root: Path, package_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    property_root = repo_root / "tests" / "property"
    property_files = _test_files(property_root)
    hypothesis_files = [
        _rel(path, repo_root)
        for path in _walk_files(repo_root / "tests", suffix=".py")
        if _has_hypothesis_usage(path)
    ]

    by_package: list[dict[str, Any]] = []
    for row in package_rows:
        package = str(row["package"])
        package_property_dir = property_root / package
        files = _test_files(package_property_dir)
        by_package.append(
            {
                "package": package,
                "property_path": _rel(package_property_dir, repo_root),
                "exists": package_property_dir.exists(),
                "property_test_file_count": len(files),
                "hypothesis_file_count": sum(1 for file in files if _has_hypothesis_usage(file)),
                "property_to_source_ratio": _ratio(len(files), int(row["source_module_count"])),
                "data_contract_heavy": package in DATA_CONTRACT_HEAVY_PACKAGES,
            }
        )

    missing_data_contract_heavy = [
        row["package"]
        for row in by_package
        if row["data_contract_heavy"] and row["property_test_file_count"] == 0
    ]
    missing_any_property = [
        row["package"] for row in by_package if row["property_test_file_count"] == 0
    ]
    return {
        "property_root": _rel(property_root, repo_root),
        "total_property_test_files": len(property_files),
        "total_hypothesis_usage_files": len(hypothesis_files),
        "hypothesis_usage_files": hypothesis_files,
        "by_package": by_package,
        "missing_data_contract_heavy_packages": missing_data_contract_heavy,
        "missing_any_property_packages": missing_any_property,
    }


def _registered_pytest_markers(repo_root: Path) -> list[str]:
    parser = configparser.ConfigParser()
    parser.read(repo_root / "pytest.ini")
    if not parser.has_option("pytest", "markers"):
        return []
    markers = []
    for line in parser.get("pytest", "markers").splitlines():
        marker = line.strip().split(":", 1)[0].strip()
        if marker:
            markers.append(marker)
    return markers


def _pytest_ini_options(repo_root: Path) -> dict[str, Any]:
    parser = configparser.ConfigParser()
    parser.read(repo_root / "pytest.ini")
    options: dict[str, Any] = {}
    if not parser.has_section("pytest"):
        return options
    for key in ("addopts", "cache_dir", "testpaths", "asyncio_mode"):
        options[key] = parser.get("pytest", key, fallback="")
    addopts = str(options.get("addopts", ""))
    import_mode_match = re.search(r"--import-mode=([^\s]+)", addopts)
    benchmark_storage_match = re.search(r"--benchmark-storage=([^\s]+)", addopts)
    options["import_mode"] = import_mode_match.group(1) if import_mode_match else None
    options["benchmark_storage"] = (
        benchmark_storage_match.group(1) if benchmark_storage_match else None
    )
    options["markers"] = _registered_pytest_markers(repo_root)
    return options


def _inventory_benchmarks(repo_root: Path) -> dict[str, Any]:
    benchmark_root = repo_root / "benchmarks"
    benchmark_py_files = _walk_files(benchmark_root, suffix=".py")
    performance_root = repo_root / "tests" / "performance"
    performance_tests = _test_files(performance_root)
    all_test_files = _test_files(repo_root / "tests")

    benchmark_importing_tests = []
    benchmark_marker_tests = []
    performance_marker_tests = []
    for test_file in all_test_files:
        text = _read_text(test_file)
        if "import benchmarks" in text or "from benchmarks" in text:
            benchmark_importing_tests.append(_rel(test_file, repo_root))
        if "pytest.mark.benchmark" in text or "@pytest.mark.benchmark" in text:
            benchmark_marker_tests.append(_rel(test_file, repo_root))
        if "pytest.mark.performance" in text or "@pytest.mark.performance" in text:
            performance_marker_tests.append(_rel(test_file, repo_root))

    suite_rows: list[dict[str, Any]] = []
    if benchmark_root.exists():
        for child in sorted(benchmark_root.iterdir()):
            if not child.is_dir() or child.name in IGNORED_DIR_NAMES or child.name.startswith("."):
                continue
            py_files = _walk_files(child, suffix=".py")
            suite_rows.append(
                {
                    "path": _rel(child, repo_root),
                    "py_file_count": len(py_files),
                    "fixture_dir_count": len(
                        [path for path in _walk_dirs(child) if path.name in DATA_LIKE_DIR_NAMES]
                    ),
                    "entrypoint_like_files": [
                        _rel(path, repo_root)
                        for path in py_files
                        if path.name.startswith(("run_", "prepare_")) or "benchmark" in path.name
                    ],
                }
            )

    report_dirs = [
        {"path": hint, "exists": (repo_root / hint).exists()} for hint in BENCHMARK_REPORT_HINTS
    ]
    pytest_options = _pytest_ini_options(repo_root)

    return {
        "benchmark_root": {
            "path": "benchmarks",
            "exists": benchmark_root.exists(),
            "py_file_count": len(benchmark_py_files),
            "test_file_count": len(_test_files(benchmark_root)),
            "init_file_count": len(
                [path for path in benchmark_py_files if path.name == "__init__.py"]
            ),
            "conftest_files": [
                _rel(path, repo_root) for path in _walk_files(benchmark_root, suffix="conftest.py")
            ],
        },
        "suite_directories": suite_rows,
        "performance_tests": {
            "path": "tests/performance",
            "test_file_count": len(performance_tests),
            "files": [_rel(path, repo_root) for path in performance_tests],
        },
        "pytest_configuration": {
            "default_testpaths": pytest_options.get("testpaths", ""),
            "benchmark_storage": pytest_options.get("benchmark_storage"),
            "registered_benchmark_marker": "benchmark" in pytest_options.get("markers", []),
            "registered_performance_marker": "performance" in pytest_options.get("markers", []),
        },
        "benchmark_importing_tests": sorted(benchmark_importing_tests),
        "benchmark_marker_tests": sorted(benchmark_marker_tests),
        "performance_marker_tests": sorted(performance_marker_tests),
        "report_directories": report_dirs,
        "role_decision": (
            "benchmarks/ is source-like and importable, while default pytest collection is tests/; "
            "Phase 1.4 must decide whether runners become product benchmark APIs or move under tests/performance."
        ),
    }


def _fixture_decorator_info(decorator: ast.AST) -> tuple[bool, str, bool]:
    if isinstance(decorator, ast.Name) and decorator.id == "fixture":
        return True, "function", False
    call: ast.Call | None = None
    if isinstance(decorator, ast.Call):
        call = decorator
        candidate = decorator.func
    else:
        candidate = decorator

    is_fixture = False
    if isinstance(candidate, ast.Attribute):
        is_fixture = candidate.attr == "fixture"
    elif isinstance(candidate, ast.Name):
        is_fixture = candidate.id == "fixture"
    if not is_fixture:
        return False, "function", False
    if call is None:
        return True, "function", False

    scope = "function"
    autouse = False
    for keyword in call.keywords:
        if keyword.arg == "scope" and isinstance(keyword.value, ast.Constant):
            scope = str(keyword.value.value)
        if keyword.arg == "autouse" and isinstance(keyword.value, ast.Constant):
            autouse = bool(keyword.value.value)
    return True, scope, autouse


def _fixture_definitions(path: Path, repo_root: Path) -> list[FixtureDefinition]:
    try:
        tree = ast.parse(_read_text(path), filename=str(path))
    except SyntaxError:
        return []
    fixtures: list[FixtureDefinition] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            is_fixture, scope, autouse = _fixture_decorator_info(decorator)
            if is_fixture:
                fixtures.append(
                    FixtureDefinition(
                        name=node.name,
                        path=_rel(path, repo_root),
                        scope=scope,
                        autouse=autouse,
                    )
                )
                break
    return fixtures


def _inventory_pytest(repo_root: Path) -> dict[str, Any]:
    pytest_ini = repo_root / "pytest.ini"
    pyproject = _load_toml(repo_root / "pyproject.toml")
    pytest_options = _pytest_ini_options(repo_root)
    conftest_files = sorted(
        [
            *list((repo_root / "tests").rglob("conftest.py")),
            *list((repo_root / "benchmarks").rglob("conftest.py")),
        ]
    )

    conftest_rows: list[dict[str, Any]] = []
    fixture_rows: list[FixtureDefinition] = []
    for path in conftest_files:
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        fixtures = _fixture_definitions(path, repo_root)
        fixture_rows.extend(fixtures)
        relative = Path(_rel(path, repo_root))
        conftest_rows.append(
            {
                "path": relative.as_posix(),
                "depth": len(relative.parts),
                "fixture_count": len(fixtures),
                "autouse_fixture_count": sum(1 for fixture in fixtures if fixture.autouse),
            }
        )

    fixtures_by_name: dict[str, list[FixtureDefinition]] = defaultdict(list)
    for fixture in fixture_rows:
        fixtures_by_name[fixture.name].append(fixture)

    duplicate_fixtures = []
    for name, definitions in sorted(fixtures_by_name.items()):
        if len(definitions) <= 1:
            continue
        scopes = sorted({definition.scope for definition in definitions})
        duplicate_fixtures.append(
            {
                "fixture": name,
                "definition_count": len(definitions),
                "scopes": scopes,
                "paths": [definition.path for definition in definitions],
                "scope_ambiguity": len(scopes) > 1,
            }
        )

    importable_non_source_roots = []
    for name in ("benchmarks", "tools", "tests", "schemas"):
        root = repo_root / name
        init_files = _walk_files(root, suffix="__init__.py") if root.exists() else []
        importable_non_source_roots.append(
            {
                "path": name,
                "exists": root.exists(),
                "init_file_count": len(init_files),
                "has_conftest": bool(list(root.rglob("conftest.py"))) if root.exists() else False,
            }
        )

    return {
        "config_files": {
            "pytest_ini": pytest_ini.exists(),
            "pyproject_tool_pytest": bool(pyproject.get("tool", {}).get("pytest")),
        },
        "addopts": pytest_options.get("addopts", ""),
        "testpaths": pytest_options.get("testpaths", ""),
        "cache_dir": pytest_options.get("cache_dir", ""),
        "asyncio_mode": pytest_options.get("asyncio_mode", ""),
        "import_mode": pytest_options.get("import_mode"),
        "registered_markers": pytest_options.get("markers", []),
        "conftest_files": conftest_rows,
        "conftest_count": len(conftest_rows),
        "duplicate_fixture_names": duplicate_fixtures,
        "duplicate_fixture_name_count": len(duplicate_fixtures),
        "scope_ambiguous_fixture_names": [
            row["fixture"] for row in duplicate_fixtures if row["scope_ambiguity"]
        ],
        "importable_non_source_roots": importable_non_source_roots,
    }


def _ratchet_starting_points(package_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in package_rows:
        package = str(row["package"])
        rows.append(
            {
                "package": package,
                "mirror_floor": row["strict_module_mirror_ratio"],
                "property_file_floor": row["property_test_file_count"],
                "unit_test_file_floor": row["unit_test_file_count"],
                "note": (
                    "Use current strict mirror ratio as the report-only no-regression floor; "
                    "raise only after Phase 1.4 maps behavioral tests to source modules."
                ),
            }
        )
    return rows


def build_inventory(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    shim_rows, shim_packages = _compatibility_shim_inventory(repo_root)
    package_rows = [
        _mirror_package(repo_root, package)
        for package in _package_measurement_order(repo_root, shim_packages)
    ]

    inventory = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "last_verified": LAST_VERIFIED,
        "phase": PHASE,
        "owner": OWNER,
        "mode": "read_only_inventory",
        "measurement_notes": [
            "`source_module_count` excludes `__init__.py` files",
            "`strict_module_mirror_ratio` requires path-preserving "
            "`tests/unit/<package>/.../test_<module>.py` or `<module>_test.py`",
            "`loose_name_mirror_ratio` accepts same-name tests anywhere under `tests/unit/<package>`",
            "file scans use git-tracked files plus Phase 0.4 files introduced "
            "by this inventory, excluding unrelated local untracked files",
            "no tests, fixtures, benchmarks, or pytest configuration are moved or edited by this inventory",
        ],
        "summary": {},
        "mirror_ratios": {
            "tracked_packages": list(TRACKED_PACKAGES),
            "packages": package_rows,
            "compatibility_shims": shim_rows,
        },
        "fixtures": _inventory_fixtures(repo_root),
        "test_role_inventory": _inventory_test_roles(repo_root),
        "property_coverage": _inventory_property_coverage(repo_root, package_rows),
        "benchmarks": _inventory_benchmarks(repo_root),
        "pytest": _inventory_pytest(repo_root),
        "ratchet_starting_points": _ratchet_starting_points(package_rows),
    }
    inventory["summary"] = _build_summary(inventory)
    return inventory


def _build_summary(inventory: Mapping[str, Any]) -> dict[str, Any]:
    packages = list(inventory["mirror_ratios"]["packages"])
    strict_ratios = [
        row["strict_module_mirror_ratio"]
        for row in packages
        if row["strict_module_mirror_ratio"] is not None
    ]
    property_coverage = inventory["property_coverage"]
    fixtures = inventory["fixtures"]
    benchmarks = inventory["benchmarks"]
    pytest = inventory["pytest"]
    return {
        "package_count": len(packages),
        "tracked_package_count": len(inventory["mirror_ratios"]["tracked_packages"]),
        "source_module_count": sum(int(row["source_module_count"]) for row in packages),
        "unit_test_file_count": sum(int(row["unit_test_file_count"]) for row in packages),
        "strict_mirror_ratio_min": min(strict_ratios) if strict_ratios else None,
        "strict_mirror_ratio_max": max(strict_ratios) if strict_ratios else None,
        "strict_mirror_ratio_weighted": _ratio(
            sum(int(row["strict_mirrored_source_count"]) for row in packages),
            sum(int(row["source_module_count"]) for row in packages),
        ),
        "packages_missing_property_tests": property_coverage["missing_any_property_packages"],
        "data_contract_heavy_packages_missing_property_tests": property_coverage[
            "missing_data_contract_heavy_packages"
        ],
        "data_like_directory_count": fixtures["data_like_directory_count"],
        "pytest_collectable_data_like_tests": len(
            fixtures["pytest_collectable_tests_under_data_like_dirs"]
        ),
        "benchmark_py_file_count": benchmarks["benchmark_root"]["py_file_count"],
        "performance_test_file_count": benchmarks["performance_tests"]["test_file_count"],
        "pytest_conftest_count": pytest["conftest_count"],
        "pytest_duplicate_fixture_name_count": pytest["duplicate_fixture_name_count"],
    }


def dump_json(inventory: Mapping[str, Any]) -> str:
    return _json_dumps(inventory)


def _md_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def _short_list(values: Sequence[str], limit: int = 12) -> str:
    if not values:
        return "-"
    rendered = ", ".join(f"`{value}`" for value in values[:limit])
    if len(values) > limit:
        rendered += f", ... (+{len(values) - limit})"
    return rendered


def render_markdown(inventory: Mapping[str, Any]) -> str:
    summary = inventory["summary"]
    packages = list(inventory["mirror_ratios"]["packages"])
    fixtures = inventory["fixtures"]
    property_coverage = inventory["property_coverage"]
    benchmarks = inventory["benchmarks"]
    pytest = inventory["pytest"]

    lines: list[str] = [
        "# Repository Best-In-Class Phase 0.4 Verification Inventory",
        "",
        "Generated by `tools/quality/validation/repository_verification_inventory.py`.",
        "",
        f"- Schema: `{inventory['schema_version']}`",
        f"- Generated at: `{inventory['generated_at']}`",
        f"- Last verified: `{inventory['last_verified']}`",
        f"- Owner: `{inventory['owner']}`",
        "- Mode: read-only inventory; no tests, fixtures, benchmarks, or pytest configuration are moved.",
        "",
        "## Summary",
        "",
        *(
            _md_table(
                ["Metric", "Baseline"],
                [
                    ("Packages measured", summary["package_count"]),
                    ("Tracked Phase 0.4 packages", summary["tracked_package_count"]),
                    ("Source modules", summary["source_module_count"]),
                    ("Unit test files under package hubs", summary["unit_test_file_count"]),
                    (
                        "Weighted strict mirror ratio",
                        _percent(summary["strict_mirror_ratio_weighted"]),
                    ),
                    (
                        "Data-like directories",
                        summary["data_like_directory_count"],
                    ),
                    (
                        "Pytest-collectable tests under data-like dirs",
                        summary["pytest_collectable_data_like_tests"],
                    ),
                    ("Benchmark Python files", summary["benchmark_py_file_count"]),
                    ("Performance test files", summary["performance_test_file_count"]),
                    ("Conftest files in tests/benchmarks", summary["pytest_conftest_count"]),
                    (
                        "Duplicate fixture names across conftests",
                        summary["pytest_duplicate_fixture_name_count"],
                    ),
                ],
            )
        ),
        "",
        "## Measurement Notes",
        "",
        *[f"- {note}" for note in inventory["measurement_notes"]],
        "",
        "## Mirror-Ratio Baselines",
        "",
        "Strict mirror ratio is path-preserving and excludes `__init__.py`; loose mirror ratio only matches test filename stems under the package unit hub.",
        "",
        *(
            _md_table(
                [
                    "Package",
                    "Source modules",
                    "Unit tests",
                    "Strict mirror",
                    "Loose name mirror",
                    "Property tests",
                    "Package data dirs",
                ],
                [
                    (
                        row["package"],
                        row["source_module_count"],
                        row["unit_test_file_count"],
                        _percent(row["strict_module_mirror_ratio"]),
                        _percent(row["loose_name_mirror_ratio"]),
                        row["property_test_file_count"],
                        row["package_local_data_dir_count"],
                    )
                    for row in packages
                ],
            )
        ),
        "",
        "## Compatibility Shims",
        "",
        *(
            _md_table(
                [
                    "Shim",
                    "Type",
                    "Source package",
                    "Target package",
                    "Owner",
                    "Sunset",
                    "Issue / ADR",
                    "Source exists",
                    "Target exists",
                ],
                [
                    (
                        row["id"],
                        row["type"],
                        row["source_package"] or "-",
                        row["target_package"] or "-",
                        row["owner"] or "-",
                        row["sunset_date"] or "-",
                        row["reference"] or "-",
                        row["source_exists"],
                        row["target_exists"],
                    )
                    for row in inventory["mirror_ratios"]["compatibility_shims"]
                ],
            )
        ),
        "",
        "## Fixture And Data Layout",
        "",
        *(
            _md_table(
                ["Root", "Files", "Python files", "Collectable tests"],
                [
                    (
                        path,
                        root["file_count"],
                        root["python_file_count"],
                        root["test_file_count"],
                    )
                    for path, root in fixtures["roots"].items()
                ],
            )
        ),
        "",
        "Pytest-collectable tests under data-like directories:",
        "",
        _short_list(fixtures["pytest_collectable_tests_under_data_like_dirs"]),
        "",
        "Package-local and benchmark-local data directories are recorded in the JSON inventory under `fixtures.data_like_directories`.",
        "",
        "## Test Role Inventory",
        "",
        *(
            _md_table(
                ["Root", "Role", "Test files", "Python files", "Conftests"],
                [
                    (
                        row["path"],
                        row["role"],
                        row["test_file_count"],
                        row["python_file_count"],
                        row["conftest_count"],
                    )
                    for row in inventory["test_role_inventory"]["role_roots"]
                ],
            )
        ),
        "",
        "## Property Coverage",
        "",
        f"Total property test files: `{property_coverage['total_property_test_files']}`.",
        "",
        f"Hypothesis usage files across `tests/**`: `{property_coverage['total_hypothesis_usage_files']}`.",
        "",
        "Data-contract-heavy packages missing dedicated property tests:",
        "",
        _short_list(property_coverage["missing_data_contract_heavy_packages"]),
        "",
        *(
            _md_table(
                [
                    "Package",
                    "Property tests",
                    "Hypothesis files",
                    "Property/source ratio",
                    "Data-contract-heavy",
                ],
                [
                    (
                        row["package"],
                        row["property_test_file_count"],
                        row["hypothesis_file_count"],
                        _percent(row["property_to_source_ratio"]),
                        row["data_contract_heavy"],
                    )
                    for row in property_coverage["by_package"]
                ],
            )
        ),
        "",
        "## Benchmark Topology",
        "",
        f"`benchmarks/` has `{benchmarks['benchmark_root']['py_file_count']}` Python files, `{benchmarks['benchmark_root']['init_file_count']}` `__init__.py` files, and `{benchmarks['benchmark_root']['test_file_count']}` pytest-collectable test files.",
        "",
        f"`tests/performance` has `{benchmarks['performance_tests']['test_file_count']}` pytest files.",
        "",
        f"Benchmark storage from `pytest.ini`: `{benchmarks['pytest_configuration']['benchmark_storage']}`.",
        "",
        benchmarks["role_decision"],
        "",
        *(
            _md_table(
                ["Suite/root", "Python files", "Fixture dirs", "Entrypoint-like files"],
                [
                    (
                        row["path"],
                        row["py_file_count"],
                        row["fixture_dir_count"],
                        len(row["entrypoint_like_files"]),
                    )
                    for row in benchmarks["suite_directories"]
                ],
            )
        ),
        "",
        "## Pytest Roots And Fixture Scope",
        "",
        f"Default `testpaths`: `{pytest['testpaths'].strip()}`.",
        "",
        f"Import mode: `{pytest['import_mode']}`.",
        "",
        f"Cache dir: `{pytest['cache_dir']}`.",
        "",
        f"Registered markers: {_short_list(pytest['registered_markers'], limit=20)}",
        "",
        *(
            _md_table(
                ["Path", "Fixtures", "Autouse fixtures", "Depth"],
                [
                    (
                        row["path"],
                        row["fixture_count"],
                        row["autouse_fixture_count"],
                        row["depth"],
                    )
                    for row in pytest["conftest_files"]
                ],
            )
        ),
        "",
        "Duplicate fixture names across conftests:",
        "",
        *(
            _md_table(
                ["Fixture", "Definitions", "Scopes", "Paths", "Scope ambiguity"],
                [
                    (
                        f"`{row['fixture']}`",
                        row["definition_count"],
                        ", ".join(f"`{scope}`" for scope in row["scopes"]),
                        "<br>".join(f"`{path}`" for path in row["paths"]),
                        "yes" if row["scope_ambiguity"] else "no",
                    )
                    for row in pytest["duplicate_fixture_names"]
                ],
            )
            if pytest["duplicate_fixture_names"]
            else ["No duplicate fixture names were observed across conftests."]
        ),
        "",
        "Fixture names with cross-conftest scope ambiguity:",
        "",
        (
            _short_list(pytest["scope_ambiguous_fixture_names"], limit=20)
            if pytest["scope_ambiguous_fixture_names"]
            else "None; duplicate fixture names currently share a single fixture scope each."
        ),
        "",
        "## Ratchet Starting Points",
        "",
        "Phase 1.4 ratchets should start from the strict mirror/property floors below and stay report-only until behavioral test mapping is explicit.",
        "",
        *(
            _md_table(
                ["Package", "Mirror floor", "Property file floor", "Unit test file floor"],
                [
                    (
                        row["package"],
                        _percent(row["mirror_floor"]),
                        row["property_file_floor"],
                        row["unit_test_file_floor"],
                    )
                    for row in inventory["ratchet_starting_points"]
                ],
            )
        ),
        "",
    ]
    return "\n".join(lines)


def check_artifacts(
    *,
    repo_root: Path = REPO_ROOT,
    inventory_path: Path = DEFAULT_INVENTORY,
    report_path: Path = DEFAULT_REPORT,
) -> list[str]:
    repo_root = repo_root.resolve()
    inventory_path = _resolve(inventory_path, repo_root)
    report_path = _resolve(report_path, repo_root)
    inventory = build_inventory(repo_root)
    expected_inventory = dump_json(inventory)
    expected_report = render_markdown(inventory)
    errors: list[str] = []
    if (
        not inventory_path.exists()
        or inventory_path.read_text(encoding="utf-8") != expected_inventory
    ):
        errors.append(f"inventory out of date: {_rel(inventory_path, repo_root)}")
    if not report_path.exists() or report_path.read_text(encoding="utf-8") != expected_report:
        errors.append(f"report out of date: {_rel(report_path, repo_root)}")
    return errors


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    inventory_path = _resolve(args.inventory_output, repo_root)
    report_path = _resolve(args.markdown_output, repo_root)

    inventory = build_inventory(repo_root)
    if args.update:
        _write(inventory_path, dump_json(inventory))
        _write(report_path, render_markdown(inventory))

    if args.check:
        errors = check_artifacts(
            repo_root=repo_root,
            inventory_path=inventory_path,
            report_path=report_path,
        )
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1

    if not args.update and not args.check:
        print(dump_json(inventory), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
