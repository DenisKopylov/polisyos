"""Run derivative-free evolution strategies for agent-simulation policy search."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


@dataclass(frozen=True)
class ESConfig:
    """Configure evolution-strategy search over repeated simulation rollouts."""

    population_size: int = 64
    n_generations: int = 100
    sigma: float = 0.02
    learning_rate: float = 0.01
    elite_fraction: float = 0.1
    antithetic: bool = True
    n_eval_steps: int = 256
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID


def run_evolution_strategies(
    actor_critic: ActorCritic,
    make_executor: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    fitness_fn: Callable[[GlobalState], jnp.ndarray],
    config: ESConfig,
    rng_key: jax.Array,
) -> tuple[ActorCritic, dict]:
    """Optimize an actor-critic policy with evolution strategies over simulated rollouts."""
    params, static = eqx.partition(actor_critic, eqx.is_inexact_array)
    flat_params, unflatten = jax.flatten_util.ravel_pytree(params)
    n_params = flat_params.shape[0]

    pop_size = int(config.population_size)
    if config.antithetic and pop_size % 2 == 1:
        pop_size -= 1

    def evaluate_params(flat_p: jnp.ndarray, key: jax.Array) -> jnp.ndarray:
        params_tree = unflatten(flat_p)
        actor = eqx.combine(static, params_tree)
        executor = make_executor(actor)
        final_state, _ = executor.run(
            initial_state,
            int(config.n_eval_steps),
            fidelity=config.fidelity,
        )
        return fitness_fn(final_state)

    @jax.jit
    def es_step(mean_params: jnp.ndarray, step_key: jax.Array) -> tuple[jnp.ndarray, jnp.ndarray]:
        key1, key2 = jax.random.split(step_key)
        half_pop = pop_size // 2 if config.antithetic else pop_size
        noise = jax.random.normal(key1, (half_pop, n_params)) * config.sigma
        if config.antithetic:
            noise = jnp.concatenate([noise, -noise], axis=0)

        candidates = mean_params + noise
        eval_keys = jax.random.split(key2, pop_size)
        fitnesses = jax.vmap(evaluate_params)(candidates, eval_keys)

        normalized = (fitnesses - jnp.mean(fitnesses)) / (jnp.std(fitnesses) + 1e-8)
        grad_estimate = jnp.dot(normalized, noise) / (pop_size * config.sigma)
        new_mean = mean_params + config.learning_rate * grad_estimate
        return new_mean, jnp.max(fitnesses)

    mean_params = flat_params
    best_fitness_history = []

    for _ in range(int(config.n_generations)):
        rng_key, step_key = jax.random.split(rng_key)
        mean_params, best_fitness = es_step(mean_params, step_key)
        best_fitness_history.append(float(best_fitness))

    final_params = unflatten(mean_params)
    final_actor = eqx.combine(static, final_params)
    metrics = {
        "fitness_history": best_fitness_history,
        "final_fitness": best_fitness_history[-1] if best_fitness_history else 0.0,
    }
    return final_actor, metrics


@dataclass(frozen=True)
class CMAESConfig:
    """Configure CMA-ES policy search when covariance adaptation matters."""

    population_size: int = 64
    n_generations: int = 100
    sigma_init: float = 0.5
    n_eval_steps: int = 256
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID


def run_cma_es(
    actor_critic: ActorCritic,
    make_executor: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    fitness_fn: Callable[[GlobalState], jnp.ndarray],
    config: CMAESConfig,
    rng_key: jax.Array,
) -> tuple[ActorCritic, dict]:
    """Optimize an actor-critic policy with CMA-ES over simulated rollouts."""
    params, static = eqx.partition(actor_critic, eqx.is_inexact_array)
    flat_params, unflatten = jax.flatten_util.ravel_pytree(params)
    n_params = flat_params.shape[0]

    mu = max(1, config.population_size // 2)
    weights = jnp.log(mu + 0.5) - jnp.log(jnp.arange(1, mu + 1))
    weights = weights / jnp.sum(weights)
    mu_eff = 1.0 / jnp.sum(weights**2)

    cc = (4 + mu_eff / n_params) / (n_params + 4 + 2 * mu_eff / n_params)
    cs = (mu_eff + 2) / (n_params + mu_eff + 5)
    c1 = 2 / ((n_params + 1.3) ** 2 + mu_eff)
    cmu = min(1 - c1, 2 * (mu_eff - 2 + 1 / mu_eff) / ((n_params + 2) ** 2 + mu_eff))
    damps = 1 + 2 * jnp.maximum(0.0, jnp.sqrt((mu_eff - 1) / (n_params + 1)) - 1) + cs
    chi_n = jnp.sqrt(n_params) * (1 - 1 / (4 * n_params) + 1 / (21 * n_params**2))

    def evaluate_params(flat_p: jnp.ndarray, key: jax.Array) -> jnp.ndarray:
        params_tree = unflatten(flat_p)
        actor = eqx.combine(static, params_tree)
        executor = make_executor(actor)
        final_state, _ = executor.run(
            initial_state,
            int(config.n_eval_steps),
            fidelity=config.fidelity,
        )
        return fitness_fn(final_state)

    mean = flat_params
    sigma = jnp.array(config.sigma_init, dtype=jnp.float32)
    c_diag = jnp.ones((n_params,), dtype=jnp.float32)
    pc = jnp.zeros((n_params,), dtype=jnp.float32)
    ps = jnp.zeros((n_params,), dtype=jnp.float32)

    fitness_history = []

    for gen in range(int(config.n_generations)):
        rng_key, key1, key2 = jax.random.split(rng_key, 3)

        noise = jax.random.normal(key1, (config.population_size, n_params))
        candidates = mean + sigma * noise * jnp.sqrt(c_diag)

        eval_keys = jax.random.split(key2, config.population_size)
        fitnesses = jax.vmap(evaluate_params)(candidates, eval_keys)
        sorted_idx = jnp.argsort(-fitnesses)
        selected = candidates[sorted_idx[:mu]]

        old_mean = mean
        mean = jnp.sum(weights[:, None] * selected, axis=0)

        ps = (1 - cs) * ps + jnp.sqrt(cs * (2 - cs) * mu_eff) * (mean - old_mean) / sigma
        norm_ps = jnp.linalg.norm(ps) / jnp.maximum(chi_n, 1e-8)
        hsig = norm_ps < (1.4 + 2 / (n_params + 1))
        pc = (1 - cc) * pc + hsig * jnp.sqrt(cc * (2 - cc) * mu_eff) * (mean - old_mean) / sigma

        artmp = (selected - old_mean) / sigma
        c_diag = (
            (1 - c1 - cmu) * c_diag
            + c1 * pc**2
            + cmu * jnp.sum(weights[:, None] * artmp**2, axis=0)
        )
        sigma = sigma * jnp.exp((cs / damps) * (norm_ps - 1))

        fitness_history.append(float(jnp.max(fitnesses)))

    final_params = unflatten(mean)
    final_actor = eqx.combine(static, final_params)
    metrics = {
        "fitness_history": fitness_history,
        "final_fitness": fitness_history[-1] if fitness_history else 0.0,
        "final_sigma": float(sigma),
    }
    return final_actor, metrics
