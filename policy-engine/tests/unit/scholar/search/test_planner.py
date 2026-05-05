"""Tests for Scholar research-brief and query-graph planning."""

from __future__ import annotations

from polisyos.core.contracts.scholar import ResearchIntent
from polisyos.scholar.search.planner import (
    apply_adaptive_query_reformulation,
    build_research_brief,
    plan_query_graph,
)


def test_build_research_brief_from_intent_uses_domain_perspectives():
    brief = build_research_brief(
        intent=ResearchIntent(
            domain="labor",
            topic="minimum wage effects on youth employment",
            jurisdiction="United States",
            seed_sources=[],
        ),
        locale="en-US",
    )

    assert brief.question == "minimum wage effects on youth employment"
    assert brief.domain == "labor"
    assert "United States" in brief.jurisdictions
    assert "official labor regulation" in brief.perspectives
    assert "academic" in brief.required_source_types
    assert "dol.gov" in brief.preferred_domains


def test_plan_query_graph_expands_perspectives_and_jurisdictions():
    brief = build_research_brief(
        question="carbon border adjustment fiscal impact",
        locale="en-US",
        perspectives=["official policy source", "cross-jurisdiction comparison"],
    )
    graph = plan_query_graph(brief, max_depth=1, per_perspective_queries=2)

    assert len(graph.root_node_ids) == 1
    assert len(graph.nodes) >= 5
    assert any(node.perspective == "official policy source" for node in graph.nodes)
    assert any("site:" in node.query for node in graph.nodes if node.depth == 1)


def test_apply_adaptive_query_reformulation_adds_children_for_low_yield_node():
    brief = build_research_brief(question="land value tax pilot evaluation")
    graph = plan_query_graph(brief, max_depth=1, per_perspective_queries=1)
    root_node_id = graph.root_node_ids[0]
    root = graph.node_by_id(root_node_id)
    root.hit_count = 0

    children = apply_adaptive_query_reformulation(
        graph,
        node_id=root_node_id,
        min_hit_count=2,
        max_children=2,
    )

    assert len(children) >= 1
    assert all(child.parent_id == root_node_id for child in children)
    assert all(child.depth == 1 for child in children)
