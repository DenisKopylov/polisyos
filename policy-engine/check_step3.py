# check_step3.py
import jax_bootstrap  # noqa: F401
import jax
import jax.numpy as jnp
import equinox as eqx

from src.domain.state import GlobalState, AgentState
from src.foundry.fiscal import TaxSubsidy
from src.foundry.types import FidelityLevel

def create_dummy_state(n=10):
    # Создаем упрощенное состояние для тестирования
    from src.domain.state import FirmState, MarketState

    agents = AgentState(
        age=jnp.ones(n, dtype=jnp.int32)*30,
        skill_level=jnp.ones(n, dtype=jnp.float32),
        income=jnp.ones(n, dtype=jnp.float32)*1000.0,
        savings=jnp.zeros(n, dtype=jnp.float32),
        consumption=jnp.zeros(n, dtype=jnp.float32),
        is_employed=jnp.ones(n, dtype=bool),
        employer_id=jnp.zeros(n, dtype=jnp.int32)
    )

    # Минимальные фирмы и рынок для GlobalState
    firms = FirmState(
        sector_id=jnp.zeros(1, dtype=jnp.int32),
        productivity=jnp.ones(1, dtype=jnp.float32),
        capital=jnp.ones(1, dtype=jnp.float32)*100.0,
        labor_count=jnp.zeros(1, dtype=jnp.float32),
        cash=jnp.ones(1, dtype=jnp.float32)*10000.0,
        inventory=jnp.zeros(1, dtype=jnp.float32),
        debt=jnp.zeros(1, dtype=jnp.float32),
        wage_offer=jnp.ones(1, dtype=jnp.float32)*10.0,
        price=jnp.ones(1, dtype=jnp.float32)*1.0
    )

    market = MarketState(
        avg_price=1.0,
        total_supply=0.0,
        total_demand=0.0,
        avg_wage=10.0,
        unemployment_rate=0.0,
        interest_rate=0.05
    )

    return GlobalState(
        step=0,
        agents=agents,
        firms=firms,
        market=market,
        government_balance=0.0,
        gdp=0.0
    )

def test_differentiability():
    print("--- Testing Mechanism Differentiability ---")

    n_agents = 5
    state = create_dummy_state(n_agents)
    key = jax.random.PRNGKey(0)

    # Функция потерь: "Мы хотим максимизировать доход агентов"
    # Loss = - (Average Income)
    def loss_fn(mech):
        # mech - это объект TaxSubsidy (PyTree)
        # Мы запускаем симуляцию на 1 шаг
        next_state = mech(state, key)
        return -jnp.mean(next_state.agents.income)

    # Создаем механизм с ставкой 0.1 (10% субсидия)
    mech = TaxSubsidy(rate=0.1, n_agents=n_agents)

    print(f"Initial Rate: {mech.rate}")

    # 1. Считаем значение и градиент
    # equinox.filter_grad позволяет брать градиент по полям класса
    grad_fn = eqx.filter_grad(loss_fn)
    grads = grad_fn(mech)

    print(f"Gradient w.r.t Rate: {grads.rate}")

    # Интерпретация:
    # Если мы даем субсидию, доход растет. Значит Loss (минус доход) падает.
    # Значит градиент должен быть отрицательным (увеличиваем rate -> уменьшаем Loss).

    assert grads.rate is not None, "Gradient is None! Differentiability broken."
    assert grads.rate < 0, "Gradient direction is wrong (Subsidy should increase income)."

    print("✅ Gradients are flowing correctly!")

    # 2. Проверка инвариантов
    next_state = mech(state, key)
    is_valid = mech.invariants(next_state)
    print(f"Invariant Check: {is_valid}")
    assert is_valid, "Invariant check failed"
    print("✅ Invariants passed!")

if __name__ == "__main__":
    test_differentiability()
