import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# check_step1.py
from datetime import datetime

from pydantic import ValidationError
from polisyos.ir.contract import PolicyRequestIR, PolicyEntity, Intervention, TargetSelector, SelectorPredicate
from polisyos.ir.types import TranslatableString, EntityType, SelectorOperator

def test_valid_ir():
    print("--- Test Valid IR ---")
    try:
        ir = PolicyRequestIR(
            project_name=TranslatableString(en="Test Project", ua="Тест"),
            schema_version="1.0",
            generated_at=datetime.utcnow().isoformat(),
            generator={"name": "policy-engine", "version": "0.1.0"},
            currency="USD",
            time_unit="year",
            price_base_year=2024,
            simulation_params={"scope_years": 5},
            scenarios={"random_seed": 7, "shocks": [], "timeline": {"start_year": 2024, "end_year": 2028}},
            entities=[
                PolicyEntity(
                    id="holding_inc",
                    entity_type=EntityType.AGENT,
                    name=TranslatableString(en="Holding", ua="Холдинг")
                ),
                PolicyEntity(
                    id="factory_a",
                    entity_type=EntityType.AGENT,
                    name=TranslatableString(en="Factory A", ua="Завод А"),
                    parent_id="holding_inc"  # Valid parent
                )
            ],
            interventions=[
                Intervention(
                    id="sub_1",
                    name=TranslatableString(en="Sub", ua="Субсидия"),
                    target_selector=TargetSelector(
                        all_of=[
                            SelectorPredicate(field="sector", operator=SelectorOperator.EQUALS, value="IT")
                        ]
                    ),
                    mechanism_type="tax_subsidy",
                    parameters={"rate": 0.2}
                )
            ],
            objectives=[]
        )
        print("✅ IR Validated Successfully!")
        print(f"Selector AST: {ir.interventions[0].target_selector.to_human_readable()}")
    except ValidationError as e:
        print(f"❌ Unexpected Error: {e}")

def test_cycle_ir():
    print("\n--- Test Cyclic Dependency ---")
    try:
        PolicyRequestIR(
            project_name=TranslatableString(en="Bad Project", ua="Тест"),
            schema_version="1.0",
            generated_at=datetime.utcnow().isoformat(),
            generator={"name": "policy-engine", "version": "0.1.0"},
            currency="USD",
            time_unit="year",
            price_base_year=2024,
            simulation_params={"scope_years": 1},
            scenarios={"random_seed": 7, "shocks": [], "timeline": {"start_year": 2024, "end_year": 2024}},
            entities=[
                PolicyEntity(id="a", entity_type="agent", name=TranslatableString(en="A", ua="A"), parent_id="b"),
                PolicyEntity(id="b", entity_type="agent", name=TranslatableString(en="B", ua="B"), parent_id="a")
            ],
            interventions=[],
            objectives=[]
        )
        print("❌ Failed to catch cycle!")
    except ValidationError as e:
        print("✅ Caught expected cycle error:")
        # Ищем наше сообщение об ошибке
        errors = e.errors()
        print(f"  -> {errors[0]['msg']}")

if __name__ == "__main__":
    test_valid_ir()
    test_cycle_ir()
