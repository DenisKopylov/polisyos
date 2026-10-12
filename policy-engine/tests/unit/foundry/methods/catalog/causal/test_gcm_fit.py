from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import gcm_fit as gcm_fit_module
from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit, _pag_to_dag_projection
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    UnsupportedGraphProjectionError,
)
from polisyos.ir.analytics.structural_causal_model import MechanismFamily, MechanismSource


def test_pag_projection_rejects_unresolved_orientation() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["Z", "Y"],
        edges=[
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
        ],
    )

    with pytest.raises(ValueError, match="cannot project unresolved partial orientation"):
        _pag_to_dag_projection(graph)


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

    result = HybridSCMFit.pure_step(payload, params={"fit_backend": "native_hybrid"})
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
    assert scm_spec.fit_method == "native_hybrid"
    assert scm_spec.fit_metrics["dowhy_available"] == 0.0
    assert scm_spec.source_graph == graph
    assert scm_spec.source_graph_ref is None
    assert scm_spec.graph_projection is not None
    assert scm_spec.graph_projection.status.value == "identity"
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

    result = HybridSCMFit.pure_step(payload, params={"fit_backend": "native_hybrid"})
    mechanism_y = next(item for item in result["scm_spec"].mechanisms if item.variable == "Y")
    assert mechanism_y.source is MechanismSource.HYBRID
    assert mechanism_y.family in {MechanismFamily.ADDITIVE_NOISE, MechanismFamily.EMPIRICAL}
    assert mechanism_y.family_params.get("hybrid_fallback") == "nonlinear_not_supported_phase10"


def test_hybrid_scm_fit_refuses_unadmitted_pag_profile_before_fitting(monkeypatch) -> None:
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

    source = graph.model_dump(mode="json")
    with pytest.raises(UnsupportedGraphProjectionError) as caught:
        HybridSCMFit.pure_step(
            payload,
            params={"fit_backend": "native_hybrid", "latent_sensitivity_threshold": 0.3},
        )

    assert caught.value.reason_code == "partial_graph_endpoint_profile_not_admitted"
    assert graph.model_dump(mode="json") == source


def test_native_hybrid_projection_preserves_source_and_refuses_unresolved_profile():
    rows = np.asarray([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0], [4.0, 8.0]])
    directed_pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
            )
        ],
    )
    result = HybridSCMFit.pure_step(
        SCMFitData(
            data=rows,
            column_names=["X", "Y"],
            graph=directed_pag,
            graph_ref="graph-ref",
        ),
        params={"fit_backend": "native_hybrid"},
    )
    spec = result["scm_spec"]
    assert spec.source_graph == directed_pag
    assert spec.source_graph_ref == "graph-ref"
    assert spec.graph_projection is not None
    assert spec.graph_projection.source_graph_sha256
    assert spec.graph_projection.status.value == "projected"

    unresolved = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.ARROW,
            )
        ],
    )
    with pytest.raises(ValueError, match="partial_graph_endpoint_profile_not_admitted"):
        HybridSCMFit.pure_step(
            SCMFitData(data=rows, column_names=["X", "Y"], graph=unresolved),
            params={"fit_backend": "native_hybrid"},
        )
