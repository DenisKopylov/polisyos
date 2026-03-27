"""Tests for agent_sim distribution tracking."""
from __future__ import annotations

import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim.distributions import (
    ComputeMode,
    DistributionConfig,
    DistributionState,
)


class TestDistributionConfig:
    def test_default_values(self):
        cfg = DistributionConfig()
        assert cfg.mode == ComputeMode.HARD
        assert cfg.update_frequency == 8
        assert cfg.n_quantiles == 10

    def test_custom_values(self):
        cfg = DistributionConfig(mode=ComputeMode.SOFT, n_quantiles=20)
        assert cfg.mode == ComputeMode.SOFT
        assert cfg.n_quantiles == 20


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
