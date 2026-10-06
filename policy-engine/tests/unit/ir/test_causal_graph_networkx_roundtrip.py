"""Actual mixed MultiDiGraph export after CAS readback, including loss controls."""

from itertools import permutations
from pathlib import Path

import networkx as nx
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.admg_ops import ancestors
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    load_causal_graph_model,
    persist_causal_graph_model,
)


def _edges() -> list[CausalEdge]:
    return [
        CausalEdge(
            src="X", dst="Y", metadata={"relation": "directed", "nested": {"weight": [1, 2]}}
        ),
        CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, metadata={"relation": "bidirected"}),
        CausalEdge(src="X", dst="Y", lag=1, metadata={"relation": "lag1"}),
        CausalEdge(src="X", dst="Y", lag=2, metadata={"relation": "lag2"}),
        CausalEdge(
            src="X", dst="Y", metadata={"relation": "directed", "nested": {"weight": [1, 2]}}
        ),
    ]


def _assert_full_export(graph: CausalGraphModel) -> None:
    exported = graph.to_networkx()
    assert exported.is_multigraph()
    assert exported.number_of_edges() == len(graph.edges) == 5
    actual = [
        {"src": u, "dst": v, **data} for u, v, key, data in exported.edges(keys=True, data=True)
    ]
    expected = [edge.model_dump(mode="json") for edge in graph.edges]
    # Compare complete payload multisets; duplicate records must retain multiplicity.
    import json

    assert sorted(json.dumps(item, sort_keys=True) for item in actual) == sorted(
        json.dumps(item, sort_keys=True) for item in expected
    )


def test_native_networkx_mixed_export_after_cas_all_input_permutations(tmp_path: Path) -> None:
    assert nx.__version__ == "3.6.1"
    store = FileSystemCAS(tmp_path / "cas")
    for ordering in permutations(_edges()):
        graph = CausalGraphModel(graph_type=GraphType.ADMG, nodes=["X", "Y"], edges=ordering)
        ref = persist_causal_graph_model(store, graph)
        reloaded = load_causal_graph_model(FileSystemCAS(tmp_path / "cas"), ref)
        _assert_full_export(reloaded)


def test_native_networkx_export_loss_is_detected_with_markers_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = CausalGraphModel(graph_type=GraphType.ADMG, nodes=["X", "Y"], edges=_edges())
    _assert_full_export(graph)
    monkeypatch.setattr(nx, "MultiDiGraph", nx.DiGraph)
    with pytest.raises(AssertionError):
        _assert_full_export(graph)


def test_warm_graph_copy_export_and_topology_agree(tmp_path: Path) -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="X", dst="Y")]
    )
    assert ancestors(graph, frozenset({"Y"})) == frozenset({"X", "Y"})
    assert graph.kuzu_edge_rows
    assert graph.to_networkx().number_of_edges() == 1
    with pytest.raises((AttributeError, TypeError)):
        graph.edges.clear()
    updated = graph.model_copy(update={"edges": []})
    cold = CausalGraphModel.model_validate(updated.model_dump(mode="json"))
    assert not updated.kuzu_edge_rows
    assert (
        ancestors(updated, frozenset({"Y"}))
        == ancestors(cold, frozenset({"Y"}))
        == frozenset({"Y"})
    )
    assert updated.model_dump(mode="json") == cold.model_dump(mode="json")
    assert updated.to_networkx().number_of_edges() == 0
