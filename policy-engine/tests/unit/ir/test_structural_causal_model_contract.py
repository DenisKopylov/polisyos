from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    load_structural_causal_model_spec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.registry.refs import StructuralCausalModelSpecRef


def _minimal_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["A", "B", "C"],
        edges=[
            CausalEdge(src="A", dst="B"),
            CausalEdge(src="B", dst="C"),
        ],
        discovery_method="manual",
    )


def test_structural_model_allows_root_without_mechanism() -> None:
    graph = _minimal_graph()
    model = StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="B",
                parents=["A"],
                family=MechanismFamily.LINEAR,
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="C",
                parents=["B"],
                family=MechanismFamily.LINEAR,
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )
    assert model.graph.graph_type is GraphType.DAG
    assert len(model.mechanisms) == 2


def test_structural_model_rejects_missing_non_root_mechanism() -> None:
    with pytest.raises(ValueError, match="Non-root nodes without mechanisms"):
        StructuralCausalModelSpec(
            graph=_minimal_graph(),
            mechanisms=[
                NodeMechanism(
                    variable="B",
                    parents=["A"],
                    family=MechanismFamily.LINEAR,
                    source=MechanismSource.DATA_FITTED,
                )
            ],
        )


def test_node_mechanism_rejects_non_json_family_params() -> None:
    with pytest.raises(ValueError, match="JSON-serializable"):
        NodeMechanism(
            variable="B",
            parents=["A"],
            family=MechanismFamily.LINEAR,
            source=MechanismSource.DATA_FITTED,
            family_params={"invalid": object()},
        )


def test_structural_model_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    model = StructuralCausalModelSpec(
        graph=_minimal_graph(),
        mechanisms=[
            NodeMechanism(
                variable="B",
                parents=["A"],
                family=MechanismFamily.LINEAR,
                source=MechanismSource.DATA_FITTED,
                family_params={"coef": 1.0},
            ),
            NodeMechanism(
                variable="C",
                parents=["B"],
                family=MechanismFamily.PARAMETRIC_PRIOR,
                source=MechanismSource.LITERATURE_PRIOR,
                family_params={"prior": {"B": {"mean": 0.5, "std": 0.2}}},
            ),
        ],
        fitted=True,
        fit_method="hybrid",
        fit_metrics={"dowhy_available": 0.0},
    )

    ref = persist_structural_causal_model_spec(store, model)
    loaded = load_structural_causal_model_spec(store, ref)

    assert isinstance(ref, StructuralCausalModelSpecRef)
    assert ref.kind == "ir.structural_causal_model_spec"
    assert loaded == model
