from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from tools.quality.validation import directory_health

REPO_ROOT = Path(__file__).resolve().parents[3]

TEST_GATE_IDS = {
    "mirror-ratio",
    "no-regression",
    "property-test",
    "fixture-golden",
    "repo-quality",
    "pytest-root",
    "benchmark-role",
}

DIRECTORY_GATE_IDS = {
    "top-level-directory-contract",
    "top-level-loose-file-allow-list",
    "forbidden-lifecycle-commits",
    "source-local-residue",
    "non-product-init-files",
    "product-imports-tests-benchmarks",
    "data-only-pytest-collectable",
    "frontend-src-fixture-registration",
    "generated-api-placement",
    "empty-ui-component-directory",
    "feature-module-owner-threshold",
    "phase-local-junk-residue",
}

REQUIRED_DASHBOARD_METRICS = {
    "top_level_directory_contract_coverage_percent",
    "high_volume_subtree_documentation_coverage_percent",
    "non_product_python_root_count",
    "source_local_residue_count",
    "empty_directory_count_outside_ignored_roots",
    "product_asset_count",
    "test_fixture_count",
    "golden_record_count",
    "example_asset_count",
    "undocumented_frontend_subtree_count",
    "archive_report_promotion_backlog",
    "max_directory_depth",
    "closure_non_product_init_count",
    "closure_phase_local_junk_count",
}


def test_phase6_2_gate_conversion_contract_covers_tests_benchmarks_and_directories() -> None:
    contract = _read_toml("architecture/policies/directory_health.toml")
    header = contract["directory_health"]
    gates = {gate["id"]: gate for gate in contract["gate"]}

    assert header["status"] == "active"
    assert header["phase"] == "repository-best-in-class-phase-6.2"
    assert header["validator_command"].endswith("directory-health --fail-on-regression")
    assert header["mode"] == "fail_closed"
    assert header["top_level_path_moves_active"] is False
    assert TEST_GATE_IDS <= set(gates)
    assert DIRECTORY_GATE_IDS <= set(gates)

    for gate_id in TEST_GATE_IDS:
        gate = gates[gate_id]
        assert gate["owner"] == "team-quality"
        assert gate["mode"] in {"fail_closed_no_regression", "fail_closed_contract"}
        assert gate["command"]
        assert _path_exists(gate["evidence"])

    assert gates["top-level-directory-contract"]["mode"] == "fail_closed"
    for gate_id in DIRECTORY_GATE_IDS - {"source-local-residue"}:
        assert gates[gate_id]["mode"] == "fail_closed"
    assert gates["source-local-residue"]["mode"] == "ratchet_from_current_count"


def test_phase6_2_durable_roots_for_tests_fixtures_goldens_and_benchmarks() -> None:
    ratchets = _read_toml("architecture/tests/ratchets.toml")
    fixture_policy = ratchets["fixture_policy"]
    benchmark_policy = ratchets["benchmark_policy"]
    topology = _read_toml("architecture/tests/topology.toml")["test_topology"]

    for key in ("shared_fixture_root", "shared_golden_root", "shared_helper_root"):
        assert _path_exists(fixture_policy[key]), key
    assert _path_exists(topology["repo_quality_root"])
    assert _path_exists(topology["repo_quality_architecture_root"])
    assert _path_exists(topology["repo_quality_lint_root"])
    assert _path_exists(topology["repo_quality_tools_root"])

    assert benchmark_policy["decision"] == "public_product_evaluation"
    assert benchmark_policy["target_public_root"] == "benchmarks"
    assert benchmark_policy["internal_performance_root"] == "tests/performance"
    assert _path_exists(benchmark_policy["target_public_root"])


def test_phase6_2_directory_health_dashboard_metrics_are_regression_baselined() -> None:
    contract = _read_toml("architecture/policies/directory_health.toml")
    baselines = {metric["id"]: metric for metric in contract["metric_baseline"]}
    report = directory_health.build_report(REPO_ROOT)
    metrics = report["dashboard"]["metrics"]

    assert report["contract_error_count"] == 0
    assert report["finding_count"] == 0
    assert REQUIRED_DASHBOARD_METRICS <= set(metrics)
    assert REQUIRED_DASHBOARD_METRICS <= set(baselines)
    assert metrics["top_level_directory_contract_coverage_percent"] >= 100.0
    assert metrics["closure_forbidden_lifecycle_commit_count"] == 0
    assert metrics["closure_non_product_init_count"] == 0
    assert metrics["closure_forbidden_product_import_count"] == 0
    assert metrics["closure_data_only_pytest_count"] == 0
    assert metrics["closure_unregistered_frontend_fixture_count"] == 0
    assert metrics["closure_unregistered_generated_api_count"] == 0
    assert metrics["closure_empty_ui_component_directory_count"] == 0
    assert metrics["closure_over_threshold_feature_without_owner_count"] == 0
    assert metrics["closure_phase_local_junk_count"] == 0

    for metric_id, baseline in baselines.items():
        assert baseline["owner"], metric_id
        assert baseline["direction"] in {"not_increase", "not_decrease"}, metric_id


def test_phase6_2_directory_health_cli_can_fail_on_regression_without_findings() -> None:
    assert (
        directory_health.run_cli(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--fail-on-regression",
                "--json-output",
                str(REPO_ROOT / "_build/.tmp/phase6_2_directory_health.json"),
            ]
        )
        == 0
    )


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()
