from __future__ import annotations

import json
from fractions import Fraction
from itertools import combinations

import pytest

from polisyos.foundry.methods.catalog.causal.amn import AMNMetadata, amn_d_separation, build_amn
from polisyos.foundry.methods.catalog.causal.twin_graph import (
    TwinGraphMetadata,
    build_twin_graph,
    to_counterfactual_subgraph,
    to_factual_subgraph,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _base_admg() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["U_XY", "X", "Y"],
        edges=[
            CausalEdge(src="U_XY", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="U_XY", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        metadata={"shared_exogenous": ["U_XY"]},
    )


def test_build_twin_graph_doubles_variables_and_keeps_shared_exogenous() -> None:
    twin, meta = build_twin_graph(_base_admg())
    assert twin.graph_type is GraphType.ADMG
    assert meta.world_count == 2
    assert "U_XY" in twin.nodes
    assert "X__0" in twin.nodes and "X__1" in twin.nodes
    assert "Y__0" in twin.nodes and "Y__1" in twin.nodes
    assert "U_XY__0" not in twin.nodes and "U_XY__1" not in twin.nodes


def test_twin_world_subgraphs_roundtrip_to_source_node_set() -> None:
    source = _base_admg()
    twin, meta = build_twin_graph(source)
    factual = to_factual_subgraph(twin, meta)
    counter = to_counterfactual_subgraph(twin, meta)
    assert set(factual.nodes) == set(source.nodes)
    assert set(counter.nodes) == set(source.nodes)
    assert {(e.src, e.dst) for e in factual.edges} == {(e.src, e.dst) for e in source.edges}
    assert {(e.src, e.dst) for e in counter.edges} == {(e.src, e.dst) for e in source.edges}


def test_build_amn_with_three_worlds() -> None:
    interventions = {
        "w0": {"X": 0.0},
        "w1": {"X": 1.0},
        "w2": {"X": 2.0},
    }
    amn_graph, meta = build_amn(_base_admg(), interventions)
    assert amn_graph.graph_type is GraphType.ADMG
    assert meta.worlds == ["w0", "w1", "w2"]
    assert set(meta.world_partition) == {"w0", "w1", "w2"}
    assert "X__w0" in amn_graph.nodes
    assert "X__w1" in amn_graph.nodes
    assert "X__w2" in amn_graph.nodes
    assert len(meta.bridge_edges) == 3


def test_amn_cross_world_separation() -> None:
    # Shared U→X→Y, without a direct U→Y path: X0 and Y1 separate given X1.
    source = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["U_shared", "X", "Y"],
        edges=[CausalEdge(src="U_shared", dst="X"), CausalEdge(src="X", dst="Y")],
        metadata={"shared_exogenous": ["U_shared"]},
    )
    amn_graph, meta = build_amn(source, {"w0": {"X": 0.0}, "w1": {"X": 1.0}})
    expected_edges = {
        ("U_shared", "X__w0", EdgeMark.TAIL, EdgeMark.ARROW),
        ("X__w0", "Y__w0", EdgeMark.TAIL, EdgeMark.ARROW),
        ("U_shared", "X__w1", EdgeMark.TAIL, EdgeMark.ARROW),
        ("X__w1", "Y__w1", EdgeMark.TAIL, EdgeMark.ARROW),
        ("X__w0", "X__w1", EdgeMark.ARROW, EdgeMark.ARROW),
    }
    assert {(e.src, e.dst, e.mark_src, e.mark_dst) for e in amn_graph.edges} == expected_edges
    # Expand the single bridge into its own hidden common cause B.
    latent_edges = [
        ("U_shared", "X__w0"),
        ("X__w0", "Y__w0"),
        ("U_shared", "X__w1"),
        ("X__w1", "Y__w1"),
        ("B", "X__w0"),
        ("B", "X__w1"),
    ]
    for condition, separated in [(frozenset(), False), (frozenset({"X__w1"}), True)]:
        expected = _latent_dag_separated(latent_edges, "X__w0", "Y__w1", condition)
        assert expected == separated
        assert (
            amn_d_separation(amn_graph, meta, frozenset({"X__w0"}), frozenset({"Y__w1"}), condition)
            == expected
        )
    # Independent unit-Gaussian realization of this derived graph:
    # X0=U+B+E0; X1=U+B+E1; Y1=X1+E2 (all sources independent).
    # Cov(X0,Y1|X1)=2 - 2*3/3 = 0. This is a graph oracle, not do-SEM authority.
    x0 = (1, 1, 1, 0, 0)
    x1 = (1, 1, 0, 1, 0)
    y1 = (1, 1, 0, 1, 1)

    def covariance(left, right):
        return sum(Fraction(a) * Fraction(b) for a, b in zip(left, right, strict=True))

    marginal = covariance(x0, y1)
    conditional = marginal - covariance(x0, x1) * covariance(x1, y1) / covariance(x1, x1)
    assert marginal == 2
    assert conditional == 0


def test_twin_and_amn_metadata_json_roundtrip() -> None:
    source = _base_admg()
    twin, twin_meta = build_twin_graph(source)
    amn, amn_meta = build_amn(source, {"w0": {"X": 0.0}, "w1": {"X": 1.0}})

    twin_payload = json.loads(json.dumps(twin.model_dump(mode="json")))
    twin_meta_payload = json.loads(json.dumps(twin_meta.model_dump(mode="json")))
    amn_payload = json.loads(json.dumps(amn.model_dump(mode="json")))
    amn_meta_payload = json.loads(json.dumps(amn_meta.model_dump(mode="json")))

    restored_twin = CausalGraphModel.model_validate(twin_payload)
    restored_twin_meta = TwinGraphMetadata.model_validate(twin_meta_payload)
    restored_amn = CausalGraphModel.model_validate(amn_payload)
    restored_amn_meta = AMNMetadata.model_validate(amn_meta_payload)

    assert restored_twin.graph_type is GraphType.ADMG
    assert restored_twin_meta.world_count == 2
    assert restored_amn.graph_type is GraphType.ADMG
    assert restored_amn_meta.worlds == ["w0", "w1"]


def _latent_dag_separated(edges, x: str, y: str, conditioned: frozenset[str]) -> bool:
    """Independent ancestral moralization, not the native endpoint walk."""
    parents: dict[str, set[str]] = {}
    for source, target in edges:
        parents.setdefault(target, set()).add(source)
    ancestors = {x, y, *conditioned}
    pending = list(ancestors)
    while pending:
        for parent in parents.get(pending.pop(), set()):
            if parent not in ancestors:
                ancestors.add(parent)
                pending.append(parent)
    moral = {node: set() for node in ancestors}
    for child in ancestors:
        family = parents.get(child, set()) & ancestors
        for parent in family:
            moral[parent].add(child)
            moral[child].add(parent)
        for left, right in combinations(family, 2):
            moral[left].add(right)
            moral[right].add(left)
    visited = set(conditioned)
    pending = [x]
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        if node == y:
            return False
        visited.add(node)
        pending.extend(moral[node] - visited)
    return True


def test_amn_endpoint_conditioning_is_not_disjoint_separation() -> None:
    """Keep the old overlapping query as an unsupported-domain negative."""
    amn_graph, meta = build_amn(_base_admg(), {"w0": {"X": 0.0}, "w1": {"X": 1.0}})
    assert not amn_d_separation(
        amn_graph,
        meta,
        x_set=frozenset({"X__w0"}),
        y_set=frozenset({"X__w1"}),
        z_set=frozenset({"X__w1"}),
    )


@pytest.mark.parametrize(
    ("edges", "conditioned", "separated"),
    [
        ([("M", "X"), ("M", "Y")], (), False),
        ([("M", "X"), ("M", "Y")], ("M",), True),
        ([("X", "M"), ("Y", "M"), ("M", "D")], (), True),
        ([("X", "M"), ("Y", "M"), ("M", "D")], ("M",), False),
        ([("X", "M"), ("Y", "M"), ("M", "D")], ("D",), False),
    ],
    ids=["fork-open", "fork-blocked", "collider-closed", "collider-conditioned", "descendant"],
)
def test_amn_disjoint_fork_collider_queries_match_latent_oracle(
    edges, conditioned, separated
) -> None:
    source = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y", "D"],
        edges=[CausalEdge(src=src, dst=dst) for src, dst in edges],
    )
    graph, meta = build_amn(source, {"w0": {}, "w1": {}})
    # Independent reference comes from the specified source, not native graph traversal.
    latent_edges = [(f"{src}__w0", f"{dst}__w0") for src, dst in edges]
    condition = frozenset(f"{node}__w0" for node in conditioned)
    expected = _latent_dag_separated(latent_edges, "X__w0", "Y__w0", condition)
    assert expected == separated
    assert (
        amn_d_separation(graph, meta, frozenset({"X__w0"}), frozenset({"Y__w0"}), condition)
        == expected
    )
