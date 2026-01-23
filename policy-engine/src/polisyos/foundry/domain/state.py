import chex
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float, Int


# --- 1. ЛЮДИ (Households) ---
@chex.dataclass(frozen=True)
class AgentState:
    # Active mask: True means the agent participates in the simulation.
    active: Bool[Array, "n_agents"]

    # Демография и Навыки
    age: Int[Array, "n_agents"]
    skill_level: Float[Array, "n_agents"]  # Влияет на зарплату

    # Финансы
    income: Float[Array, "n_agents"]
    reported_income: Float[Array, "n_agents"]
    savings: Float[Array, "n_agents"]
    consumption: Float[Array, "n_agents"]  # Сколько потратил
    risk_aversion: Float[Array, "n_agents"]

    # Работа
    is_employed: Bool[Array, "n_agents"]
    employer_id: Int[Array, "n_agents"]  # ID фирмы (0..M-1) или -1

    @property
    def size(self) -> int:
        return self.income.shape[0]


# --- 2. БИЗНЕС (Firms) ---
@chex.dataclass(frozen=True)
class FirmState:
    # Статика
    sector_id: Int[Array, "n_firms"]  # 0=IT, 1=Agro...
    productivity: Float[Array, "n_firms"]  # Технологичность (A)

    # Производственные факторы
    capital: Float[Array, "n_firms"]  # Станки/Софт (K)
    labor_count: Float[Array, "n_firms"]  # Текущий штат (L)

    # Финансы
    cash: Float[Array, "n_firms"]  # Деньги на зарплаты
    inventory: Float[Array, "n_firms"]  # Товары на складе
    debt: Float[Array, "n_firms"]  # Долги

    # Рынок
    wage_offer: Float[Array, "n_firms"]  # Зарплатное предложение
    price: Float[Array, "n_firms"]  # Цена товара фирмы

    @property
    def size(self) -> int:
        return self.capital.shape[0]


# --- 3. РЫНОК (Macro) ---
@chex.dataclass(frozen=True)
class MarketState:
    # Агрегаты
    avg_price: Float[Array, ""]  # CPI (Индекс цен)
    total_supply: Float[Array, ""]  # Всего товаров
    total_demand: Float[Array, ""]  # Всего денег у покупателей

    avg_wage: Float[Array, ""]
    unemployment_rate: Float[Array, ""]
    interest_rate: Float[Array, ""]  # Ставка ЦБ


# --- 4. МИР (Global State) ---
@chex.dataclass(frozen=True)
class GlobalState:
    step: Int[Array, ""]
    agents: AgentState
    firms: FirmState
    market: MarketState

    government_balance: Float[Array, ""]
    tax_rate: Float[Array, ""]
    gdp: Float[Array, ""]

    @classmethod
    def empty(cls, n_agents: int, n_firms: int) -> "GlobalState":
        # Инициализация дефолтными значениями
        agents = AgentState(
            active=jnp.ones(n_agents, dtype=jnp.bool_),
            age=jnp.zeros(n_agents, dtype=jnp.int32),
            skill_level=jnp.ones(n_agents, dtype=jnp.float32),
            income=jnp.zeros(n_agents, dtype=jnp.float32),
            reported_income=jnp.zeros(n_agents, dtype=jnp.float32),
            savings=jnp.zeros(n_agents, dtype=jnp.float32),
            consumption=jnp.zeros(n_agents, dtype=jnp.float32),
            risk_aversion=jnp.ones(n_agents, dtype=jnp.float32) * 0.5,
            is_employed=jnp.zeros(n_agents, dtype=jnp.bool_),
            employer_id=jnp.full(n_agents, -1, dtype=jnp.int32),
        )

        firms = FirmState(
            sector_id=jnp.zeros(n_firms, dtype=jnp.int32),
            productivity=jnp.ones(n_firms, dtype=jnp.float32),
            capital=jnp.ones(n_firms, dtype=jnp.float32) * 100.0,
            labor_count=jnp.zeros(n_firms, dtype=jnp.float32),
            cash=jnp.ones(n_firms, dtype=jnp.float32) * 10000.0,
            inventory=jnp.zeros(n_firms, dtype=jnp.float32),
            debt=jnp.zeros(n_firms, dtype=jnp.float32),
            wage_offer=jnp.ones(n_firms, dtype=jnp.float32) * 10.0,
            price=jnp.ones(n_firms, dtype=jnp.float32) * 1.0,
        )

        market = MarketState(
            avg_price=jnp.array(1.0, dtype=jnp.float32),
            total_supply=jnp.array(0.0, dtype=jnp.float32),
            total_demand=jnp.array(0.0, dtype=jnp.float32),
            avg_wage=jnp.array(10.0, dtype=jnp.float32),
            unemployment_rate=jnp.array(0.0, dtype=jnp.float32),
            interest_rate=jnp.array(0.05, dtype=jnp.float32),
        )

        return cls(
            step=jnp.array(0, dtype=jnp.int32),
            agents=agents,
            firms=firms,
            market=market,
            government_balance=jnp.array(0.0, dtype=jnp.float32),
            tax_rate=jnp.array(0.0, dtype=jnp.float32),
            gdp=jnp.array(0.0, dtype=jnp.float32),
        )
