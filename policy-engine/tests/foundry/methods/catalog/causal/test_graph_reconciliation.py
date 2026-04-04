from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.graph_reconciliation import (
    ComposeSCMFragments,
    MAX_RECON_EDGES,
    ReconcileCausalGraph,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    FragmentCompositionData,
    GraphReconciliationData,
    LLMStructuralHint,
)
from polisyos.ir.analytics.alignment_certification import (
    AlignmentOverallStatus,
    AlignmentVerificationConfig,
    verify_fragment_alignment,
    verify_fragment_bundle_alignment,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)
from polisyos.ir.analytics.cross_graph import SCMFragment
from polisyos.ir.analytics.literature import LiteratureCausalPrior, LiteratureEdgePrior


def _data_edge(
    src: str,
    dst: str,
    *,
    confidence: float,
    lag: int | None = None,
    metadata: dict | None = None,
) -> CausalEdge:
    return CausalEdge(
        src=src,
        dst=dst,
        lag=lag,
        sources=[EdgeSource.DATA],
        data_confidence=confidence,
        combined_confidence=confidence,
        metadata=metadata or {},
    )


def _graph(nodes: list[str], edges: list[CausalEdge], *, graph_type: GraphType = GraphType.DAG) -> CausalGraphModel:
    return CausalGraphModel(graph_type=graph_type, nodes=nodes, edges=edges)


def _fragment(
    fragment_id: str,
    *,
    interface_variables: list[str],
    outputs: list[str] | None = None,
    inputs: list[str] | None = None,
    latent_summary: dict[str, str] | None = None,
    definitions: dict[str, str] | None = None,
    units: dict[str, str] | None = None,
    measurement_models: dict[str, str] | None = None,
) -> SCMFragment:
    return SCMFragment(
        fragment_id=fragment_id,
        graph_ref=f"artifact:graph:{fragment_id}",
        semantic_namespace="policy.labor",
        interface_variables=interface_variables,
        exposed_inputs=list(inputs or []),
        exposed_outputs=list(outputs or []),
        latent_summary=dict(latent_summary or {}),
        variable_definitions=dict(definitions or {}),
        variable_units=dict(units or {}),
        measurement_models=dict(measurement_models or {}),
    )


def test_literature_and_data_agreement_increases_combined_confidence() -> None:
    data_graph = _graph(["X", "Y"], [_data_edge("X", "Y", confidence=0.7)])
    prior = LiteratureCausalPrior(
        edges=[LiteratureEdgePrior(src="X", dst="Y", confidence=0.6)],
    )
    payload = GraphReconciliationData(data_graph=data_graph, literature_prior=prior, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    edge = next(item for item in result["reconciled_graph"].edges if item.src == "X" and item.dst == "Y")

    assert edge.combined_confidence is not None
    assert edge.combined_confidence > 0.7
    assert edge.combined_confidence > 0.6


def test_data_wins_when_direction_conflicts_with_literature() -> None:
    data_graph = _graph(["A", "B"], [_data_edge("A", "B", confidence=0.9)])
    prior = LiteratureCausalPrior(
        edges=[LiteratureEdgePrior(src="B", dst="A", confidence=0.8)],
    )
    payload = GraphReconciliationData(data_graph=data_graph, literature_prior=prior, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    pairs = {(edge.src, edge.dst) for edge in result["reconciled_graph"].edges}

    assert ("A", "B") in pairs
    assert ("B", "A") not in pairs


def test_llm_only_hint_is_marked_unsupported_and_capped() -> None:
    data_graph = _graph(["A", "B"], [])
    payload = GraphReconciliationData(
        data_graph=data_graph,
        llm_hints=[LLMStructuralHint(src="A", dst="B", confidence=0.95)],
        min_edge_confidence=0.0,
    )

    result = ReconcileCausalGraph.pure_step(payload, params={})
    edge = next(item for item in result["reconciled_graph"].edges if item.src == "A" and item.dst == "B")

    assert edge.unsupported_by_evidence is True
    assert edge.combined_confidence is not None
    assert edge.combined_confidence <= 0.3


def test_simple_cycle_converts_min_confidence_edge_to_lagged_edge() -> None:
    data_graph = _graph(
        ["A", "B", "C"],
        [
            _data_edge("A", "B", confidence=0.9),
            _data_edge("B", "C", confidence=0.8),
            _data_edge("C", "A", confidence=0.2),
        ],
        graph_type=GraphType.CPDAG,
    )
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    edges = result["reconciled_graph"].edges
    lagged = [edge for edge in edges if edge.dst == "A" and edge.lag == 1]

    assert lagged
    assert any(edge.src.startswith("C_t-1") for edge in lagged)


def test_more_than_eight_cycles_triggers_fallback_removal_warning() -> None:
    nodes: list[str] = []
    edges: list[CausalEdge] = []
    for idx in range(9):
        a = f"A{idx}"
        b = f"B{idx}"
        c = f"C{idx}"
        nodes.extend([a, b, c])
        edges.extend(
            [
                _data_edge(a, b, confidence=0.9),
                _data_edge(b, c, confidence=0.8),
                _data_edge(c, a, confidence=0.1),
            ]
        )
    data_graph = _graph(nodes, edges, graph_type=GraphType.CPDAG)
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    warnings = [str(item).lower() for item in result["warnings"]]

    assert any("cycle resolution budget exceeded" in warning for warning in warnings)
    assert any("fallback removal" in warning for warning in warnings)


def test_cycle_edge_with_lag_depth_limit_is_removed() -> None:
    data_graph = _graph(
        ["A", "B", "C"],
        [
            _data_edge("A", "B", confidence=0.9),
            _data_edge("B", "C", confidence=0.8),
            _data_edge("C", "A", confidence=0.1, lag=2),
        ],
        graph_type=GraphType.CPDAG,
    )
    payload = GraphReconciliationData(
        data_graph=data_graph,
        min_edge_confidence=0.0,
        max_lag_depth=2,
    )

    result = ReconcileCausalGraph.pure_step(payload, params={})
    pairs = {(edge.src, edge.dst, edge.lag) for edge in result["reconciled_graph"].edges}

    assert ("C", "A", 2) not in pairs


def test_triangle_conflict_produces_positive_cyclic_inconsistency_norm() -> None:
    data_graph = _graph(
        ["A", "B", "C"],
        [
            _data_edge("A", "B", confidence=0.8),
            _data_edge("B", "C", confidence=0.9),
            _data_edge("A", "C", confidence=0.2),
        ],
    )
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    diagnostics = result["diagnostics"]

    assert diagnostics.cyclic_inconsistency_norm > 0.0


def test_irreducible_conflict_triggers_expert_review_flag() -> None:
    data_graph = _graph(["A", "B"], [_data_edge("A", "B", confidence=0.9)])
    payload = GraphReconciliationData(
        data_graph=data_graph,
        llm_hints=[LLMStructuralHint(src="B", dst="A", confidence=0.9)],
        min_edge_confidence=0.0,
    )

    result = ReconcileCausalGraph.pure_step(payload, params={})

    assert result["diagnostics"].irreducible_conflict_norm > 0.5
    assert result["needs_expert_review"] is True
    assert result["reconciled_graph"].metadata["needs_expert_review"] is True


def test_diagnostics_truncated_when_hard_limits_exceeded() -> None:
    nodes = [f"N{i}" for i in range(MAX_RECON_EDGES + 3)]
    edges = [
        _data_edge(nodes[idx], nodes[idx + 1], confidence=0.55)
        for idx in range(MAX_RECON_EDGES + 2)
    ]
    data_graph = _graph(nodes, edges, graph_type=GraphType.CPDAG)
    payload = GraphReconciliationData(data_graph=data_graph, min_edge_confidence=0.0)

    result = ReconcileCausalGraph.pure_step(payload, params={})
    diagnostics = result["diagnostics"]

    assert diagnostics.diagnostics_truncated is True
    assert diagnostics.truncation_reason is not None


def test_compose_scm_fragments_preserves_exact_observed_interface() -> None:
    fragment_a = _fragment(
        "a",
        interface_variables=["employment_rate"],
        outputs=["employment_rate"],
        definitions={"employment_rate": "Employment rate"},
        units={"employment_rate": "percent"},
    )
    fragment_b = _fragment(
        "b",
        interface_variables=["employment_rate"],
        inputs=["employment_rate"],
        definitions={"employment_rate": "Employment rate"},
        units={"employment_rate": "percent"},
    )
    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["employment_rate", "tax"], [_data_edge("tax", "employment_rate", confidence=0.8)]),
                "b": _graph(["employment_rate", "wages"], [_data_edge("employment_rate", "wages", confidence=0.7)]),
            },
            alignment_report=report,
            interface_mapping=mapping,
            source_fragment_refs={"a": "artifact:fragment:a", "b": "artifact:fragment:b"},
            source_fragment_graph_refs={"a": "artifact:graph:a", "b": "artifact:graph:b"},
            metadata={
                "alignment_report_ref": "artifact:alignment:1",
                "interface_mapping_ref": "artifact:mapping:1",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "preserved"
    assert result["composition_certificate"].structure_status == "valid"
    assert result["composition_certificate"].review_status == "clear"
    assert result["needs_expert_review"] is False
    assert result["composition_certificate"].checked_queries == {}
    assert result["composition_certificate"].source_fragment_refs == {
        "a": "artifact:fragment:a",
        "b": "artifact:fragment:b",
    }
    assert result["composition_certificate"].source_fragment_graph_refs == {
        "a": "artifact:graph:a",
        "b": "artifact:graph:b",
    }
    assert result["composed_graph"] is not None
    assert any(node.startswith("stitched::employment_rate") for node in result["composed_graph"].nodes)


def test_compose_scm_fragments_promotes_output_to_admg_when_any_fragment_is_admg() -> None:
    fragment_a = _fragment("a", interface_variables=["employment_rate"], outputs=["employment_rate"])
    fragment_b = _fragment("b", interface_variables=["employment_rate"], inputs=["employment_rate"])
    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["employment_rate", "tax"], [_data_edge("tax", "employment_rate", confidence=0.8)]),
                "b": _graph(
                    ["employment_rate", "latent_u"],
                    [
                        CausalEdge(
                            src="employment_rate",
                            dst="latent_u",
                            mark_src=EdgeMark.ARROW,
                            mark_dst=EdgeMark.ARROW,
                            sources=[EdgeSource.DATA],
                            combined_confidence=0.6,
                        )
                    ],
                    graph_type=GraphType.ADMG,
                ),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:2",
                "interface_mapping_ref": "artifact:mapping:2",
            },
        ),
        params={},
    )

    assert result["composed_graph"] is not None
    assert result["composed_graph"].graph_type is GraphType.ADMG


def test_compose_scm_fragments_allows_asymmetric_output_input_stitch() -> None:
    fragment_a = _fragment(
        "a",
        interface_variables=["employment_rate"],
        outputs=["employment_rate"],
        definitions={"employment_rate": "Employment rate"},
        units={"employment_rate": "percent"},
    )
    fragment_b = _fragment(
        "b",
        interface_variables=["employment_rate", "wages"],
        inputs=["employment_rate"],
        outputs=["wages"],
        definitions={
            "employment_rate": "Employment rate",
            "wages": "Average wage level",
        },
        units={"employment_rate": "percent", "wages": "usd_per_month"},
    )
    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.incompatible_pairs == []
    assert report.metadata["boundary_interface_variables"] == {"a": [], "b": ["wages"]}

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["employment_rate", "tax"], [_data_edge("tax", "employment_rate", confidence=0.8)]),
                "b": _graph(["employment_rate", "wages"], [_data_edge("employment_rate", "wages", confidence=0.7)]),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:asym",
                "interface_mapping_ref": "artifact:mapping:asym",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "preserved"
    assert result["composition_certificate"].structure_status == "valid"
    assert result["composition_certificate"].review_status == "clear"
    assert result["blocking_reasons"] == []
    assert result["failure_cards"] == []


def test_compose_scm_fragments_allows_chain_topology() -> None:
    fragments = [
        _fragment(
            "a",
            interface_variables=["employment_rate"],
            outputs=["employment_rate"],
            definitions={"employment_rate": "Employment rate"},
            units={"employment_rate": "percent"},
        ),
        _fragment(
            "b",
            interface_variables=["employment_rate", "wages"],
            inputs=["employment_rate"],
            outputs=["wages"],
            definitions={"employment_rate": "Employment rate", "wages": "Average wage level"},
            units={"employment_rate": "percent", "wages": "usd_per_month"},
        ),
        _fragment(
            "c",
            interface_variables=["wages"],
            inputs=["wages"],
            definitions={"wages": "Average wage level"},
            units={"wages": "usd_per_month"},
        ),
    ]
    report, mapping = verify_fragment_bundle_alignment(fragments)

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=fragments,
            fragment_graphs={
                "a": _graph(["tax", "employment_rate"], [_data_edge("tax", "employment_rate", confidence=0.8)]),
                "b": _graph(["employment_rate", "wages"], [_data_edge("employment_rate", "wages", confidence=0.7)]),
                "c": _graph(["wages", "consumption"], [_data_edge("wages", "consumption", confidence=0.7)]),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:chain",
                "interface_mapping_ref": "artifact:mapping:chain",
            },
        ),
        params={},
    )

    assert report.metadata["selected_stitch_pairs"] == [["a", "b"], ["b", "c"]]
    assert result["composition_certificate"].status == "preserved"
    assert result["composition_certificate"].structure_status == "valid"
    assert result["composition_certificate"].review_status == "clear"
    assert result["blocking_reasons"] == []


def test_compose_scm_fragments_rejects_disconnected_fragment_topology() -> None:
    fragments = [
        _fragment(
            "a",
            interface_variables=["employment_rate"],
            outputs=["employment_rate"],
            definitions={"employment_rate": "Employment rate"},
            units={"employment_rate": "percent"},
        ),
        _fragment(
            "b",
            interface_variables=["employment_rate"],
            inputs=["employment_rate"],
            definitions={"employment_rate": "Employment rate"},
            units={"employment_rate": "percent"},
        ),
        _fragment(
            "c",
            interface_variables=["hospital_occupancy"],
            outputs=["hospital_occupancy"],
            definitions={"hospital_occupancy": "Hospital occupancy rate"},
            units={"hospital_occupancy": "beds_per_hospital"},
        ),
    ]
    report, mapping = verify_fragment_bundle_alignment(fragments)

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=fragments,
            fragment_graphs={
                "a": _graph(["tax", "employment_rate"], [_data_edge("tax", "employment_rate", confidence=0.8)]),
                "b": _graph(["employment_rate", "wages"], [_data_edge("employment_rate", "wages", confidence=0.7)]),
                "c": _graph(["hospital_occupancy"], []),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:disconnected",
                "interface_mapping_ref": "artifact:mapping:disconnected",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "broken"
    assert result["composition_certificate"].structure_status == "invalid"
    assert result["composition_certificate"].review_status == "clear"
    assert "c" in result["composition_certificate"].metadata["disconnected_fragment_ids"]
    assert {card.failure_type for card in result["failure_cards"]} >= {
        "fragment_topology_disconnected"
    }


def test_compose_scm_fragments_rejects_unobserved_or_latent_pending_interfaces() -> None:
    fragment_a = _fragment(
        "a",
        interface_variables=["employment_rate"],
        outputs=["employment_rate"],
        latent_summary={"employment_rate": "latent proxy"},
    )
    fragment_b = _fragment("b", interface_variables=["employment_rate"], inputs=["employment_rate"])
    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["employment_rate"], []),
                "b": _graph(["employment_rate"], []),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:3",
                "interface_mapping_ref": "artifact:mapping:3",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "broken"
    assert result["composition_certificate"].structure_status == "invalid"
    assert result["composition_certificate"].review_status == "pending_review"
    assert result["needs_expert_review"] is True
    assert any("unobserved" in reason.lower() for reason in result["blocking_reasons"])
    assert {card.failure_type for card in result["failure_cards"]} >= {"unobserved_interface"}


def test_compose_scm_fragments_allows_proxy_but_marks_deferred() -> None:
    fragment_a = _fragment(
        "a",
        interface_variables=["RL.EST"],
        outputs=["RL.EST"],
        definitions={"RL.EST": "Rule of law estimate"},
    )
    fragment_b = _fragment(
        "b",
        interface_variables=["GE.EST"],
        inputs=["GE.EST"],
        definitions={"GE.EST": "Government effectiveness estimate"},
    )
    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["RL.EST", "tax"], [_data_edge("tax", "RL.EST", confidence=0.8)]),
                "b": _graph(["GE.EST", "wages"], [_data_edge("GE.EST", "wages", confidence=0.7)]),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:4",
                "interface_mapping_ref": "artifact:mapping:4",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "deferred"
    assert result["composition_certificate"].structure_status == "valid"
    assert result["composition_certificate"].review_status == "pending_review"
    assert result["needs_expert_review"] is True
    assert result["composed_graph"] is not None
    assert {card.failure_type for card in result["failure_cards"]} >= {
        "proxy_alignment_pending_review"
    }


def test_compose_scm_fragments_promotes_human_verified_proxy_to_preserved() -> None:
    fragment_a = _fragment(
        "a",
        interface_variables=["RL.EST"],
        outputs=["RL.EST"],
        definitions={"RL.EST": "Rule of law estimate"},
    )
    fragment_b = _fragment(
        "b",
        interface_variables=["GE.EST"],
        inputs=["GE.EST"],
        definitions={"GE.EST": "Government effectiveness estimate"},
    )
    report, mapping = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(human_verified_pairs=["a:RL.EST|b:GE.EST"]),
    )

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["RL.EST", "tax"], [_data_edge("tax", "RL.EST", confidence=0.8)]),
                "b": _graph(["GE.EST", "wages"], [_data_edge("GE.EST", "wages", confidence=0.7)]),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:4b",
                "interface_mapping_ref": "artifact:mapping:4b",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "preserved"
    assert result["composition_certificate"].structure_status == "valid"
    assert result["composition_certificate"].review_status == "clear"
    assert result["needs_expert_review"] is False
    assert result["failure_cards"] == []


def test_compose_scm_fragments_blocks_explicit_incompatible_pair_labels() -> None:
    fragment_a = _fragment(
        "labor",
        interface_variables=["rate"],
        outputs=["rate"],
        definitions={"rate": "Employment rate among working-age adults"},
        units={"rate": "percent"},
        measurement_models={"rate": "artifact:mm:labor"},
    )
    fragment_b = _fragment(
        "health",
        interface_variables=["rate"],
        inputs=["rate"],
        definitions={"rate": "Hospital occupancy beds"},
        units={"rate": "beds_per_hospital"},
        measurement_models={"rate": "artifact:mm:health"},
    )
    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "labor": _graph(["rate"], []),
                "health": _graph(["rate"], []),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:strict",
                "interface_mapping_ref": "artifact:mapping:strict",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "broken"
    assert result["composition_certificate"].structure_status == "invalid"
    assert result["composition_certificate"].review_status == "clear"
    assert result["needs_expert_review"] is False
    assert any("labor:rate <-> health:rate" in reason for reason in result["blocking_reasons"])
    assert {card.failure_type for card in result["failure_cards"]} >= {"alignment_incompatible"}


def test_compose_scm_fragments_defers_pending_latent_bridge_and_rejects_cycles() -> None:
    fragment_a = _fragment(
        "a",
        interface_variables=["x", "y"],
        outputs=["x", "y"],
        definitions={"x": "Labor market state", "y": "Wage outcome"},
    )
    fragment_b = _fragment(
        "b",
        interface_variables=["x", "y"],
        inputs=["x", "y"],
        definitions={"x": "Labor market state", "y": "Wage outcome"},
    )
    pair_key = "a:x|b:x"
    report, mapping = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(explicit_latent_bridges={pair_key: "artifact:latent:x"}),
    )

    latent_result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["x", "y"], [_data_edge("x", "y", confidence=0.8)]),
                "b": _graph(["x", "y", "z"], [_data_edge("x", "z", confidence=0.7)]),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:5",
                "interface_mapping_ref": "artifact:mapping:5",
            },
        ),
        params={},
    )

    assert latent_result["composition_certificate"].status == "deferred"
    assert latent_result["composition_certificate"].structure_status == "valid"
    assert latent_result["composition_certificate"].review_status == "pending_review"
    assert latent_result["blocking_reasons"] == []
    assert {card.failure_type for card in latent_result["failure_cards"]} >= {
        "latent_bridge_pending_review"
    }

    exact_report, exact_mapping = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(),
    )
    cycle_result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["x", "y"], [_data_edge("x", "y", confidence=0.8)]),
                "b": _graph(["x", "y"], [_data_edge("y", "x", confidence=0.7)]),
            },
            alignment_report=exact_report,
            interface_mapping=exact_mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:6",
                "interface_mapping_ref": "artifact:mapping:6",
            },
        ),
        params={},
    )

    assert cycle_result["composition_certificate"].status == "broken"
    assert cycle_result["composition_certificate"].structure_status == "invalid"
    assert any("cycle" in reason.lower() for reason in cycle_result["blocking_reasons"])
    assert {card.failure_type for card in cycle_result["failure_cards"]} >= {"directed_cycle"}


def test_compose_scm_fragments_allows_human_verified_latent_bridge() -> None:
    fragment_a = _fragment(
        "a",
        interface_variables=["x"],
        outputs=["x"],
        definitions={"x": "Labor market state"},
    )
    fragment_b = _fragment(
        "b",
        interface_variables=["x"],
        inputs=["x"],
        definitions={"x": "Labor market state"},
    )
    report, mapping = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(
            explicit_latent_bridges={"a:x|b:x": "artifact:latent:x"},
            human_verified_pairs=["a:x|b:x"],
        ),
    )

    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=[fragment_a, fragment_b],
            fragment_graphs={
                "a": _graph(["x", "tax"], [_data_edge("tax", "x", confidence=0.8)]),
                "b": _graph(["x", "wages"], [_data_edge("x", "wages", confidence=0.7)]),
            },
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:6b",
                "interface_mapping_ref": "artifact:mapping:6b",
            },
        ),
        params={},
    )

    assert result["composition_certificate"].status == "preserved"
    assert result["composition_certificate"].structure_status == "valid"
    assert result["composition_certificate"].review_status == "clear"
    assert result["needs_expert_review"] is False
    assert result["failure_cards"] == []
