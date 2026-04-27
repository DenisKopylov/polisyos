"""Calibration audit and expiration checks for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ddm_15_7.integration.events import CalibrationAudit

if TYPE_CHECKING:
    from polisyos.ddm_15_7.calibration.calibrate import CalibrationReport


class CalibrationInvalidationStatus(BaseModel):
    """Whether a calibration artifact is currently valid."""

    model_config = ConfigDict(extra="forbid")

    calibration_id: str = Field(min_length=1)
    expired: bool
    invalidated: bool
    valid: bool
    reasons: list[str] = Field(default_factory=list)


def build_calibration_audit(
    *,
    calibration_id: str,
    report: CalibrationReport,
) -> CalibrationAudit:
    """Project a calibration report into the runtime audit output."""

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
    return CalibrationInvalidationStatus(
        calibration_id=calibration_id,
        expired=expired,
        invalidated=bool(matched_triggers),
        valid=not expired and not matched_triggers,
        reasons=reasons,
    )
