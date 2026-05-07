"""Human-review decision persistence and status aggregation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.governance.human_review.models import (
    HumanReviewDecision,
    HumanReviewPacket,
    HumanReviewStatus,
    ReviewAction,
)

HUMAN_REVIEW_DECISION_KIND = "scientist.human_review_decision"
HUMAN_REVIEW_DECISION_SCHEMA_NAME = "polisyos.scientist.human_review.HumanReviewDecision"
HUMAN_REVIEW_DECISION_SCHEMA_VERSION = "1.0"

__all__ = [
    "HUMAN_REVIEW_DECISION_KIND",
    "HUMAN_REVIEW_DECISION_SCHEMA_NAME",
    "HUMAN_REVIEW_DECISION_SCHEMA_VERSION",
    "human_review_decision_inputs",
    "human_review_status",
    "load_review_decision",
    "persist_review_decision",
    "review_decision_summary",
]


def human_review_decision_inputs(decision: HumanReviewDecision) -> list[InputRef]:
    """Build manifest lineage inputs for a review decision."""

    inputs: list[InputRef] = []
    if decision.packet_ref is not None:
        inputs.append(InputRef(artifact_id=decision.packet_ref.artifact_id, role="review_packet"))
    if decision.supersedes_decision_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=decision.supersedes_decision_ref.artifact_id,
                role="supersedes_decision",
            )
        )
    if decision.signature.signature_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=decision.signature.signature_ref.artifact_id,
                role="reviewer_signature",
            )
        )
    return inputs


def persist_review_decision(
    store: FileSystemCAS,
    decision: HumanReviewDecision,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a human-review decision as a CAS artifact."""

    return store.put_json(
        decision,
        PutOptions(
            kind=HUMAN_REVIEW_DECISION_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=HUMAN_REVIEW_DECISION_SCHEMA_NAME,
                version=HUMAN_REVIEW_DECISION_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else human_review_decision_inputs(decision),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_review_decision(store: FileSystemCAS, ref: ArtifactRef) -> HumanReviewDecision:
    """Load a persisted human-review decision from CAS."""

    return HumanReviewDecision.model_validate(
        from_canonical_bytes(store.get_bytes(ref.artifact_id))
    )


def human_review_status(
    decisions: Iterable[HumanReviewDecision],
    *,
    packet: HumanReviewPacket | None = None,
    required_reviewer_count: int | None = None,
) -> HumanReviewStatus:
    """Aggregate reviewer decisions into an operational release status."""

    decision_list = list(decisions)
    if not decision_list:
        return HumanReviewStatus.PENDING
    actions = [decision.action for decision in decision_list]
    if ReviewAction.INTERRUPT_RELEASE in actions:
        return HumanReviewStatus.INTERRUPTED
    if ReviewAction.REJECT in actions:
        return HumanReviewStatus.REJECTED
    if ReviewAction.REQUEST_RERUN in actions:
        return HumanReviewStatus.RERUN_REQUESTED
    if ReviewAction.EXPLANATION_INSUFFICIENT in actions:
        return HumanReviewStatus.EXPLANATION_INSUFFICIENT
    if ReviewAction.OVERRIDE in actions:
        return HumanReviewStatus.OVERRIDDEN
    required_count = required_reviewer_count or (
        packet.required_reviewer_count if packet is not None else 1
    )
    approving_reviewers = {
        decision.reviewer_id
        for decision in decision_list
        if decision.action is ReviewAction.APPROVE
    }
    if len(approving_reviewers) >= required_count:
        return HumanReviewStatus.APPROVED
    return HumanReviewStatus.PENDING


def review_decision_summary(
    decisions: Iterable[HumanReviewDecision],
    *,
    packet: HumanReviewPacket | None = None,
) -> dict[str, Any]:
    """Return a governance/decision-packet safe summary of review decisions."""

    decision_list = list(decisions)
    status = human_review_status(decision_list, packet=packet)
    return {
        "status": status.value,
        "decision_count": len(decision_list),
        "required_reviewer_count": (
            packet.required_reviewer_count if packet is not None else 1
        ),
        "reviewer_ids": sorted({decision.reviewer_id for decision in decision_list}),
        "actions": [decision.action.value for decision in decision_list],
        "latest_decision_at": (
            max(decision.decided_at for decision in decision_list).isoformat()
            if decision_list
            else None
        ),
    }
