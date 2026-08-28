import numpy as np
import pytest

from polisyos.foundry.calibration.dp_ci import (
    CITestThresholdPolicy,
    CITestThresholdPolicySet,
    ci_threshold_scope,
)
from polisyos.foundry.methods.catalog.causal import constraint_discovery as constraint_module
from polisyos.foundry.methods.catalog.causal.constraint_discovery import PCDiscovery
from polisyos.foundry.methods.catalog.causal.protocols import (
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from polisyos.ir.analytics.causal_discovery import (
    CausalDiscoveryReport,
    DataCharacteristics,
    DataType,
    DimensionRegime,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.scientist.methods.discovery import portfolio as portfolio_module
from polisyos.scientist.methods.discovery.portfolio import (
    GraphDiscoveryPortfolioRunner,
    PortfolioRunnerConfig,
)
from polisyos.scientist.methods.discovery.schema import (
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
)
from polisyos.scientist.methods.search.judge_thresholds import (
    JudgeThresholdEntry,
    JudgeThresholdRegistry,
)


def _tabular_state() -> TabularCausalDiscoveryData:
    return TabularCausalDiscoveryData(
        data=np.array(
            [
                [0.0, 1.0, 0.5],
                [1.0, 2.0, 1.5],
                [2.0, 3.0, 2.5],
                [3.0, 4.0, 3.5],
            ]
        ),
        variable_names=["X", "Y", "Z"],
    )


def _time_series_state() -> TimeSeriesCausalData:
    return TimeSeriesCausalData(
        data=np.array(
            [
                [0.0, 0.1],
                [1.0, 0.2],
                [2.0, 0.4],
                [3.0, 0.8],
                [4.0, 1.6],
            ]
        ),
        variable_names=["X", "Y"],
    )


def _characteristics(data_type: DataType) -> DataCharacteristics:
    return DataCharacteristics(
        data_type=data_type,
        n_samples=20,
        n_variables=3 if data_type is DataType.CROSS_SECTIONAL else 2,
        dimension_regime=DimensionRegime.LOW_DIM,
        estimated_density=0.25,
        has_mixed_types=False,
        suspected_latent_confounders=False,
        is_stationary=True if data_type is DataType.TIME_SERIES else None,
        max_lag=3 if data_type is DataType.TIME_SERIES else None,
    )


def _report_for_method(method: DiscoveryMethod) -> CausalDiscoveryReport:
    graph_type = {
        DiscoveryMethod.PC: GraphType.CPDAG,
        DiscoveryMethod.FCI: GraphType.PAG,
        DiscoveryMethod.GES: GraphType.CPDAG,
        DiscoveryMethod.DAGMA: GraphType.DAG,
        DiscoveryMethod.ANM: GraphType.DAG,
        DiscoveryMethod.PAIRWISE_HEURISTIC: GraphType.DAG,
        DiscoveryMethod.PCMCI_PLUS: GraphType.DAG,
    }[method]
    return CausalDiscoveryReport(
        method=method.value,
        graph=CausalGraphModel(
            graph_type=graph_type,
            nodes=["X", "Y", "Z"] if method is not DiscoveryMethod.PCMCI_PLUS else ["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.75)],
            discovery_method=method.value,
        ),
        computation_time_seconds=0.2,
        metadata={"scale_backend_used": "classic", "optimizer": method.value},
    )


def test_discovery_registry_policy_reaches_real_foundry_dispatch_and_report(
    monkeypatch,
    tmp_path,
) -> None:
    registry_root = tmp_path / "judge_thresholds"
    registry = JudgeThresholdRegistry(registry_root)
    registry.record(
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="alpha_base",
            threshold_value=0.137,
            direction="max",
            rationale="Distinct bridge-integration threshold.",
            benchmark_source="test_discovery_registry_policy_bridge",
            scope_family="categorical_ci",
            scope_query_type="g2",
            scope_estimator="stratified_counts",
            scope_readiness_target="diagnostic",
            scope_dp_mechanism="gaussian_counts",
            scope_dp_epsilon_bucket="0.5_to_1.0",
            scope_dp_delta_bucket="zero",
        )
    )
    x = np.tile(np.array([0.0, 1.0]), 200)
    state = TabularCausalDiscoveryData(
        data=np.column_stack([x, x]),
        variable_names=["X", "Y"],
    )

    def fake_discovery_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=np.zeros((2, 2), dtype=int),
            metadata={},
            error=None,
            timed_out=False,
        )

    observed_lower_params: list[dict[str, object]] = []
    real_pure_step = PCDiscovery.pure_step

    def observing_pure_step(state, params):
        observed_lower_params.append(dict(params))
        return real_pure_step(state, params)

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", fake_discovery_runner)
    monkeypatch.setattr(PCDiscovery, "pure_step", staticmethod(observing_pure_step))

    report = portfolio_module.run_discovery_method(
        state,
        DiscoveryMethod.PC,
        {
            "judge_threshold_registry_root": str(registry_root),
            "significance_level": 0.05,
            "dp_context": {
                "mechanism": "gaussian_counts",
                "epsilon": 0.7,
                "delta": 0.0,
            },
            "discovery_scale_backend": "classic",
            "n_bootstrap": 0,
            "timeout_seconds": 30,
        },
    )

    assert len(observed_lower_params) == 1
    assert "judge_threshold_registry_root" not in observed_lower_params[0]
    assert "ci_threshold_policies" in observed_lower_params[0]
    assert report.algebraic_constraints is not None
    violation = next(
        item
        for item in report.algebraic_constraints.violated_constraints_preview
        if item.metadata.get("route") == "g_test"
    )
    assert violation.metadata["critical_value"] == pytest.approx(0.137)
    assert violation.metadata["threshold_registry_scope"]["dp_epsilon_bucket"] == "0.5_to_1.0"


def test_discovery_rejects_mismatched_policy_scope_before_foundry_dispatch(
    monkeypatch,
) -> None:
    runtime_dp_context = {
        "mechanism": "gaussian_counts",
        "epsilon": 0.7,
        "delta": 0.0,
    }
    mismatched = CITestThresholdPolicySet(
        policies=(
            CITestThresholdPolicy(
                alpha_base=0.137,
                threshold_scope=ci_threshold_scope(
                    family="kernel_ci",
                    query_type="hsic",
                    estimator="permutation",
                    dp_context={
                        "mechanism": "gaussian_counts",
                        "epsilon": 0.2,
                        "delta": 0.0,
                    },
                    readiness_target="diagnostic",
                ),
            ),
        )
    )
    lower_called = False

    def observing_pure_step(state, params):
        nonlocal lower_called
        lower_called = True
        return {"report": _report_for_method(DiscoveryMethod.PC)}

    monkeypatch.setattr(PCDiscovery, "pure_step", staticmethod(observing_pure_step))

    with pytest.raises(ValueError, match="CI threshold policy scope mismatch"):
        portfolio_module.run_discovery_method(
            _tabular_state(),
            DiscoveryMethod.PC,
            {
                "dp_context": runtime_dp_context,
                "ci_threshold_policies": mismatched.model_dump(mode="python"),
            },
        )

    assert lower_called is False


def test_cross_sectional_portfolio_runs_constraint_score_and_functional_methods(
    monkeypatch,
) -> None:
    seen_params: dict[DiscoveryMethod, dict[str, object]] = {}

    def fake_run(state, method, params):
        normalized = DiscoveryMethod(method)
        seen_params[normalized] = dict(params)
        return _report_for_method(normalized)

    monkeypatch.setattr(portfolio_module, "run_discovery_method", fake_run)
    monkeypatch.setattr(
        portfolio_module,
        "_characterize_data",
        lambda state, config: _characteristics(DataType.CROSS_SECTIONAL),
    )

    runner = GraphDiscoveryPortfolioRunner(config=PortfolioRunnerConfig(random_seed=11))
    result = runner.run(_tabular_state())

    assert [candidate.hypothesis.method for candidate in result.candidates] == [
        DiscoveryMethod.PC,
        DiscoveryMethod.FCI,
        DiscoveryMethod.GES,
        DiscoveryMethod.DAGMA,
        DiscoveryMethod.ANM,
        DiscoveryMethod.PAIRWISE_HEURISTIC,
    ]
    assert result.skipped_families == {
        DiscoveryAlgorithmFamily.TIME_SERIES: "requires_time_series_causal_data"
    }
    assert seen_params[DiscoveryMethod.PC]["discovery_scale_backend"] == "classic"
    assert seen_params[DiscoveryMethod.PC]["n_bootstrap"] == 0
    assert (
        result.candidates[0].hypothesis.algorithm_family
        is DiscoveryAlgorithmFamily.CONSTRAINT_BASED
    )
    assert result.candidates[3].hypothesis.algorithm_family is DiscoveryAlgorithmFamily.SCORE_BASED
    assert result.candidates[-1].hypothesis.algorithm_family is DiscoveryAlgorithmFamily.FUNCTIONAL


def test_cross_sectional_portfolio_forwards_algebraic_blocks_to_auditable_methods(
    monkeypatch,
) -> None:
    seen_params: dict[DiscoveryMethod, dict[str, object]] = {}

    def fake_run(state, method, params):
        normalized = DiscoveryMethod(method)
        seen_params[normalized] = dict(params)
        return _report_for_method(normalized)

    monkeypatch.setattr(portfolio_module, "run_discovery_method", fake_run)
    monkeypatch.setattr(
        portfolio_module,
        "_characterize_data",
        lambda state, config: _characteristics(DataType.CROSS_SECTIONAL),
    )

    algebraic_blocks = [
        {
            "block_id": "factor_1",
            "family": "tetrad",
            "variables": ["X", "Y", "Z", "W"],
        }
    ]
    expected_blocks = [
        {
            "block_id": "factor_1",
            "family": "tetrad",
            "variables": ["X", "Y", "Z", "W"],
            "quadruples": [],
            "expected_rank": None,
            "max_residual_energy": None,
            "row_variables": [],
            "col_variables": [],
            "max_rank": None,
            "graph_scope": None,
            "left_choke_set": [],
            "right_choke_set": [],
            "assumption_regime": None,
            "test_mode": None,
            "cadmg_scope": None,
            "fixing_sequence": [],
            "kernel_statement": None,
            "identified_kernel_ref": None,
            "positivity_required": None,
            "model_family": None,
            "invariant_polynomials": [],
            "semi_algebraic_inequalities": [],
            "derivation_method": None,
            "certificate_ref": None,
            "precomputed_violation_score": None,
        }
    ]
    runner = GraphDiscoveryPortfolioRunner(
        config=PortfolioRunnerConfig(random_seed=11, algebraic_blocks=algebraic_blocks)
    )
    runner.run(_tabular_state())

    for method in (
        DiscoveryMethod.PC,
        DiscoveryMethod.FCI,
        DiscoveryMethod.GES,
        DiscoveryMethod.DAGMA,
    ):
        assert seen_params[method]["algebraic_blocks"] == expected_blocks
    assert "algebraic_blocks" not in seen_params[DiscoveryMethod.ANM]
    assert "algebraic_blocks" not in seen_params[DiscoveryMethod.PAIRWISE_HEURISTIC]


def test_time_series_portfolio_routes_only_to_pcmci_plus(monkeypatch) -> None:
    called_methods: list[DiscoveryMethod] = []

    def fake_run(state, method, params):
        normalized = DiscoveryMethod(method)
        called_methods.append(normalized)
        return _report_for_method(normalized)

    monkeypatch.setattr(portfolio_module, "run_discovery_method", fake_run)
    monkeypatch.setattr(
        portfolio_module,
        "_characterize_data",
        lambda state, config: _characteristics(DataType.TIME_SERIES),
    )

    result = GraphDiscoveryPortfolioRunner().run(_time_series_state())

    assert called_methods == [DiscoveryMethod.PCMCI_PLUS]
    assert [candidate.hypothesis.method for candidate in result.candidates] == [
        DiscoveryMethod.PCMCI_PLUS
    ]
    assert result.skipped_families == {
        DiscoveryAlgorithmFamily.CONSTRAINT_BASED: "cross_sectional_only_for_phase_c1_to_c4",
        DiscoveryAlgorithmFamily.SCORE_BASED: "cross_sectional_only_for_phase_c1_to_c4",
        DiscoveryAlgorithmFamily.FUNCTIONAL: "cross_sectional_only_for_phase_c1_to_c4",
    }


def test_portfolio_surfaces_backend_failures_as_candidate_warnings(monkeypatch) -> None:
    def fake_run(state, method, params):
        normalized = DiscoveryMethod(method)
        if normalized is DiscoveryMethod.PC:
            raise ModuleNotFoundError("optional backend missing")
        return _report_for_method(normalized)

    monkeypatch.setattr(portfolio_module, "run_discovery_method", fake_run)
    monkeypatch.setattr(
        portfolio_module,
        "_characterize_data",
        lambda state, config: _characteristics(DataType.CROSS_SECTIONAL),
    )

    result = GraphDiscoveryPortfolioRunner().run(_tabular_state())
    failed_candidate = result.candidates[0]

    assert failed_candidate.hypothesis.method is DiscoveryMethod.PC
    assert failed_candidate.hypothesis.failure_reasons == [
        "algorithm_failed:ModuleNotFoundError: optional backend missing"
    ]
    assert failed_candidate.hypothesis.graph.nodes == ["X", "Y", "Z"]
    assert failed_candidate.hypothesis.graph.edges == []
    assert any("ModuleNotFoundError" in warning for warning in result.warnings)


def test_functional_runner_emits_graph_hypotheses_for_tabular_data() -> None:
    result = portfolio_module.run_discovery_method(
        _tabular_state(),
        DiscoveryMethod.ANM,
        {"functional_strength_threshold": 0.1, "functional_max_edges": 4},
    )

    assert result.method == DiscoveryMethod.ANM.value
    assert result.graph.graph_type is GraphType.DAG
    assert result.graph.edges
    assert any(
        "functional_portfolio_runner_uses_builtin_proxy" in warning for warning in result.warnings
    )


def test_functional_runner_clamps_non_finite_scores() -> None:
    assert portfolio_module._clamp01(float("nan")) == 0.0


def test_reachability_tracker_detects_transitive_cycles_without_dfs() -> None:
    tracker = portfolio_module._ReachabilityTracker(["A", "B", "C", "D"])

    assert tracker.would_create_cycle("A", "B") is False
    tracker.add_edge("A", "B")
    tracker.add_edge("B", "C")

    assert tracker.would_create_cycle("C", "A") is True
    assert tracker.would_create_cycle("C", "B") is True
    assert tracker.would_create_cycle("C", "D") is False

    tracker.add_edge("C", "D")

    assert tracker.would_create_cycle("D", "A") is True
