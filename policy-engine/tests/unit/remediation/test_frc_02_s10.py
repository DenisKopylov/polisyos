"""Test-first witnesses for the FRC-02 predictive-evidence to S10 bridge.

Closure witnesses use the production-named
``RealValueOwnerGateway.produce_forecast_inputs`` path with an injected
canonical evidence resolver.  The caller supplies a typed persisted evidence
reference through the method-owner result, not a decoded mapping or derived
status/count/time fields.  The gateway/consumer must resolve the reference in
the same CAS and derive the S10 projection itself.

The raw-report guard at the bottom is characterization only.  It preserves
the FRC-01 no-fake-pass boundary and is not claimed as the new RED.
"""

from __future__ import annotations

import hashlib
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
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.artifacts import InputRef, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, from_canonical_bytes
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
    method_ref: str,
    method_version: str,
    rule_version_ref: str,
    threshold: float,
) -> dict[str, dict[str, str]]:
    """Persist the complete neutral context required by the producer."""

    binding = {
        "report_id": report_id,
        "model_spec_ref": MODEL_REF,
        "policy_spec_ref": POLICY_REF,
        "estimand": ESTIMAND,
        "method_ref": method_ref,
        "method_version": method_version,
        "rule_version_ref": rule_version_ref,
        "calibration_threshold": f"{threshold:.2f}",
    }
    specs: tuple[tuple[str, str, str, Mapping[str, object] | None], ...] = (
        ("scope_binding", report_id, "report_id", binding),
        (
            "calibration_threshold",
            f"threshold://frc02/{threshold:.2f}",
            "identity",
            {"threshold": Decimal(f"{threshold:.2f}")},
        ),
        ("observed_outcome", "observation://frc02/held-out/v1", "identity", None),
        ("prediction", "prediction://frc02/held-out/v1", "identity", None),
        (
            "evaluation_design",
            "evaluation://frc02/rolling-origin/v1",
            "identity",
            None,
        ),
        (
            "credible_evaluation",
            "evaluation-evidence://frc02/v1",
            "identity",
            None,
        ),
        ("source_lineage", "source://frc02/panel/v1", "identity", None),
        ("method_lineage", "method-lineage://frc02/ets/v1", "identity", None),
    )
    return {
        role: _persist_context_ref(
            store,
            role=role,
            report_id=report_id,
            identity=identity,
            identity_path=identity_path,
            binding=(payload_fields if role == "scope_binding" else None),
            payload_fields=(payload_fields if role != "scope_binding" else None),
        )
        for role, identity, identity_path, payload_fields in specs
    }


def _persist_report(
    tmp_path: Path,
    *,
    label: str,
    observations: tuple[bool | None, ...],
    nominal_confidence: float = 0.95,
    threshold: float = 0.5,
    method_ref: str = METHOD_REF,
    method_version: str = METHOD_VERSION,
    rule_version_ref: str = RULE_VERSION_REF,
) -> tuple[FileSystemCAS, BacktestReportRef, dict[str, dict[str, str]]]:
    """Persist a report whose held-out interval hits are recomputable."""

    store = FileSystemCAS(tmp_path / f"frc02-s10-{label}-cas")
    report_id = f"frc02-s10-{label}"
    comparisons: list[OutcomeComparison] = []
    for index, observed_hit in enumerate(observations):
        y_pred = 10.0 + index
        if observed_hit is None:
            y_true, absolute_error, ci_lower, ci_upper = y_pred, 0.0, None, None
        elif observed_hit:
            y_true, absolute_error = y_pred, 0.0
            ci_lower, ci_upper = y_pred - 0.5, y_pred + 0.5
        else:
            y_true, absolute_error = y_pred + 5.0, 5.0
            ci_lower, ci_upper = y_pred - 0.5, y_pred + 0.5
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
            "method_ref": method_ref,
            "method_version": method_version,
            "rule_version_ref": rule_version_ref,
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
        method_ref=method_ref,
        method_version=method_version,
        rule_version_ref=rule_version_ref,
        threshold=threshold,
    )
    report_ref = persist_backtest_report(
        store,
        report,
        inputs=[
            InputRef(artifact_id=ref["artifact_id"], role=role)
            for role, ref in refs.items()
        ],
    )
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
    """Build explicit predictive context with six ordered time roles."""

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
    method_ref: str = METHOD_REF,
    method_version: str = METHOD_VERSION,
    rule_version_ref: str = RULE_VERSION_REF,
    temporal_updates: Mapping[str, object] | None = None,
) -> tuple[FileSystemCAS, BacktestReportRef, Any, Any, dict[str, dict[str, str]]]:
    """Produce, persist, and load one neutral empirical evidence artifact."""

    store, report_ref, refs = _persist_report(
        tmp_path,
        label=label,
        observations=observations,
        nominal_confidence=nominal_confidence,
        threshold=threshold,
        method_ref=method_ref,
        method_version=method_version,
        rule_version_ref=rule_version_ref,
    )
    bridge = _bridge()
    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=_context(
            refs,
            threshold=threshold,
            method_ref=method_ref,
            method_version=method_version,
            rule_version_ref=rule_version_ref,
            temporal_updates=temporal_updates,
        ),
    )
    evidence_ref = bridge.persist_empirical_calibration_evidence(store, evidence)
    loaded = bridge.load_empirical_calibration_evidence(store, evidence_ref)
    assert loaded == evidence
    return store, report_ref, evidence_ref, loaded, refs


def _temporal_roles(*, shifted: bool = False) -> SimpleNamespace:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    offset = 2 if shifted else 0
    return SimpleNamespace(
        data_valid_time=start + timedelta(days=offset),
        calibration_window_start=start + timedelta(days=1 + offset),
        calibration_window_end=start + timedelta(days=2 + offset),
        policy_effective_time=start + timedelta(days=3 + offset),
        prediction_time=start + timedelta(days=4 + offset),
        observation_time=start + timedelta(days=5 + offset),
    )


def _method_result(
    *,
    evidence_ref: Any | None = None,
    temporal_roles: SimpleNamespace | None = None,
    report: Any | None = None,
    expected_rule_version_ref: str = RULE_VERSION_REF,
) -> Any:
    output: dict[str, object] = {
        "report": report
        or SimpleNamespace(
            point_estimate=1.5,
            confidence_interval=(1.0, 2.0),
            standard_error=0.2,
            confidence_level=0.95,
            diagnostics=(),
            sample_size=2,
            n_treated=0,
            n_control=0,
            pre_periods=0,
            post_periods=0,
        )
    }
    # The reference is present even for the missing-ref negative witness.  The
    # consumer must route that typed input through its resolver and fail with a
    # named reason rather than silently falling back to estimator shape.
    output["empirical_calibration_evidence_ref"] = evidence_ref
    output["expected_rule_version_ref"] = expected_rule_version_ref
    return SimpleNamespace(
        output=output,
        temporal_roles=temporal_roles or _temporal_roles(),
    )


class _CanonicalEvidenceResolver:
    """Test-injected canonical loader; runtime need not import calibration."""

    def __init__(self, store: FileSystemCAS) -> None:
        self.store = store
        self.trace: list[dict[str, object]] = []

    def __call__(self, evidence_ref: Any) -> Any:
        self.trace.append({"event": "attempt", "evidence_ref": evidence_ref})
        try:
            evidence = _bridge().load_empirical_calibration_evidence(
                self.store,
                evidence_ref,
            )
        except Exception as exc:
            self.trace.append(
                {
                    "event": "error",
                    "exception_type": type(exc).__name__,
                    "reason": str(exc),
                }
            )
            raise
        self.trace.append(
            {
                "event": "loaded",
                "evidence_ref": evidence_ref,
                "evidence": evidence,
                "nominal_confidence_level": getattr(
                    evidence, "nominal_confidence_level", None
                ),
            }
        )
        return evidence

    def resolve(self, evidence_ref: Any) -> Any:
        return self(evidence_ref)


def _produce_forecast_inputs(
    *,
    store: FileSystemCAS,
    evidence_ref: Any | None,
    method_result: Any | None = None,
    selected_method_fqn: str = METHOD_FQN,
    resolver: _CanonicalEvidenceResolver | None = None,
) -> Mapping[str, Any]:
    """Call the production-named gateway with resolver injection only."""

    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

    evidence_resolver = resolver or _CanonicalEvidenceResolver(store)
    gateway = RealValueOwnerGateway(
        repo_root=store.root,
        empirical_evidence_resolver=evidence_resolver,
    )
    return gateway.produce_forecast_inputs(
        candidate=SimpleNamespace(candidate_id="frc02-s10-candidate"),
        problem=SimpleNamespace(
            design_problem_id="frc02-s10-problem",
            outcome_of_interest=SimpleNamespace(target_variable="firm_survival"),
        ),
        world_record=SimpleNamespace(
            world_model_record_id="world_model_record_frc02_s10",
            content_hash="sha256:" + "a" * 64,
            valid_time_scope="2026-Q1",
            region_or_jurisdiction="UA",
        ),
        method_result=method_result or _method_result(evidence_ref=evidence_ref),
        selected_method_fqn=selected_method_fqn,
    )


def _assert_gateway_blocked(
    *,
    expected_code: str,
    expected_trace_event: str,
    **kwargs: Any,
) -> None:
    """Require resolver invocation and a targeted fail-closed reason."""

    resolver = kwargs.get("resolver")
    if not isinstance(resolver, _CanonicalEvidenceResolver):
        resolver = _CanonicalEvidenceResolver(kwargs["store"])
        kwargs["resolver"] = resolver
    result: Mapping[str, Any] | None = None
    captured_exception: FileNotFoundError | KeyError | ValueError | None = None
    try:
        result = _produce_forecast_inputs(**kwargs)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        captured_exception = exc
    if captured_exception is not None:
        with pytest.raises((FileNotFoundError, KeyError, ValueError)) as exc_info:
            raise captured_exception
        assert expected_code in str(exc_info.value).lower(), str(exc_info.value)
    else:
        assert result is not None
        support = result.get("forecast_support")
        assert support is not None
        assert support.forecast_tier == "blocked"
        assert result.get("forecast_calibration_record") is None
        assert expected_code in repr(result).lower(), repr(result)
    assert resolver.trace
    assert resolver.trace[0]["event"] == "attempt"
    assert sum(item["event"] == "attempt" for item in resolver.trace) == 1
    assert any(item["event"] == expected_trace_event for item in resolver.trace)


def _assert_evidence_binding(
    store: FileSystemCAS,
    record: Any,
    evidence_ref: Any,
) -> None:
    """Require typed identity, manifest schema, bytes, and non-synthetic refs."""

    source_ref = record.empirical_evidence_ref
    assert source_ref.artifact_id == evidence_ref.artifact_id
    assert source_ref.kind == "ir.empirical_calibration_evidence"
    assert source_ref.media_type == "application/json"
    manifest = store.get_manifest(evidence_ref.artifact_id)
    assert manifest.kind == source_ref.kind
    assert manifest.media_type == source_ref.media_type
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == (
        "polisyos.calibration.empirical_calibration_evidence"
    )
    assert manifest.artifact_schema.version == "1.1"
    assert manifest.integrity.sha256 == evidence_ref.artifact_id.hex
    evidence_bytes = store.get_bytes(evidence_ref.artifact_id)
    assert hashlib.sha256(evidence_bytes).hexdigest() == evidence_ref.artifact_id.hex
    evidence = _bridge().load_empirical_calibration_evidence(store, evidence_ref)
    assert (
        _ref_artifact_id(record.observed_outcome_ref)
        == str(evidence.observed_outcome_ref.artifact_id)
    )
    assert (
        _ref_artifact_id(record.prediction_ref)
        == str(evidence.prediction_ref.artifact_id)
    )
    assert (
        _ref_artifact_id(record.historical_implementation_ref)
        == str(evidence.report_ref.artifact_id)
    )
    assert (
        _ref_artifact_id(record.evaluation_design_ref)
        == str(evidence.evaluation_design_ref.artifact_id)
    )
    assert (
        _ref_artifact_id(record.credible_evaluation_evidence_ref)
        == str(evidence.credible_evaluation_evidence_ref.artifact_id)
    )
    assert (
        _ref_artifact_id(record.calibration_threshold_ref)
        == str(evidence.calibration_threshold_ref.artifact_id)
    )
    assert tuple(_ref_artifact_id(ref) for ref in record.source_lineage_refs) == tuple(
        str(ref.artifact_id) for ref in evidence.source_lineage_refs
    )
    assert tuple(_ref_artifact_id(ref) for ref in record.method_lineage_refs) == tuple(
        str(ref.artifact_id) for ref in evidence.method_lineage_refs
    )
    source_values = (
        source_ref,
        record.observed_outcome_ref,
        record.prediction_ref,
        record.historical_implementation_ref,
        record.evaluation_design_ref,
        record.credible_evaluation_evidence_ref,
        record.calibration_threshold_ref,
        *record.source_lineage_refs,
        *record.method_lineage_refs,
    )
    assert all(
        not (
            str(value).startswith("s10://")
            or str(getattr(value, "uri", "")).startswith("s10://")
        )
        for value in source_values
    )


def _ref_artifact_id(value: Any) -> str:
    """Normalize a typed artifact ref or legacy string field to its CAS id."""

    artifact_id = getattr(value, "artifact_id", None)
    return str(artifact_id) if artifact_id is not None else str(value)


def test_same_ets_shape_with_different_held_out_observations_changes_s10_suitability(
    tmp_path: Path,
) -> None:
    """Real observations, not estimator shape, determine S10 suitability."""

    (
        passing_store,
        _passing_report,
        passing_ref,
        passing_evidence,
        _,
    ) = _persist_loaded_evidence(
        tmp_path,
        label="all-hit",
        observations=(True, True),
        nominal_confidence=0.95,
        threshold=1.0,
    )
    (
        limited_store,
        _limited_report,
        limited_ref,
        _limited,
        _,
    ) = _persist_loaded_evidence(
        tmp_path,
        label="one-miss",
        observations=(True, False),
        nominal_confidence=0.95,
        threshold=1.0,
    )
    passing_resolver = _CanonicalEvidenceResolver(passing_store)
    limited_resolver = _CanonicalEvidenceResolver(limited_store)
    passing = _produce_forecast_inputs(
        store=passing_store,
        evidence_ref=passing_ref,
        resolver=passing_resolver,
    )
    limited = _produce_forecast_inputs(
        store=limited_store,
        evidence_ref=limited_ref,
        resolver=limited_resolver,
    )
    assert passing["forecast_support"].forecast_tier == "observable_calibrated"
    assert limited["forecast_support"].forecast_tier != (
        passing["forecast_support"].forecast_tier
    )
    record = passing["forecast_calibration_record"]
    limited_record = limited["forecast_calibration_record"]
    assert record is not None
    assert limited_record is not None
    assert record.numerator == 2
    assert record.denominator == 2
    assert limited_record.numerator == 1
    assert limited_record.denominator == 2
    assert limited_record.calibration_status != "pass"
    assert passing_resolver.trace[-1]["event"] == "loaded"
    assert limited_resolver.trace[-1]["event"] == "loaded"
    _assert_evidence_binding(passing_store, record, passing_ref)
    assert str(record.empirical_evidence_ref.artifact_id) == str(
        passing_ref.artifact_id
    )
    assert record.prediction_time == passing_evidence.prediction_time
    assert record.observation_time == passing_evidence.observation_time
    assert record.policy_effective_time == passing_evidence.policy_effective_time
    assert record.data_valid_time == passing_evidence.data_valid_time
    assert record.calibration_window_start == passing_evidence.calibration_window_start
    assert record.calibration_window_end == passing_evidence.calibration_window_end
    assert len(
        {
            record.prediction_time,
            record.observation_time,
            record.policy_effective_time,
            record.data_valid_time,
            record.calibration_window_start,
            record.calibration_window_end,
        }
    ) == 6


def test_nominal_confidence_only_does_not_change_s10_suitability(
    tmp_path: Path,
) -> None:
    """Changing nominal confidence without new observations cannot change the result."""

    low_store, low_report_ref, low_ref, low_evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="nominal-80",
        observations=(True, False),
        nominal_confidence=0.80,
        threshold=0.5,
    )
    high_store, high_report_ref, high_ref, high_evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="nominal-95",
        observations=(True, False),
        nominal_confidence=0.95,
        threshold=0.5,
    )
    low_report = load_backtest_report(low_store, low_report_ref)
    high_report = load_backtest_report(high_store, high_report_ref)
    assert low_report.scenarios[0].nominal_confidence_level == pytest.approx(0.80)
    assert high_report.scenarios[0].nominal_confidence_level == pytest.approx(0.95)
    assert low_ref.artifact_id != high_ref.artifact_id
    low_payload = from_canonical_bytes(low_store.get_bytes(low_ref.artifact_id))
    high_payload = from_canonical_bytes(high_store.get_bytes(high_ref.artifact_id))
    assert low_payload["nominal_confidence_level"] == pytest.approx(0.80)
    assert high_payload["nominal_confidence_level"] == pytest.approx(0.95)
    assert low_evidence.nominal_confidence_level == pytest.approx(0.80)
    assert high_evidence.nominal_confidence_level == pytest.approx(0.95)
    low_resolver = _CanonicalEvidenceResolver(low_store)
    high_resolver = _CanonicalEvidenceResolver(high_store)
    low = _produce_forecast_inputs(
        store=low_store,
        evidence_ref=low_ref,
        resolver=low_resolver,
    )
    high = _produce_forecast_inputs(
        store=high_store,
        evidence_ref=high_ref,
        resolver=high_resolver,
    )
    assert (
        low["forecast_support"].forecast_tier
        == high["forecast_support"].forecast_tier
    )
    low_record = low.get("forecast_calibration_record")
    high_record = high.get("forecast_calibration_record")
    assert low_record is not None
    assert high_record is not None
    assert low_record.numerator == high_record.numerator == 1
    assert low_record.denominator == high_record.denominator == 2
    assert low_record.pass_rate == high_record.pass_rate == pytest.approx(0.5)
    assert low_record.calibration_status == high_record.calibration_status
    assert low_resolver.trace[-1]["event"] == "loaded"
    assert high_resolver.trace[-1]["event"] == "loaded"
    assert low_resolver.trace[-1]["nominal_confidence_level"] == pytest.approx(0.80)
    assert high_resolver.trace[-1]["nominal_confidence_level"] == pytest.approx(0.95)
    _assert_evidence_binding(low_store, low_record, low_ref)
    _assert_evidence_binding(high_store, high_record, high_ref)


def test_legacy_v1_0_evidence_loads_without_nominal_and_preserves_cas_bytes(
    tmp_path: Path,
) -> None:
    """Legacy evidence remains readable without being rewritten or enriched."""

    store, _report, _current_ref, evidence, refs = _persist_loaded_evidence(
        tmp_path,
        label="legacy-v1-0",
        observations=(True, True),
        nominal_confidence=0.95,
        threshold=1.0,
    )
    bridge = _bridge()
    legacy_payload = evidence.model_dump(mode="json")
    legacy_payload["schema_version"] = "1.0"
    legacy_payload.pop("nominal_confidence_level", None)
    legacy_ref_payload = put_json_artifact(
        store,
        legacy_payload,
        kind="ir.empirical_calibration_evidence",
        schema_name="polisyos.calibration.empirical_calibration_evidence",
        schema_version="1.0",
        inputs=[
            {
                "artifact_id": str(evidence.report_ref.artifact_id),
                "role": "backtest_report",
            },
            *(
                {"artifact_id": ref["artifact_id"], "role": role}
                for role, ref in refs.items()
            ),
        ],
        canon_spec=CanonSpec(forbid_floats=False),
    )
    legacy_ref = bridge.EmpiricalCalibrationEvidenceRef.model_validate(
        legacy_ref_payload
    )
    before = store.get_bytes(legacy_ref.artifact_id)
    before_sha = hashlib.sha256(before).hexdigest()

    loaded = bridge.load_empirical_calibration_evidence(store, legacy_ref)

    after = store.get_bytes(legacy_ref.artifact_id)
    expected_payload = evidence.model_dump(mode="json")
    expected_payload["schema_version"] = "1.0"
    expected_payload["nominal_confidence_level"] = None
    assert loaded.model_dump(mode="json") == expected_payload
    assert loaded.nominal_confidence_level is None
    assert loaded.may_not_use_for == evidence.may_not_use_for
    assert loaded.recomputed_numerator == evidence.recomputed_numerator
    assert loaded.recomputed_denominator == evidence.recomputed_denominator
    assert after == before
    assert hashlib.sha256(after).hexdigest() == before_sha
    with pytest.raises(
        ValueError,
        match="legacy empirical calibration evidence must not be repersisted",
    ):
        bridge.persist_empirical_calibration_evidence(store, loaded)


def test_predictive_denials_and_non_causal_family_survive_s10_projection(
    tmp_path: Path,
) -> None:
    """A bounded S10 projection cannot launder predictive producer denials."""

    store, _report, evidence_ref, _evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="denials",
        observations=(True, True),
        threshold=1.0,
    )
    resolver = _CanonicalEvidenceResolver(store)
    result = _produce_forecast_inputs(
        store=store,
        evidence_ref=evidence_ref,
        resolver=resolver,
    )
    support = result["forecast_support"]
    assert support.method_family == "foundry_forecast"
    assert set(support.may_not_use_for) >= PREDICTIVE_AUTHORITY_DENIALS
    assert set(support.authority_boundary.authoritative_for) <= {
        "forecast_support_tiering",
        "observable_subset_calibration",
    }
    record = result.get("forecast_calibration_record")
    assert record is not None
    assert set(record.may_not_use_for) >= PREDICTIVE_AUTHORITY_DENIALS
    assert resolver.trace[-1]["event"] == "loaded"


@pytest.mark.parametrize(
    ("bad_ref", "expected_code"),
    [
        pytest.param("missing", "empirical_evidence_ref_missing", id="missing"),
        pytest.param(
            "wrong_kind",
            "empirical_evidence_ref_kind_mismatch",
            id="wrong_kind",
        ),
        pytest.param("foreign", "empirical_evidence_ref_unresolved", id="foreign"),
    ],
)
def test_missing_wrong_kind_or_foreign_evidence_ref_fails_closed(
    tmp_path: Path,
    bad_ref: str,
    expected_code: str,
) -> None:
    """The gateway must resolve the typed evidence ref in its injected CAS."""

    store, report_ref, evidence_ref, _evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label=f"bad-ref-{bad_ref}",
        observations=(True, True),
        threshold=1.0,
    )
    if bad_ref == "missing":
        invalid_ref: Any = None
    elif bad_ref == "wrong_kind":
        invalid_ref = report_ref
    else:
        _foreign_store, _foreign_report, invalid_ref, _foreign_evidence, _ = (
            _persist_loaded_evidence(
                tmp_path,
                label="foreign-source",
                observations=(True, True),
                threshold=1.0,
            )
        )
    _assert_gateway_blocked(
        expected_code=expected_code,
        expected_trace_event="error",
        store=store,
        evidence_ref=invalid_ref,
        resolver=_CanonicalEvidenceResolver(store),
    )
    assert evidence_ref is not invalid_ref


def test_corrupt_existing_evidence_bytes_fail_closed_at_gateway(
    tmp_path: Path,
) -> None:
    """Changing bytes behind an existing evidence ref cannot yield S10 support."""

    store, _report, evidence_ref, _evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="corrupt-bytes",
        observations=(True, True),
        threshold=1.0,
    )
    blob_path, _manifest_path = store._paths(evidence_ref.artifact_id)
    blob_path.write_bytes(b'{"schema_version":"1.0","corrupt":true}')
    _assert_gateway_blocked(
        expected_code="empirical_evidence_ref_integrity_mismatch",
        expected_trace_event="error",
        store=store,
        evidence_ref=evidence_ref,
        resolver=_CanonicalEvidenceResolver(store),
    )


@pytest.mark.parametrize(
    (
        "label",
        "method_ref",
        "method_version",
        "rule_version_ref",
        "expected_code",
    ),
    [
        pytest.param(
            "method-mismatch",
            "forecasting.univariate.other",
            "9.9.9",
            RULE_VERSION_REF,
            "empirical_evidence_method_mismatch",
            id=(
                "method-mismatch-forecasting.univariate.other-9.9.9-"
                "rolling-origin-residual-conformal.v1"
            ),
        ),
        pytest.param(
            "rule-mismatch",
            METHOD_REF,
            METHOD_VERSION,
            "rolling-origin-residual-conformal.v9",
            "empirical_evidence_rule_mismatch",
            id=(
                "rule-mismatch-forecasting.univariate.exponential_smoothing-"
                "1.0.0-rolling-origin-residual-conformal.v9"
            ),
        ),
    ],
)
def test_method_or_rule_mismatch_in_persisted_evidence_fails_closed(
    tmp_path: Path,
    label: str,
    method_ref: str,
    method_version: str,
    rule_version_ref: str,
    expected_code: str,
) -> None:
    """The gateway compares loaded method/rule identity with its request."""

    store, _report, evidence_ref, _evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label=label,
        observations=(True, True),
        threshold=1.0,
        method_ref=method_ref,
        method_version=method_version,
        rule_version_ref=rule_version_ref,
    )
    _assert_gateway_blocked(
        expected_code=expected_code,
        expected_trace_event="loaded",
        store=store,
        evidence_ref=evidence_ref,
        selected_method_fqn=METHOD_FQN,
        resolver=_CanonicalEvidenceResolver(store),
        method_result=_method_result(
            evidence_ref=evidence_ref,
            expected_rule_version_ref=RULE_VERSION_REF,
        ),
    )


def test_temporal_role_mismatch_in_persisted_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    """A differently bound persisted time context cannot be rebound silently."""

    shifted_start = datetime(2026, 1, 3, tzinfo=UTC)
    temporal_updates = {
        "data_valid_time": shifted_start,
        "calibration_window_start": shifted_start + timedelta(days=1),
        "calibration_window_end": shifted_start + timedelta(days=2),
        "policy_effective_time": shifted_start + timedelta(days=3),
        "prediction_time": shifted_start + timedelta(days=4),
        "observation_time": shifted_start + timedelta(days=5),
    }
    store, _report, evidence_ref, _evidence, _ = _persist_loaded_evidence(
        tmp_path,
        label="time-mismatch",
        observations=(True, True),
        threshold=1.0,
        temporal_updates=temporal_updates,
    )
    _assert_gateway_blocked(
        expected_code="empirical_evidence_time_mismatch",
        expected_trace_event="loaded",
        store=store,
        evidence_ref=evidence_ref,
        resolver=_CanonicalEvidenceResolver(store),
        method_result=_method_result(
            evidence_ref=evidence_ref,
            temporal_roles=_temporal_roles(),
            expected_rule_version_ref=RULE_VERSION_REF,
        ),
    )


def test_raw_causal_effect_report_remains_non_positive_characterization() -> None:
    """The old raw report path remains blocked without persisted empirical evidence."""

    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

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
    inputs = RealValueOwnerGateway().produce_forecast_inputs(
        candidate=SimpleNamespace(candidate_id="frc02-raw-report-candidate"),
        problem=problem,
        world_record=world_record,
        method_result=_method_result(
            report=CausalEffectReport(
                method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
                estimand="ATT",
                point_estimate=1.5,
                standard_error=0.2,
                confidence_interval=(1.0, 2.0),
                inference_method="did",
                diagnostics=[],
                sample_size=100,
                n_treated=50,
                n_control=50,
                pre_periods=4,
                post_periods=4,
            )
        ),
        selected_method_fqn="causal.inference.difference_in_differences@1.0.0",
    )
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"
