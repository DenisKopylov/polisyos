"""Source invalidation propagation for Research DAG and Claim Ledger."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
    append_lifecycle_event,
)
from polisyos.scientist.methods.research_dag.models import ResearchDAGArtifact


class SourceInvalidationEvent(BaseModel):
    """One source invalidation event with explicit source and target lineage."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    source_ref: ArtifactRef
    invalidation_type: Literal["stale", "withdrawn", "contradicted", "unavailable"]
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source invalidation text fields cannot be blank")
        return value


class SourceInvalidationImpact(BaseModel):
    """Propagation result from one source invalidation event."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    workflow_id: str
    event: SourceInvalidationEvent
    source_node_ids: list[str] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)
    stale_claim_ids: list[str] = Field(default_factory=list)
    claim_lifecycle_action: ClaimLifecycleAction
    metadata: dict[str, Any] = Field(default_factory=dict)


def validate_source_invalidation_event(
    dag: ResearchDAGArtifact,
    event: SourceInvalidationEvent,
) -> None:
    """Validate that invalidation targets are present in the DAG lineage."""

    node_ids = {node.node_id for node in dag.nodes}
    claim_ids = _claim_ids(dag)
    source_node_ids = _source_node_ids_for_ref(dag, event.source_ref)
    if not source_node_ids:
        raise ValueError("source invalidation source_ref is not present in the Research DAG")
    orphan_nodes = sorted(set(event.affected_node_ids) - node_ids)
    if orphan_nodes:
        raise ValueError(f"orphaned invalidation target node ids: {orphan_nodes}")
    orphan_claims = sorted(set(event.affected_claim_ids) - claim_ids)
    if orphan_claims:
        raise ValueError(f"orphaned invalidation target claim ids: {orphan_claims}")


def propagate_source_invalidation(
    dag: ResearchDAGArtifact,
    event: SourceInvalidationEvent,
) -> SourceInvalidationImpact:
    """Propagate source invalidation through DAG descendants to dependent claims."""

    validate_source_invalidation_event(dag, event)
    source_node_ids = _source_node_ids_for_ref(dag, event.source_ref)
    seed_node_ids = sorted(set(source_node_ids) | set(event.affected_node_ids))
    affected_node_ids = _downstream_node_ids(dag, seed_node_ids)
    stale_claim_ids = sorted(
        set(event.affected_claim_ids) | _claim_ids_for_nodes(dag, set(affected_node_ids))
    )
    action = (
        ClaimLifecycleAction.INVALIDATED
        if event.invalidation_type in {"withdrawn", "contradicted"}
        else ClaimLifecycleAction.MARKED_STALE
    )
    return SourceInvalidationImpact(
        run_id=dag.run_id,
        workflow_id=dag.workflow_id,
        event=event,
        source_node_ids=source_node_ids,
        affected_node_ids=affected_node_ids,
        stale_claim_ids=stale_claim_ids,
        claim_lifecycle_action=action,
        metadata={
            "source_ref": str(event.source_ref.artifact_id),
            "invalidation_type": event.invalidation_type,
        },
    )


def claim_lifecycle_events_for_invalidation(
    impact: SourceInvalidationImpact,
    *,
    actor_id: str,
    occurred_at: datetime | None = None,
) -> list[ClaimLifecycleEvent]:
    """Create claim lifecycle events for stale/invalidated dependent claims."""

    timestamp = occurred_at or impact.event.occurred_at
    return [
        ClaimLifecycleEvent(
            event_id=_claim_invalidation_event_id(
                impact=impact,
                claim_id=claim_id,
                sequence=index,
            ),
            claim_id=claim_id,
            run_id=impact.run_id,
            action=impact.claim_lifecycle_action,
            occurred_at=timestamp,
            actor_id=actor_id,
            reason=impact.event.reason,
            metadata={
                "source_invalidation_event_id": impact.event.event_id,
                "source_ref": str(impact.event.source_ref.artifact_id),
                "invalidation_type": impact.event.invalidation_type,
                "affected_node_ids": list(impact.affected_node_ids),
            },
        )
        for index, claim_id in enumerate(impact.stale_claim_ids)
    ]


def append_invalidation_events_to_ledger(
    ledger: AppendOnlyClaimLedger,
    impact: SourceInvalidationImpact,
    *,
    actor_id: str,
    occurred_at: datetime | None = None,
) -> AppendOnlyClaimLedger:
    """Append stale/invalidated claim events to an append-only Claim Ledger."""

    updated = ledger
    for event in claim_lifecycle_events_for_invalidation(
        impact,
        actor_id=actor_id,
        occurred_at=occurred_at,
    ):
        updated = append_lifecycle_event(updated, event)
    return updated


def _source_node_ids_for_ref(
    dag: ResearchDAGArtifact,
    source_ref: ArtifactRef,
) -> list[str]:
    target_id = str(source_ref.artifact_id)
    return sorted(
        node.node_id
        for node in dag.nodes
        if any(str(ref.artifact_id) == target_id for ref in node.artifact_refs)
    )


def _downstream_node_ids(
    dag: ResearchDAGArtifact,
    seed_node_ids: list[str],
) -> list[str]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in dag.edges:
        outgoing[edge.source_node_id].append(edge.target_node_id)
    seen: set[str] = set(seed_node_ids)
    queue: deque[str] = deque(seed_node_ids)
    while queue:
        current = queue.popleft()
        for child in sorted(outgoing[current]):
            if child in seen:
                continue
            seen.add(child)
            queue.append(child)
    return sorted(seen)


def _claim_ids_for_nodes(dag: ResearchDAGArtifact, node_ids: set[str]) -> set[str]:
    claim_ids: set[str] = set()
    for node in dag.nodes:
        if node.node_id in node_ids:
            claim_ids.update(node.claim_ids)
    for edge in dag.edges:
        if edge.source_node_id in node_ids or edge.target_node_id in node_ids:
            claim_ids.update(edge.claim_ids)
    return claim_ids


def _claim_ids(dag: ResearchDAGArtifact) -> set[str]:
    return _claim_ids_for_nodes(dag, {node.node_id for node in dag.nodes})


def _claim_invalidation_event_id(
    *,
    impact: SourceInvalidationImpact,
    claim_id: str,
    sequence: int,
) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "source_event_id": impact.event.event_id,
                "run_id": impact.run_id,
                "claim_id": claim_id,
                "action": impact.claim_lifecycle_action.value,
                "sequence": sequence,
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"claim_source_invalidation_{digest}"


__all__ = [
    "SourceInvalidationEvent",
    "SourceInvalidationImpact",
    "append_invalidation_events_to_ledger",
    "claim_lifecycle_events_for_invalidation",
    "propagate_source_invalidation",
    "validate_source_invalidation_event",
]
