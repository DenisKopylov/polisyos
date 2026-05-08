#!/usr/bin/env python3
"""Report package-level mirror and property-test ratchets."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
DEFAULT_CONTRACT = REPO_ROOT / "architecture" / "tests" / "ratchets.toml"
TEST_ROOT = REPO_ROOT / "tests"


@dataclass(frozen=True)
class PackageRatchetReport:
    package: str
    package_mode: str
    source_module_count: int
    source_module_count_baseline: int | None
    strict_mirrored_source_count: int
    loose_name_mirrored_source_count: int
    strict_module_mirror_ratio: float
    loose_name_mirror_ratio: float
    strict_module_mirror_ratio_baseline: float | None
    loose_name_mirror_ratio_baseline: float | None
    strict_module_mirror_ratio_delta: float | None
    loose_name_mirror_ratio_delta: float | None
    ratchet_floor: float
    floor_delta: float
    first_target_ratio: float | None
    target_gap: float | None
    property_decision: str
    property_path: str
    property_test_file_count: int
    property_test_file_count_baseline: int | None
    property_test_file_count_floor: int | None
    property_test_file_count_delta: int | None
    property_status: str
    integration_decision: str
    integration_path: str | None
    mirror_status: str
    strict_mirror_status: str
    status: str


def _load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _iter_source_modules(source_root: Path) -> list[Path]:
    if not source_root.exists():
        return []
    return sorted(
        path
        for path in source_root.rglob("*.py")
        if path.name != "__init__.py" and "__pycache__" not in path.parts
    )


def _iter_unit_test_files(unit_root: Path) -> list[Path]:
    return _iter_test_files(unit_root)


def _iter_test_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    )


def _strict_mirror_candidates(unit_root: Path, relative_source: Path) -> tuple[Path, Path]:
    test_parent = unit_root / relative_source.parent
    stem = relative_source.stem
    return (test_parent / f"test_{stem}.py", test_parent / f"{stem}_test.py")


def _loose_test_names(unit_root: Path) -> set[str]:
    names: set[str] = set()
    for path in _iter_unit_test_files(unit_root):
        file_name = path.name
        if file_name.startswith("test_") and file_name.endswith(".py"):
            names.add(file_name.removeprefix("test_").removesuffix(".py"))
        if file_name.endswith("_test.py"):
            names.add(file_name.removesuffix("_test.py"))
    return names


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _status(
    *,
    package_mode: str,
    loose_ratio: float,
    ratchet_floor: float,
    first_target_ratio: float | None,
    no_regression: bool = True,
    mirror_regression_exception: bool = False,
) -> str:
    if no_regression and loose_ratio < ratchet_floor and mirror_regression_exception:
        return "floor_regression_exception"
    if no_regression and loose_ratio < ratchet_floor:
        return "floor_regression"
    if not no_regression and loose_ratio < ratchet_floor:
        return "floor_exception"
    if package_mode == "explicit_exception":
        return "explicit_exception"
    if first_target_ratio is not None and loose_ratio < first_target_ratio:
        return "below_first_target_tracking"
    return "at_or_above_target"


def _property_status(
    *,
    decision: str,
    file_count: int,
    baseline: int | None,
    floor: int | None,
) -> str:
    if decision == "required" and file_count <= 0:
        return "required_missing"
    if floor is not None and file_count < floor:
        return "property_floor_regression"
    if baseline is not None and file_count < baseline:
        return "property_regression"
    if decision == "required":
        return "required_present"
    if file_count:
        return "optional_present"
    return "not_required"


def _strict_mirror_status(
    *,
    strict_delta: float | None,
    no_regression: bool,
    mirror_regression_exception: bool,
    strict_mirror_regression_exception: bool,
) -> str:
    if strict_delta is None or strict_delta >= 0:
        return "no_regression"
    if not no_regression:
        return "regression_allowed"
    if mirror_regression_exception or strict_mirror_regression_exception:
        return "strict_regression_exception"
    return "strict_regression"


def _package_baseline_from_contract(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_module_count": package.get("source_module_count_baseline"),
        "strict_module_mirror_ratio": package.get("strict_mirror_ratio_baseline"),
        "loose_name_mirror_ratio": package.get("loose_mirror_ratio_baseline"),
        "property_test_file_count": package.get("property_test_file_count_baseline"),
    }


def _baseline_packages(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    baseline_path = _repo_path(str(contract["test_ratchets"].get("baseline_inventory", "")))
    if not baseline_path.exists():
        return {}
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    return {
        str(package["package"]): package
        for package in payload.get("mirror_ratios", {}).get("packages", [])
        if isinstance(package, dict) and "package" in package
    }


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _read_python_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _iter_shared_helper_files(shared_helper_root: Path) -> list[Path]:
    if not shared_helper_root.exists():
        return []
    return sorted(
        path
        for path in shared_helper_root.rglob("*.py")
        if path.name != "__init__.py" and "__pycache__" not in path.parts
    )


def _iter_layer_local_conftests(pattern: str) -> list[Path]:
    conftests: list[Path] = []
    for path in sorted(REPO_ROOT.glob(pattern)):
        if path == TEST_ROOT / "conftest.py" or "__pycache__" in path.parts:
            continue
        try:
            relative = path.relative_to(TEST_ROOT)
        except ValueError:
            continue
        if relative.parts and not relative.parts[0].startswith("_"):
            conftests.append(path)
    return conftests


def _iter_python_test_files() -> list[Path]:
    if not TEST_ROOT.exists():
        return []
    return sorted(
        path
        for path in TEST_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _iter_imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    modules: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                modules.append((node.module, node.lineno))
            if node.module in {"_helpers", "tests._helpers", "tests"}:
                modules.extend(
                    (f"{node.module}.{alias.name}", node.lineno)
                    for alias in node.names
                    if alias.name != "*"
                )
    return modules


def _iter_string_literals(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        values: list[str] = []
        for item in node.elts:
            values.extend(_iter_string_literals(item))
        return values
    return []


def _iter_pytest_plugin_modules(tree: ast.AST) -> list[tuple[str, int]]:
    modules: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "pytest_plugins"
            for target in node.targets
        ):
            continue
        modules.extend((value, node.lineno) for value in _iter_string_literals(node.value))
    return modules


def _helper_module_names(path: Path, shared_helper_root: Path) -> set[str]:
    module_suffix = ".".join(path.relative_to(shared_helper_root).with_suffix("").parts)
    return {f"_helpers.{module_suffix}", f"tests._helpers.{module_suffix}"}


def _find_helper_usages(
    helper_files: list[Path],
    shared_helper_root: Path,
) -> dict[str, list[dict[str, Any]]]:
    usage: dict[str, list[dict[str, Any]]] = {
        _repo_relative(path): [] for path in helper_files
    }
    helper_modules = {
        path: _helper_module_names(path, shared_helper_root) for path in helper_files
    }
    for python_file in _iter_python_test_files():
        tree = _read_python_ast(python_file)
        module_refs = _iter_imported_modules(tree) + _iter_pytest_plugin_modules(tree)
        for helper_file, helper_names in helper_modules.items():
            if python_file == helper_file:
                continue
            for module_name, lineno in module_refs:
                if any(
                    module_name == helper_name or module_name.startswith(f"{helper_name}.")
                    for helper_name in helper_names
                ):
                    usage[_repo_relative(helper_file)].append(
                        {
                            "path": _repo_relative(python_file),
                            "line": lineno,
                            "module": module_name,
                        }
                    )
                    break
    return usage


def _forbidden_import_prefixes(helper_contract: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(path).replace("/", ".")
        for path in helper_contract["shared_helper_forbidden_test_layers"]
    )


def _find_forbidden_reverse_imports(
    helper_files: list[Path],
    helper_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    forbidden_prefixes = _forbidden_import_prefixes(helper_contract)
    findings: list[dict[str, Any]] = []
    for helper_file in helper_files:
        for module_name, lineno in _iter_imported_modules(_read_python_ast(helper_file)):
            if any(
                module_name == prefix or module_name.startswith(f"{prefix}.")
                for prefix in forbidden_prefixes
            ):
                findings.append(
                    {
                        "path": _repo_relative(helper_file),
                        "line": lineno,
                        "module": module_name,
                    }
                )
    return findings


def _fixture_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return _fixture_name_from_decorator(node, decorator)
        if isinstance(target, ast.Name) and target.id == "fixture":
            return _fixture_name_from_decorator(node, decorator)
    return None


def _fixture_name_from_decorator(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    decorator: ast.expr,
) -> str:
    if isinstance(decorator, ast.Call):
        for keyword in decorator.keywords:
            if (
                keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                return keyword.value.value
    return node.name


def _fixture_factory_hash(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    payload = repr(
        (
            ast.dump(node.args, include_attributes=False),
            [ast.dump(decorator, include_attributes=False) for decorator in node.decorator_list],
            ast.dump(node.returns, include_attributes=False) if node.returns is not None else None,
            [ast.dump(statement, include_attributes=False) for statement in node.body],
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _find_duplicated_fixture_factories(conftests: list[Path]) -> list[dict[str, Any]]:
    fixtures_by_hash: dict[str, list[dict[str, Any]]] = {}
    for conftest in conftests:
        tree = _read_python_ast(conftest)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            fixture_name = _fixture_name(node)
            if fixture_name is None:
                continue
            factory_hash = _fixture_factory_hash(node)
            fixtures_by_hash.setdefault(factory_hash, []).append(
                {
                    "fixture": fixture_name,
                    "path": _repo_relative(conftest),
                    "line": node.lineno,
                }
            )

    duplicate_groups: list[dict[str, Any]] = []
    for factory_hash, instances in fixtures_by_hash.items():
        if len(instances) <= 1:
            continue
        fixture_names = sorted({str(instance["fixture"]) for instance in instances})
        duplicate_groups.append(
            {
                "id": f"{fixture_names[0]}:{factory_hash}",
                "factory_hash": factory_hash,
                "fixture": fixture_names[0] if len(fixture_names) == 1 else fixture_names,
                "instances": sorted(instances, key=lambda item: (item["path"], item["line"])),
            }
        )
    return sorted(duplicate_groups, key=lambda item: str(item["id"]))


def _registered_duplicate_fixture_factories(contract: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "id": str(item["id"]),
                "fixture": item["fixture"],
                "paths": sorted(str(path) for path in item["paths"]),
                "owner": str(item["owner"]),
                "reason": str(item["reason"]),
            }
            for item in contract.get("test_helper_duplicate_fixture_factory", [])
        ),
        key=lambda item: item["id"],
    )


def _duplicate_key(item: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    fixture = item["fixture"]
    fixture_key = ",".join(fixture) if isinstance(fixture, list) else str(fixture)
    if "instances" in item:
        paths = tuple(sorted(str(instance["path"]) for instance in item["instances"]))
    else:
        paths = tuple(sorted(str(path) for path in item["paths"]))
    return fixture_key, paths


def _baseline_count_regressions(
    summary: dict[str, int],
    baseline_summary: dict[str, Any],
) -> dict[str, dict[str, int]]:
    regressions: dict[str, dict[str, int]] = {}
    for key, actual in summary.items():
        baseline = baseline_summary.get(key)
        if baseline is not None and actual > int(baseline):
            regressions[key] = {"actual": actual, "baseline": int(baseline)}
    return regressions


def _build_test_helper_topology_report(contract: dict[str, Any]) -> dict[str, Any]:
    helper_contract = contract["test_helper_topology"]
    shared_helper_root = _repo_path(str(helper_contract["shared_helper_root"]))
    helper_files = _iter_shared_helper_files(shared_helper_root)
    conftests = _iter_layer_local_conftests(str(helper_contract["layer_local_conftest_glob"]))
    helper_usages = _find_helper_usages(helper_files, shared_helper_root)
    unused_helpers = [
        {"path": path}
        for path, usages in sorted(helper_usages.items())
        if not usages
    ]
    duplicate_factories = _find_duplicated_fixture_factories(conftests)
    registered_duplicates = _registered_duplicate_fixture_factories(contract)
    duplicate_keys = {_duplicate_key(item) for item in duplicate_factories}
    registered_duplicate_keys = {_duplicate_key(item) for item in registered_duplicates}
    unregistered_duplicates = [
        item
        for item in duplicate_factories
        if _duplicate_key(item) not in registered_duplicate_keys
    ]
    stale_duplicate_registrations = [
        item for item in registered_duplicates if _duplicate_key(item) not in duplicate_keys
    ]
    forbidden_reverse_imports = _find_forbidden_reverse_imports(helper_files, helper_contract)
    summary = {
        "shared_helper_files": len(helper_files),
        "layer_local_conftest_files": len(conftests),
        "duplicated_fixture_factories": len(duplicate_factories),
        "unused_helpers": len(unused_helpers),
        "forbidden_reverse_imports": len(forbidden_reverse_imports),
    }

    baseline_path = _repo_path(str(helper_contract["baseline"]))
    baseline_summary: dict[str, Any] = {}
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_summary = baseline.get("summary", {})
    count_regressions = _baseline_count_regressions(summary, baseline_summary)
    status = "ok"
    if (
        count_regressions
        or forbidden_reverse_imports
        or unregistered_duplicates
        or stale_duplicate_registrations
    ):
        status = "regression"

    return {
        "status": status,
        "contract": str(DEFAULT_CONTRACT.relative_to(REPO_ROOT)),
        "baseline": str(baseline_path.relative_to(REPO_ROOT)),
        "summary": summary,
        "baseline_summary": baseline_summary,
        "count_regressions": count_regressions,
        "shared_helper_files": [_repo_relative(path) for path in helper_files],
        "layer_local_conftest_files": [_repo_relative(path) for path in conftests],
        "unused_helpers": unused_helpers,
        "helper_usages": helper_usages,
        "duplicated_fixture_factories": duplicate_factories,
        "registered_duplicate_fixture_factories": registered_duplicates,
        "unregistered_duplicate_fixture_factories": unregistered_duplicates,
        "stale_duplicate_fixture_registrations": stale_duplicate_registrations,
        "forbidden_reverse_imports": forbidden_reverse_imports,
    }


def _float_delta(value: float, baseline: object) -> float | None:
    if baseline is None:
        return None
    return round(value - float(baseline), 4)


def _int_delta(value: int, baseline: object) -> int | None:
    if baseline is None:
        return None
    return value - int(baseline)


def _build_package_report(
    package: dict[str, Any],
    *,
    baseline: dict[str, Any] | None,
) -> PackageRatchetReport:
    package_name = str(package["name"])
    source_root = _repo_path(str(package["source_path"]))
    unit_root = _repo_path(str(package["unit_path"]))
    property_path = str(package.get("property_path") or f"tests/property/{package_name}")
    property_root = _repo_path(property_path)
    source_modules = _iter_source_modules(source_root)
    loose_names = _loose_test_names(unit_root)
    baseline = baseline or _package_baseline_from_contract(package)

    strict_count = 0
    loose_count = 0
    for source_module in source_modules:
        relative_source = source_module.relative_to(source_root)
        strict_candidates = _strict_mirror_candidates(unit_root, relative_source)
        if any(candidate.exists() for candidate in strict_candidates):
            strict_count += 1
        if relative_source.stem in loose_names:
            loose_count += 1

    source_count = len(source_modules)
    strict_ratio = _ratio(strict_count, source_count)
    loose_ratio = _ratio(loose_count, source_count)
    strict_delta = _float_delta(strict_ratio, baseline.get("strict_module_mirror_ratio"))
    ratchet_floor = float(package["ratchet_floor"])
    first_target_ratio = (
        float(package["first_target_ratio"]) if "first_target_ratio" in package else None
    )
    target_gap = (
        round(first_target_ratio - loose_ratio, 4)
        if first_target_ratio is not None and loose_ratio < first_target_ratio
        else None
    )
    property_file_count = len(_iter_test_files(property_root))
    property_decision = str(package["property_decision"])
    property_baseline = baseline.get("property_test_file_count")
    property_floor = package.get("property_test_file_count_floor")
    property_status = _property_status(
        decision=property_decision,
        file_count=property_file_count,
        baseline=property_baseline,
        floor=int(property_floor) if property_floor is not None else None,
    )
    mirror_status = _status(
        package_mode=str(package["package_mode"]),
        loose_ratio=loose_ratio,
        ratchet_floor=ratchet_floor,
        first_target_ratio=first_target_ratio,
        no_regression=bool(package.get("no_regression", True)),
        mirror_regression_exception=bool(package.get("mirror_regression_exception", False)),
    )
    strict_status = _strict_mirror_status(
        strict_delta=strict_delta,
        no_regression=bool(package.get("no_regression", True)),
        mirror_regression_exception=bool(package.get("mirror_regression_exception", False)),
        strict_mirror_regression_exception=bool(
            package.get("strict_mirror_regression_exception", False)
        ),
    )
    status = (
        mirror_status
        if mirror_status in {"floor_regression", "floor_regression_exception"}
        else strict_status
        if strict_status == "strict_regression"
        else property_status
        if property_status.endswith("_regression")
        or property_status == "required_missing"
        else mirror_status
    )

    return PackageRatchetReport(
        package=package_name,
        package_mode=str(package["package_mode"]),
        source_module_count=source_count,
        source_module_count_baseline=(
            int(baseline["source_module_count"])
            if baseline.get("source_module_count") is not None
            else None
        ),
        strict_mirrored_source_count=strict_count,
        loose_name_mirrored_source_count=loose_count,
        strict_module_mirror_ratio=strict_ratio,
        loose_name_mirror_ratio=loose_ratio,
        strict_module_mirror_ratio_baseline=(
            float(baseline["strict_module_mirror_ratio"])
            if baseline.get("strict_module_mirror_ratio") is not None
            else None
        ),
        loose_name_mirror_ratio_baseline=(
            float(baseline["loose_name_mirror_ratio"])
            if baseline.get("loose_name_mirror_ratio") is not None
            else None
        ),
        strict_module_mirror_ratio_delta=strict_delta,
        loose_name_mirror_ratio_delta=_float_delta(
            loose_ratio,
            baseline.get("loose_name_mirror_ratio"),
        ),
        ratchet_floor=ratchet_floor,
        floor_delta=round(loose_ratio - ratchet_floor, 4),
        first_target_ratio=first_target_ratio,
        target_gap=target_gap,
        property_decision=property_decision,
        property_path=property_path,
        property_test_file_count=property_file_count,
        property_test_file_count_baseline=(
            int(property_baseline) if property_baseline is not None else None
        ),
        property_test_file_count_floor=(
            int(property_floor) if property_floor is not None else None
        ),
        property_test_file_count_delta=_int_delta(property_file_count, property_baseline),
        property_status=property_status,
        integration_decision=str(package["integration_decision"]),
        integration_path=(
            str(package["integration_path"])
            if package.get("integration_path") is not None
            else None
        ),
        mirror_status=mirror_status,
        strict_mirror_status=strict_status,
        status=status,
    )


def _build_payload(contract_path: Path) -> dict[str, Any]:
    contract = _load_toml(contract_path)
    baselines = _baseline_packages(contract)
    helper_topology_report = (
        _build_test_helper_topology_report(contract)
        if "test_helper_topology" in contract
        else None
    )
    reports = [
        _build_package_report(package, baseline=baselines.get(str(package["name"])))
        for package in sorted(contract.get("package_ratchet", []), key=lambda item: item["name"])
    ]
    regressions = [report for report in reports if report.mirror_status == "floor_regression"]
    regression_exceptions = [
        report for report in reports if report.mirror_status == "floor_regression_exception"
    ]
    strict_regressions = [
        report for report in reports if report.strict_mirror_status == "strict_regression"
    ]
    strict_regression_exceptions = [
        report for report in reports if report.strict_mirror_status == "strict_regression_exception"
    ]
    property_required = [report for report in reports if report.property_decision == "required"]
    property_regressions = [
        report
        for report in reports
        if report.property_status
        in {
            "required_missing",
            "property_floor_regression",
            "property_regression",
        }
    ]
    below_target = [
        report for report in reports if report.mirror_status == "below_first_target_tracking"
    ]
    exceptions = [report for report in reports if report.status == "explicit_exception"]
    summary: dict[str, Any] = {
        "packages": len(reports),
        "floor_regressions": len(regressions),
        "mirror_floor_regressions": len(regressions),
        "mirror_floor_regression_exceptions": len(regression_exceptions),
        "strict_mirror_regressions": len(strict_regressions),
        "strict_mirror_regression_exceptions": len(strict_regression_exceptions),
        "below_first_target_tracking": len(below_target),
        "explicit_exceptions": len(exceptions),
        "property_required_packages": len(property_required),
        "property_regressions": len(property_regressions),
        "property_file_delta_total": sum(
            report.property_test_file_count_delta or 0 for report in reports
        ),
        "loose_mirror_ratio_delta_total": round(
            sum(report.loose_name_mirror_ratio_delta or 0.0 for report in reports),
            4,
        ),
        "strict_mirror_ratio_delta_total": round(
            sum(report.strict_module_mirror_ratio_delta or 0.0 for report in reports),
            4,
        ),
    }
    if helper_topology_report is not None:
        summary["test_helper_topology_status"] = helper_topology_report["status"]
        summary["test_helper_topology_count_regressions"] = len(
            helper_topology_report["count_regressions"]
        )

    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "contract": str(contract_path.relative_to(REPO_ROOT)),
        "baseline_inventory": contract["test_ratchets"]["baseline_inventory"],
        "ratchet_mode": contract["test_ratchets"]["status"],
        "ratchet_policy": contract["ratchet_policy"],
        "summary": summary,
        "packages": [asdict(report) for report in reports],
    }
    if helper_topology_report is not None:
        payload["test_helper_topology"] = helper_topology_report
    return payload


def _percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.2f}%"


def _percent_delta(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:+.2f}pp"


def _int_delta_text(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:+d}"


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Test Ratchet Mirror Report",
        "",
        f"Generated at `{payload['generated_at']}`.",
        "",
        f"- Contract: `{payload['contract']}`",
        f"- Baseline inventory: `{payload['baseline_inventory']}`",
        f"- Mode: `{payload['ratchet_mode']}`",
        f"- Packages: {summary['packages']}",
        f"- Floor regressions: {summary['floor_regressions']}",
        f"- Floor regression exceptions: {summary['mirror_floor_regression_exceptions']}",
        f"- Strict mirror regressions: {summary['strict_mirror_regressions']}",
        f"- Strict mirror regression exceptions: {summary['strict_mirror_regression_exceptions']}",
        f"- Below first target: {summary['below_first_target_tracking']} (tracked)",
        f"- Explicit exceptions: {summary['explicit_exceptions']}",
        f"- Property-required packages: {summary['property_required_packages']}",
        f"- Property regressions: {summary['property_regressions']}",
        f"- Total property file delta: {summary['property_file_delta_total']:+d}",
        f"- Total loose mirror delta: {summary['loose_mirror_ratio_delta_total'] * 100:+.2f}pp",
        f"- Total strict mirror delta: {summary['strict_mirror_ratio_delta_total'] * 100:+.2f}pp",
    ]
    if "test_helper_topology" in payload:
        helper_topology = payload["test_helper_topology"]
        helper_summary = helper_topology["summary"]
        lines.extend(
            [
                f"- Test helper topology: `{helper_topology['status']}`",
                f"- Shared helper files: {helper_summary['shared_helper_files']}",
                f"- Layer-local conftest files: {helper_summary['layer_local_conftest_files']}",
                f"- Duplicated fixture factories: {helper_summary['duplicated_fixture_factories']}",
                f"- Unused helpers: {helper_summary['unused_helpers']}",
                f"- Forbidden reverse imports: {helper_summary['forbidden_reverse_imports']}",
            ]
        )
    lines.extend(
        [
            "",
            "| package | mode | modules | strict mirror | loose mirror | floor | "
            "property files | target | status |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for package in payload["packages"]:
        lines.append(
            "| "
            f"`{package['package']}` | "
            f"`{package['package_mode']}` | "
            f"{package['source_module_count']} | "
            f"{_percent(package['strict_module_mirror_ratio'])} "
            f"({_percent_delta(package['strict_module_mirror_ratio_delta'])}) | "
            f"{_percent(package['loose_name_mirror_ratio'])} "
            f"({_percent_delta(package['loose_name_mirror_ratio_delta'])}) | "
            f"{_percent(package['ratchet_floor'])} | "
            f"{package['property_test_file_count']} "
            f"({_int_delta_text(package['property_test_file_count_delta'])}) | "
            f"{_percent(package['first_target_ratio'])} | "
            f"`{package['status']}` |"
        )
    lines.extend(
        [
            "",
            "Gate note: this command exits non-zero with `--fail-on-regression` "
            "when mirror or property coverage falls below its committed floor. "
            "First-target gaps remain tracked until each package reaches its target.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Report format.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional output path.")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero when mirror or property coverage falls below its floor.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    contract_path = args.contract if args.contract.is_absolute() else REPO_ROOT / args.contract
    payload = _build_payload(contract_path)

    rendered = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else _render_markdown(payload)
    )
    if args.output is not None:
        output_path = args.output if args.output.is_absolute() else REPO_ROOT / args.output
        atomic_write_text(output_path, rendered)
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")  # noqa: T201

    if args.fail_on_regression and (
        payload["summary"]["floor_regressions"]
        or payload["summary"]["strict_mirror_regressions"]
        or payload["summary"]["property_regressions"]
        or payload["summary"].get("test_helper_topology_status") == "regression"
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
