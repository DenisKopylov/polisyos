"""RED witnesses for the FRC-02 empirical calibration bridge.

The tests deliberately begin at a persisted ``BacktestReport`` and cross the
real CAS boundary.  They keep the evidence predictive-only: observed interval
hits are neutral empirical evidence, not causal effect authority or an S10
promotion.  The bridge import is resolved inside test execution so this
test-only RED commit still collects while the producer module is absent.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
METHOD_VERSION = "1.0.0"
RULE_VERSION_REF = "rolling-origin-residual-conformal.v1"

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
    """Resolve the real producer only when a test invokes the bridge seam."""

    return importlib.import_module("polisyos.calibration.forecast_bridge")


def _persist_context_ref(
    store: FileSystemCAS,
    *,
    role: str,
    report_id: str,
    identity: str,
    identity_path: str = "identity",
    binding: Mapping[str, object] | None = None,
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
    model_ref: str,
    policy_ref: str,
) -> dict[str, dict[str, str]]:
    """Persist the complete neutral context required by the producer."""

    binding = {
        "report_id": report_id,
        "model_spec_ref": model_ref,
        "policy_spec_ref": policy_ref,
        "estimand": ESTIMAND,
        "method_ref": METHOD_REF,
        "method_version": METHOD_VERSION,
        "rule_version_ref": RULE_VERSION_REF,
    }
    refs: dict[str, dict[str, str]] = {
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
            identity="threshold://frc02/0.50",
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
    return refs


def _persist_report(
    tmp_path: Path,
    *,
    label: str,
    observations: tuple[bool | None, ...],
    nominal_confidence: float = 0.95,
) -> tuple[FileSystemCAS, BacktestReportRef, BacktestReport, dict[str, dict[str, str]]]:
    """Persist a report whose interval observations can be recomputed exactly."""

    store = FileSystemCAS(tmp_path / f"frc02-{label}-cas")
    report_id = f"frc02-bridge-{label}"
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

    denominator = sum(observed_hit is not None for observed_hit in observations)
    numerator = sum(observed_hit is True for observed_hit in observations)
    requested = len(observations)
    scenario = BacktestScenario(
        scenario_id="frc02-bridge-scenario",
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
    metadata: dict[str, object] = {
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
    }
    report = BacktestReport(
        schema_version="1.0",
        report_id=report_id,
        model_spec_ref=MODEL_REF,
        policy_spec_ref=POLICY_REF,
        scenarios=[scenario],
        overall_coverage_probability=numerator / denominator if denominator else None,
        n_scenarios=1,
        n_metrics_evaluated=requested,
        metadata=metadata,
    )
    refs = _persist_context_refs(
        store,
        report_id=report_id,
        model_ref=MODEL_REF,
        policy_ref=POLICY_REF,
    )
    inputs = [
        InputRef(artifact_id=ref["artifact_id"], role=role)
        for role, ref in refs.items()
    ]
    report_ref = persist_backtest_report(store, report, inputs=inputs)
    persisted = load_backtest_report(store, report_ref)
    return store, report_ref, persisted, refs


def _context(
    refs: dict[str, dict[str, str]],
    *,
    threshold: float = 0.5,
    model_ref: str = MODEL_REF,
    policy_ref: str = POLICY_REF,
) -> Any:
    """Build the explicit predictive context with six independent time roles."""

    bridge = _bridge()
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def typed_ref(role: str) -> Any:
        return bridge.EvidenceArtifactRef.model_validate(refs[role])

    return bridge.EmpiricalCalibrationContext.model_validate(
        {
            "model_spec_ref": model_ref,
            "policy_spec_ref": policy_ref,
            "estimand": ESTIMAND,
            "method_ref": METHOD_REF,
            "method_version": METHOD_VERSION,
            "rule_version_ref": RULE_VERSION_REF,
            "calibration_threshold": threshold,
            "scope_binding_ref": typed_ref("scope_binding"),
            "calibration_threshold_ref": typed_ref("calibration_threshold"),
            "observed_outcome_ref": typed_ref("observed_outcome"),
            "prediction_ref": typed_ref("prediction"),
            "evaluation_design_ref": typed_ref("evaluation_design"),
            "credible_evaluation_evidence_ref": typed_ref("credible_evaluation"),
            "source_lineage_refs": (typed_ref("source_lineage"),),
            "method_lineage_refs": (typed_ref("method_lineage"),),
            "prediction_time": start,
            "observation_time": start + timedelta(days=1),
            "policy_effective_time": start + timedelta(days=2),
            "data_valid_time": start + timedelta(days=3),
            "calibration_window_start": start - timedelta(days=30),
            "calibration_window_end": start - timedelta(days=1),
            "evidence_origin": "persisted_backtest",
        }
    )


class _StoreOverride:
    """Read-only CAS facade used to falsify manifest or content binding."""

    def __init__(
        self,
        store: FileSystemCAS,
        *,
        manifest: object | None = None,
        bytes_override: bytes | None = None,
    ) -> None:
        self._store = store
        self._manifest = manifest
        self._bytes_override = bytes_override

    def get_manifest(self, artifact_id: object) -> object:
        if self._manifest is not None:
            return self._manifest
        return self._store.get_manifest(artifact_id)

    def get_bytes(self, artifact_id: object) -> bytes:
        if self._bytes_override is not None:
            return self._bytes_override
        return self._store.get_bytes(artifact_id)


def test_persisted_backtest_report_readback_produces_neutral_empirical_interval_hit_evidence(
    tmp_path: Path,
) -> None:
    """Observed bounds are recomputed from the persisted report, not self-attested flags."""

    store, report_ref, persisted, refs = _persist_report(
        tmp_path,
        label="neutral",
        observations=(True, False),
    )
    bridge = _bridge()
    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=_context(refs),
    )

    assert persisted.report_id == "frc02-bridge-neutral"
    assert evidence.evidence_kind == "observed_interval_comparisons"
    assert evidence.empirical_observations_available is True
    assert evidence.context_bound is True
    assert evidence.usable_for_calibration is True
    assert evidence.floor_passed is True
    assert evidence.recomputed_numerator == 1
    assert evidence.recomputed_denominator == 2
    assert evidence.recomputed_pass_rate == pytest.approx(0.5)
    assert evidence.persisted_numerator == 1
    assert evidence.persisted_denominator == 2
    assert evidence.observed_outcome_ref.identity_value == (
        "observation://frc02/held-out/v1"
    )
    assert evidence.evidence_origin == "persisted_backtest"
    assert evidence.failure_codes == ()

    evidence_ref = bridge.persist_empirical_calibration_evidence(store, evidence)
    readback = bridge.load_empirical_calibration_evidence(store, evidence_ref)
    assert readback == evidence


def test_observed_comparisons_change_empirical_admission_with_same_nominal_confidence(
    tmp_path: Path,
) -> None:
    """The same nominal level admits only the report whose observations meet the floor."""

    pass_store, pass_ref, _pass_report, pass_refs = _persist_report(
        tmp_path,
        label="all-hit",
        observations=(True, True),
        nominal_confidence=0.95,
    )
    limited_store, limited_ref, _limited_report, limited_refs = _persist_report(
        tmp_path,
        label="one-miss",
        observations=(True, False),
        nominal_confidence=0.95,
    )

    passing = _bridge().produce_empirical_calibration_evidence(
        pass_store,
        pass_ref,
        context=_context(pass_refs, threshold=1.0),
    )
    limited = _bridge().produce_empirical_calibration_evidence(
        limited_store,
        limited_ref,
        context=_context(limited_refs, threshold=1.0),
    )

    assert passing.recomputed_pass_rate == 1.0
    assert passing.usable_for_calibration is True
    assert limited.recomputed_pass_rate == 0.5
    assert limited.usable_for_calibration is False
    assert limited.floor_passed is False
    assert "calibration_floor_not_met" in limited.failure_codes


def test_nominal_confidence_without_observations_is_not_empirical_evidence(
    tmp_path: Path,
) -> None:
    """A nominal confidence field cannot create an empirical denominator."""

    store, report_ref, persisted, refs = _persist_report(
        tmp_path,
        label="nominal-only",
        observations=(None,),
        nominal_confidence=0.95,
    )
    evidence = _bridge().produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=_context(refs),
    )

    assert persisted.scenarios[0].nominal_confidence_level == pytest.approx(0.95)
    assert evidence.evidence_kind == "unavailable"
    assert evidence.empirical_observations_available is False
    assert evidence.recomputed_denominator == 0
    assert evidence.recomputed_pass_rate is None
    assert evidence.usable_for_calibration is False
    assert evidence.floor_passed is False
    assert "zero_observation_denominator" in evidence.failure_codes
    assert "nominal_confidence_only" in evidence.failure_codes


def test_forged_report_manifest_or_content_binding_is_refused_before_persistence_readback(
    tmp_path: Path,
) -> None:
    """Forged projections and report bytes cannot cross the bridge boundary."""

    store, report_ref, _persisted, refs = _persist_report(
        tmp_path,
        label="binding",
        observations=(True,),
    )
    bridge = _bridge()
    context = _context(refs)

    with pytest.raises(ValueError, match="kind|manifest"):
        bridge.produce_empirical_calibration_evidence(
            store,
            report_ref.model_copy(update={"kind": "ir.not_a_backtest_report"}),
            context=context,
        )

    forged_manifest = store.get_manifest(report_ref.artifact_id).model_copy(
        update={"kind": "ir.not_a_backtest_report"}
    )
    with pytest.raises(ValueError, match="manifest"):
        bridge.produce_empirical_calibration_evidence(
            _StoreOverride(store, manifest=forged_manifest),
            report_ref,
            context=context,
        )

    with pytest.raises(ValueError, match="content binding"):
        bridge.produce_empirical_calibration_evidence(
            _StoreOverride(store, bytes_override=b"not-the-report"),
            report_ref,
            context=context,
        )

    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=context,
    )
    forged_evidence = evidence.model_copy(
        update={"recomputed_numerator": 0, "usable_for_calibration": False}
    )
    with pytest.raises(ValueError, match="not reproducible"):
        bridge.persist_empirical_calibration_evidence(store, forged_evidence)
