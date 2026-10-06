"""Model-registry gate integration for DDM-15.7 readiness states."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PrivateAttr

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
    from datetime import datetime

    from polisyos.ddm.calibration.calibrate import CalibrationReport
    from polisyos.ddm.readiness.readiness_mapper import MetricBudgetPolicy


class RegistryIdentityBinding(BaseModel):
    """Durable source identities reconciled into one registry record."""

    model_config = ConfigDict(extra="forbid")

    calibration_model_id: str | None = Field(default=None, min_length=1)
    calibration_model_version: str | None = Field(default=None, min_length=1)
    metric_budget_model_id: str | None = Field(default=None, min_length=1)
    metric_budget_model_version: str | None = Field(default=None, min_length=1)
    last_shift_event_model_id: str | None = Field(default=None, min_length=1)
    last_shift_event_model_version: str | None = Field(default=None, min_length=1)
    last_degradation_event_model_id: str | None = Field(default=None, min_length=1)
    last_degradation_event_model_version: str | None = Field(default=None, min_length=1)


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
    readiness_event_id: str | None = Field(default=None, min_length=1)
    readiness_effective_at: AwareDatetime | None = None
    readiness_expires_at: AwareDatetime | None = None
    source_binding_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    last_shift_event: str | None = None
    last_degradation_event: str | None = None
    required_action: str | None = None
    active_incident_id: str | None = None
    promotion_allowed: bool
    calibration_validity: CalibrationValidityProjection | None = None
    # Optional keeps pre-binding registry payloads readable; a record built by
    # the current producer always carries this source-identity projection.
    identity_binding: RegistryIdentityBinding | None = None
    _calibration_validity_evidence: _CalibrationValidityEvidence | None = PrivateAttr(default=None)
    _registry_source_evidence: _RegistrySourceEvidence | None = PrivateAttr(default=None)


_REGISTRY_SOURCE_TOKEN = object()


@dataclass(frozen=True)
class _RegistrySourceEvidence:
    """Private immutable reconciliation result, never supplied by a JSON flag."""

    issuer_token: object
    record_digest: str
    source_promotion_allowed: bool
    binding_reasons: tuple[str, ...]


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
    _source_shift_events: list[ShiftRiskEvent] | None = None,
) -> ModelRegistryReadinessRecord:
    """Build the durable registry state described by the Phase 5 plan."""

    identity_binding = _build_registry_identity_binding(
        calibration_audit=calibration_audit,
        metric_budget=metric_budget,
        last_shift_event=last_shift_event,
        last_degradation_event=last_degradation_event,
    )
    identity_binding_reasons = _registry_identity_binding_reasons(
        model_id=readiness_event.model_id,
        model_version=readiness_event.model_version,
        calibration_audit=calibration_audit,
        metric_budget=metric_budget,
        last_shift_event=last_shift_event,
        last_degradation_event=last_degradation_event,
    )
    source_shifts = (
        ([] if last_shift_event is None else [last_shift_event])
        if _source_shift_events is None
        else _source_shift_events
    )
    source_binding_reasons = _registry_source_binding_reasons(
        calibration_audit=calibration_audit,
        metric_budget=metric_budget,
        shift_events=source_shifts,
        degradation_event=last_degradation_event,
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
        readiness_event_id=readiness_event.event_id,
        readiness_effective_at=readiness_event.timestamp,
        readiness_expires_at=readiness_event.expires_at,
        source_binding_digest=_source_digest(
            readiness_event=readiness_event,
            calibration_audit=calibration_audit,
            metric_budget=metric_budget,
            shift_events=source_shifts,
            degradation_event=last_degradation_event,
        ),
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
            and not source_binding_reasons
        ),
        calibration_validity=(
            None
            if _calibration_validity_evidence is None
            else _calibration_validity_evidence.projection.model_copy(deep=True)
        ),
        identity_binding=identity_binding,
    )
    record._calibration_validity_evidence = _calibration_validity_evidence
    record._registry_source_evidence = _RegistrySourceEvidence(
        issuer_token=_REGISTRY_SOURCE_TOKEN,
        record_digest=_registry_projection_digest(record),
        source_promotion_allowed=readiness_event.promotion_allowed,
        binding_reasons=tuple(identity_binding_reasons) + source_binding_reasons,
    )
    return record


def rebind_calibration_validity(
    record: ModelRegistryReadinessRecord,
    *,
    report: CalibrationReport,
    calibration_audit: CalibrationAudit,
    now: datetime,
    observed_invalidation_triggers: list[str] | None,
    metric_budget: MetricBudgetPolicy | None = None,
    readiness_event: ReadinessStateEvent | None = None,
    shift_events: list[ShiftRiskEvent] | None = None,
    last_degradation_event: PerformanceDegradationEvent | None = None,
) -> ModelRegistryReadinessRecord:
    """Recheck a persisted projection against its exact source context.

    A public registry payload never carries checker authority.  A caller must
    provide the exact calibration report, projected audit, effective time, and
    trigger observation context to refresh calibration validity. Registry
    eligibility additionally requires the original readiness event, metric
    policy, ordered shift events and degradation event. Legacy records without
    their source digest or temporal projection remain ``not_established``.
    """

    rebound = record.model_copy(deep=True)
    # Reopening must reconcile the same source inputs, not promote a payload's
    # digest or source-shaped fields into fresh private checker authority.
    rebound._registry_source_evidence = None
    rebound.identity_binding = _restore_calibration_identity_binding(
        record.identity_binding,
        calibration_audit=calibration_audit,
    )
    if _durable_identity_binding_block_reason(rebound) is not None:
        rebound.promotion_allowed = False
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
        rebound.calibration_validity = evidence.projection.model_copy(deep=True)
    rebound._calibration_validity_evidence = evidence
    if metric_budget is not None and readiness_event is not None:
        shifts = [] if shift_events is None else shift_events
        expected = build_model_registry_record(
            readiness_event=readiness_event,
            calibration_audit=calibration_audit,
            metric_budget=metric_budget,
            last_shift_event=None if not shifts else shifts[-1],
            last_degradation_event=last_degradation_event,
            active_incident_id=record.active_incident_id,
            _calibration_validity_evidence=evidence,
            _source_shift_events=shifts,
        )
        # Reconciliation may retain a persisted restriction, never restore a
        # dropped permission from the original source's optimistic baseline.
        expected.promotion_allowed = record.promotion_allowed and expected.promotion_allowed
        source_evidence = expected._registry_source_evidence
        if source_evidence is not None:
            expected._registry_source_evidence = _RegistrySourceEvidence(
                issuer_token=source_evidence.issuer_token,
                record_digest=_registry_projection_digest(expected),
                source_promotion_allowed=source_evidence.source_promotion_allowed,
                binding_reasons=source_evidence.binding_reasons,
            )
        if _registry_projection_digest(expected) == _registry_projection_digest(rebound):
            rebound._registry_source_evidence = expected._registry_source_evidence
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
    identity_binding_reason = _durable_identity_binding_block_reason(record)
    if identity_binding_reason is not None:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason=identity_binding_reason,
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
        source_reason = _registry_source_block_reason(record)
        if source_reason is not None:
            return _source_blocked_decision(record, source_reason)
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
        source_reason = _registry_source_block_reason(record)
        if source_reason is not None:
            return _source_blocked_decision(record, source_reason)
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
    elif calibration_audit.model_id != model_id or calibration_audit.model_version != model_version:
        reasons.append("calibration_model_identity_mismatch")

    if metric_budget.model_id != model_id or metric_budget.model_version != model_version:
        reasons.append("metric_budget_model_identity_mismatch")

    if last_shift_event is not None and (
        last_shift_event.model_id != model_id or last_shift_event.model_version != model_version
    ):
        reasons.append("shift_event_model_identity_mismatch")

    if last_degradation_event is not None and (
        last_degradation_event.model_id != model_id
        or last_degradation_event.model_version != model_version
    ):
        reasons.append("degradation_event_model_identity_mismatch")

    return tuple(dict.fromkeys(reasons))


def _build_registry_identity_binding(
    *,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    last_shift_event: ShiftRiskEvent | None,
    last_degradation_event: PerformanceDegradationEvent | None,
) -> RegistryIdentityBinding:
    """Project source model identities into the durable registry record."""

    return RegistryIdentityBinding(
        calibration_model_id=calibration_audit.model_id,
        calibration_model_version=calibration_audit.model_version,
        metric_budget_model_id=metric_budget.model_id,
        metric_budget_model_version=metric_budget.model_version,
        last_shift_event_model_id=(None if last_shift_event is None else last_shift_event.model_id),
        last_shift_event_model_version=(
            None if last_shift_event is None else last_shift_event.model_version
        ),
        last_degradation_event_model_id=(
            None if last_degradation_event is None else last_degradation_event.model_id
        ),
        last_degradation_event_model_version=(
            None if last_degradation_event is None else last_degradation_event.model_version
        ),
    )


def _restore_calibration_identity_binding(
    binding: RegistryIdentityBinding | None,
    *,
    calibration_audit: CalibrationAudit,
) -> RegistryIdentityBinding:
    """Restore only an absent legacy calibration identity during rebind."""

    if binding is None:
        return RegistryIdentityBinding(
            calibration_model_id=calibration_audit.model_id,
            calibration_model_version=calibration_audit.model_version,
        )
    if binding.calibration_model_id is None and binding.calibration_model_version is None:
        return binding.model_copy(
            update={
                "calibration_model_id": calibration_audit.model_id,
                "calibration_model_version": calibration_audit.model_version,
            }
        )
    return binding


def _durable_identity_binding_block_reason(
    record: ModelRegistryReadinessRecord,
) -> str | None:
    """Return a fail-closed reason from the persisted source identities."""

    binding = record.identity_binding
    if binding is None:
        return "model_identity_binding_not_established"
    if binding.calibration_model_id is None or binding.calibration_model_version is None:
        return "calibration_model_identity_not_established"
    if (
        binding.calibration_model_id != record.model_id
        or binding.calibration_model_version != record.model_version
    ):
        return "calibration_model_identity_mismatch"
    if binding.metric_budget_model_id is None or binding.metric_budget_model_version is None:
        return "metric_budget_model_identity_not_established"
    if (
        binding.metric_budget_model_id != record.model_id
        or binding.metric_budget_model_version != record.model_version
    ):
        return "metric_budget_model_identity_mismatch"
    if record.last_shift_event is not None:
        if (
            binding.last_shift_event_model_id is None
            or binding.last_shift_event_model_version is None
        ):
            return "shift_event_model_identity_not_established"
        if (
            binding.last_shift_event_model_id != record.model_id
            or binding.last_shift_event_model_version != record.model_version
        ):
            return "shift_event_model_identity_mismatch"
    if record.last_degradation_event is not None:
        if (
            binding.last_degradation_event_model_id is None
            or binding.last_degradation_event_model_version is None
        ):
            return "degradation_event_model_identity_not_established"
        if (
            binding.last_degradation_event_model_id != record.model_id
            or binding.last_degradation_event_model_version != record.model_version
        ):
            return "degradation_event_model_identity_mismatch"
    return None


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


def _shared_source_mismatches(left: BaseModel, right: BaseModel) -> tuple[str, ...]:
    """Reconcile every common declared field rather than sampled identities."""

    left_payload = left.model_dump(mode="json", by_alias=True)
    right_payload = right.model_dump(mode="json", by_alias=True)
    return tuple(
        field
        for field in sorted(left_payload.keys() & right_payload.keys())
        if left_payload[field] != right_payload[field]
    )


def _registry_source_binding_reasons(
    *,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    shift_events: list[ShiftRiskEvent],
    degradation_event: PerformanceDegradationEvent | None,
) -> tuple[str, ...]:
    """Reconcile complete calibration and metric contracts at one boundary."""

    reasons = [
        f"shift_events[{index}].calibration_binding_{field}_mismatch"
        for index, event in enumerate(shift_events)
        for field in _shared_source_mismatches(calibration_audit, event)
    ]
    if degradation_event is not None:
        reasons.extend(
            f"degradation_event.metric_binding_{field}_mismatch"
            for field in _shared_source_mismatches(metric_budget, degradation_event)
        )
        budget_reason = _degradation_budget_binding_reason(metric_budget, degradation_event)
        if budget_reason is not None:
            reasons.append(budget_reason)
        # Missing performance calibration is distinct from a false reference.
        if (
            degradation_event.calibration_id is not None
            and degradation_event.calibration_id != calibration_audit.calibration_id
        ):
            reasons.append("degradation_event.calibration_binding_calibration_id_mismatch")
    return tuple(reasons)


def _degradation_budget_binding_reason(
    metric_budget: MetricBudgetPolicy, event: PerformanceDegradationEvent
) -> str | None:
    """Recompute the quantity consumed by readiness using its canonical owner."""

    from polisyos.ddm.readiness.readiness_mapper import metric_budget_used

    source_values = (
        metric_budget.reference_value,
        metric_budget.minimum_acceptable_value,
        metric_budget.maximum_acceptable_value,
        event.current_estimate,
        *event.confidence_interval_95,
    )
    if any(value is not None and not math.isfinite(value) for value in source_values):
        return "degradation_event.metric_binding_budget_used_not_established"
    expected = metric_budget_used(
        metric_direction=metric_budget.metric_direction,
        reference_value=metric_budget.reference_value,
        current_estimate=event.current_estimate,
        confidence_interval_95=event.confidence_interval_95,
        minimum_acceptable_value=metric_budget.minimum_acceptable_value,
        maximum_acceptable_value=metric_budget.maximum_acceptable_value,
    )
    if event.budget_used != expected:
        return "degradation_event.metric_binding_budget_used_mismatch"
    return None


def _payload_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _source_digest(
    *,
    readiness_event: ReadinessStateEvent,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    shift_events: list[ShiftRiskEvent],
    degradation_event: PerformanceDegradationEvent | None,
) -> str:
    return _payload_digest(
        {
            "profile": "ddm.registry.source_binding.v1",
            "readiness": readiness_event.model_dump(mode="json", by_alias=True),
            "calibration": calibration_audit.model_dump(mode="json", by_alias=True),
            "metric_budget": metric_budget.model_dump(mode="json", by_alias=True),
            "shift_events": [
                event.model_dump(mode="json", by_alias=True) for event in shift_events
            ],
            "degradation": (
                None
                if degradation_event is None
                else degradation_event.model_dump(mode="json", by_alias=True)
            ),
        }
    )


def _registry_projection_digest(record: ModelRegistryReadinessRecord) -> str:
    # Calibration time/trigger/status is refreshed by its canonical checker;
    # baseline permission may only be reduced before binding, and R2 retains
    # its explicit signoff exception. Every other field is source-reconciled.
    return _payload_digest(record.model_dump(mode="json", exclude={"calibration_validity"}))


def _registry_source_block_reason(record: ModelRegistryReadinessRecord) -> str | None:
    evidence = record._registry_source_evidence
    if (
        evidence is None
        or evidence.issuer_token is not _REGISTRY_SOURCE_TOKEN
        or evidence.binding_reasons
        or evidence.record_digest != _registry_projection_digest(record)
        or (
            record.readiness_state in {ReadinessState.R4, ReadinessState.R3}
            and not evidence.source_promotion_allowed
        )
    ):
        return "registry_source_binding_not_established"
    validity = record._calibration_validity_evidence
    if record.readiness_effective_at is None or record.readiness_expires_at is None:
        return "readiness_time_not_established"
    if validity is None:
        return "calibration_validity_not_established"
    if validity.effective_at < record.readiness_effective_at:
        return "readiness_not_yet_effective"
    if validity.effective_at > record.readiness_expires_at:
        return "readiness_expired"
    return None


def _source_blocked_decision(
    record: ModelRegistryReadinessRecord, reason: str
) -> RegistryGateDecision:
    return RegistryGateDecision(
        model_id=record.model_id,
        model_version=record.model_version,
        promotion_allowed=False,
        reason=reason,
        required_actions=["reconcile_registry_bindings"],
    )
