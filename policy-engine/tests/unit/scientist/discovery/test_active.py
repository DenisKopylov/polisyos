from __future__ import annotations

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.scientist.methods.discovery.active import (
    ActiveDisambiguationPlanner,
    ActiveDisambiguationPlannerInput,
)
from polisyos.scientist.methods.discovery.aggregator import EdgeConfidenceEntry, EdgeConfidenceMatrix
from polisyos.scientist.methods.discovery.priors import (
    DisputedEdge,
    GraphPriorBundle,
    PriorEdge,
    PriorKnowledgeBundle,
)
from polisyos.scientist.methods.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
)
from polisyos.scientist.methods.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityConfig,
    BootstrapStabilityReport,
    HypothesisStabilitySummary,
)
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)


def _query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _hypothesis() -> GraphHypothesis:
    return GraphHypothesis(
        hypothesis_id="h1",
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        method=DiscoveryMethod.PC,
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "Z"],
            edges=[
                CausalEdge(src="Z", dst="X", combined_confidence=0.8),
                CausalEdge(src="X", dst="Y", combined_confidence=0.8),
            ],
            discovery_method="pc",
        ),
        edge_confidence={"Z->X": 0.8, "X->Y": 0.8},
        compute_footprint=ComputeFootprint(),
    )


def _stability(hypothesis_id: str = "h1", mean: float = 0.6) -> BootstrapStabilityReport:
    return BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=5),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id=hypothesis_id,
                edge_selection_frequency={"X->Y": mean},
                mean_edge_stability=mean,
                adjustment_set_stability=mean,
                completed_resamples=5,
            )
        ],
    )


def _utility(
    *,
    hypothesis_id: str = "h1",
    identification_status: str = "identified",
    composite_score: float = 0.9,
) -> DownstreamUtilityReport:
    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id=hypothesis_id,
                identification_status=identification_status,
                identifiability_score=1.0 if identification_status == "identified" else 0.5,
                stability_score=0.7,
                composite_score=composite_score,
                rank=1,
            )
        ],
        recommended_shortlist=[hypothesis_id],
    )


def test_active_planner_builds_ready_plan_for_disputed_edge() -> None:
    planner = ActiveDisambiguationPlanner()
    plan = planner.plan(
        ActiveDisambiguationPlannerInput(
            edge_confidence_matrix=EdgeConfidenceMatrix(
                entries=[
                    EdgeConfidenceEntry(
                        skeleton_key="X--Y",
                        edge_key="X->Y",
                        src="X",
                        dst="Y",
                        presence_confidence=0.8,
                        orientation_confidence=0.4,
                        directional_support={"X->Y": 0.5, "Y->X": 0.45},
                        orientation_support={"X|tail>arrow|Y": 0.5, "Y|tail>arrow|X": 0.45},
                        supporting_hypothesis_ids=["h1"],
                        disputed=True,
                        dispute_reasons=["orientation_conflict"],
                    )
                ]
            ),
            bootstrap_stability_report=_stability(),
            downstream_utility_report=_utility(),
            hypotheses=[_hypothesis()],
            graph_prior_bundle=GraphPriorBundle(
                disputed_edges=[
                    DisputedEdge(
                        dispute_id="d1",
                        skeleton_key="X--Y",
                        candidate_edges=[
                            PriorEdge(
                                edge_key="X->Y",
                                src="X",
                                dst="Y",
                                presence_confidence=0.8,
                                orientation_confidence=0.4,
                                supporting_hypothesis_ids=["h1"],
                            )
                        ],
                        dispute_reasons=["orientation_conflict"],
                    )
                ]
            ),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
            causal_query=_query(),
        )
    )

    assert plan.status == "ready"
    assert plan.target_edge_keys == ["X->Y"]
    assert any(action.action_type == "run_intervention" for action in plan.actions)


def test_active_planner_returns_no_action_needed_when_ambiguity_is_absent() -> None:
    planner = ActiveDisambiguationPlanner()
    plan = planner.plan(
        ActiveDisambiguationPlannerInput(
            edge_confidence_matrix=EdgeConfidenceMatrix(
                entries=[
                    EdgeConfidenceEntry(
                        skeleton_key="X--Y",
                        edge_key="X->Y",
                        src="X",
                        dst="Y",
                        presence_confidence=0.95,
                        orientation_confidence=0.95,
                        directional_support={"X->Y": 0.95},
                        orientation_support={"X|tail>arrow|Y": 0.95},
                        supporting_hypothesis_ids=["h1"],
                    )
                ]
            ),
            bootstrap_stability_report=_stability(mean=0.9),
            downstream_utility_report=_utility(),
            hypotheses=[_hypothesis()],
            graph_prior_bundle=GraphPriorBundle(),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
            causal_query=_query(),
        )
    )

    assert plan.status == "no_action_needed"
    assert plan.actions == []


def test_active_planner_falls_back_to_literature_followup_for_academic_conflict() -> None:
    planner = ActiveDisambiguationPlanner()
    plan = planner.plan(
        ActiveDisambiguationPlannerInput(
            edge_confidence_matrix=EdgeConfidenceMatrix(),
            bootstrap_stability_report=_stability(),
            downstream_utility_report=_utility(),
            hypotheses=[],
            graph_prior_bundle=GraphPriorBundle(),
            prior_knowledge_bundle=PriorKnowledgeBundle(
                unresolved_edges=["X->Y"],
                warnings=["conflicting_academic_support"],
            ),
            causal_query=_query(),
        )
    )

    assert plan.status == "degraded"
    assert any(action.action_type == "literature_followup" for action in plan.actions)


def test_active_planner_clamps_non_finite_scores_to_safe_defaults() -> None:
    planner = ActiveDisambiguationPlanner()
    non_finite_score = HypothesisUtilityScore.model_construct(
        hypothesis_id="h1",
        identification_status="partial",
        identifiability_score=float("nan"),
        stability_score=0.7,
        transport_status=None,
        transportability_score=None,
        estimation_quality_score=None,
        discovery_consistency_score=None,
        algebraic_severity=None,
        disputed_edge_count=None,
        disputed_edge_fraction=None,
        composite_score=float("nan"),
        rank=1,
        reasons=[],
        warnings=[],
        blocking_certificates=[],
    )
    plan = planner.plan(
        ActiveDisambiguationPlannerInput(
            edge_confidence_matrix=EdgeConfidenceMatrix.model_construct(
                entries=[
                    EdgeConfidenceEntry.model_construct(
                        skeleton_key="X--Y",
                        edge_key="X->Y",
                        src="X",
                        dst="Y",
                        presence_confidence=0.8,
                        orientation_confidence=float("nan"),
                        directional_support={"X->Y": 0.5, "Y->X": 0.45},
                        orientation_support={"X|tail>arrow|Y": float("nan")},
                        supporting_hypothesis_ids=["h1"],
                        disputed=True,
                        dispute_reasons=["orientation_conflict"],
                    )
                ]
            ),
            bootstrap_stability_report=_stability(),
            downstream_utility_report=DownstreamUtilityReport.model_construct(
                scores=[non_finite_score],
                recommended_shortlist=["h1"],
                metadata={},
            ),
            hypotheses=[_hypothesis()],
            graph_prior_bundle=GraphPriorBundle(),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
            causal_query=_query(),
        )
    )

    assert plan.status == "no_action_needed"
    assert plan.targets == []
