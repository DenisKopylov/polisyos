import jax
import jax.numpy as jnp
from polisyos.foundry.agent_sim import (
    ActorCritic,
    CreditConfig,
    CreditMode,
    ESConfig,
    GlobalState,
    GovernmentPolicy,
    GovernmentTrainingConfig,
    JITTrainingConfig,
    build_government_welfare_reward,
    build_temporal_observations,
    compute_credit_assignment,
    create_jit_trainer,
    create_temporal_executor,
    run_evolution_strategies,
    social_welfare_objective,
)
from polisyos.foundry.methods.catalog.policy.welfare import (
    clear_social_weight_manifest_registry,
    register_social_weight_manifest,
)


def _register_test_social_weights() -> str:
    clear_social_weight_manifest_registry()
    manifest = register_social_weight_manifest(
        {
            "method_fqn": "policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            "normalization": "mean_one",
            "basis": {"family": "cell"},
            "regime_ids": ["test"],
            "state_keys": [],
            "support": {"n_cells": 3},
            "diagnostics": {"moment_norm": 0.0},
            "coefficients": [2.0, 1.0, 0.5],
            "income_grid": [0.0, 10.0, 20.0],
            "weights_on_grid": [2.0, 1.0, 0.5],
            "normalization_weights": [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0],
        }
    )
    return manifest["ref"]


def _state_with_income_and_consumption() -> GlobalState:
    state = GlobalState.empty(n_agents=3, seed=0)
    agents = state.agents.replace(
        income=jnp.array([0.0, 10.0, 20.0], dtype=jnp.float32),
        consumption=jnp.array([10.0, 20.0, 40.0], dtype=jnp.float32),
        active=jnp.array([True, True, True]),
    )
    return state.replace(agents=agents)


def _expected_weighted_consumption() -> jnp.ndarray:
    raw_weights = jnp.array([2.0, 1.0, 0.5], dtype=jnp.float32)
    normalized_weights = raw_weights / jnp.mean(raw_weights)
    consumption = jnp.array([10.0, 20.0, 40.0], dtype=jnp.float32)
    return jnp.mean(normalized_weights * consumption)


def test_credit_assignment_individual() -> None:
    state = GlobalState.empty(n_agents=4, seed=0)
    rewards = jnp.array([1.0, 2.0, 3.0, 4.0], dtype=jnp.float32)
    config = CreditConfig(mode=CreditMode.INDIVIDUAL)
    result = compute_credit_assignment(rewards, state, state, config)
    assert bool(jnp.allclose(result, rewards))


def test_credit_assignment_counterfactual_mean() -> None:
    state = GlobalState.empty(n_agents=3, seed=0)
    rewards = jnp.array([0.0, 1.0, 2.0], dtype=jnp.float32)
    config = CreditConfig(
        mode=CreditMode.COUNTERFACTUAL,
        counterfactual_baseline="mean",
    )
    result = compute_credit_assignment(rewards, state, state, config)
    assert bool(jnp.isclose(jnp.mean(result), 0.0, atol=1e-6))


def test_credit_assignment_mean_field_shape() -> None:
    state = GlobalState.empty(n_agents=5, seed=0)
    rewards = jnp.arange(5, dtype=jnp.float32)
    config = CreditConfig(mode=CreditMode.MEAN_FIELD, mean_field_temperature=1.0)
    result = compute_credit_assignment(rewards, state, state, config)
    assert result.shape == rewards.shape


def test_jit_trainer_compiles() -> None:
    key = jax.random.PRNGKey(0)
    state = GlobalState.empty(n_agents=4, simulation_horizon=12)
    obs = build_temporal_observations(state, horizon=12, include_expectations=True)
    actor = ActorCritic(key, obs_dim=obs.shape[-1], action_dim=1)

    def make_executor(ac: ActorCritic):
        return create_temporal_executor(ac, horizon=12)

    config = JITTrainingConfig(
        n_episodes=2,
        steps_per_episode=2,
        ppo_epochs=1,
        horizon=12,
    )
    trainer = create_jit_trainer(actor, make_executor, state, config)
    trained, metrics = trainer(jax.random.PRNGKey(1))

    assert isinstance(trained, ActorCritic)
    assert metrics["loss_history"].shape[0] == config.n_episodes


def test_es_runs() -> None:
    key = jax.random.PRNGKey(0)
    state = GlobalState.empty(n_agents=4, simulation_horizon=12)
    obs = build_temporal_observations(state, horizon=12, include_expectations=True)
    actor = ActorCritic(key, obs_dim=obs.shape[-1], action_dim=1)

    def make_executor(ac: ActorCritic):
        return create_temporal_executor(ac, horizon=12)

    def fitness_fn(s: GlobalState) -> jnp.ndarray:
        return jnp.sum(s.agents.wealth * s.agents.active)

    config = ESConfig(population_size=4, n_generations=2, n_eval_steps=2)
    _, metrics = run_evolution_strategies(
        actor,
        make_executor,
        state,
        fitness_fn,
        config,
        jax.random.PRNGKey(2),
    )

    assert len(metrics["fitness_history"]) == config.n_generations


def test_government_policy_bounds() -> None:
    gov = GovernmentPolicy(jax.random.PRNGKey(0))
    obs = jnp.zeros((12,), dtype=jnp.float32)
    policy_state = gov(obs)

    assert 0.0 <= float(policy_state.tax_rate) <= 0.5
    assert 0.0 <= float(policy_state.transfer_rate) <= 0.3
    assert 0.0 <= float(policy_state.interest_rate) <= 0.2


def test_social_welfare_objective_total_wealth() -> None:
    state = GlobalState.empty(n_agents=3, seed=0)
    aggregates = state.aggregates.replace(total_wealth=jnp.array(100.0))
    state = state.replace(aggregates=aggregates)
    welfare = social_welfare_objective(state, {"gdp": 1.0})
    assert bool(jnp.isclose(welfare, 100.0))


def test_social_welfare_objective_uses_social_weight_ref() -> None:
    social_weight_ref = _register_test_social_weights()
    state = _state_with_income_and_consumption()

    welfare = social_welfare_objective(
        state,
        {},
        social_weight_ref=social_weight_ref,
    )

    assert bool(jnp.isclose(welfare, _expected_weighted_consumption(), atol=1e-5))
    assert not bool(jnp.isclose(welfare, jnp.mean(state.agents.consumption), atol=1e-5))


def test_government_welfare_reward_uses_social_weight_ref() -> None:
    social_weight_ref = _register_test_social_weights()
    state = _state_with_income_and_consumption()
    config = GovernmentTrainingConfig(
        welfare_weights={},
        social_weight_ref=social_weight_ref,
    )

    reward = build_government_welfare_reward(config)(state)

    assert bool(jnp.isclose(reward, _expected_weighted_consumption(), atol=1e-5))
