# src/orchestrator/nodes.py
import jax
import jax.numpy as jnp
from src.orchestrator.state import ExperimentState, GovernorFeedback
from src.orchestrator.registry import create_mechanism
from src.domain.state import GlobalState, AgentState, FirmState, MarketState

# --- Mock Simulation Setup ---
# В реальности это будет браться из UDF
def get_initial_state(n_agents=100) -> GlobalState:
    return GlobalState(
        agents=AgentState(
            age=jnp.ones(n_agents) * 30,
            skill_level=jnp.ones(n_agents),
            income=jnp.ones(n_agents) * 1000.0,
            savings=jnp.zeros(n_agents),
            consumption=jnp.zeros(n_agents),
            is_employed=jnp.ones(n_agents, dtype=bool),
            employer_id=jnp.full(n_agents, -1, dtype=jnp.int32),
        ),
        firms=FirmState(
            sector_id=jnp.zeros(10, dtype=jnp.int32),
            productivity=jnp.ones(10),
            capital=jnp.ones(10) * 100.0,
            labor_count=jnp.zeros(10),
            cash=jnp.ones(10) * 10000.0,
            inventory=jnp.zeros(10),
            debt=jnp.zeros(10),
            wage_offer=jnp.ones(10) * 10.0,
            price=jnp.ones(10),
        ),
        market=MarketState(
            avg_price=1.0,
            total_supply=0.0,
            total_demand=0.0,
            avg_wage=10.0,
            unemployment_rate=0.0,
            interest_rate=0.05,
        ),
        government_balance=0.0,
        gdp=0.0,
        step=0
    )

def simulator_node(state: ExperimentState) -> ExperimentState:
    """Узел Симулятора: Запускает мир на основе IR."""
    print("   [Simulator] Running simulation...")
    ir = state["ir"]

    # 1. Инициализация
    # Пока хардкодим 10 агентов для теста
    n_agents = 10
    world_state = get_initial_state(n_agents)
    key = jax.random.PRNGKey(ir.simulation_params.random_seed)

    # 2. Сборка механизмов из IR
    mechanisms = []
    for intervention in ir.interventions:
        mech = create_mechanism(intervention, n_agents)
        mechanisms.append(mech)

    # 3. Прогон (пока 1 шаг для MVP)
    # В реальности тут будет цикл по времени scope_years
    for mech in mechanisms:
        world_state = mech(world_state, key)

    # 4. Сбор метрик
    # Допустим, нас интересует средний доход и баланс бюджета
    results = {
        "avg_income": float(jnp.mean(world_state.agents.income)),
        "gov_balance": float(world_state.government_balance)
    }

    return {**state, "simulation_results": results}

def governor_node(state: ExperimentState) -> ExperimentState:
    """Узел Губернатора: Проверяет ограничения."""
    print("   [Governor] Reviewing results...")
    results = state["simulation_results"]
    ir = state["ir"]

    comments = []
    verdict = "APPROVE"

    # Проверка 1: Бюджет не должен уйти в глубокий минус (если есть ограничение)
    # Пример: global_constraints={"min_balance": -5000}
    min_balance = ir.global_constraints.get("min_balance", -1e9)
    if results["gov_balance"] < min_balance:
        verdict = "REJECT"
        comments.append(f"Budget deficit too high: {results['gov_balance']} < {min_balance}")

    # Проверка 2: Инварианты (sanity check)
    if results["avg_income"] < 0:
        verdict = "REJECT"
        comments.append("Average income is negative! Model breakdown.")

    return {
        **state,
        "feedback": GovernorFeedback(verdict=verdict, comments=comments)
    }
