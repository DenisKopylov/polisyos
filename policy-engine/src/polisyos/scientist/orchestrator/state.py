# polisyos/orchestrator/state.py
from typing import Any, Dict, List, Optional, TypedDict

from polisyos.ir.surface import PolicySurfaceIR
from polisyos.core.contracts.scientist import FailureCardRef
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame, SubTask
from polisyos.scientist.orchestrator.run_record import RunRecord


class GovernorFeedback(TypedDict):
    verdict: str  # "APPROVE", "REJECT", "NEEDS_REVISION"
    issues: List[Dict[str, Any]]  # ValidationIssue payloads


class RepairAttempt(TypedDict):
    repair_attempt: int
    error_summary: str
    diff_before_after: Dict[str, Any]


class ReflexionState(TypedDict, total=False):
    """Reflexion-specific state fields."""

    current_failure_card: Optional[Dict[str, Any]]
    failure_history: List[FailureCardRef]
    reflexion_cycle_count: int
    total_retry_count: int
    reflexion_decision: Optional[str]
    retry_context: Optional[Dict[str, Any]]
    human_intervention_payload: Optional[Dict[str, Any]]


class ExperimentState(TypedDict):
    # Входные данные
    user_request: str  # <--- НОВОЕ ПОЛЕ: "Reduce poverty"
    ir: Optional[PolicySurfaceIR]  # Surface IR (semantic + advisory)
    last_ir_json: Optional[str]
    last_error: Optional[str]

    # NEW: Multi-agent state
    problem_frame: Optional[ProblemFrame]
    sub_tasks: Optional[List[SubTask]]
    draft_result: Optional[DraftResult]
    critique_report: Optional[Dict[str, Any]]

    # Reflexion loop tracking
    reflexion_attempt: int
    max_reflexion_attempts: int
    reflexion_hints: Optional[List[str]]

    # New Reflexion loop tracking
    current_failure_card: Optional[Dict[str, Any]]
    failure_history: List[Dict[str, Any]]
    reflexion_cycle_count: int
    total_retry_count: int
    reflexion_decision: Optional[str]
    retry_context: Optional[Dict[str, Any]]
    human_intervention_payload: Optional[Dict[str, Any]]

    # Memory reference
    short_term_memory: Optional[Dict[str, Any]]

    # Agent/LLM overrides
    llm_client: Optional[Any]
    pi_agent: Optional[Any]
    drafter_agent: Optional[Any]
    formalizer_agent: Optional[Any]
    critic_agent: Optional[Any]

    # Optional test/debug controls
    stop_after_phase: Optional[str]

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
    random_seed: Optional[int]
    last_prompt: Optional[str]
    last_llm_response: Optional[str]
    data_view_requests: Optional[List[Dict[str, Any]]]
    data_view_plans: Optional[List[Dict[str, Any]]]
    calibration_config: Optional[Dict[str, Any]]
    calibration_raw_targets: Optional[Dict[str, Any]]
    calibration_controls_seq: Optional[List[Any]]
    calibration_config_ref: Optional[Dict[str, Any]]
    calibration_report_ref: Optional[Dict[str, Any]]
    agent_training_config: Optional[Dict[str, Any]]
    agent_training_report_ref: Optional[Dict[str, Any]]
    agent_weights_ref: Optional[Dict[str, Any]]
    calibrated_params: Optional[Dict[str, float]]
    calibrated_params_ref: Optional[Dict[str, Dict[str, Any]]]
    compiled_model: Optional[Any]
    policy_ir_ref: Optional[Dict[str, Any]]
    program_graph_ref: Optional[Dict[str, Any]]
    exec_plan_ref: Optional[Dict[str, Any]]
    link_report_ref: Optional[Dict[str, Any]]
    compile_report_ref: Optional[Dict[str, Any]]
    state_delta_ref: Optional[Dict[str, Any]]
    metrics_ref: Optional[Dict[str, Any]]
    state_snapshot_ref: Optional[Dict[str, Any]]
    registry_bundle_ref: Optional[Dict[str, Any]]
    cas_root: Optional[str]
    analysis: Optional[Dict[str, Any]]
    decision_packet: Optional[Dict[str, Any]]
    gate_request: Optional[Dict[str, Any]]

    # Результаты симуляции (сырые данные или метрики)
    simulation_results: Optional[Dict[str, float]]
    simulation_results_ref: Optional[Dict[str, Any]]

    # Обратная связь от Губернатора
    feedback: Optional[GovernorFeedback]

    # Human gate / safety controls (must be part of state schema for LangGraph)
    require_human_gate: Optional[bool]
    gate_decision: Optional[Dict[str, Any]]
    pii_tier: Optional[str]
    uncertainty_bounds: Optional[Dict[str, float]]
    validation_trace: Optional[Dict[str, Any]]
    validation_warnings: Optional[List[Dict[str, Any]]]

    # Execution config
    runner_backend: Optional[str]

    # Счетчик попыток (чтобы избежать бесконечных циклов)
    revision_count: int
    max_repair_attempts: int
    repair_log: List[RepairAttempt]
    audit_trail: List[Dict[str, Any]]
    phase: Optional[str]


def create_initial_state(
    user_request: str,
    run_id: str,
    budget: Optional[Dict[str, float]] = None,
) -> ExperimentState:
    """Create a fresh experiment state with Reflexion fields initialized."""
    return ExperimentState(
        user_request=user_request,
        run_id=run_id,
        budget=budget or {"max_llm_calls": 50.0, "max_sim_runs": 5.0, "max_wall_time_s": 3600.0},
        reflexion_attempt=0,
        max_reflexion_attempts=3,
        reflexion_hints=None,
        current_failure_card=None,
        failure_history=[],
        reflexion_cycle_count=0,
        total_retry_count=0,
        reflexion_decision=None,
        retry_context=None,
        human_intervention_payload=None,
        audit_trail=[],
        revision_count=0,
        max_repair_attempts=3,
        repair_log=[],
        pruned=False,
        phase="INTAKE",
    )


def get_retry_count(state: ExperimentState) -> int:
    """Get total retry count from state."""
    return state.get("total_retry_count", 0)


def get_failure_history(state: ExperimentState) -> List[Dict[str, Any]]:
    """Get failure history from state."""
    return state.get("failure_history", [])


def has_active_failure(state: ExperimentState) -> bool:
    """Check if there's an active failure being processed."""
    return state.get("current_failure_card") is not None


def get_reflexion_cycle_count(state: ExperimentState) -> int:
    """Get number of reflexion cycles in this run."""
    return state.get("reflexion_cycle_count", 0)
