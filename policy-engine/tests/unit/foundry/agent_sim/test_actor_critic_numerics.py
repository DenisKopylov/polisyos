from __future__ import annotations

import equinox as eqx
import jax
import jax.numpy as jnp
from polisyos.foundry.agent_sim.actor_critic import (
    ActorCritic,
    compute_entropy,
    compute_log_prob,
)
from polisyos.foundry.agent_sim.rewards import compute_agent_reward
from polisyos.foundry.agent_sim.state import GlobalState


def test_actor_critic_distribution_math_stays_finite_for_extreme_log_std() -> None:
    actor = ActorCritic(
        key=jax.random.PRNGKey(0),
        obs_dim=3,
        action_dim=2,
        hidden_dims=(8,),
    )
    actor = eqx.tree_at(
        lambda model: model.action_log_std,
        actor,
        jnp.array([100.0, -100.0], dtype=jnp.float32),
    )

    obs = jnp.ones((4, 3), dtype=jnp.float32)
    dist = actor.get_action_distribution(obs)
    actions = dist["mean"]

    assert bool(jnp.all(jnp.isfinite(dist["std"])))
    assert bool(jnp.all(jnp.isfinite(compute_log_prob(actions, dist))))
    assert bool(jnp.all(jnp.isfinite(compute_entropy(dist))))


def test_cara_utility_handles_zero_risk_aversion_limit() -> None:
    state = GlobalState.empty(2)
    next_state = GlobalState.empty(2)
    next_state = eqx.tree_at(
        lambda s: (
            s.agents.active,
            s.agents.consumption,
            s.agents.risk_aversion,
            s.agents.wealth,
        ),
        next_state,
        (
            jnp.array([True, True]),
            jnp.array([2.0, 5.0], dtype=jnp.float32),
            jnp.array([0.0, 1e-9], dtype=jnp.float32),
            jnp.array([10.0, 10.0], dtype=jnp.float32),
        ),
    )

    reward = compute_agent_reward(state, next_state, utility_type="cara")
    assert bool(jnp.all(jnp.isfinite(reward)))


def test_compute_agent_reward_supports_zero_agent_states() -> None:
    state = GlobalState.empty(0)
    next_state = GlobalState.empty(0)

    reward = compute_agent_reward(state, next_state, utility_type="crra")
    assert reward.shape == (0,)
