"""Public agent sim credit assignment module API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import compute_quantiles_hard
from polisyos.foundry.agent_sim.state import GlobalState


class CreditMode(str, Enum):
    """Credit mode public type."""

    INDIVIDUAL = "individual"
    SHARED = "shared"
    COUNTERFACTUAL = "counterfactual"
    MEAN_FIELD = "mean_field"
    SHAPLEY_APPROX = "shapley_approx"


@dataclass(frozen=True)
class CreditConfig:
    """Choose how global returns are reallocated back to individual agents."""

    mode: CreditMode = CreditMode.INDIVIDUAL
    counterfactual_baseline: str = "mean"
    mean_field_temperature: float = 1.0
    shapley_samples: int = 10


def compute_credit_assignment(
    individual_rewards: jnp.ndarray,
    state: GlobalState,
    next_state: GlobalState,
    config: CreditConfig,
    *,
    rng_key: jax.Array | None = None,
) -> jnp.ndarray:
    """Redistribute rewards with the selected individual, shared, or counterfactual scheme."""
    active = next_state.agents.active
    active_f = active.astype(jnp.float32)
    n_active = jnp.sum(active_f)
    safe_active = jnp.maximum(n_active, 1.0)

    if config.mode == CreditMode.INDIVIDUAL:
        return jnp.where(active, individual_rewards, 0.0)

    if config.mode == CreditMode.SHARED:
        total = jnp.sum(individual_rewards * active_f)
        shared = total / safe_active
        return jnp.where(active, shared, 0.0)

    if config.mode == CreditMode.COUNTERFACTUAL:
        adjusted = _counterfactual_credit(
            individual_rewards, active, config.counterfactual_baseline
        )
        return jnp.where(active, adjusted, 0.0)

    if config.mode == CreditMode.MEAN_FIELD:
        adjusted = _mean_field_credit(individual_rewards, active, config.mean_field_temperature)
        return jnp.where(active, adjusted, 0.0)

    if config.mode == CreditMode.SHAPLEY_APPROX:
        key = rng_key if rng_key is not None else jax.random.PRNGKey(0)
        adjusted = _shapley_approx_credit(individual_rewards, active, config.shapley_samples, key)
        return jnp.where(active, adjusted, 0.0)

    return jnp.where(active, individual_rewards, 0.0)


def _counterfactual_credit(
    rewards: jnp.ndarray,
    active: jnp.ndarray,
    baseline: str,
) -> jnp.ndarray:
    active_f = active.astype(jnp.float32)
    n_active = jnp.sum(active_f)
    safe_active = jnp.maximum(n_active, 1.0)
    total = jnp.sum(rewards * active_f)

    if baseline == "median":
        median = compute_quantiles_hard(rewards, active, 2)[0]
        return rewards - median

    others_mean = (total - rewards) / jnp.maximum(safe_active - 1.0, 1.0)
    return rewards - others_mean


def _mean_field_credit(
    rewards: jnp.ndarray,
    active: jnp.ndarray,
    temperature: float,
) -> jnp.ndarray:
    active_f = active.astype(jnp.float32)
    n_active = jnp.sum(active_f)
    safe_active = jnp.maximum(n_active, 1.0)
    mean_reward = jnp.sum(rewards * active_f) / safe_active
    std_reward = jnp.sqrt(jnp.sum((rewards - mean_reward) ** 2 * active_f) / safe_active)

    z_score = (rewards - mean_reward) / (std_reward + 1e-8)
    weight = jax.nn.sigmoid(z_score / temperature)
    return rewards * (0.5 + weight)


def _shapley_approx_credit(
    rewards: jnp.ndarray,
    active: jnp.ndarray,
    n_samples: int,
    rng_key: jax.Array,
) -> jnp.ndarray:
    n_agents = rewards.shape[0]
    active_f = active.astype(jnp.float32)

    def sample_marginal(key):
        perm = jax.random.permutation(key, n_agents)

        def compute_marginal(i, carry):
            cumsum, marginals = carry
            agent_idx = perm[i]
            marginal = rewards[agent_idx] * active_f[agent_idx]
            new_cumsum = cumsum + marginal
            marginals = marginals.at[agent_idx].add(marginal)
            return (new_cumsum, marginals), None

        (_, marginals), _ = jax.lax.scan(
            compute_marginal,
            (jnp.array(0.0), jnp.zeros((n_agents,), dtype=rewards.dtype)),
            jnp.arange(n_agents),
        )
        return marginals

    keys = jax.random.split(rng_key, int(n_samples))
    all_marginals = jax.vmap(sample_marginal)(keys)
    return jnp.mean(all_marginals, axis=0)


class CentralizedCritic:
    """Centralized critic public type."""

    @staticmethod
    def build_global_observations(state: GlobalState) -> jnp.ndarray:
        agents = state.agents
        active_f = agents.active.astype(jnp.float32)
        n_active = jnp.maximum(jnp.sum(active_f), 1.0)

        mean_wealth = jnp.sum(agents.wealth * active_f) / n_active
        std_wealth = jnp.sqrt(jnp.sum((agents.wealth - mean_wealth) ** 2 * active_f) / n_active)
        mean_income = jnp.sum(agents.income * active_f) / n_active
        mean_consumption = jnp.sum(agents.consumption * active_f) / n_active

        gini_wealth = state.distributions.gini_wealth
        gini_income = state.distributions.gini_income
        top_10_share = state.distributions.top_10_share
        bottom_50_share = state.distributions.bottom_50_share

        tax_rate = state.policy.tax_rate
        interest_rate = state.policy.interest_rate

        time_step = state.time_step.astype(jnp.float32)
        horizon = state.simulation_horizon.astype(jnp.float32)
        time_frac = time_step / jnp.maximum(horizon, 1.0)

        return jnp.array(
            [
                mean_wealth,
                std_wealth,
                mean_income,
                mean_consumption,
                gini_wealth,
                gini_income,
                top_10_share,
                bottom_50_share,
                tax_rate,
                interest_rate,
                time_frac,
                n_active,
            ],
            dtype=jnp.float32,
        )

    @staticmethod
    def build_agent_with_global(
        agent_obs: jnp.ndarray,
        global_obs: jnp.ndarray,
    ) -> jnp.ndarray:
        n_agents = agent_obs.shape[0]
        global_broadcast = jnp.broadcast_to(global_obs, (n_agents, global_obs.shape[0]))
        return jnp.concatenate([agent_obs, global_broadcast], axis=-1)
