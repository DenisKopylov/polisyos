"""Normalize UTC timestamps for manifests, events, and JSON APIs."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger

logger = get_logger(__name__)

_ISO_LIKE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ][0-9:+.\-Z]+)?$")

if TYPE_CHECKING:
    import pandas as pd

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


def parse_iso_date(value: str | None) -> date | None:
    """Parse an ISO-like date or timestamp, returning its calendar date."""
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw.count("-") == 2:
            return date.fromisoformat(raw)
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        if _ISO_LIKE_RE.fullmatch(raw):
            logger.debug("Failed to parse ISO date: {!r}", value)
        return None


def latest_object_by_subject(
    facts: pd.DataFrame,
    *,
    subject_ids: set[str],
    predicate_id: str,
) -> dict[str, str]:
    """Return the latest non-empty object value for each requested fact subject."""
    if not subject_ids:
        return {}
    subset = facts[
        (facts["predicate_id"] == predicate_id)
        & (facts["subject_id"].isin(subject_ids))
        & (facts["object_value"].notna())
    ].copy()
    if subset.empty:
        return {}
    subset["tx_time"] = subset["tx_time"].fillna("").astype(str)
    subset["fact_id"] = subset["fact_id"].fillna("").astype(str)
    subset = subset.sort_values(
        by=["subject_id", "tx_time", "fact_id"], ascending=[True, False, False]
    )
    subset = subset.drop_duplicates(subset=["subject_id"], keep="first")
    return {str(row["subject_id"]): str(row["object_value"]) for _, row in subset.iterrows()}


def to_epoch_seconds(value: datetime) -> float:
    """Convert to epoch seconds."""
    return ensure_utc(value).timestamp()


def from_epoch_seconds(value: float) -> datetime:
    """Create from epoch seconds."""
    return datetime.fromtimestamp(value, tz=UTC)


__all__ = [
    "ensure_utc",
    "from_epoch_seconds",
    "latest_object_by_subject",
    "parse_iso_date",
    "parse_iso_datetime",
    "to_epoch_seconds",
    "to_iso_utc",
    "utc_now",
]
