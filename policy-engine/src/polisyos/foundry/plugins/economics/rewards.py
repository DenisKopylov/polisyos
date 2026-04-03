"""Public economics rewards module API."""
from __future__ import annotations

import jax.numpy as jnp

from polisyos.foundry.plugins.economics.state import EconomicState


class EconomicReward:
    """Reward function for economic agents."""

    utility_type: str = "crra"
    risk_aversion: float = 2.0

    def compute(
        self,
        state: EconomicState,
        next_state: EconomicState,
        agent_actions: jnp.ndarray | None = None,
    ) -> jnp.ndarray:
        del agent_actions
        agents = next_state.agents
        prev_agents = state.agents
        active = agents.active.astype(jnp.float32)

        consumption = agents.consumption + 1e-6

        if self.utility_type == "crra":
            gamma = agents.risk_aversion
            denom = 1.0 - gamma + 1e-8
            utility = jnp.where(
                gamma == 1.0,
                jnp.log(consumption),
                consumption ** (1.0 - gamma) / denom,
            )
        elif self.utility_type == "log":
            utility = jnp.log(consumption)
        else:
            utility = consumption / 10000.0

        wealth_change = agents.wealth - prev_agents.wealth
        wealth_utility = jnp.tanh(wealth_change / 10000.0) * 0.1

        employment_bonus = agents.employed.astype(jnp.float32) * 0.05

        reward = (utility + wealth_utility + employment_bonus) * active
        return reward
