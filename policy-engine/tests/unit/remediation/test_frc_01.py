"""Check that the bounded S10 stage separates estimator and calibration data."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError


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


def test_same_nominal_level_distinguishes_two_observed_corpora() -> None:
    """Measure coverage using the actual observations under the same bounds."""
    from polisyos.calibration import compute_calibration_curve

    bounds = [[(0.0, 1.0)] * 4]
    covered = compute_calibration_curve([0.2, 0.3, 0.4, 0.5], bounds, levels=[0.95])
    missed = compute_calibration_curve([1.2, 1.3, 1.4, 1.5], bounds, levels=[0.95])
    assert covered.points[0].n_observations == missed.points[0].n_observations == 4
    assert covered.points[0].empirical_coverage == 1.0
    assert missed.points[0].empirical_coverage == 0.0
    assert covered.ece == pytest.approx(0.05)
    assert missed.ece == pytest.approx(0.95)


def test_missing_report_remains_blocked_and_records_false_clear() -> None:
    """A missing estimator report remains an explicit fail-closed boundary."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(None)

    assert evidence["calibration_status"] == "blocked"
    assert evidence["floor_passed"] is False
    assert evidence["counterfactual_credibility"] != "credible"
    assert (
        evidence["false_clear_counts"]["uncalibrated_observable_promotion_false_clear_count"] >= 1
    )


def test_failed_estimator_diagnostic_remains_limited() -> None:
    """Estimator diagnostics still surface a bounded non-pass outcome."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report(diagnostics=(SimpleNamespace(passed=False),))
    )

    assert evidence["calibration_status"] != "pass"
    assert evidence["floor_passed"] is False
    assert evidence["numerator"] == 0
    assert evidence["pass_rate"] == 0.0


def test_raw_calibration_map_cannot_bind_temporal_roles_or_mint_record() -> None:
    """Syntactically valid times and reference strings cannot establish calibration."""

    build_inputs = _generation_cycle("_build_s10_forecast_inputs")
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
    method_result = SimpleNamespace(output={"report": _finite_estimator_report()})

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
            **_forecast_times(),
            "observed_outcome_ref": "outcome://frc01/observed",
            "historical_implementation_ref": "implementation://frc01/history",
            "evaluation_design_ref": "evaluation://frc01/design",
            "credible_evaluation_evidence_ref": "evidence://frc01/credible",
            "source_lineage_refs": ["lineage://frc01/source"],
            "method_lineage_refs": ["lineage://frc01/method"],
        },
    )
    assert inputs["forecast_calibration_record"] is None
    support = inputs["forecast_support"]
    assert support.forecast_tier == "blocked"
    assert support.calibration_record_ref is None


def _forecast_times() -> dict[str, str]:
    return {
        "data_valid_time": "2025-01-15T08:30:00+00:00",
        "calibration_window_start": "2025-02-01T00:00:00+00:00",
        "policy_effective_time": "2025-02-12T14:00:00-05:00",
        "calibration_window_end": "2025-03-01T00:00:00+00:00",
        "prediction_time": "2025-04-01T12:00:00+02:00",
        "observation_time": "2025-04-20T09:45:00+00:00",
    }


def test_owner_and_s10_preserve_six_distinct_temporal_instants() -> None:
    """Check corresponding instants when inputs contain timezone offsets."""
    from polisyos.scientist.methods.backtesting.forecast_owner import ForecastTemporalRoles

    submitted = _forecast_times()
    owner = ForecastTemporalRoles.model_validate(submitted)
    roles = _generation_cycle("_bound_s10_temporal_roles")(owner.model_dump(mode="json"))
    assert len(set(roles.values())) == 6
    assert roles == {key: datetime.fromisoformat(value) for key, value in submitted.items()}
    assert all(value.tzinfo is UTC for value in roles.values())


@pytest.mark.parametrize(
    ("role", "value"),
    [
        ("observation_time", None),
        ("observation_time", "2025-04-20T09:45:00"),
        ("observation_time", "2025-04-01T10:00:00+00:00"),
        ("calibration_window_end", "2025-04-02T00:00:00+00:00"),
    ],
)
def test_owner_and_s10_refuse_missing_naive_equal_or_misordered_time(
    role: str, value: str | None
) -> None:
    from polisyos.scientist.methods.backtesting.forecast_owner import ForecastTemporalRoles

    submitted = _forecast_times() | {role: value}
    with pytest.raises(ValidationError):
        ForecastTemporalRoles.model_validate(submitted)
    assert _generation_cycle("_bound_s10_temporal_roles")(submitted) is None


def test_missing_calibration_evidence_refs_stays_typed_blocked() -> None:
    """Temporal dates alone cannot mint a calibration record or pass-through tier."""

    build_inputs = _generation_cycle("_build_s10_forecast_inputs")
    timestamp = datetime(2025, 1, 15, 8, 30, tzinfo=UTC).isoformat()
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
    method_result = SimpleNamespace(output={"report": _finite_estimator_report()})

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
            "counterfactual_credibility": "insufficient_history",
            "prediction_time": timestamp,
            "observation_time": timestamp,
            "policy_effective_time": timestamp,
            "data_valid_time": timestamp,
            "calibration_window_start": timestamp,
            "calibration_window_end": timestamp,
        },
    )

    support = inputs["forecast_support"]
    assert inputs["forecast_calibration_record"] is None
    assert support.forecast_tier == "blocked"
    assert support.calibration_record_ref is None
    assert support.s6_limitation_refs


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
