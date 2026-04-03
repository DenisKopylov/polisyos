"""Public agent sim mpc module API."""
from __future__ import annotations

from dataclasses import dataclass

import chex
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.rewards import compute_agent_reward
from polisyos.foundry.agent_sim.temporal import build_temporal_observations


@dataclass(frozen=True)
class MPCPlanner:
    """MPC planner public type."""
    simulator: PureExecutor
    horizon: int = 8
    n_samples: int = 32
    discount_factor: float = 0.99
    utility_type: str = "crra"

    def plan(
        self,
        state,
        agent_idx: int,
        action_candidates: jnp.ndarray,
        rng_key: chex.PRNGKey,
    ) -> int:
        n_candidates = action_candidates.shape[0]
        keys = jax.random.split(rng_key, n_candidates)
        rewards = jax.vmap(self._evaluate_action, in_axes=(0, 0, None, None))(
            action_candidates, keys, state, agent_idx
        )
        return int(jnp.argmax(rewards))

    def _evaluate_action(
        self,
        action: jnp.ndarray,
        rng_key: chex.PRNGKey,
        state,
        agent_idx: int,
    ) -> jnp.ndarray:
        modified_state = self._apply_action(state, agent_idx, action)

        sample_keys = jax.random.split(rng_key, int(self.n_samples))

        def rollout_once(sample_key):
            def rollout_step(carry, t):
                cur_state = carry
                next_state, _ = self.simulator.step(cur_state)
                reward = compute_agent_reward(
                    cur_state, next_state, utility_type=self.utility_type
                )
                discounted = (self.discount_factor**t) * reward[agent_idx]
                return next_state, discounted

            seeded_state = modified_state.replace(rng_key=sample_key)
            _, rewards = jax.lax.scan(
                rollout_step,
                seeded_state,
                jnp.arange(int(self.horizon)),
            )
            return jnp.sum(rewards)

        return jnp.mean(jax.vmap(rollout_once)(sample_keys))

    def _apply_action(self, state, agent_idx: int, action: jnp.ndarray):
        active = state.agents.active[agent_idx]
        fraction = jax.nn.sigmoid(action[0]) if action.ndim > 0 else jax.nn.sigmoid(action)
        budget = state.agents.wealth[agent_idx] + state.agents.income[agent_idx]
        new_consumption = fraction * budget
        new_wealth = jnp.maximum(budget - new_consumption, 0.0)

        def _apply(_):
            consumption = state.agents.consumption.at[agent_idx].set(new_consumption)
            wealth = state.agents.wealth.at[agent_idx].set(new_wealth)
            new_agents = state.agents.replace(consumption=consumption, wealth=wealth)
            return state.replace(agents=new_agents)

        return jax.lax.cond(active, _apply, lambda _: state, operand=None)


@dataclass(frozen=True)
class HybridPlanner:
    """Hybrid planner public type."""
    actor_critic: ActorCritic
    mpc_planner: MPCPlanner
    mpc_threshold: float = 0.1

    def get_action(self, state, agent_idx: int, rng_key: chex.PRNGKey) -> jnp.ndarray:
        obs = build_temporal_observations(state, horizon=self.mpc_planner.horizon)
        action_out, _ = self.actor_critic(obs[agent_idx : agent_idx + 1], deterministic=True)
        uncertainty = self._estimate_uncertainty(state, agent_idx)
        if uncertainty > self.mpc_threshold:
            key1, key2 = jax.random.split(rng_key)
            candidates = action_out + 0.1 * jax.random.normal(
                key1, shape=(32, action_out.shape[-1])
            )
            best_idx = self.mpc_planner.plan(state, agent_idx, candidates, key2)
            return candidates[best_idx]
        return action_out.squeeze(0)

    def _estimate_uncertainty(self, state, agent_idx: int) -> float:
        del state, agent_idx
        return 0.0
