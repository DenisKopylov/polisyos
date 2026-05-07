from polisyos.core.artifacts.ids import ArtifactID
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
)
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    LatentAssumptionCard,
    LatentDiscoveryBundle,
    LatentTrustLevel,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.scientist.methods.discovery.aggregator import EvidenceWeightedAggregator
from polisyos.scientist.methods.discovery.output import (
    DiscoveryArtifactBuilder,
    DiscoveryArtifactBuildInput,
)
from polisyos.scientist.methods.discovery.portfolio import PortfolioCandidate, PortfolioRunResult
from polisyos.scientist.methods.discovery.priors import GraphPriorBuilder, PriorKnowledgeBundle
from polisyos.scientist.methods.discovery.schema import graph_hypothesis_from_report
from polisyos.scientist.methods.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityConfig,
    BootstrapStabilityReport,
    HypothesisStabilitySummary,
)
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityJudge,
    UtilityJudgeInput,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    load_effective_latent_discovery_bundle_for_state,
    resolve_effective_latent_discovery_bundle_for_state,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF,
)


def _query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.9)],
        discovery_method="pc",
    )


def test_runtime_loads_latent_bundle_from_discovery_artifact_and_merges_proxy_boundary(
    execution_context,
    minimal_state,
) -> None:
    discovery_report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(),
        algebraic_constraints=AlgebraicConstraintReport(severity="warning"),
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
    hypothesis = graph_hypothesis_from_report(discovery_report, hypothesis_id="pc_main")
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=3),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_main",
                edge_selection_frequency={"X->Y": 0.9},
                mean_edge_stability=0.9,
                adjustment_set_stability=0.8,
                completed_resamples=3,
            )
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate([hypothesis], stability, utility)
    bundle_ref = DiscoveryArtifactBuilder().build(
        execution_context.store,
        DiscoveryArtifactBuildInput(
            run_id="R_phase_e_runtime",
            task_id="task_phase_e_runtime",
            variable_names=["X", "Y", "Z"],
            causal_query=_query(),
            hypotheses=[hypothesis],
            portfolio_result=PortfolioRunResult(
                candidates=[
                    PortfolioCandidate(
                        hypothesis=hypothesis,
                        source_report=discovery_report,
                        method_params={"significance_level": 0.05},
                    )
                ]
            ),
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=GraphPriorBuilder().build(matrix, utility),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
    )
    state = minimal_state.model_copy(
        update={
            "artifacts_index": {
                **minimal_state.artifacts_index,
                ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF: bundle_ref,
            }
        }
    )
    causal_report = CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE(X,Y)",
        point_estimate=0.4,
        confidence_interval=(0.1, 0.7),
        inference_method="bootstrap",
        sample_size=120,
        n_treated=60,
        n_control=60,
        pre_periods=0,
        post_periods=1,
        metadata={
            "proxy_boundary": {
                "boundary_notes": [
                    "Observed proxy path may still explain the effect without latent promotion."
                ],
                "no_promotion_reasons": ["proxy_explanation_not_ruled_out"],
            }
        },
    )

    latent_bundle = load_effective_latent_discovery_bundle_for_state(
        execution_context,
        state,
        causal_report=causal_report,
    )

    assert latent_bundle is not None
    assert latent_bundle.readiness_cap == "proof_only"
    assert latent_bundle.promotion_allowed is False
    assert latent_bundle.human_gate_required is True
    assert latent_bundle.metadata["source_hypothesis_ids"] == ["pc_main"]
    assert latent_bundle.metadata["proxy_boundary"]["boundary_notes"] == [
        "Observed proxy path may still explain the effect without latent promotion."
    ]
    assert "proxy_explanation_not_ruled_out" in latent_bundle.no_promotion_reasons


def test_runtime_marks_unreadable_discovery_bundle_ref_as_latent_resolution_error(
    execution_context,
    minimal_state,
) -> None:
    discovery_report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(),
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
    )
    hypothesis = graph_hypothesis_from_report(discovery_report, hypothesis_id="pc_main")
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=3),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_main",
                edge_selection_frequency={"X->Y": 0.9},
                mean_edge_stability=0.9,
                adjustment_set_stability=0.8,
                completed_resamples=3,
            )
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate([hypothesis], stability, utility)
    bundle_ref = DiscoveryArtifactBuilder().build(
        execution_context.store,
        DiscoveryArtifactBuildInput(
            run_id="R_phase_e_runtime_error",
            task_id="task_phase_e_runtime_error",
            variable_names=["X", "Y", "Z"],
            causal_query=_query(),
            hypotheses=[hypothesis],
            portfolio_result=PortfolioRunResult(
                candidates=[
                    PortfolioCandidate(
                        hypothesis=hypothesis,
                        source_report=discovery_report,
                        method_params={"significance_level": 0.05},
                    )
                ]
            ),
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=GraphPriorBuilder().build(matrix, utility),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
    )
    broken_ref = bundle_ref.model_copy(update={"artifact_id": ArtifactID.from_sha256_hex("f" * 64)})
    state = minimal_state.model_copy(
        update={
            "artifacts_index": {
                **minimal_state.artifacts_index,
                ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF: broken_ref,
            }
        }
    )

    resolution = resolve_effective_latent_discovery_bundle_for_state(
        execution_context,
        state,
    )

    assert resolution.status == "unreadable"
    assert resolution.bundle is None
    assert resolution.source_bundle_ref == broken_ref
    assert resolution.error_payload() is not None
    assert resolution.error_payload()["error_code"]
