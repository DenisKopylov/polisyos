from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from polisyos.common.logger import get_logger
from polisyos.core.contracts.runtime import (
    RunTimelineEvent,
    RunTimelineSummary,
    RunTimelineView,
)
from polisyos.core.trace.record import TraceRecord

from .run_index import IndexedRunRecord

logger = get_logger(__name__)


@dataclass(frozen=True)
class TimelineBuildResult:
    timeline: RunTimelineView


class TimelineService:
    def build_for_run(self, run: IndexedRunRecord) -> TimelineBuildResult:
        if run.trace_path is None or not run.trace_path.exists():
            timeline = RunTimelineView(
                run_id=run.run_id,
                source_kind=run.source_kind,
                summary=RunTimelineSummary(run_id=run.run_id),
                events=[],
                notes=["trace_not_available_for_run_source"],
            )
            return TimelineBuildResult(timeline=timeline)

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
        return TimelineBuildResult(timeline=timeline)


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
