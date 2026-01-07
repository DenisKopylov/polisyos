import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import json

from loguru import logger
from pydantic import ValidationError

from polisyos.ir.contract import Intervention, PolicyRequestIR
from polisyos.ir.types import TranslatableString
from polisyos.ir.validation import build_validation_report

# IMPORTS HACK


def main():
    logger.info("📜 Generating JSON Schema for LLM...")

    # 1. Генерация схемы
    schema = PolicyRequestIR.model_json_schema()
    schema_str = json.dumps(schema, indent=2)

    # Сохраняем схему (ее потом можно вставить в промпт)
    with open("policy_ir_schema.json", "w", encoding="utf-8") as f:
        f.write(schema_str)

    logger.info(f"✅ Schema generated: policy_ir_schema.json ({len(schema_str)} bytes)")

    # 2. Тест "Self-Healing" (Валидация бизнес-логики)
    logger.info("🛡 Testing Semantic Validation (Self-Healing check)...")

    try:
        # Пытаемся создать "сломанную" интервенцию
        # target_selector без условий - это должно упасть
        bad_intervention = Intervention(
            id="bad_tax_cut",
            name=TranslatableString(en="Bad Cut", ua="Погана знижка"),
            target_selector={"all_of": []},
            mechanism_type="tax_subsidy",
            parameters={"amount": 1000},
        )
    except ValidationError as e:
        logger.info("✅ Caught expected validation error:")
        # Выводим ошибку так, как ее увидит LLM (self-healing report)
        report = build_validation_report(e)
        print(f"\n{report.model_dump_json(indent=2)}\n")

        # Проверяем, что сообщение понятное
        if "TargetSelector must define at least one of all_of/any_of/not" in str(e):
            logger.info("✅ Error message is descriptive (LLM can fix this).")
        else:
            logger.error("❌ Error message is too vague!")

    # 3. Тест успешного создания
    logger.info("Testing valid IR creation...")
    try:
        valid_ir = PolicyRequestIR(
            project_name=TranslatableString(en="SME Support", ua="Підтримка МСБ"),
            schema_version="1.0",
            generated_at="2024-01-01T00:00:00",
            generator={"name": "policy-engine", "version": "0.1.0"},
            currency="USD",
            time_unit="year",
            price_base_year=2024,
            simulation_params={"scope_years": 3, "time_frequency": "M"},
            scenarios={"random_seed": 42, "shocks": [], "timeline": {"start_year": 2024, "end_year": 2026}},
            entities=[
                {
                    "id": "kyiv_region",
                    "entity_type": "infrastructure",
                    "name": {"en": "Kyiv Region", "ua": "Київська область"},
                }
            ],
            objectives=[],
            interventions=[
                {
                    "id": "it_tax_break",
                    "name": {"en": "IT Tax Break", "ua": "Податкові канікули IT"},
                    "target_selector": {
                        "all_of": [
                            {"field": "sector", "operator": "==", "value": "IT"}
                        ]
                    },
                    "mechanism_type": "tax_subsidy",
                    "parameters": {"rate": 0.05},  # ВЕРНО
                }
            ],
        )
        logger.info("✅ Valid IR created successfully.")
    except ValidationError as e:
        logger.error(f"❌ Valid IR failed: {e}")


if __name__ == "__main__":
    main()
