from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.scientist.methods.discovery.aggregator import EvidenceWeightedAggregator
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


def _graph(edge_specs: list[tuple[str, str]]) -> CausalGraphModel:
    nodes = sorted({node for src, dst in edge_specs for node in (src, dst)})
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(
                src=src, dst=dst, combined_confidence=1.0, evidence_refs=[f"prov:{src}->{dst}"]
            )
            for src, dst in edge_specs
        ],
        discovery_method="unit",
    )


def _hypothesis(
    *,
    hypothesis_id: str,
    family: DiscoveryAlgorithmFamily,
    method: DiscoveryMethod,
    edges: list[tuple[str, str]],
    failure_reasons: list[str] | None = None,
) -> GraphHypothesis:
    graph = (
        _graph(edges)
        if edges
        else CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[],
            discovery_method="unit",
        )
    )
    return GraphHypothesis(
        hypothesis_id=hypothesis_id,
        algorithm_family=family,
        method=method,
        graph=graph,
        edge_confidence={f"{src}->{dst}": 1.0 for src, dst in edges},
        compute_footprint=ComputeFootprint(),
        failure_reasons=failure_reasons or [],
    )


def _stability(*summaries: HypothesisStabilitySummary) -> BootstrapStabilityReport:
    return BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=5),
        summaries=list(summaries),
    )


def _utility(*scores: HypothesisUtilityScore) -> DownstreamUtilityReport:
    return DownstreamUtilityReport(scores=list(scores))


def test_aggregator_balances_families_and_ignores_failed_empty_candidate() -> None:
    hypotheses = [
        _hypothesis(
            hypothesis_id="pc_main",
            family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            method=DiscoveryMethod.PC,
            edges=[("X", "Y")],
        ),
        _hypothesis(
            hypothesis_id="fci_minor",
            family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            method=DiscoveryMethod.FCI,
            edges=[("Y", "X")],
        ),
        _hypothesis(
            hypothesis_id="dagma_main",
            family=DiscoveryAlgorithmFamily.SCORE_BASED,
            method=DiscoveryMethod.DAGMA,
            edges=[("X", "Y")],
        ),
        _hypothesis(
            hypothesis_id="ges_failed",
            family=DiscoveryAlgorithmFamily.SCORE_BASED,
            method=DiscoveryMethod.GES,
            edges=[],
            failure_reasons=["algorithm_failed:TimeoutError"],
        ),
    ]
    stability = _stability(
        HypothesisStabilitySummary(hypothesis_id="pc_main", edge_selection_frequency={"X->Y": 1.0}),
        HypothesisStabilitySummary(
            hypothesis_id="fci_minor", edge_selection_frequency={"Y->X": 1.0}
        ),
        HypothesisStabilitySummary(
            hypothesis_id="dagma_main", edge_selection_frequency={"X->Y": 1.0}
        ),
    )
    utility = _utility(
        HypothesisUtilityScore(
            hypothesis_id="pc_main",
            identification_status="identified",
            identifiability_score=1.0,
            stability_score=1.0,
            composite_score=0.90,
        ),
        HypothesisUtilityScore(
            hypothesis_id="fci_minor",
            identification_status="identified",
            identifiability_score=1.0,
            stability_score=1.0,
            composite_score=0.10,
        ),
        HypothesisUtilityScore(
            hypothesis_id="dagma_main",
            identification_status="identified",
            identifiability_score=1.0,
            stability_score=1.0,
            composite_score=0.50,
        ),
        HypothesisUtilityScore(
            hypothesis_id="ges_failed",
            identification_status="unsupported",
            identifiability_score=0.0,
            stability_score=0.0,
            composite_score=0.99,
        ),
    )

    matrix = EvidenceWeightedAggregator().aggregate(hypotheses, stability, utility)

    entry = matrix.entry_for_key("X->Y")
    assert entry is not None
    assert matrix.hypothesis_weights["dagma_main"] == 0.5
    assert matrix.hypothesis_weights["pc_main"] > matrix.hypothesis_weights["fci_minor"]
    assert "ges_failed" not in matrix.hypothesis_weights
    assert entry.presence_confidence == 1.0
    assert entry.directional_support["X->Y"] > entry.directional_support["Y->X"]
    assert entry.disputed is False


def test_aggregator_preserves_disputed_edge_when_directions_compete() -> None:
    hypotheses = [
        _hypothesis(
            hypothesis_id="pc_a",
            family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            method=DiscoveryMethod.PC,
            edges=[("X", "Y")],
        ),
        _hypothesis(
            hypothesis_id="dagma_b",
            family=DiscoveryAlgorithmFamily.SCORE_BASED,
            method=DiscoveryMethod.DAGMA,
            edges=[("Y", "X")],
        ),
    ]
    stability = _stability(
        HypothesisStabilitySummary(hypothesis_id="pc_a", edge_selection_frequency={"X->Y": 1.0}),
        HypothesisStabilitySummary(hypothesis_id="dagma_b", edge_selection_frequency={"Y->X": 1.0}),
    )
    utility = _utility(
        HypothesisUtilityScore(
            hypothesis_id="pc_a",
            identification_status="identified",
            identifiability_score=1.0,
            stability_score=1.0,
            composite_score=0.80,
        ),
        HypothesisUtilityScore(
            hypothesis_id="dagma_b",
            identification_status="identified",
            identifiability_score=1.0,
            stability_score=1.0,
            composite_score=0.80,
        ),
    )

    matrix = EvidenceWeightedAggregator().aggregate(hypotheses, stability, utility)

    entry = matrix.entry_for_key("Y->X")
    assert entry is not None
    assert entry.disputed is True
    assert "competing_direction_support" in entry.dispute_reasons
    assert matrix.metadata["equivalence_class_summary"]["unresolved_disputes"]
