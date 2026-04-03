"""Trace-record schema used to persist run events, refs, metrics, warnings, and errors."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef


def utc_now() -> datetime:
    """Return a second-granularity UTC timestamp for new trace events."""
    return datetime.now(timezone.utc).replace(microsecond=0)


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

    span_id: str | None = None
    parent_span_id: str | None = None
    tenant_id: str | None = None
    cell_id: str | None = None

    refs: TraceRefs = Field(default_factory=TraceRefs)
    metrics: dict[str, float | int] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
