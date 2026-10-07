"""Real PPO scans and metric storage obey the declared numerical profile."""

from __future__ import annotations

import warnings

import equinox as eqx
import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.jit_training import (
    JITTrainingConfig,
    create_jit_trainer,
    create_jit_trainer_with_metrics,
)
from polisyos.foundry.agent_sim.metrics import MetricsBuffer
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_executor import create_temporal_executor


def _training_profile(model_profile, state_dtype):
    state = GlobalState.empty(n_agents=3, simulation_horizon=8)
    agents = state.agents.replace(
        wealth=jnp.asarray([1.0, 3.0, 5.0], dtype=state_dtype),
        income=jnp.ones(3, dtype=state_dtype),
        consumption=state.agents.consumption.astype(state_dtype),
        expected_lifetime_utility=state.agents.expected_lifetime_utility.astype(state_dtype),
    )
    state = state.replace(agents=agents)
    observations = build_temporal_observations(state, horizon=8, include_expectations=True)
    actor = ActorCritic(jax.random.PRNGKey(0), obs_dim=observations.shape[-1], hidden_dims=(8, 4))
    dtype = jnp.float64 if model_profile == "float64" else jnp.float32
    actor = jax.tree_util.tree_map(
        lambda leaf: leaf.astype(dtype) if eqx.is_inexact_array(leaf) else leaf, actor
    )
    if model_profile == "mixed":
        # A wider participating critic head makes the actual PPO value loss
        # float64 while the actor/trunk and their gradients remain float32.
        actor = eqx.tree_at(
            lambda model: model.critic_out,
            actor,
            replace_fn=lambda head: jax.tree_util.tree_map(
                lambda leaf: leaf.astype(jnp.float64) if eqx.is_inexact_array(leaf) else leaf,
                head,
            ),
        )
    return actor, state


@pytest.mark.parametrize(
    "model_profile,state_dtype,x64",
    [("float32", jnp.float32, False)]
    + [
        (model, dtype, True)
        for model in ["float32", "float64", "mixed"]
        for dtype in [jnp.float32, jnp.float64]
    ],
)
@pytest.mark.parametrize("with_metrics", [False, True], ids=["plain", "metrics"])
def test_real_plain_and_metric_trainer_promotes_loss_carry_and_preserves_parameters(
    model_profile, state_dtype, x64, with_metrics
):
    with jax.enable_x64(x64):
        actor, state = _training_profile(model_profile, state_dtype)
        factory = create_jit_trainer_with_metrics if with_metrics else create_jit_trainer
        trainer = factory(
            actor,
            lambda model: create_temporal_executor(model, horizon=8),
            state,
            JITTrainingConfig(n_episodes=2, steps_per_episode=2, ppo_epochs=1, horizon=8),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            result = trainer(jax.random.PRNGKey(19))
        trained, metrics = result[:2]
        # Existing continuous-action draws use JAX's default random dtype.
        # Thus even a float32 model/state has a float64 PPO result with x64 on.
        expected_dtype = jnp.float64 if x64 else jnp.float32
        for name in ["loss_history", "best_loss", "final_loss"]:
            assert metrics[name].dtype == expected_dtype
            assert np.isfinite(np.asarray(metrics[name])).all()
        assert metrics["loss_history"].shape == (2,)
        before = [x for x in jax.tree_util.tree_leaves(actor) if eqx.is_inexact_array(x)]
        after = [x for x in jax.tree_util.tree_leaves(trained) if eqx.is_inexact_array(x)]
        assert [x.dtype for x in after] == [x.dtype for x in before]
        assert any(not np.array_equal(x, y) for x, y in zip(before, after, strict=True))
        assert all(np.isfinite(np.asarray(x)).all() for x in after)
        if with_metrics:
            collector = result[2]
            assert int(collector.step_counter) == 2
            for name in ["policy_loss", "value_loss", "mean_reward", "gini_wealth"]:
                history = collector.get_scalar_history(name)
                assert history.dtype == jnp.float32
                assert history.shape == (2,) and np.isfinite(np.asarray(history)).all()
            for value in collector.buffer.histograms.values():
                assert value.dtype == jnp.float32 and np.isfinite(np.asarray(value)).all()


@pytest.mark.parametrize("destination_dtype", [jnp.float32, jnp.float64])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_metric_scalar_storage_explicitly_encodes_destination_dtype(destination_dtype, compiled):
    with jax.enable_x64(True):
        buffer = MetricsBuffer.create(["metric", "untouched"], [], max_size=3)
        buffer = buffer.replace(
            scalars={
                name: value.astype(destination_dtype) for name, value in buffer.scalars.items()
            }
        )
        value = jnp.asarray(1.0 + 2**-30, dtype=jnp.float64)
        write = lambda current: current.write_scalar_at("metric", value, jnp.asarray(1))
        if compiled:
            write = jax.jit(write)
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            updated = write(buffer)
        assert updated.scalars["metric"].dtype == destination_dtype
        assert updated.scalars["metric"][1] == value.astype(destination_dtype)
        np.testing.assert_array_equal(updated.scalars["untouched"], buffer.scalars["untouched"])
        assert int(updated.write_idx) == int(buffer.write_idx)


@pytest.mark.parametrize("destination_dtype", [jnp.float32, jnp.float64])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_metric_histogram_storage_encodes_fixed_dtype_after_finite_sample_equation(
    destination_dtype, compiled
):
    with jax.enable_x64(True):
        buffer = MetricsBuffer.create([], ["metric", "untouched"], max_size=3, n_bins=3)
        buffer = buffer.replace(
            histograms={
                name: value.astype(destination_dtype) for name, value in buffer.histograms.items()
            }
        )
        values = jnp.asarray([0.2, 1.8, 2.7, jnp.nan], dtype=jnp.float64)
        bins = jnp.asarray([0.0, 1.0, 2.0, 3.0], dtype=jnp.float64)
        write = lambda current: current.write_histogram_at("metric", values, bins, jnp.asarray(1))
        if compiled:
            write = jax.jit(write)
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            updated = write(buffer)
        expected = np.asarray([1 / 3, 1 / 3, 1 / 3], dtype=np.dtype(destination_dtype))
        assert updated.histograms["metric"].dtype == destination_dtype
        np.testing.assert_array_equal(updated.histograms["metric"][1], expected)
        np.testing.assert_array_equal(
            updated.histograms["untouched"], buffer.histograms["untouched"]
        )
        assert int(updated.write_idx) == int(buffer.write_idx)
