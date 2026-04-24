"""Transform persisted trace JSONL into stable timeline API responses."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.contracts.runtime import (
    RunTimelineEvent,
    RunTimelineSummary,
    RunTimelineView,
)
from polisyos.core.trace.record import TraceRecord

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from .run_index import IndexedRunRecord

logger = get_logger(__name__)


@dataclass(frozen=True)
class TimelineBuildResult:
    """Wrap the run timeline projection returned by `TimelineService`."""

    timeline: RunTimelineView


@dataclass(frozen=True)
class _TimelineCacheKey:
    """File identity used to avoid rescanning unchanged JSONL traces."""

    path: Path
    mtime_ns: int
    size: int


@dataclass(frozen=True)
class _TimelineCacheEntry:
    """Cached timeline projection for one stable trace file version."""

    result: TimelineBuildResult
    built_at: float


class TimelineService:
    """Read trace JSONL files and summarize node/event timing for one run."""

    def __init__(
        self,
        *,
        cache_max_entries: int = 128,
        metrics: Any | None = None,
    ) -> None:
        self._cache_max_entries = max(int(cache_max_entries), 1)
        self._metrics = metrics
        self._cache: OrderedDict[_TimelineCacheKey, _TimelineCacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def build_for_run(self, run: IndexedRunRecord) -> TimelineBuildResult:
        """Build a chronological timeline view for one indexed run.

        Missing trace files are not treated as hard failures; the method returns
        an empty timeline with a diagnostic note so callers can render partial
        run state.
        """
        if run.trace_path is None or not run.trace_path.exists():
            timeline = RunTimelineView(
                run_id=run.run_id,
                source_kind=run.source_kind,
                summary=RunTimelineSummary(run_id=run.run_id),
                events=[],
                notes=["trace_not_available_for_run_source"],
            )
            return TimelineBuildResult(timeline=timeline)

        cache_key = _timeline_cache_key(run.trace_path)
        if cache_key is None:
            timeline = RunTimelineView(
                run_id=run.run_id,
                source_kind=run.source_kind,
                summary=RunTimelineSummary(run_id=run.run_id),
                events=[],
                notes=["trace_not_available_for_run_source"],
            )
            return TimelineBuildResult(timeline=timeline)

        cached = self._get_cached_timeline(cache_key)
        if cached is not None:
            self._record_cache_event(operation="build", outcome="cache_hit")
            return cached

        self._record_cache_event(operation="build", outcome="cache_miss")
        events = _load_trace_events(run.trace_path)
        summary = _summarize_timeline(
            run.run_id,
            events,
            fallback_duration_ms=run.details.duration_ms,
        )
        timeline = RunTimelineView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            summary=summary,
            events=events,
            notes=[],
        )
        result = TimelineBuildResult(timeline=timeline)
        self._put_cached_timeline(cache_key, result)
        return result

    def _get_cached_timeline(self, key: _TimelineCacheKey) -> TimelineBuildResult | None:
        with self._lock:
            cached = self._cache.get(key)
            if cached is None:
                return None
            self._cache.move_to_end(key)
            self._record_cache_staleness(time.monotonic() - cached.built_at)
            return cached.result

    def _put_cached_timeline(self, key: _TimelineCacheKey, result: TimelineBuildResult) -> None:
        with self._lock:
            self._cache[key] = _TimelineCacheEntry(result=result, built_at=time.monotonic())
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_max_entries:
                self._cache.popitem(last=False)
                self._record_cache_event(operation="evict", outcome="capacity")
            self._record_cache_rebuild(item_count=len(self._cache))

    def _record_cache_event(self, *, operation: str, outcome: str) -> None:
        recorder = getattr(self._metrics, "record_runtime_cache_event", None)
        if callable(recorder):
            recorder(cache_name="timeline_index", operation=operation, outcome=outcome)

    def _record_cache_rebuild(self, *, item_count: int) -> None:
        recorder = getattr(self._metrics, "record_runtime_cache_rebuild", None)
        if callable(recorder):
            recorder(cache_name="timeline_index", duration_seconds=0.0, item_count=item_count)

    def _record_cache_staleness(self, staleness_seconds: float) -> None:
        recorder = getattr(self._metrics, "set_runtime_cache_staleness", None)
        if callable(recorder):
            recorder(cache_name="timeline_index", staleness_seconds=staleness_seconds)


def _timeline_cache_key(path: Path) -> _TimelineCacheKey | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return _TimelineCacheKey(
        path=path.resolve(),
        mtime_ns=int(stat.st_mtime_ns),
        size=int(stat.st_size),
    )


def _load_trace_events(path: Path) -> list[RunTimelineEvent]:
    staged: list[tuple[datetime, int, RunTimelineEvent]] = []
    with path.open("r", encoding="utf-8") as handle:
        for file_idx, line in enumerate(handle):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = TraceRecord.model_validate_json(stripped)
            except (TypeError, ValueError) as exc:
                logger.debug("Skipping invalid trace event in %s: %s", path, exc)
                continue

            metrics: dict[str, int | float] = {}
            for key, value in record.metrics.items():
                if isinstance(value, bool):
                    metrics[key] = int(value)
                elif isinstance(value, (int, float)):
                    metrics[key] = value

            staged.append(
                (
                    record.ts,
                    file_idx,
                    RunTimelineEvent(
                        index=file_idx,
                        timestamp=record.ts,
                        phase=record.phase,
                        event=record.event,
                        span_id=record.span_id,
                        parent_span_id=record.parent_span_id,
                        input_artifact_ids=[str(ref.artifact_id) for ref in record.refs.inputs],
                        output_artifact_ids=[str(ref.artifact_id) for ref in record.refs.outputs],
                        metrics=metrics,
                        warning_count=len(record.warnings),
                        error_count=len(record.errors),
                    ),
                )
            )
    staged.sort(key=lambda item: (item[0], item[1]))

    events: list[RunTimelineEvent] = []
    for idx, (_, _, event) in enumerate(staged):
        events.append(event.model_copy(update={"index": idx}))
    return events


def _summarize_timeline(
    run_id: str,
    events: list[RunTimelineEvent],
    *,
    fallback_duration_ms: int | None,
) -> RunTimelineSummary:
    if not events:
        return RunTimelineSummary(run_id=run_id, duration_ms=fallback_duration_ms)

    phase_counts: dict[str, int] = {}
    node_status_counts: dict[str, int] = {"ok": 0, "skip": 0, "fail": 0}
    cache_hits = 0
    cache_stores = 0
    cache_bypasses = 0

    first_ts: datetime = events[0].timestamp
    last_ts: datetime = events[0].timestamp
    for event in events:
        phase_counts[event.phase] = phase_counts.get(event.phase, 0) + 1
        first_ts = event.timestamp if event.timestamp < first_ts else first_ts
        last_ts = event.timestamp if event.timestamp > last_ts else last_ts

        if event.event == "NODE_OK":
            node_status_counts["ok"] = node_status_counts.get("ok", 0) + 1
        elif event.event == "NODE_SKIP":
            node_status_counts["skip"] = node_status_counts.get("skip", 0) + 1
        elif event.event == "NODE_FAIL":
            node_status_counts["fail"] = node_status_counts.get("fail", 0) + 1

        cache_hits += int(event.metrics.get("cache_hit", 0))
        cache_stores += int(event.metrics.get("cache_store", 0))
        cache_bypasses += int(event.metrics.get("cache_bypass", 0))

    duration_ms = int(max((last_ts - first_ts).total_seconds() * 1000, 0))
    if duration_ms == 0 and fallback_duration_ms is not None:
        duration_ms = fallback_duration_ms

    return RunTimelineSummary(
        run_id=run_id,
        total_events=len(events),
        duration_ms=duration_ms,
        node_status_counts=node_status_counts,
        phase_counts=phase_counts,
        cache_hits=cache_hits,
        cache_stores=cache_stores,
        cache_bypasses=cache_bypasses,
    )
