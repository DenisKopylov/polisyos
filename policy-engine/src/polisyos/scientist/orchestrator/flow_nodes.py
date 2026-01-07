from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import jax
import jax.numpy as jnp
from pydantic import ValidationError

from polisyos.scientist.agent.drafter import MockLLM
from polisyos.scientist.agent.prompts import get_system_prompt
from polisyos.foundry.registry import MECHANISM_REGISTRY, create_mechanism
from polisyos.scientist.orchestrator.audit import append_audit
from polisyos.scientist.orchestrator.compiler import compile_policy
from polisyos.scientist.orchestrator.data_loader import load_initial_state
from polisyos.scientist.orchestrator.decision_packet import build_decision_packet
from polisyos.scientist.orchestrator.run_record import ReproMode, build_run_record
from polisyos.scientist.orchestrator.state import ExperimentState, GovernorFeedback
from polisyos.ir.contract import PolicyRequestIR
from polisyos.ir.data_views import DataViewRequest
from polisyos.ir.validation import build_validation_report, diff_payloads, ValidationIssue
from polisyos.runtime import finalize_run, log_artifact, start_run, update_budget_usage
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.fabric.io.db import SimulationDB

DEFAULT_BUDGET = {
    "max_llm_calls": 3.0,
    "max_sim_runs": 1.0,
    "max_wall_time_s": 120.0,
}


def _runtime_base_dir(state: ExperimentState) -> Path:
    runtime_base_dir = state.get("runtime_base_dir")
    return Path(runtime_base_dir) if runtime_base_dir else Path("runs")


def _ensure_budget(state: ExperimentState) -> ExperimentState:
    budget = dict(DEFAULT_BUDGET)
    budget.update(state.get("budget") or {})
    usage = state.get("budget_usage") or {"llm_calls": 0.0, "sim_runs": 0.0, "wall_time_s": 0.0}
    started_at = state.get("budget_started_at")
    if started_at is None:
        started_at = time.monotonic()
    usage["wall_time_s"] = time.monotonic() - started_at
    return {
        **state,
        "budget": budget,
        "budget_usage": usage,
        "budget_started_at": started_at,
    }


def _update_budget_manifest(state: ExperimentState) -> None:
    run_id = state.get("run_id")
    if not run_id:
        return
    update_budget_usage(
        run_id=run_id,
        budget_usage=state.get("budget_usage") or {},
        base_dir=_runtime_base_dir(state),
    )


def _make_issue(loc: list[Any], message: str, error_type: str, input_value: Any = None) -> dict:
    issue = ValidationIssue(
        loc=loc,
        message=message,
        error_type=error_type,
        input_value=input_value,
    )
    return issue.model_dump()


def _prune(state: ExperimentState, reason: str, detail: str) -> ExperimentState:
    issue = _make_issue(["budget"], f"Pruned: {reason}", "budget", detail)
    feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
    new_state = {
        **state,
        "pruned": True,
        "pruning_reason": {"reason": reason, "detail": detail},
        "feedback": feedback,
    }
    return append_audit(new_state, "budget", "pruned", new_state["pruning_reason"])


def _blocked_by_feedback(state: ExperimentState) -> bool:
    feedback = state.get("feedback")
    if not feedback:
        return False
    verdict = feedback.get("verdict")
    return verdict in {"REJECT", "NEEDS_REVISION"}


def _check_budget(state: ExperimentState, kind: str) -> ExperimentState:
    state = _ensure_budget(state)
    budget = state.get("budget") or {}
    usage = dict(state.get("budget_usage") or {})
    if kind == "llm":
        usage["llm_calls"] = usage.get("llm_calls", 0.0) + 1.0
        if usage["llm_calls"] > budget.get("max_llm_calls", 0.0):
            state = {**state, "budget_usage": usage}
            _update_budget_manifest(state)
            return _prune(state, "llm_calls", "Exceeded max_llm_calls")
    elif kind == "sim":
        usage["sim_runs"] = usage.get("sim_runs", 0.0) + 1.0
        if usage["sim_runs"] > budget.get("max_sim_runs", 0.0):
            state = {**state, "budget_usage": usage}
            _update_budget_manifest(state)
            return _prune(state, "sim_runs", "Exceeded max_sim_runs")
    state = {**state, "budget_usage": usage}
    if usage.get("wall_time_s", 0.0) > budget.get("max_wall_time_s", float("inf")):
        _update_budget_manifest(state)
        return _prune(state, "wall_time", "Exceeded max_wall_time_s")
    _update_budget_manifest(state)
    return state


def _ensure_run(state: ExperimentState) -> ExperimentState:
    if state.get("run_id"):
        return state
    runtime_dir = _runtime_base_dir(state)
    manifest = start_run(
        run_id=state.get("run_id"),
        parent_run_id=state.get("parent_run_id"),
        generator={"name": "policy-engine", "version": "0.1.0"},
        budgets=state.get("budget") or DEFAULT_BUDGET,
        base_dir=runtime_dir,
    )
    new_state = {**state, "run_id": manifest.run_id, "runtime_base_dir": str(runtime_dir)}
    return append_audit(new_state, "runtime", "start_run", {"run_id": manifest.run_id})


def _generate_ir(state: ExperimentState, *, repair: bool) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned"):
        return state
    state = _check_budget(state, "llm")
    if state.get("pruned"):
        return state

    user_request = state.get("user_request")
    if not user_request:
        issue = _make_issue(["user_request"], "Missing user_request", "input")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "drafter", "missing_user_request", {})

    prior_issues = []
    feedback = state.get("feedback")
    if feedback and feedback.get("verdict") == "NEEDS_REVISION":
        prior_issues = feedback.get("issues", [])

    system_prompt = get_system_prompt()
    if prior_issues:
        issues_text = json.dumps(prior_issues, ensure_ascii=True, indent=2)
        user_prompt = f"USER REQUEST: {user_request}\n\nISSUES:\n{issues_text}"
    else:
        user_prompt = f"USER REQUEST: {user_request}"
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    log_artifact(
        run_id=state["run_id"],
        artifact_type="prompt",
        payload=full_prompt,
        media_type="text/plain",
        step="draft_ir" if not repair else "repair_ir",
        base_dir=_runtime_base_dir(state),
    )

    llm = MockLLM()
    response_text = llm.invoke(full_prompt)
    log_artifact(
        run_id=state["run_id"],
        artifact_type="llm_response",
        payload=response_text,
        media_type="text/plain",
        step="draft_ir" if not repair else "repair_ir",
        base_dir=_runtime_base_dir(state),
    )

    clean_json = response_text.strip().replace("```json", "").replace("```", "")
    try:
        data = json.loads(clean_json)
        ir = PolicyRequestIR(**data)
        after_json = json.dumps(data, sort_keys=True)
        new_state = {
            **state,
            "ir": ir,
            "last_ir_json": after_json,
            "last_error": None,
            "last_prompt": full_prompt,
            "last_llm_response": response_text,
        }
        if repair:
            before = state.get("last_ir_json")
            if before:
                diff_text = diff_payloads(json.loads(before), data)
                log_artifact(
                    run_id=state["run_id"],
                    artifact_type="repair_diff",
                    payload=diff_text,
                    media_type="text/plain",
                    step="repair_ir",
                    base_dir=_runtime_base_dir(state),
                )
        return append_audit(new_state, "drafter", "ir_generated", {"valid": True})
    except (json.JSONDecodeError, ValidationError) as exc:
        report = build_validation_report(exc) if isinstance(exc, ValidationError) else None
        if report:
            issues = report.issues
        else:
            issues = [
                ValidationIssue(
                    loc=["ir"],
                    message=str(exc),
                    error_type="parse",
                    input_value=clean_json,
                )
            ]
        issue_payloads = [issue.model_dump() for issue in issues]
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": issue_payloads}
        new_state = {
            **state,
            "ir": None,
            "last_error": str(exc),
            "feedback": feedback,
            "last_prompt": full_prompt,
            "last_llm_response": response_text,
        }
        if report:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="validation_report",
                payload=report.model_dump(),
                media_type="application/json",
                step="draft_ir" if not repair else "repair_ir",
                base_dir=_runtime_base_dir(state),
            )
        return append_audit(new_state, "drafter", "ir_invalid", {"error": str(exc)})


def draft_ir_node(state: ExperimentState) -> ExperimentState:
    if state.get("ir") is not None and not state.get("feedback"):
        return append_audit(state, "drafter", "skip_existing_ir", {"reason": "ir_present"})
    return _generate_ir(state, repair=False)


def validate_ir_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned"):
        return state
    if state.get("ir") is None:
        issue = _make_issue(["ir"], "IR is missing", "validation")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "validate_ir", "missing_ir", {})

    try:
        payload = state["ir"].model_dump()
        PolicyRequestIR.model_validate(payload)
    except ValidationError as exc:
        report = build_validation_report(exc, before=payload, after=payload)
        feedback: GovernorFeedback = {
            "verdict": "NEEDS_REVISION",
            "issues": [issue.model_dump() for issue in report.issues],
        }
        log_artifact(
            run_id=state["run_id"],
            artifact_type="validation_report",
            payload=report.model_dump(),
            media_type="application/json",
            step="validate_ir",
            base_dir=_runtime_base_dir(state),
        )
        return append_audit({**state, "feedback": feedback}, "validate_ir", "invalid", {})

    safety_issues = []
    if not state["ir"].interventions:
        safety_issues.append(
            _make_issue(["interventions"], "At least one intervention is required", "safety")
        )
    for idx, intervention in enumerate(state["ir"].interventions):
        if intervention.mechanism_type not in MECHANISM_REGISTRY:
            safety_issues.append(
                _make_issue(
                    ["interventions", idx, "mechanism_type"],
                    f"Unknown mechanism type '{intervention.mechanism_type}'",
                    "safety",
                    intervention.mechanism_type,
                )
            )
    if safety_issues:
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": safety_issues}
        return append_audit({**state, "feedback": feedback}, "validate_ir", "safety_block", {})

    return append_audit({**state, "feedback": None}, "validate_ir", "valid", {})


def repair_ir_node(state: ExperimentState) -> ExperimentState:
    if state.get("pruned"):
        return state
    max_attempts = state.get("max_repair_attempts") or 3
    revision_count = state.get("revision_count") or 0
    if revision_count >= max_attempts:
        return _prune(state, "max_repair_attempts", "Exceeded max_repair_attempts")
    state = {**state, "revision_count": revision_count + 1}
    return _generate_ir(state, repair=True)


def compile_data_views_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "compile_data_views", "skipped", {"reason": "feedback_blocked"})

    requests_raw = state.get("data_view_requests") or []
    if not requests_raw:
        log_artifact(
            run_id=state["run_id"],
            artifact_type="data_view_plans",
            payload={"status": "skipped", "reason": "no_data_view_requests"},
            media_type="application/json",
            step="compile_data_views",
            base_dir=_runtime_base_dir(state),
        )
        return append_audit(state, "compile_data_views", "skipped", {})

    db = SimulationDB("integration.duckdb")
    udf = UDFEngine(db)
    plans: List[Dict[str, Any]] = []
    try:
        for req_payload in requests_raw:
            if hasattr(req_payload, "model_dump"):
                req_payload = req_payload.model_dump()
            req = DataViewRequest.model_validate(req_payload)
            plan = udf.compile(req)
            plans.append(plan.__dict__)
        new_state = {**state, "data_view_plans": plans}
        log_artifact(
            run_id=state["run_id"],
            artifact_type="data_view_plans",
            payload=plans,
            media_type="application/json",
            step="compile_data_views",
            base_dir=_runtime_base_dir(state),
        )
        return append_audit(new_state, "compile_data_views", "compiled", {"count": len(plans)})
    except Exception as exc:
        issue = _make_issue(["data_views"], str(exc), "data")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "compile_data_views", "failed", {})
    finally:
        db.close()


def compile_model_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "compile_model", "skipped", {"reason": "feedback_blocked"})
    ir = state.get("ir")
    if ir is None:
        issue = _make_issue(["ir"], "IR missing before compile_model", "compile")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "compile_model", "missing_ir", {})
    try:
        policy_model = compile_policy(ir, n_agents=0, n_firms=0)
        compiled_spec = [
            {
                "mechanism_type": intervention.mechanism_type,
                "parameters": intervention.parameters,
            }
            for intervention in ir.interventions
        ]
        log_artifact(
            run_id=state["run_id"],
            artifact_type="compiled_model_spec",
            payload=compiled_spec,
            media_type="application/json",
            step="compile_model",
            base_dir=_runtime_base_dir(state),
        )
        return append_audit(
            {**state, "compiled_model": policy_model},
            "compile_model",
            "ok",
            {"count": len(compiled_spec)},
        )
    except Exception as exc:
        issue = _make_issue(["interventions"], str(exc), "compile")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "compile_model", "failed", {})


def run_sim_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "run_sim", "skipped", {"reason": "feedback_blocked"})
    state = _check_budget(state, "sim")
    if state.get("pruned"):
        return state

    ir = state.get("ir")
    if ir is None:
        issue = _make_issue(["ir"], "IR missing before run_sim", "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "missing_ir", {})

    db = SimulationDB("integration.duckdb")
    udf = UDFEngine(db)
    try:
        world_state = load_initial_state(udf, "baseline_2023", step=0)
    except Exception as exc:
        issue = _make_issue(["data"], str(exc), "data")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "data_load_failed", {})

    n_agents = world_state.agents.income.shape[0]
    mechanisms = [create_mechanism(intervention, n_agents) for intervention in ir.interventions]
    key = jax.random.PRNGKey(ir.simulation_params.random_seed)
    for mech in mechanisms:
        key, step_key = jax.random.split(key)
        world_state, key = mech(world_state, step_key)

    results = {
        "avg_income": float(jnp.mean(world_state.agents.income)),
        "gov_balance": float(world_state.government_balance),
        "n_agents": int(n_agents),
    }

    run_record = build_run_record(
        run_id=state["run_id"],
        parent_run_id=state.get("parent_run_id"),
        seed=ir.simulation_params.random_seed,
        repro_mode=ReproMode.FAST,
        generator={"name": ir.generator.name, "version": ir.generator.version},
    )
    log_artifact(
        run_id=state["run_id"],
        artifact_type="run_record",
        payload=run_record.model_dump(),
        media_type="application/json",
        step="run_sim",
        base_dir=_runtime_base_dir(state),
    )
    db.close()

    return append_audit(
        {**state, "simulation_results": results, "run_record": run_record},
        "run_sim",
        "completed",
        results,
    )


def analyze_node(state: ExperimentState) -> ExperimentState:
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "analyze", "skipped", {"reason": "feedback_blocked"})
    results = state.get("simulation_results") or {}
    analysis = {"status": "ok", "metrics": results}
    if state.get("run_id"):
        log_artifact(
            run_id=state["run_id"],
            artifact_type="analysis",
            payload=analysis,
            media_type="application/json",
            step="analyze",
            base_dir=_runtime_base_dir(state),
        )
    return append_audit({**state, "analysis": analysis}, "analyze", "ok", {})


def governor_node(state: ExperimentState) -> ExperimentState:
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "governor", "skipped", {"reason": "feedback_blocked"})
    results = state.get("simulation_results") or {}
    ir = state.get("ir")
    if not ir:
        issue = _make_issue(["ir"], "Missing IR before governor", "governor")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "governor", "missing_ir", {})

    issues: List[Dict[str, Any]] = []
    verdict = "APPROVE"

    min_balance = ir.global_constraints.get("min_balance", -1e9)
    if results.get("gov_balance") is not None and results["gov_balance"] < min_balance:
        verdict = "NEEDS_REVISION"
        issues.append(
            _make_issue(
                ["global_constraints", "min_balance"],
                f"Budget deficit too high: {results['gov_balance']} < {min_balance}",
                "policy",
                results["gov_balance"],
            )
        )

    feedback: GovernorFeedback = {"verdict": verdict, "issues": issues}
    return append_audit({**state, "feedback": feedback}, "governor", "verdict", feedback)


def pack_decision_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    run_record = state.get("run_record")
    if run_record is None:
        run_record = build_run_record(
            run_id=state["run_id"],
            parent_run_id=state.get("parent_run_id"),
            seed=0,
            repro_mode=ReproMode.FAST,
            generator={"name": "policy-engine", "version": "0.1.0"},
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="run_record",
            payload=run_record.model_dump(),
            media_type="application/json",
            step="pack_decision",
            base_dir=_runtime_base_dir(state),
        )
        state = {**state, "run_record": run_record}

    packet = build_decision_packet(state, run_record)
    log_artifact(
        run_id=state["run_id"],
        artifact_type="decision_packet",
        payload=packet.model_dump(),
        media_type="application/json",
        step="pack_decision",
        base_dir=_runtime_base_dir(state),
    )

    status = "running"
    feedback = state.get("feedback")
    if state.get("pruned"):
        status = "pruned"
    elif feedback:
        verdict = feedback.get("verdict")
        status = verdict.lower() if verdict else "running"
    finalize_run(
        run_id=state["run_id"],
        status=status,
        pruning_reason=state.get("pruning_reason"),
        base_dir=_runtime_base_dir(state),
    )

    return append_audit(
        {**state, "decision_packet": packet.model_dump() if packet else None},
        "pack_decision",
        "completed",
        {"status": status},
    )
