from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.methods.research_dag.comparison import (
    compare_research_trajectories,
    public_comparison_export,
)
from polisyos.scientist.methods.research_dag.diff import diff_research_dags
from polisyos.scientist.methods.research_dag.models import ResearchNodeType


def _ref(suffix: str, *, kind: str = "scientist.source") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
    )


def _dag(
    *,
    run_id: str,
    query: str,
    source_ref: ArtifactRef,
    snippet_id: str,
    claim_id: str,
    verdict: str,
):
    builder = ResearchDAGBuilder(run_id=run_id, workflow_id="scientist_causal_full")
    builder.add_node(
        node_type=ResearchNodeType.QUESTION,
        producer="planner",
        summary=query,
        metadata={"query": query},
    )
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Read source.",
        artifact_refs=[source_ref],
    )
    builder.add_node(
        node_type=ResearchNodeType.EXTRACTION,
        producer="extractor",
        summary="Extract snippet.",
        metadata={"snippet_id": snippet_id},
        claim_ids=[claim_id],
    )
    builder.add_node(
        node_type=ResearchNodeType.SYNTHESIS,
        producer="synthesizer",
        summary="Synthesize claim.",
        claim_ids=[claim_id],
    )
    builder.add_node(
        node_type=ResearchNodeType.GOVERNANCE,
        producer="governance",
        summary=f"Governance {verdict}",
        metadata={"verdict": verdict},
    )
    return builder.artifact()


def test_diff_reports_queries_sources_snippets_claims_and_governance() -> None:
    old = _dag(
        run_id="old",
        query="old query",
        source_ref=_ref("1"),
        snippet_id="snippet_old",
        claim_id="claim_old",
        verdict="warn",
    )
    new = _dag(
        run_id="new",
        query="new query",
        source_ref=_ref("2"),
        snippet_id="snippet_new",
        claim_id="claim_new",
        verdict="pass",
    )

    diff = diff_research_dags(old, new)

    assert "added:new query" in diff.changed_queries
    assert any(item.startswith("added:sha256:" + "2" * 64) for item in diff.changed_sources)
    assert "added:snippet_new" in diff.changed_snippets
    assert "added:claim_new" in diff.changed_claim_ids
    assert any("pass" in item for item in diff.changed_governance_outcomes)


def test_comparison_report_explains_changed_research_trajectory() -> None:
    old = _dag(
        run_id="old",
        query="old query",
        source_ref=_ref("1"),
        snippet_id="snippet_old",
        claim_id="claim_old",
        verdict="warn",
    )
    new = _dag(
        run_id="new",
        query="new query",
        source_ref=_ref("2"),
        snippet_id="snippet_new",
        claim_id="claim_new",
        verdict="pass",
    )

    report = compare_research_trajectories(old, new)

    assert report.workflow_id == "scientist_causal_full"
    assert report.metadata["changed_categories"] == [
        "queries",
        "sources",
        "snippets",
        "claims",
        "governance",
    ]
    assert "Research trajectory changed" in report.explanation


def test_public_comparison_export_does_not_include_hidden_refs() -> None:
    old = _dag(
        run_id="old",
        query="old query",
        source_ref=_ref("1"),
        snippet_id="snippet_old",
        claim_id="claim_old",
        verdict="warn",
    )
    hidden_ref = _ref("9", kind="scientist.hidden_benchmark.answer")
    new = _dag(
        run_id="new",
        query="old query",
        source_ref=hidden_ref,
        snippet_id="snippet_old",
        claim_id="claim_old",
        verdict="warn",
    )

    export_json = str(public_comparison_export(compare_research_trajectories(old, new)))

    assert str(hidden_ref.artifact_id) not in export_json
    assert "hidden_benchmark" not in export_json


def test_public_comparison_export_redacts_hidden_node_text() -> None:
    old = _dag(
        run_id="old",
        query="old query",
        source_ref=_ref("1"),
        snippet_id="snippet_old",
        claim_id="claim_old",
        verdict="warn",
    )
    hidden_ref = _ref("9", kind="scientist.hidden_benchmark.answer")
    hidden_builder = ResearchDAGBuilder(run_id="new", workflow_id="scientist_causal_full")
    hidden_builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="hidden_eval",
        summary="hidden_benchmark answer read.",
        artifact_refs=[hidden_ref],
    )

    export_json = str(
        public_comparison_export(compare_research_trajectories(old, hidden_builder.artifact()))
    )

    assert str(hidden_ref.artifact_id) not in export_json
    assert "hidden_eval" not in export_json
    assert "hidden_benchmark" not in export_json
    assert "redacted_source" in export_json
