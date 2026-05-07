import pytest
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
)
from polisyos.scientist.methods.discovery import utility_judge as utility_module
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
    DownstreamUtilityJudge,
    UtilityJudgeInput,
)


def _query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _dag_graph(*, metadata: dict | None = None) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        discovery_method="dagma",
        metadata=metadata or {},
    )


def _pag_ambiguous_graph(*, metadata: dict | None = None) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
        discovery_method="fci",
        metadata=metadata or {},
    )


def _hypothesis(
    *,
    hypothesis_id: str,
    graph: CausalGraphModel,
    method: DiscoveryMethod,
    algorithm_family: DiscoveryAlgorithmFamily,
) -> GraphHypothesis:
    return GraphHypothesis(
        hypothesis_id=hypothesis_id,
        algorithm_family=algorithm_family,
        method=method,
        graph=graph,
        edge_confidence={},
        compute_footprint=ComputeFootprint(),
        metadata=graph.metadata,
    )


def _stability_report(*summaries: HypothesisStabilitySummary) -> BootstrapStabilityReport:
    return BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=5),
        summaries=list(summaries),
    )


def _success_effect_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE(X,Y)",
        point_estimate=0.0,
        confidence_interval=(-4.0, 5.0),
        inference_method="bootstrap",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=1,
    )


def test_identified_graph_outranks_pag_ambiguous_candidate_with_real_identification() -> None:
    identified = _hypothesis(
        hypothesis_id="identified",
        graph=_dag_graph(metadata={"structural_fit": 0.20}),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    ambiguous = _hypothesis(
        hypothesis_id="ambiguous",
        graph=_pag_ambiguous_graph(metadata={"structural_fit": 0.99}),
        method=DiscoveryMethod.FCI,
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="identified",
            mean_edge_stability=0.0,
            completed_resamples=5,
        ),
        HypothesisStabilitySummary(
            hypothesis_id="ambiguous",
            mean_edge_stability=1.0,
            completed_resamples=5,
        ),
    )

    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[ambiguous, identified],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    assert [score.hypothesis_id for score in report.scores] == ["identified", "ambiguous"]
    assert report.scores[0].identification_status == "identified"
    assert report.scores[1].identification_status == "pag_ambiguous"
    assert report.scores[1].composite_score <= report.scores[0].composite_score


def test_transport_context_changes_ranking_only_when_present(monkeypatch) -> None:
    worse_first = _hypothesis(
        hypothesis_id="worse_first",
        graph=_dag_graph(metadata={"transport_rank": "bad"}),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    better_second = _hypothesis(
        hypothesis_id="better_second",
        graph=_dag_graph(metadata={"transport_rank": "good"}),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="worse_first",
            mean_edge_stability=0.5,
            completed_resamples=5,
        ),
        HypothesisStabilitySummary(
            hypothesis_id="better_second",
            mean_edge_stability=0.5,
            completed_resamples=5,
        ),
    )
    judge = DownstreamUtilityJudge()

    baseline = judge.evaluate(
        UtilityJudgeInput(
            hypotheses=[worse_first, better_second],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    def fake_transport(selection_diagram, query_treatment, query_outcome):
        status = (
            TransportabilityStatus.IDENTIFIED
            if selection_diagram.base_graph.metadata.get("transport_rank") == "good"
            else TransportabilityStatus.UNSUPPORTED
        )
        return TransportabilityResult(
            status=status,
            transport_mode=TransportMode.DIRECT
            if status is TransportabilityStatus.IDENTIFIED
            else TransportMode.NONE,
            unsupported_reason="test_transport_not_identified"
            if status is TransportabilityStatus.UNSUPPORTED
            else None,
        )

    monkeypatch.setattr(utility_module, "solve_transportability", fake_transport)
    with_transport = judge.evaluate(
        UtilityJudgeInput(
            hypotheses=[worse_first, better_second],
            stability_report=stability_report,
            causal_query=_query(),
            selection_diagram=SelectionDiagram(
                base_graph=worse_first.graph,
                source_context=ContextProfile(context_id="DE"),
                target_context=ContextProfile(context_id="UA"),
            ),
        )
    )

    assert [score.hypothesis_id for score in baseline.scores] == ["worse_first", "better_second"]
    assert all(score.transportability_score is None for score in baseline.scores)
    assert baseline.metadata["channel_coverage"]["transportability"] is False
    assert [score.hypothesis_id for score in with_transport.scores] == [
        "better_second",
        "worse_first",
    ]
    assert with_transport.scores[0].transportability_score == 1.0
    assert with_transport.scores[1].transportability_score == 0.0
    assert with_transport.metadata["channel_coverage"]["transportability"] is True


def test_estimation_quality_only_contributes_when_benchmark_reports_are_present() -> None:
    hypothesis = _hypothesis(
        hypothesis_id="candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="candidate",
            mean_edge_stability=0.5,
            completed_resamples=5,
        )
    )
    judge = DownstreamUtilityJudge()

    without_benchmark = judge.evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )
    with_benchmark = judge.evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability_report,
            causal_query=_query(),
            benchmark_reports={"candidate": _success_effect_report()},
        )
    )

    assert without_benchmark.scores[0].estimation_quality_score is None
    assert with_benchmark.scores[0].estimation_quality_score is not None
    assert with_benchmark.scores[0].composite_score != without_benchmark.scores[0].composite_score
    assert without_benchmark.metadata["channel_coverage"]["benchmark"] is False
    assert with_benchmark.metadata["channel_coverage"]["benchmark"] is True


def test_s_nodes_activate_transport_channel_without_selection_diagram(monkeypatch) -> None:
    hypothesis = _hypothesis(
        hypothesis_id="candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="candidate",
            mean_edge_stability=0.5,
            completed_resamples=5,
        )
    )

    def fake_identify(*args, **kwargs):
        return utility_module.IdentificationResult(
            status=utility_module.IdentificationStatus.IDENTIFIED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=[],
            required_distributions=[],
            query_str="P(Y|do(X))",
        )

    monkeypatch.setattr(utility_module.CausalEngine, "identify", fake_identify)
    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability_report,
            causal_query=_query(),
            s_nodes=[
                SNode(
                    target_variable="X",
                    context_dimension="domain",
                    source_value=0.0,
                    target_value=1.0,
                    delta=1.0,
                    severity="medium",
                    origin=SNodeOrigin.CONTEXT_DELTA,
                )
            ],
        )
    )

    assert report.metadata["channel_coverage"]["transportability"] is True


def test_missing_optional_inputs_are_renormalized_in_composite_score() -> None:
    hypothesis = _hypothesis(
        hypothesis_id="candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="candidate",
            mean_edge_stability=0.5,
            completed_resamples=5,
        )
    )

    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    assert report.scores[0].transportability_score is None
    assert report.scores[0].estimation_quality_score is None
    assert report.scores[0].discovery_consistency_score == pytest.approx(1.0, rel=1e-6)
    assert report.scores[0].composite_score == pytest.approx(0.8333333333, rel=1e-6)


def test_algebraic_blocker_is_excluded_from_shortlist_when_clean_candidate_exists() -> None:
    blocker = _hypothesis(
        hypothesis_id="blocker_candidate",
        graph=_dag_graph(
            metadata={
                "discovery_report_metadata": {
                    "algebraic_constraint_severity": "blocker",
                }
            }
        ),
        method=DiscoveryMethod.PC,
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
    )
    clean = _hypothesis(
        hypothesis_id="clean_candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="blocker_candidate",
            mean_edge_stability=0.6,
            completed_resamples=5,
        ),
        HypothesisStabilitySummary(
            hypothesis_id="clean_candidate",
            mean_edge_stability=0.6,
            completed_resamples=5,
        ),
    )

    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[blocker, clean],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    assert report.recommended_shortlist == ["clean_candidate"]
    assert report.metadata["shortlist_exclusions"] == [
        "blocked:blocker_candidate:algebraic_blocker"
    ]
    by_id = {score.hypothesis_id: score for score in report.scores}
    assert by_id["blocker_candidate"].algebraic_severity == "blocker"
    assert by_id["blocker_candidate"].discovery_consistency_score == pytest.approx(0.3)


def test_algebraic_warning_penalizes_but_does_not_zero_discovery_consistency() -> None:
    warned = _hypothesis(
        hypothesis_id="warned_candidate",
        graph=_dag_graph(
            metadata={
                "discovery_report_metadata": {
                    "algebraic_constraint_severity": "warning",
                }
            }
        ),
        method=DiscoveryMethod.PC,
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="warned_candidate",
            mean_edge_stability=0.5,
            completed_resamples=5,
        )
    )

    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[warned],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    assert report.scores[0].algebraic_severity == "warning"
    assert report.scores[0].discovery_consistency_score == pytest.approx(0.65, rel=1e-6)
    assert report.scores[0].composite_score > 0.0


def test_disputed_edges_reduce_discovery_consistency_score() -> None:
    forward = _hypothesis(
        hypothesis_id="forward",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    reverse_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Y", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        discovery_method="pc",
    )
    reverse = _hypothesis(
        hypothesis_id="reverse",
        graph=reverse_graph,
        method=DiscoveryMethod.PC,
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="forward",
            mean_edge_stability=0.5,
            completed_resamples=5,
        ),
        HypothesisStabilitySummary(
            hypothesis_id="reverse",
            mean_edge_stability=0.5,
            completed_resamples=5,
        ),
    )

    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[forward, reverse],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    by_id = {score.hypothesis_id: score for score in report.scores}
    assert by_id["forward"].disputed_edge_count == 1
    assert by_id["reverse"].disputed_edge_count == 1
    assert by_id["forward"].disputed_edge_fraction == pytest.approx(1 / 3, rel=1e-6)
    assert by_id["forward"].discovery_consistency_score == pytest.approx(0.9, rel=1e-6)
    assert report.metadata["dispute_summary"]["n_hypotheses_with_disputes"] == 2


def test_missing_algebraic_metadata_defaults_to_clean_discovery_consistency() -> None:
    hypothesis = _hypothesis(
        hypothesis_id="candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.PAIRWISE_HEURISTIC,
        algorithm_family=DiscoveryAlgorithmFamily.FUNCTIONAL,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="candidate",
            mean_edge_stability=0.5,
            completed_resamples=5,
        )
    )

    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    assert report.scores[0].algebraic_severity is None
    assert report.scores[0].discovery_consistency_score == pytest.approx(1.0, rel=1e-6)


def test_runtime_auditable_hypothesis_missing_algebraic_stamp_degrades_to_warning() -> None:
    hypothesis = _hypothesis(
        hypothesis_id="candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    hypothesis = hypothesis.model_copy(
        update={"metadata": {"portfolio_method": "dagma", "report_method": "dagma"}}
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="candidate",
            mean_edge_stability=0.5,
            completed_resamples=5,
        )
    )

    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability_report,
            causal_query=_query(),
        )
    )

    assert report.scores[0].algebraic_severity == "warning"
    assert report.scores[0].discovery_consistency_score == pytest.approx(0.65, rel=1e-6)
