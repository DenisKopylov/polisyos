"""Test-first witnesses for the bounded FRC-01 S10 calibration stage.

These tests intentionally keep the Foundry estimator result separate from an
observable calibration corpus.  The branch owns no calibration producer yet;
the first two witnesses therefore remain RED until the production adapter
stops manufacturing calibration evidence from finite estimator metadata.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any


def _generation_cycle(name: str) -> Any:
    import polisyos.runtime.quality.generation_cycle as module

    return getattr(module, name)


def _finite_estimator_report(
    *, confidence_level: float = 0.95, diagnostics: tuple[Any, ...] = ()
) -> Any:
    """Return estimator-shaped output with no observation-side calibration data."""

    return SimpleNamespace(
        point_estimate=1.5,
        confidence_interval=(1.0, 2.0),
        standard_error=0.2,
        confidence_level=confidence_level,
        diagnostics=diagnostics,
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=4,
        post_periods=4,
    )


def test_finite_estimator_report_without_observations_cannot_pass_calibration() -> None:
    """Finite point/CI diagnostics are not an observed calibration corpus."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report()
    )

    assert evidence["calibration_status"] in {"limit", "insufficient_history", "blocked"}
    assert evidence["denominator"] == 0
    assert evidence["numerator"] == 0
    assert evidence["pass_rate"] == 0.0
    assert evidence["floor_passed"] is False
    assert evidence["counterfactual_credibility"] != "credible"


def test_nominal_confidence_is_not_empirical_coverage_without_observations() -> None:
    """Changing only the declared CI level must not change measured coverage."""

    evidence_80 = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report(confidence_level=0.80)
    )
    evidence_95 = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report(confidence_level=0.95)
    )

    assert evidence_80["calibration_status"] != "pass"
    assert evidence_95["calibration_status"] != "pass"
    assert evidence_80["interval_coverage_metric"] is None
    assert evidence_95["interval_coverage_metric"] is None
    assert evidence_80["calibration_error_metric"] is None
    assert evidence_95["calibration_error_metric"] is None


def test_missing_report_remains_blocked_and_records_false_clear() -> None:
    """A missing estimator report remains an explicit fail-closed boundary."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(None)

    assert evidence["calibration_status"] == "blocked"
    assert evidence["floor_passed"] is False
    assert evidence["counterfactual_credibility"] != "credible"
    assert evidence["false_clear_counts"][
        "uncalibrated_observable_promotion_false_clear_count"
    ] >= 1


def test_failed_estimator_diagnostic_remains_limited() -> None:
    """Estimator diagnostics still surface a bounded non-pass outcome."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report(diagnostics=(SimpleNamespace(passed=False),))
    )

    assert evidence["calibration_status"] != "pass"
    assert evidence["floor_passed"] is False
    assert evidence["numerator"] == 0
    assert evidence["pass_rate"] == 0.0


def test_calibration_time_roles_are_preserved_from_bound_evidence() -> None:
    """Prediction, observation, effective, valid, and window times stay distinct."""

    build_inputs = _generation_cycle("_build_s10_forecast_inputs")
    prediction_time = datetime(2025, 1, 15, 8, 30, tzinfo=UTC)
    observation_time = datetime(2025, 4, 20, 9, 45, tzinfo=UTC)
    policy_effective_time = datetime(2025, 2, 1, 0, 0, tzinfo=UTC)
    data_valid_time = datetime(2025, 4, 1, 0, 0, tzinfo=UTC)
    window_start = datetime(2025, 3, 1, 0, 0, tzinfo=UTC)
    window_end = datetime(2025, 4, 30, 23, 59, tzinfo=UTC)
    world_record = SimpleNamespace(
        world_model_record_id="world_model_record_frc01",
        content_hash="sha256:" + "a" * 64,
        valid_time_scope="2025-Q2",
        region_or_jurisdiction="UA",
    )
    problem = SimpleNamespace(
        design_problem_id="frc01-problem",
        outcome_of_interest=SimpleNamespace(target_variable="firm_survival"),
    )
    candidate = SimpleNamespace(candidate_id="frc01-candidate")
    method_result = SimpleNamespace(
        output={"report": _finite_estimator_report()}
    )

    inputs = build_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn="foundry.methods.example",
        forecast_tier="observable_calibrated",
        calibration_status="limit",
        policy_context_ref="policy-context://world_model_record_frc01",
        expected_policy_context_ref="policy-context://world_model_record_frc01",
        false_clear_counts={},
        calibration_evidence={
            "denominator": 0,
            "numerator": 0,
            "pass_rate": 0.0,
            "floor_passed": False,
            "counterfactual_credibility": "insufficient_history",
            "prediction_time": prediction_time.isoformat(),
            "observation_time": observation_time.isoformat(),
            "policy_effective_time": policy_effective_time.isoformat(),
            "data_valid_time": data_valid_time.isoformat(),
            "calibration_window_start": window_start.isoformat(),
            "calibration_window_end": window_end.isoformat(),
        },
    )
    record = inputs["forecast_calibration_record"]

    assert record.prediction_time == prediction_time
    assert record.observation_time == observation_time
    assert record.policy_effective_time == policy_effective_time
    assert record.data_valid_time == data_valid_time
    assert record.calibration_window_start == window_start
    assert record.calibration_window_end == window_end
    assert len({
        record.prediction_time,
        record.observation_time,
        record.policy_effective_time,
        record.data_valid_time,
        record.calibration_window_start,
        record.calibration_window_end,
    }) == 6


def test_s10_authority_boundary_keeps_purpose_denials() -> None:
    """Bounded FRC-01 evidence cannot become recommendation or S11 authority."""

    boundary = _generation_cycle("_s10_value_authority_boundary")()

    assert boundary["posture"] == "shadow"
    assert {
        "production_recommendation",
        "production_claim_authority",
        "claim_authority",
        "closeout_authority",
        "s11_calibration",
    } <= set(boundary["may_not_use_for"])
