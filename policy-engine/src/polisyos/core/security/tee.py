"""Public security tee module API."""
from __future__ import annotations

import json
import os
from abc import abstractmethod
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.canon import content_hash, truncated_hash


class TEEPlatform(str, Enum):
    """TEE platform public type."""
    SEV_SNP = "sev-snp"
    TDX = "tdx"
    NITRO = "nitro"


class AttestationStatus(str, Enum):
    """Attestation status public type."""
    VERIFIED = "verified"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class AttestationReport(BaseModel):
    """Normalized attestation report.

    The report is intentionally represented as JSON-friendly fields because
    production deployments can source it from a sidecar/agent in online and
    air-gapped environments.
    """

    model_config = ConfigDict(extra="forbid")

    platform: TEEPlatform = TEEPlatform.SEV_SNP
    measurement: str = ""
    host_data: str | None = None
    guest_svn: int = 0
    tcb_version: int = 0
    report_data_hex: str = ""
    report_hash: str | None = None
    signature_validated: bool = False
    raw_report_b64: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def normalized_measurement(self) -> str:
        return self.measurement.strip().lower()

    def normalized_host_data(self) -> str | None:
        if self.host_data is None:
            return None
        value = self.host_data.strip().lower()
        return value or None


class AttestationPolicy(BaseModel):
    """Attestation policy data model."""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    allowed_platforms: tuple[TEEPlatform, ...] = (TEEPlatform.SEV_SNP,)
    expected_measurements: tuple[str, ...] = ()
    min_tcb_version: int = 0
    min_guest_svn: int = 0
    require_host_data_match: bool = False
    expected_host_data: str | None = None
    require_signature_validation: bool = True
    max_report_age_seconds: int = 300
    fail_closed: bool = True

    def normalized_measurements(self) -> tuple[str, ...]:
        return tuple(item.strip().lower() for item in self.expected_measurements if item.strip())

    def normalized_expected_host_data(self) -> str | None:
        if self.expected_host_data is None:
            return None
        value = self.expected_host_data.strip().lower()
        return value or None


class AttestationResult(BaseModel):
    """Attestation result data model."""
    model_config = ConfigDict(extra="forbid")

    status: AttestationStatus
    platform: TEEPlatform | None = None
    report_hash: str | None = None
    measurement: str | None = None
    tcb_version: int | None = None
    errors: list[str] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    policy_digest: str | None = None
    cached: bool = False

    @property
    def is_trusted(self) -> bool:
        return self.status == AttestationStatus.VERIFIED


@runtime_checkable
class AttestationVerifier(Protocol):
    """Attestation verifier public type."""
    @abstractmethod
    def fetch_report(
        self,
        *,
        nonce: bytes | None = None,
        timeout_seconds: float = 10.0,
    ) -> AttestationReport:
        ...

    @abstractmethod
    def verify(
        self,
        report: AttestationReport,
        policy: AttestationPolicy,
        *,
        nonce: bytes | None = None,
    ) -> AttestationResult:
        ...


class TEEError(RuntimeError):
    """Base TEE error."""


class TEEUnavailableError(TEEError):
    """TEE hardware or provider is unavailable."""


class AttestationFetchError(TEEError):
    """Attestation report could not be fetched."""


class SEVSNPVerifier:
    """SEV-SNP verifier.

    Current implementation validates policy constraints against a normalized
    report payload. Hardware signature verification is expected to be performed
    by an attestation provider which sets `signature_validated=true`.
    """

    def __init__(self, *, report_path: Path | None = None) -> None:
        self._report_path = report_path

    def fetch_report(
        self,
        *,
        nonce: bytes | None = None,
        timeout_seconds: float = 10.0,
    ) -> AttestationReport:
        del timeout_seconds
        path = self._resolve_report_path()
        if path is not None:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                report = AttestationReport.model_validate(payload)
            except (TypeError, ValueError) as exc:  # noqa: BLE001
                raise AttestationFetchError(f"Failed to parse attestation report: {exc}") from exc

            if nonce is not None and report.report_data_hex:
                nonce_hex = nonce.hex().lower()
                if not report.report_data_hex.lower().startswith(nonce_hex):
                    raise AttestationFetchError("Attestation report nonce does not match challenge")
            return report

        if Path("/dev/sev-guest").exists():
            raise AttestationFetchError(
                "SEV-SNP device is present but no report provider is configured. "
                "Set POLISYOS_TEE_REPORT_PATH to JSON report produced by attestation agent."
            )

        raise TEEUnavailableError("SEV-SNP device not present on this node")

    def verify(
        self,
        report: AttestationReport,
        policy: AttestationPolicy,
        *,
        nonce: bytes | None = None,
    ) -> AttestationResult:
        errors: list[str] = []

        if report.platform != TEEPlatform.SEV_SNP:
            errors.append(f"unsupported platform: {report.platform.value}")

        if report.platform not in policy.allowed_platforms:
            errors.append(f"platform {report.platform.value} not allowed")

        if nonce is not None and not _report_data_matches_nonce(report.report_data_hex, nonce):
            errors.append("report_data nonce mismatch")

        age_seconds = (datetime.now(timezone.utc) - report.collected_at).total_seconds()
        if age_seconds > policy.max_report_age_seconds:
            errors.append(
                f"attestation report expired: age={int(age_seconds)}s "
                f"max={policy.max_report_age_seconds}s"
            )

        expected_measurements = policy.normalized_measurements()
        if expected_measurements and report.normalized_measurement() not in expected_measurements:
            errors.append("launch measurement mismatch")

        if report.tcb_version < policy.min_tcb_version:
            errors.append(
                f"tcb_version too old: {report.tcb_version} < {policy.min_tcb_version}"
            )

        if report.guest_svn < policy.min_guest_svn:
            errors.append(f"guest_svn too old: {report.guest_svn} < {policy.min_guest_svn}")

        expected_host_data = policy.normalized_expected_host_data()
        if policy.require_host_data_match and expected_host_data:
            if report.normalized_host_data() != expected_host_data:
                errors.append("host_data mismatch")

        if policy.require_signature_validation and not report.signature_validated:
            errors.append("signature_validated=false")

        status = AttestationStatus.VERIFIED if not errors else AttestationStatus.FAILED
        return AttestationResult(
            status=status,
            platform=report.platform,
            report_hash=report.report_hash or _fallback_report_hash(report),
            measurement=report.measurement,
            tcb_version=report.tcb_version,
            errors=errors,
            policy_digest=_policy_digest(policy),
        )

    def _resolve_report_path(self) -> Path | None:
        if self._report_path is not None:
            return self._report_path
        env_path = os.getenv("POLISYOS_TEE_REPORT_PATH", "").strip()
        if env_path:
            candidate = Path(env_path)
            if candidate.exists() and candidate.is_file():
                return candidate
        return None


class NoOpVerifier:
    """Verifier for non-confidential or local dev tiers."""

    def fetch_report(
        self,
        *,
        nonce: bytes | None = None,
        timeout_seconds: float = 10.0,
    ) -> AttestationReport:
        del nonce
        del timeout_seconds
        raise TEEUnavailableError("TEE is disabled")

    def verify(
        self,
        report: AttestationReport,
        policy: AttestationPolicy,
        *,
        nonce: bytes | None = None,
    ) -> AttestationResult:
        del report
        del policy
        del nonce
        return AttestationResult(status=AttestationStatus.SKIPPED)


def create_verifier(
    *,
    enabled: bool,
    platform: TEEPlatform = TEEPlatform.SEV_SNP,
    report_path: Path | None = None,
) -> AttestationVerifier:
    """Create verifier."""
    if not enabled:
        return NoOpVerifier()
    if platform == TEEPlatform.SEV_SNP:
        return SEVSNPVerifier(report_path=report_path)
    raise ValueError(f"Unsupported TEE platform: {platform.value}")


def _policy_digest(policy: AttestationPolicy) -> str:
    payload = json.dumps(policy.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return truncated_hash(payload, length=16)


def _fallback_report_hash(report: AttestationReport) -> str:
    payload = json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return content_hash(payload)


def _report_data_matches_nonce(report_data_hex: str, nonce: bytes) -> bool:
    if not report_data_hex:
        return False
    value = report_data_hex.strip().lower()
    try:
        report_data = bytes.fromhex(value)
    except ValueError:
        return False
    return report_data.startswith(nonce)


__all__ = [
    "AttestationFetchError",
    "AttestationPolicy",
    "AttestationReport",
    "AttestationResult",
    "AttestationStatus",
    "AttestationVerifier",
    "NoOpVerifier",
    "SEVSNPVerifier",
    "TEEError",
    "TEEPlatform",
    "TEEUnavailableError",
    "create_verifier",
]
