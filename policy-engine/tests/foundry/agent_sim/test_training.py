"""Tests for agent_sim training configuration."""
from __future__ import annotations

import pytest

from polisyos.foundry.agent_sim.training import TrainingConfig, train_actor_critic


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
        import jax
        from polisyos.foundry.agent_sim.actor_critic import ActorCritic

        key = jax.random.PRNGKey(42)
        ac = ActorCritic(obs_dim=5, action_dim=1, hidden_dims=[8], key=key)
        with pytest.raises(ValueError, match="executor"):
            train_actor_critic(ac, None, TrainingConfig())
