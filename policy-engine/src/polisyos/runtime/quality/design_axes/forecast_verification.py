"""Independently re-run the admitted ETS forecast against its held-out source.

This verifier checks the numeric forecast/calibration chain from CAS bytes. It
does not admit a jurisdiction, unit, or source-time scope: the pinned C
projection explicitly leaves source-time semantics unestablished, and the
current forecast request has no typed C profile binding. Its successful result
is therefore predictive-only and limited, never an S10 authority grant.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.calibration.forecast_bridge import (
    REFERENCE_PROFILES,
    EmpiricalCalibrationEvidence,
    EmpiricalCalibrationEvidenceRef,
    EvidenceArtifactRef,
    load_empirical_calibration_evidence,
)
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.catalog.forecasting import ensure_forecasting_methods_registered
from polisyos.foundry.methods.compiler.specialization import compute_static_params_hash
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics.backtest import BacktestReport, BacktestScenario
from polisyos.ir.analytics.forecasting_uncertainty import (
    ForecastingUncertaintyBundle,
    ForecastIntervalSemantics,
)
from polisyos.ir.artifacts import ArtifactID, ArtifactStore, get_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel, BacktestReportRef
from polisyos.ir.trinity.loaders import load_model_spec, load_policy_spec
from polisyos.scientist.methods.backtesting.forecast_owner import (
    METHOD_FQN,
    CalibrationRuleArtifact,
    ForecastOwnerRequest,
)

_REPORT_SCHEMA_NAME = "ir.backtest_report"
_REPORT_SCHEMA_VERSION = "1.0"
_REPORT_KIND = "ir.backtest_report"
_EVIDENCE_KIND = "ir.empirical_calibration_evidence"
_RULE_KIND = "ir.forecast_calibration_rule"
_TRAINING_SLICE_KIND = "ir.forecast_training_slice"
_METHOD_ARTIFACT_KIND = "foundry.method_artifact"
_UNCERTAINTY_BUNDLE_KIND = "ir.forecasting_uncertainty_bundle"
_CALIBRATION_DIAGNOSTICS_KIND = "ir.calibration_diagnostics_report"
_SCOPE_NOT_ESTABLISHED = "source_scope_not_established"
_UNIT_NOT_ESTABLISHED = "target_unit_not_established"
_SOURCE_TIME_NOT_ESTABLISHED = "source_time_semantics_not_established"


class ForecastVerificationResult(BaseModel):
    """Non-persisted result of A's independent predictive verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["recomputed_predictive_limited", "blocked"]
    reason_codes: tuple[str, ...]
    observed_source_ref: DataSnapshotRef | None = None
    report_ref: BacktestReportRef | None = None
    empirical_evidence_ref: EmpiricalCalibrationEvidenceRef | None = None
    report_id: str | None = None
    target_metric: str | None = None
    method_fqn: Literal["forecasting.univariate.exponential_smoothing@1.0.0"] = METHOD_FQN
    point_forecast: tuple[float, ...] = ()
    predictive_intervals: tuple[tuple[float, float], ...] = ()
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    calibration_threshold: float | None = Field(default=None, gt=0.0, le=1.0)
    threshold_passed: bool | None = None
    temporal_roles_status: Literal["request_evidence_report_bound", "not_established"] = (
        "not_established"
    )
    source_scope_status: Literal["not_established"] = "not_established"
    target_unit_status: Literal["not_established"] = "not_established"
    source_time_status: Literal["not_established"] = "not_established"
    authority_scope: Literal["predictive_only"] = "predictive_only"
    may_not_use_for: tuple[str, ...] = (
        "causal_effect_authority",
        "treatment_assignment_authority",
        "s10_authority",
    )


class _VerificationRefusalError(ValueError):
    """Expected fail-closed input or reconciliation refusal."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def verify_forecast_calibration(
    store: ArtifactStore,
    request: ForecastOwnerRequest,
    evidence_ref: EmpiricalCalibrationEvidenceRef,
) -> ForecastVerificationResult:
    """Resolve E's evidence and independently replay registered ETS in process.

    The verifier resolves the exact source snapshot named by the strict E
    request and the report referenced by E's evidence, runs the registered
    ETS method on the request's training slice with no artifact store in
    method state, and reconciles predictions, intervals, held-out observations,
    counts, rate, threshold, request/report lineage, and six temporal-role
    bindings.

    Args:
        store: Read-only CAS interface used to resolve source and evidence.
        request: The exact strict request used by E's forecast owner.
        evidence_ref: Typed E empirical evidence reference. E's loader checks
            its CAS profile and report-bound input graph before A continues.

    Returns:
        A predictive-only verification result. Numeric verification remains
        limited because the current admitted C projection does not bind
        source-time, jurisdiction, or unit semantics to this request.
    """

    validated_request: ForecastOwnerRequest | None = None
    validated_evidence_ref: EmpiricalCalibrationEvidenceRef | None = None
    stage = "request"
    try:
        validated_request = ForecastOwnerRequest.model_validate(request)
        stage = "evidence_reference"
        validated_evidence_ref = EmpiricalCalibrationEvidenceRef.model_validate(evidence_ref)
        stage = "evidence_resolution"
        evidence = load_empirical_calibration_evidence(store, validated_evidence_ref)
        stage = "independent_replay"
        verified = _verify_resolved_chain(
            store,
            validated_request,
            validated_evidence_ref,
            evidence,
        )
    except _VerificationRefusalError as exc:
        return ForecastVerificationResult(
            status="blocked",
            reason_codes=(exc.code,),
            observed_source_ref=(
                validated_request.observed_source_ref if validated_request is not None else None
            ),
            empirical_evidence_ref=validated_evidence_ref,
            report_id=validated_request.report_id if validated_request is not None else None,
            target_metric=(
                validated_request.target_metric if validated_request is not None else None
            ),
        )
    except FileNotFoundError, OSError, TypeError, ValueError, KeyError:
        # Loader/DTO failures are refusals. Their raw messages are omitted so
        # callers cannot accidentally turn implementation text into a reason.
        code = {
            "request": "forecast_request_invalid",
            "evidence_reference": "empirical_evidence_ref_invalid",
            "evidence_resolution": "empirical_evidence_unresolved",
            "independent_replay": "input_unresolved",
        }[stage]
        return ForecastVerificationResult(
            status="blocked",
            reason_codes=(code,),
            observed_source_ref=(
                validated_request.observed_source_ref if validated_request is not None else None
            ),
            empirical_evidence_ref=validated_evidence_ref,
            report_id=validated_request.report_id if validated_request is not None else None,
            target_metric=(
                validated_request.target_metric if validated_request is not None else None
            ),
        )
    return verified


def _verify_resolved_chain(
    store: ArtifactStore,
    request: ForecastOwnerRequest,
    evidence_ref: EmpiricalCalibrationEvidenceRef,
    evidence: EmpiricalCalibrationEvidence,
) -> ForecastVerificationResult:
    if request.method_fqn != METHOD_FQN:
        raise _VerificationRefusalError("unsupported_forecast_method")
    _validate_model_policy_content(store, request)
    if evidence.report_id != request.report_id:
        raise _VerificationRefusalError("report_request_identity_mismatch")
    if evidence.authority_scope != "predictive_only":
        raise _VerificationRefusalError("forecast_authority_scope_mismatch")

    request_source_ref, snapshot_payload = _resolve_json(
        store,
        request.observed_source_ref,
        expected_kind="fabric.data_snapshot",
    )
    if request_source_ref.artifact_id != request.observed_source_ref.artifact_id:
        raise _VerificationRefusalError("source_request_identity_mismatch")
    try:
        snapshot = DataSnapshot.model_validate(snapshot_payload)
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("source_snapshot_invalid") from exc
    observed_data_ref, observed_payload = _resolve_json(store, snapshot.data_ref)
    if not isinstance(observed_payload, Mapping):
        raise _VerificationRefusalError("source_data_not_metric_mapping")
    source_values = _finite_series(observed_payload.get(request.target_metric))
    if request.split.holdout_end > source_values.size:
        raise _VerificationRefusalError("train_holdout_split_exceeds_source")
    if request.split.train_end < 8:
        raise _VerificationRefusalError("ets_training_slice_too_short")

    rule_ref, rule_payload = _resolve_json(
        store,
        request.calibration_rule.artifact_ref,
        expected_kind=_RULE_KIND,
    )
    try:
        rule = CalibrationRuleArtifact.model_validate(rule_payload)
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("calibration_rule_invalid") from exc
    if rule.rule_id != request.calibration_rule.rule_id or rule.estimand != request.estimand:
        raise _VerificationRefusalError("calibration_rule_request_mismatch")

    report_ref = BacktestReportRef.model_validate(evidence.report_ref)
    if not _has_evidence_context(evidence, request):
        raise _VerificationRefusalError("empirical_evidence_context_incomplete")
    report_ref, report_payload = _resolve_json(
        store,
        report_ref,
        expected_kind=_REPORT_KIND,
        expected_schema=(_REPORT_SCHEMA_NAME, _REPORT_SCHEMA_VERSION),
    )
    try:
        report = BacktestReport.model_validate(report_payload)
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("backtest_report_invalid") from exc
    if report.report_id != request.report_id or evidence.report_id != report.report_id:
        raise _VerificationRefusalError("report_identity_mismatch")
    if (
        report.trust_eligible
        or report.trust_score is not None
        or "trust_screening:predictive_only_bridge_pending" not in report.degraded_reasons
    ):
        raise _VerificationRefusalError("report_predictive_only_trust_boundary_mismatch")

    edges = _manifest_input_edges(store, report_ref)
    expected_edges = {
        (str(request_source_ref.artifact_id), "observed_source"),
        (str(observed_data_ref.artifact_id), "observed_data"),
        (str(rule_ref.artifact_id), "calibration_rule"),
    }
    if request.model_spec_ref is not None and request.policy_spec_ref is not None:
        expected_edges.update(
            {
                (str(request.model_spec_ref), "model_spec"),
                (str(request.policy_spec_ref), "policy_spec"),
            }
        )
    for role in (
        "observed_source",
        "observed_data",
        "calibration_rule",
        "model_spec",
        "policy_spec",
    ):
        actual_for_role = {artifact_id for artifact_id, edge_role in edges if edge_role == role}
        expected_for_role = {
            artifact_id for artifact_id, edge_role in expected_edges if edge_role == role
        }
        if actual_for_role != expected_for_role:
            raise _VerificationRefusalError("report_source_or_scope_lineage_mismatch")
    if not expected_edges.issubset(edges):
        raise _VerificationRefusalError("report_source_or_rule_lineage_missing")
    derived_refs = _resolve_owner_derived_inputs(store, edges)
    training_edges = _manifest_input_edges(store, derived_refs["training_slice"][0])
    expected_training_edges = {
        (str(request_source_ref.artifact_id), "observed_source"),
        (str(observed_data_ref.artifact_id), "observed_data"),
    }
    if training_edges != expected_training_edges:
        raise _VerificationRefusalError("training_slice_lineage_mismatch")
    _validate_request_report_binding(
        request,
        evidence,
        report,
        observed_data_ref=observed_data_ref,
        rule=rule,
        derived_refs=derived_refs,
        source_values=source_values,
    )

    train = source_values[request.split.train_start : request.split.train_end]
    holdout = source_values[request.split.holdout_start : request.split.holdout_end]
    if train.size < 8 or holdout.size != request.split.horizon:
        raise _VerificationRefusalError("train_holdout_source_slice_invalid")

    registry = MethodRegistry.get_instance()
    ensure_forecasting_methods_registered(registry)
    try:
        method_class = registry.get(request.method_fqn)
    except (KeyError, ValueError) as exc:
        raise _VerificationRefusalError("registered_ets_method_unavailable") from exc
    if method_class.signature.fqn != METHOD_FQN:
        raise _VerificationRefusalError("registered_ets_identity_mismatch")
    try:
        dispatch = MethodDispatcher.get_instance().dispatch(
            method_class=method_class,
            signature=method_class.signature,
            state={
                "series": train,
                "target_id": request.target_metric,
                "calibration_nominal_coverage": rule.nominal_coverage,
            },
            params=request.method_params.model_dump(mode="python"),
            seed=request.seed,
        )
    except Exception as exc:
        raise _VerificationRefusalError("independent_ets_execution_failed") from exc
    if dispatch.reproducibility.backend is not ComputeBackend.NUMPY:
        raise _VerificationRefusalError("independent_ets_backend_mismatch")
    point_forecast, intervals, sample_counts = _forecast_values(
        dispatch.output,
        request=request,
        nominal_coverage=rule.nominal_coverage,
    )
    _validate_stored_uncertainty_bundle(
        derived_refs["uncertainty_bundle"][1],
        request=request,
        point_forecast=point_forecast,
        intervals=intervals,
        sample_counts=sample_counts,
        nominal_coverage=rule.nominal_coverage,
    )

    scenario = _only_scenario(report)
    numerator, denominator, pass_rate = _reconcile_report_observations(
        report,
        scenario,
        request=request,
        point_forecast=point_forecast,
        intervals=intervals,
        holdout=holdout,
        nominal_coverage=rule.nominal_coverage,
    )
    threshold = _resolve_threshold(
        store,
        evidence.calibration_threshold_ref,
        report_id=report.report_id,
        expected=evidence.calibration_threshold,
    )
    _validate_scope_binding(
        store,
        evidence,
        request,
        report,
        threshold=threshold,
    )
    if (
        evidence.recomputed_numerator != numerator
        or evidence.recomputed_denominator != denominator
        or not _close(evidence.recomputed_pass_rate, pass_rate)
        or evidence.within_ci_numerator != numerator
        or evidence.within_ci_denominator != denominator
        or evidence.persisted_numerator != numerator
        or evidence.persisted_denominator != denominator
    ):
        raise _VerificationRefusalError("empirical_evidence_recomputation_mismatch")
    threshold_passed = pass_rate >= threshold
    if evidence.floor_passed is not threshold_passed:
        raise _VerificationRefusalError("empirical_evidence_threshold_projection_mismatch")
    reasons = [
        _SCOPE_NOT_ESTABLISHED,
        _UNIT_NOT_ESTABLISHED,
        _SOURCE_TIME_NOT_ESTABLISHED,
        "request_seed_not_source_bound",
    ]
    if not threshold_passed:
        reasons.append("calibration_floor_not_met")
    return ForecastVerificationResult(
        status="recomputed_predictive_limited",
        reason_codes=tuple(reasons),
        observed_source_ref=request_source_ref,
        report_ref=report_ref,
        empirical_evidence_ref=evidence_ref,
        report_id=report.report_id,
        target_metric=request.target_metric,
        point_forecast=point_forecast,
        predictive_intervals=intervals,
        numerator=numerator,
        denominator=denominator,
        pass_rate=pass_rate,
        calibration_threshold=threshold,
        threshold_passed=threshold_passed,
        temporal_roles_status="request_evidence_report_bound",
    )


def _resolve_json(
    store: ArtifactStore,
    raw_ref: object,
    *,
    expected_kind: str | None = None,
    expected_schema: tuple[str, str] | None = None,
) -> tuple[ArtifactRefModel, object]:
    ref = ArtifactRefModel.model_validate(_model_payload(raw_ref))
    if expected_kind is not None and ref.kind != expected_kind:
        raise _VerificationRefusalError("artifact_kind_mismatch")
    artifact_id = ArtifactID.model_validate(str(ref.artifact_id))
    manifest = store.get_manifest(artifact_id)
    if _string_field(manifest, "artifact_id") != str(artifact_id):
        raise _VerificationRefusalError("artifact_manifest_identity_mismatch")
    if (
        _string_field(manifest, "kind") != ref.kind
        or _string_field(manifest, "media_type") != ref.media_type
    ):
        raise _VerificationRefusalError("artifact_manifest_profile_mismatch")
    payload_bytes = store.get_bytes(artifact_id)
    actual_hash = hashlib.sha256(payload_bytes).hexdigest()
    if actual_hash != artifact_id.hex:
        raise _VerificationRefusalError("artifact_content_hash_mismatch")
    integrity = _as_mapping(_field(manifest, "integrity"))
    if integrity.get("sha256") != actual_hash:
        raise _VerificationRefusalError("artifact_integrity_manifest_mismatch")
    byte_size = _field(manifest, "byte_size")
    if byte_size is not None and int(byte_size) != len(payload_bytes):
        raise _VerificationRefusalError("artifact_byte_size_mismatch")
    if expected_schema is not None:
        raw_schema = _field(manifest, "schema")
        schema = _as_mapping(raw_schema)
        if not schema:
            schema = _as_mapping(_field(manifest, "artifact_schema"))
        if (schema.get("name"), schema.get("version")) != expected_schema:
            raise _VerificationRefusalError("artifact_schema_mismatch")
    return ref, get_json_artifact(store, artifact_id)


def _resolve_owner_derived_inputs(
    store: ArtifactStore,
    edges: set[tuple[str, str]],
) -> dict[str, tuple[ArtifactRefModel, object]]:
    expected = {
        "training_slice": _TRAINING_SLICE_KIND,
        "method_artifact": _METHOD_ARTIFACT_KIND,
        "uncertainty_bundle": _UNCERTAINTY_BUNDLE_KIND,
        "calibration_diagnostics": _CALIBRATION_DIAGNOSTICS_KIND,
    }
    resolved: dict[str, tuple[ArtifactRefModel, object]] = {}
    for role, expected_kind in expected.items():
        ids = {artifact_id for artifact_id, edge_role in edges if edge_role == role}
        if len(ids) != 1:
            raise _VerificationRefusalError(f"report_{role}_edge_not_unique")
        artifact_id = next(iter(ids))
        manifest = store.get_manifest(ArtifactID.model_validate(artifact_id))
        ref = ArtifactRefModel(
            artifact_id=ArtifactID.model_validate(artifact_id),
            kind=_string_field(manifest, "kind"),
            media_type=_string_field(manifest, "media_type"),
        )
        if ref.kind != expected_kind:
            raise _VerificationRefusalError(f"report_{role}_kind_mismatch")
        resolved_ref, payload = _resolve_json(store, ref, expected_kind=expected_kind)
        resolved[role] = (resolved_ref, payload)
    return resolved


def _validate_model_policy_content(store: ArtifactStore, request: ForecastOwnerRequest) -> None:
    """Resolve and validate a complete, distinct supplied Core spec pair.

    Requests without a model/policy pair remain limited. When a pair is
    supplied, matching report strings and CAS roles are insufficient: the
    content must resolve under the canonical strict Trinity Core loaders.
    """

    model_spec_id = request.model_spec_ref
    policy_spec_id = request.policy_spec_ref
    if model_spec_id is None and policy_spec_id is None:
        return
    if model_spec_id is None or policy_spec_id is None:
        raise _VerificationRefusalError("model_policy_spec_pair_incomplete")
    if model_spec_id == policy_spec_id:
        raise _VerificationRefusalError("model_policy_spec_pair_not_distinct")

    model_ref = ArtifactRefModel(
        artifact_id=model_spec_id,
        kind="ir.model_spec",
        media_type="application/json",
    )
    try:
        _, model_payload = _resolve_json(store, model_ref, expected_kind="ir.model_spec")
        load_model_spec(model_payload)
    except _VerificationRefusalError as exc:
        raise _VerificationRefusalError("model_spec_content_unresolved") from exc
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("model_spec_content_invalid") from exc

    policy_ref = ArtifactRefModel(
        artifact_id=policy_spec_id,
        kind="ir.policy_spec",
        media_type="application/json",
    )
    try:
        _, policy_payload = _resolve_json(store, policy_ref, expected_kind="ir.policy_spec")
        load_policy_spec(policy_payload)
    except _VerificationRefusalError as exc:
        raise _VerificationRefusalError("policy_spec_content_unresolved") from exc
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("policy_spec_content_invalid") from exc


def _validate_request_report_binding(
    request: ForecastOwnerRequest,
    evidence: EmpiricalCalibrationEvidence,
    report: BacktestReport,
    *,
    observed_data_ref: ArtifactRefModel,
    rule: CalibrationRuleArtifact,
    derived_refs: Mapping[str, tuple[ArtifactRefModel, object]],
    source_values: np.ndarray,
) -> None:
    if report.historical_data_ref != str(observed_data_ref.artifact_id):
        raise _VerificationRefusalError("report_historical_source_mismatch")
    if report.model_spec_ref != _ref_id(request.model_spec_ref):
        raise _VerificationRefusalError("report_model_scope_mismatch")
    if report.policy_spec_ref != _ref_id(request.policy_spec_ref):
        raise _VerificationRefusalError("report_policy_scope_mismatch")
    method_ref, _, method_version = request.method_fqn.rpartition("@")
    metadata = report.metadata
    expected_metadata = {
        "method_ref": method_ref,
        "method_version": method_version,
        "rule_version_ref": request.calibration_rule.rule_id,
        "calibration_rule_version": rule.rule_version,
        "estimand": request.estimand,
        "authority_scope": "predictive_only",
        "bridge_status": "bridge_pending",
    }
    if any(metadata.get(key) != value for key, value in expected_metadata.items()):
        raise _VerificationRefusalError("report_method_rule_or_purpose_mismatch")
    for field_name, request_value in (
        ("model_spec_ref", _ref_id(request.model_spec_ref)),
        ("policy_spec_ref", _ref_id(request.policy_spec_ref)),
    ):
        if metadata.get(field_name) != request_value:
            raise _VerificationRefusalError("report_model_policy_metadata_mismatch")
    if _metadata_ref_id(metadata.get("observed_source_ref")) != str(
        request.observed_source_ref.artifact_id
    ):
        raise _VerificationRefusalError("report_source_snapshot_mismatch")
    if _metadata_ref_id(metadata.get("calibration_rule_ref")) != str(
        request.calibration_rule.artifact_ref.artifact_id
    ):
        raise _VerificationRefusalError("report_calibration_rule_ref_mismatch")
    if _temporal_payload(metadata.get("temporal_roles")) != _temporal_payload(
        request.temporal_roles.model_dump(mode="json")
    ):
        raise _VerificationRefusalError("report_temporal_roles_mismatch")
    if evidence.method_ref != method_ref or evidence.method_version != method_version:
        raise _VerificationRefusalError("evidence_method_binding_mismatch")
    if evidence.rule_version_ref != request.calibration_rule.rule_id:
        raise _VerificationRefusalError("evidence_rule_binding_mismatch")
    if evidence.estimand != request.estimand:
        raise _VerificationRefusalError("evidence_estimand_mismatch")
    if (
        evidence.model_spec_ref != report.model_spec_ref
        or evidence.policy_spec_ref != report.policy_spec_ref
    ):
        raise _VerificationRefusalError("evidence_model_policy_binding_mismatch")
    if _evidence_temporal_payload(evidence) != _temporal_payload(
        request.temporal_roles.model_dump(mode="json")
    ):
        raise _VerificationRefusalError("evidence_temporal_roles_mismatch")

    _validate_training_slice(
        derived_refs["training_slice"][1],
        request,
        source_values=source_values,
        observed_data_ref=observed_data_ref,
    )
    _validate_method_artifact(derived_refs["method_artifact"][1], request)
    _validate_bound_metadata_ref(
        metadata.get("uncertainty_bundle_ref"),
        derived_refs["uncertainty_bundle"][0],
    )
    _validate_bound_metadata_ref(
        metadata.get("calibration_diagnostics_ref"),
        derived_refs["calibration_diagnostics"][0],
    )


def _validate_training_slice(
    payload: object,
    request: ForecastOwnerRequest,
    *,
    source_values: np.ndarray,
    observed_data_ref: ArtifactRefModel,
) -> None:
    if not isinstance(payload, Mapping):
        raise _VerificationRefusalError("training_slice_invalid")
    expected = {
        "source_ref": request.observed_source_ref.model_dump(mode="json"),
        "target_metric": request.target_metric,
        "split": request.split.model_dump(mode="json"),
        "method_fqn": request.method_fqn,
        "method_params": request.method_params.model_dump(mode="json"),
        "temporal_roles": request.temporal_roles.model_dump(mode="json"),
        "authority_scope": "predictive_only",
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise _VerificationRefusalError("training_slice_request_binding_mismatch")
    if _metadata_ref_id(payload.get("observed_data_ref")) != str(observed_data_ref.artifact_id):
        raise _VerificationRefusalError("training_slice_source_data_mismatch")
    values = payload.get("values")
    expected_values = source_values[request.split.train_start : request.split.train_end]
    if (
        not isinstance(values, list)
        or len(values) != expected_values.size
        or any(
            not _close(actual, expected)
            for actual, expected in zip(values, expected_values, strict=True)
        )
    ):
        raise _VerificationRefusalError("training_slice_values_invalid")


def _validate_method_artifact(payload: object, request: ForecastOwnerRequest) -> None:
    if not isinstance(payload, Mapping) or payload.get("fqn") != request.method_fqn:
        raise _VerificationRefusalError("method_artifact_identity_mismatch")
    specialization = _as_mapping(payload.get("specialization"))
    backend = _as_mapping(specialization.get("backend"))
    input_shapes = specialization.get("input_shapes")
    expected_params_hash = compute_static_params_hash(
        request.method_params.model_dump(mode="python")
    )
    if (
        specialization.get("method_fqn") != request.method_fqn
        or specialization.get("static_params_hash") != expected_params_hash
        or backend.get("platform") != ComputeBackend.NUMPY.value
        or not isinstance(input_shapes, list)
    ):
        raise _VerificationRefusalError("method_artifact_specialization_mismatch")
    series_shapes = [
        item for item in input_shapes if isinstance(item, Mapping) and item.get("name") == "series"
    ]
    if len(series_shapes) != 1:
        raise _VerificationRefusalError("method_artifact_input_shape_mismatch")
    shape = series_shapes[0].get("shape")
    dtype = series_shapes[0].get("dtype")
    expected_size = request.split.train_end - request.split.train_start
    if (
        not isinstance(shape, list)
        or shape != [expected_size]
        or dtype != "float64"
        or backend.get("precision") != "float64"
    ):
        raise _VerificationRefusalError("method_artifact_input_shape_mismatch")


def _validate_bound_metadata_ref(value: object, expected_ref: ArtifactRefModel) -> None:
    ref = _as_mapping(value)
    if (
        not ref.get("artifact_id")
        or str(ref.get("artifact_id")) != str(expected_ref.artifact_id)
        or ref.get("kind") != expected_ref.kind
        or ref.get("media_type") != expected_ref.media_type
    ):
        raise _VerificationRefusalError("report_derived_artifact_binding_missing")


def _validate_stored_uncertainty_bundle(
    payload: object,
    *,
    request: ForecastOwnerRequest,
    point_forecast: tuple[float, ...],
    intervals: tuple[tuple[float, float], ...],
    sample_counts: tuple[int, ...],
    nominal_coverage: float,
) -> None:
    try:
        bundle = ForecastingUncertaintyBundle.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("stored_uncertainty_bundle_invalid") from exc
    if (
        bundle.method_fqn != request.method_fqn
        or bundle.target_id != request.target_metric
        or bundle.interval_semantics
        is not ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
        or not math.isclose(bundle.nominal_coverage, nominal_coverage, rel_tol=0.0, abs_tol=1e-12)
    ):
        raise _VerificationRefusalError("stored_uncertainty_bundle_binding_mismatch")
    ordered_intervals = sorted(bundle.prediction_interval, key=lambda entry: entry.horizon)
    if [item.horizon for item in ordered_intervals] != list(range(1, len(intervals) + 1)):
        raise _VerificationRefusalError("stored_uncertainty_horizon_mismatch")
    stored_intervals: list[tuple[float, float]] = []
    for item in ordered_intervals:
        stored_intervals.append(
            (
                _scalar(item.lower, "stored interval lower"),
                _scalar(item.upper, "stored interval upper"),
            )
        )
    if len(stored_intervals) != len(intervals) or any(
        not _close_pair(actual, stored)
        for actual, stored in zip(intervals, stored_intervals, strict=True)
    ):
        raise _VerificationRefusalError("stored_uncertainty_interval_replay_mismatch")
    stored_sample_counts = tuple(item.sample_count for item in ordered_intervals)
    if stored_sample_counts != sample_counts:
        raise _VerificationRefusalError("stored_uncertainty_sample_count_replay_mismatch")
    stored_points = tuple(
        _scalar(item.point, "stored interval point") for item in ordered_intervals
    )
    if len(stored_points) != len(point_forecast) or any(
        not _close(actual, stored)
        for actual, stored in zip(point_forecast, stored_points, strict=True)
    ):
        raise _VerificationRefusalError("stored_uncertainty_point_replay_mismatch")


def _forecast_values(
    output: object,
    *,
    request: ForecastOwnerRequest,
    nominal_coverage: float,
) -> tuple[tuple[float, ...], tuple[tuple[float, float], ...], tuple[int, ...]]:
    if not isinstance(output, Mapping):
        raise _VerificationRefusalError("independent_ets_output_invalid")
    result = output.get("result")
    if not isinstance(result, Mapping):
        raise _VerificationRefusalError("independent_ets_point_forecast_missing")
    raw_points = result.get("forecast")
    if not isinstance(raw_points, (list, tuple)) or len(raw_points) != request.split.horizon:
        raise _VerificationRefusalError("independent_ets_horizon_mismatch")
    points = tuple(_scalar(value, "point forecast") for value in raw_points)
    try:
        bundle = ForecastingUncertaintyBundle.model_validate(
            output.get("forecasting_uncertainty_bundle")
        )
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("independent_ets_uncertainty_output_invalid") from exc
    if (
        bundle.method_fqn != request.method_fqn
        or bundle.target_id != request.target_metric
        or bundle.interval_semantics
        is not ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
        or not math.isclose(bundle.nominal_coverage, nominal_coverage, rel_tol=0.0, abs_tol=1e-12)
    ):
        raise _VerificationRefusalError("independent_ets_uncertainty_binding_mismatch")
    by_horizon = {item.horizon: item for item in bundle.prediction_interval}
    if set(by_horizon) != set(range(1, request.split.horizon + 1)):
        raise _VerificationRefusalError("independent_ets_interval_horizon_mismatch")
    intervals: list[tuple[float, float]] = []
    sample_counts: list[int] = []
    for horizon, point in enumerate(points, start=1):
        item = by_horizon[horizon]
        interval_point = _scalar(item.point, "interval point")
        lower = _scalar(item.lower, "interval lower")
        upper = _scalar(item.upper, "interval upper")
        if not _close(interval_point, point) or lower > upper:
            raise _VerificationRefusalError("independent_ets_interval_point_mismatch")
        if item.sample_count is None or item.sample_count < 1:
            raise _VerificationRefusalError("independent_ets_interval_history_missing")
        intervals.append((lower, upper))
        sample_counts.append(item.sample_count)
    return points, tuple(intervals), tuple(sample_counts)


def _only_scenario(report: BacktestReport) -> BacktestScenario:
    if len(report.scenarios) != 1:
        raise _VerificationRefusalError("report_scenario_count_mismatch")
    return report.scenarios[0]


def _reconcile_report_observations(
    report: BacktestReport,
    scenario: BacktestScenario,
    *,
    request: ForecastOwnerRequest,
    point_forecast: tuple[float, ...],
    intervals: tuple[tuple[float, float], ...],
    holdout: np.ndarray,
    nominal_coverage: float,
) -> tuple[int, int, float]:
    horizon = request.split.horizon
    if scenario.scenario_id != f"{request.report_id}:ets":
        raise _VerificationRefusalError("report_scenario_identity_mismatch")
    if len(scenario.outcome_comparisons) != horizon or holdout.size != horizon:
        raise _VerificationRefusalError("report_heldout_denominator_mismatch")
    if _temporal_payload(scenario.metadata.get("temporal_roles")) != _temporal_payload(
        request.temporal_roles.model_dump(mode="json")
    ):
        raise _VerificationRefusalError("scenario_temporal_roles_mismatch")
    method_ref, _, method_version = request.method_fqn.rpartition("@")
    expected_scenario_metadata = {
        "method_ref": method_ref,
        "method_version": method_version,
        "rule_version_ref": request.calibration_rule.rule_id,
        "estimand": request.estimand,
        "authority_scope": "predictive_only",
        "bridge_status": "bridge_pending",
    }
    if any(
        scenario.metadata.get(key) != value for key, value in expected_scenario_metadata.items()
    ):
        raise _VerificationRefusalError("scenario_method_rule_or_purpose_mismatch")
    if _metadata_ref_id(scenario.metadata.get("observed_source_ref")) != str(
        request.observed_source_ref.artifact_id
    ):
        raise _VerificationRefusalError("scenario_source_snapshot_mismatch")

    numerator = 0
    for index, (comparison, actual, predicted, interval) in enumerate(
        zip(scenario.outcome_comparisons, holdout, point_forecast, intervals, strict=True)
    ):
        lower, upper = interval
        hit = lower <= float(actual) <= upper
        if (
            comparison.metric_name != request.target_metric
            or not _close(comparison.y_true, float(actual))
            or not _close(comparison.y_pred, predicted)
            or comparison.ci_lower is None
            or comparison.ci_upper is None
            or not _close(comparison.ci_lower, lower)
            or not _close(comparison.ci_upper, upper)
            or comparison.within_ci is not hit
            or not _close(comparison.absolute_error, abs(float(actual) - predicted))
        ):
            raise _VerificationRefusalError(f"report_heldout_comparison_mismatch_{index + 1}")
        numerator += int(hit)
    denominator = horizon
    pass_rate = numerator / denominator
    if (
        scenario.requested_count != denominator
        or scenario.compared_count != denominator
        or scenario.missing_count != 0
        or scenario.invalid_count != 0
        or scenario.interval_requested_count != denominator
        or scenario.interval_available_count != denominator
        or scenario.interval_evaluated_count != denominator
        or scenario.interval_hit_count != numerator
        or not _close(scenario.interval_availability, 1.0)
        or not _close(scenario.interval_hit_rate, pass_rate)
        or not _close(scenario.nominal_confidence_level, nominal_coverage)
        or not _close(scenario.coverage_probability, pass_rate)
        or not _close(report.overall_coverage_probability, pass_rate)
        or report.n_scenarios != 1
        or report.n_metrics_evaluated != denominator
    ):
        raise _VerificationRefusalError("report_calibration_counts_or_rate_mismatch")
    for numerator_key, denominator_key in (
        ("calibration_numerator", "calibration_denominator"),
        ("interval_hit_count", "interval_evaluated_count"),
    ):
        raw_num = report.metadata.get(numerator_key)
        raw_den = report.metadata.get(denominator_key)
        if (raw_num is not None or raw_den is not None) and (
            raw_num != numerator or raw_den != denominator
        ):
            raise _VerificationRefusalError("report_metadata_counts_mismatch")
    return numerator, denominator, pass_rate


def _resolve_threshold(
    store: ArtifactStore,
    ref: EvidenceArtifactRef | None,
    *,
    report_id: str,
    expected: float | None,
) -> float:
    if ref is None or expected is None:
        raise _VerificationRefusalError("calibration_threshold_not_established")
    profile = REFERENCE_PROFILES["calibration_threshold"]
    if (
        ref.role != "calibration_threshold"
        or (ref.kind, ref.schema_name, ref.schema_version) != profile
        or ref.identity_path != "identity"
    ):
        raise _VerificationRefusalError("calibration_threshold_profile_mismatch")
    _, payload = _resolve_json(
        store,
        ArtifactRefModel(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            media_type=ref.media_type,
        ),
        expected_kind=profile[0],
        expected_schema=(profile[1], profile[2]),
    )
    if not isinstance(payload, Mapping):
        raise _VerificationRefusalError("calibration_threshold_payload_invalid")
    threshold_value = payload.get("threshold")
    threshold = _scalar(threshold_value, "calibration threshold")
    if (
        payload.get("role") != "calibration_threshold"
        or payload.get("report_id") != report_id
        or payload.get("identity") != ref.identity_value
        or not _close(threshold, expected)
    ):
        raise _VerificationRefusalError("calibration_threshold_binding_mismatch")
    return threshold


def _validate_scope_binding(
    store: ArtifactStore,
    evidence: EmpiricalCalibrationEvidence,
    request: ForecastOwnerRequest,
    report: BacktestReport,
    *,
    threshold: float,
) -> None:
    ref = evidence.scope_binding_ref
    if ref is None:
        raise _VerificationRefusalError("scope_binding_not_established")
    profile = REFERENCE_PROFILES["scope_binding"]
    if (
        ref.role != "scope_binding"
        or (ref.kind, ref.schema_name, ref.schema_version) != profile
        or ref.identity_path != "report_id"
    ):
        raise _VerificationRefusalError("scope_binding_profile_mismatch")
    _, payload = _resolve_json(
        store,
        ArtifactRefModel(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            media_type=ref.media_type,
        ),
        expected_kind=profile[0],
        expected_schema=(profile[1], profile[2]),
    )
    if not isinstance(payload, Mapping):
        raise _VerificationRefusalError("scope_binding_payload_invalid")
    binding = _as_mapping(payload.get("binding"))
    method_ref, _, method_version = request.method_fqn.rpartition("@")
    if (
        payload.get("role") != "scope_binding"
        or payload.get("report_id") != report.report_id
        or payload.get("report_id") != ref.identity_value
    ):
        raise _VerificationRefusalError("scope_binding_report_identity_mismatch")
    expected_binding = {
        "report_id": report.report_id,
        "model_spec_ref": report.model_spec_ref,
        "policy_spec_ref": report.policy_spec_ref,
        "estimand": request.estimand,
        "method_ref": method_ref,
        "method_version": method_version,
        "rule_version_ref": request.calibration_rule.rule_id,
    }
    if any(
        binding.get(key) is None or str(binding.get(key)) != str(value)
        for key, value in expected_binding.items()
    ):
        raise _VerificationRefusalError("scope_binding_request_report_mismatch")
    if not _close(binding.get("calibration_threshold"), threshold):
        raise _VerificationRefusalError("scope_binding_threshold_mismatch")


def _has_evidence_context(
    evidence: EmpiricalCalibrationEvidence,
    request: ForecastOwnerRequest,
) -> bool:
    refs = (
        evidence.scope_binding_ref,
        evidence.calibration_threshold_ref,
        evidence.observed_outcome_ref,
        evidence.prediction_ref,
        evidence.evaluation_design_ref,
        evidence.credible_evaluation_evidence_ref,
    )
    required_values = (
        evidence.estimand,
        evidence.method_ref,
        evidence.method_version,
        evidence.rule_version_ref,
        evidence.calibration_threshold,
        evidence.data_valid_time,
        evidence.calibration_window_start,
        evidence.calibration_window_end,
        evidence.policy_effective_time,
        evidence.prediction_time,
        evidence.observation_time,
    )
    if not all(ref is not None for ref in refs) or not all(
        value is not None for value in required_values
    ):
        return False
    if not evidence.source_lineage_refs or not evidence.method_lineage_refs:
        return False
    source_ids = {str(ref.artifact_id) for ref in evidence.source_lineage_refs}
    method_ids = {str(ref.artifact_id) for ref in evidence.method_lineage_refs}
    if source_ids & method_ids:
        return False
    role_values = _evidence_temporal_payload(evidence)
    request_values = _temporal_payload(request.temporal_roles.model_dump(mode="json"))
    return role_values == request_values


def _evidence_temporal_payload(evidence: EmpiricalCalibrationEvidence) -> dict[str, datetime]:
    fields = (
        "data_valid_time",
        "calibration_window_start",
        "calibration_window_end",
        "policy_effective_time",
        "prediction_time",
        "observation_time",
    )
    return {
        field: getattr(evidence, field) for field in fields if getattr(evidence, field) is not None
    }


def _temporal_payload(value: object) -> dict[str, datetime | None]:
    mapping = _as_mapping(value)
    fields = (
        "data_valid_time",
        "calibration_window_start",
        "calibration_window_end",
        "policy_effective_time",
        "prediction_time",
        "observation_time",
    )
    return {field: _datetime_value(mapping.get(field)) for field in fields}


def _datetime_value(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _finite_series(value: object) -> np.ndarray:
    if not isinstance(value, (list, tuple)):
        raise _VerificationRefusalError("observed_metric_not_numeric_sequence")
    try:
        values = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise _VerificationRefusalError("observed_metric_not_numeric") from exc
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise _VerificationRefusalError("observed_metric_not_finite_vector")
    return values


def _scalar(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise _VerificationRefusalError(f"{label.replace(' ', '_')}_not_numeric")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _VerificationRefusalError(f"{label.replace(' ', '_')}_not_numeric") from exc
    if not math.isfinite(result):
        raise _VerificationRefusalError(f"{label.replace(' ', '_')}_not_finite")
    return result


def _close(left: object, right: object, *, tolerance: float = 1e-12) -> bool:
    if left is None or right is None:
        return False
    try:
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)
    except TypeError, ValueError, OverflowError:
        return False


def _close_pair(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return _close(left[0], right[0]) and _close(left[1], right[1])


def _manifest_input_edges(store: ArtifactStore, ref: ArtifactRefModel) -> set[tuple[str, str]]:
    manifest = store.get_manifest(ref.artifact_id)
    raw_inputs = _field(manifest, "inputs")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes, bytearray)):
        raise _VerificationRefusalError("report_manifest_inputs_missing")
    edges: set[tuple[str, str]] = set()
    for item in raw_inputs:
        payload = _as_mapping(item)
        artifact_id = payload.get("artifact_id")
        role = payload.get("role")
        if artifact_id is None or not isinstance(role, str) or not role.strip():
            raise _VerificationRefusalError("report_manifest_input_malformed")
        edge = (str(artifact_id), role.strip())
        if edge in edges:
            raise _VerificationRefusalError("report_manifest_input_edge_not_unique")
        edges.add(edge)
    return edges


def _ref_id(value: object | None) -> str | None:
    return None if value is None else str(value)


def _metadata_ref_id(value: object) -> str | None:
    mapping = _as_mapping(value)
    raw = mapping.get("artifact_id")
    return None if raw is None else str(raw)


def _model_payload(value: object) -> object:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return value


def _field(value: object, name: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _string_field(value: object, name: str) -> str:
    field = _field(value, name)
    return "" if field is None else str(field)


__all__ = ["ForecastVerificationResult", "verify_forecast_calibration"]
