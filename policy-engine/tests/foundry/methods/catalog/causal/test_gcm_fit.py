from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal import gcm_fit as gcm_fit_module
from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit, _pag_to_dag_projection
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.structural_causal_model import MechanismFamily, MechanismSource


def test_pag_projection_adds_latent_u_node_and_orients_uncertain_edges() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
        ],
    )

    dag, latent_vars = _pag_to_dag_projection(graph)
    assert dag.graph_type is GraphType.DAG
    assert latent_vars == ["U_0"]
    assert "U_0" in dag.nodes

    edge_pairs = {(edge.src, edge.dst) for edge in dag.edges}
    assert ("U_0", "X") in edge_pairs
    assert ("U_0", "Y") in edge_pairs
    assert ("Z", "Y") in edge_pairs

    uncertain_edge = next(edge for edge in dag.edges if edge.src == "Z" and edge.dst == "Y")
    assert uncertain_edge.metadata.get("orientation_uncertain") is True


def test_hybrid_scm_fit_assigns_all_mechanism_sources(monkeypatch) -> None:
    def _raise_import_error():
        raise ModuleNotFoundError("No module named 'dowhy'")

    monkeypatch.setattr(gcm_fit_module, "_load_dowhy_gcm_dependencies", _raise_import_error)

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["A", "B", "C", "D", "E", "F", "G"],
        edges=[
            CausalEdge(src="A", dst="B"),
            CausalEdge(src="B", dst="C"),
            CausalEdge(src="D", dst="E"),
            CausalEdge(src="G", dst="F"),
        ],
    )
    payload = SCMFitData(
        data=np.array(
            [
                [1.0, 1.6, 2.8],
                [1.5, 2.1, 3.5],
                [2.0, 2.4, 4.2],
                [2.5, 2.9, 4.8],
            ],
            dtype=float,
        ),
        column_names=["A", "B", "C"],
        graph=graph,
        literature_priors={
            "C": {
                "B": {"mean": 0.8, "std": 0.5},
                "__intercept__": {"mean": 0.0, "std": 1.0},
            },
            "E": {"D": {"mean": 0.3, "std": 0.7}},
        },
    )

    result = HybridSCMFit.pure_step(payload, params={})
    scm_spec = result["scm_spec"]
    mechanisms = {item.variable: item for item in scm_spec.mechanisms}

    assert mechanisms["B"].source is MechanismSource.DATA_FITTED
    assert mechanisms["C"].source is MechanismSource.HYBRID
    assert mechanisms["E"].source is MechanismSource.LITERATURE_PRIOR
    assert mechanisms["F"].source is MechanismSource.DEFAULT

    assert mechanisms["C"].family is MechanismFamily.LINEAR
    assert "posterior_mean" in mechanisms["C"].family_params
    assert "posterior_std" in mechanisms["C"].family_params
    assert mechanisms["C"].literature_prior is not None
    assert mechanisms["C"].literature_prior["B"]["mean"] == 0.8
    assert scm_spec.fit_method == "hybrid"
    assert scm_spec.fit_metrics["dowhy_available"] == 0.0
    assert result["warnings"]


def test_hybrid_scm_fit_marks_hybrid_fallback_for_invalid_prior(monkeypatch) -> None:
    def _raise_import_error():
        raise ModuleNotFoundError("No module named 'dowhy'")

    monkeypatch.setattr(gcm_fit_module, "_load_dowhy_gcm_dependencies", _raise_import_error)

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    payload = SCMFitData(
        data=np.array(
            [
                [0.1, 1.1],
                [0.2, 1.3],
                [0.3, 1.5],
                [0.4, 1.7],
            ],
            dtype=float,
        ),
        column_names=["X", "Y"],
        graph=graph,
        literature_priors={
            "Y": {
                "X": {"mean": 0.2, "std": 0.0},
                "__intercept__": {"mean": 0.0, "std": 1.0},
            }
        },
    )

    result = HybridSCMFit.pure_step(payload, params={})
    mechanism_y = next(item for item in result["scm_spec"].mechanisms if item.variable == "Y")
    assert mechanism_y.source is MechanismSource.HYBRID
    assert mechanism_y.family in {MechanismFamily.ADDITIVE_NOISE, MechanismFamily.EMPIRICAL}
    assert mechanism_y.family_params.get("hybrid_fallback") == "nonlinear_not_supported_phase10"


def test_hybrid_scm_fit_pag_u_node_does_not_crash_and_sets_sensitivity(monkeypatch) -> None:
    def _raise_import_error():
        raise ModuleNotFoundError("No module named 'dowhy'")

    monkeypatch.setattr(gcm_fit_module, "_load_dowhy_gcm_dependencies", _raise_import_error)

    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)],
    )
    payload = SCMFitData(
        data=np.array(
            [
                [1.0, 2.0],
                [1.2, 2.3],
                [1.5, 2.9],
                [1.7, 3.1],
            ],
            dtype=float,
        ),
        column_names=["X", "Y"],
        graph=graph,
    )

    result = HybridSCMFit.pure_step(payload, params={"latent_sensitivity_threshold": 0.3})
    scm_spec = result["scm_spec"]
    assert result["latent_vars"] == ["U_0"]
    assert scm_spec.graph.graph_type is GraphType.DAG

    latent_affected = [
        item
        for item in scm_spec.mechanisms
        if item.sensitivity_to_latent is not None
    ]
    assert latent_affected
    assert scm_spec.fit_metrics["unstable_due_to_latent"] == 1.0
