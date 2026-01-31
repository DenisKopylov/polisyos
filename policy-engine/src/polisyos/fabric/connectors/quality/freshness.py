"""
Freshness checking logic with schedule-aware policies.

Distinguishes between cache age (time since fetch) and data age
(time since the source updated). Supports schedule inference and
adaptive TTL based on update intervals (not data age).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
import logging

from polisyos.ir.connectors import ConnectorCapability

from .report import FreshnessLevel, FreshnessStatus

logger = logging.getLogger(__name__)

KNOWN_SCHEDULES = {
    "real-time",
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "annual",
}

SCHEDULE_ALIASES = {
    "realtime": "real-time",
    "real_time": "real-time",
    "real time": "real-time",
    "streaming": "real-time",
    "live": "real-time",
    "minutely": "real-time",
    "minute": "real-time",
    "seconds": "real-time",
    "second": "real-time",
    "hour": "hourly",
    "day": "daily",
    "week": "weekly",
    "month": "monthly",
    "quarter": "quarterly",
    "year": "annual",
    "yearly": "annual",
}

SCHEDULE_INTERVALS = {
    "real-time": timedelta(minutes=1),
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "quarterly": timedelta(days=91),
    "annual": timedelta(days=365),
}


@dataclass(frozen=True)
class FreshnessPolicy:
    """
    TTL policy for a dataset.

    Supports both fixed and adaptive policies.
    """

    ttl: timedelta
    schedule: str

    adaptive: bool = False
    multiplier: float = 1.5

    fresh_threshold: float = 0.8
    healthy_threshold: float = 1.2


DEFAULT_POLICIES = {
    "real-time": FreshnessPolicy(ttl=timedelta(minutes=5), schedule="real-time"),
    "hourly": FreshnessPolicy(ttl=timedelta(hours=2), schedule="hourly"),
    "daily": FreshnessPolicy(ttl=timedelta(days=2), schedule="daily"),
    "weekly": FreshnessPolicy(ttl=timedelta(days=10), schedule="weekly"),
    "monthly": FreshnessPolicy(ttl=timedelta(days=45), schedule="monthly"),
    "quarterly": FreshnessPolicy(ttl=timedelta(days=120), schedule="quarterly"),
    "annual": FreshnessPolicy(ttl=timedelta(days=400), schedule="annual"),
}


class FreshnessChecker:
    """
    Schedule-aware freshness validation.

    Uses dataset-specific policies when available, otherwise falls back
    to schedule policies and defaults.
    """

    def __init__(
        self,
        policies: dict[str, FreshnessPolicy] | None = None,
        *,
        dataset_policies: dict[str, FreshnessPolicy] | None = None,
        schedule_policies: dict[str, FreshnessPolicy] | None = None,
    ) -> None:
        self._dataset_policies: dict[str, FreshnessPolicy] = dict(dataset_policies or {})
        self._schedule_policies: dict[str, FreshnessPolicy] = dict(schedule_policies or {})

        if policies:
            for key, policy in policies.items():
                normalized = _normalize_schedule(str(key))
                if normalized in KNOWN_SCHEDULES:
                    self._schedule_policies.setdefault(normalized, policy)
                else:
                    self._dataset_policies.setdefault(str(key), policy)

    def check_freshness(
        self,
        dataset_id: str,
        metadata: Any | None,
        fetched_at: datetime,
        last_updated: datetime | None = None,
    ) -> FreshnessStatus:
        now = datetime.now(timezone.utc)

        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if last_updated and last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        cache_age = now - fetched_at
        data_age = (now - last_updated) if last_updated else None

        policy = self._get_policy(dataset_id, metadata)
        ttl = policy.ttl

        if policy.adaptive:
            update_interval = _extract_update_interval(metadata)
            if update_interval is not None:
                ttl = update_interval * policy.multiplier
            else:
                logger.debug(
                    "Adaptive freshness disabled: no update_interval for %s",
                    dataset_id,
                )

        age_to_check = data_age if data_age else cache_age
        ttl_seconds = int(ttl.total_seconds())

        if age_to_check <= ttl * policy.fresh_threshold:
            level = FreshnessLevel.FRESH
            message = (
                f"Data is fresh ({_format_age(age_to_check)} < {policy.schedule} TTL)"
            )
        elif age_to_check <= ttl * policy.healthy_threshold:
            level = FreshnessLevel.HEALTHY
            message = (
                f"Data is healthy ({_format_age(age_to_check)} within acceptable range)"
            )
        elif age_to_check <= ttl * 2.0:
            level = FreshnessLevel.STALE
            message = (
                f"Data is stale ({_format_age(age_to_check)} > {policy.schedule} TTL)"
            )
        else:
            level = FreshnessLevel.EXPIRED
            message = (
                "Data is critically outdated "
                f"({_format_age(age_to_check)} >> {policy.schedule} TTL)"
            )

        return FreshnessStatus(
            level=level,
            cache_age_seconds=int(cache_age.total_seconds()),
            data_age_seconds=int(data_age.total_seconds()) if data_age else None,
            ttl_seconds=ttl_seconds,
            schedule=policy.schedule,
            last_updated=last_updated,
            fetched_at=fetched_at,
            message=message,
        )

    def _get_policy(self, dataset_id: str, metadata: Any | None) -> FreshnessPolicy:
        if dataset_id in self._dataset_policies:
            return self._dataset_policies[dataset_id]

        schedule = self._infer_schedule(dataset_id, metadata)

        if schedule in self._schedule_policies:
            return self._schedule_policies[schedule]

        if schedule in DEFAULT_POLICIES:
            return DEFAULT_POLICIES[schedule]

        return DEFAULT_POLICIES["daily"]

    def _infer_schedule(self, dataset_id: str, metadata: Any | None) -> str:
        schedule_hint = None
        if metadata is not None:
            schedule_hint = _normalize_schedule(getattr(metadata, "schedule", None))
            if schedule_hint is None:
                schedule_hint = _normalize_schedule(
                    getattr(metadata, "update_frequency", None)
                )

        if schedule_hint in KNOWN_SCHEDULES:
            return schedule_hint

        dataset_lower = dataset_id.lower()

        keyword_map = {
            "real-time": ["real-time", "realtime", "real_time", "live", "stream"],
            "hourly": ["hourly", "hour"],
            "daily": ["daily"],
            "weekly": ["weekly", "week"],
            "monthly": ["monthly", "month", "census", "survey"],
            "quarterly": ["quarterly", "quarter"],
            "annual": ["annual", "yearly", "year"],
        }

        for schedule, keywords in keyword_map.items():
            if any(kw in dataset_lower for kw in keywords):
                return schedule

        if _has_streaming_capability(metadata):
            return "real-time"

        return "daily"


def _normalize_schedule(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"", "unknown", "n/a", "na", "none", "null"}:
        return None
    text = text.replace("_", "-")
    if text in SCHEDULE_ALIASES:
        text = SCHEDULE_ALIASES[text]
    if text in KNOWN_SCHEDULES:
        return text
    return None


def _has_streaming_capability(metadata: Any | None) -> bool:
    if metadata is None:
        return False
    caps = getattr(metadata, "capabilities", None)
    if caps is None:
        return False
    try:
        if isinstance(caps, ConnectorCapability):
            return ConnectorCapability.STREAMING in caps
        if isinstance(caps, int):
            return bool(ConnectorCapability(caps) & ConnectorCapability.STREAMING)
        if isinstance(caps, (set, frozenset, list, tuple)):
            return ConnectorCapability.STREAMING in caps
    except Exception:
        return False
    return False


def _extract_update_interval(metadata: Any | None) -> timedelta | None:
    if metadata is None:
        return None

    value = getattr(metadata, "update_interval", None)
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))

    seconds = getattr(metadata, "update_interval_seconds", None)
    if isinstance(seconds, (int, float)):
        return timedelta(seconds=float(seconds))

    schedule = _normalize_schedule(getattr(metadata, "update_frequency", None))
    if schedule in SCHEDULE_INTERVALS:
        return SCHEDULE_INTERVALS[schedule]

    return None


def _format_age(age: timedelta) -> str:
    seconds = int(age.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    days = seconds // 86400
    if days > 365:
        return f"{days // 365}y"
    if days > 30:
        return f"{days // 30}mo"
    return f"{days}d"
