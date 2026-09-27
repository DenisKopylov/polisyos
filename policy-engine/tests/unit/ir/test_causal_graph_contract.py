from __future__ import annotations

from itertools import permutations

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
from polisyos.ir.registry.refs import CausalGraphModelRef


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


def _mixed_edge_variants(order: tuple[str, ...]) -> list[CausalEdge]:
    """Build adversarial same-endpoint edge variants without using production logic."""
    by_kind = {
        "directed": CausalEdge(
            src="X",
            dst="Y",
            mark_src=EdgeMark.TAIL,
            mark_dst=EdgeMark.ARROW,
            metadata={"relation": "directed"},
        ),
        "bidirected": CausalEdge(
            src="X",
            dst="Y",
            mark_src=EdgeMark.ARROW,
            mark_dst=EdgeMark.ARROW,
            metadata={"relation": "bidirected"},
        ),
        "lag1": CausalEdge(
            src="X",
            dst="Y",
            mark_src=EdgeMark.TAIL,
            mark_dst=EdgeMark.ARROW,
            lag=1,
            metadata={"relation": "lag1"},
        ),
        "lag2": CausalEdge(
            src="X",
            dst="Y",
            mark_src=EdgeMark.TAIL,
            mark_dst=EdgeMark.ARROW,
            lag=2,
            metadata={"relation": "lag2"},
        ),
        "same_alpha": CausalEdge(
            src="X",
            dst="Y",
            mark_src=EdgeMark.TAIL,
            mark_dst=EdgeMark.ARROW,
            metadata={"relation": "same-alpha"},
        ),
        "same_alpha_duplicate": CausalEdge(
            src="X",
            dst="Y",
            mark_src=EdgeMark.TAIL,
            mark_dst=EdgeMark.ARROW,
            metadata={"relation": "same-alpha"},
        ),
        "same_zeta": CausalEdge(
            src="X",
            dst="Y",
            mark_src=EdgeMark.TAIL,
            mark_dst=EdgeMark.ARROW,
            metadata={"relation": "same-zeta"},
        ),
    }
    return [by_kind[kind] for kind in order]


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


@pytest.mark.parametrize(
    "edge_order",
    [
        *permutations(("directed", "bidirected")),
        *permutations(("lag1", "lag2")),
    ],
    ids=(
        "directed-before-bidirected",
        "bidirected-before-directed",
        "lag1-before-lag2",
        "lag2-before-lag1",
    ),
)
def test_causal_graph_networkx_preserves_mixed_edge_identity(
    edge_order: tuple[str, ...],
) -> None:
    """Each same-endpoint relation survives export independent of insertion order."""
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=_mixed_edge_variants(edge_order),
    )

    exported = graph.to_networkx()
    assert exported.is_directed()
    assert exported.is_multigraph()
    observed_key_to_relation = {
        key: (
            src,
            dst,
            data["mark_src"],
            data["mark_dst"],
            data["lag"],
            data["metadata"]["relation"],
        )
        for src, dst, key, data in exported.edges(keys=True, data=True)
    }

    expected_by_kind = {
        "directed": ("X", "Y", "tail", "arrow", None, "directed"),
        "bidirected": ("X", "Y", "arrow", "arrow", None, "bidirected"),
        "lag1": ("X", "Y", "tail", "arrow", 1, "lag1"),
        "lag2": ("X", "Y", "tail", "arrow", 2, "lag2"),
    }
    expected_key_by_kind = {
        "directed": ("tail", "arrow", None, 0),
        "bidirected": ("arrow", "arrow", None, 0),
        "lag1": ("tail", "arrow", 1, 0),
        "lag2": ("tail", "arrow", 2, 0),
    }
    assert observed_key_to_relation == {
        expected_key_by_kind[kind]: expected_by_kind[kind] for kind in edge_order
    }


@pytest.mark.parametrize(
    "edge_order",
    list(permutations(("same_alpha", "same_alpha_duplicate", "same_zeta"))),
    ids=(
        "alpha-alpha-duplicate-zeta",
        "alpha-zeta-alpha-duplicate",
        "alpha-duplicate-alpha-zeta",
        "alpha-duplicate-zeta-alpha",
        "zeta-alpha-alpha-duplicate",
        "zeta-alpha-duplicate-alpha",
    ),
)
def test_causal_graph_networkx_keys_same_relation_payloads_collision_safely(
    edge_order: tuple[str, ...],
) -> None:
    """Distinct payloads and exact duplicates get deterministic, unique relation keys."""
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=_mixed_edge_variants(edge_order),
    )

    exported = graph.to_networkx()
    assert exported.is_directed()
    assert exported.is_multigraph()
    observed_key_to_relation = {
        key: (
            src,
            dst,
            data["mark_src"],
            data["mark_dst"],
            data["lag"],
            data["metadata"]["relation"],
        )
        for src, dst, key, data in exported.edges(keys=True, data=True)
    }

    assert observed_key_to_relation == {
        ("tail", "arrow", None, 0): (
            "X",
            "Y",
            "tail",
            "arrow",
            None,
            "same-alpha",
        ),
        ("tail", "arrow", None, 1): (
            "X",
            "Y",
            "tail",
            "arrow",
            None,
            "same-alpha",
        ),
        ("tail", "arrow", None, 2): (
            "X",
            "Y",
            "tail",
            "arrow",
            None,
            "same-zeta",
        ),
    }


def test_causal_graph_networkx_preserves_single_edge_payload() -> None:
    """The directed multigraph export keeps ordinary one-edge payloads intact."""
    edge = CausalEdge(
        src="A",
        dst="B",
        sources=[EdgeSource.DATA],
        data_confidence=0.6,
        evidence_refs=["evidence-1"],
        metadata={"relation": "single"},
    )
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["A", "B"],
        edges=[edge],
    )

    exported = graph.to_networkx()

    assert exported.is_directed()
    assert exported.number_of_edges("A", "B") == 1
    if exported.is_multigraph():
        edge_payload = next(iter(exported.get_edge_data("A", "B").values()))
    else:
        edge_payload = exported.get_edge_data("A", "B")
    assert edge_payload is not None
    assert edge_payload["mark_src"] == "tail"
    assert edge_payload["mark_dst"] == "arrow"
    assert edge_payload["lag"] is None
    assert edge_payload["data_confidence"] == 0.6
    assert edge_payload["evidence_refs"] == ["evidence-1"]
    assert edge_payload["metadata"] == {"relation": "single"}



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
