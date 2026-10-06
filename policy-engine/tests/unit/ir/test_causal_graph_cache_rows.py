"""Native row-reader isolation with topology, export and copy coherence."""

import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from polisyos.foundry.methods.catalog.causal.admg_ops import ancestors
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_graph_kuzu import (
    _export_graph_edges_csv,
    _export_graph_nodes_csv,
)


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", metadata={"nested": {"tags": ["source"]}})],
        metadata={"nested": {"tags": ["graph"]}},
    )


@pytest.mark.parametrize("rows_name", ["kuzu_node_rows", "kuzu_edge_rows"])
@pytest.mark.parametrize("mutation", ["overwrite", "base_alias", "clear", "add_nested"])
def test_returned_rows_cannot_change_cached_graph_export(rows_name: str, mutation: str) -> None:
    graph = _graph()
    canonical = graph.model_dump(mode="json")
    rows = getattr(graph, rows_name)
    assert type(rows) is tuple
    assert all(type(row) is dict for row in rows)
    expected = deepcopy(rows)
    key = "name" if rows_name == "kuzu_node_rows" else "src"
    if mutation == "overwrite":
        rows[0][key] = "hostile"
    elif mutation == "base_alias":
        dict.__setitem__(rows[0], key, "hostile")
    elif mutation == "clear":
        rows[0].clear()
    else:
        rows[0]["extra"] = {"nested": ["hostile"]}
        rows[0]["extra"]["nested"].append("again")
    cold = CausalGraphModel.model_validate(canonical)
    assert getattr(graph, rows_name) == getattr(cold, rows_name) == expected
    assert graph.model_dump(mode="json") == canonical
    assert ancestors(graph, frozenset({"Y"})) == frozenset({"X", "Y"})
    assert json.loads(graph.kuzu_edge_rows[0]["metadata_json"]) == canonical["edges"][0]["metadata"]


def test_native_emitter_can_mutate_its_plain_dict_without_corrupting_cache() -> None:
    graph = _graph()
    expected = (deepcopy(graph.kuzu_node_rows), deepcopy(graph.kuzu_edge_rows))
    calls: list[dict[str, Any]] = []

    class RecordingConsumer:
        def execute(self, statement: str, parameters: dict[str, Any]) -> None:
            assert type(parameters) is dict
            calls.append(deepcopy(parameters))
            parameters.clear()

    graph.to_kuzu(RecordingConsumer())
    assert tuple(calls[:2]) == expected[0]
    assert tuple(calls[2:]) == expected[1]
    assert (graph.kuzu_node_rows, graph.kuzu_edge_rows) == expected


def test_private_preparation_is_immutable_reused_and_copy_has_new_rows() -> None:
    graph = _graph()
    assert graph.kuzu_node_rows
    assert graph.kuzu_edge_rows
    old_nodes = graph.__dict__["_kuzu_node_rows_json"]
    old_edges = graph.__dict__["_kuzu_edge_rows_json"]
    assert type(old_nodes) is tuple and all(type(row) is str for row in old_nodes)
    assert type(old_edges) is tuple and all(type(row) is str for row in old_edges)
    assert graph.kuzu_edge_rows
    assert graph.__dict__["_kuzu_edge_rows_json"] is old_edges
    updated = graph.model_copy(update={"edges": []})
    assert "_kuzu_node_rows_json" not in updated.__dict__
    assert "_kuzu_edge_rows_json" not in updated.__dict__
    assert updated.kuzu_edge_rows == ()
    assert updated.__dict__["_kuzu_edge_rows_json"] is not old_edges
    assert graph.__dict__["_kuzu_edge_rows_json"] is old_edges
    assert ancestors(updated, frozenset({"Y"})) == frozenset({"Y"})


def test_actual_csv_helpers_retain_plain_row_values_after_reader_mutation(tmp_path: Path) -> None:
    graph = _graph()
    graph.kuzu_node_rows[0]["name"] = "hostile"
    graph.kuzu_edge_rows[0]["src"] = "hostile"
    node_path = tmp_path / "nodes.csv"
    edge_path = tmp_path / "edges.csv"
    _export_graph_nodes_csv(graph, node_path)
    _export_graph_edges_csv(graph, edge_path)
    with node_path.open(newline="") as stream:
        nodes = list(csv.DictReader(stream))
    with edge_path.open(newline="") as stream:
        edges = list(csv.DictReader(stream))
    assert nodes == [{"name": "X"}, {"name": "Y"}]
    assert edges[0]["FROM"] == "X"
    assert edges[0]["TO"] == "Y"
    assert json.loads(edges[0]["metadata_json"]) == {"nested": {"tags": ["source"]}}
