"""Model-registry gate integration for DDM-15.7 readiness states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ddm.contracts.events import (
    ApplicabilityStatus,
    CalibrationAudit,
    DDMApplicabilityProjection,
    DEFAULT_READINESS_POLICY_ID,
    DEFAULT_READINESS_POLICY_VERSION,
    GatePredicateProvenance,
    ObservationWindowStatus,
    PerformanceDegradationEvent,
    ReadinessState,
    ReadinessStateEvent,
    ShiftRiskEvent,
)

if TYPE_CHECKING:
    from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy


class ModelRegistryReadinessRecord(BaseModel):
    """Registry-facing readiness record for one deployed model version."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    stationarity_regime_id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    system_fp_budget: dict[str, float | str] = Field(default_factory=dict)
    empirical_fp_certificate: bool
    primary_metric_budget: dict[str, float | str] = Field(default_factory=dict)
    readiness_state: ReadinessState
    readiness_score: int = Field(ge=0, le=100)
    last_shift_event: str | None = None
    last_degradation_event: str | None = None
    required_action: str | None = None
    active_incident_id: str | None = None
    promotion_allowed: bool


class RegistryGateDecision(BaseModel):
    """Decision returned by the model-registry promotion gate."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    promotion_allowed: bool
    reason: str = Field(min_length=1)
    required_actions: list[str] = Field(default_factory=list)


def build_model_registry_record(
    *,
    readiness_event: ReadinessStateEvent,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    applicability: DDMApplicabilityProjection | None = None,
    last_shift_event: ShiftRiskEvent | None = None,
    last_degradation_event: PerformanceDegradationEvent | None = None,
    active_incident_id: str | None = None,
) -> ModelRegistryReadinessRecord:
    """Build the durable registry state described by the Phase 5 plan."""

    record = ModelRegistryReadinessRecord(
        model_id=readiness_event.model_id,
        model_version=readiness_event.model_version,
        stationarity_regime_id=calibration_audit.stationarity_regime_id,
        calibration_id=calibration_audit.calibration_id,
        system_fp_budget={
            "horizon": calibration_audit.horizon,
            "alpha": calibration_audit.alpha,
            "empirical_fp_upper_95": calibration_audit.empirical_fp_upper_95,
        },
        empirical_fp_certificate=calibration_audit.pass_,
        primary_metric_budget=_metric_budget_payload(metric_budget),
        readiness_state=readiness_event.readiness_state,
        readiness_score=readiness_event.readiness_score,
        last_shift_event=None if last_shift_event is None else last_shift_event.shift_event_id,
        last_degradation_event=(
            None if last_degradation_event is None else last_degradation_event.event_id
        ),
        required_action=(
            None if not readiness_event.required_actions else readiness_event.required_actions[0]
        ),
        active_incident_id=active_incident_id,
        promotion_allowed=(
            applicability is not None
            and readiness_event.promotion_allowed
            and applicability.is_authority_ready()
        ),
    )
    return record


def evaluate_registry_gate(
    record: ModelRegistryReadinessRecord,
    *,
    owner_signoff: bool = False,
    applicability: DDMApplicabilityProjection | None = None,
) -> RegistryGateDecision:
    """Evaluate registry-promotion eligibility from DDM-15.7 state."""

    if not record.empirical_fp_certificate:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="calibration_fp_certificate_failed",
            required_actions=["recalibrate_detector"],
        )
    if applicability is None:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="applicability_not_established",
            required_actions=["reconcile_applicability_projection"],
        )
    projection = applicability
    if (
        projection.policy_id != DEFAULT_READINESS_POLICY_ID
        or projection.policy_version != DEFAULT_READINESS_POLICY_VERSION
        or projection.policy_provenance is not GatePredicateProvenance.RECOMPUTED
    ):
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="readiness_policy_version_unknown",
            required_actions=["reconcile_readiness_policy"],
        )
    if (
        projection.validity is not ApplicabilityStatus.VALID
        or projection.validity_provenance is not GatePredicateProvenance.RECOMPUTED
        or projection.effective_at is None
    ):
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason=(
                "calibration_validity_failed"
                if not projection.invalidation_reasons
                else "calibration_" + "_".join(projection.invalidation_reasons)
            ),
            required_actions=["revalidate_calibration"],
        )
    if (
        projection.observation_window is not ObservationWindowStatus.OBSERVED
        or projection.observation_provenance is not GatePredicateProvenance.RECOMPUTED
    ):
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="observation_window_unavailable",
            required_actions=["obtain_observation_window"],
        )
    if (
        projection.model_id != record.model_id
        or projection.model_version != record.model_version
        or projection.metric_budget_model_id != record.model_id
        or projection.metric_budget_model_version != record.model_version
        or projection.stationarity_regime_id != record.stationarity_regime_id
        or projection.calibration_id != record.calibration_id
        or not projection.identity_bound
        or bool(projection.identity_reasons)
        or projection.identity_provenance is not GatePredicateProvenance.INDEPENDENTLY_RECONCILED
    ):
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="applicability_identity_mismatch",
            required_actions=["reconcile_registry_bindings"],
        )
    if projection.persisted_veto or (
        record.readiness_state in {ReadinessState.R4, ReadinessState.R3}
        and (not projection.baseline_allowed or not record.promotion_allowed)
    ):
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="persisted_readiness_veto",
            required_actions=[] if record.required_action is None else [record.required_action],
        )
    if record.readiness_state in {ReadinessState.R4, ReadinessState.R3}:
        if not record.promotion_allowed:
            return RegistryGateDecision(
                model_id=record.model_id,
                model_version=record.model_version,
                promotion_allowed=False,
                reason="persisted_readiness_veto",
                required_actions=[] if record.required_action is None else [record.required_action],
            )
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=True,
            reason=f"{record.readiness_state.value}_promotion_allowed",
            required_actions=[] if record.required_action is None else [record.required_action],
        )
    if record.readiness_state is ReadinessState.R2 and owner_signoff:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=True,
            reason="R2_owner_signoff_allows_limited_expansion",
            required_actions=[] if record.required_action is None else [record.required_action],
        )
    return RegistryGateDecision(
        model_id=record.model_id,
        model_version=record.model_version,
        promotion_allowed=False,
        reason=f"{record.readiness_state.value}_blocks_promotion",
        required_actions=[] if record.required_action is None else [record.required_action],
    )


def bind_applicability_projection(
    *,
    projection: DDMApplicabilityProjection,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    last_shift_event: ShiftRiskEvent | None,
) -> DDMApplicabilityProjection:
    """Bind checked calibration and budget identities without recomputing validity."""

    identity_reasons = list(projection.identity_reasons)
    if calibration_audit.model_id is None:
        identity_reasons.append("calibration_model_binding_not_established")
    if (
        calibration_audit.model_id is not None
        and calibration_audit.model_id != projection.model_id
    ):
        identity_reasons.append("calibration_model_id")
    if calibration_audit.model_version is None:
        identity_reasons.append("calibration_model_binding_not_established")
    if (
        calibration_audit.model_version is not None
        and calibration_audit.model_version != projection.model_version
    ):
        identity_reasons.append("calibration_model_version")
    if metric_budget.model_id != projection.model_id:
        identity_reasons.append("metric_budget_model_id")
    if metric_budget.model_version != projection.model_version:
        identity_reasons.append("metric_budget_model_version")
    if last_shift_event is not None:
        if last_shift_event.model_id != projection.model_id:
            identity_reasons.append("model_id")
        if last_shift_event.model_version != projection.model_version:
            identity_reasons.append("model_version")
        if last_shift_event.detector_id != calibration_audit.detector_id:
            identity_reasons.append("detector_id")
        if last_shift_event.stationarity_regime_id != calibration_audit.stationarity_regime_id:
            identity_reasons.append("stationarity_regime_id")
        if last_shift_event.calibration_id != calibration_audit.calibration_id:
            identity_reasons.append("calibration_id")
    identity_reasons = sorted(set(identity_reasons))
    validity = calibration_audit.validity
    return projection.model_copy(
        update={
            "detector_id": calibration_audit.detector_id,
            "stationarity_regime_id": calibration_audit.stationarity_regime_id,
            "calibration_id": calibration_audit.calibration_id,
            "metric": metric_budget.metric,
            "metric_budget_model_id": metric_budget.model_id,
            "metric_budget_model_version": metric_budget.model_version,
            "valid_until": calibration_audit.valid_until,
            "invalidation_reasons": list(calibration_audit.validity_reasons),
            "invalidation_triggers": list(calibration_audit.invalidation_triggers),
            "observed_invalidation_triggers": list(
                calibration_audit.observed_invalidation_triggers
            ),
            "validity": validity,
            "effective_at": calibration_audit.validity_checked_at,
            "validity_provenance": (
                GatePredicateProvenance.RECOMPUTED
                if (
                    calibration_audit.validity_checked_at is not None
                    and validity is not ApplicabilityStatus.NOT_ESTABLISHED
                )
                else GatePredicateProvenance.NOT_ESTABLISHED
            ),
            "identity_reasons": identity_reasons,
            "identity_bound": not identity_reasons,
            "identity_provenance": GatePredicateProvenance.INDEPENDENTLY_RECONCILED,
        }
    )


def _metric_budget_payload(metric_budget: MetricBudgetPolicy) -> dict[str, float | str]:
    payload: dict[str, float | str] = {
        "metric": metric_budget.metric,
        "metric_direction": metric_budget.metric_direction.value,
        "reference_value": metric_budget.reference_value,
    }
    if metric_budget.minimum_acceptable_value is not None:
        payload["minimum_acceptable_value"] = metric_budget.minimum_acceptable_value
    if metric_budget.maximum_acceptable_value is not None:
        payload["maximum_acceptable_value"] = metric_budget.maximum_acceptable_value
    return payload
