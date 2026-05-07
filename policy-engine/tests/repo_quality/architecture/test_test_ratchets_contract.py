from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
RATCHETS = REPO_ROOT / "architecture" / "test_ratchets.toml"
TOPOLOGY = REPO_ROOT / "architecture" / "test_topology.toml"
BASELINE = (
    REPO_ROOT
    / "architecture"
    / "baselines"
    / "repository_best_in_class_phase0_4"
    / "verification_inventory.json"
)
REPORTER = REPO_ROOT / "tools" / "quality" / "testing" / "report_test_ratchets.py"


def _load_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_reporter() -> ModuleType:
    spec = importlib.util.spec_from_file_location("report_test_ratchets", REPORTER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase_6_2_ratchets_match_topology_and_measured_baseline() -> None:
    ratchets = _load_toml(RATCHETS)
    topology = _load_toml(TOPOLOGY)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    package_ratchets = {package["name"]: package for package in ratchets["package_ratchet"]}
    topology_packages = {package["name"]: package for package in topology["package"]}
    baseline_packages = {
        package["package"]: package
        for package in baseline["mirror_ratios"]["packages"]
        if package["package"] in topology_packages
    }

    assert ratchets["test_ratchets"]["status"] == "active"
    assert ratchets["test_ratchets"]["phase"] == "repository-best-in-class-phase-6.2"
    assert ratchets["test_ratchets"]["default_gate_mode"] == "fail_closed_no_regression"
    assert topology["test_topology"]["ratchets_contract"] == "architecture/test_ratchets.toml"
    assert topology["test_topology"]["ratchets_status"] == "fail_closed_no_regression"
    assert set(package_ratchets) == set(topology_packages)
    assert set(package_ratchets) == set(baseline_packages)

    for name, package in package_ratchets.items():
        measured = baseline_packages[name]
        assert package["ratchet_mode"] == "fail_closed_no_regression"
        assert package["ratchet_floor"] >= measured["loose_name_mirror_ratio"]
        assert package["loose_mirror_ratio_baseline"] == measured["loose_name_mirror_ratio"]
        assert package["strict_mirror_ratio_baseline"] == measured["strict_module_mirror_ratio"]

        if package["critical"]:
            assert package["package_mode"] == "critical_target"
            assert package["first_target_ratio"] == 0.7000
        else:
            assert package["package_mode"] == "explicit_exception"
            assert package["exception_reason"]

    for name in ("data_forge", "fabric", "lex"):
        assert package_ratchets[name]["ratchet_floor"] > baseline_packages[name][
            "loose_name_mirror_ratio"
        ]
        assert package_ratchets[name]["phase_5_3_floor_source"]


def test_phase_6_2_property_and_integration_decisions_stay_consistent() -> None:
    ratchets = _load_toml(RATCHETS)
    topology = _load_toml(TOPOLOGY)

    package_ratchets = {package["name"]: package for package in ratchets["package_ratchet"]}
    topology_packages = {package["name"]: package for package in topology["package"]}

    for name, package in package_ratchets.items():
        topology_package = topology_packages[name]
        integration = topology_package["integration"]
        property_contract = topology_package["property"]

        expected_integration = "required" if integration["required"] else "not_required"
        assert package["integration_decision"] == expected_integration
        if integration["required"]:
            assert package["integration_path"] == integration["path"]
        else:
            assert package["integration_reason"] == integration["reason"]

        expected_property = "required" if property_contract["required"] else "not_required"
        assert package["property_decision"] == expected_property
        if property_contract["required"]:
            assert package["property_path"] == property_contract["path"]
        else:
            assert package["property_reason"] == property_contract["reason"]

    for name in ("data_forge", "fabric", "lex"):
        assert package_ratchets[name]["property_decision"] == "required"
        assert package_ratchets[name]["property_path"] == f"tests/property/{name}"
        assert package_ratchets[name]["property_test_file_count_floor"] == 1


def test_phase_6_2_pytest_benchmark_and_fixture_contracts_are_explicit() -> None:
    ratchets = _load_toml(RATCHETS)

    assert "new_package_move_policy" in ratchets["ratchet_policy"]
    assert ratchets["pytest_policy"]["root_config"] == "pytest.ini"
    assert ratchets["pytest_policy"]["pytest_roots"] == ["tests"]
    assert "pyproject.toml:[tool.pytest.ini_options]" in ratchets["pytest_policy"][
        "forbidden_config_roots"
    ]

    exceptions = {exception["id"]: exception for exception in ratchets["pytest_universe_exception"]}
    assert exceptions["benchmarks-conftest-transition"]["path"] == "benchmarks/conftest.py"

    benchmark_policy = ratchets["benchmark_policy"]
    assert benchmark_policy["decision"] == "public_product_evaluation"
    assert benchmark_policy["status"] == "active_contract"
    assert benchmark_policy["target_runner_root"] == "src/polisyos/benchmarks"
    assert benchmark_policy["target_suite_root"] == "benchmarks/suites"
    assert benchmark_policy["target_data_root"] == "benchmarks/_data"
    assert benchmark_policy["internal_performance_root"] == "tests/performance"

    fixture_policy = ratchets["fixture_policy"]
    assert fixture_policy["shared_fixture_root"] == "tests/_data"
    assert fixture_policy["shared_golden_root"] == "tests/_golden"
    assert fixture_policy["shared_helper_root"] == "tests/_helpers"
    assert fixture_policy["benchmark_data_root"] == "benchmarks/_data"

    normalizations = {
        normalization["id"]: normalization for normalization in ratchets["coverage_normalization"]
    }
    assert normalizations["runtime-http-cross-module-behavior"]["package"] == "runtime"
    assert normalizations["runtime-http-cross-module-behavior"]["test_path"] == (
        "tests/unit/runtime/http"
    )
    assert normalizations["data-forge-domain-flow-characterization"]["package"] == "data_forge"
    assert normalizations["fabric-connector-and-data-plane-characterization"]["package"] == (
        "fabric"
    )
    assert normalizations["lex-legal-batch-cross-package-characterization"]["package"] == "lex"


def test_phase_6_2_reporter_renders_package_mirror_and_property_summary() -> None:
    reporter = _load_reporter()

    payload = reporter._build_payload(RATCHETS)
    markdown = reporter._render_markdown(payload)
    package_contracts = {
        package["name"]: package for package in _load_toml(RATCHETS)["package_ratchet"]
    }

    assert payload["ratchet_mode"] == "active"
    assert payload["summary"]["packages"] == len(_load_toml(RATCHETS)["package_ratchet"])
    assert payload["summary"]["floor_regressions"] == 0
    assert payload["summary"]["strict_mirror_regressions"] == 0
    assert payload["summary"]["property_regressions"] == 0
    assert payload["summary"]["property_file_delta_total"] >= 3

    for package in payload["packages"]:
        if package["mirror_status"] == "floor_regression_exception":
            assert package_contracts[package["package"]]["mirror_regression_exception"] is True
        else:
            assert package["mirror_status"] != "floor_regression"
        if package["strict_mirror_status"] == "strict_regression_exception":
            contract = package_contracts[package["package"]]
            assert (
                contract.get("mirror_regression_exception") is True
                or contract.get("strict_mirror_regression_exception") is True
            )
        else:
            assert package["strict_mirror_status"] != "strict_regression"

    for name in ("data_forge", "fabric", "lex"):
        package = next(row for row in payload["packages"] if row["package"] == name)
        assert package["property_status"] == "required_present"
        assert package["property_test_file_count_delta"] >= 1

    assert "`scientist`" in markdown
    assert "Property-required packages" in markdown
    assert "Gate note" in markdown
