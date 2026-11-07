"""Finite temporal projection preserves declared coordinates and initial conditions."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    expand_temporal_graph,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.artifacts import InputRef


def _source(tmp_path: Path, *, lag: int = 1):
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "irrelevant"],
        edges=[
            CausalEdge(src="X", dst="Y", lag=lag, metadata={"coefficient": 3}),
            CausalEdge(src="Y", dst="X", lag=lag, metadata={"coefficient": 2}),
            CausalEdge(src="irrelevant", dst="irrelevant", lag=1),
        ],
        metadata={"graph_basis": "declared_synthetic_hypothesis"},
    )
    ref = persist_causal_graph_model(store, graph, return_selected_profile=True)
    return store, graph, ref


def test_feedback_expansion_has_only_required_ancestors_and_fresh_mapping(tmp_path: Path) -> None:
    store, source, ref = _source(tmp_path)
    original = source.model_dump(mode="json")
    expanded = expand_temporal_graph(
        store,
        ref,
        query_coordinates=[("X", 3), ("Y", 3)],
        start_step=0,
        end_step=3,
        boundary_coordinates=[("X", 0), ("Y", 0)],
        lag_unit="year",
        time_unit="year",
    )
    assert len(expanded.nodes) == 8
    assert len(expanded.edges) == 6
    assert nx.is_directed_acyclic_graph(expanded.to_networkx())
    assert not any("irrelevant" in node for node in expanded.nodes)
    mapping = expanded.metadata["temporal_expansion"]
    coordinates = {
        item["node"]: (item["variable"], item["step"]) for item in mapping["coordinates"]
    }
    assert set(coordinates.values()) == {
        (variable, step) for variable in ("X", "Y") for step in range(4)
    }
    for edge in expanded.edges:
        parent, child = coordinates[edge.src], coordinates[edge.dst]
        assert parent[0] != child[0]
        assert parent[1] == child[1] - 1
        assert edge.lag is None
        assert edge.metadata["temporal_source_lag"] == 1
    selected = persist_causal_graph_model(
        store,
        expanded,
        return_selected_profile=True,
        inputs=[
            InputRef(
                artifact_id=str(ref.artifact_id),
                role="source_graph",
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
        ],
    )
    fresh = load_causal_graph_model(
        ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")), selected
    )
    assert fresh.model_dump(mode="json") == expanded.model_dump(mode="json")
    assert fresh.metadata["temporal_expansion"]["source_graph_ref"] == ref.model_dump(mode="json")
    assert source.model_dump(mode="json") == original


def test_second_lag_profile_reuses_same_coordinate_adapter(tmp_path: Path) -> None:
    store, _, ref = _source(tmp_path, lag=2)
    expanded = expand_temporal_graph(
        store,
        ref,
        query_coordinates=[("X", 3)],
        start_step=1,
        end_step=4,
        boundary_coordinates=[("X", 0), ("Y", 0), ("X", 1), ("Y", 1)],
        lag_unit="month",
        time_unit="month",
    )
    assert len(expanded.nodes) == 2
    assert len(expanded.edges) == 1
    scope = expanded.model_dump(mode="json")["metadata"]["temporal_expansion"]
    assert scope["boundary_coordinates"] == [["Y", 1]]
    assert scope["query_coordinates"] == [["X", 3]]
    assert scope["scope"] == "conditional_on_declared_graph_and_initial_conditions"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"boundary_coordinates": [("X", 0)]}, "missing_boundary"),
        ({"lag_unit": "month"}, "lag_time_unit_mismatch"),
        ({"query_coordinates": [("X", 4)]}, "coordinate_outside_horizon"),
        ({"query_coordinates": [("X", 3), ("X", 3)]}, "duplicate_coordinate"),
        ({"boundary_coordinates": [("X", 1), ("Y", 0)]}, "coordinate_outside_horizon"),
        ({"query_coordinates": [("X", True)]}, "invalid_coordinate"),
        ({"query_coordinates": [("foreign", 3)]}, "invalid_coordinate"),
    ],
)
def test_temporal_boundary_scope_refuses_before_any_numerical_consumer(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    store, _, ref = _source(tmp_path)
    kwargs = {
        "query_coordinates": [("X", 3), ("Y", 3)],
        "start_step": 0,
        "end_step": 3,
        "boundary_coordinates": [("X", 0), ("Y", 0)],
        "lag_unit": "year",
        "time_unit": "year",
        **change,
    }
    with pytest.raises(ValueError, match=message):
        expand_temporal_graph(store, ref, **kwargs)


def test_temporal_expansion_requires_selected_source_profile(tmp_path: Path) -> None:
    store, _, ref = _source(tmp_path)
    with pytest.raises(ValueError, match="selected_write_ref_requires_profile"):
        expand_temporal_graph(
            store,
            ref.model_copy(update={"manifest_profile_sha256": None}),
            query_coordinates=[("X", 3)],
            start_step=0,
            end_step=3,
            boundary_coordinates=[("X", 0), ("Y", 0)],
            lag_unit="year",
            time_unit="year",
        )
