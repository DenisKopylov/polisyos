from __future__ import annotations

import chex
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float, Int

from polisyos.foundry.agent_sim.state import GlobalState


@chex.dataclass(frozen=True)
class TemporalObservation:
    current_state: Float[Array, "n_agents state_dim"]
    time_step: Int[Array, ""]
    time_remaining: Int[Array, ""]
    discount_factor: Float[Array, "n_agents"]
    risk_aversion: Float[Array, "n_agents"]
    age: Int[Array, "n_agents"]
    expected_income_growth: Float[Array, "n_agents"]
    expected_interest_rate: Float[Array, ""]


def build_temporal_observations(
    state: GlobalState,
    horizon: int | None = None,
    *,
    include_expectations: bool = True,
    steps_per_year: int = 12,
) -> Float[Array, "n_agents temporal_obs_dim"]:
    agents = state.agents
    n_agents = agents.wealth.shape[0]
    if horizon is None:
        horizon_val = state.simulation_horizon.astype(jnp.float32)
    else:
        horizon_val = jnp.array(horizon, dtype=jnp.float32)
    horizon_val = jnp.maximum(horizon_val, 1.0)

    base_features = [
        agents.wealth,
        agents.income,
        agents.consumption,
        agents.risk_aversion,
        agents.discount_factor,
    ]
    if include_expectations:
        base_features.append(agents.expected_income_growth)
    base_stack = jnp.stack(base_features, axis=-1)

    time_step = state.time_step.astype(jnp.float32)
    time_remaining = (horizon_val - time_step).astype(jnp.float32)
    time_features = jnp.broadcast_to(
        jnp.array(
            [
                time_step / horizon_val,
                time_remaining / horizon_val,
                jnp.sin(2.0 * jnp.pi * time_step / 12.0),
                jnp.cos(2.0 * jnp.pi * time_step / 12.0),
            ],
            dtype=jnp.float32,
        ),
        (n_agents, 4),
    )

    age_years = agents.age.astype(jnp.float32) / float(steps_per_year)
    retirement_distance = jnp.maximum(65.0 - age_years, 0.0) / 65.0
    life_stage = age_years / 100.0
    age_features = jnp.stack([retirement_distance, life_stage], axis=-1)

    policy_features = [
        state.policy.tax_rate,
        state.policy.interest_rate,
        state.policy.transfer_rate,
    ]
    if include_expectations:
        policy_features.append(state.policy.expected_interest_rate)
    policy_stack = jnp.stack(policy_features, axis=0)
    policy_stack = jnp.broadcast_to(policy_stack, (n_agents, policy_stack.shape[0]))

    return jnp.concatenate([base_stack, time_features, age_features, policy_stack], axis=-1)


def build_temporal_mask(
    state: GlobalState,
    *,
    include_inactive: bool = False,
) -> Bool[Array, "n_agents"]:
    if include_inactive:
        return jnp.ones_like(state.agents.active, dtype=jnp.bool_)
    return state.agents.active
