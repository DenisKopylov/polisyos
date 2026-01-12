import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry._legacy.engine.logic import (
    aggregate_market_stats,
    update_agents_consumption,
    update_firms_production,
    update_goods_market,
    update_labor_market,
)


class SimulationKernel:
    def __init__(self):
        self.step = jax.jit(self._step_logic)

    def _step_logic(self, state: GlobalState, key: jax.Array) -> GlobalState:
        key1, key2, key3, key4 = jax.random.split(key, 4)
        new_firms, produced_goods = update_firms_production(state.firms, key1)
        new_agents, new_firms = update_labor_market(state.agents, new_firms, key2)
        new_firms, new_agents, new_market = update_goods_market(
            new_firms, new_agents, state.market, produced_goods, key3
        )
        final_agents = update_agents_consumption(new_agents, new_market, key4)
        final_market = aggregate_market_stats(final_agents, new_firms, new_market)
        total_gdp = jnp.sum(final_agents.income) + jnp.sum(new_firms.cash - new_firms.cash * 0.1)
        return state.replace(
            step=state.step + 1,
            agents=final_agents,
            firms=new_firms,
            market=final_market,
            gdp=total_gdp,
        )

