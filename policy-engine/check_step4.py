# check_step4.py
import jax
from src.policy_ir.contract import (
    PolicyRequestIR, PolicyEntity, Intervention, TargetSelector, SelectorPredicate,
    SimulationParameters
)
from src.policy_ir.types import TranslatableString, EntityType, SelectorOperator
from src.orchestrator.workflow import build_workflow

def create_test_ir(rate: float):
    return PolicyRequestIR(
        project_name=TranslatableString(en="Test Run", ua="Тест"),
        schema_version="1.0",
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
    app = build_workflow()

    print("--- 🧪 Case 1: Valid Policy (Rate 0.1) ---")
    # При ставке 0.1 и доходе 1000 * 10 чел = 10000. Субсидия = 1000. Баланс = -1000.
    # Это больше -2000, должно пройти.
    ir_valid = create_test_ir(0.1)
    result_valid = app.invoke({
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
    # JAX на CPU для тестов CI/Dev
    jax.config.update("jax_platform_name", "cpu")
    main()
