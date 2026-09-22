"""Calibration audit and expiration checks for DDM-15.7."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ddm.integration.events import CalibrationAudit, CalibrationValidityProjection

if TYPE_CHECKING:
    from polisyos.ddm.calibration.calibrate import CalibrationReport


CALIBRATION_VALIDITY_VERIFIER_ID = "polisyos.ddm.calibration.check_calibration_validity"
CALIBRATION_VALIDITY_VERIFIER_VERSION = "1"
_IMMUTABLE_VALIDITY_PROJECTION_FIELDS = (
    "calibration_id",
    "detector_id",
    "stationarity_regime_id",
    "report_digest",
)


class CalibrationInvalidationStatus(BaseModel):
    """Whether a calibration artifact is currently valid."""

    model_config = ConfigDict(extra="forbid")

    calibration_id: str = Field(min_length=1)
    expired: bool
    invalidated: bool
    valid: bool
    reasons: list[str] = Field(default_factory=list)


_CHECKER_EVIDENCE_TOKEN = object()


@dataclass(frozen=True)
class _CalibrationValidityEvidence:
    """Private, checker-issued applicability evidence for one calibration report."""

    issuer_token: object
    calibration_id: str
    report_digest: str
    effective_at: datetime
    status: CalibrationInvalidationStatus
    projection: CalibrationValidityProjection
    audit_binding_reasons: tuple[str, ...]

    @property
    def is_bound(self) -> bool:
        """Return whether the checker result is bound to the projected audit."""

        return (
            self.issuer_token is _CHECKER_EVIDENCE_TOKEN
            and not self.audit_binding_reasons
        )


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


def build_calibration_validity_projection(
    *,
    calibration_id: str,
    report: CalibrationReport,
    now: datetime,
    observed_invalidation_triggers: list[str] | None,
) -> CalibrationValidityProjection:
    """Build a durable projection from the canonical validity checker."""

    status = check_calibration_validity(
        calibration_id=calibration_id,
        report=report,
        now=now,
        observed_invalidation_triggers=observed_invalidation_triggers,
    )
    observation_status = "observed" if observed_invalidation_triggers is not None else "unavailable"
    projection_status = "not_established"
    if observation_status == "observed":
        if status.invalidated:
            projection_status = "invalidated"
        elif status.expired:
            projection_status = "expired"
        else:
            projection_status = "valid"
    projection_reasons = list(status.reasons)
    if observation_status != "observed":
        projection_reasons.append("invalidation_observation_unavailable")
    return CalibrationValidityProjection(
        calibration_id=calibration_id,
        detector_id=report.detector_id,
        stationarity_regime_id=report.stationarity_regime_id,
        report_digest=_canonical_report_digest(report),
        verifier_id=CALIBRATION_VALIDITY_VERIFIER_ID,
        verifier_version=CALIBRATION_VALIDITY_VERIFIER_VERSION,
        effective_at=now,
        valid_until=report.expiration.valid_until,
        configured_invalidation_triggers=report.expiration.invalidation_triggers,
        observed_invalidation_triggers=observed_invalidation_triggers,
        observation_status=observation_status,
        status=projection_status,
        reasons=projection_reasons,
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


def _check_bound_calibration_validity(
    *,
    calibration_id: str,
    report: CalibrationReport,
    audit: CalibrationAudit,
    now: datetime,
    observed_invalidation_triggers: list[str] | None = None,
    expected_projection: CalibrationValidityProjection | None = None,
) -> _CalibrationValidityEvidence:
    """Run the canonical checker and bind its result to the report projection.

    This is intentionally private.  A caller-shaped ``CalibrationAudit`` is
    not allowed to declare current validity; the monitor must supply the
    source report so this helper can execute the existing checker and compare
    every field that the public audit currently projects from that report.
    During rebind, only the report identity and canonical digest are
    immutable; effective time and observed-trigger fields are recomputed for
    the current context.
    """

    status = check_calibration_validity(
        calibration_id=calibration_id,
        report=report,
        now=now,
        observed_invalidation_triggers=observed_invalidation_triggers,
    )
    projection = build_calibration_validity_projection(
        calibration_id=calibration_id,
        report=report,
        now=now,
        observed_invalidation_triggers=observed_invalidation_triggers,
    )
    expected_audit = build_calibration_audit(
        calibration_id=calibration_id,
        report=report,
    )
    expected_payload = expected_audit.model_dump(mode="json", by_alias=True)
    actual_payload = audit.model_dump(mode="json", by_alias=True)
    binding_reasons = [
        f"calibration_audit_{field}_mismatch"
        for field in sorted(set(expected_payload) | set(actual_payload))
        if expected_payload.get(field) != actual_payload.get(field)
    ]
    if expected_projection is not None:
        expected_projection_payload = expected_projection.model_dump(mode="json")
        projection_payload = projection.model_dump(mode="json")
        binding_reasons.extend(
            f"calibration_validity_{field}_mismatch"
            for field in _IMMUTABLE_VALIDITY_PROJECTION_FIELDS
            if expected_projection_payload.get(field) != projection_payload.get(field)
        )
    return _CalibrationValidityEvidence(
        issuer_token=_CHECKER_EVIDENCE_TOKEN,
        calibration_id=calibration_id,
        report_digest=projection.report_digest,
        effective_at=now,
        status=status,
        projection=projection,
        audit_binding_reasons=tuple(binding_reasons),
    )


def _canonical_report_digest(report: CalibrationReport) -> str:
    report_payload = report.model_dump(mode="json")
    report_bytes = json.dumps(
        report_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(report_bytes).hexdigest()
