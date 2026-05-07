from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.methods.research_dag.diff import diff_research_dags
from polisyos.scientist.methods.research_dag.models import ResearchNodeType


def _ref(suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.source",
        media_type="application/json",
    )


def _dag(*, run_id: str, source_ref: ArtifactRef, claim_id: str, verdict: str):
    builder = ResearchDAGBuilder(run_id=run_id, workflow_id="scientist_causal_full")
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_ACQUISITION,
        producer="search",
        summary="Acquire source.",
        artifact_refs=[source_ref],
    )
    builder.add_node(
        node_type=ResearchNodeType.SYNTHESIS,
        producer="causal",
        summary="Causal synthesis.",
        claim_ids=[claim_id],
    )
    builder.add_node(
        node_type=ResearchNodeType.GOVERNANCE,
        producer="governance",
        summary=f"Governance {verdict}",
        metadata={"verdict": verdict},
    )
    return builder.artifact()


def test_diff_shows_changed_sources_claims_and_governance() -> None:
    old = _dag(run_id="old", source_ref=_ref("1"), claim_id="claim_old", verdict="warn")
    new = _dag(run_id="new", source_ref=_ref("2"), claim_id="claim_new", verdict="pass")

    diff = diff_research_dags(old, new)

    assert any(item.startswith("added:sha256:" + "2" * 64) for item in diff.changed_sources)
    assert "added:claim_new" in diff.changed_claim_ids
    assert "removed:claim_old" in diff.changed_claim_ids
    assert any("pass" in item for item in diff.changed_governance_outcomes)
