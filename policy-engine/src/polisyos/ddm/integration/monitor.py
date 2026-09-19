"""Window-level orchestration for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ddm.contracts.events import (
    ApplicabilityStatus,
    CalibrationAudit,
    DataQualitySignal,
    DDMApplicabilityProjection,
    DEFAULT_READINESS_POLICY_ID,
    DEFAULT_READINESS_POLICY_VERSION,
    IncidentPayload,
    PerformanceDegradationEvent,
    ReadinessStateEvent,
    RootCauseBundle,
    ShiftDetectedEvent,
    ShiftRiskEvent,
)
from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy
from polisyos.ddm.detectors.track_2_2_shift_adapter import adapt_shift_event
from polisyos.ddm.integration.incident import (
    build_incident_payload,
    build_root_cause_bundle,
)
from polisyos.ddm.integration.model_registry import (
    ModelRegistryReadinessRecord,
    bind_applicability_projection,
    build_model_registry_record,
)
from polisyos.ddm.readiness.readiness_mapper import map_readiness_with_applicability

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
    applicability: DDMApplicabilityProjection
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
        calibration_report: CalibrationReport | None = None,
        observed_invalidation_triggers: list[str] | None = None,
        observation_window_available: bool | None = None,
        policy_id: str | None = None,
        policy_version: str | None = None,
        active_incident_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> DDMWindowResult:
        """Evaluate one production window and emit all DDM-15.7 outputs."""

        effective_timestamp = timestamp or datetime.now(UTC)
        shift_risks = [adapt_shift_event(event) for event in shift_events or []]
        report_identity_reasons: list[str] = []
        if calibration_audit is not None and calibration_report is not None:
            from polisyos.ddm.calibration.audit import check_calibration_validity

            status = check_calibration_validity(
                calibration_id=calibration_audit.calibration_id,
                report=calibration_report,
                now=effective_timestamp,
                observed_invalidation_triggers=observed_invalidation_triggers,
            )
            if calibration_audit.detector_id != calibration_report.detector_id:
                report_identity_reasons.append("calibration_report_detector_id")
            if (
                calibration_audit.stationarity_regime_id
                != calibration_report.stationarity_regime_id
            ):
                report_identity_reasons.append("calibration_report_stationarity_regime_id")
            calibration_audit = calibration_audit.model_copy(
                update={
                    "valid_until": calibration_report.expiration.valid_until,
                    "invalidation_triggers": list(
                        calibration_report.expiration.invalidation_triggers
                    ),
                    "observed_invalidation_triggers": list(
                        status.observed_invalidation_triggers
                    ),
                    "validity": (
                        ApplicabilityStatus.VALID
                        if status.valid
                        else ApplicabilityStatus.INVALID
                    ),
                    "validity_reasons": list(status.reasons),
                    "validity_checked_at": status.evaluated_at,
                }
            )
        mapped = map_readiness_with_applicability(
            model_id=model_id,
            model_version=model_version,
            degradation_event=degradation_event,
            shift_events=shift_risks,
            data_quality_signals=data_quality_signals,
            critical_slice_budget_used=critical_slice_budget_used,
            policy_id=policy_id if policy_id is not None else DEFAULT_READINESS_POLICY_ID,
            policy_version=(
                policy_version if policy_version is not None else DEFAULT_READINESS_POLICY_VERSION
            ),
            observation_window_available=observation_window_available,
            timestamp=effective_timestamp,
        )
        readiness = mapped.readiness_event
        applicability = mapped.applicability
        if report_identity_reasons:
            applicability = applicability.model_copy(
                update={
                    "identity_reasons": sorted(
                        set(applicability.identity_reasons).union(report_identity_reasons)
                    )
                }
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
            applicability = bind_applicability_projection(
                projection=applicability,
                calibration_audit=calibration_audit,
                metric_budget=metric_budget,
                last_shift_event=None if not shift_risks else shift_risks[-1],
            )
            registry_record = build_model_registry_record(
                readiness_event=readiness,
                calibration_audit=calibration_audit,
                metric_budget=metric_budget,
                applicability=applicability,
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
            applicability=applicability,
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
