"""Public foundry loss module API."""
# polisyos/foundry/loss.py
import jax.numpy as jnp

from polisyos.foundry._numeric import finite_loss_or_inf
from polisyos.foundry.contracts.state import GlobalState


def policy_loss_fn(final_state: GlobalState, min_balance: float = -1000.0) -> float:
    """Policy objective with fail-closed numerics and normalized budget penalties."""
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
        ~jnp.all(jnp.isfinite(incomes))
        | ~jnp.isfinite(balance)
        | ~jnp.isfinite(min_balance_arr)
    )
    inf_value = jnp.asarray(jnp.inf, dtype=total_loss.dtype)
    return jnp.where(invalid, inf_value, finite_loss_or_inf(total_loss))
