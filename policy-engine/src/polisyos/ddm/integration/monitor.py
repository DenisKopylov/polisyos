"""Window-level orchestration for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ddm.calibration.audit import _check_bound_calibration_validity
from polisyos.ddm.detectors.track_2_2_shift_adapter import adapt_shift_event
from polisyos.ddm.integration.events import (
    CalibrationAudit,
    DataQualitySignal,
    IncidentPayload,
    PerformanceDegradationEvent,
    ReadinessStateEvent,
    RootCauseBundle,
    ShiftDetectedEvent,
    ShiftRiskEvent,
)
from polisyos.ddm.integration.incident import (
    build_incident_payload,
    build_root_cause_bundle,
)
from polisyos.ddm.integration.model_registry import (
    ModelRegistryReadinessRecord,
    _registry_source_binding_reasons,
    build_model_registry_record,
)
from polisyos.ddm.readiness.readiness_mapper import MetricBudgetPolicy, map_readiness

if TYPE_CHECKING:
    from polisyos.ddm.calibration.calibrate import CalibrationReport

_PYDANTIC_RUNTIME_TYPES = (
    CalibrationAudit,
    DataQualitySignal,
    IncidentPayload,
    PerformanceDegradationEvent,
    ReadinessStateEvent,
    RootCauseBundle,
    ShiftDetectedEvent,
    ShiftRiskEvent,
)


class DDMWindowResult(BaseModel):
    """All runtime outputs produced for one monitoring window."""

    model_config = ConfigDict(extra="forbid")

    shift_risk_events: list[ShiftRiskEvent] = Field(default_factory=list)
    degradation_event: PerformanceDegradationEvent | None = None
    readiness_event: ReadinessStateEvent
    root_cause_bundle: RootCauseBundle
    incident_payload: IncidentPayload
    registry_record: ModelRegistryReadinessRecord | None = None


class DriftAndDegradationMonitor:
    """Compose shift, degradation, quality, readiness, and incident outputs."""

    def evaluate_window(
        self,
        *,
        model_id: str,
        model_version: str,
        shift_events: list[ShiftDetectedEvent | dict[str, object]] | None = None,
        degradation_event: PerformanceDegradationEvent | None = None,
        data_quality_signals: list[DataQualitySignal] | None = None,
        critical_slice_budget_used: float | None = None,
        upstream_versions: dict[str, str] | None = None,
        metric_budget: MetricBudgetPolicy | None = None,
        calibration_audit: CalibrationAudit | None = None,
        active_incident_id: str | None = None,
        timestamp: datetime | None = None,
        _calibration_report: CalibrationReport | None = None,
        _observed_invalidation_triggers: list[str] | None = None,
    ) -> DDMWindowResult:
        """Evaluate one production window and emit all DDM-15.7 outputs.

        ``_observed_invalidation_triggers=None`` records unavailable trigger
        observations; an explicit empty list records an observed empty set.
        Neither state is inferred from the public registry payload.
        """

        effective_timestamp = timestamp or datetime.now(UTC)
        shift_risks = [adapt_shift_event(event) for event in shift_events or []]
        _validate_window_input_identities(
            model_id=model_id,
            model_version=model_version,
            metric_budget=metric_budget,
            shift_events=shift_risks,
            degradation_event=degradation_event,
            data_quality_signals=data_quality_signals,
        )
        if calibration_audit is not None and metric_budget is not None:
            binding_reasons = _registry_source_binding_reasons(
                calibration_audit=calibration_audit,
                metric_budget=metric_budget,
                shift_events=shift_risks,
                degradation_event=degradation_event,
            )
            if binding_reasons:
                raise ValueError("monitor source binding mismatch: " + ", ".join(binding_reasons))
        readiness = map_readiness(
            model_id=model_id,
            model_version=model_version,
            degradation_event=degradation_event,
            shift_events=shift_risks,
            data_quality_signals=data_quality_signals,
            critical_slice_budget_used=critical_slice_budget_used,
            timestamp=effective_timestamp,
        )
        enriched_degradation = _attach_readiness(degradation_event, readiness)
        root_cause = build_root_cause_bundle(
            model_id=model_id,
            model_version=model_version,
            shift_events=shift_risks,
            degradation_events=[] if enriched_degradation is None else [enriched_degradation],
            data_quality_signals=data_quality_signals,
            upstream_versions=upstream_versions,
            timestamp=effective_timestamp,
        )
        incident = build_incident_payload(
            readiness_event=readiness,
            root_cause_bundle=root_cause,
        )
        registry_record = None
        if calibration_audit is not None and metric_budget is not None:
            validity_evidence = None
            if _calibration_report is not None:
                validity_evidence = _check_bound_calibration_validity(
                    calibration_id=calibration_audit.calibration_id,
                    report=_calibration_report,
                    audit=calibration_audit,
                    now=effective_timestamp,
                    observed_invalidation_triggers=_observed_invalidation_triggers,
                )
            registry_record = build_model_registry_record(
                readiness_event=readiness,
                calibration_audit=calibration_audit,
                metric_budget=metric_budget,
                last_shift_event=None if not shift_risks else shift_risks[-1],
                last_degradation_event=enriched_degradation,
                active_incident_id=active_incident_id,
                _calibration_validity_evidence=validity_evidence,
                _source_shift_events=shift_risks,
            )
        return DDMWindowResult(
            shift_risk_events=shift_risks,
            degradation_event=enriched_degradation,
            readiness_event=readiness,
            root_cause_bundle=root_cause,
            incident_payload=incident,
            registry_record=registry_record,
        )


def _validate_window_input_identities(
    *,
    model_id: str,
    model_version: str,
    metric_budget: MetricBudgetPolicy | None,
    shift_events: list[ShiftRiskEvent],
    degradation_event: PerformanceDegradationEvent | None,
    data_quality_signals: list[DataQualitySignal] | None,
) -> None:
    """Reject window evidence belonging to a different model subject."""

    mismatches: list[str] = []
    if metric_budget is not None and (
        metric_budget.model_id != model_id or metric_budget.model_version != model_version
    ):
        mismatches.append("metric_budget")
    for index, event in enumerate(shift_events):
        if event.model_id != model_id or event.model_version != model_version:
            mismatches.append(f"shift_events[{index}]")
    if degradation_event is not None and (
        degradation_event.model_id != model_id or degradation_event.model_version != model_version
    ):
        mismatches.append("degradation_event")
    for index, signal in enumerate(data_quality_signals or []):
        if signal.model_id != model_id or signal.model_version != model_version:
            mismatches.append(f"data_quality_signals[{index}]")
    if mismatches:
        raise ValueError("monitor input model identity mismatch: " + ", ".join(mismatches))


def _attach_readiness(
    degradation_event: PerformanceDegradationEvent | None,
    readiness_event: ReadinessStateEvent,
) -> PerformanceDegradationEvent | None:
    if degradation_event is None:
        return None
    recommended_action = (
        None if not readiness_event.required_actions else readiness_event.required_actions[0]
    )
    return degradation_event.model_copy(
        update={
            "readiness_state": readiness_event.readiness_state,
            "recommended_action": recommended_action,
        }
    )
