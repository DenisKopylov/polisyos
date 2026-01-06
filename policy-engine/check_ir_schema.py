import json

from loguru import logger
from pydantic import ValidationError

from src.policy_ir.contract import Intervention, PolicyRequestIR
from src.policy_ir.types import TranslatableString

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
        # tax_subsidy без rate - это должно упасть
        bad_intervention = Intervention(
            id="bad_tax_cut",
            name=TranslatableString(en="Bad Cut", ua="Погана знижка"),
            target_selector={"all_of": [{"field": "id", "operator": "==", "value": "all"}]},
            mechanism_type="tax_subsidy",
            parameters={"amount": 1000},  # ОШИБКА: нужен rate, а не amount
        )
    except ValidationError as e:
        logger.info("✅ Caught expected validation error:")
        # Выводим ошибку так, как ее увидит LLM
        error_json = e.json(include_url=False)
        print(f"\n{error_json}\n")

        # Проверяем, что сообщение понятное
        if "requires parameter 'rate'" in str(e):
            logger.info("✅ Error message is descriptive (LLM can fix this).")
        else:
            logger.error("❌ Error message is too vague!")

    # 3. Тест успешного создания
    logger.info("Testing valid IR creation...")
    try:
        valid_ir = PolicyRequestIR(
            project_name=TranslatableString(en="SME Support", ua="Підтримка МСБ"),
            schema_version="1.0",
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
