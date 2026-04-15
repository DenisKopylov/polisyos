"""Cursor and checkpoint contracts for incremental and streaming ingestion."""

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
    SCHEMA = "schema"


class StreamLifecycleState(str, Enum):
    """Lifecycle state for a resumable stream subscription."""

    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class WindowStrategy(str, Enum):
    """Logical windowing strategy for event-driven ingestion."""

    TUMBLING = "tumbling"
    SLIDING = "sliding"
    SESSION = "session"
    COUNT = "count"


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
    stream_checkpoints: list["StreamCheckpoint"] = Field(default_factory=list)
    created_at: datetime


class StreamCheckpoint(BaseModel):
    """Checkpoint for one stream partition/offset pair."""

    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str
    stream_id: str = Field(
        description="Unique stream identifier: '{connector_id}:{dataset_id}:{partition_key}'",
    )
    connector_id: str
    dataset_id: str
    partition_key: str = Field(default="default")
    offset: int = Field(default=0, ge=0)
    resume_token: str | None = None
    watermark_type: WatermarkType = WatermarkType.OFFSET
    lifecycle_state: StreamLifecycleState = StreamLifecycleState.ACTIVE
    dedupe_keys: tuple[str, ...] = Field(default_factory=tuple)
    schema_fingerprint: str | None = None
    created_at: datetime
    committed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PartitionCursorState(BaseModel):
    """Persisted state for one independently resumable ingestion partition."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    partition_id: str
    connector_id: str
    dataset_id: str
    partition_key: str
    partition_bounds: dict[str, Any] = Field(default_factory=dict)
    source_cursor: str | None = None
    expected_cardinality: int | None = None
    merge_policy: str = "append"
    status: str = "pending"
    last_error: str | None = None
    checkpoint_id: str | None = None
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "CursorState",
    "IncrementalCheckpoint",
    "PartitionCursorState",
    "StreamCheckpoint",
    "StreamLifecycleState",
    "WatermarkType",
    "WindowStrategy",
]
