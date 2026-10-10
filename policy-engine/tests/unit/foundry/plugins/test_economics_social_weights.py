import jax.numpy as jnp

from polisyos.foundry.methods.catalog.policy.welfare import (
    clear_social_weight_manifest_registry,
    register_social_weight_manifest,
)
from polisyos.foundry.plugins.economics import EconomicState, SocialWelfareObjective


def _register_test_social_weights() -> str:
    clear_social_weight_manifest_registry()
    manifest = register_social_weight_manifest(
        {
            "method_fqn": "policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            "normalization": "mean_one",
            "basis": {"family": "cell"},
            "regime_ids": ["test"],
            "state_keys": [],
            "support": {"n_cells": 3},
            "diagnostics": {"moment_norm": 0.0},
            "coefficients": [2.0, 1.0, 0.5],
            "income_grid": [0.0, 10.0, 20.0],
            "weights_on_grid": [2.0, 1.0, 0.5],
            "normalization_weights": [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0],
        }
    )
    return manifest["ref"]


def test_social_welfare_objective_applies_registered_social_weight_ref() -> None:
    social_weight_ref = _register_test_social_weights()
    state = EconomicState.empty(n_agents=3, seed=0)
    agents = state.agents.replace(
        income=jnp.array([0.0, 10.0, 20.0], dtype=jnp.float32),
        consumption=jnp.array([10.0, 20.0, 40.0], dtype=jnp.float32),
        active=jnp.array([True, True, True]),
    )
    state = state.replace(agents=agents)

    objective = SocialWelfareObjective(weights={}, social_weight_ref=social_weight_ref)
    welfare = objective.evaluate(state)

    raw_weights = jnp.array([2.0, 1.0, 0.5], dtype=jnp.float32)
    normalized_weights = raw_weights / jnp.mean(raw_weights)
    expected = jnp.mean(normalized_weights * agents.consumption)

    assert bool(jnp.isclose(welfare, expected, atol=1e-5))
    assert not bool(jnp.isclose(welfare, jnp.mean(agents.consumption), atol=1e-5))
