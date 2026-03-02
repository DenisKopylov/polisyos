from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
    PAGIdentificationPolicy,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.refs import CausalGraphModelRef


def _minimal_dag() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="Z", dst="X"),
            CausalEdge(src="Z", dst="Y"),
            CausalEdge(src="X", dst="Y"),
        ],
        discovery_method="manual",
    )


def test_causal_graph_valid_dag_cpdag_pag() -> None:
    dag = _minimal_dag()
    assert dag.graph_type is GraphType.DAG

    cpdag = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["A", "B"],
        edges=[CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.TAIL)],
    )
    assert cpdag.graph_type is GraphType.CPDAG

    pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["M", "N"],
        edges=[CausalEdge(src="M", dst="N", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
    )
    assert pag.graph_type is GraphType.PAG


def test_causal_graph_rejects_unknown_nodes_in_edges() -> None:
    with pytest.raises(ValueError, match="not in nodes"):
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Z")],
        )


def test_causal_graph_rejects_duplicate_nodes() -> None:
    with pytest.raises(ValueError, match="nodes must be unique"):
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "X"],
            edges=[],
        )


def test_causal_graph_rejects_invalid_marks_for_dag() -> None:
    with pytest.raises(ValueError, match="DAG requires oriented edges"):
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.TAIL)],
        )


def test_causal_graph_rejects_dag_cycle() -> None:
    with pytest.raises(ValueError, match="acyclic"):
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["A", "B"],
            edges=[CausalEdge(src="A", dst="B"), CausalEdge(src="B", dst="A")],
        )


def test_causal_graph_accepts_lagged_reciprocal_edges_in_dag() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", lag=1),
            CausalEdge(src="Y", dst="X", lag=1),
        ],
    )
    assert graph.graph_type is GraphType.DAG
    assert len(graph.edges) == 2


def test_causal_graph_rejects_contemporaneous_cycle_even_with_lagged_edges() -> None:
    with pytest.raises(ValueError, match="acyclic"):
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["A", "B"],
            edges=[
                CausalEdge(src="A", dst="B"),
                CausalEdge(src="B", dst="A"),
                CausalEdge(src="A", dst="B", lag=1),
            ],
        )


def test_causal_edge_combined_confidence_monotonicity() -> None:
    one_source = CausalEdge(
        src="X",
        dst="Y",
        sources=[EdgeSource.DATA],
        data_confidence=0.6,
    )
    two_sources = CausalEdge(
        src="X",
        dst="Y",
        sources=[EdgeSource.DATA, EdgeSource.LITERATURE],
        data_confidence=0.6,
        literature_confidence=0.7,
    )
    assert two_sources.compute_combined_confidence() > one_source.compute_combined_confidence()


def test_causal_graph_to_dot_success_for_dag() -> None:
    dot = _minimal_dag().to_dot()
    assert dot.startswith("digraph {")
    assert '"X" -> "Y";' in dot


def test_causal_graph_to_dot_rejects_non_dag() -> None:
    pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["M", "N"],
        edges=[CausalEdge(src="M", dst="N", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
    )
    with pytest.raises(ValueError, match="only supported for DAG"):
        pag.to_dot()


def test_causal_graph_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    graph = _minimal_dag()

    ref = persist_causal_graph_model(store, graph)
    loaded = load_causal_graph_model(store, ref)

    assert isinstance(ref, CausalGraphModelRef)
    assert ref.kind == "ir.causal_graph_model"
    assert loaded == graph


def test_causal_graph_pag_policy_defaults_to_conservative() -> None:
    graph = _minimal_dag()
    assert graph.pag_identification_policy is PAGIdentificationPolicy.CONSERVATIVE
    assert graph.id_confidence_under_pag is None


def test_causal_graph_probabilistic_pag_policy_accepts_id_confidence() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
        pag_identification_policy=PAGIdentificationPolicy.PROBABILISTIC,
        id_confidence_under_pag=0.7,
    )
    assert graph.id_confidence_under_pag == pytest.approx(0.7)


def test_causal_graph_rejects_id_confidence_for_non_probabilistic_pag_policy() -> None:
    with pytest.raises(ValueError, match="only allowed"):
        CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
            pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
            id_confidence_under_pag=0.6,
        )


def test_causal_graph_rejects_out_of_range_id_confidence() -> None:
    with pytest.raises(ValueError, match="must be in \\[0,1\\]"):
        CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
            pag_identification_policy=PAGIdentificationPolicy.PROBABILISTIC,
            id_confidence_under_pag=1.2,
        )
