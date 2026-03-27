from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.query_preservation import (
    check_query_preservation,
    check_query_preservation_batch,
    evaluate_query_preservation,
    evaluate_query_preservation_batch,
    update_query_preservation_cache,
)
from polisyos.ir.analytics.alignment_certification import AlignmentVerificationConfig, verify_fragment_bundle_alignment
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, EdgeSource, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.cross_graph import CompositionCertificate, SCMFragment
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ComposeSCMFragments
from polisyos.foundry.methods.catalog.causal.protocols import FragmentCompositionData


def _edge(src: str, dst: str) -> CausalEdge:
    return CausalEdge(
        src=src,
        dst=dst,
        mark_src=EdgeMark.TAIL,
        mark_dst=EdgeMark.ARROW,
        sources=[EdgeSource.DATA],
        combined_confidence=0.8,
    )


def _bidirected(src: str, dst: str) -> CausalEdge:
    return CausalEdge(
        src=src,
        dst=dst,
        mark_src=EdgeMark.ARROW,
        mark_dst=EdgeMark.ARROW,
        sources=[EdgeSource.DATA],
        combined_confidence=0.6,
    )


def _graph(nodes: list[str], edges: list[CausalEdge], *, graph_type: GraphType = GraphType.DAG) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=graph_type,
        nodes=nodes,
        edges=edges,
        discovery_method="test_fixture",
    )


def _fragment(
    fragment_id: str,
    *,
    interface_variables: list[str],
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
) -> SCMFragment:
    return SCMFragment(
        fragment_id=fragment_id,
        graph_ref=f"artifact:graph:{fragment_id}",
        semantic_namespace=f"policy.{fragment_id}",
        interface_variables=interface_variables,
        exposed_inputs=list(inputs or []),
        exposed_outputs=list(outputs or []),
        variable_definitions={name: name.replace("_", " ").title() for name in interface_variables},
    )


def _compose(
    fragments: list[SCMFragment],
    fragment_graphs: dict[str, CausalGraphModel],
    *,
    config: AlignmentVerificationConfig | None = None,
    direct_stitch_pairs: list[tuple[str, str]] | None = None,
) -> tuple[CausalGraphModel, CompositionCertificate, object]:
    report, mapping = verify_fragment_bundle_alignment(
        fragments,
        config=config,
        stitch_pairs=direct_stitch_pairs,
    )
    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=fragments,
            fragment_graphs=fragment_graphs,
            alignment_report=report,
            interface_mapping=mapping,
            direct_stitch_pairs=list(direct_stitch_pairs or []),
            metadata={
                "alignment_report_ref": "artifact:alignment:test",
                "interface_mapping_ref": "artifact:mapping:test",
            },
        ),
        params={},
    )
    return result["composed_graph"], result["composition_certificate"], mapping


def test_check_query_preservation_preserved_for_supported_dag_query() -> None:
    fragments = [
        _fragment("core", interface_variables=["employment_rate", "wages"], outputs=["employment_rate", "wages"]),
        _fragment("training", interface_variables=["employment_rate", "wages"], inputs=["employment_rate", "wages"]),
    ]
    fragment_graphs = {
        "core": _graph(
            ["schooling", "employment_rate", "wages"],
            [
                _edge("employment_rate", "wages"),
            ],
        ),
        "training": _graph(
            ["employment_rate", "wages", "training_slots"],
            [_edge("employment_rate", "training_slots")],
        ),
    }
    composed_graph, certificate, mapping = _compose(fragments, fragment_graphs)
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="wages",
        condition={"schooling": 1.0},
    )

    assert (
        check_query_preservation(
            query,
            composed_graph=composed_graph,
            fragments=fragments,
            fragment_graphs=fragment_graphs,
            interface_mapping=mapping,
            composition_certificate=certificate,
        )
        == "preserved"
    )


def test_check_query_preservation_detects_broken_query_after_stitching() -> None:
    fragments = [
        _fragment(
            "core",
            interface_variables=["schooling", "employment_rate", "wages"],
            outputs=["schooling", "employment_rate", "wages"],
        ),
        _fragment(
            "aid",
            interface_variables=["schooling", "employment_rate", "wages"],
            inputs=["schooling", "employment_rate", "wages"],
        ),
    ]
    fragment_graphs = {
        "core": _graph(
            ["schooling", "employment_rate", "wages"],
            [
                _edge("employment_rate", "wages"),
            ],
        ),
        "aid": _graph(
            ["schooling", "employment_rate", "wages"],
            [
                _edge("employment_rate", "schooling"),
            ],
        ),
    }
    composed_graph, certificate, mapping = _compose(fragments, fragment_graphs)
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="wages",
        condition={"schooling": 1.0},
    )

    assert (
        check_query_preservation(
            query,
            composed_graph=composed_graph,
            fragments=fragments,
            fragment_graphs=fragment_graphs,
            interface_mapping=mapping,
            composition_certificate=certificate,
        )
        == "broken"
    )


def test_check_query_preservation_uses_m_separation_for_admg() -> None:
    fragments = [
        _fragment("core", interface_variables=["employment_rate", "wages"], outputs=["employment_rate", "wages"]),
        _fragment("spillover", interface_variables=["employment_rate", "wages"], inputs=["employment_rate", "wages"]),
    ]
    fragment_graphs = {
        "core": _graph(
            ["schooling", "employment_rate", "wages"],
            [
                _edge("schooling", "employment_rate"),
                _edge("schooling", "wages"),
                _edge("employment_rate", "wages"),
            ],
            graph_type=GraphType.ADMG,
        ),
        "spillover": _graph(
            ["employment_rate", "wages", "latent_shock"],
            [_bidirected("wages", "latent_shock")],
            graph_type=GraphType.ADMG,
        ),
    }
    report, mapping = verify_fragment_bundle_alignment(fragments)
    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=fragments,
            fragment_graphs=fragment_graphs,
            alignment_report=report,
            interface_mapping=mapping,
            metadata={
                "alignment_report_ref": "artifact:alignment:admg",
                "interface_mapping_ref": "artifact:mapping:admg",
            },
        ),
        params={},
    )
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="wages",
        condition={"schooling": 1.0},
    )

    assert (
        check_query_preservation(
            query,
            composed_graph=result["composed_graph"],
            fragments=fragments,
            fragment_graphs=fragment_graphs,
            interface_mapping=mapping,
            composition_certificate=result["composition_certificate"],
        )
        == "preserved"
    )


def test_check_query_preservation_returns_unknown_for_unsupported_query_shape() -> None:
    fragments = [
        _fragment("core", interface_variables=["employment_rate"], outputs=["employment_rate"]),
        _fragment("training", interface_variables=["employment_rate"], inputs=["employment_rate"]),
    ]
    fragment_graphs = {
        "core": _graph(["schooling", "employment_rate", "wages"], [_edge("schooling", "employment_rate")]),
        "training": _graph(["employment_rate", "training_slots"], [_edge("employment_rate", "training_slots")]),
    }
    composed_graph, certificate, mapping = _compose(fragments, fragment_graphs)
    query = CausalQuery(
        query_type=QueryType.COUNTERFACTUAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="wages",
        condition={"schooling": 1.0},
    )

    assert (
        check_query_preservation(
            query,
            composed_graph=composed_graph,
            fragments=fragments,
            fragment_graphs=fragment_graphs,
            interface_mapping=mapping,
            composition_certificate=certificate,
        )
        == "unknown"
    )


def test_evaluate_query_preservation_batch_surfaces_reason_codes() -> None:
    fragments = [
        _fragment("core", interface_variables=["employment_rate"], outputs=["employment_rate"]),
        _fragment("training", interface_variables=["employment_rate"], inputs=["employment_rate"]),
    ]
    fragment_graphs = {
        "core": _graph(["schooling", "employment_rate", "wages"], [_edge("schooling", "employment_rate")]),
        "training": _graph(["employment_rate", "training_slots"], [_edge("employment_rate", "training_slots")]),
    }
    composed_graph, certificate, mapping = _compose(fragments, fragment_graphs)
    query = CausalQuery(
        query_type=QueryType.COUNTERFACTUAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="wages",
        condition={"schooling": 1.0},
    )

    traces = evaluate_query_preservation_batch(
        [query],
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=mapping,
        composition_certificate=certificate,
    )

    assert len(traces) == 1
    trace = next(iter(traces.values()))
    assert trace.status == "unknown"
    assert trace.reason_code == "unsupported_query_type"
    assert trace.query_semantics == "counterfactual"


def test_query_preservation_cache_is_stable_and_invalidates_when_composition_changes() -> None:
    fragments = [
        _fragment(
            "core",
            interface_variables=["schooling", "employment_rate", "wages"],
            outputs=["schooling", "employment_rate", "wages"],
        ),
        _fragment(
            "training",
            interface_variables=["schooling", "employment_rate", "wages"],
            inputs=["schooling", "employment_rate", "wages"],
        ),
    ]
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="wages",
        condition={"schooling": 1.0},
    )
    fragment_graphs_v1 = {
        "core": _graph(
            ["schooling", "employment_rate", "wages"],
            [
                _edge("employment_rate", "wages"),
            ],
        ),
        "training": _graph(
            ["schooling", "employment_rate", "wages", "training_slots"],
            [_edge("employment_rate", "training_slots")],
        ),
    }
    composed_graph_v1, certificate_v1, mapping = _compose(fragments, fragment_graphs_v1)

    updated_once, statuses_once = update_query_preservation_cache(
        certificate_v1,
        queries=[query],
        composed_graph=composed_graph_v1,
        fragments=fragments,
        fragment_graphs=fragment_graphs_v1,
        interface_mapping=mapping,
    )
    updated_twice, statuses_twice = update_query_preservation_cache(
        updated_once,
        queries=[query],
        composed_graph=composed_graph_v1,
        fragments=fragments,
        fragment_graphs=fragment_graphs_v1,
        interface_mapping=mapping,
    )

    assert len(updated_once.checked_queries) == 1
    assert updated_once.checked_queries == updated_twice.checked_queries
    assert statuses_once == statuses_twice

    fragment_graphs_v2 = {
        "core": fragment_graphs_v1["core"],
        "training": _graph(
            ["schooling", "employment_rate", "wages", "training_slots"],
            [
                _edge("employment_rate", "training_slots"),
                _edge("employment_rate", "schooling"),
            ],
        ),
    }
    composed_graph_v2, _, _ = _compose(fragments, fragment_graphs_v2)
    updated_v2, statuses_v2 = update_query_preservation_cache(
        updated_once,
        queries=[query],
        composed_graph=composed_graph_v2,
        fragments=fragments,
        fragment_graphs=fragment_graphs_v2,
        interface_mapping=mapping,
    )

    assert len(updated_v2.checked_queries) == 2
    assert set(statuses_v2.values()) == {"broken"}


def test_check_query_preservation_batch_returns_fingerprint_status_map() -> None:
    fragments = [
        _fragment("core", interface_variables=["employment_rate", "wages"], outputs=["employment_rate", "wages"]),
        _fragment("training", interface_variables=["employment_rate", "wages"], inputs=["employment_rate", "wages"]),
    ]
    fragment_graphs = {
        "core": _graph(
            ["schooling", "employment_rate", "wages"],
            [
                _edge("schooling", "employment_rate"),
                _edge("schooling", "wages"),
                _edge("employment_rate", "wages"),
            ],
        ),
        "training": _graph(
            ["employment_rate", "wages", "training_slots"],
            [_edge("employment_rate", "training_slots")],
        ),
    }
    composed_graph, certificate, mapping = _compose(fragments, fragment_graphs)
    queries = [
        CausalQuery(
            query_type=QueryType.INTERVENTIONAL,
            treatment_variable="employment_rate",
            treatment_value=1.0,
            outcome_variable="wages",
            condition={"schooling": 1.0},
        ),
        CausalQuery(
            query_type=QueryType.COUNTERFACTUAL,
            treatment_variable="employment_rate",
            treatment_value=1.0,
            outcome_variable="wages",
            condition={"schooling": 1.0},
        ),
    ]

    batch = check_query_preservation_batch(
        queries,
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=mapping,
        composition_certificate=certificate,
    )

    assert len(batch) == 2
    assert set(batch.values()) == {"preserved", "unknown"}


def test_evaluate_query_preservation_uses_witness_subgraph_for_chain() -> None:
    fragments = [
        _fragment("a", interface_variables=["employment_rate"], outputs=["employment_rate"]),
        _fragment("b", interface_variables=["employment_rate", "wages"], inputs=["employment_rate"], outputs=["wages"]),
        _fragment("c", interface_variables=["wages"], inputs=["wages"]),
    ]
    fragment_graphs = {
        "a": _graph(["schooling", "employment_rate"], [_edge("schooling", "employment_rate")]),
        "b": _graph(["employment_rate", "wages"], [_edge("employment_rate", "wages")]),
        "c": _graph(["wages", "consumption"], [_edge("wages", "consumption")]),
    }
    composed_graph, certificate, mapping = _compose(fragments, fragment_graphs)
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="consumption",
        condition={"schooling": 1.0},
    )

    trace = evaluate_query_preservation(
        query,
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=mapping,
        composition_certificate=certificate,
    )

    assert trace.status == "preserved"
    assert trace.reason_code == "evaluated"
    assert trace.witness_fragment_ids == ("a", "b", "c")
    assert trace.source_witness_kind == "stitched_subgraph"
    assert trace.assumption_boundary is None


def test_evaluate_query_preservation_marks_verified_latent_bridge_as_research_boundary() -> None:
    fragments = [
        _fragment("a", interface_variables=["x", "y"], outputs=["x", "y"]),
        _fragment("b", interface_variables=["x", "y"], inputs=["x", "y"]),
    ]
    fragment_graphs = {
        "a": _graph(
            ["schooling", "x", "y"],
            [
                _edge("schooling", "x"),
                _edge("schooling", "y"),
                _edge("x", "y"),
            ],
        ),
        "b": _graph(["x", "y", "spill"], [_edge("x", "spill")]),
    }
    composed_graph, certificate, mapping = _compose(
        fragments,
        fragment_graphs,
        config=AlignmentVerificationConfig(
            explicit_latent_bridges={
                "a:x|b:x": "artifact:latent:x",
                "a:y|b:y": "artifact:latent:y",
            },
            human_verified_pairs=["a:x|b:x", "a:y|b:y"],
        ),
    )
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="x",
        treatment_value=1.0,
        outcome_variable="y",
        condition={"schooling": 1.0},
    )

    trace = evaluate_query_preservation(
        query,
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=mapping,
        composition_certificate=certificate,
    )

    assert certificate.status == "preserved"
    assert trace.status == "unknown"
    assert trace.reason_code == "latent_bridge_research_boundary"
    assert trace.assumption_boundary == "latent_bridge"
