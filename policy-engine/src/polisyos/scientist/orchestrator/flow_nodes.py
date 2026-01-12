from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import jax
import jax.numpy as jnp
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.compiler import CompileReport, put_compile_report, put_link_report
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.core.run.context import RunContext
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.foundry.compiler import compile_surface_policy, put_policy_surface
from polisyos.foundry.executor import load_state_snapshot, put_state_snapshot
from polisyos.foundry.registry import create_mechanism_from_spec
from polisyos.ir.data_views import DataViewRequest
from polisyos.ir.kernel import MergeRuleKind
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.linker import link_policy
from polisyos.ir.surface import PolicySurfaceIR
from polisyos.ir.validation import ValidationIssue, build_validation_report, diff_payloads
from polisyos.runtime import finalize_run, log_artifact, start_run, update_budget_usage
from polisyos.scientist.agent.drafter import MockLLM
from polisyos.scientist.agent.prompts import get_system_prompt
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import resolve_backend, run_job
from polisyos.scientist.orchestrator.audit import append_audit
from polisyos.scientist.orchestrator.data_loader import load_initial_state
from polisyos.scientist.orchestrator.decision_packet import build_decision_packet
from polisyos.scientist.orchestrator.run_record import ReproMode, build_run_record
from polisyos.scientist.orchestrator.state import ExperimentState, GovernorFeedback
from polisyos.scientist.kernel.human_gate import GateDecision, GateRequest

DEFAULT_BUDGET = {
    "max_llm_calls": 3.0,
    "max_sim_runs": 1.0,
    "max_wall_time_s": 120.0,
}


def _runtime_base_dir(state: ExperimentState) -> Path:
    runtime_base_dir = state.get("runtime_base_dir")
    return Path(runtime_base_dir) if runtime_base_dir else Path("runs")


def _cas_root(state: ExperimentState) -> Path:
    if state.get("cas_root"):
        return Path(state["cas_root"])
    runtime_base = _runtime_base_dir(state)
    return runtime_base.parent / ".polisyos"


def _ensure_registry_bundle(state: ExperimentState) -> ExperimentState:
    if state.get("registry_bundle_ref"):
        return state
    store = FileSystemCAS(_cas_root(state))
    bundle = build_default_registry_bundle(store)
    run_id = state.get("run_id")
    if run_id:
        log_artifact(
            run_id=run_id,
            artifact_type="registry_bundle_ref",
            payload=bundle.bundle_ref.model_dump(),
            media_type="application/json",
            step="runtime",
            base_dir=_runtime_base_dir(state),
        )
    return {
        **state,
        "registry_bundle_ref": bundle.bundle_ref.model_dump(),
        "cas_root": str(_cas_root(state)),
    }


def _ensure_context_snapshot(
    state: ExperimentState,
    policy: PolicySurfaceIR,
) -> tuple[ExperimentState, PolicySurfaceIR]:
    store = FileSystemCAS(_cas_root(state))
    try:
        snapshot_id = ArtifactID.model_validate(policy.semantic.context_snapshot_ref)
    except Exception as exc:
        raise ValueError(f"Invalid context_snapshot_ref: {exc}") from exc

    if store.has(snapshot_id):
        return state, policy

    baseline_run_id = state.get("baseline_run_id")
    if not baseline_run_id:
        raise ValueError("context_snapshot_ref not found in CAS and baseline_run_id missing")
    db_path = state.get("db_path") or "integration.duckdb"
    graph_path = state.get("graph_path")
    db = SimulationDB(db_path)
    graph = GraphStore(str(graph_path)) if graph_path else None
    udf = UDFEngine(db, graph) if graph is not None else UDFEngine(db)
    try:
        world_state = load_initial_state(udf, baseline_run_id, step=0)
    finally:
        db.close()
    snapshot_ref = put_state_snapshot(
        store,
        state=world_state,
        step=int(world_state.step),
    )
    updated_policy = policy.model_copy(
        update={
            "semantic": policy.semantic.model_copy(
                update={"context_snapshot_ref": str(snapshot_ref.artifact_id)}
            )
        }
    )
    if state.get("run_id"):
        log_artifact(
            run_id=state["run_id"],
            artifact_type="context_snapshot_ref",
            payload=snapshot_ref.model_dump(),
            media_type="application/json",
            step="runtime",
            base_dir=_runtime_base_dir(state),
        )
    return {**state, "ir": updated_policy}, updated_policy


def _resolve_registry_bundle_id(
    state: ExperimentState, policy: PolicySurfaceIR | None
) -> str | None:
    if policy and policy.semantic.registry_bundle_ref:
        return policy.semantic.registry_bundle_ref
    bundle_ref = state.get("registry_bundle_ref")
    if isinstance(bundle_ref, dict):
        return bundle_ref.get("artifact_id")
    return None


def _resolve_registry_bundle_ref(
    state: ExperimentState, policy: PolicySurfaceIR | None
) -> ArtifactRef | None:
    bundle_id = _resolve_registry_bundle_id(state, policy)
    if not bundle_id:
        return None
    bundle_ref = state.get("registry_bundle_ref")
    if isinstance(bundle_ref, dict):
        if bundle_ref.get("artifact_id") == bundle_id:
            return ArtifactRef.model_validate(bundle_ref)
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(bundle_id),
        kind="core.registry_bundle",
        media_type="application/json",
    )


def _load_registry_bundle_content_for(state: ExperimentState, policy: PolicySurfaceIR | None):
    bundle_id = _resolve_registry_bundle_id(state, policy)
    if not bundle_id:
        raise ValueError("registry_bundle_ref is missing")
    store = FileSystemCAS(_cas_root(state))
    return load_registry_bundle_content(store, bundle_id)


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


def _coerce_number(value: Any) -> float | None:
    from decimal import Decimal, InvalidOperation

    if isinstance(value, MoneyValue):
        return float(value.amount)
    if isinstance(value, RateValue):
        return float(value.as_ratio())
    if isinstance(value, CountValue):
        return float(value.value)
    if isinstance(value, DurationValue):
        return float(value.value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(Decimal(value))
        except InvalidOperation:
            return None
    return None


def _constraint_value(policy: PolicySurfaceIR, constraint_id: str) -> float | None:
    for constraint in policy.semantic.constraints:
        if constraint.constraint_id == constraint_id:
            return _coerce_number(constraint.value)
    return None


def _get_state_path(state: Any, path: str) -> Any:
    current = state
    for part in path.split("."):
        current = getattr(current, part)
    return current


def _set_state_path(state: Any, path: str, value: Any) -> Any:
    parts = path.split(".")
    if len(parts) == 1:
        return state.replace(**{parts[0]: value})
    head, tail = parts[0], parts[1:]
    child = getattr(state, head)
    updated = _set_nested_path(child, tail, value)
    return state.replace(**{head: updated})


def _set_nested_path(obj: Any, parts: list[str], value: Any) -> Any:
    if len(parts) == 1:
        return obj.replace(**{parts[0]: value})
    head, tail = parts[0], parts[1:]
    child = getattr(obj, head)
    updated = _set_nested_path(child, tail, value)
    return obj.replace(**{head: updated})


def _collect_slot_patches(
    base_state: Any,
    policy: PolicySurfaceIR,
    *,
    mechanism_registry,
    slot_registry,
    key: jax.Array,
    n_agents: int,
) -> tuple[dict[str, list[dict[str, Any]]], jax.Array]:
    patches: dict[str, list[dict[str, Any]]] = {}
    for intervention in sorted(
        policy.semantic.interventions, key=lambda item: item.intervention_id
    ):
        mech_spec = mechanism_registry.mechanisms.get(intervention.kind)
        if mech_spec is None:
            raise ValueError(f"Unknown mechanism '{intervention.kind}' during execution")
        mech = create_mechanism_from_spec(intervention.kind, intervention.params, n_agents)
        key, step_key = jax.random.split(key)
        mech_state, key = mech(base_state, step_key)
        for slot_id in mech_spec.writes_slots:
            slot_spec = slot_registry.slots.get(slot_id)
            if slot_spec is None or not slot_spec.state_path:
                raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
            base_value = _get_state_path(base_state, slot_spec.state_path)
            new_value = _get_state_path(mech_state, slot_spec.state_path)
            delta = new_value - base_value
            patches.setdefault(slot_id, []).append(
                {
                    "intervention_id": intervention.intervention_id,
                    "priority": intervention.priority,
                    "delta": delta,
                    "value": new_value,
                }
            )
    return patches, key


def _apply_slot_patches(
    base_state: Any,
    patches: dict[str, list[dict[str, Any]]],
    *,
    slot_registry,
    merge_registry,
) -> Any:
    state = base_state
    for slot_id, records in sorted(patches.items()):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")
        base_value = _get_state_path(base_state, slot_spec.state_path)
        if rule.kind == MergeRuleKind.SUM:
            total_delta = None
            for record in records:
                total_delta = (
                    record["delta"] if total_delta is None else total_delta + record["delta"]
                )
            merged = base_value if total_delta is None else base_value + total_delta
        elif rule.kind == MergeRuleKind.OVERRIDE:
            picked = sorted(records, key=lambda item: item["intervention_id"])[-1]
            merged = picked["value"]
        elif rule.kind == MergeRuleKind.PRIORITY:
            if any(record["priority"] is None for record in records):
                raise ValueError(f"Priority merge requires priority for slot '{slot_id}'")
            picked = sorted(
                records, key=lambda item: (-int(item["priority"]), item["intervention_id"])
            )[0]
            merged = picked["value"]
        elif rule.kind == MergeRuleKind.ERROR:
            if len(records) > 1:
                ids = ", ".join(record["intervention_id"] for record in records)
                raise ValueError(f"Merge conflict for slot '{slot_id}': {ids}")
            merged = records[0]["value"]
        else:
            raise ValueError(f"Unsupported merge rule '{rule.kind}' for '{slot_id}'")
        state = _set_state_path(state, slot_spec.state_path, merged)
    return state


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
    if state.get("run_id") and state.get("run_context"):
        return _ensure_registry_bundle(state)
    runtime_dir = _runtime_base_dir(state)
    manifest = start_run(
        run_id=state.get("run_id"),
        parent_run_id=state.get("parent_run_id"),
        generator={"name": "policy-engine", "version": "0.1.0"},
        budgets=state.get("budget") or DEFAULT_BUDGET,
        base_dir=runtime_dir,
    )
    new_state = {**state, "run_id": manifest.run_id, "runtime_base_dir": str(runtime_dir)}
    new_state = _ensure_registry_bundle(new_state)
    registry_bundle_ref = new_state.get("registry_bundle_ref")
    if registry_bundle_ref:
        store = FileSystemCAS(_cas_root(new_state))
        ctx = RunContext.start(
            store,
            registry_bundle=ArtifactRef.model_validate(registry_bundle_ref),
            run_dir=_runtime_base_dir(new_state),
            run_id=manifest.run_id,
        )
        new_state = {**new_state, "run_context": ctx}
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
        ir = PolicySurfaceIR(**data)
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
        payload = state["ir"].model_dump(mode="json")
        PolicySurfaceIR.model_validate(payload)
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
    policy = state["ir"]
    try:
        registry_content = _load_registry_bundle_content_for(state, policy)
    except Exception as exc:
        issue = _make_issue(["semantic", "registry_bundle_ref"], str(exc), "registry")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "validate_ir", "registry_failed", {})

    bundle_id = _resolve_registry_bundle_id(state, policy)
    if policy.semantic.registry_bundle_ref is None and bundle_id:
        policy = policy.model_copy(
            update={
                "semantic": policy.semantic.model_copy(update={"registry_bundle_ref": bundle_id})
            }
        )
        state = {**state, "ir": policy}
    if not policy.semantic.interventions:
        safety_issues.append(
            _make_issue(
                ["semantic", "interventions"], "At least one intervention is required", "safety"
            )
        )
    for idx, intervention in enumerate(policy.semantic.interventions):
        if intervention.kind not in registry_content.mechanism_registry.mechanisms:
            safety_issues.append(
                _make_issue(
                    ["semantic", "interventions", idx, "kind"],
                    f"Unknown mechanism type '{intervention.kind}'",
                    "safety",
                    intervention.kind,
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

    db_path = state.get("db_path") or "integration.duckdb"
    graph_path = state.get("graph_path")
    db = SimulationDB(db_path)
    graph = GraphStore(str(graph_path)) if graph_path else None
    udf = UDFEngine(db, graph) if graph is not None else UDFEngine(db)
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
        state = _ensure_registry_bundle(state)
        state, ir = _ensure_context_snapshot(state, ir)
        store = FileSystemCAS(_cas_root(state))
        bundle_id = _resolve_registry_bundle_id(state, ir)
        if bundle_id and ir.semantic.registry_bundle_ref is None:
            ir = ir.model_copy(
                update={
                    "semantic": ir.semantic.model_copy(update={"registry_bundle_ref": bundle_id})
                }
            )
            state = {**state, "ir": ir}
        registry_content = _load_registry_bundle_content_for(state, ir)
        bundle_ref = _resolve_registry_bundle_ref(state, ir)

        policy_ref = put_policy_surface(
            store,
            ir,
            mechanism_registry=registry_content.mechanism_registry,
            units_registry=registry_content.units_registry,
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="policy_ir_ref",
            payload=policy_ref.model_dump(),
            media_type="application/json",
            step="compile_model",
            base_dir=_runtime_base_dir(state),
        )

        link_inputs = [InputRef(artifact_id=policy_ref.artifact_id, role="ir")]
        if bundle_ref is not None:
            link_inputs.append(InputRef(artifact_id=bundle_ref.artifact_id, role="registry_bundle"))

        link_report = link_policy(
            ir,
            registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            constraint_registry=registry_content.constraint_registry,
            metric_registry=registry_content.metric_registry,
            selector_field_registry=registry_content.selector_field_registry,
            units_registry=registry_content.units_registry,
        )
        link_ref = put_link_report(store, link_report, inputs=link_inputs)
        log_artifact(
            run_id=state["run_id"],
            artifact_type="link_report_ref",
            payload=link_ref.model_dump(),
            media_type="application/json",
            step="compile_model",
            base_dir=_runtime_base_dir(state),
        )

        compile_inputs = [
            InputRef(artifact_id=policy_ref.artifact_id, role="ir"),
            InputRef(artifact_id=link_ref.artifact_id, role="link_report"),
        ]
        if bundle_ref is not None:
            compile_inputs.append(
                InputRef(artifact_id=bundle_ref.artifact_id, role="registry_bundle")
            )

        if not link_report.ok:
            compile_report = CompileReport(
                ok=False,
                policy_ref=policy_ref,
                registry_bundle_ref=bundle_ref,
                link_report_ref=link_ref,
            )
            compile_ref = put_compile_report(store, compile_report, inputs=compile_inputs)
            log_artifact(
                run_id=state["run_id"],
                artifact_type="compile_report_ref",
                payload=compile_ref.model_dump(),
                media_type="application/json",
                step="compile_model",
                base_dir=_runtime_base_dir(state),
            )
            feedback: GovernorFeedback = {
                "verdict": "NEEDS_REVISION",
                "issues": [issue.model_dump() for issue in link_report.issues],
            }
            return append_audit(
                {
                    **state,
                    "feedback": feedback,
                    "policy_ir_ref": policy_ref.model_dump(),
                    "link_report_ref": link_ref.model_dump(),
                    "compile_report_ref": compile_ref.model_dump(),
                },
                "compile_model",
                "link_failed",
                {},
            )

        artifacts = compile_surface_policy(
            store,
            ir,
            mechanism_registry=registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            units_registry=registry_content.units_registry,
            policy_ref=policy_ref,
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="program_graph_ref",
            payload=artifacts.program_ref.model_dump(),
            media_type="application/json",
            step="compile_model",
            base_dir=_runtime_base_dir(state),
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="exec_plan_ref",
            payload=artifacts.exec_plan_ref.model_dump(),
            media_type="application/json",
            step="compile_model",
            base_dir=_runtime_base_dir(state),
        )
        if artifacts.slot_layout_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="slot_layout_ref",
                payload=artifacts.slot_layout_ref.model_dump(),
                media_type="application/json",
                step="compile_model",
                base_dir=_runtime_base_dir(state),
            )
        if artifacts.treasury_plan_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="treasury_plan_ref",
                payload=artifacts.treasury_plan_ref.model_dump(),
                media_type="application/json",
                step="compile_model",
                base_dir=_runtime_base_dir(state),
            )

        compile_inputs.extend(
            [
                InputRef(artifact_id=artifacts.program_ref.artifact_id, role="program_graph"),
                InputRef(artifact_id=artifacts.exec_plan_ref.artifact_id, role="exec_plan"),
            ]
        )
        if artifacts.slot_layout_ref is not None:
            compile_inputs.append(
                InputRef(artifact_id=artifacts.slot_layout_ref.artifact_id, role="slot_layout")
            )
        if artifacts.treasury_plan_ref is not None:
            compile_inputs.append(
                InputRef(
                    artifact_id=artifacts.treasury_plan_ref.artifact_id, role="treasury_plan"
                )
            )
        compile_report = CompileReport(
            ok=True,
            policy_ref=artifacts.policy_ref,
            registry_bundle_ref=bundle_ref,
            link_report_ref=link_ref,
            program_graph_ref=artifacts.program_ref,
            exec_plan_ref=artifacts.exec_plan_ref,
            slot_layout_ref=artifacts.slot_layout_ref,
            treasury_plan_ref=artifacts.treasury_plan_ref,
        )
        compile_ref = put_compile_report(store, compile_report, inputs=compile_inputs)
        log_artifact(
            run_id=state["run_id"],
            artifact_type="compile_report_ref",
            payload=compile_ref.model_dump(),
            media_type="application/json",
            step="compile_model",
            base_dir=_runtime_base_dir(state),
        )
        return append_audit(
            {
                **state,
                "compiled_model": None,
                "policy_ir_ref": artifacts.policy_ref.model_dump(),
                "program_graph_ref": artifacts.program_ref.model_dump(),
                "exec_plan_ref": artifacts.exec_plan_ref.model_dump(),
                "slot_layout_ref": artifacts.slot_layout_ref.model_dump()
                if artifacts.slot_layout_ref
                else None,
                "treasury_plan_ref": artifacts.treasury_plan_ref.model_dump()
                if artifacts.treasury_plan_ref
                else None,
                "link_report_ref": link_ref.model_dump(),
                "compile_report_ref": compile_ref.model_dump(),
            },
            "compile_model",
            "ok",
            {"count": len(ir.semantic.interventions)},
        )
    except Exception as exc:
        issue = _make_issue(["semantic", "interventions"], str(exc), "compile")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "compile_model", "failed", {})


def run_sim_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "run_sim", "skipped", {"reason": "feedback_blocked"})
    state = _check_budget(state, "sim")
    if state.get("pruned"):
        return state

    policy = state.get("ir")
    if policy is None:
        issue = _make_issue(["ir"], "IR missing before run_sim", "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "missing_ir", {})

    state = _ensure_registry_bundle(state)
    try:
        state, policy = _ensure_context_snapshot(state, policy)
    except Exception as exc:
        issue = _make_issue(["semantic", "context_snapshot_ref"], str(exc), "registry")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "context_missing", {})
    try:
        registry_content = _load_registry_bundle_content_for(state, policy)
    except Exception as exc:
        issue = _make_issue(["semantic", "registry_bundle_ref"], str(exc), "registry")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "registry_failed", {})
    try:
        world_state = load_state_snapshot(
            FileSystemCAS(_cas_root(state)),
            snapshot_ref=ArtifactID.model_validate(policy.semantic.context_snapshot_ref),
        )
    except Exception as exc:
        issue = _make_issue(["semantic", "context_snapshot_ref"], str(exc), "data")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "context_load_failed", {})

    n_agents = world_state.agents.income.shape[0]
    seed = state.get("random_seed") or 42
    key = jax.random.PRNGKey(seed)
    program_graph_ref = state.get("program_graph_ref")
    exec_plan_ref = state.get("exec_plan_ref")
    if not program_graph_ref or not exec_plan_ref:
        issue = _make_issue(["program_graph_ref"], "Compiled program missing", "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "missing_program", {})

    try:
        job_spec = JobSpec(
            program_ref=ArtifactRef.model_validate(program_graph_ref),
            exec_plan_ref=ArtifactRef.model_validate(exec_plan_ref),
            state_snapshot_ref=None,
            seed=seed,
        )
        backend = resolve_backend(state.get("runner_backend"))
        job_result = run_job(
            job_spec,
            backend=backend,
            registry_content=registry_content,
            base_state=world_state,
            cas_root=_cas_root(state),
        )
        if job_result.warnings:
            issue = _make_issue(["runtime"], "; ".join(job_result.warnings), "runtime")
            feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
            return append_audit({**state, "feedback": feedback}, "run_sim", "failed", {})
        exec_artifacts = job_result
        world_state = job_result.final_state or world_state
        if exec_artifacts.state_delta_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="state_delta_ref",
                payload=exec_artifacts.state_delta_ref.model_dump(),
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
        if exec_artifacts.metrics_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="metrics_ref",
                payload=exec_artifacts.metrics_ref.model_dump(),
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
        if exec_artifacts.state_snapshot_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="state_snapshot_ref",
                payload=exec_artifacts.state_snapshot_ref.model_dump(),
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
    except Exception as exc:
        verdict = "REJECT"
        issue_kind = "runtime"
        if str(exc).startswith("Constraint"):
            verdict = "NEEDS_REVISION"
            issue_kind = "constraint"
        issue = _make_issue(["semantic", "constraints"], str(exc), issue_kind)
        feedback: GovernorFeedback = {"verdict": verdict, "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "failed", {})

    results = {
        "avg_income": float(jnp.mean(world_state.agents.income)),
        "gov_balance": float(world_state.government_balance),
        "n_agents": int(n_agents),
    }

    run_record = build_run_record(
        run_id=state["run_id"],
        parent_run_id=state.get("parent_run_id"),
        seed=seed,
        repro_mode=ReproMode.FAST,
        generator={"name": "policy-engine", "version": "0.1.0"},
    )
    log_artifact(
        run_id=state["run_id"],
        artifact_type="run_record",
        payload=run_record.model_dump(),
        media_type="application/json",
        step="run_sim",
        base_dir=_runtime_base_dir(state),
    )
    return append_audit(
        {
            **state,
            "simulation_results": results,
            "run_record": run_record,
            "state_delta_ref": exec_artifacts.state_delta_ref.model_dump(),
            "metrics_ref": exec_artifacts.metrics_ref.model_dump(),
            "state_snapshot_ref": exec_artifacts.state_snapshot_ref.model_dump()
            if exec_artifacts.state_snapshot_ref is not None
            else None,
        },
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
    policy = state.get("ir")
    if not policy:
        issue = _make_issue(["ir"], "Missing IR before governor", "governor")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "governor", "missing_ir", {})

    issues: List[Dict[str, Any]] = []
    verdict = "APPROVE"

    min_balance = _constraint_value(policy, "min_balance")
    if min_balance is None:
        min_balance = -1e9
    if results.get("gov_balance") is not None and results["gov_balance"] < min_balance:
        verdict = "NEEDS_REVISION"
        issues.append(
            _make_issue(
                ["semantic", "constraints", "min_balance"],
                f"Budget deficit too high: {results['gov_balance']} < {min_balance}",
                "policy",
                results["gov_balance"],
            )
        )

    gate_reasons: list[str] = []
    if state.get("require_human_gate"):
        gate_reasons.append("require_human_gate_flag")
    uncertainty = state.get("uncertainty_bounds")
    if uncertainty and isinstance(uncertainty, dict):
        lower = uncertainty.get("lower")
        upper = uncertainty.get("upper")
        if lower is not None and upper is not None and (upper - lower) > 0.2:
            gate_reasons.append("wide_uncertainty_bounds")
    pii_tier = state.get("pii_tier")
    if pii_tier and str(pii_tier).lower() in {"high", "sensitive"}:
        gate_reasons.append("high_pii_tier")

    gate_decision = state.get("gate_decision")
    if gate_reasons and not gate_decision:
        gate_request = GateRequest(
            run_id=state.get("run_id") or "unknown",
            reason=";".join(gate_reasons),
            details={"reasons": gate_reasons, "results": results},
        )
        feedback: GovernorFeedback = {"verdict": "HUMAN_GATE", "issues": issues}
        return append_audit(
            {**state, "feedback": feedback, "gate_request": gate_request.model_dump()},
            "governor",
            "human_gate_required",
            {"reasons": gate_reasons},
        )

    if gate_reasons and gate_decision:
        decision_obj = (
            gate_decision if isinstance(gate_decision, GateDecision) else GateDecision.model_validate(gate_decision)
        )
        if not decision_obj.approved:
            issues.append(
                _make_issue(
                    ["governor", "human_gate"],
                    "Human gate rejected the run",
                    "policy",
                    decision_obj.reason_codes,
                )
            )
            feedback = {"verdict": "REJECT", "issues": issues}
            return append_audit(
                {**state, "feedback": feedback, "gate_decision": decision_obj.model_dump()},
                "governor",
                "rejected_by_gate",
                {},
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
        payload=packet.model_dump(mode="json"),
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
        if verdict and verdict.upper() == "HUMAN_GATE":
            status = "waiting_human_gate"
        else:
            status = verdict.lower() if verdict else "running"
    finalize_run(
        run_id=state["run_id"],
        status=status,
        pruning_reason=state.get("pruning_reason"),
        base_dir=_runtime_base_dir(state),
    )

    ctx = state.get("run_context")
    run_manifest_ref = None
    if ctx:
        run_manifest_ref = ctx.finalize(status=status)

    return append_audit(
        {
            **state,
            "decision_packet": packet.model_dump(mode="json") if packet else None,
            "run_manifest_ref": run_manifest_ref.model_dump() if run_manifest_ref else None,
        },
        "pack_decision",
        "completed",
        {"status": status},
    )
