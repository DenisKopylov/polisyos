from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Mapping
import uuid
import warnings

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.observability import get_tracer
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent.memory import ShortTermMemory, TurnRole
from polisyos.scientist.agent.protocols import (
    CriticAgent,
    CritiqueIssue,
    CritiqueReport,
    DraftResult,
    DrafterAgent,
    FormalizerAgent,
    PIAgent,
    ProblemFrame,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState as EngineExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestrator.agent_factory import build_agent_stack, resolve_critic_agent
from polisyos.scientist.orchestrator.state import ExperimentState

_LOGGER = logging.getLogger(__name__)
_WARNED = False


class _SemanticView:
    def __init__(self, bundle: TrinityBundle) -> None:
        self.interventions = list(bundle.policy_spec.interventions)


class LegacyIRView:
    """Thin compatibility wrapper exposing `ir.semantic.interventions`."""

    def __init__(self, bundle: TrinityBundle) -> None:
        self.trinity_bundle = bundle
        self.semantic = _SemanticView(bundle)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.trinity_bundle, name)


def _warn_once() -> None:
    global _WARNED
    if _WARNED:
        return
    warnings.warn(
        "polisyos.scientist.orchestrator.flow_nodes is deprecated; use "
        "polisyos.scientist.workflows.default where possible.",
        DeprecationWarning,
        stacklevel=2,
    )
    _WARNED = True


def _run_async(coro):
    return asyncio.run(coro)


def _to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _ensure_run(state: ExperimentState) -> ExperimentState:
    if state.get("run_id"):
        return state
    updated = dict(state)
    updated["run_id"] = f"R_{uuid.uuid4().hex[:12]}"
    return updated


def _check_budget(state: ExperimentState, counter_key: str) -> ExperimentState:
    budget = dict(state.get("budget") or {})
    usage = dict(state.get("budget_usage") or {})
    current = float(usage.get(counter_key, 0.0))
    usage[counter_key] = current + 1.0

    hard_key = {
        "llm_calls": "max_llm_calls",
        "sim_runs": "max_sim_runs",
    }.get(counter_key)

    updated = dict(state)
    updated["budget_usage"] = usage
    if hard_key and hard_key in budget and usage[counter_key] > float(budget[hard_key]):
        updated["pruned"] = True
        updated["feedback"] = {
            "verdict": "REJECT",
            "issues": [
                {
                    "severity": "error",
                    "error_type": "budget",
                    "code": "BUDGET_EXHAUSTED",
                    "message": f"Budget '{hard_key}' exhausted",
                }
            ],
        }
    return updated


def _load_memory(state: ExperimentState) -> ShortTermMemory:
    payload = state.get("short_term_memory")
    if isinstance(payload, Mapping):
        try:
            return ShortTermMemory.from_dict(dict(payload))
        except Exception:
            return ShortTermMemory()
    return ShortTermMemory()


def _as_problem_frame(value: Any, *, user_request: str = "") -> ProblemFrame:
    if isinstance(value, ProblemFrame):
        return value

    if isinstance(value, Mapping):
        frame_id = _to_str(value.get("frame_id") or value.get("problem_id"), "pf_legacy")
        domain = _to_str(value.get("domain"), "economic")
        problem_statement = _to_str(value.get("problem_statement"), user_request)
        actors = tuple(str(item) for item in value.get("actors", ()) if item is not None)
        goals = tuple(str(item) for item in value.get("goals", ()) if item is not None)
        constraints = tuple(
            str(item) for item in value.get("constraints", ()) if item is not None
        )
        assumptions = tuple(
            str(item) for item in value.get("assumptions", ()) if item is not None
        )
        success_criteria = value.get("success_criteria") if isinstance(
            value.get("success_criteria"), dict
        ) else {}
        context = value.get("context") if isinstance(value.get("context"), dict) else {}
        return ProblemFrame(
            frame_id=frame_id,
            domain=domain,
            problem_statement=problem_statement,
            actors=actors,
            goals=goals,
            constraints=constraints,
            success_criteria=success_criteria,
            assumptions=assumptions,
            context=context,
            created_at=datetime.utcnow(),
        )

    # Best-effort conversion from IR ProblemFrame-like objects.
    frame_id = _to_str(getattr(value, "problem_id", None) or getattr(value, "frame_id", None))
    if not frame_id:
        frame_id = "pf_legacy"
    domain_raw = getattr(value, "domain", "economic")
    domain = _to_str(getattr(domain_raw, "value", domain_raw), "economic")
    statement = _to_str(getattr(value, "problem_statement", None), user_request)
    return ProblemFrame(
        frame_id=frame_id,
        domain=domain,
        problem_statement=statement,
        created_at=datetime.utcnow(),
    )


def _issue_to_dict(issue: CritiqueIssue) -> dict[str, Any]:
    return {
        "issue_id": issue.issue_id,
        "category": issue.category.value if hasattr(issue.category, "value") else str(issue.category),
        "severity": issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
        "message": issue.message,
        "location": issue.location,
        "suggestion": issue.suggestion,
        "evidence": dict(issue.evidence or {}),
    }


def _critique_to_dict(report: CritiqueReport) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "ir_ref": report.ir_ref,
        "problem_frame_ref": report.problem_frame_ref,
        "verdict": report.verdict,
        "issues": [_issue_to_dict(issue) for issue in report.issues],
        "alignment_score": report.alignment_score,
        "completeness_score": report.completeness_score,
        "overall_quality": report.overall_quality,
        "reflexion_hint": report.reflexion_hint,
        "metadata": dict(report.metadata or {}),
        "created_at": report.created_at.isoformat(),
    }


def _resolve_agents(
    state: ExperimentState, memory: ShortTermMemory
) -> tuple[PIAgent, DrafterAgent, FormalizerAgent, CriticAgent]:
    llm_client = state.get("llm_client")
    model_name = _to_str(state.get("model_name"), "") or None

    stack = build_agent_stack(
        llm_client=llm_client,
        model_name=model_name,
        memory=memory,
    )

    pi = state.get("pi_agent")
    if not isinstance(pi, PIAgent):
        pi = stack.pi

    drafter = state.get("drafter_agent")
    if not isinstance(drafter, DrafterAgent):
        drafter = stack.drafter

    formalizer = state.get("formalizer_agent")
    if not isinstance(formalizer, FormalizerAgent):
        formalizer = stack.formalizer

    # Wiring target: resolve critic through factory (feature-flag aware) unless explicit override.
    critic = resolve_critic_agent(
        state,
        llm_client=llm_client,
        model_name=model_name,
    )

    return pi, drafter, formalizer, critic


def _extract_trinity_bundle(ir: Any) -> TrinityBundle | None:
    if isinstance(ir, TrinityBundle):
        return ir
    candidate = getattr(ir, "trinity_bundle", None)
    if isinstance(candidate, TrinityBundle):
        return candidate
    return None


def pi_decompose_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    tracer = get_tracer()
    state = _ensure_run(state)
    with tracer.start_as_current_span(
        "pi_decompose_node",
        attributes={
            "polisyos.phase": "FRAME",
            "polisyos.agent.name": "pi",
            "polisyos.run_id": _to_str(state.get("run_id")),
        },
    ):
        if state.get("problem_frame"):
            return state

        memory = _load_memory(state)
        pi, _, _, _ = _resolve_agents(state, memory)
        user_request = _to_str(state.get("user_request"), "")
        if not user_request:
            return state

        frame = _run_async(pi.create_problem_frame(user_request))
        updated = dict(state)
        updated["problem_frame"] = frame
        memory.add_turn(TurnRole.USER, user_request)
        updated["short_term_memory"] = memory.to_dict()
        return updated


def drafter_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    tracer = get_tracer()
    state = _check_budget(_ensure_run(state), "llm_calls")
    with tracer.start_as_current_span(
        "drafter_node",
        attributes={
            "polisyos.phase": "DRAFT",
            "polisyos.agent.name": "drafter",
            "polisyos.run_id": _to_str(state.get("run_id")),
        },
    ):
        if state.get("pruned"):
            return state

        memory = _load_memory(state)
        pi, drafter, _, _ = _resolve_agents(state, memory)

        frame_value = state.get("problem_frame")
        if frame_value is None:
            user_request = _to_str(state.get("user_request"), "")
            if user_request:
                frame_value = _run_async(pi.create_problem_frame(user_request))
            else:
                frame_value = ProblemFrame(
                    frame_id="pf_legacy",
                    domain="economic",
                    problem_statement="",
                )
        problem_frame = _as_problem_frame(
            frame_value,
            user_request=_to_str(state.get("user_request"), ""),
        )

        hints = memory.get_hints()
        draft = _run_async(
            drafter.draft_policy(problem_frame, hints=hints if hints else None)
        )

        updated = dict(state)
        updated["problem_frame"] = problem_frame
        updated["draft_result"] = draft
        updated["short_term_memory"] = memory.to_dict()
        return updated


def formalize_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    tracer = get_tracer()
    state = _check_budget(_ensure_run(state), "llm_calls")
    with tracer.start_as_current_span(
        "formalize_node",
        attributes={
            "polisyos.phase": "FRAME",
            "polisyos.agent.name": "formalizer",
            "polisyos.run_id": _to_str(state.get("run_id")),
        },
    ):
        if state.get("pruned"):
            return state

        draft = state.get("draft_result")
        if not isinstance(draft, DraftResult):
            return state

        memory = _load_memory(state)
        _, _, formalizer, _ = _resolve_agents(state, memory)
        bundle = _run_async(formalizer.formalize(draft))

        updated = dict(state)
        updated["trinity_bundle"] = bundle
        updated["ir"] = LegacyIRView(bundle)
        return updated


def critic_review_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    tracer = get_tracer()
    state = _check_budget(_ensure_run(state), "llm_calls")
    with tracer.start_as_current_span(
        "critic_review_node",
        attributes={
            "polisyos.phase": "FRAME",
            "polisyos.agent.name": "critic",
            "polisyos.run_id": _to_str(state.get("run_id")),
        },
    ):
        if state.get("pruned"):
            return state

        ir = state.get("ir")
        bundle = _extract_trinity_bundle(ir)
        if bundle is None:
            return state

        memory = _load_memory(state)
        _, _, _, critic = _resolve_agents(state, memory)
        problem_frame = _as_problem_frame(
            state.get("problem_frame") or bundle.problem_frame,
            user_request=_to_str(state.get("user_request"), ""),
        )
        report = _run_async(critic.critique(bundle, problem_frame))

        updated = dict(state)
        updated["problem_frame"] = problem_frame
        updated["critic_agent"] = critic
        updated["critique_report"] = _critique_to_dict(report)
        memory.add_attempt(
            draft_summary=_to_str(getattr(state.get("draft_result"), "narrative", ""), ""),
            ir_summary=f"interventions={len(bundle.policy_spec.interventions)}",
            critique_verdict=report.verdict,
            critique_hint=report.reflexion_hint,
        )
        updated["short_term_memory"] = memory.to_dict()
        return updated


def _validate_ir_node_impl(state: ExperimentState) -> ExperimentState:
    critique = state.get("critique_report")
    if isinstance(critique, Mapping):
        verdict = _to_str(critique.get("verdict"), "APPROVE")
        issues = critique.get("issues")
        if not isinstance(issues, list):
            issues = []
        updated = dict(state)
        updated["feedback"] = {"verdict": verdict, "issues": list(issues)}
        return updated

    if state.get("ir") is None:
        updated = dict(state)
        updated["feedback"] = {
            "verdict": "REJECT",
            "issues": [
                {
                    "severity": "error",
                    "error_type": "schema",
                    "code": "IR_MISSING",
                    "message": "IR is missing",
                }
            ],
        }
        return updated

    updated = dict(state)
    updated["feedback"] = {"verdict": "APPROVE", "issues": []}
    return updated


def validate_ir_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    tracer = get_tracer()
    state = _ensure_run(state)
    with tracer.start_as_current_span(
        "validate_ir_node",
        attributes={
            "polisyos.phase": "FRAME",
            "polisyos.agent.name": "validator",
            "polisyos.run_id": _to_str(state.get("run_id")),
        },
    ) as span:
        updated = _validate_ir_node_impl(state)
        feedback = updated.get("feedback")
        if isinstance(feedback, Mapping):
            issues = feedback.get("issues")
            issue_count = len(issues) if isinstance(issues, list) else 0
            span.set_attribute("polisyos.validation.issue_count", issue_count)
            span.set_attribute("polisyos.verdict", _to_str(feedback.get("verdict")))
        return updated


def reflexion_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return state


def repair_ir_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return state


def compile_data_views_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return state


def train_agents_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return state


def analyze_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return state


def governor_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    if not state.get("require_human_gate"):
        return state

    if isinstance(state.get("gate_decision"), Mapping):
        return state

    updated = dict(state)
    updated["feedback"] = {"verdict": "HUMAN_GATE", "issues": []}
    updated["gate_request"] = {
        "reason": "human_gate_required",
        "run_id": _to_str(state.get("run_id")),
    }
    return updated


def pack_decision_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return state


def draft_ir_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return formalize_node(drafter_node(state))


def reflexion_repair_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return repair_ir_node(state)


def run_calibration_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    return state


def _cas_root(state: Mapping[str, Any]) -> Path:
    cas_root = state.get("cas_root")
    if isinstance(cas_root, str) and cas_root.strip():
        return Path(cas_root)
    return Path(".polisyos")


def _as_artifact_ref(value: Any, *, kind: str) -> ArtifactRef | None:
    if value is None:
        return None
    if isinstance(value, ArtifactRef):
        return value
    if hasattr(value, "model_dump"):
        try:
            value = value.model_dump()
        except Exception:
            value = None
    if not isinstance(value, Mapping):
        return None
    data = dict(value)
    if "kind" not in data:
        data["kind"] = kind
    if "media_type" not in data:
        data["media_type"] = "application/json"
    try:
        return ArtifactRef.model_validate(data)
    except Exception:
        return None


def _legacy_to_engine_state(state: Mapping[str, Any]) -> EngineExperimentState:
    inputs: dict[str, ArtifactRef] = {}
    artifacts: dict[str, ArtifactRef] = {}
    reports: dict[str, ArtifactRef] = {}

    trinity_ref = _as_artifact_ref(
        state.get(INPUT_TRINITY_BUNDLE_REF), kind="ir.trinity_bundle"
    )
    if trinity_ref is not None:
        inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    registry_ref = _as_artifact_ref(
        state.get(INPUT_REGISTRY_BUNDLE_REF), kind="core.registry_bundle"
    )
    if registry_ref is not None:
        inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_ref

    data_snapshot_ref = _as_artifact_ref(
        state.get(INPUT_DATA_SNAPSHOT_REF), kind="fabric.data_snapshot"
    )
    if data_snapshot_ref is not None:
        inputs[INPUT_DATA_SNAPSHOT_REF] = data_snapshot_ref

    state_snapshot_ref = _as_artifact_ref(
        state.get(INPUT_STATE_SNAPSHOT_REF), kind="foundry.state_snapshot"
    )
    if state_snapshot_ref is not None:
        inputs[INPUT_STATE_SNAPSHOT_REF] = state_snapshot_ref

    exec_plan_ref = _as_artifact_ref(state.get(ARTIFACT_EXEC_PLAN_REF), kind="foundry.exec_plan")
    if exec_plan_ref is not None:
        artifacts[ARTIFACT_EXEC_PLAN_REF] = exec_plan_ref

    sim_ref = _as_artifact_ref(
        state.get(ARTIFACT_SIMULATION_RESULT_REF) or state.get("simulation_results_ref"),
        kind="foundry.simulation_result",
    )
    if sim_ref is not None:
        artifacts[ARTIFACT_SIMULATION_RESULT_REF] = sim_ref

    metrics_ref = _as_artifact_ref(state.get(ARTIFACT_METRICS_REF), kind="foundry.metrics")
    if metrics_ref is not None:
        artifacts[ARTIFACT_METRICS_REF] = metrics_ref

    return EngineExperimentState(
        run_id=_to_str(state.get("run_id")),
        inputs=inputs,
        artifacts_index=artifacts,
        reports_index=reports,
    )


def _apply_engine_to_legacy(
    engine_state: EngineExperimentState, legacy_state: Mapping[str, Any]
) -> dict[str, Any]:
    updated = dict(legacy_state)
    updated["run_id"] = engine_state.run_id

    for key, ref in engine_state.inputs.items():
        updated[key] = ref.model_dump()
    for key, ref in engine_state.artifacts_index.items():
        updated[key] = ref.model_dump()
    for key, ref in engine_state.reports_index.items():
        updated[key] = ref.model_dump()

    if ARTIFACT_SIMULATION_RESULT_REF in engine_state.artifacts_index:
        updated["simulation_results_ref"] = engine_state.artifacts_index[
            ARTIFACT_SIMULATION_RESULT_REF
        ].model_dump()

    return updated


def _build_execution_context(
    store: FileSystemCAS, run_id: str, registry_ref: ArtifactRef
) -> ExecutionContext:
    run_ctx = RunContext.start(store, registry_ref, run_id=run_id)
    foundry: Any | None = None
    try:
        from polisyos.scientist.foundry import DefaultFoundryPort

        foundry = DefaultFoundryPort()
    except ModuleNotFoundError:
        # Optional dependency (jax stack) can be absent in light test environments.
        foundry = None
    return ExecutionContext(
        store=store,
        run=run_ctx,
        logger=_LOGGER,
        foundry=foundry,
    )


def _ensure_registry_ref(state: Mapping[str, Any], store: FileSystemCAS) -> ArtifactRef:
    ref = _as_artifact_ref(state.get(INPUT_REGISTRY_BUNDLE_REF), kind="core.registry_bundle")
    if ref is not None:
        return ref
    bundle = build_default_registry_bundle(store)
    return bundle.bundle_ref


def _ensure_trinity_ref(
    state: Mapping[str, Any], store: FileSystemCAS
) -> ArtifactRef | None:
    existing = _as_artifact_ref(state.get(INPUT_TRINITY_BUNDLE_REF), kind="ir.trinity_bundle")
    if existing is not None:
        return existing

    ir = state.get("ir")
    bundle = _extract_trinity_bundle(ir)
    if bundle is None:
        return None
    stored = store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
        ),
    )
    return stored


def _feedback_for_error(code: str, message: str) -> dict[str, Any]:
    return {
        "verdict": "NEEDS_REVISION",
        "issues": [
            {
                "severity": "error",
                "error_type": "runtime",
                "code": code,
                "message": message,
            }
        ],
    }


def compile_model_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode

    store = FileSystemCAS(_cas_root(state))
    run_id = _to_str(state.get("run_id"), "R_legacy")
    registry_ref = _ensure_registry_ref(state, store)
    trinity_ref = _ensure_trinity_ref(state, store)

    engine_state = _legacy_to_engine_state(state)
    engine_state.inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_ref
    if trinity_ref is not None:
        engine_state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    ctx = _build_execution_context(store, run_id, registry_ref)
    outcome = CompileFoundryNode().execute(ctx, engine_state)
    updated = _apply_engine_to_legacy(outcome.state, state)

    if outcome.status == "fail" and outcome.error is not None:
        updated["feedback"] = _feedback_for_error(outcome.error.code, outcome.error.message)
    return updated


def run_sim_node(state: ExperimentState) -> ExperimentState:
    _warn_once()
    from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode

    state = _check_budget(_ensure_run(state), "sim_runs")
    if state.get("pruned"):
        return state

    store = FileSystemCAS(_cas_root(state))
    run_id = _to_str(state.get("run_id"), "R_legacy")
    registry_ref = _ensure_registry_ref(state, store)
    ctx = _build_execution_context(store, run_id, registry_ref)

    engine_state = _legacy_to_engine_state(state)
    engine_state.inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_ref

    outcome = RunSimulationNode().execute(ctx, engine_state)
    updated = _apply_engine_to_legacy(outcome.state, state)
    if outcome.status == "fail" and outcome.error is not None:
        updated["feedback"] = _feedback_for_error(outcome.error.code, outcome.error.message)
        return updated

    metrics_ref = outcome.state.artifacts_index.get(ARTIFACT_METRICS_REF)
    if metrics_ref is not None:
        try:
            payload = from_canonical_bytes(store.get_bytes(metrics_ref.artifact_id))
            if isinstance(payload, Mapping):
                values = payload.get("values")
                if isinstance(values, Mapping):
                    updated["simulation_results"] = dict(values)
        except Exception:
            pass
    return updated
