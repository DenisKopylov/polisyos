"""Tests for KnowledgeToolkit web-evidence prompt formatting."""

from __future__ import annotations

from polisyos.scholar.search.models import (
    ClaimSupportLink,
    QueryGraph,
    ResearchBrief,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
)
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit


def test_format_web_evidence_context_renders_citations_and_spans():
    brief = ResearchBrief(question="minimum wage effect", locale="en-US")
    graph = QueryGraph(brief=brief)
    bundle = WebEvidenceBundle(
        bundle_id="webkb.test",
        brief=brief,
        query_graph=graph,
        sources=[
            SourceMetadata(
                source_id="src.1",
                url="https://agency.gov/report",
                title="Agency report",
                domain="agency.gov",
                quality_score=0.9,
            )
        ],
        snippets=[
            SourceSnippet(
                snippet_id="snip.1",
                source_id="src.1",
                url="https://agency.gov/report",
                query_node_id="q.root",
                perspective="overview",
                text="Minimum wage increased earnings for low-wage workers.",
                start_char=12,
                end_char=64,
                relevance_score=0.8,
            )
        ],
        claim_supports=[
            ClaimSupportLink(
                claim_id="claim.1",
                claim_text="minimum wage increased earnings",
                snippet_ids=["snip.1"],
                source_ids=["src.1"],
                support_score=0.8,
            )
        ],
        uncertainty_notes=["conflicting-source-claims"],
    )

    text = KnowledgeToolkit().format_web_evidence_context(bundle)

    assert "## WEB EVIDENCE" in text
    assert "- Claim: minimum wage increased earnings" in text
    assert "[Agency report](https://agency.gov/report)" in text
    assert "[12:64]" in text
    assert "conflicting-source-claims" in text
