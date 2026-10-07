"""Installed graph row consumers and fresh CAS readers share the canonical contract.

This module is a Git-bound test carrier for an installed distribution, not a
claim that a different evidence-carrier head was built or executed.
"""
# ruff: noqa: T201 -- retain complete fresh-reader provenance in deciding output

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import sysconfig
from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.admg_ops import ancestors
from polisyos.ir.analytics import causal_graph as owner
from polisyos.ir.analytics.causal_graph_kuzu import (
    _export_graph_edges_csv,
    _export_graph_nodes_csv,
)

READER = """
import hashlib,json,sys,sysconfig
from pathlib import Path
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.admg_ops import ancestors
from polisyos.ir.analytics import causal_graph as owner
from polisyos.ir.registry.refs import CausalGraphModelRef
site=Path(sysconfig.get_paths()['purelib']).resolve()
assert sys.flags.isolated
assert Path(owner.__file__).resolve().is_relative_to(site)
expected=json.loads(sys.argv[3])
ref=CausalGraphModelRef.model_validate_json(sys.argv[2])
graph=owner.load_causal_graph_model(FileSystemCAS(sys.argv[1]),ref)
assert graph.schema_version=='1.0'
assert graph.model_dump(mode='json')==expected
network=graph.to_networkx()
assert network.is_multigraph()
actual=[{'src':u,'dst':v,**data} for u,v,key,data in network.edges(keys=True,data=True)]
assert sorted(json.dumps(x,sort_keys=True) for x in actual)==sorted(json.dumps(x,sort_keys=True) for x in expected['edges'])
if sys.argv[4]=='static_refused':
    try:
        ancestors(graph,frozenset({'Y'}))
    except ValueError as exc:
        assert 'Unsupported static ADMG profile' in str(exc) and 'lag=1' in str(exc)
        ancestry='static_refused'
    else:
        raise AssertionError('temporal graph admitted to static ancestry')
else:
    ancestry=sorted(ancestors(graph,frozenset({'Y'})))
    assert ancestry==json.loads(sys.argv[4])
origins={name:module.__file__ for name,module in sys.modules.copy().items() if name.startswith('polisyos') and getattr(module,'__file__',None)}
assert all(Path(path).resolve().is_relative_to(site) for path in origins.values())
print(json.dumps({'owner':str(Path(owner.__file__).resolve()),'owner_sha256':hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest(),'cas_id':ref.model_dump(mode='json')['artifact_id'],'schema_version':graph.schema_version,'edge_count':network.number_of_edges(),'edges':actual,'ancestors':ancestry,'origins':origins},sort_keys=True))
"""


def _mixed_graph() -> owner.CausalGraphModel:
    return owner.CausalGraphModel(
        graph_type=owner.GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[
            owner.CausalEdge(src="X", dst="Y", metadata={"nested": {"tags": ["directed"]}}),
            owner.CausalEdge(src="X", dst="Y", mark_src=owner.EdgeMark.ARROW),
            owner.CausalEdge(src="X", dst="Y", lag=1),
            owner.CausalEdge(src="X", dst="Y", lag=2),
            owner.CausalEdge(src="X", dst="Y", metadata={"nested": {"tags": ["directed"]}}),
        ],
    )


@pytest.mark.parametrize("version", ("mixed", "updated"))
def test_installed_detached_rows_csv_and_fresh_typed_graph_reader(
    tmp_path: Path, version: str
) -> None:
    site = Path(sysconfig.get_paths()["purelib"]).resolve()
    assert Path(owner.__file__).resolve().is_relative_to(site)
    original = (
        _mixed_graph()
        if version == "mixed"
        else owner.CausalGraphModel(
            graph_type=owner.GraphType.DAG,
            nodes=["X", "Y"],
            edges=[owner.CausalEdge(src="X", dst="Y")],
        )
    )
    original_dump = original.model_dump(mode="json")
    original_edge_count = 5 if version == "mixed" else 1
    assert len(original.kuzu_edge_rows) == original_edge_count
    if version == "mixed":
        with pytest.raises(ValueError, match="Unsupported static ADMG profile.*lag=1"):
            ancestors(original, frozenset({"Y"}))
    else:
        assert ancestors(original, frozenset({"Y"})) == frozenset({"X", "Y"})
    graph = original if version == "mixed" else original.model_copy(update={"edges": []})
    expected = graph.model_dump(mode="json")
    edge_count = 5 if version == "mixed" else 0
    ancestry_argument = "static_refused" if version == "mixed" else json.dumps(["Y"])
    rows = (deepcopy(graph.kuzu_node_rows), deepcopy(graph.kuzu_edge_rows))

    # A real parameter consumer may mutate ordinary dictionaries. Neither this
    # call nor base-dict mutation may alter a later CSV export or published graph.
    calls: list[dict[str, object]] = []

    class ParameterConsumer:
        def execute(self, statement: str, parameters: dict[str, object]) -> None:
            assert type(parameters) is dict
            calls.append(deepcopy(parameters))
            parameters.clear()

    graph.to_kuzu(ParameterConsumer())
    assert tuple(calls[:2]) == rows[0]
    assert tuple(calls[2:]) == rows[1]
    dict.__setitem__(graph.kuzu_node_rows[0], "name", "hostile")
    if edge_count:
        dict.__setitem__(graph.kuzu_edge_rows[0], "src", "hostile")
    assert (graph.kuzu_node_rows, graph.kuzu_edge_rows) == rows
    assert graph.model_dump(mode="json") == expected

    node_path, edge_path = tmp_path / "nodes.csv", tmp_path / "edges.csv"
    _export_graph_nodes_csv(graph, node_path)
    _export_graph_edges_csv(graph, edge_path)
    with node_path.open(newline="") as stream:
        assert list(csv.DictReader(stream)) == [{"name": "X"}, {"name": "Y"}]
    with edge_path.open(newline="") as stream:
        edges = list(csv.DictReader(stream))
    assert len(edges) == edge_count
    assert sorted((row["mark_src"], row["mark_dst"], row["lag"]) for row in edges) == (
        sorted(
            [
                ("tail", "arrow", ""),
                ("arrow", "arrow", ""),
                ("tail", "arrow", "1"),
                ("tail", "arrow", "2"),
                ("tail", "arrow", ""),
            ]
        )
        if edge_count
        else []
    )
    assert all(row["FROM"] == "X" and row["TO"] == "Y" for row in edges)
    assert original.model_dump(mode="json") == original_dump
    assert len(original.kuzu_edge_rows) == original_edge_count

    cas = tmp_path / "cas"
    ref = owner.persist_causal_graph_model(FileSystemCAS(cas), graph)
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            READER,
            str(cas),
            ref.model_dump_json(),
            json.dumps(expected),
            ancestry_argument,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(child.stdout, end="")
    print(child.stderr, end="", file=sys.stderr)
    assert child.returncode == 0, child.stdout + child.stderr
    observed = json.loads(child.stdout)
    assert observed["edge_count"] == edge_count
    assert observed["owner_sha256"] == hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest()
