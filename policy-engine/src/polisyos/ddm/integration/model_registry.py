"""Model-registry gate integration for DDM-15.7 readiness states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

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

    _applicability_projection: DDMApplicabilityProjection | None = PrivateAttr(default=None)


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
    last_shift_event: ShiftRiskEvent | None = None,
    last_degradation_event: PerformanceDegradationEvent | None = None,
    active_incident_id: str | None = None,
) -> ModelRegistryReadinessRecord:
    """Build the durable registry state described by the Phase 5 plan."""

    applicability = _resolve_applicability_projection(
        readiness_event=readiness_event,
        calibration_audit=calibration_audit,
        metric_budget=metric_budget,
        last_shift_event=last_shift_event,
    )
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
            readiness_event.promotion_allowed
            and applicability.validity is ApplicabilityStatus.VALID
            and applicability.observation_window is ObservationWindowStatus.OBSERVED
            and applicability.identity_bound
            and applicability.policy_id == DEFAULT_READINESS_POLICY_ID
            and applicability.policy_version == DEFAULT_READINESS_POLICY_VERSION
        ),
    )
    record._applicability_projection = applicability
    return record


def evaluate_registry_gate(
    record: ModelRegistryReadinessRecord,
    *,
    owner_signoff: bool = False,
    applicability: DDMApplicabilityProjection | None = None,
) -> RegistryGateDecision:
    """Evaluate registry-promotion eligibility from DDM-15.7 state."""

    projection = applicability or record._applicability_projection
    if not record.empirical_fp_certificate:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="calibration_fp_certificate_failed",
            required_actions=["recalibrate_detector"],
        )
    if projection is None:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="applicability_not_established",
            required_actions=["reconcile_applicability_projection"],
        )
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
        or (
            projection.valid_until is not None
            and projection.effective_at is not None
            and projection.effective_at > projection.valid_until
        )
        or bool(
            set(projection.observed_invalidation_triggers)
            - set(projection.invalidation_triggers)
        )
        or bool(projection.observed_invalidation_triggers)
        or bool(projection.invalidation_reasons)
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


def _resolve_applicability_projection(
    *,
    readiness_event: ReadinessStateEvent,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    last_shift_event: ShiftRiskEvent | None,
) -> DDMApplicabilityProjection:
    """Reconcile one runtime applicability projection at the registry boundary."""

    inherited = readiness_event.applicability
    projection = inherited or DDMApplicabilityProjection(
        model_id=readiness_event.model_id,
        model_version=readiness_event.model_version,
        observation_window=ObservationWindowStatus.OBSERVED,
        effective_at=readiness_event.timestamp,
        policy_provenance=GatePredicateProvenance.RECOMPUTED,
        observation_provenance=GatePredicateProvenance.RECOMPUTED,
    )
    reasons = list(projection.invalidation_reasons)
    validity = calibration_audit.validity
    observed_triggers = list(calibration_audit.observed_invalidation_triggers)
    declared_triggers = list(calibration_audit.invalidation_triggers)
    unknown_triggers = sorted(set(observed_triggers) - set(declared_triggers))
    matched_triggers = sorted(set(observed_triggers) & set(declared_triggers))
    if unknown_triggers:
        validity = ApplicabilityStatus.INVALID
        if "invalidation_trigger_binding_unknown" not in reasons:
            reasons.append("invalidation_trigger_binding_unknown")
    if matched_triggers:
        validity = ApplicabilityStatus.INVALID
        for trigger in matched_triggers:
            if trigger not in reasons:
                reasons.append(trigger)
    effective_at = calibration_audit.validity_checked_at or readiness_event.timestamp
    if projection.effective_at is not None and projection.effective_at > effective_at:
        effective_at = projection.effective_at
    if calibration_audit.valid_until is not None and effective_at > calibration_audit.valid_until:
        validity = ApplicabilityStatus.INVALID
        if "calibration_expired" not in reasons:
            reasons.append("calibration_expired")
    if validity is ApplicabilityStatus.NOT_ESTABLISHED:
        validity = ApplicabilityStatus.VALID
    if validity is ApplicabilityStatus.INVALID:
        for reason in calibration_audit.validity_reasons:
            if reason not in reasons:
                reasons.append(reason)

    identity_reasons: list[str] = []
    if (
        calibration_audit.model_id is not None
        and calibration_audit.model_id != readiness_event.model_id
    ):
        identity_reasons.append("calibration_model_id")
    if (
        calibration_audit.model_version is not None
        and calibration_audit.model_version != readiness_event.model_version
    ):
        identity_reasons.append("calibration_model_version")
    if metric_budget.model_id != readiness_event.model_id:
        identity_reasons.append("metric_budget_model_id")
    if metric_budget.model_version != readiness_event.model_version:
        identity_reasons.append("metric_budget_model_version")
    if last_shift_event is not None:
        if last_shift_event.model_id != readiness_event.model_id:
            identity_reasons.append("model_id")
        if last_shift_event.model_version != readiness_event.model_version:
            identity_reasons.append("model_version")
        if last_shift_event.detector_id != calibration_audit.detector_id:
            identity_reasons.append("detector_id")
        if last_shift_event.stationarity_regime_id != calibration_audit.stationarity_regime_id:
            identity_reasons.append("stationarity_regime_id")
        if last_shift_event.calibration_id != calibration_audit.calibration_id:
            identity_reasons.append("calibration_id")
    for reason in identity_reasons:
        if reason not in reasons:
            reasons.append(reason)

    policy_known = (
        projection.policy_id == DEFAULT_READINESS_POLICY_ID
        and projection.policy_version == DEFAULT_READINESS_POLICY_VERSION
    )
    identity_bound = not identity_reasons
    identity_provenance = GatePredicateProvenance.INDEPENDENTLY_RECONCILED
    validity_provenance = GatePredicateProvenance.RECOMPUTED
    return projection.model_copy(
        update={
            "model_id": readiness_event.model_id,
            "model_version": readiness_event.model_version,
            "detector_id": calibration_audit.detector_id,
            "stationarity_regime_id": calibration_audit.stationarity_regime_id,
            "calibration_id": calibration_audit.calibration_id,
            "metric": metric_budget.metric,
            "metric_budget_model_id": metric_budget.model_id,
            "metric_budget_model_version": metric_budget.model_version,
            "valid_until": calibration_audit.valid_until,
            "effective_at": effective_at,
            "validity": validity,
            "invalidation_reasons": reasons,
            "invalidation_triggers": declared_triggers,
            "observed_invalidation_triggers": observed_triggers,
            "identity_bound": identity_bound,
            "baseline_allowed": readiness_event.promotion_allowed,
            "persisted_veto": (
                readiness_event.readiness_state in {ReadinessState.R4, ReadinessState.R3}
                and not readiness_event.promotion_allowed
            ),
            "policy_provenance": (
                GatePredicateProvenance.RECOMPUTED
                if policy_known
                else GatePredicateProvenance.NOT_ESTABLISHED
            ),
            "validity_provenance": validity_provenance,
            "identity_provenance": identity_provenance,
            "observation_provenance": (
                projection.observation_provenance
                if projection.observation_provenance
                is not GatePredicateProvenance.NOT_ESTABLISHED
                else GatePredicateProvenance.RECOMPUTED
            ),
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
