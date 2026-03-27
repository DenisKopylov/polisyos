"""Phase 10 tests for graph-based interference identification."""
from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.interference import (
    InterferenceAugmentedGraph,
    InterferenceIdentificationResult,
    build_interference_topology_contracts,
    identify_interference_effect,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _make_graph(with_interference: bool) -> CausalGraphModel:
    edges = [
        CausalEdge(src="T_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="T_2", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
    ]
    if with_interference:
        edges.append(
            CausalEdge(src="T_1", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        )
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T_1", "Y_1", "T_2", "Y_2"],
        edges=edges,
        metadata={"dataset_ref": "demo"},
    )


def test_identify_interference_detects_cross_unit_edges_and_augmentation() -> None:
    graph = _make_graph(with_interference=True)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert isinstance(result, InterferenceIdentificationResult)
    assert result.interference_detected is True
    assert result.sutva_violated is True
    assert result.status == "identified"
    assert isinstance(result.augmented_graph, InterferenceAugmentedGraph)
    assert result.augmented_graph.exposure_nodes == ("E__u0",)
    assert result.augmented_graph.cluster_partition == (("T_1", "Y_1"), ("T_2", "Y_2"))
    assert "E__u0" in result.augmented_graph.augmented_graph.nodes
    assert any(step.rule_name == "SUTVA_CHECK" for step in result.proof_steps)
    assert any(step.rule_name == "EXPOSURE_AUGMENTATION" for step in result.proof_steps)
    assert any("cross_unit_edges=1" in line for line in result.trace)


def test_identify_interference_no_cross_unit_edges_keeps_original_graph() -> None:
    graph = _make_graph(with_interference=False)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert result.interference_detected is False
    assert result.sutva_violated is False
    assert result.status == "identified"
    assert result.augmented_graph.exposure_nodes == ()
    assert result.augmented_graph.augmented_graph.nodes == graph.nodes
    assert result.augmented_graph.augmented_graph.edges == graph.edges
    assert any(step.rule_name == "NO_INTERFERENCE" for step in result.proof_steps)


def test_identify_interference_roundtrip_serialization() -> None:
    graph = _make_graph(with_interference=True)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    payload = result.model_dump(mode="json")
    rebuilt = InterferenceIdentificationResult.model_validate(payload)

    assert rebuilt == result
    assert rebuilt.augmented_graph.exposure_nodes == ("E__u0",)
    assert rebuilt.proof_steps[0].rule_name == "SUTVA_CHECK"


def test_topology_adapter_discloses_cluster_and_pairwise_fallbacks() -> None:
    graph = _make_graph(with_interference=True)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    cluster_complex, cluster_certificate = build_interference_topology_contracts(
        result,
        reduction_policy="cluster_projection",
    )
    pairwise_complex, pairwise_certificate = build_interference_topology_contracts(
        result.augmented_graph,
        reduction_policy="pairwise_projection",
    )

    assert cluster_complex is not None
    assert cluster_complex.hyperedges == (("T_1", "Y_1"), ("T_2", "Y_2"))
    assert cluster_complex.reduction_policy == "cluster_projection"
    assert cluster_certificate.fallback_mode == "clustered"
    assert cluster_certificate.supported_query_family == "cluster_projection_queries"
    assert pairwise_complex is not None
    assert pairwise_complex.reduction_policy == "pairwise_projection"
    assert pairwise_certificate.fallback_mode == "pairwise"
    assert pairwise_certificate.supported_query_family == "pairwise_projection_queries"


def test_topology_adapter_marks_full_complex_as_unsupported() -> None:
    graph = _make_graph(with_interference=True)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    interaction_complex, certificate = build_interference_topology_contracts(
        result,
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert interaction_complex.reduction_policy == "full_complex"
    assert certificate.fallback_mode == "unsupported"
    assert certificate.reduction_error_bound is None
    assert certificate.supported_query_family == "cluster_projection_queries"
    assert "hypergraph_identification_not_claimed" in certificate.exposure_assumptions
