import jax_bootstrap  # noqa: F401
import jax
import jax.numpy as jnp

from src.domain.state import GlobalState  # noqa: E402
from src.foundry.fiscal import IncomeTax, TaxSubsidy  # noqa: E402

# IMPORTS HACK
from src.utils.logger import logger  # noqa: E402


def main():
    logger.info("💰 Starting Budget Logic Check...")

    # 1. Init World
    N = 10
    state = GlobalState.empty(n_agents=N, n_firms=2)
    # У всех доход 1000, в казне 0
    state = state.replace(
        agents=state.agents.replace(income=jnp.ones(N) * 1000.0), government_balance=0.0
    )

    logger.info(f"Step 0: Balance = {state.government_balance}")

    # 2. Apply Tax (10%)
    tax_mech = IncomeTax(n_agents=N, rate=0.10)
    state = tax_mech(state, jax.random.PRNGKey(0))

    # Ожидание:
    # Доход агентов: 1000 - 100 = 900
    # Казна: 0 + (100 * 10) = 1000
    logger.info(f"Step 1 (After Tax): Balance = {state.government_balance} (Expected 1000.0)")
    assert state.government_balance == 1000.0, "Tax collection failed!"

    # 3. Apply Subsidy (50% от текущего дохода)
    # Текущий доход 900. Субсидия 450.
    sub_mech = TaxSubsidy(n_agents=N, rate=0.50)
    state = sub_mech(state, jax.random.PRNGKey(0))

    # Ожидание:
    # Расход: 450 * 10 = 4500
    # Казна: 1000 - 4500 = -3500 (Дефицит!)
    logger.info(f"Step 2 (After Subsidy): Balance = {state.government_balance} (Expected -3500.0)")
    assert state.government_balance == -3500.0, "Subsidy spending failed!"

    logger.success("✅ Fiscal Physics Works! Budget is tracked correctly.")


if __name__ == "__main__":
    main()
