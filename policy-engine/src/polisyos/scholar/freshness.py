"""Evaluate and report knowledge-bundle freshness against policy thresholds."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.core.contracts.scholar import FreshnessMetadata, FreshnessStatus
from polisyos.core.observability import get_metrics

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.observability import MetricsRegistry
    from polisyos.scholar.freshness_store import FreshnessRuntimeState
    from polisyos.scholar.policies import ScholarPolicy

_DEFAULT_STALENESS_DAYS = 30
_DEFAULT_EXPIRY_DAYS = 90
_DEFAULT_COOLDOWN_SECONDS = 3600

_DOMAIN_DAYS_DEFAULTS: dict[str, tuple[int, int, int]] = {
    "fiscal": (90, 365, 3600),
    "labor": (30, 90, 3600),
    "health": (14, 60, 1800),
    "infrastructure": (180, 730, 7200),
    "education": (60, 365, 3600),
}


@dataclass(frozen=True)
class DomainThresholds:
    """Carry normalized stale/expired/cooldown cutoffs in seconds."""
    staleness_seconds: int
    expiry_seconds: int
    cooldown_seconds: int


@dataclass(frozen=True)
class FreshnessCheckResult:
    """Return the freshness verdict and refresh/cooldown decision for one bundle."""
    bundle_ref: str
    status: FreshnessStatus
    age_seconds: int
    staleness_ratio: float
    needs_refresh: bool
    cooldown_active: bool
    retry_after_seconds: int | None
    reason: str

    @property
    def blocked_by_cooldown(self) -> bool:
        """Report whether refresh is suppressed solely by the cooldown window."""
        return self.cooldown_active


def _sanitize_thresholds(
    stale_days: int,
    expiry_days: int,
    cooldown_seconds: int,
) -> DomainThresholds:
    stale = max(1, int(stale_days))
    expiry = max(stale, int(expiry_days))
    cooldown = max(0, int(cooldown_seconds))
    return DomainThresholds(
        staleness_seconds=stale * 24 * 3600,
        expiry_seconds=expiry * 24 * 3600,
        cooldown_seconds=cooldown,
    )


def resolve_domain_thresholds(
    domain: str | None,
    *,
    policy: ScholarPolicy | None = None,
) -> DomainThresholds:
    """Resolve domain thresholds."""
    key = (domain or "").strip().lower()

    if policy is not None:
        resolved = policy.freshness.resolve(domain)
        return _sanitize_thresholds(
            resolved.staleness_days,
            resolved.expiry_days,
            resolved.cooldown_seconds,
        )

    if key in _DOMAIN_DAYS_DEFAULTS:
        stale_days, expiry_days, cooldown_seconds = _DOMAIN_DAYS_DEFAULTS[key]
    else:
        stale_days = _DEFAULT_STALENESS_DAYS
        expiry_days = _DEFAULT_EXPIRY_DAYS
        cooldown_seconds = _DEFAULT_COOLDOWN_SECONDS

    return _sanitize_thresholds(stale_days, expiry_days, cooldown_seconds)


def build_freshness_metadata(
    *,
    domain: str | None,
    source_freshness_at: datetime | None,
    policy: ScholarPolicy | None = None,
    previous_bundle_ref: str | None = None,
    enrichment_count: int = 1,
    last_refresh_attempt_at: datetime | None = None,
    now: datetime | None = None,
) -> FreshnessMetadata:
    # Keep knowledge bundle payload deterministic when source timestamps exist.
    # Mutable freshness bookkeeping is handled by FreshnessStateStore sidecar.
    """Build freshness metadata."""
    reference_now = now or source_freshness_at or datetime(1970, 1, 1, tzinfo=UTC)
    thresholds = resolve_domain_thresholds(domain, policy=policy)
    return FreshnessMetadata(
        created_at=reference_now,
        source_freshness_at=source_freshness_at,
        staleness_threshold_seconds=thresholds.staleness_seconds,
        expiry_threshold_seconds=thresholds.expiry_seconds,
        refresh_cooldown_seconds=thresholds.cooldown_seconds,
        enrichment_count=max(1, int(enrichment_count)),
        previous_bundle_ref=previous_bundle_ref,
        last_refresh_attempt_at=last_refresh_attempt_at,
    )


class FreshnessPolicy:
    """Decide whether a bundle should refresh, continue, or block execution."""
    def __init__(
        self,
        *,
        auto_refresh_on_stale: bool = True,
        block_on_expired: bool = False,
        refresh_cooldown_seconds: int = 3600,
    ) -> None:
        self.auto_refresh_on_stale = auto_refresh_on_stale
        self.block_on_expired = block_on_expired
        self.refresh_cooldown_seconds = max(0, int(refresh_cooldown_seconds))

    def check(
        self,
        *,
        bundle_ref: str,
        freshness: FreshnessMetadata,
        runtime_state: FreshnessRuntimeState | None = None,
        now: datetime | None = None,
        external_drift_signals: Mapping[str, bool] | None = None,
    ) -> FreshnessCheckResult:
        """Evaluate age, expiry, external drift, and runtime cooldown state."""
        now_utc = now or datetime.now(UTC)
        status = freshness.compute_status(now_utc)
        age_seconds = freshness.age_seconds(now_utc)

        stale_threshold = max(1, freshness.staleness_threshold_seconds)
        ratio = age_seconds / stale_threshold
        drift_detected = any(bool(value) for value in (external_drift_signals or {}).values())

        cooldown_window = max(self.refresh_cooldown_seconds, freshness.refresh_cooldown_seconds)
        retry_after_seconds: int | None = None
        cooldown_active = False

        runtime_next_retry = runtime_state.next_retry_at if runtime_state is not None else None
        if runtime_next_retry is not None and now_utc < runtime_next_retry:
            cooldown_active = True
            retry_after_seconds = int((runtime_next_retry - now_utc).total_seconds())
        else:
            last_attempt = (
                runtime_state.last_refresh_attempt_at
                if runtime_state is not None and runtime_state.last_refresh_attempt_at is not None
                else freshness.last_refresh_attempt_at
            )
            if last_attempt is not None and cooldown_window > 0:
                elapsed = int((now_utc - last_attempt).total_seconds())
                if elapsed < cooldown_window:
                    cooldown_active = True
                    retry_after_seconds = cooldown_window - elapsed

        needs_refresh = False
        reason = "fresh"
        if status is FreshnessStatus.EXPIRED:
            needs_refresh = True
            reason = "bundle expired"
        elif status is FreshnessStatus.STALE and self.auto_refresh_on_stale:
            needs_refresh = True
            reason = "bundle stale"
        elif drift_detected:
            needs_refresh = True
            reason = "external drift signal"

        if needs_refresh and cooldown_active:
            needs_refresh = False
            reason = "refresh cooldown active"

        return FreshnessCheckResult(
            bundle_ref=bundle_ref,
            status=status,
            age_seconds=age_seconds,
            staleness_ratio=ratio,
            needs_refresh=needs_refresh,
            cooldown_active=cooldown_active,
            retry_after_seconds=retry_after_seconds,
            reason=reason,
        )


def emit_freshness_metrics(
    result: FreshnessCheckResult,
    *,
    metrics: MetricsRegistry | Any | None = None,
) -> None:
    """Publish the freshness verdict to the configured metrics backend."""
    resolved_metrics = metrics if metrics is not None else get_metrics()
    record = getattr(resolved_metrics, "record_knowledge_freshness_check", None)
    if callable(record):
        record(
            bundle_ref=result.bundle_ref,
            status=result.status.value,
            age_seconds=float(result.age_seconds),
            staleness_ratio=float(result.staleness_ratio),
        )
    else:
        labels = {"bundle_ref": result.bundle_ref[:16]}
        age_metric = getattr(resolved_metrics, "knowledge_bundle_age_seconds", None)
        if age_metric is not None and hasattr(age_metric, "set"):
            age_metric.set(float(result.age_seconds), labels)

        ratio_metric = getattr(resolved_metrics, "knowledge_bundle_staleness_ratio", None)
        if ratio_metric is not None and hasattr(ratio_metric, "set"):
            ratio_metric.set(float(result.staleness_ratio), labels)

        status_metric = getattr(resolved_metrics, "knowledge_bundle_status", None)
        if status_metric is not None and hasattr(status_metric, "set"):
            status_metric.set(1.0, {"status": result.status.value})

    if result.needs_refresh:
        refresh = getattr(resolved_metrics, "record_knowledge_refresh", None)
        if callable(refresh):
            refresh(reason=result.reason)
        else:
            counter = getattr(resolved_metrics, "knowledge_bundle_refresh_total", None)
            if counter is not None and hasattr(counter, "add"):
                counter.add(1, {"reason": result.reason})


def timed_freshness_check(
    policy: FreshnessPolicy,
    *,
    bundle_ref: str,
    freshness: FreshnessMetadata,
    runtime_state: FreshnessRuntimeState | None = None,
    now: datetime | None = None,
    external_drift_signals: Mapping[str, bool] | None = None,
    metrics: MetricsRegistry | Any | None = None,
) -> FreshnessCheckResult:
    """Run a freshness check, record latency/status metrics, and return the verdict."""
    started = time.perf_counter()
    result = policy.check(
        bundle_ref=bundle_ref,
        freshness=freshness,
        runtime_state=runtime_state,
        now=now,
        external_drift_signals=external_drift_signals,
    )
    elapsed = time.perf_counter() - started

    resolved_metrics = metrics if metrics is not None else get_metrics()
    duration_metric = getattr(resolved_metrics, "knowledge_bundle_check_duration_seconds", None)
    if duration_metric is not None and hasattr(duration_metric, "record"):
        duration_metric.record(elapsed, {"status": result.status.value})

    emit_freshness_metrics(result, metrics=resolved_metrics)
    return result


__all__ = [
    "DomainThresholds",
    "FreshnessCheckResult",
    "FreshnessPolicy",
    "build_freshness_metadata",
    "emit_freshness_metrics",
    "resolve_domain_thresholds",
    "timed_freshness_check",
]
