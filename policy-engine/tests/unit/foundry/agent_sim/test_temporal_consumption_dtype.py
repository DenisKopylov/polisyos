"""Temporal neural transitions preserve state-carry encoding, equations and keys."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.actor_critic import ActorCritic, sample_actions
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism
from polisyos.foundry.contracts.fidelity import FidelityLevel


def _profile(dtype):
    state = GlobalState.empty(n_agents=4, simulation_horizon=12)
    state = state.replace(
        agents=state.agents.replace(
            wealth=jnp.asarray([1.0, 3.0, 2.0, 7.0], dtype=dtype),
            income=jnp.ones(4, dtype=jnp.float32),
            consumption=state.agents.consumption.astype(dtype),
            expected_lifetime_utility=state.agents.expected_lifetime_utility.astype(dtype),
        )
    )
    obs = build_temporal_observations(state, horizon=12, include_expectations=True)
    actor = ActorCritic(jax.random.PRNGKey(0), obs_dim=obs.shape[-1], action_dim=1)
    assert actor(obs, deterministic=True)[0].dtype == jnp.float64
    return state, actor


@pytest.mark.parametrize("dtype", [jnp.float32, jnp.float64])
@pytest.mark.parametrize("fidelity", [FidelityLevel.SURROGATE_FLUID, FidelityLevel.HARD_DISCRETE])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_real_actor64_transition_matches_equation_and_input_field_dtype(dtype, fidelity, compiled):
    with jax.enable_x64(True):
        before, actor = _profile(dtype)
        mechanism = TemporalConsumptionMechanism(actor, horizon=12)
        key = jax.random.PRNGKey(19)
        obs = build_temporal_observations(before, horizon=12, include_expectations=True)
        action, values = actor(obs, deterministic=True)
        if fidelity == FidelityLevel.HARD_DISCRETE:
            draw = action
        else:
            draw = sample_actions(
                actor.get_action_distribution(obs, action_output=action),
                key,
                action_type=actor.action_type,
            )
        fraction = jax.nn.sigmoid(draw[:, 0])
        budget = before.agents.wealth + before.agents.income
        consumption = jnp.maximum(fraction * budget, mechanism.min_consumption)
        wealth = jnp.maximum(budget - consumption, 0)
        evaluate = lambda s, k: mechanism.apply(s, k, fidelity)
        if compiled:
            evaluate = jax.jit(evaluate)
        after, _ = evaluate(before, key)
        for name, expected in [
            ("consumption", consumption),
            ("wealth", wealth),
            ("expected_lifetime_utility", values),
        ]:
            original = getattr(before.agents, name)
            actual = getattr(after.agents, name)
            assert actual.dtype == original.dtype == dtype
            # The independent eager equation and fused JIT graph may differ
            # by ordinary rounding. Use four dtype epsilons for relative and
            # absolute error, including value-network outputs near zero.
            np.testing.assert_allclose(
                actual,
                expected.astype(dtype),
                rtol=4 * np.finfo(np.dtype(dtype)).eps,
                atol=4 * np.finfo(np.dtype(dtype)).eps,
            )
        np.testing.assert_array_equal(after.rng_key, before.rng_key)
        repeated, _ = evaluate(before, key)
        np.testing.assert_array_equal(repeated.agents.wealth, after.agents.wealth)
        if fidelity == FidelityLevel.SURROGATE_FLUID:
            changed, _ = evaluate(before, jax.random.PRNGKey(20))
            assert not np.array_equal(changed.agents.wealth, after.agents.wealth)


@pytest.mark.parametrize("dtype", [jnp.float32, jnp.float64])
def test_native_executor_scan_and_gradient_keep_state_profile_with_actor64(dtype):
    with jax.enable_x64(True):
        before, actor = _profile(dtype)
        executor = PureExecutor([TemporalConsumptionMechanism(actor, horizon=12)])
        after, _ = executor.run(before, 3)
        assert int(after.time_step) == 3
        for name in ["wealth", "consumption", "expected_lifetime_utility"]:
            assert getattr(after.agents, name).dtype == dtype
        gradient = jax.grad(
            lambda wealth: jnp.sum(
                executor.run(before.replace(agents=before.agents.replace(wealth=wealth)), 2)[
                    0
                ].agents.wealth
            )
        )(before.agents.wealth)
        assert gradient.dtype == dtype and np.isfinite(np.asarray(gradient)).all()
        assert np.any(np.asarray(gradient) != 0)
