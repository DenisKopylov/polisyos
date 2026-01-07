# polisyos/orchestrator/state.py
from typing import Any, Dict, List, Optional, TypedDict


from polisyos.ir.contract import PolicyRequestIR
from polisyos.scientist.orchestrator.run_record import RunRecord


class GovernorFeedback(TypedDict):
    verdict: str  # "APPROVE", "REJECT", "NEEDS_REVISION"
    issues: List[Dict[str, Any]]  # ValidationIssue payloads


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
    runtime_base_dir: Optional[str]
    db_path: Optional[str]
    graph_path: Optional[str]
    baseline_run_id: Optional[str]
    budget: Optional[Dict[str, float]]
    budget_usage: Optional[Dict[str, float]]
    budget_started_at: Optional[float]
    pruning_reason: Optional[Dict[str, Any]]
    pruned: Optional[bool]
    last_prompt: Optional[str]
    last_llm_response: Optional[str]
    data_view_requests: Optional[List[Dict[str, Any]]]
    data_view_plans: Optional[List[Dict[str, Any]]]
    compiled_model: Optional[Any]
    analysis: Optional[Dict[str, Any]]
    decision_packet: Optional[Dict[str, Any]]

    # Результаты симуляции (сырые данные или метрики)
    simulation_results: Optional[Dict[str, float]]

    # Обратная связь от Губернатора
    feedback: Optional[GovernorFeedback]

    # Счетчик попыток (чтобы избежать бесконечных циклов)
    revision_count: int
    max_repair_attempts: int
    repair_log: List[RepairAttempt]
    audit_trail: List[Dict[str, Any]]
