from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.graph_reconciliation import (
    MAX_RECON_EDGES,
    ReconcileCausalGraph,
)
from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData, LLMStructuralHint
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType
from polisyos.ir.analytics.literature import LiteratureCausalPrior, LiteratureEdgePrior


def _data_edge(
    src: str,
    dst: str,
    *,
    confidence: float,
    lag: int | None = None,
    metadata: dict | None = None,
) -> CausalEdge:
    return CausalEdge(
        src=src,
        dst=dst,
        lag=lag,
        sources=[EdgeSource.DATA],
        data_confidence=confidence,
        combined_confidence=confidence,
        metadata=metadata or {},
    )


def _graph(nodes: list[str], edges: list[CausalEdge], *, graph_type: GraphType = GraphType.DAG) -> CausalGraphModel:
    return CausalGraphModel(graph_type=graph_type, nodes=nodes, edges=edges)


def test_literature_and_data_agreement_increases_combined_confidence() -> None:
    data_graph = _graph(["X", "Y"], [_data_edge("X", "Y", confidence=0.7)])
    prior = LiteratureCausalPrior(
        edges=[LiteratureEdgePrior(src="X", dst="Y", confidence=0.6)],
    )
    payload = GraphReconciliationData(data_graph=data_graph, literature_prior=prior, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    edge = next(item for item in result["reconciled_graph"].edges if item.src == "X" and item.dst == "Y")

    assert edge.combined_confidence is not None
    assert edge.combined_confidence > 0.7
    assert edge.combined_confidence > 0.6


def test_data_wins_when_direction_conflicts_with_literature() -> None:
    data_graph = _graph(["A", "B"], [_data_edge("A", "B", confidence=0.9)])
    prior = LiteratureCausalPrior(
        edges=[LiteratureEdgePrior(src="B", dst="A", confidence=0.8)],
    )
    payload = GraphReconciliationData(data_graph=data_graph, literature_prior=prior, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    pairs = {(edge.src, edge.dst) for edge in result["reconciled_graph"].edges}

    assert ("A", "B") in pairs
    assert ("B", "A") not in pairs


def test_llm_only_hint_is_marked_unsupported_and_capped() -> None:
    data_graph = _graph(["A", "B"], [])
    payload = GraphReconciliationData(
        data_graph=data_graph,
        llm_hints=[LLMStructuralHint(src="A", dst="B", confidence=0.95)],
        min_edge_confidence=0.0,
    )

    result = ReconcileCausalGraph.pure_step(payload, params={})
    edge = next(item for item in result["reconciled_graph"].edges if item.src == "A" and item.dst == "B")

    assert edge.unsupported_by_evidence is True
    assert edge.combined_confidence is not None
    assert edge.combined_confidence <= 0.3


def test_simple_cycle_converts_min_confidence_edge_to_lagged_edge() -> None:
    data_graph = _graph(
        ["A", "B", "C"],
        [
            _data_edge("A", "B", confidence=0.9),
            _data_edge("B", "C", confidence=0.8),
            _data_edge("C", "A", confidence=0.2),
        ],
        graph_type=GraphType.CPDAG,
    )
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    edges = result["reconciled_graph"].edges
    lagged = [edge for edge in edges if edge.dst == "A" and edge.lag == 1]

    assert lagged
    assert any(edge.src.startswith("C_t-1") for edge in lagged)


def test_more_than_eight_cycles_triggers_fallback_removal_warning() -> None:
    nodes: list[str] = []
    edges: list[CausalEdge] = []
    for idx in range(9):
        a = f"A{idx}"
        b = f"B{idx}"
        c = f"C{idx}"
        nodes.extend([a, b, c])
        edges.extend(
            [
                _data_edge(a, b, confidence=0.9),
                _data_edge(b, c, confidence=0.8),
                _data_edge(c, a, confidence=0.1),
            ]
        )
    data_graph = _graph(nodes, edges, graph_type=GraphType.CPDAG)
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    warnings = [str(item).lower() for item in result["warnings"]]

    assert any("cycle resolution budget exceeded" in warning for warning in warnings)
    assert any("fallback removal" in warning for warning in warnings)


def test_cycle_edge_with_lag_depth_limit_is_removed() -> None:
    data_graph = _graph(
        ["A", "B", "C"],
        [
            _data_edge("A", "B", confidence=0.9),
            _data_edge("B", "C", confidence=0.8),
            _data_edge("C", "A", confidence=0.1, lag=2),
        ],
        graph_type=GraphType.CPDAG,
    )
    payload = GraphReconciliationData(
        data_graph=data_graph,
        min_edge_confidence=0.0,
        max_lag_depth=2,
    )

    result = ReconcileCausalGraph.pure_step(payload, params={})
    pairs = {(edge.src, edge.dst, edge.lag) for edge in result["reconciled_graph"].edges}

    assert ("C", "A", 2) not in pairs


def test_triangle_conflict_produces_positive_cyclic_inconsistency_norm() -> None:
    data_graph = _graph(
        ["A", "B", "C"],
        [
            _data_edge("A", "B", confidence=0.8),
            _data_edge("B", "C", confidence=0.9),
            _data_edge("A", "C", confidence=0.2),
        ],
    )
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    diagnostics = result["diagnostics"]

    assert diagnostics.cyclic_inconsistency_norm > 0.0


def test_irreducible_conflict_triggers_expert_review_flag() -> None:
    data_graph = _graph(["A", "B"], [_data_edge("A", "B", confidence=0.9)])
    payload = GraphReconciliationData(
        data_graph=data_graph,
        llm_hints=[LLMStructuralHint(src="B", dst="A", confidence=0.9)],
        min_edge_confidence=0.0,
    )

    result = ReconcileCausalGraph.pure_step(payload, params={})

    assert result["diagnostics"].irreducible_conflict_norm > 0.5
    assert result["needs_expert_review"] is True
    assert result["reconciled_graph"].metadata["needs_expert_review"] is True


def test_diagnostics_truncated_when_hard_limits_exceeded() -> None:
    nodes = [f"N{i}" for i in range(MAX_RECON_EDGES + 3)]
    edges = [
        _data_edge(nodes[idx], nodes[idx + 1], confidence=0.55)
        for idx in range(MAX_RECON_EDGES + 2)
    ]
    data_graph = _graph(nodes, edges, graph_type=GraphType.CPDAG)
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    diagnostics = result["diagnostics"]

    assert diagnostics.diagnostics_truncated is True
    assert diagnostics.truncation_reason is not None
