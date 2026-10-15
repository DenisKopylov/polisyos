"""Trace-record schema used to persist run events, refs, metrics, warnings, and errors."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..artifacts.manifest import ArtifactRef


def utc_now() -> datetime:
    """Return a second-granularity UTC timestamp for new trace events."""
    return datetime.now(UTC).replace(microsecond=0)


class RunTerminality(StrEnum):
    """Producer-owned knowledge state for whether a run has terminated."""

    TERMINAL = "terminal"
    NON_TERMINAL = "non_terminal"
    NOT_ESTABLISHED = "not_established"


class TraceRefs(BaseModel):
    """Trace refs public type."""

    model_config = ConfigDict(extra="forbid")
    inputs: list[ArtifactRef] = Field(default_factory=list)
    outputs: list[ArtifactRef] = Field(default_factory=list)


class TraceRecord(BaseModel):
    """One structured execution event emitted into the run trace stream."""

    model_config = ConfigDict(extra="forbid")

    ts: datetime = Field(default_factory=utc_now)
    run_id: str

    phase: str
    event: str
    run_terminality: RunTerminality | None = Field(
        default=None,
        description="Run-lifecycle fact when this event is emitted by the lifecycle owner.",
    )

    span_id: str | None = None
    parent_span_id: str | None = None
    tenant_id: str | None = None
    cell_id: str | None = None

    refs: TraceRefs = Field(default_factory=TraceRefs)
    metrics: dict[str, float | int] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)

    worker_invocation_id: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Parent-derived deduplication identity for staged worker events.",
    )
    worker_dispatch_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Parent-derived digest of the exact worker dispatch envelope.",
    )
    worker_receipt_phase: Literal["started", "completed"] | None = None
    worker_receipt_count: int | None = Field(default=None, ge=0)
    worker_receipt_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_worker_receipt(self) -> TraceRecord:
        worker_bound = (
            self.worker_invocation_id is not None or self.worker_dispatch_sha256 is not None
        )
        if worker_bound and (
            self.worker_invocation_id is None or self.worker_dispatch_sha256 is None
        ):
            raise ValueError("worker dispatch binding incomplete")
        if worker_bound and self.run_terminality is not None:
            raise ValueError("worker events cannot set run terminality")
        if (
            worker_bound
            and self.event.startswith("RUN_")
            and self.event not in {"RUN_INPUT_ADDED", "RUN_OUTPUT_ADDED", "RUN_CONTEXT_SNAPSHOT"}
        ):
            raise ValueError("worker events cannot claim run lifecycle")

        marker_values = (
            self.worker_receipt_phase,
            self.worker_receipt_count,
            self.worker_receipt_sha256,
        )
        if self.worker_receipt_phase is None:
            if self.worker_receipt_count is not None or self.worker_receipt_sha256 is not None:
                raise ValueError("worker receipt marker incomplete")
            return self
        if (
            not worker_bound
            or self.worker_receipt_count is None
            or self.worker_receipt_sha256 is None
            or any(value is None for value in marker_values)
        ):
            raise ValueError("worker receipt marker incomplete")

        expected_event = (
            "WORKER_INVOCATION_STARTED"
            if self.worker_receipt_phase == "started"
            else "WORKER_INVOCATION_COMPLETED"
        )
        if self.event != expected_event or self.run_terminality is not None:
            raise ValueError("worker receipt marker event invalid")
        return self
