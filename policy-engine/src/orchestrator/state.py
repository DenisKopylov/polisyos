# src/orchestrator/state.py
from typing import Dict, List, Optional, TypedDict, Any

from src.policy_ir.contract import PolicyRequestIR
from src.orchestrator.run_record import RunRecord


class GovernorIssue(TypedDict):
    issue_id: str
    severity: str  # "INFO" | "WARN" | "ERROR"
    component: str  # "legal" | "ethics" | "data" | "logic" | "validation"
    message: str
    recommended_fix: str
    blocking: bool


class GovernorFeedback(TypedDict):
    verdict: str  # "APPROVE", "REJECT", "NEEDS_REVISION"
    issues: List[GovernorIssue]


class RepairAttempt(TypedDict):
    repair_attempt: int
    error_summary: str
    diff_before_after: Dict[str, Any]


class ExperimentState(TypedDict):
    # Входные данные
    user_request: str  # <--- НОВОЕ ПОЛЕ: "Reduce poverty"
    ir: Optional[PolicyRequestIR]  # Теперь опционально, т.к. создается в процессе
    last_ir_json: Optional[str]
    last_error: Optional[str]

    # Управление поведением workflow
    optimize: Optional[bool]
    run_id: Optional[str]
    parent_run_id: Optional[str]
    repro_mode: Optional[str]
    run_record: Optional[RunRecord]

    # Результаты симуляции (сырые данные или метрики)
    simulation_results: Optional[Dict[str, float]]

    # Обратная связь от Губернатора
    feedback: Optional[GovernorFeedback]

    # Счетчик попыток (чтобы избежать бесконечных циклов)
    revision_count: int
    max_repair_attempts: int
    repair_log: List[RepairAttempt]
    audit_trail: List[Dict[str, Any]]
