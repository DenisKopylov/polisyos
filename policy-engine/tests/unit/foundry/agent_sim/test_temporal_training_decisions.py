"""Qualify PPO trajectories against the decision actually applied by an executor."""

from __future__ import annotations

import math
from types import SimpleNamespace

import equinox as eqx
import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim import jit_training, temporal_mechanisms, training
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_mechanisms import (
    TemporalConsumptionMechanism,
    _capture_temporal_decisions,
    _UnsupportedPolicyExecutorError,
)
from polisyos.foundry.contracts.fidelity import FidelityLevel


class _Prefix(Mechanism):
    def __init__(self, change: str) -> None:
        self.change = change

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            "prefix", frozenset(), frozenset({"agents.income", "agents.active"}), {}, False
        )

    def apply(self, state, rng_key, fidelity):
        agents = state.agents
        if self.change == "income":
            agents = agents.replace(
                income=agents.income + jnp.asarray([20.0, 30.0], dtype=agents.income.dtype)
            )
        else:
            agents = agents.replace(active=jnp.asarray([False, state.time_step < 4]))
        return state.replace(agents=agents), {}


def _profile() -> tuple[ActorCritic, GlobalState]:
    state = GlobalState.empty(n_agents=2, max_agents=2, simulation_horizon=8, seed=29)
    state = state.replace(
        time_step=jnp.asarray(3, dtype=state.time_step.dtype),
        agents=state.agents.replace(
            wealth=jnp.full_like(state.agents.wealth, 100.0),
            income=jnp.full_like(state.agents.income, 10.0),
        ),
    )
    actor = ActorCritic(jax.random.PRNGKey(7), obs_dim=16, hidden_dims=(2,), action_dim=1)
    actor = jax.tree_util.tree_map(
        lambda leaf: jnp.zeros_like(leaf, dtype=jnp.float32)
        if eqx.is_inexact_array(leaf)
        else leaf,
        actor,
    )
    return actor, state


def _assert_same_tree(first, second) -> None:
    first_leaves, first_tree = jax.tree_util.tree_flatten(first)
    second_leaves, second_tree = jax.tree_util.tree_flatten(second)
    assert first_tree == second_tree
    for left, right in zip(first_leaves, second_leaves, strict=True):
        assert bool(jnp.array_equal(left, right))


@pytest.mark.parametrize("with_metrics", [False, True], ids=["plain", "metrics"])
@pytest.mark.parametrize(
    "fidelity", [FidelityLevel.SURROGATE_FLUID, FidelityLevel.RELAXED_DISCRETE]
)
@pytest.mark.parametrize("change", ["income", "active"])
@pytest.mark.parametrize("explicit_salt", [False, True], ids=["partial-map", "explicit-salt"])
def test_native_collectors_use_executed_prefix_decision_and_mechanism_key(
    monkeypatch, with_metrics: bool, fidelity: FidelityLevel, change: str, explicit_salt: bool
) -> None:
    """Observe the real PPO input while delegating its loss and native optimizer."""
    actor, state = _profile()
    prefix = _Prefix(change)
    mapping = {"prefix": 19}
    if explicit_salt:
        mapping["temporal_consumption"] = 47

    def make_executor(model):
        return PureExecutor(
            [prefix, TemporalConsumptionMechanism(model, horizon=8)], prng_config=mapping
        )

    source = make_executor(actor)
    captured = _capture_temporal_decisions(source)
    ordinary_state, ordinary_metrics = source.step(state, fidelity)
    captured_state, captured_metrics = captured.step(state, fidelity)
    assert captured is not source
    assert captured.mechanisms[1] is not source.mechanisms[1]
    assert not source.mechanisms[1]._capture_policy_decision
    assert captured.mechanisms[1]._capture_policy_decision
    assert source.prng_config == mapping
    assert set(ordinary_metrics) == {
        "temporal_consumption/mean_consumption",
        "temporal_consumption/mean_value",
        "temporal_consumption/mean_consumption_fraction",
    }
    assert all(value.shape == () for value in ordinary_metrics.values())
    assert len(captured_metrics) == len(ordinary_metrics) + 6
    assert bool(captured_metrics["temporal_consumption/policy_decision_sampled_law"])
    _assert_same_tree(ordinary_state, captured_state)
    _assert_same_tree(ordinary_metrics, {key: captured_metrics[key] for key in ordinary_metrics})

    observed = []
    native_loss = jit_training.ppo_loss

    def observing_loss(model, trajectory, *args, **kwargs):
        jax.debug.callback(
            lambda *fields: observed.append(tuple(field.copy() for field in fields)),
            trajectory.observations,
            trajectory.actions,
            trajectory.log_probs,
            trajectory.values,
            trajectory.active_mask,
            trajectory.final_observation,
            trajectory.dones,
        )
        return native_loss(model, trajectory, *args, **kwargs)

    monkeypatch.setattr(jit_training, "ppo_loss", observing_loss)
    factory = (
        jit_training.create_jit_trainer_with_metrics
        if with_metrics
        else jit_training.create_jit_trainer
    )
    trainer = factory(
        actor,
        make_executor,
        state,
        jit_training.JITTrainingConfig(
            n_episodes=1, steps_per_episode=1, ppo_epochs=1, horizon=13, fidelity=fidelity
        ),
    )
    result = trainer(jax.random.PRNGKey(101))
    jax.block_until_ready(result)
    assert bool(jnp.isfinite(result[1]["final_loss"]))
    assert len(observed) == 1
    observations, actions, log_probs, values, active, final_observation, dones = observed[0]
    after_prefix, _ = prefix.apply(state, None, fidelity)
    expected_active = after_prefix.agents.active
    expected_observations = build_temporal_observations(after_prefix, horizon=8)
    expected_observations = jnp.where(expected_active[:, None], expected_observations, 0.0)
    salt = 47 if explicit_salt else 1
    expected_key = jax.random.fold_in(jax.random.fold_in(state.rng_key, state.time_step), salt)
    expected_actions = jax.random.normal(expected_key, shape=(2, 1))
    expected_log_probs = [
        -0.5 * (float(action) ** 2 + math.log(2.0 * math.pi)) for action in expected_actions[:, 0]
    ]
    assert bool(jnp.allclose(observations[0], expected_observations, rtol=1e-6, atol=1e-6))
    assert bool(jnp.array_equal(active[0], expected_active))
    assert bool(jnp.allclose(actions[0], expected_actions, rtol=1e-6, atol=1e-6))
    assert list(log_probs[0]) == pytest.approx(expected_log_probs, rel=1e-6, abs=1e-6)
    assert bool(jnp.array_equal(values, jnp.zeros((1, 2), dtype=jnp.float32)))
    expected_consumption = jnp.asarray(
        [
            (100.0 + float(income)) / (1.0 + math.exp(-float(action))) if enabled else 0.0
            for income, action, enabled in zip(
                after_prefix.agents.income, expected_actions[:, 0], expected_active, strict=True
            )
        ]
    )
    assert bool(
        jnp.allclose(captured_state.agents.consumption, expected_consumption, rtol=1e-6, atol=1e-6)
    )
    bootstrap_state, _ = prefix.apply(captured_state, None, fidelity)
    future_active = bootstrap_state.agents.active
    expected_final = build_temporal_observations(bootstrap_state, horizon=8)
    expected_final = jnp.where(future_active[:, None], expected_final, 0.0)
    expected_dones = expected_active & ~future_active
    assert bool(jnp.allclose(final_observation, expected_final, rtol=1e-6, atol=1e-6))
    assert bool(jnp.array_equal(dones[0], expected_dones))
    if (
        not with_metrics
        and change == "income"
        and not explicit_salt
        and fidelity == FidelityLevel.SURROGATE_FLUID
    ):
        legacy = training.collect_trajectory(
            source,
            state,
            actor,
            training.TrainingConfig(steps_per_episode=1, horizon=13, fidelity=fidelity),
        )
        assert bool(jnp.allclose(legacy.observations[0], expected_observations))
        assert bool(jnp.allclose(legacy.actions[0], expected_actions))
        assert bool(jnp.allclose(legacy.final_observation, expected_final))
        assert bool(jnp.array_equal(legacy.dones[0], expected_dones))
    assert not source.mechanisms[1]._capture_policy_decision


def test_ordinary_hard_mean_and_controlled_fluid_noise_keep_their_execution_laws(monkeypatch):
    actor, state = _profile()
    mechanism = TemporalConsumptionMechanism(actor, horizon=8)
    hard, metrics = mechanism.apply(state, state.rng_key, FidelityLevel.HARD_DISCRETE)
    assert list(hard.agents.consumption) == pytest.approx([55.0, 55.0])
    assert set(metrics) == {"mean_consumption", "mean_value", "mean_consumption_fraction"}
    monkeypatch.setattr(
        temporal_mechanisms,
        "sample_actions",
        lambda distribution, key, **kwargs: jnp.full_like(distribution["mean"], 2.0),
    )
    fluid, _ = mechanism.apply(state, state.rng_key, FidelityLevel.SURROGATE_FLUID)
    expected = 110.0 / (1.0 + math.exp(-2.0))
    assert expected == pytest.approx(96.8876786, rel=1e-8)
    assert list(fluid.agents.consumption) == pytest.approx([expected, expected], rel=1e-6)


@pytest.mark.parametrize("entry", ["plain", "metrics", "legacy", "artifact"])
@pytest.mark.parametrize("consumer_count", [0, 2], ids=["missing", "ambiguous"])
def test_training_without_temporal_consumer_refuses_before_optimizer_or_publication(
    monkeypatch, entry: str, consumer_count: int
) -> None:
    actor, state = _profile()
    executor = PureExecutor([_Prefix("income")])
    ordinary, _ = executor.step(state)
    assert list(ordinary.agents.income) == [30.0, 40.0]
    # Two identically named temporal writers cannot be topologically ordered.
    # Exercise malformed caller input directly; admission must refuse it before
    # looking at the stale execution order or constructing an optimizer.
    executor.mechanisms.extend(
        TemporalConsumptionMechanism(actor, horizon=8) for _ in range(consumer_count)
    )

    def forbidden(*args, **kwargs):
        pytest.fail("unsupported executor reached optimizer, artifact, fingerprint, or store")

    monkeypatch.setattr(jit_training.optax, "chain", forbidden)
    monkeypatch.setattr(training.EnvironmentFingerprint, "capture", forbidden)
    monkeypatch.setattr(training.AgentPolicyArtifact, "from_trained_policy", forbidden)
    config = training.TrainingConfig(n_episodes=1, steps_per_episode=1, ppo_epochs=1, horizon=8)

    def invoke():
        if entry in ("plain", "metrics"):
            factory = (
                jit_training.create_jit_trainer_with_metrics
                if entry == "metrics"
                else jit_training.create_jit_trainer
            )
            factory(actor, lambda model: executor, state, jit_training.JITTrainingConfig())
        elif entry == "legacy":
            training.train_actor_critic(actor, state, config, executor=executor)
        else:
            training.train_actor_critic_with_artifact(
                actor,
                state,
                config,
                make_executor=lambda model: executor,
                run_id="unsupported-no-temporal",
                cas=SimpleNamespace(put=forbidden),
            )

    with pytest.raises(_UnsupportedPolicyExecutorError) as refused:
        invoke()
    assert refused.value.code == "training_policy_executor_unsupported"
