"""RED witnesses for the FRC-02 empirical calibration bridge.

The tests deliberately begin at a persisted ``BacktestReport`` and cross the
real CAS boundary.  They keep the evidence predictive-only: observed interval
hits are neutral empirical evidence, not causal effect authority or an S10
promotion.  The bridge import is resolved inside test execution so this
test-only RED commit still collects while the producer module is absent.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    OutcomeComparison,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts import InputRef, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import BacktestReportRef

MODEL_REF = "model://frc02/ets/v1"
POLICY_REF = "policy://frc02/ets/v1"
ESTIMAND = "predictive_interval_coverage"
METHOD_REF = "forecasting.univariate.exponential_smoothing"
METHOD_VERSION = "1.0.0"
RULE_VERSION_REF = "rolling-origin-residual-conformal.v1"
PREDICTIVE_AUTHORITY_SCOPE = "predictive_only"
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
    """Resolve the real producer only when a test invokes the bridge seam."""

    return importlib.import_module("polisyos.calibration.forecast_bridge")


class _WriteSpyCAS(FileSystemCAS):
    """Record canonical CAS writes while retaining the real filesystem store."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.write_calls: list[str] = []
        super().__init__(*args, **kwargs)

    def put_bytes(
        self,
        data: bytes,
        opts: Any,
        *,
        return_selected_profile: bool = False,
    ) -> Any:
        self.write_calls.append(f"put_bytes:{opts.kind}")
        if return_selected_profile:
            return super().put_bytes(data, opts, return_selected_profile=True)
        return super().put_bytes(data, opts)

    def put_json(
        self,
        obj: object,
        opts: Any,
        canon_spec: Any = None,
        *,
        return_selected_profile: bool = False,
    ) -> Any:
        self.write_calls.append(f"put_json:{opts.kind}")
        if return_selected_profile:
            return super().put_json(obj, opts, canon_spec=canon_spec, return_selected_profile=True)
        return super().put_json(obj, opts, canon_spec=canon_spec)

    def clear_write_trace(self) -> None:
        self.write_calls.clear()

    def artifact_ids_snapshot(self) -> frozenset[str]:
        return frozenset(str(artifact_id) for artifact_id in self.iter_artifact_ids())


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
        _ensure_ir_artifact_store(store),
        payload,
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        return_selected_profile=True,
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
    threshold: float = 0.5,
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
        "calibration_threshold": f"{threshold:.2f}",
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
    return refs


def _persist_report_into_store(
    store: FileSystemCAS,
    *,
    label: str,
    observations: tuple[bool | None, ...],
    nominal_confidence: float = 0.95,
    threshold: float = 0.5,
) -> tuple[BacktestReportRef, BacktestReport, dict[str, dict[str, str]]]:
    """Persist a report whose interval observations can be recomputed exactly."""

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
        "temporal_roles": {name: value.isoformat() for name, value in _temporal_roles().items()},
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
        threshold=threshold,
    )
    inputs = [
        InputRef(
            artifact_id=ref["artifact_id"],
            role=role,
            manifest_profile_sha256=ref.get("manifest_profile_sha256"),
        )
        for role, ref in refs.items()
    ]
    report_ref = persist_backtest_report(_ensure_ir_artifact_store(store), report, inputs=inputs)
    persisted = load_backtest_report(_ensure_ir_artifact_store(store), report_ref)
    return report_ref, persisted, refs


def _persist_report(
    tmp_path: Path,
    *,
    label: str,
    observations: tuple[bool | None, ...],
    nominal_confidence: float = 0.95,
    threshold: float = 0.5,
) -> tuple[_WriteSpyCAS, BacktestReportRef, BacktestReport, dict[str, dict[str, str]]]:
    """Create an isolated real CAS with a fully persisted backtest report."""

    store = _WriteSpyCAS(tmp_path / f"frc02-{label}-cas")
    report_ref, persisted, refs = _persist_report_into_store(
        store,
        label=label,
        observations=observations,
        nominal_confidence=nominal_confidence,
        threshold=threshold,
    )
    return store, report_ref, persisted, refs


def _temporal_roles() -> dict[str, datetime]:
    """Return the six fixed time roles shared by this persisted report fixture."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "data_valid_time": start,
        "calibration_window_start": start + timedelta(days=1),
        "calibration_window_end": start + timedelta(days=2),
        "policy_effective_time": start + timedelta(days=3),
        "prediction_time": start + timedelta(days=4),
        "observation_time": start + timedelta(days=5),
    }


def _context(
    refs: dict[str, dict[str, str]],
    *,
    threshold: float = 0.5,
    model_ref: str = MODEL_REF,
    policy_ref: str = POLICY_REF,
    method_ref: str = METHOD_REF,
    method_version: str = METHOD_VERSION,
    rule_version_ref: str = RULE_VERSION_REF,
    temporal_updates: Mapping[str, object] | None = None,
) -> Any:
    """Build the explicit predictive context with six independent time roles."""

    bridge = _bridge()

    def typed_ref(role: str) -> Any:
        return bridge.EvidenceArtifactRef.model_validate(refs[role])

    payload: dict[str, object] = {
        "model_spec_ref": model_ref,
        "policy_spec_ref": policy_ref,
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
        "evidence_origin": "persisted_backtest",
    }
    # The six roles have distinct meanings and an explicit causal order:
    # data_valid < calibration_start < calibration_end <= prediction < observation.
    payload.update(_temporal_roles())
    payload.update(temporal_updates or {})
    return bridge.EmpiricalCalibrationContext.model_validate(payload)


class _StoreOverride:
    """Read-only CAS facade used to falsify manifest or content binding."""

    def __init__(
        self,
        store: FileSystemCAS,
        *,
        manifest: object | None = None,
        bytes_override: bytes | None = None,
        manifest_overrides: Mapping[str, object] | None = None,
        bytes_overrides: Mapping[str, bytes] | None = None,
    ) -> None:
        self._store = store
        self._reader = _ensure_ir_artifact_store(store)
        self._manifest = manifest
        self._bytes_override = bytes_override
        self._manifest_overrides = dict(manifest_overrides or {})
        self._bytes_overrides = dict(bytes_overrides or {})

    @staticmethod
    def _artifact_key(selector: object) -> str:
        if isinstance(selector, Mapping):
            artifact_id = selector.get("artifact_id", selector)
        else:
            artifact_id = getattr(selector, "artifact_id", selector)
        return str(artifact_id)

    def get_manifest(self, artifact_id: object) -> object:
        artifact_key = self._artifact_key(artifact_id)
        if artifact_key in self._manifest_overrides:
            return self._manifest_overrides[artifact_key]
        if self._manifest is not None:
            return self._manifest
        return self._reader.get_manifest(artifact_id)

    def get_bytes(self, artifact_id: object) -> bytes:
        artifact_key = self._artifact_key(artifact_id)
        if artifact_key in self._bytes_overrides:
            return self._bytes_overrides[artifact_key]
        if self._bytes_override is not None:
            return self._bytes_override
        return self._reader.get_bytes(artifact_id)


def _assert_rejected_without_write(
    store: _WriteSpyCAS,
    action: Callable[[], Any],
) -> None:
    """Require an invalid input to reject or remain unusable before any CAS write."""

    before = store.artifact_ids_snapshot()
    store.clear_write_trace()
    try:
        result = action()
    except ValueError:
        result = None
    else:
        assert result.usable_for_calibration is False
        assert result.floor_passed is False
        assert result.failure_codes
    assert store.write_calls == []
    assert store.artifact_ids_snapshot() == before


def _persist_contradictory_projection(
    store: FileSystemCAS,
    *,
    report: BacktestReport,
    refs: dict[str, dict[str, str]],
) -> BacktestReportRef:
    """Persist a report whose counters and flags lie about its stored bounds."""

    original = report.scenarios[0]
    forged_comparisons = [
        comparison.model_copy(update={"within_ci": True})
        for comparison in original.outcome_comparisons
    ]
    forged_scenario = original.model_copy(
        update={
            "outcome_comparisons": forged_comparisons,
            "interval_available_count": len(forged_comparisons),
            "interval_evaluated_count": len(forged_comparisons),
            "interval_hit_count": len(forged_comparisons),
            "interval_availability": 1.0,
            "interval_hit_rate": 1.0,
        }
    )
    forged_metadata = dict(report.metadata)
    forged_metadata.update(
        {
            "calibration_numerator": len(forged_comparisons),
            "calibration_denominator": len(forged_comparisons),
            "interval_hit_count": len(forged_comparisons),
            "interval_evaluated_count": len(forged_comparisons),
        }
    )
    forged_report = report.model_copy(
        update={
            "scenarios": [forged_scenario],
            "overall_coverage_probability": 1.0,
            "metadata": forged_metadata,
        }
    )
    inputs = [
        InputRef(
            artifact_id=ref["artifact_id"],
            role=role,
            manifest_profile_sha256=ref.get("manifest_profile_sha256"),
        )
        for role, ref in refs.items()
    ]
    return persist_backtest_report(_ensure_ir_artifact_store(store), forged_report, inputs=inputs)


def test_context_sibling_manifest_profile_for_same_bytes_is_not_report_basis(
    tmp_path: Path,
) -> None:
    """Same report bytes under a sibling context profile do not match the declared report edge."""

    store, report_ref, _persisted, refs = _persist_report(
        tmp_path,
        label="sibling-context-profile",
        observations=(True, True),
    )
    bridge = _bridge()
    context = _context(refs)
    original = context.observed_outcome_ref
    original_selector = bridge._store_selector_for_ref(original)
    ir_store = _ensure_ir_artifact_store(store)
    original_manifest = ir_store.get_manifest(original_selector)
    original_bytes = ir_store.get_bytes(original_selector)
    sibling = store.put_bytes(
        original_bytes,
        PutOptions(
            kind=original_manifest.kind,
            media_type=original_manifest.media_type,
            schema=original_manifest.artifact_schema,
            producer=ProducerInfo(component="test.sibling-context-view", version="1.0"),
            inputs=original_manifest.inputs,
        ),
        return_selected_profile=True,
    )
    assert str(sibling.artifact_id) == str(original.artifact_id)
    assert sibling.manifest_profile_sha256 != original.manifest_profile_sha256
    assert store.get_bytes(sibling) == original_bytes

    sibling_ref = original.model_copy(
        update={"manifest_profile_sha256": sibling.manifest_profile_sha256}
    )
    sibling_context = context.model_copy(update={"observed_outcome_ref": sibling_ref})
    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=sibling_context,
    )

    assert "reference_report_profile_mismatch" in evidence.failure_codes
    assert "report_context_input_edges_mismatch" in evidence.failure_codes
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False
    assert evidence.floor_passed is False


def test_profileless_report_ref_is_not_a_producer_selected_basis(tmp_path: Path) -> None:
    store, report_ref, _persisted, refs = _persist_report(
        tmp_path, label="profileless-report-ref", observations=(True, True)
    )
    bridge = _bridge()
    profileless = report_ref.model_copy(update={"manifest_profile_sha256": None})

    evidence = bridge.produce_empirical_calibration_evidence(
        store, profileless, context=_context(refs)
    )

    assert "report_profile_not_established" in evidence.failure_codes
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False
    with pytest.raises(ValueError, match="blocked empirical calibration evidence"):
        bridge.persist_empirical_calibration_evidence(store, evidence)


def test_profileless_context_ref_is_not_selected_report_basis(tmp_path: Path) -> None:
    store, report_ref, _persisted, refs = _persist_report(
        tmp_path, label="profileless-context-ref", observations=(True, True)
    )
    bridge = _bridge()
    context = _context(refs)
    observed = context.observed_outcome_ref
    profileless = observed.model_copy(update={"manifest_profile_sha256": None})

    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=context.model_copy(update={"observed_outcome_ref": profileless}),
    )

    assert "reference_report_profile_not_established" in evidence.failure_codes
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False


def test_missing_report_input_profile_does_not_satisfy_full_basis(tmp_path: Path) -> None:
    store, report_ref, _persisted, refs = _persist_report(
        tmp_path, label="missing-report-input-profile", observations=(True, True)
    )
    bridge = _bridge()
    context = _context(refs)
    ir_store = _ensure_ir_artifact_store(store)
    manifest = ir_store.get_manifest(report_ref)
    original_bytes = ir_store.get_bytes(report_ref)
    inputs = [
        item.model_copy(update={"manifest_profile_sha256": None})
        if item.role == "observed_outcome"
        else item
        for item in manifest.inputs
    ]
    missing_input_profile_ref = store.put_bytes(
        original_bytes,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            env=manifest.env,
            inputs=inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert missing_input_profile_ref.manifest_profile_sha256 is not None
    selected_manifest = store.get_manifest_by_profile(
        missing_input_profile_ref.artifact_id,
        missing_input_profile_ref.manifest_profile_sha256,
    )
    # The fixture changes only the selected input-edge profile and the new
    # manifest timestamp; every other report-basis field remains source-bound.
    assert selected_manifest == manifest.model_copy(
        update={"inputs": inputs, "created_at": selected_manifest.created_at}
    )
    assert selected_manifest.canon == manifest.canon
    assert str(missing_input_profile_ref.artifact_id) == str(report_ref.artifact_id)
    assert missing_input_profile_ref.manifest_profile_sha256 != report_ref.manifest_profile_sha256
    assert selected_manifest.kind == manifest.kind
    assert selected_manifest.media_type == manifest.media_type
    assert selected_manifest.artifact_schema == manifest.artifact_schema
    selected_edges = [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in selected_manifest.inputs
    ]
    expected_edges = [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in inputs
    ]
    assert selected_edges == expected_edges
    original_profile_edges = [item for item in manifest.inputs if item.role == "observed_outcome"]
    assert len(original_profile_edges) == 1
    assert original_profile_edges[0].manifest_profile_sha256 is not None
    missing_profile_edges = [
        item for item in selected_manifest.inputs if item.role == "observed_outcome"
    ]
    assert len(missing_profile_edges) == 1
    assert missing_profile_edges[0].manifest_profile_sha256 is None
    assert all(
        item.manifest_profile_sha256 is not None
        for item in selected_manifest.inputs
        if item.role != "observed_outcome"
    )
    assert store.get_bytes(missing_input_profile_ref) == original_bytes

    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        BacktestReportRef.model_validate(missing_input_profile_ref.model_dump(mode="json")),
        context=context,
    )
    assert "reference_report_profile_mismatch" in evidence.failure_codes
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False


def test_legacy_profileless_evidence_keeps_historical_id_role_semantics(
    tmp_path: Path,
) -> None:
    store, report_ref, _persisted, refs = _persist_report(
        tmp_path, label="legacy-profileless-evidence", observations=(True, True)
    )
    bridge = _bridge()
    evidence = bridge.produce_empirical_calibration_evidence(
        store, report_ref, context=_context(refs)
    )
    payload = evidence.model_dump(mode="json")
    payload["schema_version"] = "1.1"

    def remove_profiles(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: remove_profiles(item)
                for key, item in value.items()
                if key != "manifest_profile_sha256"
            }
        if isinstance(value, list):
            return [remove_profiles(item) for item in value]
        return value

    payload = remove_profiles(payload)
    assert isinstance(payload, dict)
    legacy_inputs = [
        InputRef(artifact_id=report_ref.artifact_id, role="backtest_report"),
        *(InputRef(artifact_id=ref["artifact_id"], role=role) for role, ref in refs.items()),
    ]
    persisted_ref = put_json_artifact(
        _ensure_ir_artifact_store(store),
        payload,
        kind=bridge.EVIDENCE_KIND,
        schema_name=bridge.EVIDENCE_SCHEMA_NAME,
        schema_version="1.1",
        inputs=legacy_inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    legacy_ref = bridge.EmpiricalCalibrationEvidenceRef.model_validate(persisted_ref)
    loaded = bridge.load_empirical_calibration_evidence(store, legacy_ref)
    assert loaded.schema_version == "1.1"
    assert loaded.report_ref.manifest_profile_sha256 is None
    assert loaded.observed_outcome_ref is not None
    assert loaded.observed_outcome_ref.manifest_profile_sha256 is None
    assert loaded.context_bound is True


def test_persisted_backtest_report_readback_produces_neutral_empirical_interval_hit_evidence(
    tmp_path: Path,
) -> None:
    """Observed bounds are recomputed from the persisted report, not self-attested flags."""

    store, report_ref, persisted, refs = _persist_report(
        tmp_path,
        label="neutral",
        observations=(True, False),
    )
    assert set(refs) == set(REFERENCE_PROFILES)
    assert all(ref.get("manifest_profile_sha256") for ref in refs.values())
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
    assert evidence.observed_outcome_ref.identity_value == ("observation://frc02/held-out/v1")
    assert evidence.evidence_origin == "persisted_backtest"
    # These are typed evidence fields, not a free-form metadata assertion.  A
    # predictive calibration observation cannot mint causal, treatment, or S10
    # authority merely because it has a finite interval hit rate.
    assert evidence.authority_scope == PREDICTIVE_AUTHORITY_SCOPE
    assert set(evidence.may_not_use_for) >= PREDICTIVE_AUTHORITY_DENIALS
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
        threshold=1.0,
    )
    limited_store, limited_ref, _limited_report, limited_refs = _persist_report(
        tmp_path,
        label="one-miss",
        observations=(True, False),
        nominal_confidence=0.95,
        threshold=1.0,
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


def test_persisted_self_attested_projection_cannot_override_observed_bounds(
    tmp_path: Path,
) -> None:
    """Contradictory within-ci flags and counters cannot create a usable result."""

    store, _report_ref, persisted, refs = _persist_report(
        tmp_path,
        label="self-attested",
        observations=(True, False),
    )
    forged_ref = _persist_contradictory_projection(
        store,
        report=persisted,
        refs=refs,
    )
    context = _context(refs)
    bridge = _bridge()
    observed: list[Any] = []

    def produce() -> Any:
        result = bridge.produce_empirical_calibration_evidence(
            store,
            forged_ref,
            context=context,
        )
        observed.append(result)
        return result

    _assert_rejected_without_write(store, produce)
    if observed:
        # The independent calculation is 1/2 from y_true and persisted bounds;
        # the forged report advertises 2/2.  A bounded diagnostic is acceptable,
        # but a self-attested pass is not.
        assert observed[0].recomputed_numerator == 1
        assert observed[0].recomputed_denominator == 2
        assert observed[0].persisted_numerator == 2
        assert observed[0].persisted_denominator == 2


def test_context_temporal_roles_are_aware_and_ordered(tmp_path: Path) -> None:
    """The valid context preserves six distinct ordered temporal roles."""

    _store, _report_ref, _persisted, refs = _persist_report(
        tmp_path,
        label="temporal-valid",
        observations=(True,),
    )
    context = _context(refs)
    roles = (
        context.data_valid_time,
        context.calibration_window_start,
        context.calibration_window_end,
        context.policy_effective_time,
        context.prediction_time,
        context.observation_time,
    )
    assert all(role.tzinfo is not None and role.utcoffset() is not None for role in roles)
    assert context.data_valid_time < context.calibration_window_start
    assert context.calibration_window_start < context.calibration_window_end
    assert context.calibration_window_end <= context.prediction_time
    assert context.policy_effective_time <= context.prediction_time
    assert context.prediction_time < context.observation_time
    assert len(set(roles)) == 6


def test_report_temporal_roles_must_match_context_before_cas_write(
    tmp_path: Path,
) -> None:
    """A persisted report cannot be rebound to a different observation time."""

    store, report_ref, persisted, refs = _persist_report(
        tmp_path, label="temporal-report-mismatch", observations=(True, False)
    )
    bridge = _bridge()
    changed_roles = _temporal_roles()
    changed_roles["observation_time"] += timedelta(days=1)
    forged_report = persisted.model_copy(
        update={
            "metadata": {
                **persisted.metadata,
                "temporal_roles": {
                    name: value.isoformat() for name, value in changed_roles.items()
                },
            }
        }
    )
    original_manifest = _ensure_ir_artifact_store(store).get_manifest(report_ref)
    report_inputs = [
        InputRef(
            artifact_id=item.artifact_id,
            role=item.role,
            manifest_profile_sha256=item.manifest_profile_sha256,
        )
        for item in original_manifest.inputs
    ]
    forged_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store), forged_report, inputs=report_inputs
    )

    evidence = bridge.produce_empirical_calibration_evidence(
        store, forged_ref, context=_context(refs)
    )

    assert "temporal_roles_report_mismatch" in evidence.failure_codes
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False


@pytest.mark.parametrize("invalid_temporal_case", ["collapsed", "naive", "out_of_order"])
def test_context_rejects_collapsed_naive_and_out_of_order_temporal_roles(
    tmp_path: Path,
    invalid_temporal_case: str,
) -> None:
    """Temporal ambiguity cannot be admitted as a valid empirical context."""

    _store, _report_ref, _persisted, refs = _persist_report(
        tmp_path,
        label=f"temporal-{invalid_temporal_case}",
        observations=(True,),
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    mutations: dict[str, dict[str, object]] = {
        "collapsed": {"observation_time": start + timedelta(days=4)},
        "naive": {"prediction_time": start.replace(tzinfo=None) + timedelta(days=4)},
        "out_of_order": {
            "data_valid_time": start + timedelta(days=2),
        },
    }
    with pytest.raises(ValueError):
        _context(refs, temporal_updates=mutations[invalid_temporal_case])


def test_context_binding_mismatches_fail_closed_before_cas_write(tmp_path: Path) -> None:
    """Report, scope, policy, method, rule, threshold, and corrupt refs cannot be admitted."""

    store, report_ref, _persisted, refs = _persist_report(
        tmp_path,
        label="binding-negatives",
        observations=(True, False),
    )
    bridge = _bridge()
    baseline_context = _context(refs)
    forged_scope = baseline_context.scope_binding_ref.model_copy(
        update={"identity_value": "frc02-bridge-forged-scope"}
    )
    corrupted_context = baseline_context.model_copy(update={"scope_binding_ref": forged_scope})
    actions: tuple[Callable[[], Any], ...] = (
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref.model_copy(update={"kind": "ir.not_a_backtest_report"}),
            context=baseline_context,
        ),
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref,
            context=_context(refs, model_ref="model://frc02/wrong-model/v1"),
        ),
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref,
            context=_context(refs, policy_ref="policy://frc02/wrong-policy/v1"),
        ),
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref,
            context=_context(
                refs,
                method_ref="forecasting.univariate.wrong_method",
            ),
        ),
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref,
            context=_context(refs, method_version="9.9.9"),
        ),
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref,
            context=_context(refs, rule_version_ref="rolling-origin-residual-conformal.v9"),
        ),
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref,
            context=_context(refs, threshold=1.0),
        ),
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref,
            context=corrupted_context,
        ),
    )
    for action in actions:
        _assert_rejected_without_write(store, action)


def test_cross_report_context_refs_cannot_be_rebound_to_another_report(
    tmp_path: Path,
) -> None:
    """A valid context from report B is not evidence for report A."""

    store = _WriteSpyCAS(tmp_path / "frc02-cross-report-cas")
    report_a_ref, _report_a, _refs_a = _persist_report_into_store(
        store,
        label="report-a",
        observations=(True, False),
    )
    _report_b_ref, _report_b, refs_b = _persist_report_into_store(
        store,
        label="report-b",
        observations=(True, True),
    )
    context_from_b = _context(refs_b)
    bridge = _bridge()

    _assert_rejected_without_write(
        store,
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_a_ref,
            context=context_from_b,
        ),
    )


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

    _assert_rejected_without_write(
        store,
        lambda: bridge.produce_empirical_calibration_evidence(
            store,
            report_ref.model_copy(update={"kind": "ir.not_a_backtest_report"}),
            context=context,
        ),
    )

    forged_manifest = (
        _ensure_ir_artifact_store(store)
        .get_manifest(report_ref)
        .model_copy(update={"kind": "ir.not_a_backtest_report"})
    )
    _assert_rejected_without_write(
        store,
        lambda: bridge.produce_empirical_calibration_evidence(
            _StoreOverride(store, manifest=forged_manifest),
            report_ref,
            context=context,
        ),
    )

    _assert_rejected_without_write(
        store,
        lambda: bridge.produce_empirical_calibration_evidence(
            _StoreOverride(store, bytes_override=b"not-the-report"),
            report_ref,
            context=context,
        ),
    )

    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=context,
    )
    forged_evidence = evidence.model_copy(
        update={"recomputed_numerator": 0, "usable_for_calibration": False}
    )
    _assert_rejected_without_write(
        store,
        lambda: bridge.persist_empirical_calibration_evidence(store, forged_evidence),
    )


def test_forged_context_scope_bytes_and_threshold_manifest_fail_before_cas_write(
    tmp_path: Path,
) -> None:
    """Context refs remain typed while forged CAS witnesses fail content binding."""

    store, report_ref, _persisted, refs = _persist_report(
        tmp_path,
        label="context-binding",
        observations=(True,),
    )
    bridge = _bridge()
    context = _context(refs)

    # Keep the EvidenceArtifactRef unchanged and plausible; only the bytes
    # returned by the CAS are forged.  A caller-declared ref mutation would not
    # exercise the persisted content-binding check this witness requires.
    scope_ref = bridge._store_selector_for_ref(context.scope_binding_ref)
    scope_artifact_id = str(scope_ref.artifact_id)
    scope_payload = json.loads(_ensure_ir_artifact_store(store).get_bytes(scope_ref))
    scope_payload["report_id"] = "frc02-bridge-forged-context"
    forged_scope_bytes = json.dumps(
        scope_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _assert_rejected_without_write(
        store,
        lambda: bridge.produce_empirical_calibration_evidence(
            _StoreOverride(
                store,
                bytes_overrides={scope_artifact_id: forged_scope_bytes},
            ),
            report_ref,
            context=context,
        ),
    )

    threshold_ref = bridge._store_selector_for_ref(context.calibration_threshold_ref)
    threshold_artifact_id = str(threshold_ref.artifact_id)
    forged_threshold_manifest = (
        _ensure_ir_artifact_store(store)
        .get_manifest(threshold_ref)
        .model_copy(update={"kind": "ir.calibration.threshold.forged"})
    )
    _assert_rejected_without_write(
        store,
        lambda: bridge.produce_empirical_calibration_evidence(
            _StoreOverride(
                store,
                manifest_overrides={
                    threshold_artifact_id: forged_threshold_manifest,
                },
            ),
            report_ref,
            context=context,
        ),
    )
