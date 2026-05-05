"""Incident and root-cause helpers for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from polisyos.ddm.integration.events import (
    DataQualitySignal,
    IncidentPayload,
    PerformanceDegradationEvent,
    ReadinessState,
    ReadinessStateEvent,
    RootCauseBundle,
    ShiftRiskEvent,
)


def build_root_cause_bundle(
    *,
    model_id: str,
    model_version: str,
    shift_events: list[ShiftRiskEvent] | None = None,
    degradation_events: list[PerformanceDegradationEvent] | None = None,
    data_quality_signals: list[DataQualitySignal] | None = None,
    upstream_versions: dict[str, str] | None = None,
    timestamp: datetime | None = None,
) -> RootCauseBundle:
    """Collect localization and contract context into one incident artifact."""

    effective_timestamp = timestamp or datetime.now(UTC)
    shifts = list(shift_events or [])
    degradations = list(degradation_events or [])
    quality = list(data_quality_signals or [])
    feature_by_name = {item.feature: item for event in shifts for item in event.affected_features}
    affected_slices = {item.slice for event in shifts for item in event.affected_slices}
    calibration_ids = {event.calibration_id for event in shifts} | {
        event.calibration_id for event in degradations if event.calibration_id is not None
    }
    stationarity_regime_ids = {event.stationarity_regime_id for event in shifts}
    violations = [violation for signal in quality for violation in signal.violations]

    return RootCauseBundle(
        event_id=f"root-cause-{model_id}-{model_version}-{effective_timestamp.isoformat()}",
        timestamp=effective_timestamp,
        model_id=model_id,
        model_version=model_version,
        shift_event_ids=[event.shift_event_id for event in shifts],
        degradation_event_ids=[event.event_id for event in degradations],
        affected_features=sorted(feature_by_name.values(), key=lambda item: item.feature),
        affected_slices=sorted(affected_slices),
        upstream_versions=dict(upstream_versions or {}),
        data_quality_violations=violations,
        stationarity_regime_ids=sorted(stationarity_regime_ids),
        calibration_ids=sorted(calibration_ids),
    )


def build_incident_payload(
    *,
    readiness_event: ReadinessStateEvent,
    root_cause_bundle: RootCauseBundle | None = None,
) -> IncidentPayload:
    """Map readiness state into automation hooks."""

    severity = _severity_for_state(readiness_event.readiness_state)
    attach_event_ids = [] if root_cause_bundle is None else [root_cause_bundle.event_id]
    return IncidentPayload(
        event_id=f"incident-{readiness_event.event_id}",
        timestamp=readiness_event.timestamp,
        model_id=readiness_event.model_id,
        model_version=readiness_event.model_version,
        readiness_event_id=readiness_event.event_id,
        readiness_state=readiness_event.readiness_state,
        severity=severity,
        root_cause_bundle_id=None if root_cause_bundle is None else root_cause_bundle.event_id,
        required_actions=list(readiness_event.required_actions),
        attach_event_ids=attach_event_ids,
        create_ticket=readiness_event.readiness_state
        in {
            ReadinessState.R2,
            ReadinessState.R1,
            ReadinessState.R0,
        },
        notify_owner=readiness_event.readiness_state
        in {
            ReadinessState.R3,
            ReadinessState.R2,
            ReadinessState.R1,
            ReadinessState.R0,
        },
        page_owner=readiness_event.readiness_state is ReadinessState.R0,
        trigger_shadow_retrain=readiness_event.readiness_state
        in {
            ReadinessState.R2,
            ReadinessState.R1,
        },
        freeze_rollout=readiness_event.readiness_state is ReadinessState.R1,
        rollback_or_fallback=readiness_event.readiness_state is ReadinessState.R0,
    )


def _severity_for_state(
    state: ReadinessState,
) -> Literal["none", "watch", "investigate", "retrain", "rollback"]:
    if state is ReadinessState.R4:
        return "none"
    if state is ReadinessState.R3:
        return "watch"
    if state is ReadinessState.R2:
        return "investigate"
    if state is ReadinessState.R1:
        return "retrain"
    return "rollback"
