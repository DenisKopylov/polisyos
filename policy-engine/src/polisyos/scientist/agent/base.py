from abc import ABC, abstractmethod

from polisyos.ir.surface import PolicySurfaceIR


class BaseAgent(ABC):
    @abstractmethod
    def decide(self, step: int, context_df) -> PolicySurfaceIR:
        """
        Принимает данные (DataFrame), возвращает Решение (IR).
        """
        pass


class MockAgent(BaseAgent):
    """
    Притворяется LLM. Принимает решения на основе экономических показателей.
    """

    def decide(self, step: int, context_df) -> PolicySurfaceIR:
        # Эмуляция "раздумий"
        print(f"🤖 MockAgent is thinking... (Data shape: {context_df.shape})")

        # Простая политика: если бюджет положительный, даем субсидии; если отрицательный - собираем налоги
        # Также смотрим на безработицу
        current_unempl = context_df["unemployment_rate"].iloc[-1] if not context_df.empty else 0.0

        # Если это первый шаг и нет данных, начинаем с налогов
        if context_df.empty or step == 1:
            mech_type = "income_tax"
            rate = 0.15  # Собираем налоги
        elif current_unempl > 0.05:
            mech_type = "tax_subsidy"
            rate = 0.20  # Агрессивные субсидии при высокой безработице
        else:
            mech_type = "tax_subsidy"
            rate = 0.10  # Умеренные субсидии

        return PolicySurfaceIR(
            schema_version="2.0",
            semantic={
                "context_snapshot_ref": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                "time_semantics": {"frequency": "M", "start_date": "2024-01-01", "step_count": 1},
                "interventions": [
                    {
                        "intervention_id": f"policy_step_{step}",
                        "kind": mech_type,
                        "target": {
                            "kind": "predicate",
                            "field": "id",
                            "operator": "==",
                            "value": "all",
                        },
                        "schedule": {"start_step": 0, "duration_steps": 1},
                        "params": {"rate": str(rate)},
                    }
                ],
                "objectives": [],
                "constraints": [],
            },
        )
