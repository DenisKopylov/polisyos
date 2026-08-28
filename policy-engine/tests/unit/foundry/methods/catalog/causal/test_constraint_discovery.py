from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.calibration.dp_ci import (
    CITestThresholdPolicy,
    CITestThresholdPolicySet,
    ci_threshold_scope,
)
from polisyos.foundry.methods.catalog.causal import constraint_discovery as constraint_module
from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
    FCIDiscovery,
    GESDiscovery,
    PCDiscovery,
)
from polisyos.foundry.methods.catalog.causal.protocols import TabularCausalDiscoveryData
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintFamily,
    CausalDiscoveryReport,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    PAGIdentificationPolicy,
)


def _state() -> TabularCausalDiscoveryData:
    data = np.array(
        [
            [0.2, 1.0, 0.4],
            [0.4, 1.3, 0.8],
            [0.7, 1.9, 1.1],
            [1.0, 2.2, 1.6],
            [1.3, 2.6, 1.9],
            [1.5, 2.9, 2.1],
        ],
        dtype=float,
    )
    return TabularCausalDiscoveryData(data=data, variable_names=["X", "Y", "Z"])


def _large_state(n_variables: int = 55, n_samples: int = 80) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(101)
    data = rng.normal(0.0, 1.0, size=(n_samples, n_variables))
    names = [f"V{i}" for i in range(n_variables)]
    return TabularCausalDiscoveryData(data=data, variable_names=names)


def _adj_with_xy_edge() -> np.ndarray:
    return np.array(
        [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 0],
        ],
        dtype=int,
    )


def _adj_without_edges() -> np.ndarray:
    return np.zeros((3, 3), dtype=int)


def _complete_adj(n_variables: int) -> np.ndarray:
    adjacency = np.zeros((n_variables, n_variables), dtype=int)
    for src in range(n_variables):
        for dst in range(src + 1, n_variables):
            adjacency[src, dst] = -1
            adjacency[dst, src] = 1
    return adjacency


def _common_parent_adj() -> np.ndarray:
    adjacency = np.zeros((5, 5), dtype=int)
    for dst in range(1, 5):
        adjacency[0, dst] = -1
        adjacency[dst, 0] = 1
    return adjacency


def _one_factor_state(n_samples: int = 800, seed: int = 7) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    latent = rng.normal(0.0, 1.0, size=n_samples)
    noise = rng.normal(0.0, 0.2, size=(n_samples, 4))
    loadings = np.array([0.9, 0.8, 1.1, 0.7], dtype=float)
    data = latent[:, None] * loadings[None, :] + noise
    return TabularCausalDiscoveryData(
        data=data,
        variable_names=["X1", "X2", "X3", "X4"],
    )


def _two_factor_state(n_samples: int = 800, seed: int = 11) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    latent_a = rng.normal(0.0, 1.0, size=n_samples)
    latent_b = rng.normal(0.0, 1.0, size=n_samples)
    noise = rng.normal(0.0, 0.2, size=(n_samples, 4))
    data = np.column_stack(
        [
            0.9 * latent_a + noise[:, 0],
            0.8 * latent_a + noise[:, 1],
            1.0 * latent_b + noise[:, 2],
            0.7 * latent_b + noise[:, 3],
        ]
    )
    return TabularCausalDiscoveryData(
        data=data,
        variable_names=["X1", "X2", "X3", "X4"],
    )


def _low_rank_state(n_samples: int = 900, seed: int = 17) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    latent = rng.normal(0.0, 1.0, size=n_samples)
    noise = rng.normal(0.0, 0.15, size=(n_samples, 5))
    loadings = np.array([1.1, 0.9, 0.8, 1.0, 0.7], dtype=float)
    data = latent[:, None] * loadings[None, :] + noise
    return TabularCausalDiscoveryData(
        data=data,
        variable_names=["M1", "M2", "M3", "M4", "M5"],
    )


def _full_rank_state(n_samples: int = 900, seed: int = 19) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    data = rng.normal(0.0, 1.0, size=(n_samples, 5))
    return TabularCausalDiscoveryData(
        data=data,
        variable_names=["M1", "M2", "M3", "M4", "M5"],
    )


def _trek_rank_state(n_samples: int = 1200, seed: int = 29) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    latent = rng.normal(0.0, 1.0, size=n_samples)
    noise = rng.normal(0.0, 0.12, size=(n_samples, 4))
    data = np.column_stack(
        [
            0.95 * latent + noise[:, 0],
            0.80 * latent + noise[:, 1],
            1.05 * latent + noise[:, 2],
            0.75 * latent + noise[:, 3],
        ]
    )
    return TabularCausalDiscoveryData(
        data=data,
        variable_names=["A1", "A2", "B1", "B2"],
    )


def _trek_full_rank_state(n_samples: int = 1200, seed: int = 31) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    latent_a = rng.normal(0.0, 1.0, size=n_samples)
    latent_b = rng.normal(0.0, 1.0, size=n_samples)
    noise = rng.normal(0.0, 0.12, size=(n_samples, 4))
    data = np.column_stack(
        [
            0.95 * latent_a + noise[:, 0],
            0.85 * latent_b + noise[:, 1],
            1.00 * latent_a + noise[:, 2],
            0.75 * latent_b + noise[:, 3],
        ]
    )
    return TabularCausalDiscoveryData(
        data=data,
        variable_names=["A1", "A2", "B1", "B2"],
    )


def _auto_trek_rank_state(n_samples: int = 1200, seed: int = 37) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    source = rng.normal(0.0, 1.0, size=n_samples)
    noise = rng.normal(0.0, 0.12, size=(n_samples, 5))
    data = np.column_stack(
        [
            source + noise[:, 0],
            0.90 * source + noise[:, 1],
            0.75 * source + noise[:, 2],
            1.05 * source + noise[:, 3],
            0.80 * source + noise[:, 4],
        ]
    )
    return TabularCausalDiscoveryData(
        data=data,
        variable_names=["L", "A1", "A2", "B1", "B2"],
    )


def _binary_iv_compatible_state(
    n_samples: int = 4000, seed: int = 41
) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(seed)
    z = rng.integers(0, 2, size=n_samples)
    u = rng.integers(0, 2, size=n_samples)
    d = (z | u).astype(float)
    y = (d.astype(int) | u).astype(float)
    return TabularCausalDiscoveryData(
        data=np.column_stack([z, d, y]).astype(float),
        variable_names=["Z", "D", "Y"],
    )


def _binary_iv_incompatible_state() -> TabularCausalDiscoveryData:
    rows: list[list[float]] = []
    rows.extend([[1.0, 0.0, 0.0]] * 360)
    rows.extend([[1.0, 1.0, 0.0]] * 20)
    rows.extend([[1.0, 1.0, 1.0]] * 20)
    rows.extend([[0.0, 0.0, 1.0]] * 260)
    rows.extend([[0.0, 1.0, 0.0]] * 140)
    return TabularCausalDiscoveryData(
        data=np.asarray(rows, dtype=float),
        variable_names=["Z", "D", "Y"],
    )


def test_pc_discovery_graceful_fallback_on_missing_backend(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error="ModuleNotFoundError: No module named 'causallearn'",
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = PCDiscovery.pure_step(_state(), params={})
    report = output["report"]

    assert output["__determinism_tier__"] is DeterminismTier.STATISTICAL
    assert report.graph.graph_type is GraphType.CPDAG
    assert report.graph.edges == []
    assert report.resolved_graph is None
    assert report.n_bootstrap == 0
    assert any("modulenotfounderror" in warning.lower() for warning in report.warnings)


def test_fci_discovery_graceful_fallback_on_timeout(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error="FCI timeout after 0.10s",
            timed_out=True,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = FCIDiscovery.pure_step(_state(), params={"timeout_seconds": 1})
    report = output["report"]

    assert report.graph.graph_type is GraphType.PAG
    assert report.graph.pag_identification_policy is PAGIdentificationPolicy.CONSERVATIVE
    assert report.graph.edges == []
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG
    assert report.n_bootstrap == 0
    assert any("timeout" in warning.lower() for warning in report.warnings)


def test_ges_discovery_bootstrap_stability_is_bounded(monkeypatch) -> None:
    call_count = {"value": 0}

    def _fake_runner(**kwargs):
        del kwargs
        idx = call_count["value"]
        call_count["value"] += 1
        adjacency = _adj_with_xy_edge() if idx in {0, 1, 3} else _adj_without_edges()
        return constraint_module._DiscoveryExecutionResult(
            adjacency=adjacency,
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = GESDiscovery.pure_step(
        _state(),
        params={"n_bootstrap": 3, "timeout_seconds": 60},
    )
    report = output["report"]

    assert report.n_bootstrap == 3
    assert report.bootstrap_stability
    for score in report.bootstrap_stability.values():
        assert 0.0 <= score <= 1.0


def test_endpoint_code_mapping_is_deterministic_and_warns_on_unknown_codes() -> None:
    adjacency = np.array(
        [
            [0, -1, 4],
            [1, 0, 1],
            [5, -1, 0],
        ],
        dtype=int,
    )

    edges, warnings = constraint_module._adjacency_to_edges(
        adjacency=adjacency,
        variable_names=["X", "Y", "Z"],
    )

    assert {(edge.src, edge.dst) for edge in edges} == {("X", "Y"), ("Z", "Y")}
    assert all(edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW for edge in edges)
    assert any("unsupported_endpoint_code_pair" in warning for warning in warnings)


def test_fci_report_keeps_pag_and_emits_resolved_dag(monkeypatch) -> None:
    adjacency = np.array(
        [
            [0, 2, 0],
            [1, 0, 0],
            [0, 0, 0],
        ],
        dtype=int,
    )

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=adjacency,
            metadata={"engine": "fake"},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = FCIDiscovery.pure_step(_state(), params={"n_bootstrap": 0})
    report = output["report"]

    assert report.graph.graph_type is GraphType.PAG
    assert report.graph.pag_identification_policy is PAGIdentificationPolicy.CONSERVATIVE
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG


def test_pc_discovery_auto_prefers_dagma_for_high_dim(monkeypatch) -> None:
    called = {"count": 0}

    def _fake_run_dagma_discovery(*, state, params):
        del params
        called["count"] += 1
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=list(state.variable_names),
            edges=[],
            discovery_method="dagma",
        )
        report = CausalDiscoveryReport(
            method="dagma",
            graph=graph,
            warnings=[],
            metadata={"optimizer": "fake"},
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.dagma_discovery.run_dagma_discovery",
        _fake_run_dagma_discovery,
    )

    output = PCDiscovery.pure_step(
        _large_state(),
        params={"discovery_scale_backend": "auto", "discovery_ci_backend": "numpy"},
    )
    report = output["report"]

    assert called["count"] == 1
    assert report.method == "dagma"
    assert report.metadata.get("scale_backend_used") == "dagma"


def test_pc_discovery_explicit_jax_ci_backend_is_functional() -> None:
    state = _state()
    output = PCDiscovery.pure_step(
        state,
        params={
            "discovery_ci_backend": "jax",
            "significance_level": 0.05,
            "n_bootstrap": 0,
            "timeout_seconds": 30,
        },
    )
    report = output["report"]

    assert report.metadata["ci_backend_requested"] == "jax"
    assert report.metadata["ci_backend_used"] == "jax"
    assert report.metadata["ci_backend_runtime"] == "jax_partial_corr"
    assert report.graph.nodes == ["X", "Y", "Z"]


def test_implied_ci_constraints_extract_minimal_dag_separator() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Z", "Y"],
        edges=[
            CausalEdge(src="X", dst="Z"),
            CausalEdge(src="Z", dst="Y"),
        ],
        discovery_method="unit",
    )

    constraints = constraint_module._implied_ci_constraints(graph)

    assert any(
        constraint.variables == ("X", "Y") and constraint.conditioning_set == ("Z",)
        for constraint in constraints
    )


def test_implied_ci_constraints_extract_pag_marginal_separation() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[],
        discovery_method="unit",
        pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
    )

    constraints = constraint_module._implied_ci_constraints(graph)

    assert any(
        frozenset(constraint.variables) == frozenset({"X", "Y"})
        and constraint.conditioning_set == ()
        for constraint in constraints
    )


def test_ci_violation_escalates_to_blocker(monkeypatch) -> None:
    rng = np.random.default_rng(23)
    x = rng.normal(0.0, 1.0, size=200)
    y = 0.85 * x + rng.normal(0.0, 0.25, size=200)
    z = rng.normal(0.0, 1.0, size=200)
    state = TabularCausalDiscoveryData(
        data=np.column_stack([x, y, z]),
        variable_names=["X", "Y", "Z"],
    )

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_adj_without_edges(),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = PCDiscovery.pure_step(
        state,
        params={"n_bootstrap": 0, "timeout_seconds": 30},
    )
    report = output["report"]

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.severity == "blocker"
    assert report.algebraic_constraints.n_violated_constraints >= 1
    assert report.metadata["algebraic_constraint_severity"] == "blocker"
    assert "ci" in report.metadata["algebraic_constraint_families_run"]


def test_ci_violation_carries_dp_calibration_metadata(monkeypatch) -> None:
    x = np.tile(np.array([0.0, 1.0]), 200)
    y = x.copy()
    state = TabularCausalDiscoveryData(
        data=np.column_stack([x, y]),
        variable_names=["X", "Y"],
    )

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=np.zeros((2, 2), dtype=int),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    dp_context = {
        "mechanism": "gaussian_counts",
        "epsilon": 0.6,
        "delta": 1e-6,
    }
    policies = CITestThresholdPolicySet(
        policies=(
            CITestThresholdPolicy(
                threshold_scope=ci_threshold_scope(
                    family="categorical_ci",
                    query_type="g2",
                    estimator="stratified_counts",
                    dp_context=dp_context,
                    readiness_target="diagnostic",
                ),
                threshold_registry_version=1,
            ),
        )
    )
    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "dp_context": dp_context,
            "ci_threshold_policies": policies.model_dump(mode="python"),
        },
    )["report"]

    assert report.algebraic_constraints is not None
    violation = next(
        item
        for item in report.algebraic_constraints.violated_constraints_preview
        if item.family is AlgebraicConstraintFamily.CI
    )
    assert violation.metadata["route"] == "g_test"
    assert violation.metadata["ci_test_impl"] == "categorical_ci"
    assert violation.metadata["calibration_mode"] == "analytic_weighted_chi2"
    assert violation.metadata["dp_context_summary"]["mechanism"] == "gaussian_counts"
    assert violation.metadata["threshold_registry_scope"]["family"] == "categorical_ci"


def test_malformed_algebraic_blocks_are_rejected() -> None:
    with pytest.raises(ValueError):
        PCDiscovery.pure_step(
            _state(),
            params={
                "algebraic_blocks": [
                    {
                        "block_id": "bad_rank",
                        "family": "overcomplete",
                        "variables": ["X", "Y", "Z"],
                    }
                ]
            },
        )


def test_tetrad_block_passes_for_single_factor_data(monkeypatch) -> None:
    state = _one_factor_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_complete_adj(4),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "factor_1",
                    "family": "tetrad",
                    "variables": ["X1", "X2", "X3", "X4"],
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert (
        AlgebraicConstraintFamily.TETRAD.value
        in report.metadata["algebraic_constraint_families_run"]
    )
    assert report.algebraic_constraints.violated_by_family["tetrad"] == 0


def test_tetrad_block_flags_two_factor_violation(monkeypatch) -> None:
    state = _two_factor_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_complete_adj(4),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "factor_1",
                    "family": "tetrad",
                    "variables": ["X1", "X2", "X3", "X4"],
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.violated_by_family["tetrad"] >= 1
    assert report.algebraic_constraints.severity == "warning"
    violation = report.algebraic_constraints.violated_constraints_preview[0]
    metrics = violation.metadata["block_calibration_metrics"]
    decision = violation.metadata["severity_decision"]
    assert set(metrics) >= {
        "min_q",
        "max_abs_z",
        "median_delta",
        "violation_support",
        "effective_n",
        "bootstrap_draws",
    }
    assert metrics["bootstrap_draws"] == constraint_module._ALGEBRAIC_BOOTSTRAP_DRAWS
    assert decision["severity"] == "warning"
    assert "bootstrap_draws_below_blocker_floor" in decision["blocker_eligibility_failures"]


def test_overcomplete_block_passes_for_low_rank_data(monkeypatch) -> None:
    state = _low_rank_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_complete_adj(5),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "rank_1",
                    "family": "overcomplete",
                    "variables": ["M1", "M2", "M3", "M4", "M5"],
                    "expected_rank": 1,
                    "max_residual_energy": 0.12,
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.violated_by_family["overcomplete"] == 0


def test_overcomplete_block_flags_full_rank_violation(monkeypatch) -> None:
    state = _full_rank_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_complete_adj(5),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "rank_1",
                    "family": "overcomplete",
                    "variables": ["M1", "M2", "M3", "M4", "M5"],
                    "expected_rank": 1,
                    "max_residual_energy": 0.05,
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.violated_by_family["overcomplete"] >= 1
    assert report.algebraic_constraints.severity == "warning"


def test_trek_rank_block_passes_for_rank_one_cross_covariance(monkeypatch) -> None:
    state = _trek_rank_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_complete_adj(4),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "trek_rank_1",
                    "family": "trek_rank",
                    "variables": ["A1", "A2", "B1", "B2"],
                    "row_variables": ["A1", "A2"],
                    "col_variables": ["B1", "B2"],
                    "max_rank": 1,
                    "assumption_regime": "linear_gaussian_continuous",
                    "test_mode": "bootstrap_rank",
                    "max_residual_energy": 0.12,
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert (
        AlgebraicConstraintFamily.TREK_RANK.value
        in report.metadata["algebraic_constraint_families_run"]
    )
    assert report.algebraic_constraints.violated_by_family["trek_rank"] == 0
    assert report.algebraic_constraints.blocker_conditions_met_by_family["trek_rank"] is True
    assert report.algebraic_constraints.graph_ranking_penalty == 0.0


def test_trek_rank_block_flags_full_rank_cross_covariance_as_blocker(monkeypatch) -> None:
    state = _trek_full_rank_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_complete_adj(4),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "trek_rank_1",
                    "family": "trek_rank",
                    "variables": ["A1", "A2", "B1", "B2"],
                    "row_variables": ["A1", "A2"],
                    "col_variables": ["B1", "B2"],
                    "max_rank": 1,
                    "assumption_regime": "linear_gaussian_continuous",
                    "test_mode": "bootstrap_minor",
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.violated_by_family["trek_rank"] >= 1
    assert report.algebraic_constraints.severity == "blocker"
    assert report.algebraic_constraints.blocker_conditions_met_by_family["trek_rank"] is True
    assert report.algebraic_constraints.graph_ranking_penalty > 0.0
    trek_violation = next(
        violation
        for violation in report.algebraic_constraints.violated_constraints_preview
        if violation.family is AlgebraicConstraintFamily.TREK_RANK
    )
    assert trek_violation.scope_of_falsification.value == "graph_class"
    assert trek_violation.reproducibility_tier.value == "stochastic_bootstrap"
    assert trek_violation.ranking_weight > 0.0


def test_graph_implied_trek_rank_blocks_are_auto_inferred(monkeypatch) -> None:
    state = _auto_trek_rank_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_common_parent_adj(),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={"timeout_seconds": 30},
    )["report"]

    assert report.algebraic_constraints is not None
    assert (
        AlgebraicConstraintFamily.TREK_RANK.value
        in report.metadata["algebraic_constraint_families_run"]
    )
    assert report.algebraic_constraints.tested_by_family["trek_rank"] >= 1
    assert report.algebraic_constraints.violated_by_family["trek_rank"] == 0
    assert any(
        constraint.source_block_id and constraint.source_block_id.startswith("auto_trek_rank:")
        for constraint in report.algebraic_constraints.implied_constraints_preview
        if constraint.family is AlgebraicConstraintFamily.TREK_RANK
    )
    assert any(
        "trek_rank_auto_inferred" in warning for warning in report.algebraic_constraints.warnings
    )


def test_algebraic_geometry_invariant_block_is_ranking_only_info_signal(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_adj_without_edges(),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        _state(),
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "geom_1",
                    "family": "algebraic_geometry_invariant",
                    "variables": ["X", "Y", "Z"],
                    "invariant_polynomials": ["sigma_xy * sigma_yz - sigma_xz * sigma_yy"],
                    "semi_algebraic_inequalities": ["det(Sigma[X,Y,Z]) >= 0"],
                    "derivation_method": "groebner_elimination",
                    "precomputed_violation_score": 0.7,
                    "test_mode": "offline_catalog",
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert (
        AlgebraicConstraintFamily.ALGEBRAIC_GEOMETRY_INVARIANT.value
        in report.metadata["algebraic_constraint_families_run"]
    )
    assert report.algebraic_constraints.tested_by_family["algebraic_geometry_invariant"] == 0
    assert report.algebraic_constraints.violated_by_family["algebraic_geometry_invariant"] == 1
    assert report.algebraic_constraints.severity == "info"
    assert report.algebraic_constraints.graph_ranking_penalty > 0.0
    geometry_violation = next(
        violation
        for violation in report.algebraic_constraints.violated_constraints_preview
        if violation.family is AlgebraicConstraintFamily.ALGEBRAIC_GEOMETRY_INVARIANT
    )
    assert geometry_violation.scope_of_falsification.value == "ranking_only"
    assert geometry_violation.reproducibility_tier.value == "research_preview"


def test_binary_iv_algebraic_geometry_block_passes_on_compatible_data(monkeypatch) -> None:
    state = _binary_iv_compatible_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_adj_without_edges(),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "iv_binary",
                    "family": "algebraic_geometry_invariant",
                    "variables": ["Z", "D", "Y"],
                    "derivation_method": "iv_binary_response_polytope",
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.tested_by_family["algebraic_geometry_invariant"] == 4
    assert report.algebraic_constraints.violated_by_family["algebraic_geometry_invariant"] == 0
    assert (
        report.algebraic_constraints.blocker_conditions_met_by_family[
            "algebraic_geometry_invariant"
        ]
        is False
    )


def test_binary_iv_algebraic_geometry_block_emits_graph_class_blocker(monkeypatch) -> None:
    state = _binary_iv_incompatible_state()

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_adj_without_edges(),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        state,
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "iv_binary",
                    "family": "algebraic_geometry_invariant",
                    "variables": ["Z", "D", "Y"],
                    "derivation_method": "iv_binary_response_polytope",
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.severity == "blocker"
    assert report.algebraic_constraints.tested_by_family["algebraic_geometry_invariant"] == 4
    assert report.algebraic_constraints.violated_by_family["algebraic_geometry_invariant"] >= 1
    assert (
        report.algebraic_constraints.blocker_conditions_met_by_family[
            "algebraic_geometry_invariant"
        ]
        is True
    )
    geometry_violation = next(
        violation
        for violation in report.algebraic_constraints.violated_constraints_preview
        if violation.family is AlgebraicConstraintFamily.ALGEBRAIC_GEOMETRY_INVARIANT
    )
    assert geometry_violation.scope_of_falsification.value == "graph_class"
    assert geometry_violation.severity == "blocker"
    assert geometry_violation.metadata["route"] == "binary_iv_instrumental_inequalities"
    assert (
        geometry_violation.metadata["negative_certificate"]["blocking_type"]
        == "model_class_incompatible"
    )


def test_nested_verma_block_is_recorded_as_research_preview(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_complete_adj(3),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    report = PCDiscovery.pure_step(
        _state(),
        params={
            "timeout_seconds": 30,
            "algebraic_blocks": [
                {
                    "block_id": "verma_1",
                    "family": "nested_verma",
                    "variables": ["X", "Y"],
                    "cadmg_scope": "X->M->Y with latent U",
                    "fixing_sequence": ["fix(M)"],
                    "kernel_statement": "sum_m p(m|x) p(y|m,x') is invariant in x",
                    "model_family": "gaussian_nested",
                    "positivity_required": True,
                    "test_mode": "research_preview",
                }
            ],
        },
    )["report"]

    assert report.algebraic_constraints is not None
    assert (
        AlgebraicConstraintFamily.NESTED_VERMA.value
        in report.metadata["algebraic_constraint_families_run"]
    )
    assert report.algebraic_constraints.tested_by_family["nested_verma"] == 0
    assert report.algebraic_constraints.violated_by_family["nested_verma"] == 0
    assert report.algebraic_constraints.blocker_conditions_met_by_family["nested_verma"] is False
    assert report.algebraic_constraints.graph_ranking_penalty == 0.0
    assert any(
        "nested_verma_research_preview" in warning
        for warning in report.algebraic_constraints.warnings
    )


def test_algebraic_audit_failure_degrades_to_warning(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=_adj_with_xy_edge(),
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    def _boom(**kwargs):
        del kwargs
        raise RuntimeError("audit blew up")

    monkeypatch.setattr(constraint_module, "_run_algebraic_constraint_audit", _boom)

    report = PCDiscovery.pure_step(_state(), params={"timeout_seconds": 30})["report"]

    assert any("algebraic_audit_failed" in warning for warning in report.warnings)
    assert report.graph.edges
    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.severity == "warning"


@pytest.mark.integration
def test_fci_var1_emits_pag_uncertainty_when_causallearn_available() -> None:
    pytest.importorskip("causallearn")

    rng = np.random.default_rng(13)
    n = 1400
    latent = rng.normal(0.0, 1.0, size=n)
    x = 0.95 * latent + rng.normal(0.0, 0.4, size=n)
    y = 0.90 * latent + rng.normal(0.0, 0.4, size=n)

    state = TabularCausalDiscoveryData(
        data=np.column_stack([x, y]),
        variable_names=["X", "Y"],
    )

    output = FCIDiscovery.pure_step(
        state,
        params={
            "significance_level": 0.01,
            "indep_test": "fisherz",
            "timeout_seconds": 180,
            "n_bootstrap": 0,
        },
    )
    report = output["report"]

    assert report.graph.graph_type is GraphType.PAG
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG
    assert any(
        edge.mark_src is EdgeMark.CIRCLE
        or edge.mark_dst is EdgeMark.CIRCLE
        or (edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW)
        for edge in report.graph.edges
    )


@pytest.mark.integration
def test_pc_and_ges_recover_chain_adjacency_when_causallearn_available() -> None:
    pytest.importorskip("causallearn")

    rng = np.random.default_rng(21)
    n = 1200
    x = rng.normal(0.0, 1.0, size=n)
    y = 0.9 * x + rng.normal(0.0, 0.4, size=n)
    z = 0.8 * y + rng.normal(0.0, 0.4, size=n)
    state = TabularCausalDiscoveryData(
        data=np.column_stack([x, y, z]),
        variable_names=["X", "Y", "Z"],
    )

    pc_report = PCDiscovery.pure_step(
        state,
        params={"significance_level": 0.01, "timeout_seconds": 180, "n_bootstrap": 0},
    )["report"]
    ges_report = GESDiscovery.pure_step(
        state,
        params={"score_func": "local_score_BIC", "timeout_seconds": 180, "n_bootstrap": 0},
    )["report"]

    for report in (pc_report, ges_report):
        adjacency_pairs = {frozenset((edge.src, edge.dst)) for edge in report.graph.edges}
        assert frozenset({"X", "Y"}) in adjacency_pairs
        assert frozenset({"Y", "Z"}) in adjacency_pairs


# ---------------------------------------------------------------------------
# UnifiedCausalDiscovery integration: new report fields
# ---------------------------------------------------------------------------


def test_unified_discovery_report_has_skeleton_agreement(monkeypatch: pytest.MonkeyPatch) -> None:
    """DiscoveryPipelineReport.skeleton_agreement should be a dict[str, float] in [0,1]."""
    from polisyos.foundry.methods.catalog.causal.discovery_pipeline import (
        UnifiedCausalDiscovery,
    )
    from polisyos.foundry.methods.catalog.causal.protocols import UnifiedDiscoveryData
    from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    # Build a minimal CPDAG report to feed through the pipeline
    cpdag = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["A", "B"],
        edges=[CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
    )
    mock_report = CausalDiscoveryReport(method="pc", graph=cpdag)

    def _fake_parallel(state, dc, algo_specs, params):
        weights = {spec.name: spec.weight for spec in algo_specs}
        total = sum(weights.values()) or 1.0
        normed = {k: v / total for k, v in weights.items()}
        # Return pc report regardless of what was asked
        return [mock_report], {"pc": 1.0}

    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.discovery_pipeline._run_algorithms_parallel",
        _fake_parallel,
    )

    state = UnifiedDiscoveryData(
        data=np.random.default_rng(0).normal(size=(20, 2)),
        variable_names=["A", "B"],
    )
    result = UnifiedCausalDiscovery.pure_step(state, {"force_algorithms": "pc"})
    report = result["report"]

    assert isinstance(report.skeleton_agreement, dict)
    for key, score in report.skeleton_agreement.items():
        assert isinstance(key, str)
        assert 0.0 <= score <= 1.0


def test_unified_discovery_report_has_pag_validity_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """DiscoveryPipelineReport should have pag_validity_violations (list) and temporal_dag fields."""
    from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
    from polisyos.foundry.methods.catalog.causal.protocols import UnifiedDiscoveryData
    from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
    )
    mock_report = CausalDiscoveryReport(method="fci", graph=pag)

    def _fake_parallel(state, dc, algo_specs, params):
        return [mock_report], {"fci": 1.0}

    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.discovery_pipeline._run_algorithms_parallel",
        _fake_parallel,
    )

    state = UnifiedDiscoveryData(
        data=np.random.default_rng(1).normal(size=(20, 2)),
        variable_names=["X", "Y"],
    )
    result = UnifiedCausalDiscovery.pure_step(state, {"force_algorithms": "fci"})
    report = result["report"]

    assert isinstance(report.pag_validity_violations, list)
    # temporal_dag should be None since no PCMCI run
    assert report.temporal_dag is None
