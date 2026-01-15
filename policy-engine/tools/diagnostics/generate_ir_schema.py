import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import json

from loguru import logger
from pydantic import ValidationError

from polisyos.ir.surface import PolicySurfaceIR
from polisyos.ir.types import SelectorOperator
from polisyos.ir.validation import build_validation_report

# IMPORTS HACK


def main():
    logger.info("📜 Generating JSON Schema for LLM...")

    # 1. Генерация схемы
    schema = PolicySurfaceIR.model_json_schema()
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
        PolicySurfaceIR(
            semantic={
                "context_snapshot_ref": "sha256:" + "0" * 64,
                "interventions": [
                    {
                        "intervention_id": "bad_tax_cut",
                        "kind": "tax_subsidy",
                        "target": {
                            "kind": "predicate",
                            "field": "id",
                            "operator": SelectorOperator.IN,
                            "value": "all",
                        },
                        "schedule": {"start_step": 0, "duration_steps": 1},
                        "params": {"rate": "0.1"},
                    }
                ],
            }
        )
    except ValidationError as e:
        logger.info("✅ Caught expected validation error:")
        # Выводим ошибку так, как ее увидит LLM (self-healing report)
        report = build_validation_report(e)
        print(f"\n{report.model_dump_json(indent=2)}\n")

        # Проверяем, что сообщение понятное
        if "operator 'in' requires a non-empty list" in str(e):
            logger.info("✅ Error message is descriptive (LLM can fix this).")
        else:
            logger.error("❌ Error message is too vague!")

    # 3. Тест успешного создания
    logger.info("Testing valid IR creation...")
    try:
        valid_ir = PolicySurfaceIR(
            semantic={
                "context_snapshot_ref": "sha256:" + "0" * 64,
                "interventions": [
                    {
                        "intervention_id": "it_tax_break",
                        "kind": "tax_subsidy",
                        "target": {
                            "kind": "predicate",
                            "field": "sector",
                            "operator": "==",
                            "value": "IT",
                        },
                        "schedule": {"start_step": 0, "duration_steps": 1},
                        "params": {"rate": "0.05"},
                    }
                ],
                "objectives": [],
                "constraints": [],
            }
        )
        logger.info("✅ Valid IR created successfully.")
    except ValidationError as e:
        logger.error(f"❌ Valid IR failed: {e}")


if __name__ == "__main__":
    main()
