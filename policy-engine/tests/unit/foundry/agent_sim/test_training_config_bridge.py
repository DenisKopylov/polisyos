from __future__ import annotations

from polisyos.foundry.agent_sim import JITTrainingConfig, TrainingConfig


def test_training_config_common_kwargs_bridge() -> None:
    config = TrainingConfig(
        n_episodes=7,
        steps_per_episode=5,
        horizon=18,
        learning_rate=1e-3,
        include_expectations=False,
    )
    jit_config = JITTrainingConfig(**config.common_kwargs())

    assert jit_config.n_episodes == config.n_episodes
    assert jit_config.steps_per_episode == config.steps_per_episode
    assert jit_config.horizon == config.horizon
    assert jit_config.learning_rate == config.learning_rate
    assert jit_config.include_expectations is config.include_expectations
