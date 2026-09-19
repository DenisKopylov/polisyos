"""Calibration audit and expiration checks for DDM-15.7."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from polisyos.ddm.contracts.events import ApplicabilityStatus, CalibrationAudit

if TYPE_CHECKING:
    from polisyos.ddm.calibration.calibrate import CalibrationReport


class CalibrationInvalidationStatus(BaseModel):
    """Whether a calibration artifact is currently valid."""

    model_config = ConfigDict(extra="forbid")

    calibration_id: str = Field(min_length=1)
    expired: bool
    invalidated: bool
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    observed_invalidation_triggers: list[str] = Field(default_factory=list)
    evaluated_at: AwareDatetime | None = None


_LAST_VALIDITY: ContextVar[
    tuple[int, str, CalibrationInvalidationStatus] | None
] = ContextVar("ddm_last_calibration_validity", default=None)


def build_calibration_audit(
    *,
    calibration_id: str,
    report: CalibrationReport,
) -> CalibrationAudit:
    """Project a calibration report into the runtime audit output."""

    cached = _LAST_VALIDITY.get()
    validity = None
    if cached is not None and cached[0] == id(report) and cached[1] == calibration_id:
        validity = cached[2]

    return CalibrationAudit(
        calibration_id=calibration_id,
        detector_id=report.detector_id,
        stationarity_regime_id=report.stationarity_regime_id,
        horizon=report.fp_target.horizon,
        alpha=report.fp_target.alpha,
        ert=report.fp_target.ert,
        empirical_fp_rate=report.empirical_stationary_holdout.empirical_fp_rate,
        empirical_fp_upper_95=report.empirical_stationary_holdout.confidence_interval_95[1],
        pass_=report.empirical_stationary_holdout.pass_,
        valid_until=report.expiration.valid_until,
        invalidation_triggers=list(report.expiration.invalidation_triggers),
        observed_invalidation_triggers=(
            [] if validity is None else validity.observed_invalidation_triggers
        ),
        validity=(
            ApplicabilityStatus.NOT_ESTABLISHED
            if validity is None
            else (
                ApplicabilityStatus.VALID
                if validity.valid
                else ApplicabilityStatus.INVALID
            )
        ),
        validity_reasons=[] if validity is None else list(validity.reasons),
        validity_checked_at=None if validity is None else validity.evaluated_at,
    )


def check_calibration_validity(
    *,
    calibration_id: str,
    report: CalibrationReport,
    now: datetime | None = None,
    observed_invalidation_triggers: list[str] | None = None,
) -> CalibrationInvalidationStatus:
    """Check expiration and explicit stationarity-regime invalidation triggers."""

    effective_now = now or datetime.now(UTC)
    triggers = set(observed_invalidation_triggers or [])
    configured = set(report.expiration.invalidation_triggers)
    matched_triggers = sorted(triggers & configured)
    expired = effective_now > report.expiration.valid_until
    reasons: list[str] = []
    if expired:
        reasons.append("calibration_expired")
    reasons.extend(matched_triggers)
    status = CalibrationInvalidationStatus(
        calibration_id=calibration_id,
        expired=expired,
        invalidated=bool(matched_triggers),
        valid=not expired and not matched_triggers,
        reasons=reasons,
        observed_invalidation_triggers=matched_triggers,
        evaluated_at=effective_now,
    )
    _LAST_VALIDITY.set((id(report), calibration_id, status))
    return status
