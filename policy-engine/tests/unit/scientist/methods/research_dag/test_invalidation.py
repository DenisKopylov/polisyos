from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
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


def _ref(
    suffix: str,
    *,
    kind: str = "scientist.source",
    media_type: str = "application/json",
    profile: str | None = None,
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type=media_type,
        manifest_profile_sha256=profile,
    )


def _claim(claim_id: str = "claim_1", *, source_ref: ArtifactRef | None = None) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run_invalid",
        claim_type=ClaimType.FACTUAL,
        text="Claim text.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[source_ref or _ref("1")],
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


def test_source_invalidation_selects_only_exact_artifact_view() -> None:
    profile_a = "sha256:" + "a" * 64
    profile_b = "sha256:" + "b" * 64
    source_a = _ref("1", profile=profile_a)
    source_b = _ref("1", profile=profile_b)
    builder = ResearchDAGBuilder(run_id="run_invalid", workflow_id="scientist_policy_design")
    node_a = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Read source view A.",
        artifact_refs=[source_a],
        claim_ids=["claim_a"],
    )
    node_b = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Read source view B.",
        artifact_refs=[source_b],
        claim_ids=["claim_b"],
    )
    dag = builder.artifact()

    impact = propagate_source_invalidation(
        dag,
        SourceInvalidationEvent(
            event_id="source_invalid_exact",
            source_ref=source_a,
            invalidation_type="stale",
            reason="The selected source view changed.",
        ),
    )

    assert impact.source_node_ids == [node_a.node_id]
    assert node_b.node_id not in impact.affected_node_ids
    assert impact.stale_claim_ids == ["claim_a"]
    with pytest.raises(ValueError, match="source_ref is not present"):
        propagate_source_invalidation(
            _dag(source_a),
            SourceInvalidationEvent(
                event_id="source_invalid_profile_b",
                source_ref=source_b,
                invalidation_type="stale",
                reason="Source view B is absent.",
            ),
        )
    for alias in (
        _ref("1", kind="scientist.other", profile=profile_a),
        _ref("1", media_type="text/plain", profile=profile_a),
        _ref("1"),
    ):
        event = SourceInvalidationEvent(
            event_id="source_invalid_alias",
            source_ref=alias,
            invalidation_type="stale",
            reason="A different source view changed.",
        )
        with pytest.raises(ValueError, match="source_ref is not present"):
            propagate_source_invalidation(dag, event)


def _branched_dag(common_ref: ArtifactRef, independent_ref: ArtifactRef):
    builder = ResearchDAGBuilder(run_id="run_invalid", workflow_id="scientist_policy_design")
    common = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Read common source.",
        artifact_refs=[common_ref],
    )
    dependent_a = builder.add_node(
        node_type=ResearchNodeType.EXTRACTION,
        producer="extractor",
        summary="First dependent output.",
        claim_ids=["claim_a"],
    )
    dependent_b = builder.add_node(
        node_type=ResearchNodeType.SYNTHESIS,
        producer="synthesizer",
        summary="Second dependent output.",
        claim_ids=["claim_b"],
    )
    independent = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Independent output.",
        artifact_refs=[independent_ref],
        claim_ids=["claim_independent"],
    )
    for target, claim_id in ((dependent_a, "claim_a"), (dependent_b, "claim_b")):
        builder.add_edge(
            source_node_id=common.node_id,
            target_node_id=target.node_id,
            edge_type=ResearchEdgeType.SUPPORTS,
            claim_ids=[claim_id],
        )
    return builder.artifact(), common, independent


def test_common_source_invalidation_preserves_independent_claim_and_ledger_prefix() -> None:
    common_ref = _ref("1")
    dag, common, independent = _branched_dag(common_ref, _ref("2"))
    impact = propagate_source_invalidation(
        dag,
        SourceInvalidationEvent(
            event_id="source_invalid_common",
            source_ref=common_ref,
            invalidation_type="withdrawn",
            reason="Common source was withdrawn.",
        ),
    )
    claims = [
        _claim("claim_a"),
        _claim("claim_b"),
        _claim("claim_independent", source_ref=_ref("2")),
    ]
    prefix = ClaimLifecycleEvent(
        event_id="existing_event",
        claim_id="claim_independent",
        run_id="run_invalid",
        action=ClaimLifecycleAction.REVIEWED,
        occurred_at=datetime(2026, 4, 27, tzinfo=UTC),
        actor_id="reviewer",
        reason="Independent claim was reviewed.",
    )
    ledger = AppendOnlyClaimLedger(run_id="run_invalid", current_claims=claims, events=[prefix])
    updated = append_invalidation_events_to_ledger(
        ledger,
        impact,
        actor_id="replay.invalidation",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
    )

    assert impact.source_node_ids == [common.node_id]
    assert independent.node_id not in impact.affected_node_ids
    assert impact.stale_claim_ids == ["claim_a", "claim_b"]
    assert updated.events[0] == prefix
    assert [event.claim_id for event in updated.events[1:]] == ["claim_a", "claim_b"]


def test_present_unrelated_explicit_targets_cannot_expand_invalidation() -> None:
    common_ref = _ref("1")
    dag, _, independent = _branched_dag(common_ref, _ref("2"))
    for node_ids, claim_ids in (
        ([independent.node_id], []),
        ([], ["claim_independent"]),
    ):
        event = SourceInvalidationEvent(
            event_id="source_invalid_false_target",
            source_ref=common_ref,
            invalidation_type="stale",
            affected_node_ids=node_ids,
            affected_claim_ids=claim_ids,
            reason="Caller selected an unrelated present sibling.",
        )
        with pytest.raises(ValueError, match="outside the source-derived closure"):
            propagate_source_invalidation(dag, event)
