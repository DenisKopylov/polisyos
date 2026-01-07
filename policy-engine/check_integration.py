import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# check_integration.py
import os
from datetime import datetime

import jax_bootstrap  # noqa: F401
import jax
import pandas as pd

from polisyos.fabric.io.db import SimulationDB
from polisyos.scientist.orchestrator.workflow import build_workflow
from polisyos.ir.contract import (
    Intervention,
    PolicyEntity,
    PolicyRequestIR,
    SelectorPredicate,
    SimulationParameters,
    TargetSelector,
)
from polisyos.ir.types import EntityType, SelectorOperator, TranslatableString


def setup_baseline_data():
    """Создает БД и наполняет её 'историческими' данными."""
    if os.path.exists("integration.duckdb"):
        os.remove("integration.duckdb")

    db = SimulationDB("integration.duckdb")

    # Создаем 5 агентов с разным доходом
    # Агент 1-3: Бедные (500)
    # Агент 4-5: Богатые (2000)
    data = {
        "run_id": ["baseline_2023"] * 5,
        "step": [0] * 5,
        "agent_id": [1, 2, 3, 4, 5],
        "age": [25, 30, 35, 40, 45],
        "income": [500.0, 500.0, 500.0, 2000.0, 2000.0],
        "savings": [0.0] * 5,
        "is_employed": [True] * 5,
    }
    df = pd.DataFrame(data)

    # Сохраняем напрямую в таблицу
    db.conn.execute("INSERT INTO agents_snapshot SELECT * FROM df")
    print("💾 Baseline data injected: 5 agents (3 poor, 2 rich).")
    db.close()


def main():
    # 1. Готовим данные
    setup_baseline_data()

    # 2. Готовим IR (Субсидия 10%)
    ir = PolicyRequestIR(
        project_name=TranslatableString(en="Integration Test", ua="Тест"),
        schema_version="1.0",
        generated_at=datetime.utcnow().isoformat(),
        generator={"name": "policy-engine", "version": "0.1.0"},
        currency="USD",
        time_unit="year",
        price_base_year=2024,
        simulation_params=SimulationParameters(scope_years=1),
        scenarios={"random_seed": 7, "shocks": [], "timeline": {"start_year": 2024, "end_year": 2024}},
        entities=[
            PolicyEntity(
                id="pop", entity_type=EntityType.AGENT, name=TranslatableString(en="Pop", ua="Pop")
            )
        ],
        interventions=[
            Intervention(
                id="tax_sub",
                name=TranslatableString(en="Sub", ua="Sub"),
                target_selector=TargetSelector(
                    all_of=[SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="any")]
                ),
                mechanism_type="tax_subsidy",
                parameters={"rate": 0.1},  # 10% добавки к доходу
            )
        ],
        objectives=[],
        global_constraints={},
    )

    # 3. Запускаем Оркестратор
    app = build_workflow()
    print("\n🚀 Running Orchestrator with Real Data...")
    result = app.invoke(
        {
            "user_request": "Test policy simulation",
            "ir": ir,
            "optimize": False,  # keep deterministic: validate raw simulation, not auto-tuning
            "revision_count": 0,
            "simulation_results": None,
            "feedback": None,
        }
    )

    # 4. Проверка результатов
    stats = result["simulation_results"]
    print("📊 Results:", stats)

    # Простая математика:
    # Исходный средний доход: (500*3 + 2000*2) / 5 = 5500 / 5 = 1100
    # Субсидия 10%: +110
    # Ожидаемый новый доход: 1210

    assert stats["n_agents"] == 5, "Should load exactly 5 agents"
    assert abs(stats["avg_income"] - 1210.0) < 1.0, f"Expected 1210.0, got {stats['avg_income']}"

    print("\n✅ Integration Successful! JAX simulation used DuckDB data.")


if __name__ == "__main__":
    main()
