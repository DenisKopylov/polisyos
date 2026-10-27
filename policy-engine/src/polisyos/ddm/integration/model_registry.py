"""Model-registry gate integration for DDM-15.7 readiness states."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from polisyos.ddm.calibration.audit import (
    _CalibrationValidityEvidence,
    _check_bound_calibration_validity,
)
from polisyos.ddm.calibration.observations import (
    CalibrationObservationBinding,
    FiniteCalibrationObservationSource,
    _ResolvedCalibrationObservations,
)
from polisyos.ddm.integration.events import (
    CalibrationAudit,
    CalibrationValidityProjection,
    DataQualitySignal,
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


class RegistryApplicabilityBinding(BaseModel):
    """Immutable identities of the report and window evidence used for admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detector_id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    stationarity_regime_id: str = Field(min_length=1)
    report_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    shift_event_digests: tuple[str, ...]
    readiness_state: ReadinessState
    readiness_score: int = Field(ge=0, le=100)
    required_action: str | None
    last_shift_event_id: str | None = None
    last_degradation_event_id: str | None = None
    observation_binding: CalibrationObservationBinding | None = None
    degradation_event_digest: str | None = None
    metric_budget_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


_APPLICATION_EVIDENCE_TOKEN = object()


@dataclass(frozen=True)
class _RegistryApplicabilityEvidence:
    issuer_token: object
    binding: RegistryApplicabilityBinding
    reasons: tuple[str, ...]
    binding_digest: str

    @property
    def is_bound(self) -> bool:
        return self.issuer_token is _APPLICATION_EVIDENCE_TOKEN and not self.reasons


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
    # Optional keeps pre-binding registry payloads readable; a record built by
    # the current producer always carries this source-identity projection.
    identity_binding: RegistryIdentityBinding | None = None
    applicability_binding: RegistryApplicabilityBinding | None = None
    _calibration_validity_evidence: _CalibrationValidityEvidence | None = PrivateAttr(default=None)
    _applicability_evidence: _RegistryApplicabilityEvidence | None = PrivateAttr(default=None)


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
    shift_events: list[ShiftRiskEvent] | None = None,
    data_quality_signals: list[DataQualitySignal] | None = None,
    critical_slice_budget_used: float | None = None,
    last_degradation_event: PerformanceDegradationEvent | None = None,
    active_incident_id: str | None = None,
    _calibration_validity_evidence: _CalibrationValidityEvidence | None = None,
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
    consumed_shifts = (
        list(shift_events)
        if shift_events is not None
        else ([] if last_shift_event is None else [last_shift_event])
    )
    applicability_evidence = _check_registry_applicability(
        calibration_audit=calibration_audit,
        metric_budget=metric_budget,
        shift_events=consumed_shifts,
        data_quality_signals=data_quality_signals,
        critical_slice_budget_used=critical_slice_budget_used,
        readiness_event=readiness_event,
        effective_at=None
        if _calibration_validity_evidence is None
        else _calibration_validity_evidence.effective_at,
        degradation_event=last_degradation_event,
        last_shift_event=last_shift_event,
        observations=(
            None
            if _calibration_validity_evidence is None
            else _calibration_validity_evidence.observations
        ),
        report_digest=(
            None
            if _calibration_validity_evidence is None
            else _calibration_validity_evidence.report_digest
        ),
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
            and applicability_evidence.is_bound
        ),
        calibration_validity=(
            None
            if _calibration_validity_evidence is None
            else _calibration_validity_evidence.projection
        ),
        identity_binding=identity_binding,
        applicability_binding=applicability_evidence.binding,
    )
    record._calibration_validity_evidence = _calibration_validity_evidence
    record._applicability_evidence = applicability_evidence
    return record


def rebind_calibration_validity(
    record: ModelRegistryReadinessRecord,
    *,
    report: CalibrationReport,
    calibration_audit: CalibrationAudit,
    now: datetime,
    observed_invalidation_triggers: list[str] | None,
    metric_budget: MetricBudgetPolicy | None = None,
    shift_events: list[ShiftRiskEvent] | None = None,
    degradation_event: PerformanceDegradationEvent | None = None,
    observation_source: FiniteCalibrationObservationSource | None = None,
) -> ModelRegistryReadinessRecord:
    """Recheck a persisted projection against its exact source context.

    A public registry payload never carries checker authority.  A caller must
    provide the exact calibration report, projected audit, effective time, and
    trigger observation context before this function can attach fresh private
    checker evidence.  Legacy records without the projection remain
    ``not_established`` even when source context is later available.
    """

    rebound = record.model_copy(deep=True)
    rebound._calibration_validity_evidence = None
    rebound._applicability_evidence = None
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
        observation_source=observation_source,
    )
    if evidence.is_bound:
        rebound.calibration_validity = evidence.projection
    rebound._calibration_validity_evidence = evidence
    # Rebind consumes independently resolved source bytes. Caller lists,
    # public budget projections, and re-signed digests are not a source owner.
    if evidence.observations is not None:
        source_window = evidence.observations.window()
        effective_budget = source_window.metric_budget
        effective_shifts = list(source_window.shift_events)
        from polisyos.ddm.readiness.readiness_mapper import map_readiness

        source_readiness = map_readiness(
            model_id=record.model_id,
            model_version=record.model_version,
            degradation_event=source_window.degradation_event,
            shift_events=effective_shifts,
            data_quality_signals=list(source_window.data_quality_signals),
            critical_slice_budget_used=source_window.critical_slice_budget_used,
            timestamp=now,
        )
        applicability = _check_registry_applicability(
            calibration_audit=calibration_audit,
            metric_budget=effective_budget,
            shift_events=effective_shifts,
            data_quality_signals=list(source_window.data_quality_signals),
            critical_slice_budget_used=source_window.critical_slice_budget_used,
            readiness_event=source_readiness,
            effective_at=now,
            last_shift_event=None if not effective_shifts else effective_shifts[-1],
            degradation_event=source_window.degradation_event,
            report_digest=evidence.report_digest,
            expected=record.applicability_binding,
            observations=evidence.observations,
        )
        if metric_budget is not None and metric_budget != effective_budget:
            applicability = _with_applicability_reason(
                applicability, "caller_metric_budget_mismatch"
            )
        if shift_events is not None and shift_events != effective_shifts:
            applicability = _with_applicability_reason(applicability, "caller_shift_basis_mismatch")
        if degradation_event is not None and degradation_event != source_window.degradation_event:
            applicability = _with_applicability_reason(applicability, "caller_degradation_mismatch")
        rebound._applicability_evidence = applicability
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
    validity_reason = _calibration_validity_block_reason(record)
    if validity_reason is not None:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason=validity_reason,
            required_actions=["revalidate_calibration"],
        )
    applicability_reason = _applicability_block_reason(record)
    if applicability_reason is not None:
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason=applicability_reason,
            required_actions=["reconcile_registry_applicability"],
        )
    evidence = record._calibration_validity_evidence
    if (
        evidence is not None
        and evidence.observations is not None
        and evidence.observations.binding.authority_scope == "finite_replay_only"
    ):
        return RegistryGateDecision(
            model_id=record.model_id,
            model_version=record.model_version,
            promotion_allowed=False,
            reason="finite_replay_observation_not_production_authority",
            required_actions=["resolve_production_observation_owner"],
        )
    return _evaluate_readiness_gate(record, owner_signoff=owner_signoff)


def _evaluate_readiness_gate(
    record: ModelRegistryReadinessRecord, *, owner_signoff: bool
) -> RegistryGateDecision:
    """Apply the existing precedence only after observation/applicability gates."""

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
        and evidence.observations is not None
        and evidence.observations.binding.authority_scope != "finite_replay_only"
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
    if (
        evidence.projection != projection
        or evidence.projection_digest
        != hashlib.sha256(projection.model_dump_json().encode()).hexdigest()
    ):
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
    if evidence.observations is None:
        return "calibration_observation_source_not_established"
    if not evidence.observations.is_current():
        return "calibration_observation_source_changed_or_unavailable"
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


def _digest_model(value: BaseModel) -> str:
    payload = json.dumps(
        value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _check_registry_applicability(
    *,
    calibration_audit: CalibrationAudit,
    metric_budget: MetricBudgetPolicy,
    shift_events: list[ShiftRiskEvent],
    data_quality_signals: list[DataQualitySignal] | None,
    critical_slice_budget_used: float | None,
    readiness_event: ReadinessStateEvent,
    effective_at: datetime | None,
    degradation_event: PerformanceDegradationEvent | None,
    report_digest: str | None,
    last_shift_event: ShiftRiskEvent | None,
    observations: _ResolvedCalibrationObservations | None,
    expected: RegistryApplicabilityBinding | None = None,
) -> _RegistryApplicabilityEvidence:
    """Reconcile every consumed event and budget with the selected calibration."""

    binding = RegistryApplicabilityBinding(
        detector_id=calibration_audit.detector_id,
        calibration_id=calibration_audit.calibration_id,
        stationarity_regime_id=calibration_audit.stationarity_regime_id,
        report_digest=report_digest or "0" * 64,
        shift_event_digests=tuple(_digest_model(event) for event in shift_events),
        readiness_state=readiness_event.readiness_state,
        readiness_score=readiness_event.readiness_score,
        required_action=(
            None if not readiness_event.required_actions else readiness_event.required_actions[0]
        ),
        last_shift_event_id=None if last_shift_event is None else last_shift_event.shift_event_id,
        last_degradation_event_id=(
            None if degradation_event is None else degradation_event.event_id
        ),
        observation_binding=None if observations is None else observations.binding,
        degradation_event_digest=(
            None if degradation_event is None else _degradation_digest(degradation_event)
        ),
        metric_budget_digest=_digest_model(metric_budget),
    )
    reasons: list[str] = []
    if report_digest is None:
        reasons.append("calibration_report_digest_not_established")
    expected_last = None if not shift_events else shift_events[-1]
    if last_shift_event != expected_last:
        reasons.append("last_shift_event_not_in_consumed_basis")
    if observations is None:
        reasons.append("window_source_basis_not_established")
    else:
        source = observations.window()
        if effective_at is None:
            reasons.append("readiness_effective_context_not_established")
        else:
            from polisyos.ddm.readiness.readiness_mapper import map_readiness

            recomputed_readiness = map_readiness(
                model_id=source.model_id,
                model_version=source.model_version,
                degradation_event=source.degradation_event,
                shift_events=list(source.shift_events),
                data_quality_signals=list(source.data_quality_signals),
                critical_slice_budget_used=source.critical_slice_budget_used,
                timestamp=effective_at,
            )
            # Compare the complete typed producer projection. Only an explicit
            # upstream permission veto may differ from mapper eligibility.
            expected_readiness = recomputed_readiness.model_dump(
                mode="json", exclude={"promotion_allowed"}
            )
            actual_readiness = readiness_event.model_dump(
                mode="json", exclude={"promotion_allowed"}
            )
            if actual_readiness != expected_readiness:
                reasons.append("window_source_readiness_projection_mismatch")
        if list(source.shift_events) != shift_events:
            reasons.append("window_source_shift_basis_mismatch")
        if list(source.data_quality_signals) != list(data_quality_signals or []):
            reasons.append("window_source_data_quality_basis_mismatch")
        if source.critical_slice_budget_used != critical_slice_budget_used:
            reasons.append("window_source_critical_budget_mismatch")
        if source.metric_budget != metric_budget:
            reasons.append("window_source_metric_budget_mismatch")
        if (source.degradation_event is None) != (degradation_event is None) or (
            source.degradation_event is not None
            and degradation_event is not None
            and _degradation_digest(source.degradation_event)
            != _degradation_digest(degradation_event)
        ):
            reasons.append("window_source_degradation_mismatch")
    seen: dict[str, str] = {}
    for event, digest in zip(shift_events, binding.shift_event_digests, strict=True):
        previous = seen.setdefault(event.shift_event_id, digest)
        if previous != digest:
            reasons.append("conflicting_duplicate_shift_event")
        if event.detector_id != calibration_audit.detector_id:
            reasons.append("shift_detector_identity_mismatch")
        if event.calibration_id != calibration_audit.calibration_id:
            reasons.append("shift_calibration_identity_mismatch")
        if event.stationarity_regime_id != calibration_audit.stationarity_regime_id:
            reasons.append("shift_stationarity_regime_mismatch")
    if degradation_event is not None:
        policy = _metric_budget_payload(metric_budget)
        for field in (
            "metric",
            "metric_direction",
            "reference_value",
            "minimum_acceptable_value",
            "maximum_acceptable_value",
        ):
            event_value = getattr(degradation_event, field)
            if policy.get(field) != event_value:
                reasons.append(f"degradation_{field}_mismatch")
        if degradation_event.calibration_id not in (None, calibration_audit.calibration_id):
            reasons.append("degradation_calibration_identity_mismatch")
        from polisyos.ddm.readiness.readiness_mapper import metric_budget_used

        actual_used = metric_budget_used(
            metric_direction=degradation_event.metric_direction,
            reference_value=degradation_event.reference_value,
            current_estimate=degradation_event.current_estimate,
            confidence_interval_95=degradation_event.confidence_interval_95,
            minimum_acceptable_value=degradation_event.minimum_acceptable_value,
            maximum_acceptable_value=degradation_event.maximum_acceptable_value,
        )
        if abs(actual_used - degradation_event.budget_used) > 1e-12:
            reasons.append("degradation_budget_consumption_mismatch")
    if expected is not None and expected != binding:
        reasons.append("registry_applicability_projection_mismatch")
    return _RegistryApplicabilityEvidence(
        issuer_token=_APPLICATION_EVIDENCE_TOKEN,
        binding=binding,
        binding_digest=_digest_model(binding),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _applicability_block_reason(record: ModelRegistryReadinessRecord) -> str | None:
    evidence = record._applicability_evidence
    if record.applicability_binding is None or evidence is None:
        return "registry_applicability_not_established"
    if evidence.binding != record.applicability_binding or evidence.binding_digest != _digest_model(
        record.applicability_binding
    ):
        return "registry_applicability_projection_mismatch"
    if (
        record.readiness_state != record.applicability_binding.readiness_state
        or record.readiness_score != record.applicability_binding.readiness_score
        or record.required_action != record.applicability_binding.required_action
    ):
        return "registry_readiness_projection_mismatch"
    if record.last_shift_event != record.applicability_binding.last_shift_event_id:
        return "registry_last_shift_projection_mismatch"
    if record.last_degradation_event != record.applicability_binding.last_degradation_event_id:
        return "registry_last_degradation_projection_mismatch"
    if evidence.reasons:
        return evidence.reasons[0]
    if not evidence.is_bound:
        return "registry_applicability_not_established"
    return None


def _with_applicability_reason(
    evidence: _RegistryApplicabilityEvidence, reason: str
) -> _RegistryApplicabilityEvidence:
    return _RegistryApplicabilityEvidence(
        issuer_token=evidence.issuer_token,
        binding=evidence.binding,
        binding_digest=evidence.binding_digest,
        reasons=(*evidence.reasons, reason),
    )


def _degradation_digest(event: PerformanceDegradationEvent) -> str:
    # Readiness enrichment is a derived consumer projection, not a new source fact.
    payload = event.model_dump(mode="json", exclude={"readiness_state", "recommended_action"})
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
