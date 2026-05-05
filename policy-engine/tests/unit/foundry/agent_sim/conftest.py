"""Shared fixtures for agent_sim tests."""

from __future__ import annotations

import jax
import pytest

jax.config.update("jax_platforms", "cpu")

from polisyos.foundry.agent_sim.state import GlobalState


@pytest.fixture
def simple_state():
    return GlobalState.empty(n_agents=20, seed=42, max_agents=20)


@pytest.fixture
def rng_key():
    return jax.random.PRNGKey(0)
