from __future__ import annotations

from datetime import UTC, datetime

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.methods.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.methods.research_dag.invalidation import (
    SourceInvalidationEvent,
    append_invalidation_events_to_ledger,
    claim_lifecycle_events_for_invalidation,
    propagate_source_invalidation,
)
from polisyos.scientist.methods.research_dag.models import ResearchEdgeType, ResearchNodeType
from polisyos.scientist.methods.search.readiness import DecisionReadiness
from pydantic import ValidationError


def _ref(suffix: str, *, kind: str = "scientist.source") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
    )


def _claim(claim_id: str = "claim_1") -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run_invalid",
        claim_type=ClaimType.FACTUAL,
        text="Claim text.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[_ref("1")],
    )


def _dag(source_ref: ArtifactRef):
    builder = ResearchDAGBuilder(run_id="run_invalid", workflow_id="scientist_policy_design")
    source = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Read source.",
        artifact_refs=[source_ref],
    )
    extraction = builder.add_node(
        node_type=ResearchNodeType.EXTRACTION,
        producer="extractor",
        summary="Extract snippet.",
        claim_ids=["claim_1"],
        metadata={"snippet_id": "snippet_1"},
    )
    synthesis = builder.add_node(
        node_type=ResearchNodeType.SYNTHESIS,
        producer="synthesizer",
        summary="Synthesize.",
        claim_ids=["claim_1"],
    )
    builder.add_edge(
        source_node_id=source.node_id,
        target_node_id=extraction.node_id,
        edge_type=ResearchEdgeType.SUPPORTS,
        claim_ids=["claim_1"],
    )
    builder.add_edge(
        source_node_id=extraction.node_id,
        target_node_id=synthesis.node_id,
        edge_type=ResearchEdgeType.DERIVES,
        claim_ids=["claim_1"],
    )
    return builder.artifact()


def test_source_invalidation_marks_dependent_claims_stale() -> None:
    source_ref = _ref("1")
    dag = _dag(source_ref)
    event = SourceInvalidationEvent(
        event_id="source_invalid_1",
        source_ref=source_ref,
        invalidation_type="stale",
        reason="Source freshness TTL expired.",
    )

    impact = propagate_source_invalidation(dag, event)
    lifecycle_events = claim_lifecycle_events_for_invalidation(
        impact,
        actor_id="replay.invalidation",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
    )

    assert impact.stale_claim_ids == ["claim_1"]
    assert impact.claim_lifecycle_action is ClaimLifecycleAction.MARKED_STALE
    assert lifecycle_events[0].claim_id == "claim_1"
    assert lifecycle_events[0].action is ClaimLifecycleAction.MARKED_STALE


def test_withdrawn_source_invalidates_dependent_claims_in_ledger() -> None:
    source_ref = _ref("1")
    dag = _dag(source_ref)
    ledger = AppendOnlyClaimLedger(run_id="run_invalid", current_claims=[_claim()])
    event = SourceInvalidationEvent(
        event_id="source_invalid_1",
        source_ref=source_ref,
        invalidation_type="withdrawn",
        reason="Source was withdrawn.",
    )
    impact = propagate_source_invalidation(dag, event)

    updated = append_invalidation_events_to_ledger(
        ledger,
        impact,
        actor_id="replay.invalidation",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
    )

    assert updated.events[0].action is ClaimLifecycleAction.INVALIDATED
    assert updated.events[0].metadata["source_invalidation_event_id"] == "source_invalid_1"


def test_invalidation_event_with_missing_source_ref_fails_validation() -> None:
    with pytest.raises(ValidationError):
        SourceInvalidationEvent(
            event_id="source_invalid_1",
            invalidation_type="stale",
            reason="Missing source ref.",
        )


def test_orphaned_invalidation_target_claim_and_node_fail_validation() -> None:
    source_ref = _ref("1")
    dag = _dag(source_ref)
    orphan_node_event = SourceInvalidationEvent(
        event_id="source_invalid_1",
        source_ref=source_ref,
        invalidation_type="stale",
        affected_node_ids=["missing_node"],
        reason="Source changed.",
    )
    orphan_claim_event = SourceInvalidationEvent(
        event_id="source_invalid_2",
        source_ref=source_ref,
        invalidation_type="stale",
        affected_claim_ids=["missing_claim"],
        reason="Source changed.",
    )

    with pytest.raises(ValueError, match="orphaned invalidation target node"):
        propagate_source_invalidation(dag, orphan_node_event)
    with pytest.raises(ValueError, match="orphaned invalidation target claim"):
        propagate_source_invalidation(dag, orphan_claim_event)


def test_invalidation_source_ref_must_exist_in_dag_lineage() -> None:
    dag = _dag(_ref("1"))
    event = SourceInvalidationEvent(
        event_id="source_invalid_1",
        source_ref=_ref("2"),
        invalidation_type="unavailable",
        reason="Source unavailable.",
    )

    with pytest.raises(ValueError, match="source_ref is not present"):
        propagate_source_invalidation(dag, event)
