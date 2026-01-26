from __future__ import annotations

from decimal import Decimal
from io import BytesIO
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import equinox as eqx
import jax
import jax.numpy as jnp
import optax
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler import CompileReport, put_compile_report, put_link_report
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.core.run.context import RunContext
from polisyos.core.contracts.foundry import ExecPlan, ExecPlanRef, ProgramGraph, ProgramGraphRef
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.foundry.calibration import Calibrator, CalibratorInputs
from polisyos.foundry.calibration.preflight import extract_fabric_series
from polisyos.foundry.calibration.report import put_calibration_config, put_calibration_report
from polisyos.foundry.compiler import compile_surface_policy, put_policy_surface
from polisyos.foundry.executor import load_state_snapshot, put_state_snapshot
from polisyos.foundry.agent_metrics import normalize_action, policy_entropy, saturation_rate
from polisyos.foundry.agents import build_observations, continuous_actions_from_logits
from polisyos.foundry.fiscal import compute_tax
from polisyos.foundry.registry import create_mechanism_from_spec
from polisyos.foundry.utils import gradient_health_report
from polisyos.ir.calibration import CalibrationConfig
from polisyos.ir.data_views import DataViewRequest
from polisyos.foundry.merge_engine import MergeEngine, MergeRecord
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.linker import link_policy
from polisyos.ir.surface import PolicySurfaceIR, ScheduleSpec, schedule_range
from polisyos.ir.validation import ValidationIssue, build_validation_report, diff_payloads
from polisyos.runtime import finalize_run, log_artifact, start_run, update_budget_usage
from polisyos.scientist.agent.drafter import MockLLM
from polisyos.scientist.agent.prompts import get_system_prompt
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import resolve_backend, run_job
from polisyos.scientist.kernel.human_gate import GateDecision, GateRequest
from polisyos.scientist.orchestrator.audit import append_audit
from polisyos.scientist.orchestrator.data_loader import load_initial_state
from polisyos.scientist.orchestrator.decision_packet import build_decision_packet
from polisyos.scientist.orchestrator.run_record import ReproMode, build_run_record
from polisyos.scientist.orchestrator.state import ExperimentState, GovernorFeedback

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


def _artifact_id(value: ArtifactRef | ArtifactID | str) -> ArtifactID:
    if isinstance(value, ArtifactRef):
        return value.artifact_id
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def _load_model_from_ref(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str, model_cls):
    payload = from_canonical_bytes(store.get_bytes(_artifact_id(ref)))
    return model_cls.model_validate(payload)


def _load_payload(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str) -> dict[str, Any]:
    payload = from_canonical_bytes(store.get_bytes(_artifact_id(ref)))
    if not isinstance(payload, dict):
        raise ValueError("Expected dict payload")
    return payload


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
    engine = MergeEngine(slot_registry, merge_registry)
    records: list[MergeRecord] = []
    for slot_id, slot_records in patches.items():
        for record in slot_records:
            node_id = record.get("intervention_id", "unknown")
            records.append(
                MergeRecord(
                    node_id=node_id,
                    slot_id=slot_id,
                    value=record.get("value", record.get("new_value")),
                    delta=record.get("delta"),
                    priority=record.get("priority"),
                    timestamp=record.get("timestamp"),
                )
            )

    base_values: dict[str, Any] = {}
    for slot_id in patches.keys():
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        base_values[slot_id] = _get_state_path(base_state, slot_spec.state_path)

    report = engine.merge_records(records, base_values)
    report.raise_if_conflicts()

    state = base_state
    for slot_id, merged_value in report.merged_values.items():
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        state = _set_state_path(state, slot_spec.state_path, merged_value)
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
    # Validation needs the registry to exist even when the caller didn't provide one.
    # Without this, integration runs would get an immediate REJECT ("registry_bundle_ref is missing")
    # and the workflow would never reach compile/run/governor.
    state = _ensure_registry_bundle(state)
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
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
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
                InputRef(artifact_id=artifacts.treasury_plan_ref.artifact_id, role="treasury_plan")
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


def train_agents_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "train_agents", "skipped", {"reason": "feedback_blocked"})
    state = _check_budget(state, "sim")
    if state.get("pruned"):
        return state

    policy = state.get("ir")
    if policy is None:
        issue = _make_issue(["ir"], "IR missing before train_agents", "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "train_agents", "missing_ir", {})

    state = _ensure_registry_bundle(state)
    try:
        state, policy = _ensure_context_snapshot(state, policy)
    except Exception as exc:
        issue = _make_issue(["semantic", "context_snapshot_ref"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "train_agents", "context_missing", {})

    store = FileSystemCAS(_cas_root(state))
    try:
        world_state = load_state_snapshot(
            store, snapshot_ref=ArtifactID.model_validate(policy.semantic.context_snapshot_ref)
        )
    except Exception as exc:
        issue = _make_issue(["semantic", "context_snapshot_ref"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "train_agents", "context_load_failed", {})

    program_graph_ref = state.get("program_graph_ref")
    exec_plan_ref = state.get("exec_plan_ref")
    if not program_graph_ref or not exec_plan_ref:
        issue = _make_issue(["program_graph_ref"], "Compiled program missing", "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit(
            {**state, "feedback": feedback}, "train_agents", "missing_program", {}
        )

    try:
        program_graph = _load_model_from_ref(
            store, ArtifactRef.model_validate(program_graph_ref), ProgramGraph
        )
        exec_plan = _load_model_from_ref(store, ArtifactRef.model_validate(exec_plan_ref), ExecPlan)
    except Exception as exc:
        issue = _make_issue(["program_graph_ref"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "train_agents", "load_failed", {})

    agent_nodes = [
        node for node in program_graph.nodes if node.mechanism_type == "adaptive_agent"
    ]
    if not agent_nodes:
        return append_audit(state, "train_agents", "skipped", {"reason": "no_adaptive_agent"})

    config = state.get("agent_training_config") or {}
    steps = int(config.get("steps", 50))
    learning_rate = float(config.get("learning_rate", 0.01))
    seed = int(config.get("seed", state.get("random_seed") or 0))
    risk_penalty = float(config.get("risk_penalty", 1.0))
    entropy_beta = float(config.get("entropy_beta", 0.0))
    saturation_epsilon = float(config.get("saturation_epsilon", 1e-3))
    batch_size = int(config.get("batch_size", 1))
    income_noise = float(config.get("income_noise", 0.0))
    risk_noise = float(config.get("risk_noise", 0.0))
    tax_rate_spread = float(config.get("tax_rate_spread", 0.0))
    batch_tax_rates = config.get("batch_tax_rates")
    eval_stochastic = bool(config.get("eval_stochastic", False))

    if steps <= 0 or learning_rate <= 0 or batch_size <= 0:
        issue = _make_issue(
            ["agent_training_config"],
            "Training config requires steps > 0, learning_rate > 0, batch_size > 0",
            "runtime",
        )
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "train_agents", "invalid_cfg", {})

    n_agents = getattr(world_state.agents, "size", None)
    if n_agents is None:
        n_agents = int(world_state.agents.income.shape[0])
    n_firms = getattr(world_state.firms, "size", None)
    if n_firms is None:
        n_firms = int(world_state.firms.capital.shape[0])
    step = int(getattr(world_state, "step", 0))

    tax_rate_value = None
    for node in program_graph.nodes:
        if node.mechanism_type != "income_tax" or node.params_ref is None:
            continue
        payload = _load_payload(store, node.params_ref)
        schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
        start, end = schedule_range(schedule)
        if step < start or step > end:
            continue
        params = payload.get("params", {})
        tax_mech = create_mechanism_from_spec(
            "income_tax", params, n_agents=n_agents, n_firms=n_firms
        )
        tax_rate_value = tax_mech.rate
        break
    if tax_rate_value is None:
        tax_rate_value = jnp.array(0.0, dtype=jnp.float32)

    base_state = world_state.replace(
        agents=world_state.agents.replace(reported_income=world_state.agents.income)
    )
    base_income = base_state.agents.income
    base_risk = base_state.agents.risk_aversion
    base_tax_rate = jnp.asarray(tax_rate_value, dtype=jnp.float32)

    def _select_action_for_slot(
        action_val: jnp.ndarray, affects_list: list[str], slot_id: str
    ) -> jnp.ndarray:
        if action_val.ndim == 1:
            return action_val
        if action_val.ndim == 2:
            if slot_id in affects_list and action_val.shape[1] == len(affects_list):
                return action_val[:, affects_list.index(slot_id)]
            return action_val[:, 0]
        return action_val.reshape((action_val.shape[0],))

    def _prepare_batch_inputs(key: jax.Array) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
        batch_count = batch_size
        tax_rate_values = None
        if batch_tax_rates is not None:
            tax_rate_values = jnp.asarray(batch_tax_rates, dtype=jnp.float32)
            if tax_rate_values.ndim != 1:
                raise ValueError("agent_training_config.batch_tax_rates must be a 1D list")
            if tax_rate_values.size == 0:
                raise ValueError("agent_training_config.batch_tax_rates cannot be empty")
            if batch_count <= 1:
                batch_count = int(tax_rate_values.shape[0])
            elif tax_rate_values.shape[0] != batch_count:
                raise ValueError("agent_training_config.batch_tax_rates length must match batch_size")
        if batch_count <= 0:
            batch_count = 1
        income_batch = jnp.broadcast_to(base_income, (batch_count,) + base_income.shape)
        risk_batch = jnp.broadcast_to(base_risk, (batch_count,) + base_risk.shape)
        if income_noise > 0.0:
            key, subkey = jax.random.split(key)
            noise = jax.random.normal(subkey, shape=income_batch.shape)
            income_batch = jnp.maximum(income_batch * (1.0 + income_noise * noise), 0.0)
        if risk_noise > 0.0:
            key, subkey = jax.random.split(key)
            noise = jax.random.normal(subkey, shape=risk_batch.shape)
            risk_batch = jnp.clip(risk_batch + risk_noise * noise, 0.0, 1.0)
        if tax_rate_values is None:
            if batch_count > 1 and tax_rate_spread > 0.0:
                key, subkey = jax.random.split(key)
                offsets = jax.random.uniform(
                    subkey,
                    shape=(batch_count,),
                    minval=-tax_rate_spread,
                    maxval=tax_rate_spread,
                )
                tax_rate_values = jnp.clip(base_tax_rate + offsets, 0.0, 1.0)
            else:
                tax_rate_values = jnp.full((batch_count,), base_tax_rate)
        return income_batch, risk_batch, tax_rate_values

    weights_refs: dict[str, ArtifactRef] = {}
    training_metrics: dict[str, Any] = {}
    updated_nodes: list[Any] = []

    try:
        for node in program_graph.nodes:
            if node.mechanism_type != "adaptive_agent" or node.params_ref is None:
                updated_nodes.append(node)
                continue

            payload = _load_payload(store, node.params_ref)
            params = dict(payload.get("params", {}))
            action_space = params.get("action_space") or {}
            action_type = action_space.get("type", "continuous")
            affects = action_space.get("affects")
            affects_list = [affects] if isinstance(affects, str) else list(affects or [])
            if "agents.reported_income" not in affects_list:
                updated_nodes.append(node)
                continue
            if action_type == "discrete":
                issue = _make_issue(
                    ["semantic", "interventions", node.node_id],
                    "Discrete adaptive_agent training is not supported yet",
                    "runtime",
                )
                feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
                return append_audit(
                    {**state, "feedback": feedback}, "train_agents", "unsupported_action", {}
                )

            mechanism = create_mechanism_from_spec(
                "adaptive_agent", params, n_agents=n_agents, n_firms=n_firms
            )
            observation_space = mechanism.observation_space
            policy_params, policy_static = eqx.partition(
                mechanism.policy, eqx.is_inexact_array
            )

            def _loss_fn(
                policy_params: Any, key: jax.Array, batch_inputs: tuple[jnp.ndarray, ...]
            ):
                policy = eqx.combine(policy_static, policy_params)
                income_batch, risk_batch, tax_rate_batch = batch_inputs
                batch_count = income_batch.shape[0]
                keys = jax.random.split(key, batch_count)

                def _loss_single(
                    income: jnp.ndarray,
                    risk_aversion: jnp.ndarray,
                    tax_rate: jnp.ndarray,
                    subkey: jax.Array,
                ):
                    agents_state = base_state.agents.replace(
                        income=income,
                        risk_aversion=risk_aversion,
                        reported_income=income,
                    )
                    mini_state = base_state.replace(agents=agents_state)
                    obs = build_observations(
                        mini_state,
                        observation_space,
                        overrides={"tax_rate": tax_rate},
                    )
                    logits = policy(obs)
                    action_val = continuous_actions_from_logits(
                        logits,
                        action_space,
                        key=subkey,
                        stochastic=False,
                    )
                    action_val = _select_action_for_slot(
                        action_val, affects_list, "agents.reported_income"
                    )
                    action_norm = normalize_action(action_val, action_space)
                    reported = income * action_val
                    updated_state = mini_state.replace(
                        agents=agents_state.replace(reported_income=reported)
                    )
                    tax_amount = compute_tax(updated_state, tax_rate)
                    hidden_income = income - reported
                    penalty = risk_penalty * (risk_aversion * hidden_income)
                    reward = income - tax_amount - penalty
                    avg_reward = jnp.mean(reward)
                    denom = jnp.maximum(income, 1e-6)
                    reported_ratio = jnp.mean(reported / denom)
                    entropy = policy_entropy(action_norm)
                    sat_rate = saturation_rate(action_norm, epsilon=saturation_epsilon)
                    return -(avg_reward + entropy_beta * entropy), {
                        "avg_reward": avg_reward,
                        "avg_reported_ratio": reported_ratio,
                        "entropy": entropy,
                        "saturation_rate": sat_rate,
                        "action_mean": jnp.mean(action_val),
                        "action_var": jnp.var(action_val),
                    }

                losses, metrics = jax.vmap(_loss_single, in_axes=(0, 0, 0, 0))(
                    income_batch, risk_batch, tax_rate_batch, keys
                )
                loss = jnp.mean(losses)
                metrics = jax.tree_util.tree_map(lambda x: jnp.mean(x), metrics)
                return loss, metrics

            optimizer = optax.adam(learning_rate)
            opt_state = optimizer.init(policy_params)
            key = jax.random.PRNGKey(seed)

            loss_history: list[float] = []
            reward_history: list[float] = []
            reported_history: list[float] = []
            entropy_history: list[float] = []
            saturation_history: list[float] = []
            action_mean_history: list[float] = []
            action_var_history: list[float] = []
            grad_norms: list[float] = []
            grad_nan_history: list[float] = []
            grad_inf_history: list[float] = []
            grad_vanishing_history: list[bool] = []
            grad_exploding_history: list[bool] = []
            batch_size_used: int | None = None

            for _ in range(steps):
                key, batch_key, loss_key = jax.random.split(key, 3)
                batch_inputs = _prepare_batch_inputs(batch_key)
                batch_size_used = int(batch_inputs[0].shape[0])
                (loss_val, aux), grads = eqx.filter_value_and_grad(_loss_fn, has_aux=True)(
                    policy_params, loss_key, batch_inputs
                )
                updates, opt_state = optimizer.update(grads, opt_state, policy_params)
                policy_params = optax.apply_updates(policy_params, updates)

                loss_history.append(float(loss_val))
                reward_history.append(float(aux["avg_reward"]))
                reported_history.append(float(aux["avg_reported_ratio"]))
                entropy_history.append(float(aux["entropy"]))
                saturation_history.append(float(aux["saturation_rate"]))
                action_mean_history.append(float(aux["action_mean"]))
                action_var_history.append(float(aux["action_var"]))
                health_report, _ = gradient_health_report(grads)
                grad_norms.append(float(health_report.grad_norm))
                grad_nan_history.append(float(health_report.nan_frac))
                grad_inf_history.append(float(health_report.inf_frac))
                grad_vanishing_history.append(bool(health_report.vanishing))
                grad_exploding_history.append(bool(health_report.exploding))

            trained_policy = eqx.combine(policy_static, policy_params)
            buf = BytesIO()
            eqx.tree_serialise_leaves(buf, trained_policy)
            weights_ref = store.put_bytes(
                buf.getvalue(),
                PutOptions(
                    kind="foundry.agent_weights",
                    media_type="application/octet-stream",
                    inputs=[
                        InputRef(artifact_id=node.params_ref.artifact_id, role="params"),
                    ],
                ),
            )
            weights_refs[node.node_id] = weights_ref
            training_metrics[node.node_id] = {
                "loss_history": loss_history,
                "reward_history": reward_history,
                "reported_ratio_history": reported_history,
                "entropy_history": entropy_history,
                "saturation_rate_history": saturation_history,
                "action_mean_history": action_mean_history,
                "action_var_history": action_var_history,
                "grad_norm_history": grad_norms,
                "grad_nan_frac_history": grad_nan_history,
                "grad_inf_frac_history": grad_inf_history,
                "grad_vanishing_history": grad_vanishing_history,
                "grad_exploding_history": grad_exploding_history,
                "final_loss": loss_history[-1] if loss_history else None,
                "final_reward": reward_history[-1] if reward_history else None,
                "final_entropy": entropy_history[-1] if entropy_history else None,
                "final_saturation_rate": saturation_history[-1] if saturation_history else None,
                "batch_size": batch_size_used,
            }

            params["weights_artifact"] = str(weights_ref.artifact_id)
            params["stochastic"] = eval_stochastic
            new_payload = {**payload, "params": params}
            new_params_ref = store.put_json(
                new_payload,
                PutOptions(
                    kind="ir.intervention_payload",
                    media_type="application/json",
                    inputs=[
                        InputRef(artifact_id=node.params_ref.artifact_id, role="params:base"),
                        InputRef(artifact_id=weights_ref.artifact_id, role="agent_weights"),
                    ],
                ),
            )
            updated_nodes.append(node.model_copy(update={"params_ref": new_params_ref}))
    except Exception as exc:
        issue = _make_issue(["train_agents"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "train_agents", "failed", {})

    if not weights_refs:
        return append_audit(state, "train_agents", "skipped", {"reason": "no_trainable_agents"})

    program_inputs = [
        InputRef(
            artifact_id=ArtifactRef.model_validate(program_graph_ref).artifact_id,
            role="program_graph",
        )
    ]
    for node_id, ref in weights_refs.items():
        program_inputs.append(InputRef(artifact_id=ref.artifact_id, role=f"agent_weights:{node_id}"))

    updated_program_graph = ProgramGraph(
        ir_ref=program_graph.ir_ref,
        nodes=updated_nodes,
        edges=program_graph.edges,
        entrypoints=program_graph.entrypoints,
        notes=program_graph.notes,
    )
    program_ref = store.put_json(
        updated_program_graph,
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.1.0"),
            inputs=program_inputs,
        ),
    )
    updated_program_ref = ProgramGraphRef(artifact_id=program_ref.artifact_id)

    updated_exec_plan = exec_plan.model_copy(update={"program_ref": updated_program_ref})
    exec_plan_ref = store.put_json(
        updated_exec_plan,
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.1.0"),
            inputs=[InputRef(artifact_id=updated_program_ref.artifact_id, role="program_graph")],
        ),
    )
    updated_exec_ref = ExecPlanRef(artifact_id=exec_plan_ref.artifact_id)

    report_payload = {
        "ok": True,
        "steps": steps,
        "learning_rate": learning_rate,
        "risk_penalty": risk_penalty,
        "entropy_beta": entropy_beta,
        "saturation_epsilon": saturation_epsilon,
        "batch_size": batch_size,
        "income_noise": income_noise,
        "risk_noise": risk_noise,
        "tax_rate_spread": tax_rate_spread,
        "batch_tax_rates": batch_tax_rates,
        "eval_stochastic": eval_stochastic,
        "weights": {node_id: str(ref.artifact_id) for node_id, ref in weights_refs.items()},
        "metrics": training_metrics,
    }
    report_ref = store.put_json(
        report_payload,
        PutOptions(
            kind="scientist.agent_training_report",
            media_type="application/json",
            inputs=[
                InputRef(artifact_id=updated_program_ref.artifact_id, role="program_graph"),
            ],
        ),
    )

    if state.get("run_id"):
        log_artifact(
            run_id=state["run_id"],
            artifact_type="agent_training_report_ref",
            payload=report_ref.model_dump(),
            media_type="application/json",
            step="train_agents",
            base_dir=_runtime_base_dir(state),
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="program_graph_ref",
            payload=updated_program_ref.model_dump(),
            media_type="application/json",
            step="train_agents",
            base_dir=_runtime_base_dir(state),
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="exec_plan_ref",
            payload=updated_exec_ref.model_dump(),
            media_type="application/json",
            step="train_agents",
            base_dir=_runtime_base_dir(state),
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="agent_weights_ref",
            payload={node_id: ref.model_dump() for node_id, ref in weights_refs.items()},
            media_type="application/json",
            step="train_agents",
            base_dir=_runtime_base_dir(state),
        )

    return append_audit(
        {
            **state,
            "program_graph_ref": updated_program_ref.model_dump(),
            "exec_plan_ref": updated_exec_ref.model_dump(),
            "agent_training_report_ref": report_ref.model_dump(),
            "agent_weights_ref": {
                node_id: ref.model_dump() for node_id, ref in weights_refs.items()
            },
        },
        "train_agents",
        "completed",
        {"trained_nodes": sorted(weights_refs.keys())},
    )


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
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "missing_ir", {})

    state = _ensure_registry_bundle(state)
    try:
        registry_content = _load_registry_bundle_content_for(state, policy)
    except Exception as exc:
        issue = _make_issue(["semantic", "registry_bundle_ref"], str(exc), "registry")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "registry_failed", {})
    seed = state.get("random_seed") or 42
    snapshot_ref_value = policy.semantic.context_snapshot_ref
    if not snapshot_ref_value:
        issue = _make_issue(
            ["semantic", "context_snapshot_ref"],
            "context_snapshot_ref missing before run_sim",
            "runtime",
        )
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "context_missing", {})
    program_graph_ref = state.get("program_graph_ref")
    exec_plan_ref = state.get("exec_plan_ref")
    if not program_graph_ref or not exec_plan_ref:
        issue = _make_issue(["program_graph_ref"], "Compiled program missing", "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "missing_program", {})

    try:
        snapshot_ref = ArtifactRef(
            artifact_id=ArtifactID.model_validate(snapshot_ref_value),
            kind="foundry.state_snapshot",
            media_type="application/json",
        )
    except Exception as exc:
        issue = _make_issue(
            ["semantic", "context_snapshot_ref"], f"Invalid context_snapshot_ref: {exc}", "runtime"
        )
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "context_missing", {})

    try:
        job_spec = JobSpec(
            program_ref=ArtifactRef.model_validate(program_graph_ref),
            exec_plan_ref=ArtifactRef.model_validate(exec_plan_ref),
            state_snapshot_ref=snapshot_ref,
            seed=seed,
        )
        backend = resolve_backend(state.get("runner_backend"))
        job_result = run_job(
            job_spec,
            backend=backend,
            registry_content=registry_content,
            cas_root=_cas_root(state),
        )
        if job_result.issues or job_result.warnings:
            issues = list(job_result.issues)
            if not issues and job_result.warnings:
                issues = [
                    _make_issue(["runtime"], warning, "runtime")
                    for warning in job_result.warnings
                ]
            feedback = {"verdict": "NEEDS_REVISION", "issues": issues}
            return append_audit({**state, "feedback": feedback}, "run_sim", "failed", {})

        if job_result.state_delta_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="state_delta_ref",
                payload=job_result.state_delta_ref.model_dump(),
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
        if job_result.metrics_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="metrics_ref",
                payload=job_result.metrics_ref.model_dump(),
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
        if job_result.environment_ref is not None:
            payload = {
                "environment_ref": job_result.environment_ref.model_dump(),
                "fingerprint": job_result.environment_fingerprint,
            }
            log_artifact(
                run_id=state["run_id"],
                artifact_type="environment_ref",
                payload=payload,
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
        if job_result.state_snapshot_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="state_snapshot_ref",
                payload=job_result.state_snapshot_ref.model_dump(),
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
        if job_result.simulation_results_ref is not None:
            log_artifact(
                run_id=state["run_id"],
                artifact_type="simulation_results_ref",
                payload=job_result.simulation_results_ref.model_dump(),
                media_type="application/json",
                step="run_sim",
                base_dir=_runtime_base_dir(state),
            )
    except Exception as exc:
        issue = _make_issue(["runtime"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_sim", "failed", {})

    results: dict[str, Any] = {}
    if job_result.simulation_results_ref is not None:
        try:
            results = _load_payload(FileSystemCAS(_cas_root(state)), job_result.simulation_results_ref)
        except Exception as exc:
            issue = _make_issue(
                ["simulation_results_ref"], f"Failed to load results: {exc}", "runtime"
            )
            feedback: GovernorFeedback = {"verdict": "NEEDS_REVISION", "issues": [issue]}
            return append_audit({**state, "feedback": feedback}, "run_sim", "failed", {})

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
            "simulation_results_ref": job_result.simulation_results_ref.model_dump()
            if job_result.simulation_results_ref is not None
            else None,
            "state_delta_ref": job_result.state_delta_ref.model_dump()
            if job_result.state_delta_ref is not None
            else None,
            "metrics_ref": job_result.metrics_ref.model_dump() if job_result.metrics_ref is not None else None,
            "state_snapshot_ref": job_result.state_snapshot_ref.model_dump()
            if job_result.state_snapshot_ref is not None
            else None,
        },
        "run_sim",
        "completed",
        results,
    )


def run_calibration_node(state: ExperimentState) -> ExperimentState:
    state = _ensure_run(state)
    if state.get("pruned") or _blocked_by_feedback(state):
        return append_audit(state, "run_calibration", "skipped", {"reason": "feedback_blocked"})
    state = _check_budget(state, "sim")
    if state.get("pruned"):
        return state

    cfg_raw = state.get("calibration_config")
    if cfg_raw is None:
        issue = _make_issue(["calibration_config"], "Calibration config missing", "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "missing_cfg", {})
    try:
        cfg = cfg_raw if isinstance(cfg_raw, CalibrationConfig) else CalibrationConfig.model_validate(cfg_raw)
    except Exception as exc:
        issue = _make_issue(["calibration_config"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "invalid_cfg", {})

    policy = state.get("ir")
    if policy is None:
        issue = _make_issue(["ir"], "IR missing before run_calibration", "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "missing_ir", {})

    state = _ensure_registry_bundle(state)
    try:
        state, policy = _ensure_context_snapshot(state, policy)
    except Exception as exc:
        issue = _make_issue(["semantic", "context_snapshot_ref"], str(exc), "registry")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "context_missing", {})
    try:
        registry_content = _load_registry_bundle_content_for(state, policy)
    except Exception as exc:
        issue = _make_issue(["semantic", "registry_bundle_ref"], str(exc), "registry")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "registry_failed", {})

    store = FileSystemCAS(_cas_root(state))
    try:
        world_state = load_state_snapshot(
            store,
            snapshot_ref=ArtifactID.model_validate(policy.semantic.context_snapshot_ref),
        )
    except Exception as exc:
        issue = _make_issue(["semantic", "context_snapshot_ref"], str(exc), "data")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "context_load_failed", {})

    program_graph_ref = state.get("program_graph_ref")
    exec_plan_ref = state.get("exec_plan_ref")
    if not program_graph_ref or not exec_plan_ref:
        issue = _make_issue(["program_graph_ref"], "Compiled program missing", "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "missing_program", {})

    try:
        program_graph = _load_model_from_ref(
            store, ArtifactRef.model_validate(program_graph_ref), ProgramGraph
        )
        exec_plan = _load_model_from_ref(store, ArtifactRef.model_validate(exec_plan_ref), ExecPlan)
    except Exception as exc:
        issue = _make_issue(["program_graph_ref"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "load_failed", {})

    raw_targets: dict[str, Any] = {}
    raw_targets.update(state.get("calibration_raw_targets") or {})
    evidence_refs: list[ArtifactRef] = []
    if any(t.fabric_query is not None for t in cfg.targets):
        db_path = state.get("db_path") or "simulation.duckdb"
        graph_path = state.get("graph_path")
        db = SimulationDB(db_path)
        graph = GraphStore(str(graph_path)) if graph_path else None
        udf = UDFEngine(db, graph) if graph is not None else UDFEngine(db)
        try:
            for target in cfg.targets:
                if target.fabric_query is None:
                    continue
                request = DataViewRequest.model_validate(target.fabric_query)
                result = udf.query_result(request)
                df = udf._materialize_dataframe(result.data_ref)
                raw_targets[target.target_id] = extract_fabric_series(df, target, request)
                evidence_refs.append(ArtifactRef.model_validate(result.evidence_ref.model_dump()))
        finally:
            db.close()

    constraint_values: dict[str, float] = {}
    for constraint in policy.semantic.constraints:
        value = _coerce_number(constraint.value)
        if value is not None:
            constraint_values[constraint.constraint_id] = value

    def parameter_loader(ref_or_node: Any) -> dict[str, Any]:
        params_ref = None
        if isinstance(ref_or_node, ArtifactRef):
            params_ref = ref_or_node
        else:
            params_ref = getattr(ref_or_node, "params_ref", None)
        if params_ref is None:
            return {}
        return _load_payload(store, params_ref)

    controls_seq = state.get("calibration_controls_seq")
    if controls_seq is not None:
        controls_seq = jnp.asarray(controls_seq)

    try:
        inputs = CalibratorInputs(
            config=cfg,
            program_graph=program_graph,
            exec_plan=exec_plan,
            base_state=world_state,
            mechanism_registry=registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            selector_field_registry=registry_content.selector_field_registry,
            constraint_registry=registry_content.constraint_registry,
            constraint_values=constraint_values or None,
            parameter_loader=parameter_loader,
            raw_targets=raw_targets,
            controls_seq=controls_seq,
        )
        report = Calibrator(inputs).run()
    except Exception as exc:
        issue = _make_issue(["calibration"], str(exc), "runtime")
        feedback: GovernorFeedback = {"verdict": "REJECT", "issues": [issue]}
        return append_audit({**state, "feedback": feedback}, "run_calibration", "failed", {})

    config_ref = put_calibration_config(store, cfg)
    report_inputs = [InputRef(artifact_id=config_ref.artifact_id, role="calibration_config")]
    for evidence_ref in evidence_refs:
        report_inputs.append(InputRef(artifact_id=evidence_ref.artifact_id, role="fabric_evidence"))
    report_ref = put_calibration_report(store, report, inputs=report_inputs)

    if state.get("run_id"):
        log_artifact(
            run_id=state["run_id"],
            artifact_type="calibration_config_ref",
            payload=config_ref.model_dump(),
            media_type="application/json",
            step="run_calibration",
            base_dir=_runtime_base_dir(state),
        )
        log_artifact(
            run_id=state["run_id"],
            artifact_type="calibration_report_ref",
            payload=report_ref.model_dump(),
            media_type="application/json",
            step="run_calibration",
            base_dir=_runtime_base_dir(state),
        )

    updates_by_node: dict[str, dict[str, float]] = {}
    for key, value in report.calibrated_params.items():
        if "." not in key:
            continue
        node_id, param_id = key.split(".", 1)
        updates_by_node.setdefault(node_id, {})[param_id] = value

    updated_params_ref: dict[str, ArtifactRef] = {}
    for node in program_graph.nodes:
        if node.node_id not in updates_by_node:
            continue
        if node.params_ref is None:
            continue
        payload = _load_payload(store, node.params_ref)
        params = dict(payload.get("params") or {})
        for param_id, value in updates_by_node[node.node_id].items():
            params[param_id] = Decimal(str(value))
        payload["params"] = params
        new_ref = store.put_json(
            payload,
            PutOptions(kind="ir.intervention_payload", media_type="application/json"),
        )
        updated_params_ref[node.node_id] = ArtifactRef.model_validate(new_ref.model_dump())

    new_program_graph_ref = ProgramGraphRef.model_validate(program_graph_ref)
    new_exec_plan_ref = ExecPlanRef.model_validate(exec_plan_ref)
    if updated_params_ref:
        updated_nodes = []
        for node in program_graph.nodes:
            if node.node_id in updated_params_ref:
                updated_nodes.append(
                    node.model_copy(update={"params_ref": updated_params_ref[node.node_id]})
                )
            else:
                updated_nodes.append(node)
        updated_graph = program_graph.model_copy(update={"nodes": updated_nodes})
        graph_inputs = [
            InputRef(
                artifact_id=_artifact_id(ArtifactRef.model_validate(program_graph_ref)),
                role="program_graph",
            )
        ]
        for node_id, params_ref in updated_params_ref.items():
            graph_inputs.append(
                InputRef(artifact_id=params_ref.artifact_id, role=f"params:{node_id}")
            )
        stored_graph_ref = store.put_json(
            updated_graph,
            PutOptions(
                kind="foundry.program_graph",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.1.0"),
                inputs=graph_inputs,
            ),
        )
        new_program_graph_ref = ProgramGraphRef(artifact_id=stored_graph_ref.artifact_id)
        updated_exec_plan = exec_plan.model_copy(update={"program_ref": new_program_graph_ref})
        stored_exec_plan_ref = store.put_json(
            updated_exec_plan,
            PutOptions(
                kind="foundry.exec_plan",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.1.0"),
                inputs=[InputRef(artifact_id=new_program_graph_ref.artifact_id, role="program_graph")],
            ),
        )
        new_exec_plan_ref = ExecPlanRef(artifact_id=stored_exec_plan_ref.artifact_id)

        if state.get("run_id"):
            log_artifact(
                run_id=state["run_id"],
                artifact_type="program_graph_ref",
                payload=new_program_graph_ref.model_dump(),
                media_type="application/json",
                step="run_calibration",
                base_dir=_runtime_base_dir(state),
            )
            log_artifact(
                run_id=state["run_id"],
                artifact_type="exec_plan_ref",
                payload=new_exec_plan_ref.model_dump(),
                media_type="application/json",
                step="run_calibration",
                base_dir=_runtime_base_dir(state),
            )

    updated_params_payload = {
        node_id: ref.model_dump() for node_id, ref in updated_params_ref.items()
    }

    return append_audit(
        {
            **state,
            "calibration_report_ref": report_ref.model_dump(),
            "calibration_config_ref": config_ref.model_dump(),
            "calibrated_params": report.calibrated_params,
            "calibrated_params_ref": updated_params_payload,
            "program_graph_ref": new_program_graph_ref.model_dump(),
            "exec_plan_ref": new_exec_plan_ref.model_dump(),
        },
        "run_calibration",
        "completed",
        {"targets": len(cfg.targets), "updated_params": len(updated_params_ref)},
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
            gate_decision
            if isinstance(gate_decision, GateDecision)
            else GateDecision.model_validate(gate_decision)
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
