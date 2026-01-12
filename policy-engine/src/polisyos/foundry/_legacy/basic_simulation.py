"""
Базовый пример симуляции политики с использованием JAX (legacy).
"""

import jax
import jax.numpy as jnp
from jaxtyping import Array
from loguru import logger


def simple_policy_simulation(
    population_size: int, time_steps: int, policy_effect: float = 0.1, random_seed: int = 42
) -> tuple[Array, Array]:
    key = jax.random.PRNGKey(random_seed)
    initial_population = jax.random.normal(key, (population_size,)) * 10 + 100
    time_array = jnp.arange(time_steps)

    def simulate_step(population: Array, t: int) -> Array:
        growth = policy_effect * jnp.sqrt(t + 1)
        noise = jax.random.normal(jax.random.fold_in(key, t), population.shape) * 0.1
        return population * (1 + growth + noise)

    def scan_step(carry, t):
        population = simulate_step(carry, t)
        return population, population

    _, populations_over_time = jax.lax.scan(scan_step, initial_population, time_array)
    return time_array, populations_over_time


def analyze_simulation_results(time_steps: Array, populations: Array) -> dict:
    mean_population = jnp.mean(populations, axis=0)
    std_population = jnp.std(populations, axis=0)
    total_growth = (mean_population[-1] - mean_population[0]) / mean_population[0] * 100
    return {
        "mean_population": mean_population,
        "std_population": std_population,
        "total_growth_percent": total_growth,
        "final_population_mean": float(mean_population[-1]),
        "initial_population_mean": float(mean_population[0]),
        "population_shape": populations.shape,
    }


if __name__ == "__main__":
    logger.info("🚀 Запуск базовой симуляции политики (legacy)")
    POPULATION_SIZE = 1000
    TIME_STEPS = 50
    POLICY_EFFECT = 0.05
    time_steps, populations = simple_policy_simulation(
        population_size=POPULATION_SIZE, time_steps=TIME_STEPS, policy_effect=POLICY_EFFECT
    )
    analysis = analyze_simulation_results(time_steps, populations)
    logger.info(f"Final mean: {analysis['final_population_mean']}")
    logger.info(f"Total growth: {analysis['total_growth_percent']:.2f}%")
    logger.info(f"JAX backend: {jax.default_backend()}")

