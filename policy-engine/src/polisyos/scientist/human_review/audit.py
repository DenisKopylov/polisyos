"""Audit helpers for Scientist human-review lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from polisyos.scientist.human_review.models import (
    HumanReviewAuditEvent,
    HumanReviewDecision,
    ReviewAssignment,
    ReviewerSignature,
)

__all__ = [
    "append_audit_event",
    "decision_audit_event",
    "make_audit_event",
    "reviewer_ids_are_distinct",
    "signature_for_decision",
]


def make_audit_event(
    *,
    packet_id: str,
    event_type: str,
    message: str,
    actor_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> HumanReviewAuditEvent:
    """Create a deterministic-id audit event from its semantic contents."""

    occurred_at = datetime.now(UTC)
    seed = "|".join(
        [
            packet_id,
            event_type,
            actor_id or "",
            message,
            occurred_at.isoformat(),
        ]
    )
    return HumanReviewAuditEvent(
        event_id=f"hre_{sha256(seed.encode('utf-8')).hexdigest()[:16]}",
        packet_id=packet_id,
        event_type=event_type,
        actor_id=actor_id,
        occurred_at=occurred_at,
        message=message,
        metadata=metadata or {},
    )


def append_audit_event(
    events: list[HumanReviewAuditEvent],
    event: HumanReviewAuditEvent,
) -> list[HumanReviewAuditEvent]:
    """Return an append-only audit trail with duplicate event ids removed."""

    seen = {item.event_id for item in events}
    if event.event_id in seen:
        return list(events)
    return [*events, event]


def signature_for_decision(
    *,
    reviewer_id: str,
    attestation: str,
    role: str = "primary",
) -> ReviewerSignature:
    """Build a reviewer signature for tests and adapters."""

    return ReviewerSignature(
        reviewer_id=reviewer_id,
        role=role,
        attestation=attestation,
    )


def decision_audit_event(decision: HumanReviewDecision) -> HumanReviewAuditEvent:
    """Project a review decision into an audit event."""

    return make_audit_event(
        packet_id=decision.packet_id,
        event_type=f"decision.{decision.action.value}",
        actor_id=decision.reviewer_id,
        message=decision.rationale,
        metadata={
            "decision_id": decision.decision_id,
            "action": decision.action.value,
        },
    )


def reviewer_ids_are_distinct(assignments: list[ReviewAssignment]) -> bool:
    """Return whether all assigned reviewers are distinct."""

    reviewer_ids = [item.reviewer_id for item in assignments]
    return len(reviewer_ids) == len(set(reviewer_ids))
