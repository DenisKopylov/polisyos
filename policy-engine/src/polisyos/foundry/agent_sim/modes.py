from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.policy import SharedPolicy
from polisyos.foundry.agent_sim.state import GlobalState, PolicyState
from polisyos.foundry.types import FidelityLevel


@dataclass(frozen=True)
class CalibrationTarget:
    metric_path: str
    empirical_value: float
    weight: float = 1.0


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
    params = eqx.filter(agent_policy, eqx.is_inexact_array)
    opt_state = optimizer.init(params)

    for _ in range(int(n_episodes)):
        executor = make_executor(agent_policy)
        final_state, metrics = executor.run(
            initial_state,
            int(n_steps_per_episode),
            fidelity=fidelity,
        )
        (loss_val, grads) = eqx.filter_value_and_grad(loss_fn)(
            agent_policy, final_state, metrics
        )
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
