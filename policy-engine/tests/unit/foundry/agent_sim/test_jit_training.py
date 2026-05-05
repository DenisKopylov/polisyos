import jax
import jax.numpy as jnp
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.jit_training import (
    JITTrainingConfig,
    _resolve_temporal_salt,
    create_jit_trainer,
    create_jit_trainer_with_metrics,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_executor import create_temporal_executor


def _make_actor_and_state() -> tuple[ActorCritic, GlobalState]:
    state = GlobalState.empty(n_agents=4, simulation_horizon=8, max_agents=4, seed=0)
    observations = build_temporal_observations(
        state,
        horizon=8,
        include_expectations=True,
    )
    actor = ActorCritic(
        jax.random.PRNGKey(0),
        obs_dim=observations.shape[-1],
        action_dim=1,
    )
    return actor, state


def test_resolve_temporal_salt_reads_executor_prng_config() -> None:
    actor, _ = _make_actor_and_state()
    executor = create_temporal_executor(
        actor,
        horizon=8,
        prng_config={"temporal_consumption": 17},
    )

    assert _resolve_temporal_salt(executor) == 17


def test_create_jit_trainer_returns_finite_loss_history() -> None:
    actor, state = _make_actor_and_state()

    def make_executor(ac: ActorCritic):
        return create_temporal_executor(ac, horizon=8)

    trainer = create_jit_trainer(
        actor,
        make_executor,
        state,
        JITTrainingConfig(
            n_episodes=2,
            steps_per_episode=2,
            ppo_epochs=1,
            horizon=8,
        ),
    )
    trained_actor, metrics = trainer(jax.random.PRNGKey(1))

    assert isinstance(trained_actor, ActorCritic)
    assert metrics["loss_history"].shape == (2,)
    assert bool(jnp.all(jnp.isfinite(metrics["loss_history"])))
    assert bool(jnp.isfinite(metrics["final_loss"]))
    assert bool(jnp.isfinite(metrics["best_loss"]))


def test_create_jit_trainer_with_metrics_collects_scalar_histories() -> None:
    actor, state = _make_actor_and_state()

    def make_executor(ac: ActorCritic):
        return create_temporal_executor(ac, horizon=8)

    trainer = create_jit_trainer_with_metrics(
        actor,
        make_executor,
        state,
        JITTrainingConfig(
            n_episodes=2,
            steps_per_episode=2,
            ppo_epochs=1,
            horizon=8,
            metrics_frequency=1,
        ),
    )
    _, metrics, collector = trainer(jax.random.PRNGKey(2))

    assert metrics["loss_history"].shape == (2,)
    assert int(collector.step_counter) == 2
    assert collector.get_scalar_history("policy_loss").shape[0] == 2
    assert collector.get_scalar_history("mean_reward").shape[0] == 2
    assert bool(jnp.all(jnp.isfinite(collector.get_scalar_history("policy_loss"))))
