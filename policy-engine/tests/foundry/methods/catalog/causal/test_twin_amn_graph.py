from __future__ import annotations

import json

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
    interventions = {"w0": {"X": 0.0}, "w1": {"X": 1.0}}
    amn_graph, meta = build_amn(_base_admg(), interventions)
    assert not amn_d_separation(
        amn_graph,
        meta,
        x_set=frozenset({"X__w0"}),
        y_set=frozenset({"X__w1"}),
        z_set=frozenset(),
    )
    assert amn_d_separation(
        amn_graph,
        meta,
        x_set=frozenset({"X__w0"}),
        y_set=frozenset({"X__w1"}),
        z_set=frozenset({"X__w1"}),
    )


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
