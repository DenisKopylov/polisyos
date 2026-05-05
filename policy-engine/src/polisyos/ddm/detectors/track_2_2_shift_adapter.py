"""Adapter from ML Track 2.2 shift events into DDM-15.7 risk events."""

from __future__ import annotations

from typing import Literal

from polisyos.ddm.integration.events import ShiftDetectedEvent, ShiftRiskEvent


def adapt_shift_event(event: ShiftDetectedEvent | dict[str, object]) -> ShiftRiskEvent:
    """Normalize a calibrated Track 2.2 shift event into 0-1 risk units.

    The input schema already requires a stationarity regime, calibration id,
    empirical false-positive evidence, and at least one calibrated evidence
    channel. This adapter therefore fails closed on uncalibrated events instead
    of silently accepting raw drift scores.
    """

    parsed = event if isinstance(event, ShiftDetectedEvent) else ShiftDetectedEvent(**event)
    evidence_kind = _evidence_kind(parsed)
    return ShiftRiskEvent(
        event_id=f"shift-risk-{parsed.event_id}",
        shift_event_id=parsed.event_id,
        timestamp=parsed.timestamp,
        model_id=parsed.model_id,
        model_version=parsed.model_version,
        detector_id=parsed.detector_id,
        signal=parsed.signal,
        stationarity_regime_id=parsed.stationarity_regime_id,
        calibration_id=parsed.calibration_id,
        evidence_kind=evidence_kind,
        risk_score=parsed.shift_severity,
        risk_level=_risk_level(parsed.shift_severity),
        diagnostic_only=parsed.diagnostic_only,
        affected_features=list(parsed.affected_features),
        affected_slices=list(parsed.affected_slices),
    )


def validate_track_2_2_event(event: ShiftDetectedEvent | dict[str, object]) -> tuple[str, ...]:
    """Return human-readable validation issues for a Track 2.2 event."""

    try:
        adapt_shift_event(event)
    except ValueError as exc:
        return (str(exc),)
    return ()


def _evidence_kind(event: ShiftDetectedEvent) -> Literal["p_value", "e_value", "ert"]:
    if event.p_value is not None:
        return "p_value"
    if event.e_value is not None:
        return "e_value"
    return "ert"


def _risk_level(score: float) -> Literal["low", "watch", "investigate"]:
    if score >= 0.70:
        return "investigate"
    if score >= 0.25:
        return "watch"
    return "low"
