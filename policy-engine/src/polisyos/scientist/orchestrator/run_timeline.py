from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Dict, List, Optional


class TimelineEventType(Enum):
    """
    Event types for the run timeline.

    Ordered by typical occurrence in a run lifecycle.
    """

    RUN_START = "run_start"
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    NODE_ENTER = "node_enter"
    NODE_EXIT = "node_exit"
    ARTIFACT_CREATED = "artifact_created"
    VALIDATION_PASS = "validation_pass"
    VALIDATION_FAIL = "validation_fail"
    HUMAN_GATE = "human_gate"
    REFLEXION = "reflexion"
    ERROR = "error"
    RUN_END = "run_end"


@dataclass(frozen=True)
class TimelineEvent:
    """
    Single event in the run timeline.

    Immutable after creation. All timestamps in UTC.
    """

    timestamp: datetime
    event_type: TimelineEventType
    phase: str
    node_id: Optional[str] = None
    artifact_ref: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[int] = None
    parent_event_idx: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "phase": self.phase,
            "node_id": self.node_id,
            "artifact_ref": self.artifact_ref,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "parent_event_idx": self.parent_event_idx,
        }


@dataclass
class RunTimeline:
    """
    Timeline artifact for observability ("flight recorder").

    Append-only, safe for concurrent appends via an internal lock.
    Designed to be serialized as a JSON artifact.
    """

    run_id: str
    events: List[TimelineEvent] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Tracking for phase transitions
    current_phase: Optional[str] = None

    # Index caches for fast lookups
    _phase_start_indices: Dict[str, int] = field(default_factory=dict, repr=False)
    _node_indices: Dict[str, List[int]] = field(default_factory=dict, repr=False)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record(
        self,
        event_type: TimelineEventType,
        phase: str,
        *,
        node_id: Optional[str] = None,
        artifact_ref: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        parent_event_idx: Optional[int] = None,
    ) -> int:
        """
        Record an event and return its index.

        Note: details must be JSON-serializable (best-effort; serialization is enforced at
        persistence time by json.dumps(..., default=str)).
        """
        with self._lock:
            event = TimelineEvent(
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                phase=phase,
                node_id=node_id,
                artifact_ref=artifact_ref,
                details=details or {},
                duration_ms=duration_ms,
                parent_event_idx=parent_event_idx,
            )
            idx = len(self.events)
            self.events.append(event)

            if event_type == TimelineEventType.PHASE_START:
                self._phase_start_indices[phase] = idx
            if node_id:
                self._node_indices.setdefault(node_id, []).append(idx)

            return idx

    def record_run_start(self) -> None:
        self.start_time = datetime.now(timezone.utc)
        self.current_phase = "INIT"
        self.record(TimelineEventType.RUN_START, phase="INIT")

    def record_run_end(self, *, success: bool = True) -> None:
        self.end_time = datetime.now(timezone.utc)
        self.record(TimelineEventType.RUN_END, phase="COMPLETE", details={"success": success})
        self.current_phase = "COMPLETE"

    def transition_phase(self, new_phase: str) -> None:
        """
        Transition the timeline's current phase.

        We close the previous phase (if any) and open the new phase.
        """
        with self._lock:
            if self.current_phase == new_phase:
                return
            if self.current_phase:
                self._close_phase_if_open(self.current_phase)
            self.current_phase = new_phase
            self.record(TimelineEventType.PHASE_START, phase=new_phase)

    def _close_phase_if_open(self, phase: str) -> None:
        """
        Close a phase by recording PHASE_END with duration.

        Safe to call multiple times; if no start is known we record duration_ms=0.
        """
        start_ts: Optional[datetime] = None
        start_idx = self._phase_start_indices.get(phase)
        if start_idx is not None:
            try:
                start_ts = self.events[start_idx].timestamp
            except Exception:
                start_ts = None

        duration_ms = 0
        if start_ts is not None:
            now = datetime.now(timezone.utc)
            duration_ms = int((now - start_ts).total_seconds() * 1000)

        self.record(TimelineEventType.PHASE_END, phase=phase, duration_ms=duration_ms)

    def get_phase_duration(self, phase: str) -> int:
        start: Optional[datetime] = None
        end: Optional[datetime] = None
        for event in self.events:
            if event.phase != phase:
                continue
            if event.event_type == TimelineEventType.PHASE_START:
                start = event.timestamp
            elif event.event_type == TimelineEventType.PHASE_END:
                end = event.timestamp
        if start and end:
            return int((end - start).total_seconds() * 1000)
        return 0

    def get_node_durations(self) -> Dict[str, int]:
        durations: Dict[str, int] = {}
        node_starts: Dict[str, datetime] = {}

        for event in self.events:
            if not event.node_id:
                continue
            if event.event_type == TimelineEventType.NODE_ENTER:
                node_starts[event.node_id] = event.timestamp
            elif event.event_type == TimelineEventType.NODE_EXIT:
                started = node_starts.pop(event.node_id, None)
                if started:
                    delta = (event.timestamp - started).total_seconds()
                    durations[event.node_id] = durations.get(event.node_id, 0) + int(delta * 1000)

        return durations

    def get_errors(self) -> List[TimelineEvent]:
        return [e for e in self.events if e.event_type == TimelineEventType.ERROR]

    def get_artifacts(self) -> List[str]:
        return [
            e.artifact_ref
            for e in self.events
            if e.event_type == TimelineEventType.ARTIFACT_CREATED and e.artifact_ref
        ]

    def get_validation_summary(self) -> Dict[str, int]:
        passes = sum(1 for e in self.events if e.event_type == TimelineEventType.VALIDATION_PASS)
        failures = sum(1 for e in self.events if e.event_type == TimelineEventType.VALIDATION_FAIL)
        return {"passes": passes, "failures": failures}

    @property
    def total_duration_ms(self) -> int:
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return 0

    def to_artifact(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "event_count": len(self.events),
            "events": [e.to_dict() for e in self.events],
            "summary": {
                "node_durations": self.get_node_durations(),
                "validation": self.get_validation_summary(),
                "error_count": len(self.get_errors()),
                "artifact_count": len(self.get_artifacts()),
            },
        }

    def to_trace_records(self) -> List["TraceRecord"]:
        """
        Convert timeline events to core TraceRecords for unified export.

        Import is inside to avoid coupling in hot paths.
        """
        from polisyos.core.trace import TraceRecord

        records: List[TraceRecord] = []
        for event in self.events:
            records.append(
                TraceRecord(
                    ts=event.timestamp,
                    run_id=self.run_id,
                    phase=event.phase,
                    event=event.event_type.value,
                    span_id=f"timeline_{self.run_id}_{event.node_id or 'global'}",
                    metrics={"duration_ms": event.duration_ms or 0},
                    warnings=[],
                )
            )
        return records

    @classmethod
    def from_artifact(cls, data: Dict[str, Any]) -> "RunTimeline":
        timeline = cls(run_id=data["run_id"])

        if data.get("start_time"):
            timeline.start_time = datetime.fromisoformat(data["start_time"])
        if data.get("end_time"):
            timeline.end_time = datetime.fromisoformat(data["end_time"])

        for event_data in data.get("events", []):
            timeline.events.append(
                TimelineEvent(
                    timestamp=datetime.fromisoformat(event_data["timestamp"]),
                    event_type=TimelineEventType(event_data["event_type"]),
                    phase=event_data["phase"],
                    node_id=event_data.get("node_id"),
                    artifact_ref=event_data.get("artifact_ref"),
                    details=event_data.get("details", {}),
                    duration_ms=event_data.get("duration_ms"),
                    parent_event_idx=event_data.get("parent_event_idx"),
                )
            )

        # Rebuild indices best-effort.
        for idx, event in enumerate(timeline.events):
            if event.event_type == TimelineEventType.PHASE_START:
                timeline._phase_start_indices[event.phase] = idx
            if event.node_id:
                timeline._node_indices.setdefault(event.node_id, []).append(idx)

        # Infer current phase: last phase_start without later phase_end.
        timeline.current_phase = None
        open_phase = None
        for event in timeline.events:
            if event.event_type == TimelineEventType.PHASE_START:
                open_phase = event.phase
            elif event.event_type == TimelineEventType.PHASE_END and open_phase == event.phase:
                open_phase = None
        timeline.current_phase = open_phase

        return timeline

