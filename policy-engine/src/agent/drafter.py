# src/agent/drafter.py
import json

from src.agent.prompts import get_system_prompt
from src.orchestrator.state import ExperimentState
from src.policy_ir.contract import PolicyRequestIR


# --- Fake LLM for Testing (чтобы не требовать API Key) ---
class MockLLM:
    def invoke(self, prompt: str) -> str:
        """Эмулирует ответ GPT-4, возвращая валидный JSON."""
        print(f"   [MockLLM] 'Thinking' about: {prompt[:50]}...")

        # Возвращаем заранее заготовленный JSON, который решает задачу "уменьшить бедность"
        # В реальности здесь будет вызов OpenAI / Anthropic
        return """
        {
          "project_name": {"en": "Anti-Poverty Act", "ua": "Боротьба з бідністю"},
          "schema_version": "1.0.0",
          "simulation_params": {
            "scope_years": 1,
            "time_frequency": "M",
            "start_date": "2024-01-01",
            "random_seed": 42
          },
          "entities": [
            {"id": "poor_group", "entity_type": "agent", "name": {"en": "Poor", "ua": "Бідні"}}
          ],
          "interventions": [
            {
              "id": "help_poor",
              "name": {"en": "Direct Aid", "ua": "Допомога"},
              "target_selector": {
                "logic": "AND",
                "predicates": [
                  {"field": "income", "operator": "<", "value": 1000.0}
                ]
              },
              "mechanism_type": "tax_subsidy",
              "parameters": {"rate": 0.2},
              "constraints": {}
            }
          ],
          "objectives": [
            {"metric_name": "avg_income", "direction": "maximize", "priority_weight": 1.0}
          ],
          "global_constraints": {"min_balance": -5000.0}
        }
        """


def drafter_node(state: ExperimentState) -> ExperimentState:
    """Узел Drafter: User Request -> Policy IR JSON."""
    print(f"   [Drafter] Processing request: '{state['user_request']}'")

    # 1. Готовим промпт
    system_prompt = get_system_prompt()
    user_prompt = f"USER REQUEST: {state['user_request']}"
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    # 2. Вызываем LLM (здесь можно заменить MockLLM на ChatOpenAI)
    llm = MockLLM()
    response_text = llm.invoke(full_prompt)

    # 3. Парсим и валидируем через Pydantic
    try:
        # Очистка от markdown если есть
        clean_json = response_text.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_json)

        # Pydantic валидация (самый важный шаг!)
        ir = PolicyRequestIR(**data)
        print("   [Drafter] ✅ Generated valid IR.")

    except Exception as e:
        print(f"   [Drafter] ❌ Failed to generate valid IR: {e}")
        # В реальной системе тут был бы цикл самокоррекции (Reflexion)
        raise e

    return {**state, "ir": ir}
