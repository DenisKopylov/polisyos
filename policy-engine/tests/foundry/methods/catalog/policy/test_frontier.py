from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.policy import ensure_policy_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


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
