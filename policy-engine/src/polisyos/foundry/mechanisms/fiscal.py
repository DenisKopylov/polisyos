"""Public mechanisms fiscal module API."""

from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry._numeric import is_jax_tracer
from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.contracts.mechanism import Mechanism, PatchMap
from polisyos.foundry.contracts.state import GlobalState


def _combine_masks(
    target_mask: jnp.ndarray | None, active_mask: jnp.ndarray | None
) -> jnp.ndarray | None:
    if target_mask is None:
        return active_mask
    if active_mask is None:
        return target_mask
    return jnp.asarray(target_mask, dtype=jnp.bool_) & jnp.asarray(active_mask, dtype=jnp.bool_)


def _validate_rate(rate: jnp.ndarray | float, *, label: str = "rate") -> jnp.ndarray:
    rate_arr = jnp.asarray(rate, dtype=jnp.float32)
    if is_jax_tracer(rate_arr):
        return rate_arr
    rate_np = np.asarray(rate_arr)
    if not np.all(np.isfinite(rate_np)):
        raise ValueError(f"{label} must be finite")
    if np.any((rate_np < 0.0) | (rate_np > 1.0)):
        raise ValueError(f"{label} must lie in [0, 1]")
    return rate_arr


def compute_tax(state: GlobalState, rate: jnp.ndarray) -> jnp.ndarray:
    """Compute per-agent tax liabilities from reported income and an applied rate."""
    rate = _validate_rate(rate, label="tax rate")
    tax = state.agents.reported_income * rate
    active_mask = getattr(state.agents, "active", None)
    if active_mask is None:
        return tax
    return jnp.where(active_mask, tax, 0.0)


def compute_income_tax(state: GlobalState, rate: jnp.ndarray) -> jnp.ndarray:
    """Alias `compute_tax()` for fiscal APIs that explicitly expect income-tax semantics."""
    return compute_tax(state, rate)


class TaxSubsidy(Mechanism):
    """Tax subsidy public type."""

    rate: jnp.ndarray  # Изменено на jnp.ndarray для дифференцируемости
    target_sector_mask: jnp.ndarray

    def __init__(self, rate: float, n_agents: int, **kwargs: Any):
        self.rate = _validate_rate(rate, label="subsidy rate")
        self.target_sector_mask = jnp.ones(n_agents)
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ) -> tuple[PatchMap, jax.Array]:
        subsidy_amount = state.agents.income * self.rate * self.target_sector_mask
        mask = _combine_masks(target_mask, getattr(state.agents, "active", None))
        if mask is not None:
            subsidy_amount = jnp.where(mask, subsidy_amount, 0.0)
        total_cost = jnp.sum(subsidy_amount)
        if self.debug_mode:
            jax.debug.print("TaxSubsidy rate={r}, total_cost={c}", r=self.rate, c=total_cost)
        return (
            {
                "agents.income": [{"delta": subsidy_amount}],
                "government.balance": [{"delta": -total_cost}],
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
    """Income tax public type."""

    rate: jnp.ndarray

    def __init__(self, rate: float, n_agents: int, **kwargs: Any):
        self.rate = _validate_rate(rate, label="income tax rate")
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ) -> tuple[PatchMap, jax.Array]:
        tax_amount = compute_tax(state, self.rate)
        mask = _combine_masks(target_mask, getattr(state.agents, "active", None))
        if mask is not None:
            tax_amount = jnp.where(mask, tax_amount, 0.0)
        total_revenue = jnp.sum(tax_amount)
        if self.debug_mode:
            jax.debug.print("IncomeTax rate={r}, total_revenue={t}", r=self.rate, t=total_revenue)
        return (
            {
                "agents.income": [{"delta": -tax_amount}],
                "government.balance": [{"delta": total_revenue}],
            },
            key,
        )
