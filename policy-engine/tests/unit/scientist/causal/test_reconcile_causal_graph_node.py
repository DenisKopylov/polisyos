from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.composition_failure_cards import (
    load_composition_failure_card_bundle,
)
from polisyos.ir.analytics.alignment_certification import (
    AlignmentVerificationConfig,
    load_alignment_report,
    persist_alignment_report,
    verify_fragment_bundle_alignment,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeSource,
    GraphType,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.cross_graph import (
    SCMFragment,
    load_composition_certificate,
    load_interface_mapping,
    persist_interface_mapping,
    persist_scm_fragment,
)
from polisyos.ir.analytics.literature import (
    LiteratureCausalPrior,
    LiteratureEdgePrior,
    persist_literature_causal_prior,
)
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    load_negative_certificate,
)
from polisyos.ir.refs import NegativeCertificateRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
    ReconcileCausalGraphNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ALIGNMENT_REPORT_REF,
    ARTIFACT_COMPOSITION_CERTIFICATE_REF,
    ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF,
    ARTIFACT_INTERFACE_MAPPING_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)


def _build_ctx(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_phase9_recon")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.phase9.recon"))
    return ctx


def test_reconcile_causal_graph_node_persists_graph_and_params(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    prior = LiteratureCausalPrior(
        edges=[LiteratureEdgePrior(src="tax", dst="employment", confidence=0.7)],
        skg_version_id=2,
    )
    prior_ref = persist_literature_causal_prior(ctx.store, prior)
    data_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax", "employment"],
        edges=[
            CausalEdge(
                src="tax",
                dst="employment",
                sources=[EdgeSource.DATA],
                data_confidence=0.85,
                combined_confidence=0.85,
            )
        ],
    )
    state = ExperimentState(
        run_id="R_phase9_recon",
        artifacts_index={ARTIFACT_LITERATURE_PRIOR_REF: prior_ref},
        params={
            "data_causal_graph": data_graph.model_dump(mode="json"),
            "llm_structural_hints": [
                {"src": "employment", "dst": "tax", "confidence": 0.9},
            ],
        },
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in outcome.state.artifacts_index
    assert outcome.state.params["needs_expert_review"] is True
    assert "reconciliation_diagnostics" in outcome.state.params
    graph_ref = outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
    graph = load_causal_graph_model(ctx.store, graph_ref)
    assert graph.metadata["needs_expert_review"] is True


def test_reconcile_causal_graph_node_skips_without_data_graph(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    state = ExperimentState(run_id="R_phase9_recon_skip")

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "skip"


def test_reconcile_causal_graph_node_composes_fragments_and_persists_artifacts(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    graph_a = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["employment_rate", "tax"],
        edges=[
            CausalEdge(
                src="tax",
                dst="employment_rate",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            )
        ],
    )
    graph_b = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["employment_rate", "wages"],
        edges=[
            CausalEdge(
                src="employment_rate",
                dst="wages",
                sources=[EdgeSource.DATA],
                data_confidence=0.75,
                combined_confidence=0.75,
            )
        ],
    )
    graph_a_ref = persist_causal_graph_model(ctx.store, graph_a)
    graph_b_ref = persist_causal_graph_model(ctx.store, graph_b)
    fragment_a_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="labor_a",
            graph_ref=str(graph_a_ref.artifact_id),
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate"],
            exposed_outputs=["employment_rate"],
            variable_definitions={"employment_rate": "Employment rate"},
            variable_units={"employment_rate": "percent"},
        ),
    )
    fragment_b_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="labor_b",
            graph_ref=str(graph_b_ref.artifact_id),
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate"],
            exposed_inputs=["employment_rate"],
            variable_definitions={"employment_rate": "Employment rate"},
            variable_units={"employment_rate": "percent"},
        ),
    )

    state = ExperimentState(
        run_id="R_phase9_compose",
        params={
            "scm_fragment_refs": [
                str(fragment_a_ref.artifact_id),
                str(fragment_b_ref.artifact_id),
            ]
        },
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in outcome.state.artifacts_index
    assert ARTIFACT_ALIGNMENT_REPORT_REF in outcome.state.artifacts_index
    assert ARTIFACT_INTERFACE_MAPPING_REF in outcome.state.artifacts_index
    assert ARTIFACT_COMPOSITION_CERTIFICATE_REF in outcome.state.artifacts_index
    composed_graph = load_causal_graph_model(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF],
    )
    mapping = load_interface_mapping(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF],
    )
    certificate = load_composition_certificate(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF],
    )

    assert any(node.startswith("stitched::employment_rate") for node in composed_graph.nodes)
    assert len(mapping.entries) == 1
    assert certificate.status == "preserved"
    assert certificate.structure_status == "valid"
    assert certificate.review_status == "clear"
    assert outcome.state.params["needs_expert_review"] is False
    assert outcome.state.params["reconciliation_diagnostics"]["structure_status"] == "valid"
    assert outcome.state.params["reconciliation_diagnostics"]["review_status"] == "clear"


def test_reconcile_causal_graph_node_reuses_precomputed_alignment_artifacts(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    graph_a = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["employment_rate", "tax"],
        edges=[CausalEdge(src="tax", dst="employment_rate", combined_confidence=0.8)],
    )
    graph_b = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["employment_rate", "wages"],
        edges=[CausalEdge(src="employment_rate", dst="wages", combined_confidence=0.7)],
    )
    graph_a_ref = persist_causal_graph_model(ctx.store, graph_a)
    graph_b_ref = persist_causal_graph_model(ctx.store, graph_b)
    fragments = [
        {
            "fragment_id": "labor_a",
            "graph_ref": str(graph_a_ref.artifact_id),
            "semantic_namespace": "policy.labor",
            "interface_variables": ["employment_rate"],
            "exposed_outputs": ["employment_rate"],
            "variable_definitions": {"employment_rate": "Employment rate"},
            "variable_units": {"employment_rate": "percent"},
        },
        {
            "fragment_id": "labor_b",
            "graph_ref": str(graph_b_ref.artifact_id),
            "semantic_namespace": "policy.labor",
            "interface_variables": ["employment_rate"],
            "exposed_inputs": ["employment_rate"],
            "variable_definitions": {"employment_rate": "Employment rate"},
            "variable_units": {"employment_rate": "percent"},
        },
    ]
    report, mapping = verify_fragment_bundle_alignment(
        [SCMFragment.model_validate(item) for item in fragments]
    )
    report_ref = persist_alignment_report(ctx.store, report)
    mapping_ref = persist_interface_mapping(ctx.store, mapping)

    state = ExperimentState(
        run_id="R_phase9_compose_reuse",
        artifacts_index={
            ARTIFACT_ALIGNMENT_REPORT_REF: report_ref,
            ARTIFACT_INTERFACE_MAPPING_REF: mapping_ref,
        },
        params={"scm_fragments": fragments},
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert (
        outcome.state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF].artifact_id
        == report_ref.artifact_id
    )
    assert (
        outcome.state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF].artifact_id
        == mapping_ref.artifact_id
    )
    loaded_report = load_alignment_report(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF],
    )
    assert loaded_report.overall_status.value == "aligned"
    assert loaded_report.review_status.value == "clear"


def test_reconcile_causal_graph_node_updates_query_preservation_cache_without_recomposing(
    tmp_path,
) -> None:
    ctx = _build_ctx(tmp_path)
    graph_a = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["schooling", "employment_rate", "wages"],
        edges=[
            CausalEdge(
                src="schooling",
                dst="employment_rate",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
            CausalEdge(
                src="schooling",
                dst="wages",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
            CausalEdge(
                src="employment_rate",
                dst="wages",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
        ],
    )
    graph_b = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["employment_rate", "wages", "training_slots"],
        edges=[
            CausalEdge(
                src="employment_rate",
                dst="training_slots",
                sources=[EdgeSource.DATA],
                data_confidence=0.75,
                combined_confidence=0.75,
            )
        ],
    )
    graph_a_ref = persist_causal_graph_model(ctx.store, graph_a)
    graph_b_ref = persist_causal_graph_model(ctx.store, graph_b)
    fragment_a_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="labor_core",
            graph_ref=str(graph_a_ref.artifact_id),
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate", "wages"],
            exposed_outputs=["employment_rate", "wages"],
            variable_definitions={
                "employment_rate": "Employment rate",
                "wages": "Average wage level",
            },
            variable_units={"employment_rate": "percent", "wages": "usd_per_month"},
        ),
    )
    fragment_b_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="training",
            graph_ref=str(graph_b_ref.artifact_id),
            semantic_namespace="policy.training",
            interface_variables=["employment_rate", "wages"],
            exposed_inputs=["employment_rate", "wages"],
            variable_definitions={
                "employment_rate": "Employment rate",
                "wages": "Average wage level",
            },
            variable_units={"employment_rate": "percent", "wages": "usd_per_month"},
        ),
    )

    initial_state = ExperimentState(
        run_id="R_phase9_compose_query",
        params={
            "scm_fragment_refs": [
                str(fragment_a_ref.artifact_id),
                str(fragment_b_ref.artifact_id),
            ]
        },
    )
    initial_outcome = ReconcileCausalGraphNode().execute(ctx, initial_state)
    assert initial_outcome.status == "ok"

    replay_state = initial_outcome.state.model_copy(deep=True)
    replay_state.params.pop("scm_fragment_refs", None)
    replay_state.params.pop("scm_fragments", None)
    replay_state.params["query_preservation_queries"] = [
        CausalQuery(
            query_type=QueryType.INTERVENTIONAL,
            treatment_variable="employment_rate",
            treatment_value=1.0,
            outcome_variable="wages",
            condition={"schooling": 1.0},
        ).model_dump(mode="json")
    ]
    replay_outcome = ReconcileCausalGraphNode().execute(ctx, replay_state)

    assert replay_outcome.status == "ok"
    certificate = load_composition_certificate(
        ctx.store,
        replay_outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF],
    )
    assert len(certificate.checked_queries) == 1
    assert set(certificate.checked_queries.values()) == {"preserved"}
    diagnostics = replay_outcome.state.params["reconciliation_diagnostics"]
    assert diagnostics["query_preservation_statuses"] == certificate.checked_queries
    assert set(diagnostics["query_preservation_reasons"].values()) == {"evaluated"}


def test_reconcile_causal_graph_node_persists_latent_projection_certificate_artifacts(
    tmp_path,
) -> None:
    ctx = _build_ctx(tmp_path)
    graph_a = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "shared_pressure", "mediator"],
        edges=[
            CausalEdge(
                src="shared_pressure",
                dst="policy",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
            CausalEdge(
                src="policy",
                dst="mediator",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
        ],
    )
    graph_b = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["shared_pressure", "mediator", "outcome"],
        edges=[
            CausalEdge(
                src="shared_pressure",
                dst="outcome",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
            CausalEdge(
                src="mediator",
                dst="outcome",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
        ],
    )
    graph_a_ref = persist_causal_graph_model(ctx.store, graph_a)
    graph_b_ref = persist_causal_graph_model(ctx.store, graph_b)
    fragment_a_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="a",
            graph_ref=str(graph_a_ref.artifact_id),
            semantic_namespace="policy.a",
            interface_variables=["shared_pressure", "mediator"],
            exposed_outputs=["shared_pressure", "mediator"],
            variable_definitions={
                "shared_pressure": "Shared pressure index",
                "mediator": "Observed mediator",
            },
            variable_units={"shared_pressure": "index", "mediator": "points"},
        ),
    )
    fragment_b_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="b",
            graph_ref=str(graph_b_ref.artifact_id),
            semantic_namespace="policy.b",
            interface_variables=["shared_pressure", "mediator"],
            exposed_inputs=["shared_pressure", "mediator"],
            variable_definitions={
                "shared_pressure": "Shared pressure index",
                "mediator": "Observed mediator",
            },
            variable_units={"shared_pressure": "index", "mediator": "points"},
        ),
    )

    state = ExperimentState(
        run_id="R_phase9_latent_projection_frontdoor",
        params={
            "scm_fragment_refs": [
                str(fragment_a_ref.artifact_id),
                str(fragment_b_ref.artifact_id),
            ],
            "alignment_verification_config": AlignmentVerificationConfig(
                explicit_latent_bridges={
                    "a:shared_pressure|b:shared_pressure": "artifact:latent:shared_pressure"
                },
                human_verified_pairs=["a:shared_pressure|b:shared_pressure"],
            ).model_dump(mode="json"),
            "query_preservation_queries": [
                CausalQuery(
                    query_type=QueryType.INTERVENTIONAL,
                    treatment_variable="policy",
                    treatment_value=1.0,
                    outcome_variable="outcome",
                ).model_dump(mode="json")
            ],
        },
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    certificate = load_composition_certificate(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF],
    )
    assert len(certificate.query_certificates) == 1
    record = next(iter(certificate.query_certificates.values()))
    assert record.status == "preserved"
    assert record.theorem_family == "frontdoor_exact"
    assert record.latent_projection_ref is not None
    assert record.negative_certificate_ref is None
    diagnostics = outcome.state.params["reconciliation_diagnostics"]
    trace_payload = next(iter(diagnostics["query_preservation_traces"].values()))
    assert trace_payload["theorem_family"] == "frontdoor_exact"
    assert trace_payload["latent_projection_ref"] == record.latent_projection_ref


def test_reconcile_causal_graph_node_persists_negative_certificate_for_latent_hedge(
    tmp_path,
) -> None:
    ctx = _build_ctx(tmp_path)
    graph_a = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["shared_pressure", "policy"],
        edges=[
            CausalEdge(
                src="shared_pressure",
                dst="policy",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
        ],
    )
    graph_b = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["shared_pressure", "policy", "outcome"],
        edges=[
            CausalEdge(
                src="shared_pressure",
                dst="outcome",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
            CausalEdge(
                src="policy",
                dst="outcome",
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
                combined_confidence=0.8,
            ),
        ],
    )
    graph_a_ref = persist_causal_graph_model(ctx.store, graph_a)
    graph_b_ref = persist_causal_graph_model(ctx.store, graph_b)
    fragment_a_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="a",
            graph_ref=str(graph_a_ref.artifact_id),
            semantic_namespace="policy.a",
            interface_variables=["shared_pressure", "policy"],
            exposed_outputs=["shared_pressure", "policy"],
            variable_definitions={
                "shared_pressure": "Shared pressure index",
                "policy": "Policy switch",
            },
            variable_units={"shared_pressure": "index", "policy": "binary"},
        ),
    )
    fragment_b_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="b",
            graph_ref=str(graph_b_ref.artifact_id),
            semantic_namespace="policy.b",
            interface_variables=["shared_pressure", "policy"],
            exposed_inputs=["shared_pressure", "policy"],
            variable_definitions={
                "shared_pressure": "Shared pressure index",
                "policy": "Policy switch",
            },
            variable_units={"shared_pressure": "index", "policy": "binary"},
        ),
    )

    state = ExperimentState(
        run_id="R_phase9_latent_projection_hedge",
        params={
            "scm_fragment_refs": [
                str(fragment_a_ref.artifact_id),
                str(fragment_b_ref.artifact_id),
            ],
            "alignment_verification_config": AlignmentVerificationConfig(
                explicit_latent_bridges={
                    "a:shared_pressure|b:shared_pressure": "artifact:latent:shared_pressure"
                },
                human_verified_pairs=["a:shared_pressure|b:shared_pressure"],
            ).model_dump(mode="json"),
            "query_preservation_queries": [
                CausalQuery(
                    query_type=QueryType.INTERVENTIONAL,
                    treatment_variable="policy",
                    treatment_value=1.0,
                    outcome_variable="outcome",
                ).model_dump(mode="json")
            ],
        },
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    certificate = load_composition_certificate(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF],
    )
    assert len(certificate.query_certificates) == 1
    record = next(iter(certificate.query_certificates.values()))
    assert record.status == "broken"
    assert record.negative_certificate_ref is not None
    negative_certificate = load_negative_certificate(
        ctx.store,
        NegativeCertificateRef.model_validate({"artifact_id": record.negative_certificate_ref}),
    )
    assert negative_certificate.blocking_type is BlockingType.HEDGE_STRUCTURE
    diagnostics = outcome.state.params["reconciliation_diagnostics"]
    trace_payload = next(iter(diagnostics["query_preservation_traces"].values()))
    assert trace_payload["negative_certificate_ref"] == record.negative_certificate_ref


def test_reconcile_causal_graph_node_persists_failure_card_bundle_for_broken_composition(
    tmp_path,
) -> None:
    ctx = _build_ctx(tmp_path)
    labor_graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["rate"], edges=[]),
    )
    health_graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["rate"], edges=[]),
    )
    fragment_a_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="labor",
            graph_ref=str(labor_graph_ref.artifact_id),
            semantic_namespace="policy.labor",
            interface_variables=["rate"],
            exposed_outputs=["rate"],
            variable_definitions={"rate": "Employment rate among working-age adults"},
            variable_units={"rate": "percent"},
            measurement_models={"rate": "artifact:mm:labor"},
        ),
    )
    fragment_b_ref = persist_scm_fragment(
        ctx.store,
        SCMFragment(
            fragment_id="health",
            graph_ref=str(health_graph_ref.artifact_id),
            semantic_namespace="policy.health",
            interface_variables=["rate"],
            exposed_inputs=["rate"],
            variable_definitions={"rate": "Hospital occupancy beds"},
            variable_units={"rate": "beds_per_hospital"},
            measurement_models={"rate": "artifact:mm:health"},
        ),
    )

    state = ExperimentState(
        run_id="R_phase9_compose_failure_cards",
        params={
            "scm_fragment_refs": [
                str(fragment_a_ref.artifact_id),
                str(fragment_b_ref.artifact_id),
            ]
        },
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF not in outcome.state.artifacts_index
    assert ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF in outcome.state.artifacts_index
    certificate = load_composition_certificate(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF],
    )
    assert certificate.status == "broken"
    assert certificate.failure_card_bundle_ref is not None
    bundle = load_composition_failure_card_bundle(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF],
    )
    assert {card.failure_type for card in bundle.cards} >= {"alignment_incompatible"}


def test_reconcile_causal_graph_node_rejects_disconnected_fragment_topology(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    graph_a_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["employment_rate"], edges=[]),
    )
    graph_b_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["employment_rate"], edges=[]),
    )
    graph_c_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["hospital_occupancy"], edges=[]),
    )
    refs = [
        persist_scm_fragment(
            ctx.store,
            SCMFragment(
                fragment_id="a",
                graph_ref=str(graph_a_ref.artifact_id),
                semantic_namespace="policy.labor",
                interface_variables=["employment_rate"],
                exposed_outputs=["employment_rate"],
                variable_definitions={"employment_rate": "Employment rate"},
                variable_units={"employment_rate": "percent"},
            ),
        ),
        persist_scm_fragment(
            ctx.store,
            SCMFragment(
                fragment_id="b",
                graph_ref=str(graph_b_ref.artifact_id),
                semantic_namespace="policy.training",
                interface_variables=["employment_rate"],
                exposed_inputs=["employment_rate"],
                variable_definitions={"employment_rate": "Employment rate"},
                variable_units={"employment_rate": "percent"},
            ),
        ),
        persist_scm_fragment(
            ctx.store,
            SCMFragment(
                fragment_id="c",
                graph_ref=str(graph_c_ref.artifact_id),
                semantic_namespace="policy.health",
                interface_variables=["hospital_occupancy"],
                exposed_outputs=["hospital_occupancy"],
                variable_definitions={"hospital_occupancy": "Hospital occupancy rate"},
                variable_units={"hospital_occupancy": "beds_per_hospital"},
            ),
        ),
    ]
    state = ExperimentState(
        run_id="R_phase9_compose_disconnected",
        params={"scm_fragment_refs": [str(ref.artifact_id) for ref in refs]},
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    certificate = load_composition_certificate(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF],
    )
    assert certificate.status == "broken"
    bundle = load_composition_failure_card_bundle(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF],
    )
    assert {card.failure_type for card in bundle.cards} >= {"fragment_topology_disconnected"}
