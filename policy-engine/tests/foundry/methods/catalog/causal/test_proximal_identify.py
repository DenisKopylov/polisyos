from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.proximal_identify import proximal_identify_v1
from polisyos.ir.analytics.causal import proof_bundle_from_proximal_certificate
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.ir.analytics.proximal import (
    ProximalIdentificationCertificate,
    ProxyAnnotation,
)


def _directed(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _bidirected(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)


def _query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="A",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _pci_core_graph(*, graph_type: GraphType = GraphType.ADMG) -> CausalGraphModel:
    nodes = ["A", "Y", "Z", "W", "X"]
    edges = [
        _directed("X", "A"),
        _directed("X", "Y"),
        _directed("Z", "A"),
        _directed("A", "Y"),
        _bidirected("A", "Y"),
        _bidirected("A", "Z"),
        _bidirected("Y", "W"),
    ]
    return CausalGraphModel(graph_type=graph_type, nodes=nodes, edges=edges)


def test_proximal_identify_v1_emits_machine_checkable_certificate() -> None:
    result = proximal_identify_v1(
        _pci_core_graph(),
        _query(),
        ProxyAnnotation(
            treatment_inducing=("Z",),
            outcome_inducing=("W",),
            covariates=("X",),
        ),
    )

    assert isinstance(result, ProximalIdentificationCertificate)
    assert result.query.estimand == "ATE"
    assert result.proxies.treatment_inducing == ("Z",)
    assert all(check.status == "pass" for check in result.graph_checks)
    assert {bridge.role for bridge in result.bridge_functions} == {
        "outcome_bridge",
        "treatment_bridge",
    }
    assert result.identified_functionals[0].expression == "E[h(W, 1, X) - h(W, 0, X)]"

    bundle = proof_bundle_from_proximal_certificate(
        result,
        graph_ref="graph:demo",
        query_ref="query:demo",
    )
    assert bundle.proof_status == "identified"
    assert bundle.proof_stratum == "A1_extended"
    assert bundle.completeness_regime == "sound_incomplete"
    assert bundle.metadata["method"] == "proximal_bridge"
    assert bundle.metadata["proximal_certificate"]["graph_class"]["name"] == "PCI-Core"


def test_proximal_identify_v1_rejects_treatment_path_to_w_proxy() -> None:
    graph = _pci_core_graph().model_copy(
        update={"edges": [*_pci_core_graph().edges, _directed("A", "W")]}
    )

    result = proximal_identify_v1(
        graph,
        _query(),
        {"treatment_inducing": ["Z"], "outcome_inducing": ["W"], "covariates": ["X"]},
    )

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.PROXIMAL_CONDITION_FAILED
    assert result.quantitative_diagnostics["failed_check"] == "no_directed_path_A_to_W"
    assert result.quantitative_diagnostics["witness"]["path"] == ["A", "W"]


def test_proximal_identify_v1_rejects_z_path_to_y_avoiding_treatment() -> None:
    base = _pci_core_graph()
    graph = base.model_copy(
        update={
            "nodes": [*base.nodes, "M"],
            "edges": [*base.edges, _directed("Z", "M"), _directed("M", "Y")],
        }
    )

    result = proximal_identify_v1(
        graph,
        _query(),
        ProxyAnnotation(treatment_inducing=("Z",), outcome_inducing=("W",), covariates=("X",)),
    )

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.PROXIMAL_CONDITION_FAILED
    assert result.quantitative_diagnostics["failed_check"] == "no_directed_path_Z_to_Y_without_A"
    assert result.quantitative_diagnostics["witness"]["path"] == ["Z", "M", "Y"]


def test_proximal_identify_v1_rejects_district_disconnected_proxy() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["A", "Y", "Z", "W", "X"],
        edges=[
            _directed("X", "A"),
            _directed("X", "Y"),
            _directed("Z", "A"),
            _directed("A", "Y"),
            _bidirected("A", "Y"),
            _bidirected("A", "Z"),
        ],
    )

    result = proximal_identify_v1(
        graph,
        _query(),
        ProxyAnnotation(treatment_inducing=("Z",), outcome_inducing=("W",), covariates=("X",)),
    )

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.PROXIMAL_CONDITION_FAILED
    assert result.quantitative_diagnostics["failed_check"] == "district_relevance"
    assert result.quantitative_diagnostics["witness"]["violation_code"] == "DISTRICT_DISCONNECTED"
    assert result.quantitative_diagnostics["witness"]["node"] == "W"


def test_proximal_identify_v1_rejects_pag_as_out_of_scope() -> None:
    result = proximal_identify_v1(
        _pci_core_graph(graph_type=GraphType.PAG),
        _query(),
        ProxyAnnotation(treatment_inducing=("Z",), outcome_inducing=("W",), covariates=("X",)),
    )

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1
    assert result.quantitative_diagnostics["failed_check"] == "graph_type_supported"


def test_proximal_identify_v1_rejects_non_interventional_query() -> None:
    query = CausalQuery(
        query_type=QueryType.COUNTERFACTUAL,
        treatment_variable="A",
        treatment_value=1.0,
        outcome_variable="Y",
        condition={"Y": 0.0},
    )

    result = proximal_identify_v1(
        _pci_core_graph(),
        query,
        ProxyAnnotation(treatment_inducing=("Z",), outcome_inducing=("W",), covariates=("X",)),
    )

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1
    assert result.quantitative_diagnostics["failed_check"] == "query_type_supported"
