from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.policy import ensure_policy_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def _inverse_tax_rates(
    incomes: np.ndarray,
    density_row: np.ndarray,
    elasticity_row: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    mass = density_row / np.sum(density_row)
    tail_mass = np.cumsum(mass[::-1])[::-1]
    pareto_like = np.maximum(incomes, 1.0) * mass / np.maximum(tail_mass, 1.0e-8)
    tau = (1.0 - weights) / np.maximum(1.0 - weights + pareto_like * elasticity_row, 1.0e-8)
    return np.clip(tau, 0.0, 0.95)


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def test_policy_frontier_methods_run() -> None:
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()

    sufficient = registry.get("policy.welfare.sufficient_statistics_welfare@1.0.0")
    sufficient_result = sufficient.pure_step(
        {
            "mechanical_effects": [1.2, 0.8, 0.4],
            "revenue_effects": [0.3, 0.1, -0.1],
            "elasticities": [0.2, 0.3, 0.4],
            "social_weights": [3.0, 2.0, 1.0],
        },
        {},
    )["result"]
    assert sufficient_result["welfare_delta"] > 0.0

    multiplier = registry.get("policy.macro.fiscal_multiplier@1.0.0")
    multiplier_result = multiplier.pure_step(
        {
            "output_changes": [0.3, 0.2, 0.15, 0.1],
            "spending_changes": [0.2, 0.12, 0.1, 0.05],
            "slack_indicator": [1, 1, 0, 0],
        },
        {},
    )["result"]
    assert multiplier_result["cumulative_multiplier"] > 0.0
    assert "slack" in multiplier_result["state_multipliers"]

    optimal_tax = registry.get("policy.public_finance.optimal_linear_tax@1.0.0")
    tax_result = optimal_tax.pure_step(
        {
            "incomes": [10.0, 12.0, 18.0, 25.0, 40.0, 70.0],
            "social_weights": [2.5, 2.2, 1.8, 1.2, 0.9, 0.6],
        },
        {"elasticity": 0.35},
    )["result"]
    assert 0.0 <= tax_result["optimal_tax_rate"] <= 1.0

    inverse = registry.get("policy.welfare.state_dependent_inverse_social_weights@1.0.0")
    income_grid = np.array([10.0, 18.0, 28.0, 42.0], dtype=float)
    density = np.array(
        [
            [0.34, 0.28, 0.22, 0.16],
            [0.20, 0.24, 0.28, 0.28],
        ],
        dtype=float,
    )
    elasticities = np.array(
        [
            [0.20, 0.22, 0.24, 0.26],
            [0.18, 0.21, 0.23, 0.25],
        ],
        dtype=float,
    )
    weights = np.array([1.0, 0.92, 0.84, 0.76], dtype=float)
    tax_rates = np.vstack(
        [
            _inverse_tax_rates(income_grid, density[idx], elasticities[idx], weights)
            for idx in range(2)
        ]
    )
    inverse_result = inverse.pure_step(
        {
            "income_grid": income_grid,
            "marginal_tax_rates": tax_rates,
            "density": density,
            "elasticities": elasticities[:, :, None],
            "state_features": np.zeros((income_grid.size, 1), dtype=float),
            "basis_matrix": np.eye(income_grid.size, dtype=float),
        },
        {"normalization": "reference_cell", "reference_index": 0},
    )["result"]
    assert inverse_result["social_weight_ref"].startswith(
        "swr://policy.welfare/state_dependent_inverse_social_weights@1.0.0#"
    )


def test_mean_field_and_krusell_smith_lite_converge() -> None:
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()

    mean_field = registry.get("policy.agent_sim.mean_field_equilibrium@1.0.0")
    reward = np.array([[1.0, 0.4], [0.6, 1.2]], dtype=float)
    transition = np.array(
        [
            [[0.8, 0.2], [0.3, 0.7]],
            [[0.5, 0.5], [0.1, 0.9]],
        ],
        dtype=float,
    )
    mean_field_result = mean_field.pure_step(
        {
            "reward_matrix": reward,
            "transition_tensor": transition,
            "congestion_costs": [0.2, 0.1],
        },
        {"max_iter": 120},
    )["result"]
    assert np.isclose(np.sum(mean_field_result["stationary_distribution"]), 1.0, atol=1e-6)
    assert len(mean_field_result["policy_matrix"]) == 2

    ks = registry.get("policy.macro.krusell_smith_lite@1.0.0")
    ks_result = ks.pure_step(
        {
            "asset_grid": np.linspace(0.0, 8.0, 9),
            "productivity_states": np.array([0.6, 1.0, 1.4]),
            "productivity_transition": np.array(
                [[0.8, 0.2, 0.0], [0.1, 0.8, 0.1], [0.0, 0.2, 0.8]],
                dtype=float,
            ),
        },
        {},
    )["result"]
    assert ks_result["aggregate_capital"] >= 0.0
    assert len(ks_result["stationary_distribution"]) == 9


def test_foundation_model_policy_analysis_uses_tfidf_runtime() -> None:
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()
    fm = registry.get("policy.evaluation.foundation_model_policy_analysis@1.0.0")

    result = fm.pure_step(
        {
            "policy_options": [
                "Expand wage subsidy for low-income workers",
                "Cut capital taxes without targeting",
            ],
            "evidence_snippets": [
                "Low-income employment responds positively to wage subsidies in recent evaluations.",
                "Untargeted capital tax cuts mainly benefit high-income households in this setting.",
                "Administrative simplicity matters for implementation speed.",
            ],
            "policy_query": "Which policy best raises low-income employment?",
        },
        {"embedding_backend": "tfidf"},
    )["result"]

    assert result["runtime_backend"] == "tfidf"
    assert result["policy_rankings"][0]["policy_index"] == 0


def test_sufficient_statistics_propagates_social_weight_ref() -> None:
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()
    sufficient = registry.get("policy.welfare.sufficient_statistics_welfare@1.0.0")
    social_weight_ref = "swr://policy.welfare/state_dependent_inverse_social_weights@1.0.0#abc123"

    result = sufficient.pure_step(
        {
            "mechanical_effects": [1.0, 0.6, 0.2],
            "revenue_effects": [0.3, 0.1, -0.1],
            "elasticities": [0.2, 0.25, 0.3],
            "social_weights": [2.0, 1.5, 1.0],
        },
        {"social_weight_ref": social_weight_ref},
    )["result"]

    assert result["social_weight_ref"] == social_weight_ref


def test_optimal_linear_tax_propagates_social_weight_ref() -> None:
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()
    optimal_tax = registry.get("policy.public_finance.optimal_linear_tax@1.0.0")
    social_weight_ref = "swr://policy.welfare/state_dependent_inverse_social_weights@1.0.0#def456"

    result = optimal_tax.pure_step(
        {
            "incomes": [10.0, 12.0, 18.0, 25.0, 40.0, 70.0],
            "social_weights": [2.5, 2.2, 1.8, 1.2, 0.9, 0.6],
        },
        {"elasticity": 0.35, "social_weight_ref": social_weight_ref},
    )["result"]

    assert result["social_weight_ref"] == social_weight_ref
