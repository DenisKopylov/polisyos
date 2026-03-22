"""Phase 10 tests for graph-based interference identification."""
from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.interference import (
    InterferenceAugmentedGraph,
    InterferenceIdentificationResult,
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
