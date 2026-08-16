"""Strict outbound contracts for schema-hidden runtime channels."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter

from polisyos.core.artifacts.manifest import ArtifactRef  # noqa: TC001 - Pydantic runtime type
from polisyos.core.contracts.decision_validity import (  # noqa: TC001 - Pydantic runtime type
    DecisionValidityStatus,
)
from polisyos.core.trace import RunTerminality  # noqa: TC001 - Pydantic runtime type

RUNS_CHANNEL_DATA_EVENT_CONTRACT = "policyos.runtime.runs_channel_data_event.v2"


class _StrictOutboundChannelModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RunsListSnapshotPage(_StrictOutboundChannelModel):
    """Pagination state embedded in the runs-list live snapshot."""

    count: int = Field(ge=0)
    total: int | None = Field(default=None, ge=0)
    next_cursor: str | None = None


class RunsListSnapshotRun(_StrictOutboundChannelModel):
    """One run summary emitted by the runs-list live channel."""

    run_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    run_terminality: RunTerminality
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    root_artifact_count: int = Field(ge=0)
    decision_validity_status: DecisionValidityStatus | None = None
    decision_review_required: bool


class RunsListSnapshot(_StrictOutboundChannelModel):
    """Versioned snapshot emitted by ``GET /api/v1/runs/live``."""

    contract_id: Literal["policyos.runtime.runs_list_snapshot"] = (
        "policyos.runtime.runs_list_snapshot"
    )
    schema_version: Literal["policyos.runtime.runs_list_snapshot.v2"] = (
        "policyos.runtime.runs_list_snapshot.v2"
    )
    cursor: AwareDatetime
    generated_at: AwareDatetime
    page: RunsListSnapshotPage
    status_counts: dict[str, int]
    runs: list[RunsListSnapshotRun]


class RunDetailSnapshot(_StrictOutboundChannelModel):
    """Versioned snapshot emitted by ``GET /api/v1/runs/{run_id}/live``."""

    contract_id: Literal["policyos.runtime.run_detail_snapshot"] = (
        "policyos.runtime.run_detail_snapshot"
    )
    schema_version: Literal["policyos.runtime.run_detail_snapshot.v2"] = (
        "policyos.runtime.run_detail_snapshot.v2"
    )
    run_id: str = Field(min_length=1)
    cursor: AwareDatetime
    status: str = Field(min_length=1)
    run_terminality: RunTerminality
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    timeline_events: int = Field(ge=0)
    timeline_duration_ms: int | None = Field(default=None, ge=0)
    agent_attempts: int = Field(ge=0)
    agent_steps: int = Field(ge=0)
    governance_issues: int = Field(ge=0)
    transport_status: str | None = None
    decision_validity_status: DecisionValidityStatus | None = None
    decision_review_required: bool
    decision_superseded_by_ref: ArtifactRef | None = None
    generated_at: AwareDatetime


RunsLiveSnapshot = Annotated[
    RunsListSnapshot | RunDetailSnapshot,
    Field(discriminator="contract_id"),
]


class RunsStreamTimeout(_StrictOutboundChannelModel):
    """Versioned timeout event emitted when a runs stream exhausts its budget."""

    contract_id: Literal["policyos.runtime.runs_stream_timeout"] = (
        "policyos.runtime.runs_stream_timeout"
    )
    schema_version: Literal["policyos.runtime.runs_stream_timeout.v1"] = (
        "policyos.runtime.runs_stream_timeout.v1"
    )
    cursor: AwareDatetime
    generated_at: AwareDatetime
    reason: Literal["stream_timeout_budget_exhausted"] = (
        "stream_timeout_budget_exhausted"
    )


class RunsSnapshotDataEvent(_StrictOutboundChannelModel):
    """Typed SSE envelope for a runs snapshot data event."""

    event: Literal["snapshot"] = "snapshot"
    payload: RunsLiveSnapshot


class RunsStreamTimeoutDataEvent(_StrictOutboundChannelModel):
    """Typed SSE envelope for a runs timeout data event."""

    event: Literal["stream.timeout"] = "stream.timeout"
    payload: RunsStreamTimeout


RunsChannelDataEvent = Annotated[
    RunsSnapshotDataEvent | RunsStreamTimeoutDataEvent,
    Field(discriminator="event"),
]


class ReviewPresenceParticipant(_StrictOutboundChannelModel):
    """One active participant in a presence snapshot."""

    participant_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    accent_color: str = Field(min_length=1)
    last_seen_at: AwareDatetime
    session_count: int = Field(ge=1)


class ReviewCursorParticipant(_StrictOutboundChannelModel):
    """One visible participant cursor in a cursor snapshot."""

    participant_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    accent_color: str = Field(min_length=1)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    updated_at: AwareDatetime


class ReviewLock(_StrictOutboundChannelModel):
    """Current review editing lease exposed on the lock channel."""

    participant_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    accent_color: str = Field(min_length=1)
    acquired_at: AwareDatetime
    expires_at: AwareDatetime


class ReviewPresenceSnapshot(_StrictOutboundChannelModel):
    """Versioned presence snapshot for review collaboration."""

    contract_id: Literal["policyos.runtime.review_collaboration_envelope"] = (
        "policyos.runtime.review_collaboration_envelope"
    )
    schema_version: Literal["policyos.runtime.review_collaboration_envelope.v1"] = (
        "policyos.runtime.review_collaboration_envelope.v1"
    )
    channel: Literal["review.presence"] = "review.presence"
    participants: list[ReviewPresenceParticipant]
    review_id: str = Field(min_length=1)
    type: Literal["presence.snapshot"] = "presence.snapshot"


class ReviewCursorSnapshot(_StrictOutboundChannelModel):
    """Versioned cursor snapshot for review collaboration."""

    contract_id: Literal["policyos.runtime.review_collaboration_envelope"] = (
        "policyos.runtime.review_collaboration_envelope"
    )
    schema_version: Literal["policyos.runtime.review_collaboration_envelope.v1"] = (
        "policyos.runtime.review_collaboration_envelope.v1"
    )
    channel: Literal["review.cursor"] = "review.cursor"
    cursors: list[ReviewCursorParticipant]
    review_id: str = Field(min_length=1)
    type: Literal["cursor.snapshot"] = "cursor.snapshot"


class ReviewLockSnapshot(_StrictOutboundChannelModel):
    """Versioned lock snapshot for review collaboration."""

    contract_id: Literal["policyos.runtime.review_collaboration_envelope"] = (
        "policyos.runtime.review_collaboration_envelope"
    )
    schema_version: Literal["policyos.runtime.review_collaboration_envelope.v1"] = (
        "policyos.runtime.review_collaboration_envelope.v1"
    )
    channel: Literal["review.lock"] = "review.lock"
    lock: ReviewLock | None
    review_id: str = Field(min_length=1)
    type: Literal["lock.snapshot"] = "lock.snapshot"


ReviewSnapshot = Annotated[
    ReviewPresenceSnapshot | ReviewCursorSnapshot | ReviewLockSnapshot,
    Field(discriminator="type"),
]

_RUNS_LIVE_SNAPSHOT_ADAPTER = TypeAdapter(RunsLiveSnapshot)
_RUNS_CHANNEL_DATA_EVENT_ADAPTER = TypeAdapter(RunsChannelDataEvent)
_REVIEW_SNAPSHOT_ADAPTER = TypeAdapter(ReviewSnapshot)


def validate_runs_live_snapshot(payload: object) -> RunsLiveSnapshot:
    """Validate one runs SSE snapshot at its final emission boundary."""

    return _RUNS_LIVE_SNAPSHOT_ADAPTER.validate_python(payload)


def validate_runs_channel_data_event(
    payload: object,
    *,
    event: str,
) -> RunsChannelDataEvent:
    """Validate one data-bearing runs SSE event at the emission boundary."""

    return _RUNS_CHANNEL_DATA_EVENT_ADAPTER.validate_python(
        {"event": event, "payload": payload}
    )


def validate_review_snapshot(payload: object) -> ReviewSnapshot:
    """Validate one review snapshot at its final websocket emission boundary."""

    return _REVIEW_SNAPSHOT_ADAPTER.validate_python(payload)
