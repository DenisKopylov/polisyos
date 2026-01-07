from abc import ABC, abstractmethod
from datetime import datetime

from polisyos.ir.contract import PolicyRequestIR


class BaseAgent(ABC):
    @abstractmethod
    def decide(self, step: int, context_df) -> PolicyRequestIR:
        """
        Принимает данные (DataFrame), возвращает Решение (IR).
        """
        pass


class MockAgent(BaseAgent):
    """
    Притворяется LLM. Принимает решения на основе экономических показателей.
    """

    def decide(self, step: int, context_df) -> PolicyRequestIR:
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

        return PolicyRequestIR(
            project_name={"en": "Auto Rescue", "ua": "Авто-Порятунок"},
            schema_version="1.0",
            generated_at=datetime.utcnow().isoformat(),
            generator={"name": "policy-engine", "version": "0.1.0"},
            currency="USD",
            time_unit="year",
            price_base_year=2024,
            simulation_params={"scope_years": 1, "time_frequency": "M"},
            scenarios={"random_seed": 42, "shocks": [], "timeline": {"start_year": 2024, "end_year": 2024}},
            entities=[],
            objectives=[],
            interventions=[
                {
                    "id": f"policy_step_{step}",
                    "name": {"en": mech_type.replace("_", " ").title(), "ua": mech_type},
                    "target_selector": {"all_of": [{"field": "id", "operator": "==", "value": "all"}]},
                    "mechanism_type": mech_type,
                    "parameters": {"rate": rate},
                }
            ],
        )
