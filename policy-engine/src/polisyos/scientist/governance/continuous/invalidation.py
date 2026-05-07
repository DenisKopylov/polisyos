"""Bridge Research DAG invalidation into continuous governance controls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleEvent,
)
from polisyos.scientist.methods.research_dag.invalidation import (
    SourceInvalidationImpact,
    append_invalidation_events_to_ledger,
)

from .monitors import (
    GovernanceMonitorEvent,
    GovernanceMonitorRecommendation,
    MonitorSeverity,
    monitor_event_id,
    recommend_validity_action,
)


class ContinuousInvalidationResult(BaseModel):
    """Continuous-governance result for one propagated source invalidation."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal["1.0"] = "1.0"
    governance_event: GovernanceMonitorEvent
    recommendation: GovernanceMonitorRecommendation
    lifecycle_events: list[ClaimLifecycleEvent] = Field(default_factory=list)
    updated_ledger: AppendOnlyClaimLedger
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_dag_node_ids: list[str] = Field(default_factory=list)


def governance_event_from_source_invalidation(
    *,
    decision_packet_ref: ArtifactRef,
    impact: SourceInvalidationImpact,
    severity: MonitorSeverity | None = None,
    sequence: int = 0,
) -> GovernanceMonitorEvent:
    """Create a monitor event from DAG invalidation impact.

    A source invalidation without dependent claim or DAG lineage is ambiguous;
    it must be rejected rather than silently passing the monitoring loop.
    """

    if not impact.stale_claim_ids and not impact.affected_node_ids:
        raise ValueError("source invalidation must identify affected claim or DAG lineage")
    resolved_severity = severity
    if resolved_severity is None:
        resolved_severity = (
            "block"
            if impact.event.invalidation_type in {"withdrawn", "contradicted"}
            else "warning"
        )
    return GovernanceMonitorEvent(
        event_id=monitor_event_id(
            decision_packet_ref=decision_packet_ref,
            event_type="source_invalidation",
            reason=impact.event.reason,
            sequence=sequence,
        ),
        decision_packet_ref=decision_packet_ref,
        event_type="source_invalidation",
        severity=resolved_severity,
        affected_claim_ids=list(impact.stale_claim_ids),
        affected_dag_node_ids=list(impact.affected_node_ids),
        reason=impact.event.reason,
        occurred_at=impact.event.occurred_at,
        metadata={
            "source_invalidation_event_id": impact.event.event_id,
            "source_ref": str(impact.event.source_ref.artifact_id),
            "invalidation_type": impact.event.invalidation_type,
            "workflow_id": impact.workflow_id,
            "claim_lifecycle_action": impact.claim_lifecycle_action.value,
        },
    )


def mark_dependent_claims_stale(
    *,
    ledger: AppendOnlyClaimLedger,
    decision_packet_ref: ArtifactRef,
    impact: SourceInvalidationImpact,
    actor_id: str,
    occurred_at: datetime | None = None,
    severity: MonitorSeverity | None = None,
) -> ContinuousInvalidationResult:
    """Append lifecycle events and return the monitor recommendation."""

    timestamp = occurred_at or impact.event.occurred_at or datetime.now(UTC)
    before = len(ledger.events)
    updated_ledger = append_invalidation_events_to_ledger(
        ledger,
        impact,
        actor_id=actor_id,
        occurred_at=timestamp,
    )
    lifecycle_events = list(updated_ledger.events[before:])
    governance_event = governance_event_from_source_invalidation(
        decision_packet_ref=decision_packet_ref,
        impact=impact,
        severity=severity,
    )
    return ContinuousInvalidationResult(
        governance_event=governance_event,
        recommendation=recommend_validity_action(governance_event),
        lifecycle_events=lifecycle_events,
        updated_ledger=updated_ledger,
        affected_claim_ids=list(impact.stale_claim_ids),
        affected_dag_node_ids=list(impact.affected_node_ids),
    )


__all__ = [
    "ContinuousInvalidationResult",
    "governance_event_from_source_invalidation",
    "mark_dependent_claims_stale",
]
