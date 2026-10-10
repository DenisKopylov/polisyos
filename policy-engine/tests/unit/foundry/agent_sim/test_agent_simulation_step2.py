import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim import (
    ActorCritic,
    GlobalState,
    TemporalConsumptionMechanism,
    TrainingConfig,
    build_temporal_observations,
    compute_returns_and_advantages,
    create_temporal_executor,
    sample_actions,
    train_actor_critic,
)
from polisyos.foundry.agent_sim.rl import Trajectory
from polisyos.foundry.contracts.fidelity import FidelityLevel


def test_temporal_observations_shape() -> None:
    state = GlobalState.empty(n_agents=3, simulation_horizon=12)
    obs = build_temporal_observations(state, horizon=12, include_expectations=True)
    assert obs.shape == (3, 16)


def test_actor_critic_shapes() -> None:
    key = jax.random.PRNGKey(0)
    obs = jnp.zeros((4, 16), dtype=jnp.float32)
    ac = ActorCritic(key, obs_dim=16, action_dim=1)
    action_out, values = ac(obs, deterministic=True)
    assert action_out.shape == (4, 1)
    assert values.shape == (4,)
    dist = ac.get_action_distribution(obs, action_output=action_out)
    samples = sample_actions(dist, jax.random.PRNGKey(1))
    assert samples.shape == (4, 1)


def test_gae_respects_active_mask() -> None:
    T = 3
    n_agents = 2
    obs = jnp.zeros((T, n_agents, 4), dtype=jnp.float32)
    actions = jnp.zeros((T, n_agents, 1), dtype=jnp.float32)
    rewards = jnp.array([[1.0, 2.0], [1.0, 2.0], [1.0, 2.0]], dtype=jnp.float32)
    values = jnp.zeros((T, n_agents), dtype=jnp.float32)
    dones = jnp.zeros((T, n_agents), dtype=jnp.bool_)
    log_probs = jnp.zeros((T, n_agents), dtype=jnp.float32)
    active_mask = jnp.array([[True, False], [True, False], [True, False]])

    trajectory = Trajectory(
        observations=obs,
        actions=actions,
        rewards=rewards,
        values=values,
        dones=dones,
        log_probs=log_probs,
        final_observation=obs[-1],
        active_mask=active_mask,
    )

    final_value = jnp.zeros((n_agents,), dtype=jnp.float32)
    returns, advantages = compute_returns_and_advantages(
        trajectory, final_value, active_mask=active_mask
    )
    assert jnp.allclose(returns[:, 1], 0.0)
    assert jnp.allclose(advantages[:, 1], 0.0)


def test_temporal_consumption_updates_value() -> None:
    key = jax.random.PRNGKey(0)
    state = GlobalState.empty(n_agents=4, simulation_horizon=12)
    active = jnp.array([True, False, True, False])
    agents = state.agents.replace(active=active, income=jnp.ones(4) * 10.0)
    state = state.replace(agents=agents)
    obs = build_temporal_observations(state, horizon=12, include_expectations=True)

    ac = ActorCritic(key, obs_dim=obs.shape[-1], action_dim=1)
    mech = TemporalConsumptionMechanism(actor_critic=ac, horizon=12)
    new_state, _ = mech.apply(state, jax.random.PRNGKey(1), fidelity=FidelityLevel.SURROGATE_FLUID)
    _, values = ac(obs, deterministic=True)

    assert jnp.allclose(
        new_state.agents.expected_lifetime_utility[active],
        values[active],
    )
    assert jnp.allclose(
        new_state.agents.expected_lifetime_utility[~active],
        state.agents.expected_lifetime_utility[~active],
    )


def test_train_actor_critic_runs() -> None:
    key = jax.random.PRNGKey(0)
    state = GlobalState.empty(n_agents=4, simulation_horizon=12)
    obs = build_temporal_observations(state, horizon=12, include_expectations=True)
    ac = ActorCritic(key, obs_dim=obs.shape[-1], action_dim=1)

    executor = create_temporal_executor(ac, horizon=12)
    config = TrainingConfig(n_episodes=2, steps_per_episode=2, horizon=12, ppo_epochs=1)

    trained = train_actor_critic(ac, state, config, executor=executor)
    before = eqx.filter(ac, eqx.is_inexact_array)
    after = eqx.filter(trained, eqx.is_inexact_array)
    diff = _tree_sum_abs_diff(before, after)
    assert bool(jnp.isfinite(diff))


def _tree_sum_abs_diff(a, b) -> jnp.ndarray:
    diffs = jax.tree_util.tree_map(lambda x, y: jnp.sum(jnp.abs(x - y)), a, b)
    leaves = jax.tree_util.tree_leaves(diffs)
    return jnp.sum(jnp.stack(leaves))
