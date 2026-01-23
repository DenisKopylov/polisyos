from __future__ import annotations

from dataclasses import dataclass

import chex
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.actor_critic import ActorCritic, sample_actions
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.types import FidelityLevel


@dataclass(frozen=True)
class TemporalConsumptionMechanism(Mechanism):
    actor_critic: ActorCritic
    horizon: int = 256
    min_consumption: float = 0.01
    include_expectations: bool = True

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="temporal_consumption",
            reads=frozenset(
                {
                    "agents.wealth",
                    "agents.income",
                    "agents.active",
                    "agents.risk_aversion",
                    "agents.discount_factor",
                    "agents.age",
                    "agents.expected_income_growth",
                    "policy.interest_rate",
                    "policy.expected_interest_rate",
                }
            ),
            writes=frozenset({"agents.consumption", "agents.wealth", "agents.expected_lifetime_utility"}),
            parameters={"horizon": int, "min_consumption": float},
            stochastic=True,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, jnp.ndarray]]:
        agents = state.agents
        obs = build_temporal_observations(
            state, horizon=self.horizon, include_expectations=self.include_expectations
        )
        action_output, values = self.actor_critic(obs, deterministic=True)

        if fidelity == FidelityLevel.HARD_DISCRETE:
            sampled_actions = action_output
        else:
            dist = self.actor_critic.get_action_distribution(
                obs, action_output=action_output
            )
            sampled_actions = sample_actions(
                dist, rng_key, action_type=self.actor_critic.action_type
            )

        if sampled_actions.ndim == 2:
            sampled_actions = sampled_actions[:, 0]
        consumption_fraction = jax.nn.sigmoid(sampled_actions)

        budget = agents.wealth + agents.income
        consumption = consumption_fraction * budget
        consumption = jnp.maximum(consumption, self.min_consumption)
        new_wealth = jnp.maximum(budget - consumption, 0.0)

        active = agents.active
        consumption = jnp.where(active, consumption, 0.0)
        new_wealth = jnp.where(active, new_wealth, agents.wealth)
        new_values = jnp.where(active, values, agents.expected_lifetime_utility)

        new_agents = agents.replace(
            consumption=consumption,
            wealth=new_wealth,
            expected_lifetime_utility=new_values,
        )

        active_count = jnp.sum(active)
        safe_count = jnp.maximum(active_count, 1.0)
        metrics = {
            "mean_consumption": jnp.sum(consumption) / safe_count,
            "mean_value": jnp.sum(values * active) / safe_count,
            "mean_consumption_fraction": jnp.sum(consumption_fraction * active) / safe_count,
        }
        return state.replace(agents=new_agents), metrics
