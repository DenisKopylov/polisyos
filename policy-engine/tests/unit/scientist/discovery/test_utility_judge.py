import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.catalog.causal import constraint_discovery as constraint_module
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.causal_engine.identification import (
    CausalEngineIdentificationMixin,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
)
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicAssumptionStatus,
    AlgebraicConstraintFamily,
    AlgebraicFalsificationScope,
    CausalDiscoveryReport,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphProjectionStatus,
    GraphType,
    graph_projection_disposition,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
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
    graph_hypothesis_from_report,
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
    load_downstream_utility_report,
    persist_downstream_utility_report,
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
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
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


def test_identified_graph_outranks_unresolved_pag_with_fresh_limited_report(tmp_path) -> None:
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

    low_level = CausalEngine().identify(
        treatment="X",
        outcome="Y",
        graph=_pag_ambiguous_graph(metadata={"structural_fit": 0.99}),
    )
    assert isinstance(low_level, IdentificationResult)
    assert low_level.status is IdentificationStatus.ORACLE_NEEDED
    assert low_level.metadata["limitation_code"] == (
        "partial_graph_completion_semantics_not_established"
    )

    assert [score.hypothesis_id for score in report.scores] == ["identified", "ambiguous"]
    assert report.scores[0].identification_status == "identified"
    assert report.scores[1].identification_status == "unsupported_graph_profile"
    assert "identifiability:unsupported:graph_projection_unavailable" in report.scores[1].reasons
    assert report.scores[1].composite_score <= report.scores[0].composite_score

    writer = FileSystemCAS(tmp_path / "utility-report")
    ref = persist_downstream_utility_report(writer, report)
    manifest = writer.get_manifest(ref)
    payload = from_canonical_bytes(writer.get_bytes(ref))
    assert manifest.artifact_schema.name == utility_module.DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME
    assert (
        manifest.artifact_schema.version == utility_module.DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION
    )
    assert payload["schema_version"] == utility_module.DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION
    fresh_report = load_downstream_utility_report(
        FileSystemCAS(tmp_path / "utility-report"),
        ref,
    )
    fresh_score = next(score for score in fresh_report.scores if score.hypothesis_id == "ambiguous")
    assert fresh_score.identification_status == "unsupported_graph_profile"
    assert "identifiability:unsupported:graph_projection_unavailable" in fresh_score.reasons


def test_untyped_identification_error_keeps_generic_negative_certificate(monkeypatch) -> None:
    def fail_dispatch(*args, **kwargs):
        raise ValueError("untyped_backend_error")

    monkeypatch.setattr(
        CausalEngineIdentificationMixin,
        "_dispatch_static_identification",
        fail_dispatch,
    )
    result = CausalEngine().identify(
        treatment="X",
        outcome="Y",
        graph=_dag_graph(),
    )

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.MISSING_DISTRIBUTION


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


def test_s_node_negative_certificate_is_preserved_as_blocked_transportability(monkeypatch) -> None:
    hypothesis = _hypothesis(
        hypothesis_id="blocked-candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    stability_report = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="blocked-candidate",
            mean_edge_stability=0.5,
            completed_resamples=5,
        )
    )

    def identify_blocked_query(*args, **kwargs):
        return NegativeCertificate(
            blocking_type=BlockingType.S_NODE_UNRESOLVED,
            blocking_description="selection shift remains unresolved",
        )

    monkeypatch.setattr(utility_module.CausalEngine, "identify", identify_blocked_query)
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

    score = report.scores[0]
    assert score.transportability_score == 0.0
    assert score.transport_status == BlockingType.S_NODE_UNRESOLVED.value
    assert "transportability:blocked:s_node_unresolved" in score.reasons


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


def test_graph_derived_assumptions_remain_typed_through_candidate_shortlist(
    tmp_path,
) -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[],
        discovery_method="pc",
    )
    discovery_report = CausalDiscoveryReport(
        method="pc",
        graph=graph,
        projection_disposition=graph_projection_disposition(
            graph,
            None,
            status=GraphProjectionStatus.IDENTITY,
        ),
    )
    rng = np.random.default_rng(23)
    x = rng.normal(size=200)
    data = np.column_stack([x, 0.85 * x + rng.normal(scale=0.25, size=200)])
    audited_report = constraint_module._stamp_algebraic_constraint_audit(
        discovery_report,
        data=data,
        variable_names=["X", "Y"],
        significance_level=0.05,
        seed=0,
    )
    assert audited_report.algebraic_constraints is not None
    # Keep the actual CI violation while deleting family/warning labels that
    # must not be the condition which carries its candidate-only scope.
    unmarked_constraints = audited_report.algebraic_constraints.model_copy(
        update={
            "families_run": [],
            "tested_by_family": {},
            "violated_by_family": {},
            "warnings": [],
        }
    )
    audited_report = audited_report.model_copy(
        update={"algebraic_constraints": unmarked_constraints}
    )
    violation = next(
        item
        for item in audited_report.algebraic_constraints.violated_constraints_preview
        if item.family is AlgebraicConstraintFamily.CI
    )
    assert violation.assumption_status is AlgebraicAssumptionStatus.UNKNOWN
    assert violation.scope_of_falsification is AlgebraicFalsificationScope.RANKING_ONLY
    assert audited_report.algebraic_constraints.families_run == []
    assert audited_report.algebraic_constraints.warnings == []

    candidate = graph_hypothesis_from_report(
        audited_report,
        hypothesis_id="candidate",
    )
    stability = _stability_report(
        HypothesisStabilitySummary(
            hypothesis_id="candidate",
            mean_edge_stability=0.6,
            completed_resamples=5,
        )
    )
    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[candidate],
            stability_report=stability,
            causal_query=_query(),
        )
    )

    score = report.scores[0]
    assert report.schema_version == "1.2"
    assert score.graph_derived_assumption_status is AlgebraicAssumptionStatus.UNKNOWN
    assert score.graph_derived_scope_of_falsification is AlgebraicFalsificationScope.RANKING_ONLY
    assert any("candidate-ranking-only" in warning for warning in score.warnings)

    writer = FileSystemCAS(tmp_path / "candidate-only-utility")
    ref = persist_downstream_utility_report(writer, report)
    reopened = load_downstream_utility_report(
        FileSystemCAS(tmp_path / "candidate-only-utility"),
        ref,
    )
    reopened_score = reopened.scores[0]
    assert reopened_score.graph_derived_assumption_status is AlgebraicAssumptionStatus.UNKNOWN
    assert (
        reopened_score.graph_derived_scope_of_falsification
        is AlgebraicFalsificationScope.RANKING_ONLY
    )


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


def test_transport_candidate_requiring_review_is_not_scored_as_fully_transportable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hypothesis = _hypothesis(
        hypothesis_id="review_candidate",
        graph=_dag_graph(),
        method=DiscoveryMethod.DAGMA,
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
    )
    diagram = SelectionDiagram(
        base_graph=hypothesis.graph,
        source_context=ContextProfile(context_id="DE"),
        target_context=ContextProfile(context_id="UA"),
    )
    candidate = TransportabilityResult(
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        identification_engine="y0",
        requires_expert_review=True,
        expert_review_reasons=["source_data_authority_not_established"],
    )
    monkeypatch.setattr(utility_module, "solve_transportability", lambda **_kwargs: candidate)

    score, status, reasons, warnings = utility_module._score_transportability(
        hypothesis,
        _query(),
        selection_diagram=diagram,
        s_nodes=[],
    )

    assert score < 1.0
    assert status == "identified"
    assert "transportability_requires_expert_review" in reasons
    assert warnings


def test_current_utility_writer_persists_nullable_scope_fields_for_fresh_reader(tmp_path) -> None:
    from polisyos.scientist.methods.discovery.utility_judge import (
        DownstreamUtilityReport,
        HypothesisUtilityScore,
    )

    report = DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="scope-not-established",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=0.75,
                composite_score=0.8,
            )
        ]
    )
    store = FileSystemCAS(tmp_path / "nullable-utility-report")
    ref = persist_downstream_utility_report(store, report)
    payload = from_canonical_bytes(store.get_bytes(ref))
    score = payload["scores"][0]

    assert "graph_derived_assumption_status" in score
    assert score["graph_derived_assumption_status"] is None
    assert "graph_derived_scope_of_falsification" in score
    assert score["graph_derived_scope_of_falsification"] is None
    reopened = load_downstream_utility_report(FileSystemCAS(store.root), ref)
    assert reopened.scores[0].graph_derived_assumption_status is None
    assert reopened.scores[0].graph_derived_scope_of_falsification is None


def _put_raw_downstream_utility_report(store, payload, *, manifest_version, schema_name=None):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.scientist import DownstreamUtilityReportRef
    from polisyos.scientist.methods.discovery.artifact_refs import profile_bound_written_ref

    ref = store.put_json(
        payload,
        PutOptions(
            kind="scientist.downstream_utility_report",
            media_type="application/json",
            schema=(
                SchemaInfo(
                    name=schema_name or utility_module.DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME,
                    version=manifest_version,
                )
                if manifest_version is not None
                else None
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    typed_ref = DownstreamUtilityReportRef.model_validate(ref.model_dump(mode="json"))
    return profile_bound_written_ref(store, typed_ref)


def test_exact_historical_11_scorecard_loads_as_unknown_ranking_only(tmp_path) -> None:
    from polisyos.scientist.methods.discovery.utility_judge import (
        DownstreamUtilityReport,
        HypothesisUtilityScore,
    )
    from polisyos.scientist.methods.search.artifact_minimality import ArtifactFunction

    current = DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="historical",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=0.75,
                composite_score=0.8,
                rank=1,
            )
        ]
    )
    payload = current.model_dump(mode="json")
    payload["schema_version"] = "1.1"
    for score in payload["scores"]:
        score.pop("graph_derived_assumption_status")
        score.pop("graph_derived_scope_of_falsification")
    store = FileSystemCAS(tmp_path / "legacy-utility-report")
    ref = _put_raw_downstream_utility_report(store, payload, manifest_version="1.1")

    fresh = load_downstream_utility_report(FileSystemCAS(store.root), ref)

    assert fresh.schema_version == "1.1"
    assert fresh.artifact_functions == {ArtifactFunction.ROUTING}
    assert fresh.scores[0].graph_derived_assumption_status is AlgebraicAssumptionStatus.UNKNOWN
    assert (
        fresh.scores[0].graph_derived_scope_of_falsification
        is AlgebraicFalsificationScope.RANKING_ONLY
    )


@pytest.mark.parametrize(
    ("manifest_version", "payload_version", "include_scope_fields", "schema_name"),
    [
        ("1.1", "1.2", True, None),
        ("1.1", "1.1", True, None),
        ("1.2", "1.1", False, None),
        ("1.3", "1.3", True, None),
        ("1.2", "1.2", False, None),
        ("1.1", "1.1", False, "wrong.downstream.utility.schema"),
    ],
)
def test_downstream_utility_loader_rejects_unbound_or_incomplete_schema(
    tmp_path, manifest_version, payload_version, include_scope_fields, schema_name
) -> None:
    from polisyos.scientist.methods.discovery.utility_judge import (
        DownstreamUtilityReport,
        HypothesisUtilityScore,
    )

    report = DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="current",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=1.0,
                composite_score=1.0,
            )
        ]
    )
    payload = report.model_dump(mode="json")
    payload["schema_version"] = payload_version
    if not include_scope_fields:
        for score in payload["scores"]:
            score.pop("graph_derived_assumption_status", None)
            score.pop("graph_derived_scope_of_falsification", None)
    store = FileSystemCAS(tmp_path / f"utility-{manifest_version}-{payload_version}")
    ref = _put_raw_downstream_utility_report(
        store,
        payload,
        manifest_version=manifest_version,
        schema_name=schema_name,
    )

    with pytest.raises(ValueError, match="schema|version|fields"):
        load_downstream_utility_report(FileSystemCAS(store.root), ref)


def test_downstream_utility_writer_rejects_forged_historical_version_before_cas_write(
    tmp_path,
) -> None:
    from polisyos.scientist.methods.discovery.utility_judge import DownstreamUtilityReport

    report = DownstreamUtilityReport()
    forged = report.model_copy(update={"schema_version": "1.1"})
    store = FileSystemCAS(tmp_path / "writer-rejects-legacy")
    before = sorted(
        path.relative_to(store.root) for path in store.root.rglob("*") if path.is_file()
    )

    with pytest.raises(ValueError, match="schema version"):
        persist_downstream_utility_report(store, forged)

    after = sorted(path.relative_to(store.root) for path in store.root.rglob("*") if path.is_file())
    assert after == before
