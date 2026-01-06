import jax
import jax.numpy as jnp

from src.domain.state import GlobalState
from src.engine.logic import (
    aggregate_market_stats,
    update_agents_consumption,
    update_firms_production,
    update_goods_market,
    update_labor_market,
)


class SimulationKernel:
    def __init__(self):
        # Компилируем (JIT) функцию шага сразу при создании класса
        self.step = jax.jit(self._step_logic)

    def _step_logic(self, state: GlobalState, key: jax.Array) -> GlobalState:
        """
        Функция перехода S_t -> S_t+1: Производство → Рынок Труда → Рынок Товаров → Потребление
        """
        # 1. Подготовка ключей случайности
        key1, key2, key3, key4 = jax.random.split(key, 4)

        # 2. ПРОИЗВОДСТВО (Кобб-Дуглас)
        # Фирмы производят товары используя капитал и труд
        new_firms, produced_goods = update_firms_production(state.firms, key1)

        # 3. РЫНОК ТРУДА
        # Агенты ищут работу, фирмы нанимают/увольняют
        new_agents, new_firms = update_labor_market(state.agents, new_firms, key2)

        # 4. РЫНОК ТОВАРОВ
        # Фирмы устанавливают цены, агенты покупают товары
        new_firms, new_agents, new_market = update_goods_market(
            new_firms, new_agents, state.market, produced_goods, key3
        )

        # 5. ПОТРЕБЛЕНИЕ И СБЕРЕЖЕНИЯ
        # Агенты тратят доходы на товары
        final_agents = update_agents_consumption(new_agents, new_market, key4)

        # 6. АГРЕГАЦИЯ МАКРОСТАТИСТИКИ
        final_market = aggregate_market_stats(final_agents, new_firms, new_market)

        # 7. GDP: сумма всех доходов (зарплаты + прибыль)
        total_gdp = jnp.sum(final_agents.income) + jnp.sum(
            new_firms.cash - new_firms.cash * 0.1
        )  # прибыль ~10% от кэша

        return state.replace(
            step=state.step + 1,
            agents=final_agents,
            firms=new_firms,
            market=final_market,
            gdp=total_gdp,
        )
