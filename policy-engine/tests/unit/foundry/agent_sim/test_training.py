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

    def test_collect_trajectory_matches_reference_rollout(self, simple_state):
        key = jax.random.PRNGKey(0)
        obs = build_temporal_observations(simple_state, horizon=4, include_expectations=True)
        actor_critic = ActorCritic(key=key, obs_dim=obs.shape[-1], action_dim=1, hidden_dims=[8])
        executor = create_temporal_executor(actor_critic, horizon=4)
        config = TrainingConfig(steps_per_episode=3, horizon=4)

        trajectory = collect_trajectory(executor, simple_state, actor_critic, config)
        reference = _reference_collect_trajectory(executor, simple_state, actor_critic, config)

        assert jnp.allclose(trajectory.observations, reference.observations)
        assert jnp.allclose(trajectory.actions, reference.actions)
        assert jnp.allclose(trajectory.rewards, reference.rewards)
        assert jnp.allclose(trajectory.values, reference.values)
        assert jnp.allclose(trajectory.log_probs, reference.log_probs)
        assert jnp.array_equal(trajectory.dones, reference.dones)
        assert jnp.array_equal(trajectory.active_mask, reference.active_mask)
        assert jnp.allclose(trajectory.final_observation, reference.final_observation)


def _reference_collect_trajectory(executor, initial_state, actor_critic, config):
    mech = next(mech for mech in executor.mechanisms if mech.spec.name == "temporal_consumption")
    salt = executor.prng_config.get(mech.spec.name, 0)

    observations = []
    actions = []
    rewards = []
    values = []
    log_probs = []
    dones = []
    active_masks = []

    state = initial_state
    for _ in range(int(config.steps_per_episode)):
        obs = build_temporal_observations(
            state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )
        action_out, value = actor_critic(obs, deterministic=True)
        dist = actor_critic.get_action_distribution(obs, action_output=action_out)
        mech_key = get_mechanism_key(state.rng_key, state.time_step, salt)
        action = sample_actions(dist, mech_key, action_type=actor_critic.action_type)
        if actor_critic.action_type == "continuous" and action.ndim == 1:
            action = action[:, None]
        log_prob = compute_log_prob(action, dist, action_type=actor_critic.action_type)

        next_state, _ = executor.step(state, fidelity=config.fidelity)
        reward = compute_agent_reward(state, next_state, utility_type=config.utility_type)

        observations.append(obs)
        actions.append(action)
        rewards.append(reward)
        values.append(value)
        log_probs.append(log_prob)
        dones.append(jnp.zeros_like(state.agents.active, dtype=jnp.bool_))
        active_masks.append(state.agents.active)
        state = next_state

    final_obs = build_temporal_observations(
        state,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )

    from polisyos.foundry.agent_sim.rl import Trajectory

    return Trajectory(
        observations=jnp.stack(observations),
        actions=jnp.stack(actions),
        rewards=jnp.stack(rewards),
        values=jnp.stack(values),
        dones=jnp.stack(dones),
        log_probs=jnp.stack(log_probs),
        final_observation=final_obs,
        active_mask=jnp.stack(active_masks),
    )
