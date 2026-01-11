from typing import Any

import jax
import jax.numpy as jnp

from polisyos.foundry.base import Mechanism
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.types import FidelityLevel


class TaxSubsidy(Mechanism):
    rate: jnp.ndarray  # Изменено на jnp.ndarray для дифференцируемости
    target_sector_mask: jnp.ndarray

    def __init__(self, rate: float, n_agents: int, **kwargs: Any):
        self.rate = jnp.array(rate)  # Конвертируем в JAX array
        self.target_sector_mask = jnp.ones(n_agents)
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        # Основная логика
        # Ограничиваем rate в положительном диапазоне [0, 1]
        clamped_rate = jnp.clip(self.rate, 0.0, 1.0)
        subsidy_amount = state.agents.income * clamped_rate * self.target_sector_mask
        total_cost = jnp.sum(subsidy_amount)

        new_income = state.agents.income + subsidy_amount
        new_balance = state.government_balance - total_cost

        new_agents = state.agents.replace(income=new_income)
        if self.debug_mode:
            jax.debug.print("TaxSubsidy rate={r}, total_cost={c}", r=clamped_rate, c=total_cost)
        return state.replace(agents=new_agents, government_balance=new_balance), key

    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ):
        clamped_rate = jnp.clip(self.rate, 0.0, 1.0)
        subsidy_amount = state.agents.income * clamped_rate
        if target_mask is not None:
            subsidy_amount = jnp.where(target_mask, subsidy_amount, 0.0)
        total_cost = jnp.sum(subsidy_amount)
        return (
            {
                "agents.income": {"delta": subsidy_amount},
                "government.balance": {"delta": -total_cost},
            },
            key,
        )

    def invariants(self, state: GlobalState) -> bool:
        """
        Проверка: баланс правительства + доходы агентов должны сохраняться
        (сумма денег в системе не меняется, если это трансфер, а не эмиссия).
        Для примера проверим просто, что баланс не ушел в NaN.
        """
        is_finite = jnp.all(jnp.isfinite(state.government_balance))
        return bool(is_finite)


class IncomeTax(Mechanism):
    rate: jnp.ndarray

    def __init__(self, rate: float, n_agents: int, **kwargs: Any):
        self.rate = jnp.array(rate)
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        tax_amount = state.agents.income * self.rate
        total_revenue = jnp.sum(tax_amount)

        new_income = state.agents.income - tax_amount
        new_balance = state.government_balance + total_revenue

        new_agents = state.agents.replace(income=new_income)
        if self.debug_mode:
            jax.debug.print("IncomeTax rate={r}, total_revenue={t}", r=self.rate, t=total_revenue)
        return state.replace(agents=new_agents, government_balance=new_balance), key

    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ):
        tax_amount = state.agents.income * self.rate
        if target_mask is not None:
            tax_amount = jnp.where(target_mask, tax_amount, 0.0)
        total_revenue = jnp.sum(tax_amount)
        return (
            {
                "agents.income": {"delta": -tax_amount},
                "government.balance": {"delta": total_revenue},
            },
            key,
        )
