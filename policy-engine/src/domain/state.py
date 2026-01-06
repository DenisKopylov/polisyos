import chex
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float, Int


# --- 1. ЛЮДИ (Households) ---
@chex.dataclass(frozen=True)
class AgentState:
    # Демография и Навыки
    age: Int[Array, "n_agents"]
    skill_level: Float[Array, "n_agents"]  # Влияет на зарплату

    # Финансы
    income: Float[Array, "n_agents"]
    savings: Float[Array, "n_agents"]
    consumption: Float[Array, "n_agents"]  # Сколько потратил

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
    avg_price: float  # CPI (Индекс цен)
    total_supply: float  # Всего товаров
    total_demand: float  # Всего денег у покупателей

    avg_wage: float
    unemployment_rate: float
    interest_rate: float  # Ставка ЦБ


# --- 4. МИР (Global State) ---
@chex.dataclass(frozen=True)
class GlobalState:
    step: int
    agents: AgentState
    firms: FirmState
    market: MarketState

    government_balance: float
    gdp: float

    @classmethod
    def empty(cls, n_agents: int, n_firms: int) -> "GlobalState":
        # Инициализация дефолтными значениями
        agents = AgentState(
            age=jnp.zeros(n_agents, dtype=jnp.int32),
            skill_level=jnp.ones(n_agents, dtype=jnp.float32),
            income=jnp.zeros(n_agents, dtype=jnp.float32),
            savings=jnp.zeros(n_agents, dtype=jnp.float32),
            consumption=jnp.zeros(n_agents, dtype=jnp.float32),
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
            avg_price=1.0,
            total_supply=0.0,
            total_demand=0.0,
            avg_wage=10.0,
            unemployment_rate=0.0,
            interest_rate=0.05,
        )

        return cls(
            step=0, agents=agents, firms=firms, market=market, government_balance=0.0, gdp=0.0
        )
