import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.engine.kernel import SimulationKernel


def test_cobb_douglas() -> None:
    from polisyos.foundry.engine.logic import cobb_douglas_production

    a, k, l, alpha = 1.0, 100.0, 50.0, 0.3
    y = cobb_douglas_production(a, k, l, alpha)
    expected_y = a * (k**alpha) * (l ** (1.0 - alpha))

    assert abs(y - expected_y) < 1e-6


def test_production_engine_step() -> None:
    n_agents = 100
    n_firms = 5
    state = GlobalState.empty(n_agents=n_agents, n_firms=n_firms)
    kernel = SimulationKernel()
    key = jax.random.PRNGKey(42)

    new_state = kernel.step(state, key)

    assert int(new_state.step) == 1
    assert float(jnp.sum(new_state.firms.inventory)) >= 0.0
    assert float(jnp.sum(new_state.agents.income)) >= 0.0
    assert 0.0 <= float(new_state.market.unemployment_rate) <= 1.0


def test_multiple_steps() -> None:
    n_agents = 50
    n_firms = 3
    state = GlobalState.empty(n_agents=n_agents, n_firms=n_firms)
    kernel = SimulationKernel()

    gdp_history = []
    unemployment_history = []

    key = jax.random.PRNGKey(123)
    for _ in range(5):
        state = kernel.step(state, key)
        key = jax.random.split(key)[1]
        gdp_history.append(float(state.gdp))
        unemployment_history.append(float(state.market.unemployment_rate))

    assert len(gdp_history) == 5
    assert len(unemployment_history) == 5
    assert all(gdp >= 0.0 for gdp in gdp_history)
