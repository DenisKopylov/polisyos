"""Watermark extraction policies for cursor advancement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import floor
from typing import Any

from polisyos.core.contracts.cursor import WatermarkType, WindowStrategy
from polisyos.fabric.temporal import parse_datetime_utc
from polisyos.ir.connectors import VersionStrategy


class WatermarkPolicy(ABC):
    """Extracts watermark value from a FetchResult for cursor advancement."""

    @property
    @abstractmethod
    def watermark_type(self) -> WatermarkType: ...

    @abstractmethod
    def extract(self, result: Any) -> str | None:
        """Extract watermark value from fetch result. None if not available."""
        ...


class TimestampWatermark(WatermarkPolicy):
    """Uses source_updated_at or fetched_at as watermark."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.TIMESTAMP

    def extract(self, result: Any) -> str | None:
        ts = getattr(result, "source_updated_at", None) or getattr(result, "fetched_at", None)
        if ts is not None:
            return ts.isoformat()
        return None


class ETagWatermark(WatermarkPolicy):
    """Uses ETag from version info."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.ETAG

    def extract(self, result: Any) -> str | None:
        version = getattr(result, "version", None)
        if version is not None and getattr(version, "strategy", None) == VersionStrategy.ETAG:
            return version.value
        return None


class RevisionWatermark(WatermarkPolicy):
    """Uses revision number from version info."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.REVISION

    def extract(self, result: Any) -> str | None:
        version = getattr(result, "version", None)
        if version is not None and getattr(version, "strategy", None) == VersionStrategy.REVISION:
            return version.value
        return None


class OffsetWatermark(WatermarkPolicy):
    """Uses row count as offset watermark (for pagination-based incremental)."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.OFFSET

    def extract(self, result: Any) -> str | None:
        row_count = getattr(result, "row_count", None)
        if row_count is not None:
            return str(row_count)
        return None


class SchemaWatermark(WatermarkPolicy):
    """Uses schema identity as a watermark for CDC/schema-drift tracking."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.SCHEMA

    def extract(self, result: Any) -> str | None:
        schema_id = getattr(result, "schema_id", None)
        schema_version = getattr(result, "schema_version", None)
        if schema_id and schema_version:
            return f"{schema_id}:{schema_version}"
        return None


@dataclass(frozen=True)
class WindowPolicy:
    """Logical windowing policy for event-driven ingestion."""

    strategy: WindowStrategy = WindowStrategy.TUMBLING
    size: int | float = 1
    slide: int | float | None = None
    session_gap_seconds: float | None = None
    timestamp_field: str = "event_time"


@dataclass(frozen=True)
class WindowAssignment:
    """One concrete window produced from a row set."""

    window_id: str
    strategy: WindowStrategy
    row_count: int
    rows: tuple[dict[str, Any], ...]
    start_at: str | None = None
    end_at: str | None = None
    ordinal: int = 0


def assign_windows(
    rows: list[dict[str, Any]],
    policy: WindowPolicy,
) -> list[WindowAssignment]:
    """Assign rows to logical windows using time or count semantics."""
    if not rows:
        return []
    if policy.strategy == WindowStrategy.COUNT:
        return _count_windows(rows, size=max(1, int(policy.size)))
    if policy.strategy == WindowStrategy.SESSION:
        return _session_windows(rows, policy)
    if policy.strategy == WindowStrategy.SLIDING:
        timed = _rows_with_timestamps(rows, policy.timestamp_field)
        if timed:
            return _sliding_time_windows(timed, policy)
        return _sliding_count_windows(
            rows,
            size=max(1, int(policy.size)),
            slide=max(1, int(policy.slide or 1)),
        )

    timed = _rows_with_timestamps(rows, policy.timestamp_field)
    if timed:
        return _tumbling_time_windows(timed, policy)
    return _count_windows(rows, size=max(1, int(policy.size)))


# Default mapping: connector_family → watermark policy
DEFAULT_WATERMARK_POLICIES: dict[str, WatermarkPolicy] = {
    "sdmx": TimestampWatermark(),
    "worldbank": TimestampWatermark(),
    "eurostat": TimestampWatermark(),
    "ukons": TimestampWatermark(),
    "ckan": TimestampWatermark(),
    "socrata": TimestampWatermark(),
    "opendatasoft": TimestampWatermark(),
    "sparql": ETagWatermark(),
    "stream": OffsetWatermark(),
    "sql": RevisionWatermark(),
}


def resolve_watermark_policy(connector_family: str) -> WatermarkPolicy:
    """Resolve the default watermark policy for a connector family."""
    return DEFAULT_WATERMARK_POLICIES.get(connector_family, TimestampWatermark())


__all__ = [
    "DEFAULT_WATERMARK_POLICIES",
    "ETagWatermark",
    "OffsetWatermark",
    "RevisionWatermark",
    "SchemaWatermark",
    "TimestampWatermark",
    "WatermarkPolicy",
    "WindowAssignment",
    "WindowPolicy",
    "assign_windows",
    "resolve_watermark_policy",
]


def _rows_with_timestamps(
    rows: list[dict[str, Any]],
    timestamp_field: str,
) -> list[tuple[dict[str, Any], datetime]]:
    resolved: list[tuple[dict[str, Any], datetime]] = []
    for row in rows:
        value = (
            row.get(timestamp_field)
            or row.get("timestamp")
            or row.get("event_time")
            or row.get("observed_at")
        )
        if value is None:
            continue
        if isinstance(value, datetime):
            dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        else:
            dt = parse_datetime_utc(str(value), what="stream window timestamp")
        resolved.append((row, dt))
    resolved.sort(key=lambda item: item[1])
    return resolved


def _count_windows(rows: list[dict[str, Any]], *, size: int) -> list[WindowAssignment]:
    assignments: list[WindowAssignment] = []
    for ordinal, start in enumerate(range(0, len(rows), size)):
        batch = tuple(rows[start : start + size])
        assignments.append(
            WindowAssignment(
                window_id=f"count:{ordinal}",
                strategy=WindowStrategy.COUNT,
                row_count=len(batch),
                rows=batch,
                ordinal=ordinal,
            )
        )
    return assignments


def _sliding_count_windows(
    rows: list[dict[str, Any]],
    *,
    size: int,
    slide: int,
) -> list[WindowAssignment]:
    assignments: list[WindowAssignment] = []
    for ordinal, start in enumerate(range(0, len(rows), slide)):
        batch = tuple(rows[start : start + size])
        if not batch:
            break
        if len(batch) < size and start != 0:
            break
        assignments.append(
            WindowAssignment(
                window_id=f"sliding:{ordinal}",
                strategy=WindowStrategy.SLIDING,
                row_count=len(batch),
                rows=batch,
                ordinal=ordinal,
            )
        )
    return assignments


def _tumbling_time_windows(
    rows: list[tuple[dict[str, Any], datetime]],
    policy: WindowPolicy,
) -> list[WindowAssignment]:
    bucket_seconds = max(1, int(policy.size))
    by_bucket: dict[int, list[dict[str, Any]]] = {}
    for row, ts in rows:
        bucket = floor(ts.timestamp() / bucket_seconds)
        by_bucket.setdefault(bucket, []).append(row)

    assignments: list[WindowAssignment] = []
    for ordinal, bucket in enumerate(sorted(by_bucket)):
        start_dt = datetime.fromtimestamp(bucket * bucket_seconds, tz=UTC)
        end_dt = start_dt + timedelta(seconds=bucket_seconds)
        batch = tuple(by_bucket[bucket])
        assignments.append(
            WindowAssignment(
                window_id=f"tumbling:{bucket}",
                strategy=WindowStrategy.TUMBLING,
                row_count=len(batch),
                rows=batch,
                start_at=start_dt.isoformat(),
                end_at=end_dt.isoformat(),
                ordinal=ordinal,
            )
        )
    return assignments


def _sliding_time_windows(
    rows: list[tuple[dict[str, Any], datetime]],
    policy: WindowPolicy,
) -> list[WindowAssignment]:
    window_seconds = max(1, int(policy.size))
    slide_seconds = max(1, int(policy.slide or policy.size))
    first_ts = rows[0][1]
    last_ts = rows[-1][1]
    cursor = first_ts
    ordinal = 0
    assignments: list[WindowAssignment] = []
    while cursor <= last_ts:
        window_end = cursor + timedelta(seconds=window_seconds)
        batch = tuple(row for row, ts in rows if cursor <= ts < window_end)
        if batch:
            assignments.append(
                WindowAssignment(
                    window_id=f"sliding:{ordinal}",
                    strategy=WindowStrategy.SLIDING,
                    row_count=len(batch),
                    rows=batch,
                    start_at=cursor.isoformat(),
                    end_at=window_end.isoformat(),
                    ordinal=ordinal,
                )
            )
        cursor = cursor + timedelta(seconds=slide_seconds)
        ordinal += 1
    return assignments


def _session_windows(
    rows: list[dict[str, Any]],
    policy: WindowPolicy,
) -> list[WindowAssignment]:
    timed = _rows_with_timestamps(rows, policy.timestamp_field)
    if not timed:
        return [
            WindowAssignment(
                window_id="session:0",
                strategy=WindowStrategy.SESSION,
                row_count=len(rows),
                rows=tuple(rows),
                ordinal=0,
            )
        ]

    gap_seconds = float(policy.session_gap_seconds or policy.size or 0.0)
    if gap_seconds <= 0:
        gap_seconds = 60.0

    assignments: list[WindowAssignment] = []
    current_rows: list[dict[str, Any]] = []
    session_start = timed[0][1]
    previous_ts = session_start
    ordinal = 0

    for row, ts in timed:
        if current_rows and (ts - previous_ts).total_seconds() > gap_seconds:
            assignments.append(
                WindowAssignment(
                    window_id=f"session:{ordinal}",
                    strategy=WindowStrategy.SESSION,
                    row_count=len(current_rows),
                    rows=tuple(current_rows),
                    start_at=session_start.isoformat(),
                    end_at=previous_ts.isoformat(),
                    ordinal=ordinal,
                )
            )
            ordinal += 1
            current_rows = []
            session_start = ts
        current_rows.append(row)
        previous_ts = ts

    if current_rows:
        assignments.append(
            WindowAssignment(
                window_id=f"session:{ordinal}",
                strategy=WindowStrategy.SESSION,
                row_count=len(current_rows),
                rows=tuple(current_rows),
                start_at=session_start.isoformat(),
                end_at=previous_ts.isoformat(),
                ordinal=ordinal,
            )
        )
    return assignments
