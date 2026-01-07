import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# check_step4.py
import jax_bootstrap  # noqa: F401
import os
from datetime import datetime

import pandas as pd

from polisyos.fabric.io.db import SimulationDB
from polisyos.ir.contract import (
    PolicyRequestIR, PolicyEntity, Intervention, TargetSelector, SelectorPredicate,
    SimulationParameters
)
from polisyos.ir.types import TranslatableString, EntityType, SelectorOperator
from polisyos.scientist.orchestrator.workflow import build_workflow


def setup_baseline_data() -> None:
    if os.path.exists("integration.duckdb"):
        os.remove("integration.duckdb")
    db = SimulationDB("integration.duckdb")
    n_agents = 10
    df = pd.DataFrame(
        {
            "run_id": ["baseline_2023"] * n_agents,
            "step": [0] * n_agents,
            "agent_id": list(range(n_agents)),
            "age": [30] * n_agents,
            "income": [1000.0] * n_agents,
            "savings": [0.0] * n_agents,
            "is_employed": [True] * n_agents,
        }
    )
    db.conn.execute("INSERT INTO agents_snapshot SELECT * FROM df")
    db.close()

def create_test_ir(rate: float):
    return PolicyRequestIR(
        project_name=TranslatableString(en="Test Run", ua="Тест"),
        schema_version="1.0",
        generated_at=datetime.utcnow().isoformat(),
        generator={"name": "policy-engine", "version": "0.1.0"},
        currency="USD",
        time_unit="year",
        price_base_year=2024,
        simulation_params=SimulationParameters(scope_years=1),
        scenarios={"random_seed": 7, "shocks": [], "timeline": {"start_year": 2024, "end_year": 2024}},
        entities=[
            PolicyEntity(id="a", entity_type=EntityType.AGENT, name=TranslatableString(en="A", ua="A"))
        ],
        interventions=[
            Intervention(
                id="sub1",
                name=TranslatableString(en="Sub", ua="Суб"),
                target_selector=TargetSelector(
                    all_of=[SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="a")]
                ),
                mechanism_type="tax_subsidy",
                parameters={"rate": rate}
            )
        ],
        objectives=[],
        # Ставим жесткое ограничение на бюджет: не ниже -2000
        global_constraints={"min_balance": -2000.0}
    )

def main():
    setup_baseline_data()
    app = build_workflow()

    print("--- 🧪 Case 1: Valid Policy (Rate 0.1) ---")
    # При ставке 0.1 и доходе 1000 * 10 чел = 10000. Субсидия = 1000. Баланс = -1000.
    # Это больше -2000, должно пройти.
    ir_valid = create_test_ir(0.1)
    result_valid = app.invoke({
        "user_request": "Test valid policy with rate 0.1",
        "optimize": False,
        "max_repair_attempts": 0,
        "ir": ir_valid,
        "revision_count": 0,
        "simulation_results": None,
        "feedback": None
    })

    print("Verdict:", result_valid["feedback"]["verdict"])
    print("Stats:", result_valid["simulation_results"])
    assert result_valid["feedback"]["verdict"] == "APPROVE"

    print("\n--- 🧪 Case 2: Dangerous Policy (Rate 0.5) ---")
    # При ставке 0.5. Субсидия = 5000. Баланс = -5000.
    # Это меньше -2000, Губернатор должен отклонить.
    ir_invalid = create_test_ir(0.5)
    result_invalid = app.invoke({
        "user_request": "Test dangerous policy with rate 0.5",
        "optimize": False,
        "max_repair_attempts": 0,
        "ir": ir_invalid,
        "revision_count": 0,
        "simulation_results": None,
        "feedback": None
    })

    print("Verdict:", result_invalid["feedback"]["verdict"])
    issues = result_invalid["feedback"]["issues"]
    print("Reason:", issues[0]["message"] if issues else "No issues")
    assert result_invalid["feedback"]["verdict"] == "REJECT"

    print("\n✅ Step 4 Complete: Orchestrator logic is working!")

if __name__ == "__main__":
    main()
