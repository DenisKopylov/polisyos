import numpy as np
from polisyos.foundry.methods.catalog.causal.protocols import (
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.scientist.discovery import stability as stability_module
from polisyos.scientist.discovery.portfolio import PortfolioCandidate
from polisyos.scientist.discovery.schema import (
    ComputeFootprint,
    DiscoveryMethod,
    GraphHypothesis,
    infer_algorithm_family,
)
from polisyos.scientist.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityAnalyzer,
    BootstrapStabilityConfig,
)


def _tabular_state() -> TabularCausalDiscoveryData:
    return TabularCausalDiscoveryData(
        data=np.array(
            [
                [0.0, 1.0, 0.5],
                [1.0, 2.0, 1.5],
                [2.0, 3.0, 2.5],
                [3.0, 4.0, 3.5],
                [4.0, 5.0, 4.5],
            ]
        ),
        variable_names=["X", "Y", "Z"],
    )


def _time_series_state() -> TimeSeriesCausalData:
    return TimeSeriesCausalData(
        data=np.array(
            [
                [0.0, 0.2, 1.0],
                [0.3, 0.4, 1.2],
                [0.6, 0.7, 1.3],
                [0.8, 0.9, 1.5],
                [1.0, 1.1, 1.6],
                [1.2, 1.3, 1.8],
            ]
        ),
        variable_names=["X", "Y", "Z"],
    )


def _causal_query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _dag_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        discovery_method="fci_resolved",
    )


def _pag_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
        ],
        discovery_method="fci",
    )


def _candidate(
    *,
    graph: CausalGraphModel,
    resolved_graph: CausalGraphModel | None,
    method: DiscoveryMethod,
) -> PortfolioCandidate:
    report = CausalDiscoveryReport(
        method=method.value,
        graph=graph,
        resolved_graph=resolved_graph,
    )
    return PortfolioCandidate(
        hypothesis=GraphHypothesis(
            hypothesis_id=f"{method.value}_0",
            algorithm_family=infer_algorithm_family(method),
            method=method,
            graph=graph,
            resolved_graph=resolved_graph,
            edge_confidence={"Z->X": 0.5, "Z->Y": 0.5, "X->Y": 0.5},
            compute_footprint=ComputeFootprint(),
        ),
        source_report=report,
        method_params={"__seed__": 1, "n_bootstrap": 0},
    )


def test_bootstrap_mode_selection_matches_input_type() -> None:
    analyzer = BootstrapStabilityAnalyzer(config=BootstrapStabilityConfig(n_resamples=1))

    tabular_report = analyzer.analyze([], _tabular_state())
    time_series_report = analyzer.analyze([], _time_series_state())

    assert tabular_report.bootstrap_mode is BootstrapMode.ROW
    assert time_series_report.bootstrap_mode is BootstrapMode.MOVING_BLOCK


def test_adjustment_set_stability_appears_for_query_when_resolved_graph_is_available(
    monkeypatch,
) -> None:
    dag = _dag_graph()
    pag = _pag_graph()
    candidate = _candidate(graph=pag, resolved_graph=dag, method=DiscoveryMethod.FCI)

    def fake_run(state, method, params):
        return CausalDiscoveryReport(
            method="fci",
            graph=pag,
            resolved_graph=dag,
            computation_time_seconds=0.1,
        )

    monkeypatch.setattr(stability_module, "run_discovery_method", fake_run)

    analyzer = BootstrapStabilityAnalyzer(config=BootstrapStabilityConfig(n_resamples=3, seed=9))
    with_query = analyzer.analyze([candidate], _tabular_state(), causal_query=_causal_query())
    without_query = analyzer.analyze([candidate], _tabular_state(), causal_query=None)
    summary = with_query.summary_for(candidate.hypothesis.hypothesis_id)
    no_query_summary = without_query.summary_for(candidate.hypothesis.hypothesis_id)

    assert summary is not None
    assert summary.completed_resamples == 3
    assert summary.adjustment_set_stability == 1.0
    assert summary.identifiable_rate == 1.0
    assert 0.0 <= summary.mean_edge_stability <= 1.0
    assert all(0.0 <= value <= 1.0 for value in summary.edge_selection_frequency.values())
    assert "resolved_graph_used_for_bootstrap_analysis" in summary.warnings
    assert no_query_summary is not None
    assert no_query_summary.adjustment_set_stability is None
    assert no_query_summary.identifiable_rate is None


def test_truncated_bootstrap_keeps_completed_resamples_and_unavailable_metrics_explicit(
    monkeypatch,
) -> None:
    candidate = _candidate(graph=_dag_graph(), resolved_graph=None, method=DiscoveryMethod.DAGMA)

    def always_fail(state, method, params):
        raise RuntimeError("simulated bootstrap failure")

    monkeypatch.setattr(stability_module, "run_discovery_method", always_fail)

    analyzer = BootstrapStabilityAnalyzer(config=BootstrapStabilityConfig(n_resamples=4, seed=3))
    report = analyzer.analyze([candidate], _tabular_state(), causal_query=_causal_query())
    summary = report.summary_for(candidate.hypothesis.hypothesis_id)

    assert summary is not None
    assert summary.completed_resamples == 0
    assert summary.edge_selection_frequency == {}
    assert summary.orientation_frequency == {}
    assert summary.skeleton_frequency == {}
    assert summary.mean_edge_stability is None
    assert summary.identifiable_rate is None
    assert summary.adjustment_set_stability is None
    assert any("bootstrap_run_" in warning for warning in summary.warnings)
    assert any("bootstrap_truncated" in warning for warning in summary.warnings)
