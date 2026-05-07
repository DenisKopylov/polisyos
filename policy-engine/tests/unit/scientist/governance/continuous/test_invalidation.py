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
from polisyos.scientist.governance.continuous.invalidation import (
    governance_event_from_source_invalidation,
    mark_dependent_claims_stale,
)
from polisyos.scientist.governance.continuous.monitors import DecisionValidityStatus
from polisyos.scientist.methods.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.methods.research_dag.invalidation import (
    SourceInvalidationEvent,
    SourceInvalidationImpact,
    propagate_source_invalidation,
)
from polisyos.scientist.methods.research_dag.models import ResearchEdgeType, ResearchNodeType
from polisyos.scientist.methods.search.readiness import DecisionReadiness
from pydantic import ValidationError


def _ref(seed: str, *, kind: str = "scientist.source") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def _claim() -> ClaimRecord:
    return ClaimRecord(
        claim_id="claim_1",
        run_id="run_continuous",
        claim_type=ClaimType.FACTUAL,
        text="The source supports the decision.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[_ref("1")],
    )


def _dag(source_ref: ArtifactRef):
    builder = ResearchDAGBuilder(run_id="run_continuous", workflow_id="scientist_policy_design")
    source = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Read source.",
        artifact_refs=[source_ref],
    )
    extraction = builder.add_node(
        node_type=ResearchNodeType.EXTRACTION,
        producer="extractor",
        summary="Extract evidence.",
        claim_ids=["claim_1"],
    )
    builder.add_edge(
        source_node_id=source.node_id,
        target_node_id=extraction.node_id,
        edge_type=ResearchEdgeType.SUPPORTS,
        claim_ids=["claim_1"],
    )
    return builder.artifact()


def test_source_invalidation_marks_claim_stale_and_recommends_stale_status() -> None:
    source_ref = _ref("1")
    impact = propagate_source_invalidation(
        _dag(source_ref),
        SourceInvalidationEvent(
            event_id="source_invalid_1",
            source_ref=source_ref,
            invalidation_type="stale",
            reason="Source freshness TTL expired.",
        ),
    )
    ledger = AppendOnlyClaimLedger(run_id="run_continuous", current_claims=[_claim()])

    result = mark_dependent_claims_stale(
        ledger=ledger,
        decision_packet_ref=_ref("2", kind="scientist.decision_packet"),
        impact=impact,
        actor_id="continuous_governance.monitor",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
    )

    assert result.lifecycle_events[0].action is ClaimLifecycleAction.MARKED_STALE
    assert result.affected_claim_ids == ["claim_1"]
    assert result.recommendation.status is DecisionValidityStatus.STALE
    assert result.governance_event.affected_dag_node_ids


def test_withdrawn_source_triggers_review_and_reissue_recommendation() -> None:
    source_ref = _ref("1")
    impact = propagate_source_invalidation(
        _dag(source_ref),
        SourceInvalidationEvent(
            event_id="source_invalid_1",
            source_ref=source_ref,
            invalidation_type="withdrawn",
            reason="Source was withdrawn.",
        ),
    )
    ledger = AppendOnlyClaimLedger(run_id="run_continuous", current_claims=[_claim()])

    result = mark_dependent_claims_stale(
        ledger=ledger,
        decision_packet_ref=_ref("2", kind="scientist.decision_packet"),
        impact=impact,
        actor_id="continuous_governance.monitor",
    )

    assert result.lifecycle_events[0].action is ClaimLifecycleAction.INVALIDATED
    assert result.recommendation.reissue_recommended is True
    assert result.recommendation.human_review_required is True


def test_source_invalidation_without_lineage_cannot_silently_pass() -> None:
    event = SourceInvalidationEvent(
        event_id="source_invalid_orphan",
        source_ref=_ref("1"),
        invalidation_type="stale",
        reason="Source changed.",
    )
    impact = SourceInvalidationImpact(
        run_id="run_continuous",
        workflow_id="scientist_policy_design",
        event=event,
        affected_node_ids=[],
        stale_claim_ids=[],
        claim_lifecycle_action=ClaimLifecycleAction.MARKED_STALE,
    )

    with pytest.raises(ValueError, match="affected claim or DAG lineage"):
        governance_event_from_source_invalidation(
            decision_packet_ref=_ref("2", kind="scientist.decision_packet"),
            impact=impact,
        )


def test_monitor_result_validation_keeps_updated_ledger_typed() -> None:
    with pytest.raises(ValidationError):
        AppendOnlyClaimLedger(run_id="", current_claims=[])
