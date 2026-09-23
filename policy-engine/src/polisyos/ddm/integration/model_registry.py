"""Model-registry gate integration for DDM-15.7 readiness states."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from polisyos.ddm.calibration.audit import (
    _CalibrationValidityEvidence,
    _check_bound_calibration_validity,
)
from polisyos.ddm.integration.events import (
    CalibrationAudit,
    CalibrationValidityProjection,
    PerformanceDegradationEvent,
    ReadinessState,
    ReadinessStateEvent,
    ShiftRiskEvent,
)

if TYPE_CHECKING:
    from polisyos.ddm.calibration.calibrate import CalibrationReport
    from polisyos.ddm.readiness.readiness_mapper import MetricBudgetPolicy


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
    calibration_validity: CalibrationValidityProjection | None = None
    _calibration_validity_evidence: _CalibrationValidityEvidence | None = PrivateAttr(
        default=None
    )
    _identity_binding_reasons: tuple[str, ...] = PrivateAttr(default=())


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
    _calibration_validity_evidence: _CalibrationValidityEvidence | None = None,
) -> ModelRegistryReadinessRecord:
    """Build the durable registry state described by the Phase 5 plan."""

    identity_binding_reasons = _registry_identity_binding_reasons(
        model_id=readiness_event.model_id,
        model_version=readiness_event.model_version,
        calibration_audit=calibration_audit,
        metric_budget=metric_budget,
        last_shift_event=last_shift_event,
        last_degradation_event=last_degradation_event,
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
            and calibration_audit.pass_
            and _calibration_validity_is_authoritative(
                _calibration_validity_evidence,
                model_id=readiness_event.model_id,
                model_version=readiness_event.model_version,
            )
            and not identity_binding_reasons
        ),
        calibration_validity=(
            None
            if _calibration_validity_evidence is None
            else _calibration_validity_evidence.projection
        ),
    )
    record._calibration_validity_evidence = _calibration_validity_evidence
    record._identity_binding_reasons = identity_binding_reasons
    return record


def rebind_calibration_validity(
    record: ModelRegistryReadinessRecord,
    *,
    report: CalibrationReport,
    calibration_audit: CalibrationAudit,
    now: datetime,
    observed_invalidation_triggers: list[str] | None,
) -> ModelRegistryReadinessRecord:
    """Recheck a persisted projection against its exact source context.

    A public registry payload never carries checker authority.  A caller must
    provide the exact calibration report, projected audit, effective time, and
    trigger observation context before this function can attach fresh private
    checker evidence.  Legacy records without the projection remain
    ``not_established`` even when source context is later available.
    """

    rebound = record.model_copy(deep=True)
    if record.calibration_validity is None:
        rebound._calibration_validity_evidence = None
        return rebound
    evidence = _check_bound_calibration_validity(
        calibration_id=calibration_audit.calibration_id,
        report=report,
        audit=calibration_audit,
        now=now,
        observed_invalidation_triggers=observed_invalidation_triggers,
        expected_projection=record.calibration_validity,
    )
    if evidence.is_bound:
        rebound.calibration_validity = evidence.projection
    rebound._calibration_validity_evidence = evidence
    return rebound


def evaluate_registry_gate(
    record: ModelRegistryReadinessRecord,
    *,
    owner_signoff: bool = False,
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
    if record._identity_binding_reasons:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason=record._identity_binding_reasons[0],
            required_actions=["reconcile_registry_bindings"],
        )
    if record.readiness_state in {ReadinessState.R4, ReadinessState.R3}:
        applicability_reason = _calibration_validity_block_reason(record)
        if applicability_reason is not None:
            return RegistryGateDecision(
                model_id=record.model_id,
                model_version=record.model_version,
                promotion_allowed=False,
                reason=applicability_reason,
                required_actions=["revalidate_calibration"],
            )
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
        applicability_reason = _calibration_validity_block_reason(record)
        if applicability_reason is not None:
            return RegistryGateDecision(
                model_id=record.model_id,
                model_version=record.model_version,
                promotion_allowed=False,
                reason=applicability_reason,
                required_actions=["revalidate_calibration"],
            )
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


def _calibration_validity_is_authoritative(
    evidence: _CalibrationValidityEvidence | None,
    *,
    model_id: str,
    model_version: str,
) -> bool:
    """Return whether checker-owned current validity is available and true."""

    return (
        evidence is not None
        and evidence.is_bound
        and evidence.model_id == model_id
        and evidence.model_version == model_version
        and evidence.status.valid
        and evidence.projection.observation_status == "observed"
        and evidence.projection.status == "valid"
    )


def _registry_identity_binding_reasons(
    *,
    model_id: str,
    model_version: str,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    last_shift_event: ShiftRiskEvent | None,
    last_degradation_event: PerformanceDegradationEvent | None,
) -> tuple[str, ...]:
    """Return fail-closed reasons for foreign or legacy window inputs."""

    reasons: list[str] = []
    if calibration_audit.model_id is None or calibration_audit.model_version is None:
        reasons.append("calibration_model_identity_not_established")
    elif (
        calibration_audit.model_id != model_id
        or calibration_audit.model_version != model_version
    ):
        reasons.append("calibration_model_identity_mismatch")

    if metric_budget.model_id != model_id or metric_budget.model_version != model_version:
        reasons.append("metric_budget_model_identity_mismatch")

    if last_shift_event is not None and (
        last_shift_event.model_id != model_id
        or last_shift_event.model_version != model_version
    ):
        reasons.append("shift_event_model_identity_mismatch")

    if last_degradation_event is not None and (
        last_degradation_event.model_id != model_id
        or last_degradation_event.model_version != model_version
    ):
        reasons.append("degradation_event_model_identity_mismatch")

    return tuple(dict.fromkeys(reasons))


def _calibration_validity_block_reason(
    record: ModelRegistryReadinessRecord,
) -> str | None:
    """Return a fail-closed reason for missing or invalid checker evidence."""

    evidence = record._calibration_validity_evidence
    projection = record.calibration_validity
    if evidence is None or projection is None:
        return "calibration_validity_not_established"
    if not evidence.is_bound:
        return "calibration_report_binding_not_established"
    if evidence.calibration_id != record.calibration_id:
        return "calibration_identity_mismatch"
    if evidence.projection != projection:
        return "calibration_validity_projection_mismatch"
    if evidence.model_id is None or evidence.model_version is None:
        return "calibration_model_identity_not_established"
    if evidence.model_id != record.model_id or evidence.model_version != record.model_version:
        return "calibration_model_identity_mismatch"
    if projection.stationarity_regime_id != record.stationarity_regime_id:
        return "calibration_regime_identity_mismatch"
    if projection.observation_status != "observed" or projection.status == "not_established":
        if "calibration_expired" in projection.reasons:
            return "calibration_expired"
        return "calibration_validity_not_established"
    if not evidence.status.valid:
        if evidence.status.reasons:
            if "calibration_expired" in evidence.status.reasons:
                return "calibration_expired"
            return "calibration_" + "_".join(evidence.status.reasons)
        return "calibration_validity_failed"
    return None


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
