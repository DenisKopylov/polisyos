# src/orchestrator/state.py
from typing import Dict, List, Optional, TypedDict

from src.policy_ir.contract import PolicyRequestIR


class GovernorFeedback(TypedDict):
    verdict: str  # "APPROVE", "REJECT", "NEEDS_REVISION"
    comments: List[str]


class ExperimentState(TypedDict):
    # Входные данные
    user_request: str  # <--- НОВОЕ ПОЛЕ: "Reduce poverty"
    ir: Optional[PolicyRequestIR]  # Теперь опционально, т.к. создается в процессе

    # Результаты симуляции (сырые данные или метрики)
    simulation_results: Optional[Dict[str, float]]

    # Обратная связь от Губернатора
    feedback: Optional[GovernorFeedback]

    # Счетчик попыток (чтобы избежать бесконечных циклов)
    revision_count: int
