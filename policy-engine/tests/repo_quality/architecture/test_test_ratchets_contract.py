from __future__ import annotations

import configparser
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_ROOT = REPO_ROOT / "benchmarks"
RATCHETS = REPO_ROOT / "architecture" / "tests" / "ratchets.toml"
TOPOLOGY = REPO_ROOT / "architecture" / "tests" / "topology.toml"
BASELINE = (
    REPO_ROOT
    / "architecture"
    / "baselines"
    / "repository_best_in_class_phase0_4"
    / "verification_inventory.json"
)
REPORTER = REPO_ROOT / "tools" / "quality" / "testing" / "report_test_ratchets.py"
ROOT_PYTEST_CONFIG = REPO_ROOT / "pytest.ini"


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


def _pytest_configs_under_benchmarks(benchmark_root: Path) -> list[Path]:
    """Find active pytest configuration files below a benchmark root."""
    configs: list[Path] = []
    for path in sorted(benchmark_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml"}:
            configs.append(path)
        elif path.name in {"tox.ini", "setup.cfg"}:
            parser = configparser.ConfigParser()
            try:
                parser.read_string(path.read_text(encoding="utf-8"))
            except configparser.Error:
                configs.append(path)
            else:
                section = "pytest" if path.name == "tox.ini" else "tool:pytest"
                if parser.has_section(section):
                    configs.append(path)
        elif path.name == "pyproject.toml":
            try:
                payload = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError:
                configs.append(path)
            else:
                tool = payload.get("tool", {})
                pytest = tool.get("pytest", {}) if isinstance(tool, dict) else {}
                if isinstance(pytest, dict) and (
                    "ini_options" in pytest or any(key != "ini_options" for key in pytest)
                ):
                    configs.append(path)
    return configs


def _benchmark_test_files(benchmark_root: Path) -> list[Path]:
    """Return every pytest-style test module under the benchmark root."""
    return sorted(
        path
        for path in benchmark_root.rglob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    )


def _run_pytest_collection(*, cwd: Path, test_paths: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-vv", *test_paths],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


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
    assert topology["test_topology"]["ratchets_contract"] == "architecture/tests/ratchets.toml"
    assert topology["test_topology"]["ratchets_status"] == "fail_closed_no_regression"
    assert set(package_ratchets) == set(topology_packages)
    assert set(package_ratchets) == set(baseline_packages)

    for name, package in package_ratchets.items():
        measured = baseline_packages[name]
        assert package["ratchet_mode"] == "fail_closed_no_regression"
        measured_loose = measured.get("loose_name_mirror_ratio")
        measured_strict = measured.get("strict_module_mirror_ratio")
        expected_loose = (
            package["loose_mirror_ratio_baseline"] if measured_loose is None else measured_loose
        )
        expected_strict = (
            package["strict_mirror_ratio_baseline"] if measured_strict is None else measured_strict
        )
        assert expected_loose is not None
        assert expected_strict is not None
        assert package["ratchet_floor"] >= expected_loose
        assert package["loose_mirror_ratio_baseline"] == expected_loose
        assert package["strict_mirror_ratio_baseline"] == expected_strict

        if package["critical"]:
            assert package["package_mode"] == "critical_target"
            assert package["first_target_ratio"] == 0.7000
        else:
            assert package["package_mode"] == "explicit_exception"
            assert package["exception_reason"]

    for name in ("data_forge", "fabric", "lex"):
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
    assert (
        "pyproject.toml:[tool.pytest.ini_options]"
        in ratchets["pytest_policy"]["forbidden_config_roots"]
    )

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
    baseline_packages = {
        package["package"]: package
        for package in json.loads(BASELINE.read_text(encoding="utf-8"))["mirror_ratios"]["packages"]
    }

    assert payload["ratchet_mode"] == "active"
    assert payload["summary"]["packages"] == len(_load_toml(RATCHETS)["package_ratchet"])
    assert payload["summary"]["floor_regressions"] == sum(
        package["mirror_status"] == "floor_regression" for package in payload["packages"]
    )
    assert payload["summary"]["strict_mirror_regressions"] == sum(
        package["strict_mirror_status"] == "strict_regression" for package in payload["packages"]
    )
    assert payload["summary"]["property_regressions"] == 0
    assert payload["summary"]["property_file_delta_total"] >= 0

    for package in payload["packages"]:
        if package["mirror_status"] in {"floor_regression_exception", "floor_exception"}:
            assert package["loose_name_mirror_ratio"] < package["ratchet_floor"]
            if package["mirror_status"] == "floor_regression_exception":
                assert package_contracts[package["package"]]["mirror_regression_exception"] is True
        elif package["mirror_status"] == "floor_regression":
            assert package["loose_name_mirror_ratio"] < package["ratchet_floor"]
            assert (
                package_contracts[package["package"]].get("mirror_regression_exception") is not True
            )
        else:
            assert package["loose_name_mirror_ratio"] >= package["ratchet_floor"]
        if package["strict_mirror_status"] == "strict_regression_exception":
            contract = package_contracts[package["package"]]
            assert (
                contract.get("mirror_regression_exception") is True
                or contract.get("strict_mirror_regression_exception") is True
            )
            assert package["strict_module_mirror_ratio_delta"] < 0
        elif package["strict_mirror_status"] in {"strict_regression", "regression_allowed"}:
            assert package["strict_module_mirror_ratio_delta"] < 0
        else:
            assert package["strict_module_mirror_ratio_delta"] >= 0
        measured = baseline_packages[package["package"]]
        for metric in (
            "source_module_count",
            "strict_module_mirror_ratio",
            "loose_name_mirror_ratio",
            "property_test_file_count",
        ):
            expected_basis = (
                "inventory" if measured.get(metric) is not None else "contract_fallback"
            )
            assert package["baseline_basis"][metric] == expected_basis

    for name in ("data_forge", "fabric", "lex"):
        package = next(row for row in payload["packages"] if row["package"] == name)
        assert package["property_status"] == "required_present"
        assert package["property_test_file_count_delta"] >= 0

    assert "`scientist`" in markdown
    assert "Property-required packages" in markdown
    assert "Gate note" in markdown
    assert "strict_module_mirror_ratio=contract_fallback" in markdown


def test_benchmark_collection_uses_root_pytest_config_without_a_local_universe() -> None:
    root_config = configparser.ConfigParser()
    assert root_config.read(ROOT_PYTEST_CONFIG, encoding="utf-8") == [str(ROOT_PYTEST_CONFIG)]
    assert root_config.get("pytest", "testpaths").split() == ["tests"]
    assert "--strict-markers" in root_config.get("pytest", "addopts")
    assert "benchmark:" in root_config.get("pytest", "markers")

    assert _pytest_configs_under_benchmarks(BENCHMARK_ROOT) == []
    test_paths = _benchmark_test_files(BENCHMARK_ROOT)
    assert test_paths
    result = _run_pytest_collection(
        cwd=REPO_ROOT,
        test_paths=[str(path.relative_to(REPO_ROOT)) for path in test_paths],
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert f"rootdir: {REPO_ROOT}" in result.stdout
    assert "configfile: pytest.ini" in result.stdout
    assert "collected 44 items" in result.stdout


def test_benchmark_config_census_recognizes_pytest_supported_config_formats(
    tmp_path: Path,
) -> None:
    benchmark_root = tmp_path / "benchmarks"
    benchmark_root.mkdir()
    configs = {
        "pytest.ini": "[pytest]\naddopts = --strict-markers\n",
        ".pytest.ini": "[pytest]\naddopts = --strict-markers\n",
        "pytest.toml": '[pytest]\naddopts = ["--strict-markers"]\n',
        ".pytest.toml": '[pytest]\naddopts = ["--strict-markers"]\n',
        "pyproject.toml": '[tool.pytest]\naddopts = ["--strict-markers"]\n',
        "tox.ini": "[pytest]\naddopts = --strict-markers\n",
        "setup.cfg": "[tool:pytest]\naddopts = --strict-markers\n",
    }

    for name, contents in configs.items():
        config = benchmark_root / name
        config.write_text(contents, encoding="utf-8")
        assert _pytest_configs_under_benchmarks(benchmark_root) == [config]
        config.unlink()


def test_injected_benchmark_pytest_config_changes_root_and_loses_registered_marker(
    tmp_path: Path,
) -> None:
    benchmark_root = tmp_path / "benchmarks"
    benchmark_root.mkdir()
    assert _pytest_configs_under_benchmarks(benchmark_root) == []
    root_config = tmp_path / "pytest.ini"
    root_config.write_text(
        "[pytest]\n"
        "addopts = --strict-markers\n"
        "testpaths = tests\n"
        "markers =\n"
        "    retained_marker: marker retained by the root pytest universe\n",
        encoding="utf-8",
    )
    probe = benchmark_root / "test_marker_probe.py"
    probe.write_text(
        "import pytest\n\n@pytest.mark.retained_marker\ndef test_marker_probe():\n    pass\n",
        encoding="utf-8",
    )

    baseline = _run_pytest_collection(cwd=tmp_path, test_paths=["benchmarks/test_marker_probe.py"])
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    assert f"rootdir: {tmp_path}" in baseline.stdout
    assert "retained_marker" in root_config.read_text(encoding="utf-8")

    nested_config = benchmark_root / "pytest.ini"
    nested_config.write_text(
        "[pytest]\n"
        "addopts = --strict-markers\n"
        "filterwarnings =\n"
        "    error::pytest.PytestUnknownMarkWarning\n",
        encoding="utf-8",
    )
    assert _pytest_configs_under_benchmarks(benchmark_root) == [nested_config]

    injected = _run_pytest_collection(
        cwd=tmp_path,
        test_paths=["benchmarks/test_marker_probe.py"],
    )
    output = injected.stdout + injected.stderr
    assert injected.returncode != 0, output
    assert f"rootdir: {benchmark_root}" in injected.stdout
    assert "unknown pytest.mark.retained_marker" in output.lower()
    assert "pytestunknownmarkwarning" in output.lower()


def test_active_ratchet_baselines_resolve_field_by_field_for_all_packages() -> None:
    reporter = _load_reporter()
    contract = reporter._load_toml(reporter.DEFAULT_CONTRACT)
    inventory = reporter._baseline_packages(contract)
    packages = contract["package_ratchet"]
    assert set(inventory) >= {package["name"] for package in packages}

    metrics = (
        "source_module_count",
        "strict_module_mirror_ratio",
        "loose_name_mirror_ratio",
        "property_test_file_count",
    )
    source_counts: dict[str, int] = {}
    for package in packages:
        measured = inventory[package["name"]]
        values, basis = reporter._resolve_package_baseline(package, measured)
        for metric in metrics:
            expected_basis = (
                "inventory" if measured.get(metric) is not None else "contract_fallback"
            )
            assert basis[metric] == expected_basis
            if expected_basis == "inventory":
                expected_value = measured[metric]
                if metric.endswith("_ratio"):
                    expected_value = float(expected_value)
                assert values[metric] == expected_value
        source_counts[basis["source_module_count"]] = (
            source_counts.get(basis["source_module_count"], 0) + 1
        )

    assert source_counts["inventory"] == len(packages)


_BASELINE_CONTRACT_PACKAGE = {
    "source_module_count_baseline": 2,
    "strict_mirror_ratio_baseline": 1.0,
    "loose_mirror_ratio_baseline": 0.75,
    "property_test_file_count_baseline": 0,
}


def _write_ratchet_runtime_fixture(
    root: Path,
    inventory_metrics: dict[str, object],
    *,
    contract_strict_baseline: str = "1.0",
) -> Path:
    for relative in (
        "src/demo",
        "tests/unit/demo",
        "tests/property/demo",
        "architecture/tests",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    (root / "src/demo/alpha.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "src/demo/beta.py").write_text("VALUE = 2\n", encoding="utf-8")
    (root / "tests/unit/demo/test_alpha.py").write_text(
        "def test_alpha():\n    assert True\n", encoding="utf-8"
    )
    (root / "architecture/tests/ratchets.toml").write_text(
        f"""[test_ratchets]
status = "active"
baseline_inventory = "inventory.json"

[ratchet_policy]
no_regression_rule = "strict mirror ratio may not fall below its baseline"

[[package_ratchet]]
name = "demo"
package_mode = "critical_target"
source_path = "src/demo"
unit_path = "tests/unit/demo"
property_path = "tests/property/demo"
source_module_count_baseline = 2
strict_mirror_ratio_baseline = {contract_strict_baseline}
loose_mirror_ratio_baseline = 0.75
property_test_file_count_baseline = 0
ratchet_floor = 0.5
property_decision = "not_required"
integration_decision = "not_required"
integration_reason = "not required for this controlled fixture"
no_regression = true
""",
        encoding="utf-8",
    )
    inventory = {"mirror_ratios": {"packages": [{"package": "demo", **inventory_metrics}]}}
    (root / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    return root / "architecture/tests/ratchets.toml"


def test_null_inventory_ratios_fall_back_per_field_and_fail_closed_on_regression(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    reporter = _load_reporter()
    contract_path = _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": None,
            "loose_name_mirror_ratio": None,
            "property_test_file_count": 0,
        },
    )
    assert contract_path.is_file()
    monkeypatch.setattr(reporter, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(reporter, "TEST_ROOT", tmp_path / "tests")
    monkeypatch.setattr(
        reporter,
        "_parse_args",
        lambda: SimpleNamespace(
            contract=Path("architecture/tests/ratchets.toml"),
            format="json",
            output=None,
            fail_on_regression=True,
        ),
    )

    exit_code = reporter.main()
    payload = json.loads(capsys.readouterr().out)
    package = payload["packages"][0]

    assert package["source_module_count"] == 2
    assert package["source_module_count_baseline"] == 0
    assert package["strict_module_mirror_ratio"] == 0.5
    assert package["strict_module_mirror_ratio_baseline"] == 1.0
    assert package["strict_module_mirror_ratio_delta"] == -0.5
    assert package["loose_name_mirror_ratio_baseline"] == 0.75
    assert package["property_test_file_count_baseline"] == 0
    assert package["baseline_basis"] == {
        "source_module_count": "inventory",
        "strict_module_mirror_ratio": "contract_fallback",
        "loose_name_mirror_ratio": "contract_fallback",
        "property_test_file_count": "inventory",
    }
    assert package["strict_mirror_status"] == "strict_regression"
    assert payload["summary"]["strict_mirror_regressions"] == 1
    assert "strict_module_mirror_ratio=contract_fallback" in reporter._render_markdown(payload)
    assert exit_code == 1


def test_baseline_selection_uses_all_valid_inventory_metrics_over_contract() -> None:
    reporter = _load_reporter()
    inventory = {
        "source_module_count": 8,
        "strict_module_mirror_ratio": 0.25,
        "loose_name_mirror_ratio": 0.5,
        "property_test_file_count": 4,
    }

    values, basis = reporter._resolve_package_baseline(_BASELINE_CONTRACT_PACKAGE, inventory)

    assert values == inventory
    assert basis == {
        "source_module_count": "inventory",
        "strict_module_mirror_ratio": "inventory",
        "loose_name_mirror_ratio": "inventory",
        "property_test_file_count": "inventory",
    }


def test_baseline_selection_uses_contract_when_inventory_record_is_absent() -> None:
    reporter = _load_reporter()

    values, basis = reporter._resolve_package_baseline(_BASELINE_CONTRACT_PACKAGE, None)

    assert values == {
        "source_module_count": 2,
        "strict_module_mirror_ratio": 1.0,
        "loose_name_mirror_ratio": 0.75,
        "property_test_file_count": 0,
    }
    assert set(basis.values()) == {"contract_fallback"}


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("source_module_count", True),
        ("source_module_count", "0"),
        ("source_module_count", -1),
        ("source_module_count", 1.0),
        ("strict_module_mirror_ratio", False),
        ("strict_module_mirror_ratio", "0.5"),
        ("strict_module_mirror_ratio", []),
        ("strict_module_mirror_ratio", float("nan")),
        ("strict_module_mirror_ratio", float("inf")),
        ("strict_module_mirror_ratio", -0.01),
        ("loose_name_mirror_ratio", 1.01),
        ("property_test_file_count", -1),
        ("property_test_file_count", 1.5),
    ],
)
def test_baseline_selection_rejects_malformed_present_inventory_metrics(
    metric: str, value: object
) -> None:
    reporter = _load_reporter()
    inventory = {
        "source_module_count": 2,
        "strict_module_mirror_ratio": 1.0,
        "loose_name_mirror_ratio": 0.75,
        "property_test_file_count": 0,
        metric: value,
    }

    with pytest.raises(ValueError, match=metric):
        reporter._resolve_package_baseline(_BASELINE_CONTRACT_PACKAGE, inventory)


def test_missing_inventory_and_contract_metric_fails_closed() -> None:
    reporter = _load_reporter()
    package = dict.fromkeys(_BASELINE_CONTRACT_PACKAGE)
    inventory = {
        "source_module_count": None,
        "strict_module_mirror_ratio": None,
        "loose_name_mirror_ratio": None,
        "property_test_file_count": None,
    }

    with pytest.raises(ValueError, match="source_module_count"):
        reporter._resolve_package_baseline(package, inventory)


@pytest.mark.parametrize(
    ("metric", "contract_field", "value"),
    [
        ("source_module_count", "source_module_count_baseline", True),
        ("source_module_count", "source_module_count_baseline", "2"),
        ("source_module_count", "source_module_count_baseline", -1),
        ("source_module_count", "source_module_count_baseline", 2.0),
        ("strict_module_mirror_ratio", "strict_mirror_ratio_baseline", False),
        ("strict_module_mirror_ratio", "strict_mirror_ratio_baseline", "0.5"),
        ("strict_module_mirror_ratio", "strict_mirror_ratio_baseline", {}),
        ("strict_module_mirror_ratio", "strict_mirror_ratio_baseline", float("nan")),
        ("strict_module_mirror_ratio", "strict_mirror_ratio_baseline", float("inf")),
        ("strict_module_mirror_ratio", "strict_mirror_ratio_baseline", -0.01),
        ("loose_name_mirror_ratio", "loose_mirror_ratio_baseline", 1.01),
        ("property_test_file_count", "property_test_file_count_baseline", -1),
        ("property_test_file_count", "property_test_file_count_baseline", 1.5),
    ],
)
def test_baseline_selection_rejects_malformed_contract_fallback_metrics(
    metric: str, contract_field: str, value: object
) -> None:
    reporter = _load_reporter()
    package = dict(_BASELINE_CONTRACT_PACKAGE)
    package[contract_field] = value
    inventory = {
        "source_module_count": None,
        "strict_module_mirror_ratio": None,
        "loose_name_mirror_ratio": None,
        "property_test_file_count": None,
    }

    with pytest.raises(ValueError, match=metric):
        reporter._resolve_package_baseline(package, inventory)


def _configure_ratchet_main(reporter: ModuleType, root: Path, monkeypatch) -> None:
    monkeypatch.setattr(reporter, "REPO_ROOT", root)
    monkeypatch.setattr(reporter, "TEST_ROOT", root / "tests")
    monkeypatch.setattr(
        reporter,
        "_parse_args",
        lambda: SimpleNamespace(
            contract=Path("architecture/tests/ratchets.toml"),
            format="json",
            output=None,
            fail_on_regression=True,
        ),
    )


def _write_inventory_payload(root: Path, payload: object) -> None:
    (root / "inventory.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_inventory_text(root: Path, text: str) -> None:
    (root / "inventory.json").write_text(text, encoding="utf-8")


def _demo_inventory_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "package": "demo",
        "source_module_count": 0,
        "strict_module_mirror_ratio": 1.0,
        "loose_name_mirror_ratio": 0.75,
        "property_test_file_count": 0,
    }
    row.update(overrides)
    return row


def test_inventory_admits_well_formed_inactive_package_rows(tmp_path: Path) -> None:
    reporter = _load_reporter()
    contract_path = _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
    )
    contract = reporter._load_toml(contract_path)
    reporter.REPO_ROOT = tmp_path
    _write_inventory_payload(
        tmp_path,
        {"mirror_ratios": {"packages": [_demo_inventory_row(), {"package": "inactive"}]}},
    )

    assert set(reporter._baseline_packages(contract)) == {"demo", "inactive"}


def test_main_uses_valid_inventory_baseline_and_fails_on_actual_strict_regression(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    reporter = _load_reporter()
    contract_path = _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
        contract_strict_baseline="0.0",
    )
    _write_inventory_payload(tmp_path, {"mirror_ratios": {"packages": [_demo_inventory_row()]}})
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    exit_code = reporter.main()
    package = json.loads(capsys.readouterr().out)["packages"][0]

    assert package["strict_module_mirror_ratio"] == 0.5
    assert package["strict_module_mirror_ratio_baseline"] == 1.0
    assert package["baseline_basis"]["strict_module_mirror_ratio"] == "inventory"
    assert package["strict_mirror_status"] == "strict_regression"
    assert exit_code == 1


def test_main_rejects_duplicate_inventory_identity_before_any_field_fallback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    reporter = _load_reporter()
    _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
        contract_strict_baseline="0.0",
    )
    duplicate_with_missing_metrics = {"package": "demo"}
    _write_inventory_payload(
        tmp_path,
        {
            "mirror_ratios": {
                "packages": [
                    _demo_inventory_row(),
                    duplicate_with_missing_metrics,
                ]
            }
        },
    )
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="Duplicate inventory package identity: demo"):
        reporter.main()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "must be an object"),
        ({"mirror_ratios": []}, "mirror_ratios: expected a mapping"),
        ({"mirror_ratios": {"packages": "not-a-list"}}, "package rows: expected a list"),
        ({"mirror_ratios": {"packages": [None]}}, "package row 0: expected a mapping"),
        ({"mirror_ratios": {"packages": [{}]}}, "package must be a non-empty string"),
        (
            {"mirror_ratios": {"packages": [{"package": 7}]}},
            "package must be a non-empty string",
        ),
        (
            {"mirror_ratios": {"packages": [{"package": "   "}]}},
            "package must be a non-empty string",
        ),
        (
            {
                "mirror_ratios": {
                    "packages": [{"package": "inactive", "strict_module_mirror_ratio": "0.5"}]
                }
            },
            "inventory baseline metric strict_module_mirror_ratio",
        ),
    ],
)
def test_main_rejects_malformed_inventory_container_and_rows(
    tmp_path: Path, monkeypatch, payload: object, message: str
) -> None:
    reporter = _load_reporter()
    _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
    )
    _write_inventory_payload(tmp_path, payload)
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    with pytest.raises(ValueError, match=message):
        reporter.main()


def test_main_allows_a_missing_inventory_file_and_uses_contract_fallback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    reporter = _load_reporter()
    contract_path = _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
        contract_strict_baseline="0.0",
    )
    (tmp_path / "inventory.json").unlink()
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    exit_code = reporter.main()
    package = json.loads(capsys.readouterr().out)["packages"][0]

    assert package["strict_module_mirror_ratio_baseline"] == 0.0
    assert package["baseline_basis"]["strict_module_mirror_ratio"] == "contract_fallback"
    assert package["strict_mirror_status"] == "no_regression"
    assert exit_code == 0
    assert contract_path.is_file()


@pytest.mark.parametrize(
    "raw_inventory",
    [
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"package":"other","source_module_count":0,'
            '"strict_module_mirror_ratio":1.0,"loose_name_mirror_ratio":0.75,'
            '"property_test_file_count":0}]}}'
        ),
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"source_module_count":0,"strict_module_mirror_ratio":1.0,'
            '"strict_module_mirror_ratio":null,"loose_name_mirror_ratio":0.75,'
            '"property_test_file_count":0}]}}'
        ),
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"source_module_count":0,"strict_module_mirror_ratio":1.0,'
            '"loose_name_mirror_ratio":0.75,"property_test_file_count":0}]},'
            '"metadata":{"source":"first","source":"second"}}'
        ),
    ],
    ids=["duplicate-package-member", "duplicate-metric-member", "nested-unknown-member"],
)
def test_main_rejects_duplicate_json_members_before_any_fallback(
    tmp_path: Path, monkeypatch, capsys, raw_inventory: str
) -> None:
    reporter = _load_reporter()
    _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
        contract_strict_baseline="0.0",
    )
    _write_inventory_text(tmp_path, raw_inventory)
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="Malformed inventory baseline"):
        reporter.main()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "raw_inventory",
    [
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"source_module_count":0,"strict_module_mirror_ratio":1.0,'
            '"loose_name_mirror_ratio":0.75,"property_test_file_count":0}]},'
            '"unused":NaN}'
        ),
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"source_module_count":0,"strict_module_mirror_ratio":1.0,'
            '"loose_name_mirror_ratio":0.75,"property_test_file_count":0}]},'
            '"unused":Infinity}'
        ),
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"source_module_count":0,"strict_module_mirror_ratio":1.0,'
            '"loose_name_mirror_ratio":0.75,"property_test_file_count":0}]},'
            '"unused":-Infinity}'
        ),
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"source_module_count":0,"strict_module_mirror_ratio":1.0,'
            '"loose_name_mirror_ratio":0.75,"property_test_file_count":0}]},'
            '"unused":1e9999}'
        ),
        (
            '{"mirror_ratios":{"packages":[{"package":"demo",'
            '"source_module_count":0,"strict_module_mirror_ratio":1.0,'
            '"loose_name_mirror_ratio":0.75,"property_test_file_count":0}]},}'
        ),
    ],
    ids=[
        "nonstandard-nan",
        "nonstandard-infinity",
        "nonstandard-negative-infinity",
        "overflowing-json-number",
        "trailing-comma-json-syntax",
    ],
)
def test_main_rejects_non_finite_json_values_before_fallback(
    tmp_path: Path, monkeypatch, capsys, raw_inventory: str
) -> None:
    reporter = _load_reporter()
    _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
        contract_strict_baseline="0.0",
    )
    _write_inventory_text(tmp_path, raw_inventory)
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="Malformed inventory baseline"):
        reporter.main()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("inventory_strict_baseline", "expected_baseline", "expected_basis", "expected_exit"),
    [
        (None, 1.0, "contract_fallback", 1),
        (0.0, 0.0, "inventory", 0),
    ],
    ids=["explicit-null-falls-back", "inventory-zero-wins"],
)
def test_main_preserves_valid_null_fallback_and_zero_precedence(
    tmp_path: Path,
    monkeypatch,
    capsys,
    inventory_strict_baseline: float | None,
    expected_baseline: float,
    expected_basis: str,
    expected_exit: int,
) -> None:
    reporter = _load_reporter()
    _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
        contract_strict_baseline="1.0",
    )
    _write_inventory_payload(
        tmp_path,
        {
            "mirror_ratios": {
                "packages": [
                    _demo_inventory_row(strict_module_mirror_ratio=inventory_strict_baseline)
                ]
            }
        },
    )
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    exit_code = reporter.main()
    package = json.loads(capsys.readouterr().out)["packages"][0]

    assert package["strict_module_mirror_ratio_baseline"] == expected_baseline
    assert package["baseline_basis"]["strict_module_mirror_ratio"] == expected_basis
    assert exit_code == expected_exit


@pytest.mark.parametrize(
    ("contract_mutation", "message"),
    [
        (
            lambda text: text.replace(
                "strict_mirror_ratio_baseline = 1.0",
                'strict_mirror_ratio_baseline = "1.0"',
            ),
            "contract baseline metric strict_module_mirror_ratio",
        ),
        (
            lambda text: text.replace(
                'baseline_inventory = "inventory.json"',
                "baseline_inventory = 1",
            ),
            "baseline_inventory: expected a non-empty path",
        ),
        (
            lambda text: text.replace("[[package_ratchet]]", 'package_ratchet = "invalid"', 1),
            "contract package rows: expected a list",
        ),
        (
            lambda text: text.replace('name = "demo"', "name = 7", 1),
            "name must be a non-empty string",
        ),
        (
            lambda text: text + '\n[[package_ratchet]]\nname = "demo"\n',
            "Duplicate contract package identity: demo",
        ),
        (
            lambda text: text.replace("[test_ratchets]", 'test_ratchets = "invalid"', 1),
            "test_ratchets: expected a mapping",
        ),
    ],
)
def test_main_rejects_malformed_contract_baseline_inputs_before_fallback(
    tmp_path: Path, monkeypatch, contract_mutation, message: str
) -> None:
    reporter = _load_reporter()
    contract_path = _write_ratchet_runtime_fixture(
        tmp_path,
        {
            "source_module_count": 0,
            "strict_module_mirror_ratio": 1.0,
            "loose_name_mirror_ratio": 0.75,
            "property_test_file_count": 0,
        },
    )
    contract_path.write_text(
        contract_mutation(contract_path.read_text(encoding="utf-8")), encoding="utf-8"
    )
    _write_inventory_payload(tmp_path, {"mirror_ratios": {"packages": [_demo_inventory_row()]}})
    _configure_ratchet_main(reporter, tmp_path, monkeypatch)

    with pytest.raises(ValueError, match=message):
        reporter.main()
