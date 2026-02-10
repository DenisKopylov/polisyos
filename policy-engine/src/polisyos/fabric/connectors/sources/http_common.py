from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable, Mapping

import pandas as pd

from polisyos.fabric.connectors.resilience.rate_limiter import parse_retry_after_header
from polisyos.ir.connectors import DataVersion, VersionStrategy

FRESHNESS_SOURCE_TIMESTAMP_MISSING = "freshness:source_timestamp_missing"


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def frame_completeness(frame: pd.DataFrame) -> float:
    if frame.size == 0:
        return 1.0
    null_ratio = float(frame.isna().sum().sum()) / float(frame.size)
    return 1.0 - null_ratio


def parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    retry_after = parse_retry_after_header(headers.get("Retry-After"))
    if retry_after is not None:
        return retry_after

    reset = headers.get("X-RateLimit-Reset")
    if reset is None:
        return None
    try:
        reset_ts = float(reset)
    except (TypeError, ValueError):
        return None
    now_ts = datetime.now(timezone.utc).timestamp()
    return max(0.0, reset_ts - now_ts)


def build_data_version(
    *,
    etag: str | None,
    last_modified: str | None,
    content_hash: str,
    fetched_at: datetime,
) -> tuple[DataVersion, datetime | None]:
    source_updated_at = parse_http_datetime(last_modified)
    if etag:
        return (
            DataVersion(
                strategy=VersionStrategy.ETAG,
                value=etag,
                timestamp=fetched_at,
                content_hash=content_hash,
            ),
            source_updated_at,
        )
    if source_updated_at is not None:
        return (
            DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=source_updated_at.isoformat(),
                timestamp=source_updated_at,
                content_hash=content_hash,
            ),
            source_updated_at,
        )
    return (
        DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=content_hash,
            timestamp=fetched_at,
            content_hash=content_hash,
        ),
        source_updated_at,
    )


def quality_flags_from_source_metadata(
    *,
    source_updated_at: datetime | None,
    base_flags: Iterable[str] = (),
) -> frozenset[str]:
    flags = {str(flag) for flag in base_flags}
    if source_updated_at is None:
        flags.add(FRESHNESS_SOURCE_TIMESTAMP_MISSING)
    return frozenset(sorted(flags))


__all__ = [
    "FRESHNESS_SOURCE_TIMESTAMP_MISSING",
    "build_data_version",
    "frame_completeness",
    "parse_http_datetime",
    "quality_flags_from_source_metadata",
    "retry_after_seconds",
    "safe_float",
    "safe_int",
]
