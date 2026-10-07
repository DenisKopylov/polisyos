"""Test-first witnesses for the bounded FRC-01 S10 calibration stage.

Estimator diagnostics remain separate from empirical calibration. The positive
uses the existing admitted ETS producer, configured CAS, and fresh resolver;
unresolved mappings remain rejection controls. This generic predictive fixture
does not establish a trusted default/HTTP verifier or production calibration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.calibration import (
    load_empirical_calibration_evidence,
    load_forecast_candidate_receipt,
)
from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner
from tests._helpers.forecast import configured_forecast_request


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


def _fresh_gateway_inputs(
    store: core_artifacts.FileSystemCAS,
    request: Any,
    result: Any,
    *,
    fields: dict[str, Any] | None = None,
) -> Any:
    """Consume actual persisted producer refs through the public native gateway."""

    gateway = _generation_cycle("RealValueOwnerGateway")(
        repo_root=store.root,
        empirical_evidence_resolver=lambda ref: load_empirical_calibration_evidence(store, ref),
    )
    return gateway.produce_forecast_inputs(
        candidate=SimpleNamespace(candidate_id="frc01-candidate"),
        problem=SimpleNamespace(
            design_problem_id="frc01-problem",
            outcome_of_interest=SimpleNamespace(target_variable=request.target_metric),
        ),
        world_record=SimpleNamespace(
            world_model_record_id="world_model_record_frc01",
            content_hash="sha256:" + "a" * 64,
            valid_time_scope="2026-Q1",
            region_or_jurisdiction="UA",
        ),
        method_result=SimpleNamespace(
            output=result.to_s10_input_fields(store) if fields is None else fields
        ),
        selected_method_fqn=request.method_fqn,
    )


def test_calibration_time_roles_are_preserved_from_bound_evidence(tmp_path: Path) -> None:
    """Actual ETS/CAS refs retain six distinct roles through a fresh consumer."""

    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    request, profile = configured_forecast_request(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    fresh = core_artifacts.FileSystemCAS(tmp_path / "cas")
    receipt = load_forecast_candidate_receipt(fresh, result.candidate_receipt_ref)
    evidence = load_empirical_calibration_evidence(fresh, result.empirical_evidence_ref)
    assert result.candidate_receipt_ref.artifact_id != result.empirical_evidence_ref.artifact_id
    assert receipt.empirical_evidence_ref == result.empirical_evidence_ref
    assert receipt.verifier_provenance == "not_established"

    # Independent oracle reads source rows and issued bounds from different CAS
    # artifacts. It does not consume the report's hit/count/result loop.
    source = core_canon.from_canonical_bytes(
        fresh.get_bytes(request.observed_source_ref.artifact_id)
    )
    rows = core_canon.from_canonical_bytes(fresh.get_bytes(source["data_ref"]["artifact_id"]))[
        "metric"
    ][30:34]
    bundle = core_canon.from_canonical_bytes(
        fresh.get_bytes(result.uncertainty_bundle_ref.artifact_id)
    )
    intervals = sorted(bundle["prediction_interval"], key=lambda item: item["horizon"])
    bounds = [(float(item["lower"]), float(item["upper"])) for item in intervals]
    assert bounds == pytest.approx([(31.0, 31.0), (32.0, 32.0), (33.0, 33.0), (34.0, 34.0)])
    hits = sum(lo <= value <= hi for value, (lo, hi) in zip(rows, bounds, strict=True))
    assert (evidence.recomputed_numerator, evidence.recomputed_denominator) == (hits, len(rows))
    assert (hits, len(rows)) == (4, 4)

    inputs = _fresh_gateway_inputs(fresh, request, result)
    record = inputs["forecast_calibration_record"]
    assert record is not None
    assert (record.numerator, record.denominator) == (hits, len(rows))
    assert record.empirical_evidence_ref == result.empirical_evidence_ref
    for role, expected in request.temporal_roles.model_dump().items():
        assert getattr(record, role) == expected == getattr(evidence, role)
    assert len(set(request.temporal_roles.model_dump().values())) == 6
    assert record.observed_outcome_ref == str(evidence.observed_outcome_ref.artifact_id)
    assert record.historical_implementation_ref == str(evidence.report_ref.artifact_id)
    assert record.evaluation_design_ref == str(evidence.evaluation_design_ref.artifact_id)
    assert record.credible_evaluation_evidence_ref == str(
        evidence.credible_evaluation_evidence_ref.artifact_id
    )
    assert record.source_lineage_refs == [
        str(ref.artifact_id) for ref in evidence.source_lineage_refs
    ]
    assert record.method_lineage_refs == [
        str(ref.artifact_id) for ref in evidence.method_lineage_refs
    ]
    assert {"causal_effect_authority", "treatment_assignment_authority", "s10_authority"} <= set(
        record.may_not_use_for
    )
    envelope = _generation_cycle("_value_calibration_receipt")(
        inputs=inputs,
        world_record=SimpleNamespace(),
    )
    assert envelope.calibration_record_ref == record.calibration_ref
    # A second configured CAS instance resolves the producer artifacts again.
    reopened = _fresh_gateway_inputs(
        core_artifacts.FileSystemCAS(tmp_path / "cas"), request, result
    )
    assert reopened["forecast_calibration_record"] == record


@pytest.mark.parametrize(
    ("defect", "reason"),
    [
        ("missing_ref", "empirical_evidence_ref_missing"),
        ("unresolved_ref", "empirical_evidence_ref_unresolved"),
        ("wrong_kind", "empirical_evidence_ref_kind_mismatch"),
        ("wrong_time", "empirical_evidence_time_mismatch"),
        ("wrong_rule", "empirical_evidence_rule_mismatch"),
    ],
)
def test_fresh_gateway_rejects_unresolved_or_misbound_artifacts(
    tmp_path: Path, defect: str, reason: str
) -> None:
    """Actual resolver calls refuse altered producer fields and preserve a reason."""

    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    request, profile = configured_forecast_request(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    fresh = core_artifacts.FileSystemCAS(tmp_path / "cas")
    fields = result.to_s10_input_fields(fresh)
    if defect == "missing_ref":
        fields["empirical_calibration_evidence_ref"] = None
    elif defect == "unresolved_ref":
        fields["empirical_calibration_evidence_ref"] = result.empirical_evidence_ref.model_copy(
            update={"artifact_id": "sha256:" + "f" * 64}
        )
    elif defect == "wrong_kind":
        fields["empirical_calibration_evidence_ref"] = result.backtest_report_ref
    elif defect == "wrong_time":
        fields["temporal_roles"] = request.temporal_roles.model_copy(
            update={"observation_time": datetime(2025, 1, 1, tzinfo=UTC)}
        )
    else:
        fields["expected_rule_version_ref"] = "wrong-rule"
    inputs = _fresh_gateway_inputs(fresh, request, result, fields=fields)
    support = inputs["forecast_support"]
    assert inputs["forecast_calibration_record"] is None
    assert support.forecast_tier == "blocked"
    assert support.calibration_record_ref is None
    assert support.s6_limitation_refs == [f"s10://calibration/fail-closed/{reason}"]
    # A disposition-reason consistency is tested separately in its owner packet.


def test_unresolved_mapping_cannot_mint_calibration_record() -> None:
    """The historical fake positive remains an unresolved-artifact refusal."""

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
            "prediction_time": prediction_time.isoformat(),
            "observation_time": observation_time.isoformat(),
            "policy_effective_time": policy_effective_time.isoformat(),
            "data_valid_time": data_valid_time.isoformat(),
            "calibration_window_start": window_start.isoformat(),
            "calibration_window_end": window_end.isoformat(),
            "observed_outcome_ref": "outcome://frc01/observed",
            "historical_implementation_ref": "implementation://frc01/history",
            "evaluation_design_ref": "evaluation://frc01/design",
            "credible_evaluation_evidence_ref": "evidence://frc01/credible",
            "source_lineage_refs": ["lineage://frc01/source"],
            "method_lineage_refs": ["lineage://frc01/method"],
        },
    )
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"
    assert inputs["forecast_support"].calibration_record_ref is None


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
    assert (
        "s10://calibration/fail-closed/empirical_evidence_ref_missing" in support.s6_limitation_refs
    )


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
