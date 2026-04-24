"""Normalize UTC timestamps for manifests, events, and JSON APIs."""

from __future__ import annotations

from datetime import UTC, datetime

_NAIVE_DATETIME_ERROR = "Naive datetimes are not allowed; supply a timezone-aware UTC value."


def utc_now(*, drop_microseconds: bool = False) -> datetime:
    """Return the current UTC datetime, optionally dropping microseconds."""
    current = datetime.now(UTC)
    if drop_microseconds:
        return current.replace(microsecond=0)
    return current


def ensure_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC while preserving the instant."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(_NAIVE_DATETIME_ERROR)
    return value.astimezone(UTC)


def to_iso_utc(value: datetime, *, z_suffix: bool = True) -> str:
    """Convert to iso utc."""
    rendered = ensure_utc(value).isoformat()
    if z_suffix:
        return rendered.replace("+00:00", "Z")
    return rendered


def parse_iso_datetime(value: object) -> datetime | None:
    """Parse ISO-8601 strings or datetimes into UTC, returning `None` on failure."""
    if isinstance(value, datetime):
        try:
            return ensure_utc(value)
        except ValueError:
            return None
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        return ensure_utc(parsed)
    except ValueError:
        return None


def to_epoch_seconds(value: datetime) -> float:
    """Convert to epoch seconds."""
    return ensure_utc(value).timestamp()


def from_epoch_seconds(value: float) -> datetime:
    """Create from epoch seconds."""
    return datetime.fromtimestamp(value, tz=UTC)


__all__ = [
    "ensure_utc",
    "from_epoch_seconds",
    "parse_iso_datetime",
    "to_epoch_seconds",
    "to_iso_utc",
    "utc_now",
]
