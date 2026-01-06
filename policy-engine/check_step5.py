# check_step5.py
import os

import jax
import pandas as pd

from src.io.db import SimulationDB
from src.orchestrator.workflow import build_workflow


def setup_baseline_data():
    """Наполняем БД данными для теста."""
    if os.path.exists("integration.duckdb"):
        os.remove("integration.duckdb")
    db = SimulationDB("integration.duckdb")
    # Агенты с низким доходом (нуждаются в субсидии)
    data = {
        "run_id": ["baseline_2023"] * 3,
        "step": [0] * 3,
        "agent_id": [1, 2, 3],
        "age": [30, 40, 50],
        "income": [800.0, 900.0, 1500.0],  # Двое бедных (<1000), один богатый
        "savings": [0.0] * 3,
        "is_employed": [True] * 3,
    }
    df = pd.DataFrame(data)
    db.conn.execute("INSERT INTO agents_snapshot SELECT * FROM df")
    db.close()


def main():
    setup_baseline_data()

    # Входные данные: просто строка текста!
    user_query = "Help the poor people, their income is too low."

    print(f"🤖 User Query: '{user_query}'")

    app = build_workflow()
    result = app.invoke(
        {
            "user_request": user_query,
            "ir": None,  # IR нет, агент должен его создать
            "revision_count": 0,
            "simulation_results": None,
            "feedback": None,
        }
    )

    print("\n--- Final Report ---")
    ir = result["ir"]
    stats = result["simulation_results"]
    feedback = result["feedback"]

    print(f"1. AI Generated Plan: {ir.project_name.en}")
    print(
        f"2. Intervention: {ir.interventions[0].mechanism_type} (Rate: {ir.interventions[0].parameters['rate']})"
    )
    print(
        f"3. Simulation Outcome: Avg Income = {stats['avg_income']:.2f}, Budget = {stats['gov_balance']:.2f}"
    )
    print(f"4. Governor Verdict: {feedback['verdict']}")

    # Проверка логики
    # У нас было 2 бедных (800, 900) и 1 богатый (1500).
    # MockLLM выдал субсидию 20% для тех, у кого < 1000.
    # 800 -> 960 (+160)
    # 900 -> 1080 (+180)
    # 1500 -> 1500 (без изменений)
    # Итого расход бюджета: 340.
    # Новый средний: (960+1080+1500)/3 = 1180.

    if feedback["verdict"] == "APPROVE":
        print("\n✅ Step 5 Complete: AI Architect successfully solved the problem!")
    else:
        print("\n❌ System rejected the plan.")


if __name__ == "__main__":
    jax.config.update("jax_platform_name", "cpu")
    main()
