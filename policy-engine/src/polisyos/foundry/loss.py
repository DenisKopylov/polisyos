# polisyos/foundry/loss.py
import jax.numpy as jnp

from polisyos.foundry.contracts.state import GlobalState


def policy_loss_fn(final_state: GlobalState, min_balance: float = -1000.0) -> float:
    """
    Функция потерь для оптимизатора.
    Цель: Максимизировать средний доход.
    Ограничение: Баланс не ниже min_balance.
    """
    # 1. Цель (Objective): Максимизация дохода
    # Мы минимизируем Loss, поэтому берем доход со знаком минус
    avg_income = jnp.mean(final_state.agents.income)
    objective_loss = -avg_income / 1000.0  # Нормализация для стабильности градиентов

    # 2. Ограничение (Constraint): Мягкий штраф (Barrier / Penalty)
    # Если balance < min_balance, штраф растет квадратично
    balance = final_state.government_balance
    violation = min_balance - balance  # Если -2000 < -1000 -> violation = 1000 (штраф)
    # Если 500 < -1000 -> violation = -1500 (нет штрафа)

    # ReLU: штрафуем только если violation > 0 (баланс слишком низкий)
    penalty = jnp.maximum(0.0, violation) ** 2

    # Очень сильный штраф для соблюдения ограничений бюджета
    lambda_param = 1000.0  # Сильно увеличиваем штраф

    total_loss = objective_loss + lambda_param * penalty
    return total_loss
