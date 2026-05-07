from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import (
    LATENT_CARDINALITY_EVIDENCE_KEY,
    LATENT_CARDINALITY_FAILURE_REASONS_KEY,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    ConstraintEvaluationResult,
    LatentAssumptionCard,
    LatentBlockEvidence,
    LatentBlockProposal,
    LatentBlockStatus,
    LatentCardinalityEvidencePayload,
    LatentCausalRole,
    LatentDiscoveryBundle,
    LatentGraphStatus,
    LatentTrustLevel,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.scientist.methods.causal.latent_separation import SEPARATION_DIAGNOSTIC_INPUTS_KEY
from polisyos.scientist.methods.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
    edge_key_for_edge,
    graph_hypothesis_from_report,
    infer_algorithm_family,
    load_graph_hypothesis,
    persist_graph_hypothesis,
)


def _graph(
    *,
    graph_type: GraphType,
    edges: list[CausalEdge],
    nodes: list[str] | None = None,
    discovery_method: str = "",
) -> CausalGraphModel:
    resolved_nodes = nodes or sorted({node for edge in edges for node in (edge.src, edge.dst)})
    return CausalGraphModel(
        graph_type=graph_type,
        nodes=resolved_nodes,
        edges=edges,
        discovery_method=discovery_method,
    )


def test_graph_hypothesis_uses_shared_bootstrap_then_combined_then_data_confidence() -> None:
    edge = CausalEdge(
        src="X",
        dst="Y",
        lag=2,
        combined_confidence=0.81,
        data_confidence=0.37,
    )
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(graph_type=GraphType.CPDAG, edges=[edge], discovery_method="pc"),
        bootstrap_stability={edge_key_for_edge(edge): 0.99},
    )

    hypothesis_with_shared = graph_hypothesis_from_report(
        report,
        hypothesis_id="shared",
        shared_bootstrap_stability={edge_key_for_edge(edge): 0.62},
    )
    hypothesis_without_shared = graph_hypothesis_from_report(
        report,
        hypothesis_id="local",
    )

    assert edge_key_for_edge(edge) == "X->Y@lag=2"
    assert hypothesis_with_shared.edge_confidence["X->Y@lag=2"] == 0.62
    assert hypothesis_without_shared.edge_confidence["X->Y@lag=2"] == 0.81


def test_graph_hypothesis_persists_and_loads_from_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    graph = _graph(
        graph_type=GraphType.DAG,
        edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.7)],
        discovery_method="dagma",
    )
    hypothesis = GraphHypothesis(
        hypothesis_id="dagma_0",
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
        method=DiscoveryMethod.DAGMA,
        graph=graph,
        edge_confidence={"X->Y": 0.7},
        assumptions=["continuous optimization over DAG structure"],
        compute_footprint=ComputeFootprint(
            runtime_seconds=1.25,
            timeout_seconds=30.0,
            n_samples=100,
            n_variables=2,
            n_bootstrap=0,
            random_seed=7,
            backend="optimizer=dagma",
            method_params={"alpha": 0.1},
            metadata={"report_method": "dagma"},
        ),
        metadata={"source": "unit_test"},
    )

    ref = persist_graph_hypothesis(store, hypothesis)
    loaded = load_graph_hypothesis(store, ref)

    assert ref.kind == "scientist.graph_hypothesis"
    assert loaded == hypothesis


def test_graph_hypothesis_extracts_failure_reasons_from_report_warnings() -> None:
    report = CausalDiscoveryReport(
        method="fci",
        graph=_graph(
            graph_type=GraphType.PAG,
            edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
            discovery_method="fci",
        ),
        warnings=[
            "algorithm_failed:TimeoutError: backend timed out",
            "soft warning that should remain informational",
        ],
        metadata={"backend": "optional"},
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="fci_0")

    assert hypothesis.method is DiscoveryMethod.FCI
    assert hypothesis.algorithm_family is DiscoveryAlgorithmFamily.CONSTRAINT_BASED
    assert hypothesis.failure_reasons == ["algorithm_failed:TimeoutError: backend timed out"]
    assert "soft warning that should remain informational" in hypothesis.warnings


def test_graph_hypothesis_carries_typed_discovery_payloads_from_report() -> None:
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(
            graph_type=GraphType.DAG,
            edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.8)],
            discovery_method="pc",
        ),
        algebraic_constraints=AlgebraicConstraintReport(
            severity="warning",
            violated_constraints_preview=[
                ConstraintEvaluationResult(
                    constraint_id="ci:X_Y",
                    family=AlgebraicConstraintFamily.CI,
                    status="violated",
                    severity="blocker",
                )
            ],
        ),
        latent_discovery=LatentDiscoveryBundle(
            proposed_latent_nodes=["U_income"],
            inducing_environments=["region"],
            identification_conditions=["proxy_quality"],
            falsification_tests=["negative_control_outcome"],
            trust_level=LatentTrustLevel.RESEARCH,
            assumption_cards=[
                LatentAssumptionCard(
                    assumption_id="latent_card",
                    title="Latent confounding remains research-only",
                    description="Observed proxies may still mask latent confounding.",
                )
            ],
            no_promotion_reasons=["latent_discovery_proof_only"],
        ),
        metadata={"algebraic_constraint_severity": "warning"},
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="pc_0")

    assert hypothesis.algebraic_constraints == report.algebraic_constraints
    assert hypothesis.latent_discovery == report.latent_discovery
    assert hypothesis.source_discovery_report_ref is None


def test_infer_algorithm_family_supports_functional_methods() -> None:
    assert infer_algorithm_family(DiscoveryMethod.ANM) is DiscoveryAlgorithmFamily.FUNCTIONAL
    assert (
        infer_algorithm_family(DiscoveryMethod.PAIRWISE_HEURISTIC)
        is DiscoveryAlgorithmFamily.FUNCTIONAL
    )


def test_graph_hypothesis_auto_produces_latent_bundle_from_structured_evidence() -> None:
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(
            graph_type=GraphType.DAG,
            edges=[
                CausalEdge(src="W_anchor", dst="X", combined_confidence=0.9),
                CausalEdge(src="W_anchor", dst="Y", combined_confidence=0.9),
                CausalEdge(src="X", dst="Y", combined_confidence=0.8),
            ],
            nodes=["W_anchor", "X", "Y", "R1", "R2", "R3", "W", "Z"],
            discovery_method="pc",
        ),
        metadata={
            LATENT_CARDINALITY_EVIDENCE_KEY: LatentCardinalityEvidencePayload(
                model_class="ME-LiNGLaH-S",
                treatment_variable="X",
                outcome_variable="Y",
                inducing_environments=["region_a", "region_b"],
                latent_blocks=[
                    LatentBlockProposal(
                        latent_id="U_01",
                        block_size=1,
                        role=LatentCausalRole.CONFOUNDER,
                        status=LatentBlockStatus.PARTIAL,
                        graph_status=LatentGraphStatus.PARTIAL,
                        anchor_variables=["W_anchor"],
                        informative_environment_contrasts=["region_a_vs_region_b"],
                        evidence=LatentBlockEvidence(
                            gin_supported=True,
                            atomic_structure_supported=True,
                            shift_localized=True,
                            minimal_decomposition_supported=True,
                            role_rule_supported=False,
                            pure_child_count=2,
                            neighbor_count=3,
                            rank=1,
                        ),
                    )
                ],
            ).model_dump(mode="json"),
            "latent_separation_measurement": {
                "status": "passed",
                "tetrad_test": "single_signal_tetrad_passed",
                "invariance_test": "measurement_invariance_passed",
                "repeated_indicator_blocks": ["R_block"],
                "repeated_indicator_block_variables": {"R_block": ["R1", "R2", "R3"]},
            },
            "latent_separation_proxy": {
                "status": "passed",
                "bridge_test": "proximal_bridge_solved",
                "bridge_stability": "cross_environment_stable",
                "proxy_blocks": ["W", "Z"],
                "proxy_block_variables": {"W": ["W"], "Z": ["Z"]},
            },
            "latent_separation_environment": {
                "status": "passed",
                "residual_invariance": "post_calibration_residual_invariance_failed",
                "post_calibration_shift": "not_restored",
                "environments": ["region_a", "region_b"],
                "n_env": 2,
                "route_to_latent_aware_discovery": True,
            },
            "latent_separation_design": {
                "environments": ["region_a", "region_b"],
                "proxy_blocks": ["W", "Z"],
                "repeated_indicator_blocks": ["R_block"],
            },
        },
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="pc_latent_auto")

    assert hypothesis.latent_discovery is not None
    assert hypothesis.latent_discovery.readiness_cap == "proof_only"
    assert hypothesis.latent_discovery.promotion_allowed is False
    assert hypothesis.latent_discovery.trust_level is LatentTrustLevel.CONDITIONAL
    assert hypothesis.latent_discovery.proposed_latent_nodes == [
        "U_01|block_size=1|role=confounder|status=identified"
    ]
    assert LATENT_CARDINALITY_EVIDENCE_KEY in hypothesis.latent_discovery.metadata
    assert LATENT_CARDINALITY_FAILURE_REASONS_KEY in hypothesis.latent_discovery.metadata
    assert hypothesis.latent_discovery.metadata[LATENT_CARDINALITY_FAILURE_REASONS_KEY] == []
    assert SEPARATION_DIAGNOSTIC_INPUTS_KEY in hypothesis.latent_discovery.metadata
    assert hypothesis.latent_discovery.metadata["separation_diagnostics"]["resolution_label"] == (
        "latent_confounding"
    )


def test_graph_hypothesis_keeps_cardinality_bundle_fail_closed_when_prerequisites_missing() -> None:
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(
            graph_type=GraphType.DAG,
            edges=[CausalEdge(src="W_anchor", dst="Y", combined_confidence=0.9)],
            nodes=["W_anchor", "X", "Y"],
            discovery_method="pc",
        ),
        metadata={
            LATENT_CARDINALITY_EVIDENCE_KEY: LatentCardinalityEvidencePayload(
                model_class="ME-LiNGLaH-S",
                treatment_variable="X",
                outcome_variable="Y",
                inducing_environments=["region_a", "region_b"],
                latent_blocks=[
                    LatentBlockProposal(
                        latent_id="U_weak",
                        block_size=1,
                        role=LatentCausalRole.CONFOUNDER,
                        status=LatentBlockStatus.PARTIAL,
                        graph_status=LatentGraphStatus.PARTIAL,
                        anchor_variables=["W_anchor"],
                        informative_environment_contrasts=["region_a_vs_region_b"],
                        evidence=LatentBlockEvidence(
                            gin_supported=True,
                            atomic_structure_supported=True,
                            shift_localized=False,
                            minimal_decomposition_supported=True,
                            role_rule_supported=False,
                            pure_child_count=1,
                            neighbor_count=2,
                            rank=1,
                        ),
                    )
                ],
            ).model_dump(mode="json")
        },
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="pc_latent_fail_closed")

    assert hypothesis.latent_discovery is not None
    assert hypothesis.latent_discovery.trust_level is LatentTrustLevel.RESEARCH
    assert hypothesis.latent_discovery.readiness_cap == "proof_only"
    assert hypothesis.latent_discovery.promotion_allowed is False
    assert hypothesis.latent_discovery.metadata[LATENT_CARDINALITY_FAILURE_REASONS_KEY] == [
        "U_weak:neighbors",
        "U_weak:pure_children",
        "U_weak:role_rule_supported",
        "U_weak:shift_localized",
    ]
    assert "latent_discovery_proof_only" in hypothesis.latent_discovery.no_promotion_reasons
