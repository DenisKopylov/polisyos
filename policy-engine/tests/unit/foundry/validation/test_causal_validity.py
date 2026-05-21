from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.validation.causal_validity import (
    REPORT_KIND,
    REPORT_REF_KEY,
    build_causal_statistical_validity_report,
    persist_causal_statistical_validity_report,
)

FIXTURE_PATH = (
    Path(__file__).parents[3] / "_golden" / "foundry" / "causal_validity" / "cases.json"
)
REQUIRED_SCENARIOS = {
    "known_answer",
    "placebo",
    "negative_control",
    "missingness_stress",
    "uncertainty_calibration",
}
REQUIRED_CONTRACT_FIELDS = {
    "expected_assumptions",
    "input_shape",
    "estimand",
    "uncertainty_type",
    "minimum_sample_diagnostics",
    "failure_modes",
}


def _fixture_cases() -> list[dict[str, object]]:
    payload = json.loads(FIXTURE_PATH.read_text())
    return list(payload["cases"])


def test_causal_validity_report_declares_method_contracts_and_passes_fixtures() -> None:
    report = build_causal_statistical_validity_report(
        benchmark_cases=_fixture_cases(),
        benchmark_suite_id="foundry-causal-statistical-validity-offline-v1",
    )

    assert report["schema_version"] == "policyos.foundry.causal_statistical_validity.v1"
    assert report["status"] == "pass"
    assert report["blocking_issue_count"] == 0
    assert report["ref_key"] == REPORT_REF_KEY
    assert set(report["summary"]["scenarios"]) >= REQUIRED_SCENARIOS

    families = report["method_families"]
    assert set(families) >= {
        "difference_in_differences",
        "synthetic_control",
        "regression_discontinuity",
    }
    for family in families.values():
        assert REQUIRED_CONTRACT_FIELDS.issubset(family)
        assert family["expected_assumptions"]
        assert family["failure_modes"]

    known_answers = [
        case for case in report["cases"] if case["scenario"] == "known_answer"
    ]
    assert known_answers
    assert all(case["known_answer"]["within_tolerance"] for case in known_answers)


def test_known_answer_fixture_fails_outside_declared_tolerance() -> None:
    cases = _fixture_cases()
    cases[0] = deepcopy(cases[0])
    cases[0]["observed_effect"] = 0.061

    report = build_causal_statistical_validity_report(benchmark_cases=cases)

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "known_answer_outside_tolerance" in issue_codes


def test_placebo_and_negative_controls_block_confident_causal_outputs() -> None:
    cases = _fixture_cases()
    placebo = deepcopy(next(case for case in cases if case["scenario"] == "placebo"))
    placebo["case_id"] = "did_bad_placebo"
    placebo["observed_effect"] = 0.05
    placebo["recommendation_confidence"] = 0.93
    placebo["degradation_status"] = "pass"
    placebo["uncertainty"] = {
        "type": "cluster_bootstrap_ci",
        "level": 0.95,
        "interval": [0.031, 0.069],
        "standard_error": 0.01,
    }
    negative_control = deepcopy(
        next(case for case in cases if case["scenario"] == "negative_control")
    )
    negative_control["case_id"] = "synthetic_control_bad_negative_control"
    negative_control["observed_effect"] = -0.04
    negative_control["recommendation_confidence"] = 0.91
    negative_control["degradation_status"] = "pass"
    negative_control["uncertainty"] = {
        "type": "placebo_permutation_interval",
        "level": 0.9,
        "interval": [-0.055, -0.023],
        "standard_error": 0.009,
    }

    report = build_causal_statistical_validity_report(
        benchmark_cases=[placebo, negative_control]
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "placebo_confident_effect" in issue_codes
    assert "negative_control_confident_effect" in issue_codes


def test_sensitivity_power_missingness_and_uncertainty_failures_are_blocking() -> None:
    cases = _fixture_cases()
    bad = deepcopy(cases[0])
    bad["case_id"] = "did_underpowered_sensitivity_failure"
    bad["sample_diagnostics"] = {
        "sample_size": 88,
        "min_required_sample_size": 240,
        "effective_sample_size": 71,
        "power": 0.41,
        "min_power": 0.8,
    }
    bad["sensitivity"] = {"status": "fail", "reason": "e_value_below_floor"}
    bad["missingness"] = {
        "status": "fail",
        "missing_rate": 0.18,
        "max_missing_rate": 0.1,
    }
    bad["uncertainty_calibration"] = {
        "status": "fail",
        "coverage": 0.81,
        "target_coverage": 0.95,
        "tolerance": 0.03,
    }

    report = build_causal_statistical_validity_report(benchmark_cases=[bad])

    issues = {issue["code"]: issue for issue in report["issues"]}
    assert report["status"] == "fail"
    assert issues["sample_adequacy_failure"]["severity"] == "fail"
    assert issues["power_failure"]["quality_blocking"] is True
    assert issues["sensitivity_failure"]["quality_blocking"] is True
    assert issues["missingness_stress_failure"]["quality_blocking"] is True
    assert issues["uncertainty_calibration_failure"]["quality_blocking"] is True


def test_report_persistence_uses_causal_statistical_validity_ref_key(tmp_path: Path) -> None:
    report = build_causal_statistical_validity_report(benchmark_cases=_fixture_cases())
    store = FileSystemCAS(tmp_path)

    ref = persist_causal_statistical_validity_report(store, report)

    assert ref.kind == REPORT_KIND
    assert report["ref_key"] == REPORT_REF_KEY
    assert store.has(ref.artifact_id)
