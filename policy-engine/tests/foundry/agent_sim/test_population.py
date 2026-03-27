"""Tests for agent_sim population management."""
from __future__ import annotations

import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim.population import (
    PopulationConfig,
    PopulationManager,
    LifecycleConfig,
    InheritanceConfig,
    create_population_manager,
    initialize_population,
)


class TestPopulationConfig:
    def test_defaults(self):
        cfg = PopulationConfig()
        assert cfg.retirement_age == 65
        assert cfg.base_fertility_rate == 0.02


class TestCreatePopulationManager:
    def test_initial_state(self):
        pm = create_population_manager(max_agents=100, initial_active=50)
        assert int(pm.n_active) == 50
        assert int(pm.free_top) == 50
        assert int(pm.total_births) == 0
        assert int(pm.total_deaths) == 0
        assert pm.max_agents == 100


class TestInitializePopulation:
    def test_basic(self, rng_key):
        agents, pm, next_id = initialize_population(
            initial_n_agents=10,
            max_agents=20,
            rng_key=rng_key,
            config=PopulationConfig(),
        )
        assert agents.active.shape[0] == 20  # padded to max_agents
        assert int(jnp.sum(agents.active)) == 10
        assert int(pm.n_active) == 10

    def test_raises_if_too_many(self, rng_key):
        with pytest.raises(ValueError, match="initial_n_agents"):
            initialize_population(
                initial_n_agents=100,
                max_agents=50,
                rng_key=rng_key,
                config=PopulationConfig(),
            )
