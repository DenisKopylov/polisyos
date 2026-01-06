# src/orchestrator/state.py
from typing import TypedDict, Optional, List, Dict, Any
from src.policy_ir.contract import PolicyRequestIR

class GovernorFeedback(TypedDict):
    verdict: str  # "APPROVE", "REJECT", "NEEDS_REVISION"
    comments: List[str]

class ExperimentState(TypedDict):
    # Входные данные
    ir: PolicyRequestIR

    # Результаты симуляции (сырые данные или метрики)
    simulation_results: Optional[Dict[str, float]]

    # Обратная связь от Губернатора
    feedback: Optional[GovernorFeedback]

    # Счетчик попыток (чтобы избежать бесконечных циклов)
    revision_count: int
