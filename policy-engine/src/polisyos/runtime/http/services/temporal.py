"""Temporal scope adapter for runtime bitemporal API surfaces."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.core.contracts.runtime import (
    QuantityCoverageEntry,
    QuantityCoverageSummary,
    QuantityValue,
    RunDetails,
    RunTimelineEvent,
    RunTimelineSummary,
    RunTimelineView,
    TemporalCapabilitiesView,
    TemporalEventPoint,
    TemporalIndexEvidence,
    TemporalRange,
    TemporalScope,
    TemporalSurfaceCapability,
    TemporalSurfaceSupport,
)
from polisyos.runtime.http.errors import RuntimeHTTPError, conflict, unprocessable_entity

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.runtime.http.services.run_index import IndexedRunRecord
    from polisyos.runtime.http.services.timeline import TimelineService


_SUPPORTED_SURFACES: tuple[TemporalSurfaceSupport, ...] = (
    "run_details",
    "run_timeline",
    "run_lineage",
    "run_quantities",
    "run_fabric_decision_data",
    "run_compare",
)
_UNSUPPORTED_SURFACES: tuple[TemporalSurfaceSupport, ...] = (
    "run_agents",
    "run_evidence_context",
    "run_workflow",
    "run_nodes",
    "artifact_content",
)
_WORLD_TEMPORAL_TABLES: tuple[str, ...] = (
    "world.world_facts",
    "world.world_edges",
    "world.world_nodes",
    "world.quality_reports",
    "world.trust_assessments",
)


class TemporalService:
    """Resolve, validate, and describe runtime temporal cursor state."""

    def __init__(self, *, timeline_service: TimelineService | None = None) -> None:
        self._timeline_service = timeline_service

    def resolve_scope(
        self,
        *,
        valid_at: datetime | None = None,
        tx_at: datetime | None = None,
        t: datetime | None = None,
        branch: str | None = None,
        snapshot_id: str | None = None,
        scenario_id: str | None = None,
    ) -> TemporalScope | None:
        """Normalize canonical params and the `?t=` shorthand into one scope."""
        normalized_t = _normalize_datetime(t, field_name="t")
        normalized_valid_at = _normalize_datetime(valid_at, field_name="valid_at")
        normalized_tx_at = _normalize_datetime(tx_at, field_name="tx_at")
        if normalized_t is not None:
            if normalized_valid_at is not None and normalized_valid_at != normalized_t:
                raise unprocessable_entity(
                    "valid_at and shorthand t specify different instants",
                    code="temporal_scope_conflict",
                )
            normalized_valid_at = normalized_t

        normalized_branch = _strip_optional(branch)
        normalized_snapshot = _strip_optional(snapshot_id)
        normalized_scenario = _strip_optional(scenario_id)
        if not any(
            (
                normalized_valid_at,
                normalized_tx_at,
                normalized_branch,
                normalized_snapshot,
                normalized_scenario,
            )
        ):
            return None
        return TemporalScope(
            valid_at=normalized_valid_at,
            tx_at=normalized_tx_at,
            branch=normalized_branch,
            snapshot_id=normalized_snapshot,
            scenario_id=normalized_scenario,
        )

    def materialize_run_scope(
        self,
        run: IndexedRunRecord,
        scope: TemporalScope | None,
    ) -> TemporalScope | None:
        """Fill default valid/transaction time for an explicit temporal request."""
        if scope is None:
            return None
        capabilities = self.build_capabilities(run=run, active_scope=scope)
        return TemporalScope(
            valid_at=scope.valid_at or capabilities.valid_range.latest,
            tx_at=scope.tx_at or capabilities.tx_range.latest,
            branch=scope.branch,
            snapshot_id=scope.snapshot_id,
            scenario_id=scope.scenario_id,
        )

    def validate_run_scope(
        self,
        run: IndexedRunRecord,
        scope: TemporalScope | None,
        *,
        surface: TemporalSurfaceSupport,
    ) -> None:
        """Reject unsupported surfaces and out-of-range bitemporal cursors."""
        if scope is None:
            return
        if surface not in _SUPPORTED_SURFACES:
            raise conflict(
                f"Temporal scope is not supported by {surface}",
                code="temporal_surface_unsupported",
            )
        capabilities = self.build_capabilities(run=run, active_scope=scope)
        valid_range = capabilities.valid_range
        tx_range = capabilities.tx_range
        violations: dict[str, Any] = {}
        if scope.valid_at is not None and not _contains(valid_range, scope.valid_at):
            violations["valid_at"] = scope.valid_at
        if scope.tx_at is not None and not _contains(tx_range, scope.tx_at):
            violations["tx_at"] = scope.tx_at
        if violations:
            raise _temporal_range_error(
                scope=scope,
                capabilities=capabilities,
                violations=violations,
            )

    def project_run_details(
        self,
        details: RunDetails,
        scope: TemporalScope | None,
    ) -> RunDetails:
        """Return the run detail state visible at the committed temporal cursor."""
        if scope is None:
            return details
        cutoff = _scope_cutoff(scope)
        started_at = _normalize_optional_datetime(details.started_at)
        finished_at = _normalize_optional_datetime(details.finished_at)
        if cutoff is None or started_at is None or finished_at is None:
            return details
        if cutoff >= finished_at:
            return details

        duration_ms = int(max((cutoff - started_at).total_seconds() * 1000, 0))
        return details.model_copy(
            update={
                "status": "running",
                "finished_at": None,
                "duration_ms": duration_ms,
                "has_workflow_report": False,
                "workflow_report_ref": None,
                "decision_validity_status": None,
                "decision_validity_checked_at": None,
                "decision_review_required": False,
                "decision_superseded_by_ref": None,
            }
        )

    def project_timeline(
        self,
        timeline: RunTimelineView,
        scope: TemporalScope | None,
    ) -> RunTimelineView:
        """Filter timeline events to facts visible at the temporal cursor."""
        if scope is None:
            return timeline
        events = [event for event in timeline.events if _event_visible(event, scope)]
        if len(events) == len(timeline.events):
            return timeline
        notes = list(timeline.notes)
        if "temporal_scope_applied" not in notes:
            notes.append("temporal_scope_applied")
        return RunTimelineView(
            run_id=timeline.run_id,
            source_kind=timeline.source_kind,
            summary=_timeline_summary(timeline.summary.run_id, events),
            events=events,
            notes=notes,
        )

    def project_quantities(
        self,
        quantities: list[QuantityValue],
        entries: list[QuantityCoverageEntry],
        scope: TemporalScope | None,
    ) -> tuple[list[QuantityValue], QuantityCoverageSummary, list[QuantityCoverageEntry]]:
        """Filter quantity inventory to values known at the temporal cursor."""
        if scope is None:
            return quantities, _coverage_summary(entries), entries
        visible_pairs = [
            (quantity, entry)
            for quantity, entry in zip(quantities, entries, strict=False)
            if _quantity_visible(quantity, scope)
        ]
        visible_quantities = [quantity for quantity, _entry in visible_pairs]
        visible_entries = [entry for _quantity, entry in visible_pairs]
        return visible_quantities, _coverage_summary(visible_entries), visible_entries

    def build_capabilities(
        self,
        *,
        run: IndexedRunRecord | None = None,
        active_scope: TemporalScope | None = None,
    ) -> TemporalCapabilitiesView:
        """Return supported temporal surfaces, ranges, and event points."""
        event_points = _dedupe_event_points(self._event_points_for_run(run))
        valid_range = _range_from_events(
            event_points,
            fallback_start=getattr(getattr(run, "details", None), "started_at", None),
            fallback_end=getattr(getattr(run, "details", None), "finished_at", None),
        )
        tx_range = _range_from_events(
            event_points,
            fallback_start=getattr(getattr(run, "details", None), "started_at", None),
            fallback_end=datetime.now(UTC),
        )
        default_scope = active_scope or _default_scope(valid_range=valid_range, tx_range=tx_range)
        nearest = _nearest_event_points(event_points, default_scope.valid_at or valid_range.latest)

        surfaces = [
            TemporalSurfaceCapability(
                surface=surface,
                supported=True,
                resolution="event",
                valid_range=valid_range,
                tx_range=tx_range,
                nearest_event_points=nearest,
            )
            for surface in _SUPPORTED_SURFACES
        ]
        surfaces.extend(
            TemporalSurfaceCapability(
                surface=surface,
                supported=False,
                resolution="unsupported",
                reason_code="temporal_surface_unsupported",
                valid_range=valid_range,
                tx_range=tx_range,
                nearest_event_points=nearest,
            )
            for surface in _UNSUPPORTED_SURFACES
        )
        return TemporalCapabilitiesView(
            run_id=getattr(run, "run_id", None),
            default_scope=default_scope,
            valid_range=valid_range,
            tx_range=tx_range,
            resolution="event",
            surfaces=surfaces,
            event_points=event_points,
            nearest_event_points=nearest,
            supported_tables=list(_WORLD_TEMPORAL_TABLES),
            unsupported_surfaces=list(_UNSUPPORTED_SURFACES),
            branch_support=True,
            snapshot_support=True,
            scenario_branch_support="explicit_only",
            graph_temporal_scope="partial",
            slow_query_evidence=_temporal_index_evidence(),
        )

    def world_query_kwargs(
        self,
        scope: TemporalScope | None,
        *,
        snapshot_root: str | None = None,
    ) -> dict[str, Any]:
        """Map runtime TemporalScope onto Fabric `world_query` bitemporal kwargs."""
        if scope is None:
            return {}
        payload: dict[str, Any] = {}
        if scope.valid_at is not None:
            payload["as_of_valid_time"] = scope.valid_at.isoformat()
        if scope.tx_at is not None:
            payload["as_of_tx_time"] = scope.tx_at.isoformat()
        if scope.branch:
            payload["branch"] = scope.branch
        if scope.snapshot_id:
            payload["snapshot_id"] = scope.snapshot_id
        if snapshot_root:
            payload["snapshot_root"] = snapshot_root
        return payload

    def response_etag(self, *, run_id: str, surface: str, scope: TemporalScope | None) -> str:
        """Build a stable weak ETag fragment that includes the full temporal scope."""
        payload = {
            "run_id": run_id,
            "surface": surface,
            "scope": scope.model_dump(mode="json") if scope is not None else "current",
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return f'W/"temporal-{digest[:24]}"'

    def response_header_value(self, scope: TemporalScope | None) -> str:
        if scope is None:
            return "current"
        return json.dumps(scope.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def _event_points_for_run(self, run: IndexedRunRecord | None) -> list[TemporalEventPoint]:
        if run is None:
            now = datetime.now(UTC).replace(microsecond=0)
            return [TemporalEventPoint(id="now", timestamp=now, kind="now", label="Now")]
        points: list[TemporalEventPoint] = []
        started_at = _normalize_datetime(run.details.started_at, field_name="started_at")
        finished_at = _normalize_datetime(run.details.finished_at, field_name="finished_at")
        if started_at is not None:
            points.append(
                TemporalEventPoint(
                    id=f"{run.run_id}:start",
                    timestamp=started_at,
                    kind="run_start",
                    label="Run started",
                    valid_at=started_at,
                    tx_at=started_at,
                )
            )
        if self._timeline_service is not None:
            for event in self._timeline_service.build_for_run(run).timeline.events[:200]:
                timestamp = _normalize_datetime(event.timestamp, field_name="timeline.timestamp")
                if timestamp is None:
                    continue
                points.append(
                    TemporalEventPoint(
                        id=f"{run.run_id}:trace:{event.index}",
                        timestamp=timestamp,
                        kind=_event_kind(event.event),
                        label=f"{event.phase}.{event.event}",
                        valid_at=timestamp,
                        tx_at=timestamp,
                    )
                )
        if finished_at is not None:
            points.append(
                TemporalEventPoint(
                    id=f"{run.run_id}:finish",
                    timestamp=finished_at,
                    kind="run_finish",
                    label="Run finished",
                    valid_at=finished_at,
                    tx_at=finished_at,
                )
            )
        if not points:
            now = datetime.now(UTC).replace(microsecond=0)
            points.append(
                TemporalEventPoint(
                    id=f"{run.run_id}:now",
                    timestamp=now,
                    kind="now",
                    label="Current runtime state",
                    valid_at=now,
                    tx_at=now,
                )
            )
        return points


def _temporal_range_error(
    *,
    scope: TemporalScope,
    capabilities: TemporalCapabilitiesView,
    violations: dict[str, Any],
) -> RuntimeHTTPError:
    extensions = {
        "temporal_scope": scope.model_dump(mode="json"),
        "valid_range": capabilities.valid_range.model_dump(mode="json"),
        "tx_range": capabilities.tx_range.model_dump(mode="json"),
        "nearest_event_points": [
            point.model_dump(mode="json")
            for point in _nearest_event_points(
                capabilities.event_points,
                scope.valid_at or capabilities.valid_range.latest,
                limit=5,
            )
        ],
        "violations": {
            key: value.isoformat() if isinstance(value, datetime) else str(value)
            for key, value in violations.items()
        },
    }
    error = unprocessable_entity(
        "Temporal scope is outside the usable range for this run",
        code="temporal_scope_out_of_range",
    )
    return RuntimeHTTPError(
        status_code=error.status_code,
        error=error.error,
        detail=error.detail,
        code=error.code,
        extensions=extensions,
    )


def _default_scope(*, valid_range: TemporalRange, tx_range: TemporalRange) -> TemporalScope:
    return TemporalScope(valid_at=valid_range.latest, tx_at=tx_range.latest)


def _normalize_datetime(value: datetime | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise unprocessable_entity(
            f"{field_name} must be an RFC 3339 timestamp with timezone",
            code="temporal_timestamp_timezone_required",
        )
    return value.astimezone(UTC)


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _contains(window: TemporalRange, value: datetime) -> bool:
    if window.earliest is not None and value < window.earliest:
        return False
    return not (window.latest is not None and value > window.latest)


def _range_from_events(
    events: list[TemporalEventPoint],
    *,
    fallback_start: datetime | None,
    fallback_end: datetime | None,
) -> TemporalRange:
    timestamps = [event.timestamp for event in events]
    start = _normalize_datetime(fallback_start, field_name="range.start")
    end = _normalize_datetime(fallback_end, field_name="range.end")
    if timestamps:
        start = min(timestamps + ([start] if start is not None else []))
        end = max(timestamps + ([end] if end is not None else []))
    now = datetime.now(UTC).replace(microsecond=0)
    return TemporalRange(earliest=start or now, latest=end or start or now)


def _nearest_event_points(
    points: Iterable[TemporalEventPoint],
    target: datetime | None,
    *,
    limit: int = 8,
) -> list[TemporalEventPoint]:
    staged = list(points)
    if target is None:
        return staged[:limit]
    return sorted(staged, key=lambda point: abs((point.timestamp - target).total_seconds()))[:limit]


def _temporal_index_evidence() -> list[TemporalIndexEvidence]:
    return [
        TemporalIndexEvidence(
            table="world.world_facts",
            index_name="idx_world_facts_tx_valid",
            columns=["tx_time", "valid_time"],
            slow_query_gate_ms=500,
            evidence_ref="src/polisyos/fabric/world/ddl/duckdb_world.sql",
        ),
        TemporalIndexEvidence(
            table="world.world_facts",
            index_name="idx_world_facts_valid_tx",
            columns=["valid_time", "tx_time"],
            slow_query_gate_ms=500,
            evidence_ref="src/polisyos/fabric/world/ddl/duckdb_world.sql",
        ),
        TemporalIndexEvidence(
            table="world.world_edges",
            index_name="idx_world_edges_tx_valid",
            columns=["tx_time", "valid_time"],
            slow_query_gate_ms=500,
            evidence_ref="src/polisyos/fabric/world/ddl/duckdb_world.sql",
        ),
        TemporalIndexEvidence(
            table="world.world_edges",
            index_name="idx_world_edges_valid_tx",
            columns=["valid_time", "tx_time"],
            slow_query_gate_ms=500,
            evidence_ref="src/polisyos/fabric/world/ddl/duckdb_world.sql",
        ),
    ]


def _dedupe_event_points(points: list[TemporalEventPoint]) -> list[TemporalEventPoint]:
    seen: set[str] = set()
    deduped: list[TemporalEventPoint] = []
    for point in sorted(points, key=lambda item: (item.timestamp, item.id)):
        if point.id in seen:
            continue
        seen.add(point.id)
        deduped.append(point)
    return deduped


def _event_kind(event_name: str) -> str:
    normalized = event_name.lower()
    if "correction" in normalized or "corrected" in normalized:
        return "correction"
    if "late" in normalized or "evidence" in normalized:
        return "late_evidence"
    if "policy" in normalized:
        return "policy_change"
    return "trace_event"


def _scope_cutoff(scope: TemporalScope) -> datetime | None:
    instants = [instant for instant in (scope.valid_at, scope.tx_at) if instant is not None]
    if not instants:
        return None
    return min(instants)


def _event_visible(event: RunTimelineEvent, scope: TemporalScope) -> bool:
    timestamp = _normalize_optional_datetime(event.timestamp)
    if timestamp is None:
        return True
    if scope.valid_at is not None and timestamp > scope.valid_at:
        return False
    return not (scope.tx_at is not None and timestamp > scope.tx_at)


def _quantity_visible(quantity: QuantityValue, scope: TemporalScope) -> bool:
    if quantity.time is None:
        return True
    valid_at = _normalize_optional_datetime(quantity.time.valid_at)
    tx_at = _normalize_optional_datetime(quantity.time.tx_at)
    if scope.valid_at is not None and valid_at is not None and valid_at > scope.valid_at:
        return False
    return not (scope.tx_at is not None and tx_at is not None and tx_at > scope.tx_at)


def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _timeline_summary(
    run_id: str,
    events: list[RunTimelineEvent],
) -> RunTimelineSummary:
    if not events:
        return RunTimelineSummary(run_id=run_id, duration_ms=0)

    phase_counts: dict[str, int] = {}
    node_status_counts: dict[str, int] = {"ok": 0, "skip": 0, "fail": 0}
    cache_hits = 0
    cache_stores = 0
    cache_bypasses = 0
    first_ts = events[0].timestamp
    last_ts = events[0].timestamp
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

    return RunTimelineSummary(
        run_id=run_id,
        total_events=len(events),
        duration_ms=int(max((last_ts - first_ts).total_seconds() * 1000, 0)),
        node_status_counts=node_status_counts,
        phase_counts=phase_counts,
        cache_hits=cache_hits,
        cache_stores=cache_stores,
        cache_bypasses=cache_bypasses,
    )


def _coverage_summary(entries: list[QuantityCoverageEntry]) -> QuantityCoverageSummary:
    return QuantityCoverageSummary(
        total=len(entries),
        decision=sum(entry.quantity_class == "decision" for entry in entries),
        telemetry=sum(entry.quantity_class == "telemetry" for entry in entries),
        layout=sum(entry.quantity_class == "layout" for entry in entries),
        debug=sum(entry.quantity_class == "debug" for entry in entries),
        traced=sum(entry.status != "untraced" for entry in entries),
        untraced=sum(entry.status == "untraced" for entry in entries),
    )


__all__ = ["TemporalService"]
