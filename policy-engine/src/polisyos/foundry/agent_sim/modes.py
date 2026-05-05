"""Configure multi-stage agent learning, policy optimization, and bilevel search loops."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.credit_assignment import CreditConfig, CreditMode
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.policy import SharedPolicy
from polisyos.foundry.agent_sim.state import GlobalState, PolicyState
from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.welfare.social_weights import (
    prepare_social_weight_schedule,
    social_weighted_resource,
)


@dataclass(frozen=True)
class CalibrationTarget:
    """Declare an empirical metric target used by calibration-mode losses."""

    metric_path: str
    empirical_value: float
    weight: float = 1.0


class LearningMode(str, Enum):
    """Learning mode public type."""

    AGENTS_ADAPT = "agents_adapt"
    POLICY_OPTIMIZE = "policy_optimize"
    CALIBRATE = "calibrate"
    BILEVEL = "bilevel"


@dataclass(frozen=True)
class ModeAConfig:
    """Tune agent-adaptation episodes and credit assignment for mode-A training runs."""

    n_episodes: int = 100
    steps_per_episode: int = 64
    learning_rate: float = 3e-4
    credit_mode: CreditMode = CreditMode.COUNTERFACTUAL
    freeze_policy: bool = True
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID


@dataclass(frozen=True)
class ModeBConfig:
    """Tune policy-search iterations and welfare objectives for mode-B optimization runs."""

    n_iterations: int = 50
    n_steps: int = 256
    learning_rate: float = 1e-3
    objective: str = "social_welfare"
    welfare_weights: dict | None = None
    social_weight_ref: str | None = None
    social_weight_manifest: Mapping[str, Any] | None = None
    social_weight_scale: float = 1.0
    freeze_agents: bool = True
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID


@dataclass(frozen=True)
class BilevelConfig:
    """Coordinate alternating agent and policy updates for bilevel optimization runs."""

    outer_iterations: int = 20
    inner_episodes: int = 50
    mode_a_config: ModeAConfig | None = None
    mode_b_config: ModeBConfig | None = None
    alternating: bool = True


def social_welfare_objective(
    state: GlobalState,
    weights: dict | None = None,
    *,
    social_weight_ref: str | None = None,
    social_weight_manifest: Mapping[str, Any] | None = None,
    social_weight_scale: float = 1.0,
    social_weight_schedule: Mapping[str, Any] | None = None,
) -> jnp.ndarray:
    """Combine wealth, inequality, and consumption metrics into the default policy objective."""
    if weights is None:
        weights = {"gdp": 1.0, "neg_gini": 0.5}

    if social_weight_schedule is None:
        social_weight_schedule = prepare_social_weight_schedule(
            social_weight_ref=social_weight_ref,
            social_weight_manifest=social_weight_manifest,
        )

    total = jnp.array(0.0, dtype=jnp.float32)

    if "gdp" in weights:
        total = total + weights["gdp"] * state.aggregates.total_wealth

    if "neg_gini" in weights:
        total = total - weights["neg_gini"] * state.distributions.gini_wealth

    if "mean_consumption" in weights:
        total = total + weights["mean_consumption"] * state.aggregates.mean_consumption

    if "bottom_50_share" in weights:
        total = total + weights["bottom_50_share"] * state.distributions.bottom_50_share

    if social_weight_schedule is not None:
        total = total + (
            float(social_weight_scale)
            * weights.get("social_weighted_consumption", 1.0)
            * social_weighted_resource(
                state.agents.consumption,
                state.agents.income,
                state.agents.active,
                social_weight_schedule,
            )
        )

    return total


def run_mode_a_jit(
    make_executor: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    agent_policy: ActorCritic,
    config: ModeAConfig,
    credit_config: CreditConfig | None = None,
    rng_key: jax.Array | None = None,
) -> tuple[ActorCritic, dict]:
    """Train agent policies with the JIT actor-critic pipeline for mode A."""
    from polisyos.foundry.agent_sim.jit_training import (
        JITTrainingConfig,
        create_jit_trainer,
    )

    if credit_config is None:
        credit_config = CreditConfig(mode=config.credit_mode)

    if rng_key is None:
        rng_key = jax.random.PRNGKey(0)

    jit_config = JITTrainingConfig(
        n_episodes=config.n_episodes,
        steps_per_episode=config.steps_per_episode,
        learning_rate=config.learning_rate,
        fidelity=config.fidelity,
        credit_config=credit_config,
    )
    trainer = create_jit_trainer(agent_policy, make_executor, initial_state, jit_config)
    return trainer(rng_key)


def run_mode_b_jit(
    executor: PureExecutor,
    initial_state: GlobalState,
    policy_params: PolicyState,
    config: ModeBConfig,
    objective_fn: Callable[[GlobalState], jnp.ndarray] | None = None,
) -> tuple[PolicyState, dict]:
    """Optimize policy parameters against a simulated welfare objective for mode B."""
    if objective_fn is None:
        social_weight_schedule = prepare_social_weight_schedule(
            social_weight_ref=config.social_weight_ref,
            social_weight_manifest=config.social_weight_manifest,
        )
        objective_fn = lambda s: social_welfare_objective(
            s,
            config.welfare_weights,
            social_weight_scale=config.social_weight_scale,
            social_weight_schedule=social_weight_schedule,
        )

    optimizer = optax.adam(config.learning_rate)
    opt_state = optimizer.init(policy_params)

    @jax.jit
    def loss_fn(policy: PolicyState) -> jnp.ndarray:
        state = initial_state.replace(policy=policy)
        final_state, _ = executor.run(state, int(config.n_steps), fidelity=config.fidelity)
        return -objective_fn(final_state)

    @jax.jit
    def step_fn(carry, _):
        params, opt_state = carry
        loss_val, grads = jax.value_and_grad(loss_fn)(params)
        updates, new_opt_state = optimizer.update(grads, opt_state, params)
        new_params = optax.apply_updates(params, updates)
        return (new_params, new_opt_state), loss_val

    (final_params, _), losses = jax.lax.scan(
        step_fn,
        (policy_params, opt_state),
        None,
        length=int(config.n_iterations),
    )

    metrics = {
        "loss_history": losses,
        "final_objective": -losses[-1],
    }
    return final_params, metrics


def run_bilevel(
    make_executor: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    agent_policy: ActorCritic,
    policy_params: PolicyState,
    config: BilevelConfig,
    rng_key: jax.Array | None = None,
) -> tuple[ActorCritic, PolicyState, dict]:
    """Alternate agent learning and policy search across outer bilevel iterations."""
    mode_a_config = config.mode_a_config or ModeAConfig(n_episodes=config.inner_episodes)
    mode_b_config = config.mode_b_config or ModeBConfig(n_iterations=10)

    if rng_key is None:
        rng_key = jax.random.PRNGKey(0)

    current_agent = agent_policy
    current_policy = policy_params

    all_metrics = {
        "agent_losses": [],
        "policy_losses": [],
        "welfare_history": [],
    }

    for _ in range(int(config.outer_iterations)):
        key1, key2, rng_key = jax.random.split(rng_key, 3)

        state_with_policy = initial_state.replace(policy=current_policy)
        current_agent, agent_metrics = run_mode_a_jit(
            make_executor,
            state_with_policy,
            current_agent,
            mode_a_config,
            rng_key=key1,
        )
        all_metrics["agent_losses"].append(float(agent_metrics["final_loss"]))

        executor = make_executor(current_agent)
        current_policy, policy_metrics = run_mode_b_jit(
            executor,
            initial_state,
            current_policy,
            mode_b_config,
        )
        all_metrics["policy_losses"].append(float(policy_metrics["final_objective"]))
        all_metrics["welfare_history"].append(float(policy_metrics["final_objective"]))

    return current_agent, current_policy, all_metrics


def run_mode_a(
    make_executor: Callable[[SharedPolicy], PureExecutor],
    initial_state: GlobalState,
    agent_policy: SharedPolicy,
    n_episodes: int,
    n_steps_per_episode: int,
    optimizer: optax.GradientTransformation,
    loss_fn: Callable[[SharedPolicy, GlobalState, dict[str, jnp.ndarray]], jnp.ndarray],
    *,
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
) -> SharedPolicy:
    """Run mode a."""
    params = eqx.filter(agent_policy, eqx.is_inexact_array)
    opt_state = optimizer.init(params)

    for _ in range(int(n_episodes)):
        executor = make_executor(agent_policy)
        final_state, metrics = executor.run(
            initial_state,
            int(n_steps_per_episode),
            fidelity=fidelity,
        )
        (loss_val, grads) = eqx.filter_value_and_grad(loss_fn)(agent_policy, final_state, metrics)
        updates, opt_state = optimizer.update(grads, opt_state, params)
        agent_policy = eqx.apply_updates(agent_policy, updates)
        params = eqx.filter(agent_policy, eqx.is_inexact_array)
        _ = loss_val

    return agent_policy


def run_mode_b(
    executor: PureExecutor,
    initial_state: GlobalState,
    policy_params: PolicyState,
    optimizer: optax.GradientTransformation,
    n_iterations: int,
    objective_fn: Callable[[GlobalState], jnp.ndarray],
    *,
    n_steps: int = 256,
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
) -> PolicyState:
    """Run mode b."""
    opt_state = optimizer.init(policy_params)

    def loss_fn(policy: PolicyState) -> jnp.ndarray:
        state = initial_state.replace(policy=policy)
        final_state, _ = executor.run(state, int(n_steps), fidelity=fidelity)
        return -objective_fn(final_state)

    for _ in range(int(n_iterations)):
        loss_val, grads = jax.value_and_grad(loss_fn)(policy_params)
        updates, opt_state = optimizer.update(grads, opt_state, policy_params)
        policy_params = optax.apply_updates(policy_params, updates)
        _ = loss_val

    return policy_params


def run_mode_c(
    executor: PureExecutor,
    initial_state: GlobalState,
    calibration_targets: Sequence[CalibrationTarget],
    calibration_params: PolicyState,
    optimizer: optax.GradientTransformation,
    apply_params_fn: Callable[[GlobalState, PolicyState], GlobalState],
    *,
    n_steps: int = 256,
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    max_steps: int = 1000,
    loss_tol: float = 1e-6,
) -> PolicyState:
    """Run mode c."""
    opt_state = optimizer.init(calibration_params)
    targets = tuple(calibration_targets)

    def loss_fn(params: PolicyState) -> jnp.ndarray:
        state = apply_params_fn(initial_state, params)
        final_state, metrics = executor.run(state, int(n_steps), fidelity=fidelity)
        total = jnp.array(0.0, dtype=jnp.float32)
        for target in targets:
            model_value = _extract_metric(final_state, metrics, target.metric_path)
            diff = model_value - jnp.asarray(target.empirical_value, dtype=jnp.float32)
            total = total + float(target.weight) * (diff**2)
        return total

    params = calibration_params
    for _ in range(int(max_steps)):
        loss_val, grads = jax.value_and_grad(loss_fn)(params)
        updates, opt_state = optimizer.update(grads, opt_state, params)
        params = optax.apply_updates(params, updates)
        if float(loss_val) < float(loss_tol):
            break
    return params


def _extract_metric(
    final_state: GlobalState,
    metrics: dict[str, jnp.ndarray],
    metric_path: str,
) -> jnp.ndarray:
    if metric_path in metrics:
        return metrics[metric_path]
    return _resolve_path(final_state, metric_path)


def _resolve_path(obj: object, path: str) -> jnp.ndarray:
    current = obj
    for part in path.split("."):
        current = getattr(current, part)
    return jnp.asarray(current)
