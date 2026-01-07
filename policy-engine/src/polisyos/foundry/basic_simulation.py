"""
Базовый пример симуляции политики с использованием JAX.
Демонстрирует основные возможности JAX для вычислений.
"""

import jax
import jax.numpy as jnp
from jaxtyping import Array
from loguru import logger


def simple_policy_simulation(
    population_size: int, time_steps: int, policy_effect: float = 0.1, random_seed: int = 42
) -> tuple[Array, Array]:
    """
    Простая симуляция эффекта политики на популяцию.

    Args:
        population_size: Размер популяции
        time_steps: Количество временных шагов
        policy_effect: Эффект политики (0.1 = 10% улучшение)
        random_seed: Seed для воспроизводимости

    Returns:
        Кортеж (временные_шаги, значения_популяции)
    """
    # Устанавливаем seed для воспроизводимости
    key = jax.random.PRNGKey(random_seed)

    # Начальная популяция (нормальное распределение)
    initial_population = jax.random.normal(key, (population_size,)) * 10 + 100

    # Временные шаги
    time_array = jnp.arange(time_steps)

    # Симуляция эффекта политики (экспоненциальный рост с шумом)
    def simulate_step(population: Array, t: int) -> Array:
        # Добавляем эффект политики
        growth = policy_effect * jnp.sqrt(t + 1)  # Нарастающий эффект
        noise = jax.random.normal(jax.random.fold_in(key, t), population.shape) * 0.1
        return population * (1 + growth + noise)

    # Собираем результаты на каждом шаге
    def scan_step(carry, t):
        population = simulate_step(carry, t)
        return population, population

    final_population, populations_over_time = jax.lax.scan(
        scan_step, initial_population, time_array
    )

    return time_array, populations_over_time


def analyze_simulation_results(time_steps: Array, populations: Array) -> dict:
    """
    Анализирует результаты симуляции.

    Args:
        time_steps: Массив временных шагов
        populations: Массив значений популяции

    Returns:
        Словарь с результатами анализа
    """
    # Среднее значение по популяции на каждом шаге
    mean_population = jnp.mean(populations, axis=0)
    # Стандартное отклонение
    std_population = jnp.std(populations, axis=0)

    # Общая статистика
    total_growth = (mean_population[-1] - mean_population[0]) / mean_population[0] * 100

    return {
        "mean_population": mean_population,
        "std_population": std_population,
        "total_growth_percent": total_growth,
        "final_population_mean": float(mean_population[-1]),
        "initial_population_mean": float(mean_population[0]),
        "population_shape": populations.shape,
    }


# Пример использования
if __name__ == "__main__":
    logger.info("🚀 Запуск базовой симуляции политики")

    # Параметры симуляции
    POPULATION_SIZE = 1000
    TIME_STEPS = 50
    POLICY_EFFECT = 0.05  # 5% эффект политики

    logger.info(
        f"📊 Параметры: population={POPULATION_SIZE}, steps={TIME_STEPS}, effect={POLICY_EFFECT}"
    )

    # Запускаем симуляцию
    time_steps, populations = simple_policy_simulation(
        population_size=POPULATION_SIZE, time_steps=TIME_STEPS, policy_effect=POLICY_EFFECT
    )

    # Анализируем результаты
    analysis = analyze_simulation_results(time_steps, populations)

    logger.info(".1f")
    logger.info(".2f")
    logger.info(".1f")

    # Проверяем, что JAX работает корректно
    logger.info(f"✅ JAX backend: {jax.default_backend()}")
    logger.info(f"✅ Доступные устройства: {jax.devices()}")

    logger.info("🎉 Симуляция завершена успешно!")
