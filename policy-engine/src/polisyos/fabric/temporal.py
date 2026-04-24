"""UTC-only temporal helpers for Fabric contracts and runtime comparisons."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

UTC = UTC
DEFAULT_MAX_CLOCK_SKEW = timedelta(minutes=5)


class TemporalValidationError(ValueError):
    """Raised when a Fabric timestamp is invalid or cannot be normalized safely."""


class FutureTimestampError(TemporalValidationError):
    """Raised when a timestamp exceeds the allowed future clock-skew window."""


def utc_now(*, drop_microseconds: bool = False) -> datetime:
    """Return the current UTC datetime."""
    current = datetime.now(UTC)
    if drop_microseconds:
        return current.replace(microsecond=0)
    return current


def from_unix_timestamp_utc(value: int | float) -> datetime:
    """Create a UTC-aware datetime from a Unix timestamp."""
    return datetime.fromtimestamp(float(value), tz=UTC)


def ensure_aware_utc(value: datetime, *, what: str = "datetime") -> datetime:
    """Return a UTC-aware datetime, interpreting naive inputs as UTC."""
    if not isinstance(value, datetime):
        raise TemporalValidationError(f"{what} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_datetime_utc(value: Any, *, what: str = "datetime") -> datetime:
    """Parse ISO-8601 or datetime values into a UTC-aware datetime."""
    if isinstance(value, datetime):
        return ensure_aware_utc(value, what=what)
    if not isinstance(value, str):
        raise TemporalValidationError(f"{what} must be a datetime or ISO-8601 string")

    text = value.strip()
    if not text:
        raise TemporalValidationError(f"{what} must not be empty")

    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TemporalValidationError(f"Invalid {what}: {value!r}") from exc
    return ensure_aware_utc(parsed, what=what)


def normalize_reference_datetime(
    value: datetime,
    *,
    now: datetime | None = None,
    max_future_skew: timedelta = DEFAULT_MAX_CLOCK_SKEW,
    what: str = "timestamp",
    clamp_future: bool = False,
) -> tuple[datetime, str | None]:
    """Normalize one reference datetime for comparisons against ``now``."""
    normalized = ensure_aware_utc(value, what=what)
    current = ensure_aware_utc(now or utc_now(), what="current time")
    if normalized <= current:
        return normalized, None

    skew = normalized - current
    if skew <= max_future_skew:
        return current, None

    message = (
        f"{what} {normalized.isoformat()} exceeds the future clock-skew tolerance "
        f"of {int(max_future_skew.total_seconds())} seconds"
    )
    if clamp_future:
        return current, message
    raise FutureTimestampError(message)


def utc_age(
    value: datetime,
    *,
    now: datetime | None = None,
    max_future_skew: timedelta = DEFAULT_MAX_CLOCK_SKEW,
    what: str = "timestamp",
    clamp_future: bool = False,
) -> tuple[timedelta, str | None]:
    """Return the UTC age of a timestamp, guarding against future-skew."""
    current = ensure_aware_utc(now or utc_now(), what="current time")
    normalized, warning = normalize_reference_datetime(
        value,
        now=current,
        max_future_skew=max_future_skew,
        what=what,
        clamp_future=clamp_future,
    )
    return current - normalized, warning


__all__ = [
    "DEFAULT_MAX_CLOCK_SKEW",
    "FutureTimestampError",
    "TemporalValidationError",
    "ensure_aware_utc",
    "from_unix_timestamp_utc",
    "normalize_reference_datetime",
    "parse_datetime_utc",
    "utc_age",
    "utc_now",
]
