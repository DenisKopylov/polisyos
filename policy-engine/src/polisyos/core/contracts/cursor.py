"""Cursor contracts for incremental ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WatermarkType(str, Enum):
    """Watermark strategy used for cursor tracking."""

    TIMESTAMP = "timestamp"
    ETAG = "etag"
    REVISION = "revision"
    OFFSET = "offset"


class CursorState(BaseModel):
    """Persisted cursor for incremental ingestion."""

    model_config = ConfigDict(extra="forbid")

    cursor_id: str = Field(
        description="Unique identifier: '{connector_id}:{dataset_id}'",
    )
    connector_id: str
    dataset_id: str
    watermark_type: WatermarkType
    watermark_value: str = Field(
        description="The actual cursor value (timestamp ISO, ETag, revision, offset)",
    )
    created_at: datetime
    ingestion_run_id: str | None = None
    evidence_bundle_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncrementalCheckpoint(BaseModel):
    """Checkpoint for mid-ingestion recovery."""

    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str
    connector_id: str
    datasets_completed: list[str] = Field(default_factory=list)
    datasets_pending: list[str] = Field(default_factory=list)
    cursor_states: list[CursorState] = Field(default_factory=list)
    created_at: datetime


__all__ = ["CursorState", "IncrementalCheckpoint", "WatermarkType"]
