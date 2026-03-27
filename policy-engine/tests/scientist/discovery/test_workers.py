from __future__ import annotations

from polisyos.ir.analytics.causal_discovery import DataCharacteristics, DataType, DimensionRegime
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.scientist.discovery.aggregator import EdgeConfidenceEntry, EdgeConfidenceMatrix
from polisyos.scientist.discovery.priors import (
    DisputedEdge,
    GraphPriorBundle,
    PriorEdge,
    PriorKnowledgeBundle,
)
from polisyos.scientist.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
)
from polisyos.scientist.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityConfig,
    BootstrapStabilityReport,
    HypothesisStabilitySummary,
)
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)
from polisyos.scientist.discovery.workers import (
    DataProfilerWorker,
    DataProfilerWorkerInput,
    DiscoveryWorkerBudget,
    DiscoveryWorkerContext,
    SkepticWorker,
    SkepticWorkerInput,
    run_bounded_discovery_workers,
)


def _hypothesis() -> GraphHypothesis:
    return GraphHypothesis(
        hypothesis_id="h1",
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        method=DiscoveryMethod.PC,
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "Z"],
            edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.7)],
            discovery_method="pc",
        ),
        edge_confidence={"X->Y": 0.7},
        compute_footprint=ComputeFootprint(method_params={"alpha": 0.1}),
    )


def _stability() -> BootstrapStabilityReport:
    return BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=5),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="h1",
                edge_selection_frequency={"X->Y": 0.65},
                mean_edge_stability=0.65,
                adjustment_set_stability=0.55,
                completed_resamples=5,
            )
        ],
    )


def _utility(identification_status: str = "partially_identified") -> DownstreamUtilityReport:
    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="h1",
                identification_status=identification_status,
                identifiability_score=0.5,
                stability_score=0.65,
                composite_score=0.6,
                rank=1,
            )
        ],
        recommended_shortlist=["h1"],
    )


def _priors() -> GraphPriorBundle:
    return GraphPriorBundle(
        disputed_edges=[
            DisputedEdge(
                dispute_id="d1",
                skeleton_key="X--Y",
                candidate_edges=[
                    PriorEdge(
                        edge_key="X->Y",
                        src="X",
                        dst="Y",
                        presence_confidence=0.7,
                        orientation_confidence=0.4,
                        supporting_hypothesis_ids=["h1"],
                    )
                ],
                dispute_reasons=["orientation_conflict"],
            )
        ]
    )


def _matrix() -> EdgeConfidenceMatrix:
    return EdgeConfidenceMatrix(
        entries=[
            EdgeConfidenceEntry(
                skeleton_key="X--Y",
                edge_key="X->Y",
                src="X",
                dst="Y",
                presence_confidence=0.7,
                orientation_confidence=0.4,
                directional_support={"X->Y": 0.5, "Y->X": 0.45},
                orientation_support={"X|tail>arrow|Y": 0.5, "Y|tail>arrow|X": 0.45},
                supporting_hypothesis_ids=["h1"],
                disputed=True,
                dispute_reasons=["orientation_conflict"],
            )
        ]
    )


def test_data_profiler_builds_diagnostics_from_quality_inputs() -> None:
    report, provenance = DataProfilerWorker().profile(
        DataProfilerWorkerInput(
            data_characteristics=DataCharacteristics(
                data_type=DataType.CROSS_SECTIONAL,
                n_samples=20,
                n_variables=5,
                dimension_regime=DimensionRegime.LOW_DIM,
                estimated_density=0.4,
                has_mixed_types=True,
                suspected_latent_confounders=True,
            ),
            data_quality_report={"grade": "bronze", "score": 0.42},
            evidence_bundle={"sources": [{"coverage": "proxy_only"}]},
            bootstrap_stability_report=_stability(),
            downstream_utility_report=_utility(),
            graph_prior_bundle=_priors(),
            prior_knowledge_bundle=PriorKnowledgeBundle(unresolved_edges=["X->Y"]),
        )
    )

    assert report.status == "ready"
    codes = {item.code for item in report.diagnostics}
    assert "sample_adequacy_low" in codes
    assert "data_quality_low" in codes
    assert "proxy_signal_present" in codes
    assert provenance.worker_name == "data_profiler"


def test_skeptic_worker_falls_back_on_invalid_provider_output(monkeypatch) -> None:
    class _BadClient:
        async def generate(self, **kwargs):
            del kwargs
            return "not json"

    monkeypatch.setattr(
        "polisyos.scientist.discovery.workers.create_traced_gateway_client",
        lambda **kwargs: _BadClient(),
    )

    findings, provenance = SkepticWorker().critique(
        SkepticWorkerInput(
            hypotheses=[_hypothesis()],
            edge_confidence_matrix=_matrix(),
            bootstrap_stability_report=_stability(),
            downstream_utility_report=_utility(),
            graph_prior_bundle=_priors(),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
        budget=DiscoveryWorkerBudget(max_findings=3),
        context=DiscoveryWorkerContext(run_id="skeptic_test", task_id="task"),
    )

    assert findings
    assert provenance.fallback_used is True
    assert provenance.worker_name == "skeptic"


def test_worker_bundle_degrades_on_partial_inputs() -> None:
    bundle = run_bounded_discovery_workers(
        data_profiler_input=DataProfilerWorkerInput(
            data_characteristics=None,
            bootstrap_stability_report=_stability(),
            downstream_utility_report=_utility(),
            graph_prior_bundle=_priors(),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
        skeptic_input=SkepticWorkerInput(
            hypotheses=[_hypothesis()],
            edge_confidence_matrix=_matrix(),
            bootstrap_stability_report=_stability(),
            downstream_utility_report=_utility(),
            graph_prior_bundle=_priors(),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
        budget=DiscoveryWorkerBudget(max_gateway_calls=0),
        context=DiscoveryWorkerContext(run_id="degraded", task_id="task"),
    )

    assert bundle.status == "degraded"
    assert bundle.data_profile.notes == ["data_characteristics_missing"]
    assert bundle.skeptic_findings
    assert bundle.active_planner_context()["targeted_edge_keys"]
