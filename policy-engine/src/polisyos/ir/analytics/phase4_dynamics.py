"""Phase 4 closure contracts for dynamics, forecasting, ABMs, and DSCM surfaces."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ABMResultRef,
    ArtifactRefModel,
    DistributionalReportRef,
    DynamicMicrosimValidationReportRef,
    FairnessAuditReportRef,
    MetricValidationReportRef,
    MicrosimCalibrationReportRef,
    RegimeShiftForecastBundleRef,
    SpaceTimeCausalCertificateRef,
    TemporalGraphCausalCertificateRef,
    UncertaintyEnvelopeRef,
    WelfareBundleRef,
)

from .forecasting_uncertainty import ForecastingUncertaintyBundle, HorizonDiagnosticState
from .regime_shift_forecast import (
    RegimeForecastCalibrationStatus,
    RegimeShiftForecastBundle,
    load_regime_shift_forecast_bundle,
)


class Phase4GateStatus(StrEnum):
    """Decision emitted by the Phase 4 temporal dynamics gate."""

    ALLOWED = "allowed"
    REFUSED = "refused"


class Phase4TemporalPolicyGateVerdict(BaseModel):
    """Auditable verdict for a multi-period Phase 4 policy or forecast query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    gate_id: Literal["phase4_temporal_policy_gate"] = "phase4_temporal_policy_gate"
    status: Phase4GateStatus
    horizon: int = Field(ge=1)
    threshold_horizon: int = Field(default=12, ge=1)
    refusal_code: Literal["phase4_regime_gate_failed"] | None = None
    regime_status: str | None = None
    gate_eligible: bool = True
    checked_regime_bundle: bool = False
    red_horizons: tuple[int, ...] = ()
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.status is Phase4GateStatus.ALLOWED


class Phase4DynamicsGateError(ValueError):
    """Raised when a temporal policy query fails the Phase 4 dynamics gate."""

    code = "phase4_regime_gate_failed"

    def __init__(self, verdict: Phase4TemporalPolicyGateVerdict) -> None:
        self.verdict = verdict
        prefix = "phase4_regime_gate_failed"
        if verdict.horizon > verdict.threshold_horizon:
            prefix = (
                f"phase4_regime_gate_failed: forecast beyond horizon "
                f"{verdict.threshold_horizon} requires calibrated regime status"
            )
        super().__init__(prefix + ": " + "; ".join(verdict.reasons))


class Phase4DynamicsGate:
    """Shared fail-closed validator for Phase 4 multi-period policy surfaces."""

    threshold_horizon: int = 12

    def validate(
        self,
        *,
        horizon: int,
        regime_bundle: RegimeShiftForecastBundle | ForecastingUncertaintyBundle | Mapping[str, Any] | None = None,
        regime_bundle_ref: RegimeShiftForecastBundleRef | ArtifactRefModel | Mapping[str, Any] | str | None = None,
        artifact_store: ArtifactStore | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Phase4TemporalPolicyGateVerdict:
        return validate_phase4_temporal_policy_query(
            horizon=horizon,
            regime_bundle=regime_bundle,
            regime_bundle_ref=regime_bundle_ref,
            artifact_store=artifact_store,
            threshold_horizon=self.threshold_horizon,
            metadata=metadata,
        )

    def enforce(
        self,
        *,
        horizon: int,
        regime_bundle: RegimeShiftForecastBundle | ForecastingUncertaintyBundle | Mapping[str, Any] | None = None,
        regime_bundle_ref: RegimeShiftForecastBundleRef | ArtifactRefModel | Mapping[str, Any] | str | None = None,
        artifact_store: ArtifactStore | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Phase4TemporalPolicyGateVerdict:
        verdict = self.validate(
            horizon=horizon,
            regime_bundle=regime_bundle,
            regime_bundle_ref=regime_bundle_ref,
            artifact_store=artifact_store,
            metadata=metadata,
        )
        if not verdict.allowed:
            raise Phase4DynamicsGateError(verdict)
        return verdict


def validate_phase4_temporal_policy_query(
    *,
    horizon: int,
    regime_bundle: RegimeShiftForecastBundle | ForecastingUncertaintyBundle | Mapping[str, Any] | None = None,
    regime_bundle_ref: RegimeShiftForecastBundleRef | ArtifactRefModel | Mapping[str, Any] | str | None = None,
    artifact_store: ArtifactStore | None = None,
    threshold_horizon: int = 12,
    metadata: Mapping[str, Any] | None = None,
) -> Phase4TemporalPolicyGateVerdict:
    """Validate that a temporal query satisfies the Phase 4 regime-aware contract."""

    requested_horizon = max(1, int(horizon))
    threshold = max(1, int(threshold_horizon))
    resolved_metadata = dict(metadata or {})
    ref_resolution_error: str | None = None
    bundle = _coerce_forecast_bundle(regime_bundle)
    if bundle is None and regime_bundle_ref is not None:
        bundle, ref_resolution_error = _load_forecast_bundle_from_ref(
            regime_bundle_ref,
            artifact_store=artifact_store,
        )
        resolved_metadata["regime_shift_forecast_bundle_ref"] = _ref_artifact_id(
            regime_bundle_ref
        )
        if ref_resolution_error is not None:
            resolved_metadata["regime_shift_forecast_bundle_ref_error"] = (
                ref_resolution_error
            )
    reasons: list[str] = []
    red_horizons: list[int] = []
    regime_status: str | None = None
    gate_eligible = True

    if bundle is not None:
        regime_status = _enum_value(_get_attr(bundle, "regime_status"))
        policy = _get_attr(bundle, "horizon_policy")
        gate_eligible = bool(_get_attr(policy, "gate_eligible", True))
        red_horizons = _red_horizons(policy, requested_horizon)
        if not gate_eligible:
            reasons.append("forecast_horizon_policy_not_gate_eligible")
        if red_horizons:
            reasons.append("forecast_horizon_policy_red")

    if requested_horizon > threshold:
        if ref_resolution_error is not None:
            reasons.append(ref_resolution_error)
        if bundle is None:
            reasons.append("missing_regime_shift_forecast_bundle")
        elif regime_status != RegimeForecastCalibrationStatus.CALIBRATED.value:
            reasons.append(f"regime_status_not_calibrated:{regime_status or 'unknown'}")

    refused = bool(reasons)
    return Phase4TemporalPolicyGateVerdict(
        status=Phase4GateStatus.REFUSED if refused else Phase4GateStatus.ALLOWED,
        horizon=requested_horizon,
        threshold_horizon=threshold,
        refusal_code="phase4_regime_gate_failed" if refused else None,
        regime_status=regime_status,
        gate_eligible=gate_eligible,
        checked_regime_bundle=bundle is not None,
        red_horizons=tuple(red_horizons),
        reasons=tuple(reasons),
        metadata=resolved_metadata,
    )


class _ABMExecPlanArtifactRef(ArtifactRefModel):
    """Neutral typed reference to the Foundry execution plan used by an ABM run."""

    kind: Literal["foundry.exec_plan"] = "foundry.exec_plan"
    media_type: Literal["application/json"] = "application/json"


class _ABMMetricsArtifactRef(ArtifactRefModel):
    """Neutral typed reference to metrics emitted by an ABM run."""

    kind: Literal["foundry.metrics"] = "foundry.metrics"
    media_type: Literal["application/json"] = "application/json"


class _ABMMetricObservationBundleArtifactRef(ArtifactRefModel):
    """Neutral typed reference to metric observations emitted by Foundry."""

    kind: Literal["foundry.metric_observation_bundle"] = (
        "foundry.metric_observation_bundle"
    )
    media_type: Literal["application/json"] = "application/json"


class _ABMStateSnapshotArtifactRef(ArtifactRefModel):
    """Neutral typed reference to a Foundry state snapshot."""

    kind: Literal["foundry.state_snapshot"] = "foundry.state_snapshot"
    media_type: Literal["application/json"] = "application/json"


class _ABMEnvironmentArtifactRef(ArtifactRefModel):
    """Neutral typed reference to the Foundry execution environment manifest."""

    kind: Literal["foundry.environment_manifest"] = "foundry.environment_manifest"
    media_type: Literal["application/json"] = "application/json"


class _ABMTraceSliceArtifactRef(ArtifactRefModel):
    """Neutral typed reference to a Foundry execution trace slice."""

    kind: Literal["foundry.trace_slice"] = "foundry.trace_slice"
    media_type: Literal["application/jsonl"] = "application/jsonl"


class _ABMWelfareBoundArtifactRef(ArtifactRefModel):
    """Neutral typed reference to a Foundry welfare-bound report."""

    kind: Literal["foundry.welfare_bound_report"] = "foundry.welfare_bound_report"
    media_type: Literal["application/json"] = "application/json"


class _ABMFeedbackResultArtifactRef(ArtifactRefModel):
    """Neutral typed reference to a Foundry feedback result."""

    kind: Literal["foundry.feedback_result"] = "foundry.feedback_result"
    media_type: Literal["application/json"] = "application/json"


class _ABMIdentifiabilityDiagnosticArtifactRef(ArtifactRefModel):
    """Neutral typed reference to a Foundry identifiability diagnostic."""

    kind: Literal["foundry.identifiability_diagnostic"] = (
        "foundry.identifiability_diagnostic"
    )
    media_type: Literal["application/json"] = "application/json"


class _ABMAttractorAnalysisArtifactRef(ArtifactRefModel):
    """Neutral typed reference to a Foundry attractor-analysis result."""

    kind: Literal["foundry.attractor_analysis_result"] = (
        "foundry.attractor_analysis_result"
    )
    media_type: Literal["application/json"] = "application/json"


class ABMIdentifiabilityCertificate(BaseModel):
    """Lightweight Phase-4 certificate pointing to aggregate-moment ABM diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["certified", "diagnostic_attached", "not_available", "failed"] = (
        "not_available"
    )
    diagnostic_ref: _ABMIdentifiabilityDiagnosticArtifactRef | None = None
    identified: bool | None = None
    method: str = "aggregate_moment_identifiability"
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ABMBifurcationReport(BaseModel):
    """Lightweight Phase-4 bifurcation/attractor report pointer for ABM results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["available", "not_available", "failed"] = "not_available"
    attractor_analysis_ref: _ABMAttractorAnalysisArtifactRef | None = None
    bifurcation_count: int | None = Field(default=None, ge=0)
    attractor_count: int | None = Field(default=None, ge=0)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ABMResult(BaseModel):
    """Neutral Phase-4 analytical result for a completed ABM execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.3", pattern=r"^\d+\.\d+$")
    exec_plan_ref: _ABMExecPlanArtifactRef
    metrics_ref: _ABMMetricsArtifactRef
    metric_observation_bundle_ref: _ABMMetricObservationBundleArtifactRef | None = None
    state_snapshot_ref: _ABMStateSnapshotArtifactRef | None = None
    environment_ref: _ABMEnvironmentArtifactRef | None = None
    environment_fingerprint: str | None = None
    trace_slice_ref: _ABMTraceSliceArtifactRef | None = None
    uncertainty_envelopes: Mapping[str, UncertaintyEnvelopeRef] | None = None
    distributional_report_ref: DistributionalReportRef | None = None
    welfare_bundle_ref: WelfareBundleRef | None = None
    welfare_bound_refs: Mapping[str, _ABMWelfareBoundArtifactRef] | None = None
    metric_validation_report_ref: MetricValidationReportRef | None = None
    fairness_audit_report_ref: FairnessAuditReportRef | None = None
    propagation_config_ref: ArtifactRefModel | None = None
    propagation_report_ref: ArtifactRefModel | None = None
    feedback_result_ref: _ABMFeedbackResultArtifactRef | None = None
    identifiability_diagnostic_ref: _ABMIdentifiabilityDiagnosticArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)
    identifiability_certificate: ABMIdentifiabilityCertificate | None = None
    bifurcation_report: ABMBifurcationReport | None = None


class StrangleReceipt(BaseModel):
    """Content-bound receipt proving the legacy ABM stub was not used."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.ir.phase4.abm_strangle_receipt.v1"] = (
        "policyos.ir.phase4.abm_strangle_receipt.v1"
    )
    receipt_id: str = Field(..., pattern=r"^abm_strangle_receipt_[a-f0-9]{16}$")
    method_id: str = Field(..., min_length=1)
    horizon: int = Field(ge=1)
    payload_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    trajectory_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    metrics_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    diagnostics_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    diagnostics_attached: bool
    legacy_stub_rejected: Literal[True] = True


class StrangleReceiptError(ValueError):
    """Raised when an ABM strangle receipt does not bind to live run content."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def build_strangle_receipt(
    *,
    method_id: str,
    horizon: int,
    payload: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> StrangleReceipt:
    """Build a deterministic ABM strangle receipt from actual run content."""

    normalized_payload = _json_ready(payload)
    normalized_diagnostics = _json_ready(diagnostics)
    trajectory_hash = _stable_hash(
        normalized_payload.get(
            "trajectory",
            normalized_payload.get("queue_length_trajectory", ()),
        )
    )
    metrics_hash = _stable_hash(
        normalized_payload.get(
            "metrics",
            normalized_payload.get("summary", normalized_payload),
        )
    )
    diagnostics_hash = _stable_hash(normalized_diagnostics)
    payload_hash = _stable_hash(
        {
            "method_id": method_id,
            "horizon": int(horizon),
            "payload": normalized_payload,
            "diagnostics": normalized_diagnostics,
            "trajectory_hash": trajectory_hash,
            "metrics_hash": metrics_hash,
            "diagnostics_hash": diagnostics_hash,
        }
    )
    return StrangleReceipt(
        receipt_id=f"abm_strangle_receipt_{payload_hash.removeprefix('sha256:')[:16]}",
        method_id=method_id,
        horizon=max(1, int(horizon)),
        payload_hash=payload_hash,
        trajectory_hash=trajectory_hash,
        metrics_hash=metrics_hash,
        diagnostics_hash=diagnostics_hash,
        diagnostics_attached=bool(normalized_diagnostics),
    )


def verify_strangle_receipt(
    receipt: StrangleReceipt | Mapping[str, Any] | str,
    *,
    method_id: str,
    horizon: int,
    payload: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> None:
    """Recompute and verify an ABM strangle receipt against actual run content."""

    parsed = _coerce_strangle_receipt(receipt)
    expected = build_strangle_receipt(
        method_id=method_id,
        horizon=horizon,
        payload=payload,
        diagnostics=diagnostics,
    )
    if parsed != expected:
        raise StrangleReceiptError("receipt_content_mismatch")
    if not parsed.diagnostics_attached:
        raise StrangleReceiptError("receipt_diagnostics_missing")


class DynamicMicrosimValidationReport(BaseModel):
    """Public Phase-4 validation report that can block dynamic microsimulation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    validation_status: Literal["green", "amber", "red", "not_run"]
    source_status: str
    can_run_dynamic_microsim: bool
    refusal_code: Literal["dynamic_microsim_validation_red"] | None = None
    diagnostic_ref: ArtifactRefModel | None = None
    microsim_calibration_report_ref: MicrosimCalibrationReportRef | None = None
    comparison_dataset: str | None = None
    horizons_reported: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_report(self) -> DynamicMicrosimValidationReport:
        if self.validation_status == "red":
            if self.can_run_dynamic_microsim:
                raise ValueError("red dynamic microsim validation reports must block execution")
            if self.refusal_code != "dynamic_microsim_validation_red":
                raise ValueError("red dynamic microsim validation reports require refusal_code")
        return self


class DynamicMicrosimValidationError(ValueError):
    """Raised when a dynamic microsim validation report blocks execution."""

    code = "dynamic_microsim_validation_red"

    def __init__(self, report: DynamicMicrosimValidationReport) -> None:
        self.report = report
        super().__init__("dynamic_microsim_validation_red: " + "; ".join(report.blocking_reasons))


def build_dynamic_microsim_validation_report(
    diagnostic: Any,
    *,
    diagnostic_ref: Any | None = None,
    microsim_calibration_report_ref: MicrosimCalibrationReportRef | Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> DynamicMicrosimValidationReport:
    """Build the public report from the existing dynamic validation diagnostic."""

    source_status = str(_enum_value(getattr(diagnostic, "status", "not_run")) or "not_run")
    validation_status = _dynamic_validation_status(source_status)
    blocking = []
    if validation_status == "red":
        blocking.append("dynamic_microsim_validation_red")
    warnings = tuple(str(item) for item in getattr(diagnostic, "warnings", ()) or ())
    report_metadata = dict(metadata or {})
    raw_metadata = getattr(diagnostic, "metadata", None)
    if isinstance(raw_metadata, Mapping):
        report_metadata.update(raw_metadata)
    return DynamicMicrosimValidationReport(
        validation_status=validation_status,
        source_status=source_status,
        can_run_dynamic_microsim=validation_status != "red",
        refusal_code="dynamic_microsim_validation_red" if validation_status == "red" else None,
        diagnostic_ref=_artifact_ref_model(diagnostic_ref),
        microsim_calibration_report_ref=_coerce_ref(
            microsim_calibration_report_ref,
            MicrosimCalibrationReportRef,
        ),
        comparison_dataset=getattr(diagnostic, "comparison_dataset", None),
        horizons_reported=tuple(int(item) for item in getattr(diagnostic, "horizons_reported", ()) or ()),
        warnings=warnings,
        blocking_reasons=tuple(blocking),
        diagnostics=dict(getattr(diagnostic, "diagnostics", {}) or {}),
        metadata=report_metadata,
    )


def enforce_dynamic_microsim_validation_report(
    report: DynamicMicrosimValidationReport | Mapping[str, Any] | None,
) -> DynamicMicrosimValidationReport | None:
    """Fail closed when a dynamic microsim validation report is red."""

    if report is None:
        return None
    validated = (
        report
        if isinstance(report, DynamicMicrosimValidationReport)
        else DynamicMicrosimValidationReport.model_validate(report)
    )
    if validated.validation_status == "red":
        raise DynamicMicrosimValidationError(validated)
    return validated


class EquilibriumMultiplicityWelfareAnnotation(BaseModel):
    """Phase-3 welfare annotation carrying Phase-4 equilibrium multiplicity risk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["unique", "multiple", "unresolved", "not_checked"] = "not_checked"
    report_ref: ArtifactRefModel | None = None
    selection_dependence: bool = False
    materiality_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalGraphCausalCertificate(BaseModel):
    """Shared Phase-4 DSCM certificate for temporal and dynamic graph causality."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    certificate_type: Literal["temporal_graph_causal_certificate"] = (
        "temporal_graph_causal_certificate"
    )
    status: Literal["identified", "oracle_needed", "blocked", "degraded"]
    dscm_scope: str = "dynamic_graph_local_independence_v1"
    temporal_identification_certificate: dict[str, Any] | None = None
    local_independence_certificate: dict[str, Any] | None = None
    temporal_identification_certificate_ref: ArtifactRefModel | None = None
    local_independence_certificate_ref: ArtifactRefModel | None = None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpaceTimeCausalCertificate(BaseModel):
    """Shared Phase-4 DSCM certificate for space-time causal inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    certificate_type: Literal["space_time_causal_certificate"] = (
        "space_time_causal_certificate"
    )
    status: Literal["identified", "model_extrapolation", "blocked"]
    dscm_scope: str = "controlled_diffusion_reaction_st_dscm_v1"
    identification_certificate: dict[str, Any]
    spde_scope: str = "fem_spde_g_computation_v1"
    assumptions: dict[str, str] = Field(default_factory=dict)
    caveats: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_temporal_graph_causal_certificate(
    *,
    temporal_identification_certificate: Any | None,
    local_independence_certificate: Any | None,
    warnings: tuple[str, ...] = (),
    metadata: Mapping[str, Any] | None = None,
) -> TemporalGraphCausalCertificate:
    """Wrap existing temporal/local-independence certificates in the exact Phase-4 schema."""

    local_payload = _model_payload(local_independence_certificate)
    temporal_payload = _model_payload(temporal_identification_certificate)
    local_status = str((local_payload or {}).get("verification_status", "")).strip()
    if local_status == "identified":
        status: Literal["identified", "oracle_needed", "blocked", "degraded"] = "identified"
    elif local_status == "blocked":
        status = "blocked"
    elif local_status:
        status = "oracle_needed"
    else:
        status = "degraded"
    assumptions = tuple(str(item) for item in (local_payload or {}).get("assumptions", ()) or ())
    return TemporalGraphCausalCertificate(
        status=status,
        temporal_identification_certificate=temporal_payload,
        local_independence_certificate=local_payload,
        assumptions=assumptions,
        warnings=tuple(str(item) for item in warnings),
        metadata=dict(metadata or {}),
    )


def build_space_time_causal_certificate(
    identification_certificate: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> SpaceTimeCausalCertificate:
    """Wrap the space-time identification certificate in the exact Phase-4 schema."""

    payload = _model_payload(identification_certificate) or {}
    status_value = str(payload.get("status", "")).strip()
    if status_value == "blocked":
        status: Literal["identified", "model_extrapolation", "blocked"] = "blocked"
    elif status_value == "model_extrapolation":
        status = "model_extrapolation"
    else:
        status = "identified"
    return SpaceTimeCausalCertificate(
        status=status,
        identification_certificate=payload,
        assumptions={str(key): str(value) for key, value in dict(payload.get("assumptions", {})).items()},
        caveats=tuple(str(item) for item in payload.get("caveats", ()) or ()),
        metadata=dict(metadata or {}),
    )


def persist_abm_result(
    store: ArtifactStore,
    result: ABMResult,
    *,
    inputs: list[InputRef] | None = None,
) -> ABMResultRef:
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.abm_result",
        schema_name="ir.abm_result",
        schema_version="1.0",
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ABMResultRef.model_validate(ref)


def load_abm_result(store: ArtifactStore, ref: ABMResultRef) -> ABMResult:
    return ABMResult.model_validate(get_json_artifact(store, ref.artifact_id))


def persist_dynamic_microsim_validation_report(
    store: ArtifactStore,
    report: DynamicMicrosimValidationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> DynamicMicrosimValidationReportRef:
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.dynamic_microsim_validation_report",
        schema_name="ir.dynamic_microsim_validation_report",
        schema_version="1.0",
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DynamicMicrosimValidationReportRef.model_validate(ref)


def load_dynamic_microsim_validation_report(
    store: ArtifactStore,
    ref: DynamicMicrosimValidationReportRef,
) -> DynamicMicrosimValidationReport:
    return DynamicMicrosimValidationReport.model_validate(
        get_json_artifact(store, ref.artifact_id)
    )


def persist_temporal_graph_causal_certificate(
    store: ArtifactStore,
    certificate: TemporalGraphCausalCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> TemporalGraphCausalCertificateRef:
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.temporal_graph_causal_certificate",
        schema_name="ir.temporal_graph_causal_certificate",
        schema_version="1.0",
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TemporalGraphCausalCertificateRef.model_validate(ref)


def load_temporal_graph_causal_certificate(
    store: ArtifactStore,
    ref: TemporalGraphCausalCertificateRef,
) -> TemporalGraphCausalCertificate:
    return TemporalGraphCausalCertificate.model_validate(get_json_artifact(store, ref.artifact_id))


def persist_space_time_causal_certificate(
    store: ArtifactStore,
    certificate: SpaceTimeCausalCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> SpaceTimeCausalCertificateRef:
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.space_time_causal_certificate",
        schema_name="ir.space_time_causal_certificate",
        schema_version="1.0",
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SpaceTimeCausalCertificateRef.model_validate(ref)


def load_space_time_causal_certificate(
    store: ArtifactStore,
    ref: SpaceTimeCausalCertificateRef,
) -> SpaceTimeCausalCertificate:
    return SpaceTimeCausalCertificate.model_validate(get_json_artifact(store, ref.artifact_id))


def _coerce_forecast_bundle(
    value: RegimeShiftForecastBundle | ForecastingUncertaintyBundle | Mapping[str, Any] | None,
) -> RegimeShiftForecastBundle | ForecastingUncertaintyBundle | Mapping[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, (RegimeShiftForecastBundle, ForecastingUncertaintyBundle)):
        return value
    if "regime_status" in value and "method_fqn" not in value:
        return dict(value)
    if "regime_status" in value:
        return RegimeShiftForecastBundle.model_validate(value)
    return ForecastingUncertaintyBundle.model_validate(value)


def _load_forecast_bundle_from_ref(
    value: RegimeShiftForecastBundleRef | ArtifactRefModel | Mapping[str, Any] | str,
    *,
    artifact_store: ArtifactStore | None,
) -> tuple[RegimeShiftForecastBundle | None, str | None]:
    if artifact_store is None:
        return None, "regime_shift_forecast_bundle_ref_store_missing"
    try:
        ref = _coerce_regime_shift_forecast_bundle_ref(value)
        return load_regime_shift_forecast_bundle(artifact_store, ref), None
    except Exception:
        return None, "regime_shift_forecast_bundle_ref_load_failed"


def _coerce_regime_shift_forecast_bundle_ref(
    value: RegimeShiftForecastBundleRef | ArtifactRefModel | Mapping[str, Any] | str,
) -> RegimeShiftForecastBundleRef:
    if isinstance(value, RegimeShiftForecastBundleRef):
        return value
    if isinstance(value, str):
        return RegimeShiftForecastBundleRef(artifact_id=value)
    payload = value.model_dump(mode="python") if hasattr(value, "model_dump") else dict(value)
    return RegimeShiftForecastBundleRef.model_validate(payload)


def _ref_artifact_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "artifact_id"):
        return str(value.artifact_id)
    if isinstance(value, Mapping) and value.get("artifact_id") is not None:
        return str(value["artifact_id"])
    return None


def _red_horizons(policy: Any, requested_horizon: int) -> list[int]:
    if policy is None:
        return []
    red: list[int] = []
    for rule in _get_attr(policy, "rules", ()) or ():
        state = _enum_value(_get_attr(rule, "diagnostic_state"))
        if state != HorizonDiagnosticState.RED.value:
            continue
        start = int(_get_attr(rule, "horizon_start", requested_horizon))
        end = int(_get_attr(rule, "horizon_end", start))
        if start <= requested_horizon and end >= 1:
            red.extend(range(max(1, start), min(requested_horizon, end) + 1))
    return sorted(set(red))


def _dynamic_validation_status(source_status: str) -> Literal["green", "amber", "red", "not_run"]:
    normalized = source_status.strip().lower()
    if normalized == "pass":
        return "green"
    if normalized in {"warn", "inconclusive"}:
        return "amber"
    if normalized == "not_run":
        return "red"
    return "red"


def _artifact_ref_model(value: Any | None) -> ArtifactRefModel | None:
    if value is None:
        return None
    if isinstance(value, ArtifactRefModel):
        return value
    payload = value.model_dump(mode="python") if hasattr(value, "model_dump") else dict(value)
    return ArtifactRefModel.model_validate(payload)


def _get_attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _coerce_ref(value: Any | None, cls: type[Any]) -> Any | None:
    if value is None:
        return None
    if isinstance(value, cls):
        return value
    payload = value.model_dump(mode="python") if hasattr(value, "model_dump") else dict(value)
    return cls.model_validate(payload)


def _model_payload(value: Any | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"cannot serialize certificate payload of type {type(value).__name__}")


def _coerce_strangle_receipt(
    value: StrangleReceipt | Mapping[str, Any] | str,
) -> StrangleReceipt:
    if isinstance(value, StrangleReceipt):
        return value
    if isinstance(value, str):
        return StrangleReceipt.model_validate(json.loads(value))
    return StrangleReceipt.model_validate(value)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        _json_ready(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


__all__ = [
    "ABMBifurcationReport",
    "ABMIdentifiabilityCertificate",
    "ABMResult",
    "DynamicMicrosimValidationError",
    "DynamicMicrosimValidationReport",
    "EquilibriumMultiplicityWelfareAnnotation",
    "Phase4DynamicsGate",
    "Phase4DynamicsGateError",
    "Phase4GateStatus",
    "Phase4TemporalPolicyGateVerdict",
    "SpaceTimeCausalCertificate",
    "StrangleReceipt",
    "StrangleReceiptError",
    "TemporalGraphCausalCertificate",
    "build_dynamic_microsim_validation_report",
    "build_space_time_causal_certificate",
    "build_strangle_receipt",
    "build_temporal_graph_causal_certificate",
    "enforce_dynamic_microsim_validation_report",
    "load_abm_result",
    "load_dynamic_microsim_validation_report",
    "load_space_time_causal_certificate",
    "load_temporal_graph_causal_certificate",
    "persist_abm_result",
    "persist_dynamic_microsim_validation_report",
    "persist_space_time_causal_certificate",
    "persist_temporal_graph_causal_certificate",
    "validate_phase4_temporal_policy_query",
    "verify_strangle_receipt",
]
