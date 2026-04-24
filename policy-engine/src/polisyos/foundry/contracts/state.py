"""Define the JAX-compatible Foundry state bundles threaded through runtime execution."""

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float, Int

from polisyos.foundry.agent_sim.distributions import DistributionState


@chex.dataclass(frozen=True)
class ProcurementGraphState:
    """JAX state for the firm-level procurement multiplex graph.

    All fields are JAX arrays so the graph can be scanned inside simulation
    loops without leaving the compiled execution path.
    """

    senders: Int[Array, n_edges]
    receivers: Int[Array, n_edges]
    weights: Float[Array, n_edges]
    edge_types: Int[Array, n_edges]
    active: Bool[Array, n_edges]
    n_nodes: Int[Array, ""]
    last_update_step: Int[Array, ""]

    @classmethod
    def empty(cls, n_nodes: int, *, n_edges: int = 0) -> ProcurementGraphState:
        return cls(
            senders=jnp.zeros((n_edges,), dtype=jnp.int32),
            receivers=jnp.zeros((n_edges,), dtype=jnp.int32),
            weights=jnp.zeros((n_edges,), dtype=jnp.float32),
            edge_types=jnp.zeros((n_edges,), dtype=jnp.int32),
            active=jnp.zeros((n_edges,), dtype=jnp.bool_),
            n_nodes=jnp.array(n_nodes, dtype=jnp.int32),
            last_update_step=jnp.array(-1, dtype=jnp.int32),
        )


@chex.dataclass(frozen=True)
class AgentSimRuntimeState:
    """Runtime-only agent-simulation state attached to `GlobalState`.

    This bundle keeps mutable simulation auxiliaries such as the RNG key,
    procurement graph, and household distribution summaries outside the core
    policy state fields.
    """

    rng_key: chex.PRNGKey
    procurement_graph: ProcurementGraphState
    household_distribution: DistributionState

    @classmethod
    def empty(
        cls,
        n_agents: int,
        n_firms: int,
        *,
        seed: int = 0,
        n_quantiles: int = 10,
    ) -> AgentSimRuntimeState:
        return cls(
            rng_key=jax.random.PRNGKey(int(seed)),
            procurement_graph=ProcurementGraphState.empty(n_firms),
            household_distribution=DistributionState.empty(
                n_agents,
                n_quantiles=n_quantiles,
            ),
        )


@chex.dataclass(frozen=True)
class FeedbackState:
    """Compact fixed-point vector attached to `GlobalState` during feedback solve."""

    active: Bool[Array, n_feedback]
    values: Float[Array, n_feedback]
    scales: Float[Array, n_feedback]
    lower_bounds: Float[Array, n_feedback]
    upper_bounds: Float[Array, n_feedback]
    weights: Float[Array, n_feedback]
    noise_estimate: Float[Array, n_feedback]

    @property
    def size(self) -> int:
        return self.values.shape[0]

    @classmethod
    def empty(cls, n_feedback: int) -> FeedbackState:
        return cls(
            active=jnp.ones((n_feedback,), dtype=jnp.bool_),
            values=jnp.zeros((n_feedback,), dtype=jnp.float32),
            scales=jnp.ones((n_feedback,), dtype=jnp.float32),
            lower_bounds=jnp.full((n_feedback,), -jnp.inf, dtype=jnp.float32),
            upper_bounds=jnp.full((n_feedback,), jnp.inf, dtype=jnp.float32),
            weights=jnp.ones((n_feedback,), dtype=jnp.float32),
            noise_estimate=jnp.zeros((n_feedback,), dtype=jnp.float32),
        )


# --- 1. ЛЮДИ (Households) ---
@chex.dataclass(frozen=True)
class AgentState:
    """Per-agent household state stored as aligned JAX arrays."""

    # Active mask: True means the agent participates in the simulation.
    active: Bool[Array, n_agents]

    # Демография и Навыки
    age: Int[Array, n_agents]
    skill_level: Float[Array, n_agents]  # Влияет на зарплату

    # Финансы
    income: Float[Array, n_agents]
    reported_income: Float[Array, n_agents]
    savings: Float[Array, n_agents]
    consumption: Float[Array, n_agents]  # Сколько потратил
    risk_aversion: Float[Array, n_agents]

    # Работа
    is_employed: Bool[Array, n_agents]
    employer_id: Int[Array, n_agents]  # ID фирмы (0..M-1) или -1
    household_cell_id: Int[Array, n_agents] | None = None

    @property
    def size(self) -> int:
        return self.income.shape[0]


# --- 2. БИЗНЕС (Firms) ---
@chex.dataclass(frozen=True)
class FirmState:
    """Per-firm production, balance-sheet, and placement state arrays."""

    # Статика
    sector_id: Int[Array, n_firms]  # 0=IT, 1=Agro...
    productivity: Float[Array, n_firms]  # Технологичность (A)

    # Производственные факторы
    capital: Float[Array, n_firms]  # Станки/Софт (K)
    labor_count: Float[Array, n_firms]  # Текущий штат (L)

    # Финансы
    cash: Float[Array, n_firms]  # Деньги на зарплаты
    inventory: Float[Array, n_firms]  # Товары на складе
    debt: Float[Array, n_firms]  # Долги

    # Рынок
    wage_offer: Float[Array, n_firms]  # Зарплатное предложение
    price: Float[Array, n_firms]  # Цена товара фирмы
    active: Bool[Array, n_firms] | None = None
    firm_id: Int[Array, n_firms] | None = None
    cell_id: Int[Array, n_firms] | None = None
    firm_type_id: Int[Array, n_firms] | None = None

    @property
    def size(self) -> int:
        return self.capital.shape[0]


# --- 3. РЫНОК (Macro) ---
@chex.dataclass(frozen=True)
class MarketState:
    """Scalar macro aggregates shared across the simulation state."""

    # Агрегаты
    avg_price: Float[Array, ""]  # CPI (Индекс цен)
    total_supply: Float[Array, ""]  # Всего товаров
    total_demand: Float[Array, ""]  # Всего денег у покупателей

    avg_wage: Float[Array, ""]
    unemployment_rate: Float[Array, ""]
    interest_rate: Float[Array, ""]  # Ставка ЦБ


@chex.dataclass(frozen=True)
class CellState:
    """Per-cell regional/sectoral aggregates represented as JAX arrays."""

    active: Bool[Array, n_cells]
    region_code: Int[Array, n_cells]
    sector_id: Int[Array, n_cells]
    population: Float[Array, n_cells]
    employment: Float[Array, n_cells]
    output: Float[Array, n_cells]
    distress_score: Float[Array, n_cells]
    public_service_index: Float[Array, n_cells]
    firm_count: Float[Array, n_cells] | None = None

    @property
    def size(self) -> int:
        return self.population.shape[0]

    @classmethod
    def empty(cls, n_cells: int) -> CellState:
        return cls(
            active=jnp.ones(n_cells, dtype=jnp.bool_),
            region_code=jnp.zeros(n_cells, dtype=jnp.int32),
            sector_id=jnp.zeros(n_cells, dtype=jnp.int32),
            population=jnp.zeros(n_cells, dtype=jnp.float32),
            employment=jnp.zeros(n_cells, dtype=jnp.float32),
            output=jnp.zeros(n_cells, dtype=jnp.float32),
            distress_score=jnp.zeros(n_cells, dtype=jnp.float32),
            public_service_index=jnp.zeros(n_cells, dtype=jnp.float32),
            firm_count=jnp.zeros(n_cells, dtype=jnp.float32),
        )


@chex.dataclass(frozen=True)
class HouseholdCellState:
    """Per-household-cell welfare aggregates used by transfer mechanisms."""

    active: Bool[Array, n_household_cells]
    cell_id: Int[Array, n_household_cells]
    household_count: Float[Array, n_household_cells]
    disposable_income: Float[Array, n_household_cells]
    poverty_rate: Float[Array, n_household_cells]
    transfer_intensity: Float[Array, n_household_cells]

    @property
    def size(self) -> int:
        return self.household_count.shape[0]

    @classmethod
    def empty(cls, n_household_cells: int) -> HouseholdCellState:
        return cls(
            active=jnp.ones(n_household_cells, dtype=jnp.bool_),
            cell_id=jnp.zeros(n_household_cells, dtype=jnp.int32),
            household_count=jnp.zeros(n_household_cells, dtype=jnp.float32),
            disposable_income=jnp.zeros(n_household_cells, dtype=jnp.float32),
            poverty_rate=jnp.zeros(n_household_cells, dtype=jnp.float32),
            transfer_intensity=jnp.zeros(n_household_cells, dtype=jnp.float32),
        )


# --- 4. МИР (Global State) ---
@chex.dataclass(frozen=True)
class GlobalState:
    """Top-level Foundry execution state passed through compiled programs.

    The state combines agent, firm, market, and optional multi-scale cell
    tensors plus scalar fiscal controls. All fields are JAX-compatible so the
    full state can be transformed by `jit`, `scan`, and checkpointing flows.
    """

    step: Int[Array, ""]
    agents: AgentState
    firms: FirmState
    market: MarketState

    government_balance: Float[Array, ""]
    tax_rate: Float[Array, ""]
    gdp: Float[Array, ""]
    cells: CellState | None = None
    household_cells: HouseholdCellState | None = None
    agent_sim_runtime: AgentSimRuntimeState | None = None
    feedback_state: FeedbackState | None = None

    @classmethod
    def empty(
        cls,
        n_agents: int,
        n_firms: int,
        *,
        n_cells: int = 0,
        n_household_cells: int = 0,
    ) -> GlobalState:
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
            household_cell_id=jnp.full(n_agents, -1, dtype=jnp.int32),
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
            active=jnp.ones(n_firms, dtype=jnp.bool_),
            firm_id=jnp.arange(n_firms, dtype=jnp.int32),
            cell_id=jnp.full(n_firms, -1, dtype=jnp.int32),
            firm_type_id=jnp.zeros(n_firms, dtype=jnp.int32),
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
            cells=CellState.empty(n_cells) if n_cells > 0 else None,
            household_cells=HouseholdCellState.empty(n_household_cells)
            if n_household_cells > 0
            else None,
            agent_sim_runtime=None,
            feedback_state=None,
            government_balance=jnp.array(0.0, dtype=jnp.float32),
            tax_rate=jnp.array(0.0, dtype=jnp.float32),
            gdp=jnp.array(0.0, dtype=jnp.float32),
        )
