"""Regression witnesses for GRF-03 graph direction and temporal semantics."""

from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal._graph_projection import (
    pag_to_dag_projection,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)


def test_projection_normalizes_known_reversed_edge_without_losing_marks() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.ARROW,
                mark_dst=EdgeMark.TAIL,
            )
        ],
    )

    projected, latent_vars = pag_to_dag_projection(graph)

    assert latent_vars == []
    assert projected.graph_type is GraphType.DAG
    assert len(projected.edges) == 1
    edge = projected.edges[0]
    assert (edge.src, edge.dst) == ("Y", "X")
    assert (edge.mark_src, edge.mark_dst) == (EdgeMark.TAIL, EdgeMark.ARROW)
    assert edge.metadata["orientation_normalized"] is True
    assert edge.metadata["original_marks"] == [EdgeMark.ARROW.value, EdgeMark.TAIL.value]


def test_projection_rejects_unresolved_cpdag_triangle_instead_of_labeling_cycle_dag() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["A", "B", "C"],
        edges=[
            CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.TAIL),
            CausalEdge(src="B", dst="C", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.TAIL),
            CausalEdge(src="C", dst="A", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.TAIL),
        ],
    )

    with pytest.raises(ValueError, match="unresolved|partial|orientation"):
        pag_to_dag_projection(graph)


def test_temporal_round_trip_preserves_distinct_lags_in_dot_and_model_payload() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", lag=1),
            CausalEdge(src="X", dst="Y", lag=2),
        ],
    )

    restored = CausalGraphModel.model_validate(graph.model_dump(mode="json"))
    assert sorted(edge.lag for edge in restored.edges) == [1, 2]

    dot = restored.to_dot()
    assert '[lag="1"' in dot
    assert '[lag="2"' in dot


def test_positive_lagged_self_edge_is_temporal_but_zero_lag_self_loop_is_rejected() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X"],
        edges=[CausalEdge(src="X", dst="X", lag=1)],
    )
    assert graph.edges[0].lag == 1

    with pytest.raises(ValueError, match="zero-lag|self-loop"):
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X"],
            edges=[CausalEdge(src="X", dst="X", lag=0)],
        )


def test_static_dag_projection_remains_identity() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )

    projected, latent_vars = pag_to_dag_projection(graph)

    assert projected is graph
    assert latent_vars == []
    assert '"X" -> "Y";' in projected.to_dot()
    assert "lag=" not in projected.to_dot()
