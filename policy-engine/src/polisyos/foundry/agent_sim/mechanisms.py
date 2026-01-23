from __future__ import annotations

from dataclasses import dataclass

import chex
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.policy import SharedPolicy, build_observations
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.types import FidelityLevel


@dataclass(frozen=True)
class TaxationMechanism(Mechanism):
    progressive_factor: float = 0.1

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="taxation",
            reads=frozenset({"agents.income", "agents.active", "policy.tax_rate"}),
            writes=frozenset({"agents.income"}),
            parameters={"progressive_factor": float},
            stochastic=False,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, jnp.ndarray]]:
        del rng_key, fidelity
        agents = state.agents
        base_rate = state.policy.tax_rate
        effective_rate = base_rate + self.progressive_factor * jnp.log1p(agents.income)
        effective_rate = jnp.clip(effective_rate, 0.0, 0.6)

        tax_paid = agents.income * effective_rate
        post_tax_income = agents.income - tax_paid
        post_tax_income = jnp.where(agents.active, post_tax_income, agents.income)

        new_agents = agents.replace(income=post_tax_income)
        active_count = jnp.sum(agents.active)
        safe_count = jnp.maximum(active_count, 1.0)
        metrics = {
            "total_tax_collected": jnp.sum(tax_paid * agents.active),
            "mean_effective_rate": jnp.sum(effective_rate * agents.active) / safe_count,
        }
        return state.replace(agents=new_agents), metrics


@dataclass(frozen=True)
class ConsumptionMechanism(Mechanism):
    policy: SharedPolicy
    min_consumption: float = 0.01

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="consumption",
            reads=frozenset(
                {
                    "agents.wealth",
                    "agents.income",
                    "agents.active",
                    "agents.risk_aversion",
                    "policy.interest_rate",
                }
            ),
            writes=frozenset({"agents.consumption", "agents.wealth"}),
            parameters={"min_consumption": float},
            stochastic=True,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, jnp.ndarray]]:
        del fidelity
        agents = state.agents
        obs = build_observations(agents, state.policy, state.time_step)
        logits = self.policy(obs, rng_key)
        consumption_fraction = jax.nn.sigmoid(logits)

        if consumption_fraction.ndim == 2:
            if consumption_fraction.shape[1] == 1:
                consumption_fraction = consumption_fraction[:, 0]
            else:
                consumption_fraction = consumption_fraction[:, 0]

        max_consumption = agents.wealth + agents.income
        consumption = consumption_fraction * max_consumption
        consumption = jnp.maximum(consumption, self.min_consumption)
        new_wealth = agents.wealth + agents.income - consumption
        new_wealth = jnp.maximum(new_wealth, 0.0)

        consumption = jnp.where(agents.active, consumption, 0.0)
        new_wealth = jnp.where(agents.active, new_wealth, agents.wealth)

        new_agents = agents.replace(consumption=consumption, wealth=new_wealth)
        active_count = jnp.sum(agents.active)
        safe_count = jnp.maximum(active_count, 1.0)
        mean_fraction = jnp.sum(consumption_fraction * agents.active) / safe_count
        metrics = {
            "mean_consumption": jnp.sum(consumption) / safe_count,
            "mean_saving_rate": 1.0 - mean_fraction,
        }

        return state.replace(agents=new_agents), metrics
