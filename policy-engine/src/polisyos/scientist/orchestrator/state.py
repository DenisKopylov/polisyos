from __future__ import annotations

from typing import Any, TypedDict


class GovernorFeedback(TypedDict, total=False):
    verdict: str
    issues: list[dict[str, Any]]


class ExperimentState(TypedDict, total=False):
    # Core request / run fields
    run_id: str
    user_request: str
    phase: str
    stop_after_phase: str
    pruned: bool

    # Agent stack overrides
    llm_client: Any
    model_name: str
    pi_agent: Any
    drafter_agent: Any
    formalizer_agent: Any
    critic_agent: Any

    # Agent artifacts
    problem_frame: Any
    draft_result: Any
    ir: Any
    trinity_bundle: Any
    critique_report: dict[str, Any]
    short_term_memory: dict[str, Any]

    # Legacy refs/state used by flow-node shims
    cas_root: str
    registry_bundle_ref: dict[str, Any]
    trinity_bundle_ref: dict[str, Any]
    data_snapshot_ref: dict[str, Any]
    state_snapshot_ref: dict[str, Any]
    exec_plan_ref: dict[str, Any]
    simulation_result_ref: dict[str, Any]
    simulation_results_ref: dict[str, Any]
    metrics_ref: dict[str, Any]

    # Results
    feedback: GovernorFeedback
    simulation_results: dict[str, Any]
    gate_request: dict[str, Any]
    gate_decision: dict[str, Any]

    # Budget tracking
    budget: dict[str, float]
    budget_usage: dict[str, float]
