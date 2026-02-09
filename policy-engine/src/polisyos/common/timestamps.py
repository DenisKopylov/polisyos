from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now(*, drop_microseconds: bool = False) -> datetime:
    current = datetime.now(timezone.utc)
    if drop_microseconds:
        return current.replace(microsecond=0)
    return current


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_iso_utc(value: datetime, *, z_suffix: bool = True) -> str:
    rendered = ensure_utc(value).isoformat()
    if z_suffix:
        return rendered.replace("+00:00", "Z")
    return rendered


def parse_iso_datetime(value: Any) -> datetime | None:
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
    return ensure_utc(value).timestamp()


def from_epoch_seconds(value: float) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


__all__ = [
    "ensure_utc",
    "from_epoch_seconds",
    "parse_iso_datetime",
    "to_epoch_seconds",
    "to_iso_utc",
    "utc_now",
]
