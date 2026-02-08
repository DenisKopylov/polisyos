from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class TraceRefs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: list[ArtifactRef] = Field(default_factory=list)
    outputs: list[ArtifactRef] = Field(default_factory=list)


class TraceRecord(BaseModel):
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
