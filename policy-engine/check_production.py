import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import jax_bootstrap  # noqa: F401
import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.engine.kernel import SimulationKernel
from polisyos.common.logger import logger


def test_cobb_douglas():
    """Тест функции Кобба-Дугласа"""
    from polisyos.foundry.engine.logic import cobb_douglas_production

    logger.info("🧮 Testing Cobb-Douglas Production Function...")

    # Тест 1: Базовый случай
    A, K, L, alpha = 1.0, 100.0, 50.0, 0.3
    Y = cobb_douglas_production(A, K, L, alpha)
    expected_Y = 1.0 * (100.0**0.3) * (50.0**0.7)

    logger.info(f"Input: A={A}, K={K}, L={L}, α={alpha}")
    logger.info(f"Output: Y={Y:.2f}, Expected: {expected_Y:.2f}")

    assert abs(Y - expected_Y) < 1e-6, f"Cobb-Douglas calculation error: {Y} != {expected_Y}"
    logger.success("✅ Cobb-Douglas function works correctly!")


def test_production_engine():
    """Тест полного цикла производства"""
    logger.info("🏭 Testing Production Engine...")

    # Создаем состояние
    N_AGENTS = 100
    N_FIRMS = 5
    state = GlobalState.empty(n_agents=N_AGENTS, n_firms=N_FIRMS)

    # Создаем ядро симуляции
    kernel = SimulationKernel()

    # Ключ случайности
    key = jax.random.PRNGKey(42)

    logger.info("Initial state:")
    logger.info(f"  Firms cash: {jnp.sum(state.firms.cash):.0f}")
    logger.info(f"  Firms inventory: {jnp.sum(state.firms.inventory):.0f}")
    logger.info(f"  Agents employed: {jnp.sum(state.agents.is_employed)}/{N_AGENTS}")
    logger.info(f"  GDP: {state.gdp:.0f}")

    # Делаем один шаг симуляции
    new_state = kernel.step(state, key)

    logger.info("After 1 step:")
    logger.info(f"  Firms cash: {jnp.sum(new_state.firms.cash):.0f}")
    logger.info(f"  Firms inventory: {jnp.sum(new_state.firms.inventory):.0f}")
    logger.info(f"  Agents employed: {jnp.sum(new_state.agents.is_employed)}/{N_AGENTS}")
    logger.info(f"  GDP: {new_state.gdp:.0f}")
    logger.info(f"  Avg price: {new_state.market.avg_price:.2f}")
    logger.info(f"  Unemployment: {new_state.market.unemployment_rate:.1%}")

    # Проверки
    assert new_state.step == 1, "Step should increment"
    assert jnp.sum(new_state.firms.inventory) >= 0, "Inventory should be non-negative"
    assert jnp.sum(new_state.agents.income) >= 0, "Income should be non-negative"
    assert 0 <= new_state.market.unemployment_rate <= 1, "Unemployment rate should be 0-1"

    logger.success("✅ Production engine works!")


def test_multiple_steps():
    """Тест нескольких шагов симуляции"""
    logger.info("🔄 Testing Multiple Simulation Steps...")

    N_AGENTS = 50
    N_FIRMS = 3
    state = GlobalState.empty(n_agents=N_AGENTS, n_firms=N_FIRMS)
    kernel = SimulationKernel()

    gdp_history = []
    unemployment_history = []

    # 5 шагов симуляции
    key = jax.random.PRNGKey(123)
    for step in range(5):
        state = kernel.step(state, key)
        key = jax.random.split(key)[1]  # новый ключ

        gdp_history.append(float(state.gdp))
        unemployment_history.append(float(state.market.unemployment_rate))

        logger.info(
            f"Step {state.step}: GDP={state.gdp:.0f}, Unemployment={state.market.unemployment_rate:.1%}"
        )

    # Проверки трендов
    assert len(gdp_history) == 5, "Should have 5 GDP measurements"
    assert len(unemployment_history) == 5, "Should have 5 unemployment measurements"
    assert all(g >= 0 for g in gdp_history), "GDP should always be non-negative"

    logger.success("✅ Multi-step simulation works!")


def main():
    logger.info("🚀 Testing NEW Production Engine (Cobb-Douglas + Markets)...")

    try:
        test_cobb_douglas()
        test_production_engine()
        test_multiple_steps()

        logger.success("🎉 All production engine tests PASSED!")
        logger.info("🏗 Real Economy is ready for simulation!")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
