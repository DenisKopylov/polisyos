"""Convert simulation state transitions into per-agent rewards and discounted returns."""

from __future__ import annotations

import jax
import jax.numpy as jnp

from polisyos.foundry._numeric import NumericDomain, epsilon_for
from polisyos.foundry.agent_sim.credit_assignment import (
    CreditConfig,
    compute_credit_assignment,
)
from polisyos.foundry.agent_sim.state import GlobalState


class UtilityFunction:
    """Utility function public type."""

    @staticmethod
    def crra(consumption: jnp.ndarray, risk_aversion: jnp.ndarray) -> jnp.ndarray:
        gamma = risk_aversion
        eps = epsilon_for(NumericDomain.UTILITY)
        safe_c = jnp.maximum(consumption, eps)
        is_log = jnp.abs(gamma - 1.0) < eps
        power_term = (jnp.power(safe_c, 1.0 - gamma) - 1.0) / (1.0 - gamma)
        return jnp.where(is_log, jnp.log(safe_c), power_term)

    @staticmethod
    def cara(consumption: jnp.ndarray, risk_aversion: jnp.ndarray) -> jnp.ndarray:
        gamma = risk_aversion
        eps = epsilon_for(NumericDomain.UTILITY)
        near_zero = jnp.abs(gamma) < eps
        safe_gamma = jnp.where(near_zero, 1.0, gamma)
        shifted = -jnp.expm1(-gamma * consumption) / safe_gamma
        return jnp.where(near_zero, consumption, shifted)

    @staticmethod
    def epstein_zin(
        consumption: jnp.ndarray,
        continuation_value: jnp.ndarray,
        risk_aversion: jnp.ndarray,
        ies: jnp.ndarray,
        discount_factor: jnp.ndarray,
    ) -> jnp.ndarray:
        gamma = risk_aversion
        eps = epsilon_for(NumericDomain.UTILITY)
        psi = jnp.where(jnp.abs(ies - 1.0) < eps, 1.0 + eps, ies)
        beta = discount_factor
        theta = (1.0 - gamma) / (1.0 - 1.0 / psi)
        safe_c = jnp.maximum(consumption, eps)
        consumption_term = (1.0 - beta) * jnp.power(safe_c, 1.0 - 1.0 / psi)
        continuation_term = beta * jnp.power(jnp.maximum(continuation_value, eps), theta)
        return jnp.power(consumption_term + continuation_term, 1.0 / (1.0 - 1.0 / psi))


def compute_agent_reward(
    state: GlobalState,
    next_state: GlobalState,
    *,
    utility_type: str = "crra",
    ies: float | jnp.ndarray | None = None,
) -> jnp.ndarray:
    """Compute per-agent utility-adjusted rewards from the transition between two states."""
    agents = next_state.agents

    if utility_type == "crra":
        utility = UtilityFunction.crra(agents.consumption, agents.risk_aversion)
    elif utility_type == "cara":
        utility = UtilityFunction.cara(agents.consumption, agents.risk_aversion)
    elif utility_type == "epstein_zin":
        if ies is None:
            ies_val = jnp.ones_like(agents.risk_aversion)
        else:
            ies_val = jnp.asarray(ies, dtype=jnp.float32)
            if ies_val.shape == ():
                ies_val = jnp.full_like(agents.risk_aversion, ies_val)
        utility = UtilityFunction.epstein_zin(
            agents.consumption,
            agents.expected_lifetime_utility,
            agents.risk_aversion,
            ies_val,
            agents.discount_factor,
        )
    else:
        raise ValueError(f"Unknown utility type: {utility_type}")

    wealth_bonus = 0.01 * jnp.log(jnp.maximum(agents.wealth, 1.0))
    bankruptcy_penalty = -10.0 * (agents.wealth < 0.1).astype(jnp.float32)
    reward = utility + wealth_bonus + bankruptcy_penalty + agents.utility_adjustment
    return jnp.where(agents.active, reward, 0.0)


def apply_discounting(
    rewards: jnp.ndarray,
    discount_factors: jnp.ndarray,
    active_mask: jnp.ndarray,
) -> jnp.ndarray:
    """Roll rewards backward with per-agent discount factors and active masks."""

    def discount_step(carry, t):
        cumulative = carry
        reward_t = rewards[t]
        active_t = active_mask[t]
        new_cumulative = reward_t + discount_factors * cumulative * active_t
        return new_cumulative, None

    final, _ = jax.lax.scan(
        discount_step,
        jnp.zeros_like(discount_factors),
        jnp.arange(rewards.shape[0] - 1, -1, -1),
    )
    return final


def compute_agent_reward_with_credit(
    state: GlobalState,
    next_state: GlobalState,
    credit_config: CreditConfig,
    *,
    utility_type: str = "crra",
    ies: float | jnp.ndarray | None = None,
    rng_key: jax.Array | None = None,
) -> jnp.ndarray:
    """Compute base rewards and then reallocate them with the chosen credit scheme."""
    individual_rewards = compute_agent_reward(
        state,
        next_state,
        utility_type=utility_type,
        ies=ies,
    )
    return compute_credit_assignment(
        individual_rewards,
        state,
        next_state,
        credit_config,
        rng_key=rng_key,
    )
