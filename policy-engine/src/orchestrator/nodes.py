# src/orchestrator/nodes.py
import jax
import jax.numpy as jnp

from src.io.db import SimulationDB
from src.orchestrator.data_loader import load_initial_state  # <--- Импорт
from src.orchestrator.optimizer import optimize_mechanisms  # <--- Импорт
from src.orchestrator.registry import create_mechanism
from src.orchestrator.state import ExperimentState, GovernorFeedback
from src.udf.engine import UDFEngine


def simulator_node(state: ExperimentState) -> ExperimentState:
    """
    Запускает симуляцию на РЕАЛЬНЫХ данных из UDF.
    """
    print("   [Simulator] Initializing UDF connection...")

    # 1. Подключение к данным
    # В проде это будет dependency injection. Сейчас хардкод пути.
    db = SimulationDB("integration.duckdb")
    udf = UDFEngine(db)  # GraphStore пока не нужен для загрузки плоского состояния

    ir = state["ir"]

    # 2. Загрузка начального состояния
    # Предполагаем, что у нас есть "baseline" прогон, с которого мы стартуем.
    # Его ID можно передать в ir.simulation_params или хардкодом.
    baseline_run_id = "baseline_2023"

    try:
        world_state = load_initial_state(udf, baseline_run_id, step=0)
    except Exception as e:
        print(f"   [Simulator] ❌ Error loading data: {e}")
        # Возвращаем ошибку в state, чтобы workflow мог корректно упасть
        return {**state, "simulation_results": {"error": str(e)}, "feedback": {"verdict": "REJECT"}}

    n_agents = world_state.agents.income.shape[0]
    print(f"   [Simulator] Loaded {n_agents} agents from DB.")

    # 3. Сборка механизмов
    key = jax.random.PRNGKey(ir.simulation_params.random_seed)
    mechanisms = []
    for intervention in ir.interventions:
        # Важно: передаем реальное число агентов
        mech = create_mechanism(intervention, n_agents)
        mechanisms.append(mech)

    # --- НОВАЯ ЛОГИКА: ОПТИМИЗАЦИЯ ---
    # Проверяем, включен ли режим "Scientist"
    # (Для MVP включим его всегда или по флагу в state)
    do_optimize = True

    if do_optimize:
        min_balance = ir.global_constraints.get("min_balance", -1000.0)
        mechanisms = optimize_mechanisms(
            mechanisms,
            world_state,
            key,
            steps=200,
            learning_rate=0.01,  # Более консервативные параметры
            min_balance=min_balance,
        )

        # Важно: нужно обновить IR новыми параметрами!
        # (Синхронизация JAX -> JSON)
        new_interventions = []
        for i, mech in enumerate(mechanisms):
            orig_intervention = ir.interventions[i]
            # Хак для MVP: знаем, что у TaxSubsidy есть rate
            if hasattr(mech, "rate"):
                # Конвертируем JAX array -> float
                new_rate = float(mech.rate)
                # Обновляем параметры в IR объекте
                orig_intervention.parameters["rate"] = new_rate
            new_interventions.append(orig_intervention)

        # Обновляем IR в стейте
        state["ir"].interventions = new_interventions

    # --- ФИНАЛЬНЫЙ ПРОГОН (уже с оптимизированными параметрами) ---
    for mech in mechanisms:
        world_state = mech(world_state, key)

    # 5. Результаты
    results = {
        "avg_income": float(jnp.mean(world_state.agents.income)),
        "gov_balance": float(world_state.government_balance),
        "n_agents": n_agents,
    }

    # Закрываем соединение (важно для DuckDB)
    db.close()

    return {**state, "simulation_results": results}


def governor_node(state: ExperimentState) -> ExperimentState:
    """Узел Губернатора: Проверяет ограничения."""
    print("   [Governor] Reviewing results...")
    results = state.get("simulation_results", {})

    # Fail-safe если симулятор упал
    if "error" in results:
        return {
            **state,
            "feedback": GovernorFeedback(
                verdict="REJECT", comments=[f"Simulation Error: {results['error']}"]
            ),
        }

    ir = state["ir"]
    comments = []
    verdict = "APPROVE"

    min_balance = ir.global_constraints.get("min_balance", -1e9)
    if results["gov_balance"] < min_balance:
        verdict = "REJECT"
        comments.append(f"Budget deficit too high: {results['gov_balance']} < {min_balance}")

    return {**state, "feedback": GovernorFeedback(verdict=verdict, comments=comments)}
