"""Named economic baseline profiles over the canonical Foundry state."""

from __future__ import annotations

import jax.numpy as jnp

from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.runtime.numeric import finite_loss_or_inf

__all__ = ["normalized_income_budget_loss"]


def normalized_income_budget_loss(
    final_state: GlobalState,
    min_balance: float = -1000.0,
) -> float:
    """Evaluate the legacy normalized-income and budget baseline.

    This is the explicitly named ``GlobalState`` economic baseline retained
    from the legacy ``policy_loss_fn``.  It is not an ``EconomicState``
    objective and does not claim equivalence with GDP, welfare, or wealth-tax
    objectives exposed by the economics plugin.
    """
    incomes = jnp.asarray(final_state.agents.income, dtype=jnp.float32)
    balance = jnp.asarray(final_state.government_balance, dtype=jnp.float32)
    min_balance_arr = jnp.asarray(min_balance, dtype=jnp.float32)

    income_scale = jnp.maximum(jnp.mean(jnp.abs(incomes)), 1.0)
    balance_scale = jnp.maximum(jnp.abs(min_balance_arr), 1.0)

    avg_income = jnp.mean(incomes)
    objective_loss = -avg_income / income_scale

    normalized_violation = jnp.maximum(0.0, min_balance_arr - balance) / balance_scale
    penalty = jnp.square(normalized_violation)

    total_loss = objective_loss + 10.0 * penalty
    invalid = (
        ~jnp.all(jnp.isfinite(incomes)) | ~jnp.isfinite(balance) | ~jnp.isfinite(min_balance_arr)
    )
    inf_value = jnp.asarray(jnp.inf, dtype=total_loss.dtype)
    return jnp.where(invalid, inf_value, finite_loss_or_inf(total_loss))
