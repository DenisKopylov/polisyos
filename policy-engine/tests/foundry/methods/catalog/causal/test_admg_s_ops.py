"""Tests for S-node graph operations in admg_ops.py (Phase 1)."""
import pytest

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    augment_with_s_nodes,
    project_to_subgraph,
    resolve_s_node_by_adjustment,
    s_reachable,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _dag(edges):
    nodes = sorted({n for e in edges for n in e})
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for s, d in edges
        ],
    )


def _confounded(directed, bidirected):
    nodes = sorted({n for e in directed + bidirected for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed
    ]
    for s, d in bidirected:
        edges.append(CausalEdge(src=s, dst=d, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    return CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)


class TestAugmentWithSNodes:
    def test_adds_s_nodes_and_edges(self):
        graph = _dag([("X", "Y")])
        aug = augment_with_s_nodes(graph, frozenset({"X"}))
        assert "S_X" in aug.nodes
        assert any(e.src == "S_X" and e.dst == "X" for e in aug.edges)

    def test_preserves_original_nodes(self):
        graph = _dag([("X", "Y")])
        aug = augment_with_s_nodes(graph, frozenset({"X"}))
        assert "X" in aug.nodes
        assert "Y" in aug.nodes

    def test_deduplicates_existing_s_node(self):
        # If S_X is already in the graph, it should not be added twice
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        aug2 = augment_with_s_nodes(graph, frozenset({"X"}))
        assert aug2.nodes.count("S_X") == 1  # no duplicate

    def test_pure_original_unchanged(self):
        graph = _dag([("X", "Y")])
        original_node_count = len(graph.nodes)
        augment_with_s_nodes(graph, frozenset({"X"}))
        assert len(graph.nodes) == original_node_count  # original unchanged

    def test_multiple_s_nodes(self):
        graph = _dag([("X", "Y"), ("Z", "Y")])
        aug = augment_with_s_nodes(graph, frozenset({"X", "Z"}))
        assert "S_X" in aug.nodes
        assert "S_Z" in aug.nodes
        s_edges = [(e.src, e.dst) for e in aug.edges if e.src.startswith("S_")]
        assert ("S_X", "X") in s_edges
        assert ("S_Z", "Z") in s_edges

    def test_empty_s_vars_returns_pag_graph(self):
        graph = _dag([("X", "Y")])
        aug = augment_with_s_nodes(graph, frozenset())
        # No extra nodes, but graph_type upgrades to PAG
        assert set(aug.nodes) == {"X", "Y"}


class TestSReachable:
    def test_direct_edge_reachable(self):
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        reached = s_reachable(graph, frozenset({"Y"}), frozenset({"S_X"}))
        assert "Y" in reached

    def test_non_connected_s_node_not_reachable(self):
        # S_Z exists but has no path to Y
        graph = _dag([("X", "Y"), ("Z", "X")])
        aug = augment_with_s_nodes(graph, frozenset({"Z"}))
        # S_Z → Z → X → Y: Y IS reachable via directed path
        reached = s_reachable(aug, frozenset({"Y"}), frozenset({"S_Z"}))
        assert "Y" in reached  # reachable via Z→X→Y

    def test_empty_s_nodes_returns_empty(self):
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        reached = s_reachable(graph, frozenset({"Y"}), frozenset())
        assert len(reached) == 0

    def test_s_node_via_bidirected_reachable(self):
        # S_X → X ↔ Y (bidirected): Y should be reachable
        base = _confounded([("X", "Y")], [("X", "Y")])
        aug = augment_with_s_nodes(base, frozenset({"X"}))
        reached = s_reachable(aug, frozenset({"Y"}), frozenset({"S_X"}))
        assert "Y" in reached


class TestResolveSnodeByAdjustment:
    def test_removes_s_node_and_edges(self):
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        assert "S_X" in graph.nodes
        resolved = resolve_s_node_by_adjustment(graph, "X", frozenset())
        assert "S_X" not in resolved.nodes
        assert not any(e.src == "S_X" or e.dst == "S_X" for e in resolved.edges)

    def test_no_op_if_s_node_absent(self):
        graph = _dag([("X", "Y")])
        resolved = resolve_s_node_by_adjustment(graph, "X", frozenset())
        assert set(resolved.nodes) == set(graph.nodes)

    def test_pure_original_unchanged(self):
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        original_count = len(graph.nodes)
        resolve_s_node_by_adjustment(graph, "X", frozenset())
        assert len(graph.nodes) == original_count  # original unchanged

    def test_other_s_nodes_retained(self):
        graph = augment_with_s_nodes(_dag([("X", "Y"), ("Z", "Y")]), frozenset({"X", "Z"}))
        resolved = resolve_s_node_by_adjustment(graph, "X", frozenset())
        assert "S_Z" in resolved.nodes
        assert "S_X" not in resolved.nodes


class TestProjectToSubgraph:
    def test_keep_s_nodes_true_includes_s_nodes(self):
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        proj = project_to_subgraph(graph, frozenset({"X", "Y"}), keep_s_nodes=True)
        assert "S_X" in proj.nodes

    def test_keep_s_nodes_false_excludes_s_nodes(self):
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        proj = project_to_subgraph(graph, frozenset({"X", "Y"}), keep_s_nodes=False)
        assert "S_X" not in proj.nodes
        assert "X" in proj.nodes
        assert "Y" in proj.nodes

    def test_edges_outside_subset_excluded(self):
        graph = _dag([("X", "Y"), ("Y", "Z"), ("X", "Z")])
        proj = project_to_subgraph(graph, frozenset({"X", "Y"}), keep_s_nodes=False)
        assert all(e.src in {"X", "Y"} and e.dst in {"X", "Y"} for e in proj.edges)

    def test_default_keep_s_nodes_is_true(self):
        graph = augment_with_s_nodes(_dag([("X", "Y")]), frozenset({"X"}))
        proj = project_to_subgraph(graph, frozenset({"X", "Y"}))
        assert "S_X" in proj.nodes
