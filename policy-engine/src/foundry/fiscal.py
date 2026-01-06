import jax.numpy as jnp
from typing import Any

from src.domain.state import GlobalState
from src.foundry.base import Mechanism
from src.foundry.types import FidelityLevel


class TaxSubsidy(Mechanism):
    rate: jnp.ndarray  # Изменено на jnp.ndarray для дифференцируемости
    target_sector_mask: jnp.ndarray

    def __init__(self, rate: float, n_agents: int, **kwargs: Any):
        self.rate = jnp.array(rate)  # Конвертируем в JAX array
        self.target_sector_mask = jnp.ones(n_agents)
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def __call__(self, state: GlobalState, key) -> GlobalState:
        # Основная логика
        subsidy_amount = state.agents.income * self.rate * self.target_sector_mask
        total_cost = jnp.sum(subsidy_amount)

        new_income = state.agents.income + subsidy_amount
        new_balance = state.government_balance - total_cost

        new_agents = state.agents.replace(income=new_income)
        return state.replace(agents=new_agents, government_balance=new_balance)

    def invariants(self, state: GlobalState) -> bool:
        """
        Проверка: баланс правительства + доходы агентов должны сохраняться
        (сумма денег в системе не меняется, если это трансфер, а не эмиссия).
        Для примера проверим просто, что баланс не ушел в NaN.
        """
        is_finite = jnp.all(jnp.isfinite(state.government_balance))
        return bool(is_finite)


class IncomeTax(Mechanism):
    rate: float

    def __init__(self, rate: float, n_agents: int, **kwargs: Any):
        self.rate = rate
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def __call__(self, state: GlobalState, key) -> GlobalState:
        tax_amount = state.agents.income * self.rate
        total_revenue = jnp.sum(tax_amount)

        new_income = state.agents.income - tax_amount
        new_balance = state.government_balance + total_revenue

        new_agents = state.agents.replace(income=new_income)
        return state.replace(agents=new_agents, government_balance=new_balance)
