"""Normalize UTC timestamps for manifests, events, and JSON APIs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now(*, drop_microseconds: bool = False) -> datetime:
    """Return the current UTC datetime, optionally dropping microseconds."""
    current = datetime.now(timezone.utc)
    if drop_microseconds:
        return current.replace(microsecond=0)
    return current


def ensure_utc(value: datetime) -> datetime:
    """Convert naive/aware datetimes to UTC while preserving the instant."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_iso_utc(value: datetime, *, z_suffix: bool = True) -> str:
    """Convert to iso utc."""
    rendered = ensure_utc(value).isoformat()
    if z_suffix:
        return rendered.replace("+00:00", "Z")
    return rendered


def parse_iso_datetime(value: Any) -> datetime | None:
    """Parse ISO-8601 strings or datetimes into UTC, returning `None` on failure."""
    if isinstance(value, datetime):
        return ensure_utc(value)
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return ensure_utc(parsed)


def to_epoch_seconds(value: datetime) -> float:
    """Convert to epoch seconds."""
    return ensure_utc(value).timestamp()


def from_epoch_seconds(value: float) -> datetime:
    """Create from epoch seconds."""
    return datetime.fromtimestamp(value, tz=timezone.utc)


__all__ = [
    "ensure_utc",
    "from_epoch_seconds",
    "parse_iso_datetime",
    "to_epoch_seconds",
    "to_iso_utc",
    "utc_now",
]
