# polisyos/orchestrator/nodes.py
import uuid

import jax
import jax.numpy as jnp

from polisyos.fabric.io.db import SimulationDB
from polisyos.foundry.registry import create_mechanism
from polisyos.scientist.orchestrator.data_loader import load_initial_state  # <--- Импорт
from polisyos.scientist.orchestrator.optimizer import optimize_mechanisms  # <--- Импорт
from polisyos.scientist.orchestrator.audit import append_audit
from polisyos.scientist.orchestrator.decision_packet import build_decision_packet, save_decision_packet
from polisyos.scientist.orchestrator.run_record import ReproMode, build_run_record, save_run_record_json
from polisyos.scientist.orchestrator.state import ExperimentState, GovernorFeedback
from polisyos.ir.validation import ValidationIssue
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.fabric.io.graph_store import GraphStore


def simulator_node(state: ExperimentState) -> ExperimentState:
    """
    Запускает симуляцию на РЕАЛЬНЫХ данных из UDF.
    """
    print("   [Simulator] Initializing UDF connection...")

    # 1. Подключение к данным
    # В проде это будет dependency injection. Сейчас хардкод пути.
    db_path = state.get("db_path") or "integration.duckdb"
    graph_path = state.get("graph_path")
    db = SimulationDB(db_path)
    graph = GraphStore(str(graph_path)) if graph_path else None
    udf = UDFEngine(db, graph) if graph is not None else UDFEngine(db)

    ir = state.get("ir")

    if ir is None:
        issue = ValidationIssue(
            loc=["ir"],
            message=state.get("last_error") or "IR is missing or invalid",
            error_type="validation",
            input_value=None,
        ).model_dump()
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        new_state = {**state, "feedback": feedback}
        return append_audit(new_state, "simulator", "skip_invalid_ir", {"issue": issue})

    # 2. Prepare RunRecord (contract + reproducibility)
    run_id = state.get("run_id") or str(uuid.uuid4())[:8]
    repro_mode_raw = state.get("repro_mode") or "fast"
    repro_mode = ReproMode(repro_mode_raw)
    parent_run_id = state.get("parent_run_id")
    run_record = build_run_record(
        run_id=run_id,
        parent_run_id=parent_run_id,
        seed=ir.simulation_params.random_seed,
        repro_mode=repro_mode,
        generator={"name": ir.generator.name, "version": ir.generator.version},
    )
    db.save_run_record(run_record)
    save_run_record_json(run_record)
    state["run_id"] = run_id
    state["parent_run_id"] = parent_run_id
    state["repro_mode"] = repro_mode.value
    state["run_record"] = run_record

    # 3. Загрузка начального состояния
    # Предполагаем, что у нас есть "baseline" прогон, с которого мы стартуем.
    # Его ID можно передать в ir.simulation_params или хардкодом.
    baseline_run_id = state.get("baseline_run_id") or "baseline_2023"

    try:
        world_state = load_initial_state(udf, baseline_run_id, step=0)
    except Exception as e:
        print(f"   [Simulator] ❌ Error loading data: {e}")
        # Возвращаем ошибку в state, чтобы workflow мог корректно упасть
        issue = ValidationIssue(
            loc=["data"],
            message=str(e),
            error_type="data",
            input_value=None,
        ).model_dump()
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        new_state = {**state, "simulation_results": {"error": str(e)}, "feedback": feedback}
        return append_audit(new_state, "simulator", "data_load_failed", {"error": str(e)})

    n_agents = world_state.agents.income.shape[0]
    print(f"   [Simulator] Loaded {n_agents} agents from DB.")

    # 4. Сборка механизмов
    key = jax.random.PRNGKey(ir.simulation_params.random_seed)
    mechanisms = []
    for intervention in ir.interventions:
        # Важно: передаем реальное число агентов
        mech = create_mechanism(intervention, n_agents)
        mechanisms.append(mech)

    # --- НОВАЯ ЛОГИКА: ОПТИМИЗАЦИЯ ---
    # Проверяем, включен ли режим "Scientist"
    # (Для MVP включим его всегда или по флагу в state)
    do_optimize = state.get("optimize")
    if do_optimize is None:
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
        key, step_key = jax.random.split(key)
        world_state, key = mech(world_state, step_key)

    # 5. Результаты
    results = {
        "avg_income": float(jnp.mean(world_state.agents.income)),
        "gov_balance": float(world_state.government_balance),
        "n_agents": n_agents,
    }

    # Закрываем соединение (важно для DuckDB)
    db.close()

    new_state = {**state, "simulation_results": results}
    return append_audit(new_state, "simulator", "simulation_completed", results)


def governor_node(state: ExperimentState) -> ExperimentState:
    """Узел Губернатора: Проверяет ограничения."""
    print("   [Governor] Reviewing results...")
    results = state.get("simulation_results", {})

    # If simulator already requested revision, pass through
    if state.get("feedback") and state["feedback"]["verdict"] == "NEEDS_REVISION":
        return append_audit(state, "governor", "needs_revision", {"reason": "invalid_ir"})

    # Fail-safe если симулятор упал
    if "error" in results:
        issue = ValidationIssue(
            loc=["simulation"],
            message=f"Simulation Error: {results['error']}",
            error_type="logic",
            input_value=results.get("error"),
        ).model_dump()
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        new_state = {**state, "feedback": feedback}
        return append_audit(new_state, "governor", "reject", {"reason": "simulation_error"})

    ir = state["ir"]
    issues: list[dict] = []
    verdict = "APPROVE"

    min_balance = ir.global_constraints.get("min_balance", -1e9)
    if results["gov_balance"] < min_balance:
        verdict = "NEEDS_REVISION"
        issues.append(
            ValidationIssue(
                loc=["global_constraints", "min_balance"],
                message=f"Budget deficit too high: {results['gov_balance']} < {min_balance}",
                error_type="policy",
                input_value=results["gov_balance"],
            ).model_dump()
        )

    max_attempts = state.get("max_repair_attempts")
    if max_attempts is None:
        max_attempts = 3
    if verdict == "NEEDS_REVISION" and (state.get("revision_count") or 0) >= max_attempts:
        verdict = "REJECT"
        issues.append(
            {
                "issue_id": "MAX_REPAIR_ATTEMPTS",
                "severity": "ERROR",
                "component": "logic",
                "message": f"Max repair attempts reached: {max_attempts}",
                "recommended_fix": "Manual intervention required",
                "blocking": True,
            }
        )

    feedback: GovernorFeedback = {"verdict": verdict, "issues": issues}
    new_state = {**state, "feedback": feedback}
    run_record = new_state.get("run_record")
    if run_record is not None:
        packet = build_decision_packet(new_state, run_record)
        save_decision_packet(packet)
    return append_audit(new_state, "governor", "verdict", {"verdict": verdict, "issues": issues})
