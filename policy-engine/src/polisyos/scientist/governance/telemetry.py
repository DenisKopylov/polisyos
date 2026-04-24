"""Public governance telemetry module API."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from polisyos.core.canon import truncated_hash
from polisyos.core.trace import TraceRecord


@dataclass
class PassSpan:
    """
    Telemetry span for a single validation pass execution.

    Captures timing, issue counts, and input fingerprint for
    debugging and performance analysis.
    """

    pass_id: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: int | None = None
    inputs_hash: str | None = None
    issue_count: int = 0
    blocker_count: int = 0
    warning_count: int = 0
    skipped: bool = False
    error: str | None = None

    def close(self) -> None:
        """Close the span and calculate duration."""
        self.end_time = datetime.now(UTC)
        if self.start_time:
            delta = (self.end_time - self.start_time).total_seconds()
            self.duration_ms = int(delta * 1000)

    def set_inputs_hash(self, ir_payload: dict) -> None:
        """Compute and set hash of inputs for reproducibility."""
        content = json.dumps(ir_payload, sort_keys=True, default=str)
        self.inputs_hash = truncated_hash(content, length=16)


@dataclass
class ValidationTrace:
    """
    Complete trace of a validation pipeline execution.

    Integrates with core.trace.TraceRecord for unified observability.
    """

    run_id: str
    profile: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    spans: list[PassSpan] = field(default_factory=list)
    total_issues: int = 0
    total_blockers: int = 0
    short_circuited: bool = False

    def add_span(self, span: PassSpan) -> None:
        """Add a completed pass span to the trace."""
        self.spans.append(span)
        self.total_issues += span.issue_count
        self.total_blockers += span.blocker_count

    def complete(self, short_circuited: bool = False) -> None:
        """Mark the trace as complete."""
        self.completed_at = datetime.now(UTC)
        self.short_circuited = short_circuited

    @property
    def total_duration_ms(self) -> int:
        """Total duration of all pass executions."""
        return sum(span.duration_ms or 0 for span in self.spans)

    def to_trace_record(self) -> TraceRecord:
        """
        Convert to core TraceRecord for unified persistence.
        """

        profile_code = {
            "fast": 1,
            "mvp": 2,
            "strict": 3,
        }.get(self.profile, 0)

        warnings = [{"code": "VALIDATION_PROFILE", "msg": self.profile}]
        warnings.extend(
            {
                "code": "VALIDATION_ISSUE",
                "msg": f"{span.pass_id}: {span.issue_count} issues",
            }
            for span in self.spans
            if span.issue_count > 0
        )

        return TraceRecord(
            ts=self.started_at,
            run_id=self.run_id,
            phase="governance_validation",
            event="validation_complete",
            span_id=f"gov_validation_{self.run_id}",
            metrics={
                "profile_code": profile_code,
                "total_duration_ms": self.total_duration_ms,
                "pass_count": len(self.spans),
                "total_issues": self.total_issues,
                "total_blockers": self.total_blockers,
                "short_circuited": self.short_circuited,
            },
            warnings=warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage in experiment state."""
        return {
            "run_id": self.run_id,
            "profile": self.profile,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_ms": self.total_duration_ms,
            "total_issues": self.total_issues,
            "total_blockers": self.total_blockers,
            "short_circuited": self.short_circuited,
            "spans": [
                {
                    "pass_id": span.pass_id,
                    "duration_ms": span.duration_ms,
                    "issue_count": span.issue_count,
                    "blocker_count": span.blocker_count,
                    "inputs_hash": span.inputs_hash,
                }
                for span in self.spans
            ],
        }
