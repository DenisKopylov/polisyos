"""Assignment queue helpers for Scientist human-review packets."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.human_review.models import (
    HumanReviewPacket,
    HumanReviewQueueRecord,
    HumanReviewStatus,
    ReviewAssignment,
    ReviewAssignmentStatus,
    ReviewerRole,
)

HUMAN_REVIEW_QUEUE_KIND = "scientist.human_review_queue"
HUMAN_REVIEW_QUEUE_SCHEMA_NAME = "polisyos.scientist.human_review.HumanReviewQueueState"
HUMAN_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"

__all__ = [
    "HUMAN_REVIEW_QUEUE_KIND",
    "HUMAN_REVIEW_QUEUE_SCHEMA_NAME",
    "HUMAN_REVIEW_QUEUE_SCHEMA_VERSION",
    "HumanReviewQueueState",
    "assign_review",
    "enqueue_review_packet",
    "load_review_queue",
    "persist_review_queue",
]


class HumanReviewQueueState(BaseModel):
    """CAS-persisted human-review queue snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    queue_id: str = Field(default="scientist_human_review_queue", min_length=1)
    records: list[HumanReviewQueueRecord] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def pending(self) -> list[HumanReviewQueueRecord]:
        """Return records still awaiting final review decisions."""

        return [record for record in self.records if record.status is HumanReviewStatus.PENDING]


def enqueue_review_packet(
    state: HumanReviewQueueState,
    *,
    packet: HumanReviewPacket,
    packet_ref: ArtifactRef,
) -> HumanReviewQueueState:
    """Add or refresh one packet in the review queue."""

    record = HumanReviewQueueRecord(
        packet_id=packet.packet_id,
        packet_ref=packet_ref,
        status=HumanReviewStatus.PENDING,
        risk_tier=packet.risk_tier,
        required_reviewer_count=packet.required_reviewer_count,
        assignments=list(packet.assignments),
    )
    records = [item for item in state.records if item.packet_id != packet.packet_id]
    return state.model_copy(
        update={"records": [*records, record], "updated_at": datetime.now(UTC)}
    )


def assign_review(
    state: HumanReviewQueueState,
    *,
    packet_id: str,
    reviewer_id: str,
    role: ReviewerRole = ReviewerRole.PRIMARY,
) -> tuple[HumanReviewQueueState, ReviewAssignment]:
    """Assign a queued review packet to a reviewer."""

    assignment = ReviewAssignment(
        assignment_id=_assignment_id(packet_id=packet_id, reviewer_id=reviewer_id, role=role),
        packet_id=packet_id,
        reviewer_id=reviewer_id,
        role=role,
        status=ReviewAssignmentStatus.PENDING,
    )
    records: list[HumanReviewQueueRecord] = []
    matched = False
    for record in state.records:
        if record.packet_id != packet_id:
            records.append(record)
            continue
        matched = True
        existing = [
            item
            for item in record.assignments
            if not (item.reviewer_id == reviewer_id and item.role == role)
        ]
        records.append(
            record.model_copy(
                update={
                    "assignments": [*existing, assignment],
                    "updated_at": datetime.now(UTC),
                }
            )
        )
    if not matched:
        raise KeyError(f"review packet is not queued: {packet_id}")
    return state.model_copy(update={"records": records, "updated_at": datetime.now(UTC)}), assignment


def persist_review_queue(store: FileSystemCAS, state: HumanReviewQueueState) -> ArtifactRef:
    """Persist a human-review queue snapshot."""

    inputs = [
        InputRef(artifact_id=record.packet_ref.artifact_id, role=f"queued_packet[{index}]")
        for index, record in enumerate(state.records)
    ]
    return store.put_json(
        state,
        PutOptions(
            kind=HUMAN_REVIEW_QUEUE_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=HUMAN_REVIEW_QUEUE_SCHEMA_NAME,
                version=HUMAN_REVIEW_QUEUE_SCHEMA_VERSION,
            ),
            inputs=inputs or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_review_queue(store: FileSystemCAS, ref: ArtifactRef) -> HumanReviewQueueState:
    """Load a persisted human-review queue snapshot."""

    return HumanReviewQueueState.model_validate(
        from_canonical_bytes(store.get_bytes(ref.artifact_id))
    )


def _assignment_id(*, packet_id: str, reviewer_id: str, role: ReviewerRole) -> str:
    seed = f"{packet_id}|{reviewer_id}|{role.value}"
    return f"hra_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"
