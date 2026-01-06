# src/agent/drafter.py
import json

from src.agent.prompts import get_system_prompt
from src.orchestrator.audit import append_audit
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
          "schema_version": "1.0",
          "simulation_params": {
            "scope_years": 1,
            "time_frequency": "M",
            "start_date": "2024-01-01",
            "random_seed": 42
          },
          "generator": {"name": "policy-engine", "version": "0.1.0"},
          "currency": "USD",
          "time_unit": "year",
          "price_base_year": 2024,
          "scenarios": {
            "random_seed": 42,
            "shocks": [],
            "timeline": {"start_year": 2024, "end_year": 2024}
          },
          "entities": [
            {"id": "poor_group", "entity_type": "agent", "name": {"en": "Poor", "ua": "Бідні"}}
          ],
          "interventions": [
            {
              "id": "help_poor",
              "name": {"en": "Direct Aid", "ua": "Допомога"},
              "target_selector": {
                "all_of": [
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
    user_request = state.get("user_request")
    if not user_request:
        if state.get("ir") is not None:
            print("   [Drafter] Skipping: IR already provided.")
            return append_audit(state, "drafter", "skip_existing_ir", {"reason": "missing_user_request"})
        state = {**state, "last_error": "Missing required field: user_request", "ir": None}
        return append_audit(state, "drafter", "invalid_input", {"reason": "missing_user_request"})

    if state.get("ir") is not None and not (
        state.get("feedback") and state["feedback"].get("verdict") == "NEEDS_REVISION"
    ):
        print(f"   [Drafter] Skipping: IR already provided for request: '{user_request}'")
        return append_audit(state, "drafter", "skip_existing_ir", {"reason": "ir_present"})

    print(f"   [Drafter] Processing request: '{user_request}'")
    prior_feedback = state.get("feedback")
    prior_issues = []
    if prior_feedback and prior_feedback.get("verdict") == "NEEDS_REVISION":
        prior_issues = prior_feedback.get("issues", [])
        state = {**state, "revision_count": (state.get("revision_count") or 0) + 1}

    # 1. Готовим промпт
    system_prompt = get_system_prompt()
    user_prompt = f"USER REQUEST: {user_request}"
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
        after_json = json.dumps(data, sort_keys=True)
        new_state = {**state, "ir": ir, "last_ir_json": after_json, "last_error": None}
        if prior_issues:
            repair_log = list(state.get("repair_log") or [])
            error_summary = "; ".join([i.get("message", "") for i in prior_issues])
            repair_log.append(
                {
                    "repair_attempt": state.get("revision_count") or 1,
                    "error_summary": error_summary,
                    "diff_before_after": {"before": state.get("last_ir_json"), "after": after_json},
                }
            )
            new_state["repair_log"] = repair_log
        return append_audit(new_state, "drafter", "ir_generated", {"valid": True})

    except Exception as e:
        attempt = state.get("revision_count") or 0
        if attempt == 0:
            attempt = 1
        before = state.get("last_ir_json")
        error_summary = str(e)
        diff = {"before": before, "after": clean_json}
        repair_log = list(state.get("repair_log") or [])
        repair_log.append(
            {
                "repair_attempt": attempt,
                "error_summary": error_summary,
                "diff_before_after": diff,
            }
        )
        new_state = {
            **state,
            "ir": None,
            "last_error": error_summary,
            "revision_count": attempt,
            "repair_log": repair_log,
        }
        new_state = append_audit(
            new_state,
            "drafter",
            "ir_invalid",
            {"attempt": attempt, "error_summary": error_summary},
        )
        print(f"   [Drafter] ❌ Failed to generate valid IR: {e}")
        return new_state
