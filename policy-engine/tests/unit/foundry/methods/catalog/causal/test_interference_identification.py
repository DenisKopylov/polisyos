"""Phase 10 tests for graph-based interference identification."""

from __future__ import annotations

import math

import pytest

from polisyos.foundry.methods.catalog.causal.interference import (
    InterferenceAugmentedGraph,
    InterferenceIdentificationResult,
    build_interference_topology_contracts,
    identify_interference_effect,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.interference import ExposureMappingType


def _make_graph(
    with_interference: bool,
    *,
    include_partition: bool = True,
) -> CausalGraphModel:
    edges = [
        CausalEdge(src="T_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="T_2", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
    ]
    if with_interference:
        edges.append(
            CausalEdge(src="T_1", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        )
    metadata: dict[str, object] = {"dataset_ref": "demo"}
    if include_partition:
        metadata["cluster_partition"] = [["T_1", "Y_1"], ["T_2", "Y_2"]]
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T_1", "Y_1", "T_2", "Y_2"],
        edges=edges,
        metadata=metadata,
    )


def _make_topology_graph(topology: dict[str, object]) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["A", "B", "C", "D", "E", "F", "G", "U", "V", "W"],
        edges=[],
        metadata={"dataset_ref": "auction_micro_complex", "topology": topology},
    )


def _make_topology_augmented_graph(
    topology: dict[str, object],
    *,
    exposure_mapping: ExposureMappingType = ExposureMappingType.FRACTIONAL,
    cluster_partition: tuple[tuple[str, ...], ...] = (),
) -> InterferenceAugmentedGraph:
    graph = _make_topology_graph(topology)
    node_to_cluster: dict[str, str] = {}
    for cluster_idx, group in enumerate(cluster_partition):
        for node in group:
            node_to_cluster[node] = str(cluster_idx)
    return InterferenceAugmentedGraph(
        original_graph=graph,
        augmented_graph=graph,
        exposure_mapping=exposure_mapping,
        cluster_partition=cluster_partition,
        node_to_cluster=node_to_cluster,
    )


def _star_local_operator_metadata() -> dict[str, object]:
    return {
        "locality_scope": "closed_star",
        "exposure_states": (
            "direct_only",
            "pairwise_exposed",
            "simplex_exposed",
            "bridge_exposed",
        ),
        "exposure_consistency": True,
        "assignment_design": "bernoulli",
        "design_positivity": True,
        "bounded_star_overlap": True,
    }


def _fallback_ready_operator_metadata() -> dict[str, object]:
    payload = _star_local_operator_metadata()
    payload["inference_regime"] = "conditional_randomization"
    payload["selection_stage"] = "pre_outcome"
    return payload


def _auction_micro_complex_topology() -> dict[str, object]:
    return {
        "reduction_policy": "full_complex",
        "candidate_topology": "audited_or_fdr_controlled",
        "hyperedges": (("C", "D"), ("G", "A")),
        "simplices": (("A", "B", "C"), ("D", "E", "F")),
        "exposure_operator": _fallback_ready_operator_metadata(),
    }


def _fully_estimable_complex_topology() -> dict[str, object]:
    topology = _auction_micro_complex_topology()
    topology["higher_order_separability_verified"] = True
    return topology


def _pairwise_bound_model(
    *,
    p: float,
    triangle_response: str,
    triangle_weights: tuple[dict[str, object], ...] | None = None,
    lipschitz_by_node: dict[str, float] | None = None,
    exposure_mapping: str = "count",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "design": {"kind": "bernoulli_iid", "p": p},
        "exposure_mapping": exposure_mapping,
        "triangle_response": triangle_response,
    }
    if triangle_weights is not None:
        payload["triangle_weights"] = triangle_weights
    if lipschitz_by_node is not None:
        payload["lipschitz_by_node"] = lipschitz_by_node
    return payload


def test_identify_interference_refuses_unbound_cross_unit_exposure_law() -> None:
    graph = _make_graph(with_interference=True)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert isinstance(result, InterferenceIdentificationResult)
    assert result.schema_version == "1.1"
    assert result.interference_detected is True
    assert result.sutva_violated is True
    assert result.status == "oracle_needed"
    assert result.identification_method == "unsupported_exposure_law"
    assert result.base_identification_status is None
    assert result.estimand_ast is None
    assert result.negative_certificate is None
    assert result.required_distributions == ()
    assert result.augmented_graph.exposure_nodes == ()
    assert result.augmented_graph.augmented_graph == graph
    assert result.augmented_graph.cluster_partition == (("T_1", "Y_1"), ("T_2", "Y_2"))
    assert not any(node.startswith("E__") for node in result.augmented_graph.augmented_graph.nodes)
    assert any(step.rule_name == "INTERFERENCE_TOPOLOGY_CANDIDATE" for step in result.proof_steps)
    assert any(step.rule_name == "EXPOSURE_LAW_ORACLE_BOUNDARY" for step in result.proof_steps)
    assert any("cross_unit_edges=1" in line for line in result.trace)


def test_identify_interference_runs_original_graph_id_for_declared_no_cross_partition() -> None:
    graph = _make_graph(with_interference=False)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert result.interference_detected is False
    assert result.sutva_violated is False
    assert result.status == "identified"
    assert result.schema_version == "1.1"
    assert result.identification_method == "ordinary_original_graph_id"
    assert result.base_identification_status == "identified"
    assert result.estimand_ast is not None
    assert result.augmented_graph.exposure_nodes == ()
    assert result.augmented_graph.augmented_graph == graph
    assert any(step.rule_name == "NO_CROSS_UNIT_EDGES_OBSERVED" for step in result.proof_steps)


def test_identify_interference_requires_explicit_partition_not_suffix_inference() -> None:
    graph = _make_graph(with_interference=False, include_partition=False)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert result.status == "oracle_needed"
    assert result.interference_detected is None
    assert result.sutva_violated is None
    assert result.base_identification_status is None
    assert result.estimand_ast is None
    assert any(
        "complete declared unit partition is not established" in warning
        for warning in result.warnings
    )


def test_partial_partition_keeps_cross_unit_topology_indicators_unknown() -> None:
    graph = _make_graph(with_interference=False)
    metadata = dict(graph.metadata)
    metadata["cluster_partition"] = [["T_1"], ["Y_1"], ["T_2"]]
    graph = graph.model_copy(update={"metadata": metadata})

    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert result.status == "oracle_needed"
    assert result.interference_detected is None
    assert result.sutva_violated is None
    assert result.augmented_graph.cross_unit_edges == (("T_1", "Y_1"),)
    assert result.base_identification_status is None
    assert result.estimand_ast is None
    assert result.negative_certificate is None


def test_identify_interference_rejects_incomplete_declared_partition() -> None:
    graph = _make_graph(with_interference=False)
    metadata = dict(graph.metadata)
    metadata["cluster_partition"] = [["T_1", "Y_1"], ["T_2"]]
    graph = graph.model_copy(update={"metadata": metadata})
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert result.status == "oracle_needed"
    assert result.interference_detected is None
    assert result.sutva_violated is None
    assert result.base_identification_status is None
    assert result.estimand_ast is None
    assert any(
        "complete declared unit partition is not established" in warning
        for warning in result.warnings
    )


@pytest.mark.parametrize("policy", ["all_vs_none", "none", "unregistered", None])
def test_graph_policy_label_does_not_bind_an_exposure_law(policy: str | None) -> None:
    graph = _make_graph(with_interference=True)
    metadata = dict(graph.metadata)
    if policy is not None:
        metadata["interference_policy"] = policy
    graph = graph.model_copy(update={"metadata": metadata})

    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert result.status == "oracle_needed"
    assert result.identification_method == "unsupported_exposure_law"
    assert result.estimand_ast is None
    assert result.negative_certificate is None


@pytest.mark.parametrize(
    ("source_key", "cluster_var"),
    [("unit_map", None), ("cluster_map", None), ("unit_assignment", "unit_assignment")],
)
def test_identify_interference_accepts_complete_declared_unit_maps(
    source_key: str,
    cluster_var: str | None,
) -> None:
    graph = _make_graph(with_interference=False)
    metadata = dict(graph.metadata)
    metadata.pop("cluster_partition")
    metadata[source_key] = {
        "T_1": "unit-1",
        "Y_1": "unit-1",
        "T_2": "unit-2",
        "Y_2": "unit-2",
    }
    graph = graph.model_copy(update={"metadata": metadata})

    result = identify_interference_effect(
        graph,
        treatment="T_1",
        outcome="Y_1",
        cluster_var=cluster_var,
    )

    assert result.status == "identified"
    assert result.identification_method == "ordinary_original_graph_id"
    assert result.interference_detected is False
    assert result.sutva_violated is False


def test_identify_interference_refuses_conflicting_partition_declarations() -> None:
    graph = _make_graph(with_interference=False)
    metadata = dict(graph.metadata)
    metadata["unit_map"] = {
        "T_1": "unit-1",
        "Y_1": "unit-2",
        "T_2": "unit-2",
        "Y_2": "unit-1",
    }
    graph = graph.model_copy(update={"metadata": metadata})

    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    assert result.status == "oracle_needed"
    assert result.interference_detected is None
    assert result.sutva_violated is None
    assert result.base_identification_status is None
    assert result.estimand_ast is None


def test_identify_interference_preserves_genuine_hedge_status() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T", "Y"],
        edges=[
            CausalEdge(src="T", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="T", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
        metadata={"cluster_partition": [["T", "Y"]]},
    )
    result = identify_interference_effect(graph, treatment="T", outcome="Y")

    assert result.status == "non_identified"
    assert result.identification_method == "ordinary_original_graph_id"
    assert result.base_identification_status == "hedge_found"
    assert result.estimand_ast is None
    assert result.negative_certificate is not None
    assert result.negative_certificate["status"] == "hedge_found"


def test_identify_interference_roundtrip_serialization() -> None:
    graph = _make_graph(with_interference=True)
    result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")

    payload = result.model_dump(mode="json")
    rebuilt = InterferenceIdentificationResult.model_validate(payload)

    assert rebuilt == result
    assert rebuilt.schema_version == "1.1"
    assert rebuilt.status == "oracle_needed"
    assert rebuilt.augmented_graph.exposure_nodes == ()
    assert rebuilt.proof_steps[0].rule_name == "INTERFERENCE_TOPOLOGY_CANDIDATE"


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
    assert cluster_certificate.mode_requested == "clustered"
    assert cluster_certificate.mode_used == "clustered"
    assert cluster_certificate.fallback_triggered is False
    assert cluster_certificate.supported_query_family == "cluster_projection_queries"
    assert pairwise_complex is not None
    assert pairwise_complex.reduction_policy == "pairwise_projection"
    assert pairwise_certificate.fallback_mode == "pairwise"
    assert pairwise_certificate.mode_requested == "pairwise"
    assert pairwise_certificate.mode_used == "pairwise"
    assert pairwise_certificate.fallback_triggered is False
    assert pairwise_certificate.supported_query_family == "pairwise_projection_queries"
    assert (
        "interference_identification_not_established:oracle_needed"
        in cluster_certificate.exposure_assumptions
    )
    assert "interference_identification_not_supplied" in pairwise_certificate.exposure_assumptions


def test_topology_adapter_honestly_falls_back_to_pairwise_when_complex_gates_fail() -> None:
    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(_auction_micro_complex_topology()),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert interaction_complex.reduction_policy == "full_complex"
    assert ("A", "B") in interaction_complex.simplices
    assert ("A", "B", "C") in interaction_complex.simplices
    assert ("D", "E") in interaction_complex.simplices
    assert ("D", "E", "F") in interaction_complex.simplices
    assert certificate.supported_query_family == "pairwise_projection_queries"
    assert certificate.fallback_mode == "pairwise"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "pairwise"
    assert certificate.fallback_triggered is True
    assert certificate.reduction_error_bound is None
    assert "higher_order_separability_failed" in certificate.fallback_reason_codes
    assert certificate.estimability_checks["topology_evidence"] == "pass"
    assert certificate.estimability_checks["simplicial_closure"] == "pass"
    assert certificate.estimability_checks["exposure_positivity"] == "pass"
    assert certificate.estimability_checks["higher_order_separability"] == "fail"
    assert "candidate_topology:audited_or_fdr_controlled" in certificate.exposure_assumptions
    assert "selection_stage:pre_outcome" in certificate.exposure_assumptions
    assert "inference_regime:conditional_randomization" in certificate.exposure_assumptions
    assert "known_simplicial_complex" in certificate.exposure_assumptions
    assert "downward_closure_verified" in certificate.exposure_assumptions
    assert "finite_star_local_exposure_mapping" in certificate.exposure_assumptions
    assert "exposure_consistency" in certificate.exposure_assumptions
    assert "randomized_assignment" in certificate.exposure_assumptions
    assert "design_positivity" in certificate.exposure_assumptions
    assert "bounded_star_overlap" in certificate.exposure_assumptions
    assert "hypergraph_identification_not_claimed" in certificate.exposure_assumptions


def test_topology_adapter_uses_complex_mode_when_all_estimability_gates_pass() -> None:
    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(_fully_estimable_complex_topology()),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert certificate.supported_query_family == "simplicial_star_local_queries"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "complex"
    assert certificate.fallback_triggered is False
    assert certificate.fallback_reason_codes == ()
    assert set(certificate.estimability_checks.values()) == {"pass"}
    assert "candidate_topology:audited_or_fdr_controlled" in certificate.exposure_assumptions
    assert "hypergraph_identification_not_claimed" not in certificate.exposure_assumptions


def test_topology_adapter_returns_unsupported_when_no_safe_fallback_is_admissible() -> None:
    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(
            {
                "reduction_policy": "full_complex",
                "candidate_topology": "audited_or_fdr_controlled",
                "hyperedges": (("C", "D"), ("G", "A")),
                "simplices": (("A", "B", "C"), ("D", "E", "F")),
                "exposure_operator": _star_local_operator_metadata(),
            }
        ),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert certificate.supported_query_family == "unsupported_complex_queries"
    assert certificate.fallback_mode == "unsupported"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "unsupported"
    assert certificate.fallback_triggered is True
    assert "no_safe_fallback_available" in certificate.fallback_reason_codes
    assert certificate.estimability_checks["inference_regime"] == "fail"
    assert certificate.estimability_checks["pre_outcome_selection"] == "fail"


def test_topology_adapter_falls_back_to_pairwise_when_simplicial_closure_fails() -> None:
    topology = {
        "reduction_policy": "full_complex",
        "candidate_topology": "audited_or_fdr_controlled",
        "hyperedges": (("A", "B", "C"),),
        "simplices": (),
        "exposure_operator": _fallback_ready_operator_metadata(),
    }

    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert interaction_complex.reduction_policy == "full_complex"
    assert certificate.fallback_mode == "pairwise"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "pairwise"
    assert certificate.fallback_triggered is True
    assert certificate.reduction_error_bound is None
    assert certificate.supported_query_family == "pairwise_projection_queries"
    assert "hypergraph_identification_not_claimed" in certificate.exposure_assumptions
    assert "downward_closure_missing" in certificate.exposure_assumptions
    assert "simplicial_closure_failed" in certificate.fallback_reason_codes


def test_topology_adapter_rejects_complex_mode_without_topology_evidence() -> None:
    topology = _fully_estimable_complex_topology()
    topology.pop("candidate_topology", None)

    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert certificate.supported_query_family == "pairwise_projection_queries"
    assert certificate.fallback_mode == "pairwise"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "pairwise"
    assert certificate.fallback_triggered is True
    assert certificate.estimability_checks["topology_evidence"] == "fail"
    assert "topology_not_estimable" in certificate.fallback_reason_codes
    assert "candidate_topology:audited_or_fdr_controlled" not in certificate.exposure_assumptions


def test_topology_adapter_exact_pairwise_reduction_for_one_skeleton() -> None:
    topology = {
        "reduction_policy": "full_complex",
        "hyperedges": (("A", "B"), ("B", "C"), ("G", "A")),
        "simplices": (),
        "exposure_operator": {
            "design_positivity": True,
            "inference_regime": "conditional_randomization",
            "selection_stage": "pre_outcome",
        },
    }

    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert certificate.supported_query_family == "pairwise_projection_queries"
    assert certificate.fallback_mode == "pairwise"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "pairwise"
    assert certificate.fallback_triggered is True
    assert certificate.reduction_error_bound == 0.0
    assert "complex_reduces_exactly_to_pairwise" in certificate.fallback_reason_codes
    assert "pairwise_reduction_exact" in certificate.exposure_assumptions


def test_topology_adapter_exact_cluster_reduction_for_partitioned_facets() -> None:
    topology = {
        "reduction_policy": "full_complex",
        "candidate_topology": "audited_or_fdr_controlled",
        "hyperedges": (),
        "simplices": (("A", "B", "C"), ("D", "E", "F")),
        "exposure_operator": {
            "factorizes_through": "within_facet_summary",
            "design_positivity": True,
            "inference_regime": "conditional_randomization",
            "selection_stage": "pre_outcome",
        },
    }

    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert ("A", "B") in interaction_complex.simplices
    assert ("D", "F") in interaction_complex.simplices
    assert certificate.supported_query_family == "cluster_projection_queries"
    assert certificate.fallback_mode == "clustered"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "clustered"
    assert certificate.fallback_triggered is True
    assert certificate.reduction_error_bound == 0.0
    assert "complex_reduces_exactly_to_clustered" in certificate.fallback_reason_codes
    assert "cluster_reduction_exact" in certificate.exposure_assumptions


def test_pairwise_projection_bound_is_zero_for_linear_triangle_response() -> None:
    topology = {
        "reduction_policy": "pairwise_projection",
        "simplices": (("A", "B", "C"), ("D", "E", "F")),
        "bound_model": _pairwise_bound_model(p=0.35, triangle_response="linear"),
    }

    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology, exposure_mapping=ExposureMappingType.COUNT),
        reduction_policy="pairwise_projection",
    )

    assert interaction_complex is not None
    assert interaction_complex.reduction_policy == "pairwise_projection"
    assert certificate.fallback_mode == "pairwise"
    assert certificate.supported_query_family == "pairwise_projection_queries"
    assert certificate.reduction_error_bound == 0.0
    assert "bound_scope:bernoulli_mean_rate_contrasts_only" in certificate.exposure_assumptions
    assert "design:bernoulli_iid" in certificate.exposure_assumptions
    assert "linear_2complex_required" in certificate.exposure_assumptions
    assert "triangle_projection:design_calibrated" in certificate.exposure_assumptions
    assert "triangle_response:linear" in certificate.exposure_assumptions


def test_pairwise_projection_bound_is_computable_for_lipschitz_response() -> None:
    topology = {
        "reduction_policy": "pairwise_projection",
        "simplices": (("A", "B", "C"), ("A", "D", "E")),
        "bound_model": _pairwise_bound_model(
            p=0.5,
            triangle_response="lipschitz",
            triangle_weights=(
                {"simplex": ("A", "B", "C"), "weights": {"A": 1.0, "B": 1.0, "C": 1.0}},
                {"simplex": ("A", "D", "E"), "weights": {"A": 1.0, "D": 1.0, "E": 1.0}},
            ),
            lipschitz_by_node={"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0, "E": 1.0},
        ),
    }

    _, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology, exposure_mapping=ExposureMappingType.COUNT),
        reduction_policy="pairwise_projection",
    )

    assert certificate.reduction_error_bound is not None
    assert math.isclose(certificate.reduction_error_bound, 0.15, rel_tol=1e-9)
    assert "triangle_response:lipschitz" in certificate.exposure_assumptions


def test_pairwise_projection_bound_ignores_cluster_proxy_when_explicit_simplices_exist() -> None:
    topology = {
        "reduction_policy": "pairwise_projection",
        "simplices": (("A", "B", "C"), ("A", "D", "E")),
        "bound_model": _pairwise_bound_model(
            p=0.5,
            triangle_response="lipschitz",
            triangle_weights=(
                {"simplex": ("A", "B", "C"), "weights": {"A": 1.0, "B": 1.0, "C": 1.0}},
                {"simplex": ("A", "D", "E"), "weights": {"A": 1.0, "D": 1.0, "E": 1.0}},
            ),
            lipschitz_by_node={"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0, "E": 1.0},
        ),
    }

    _, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(
            topology,
            exposure_mapping=ExposureMappingType.COUNT,
            cluster_partition=(("A", "B", "C", "D", "E"), ("F", "G", "U", "V", "W")),
        ),
        reduction_policy="pairwise_projection",
    )

    assert certificate.reduction_error_bound is not None
    assert math.isclose(certificate.reduction_error_bound, 0.15, rel_tol=1e-9)


def test_full_complex_pairwise_fallback_carries_theorem_backed_bound() -> None:
    topology = {
        "reduction_policy": "full_complex",
        "candidate_topology": "audited_or_fdr_controlled",
        "simplices": (("A", "B", "C"), ("A", "D", "E")),
        "exposure_operator": _fallback_ready_operator_metadata(),
        "bound_model": _pairwise_bound_model(
            p=0.5,
            triangle_response="lipschitz",
            triangle_weights=(
                {"simplex": ("A", "B", "C"), "weights": {"A": 1.0, "B": 1.0, "C": 1.0}},
                {"simplex": ("A", "D", "E"), "weights": {"A": 1.0, "D": 1.0, "E": 1.0}},
            ),
            lipschitz_by_node={"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0, "E": 1.0},
        ),
    }

    interaction_complex, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology, exposure_mapping=ExposureMappingType.COUNT),
        reduction_policy="full_complex",
    )

    assert interaction_complex is not None
    assert certificate.supported_query_family == "pairwise_projection_queries"
    assert certificate.fallback_mode == "pairwise"
    assert certificate.mode_requested == "complex"
    assert certificate.mode_used == "pairwise"
    assert certificate.fallback_triggered is True
    assert certificate.reduction_error_bound is not None
    assert math.isclose(certificate.reduction_error_bound, 0.15, rel_tol=1e-9)
    assert "bound_scope:bernoulli_mean_rate_contrasts_only" in certificate.exposure_assumptions
    assert "triangle_response:lipschitz" in certificate.exposure_assumptions
    assert "higher_order_separability_failed" in certificate.fallback_reason_codes


def test_pairwise_projection_bound_rejects_shared_edge_triangles() -> None:
    topology = {
        "reduction_policy": "pairwise_projection",
        "simplices": (("A", "B", "C"), ("A", "B", "D")),
        "bound_model": _pairwise_bound_model(p=0.35, triangle_response="linear"),
    }

    _, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology, exposure_mapping=ExposureMappingType.COUNT),
        reduction_policy="pairwise_projection",
    )

    assert certificate.reduction_error_bound is None
    assert "linear_2complex_required" not in certificate.exposure_assumptions


def test_pairwise_projection_bound_rejects_non_count_exposure_mapping() -> None:
    topology = {
        "reduction_policy": "pairwise_projection",
        "simplices": (("A", "B", "C"), ("D", "E", "F")),
        "bound_model": _pairwise_bound_model(
            p=0.35,
            triangle_response="linear",
            exposure_mapping="fractional",
        ),
    }

    _, certificate = build_interference_topology_contracts(
        _make_topology_augmented_graph(topology, exposure_mapping=ExposureMappingType.FRACTIONAL),
        reduction_policy="pairwise_projection",
    )

    assert certificate.reduction_error_bound is None
    assert "bound_scope:bernoulli_mean_rate_contrasts_only" not in certificate.exposure_assumptions


def test_topology_indicator_truth_state_survives_trace_and_adapter_modes() -> None:
    """All topology projections retain true, false, or unknown across every mode."""
    nodes = ["T_1", "Y_1", "T_2", "Y_2"]
    within_edges = [
        CausalEdge(src="T_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="T_2", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
    ]
    partition = [["T_1", "Y_1"], ["T_2", "Y_2"]]
    scenarios = (
        (
            "unknown",
            CausalGraphModel(
                graph_type=GraphType.ADMG,
                nodes=nodes,
                edges=within_edges,
                metadata={"dataset_ref": "unknown-partition"},
            ),
            "oracle_needed",
        ),
        (
            "true",
            CausalGraphModel(
                graph_type=GraphType.ADMG,
                nodes=nodes,
                edges=[
                    *within_edges,
                    CausalEdge(
                        src="T_1",
                        dst="Y_2",
                        mark_src=EdgeMark.TAIL,
                        mark_dst=EdgeMark.ARROW,
                    ),
                ],
                metadata={"dataset_ref": "cross-unit", "cluster_partition": partition},
            ),
            "oracle_needed",
        ),
        (
            "false",
            CausalGraphModel(
                graph_type=GraphType.ADMG,
                nodes=nodes,
                edges=within_edges,
                metadata={"dataset_ref": "no-cross-unit", "cluster_partition": partition},
            ),
            "identified",
        ),
    )

    for expected_state, graph, expected_status in scenarios:
        result = identify_interference_effect(graph, treatment="T_1", outcome="Y_1")
        assert result.status == expected_status
        assert result.interference_detected is (
            None if expected_state == "unknown" else expected_state == "true"
        )
        assert result.sutva_violated is (
            None if expected_state == "unknown" else expected_state == "true"
        )
        trace = next(line for line in result.trace if "indicator projection:" in line)
        assert f"interference_detected={expected_state}" in trace
        assert f"sutva_violated={expected_state}" in trace

        for reduction_policy in (
            "pairwise_projection",
            "cluster_projection",
            "full_complex",
        ):
            _, certificate = build_interference_topology_contracts(
                result,
                reduction_policy=reduction_policy,
            )
            assumptions = set(certificate.exposure_assumptions)
            assert f"interference_detected:{expected_state}" in assumptions
            assert f"sutva_violated:{expected_state}" in assumptions
            assert f"interference_identification_status:{expected_status}" in assumptions
