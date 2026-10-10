"""Tests for agent_sim distribution tracking."""

from __future__ import annotations

import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import (
    ComputeMode,
    DistributionConfig,
    DistributionState,
    compute_quantiles,
    compute_quantiles_hard,
    compute_quantiles_soft,
)


class TestDistributionConfig:
    def test_default_values(self):
        cfg = DistributionConfig()
        assert cfg.mode == ComputeMode.HARD
        assert cfg.update_frequency == 8
        assert cfg.n_quantiles == 10
        assert cfg.use_approximate is False

    def test_custom_values(self):
        cfg = DistributionConfig(mode=ComputeMode.SOFT, n_quantiles=20)
        assert cfg.mode == ComputeMode.SOFT
        assert cfg.n_quantiles == 20

    def test_hard_quantiles_do_not_use_approximate_sampling(self):
        values = jnp.linspace(0.0, 9.0, 10)
        active = jnp.ones((10,), dtype=jnp.bool_)
        actual = compute_quantiles(
            values,
            active,
            5,
            mode=ComputeMode.HARD,
            use_approximate=True,
            rng_key=jax.random.PRNGKey(0),
            sample_size=3,
        )
        expected = compute_quantiles_hard(values, active, 5)
        assert bool(jnp.allclose(actual, expected))

    def test_soft_quantiles_ignore_inactive_extreme_values(self):
        values = jnp.array([0.0, 10.0, 1_000_000.0, 20.0], dtype=jnp.float32)
        active = jnp.array([True, True, False, True])
        quantiles = compute_quantiles_soft(values, active, 3, temperature=0.05)
        assert bool(jnp.all(jnp.isfinite(quantiles)))
        assert float(quantiles[-1]) < 100.0

    def test_soft_quantiles_are_jittable(self):
        values = jnp.array([0.0, 10.0, 20.0, 30.0], dtype=jnp.float32)
        active = jnp.array([True, False, True, True])
        compiled = jax.jit(
            lambda v, a: compute_quantiles(
                v,
                a,
                4,
                mode=ComputeMode.SOFT,
                temperature=0.2,
            )
        )
        quantiles = compiled(values, active)
        assert quantiles.shape == (4,)
        assert bool(jnp.all(jnp.isfinite(quantiles)))


class TestDistributionState:
    def test_empty_creation(self):
        ds = DistributionState.empty(n_agents=50, n_quantiles=5)
        assert ds.wealth_quantiles.shape == (5,)
        assert ds.wealth_ranks.shape == (50,)
        assert int(ds.last_update_step) == -1

    def test_empty_gini_zero(self):
        ds = DistributionState.empty(n_agents=10)
        assert float(ds.gini_wealth) == 0.0
        assert float(ds.gini_income) == 0.0
