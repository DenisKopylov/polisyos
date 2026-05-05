"""Window-level orchestration for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

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
    build_model_registry_record,
)
from polisyos.ddm.readiness.readiness_mapper import MetricBudgetPolicy, map_readiness

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
    ) -> DDMWindowResult:
        """Evaluate one production window and emit all DDM-15.7 outputs."""

        effective_timestamp = timestamp or datetime.now(UTC)
        shift_risks = [adapt_shift_event(event) for event in shift_events or []]
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
            registry_record = build_model_registry_record(
                readiness_event=readiness,
                calibration_audit=calibration_audit,
                metric_budget=metric_budget,
                last_shift_event=None if not shift_risks else shift_risks[-1],
                last_degradation_event=enriched_degradation,
                active_incident_id=active_incident_id,
            )
        return DDMWindowResult(
            shift_risk_events=shift_risks,
            degradation_event=enriched_degradation,
            readiness_event=readiness,
            root_cause_bundle=root_cause,
            incident_payload=incident,
            registry_record=registry_record,
        )


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
