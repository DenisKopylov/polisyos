"""Tests for agent_sim training configuration."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim import (
    ActorCritic,
    build_temporal_observations,
    create_temporal_executor,
)
from polisyos.foundry.agent_sim.actor_critic import compute_log_prob, sample_actions
from polisyos.foundry.agent_sim.prng import get_mechanism_key
from polisyos.foundry.agent_sim.rewards import compute_agent_reward
from polisyos.foundry.agent_sim.training import (
    TrainingConfig,
    collect_trajectory,
    train_actor_critic,
)


class TestTrainingConfig:
    def test_default_config(self):
        cfg = TrainingConfig()
        assert cfg.log_interval == 10
        assert hasattr(cfg, "learning_rate")
        assert hasattr(cfg, "gamma")

    def test_custom_log_interval(self):
        cfg = TrainingConfig(log_interval=5)
        assert cfg.log_interval == 5


class TestTrainActorCritic:
    def test_requires_executor_or_make_executor(self):
        """Should raise when neither executor nor make_executor provided."""
        key = jax.random.PRNGKey(42)
        ac = ActorCritic(obs_dim=5, action_dim=1, hidden_dims=[8], key=key)
        with pytest.raises(ValueError, match="executor"):
            train_actor_critic(ac, None, TrainingConfig())

    def test_collect_trajectory_matches_reference_rollout(self, simple_state, record_property):
        key = jax.random.PRNGKey(0)
        obs = build_temporal_observations(simple_state, horizon=4, include_expectations=True)
        actor_critic = ActorCritic(key=key, obs_dim=obs.shape[-1], action_dim=1, hidden_dims=[8])
        executor = create_temporal_executor(actor_critic, horizon=4)
        config = TrainingConfig(steps_per_episode=3, horizon=4)

        trajectory = collect_trajectory(executor, simple_state, actor_critic, config)
        # Compare within the same compiled numerical profile: producer-owned
        # decisions are evaluated inside lax.scan, not as an eager resample.
        reference = jax.jit(
            lambda state: _reference_collect_trajectory(executor, state, actor_critic, config)
        )(simple_state)

        assert jnp.allclose(trajectory.observations, reference.observations)
        assert trajectory.actions.shape == reference.actions.shape
        # The action is now captured inside the actual transition, rather than
        # resampled in a separate compiled context. Bound float32 rounding at
        # the declared native action-law precision, not near-zero relative error.
        action_error = float(jnp.max(jnp.abs(trajectory.actions - reference.actions)))
        record_property("action_max_absolute_error", action_error)
        assert action_error <= 1e-6
        assert jnp.allclose(trajectory.actions, reference.actions, rtol=1e-6, atol=1e-6)
        assert jnp.allclose(trajectory.rewards, reference.rewards)
        assert jnp.allclose(trajectory.values, reference.values)
        assert jnp.allclose(trajectory.log_probs, reference.log_probs)
        assert jnp.array_equal(trajectory.dones, reference.dones)
        assert jnp.array_equal(trajectory.active_mask, reference.active_mask)
        assert jnp.allclose(trajectory.final_observation, reference.final_observation)


def _reference_collect_trajectory(executor, initial_state, actor_critic, config):
    mech = next(mech for mech in executor.mechanisms if mech.spec.name == "temporal_consumption")
    salt = executor.prng_config.get(mech.spec.name, 0)

    def reference_step(state, _):
        obs = build_temporal_observations(
            state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )
        obs = jnp.where(state.agents.active[:, None], obs, 0.0)
        action_out, value = actor_critic(obs, deterministic=True)
        dist = actor_critic.get_action_distribution(obs, action_output=action_out)
        mech_key = get_mechanism_key(state.rng_key, state.time_step, salt)
        action = sample_actions(dist, mech_key, action_type=actor_critic.action_type)
        if actor_critic.action_type == "continuous" and action.ndim == 1:
            action = action[:, None]
        log_prob = compute_log_prob(action, dist, action_type=actor_critic.action_type)
        next_state, _ = executor.step(state, fidelity=config.fidelity)
        reward = compute_agent_reward(state, next_state, utility_type=config.utility_type)
        return next_state, (obs, action, reward, value, log_prob, state.agents.active)

    state, fields = jax.lax.scan(
        reference_step, initial_state, None, length=config.steps_per_episode
    )
    observations, actions, rewards, values, log_probs, active_masks = fields
    final_obs = build_temporal_observations(
        state,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )
    final_obs = jnp.where(state.agents.active[:, None], final_obs, 0.0)

    from polisyos.foundry.agent_sim.rl import Trajectory

    return Trajectory(
        observations=observations,
        actions=actions,
        rewards=rewards,
        values=values,
        dones=jnp.zeros_like(active_masks, dtype=jnp.bool_),
        log_probs=log_probs,
        final_observation=final_obs,
        active_mask=active_masks,
    )
