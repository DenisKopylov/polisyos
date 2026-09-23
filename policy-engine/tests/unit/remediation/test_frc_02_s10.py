"""Test-first witnesses for the FRC-02 predictive-evidence to S10 bridge.

The producer is deliberately exercised through its persisted CAS artifact and
readback loader.  These tests do not grant the neutral predictive artifact
causal or broad S10 authority: the expected downstream result is a separate,
bounded S10 projection whose source denials and content binding remain
visible.

This is a RED test-only candidate.  The current generation-cycle builder still
manufactures S10 refs, fixes ``foundry_causal`` for every method, and does not
consume the persisted evidence ref.  Production changes belong to the parent
FRC-02 implementation lease.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    OutcomeComparison,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts import InputRef, put_json_artifact
from polisyos.ir.registry.refs import BacktestReportRef

MODEL_REF = "model://frc02/ets/v1"
POLICY_REF = "policy://frc02/ets/v1"
ESTIMAND = "predictive_interval_coverage"
METHOD_REF = "forecasting.univariate.exponential_smoothing"
METHOD_FQN = "forecasting.univariate.exponential_smoothing@1.0.0"
METHOD_VERSION = "1.0.0"
RULE_VERSION_REF = "rolling-origin-residual-conformal.v1"
PREDICTIVE_AUTHORITY_DENIALS = frozenset(
    {
        "causal_effect_authority",
        "treatment_assignment_authority",
        "s10_authority",
    }
)

REFERENCE_PROFILES: dict[str, tuple[str, str, str]] = {
    "scope_binding": (
        "ir.calibration.scope_binding",
        "polisyos.calibration.scope_binding",
        "1.0",
    ),
    "calibration_threshold": (
        "ir.calibration.threshold",
        "polisyos.calibration.threshold",
        "1.0",
    ),
    "observed_outcome": (
        "ir.calibration.observed_outcome",
        "polisyos.calibration.observed_outcome",
        "1.0",
    ),
    "prediction": (
        "ir.calibration.prediction",
        "polisyos.calibration.prediction",
        "1.0",
    ),
    "evaluation_design": (
        "ir.calibration.evaluation_design",
        "polisyos.calibration.evaluation_design",
        "1.0",
    ),
    "credible_evaluation": (
        "ir.calibration.credible_evaluation",
        "polisyos.calibration.credible_evaluation",
        "1.0",
    ),
    "source_lineage": (
        "ir.calibration.source_lineage",
        "polisyos.calibration.source_lineage",
        "1.0",
    ),
    "method_lineage": (
        "ir.calibration.method_lineage",
        "polisyos.calibration.method_lineage",
        "1.0",
    ),
}


def _bridge() -> Any:
    """Resolve the real persisted producer/loader only when a test invokes it."""

    import importlib

    return importlib.import_module("polisyos.calibration.forecast_bridge")


def _generation_cycle(name: str) -> Any:
    """Resolve the current generation-cycle seam under test."""

    import polisyos.runtime.quality.generation_cycle as module

    return getattr(module, name)


def _persist_context_ref(
    store: FileSystemCAS,
    *,
    role: str,
    report_id: str,
    identity: str,
    identity_path: str = "identity",
    binding: Mapping[str, object] | None = None,
    payload_fields: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Persist one role-profiled, report-bound context artifact."""

    kind, schema_name, schema_version = REFERENCE_PROFILES[role]
    payload: dict[str, object] = {
        "role": role,
        "report_id": report_id,
        "identity": identity,
    }
    if identity_path == "report_id":
        payload["report_id"] = identity
    if binding is not None:
        payload["binding"] = dict(binding)
    if payload_fields is not None:
        payload.update(payload_fields)
    ref = put_json_artifact(
        store,
        payload,
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
    )
    ref.update(
        {
            "role": role,
            "schema_name": schema_name,
            "schema_version": schema_version,
            "identity_path": identity_path,
            "identity_value": identity,
        }
    )
    return ref


def _persist_context_refs(
    store: FileSystemCAS,
    *,
    report_id: str,
    threshold: float,
) -> dict[str, dict[str, str]]:
    """Persist the complete neutral context required by the producer."""

    binding = {
        "report_id": report_id,
        "model_spec_ref": MODEL_REF,
        "policy_spec_ref": POLICY_REF,
        "estimand": ESTIMAND,
        "method_ref": METHOD_REF,
        "method_version": METHOD_VERSION,
        "rule_version_ref": RULE_VERSION_REF,
        "calibration_threshold": f"{threshold:.2f}",
    }
    return {
        "scope_binding": _persist_context_ref(
            store,
            role="scope_binding",
            report_id=report_id,
            identity=report_id,
            identity_path="report_id",
            binding=binding,
        ),
        "calibration_threshold": _persist_context_ref(
            store,
            role="calibration_threshold",
            report_id=report_id,
            identity=f"threshold://frc02/{threshold:.2f}",
            payload_fields={"threshold": Decimal(f"{threshold:.2f}")},
        ),
        "observed_outcome": _persist_context_ref(
            store,
            role="observed_outcome",
            report_id=report_id,
            identity="observation://frc02/held-out/v1",
        ),
        "prediction": _persist_context_ref(
            store,
            role="prediction",
            report_id=report_id,
            identity="prediction://frc02/held-out/v1",
        ),
        "evaluation_design": _persist_context_ref(
            store,
            role="evaluation_design",
            report_id=report_id,
            identity="evaluation://frc02/rolling-origin/v1",
        ),
        "credible_evaluation": _persist_context_ref(
            store,
            role="credible_evaluation",
            report_id=report_id,
            identity="evaluation-evidence://frc02/v1",
        ),
        "source_lineage": _persist_context_ref(
            store,
            role="source_lineage",
            report_id=report_id,
            identity="source://frc02/panel/v1",
        ),
        "method_lineage": _persist_context_ref(
            store,
            role="method_lineage",
            report_id=report_id,
            identity="method-lineage://frc02/ets/v1",
        ),
    }


def _persist_report(
    tmp_path: Path,
    *,
    label: str,
    observations: tuple[bool | None, ...],
    nominal_confidence: float = 0.95,
    threshold: float = 0.5,
) -> tuple[FileSystemCAS, BacktestReportRef, dict[str, dict[str, str]]]:
    """Persist a real backtest report with recomputable interval observations."""

    store = FileSystemCAS(tmp_path / f"frc02-s10-{label}-cas")
    report_id = f"frc02-s10-{label}"
    comparisons: list[OutcomeComparison] = []
    for index, observed_hit in enumerate(observations):
        y_pred = 10.0 + index
        if observed_hit is None:
            y_true = y_pred
            absolute_error = 0.0
            ci_lower = None
            ci_upper = None
        elif observed_hit:
            y_true = y_pred
            absolute_error = 0.0
            ci_lower = y_pred - 0.5
            ci_upper = y_pred + 0.5
        else:
            y_true = y_pred + 5.0
            absolute_error = 5.0
            ci_lower = y_pred - 0.5
            ci_upper = y_pred + 0.5
        comparisons.append(
            OutcomeComparison(
                metric_name=f"metric-{index}",
                y_pred=y_pred,
                y_true=y_true,
                absolute_error=absolute_error,
                within_ci=observed_hit,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
            )
        )

    denominator = sum(item is not None for item in observations)
    numerator = sum(item is True for item in observations)
    requested = len(observations)
    scenario = BacktestScenario(
        scenario_id="frc02-s10-scenario",
        scenario_label="persisted FRC-02 ETS predictive comparisons",
        data_source="held-out-observations",
        outcome_comparisons=comparisons,
        requested_count=requested,
        compared_count=requested,
        interval_requested_count=requested,
        interval_available_count=denominator,
        interval_evaluated_count=denominator,
        interval_hit_count=numerator,
        interval_availability=denominator / requested if requested else 0.0,
        interval_hit_rate=numerator / denominator if denominator else None,
        nominal_confidence_level=nominal_confidence,
        interval_type="prediction",
    )
    report = BacktestReport(
        schema_version="1.0",
        report_id=report_id,
        model_spec_ref=MODEL_REF,
        policy_spec_ref=POLICY_REF,
        scenarios=[scenario],
        overall_coverage_probability=numerator / denominator if denominator else None,
        n_scenarios=1,
        n_metrics_evaluated=requested,
        metadata={
            "model_spec_ref": MODEL_REF,
            "policy_spec_ref": POLICY_REF,
            "method_ref": METHOD_REF,
            "method_version": METHOD_VERSION,
            "rule_version_ref": RULE_VERSION_REF,
            "estimand": ESTIMAND,
            "authority_scope": "predictive_only",
            "calibration_numerator": numerator,
            "calibration_denominator": denominator,
            "interval_hit_count": numerator,
            "interval_evaluated_count": denominator,
        },
    )
    refs = _persist_context_refs(
        store,
        report_id=report_id,
        threshold=threshold,
    )
    inputs = [
        InputRef(artifact_id=ref["artifact_id"], role=role)
        for role, ref in refs.items()
    ]
    report_ref = persist_backtest_report(store, report, inputs=inputs)
    load_backtest_report(store, report_ref)
    return store, report_ref, refs


def _context(
    refs: dict[str, dict[str, str]],
    *,
    threshold: float,
    method_ref: str = METHOD_REF,
    method_version: str = METHOD_VERSION,
    rule_version_ref: str = RULE_VERSION_REF,
    temporal_updates: Mapping[str, object] | None = None,
) -> Any:
    """Build the explicit predictive context with six ordered time roles."""

    bridge = _bridge()

    def typed_ref(role: str) -> Any:
        return bridge.EvidenceArtifactRef.model_validate(refs[role])

    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload: dict[str, object] = {
        "model_spec_ref": MODEL_REF,
        "policy_spec_ref": POLICY_REF,
        "estimand": ESTIMAND,
        "method_ref": method_ref,
        "method_version": method_version,
        "rule_version_ref": rule_version_ref,
        "calibration_threshold": threshold,
        "scope_binding_ref": typed_ref("scope_binding"),
        "calibration_threshold_ref": typed_ref("calibration_threshold"),
        "observed_outcome_ref": typed_ref("observed_outcome"),
        "prediction_ref": typed_ref("prediction"),
        "evaluation_design_ref": typed_ref("evaluation_design"),
        "credible_evaluation_evidence_ref": typed_ref("credible_evaluation"),
        "source_lineage_refs": (typed_ref("source_lineage"),),
        "method_lineage_refs": (typed_ref("method_lineage"),),
        "data_valid_time": start,
        "calibration_window_start": start + timedelta(days=1),
        "calibration_window_end": start + timedelta(days=2),
        "policy_effective_time": start + timedelta(days=3),
        "prediction_time": start + timedelta(days=4),
        "observation_time": start + timedelta(days=5),
        "evidence_origin": "persisted_backtest",
    }
    payload.update(temporal_updates or {})
    return bridge.EmpiricalCalibrationContext.model_validate(payload)


def _persist_loaded_evidence(
    tmp_path: Path,
    *,
    label: str,
    observations: tuple[bool | None, ...],
    nominal_confidence: float = 0.95,
    threshold: float = 0.5,
) -> tuple[Any, Any, Any, Any]:
    """Produce, persist, and load the neutral empirical evidence artifact."""

    store, report_ref, refs = _persist_report(
        tmp_path,
        label=label,
        observations=observations,
        nominal_confidence=nominal_confidence,
        threshold=threshold,
    )
    bridge = _bridge()
    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=_context(refs, threshold=threshold),
    )
    evidence_ref = bridge.persist_empirical_calibration_evidence(store, evidence)
    loaded = bridge.load_empirical_calibration_evidence(store, evidence_ref)
    assert loaded == evidence
    return store, evidence_ref, loaded, refs


def _artifact_id(ref: Any) -> str:
    return str(ref.artifact_id)


def _calibration_payload(evidence: Any, evidence_ref: Any) -> dict[str, object]:
    """Project loaded neutral evidence into the current builder seam.

    The ``empirical_evidence_ref`` and threshold ref are intentional RED
    requirements.  The current builder ignores them and instead manufactures
    ``s10://`` identities; the eventual consumer must resolve and preserve the
    persisted source artifact.
    """

    return {
        "empirical_evidence_ref": _artifact_id(evidence_ref),
        "empirical_evidence_kind": evidence_ref.kind,
        "authority_scope": evidence.authority_scope,
        "may_not_use_for": list(evidence.may_not_use_for),
        "method_ref": evidence.method_ref,
        "method_version": evidence.method_version,
        "rule_version_ref": evidence.rule_version_ref,
        "estimand": evidence.estimand,
        "denominator": evidence.recomputed_denominator,
        "numerator": evidence.recomputed_numerator,
        "pass_rate": evidence.recomputed_pass_rate or 0.0,
        "floor_passed": evidence.floor_passed,
        "counterfactual_credibility": (
            "credible" if evidence.usable_for_calibration else "insufficient_history"
        ),
        "prediction_time": evidence.prediction_time.isoformat()
        if evidence.prediction_time
        else None,
        "observation_time": evidence.observation_time.isoformat()
        if evidence.observation_time
        else None,
        "policy_effective_time": evidence.policy_effective_time.isoformat()
        if evidence.policy_effective_time
        else None,
        "data_valid_time": evidence.data_valid_time.isoformat()
        if evidence.data_valid_time
        else None,
        "calibration_window_start": evidence.calibration_window_start.isoformat()
        if evidence.calibration_window_start
        else None,
        "calibration_window_end": evidence.calibration_window_end.isoformat()
        if evidence.calibration_window_end
        else None,
        "observed_outcome_ref": _artifact_id(evidence.observed_outcome_ref),
        # The report is an actual persisted input, not a fabricated S10 URI.
        "historical_implementation_ref": _artifact_id(evidence.report_ref),
        "evaluation_design_ref": _artifact_id(evidence.evaluation_design_ref),
        "credible_evaluation_evidence_ref": _artifact_id(
            evidence.credible_evaluation_evidence_ref
        ),
        "calibration_threshold_ref": _artifact_id(evidence.calibration_threshold_ref),
        "source_lineage_refs": [
            _artifact_id(ref) for ref in evidence.source_lineage_refs
        ],
        "method_lineage_refs": [
            _artifact_id(ref) for ref in evidence.method_lineage_refs
        ],
        "forecast_authority_disposition_reason": (
            "persisted ETS predictive interval observations were recomputed from held-out data"
        ),
    }


def _minimal_generation_inputs(
    *,
    evidence: Any,
    evidence_ref: Any,
    forecast_tier: str,
    calibration_status: str,
    calibration_evidence: Mapping[str, object] | None = None,
) -> Mapping[str, Any]:
    """Invoke the current S10 builder with a fixed, test-only method shape."""

    world_record = SimpleNamespace(
        world_model_record_id="world_model_record_frc02_s10",
        content_hash="sha256:" + "a" * 64,
        valid_time_scope="2026-Q1",
        region_or_jurisdiction="UA",
    )
    problem = SimpleNamespace(
        design_problem_id="frc02-s10-problem",
        outcome_of_interest=SimpleNamespace(target_variable="firm_survival"),
    )
    candidate = SimpleNamespace(candidate_id="frc02-s10-candidate")
    method_report = SimpleNamespace(
        point_estimate=1.5,
        confidence_interval=(1.0, 2.0),
        standard_error=0.2,
        confidence_level=0.95,
        diagnostics=(),
        sample_size=evidence.recomputed_denominator,
        n_treated=0,
        n_control=0,
        pre_periods=0,
        post_periods=0,
    )
    payload = dict(calibration_evidence or _calibration_payload(evidence, evidence_ref))
    policy_context_ref = f"policy-context://{world_record.world_model_record_id}"
    return _generation_cycle("_build_s10_forecast_inputs")(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=SimpleNamespace(output={"report": method_report}),
        selected_method_fqn=METHOD_FQN,
        forecast_tier=forecast_tier,
        calibration_status=calibration_status,
        policy_context_ref=policy_context_ref,
        expected_policy_context_ref=policy_context_ref,
        false_clear_counts={},
        calibration_evidence=payload,
    )


def test_same_ets_shape_with_different_held_out_observations_changes_s10_suitability(
    tmp_path: Path,
) -> None:
    """Real observations, not estimator shape, determine S10 suitability."""

    passing_store, passing_ref, passing, _ = _persist_loaded_evidence(
        tmp_path,
        label="all-hit",
        observations=(True, True),
        nominal_confidence=0.95,
        threshold=1.0,
    )
    limited_store, limited_ref, limited, _ = _persist_loaded_evidence(
        tmp_path,
        label="one-miss",
        observations=(True, False),
        nominal_confidence=0.95,
        threshold=1.0,
    )
    assert passing_store is not limited_store
    assert passing.usable_for_calibration is True
    assert limited.usable_for_calibration is False

    passing_inputs = _minimal_generation_inputs(
        evidence=passing,
        evidence_ref=passing_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
    )
    limited_inputs = _minimal_generation_inputs(
        evidence=limited,
        evidence_ref=limited_ref,
        forecast_tier="blocked",
        calibration_status="limit",
    )

    passing_support = passing_inputs["forecast_support"]
    limited_support = limited_inputs["forecast_support"]
    passing_record = passing_inputs["forecast_calibration_record"]
    limited_record = limited_inputs["forecast_calibration_record"]
    assert passing_support.forecast_tier == "observable_calibrated"
    assert limited_support.forecast_tier == "blocked"
    assert passing_record.numerator == 2
    assert passing_record.denominator == 2
    assert limited_record.numerator == 1
    assert limited_record.denominator == 2
    assert passing_support.forecast_tier != limited_support.forecast_tier


def test_nominal_confidence_only_does_not_change_s10_suitability(
    tmp_path: Path,
) -> None:
    """Changing nominal confidence without new observations cannot change the result."""

    low_store, low_ref, low, _ = _persist_loaded_evidence(
        tmp_path,
        label="nominal-80",
        observations=(True, False),
        nominal_confidence=0.80,
        threshold=0.5,
    )
    high_store, high_ref, high, _ = _persist_loaded_evidence(
        tmp_path,
        label="nominal-95",
        observations=(True, False),
        nominal_confidence=0.95,
        threshold=0.5,
    )
    assert low_store is not high_store
    low_inputs = _minimal_generation_inputs(
        evidence=low,
        evidence_ref=low_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
    )
    high_inputs = _minimal_generation_inputs(
        evidence=high,
        evidence_ref=high_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
    )
    low_record = low_inputs["forecast_calibration_record"]
    high_record = high_inputs["forecast_calibration_record"]
    assert low_record.numerator == high_record.numerator == 1
    assert low_record.denominator == high_record.denominator == 2
    assert low_record.pass_rate == high_record.pass_rate == pytest.approx(0.5)
    assert low_record.calibration_status == high_record.calibration_status == "pass"


def test_predictive_producer_denials_are_preserved_by_the_s10_boundary(
    tmp_path: Path,
) -> None:
    """A downstream bounded S10 projection cannot launder producer denials."""

    _store, evidence_ref, evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="denials",
        observations=(True, True),
        threshold=1.0,
    )
    inputs = _minimal_generation_inputs(
        evidence=evidence,
        evidence_ref=evidence_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
    )
    support = inputs["forecast_support"]
    record = inputs["forecast_calibration_record"]
    assert PREDICTIVE_AUTHORITY_DENIALS <= set(support.may_not_use_for)
    assert PREDICTIVE_AUTHORITY_DENIALS <= set(record.may_not_use_for)
    assert set(support.authority_boundary.authoritative_for) <= {
        "forecast_support_tiering",
        "observable_subset_calibration",
    }


def test_ets_predictive_support_is_not_marked_foundry_causal(tmp_path: Path) -> None:
    """The real ETS method family cannot be represented as causal evidence."""

    _store, evidence_ref, evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="method-family",
        observations=(True, True),
        threshold=1.0,
    )
    inputs = _minimal_generation_inputs(
        evidence=evidence,
        evidence_ref=evidence_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
    )
    assert inputs["forecast_support"].method_family == "foundry_forecast"


def test_raw_causal_effect_report_cannot_yield_positive_s10_calibration() -> None:
    """A finite causal-effect-shaped report remains blocked without empirical evidence."""

    world_record = SimpleNamespace(
        world_model_record_id="world_model_record_frc02_raw-report",
        content_hash="sha256:" + "b" * 64,
        valid_time_scope="2026-Q1",
        region_or_jurisdiction="UA",
    )
    problem = SimpleNamespace(
        design_problem_id="frc02-raw-report",
        outcome_of_interest=SimpleNamespace(target_variable="firm_survival"),
    )
    candidate = SimpleNamespace(candidate_id="frc02-raw-report-candidate")
    report = SimpleNamespace(
        point_estimate=1.5,
        confidence_interval=(1.0, 2.0),
        standard_error=0.2,
        confidence_level=0.95,
        diagnostics=(),
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=4,
        post_periods=4,
    )
    inputs = _generation_cycle("_build_real_s10_forecast_inputs")(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=SimpleNamespace(output={"report": report}),
        selected_method_fqn="causal.inference.difference_in_differences@1.0.0",
    )
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"


def test_missing_empirical_evidence_ref_blocks_positive_s10_projection(
    tmp_path: Path,
) -> None:
    """A scalar mapping without the persisted evidence identity cannot pass."""

    _store, evidence_ref, evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="missing-ref",
        observations=(True, True),
        threshold=1.0,
    )
    payload = _calibration_payload(evidence, evidence_ref)
    payload.pop("empirical_evidence_ref")
    inputs = _minimal_generation_inputs(
        evidence=evidence,
        evidence_ref=evidence_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
        calibration_evidence=payload,
    )
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"


@pytest.mark.parametrize("ref_kind", ["corrupt", "foreign"])
def test_corrupt_or_foreign_empirical_ref_blocks_positive_s10_projection(
    tmp_path: Path,
    ref_kind: str,
) -> None:
    """An evidence ID must resolve in the same CAS before S10 can use it."""

    store, evidence_ref, evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label=f"ref-{ref_kind}",
        observations=(True, True),
        threshold=1.0,
    )
    bridge = _bridge()
    if ref_kind == "corrupt":
        bad_ref = evidence_ref.model_copy(
            update={"artifact_id": "sha256:" + "f" * 64}
        )
    else:
        _foreign_store, bad_ref, _foreign_evidence, _ = _persist_loaded_evidence(
            tmp_path,
            label="ref-foreign-source",
            observations=(True, True),
            threshold=1.0,
        )
    with pytest.raises((FileNotFoundError, ValueError, KeyError)):
        bridge.load_empirical_calibration_evidence(store, bad_ref)

    payload = _calibration_payload(evidence, bad_ref)
    inputs = _minimal_generation_inputs(
        evidence=evidence,
        evidence_ref=bad_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
        calibration_evidence=payload,
    )
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"


@pytest.mark.parametrize(
    ("broken_field", "broken_value"),
    [
        ("method_ref", "forecasting.univariate.other@9.9.9"),
        ("method_version", "9.9.9"),
        ("rule_version_ref", "rolling-origin-residual-conformal.v9"),
    ],
)
def test_method_or_rule_mismatch_blocks_positive_s10_projection(
    tmp_path: Path,
    broken_field: str,
    broken_value: str,
) -> None:
    """S10 must compare the selected ETS method/rule with loaded evidence."""

    _store, evidence_ref, evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label=f"mismatch-{broken_field}",
        observations=(True, True),
        threshold=1.0,
    )
    payload = _calibration_payload(evidence, evidence_ref)
    payload[broken_field] = broken_value
    inputs = _minimal_generation_inputs(
        evidence=evidence,
        evidence_ref=evidence_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
        calibration_evidence=payload,
    )
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"


def test_collapsed_or_rebound_temporal_roles_block_positive_s10_projection(
    tmp_path: Path,
) -> None:
    """The consumer cannot replace six real time roles with one convenient date."""

    _store, evidence_ref, evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="collapsed-time",
        observations=(True, True),
        threshold=1.0,
    )
    payload = _calibration_payload(evidence, evidence_ref)
    payload["observation_time"] = payload["prediction_time"]
    inputs = _minimal_generation_inputs(
        evidence=evidence,
        evidence_ref=evidence_ref,
        forecast_tier="observable_calibrated",
        calibration_status="pass",
        calibration_evidence=payload,
    )
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"
