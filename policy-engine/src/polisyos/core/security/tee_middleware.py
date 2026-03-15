from __future__ import annotations

import os
import time

from polisyos.core.cache import TTLCache
from polisyos.core.observability import get_metrics
from polisyos.core.security.settings import SecuritySettings, get_security_settings
from polisyos.core.security.tee import (
    AttestationFetchError,
    AttestationPolicy,
    AttestationResult,
    AttestationStatus,
    AttestationVerifier,
    TEEError,
    TEEPlatform,
    create_verifier,
)


class AttestationDeniedError(RuntimeError):
    """Raised when TEE attestation policy denies execution."""


class TEEGatekeeper:
    """Gatekeeper that enforces TEE attestation before sensitive execution."""

    def __init__(
        self,
        *,
        cell_tier: str,
        policy: AttestationPolicy,
        enforce_tiers: frozenset[str],
        verifier: AttestationVerifier,
        cache_ttl_seconds: int,
    ) -> None:
        self._cell_tier = cell_tier.strip().lower()
        self._policy = policy
        self._enforce_tiers = frozenset(item.strip().lower() for item in enforce_tiers)
        self._verifier = verifier
        self._cache_ttl_seconds = max(0, cache_ttl_seconds)
        self._cache = TTLCache[str, AttestationResult](
            ttl_seconds=float(self._cache_ttl_seconds),
            time_fn=time.monotonic,
        )

    @classmethod
    def from_settings(
        cls,
        *,
        settings: SecuritySettings | None = None,
        cell_tier: str | None = None,
        verifier: AttestationVerifier | None = None,
    ) -> "TEEGatekeeper":
        resolved = settings or get_security_settings()
        tier = (cell_tier or resolved.POLISYOS_DEFAULT_CELL_TIER).strip().lower()
        platform = _resolve_platform(resolved.POLISYOS_TEE_PLATFORM)
        policy = _policy_from_settings(resolved)
        report_path = resolved.POLISYOS_TEE_REPORT_PATH.strip()
        report_file = None
        if report_path:
            from pathlib import Path

            report_file = Path(report_path)
        gate_verifier = verifier or create_verifier(
            enabled=resolved.tee_enabled,
            platform=platform,
            report_path=report_file,
        )
        return cls(
            cell_tier=tier,
            policy=policy,
            enforce_tiers=resolved.tee_enforce_tiers(),
            verifier=gate_verifier,
            cache_ttl_seconds=resolved.POLISYOS_TEE_CACHE_TTL_SECONDS,
        )

    def gate(
        self,
        *,
        node_id: str | None = None,
        nonce: bytes | None = None,
    ) -> AttestationResult:
        started = time.perf_counter()
        metrics = get_metrics()

        if not self._policy.enabled or self._cell_tier not in self._enforce_tiers:
            result = AttestationResult(status=AttestationStatus.SKIPPED)
            metrics.record_tee_attestation(platform="none", outcome=result.status.value)
            metrics.record_tee_attestation_duration(platform="none", duration_seconds=0.0)
            return result

        cache_key = (node_id or os.getenv("HOSTNAME") or "default-node").strip()
        cached_result_raw = self._cache.get(cache_key)
        if cached_result_raw is not None:
            cached_result = cached_result_raw.model_copy(update={"cached": True})
            platform_label = cached_result.platform.value if cached_result.platform else "unknown"
            metrics.record_tee_attestation_cache_hit(platform=platform_label)
            metrics.record_tee_attestation(platform=platform_label, outcome="cache_hit")
            metrics.record_tee_attestation_duration(
                platform=platform_label,
                duration_seconds=time.perf_counter() - started,
            )
            return cached_result

        try:
            report = self._verifier.fetch_report(nonce=nonce)
            result = self._verifier.verify(report, self._policy, nonce=nonce)
        except (AttestationFetchError, AttestationDeniedError, TEEError, RuntimeError, ValueError) as exc:  # noqa: BLE001
            status = (
                AttestationStatus.UNAVAILABLE
                if self._policy.fail_closed
                else AttestationStatus.SKIPPED
            )
            result = AttestationResult(status=status, errors=[str(exc)])

        self._cache.set(cache_key, result)
        platform_label = result.platform.value if result.platform else "unknown"
        metrics.record_tee_attestation(platform=platform_label, outcome=result.status.value)
        metrics.record_tee_attestation_duration(
            platform=platform_label,
            duration_seconds=time.perf_counter() - started,
        )
        return result

    def enforce(
        self,
        *,
        node_id: str | None = None,
        nonce: bytes | None = None,
    ) -> AttestationResult:
        result = self.gate(node_id=node_id, nonce=nonce)
        if self.is_allowed(result):
            return result
        reasons = "; ".join(result.errors) or "attestation denied"
        raise AttestationDeniedError(reasons)

    def is_allowed(self, result: AttestationResult) -> bool:
        if result.status == AttestationStatus.VERIFIED:
            return True
        if result.status == AttestationStatus.SKIPPED:
            return True
        return not self._policy.fail_closed


def _resolve_platform(raw: str) -> TEEPlatform:
    value = raw.strip().lower()
    for platform in TEEPlatform:
        if platform.value == value:
            return platform
    return TEEPlatform.SEV_SNP


def _policy_from_settings(settings: SecuritySettings) -> AttestationPolicy:
    expected_measurements = tuple(
        item.strip().lower()
        for item in settings.POLISYOS_TEE_EXPECTED_MEASUREMENTS.split(",")
        if item.strip()
    )
    expected_host_data = settings.POLISYOS_TEE_EXPECTED_HOST_DATA.strip().lower() or None
    return AttestationPolicy(
        enabled=settings.tee_enabled,
        expected_measurements=expected_measurements,
        min_tcb_version=max(0, settings.POLISYOS_TEE_MIN_TCB_VERSION),
        min_guest_svn=max(0, settings.POLISYOS_TEE_MIN_GUEST_SVN),
        require_host_data_match=expected_host_data is not None,
        expected_host_data=expected_host_data,
        require_signature_validation=settings.POLISYOS_TEE_REQUIRE_SIGNATURE_VALIDATION,
        max_report_age_seconds=max(1, settings.POLISYOS_TEE_MAX_REPORT_AGE_SECONDS),
        fail_closed=settings.tee_required,
    )


__all__ = ["AttestationDeniedError", "TEEGatekeeper"]
