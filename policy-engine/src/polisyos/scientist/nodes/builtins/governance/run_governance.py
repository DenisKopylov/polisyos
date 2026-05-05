"""Public governance run governance module API."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.contracts.lex import (
    ChangeProposalRef,
    ComplianceIssue,
    IssueSeverity,
    LegalReportRef,
)
from polisyos.core.contracts.scientist import (
    GovernanceReportRef,
    SourceVerificationReportRef,
    VerifiedPolicyReportRef,
)
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeArbitrationResult,
    load_normative_arbitration_result,
)
from polisyos.ir.governance.gate import (
    GateContext,
    GateDecision,
    GatePriority,
    GateRequest,
    GateVerdict,
)
from polisyos.ir.refs import NormativeArbitrationResultRef
from polisyos.scientist.claims.ledger import persist_claim_ledger
from polisyos.scientist.claims.projections import project_governance_report_claims
from polisyos.scientist.claims.validators import (
    is_claim_spine_enabled,
    is_fail_on_naked_claims_enabled,
    validate_state_claim_projection,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.error_semantics import emit_degraded_path
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.governance.pass_registry import (
    build_governance_pipeline,
)
from polisyos.scientist.governance.pass_registry import (
    runtime_profile as build_runtime_profile,
)
from polisyos.scientist.governance.report import GovernanceReport, GovernanceReportLinks
from polisyos.scientist.kernel.gate_protocol import HumanGateProtocol
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_HUMAN_REVIEW_DECISION_REF,
    ARTIFACT_HUMAN_REVIEW_PACKET_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LEGAL_REPORT_REF,
)

logger = get_logger(__name__)

_GOVERNANCE_HELPER_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_governance@1.2.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Governance",
    description="Evaluate governance gates and emit GovernanceReport.",
    tags=["builtin", "governance"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params",
        "inputs",
        "artifacts_index.simulation_result_ref",
        "artifacts_index.distributional_report_ref",
        "artifacts_index.causal_report_ref",
        "artifacts_index.claims_ref",
        "artifacts_index.human_review_packet_ref",
        "artifacts_index.human_review_decision_ref",
        "artifacts_index.causal_graph_ref",
        "artifacts_index.metrics_ref",
        "artifacts_index.normative_arbitration_result_ref",
        "params.query_treatment",
        "params.human_review_request",
        "params.human_review_request_ref",
        "reports_index.legal_report_ref",
        "reports_index.change_proposal_ref",
        "artifacts_index.source_verification_report_ref",
        "artifacts_index.verified_policy_report_ref",
    ],
    state_writes=[
        "params",
        "params.validation_trace",
        "params.human_review_request",
        "params.human_review_request_ref",
        f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
        f"reports_index.{REPORT_GOVERNANCE_REPORT_REF}",
    ],
    produces=[REPORT_GOVERNANCE_REPORT_REF],
)

_DECISION_APPROVE = {"approve", "approved", "allow", "allowed"}
_DECISION_REJECT = {"reject", "rejected", "deny", "denied"}
_DECISION_ESCALATE = {"escalate", "escalated"}
_RUNTIME_PIPELINE = build_governance_pipeline()


@dataclass(frozen=True)
class _GovernanceCheckResult:
    issues: list[ComplianceIssue]
    trace: dict[str, Any]
    pass_state: dict[str, Any]


@dataclass(frozen=True)
class RunGovernanceNode:
    """Governance node with typed Human Gate protocol."""

    default_verdict: Literal["approve", "needs_revision", "reject", "human_gate"] = "approve"

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> RunGovernanceNode:
        if not params:
            return self
        verdict = params.get("default_verdict", self.default_verdict)
        return replace(self, default_verdict=str(verdict))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        verdict = self.default_verdict
        issues: list[dict[str, Any]] = []
        events: list[NodeEvent] = []

        protocol = HumanGateProtocol(ctx.run)
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state

        require_human_gate = bool(new_state.params.get("require_human_gate"))
        raw_gate_decision = new_state.params.get("gate_decision")
        gate_request = _parse_gate_request(new_state.params.get("gate_request"))
        gate_request_ref = _parse_gate_request_ref(new_state.params.get("gate_request_ref"))

        if require_human_gate and raw_gate_decision is None:
            if gate_request is None:
                gate_request, gate_request_ref = _create_gate_request(
                    ctx=ctx,
                    protocol=protocol,
                    state=new_state,
                )
                new_state.params["gate_request"] = gate_request.model_dump(mode="json")
                if gate_request_ref is not None:
                    new_state.params["gate_request_ref"] = str(gate_request_ref.artifact_id)
                events.append(
                    NodeEvent(
                        level="info",
                        message=f"Human gate requested: {gate_request.request_id}",
                    )
                )
            verdict = "human_gate"

        elif raw_gate_decision is not None:
            decision = _parse_gate_decision(
                raw_gate_decision,
                run_id=new_state.run_id,
                request_id=gate_request.request_id if gate_request else None,
            )
            if decision is None:
                issues.append(
                    {
                        "code": "gate.decision.invalid",
                        "message": "Invalid gate decision format",
                    }
                )
                verdict = "human_gate"
            else:
                protocol.persist_decision(decision, request_ref=gate_request_ref)
                new_state.params["gate_decision_typed"] = decision.model_dump(mode="json")
                new_state.params.pop("gate_decision", None)

                if decision.verdict == GateVerdict.REJECT:
                    verdict = "reject"
                elif decision.verdict == GateVerdict.APPROVE:
                    verdict = "approve"
                elif decision.verdict == GateVerdict.TIMEOUT:
                    verdict = "reject"
                elif decision.verdict == GateVerdict.ESCALATE:
                    new_state.params["gate_escalated"] = True
                    next_iteration = _as_int(new_state.params.get("gate_iteration")) + 1
                    new_state.params["gate_iteration"] = next_iteration
                    new_state.params.pop("gate_request", None)
                    new_state.params.pop("gate_request_ref", None)
                    next_request, next_request_ref = _create_gate_request(
                        ctx=ctx,
                        protocol=protocol,
                        state=new_state,
                    )
                    new_state.params["gate_request"] = next_request.model_dump(mode="json")
                    if next_request_ref is not None:
                        new_state.params["gate_request_ref"] = str(next_request_ref.artifact_id)
                    verdict = "human_gate"
                    events.append(
                        NodeEvent(
                            level="warn",
                            message=(
                                "Gate escalated; new request created "
                                f"(iteration={next_request.context.iteration})"
                            ),
                        )
                    )

        profile = _resolve_validation_profile(
            new_state.params.get("governance_profile"),
            execution_profile=new_state.execution_profile,
        )
        checks = _run_governance_checks(ctx, new_state, profile)
        governance_issues = checks.issues
        new_state.params["validation_trace"] = checks.trace
        human_review_requested = _has_issue_code(governance_issues, "HUMAN_REVIEW_REQUESTED")
        if human_review_requested:
            _ensure_human_review_gate_request(
                ctx=ctx,
                protocol=protocol,
                state=new_state,
                pass_state=checks.pass_state,
                events=events,
            )
            typed_gate_decision = _parse_typed_gate_decision(
                new_state.params.get("gate_decision_typed")
            )
            if typed_gate_decision is None:
                verdict = "human_gate"
        if governance_issues:
            issues.extend([_issue_to_payload(issue) for issue in governance_issues])
            blocker_count = sum(
                1 for issue in governance_issues if issue.severity == IssueSeverity.BLOCKER
            )
            normative_result = _load_normative_arbitration_result(ctx, new_state)
            if verdict not in {"human_gate", "reject"}:
                if blocker_count > 0:
                    verdict = "reject"
                    events.append(
                        NodeEvent(
                            level="warn",
                            message=(
                                f"Governance checks blocked decision ({blocker_count} blocker(s))"
                            ),
                        )
                    )
                elif normative_result is not None:
                    if _normative_selects_revision(normative_result):
                        verdict = "needs_revision"
                        events.append(
                            NodeEvent(
                                level="warn",
                                message=(
                                    "Normative arbitration requires revision "
                                    f"({normative_result.selected_option.value})"
                                ),
                            )
                        )
                    elif normative_result.selected_option == ArbitrationOption.PROPOSAL:
                        verdict = "approve"
            if blocker_count > 0 and verdict == "reject":
                pass
        else:
            normative_result = _load_normative_arbitration_result(ctx, new_state)
            if verdict not in {"human_gate", "reject"} and normative_result is not None:
                if _normative_selects_revision(normative_result):
                    verdict = "needs_revision"
                    events.append(
                        NodeEvent(
                            level="warn",
                            message=(
                                "Normative arbitration requires revision "
                                f"({normative_result.selected_option.value})"
                            ),
                        )
                    )
                elif normative_result.selected_option == ArbitrationOption.PROPOSAL:
                    verdict = "approve"

        if governance_issues:
            blocker_count = sum(
                1 for issue in governance_issues if issue.severity == IssueSeverity.BLOCKER
            )
            if blocker_count > 0 and verdict != "human_gate":
                verdict = "reject"

        fail_on_naked_claims = is_fail_on_naked_claims_enabled(new_state.params)
        claim_projection = validate_state_claim_projection(
            workflow_id=str(new_state.params.get("workflow_id") or ""),
            artifacts_index=new_state.artifacts_index,
            fail_on_naked_claims=fail_on_naked_claims,
        )
        if claim_projection.violations and fail_on_naked_claims:
            issues.append(
                {
                    "code": "claim_spine.naked_decision_claims",
                    "message": "Decision-bearing artifacts require claims_ref projection.",
                    "details": claim_projection.model_dump(mode="json"),
                }
            )
        if not claim_projection.passed and verdict != "human_gate":
            verdict = "reject"
            events.append(
                NodeEvent(
                    level="warn",
                    message="Governance blocked publication because claims_ref is missing.",
                )
            )

        report = GovernanceReport(
            verdict=verdict,
            issues=issues,
            links=_build_governance_links(new_state),
        )
        if is_claim_spine_enabled(new_state.params):
            claim_ledger = project_governance_report_claims(
                report,
                run_id=new_state.run_id,
                source_artifact_refs=_claim_source_artifact_refs(new_state),
            )
            claims_ref = persist_claim_ledger(ctx.store, claim_ledger)
            new_state.artifacts_index[ARTIFACT_CLAIMS_REF] = claims_ref
            report = report.model_copy(
                update={"links": report.links.model_copy(update={"claims_ref": claims_ref})}
            )
        report_ref_payload = ctx.store.put_json(
            report,
            PutOptions(
                kind="scientist.governance_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.GovernanceReport",
                    version=report.schema_version,
                ),
            ),
        )
        report_ref = GovernanceReportRef(artifact_id=report_ref_payload.artifact_id)
        new_state.reports_index[REPORT_GOVERNANCE_REPORT_REF] = report_ref

        events.append(NodeEvent(level="info", message=f"Governance verdict: {verdict}"))
        artifacts = [report_ref]
        if report.links.claims_ref is not None:
            artifacts.append(report.links.claims_ref)
        return NodeOutcome(status="ok", state=new_state, artifacts=artifacts, events=events)


def _create_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
) -> tuple[GateRequest, ArtifactRef | None]:
    iteration = _as_int(state.params.get("gate_iteration"))
    is_escalated = bool(state.params.get("gate_escalated"))
    phase = str(state.params.get("phase", "POSTFLIGHT_GOV"))
    governance_profile_raw = state.params.get("governance_profile")
    governance_profile = (
        str(governance_profile_raw) if isinstance(governance_profile_raw, str) else None
    )
    timeout_seconds = _optional_int(state.params.get("gate_timeout_seconds"))

    context = _build_gate_context(
        ctx=ctx,
        state=state,
        phase=phase,
        iteration=iteration,
        governance_profile=governance_profile,
        is_escalated=is_escalated,
        risk_indicators=[],
        issue_summary=None,
    )
    priority = GatePriority.CRITICAL if is_escalated else GatePriority.NORMAL
    return protocol.request_gate(
        run_id=state.run_id,
        reason="governance_profile_requires_approval",
        context=context,
        priority=priority,
        timeout_seconds=timeout_seconds,
        requested_by="scientist.node_run_governance",
    )


def _ensure_human_review_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    pass_state: dict[str, Any],
    events: list[NodeEvent],
) -> None:
    existing_request = _parse_gate_request(state.params.get("human_review_request"))
    existing_ref = _parse_gate_request_ref(state.params.get("human_review_request_ref"))
    if existing_request is not None and existing_ref is not None:
        return

    payload = pass_state.get("human_review_request")
    items: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        raw_items = payload.get("items")
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]

    request, request_ref = _create_human_review_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        review_items=items,
    )
    state.params["human_review_request"] = request.model_dump(mode="json")
    state.params["human_review_request_ref"] = str(request_ref.artifact_id)
    events.append(
        NodeEvent(
            level="info",
            message=f"Human review request created: {request.request_id}",
        )
    )


def _create_human_review_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    review_items: list[dict[str, Any]],
) -> tuple[GateRequest, ArtifactRef]:
    governance_profile_raw = state.params.get("governance_profile")
    governance_profile = (
        str(governance_profile_raw) if isinstance(governance_profile_raw, str) else None
    )
    timeout_seconds = _optional_int(state.params.get("human_review_timeout_seconds"))
    if timeout_seconds is None:
        timeout_seconds = 72 * 3600

    risk_indicators: list[str] = []
    for item in review_items:
        kind = item.get("kind")
        if kind is not None:
            risk_indicators.append(str(kind))

    issue_summary = {
        "requested_items": len(review_items),
        "risk_indicator_count": len(sorted(set(risk_indicators))),
    }
    context = _build_gate_context(
        ctx=ctx,
        state=state,
        phase=str(state.params.get("human_review_phase", "POSTFLIGHT_GOV_REVIEW")),
        iteration=_as_int(state.params.get("human_review_iteration")),
        governance_profile=governance_profile,
        is_escalated=bool(state.params.get("gate_escalated")),
        risk_indicators=sorted(set(risk_indicators)),
        issue_summary=issue_summary,
    )
    reason = _human_review_reason(ctx=ctx, state=state, review_items=review_items)
    return protocol.request_gate(
        run_id=state.run_id,
        reason=reason,
        context=context,
        priority=GatePriority.HIGH,
        timeout_seconds=timeout_seconds,
        requested_by="scientist.node_run_governance",
    )


def _build_gate_context(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    phase: str,
    iteration: int,
    governance_profile: str | None,
    is_escalated: bool,
    risk_indicators: list[str],
    issue_summary: dict[str, int] | None,
) -> GateContext:
    return GateContext(
        workflow_id=str(state.params.get("workflow_id", "scientist_default")),
        node_alias="run_governance",
        phase=phase,
        governance_profile=governance_profile,
        iteration=iteration,
        is_escalated=is_escalated,
        policy_summary=_policy_summary_from_state(ctx, state),
        simulation_results=_simulation_results_from_state(ctx, state),
        risk_indicators=risk_indicators,
        issue_summary=issue_summary,
        artifact_refs=_collect_gate_artifact_refs(state),
        transport_summary=_transport_summary_from_state(ctx, state),
        replay_summary=_gate_replay_summary(state),
    )


def _policy_summary_from_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> str | None:
    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="policy_summary_from_state",
            reason="trinity_bundle_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None
    if not isinstance(payload, dict):
        return None
    policy_spec = payload.get("policy_spec")
    if not isinstance(policy_spec, dict):
        return "Policy data attached"
    interventions = policy_spec.get("interventions")
    if isinstance(interventions, list):
        return f"Policy with {len(interventions)} intervention(s)"
    return "Policy data attached"


def _simulation_results_from_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> dict[str, Any] | None:
    metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
    if metrics_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
        metrics = Metrics.model_validate(payload)
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="simulation_results_from_state",
            reason="metrics_preview_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None

    preview: dict[str, Any] = {}
    for key in sorted(metrics.values)[:5]:
        preview[key] = metrics.values[key]
    return preview or None


def _collect_gate_artifact_refs(state: ExperimentState) -> dict[str, str] | None:
    refs: dict[str, str] = {}
    for key in (
        INPUT_TRINITY_BUNDLE_REF,
        INPUT_DATA_SNAPSHOT_REF,
        ARTIFACT_METRICS_REF,
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
        REPORT_LEGAL_REPORT_REF,
        REPORT_CHANGE_PROPOSAL_REF,
    ):
        ref = (
            state.inputs.get(key) or state.artifacts_index.get(key) or state.reports_index.get(key)
        )
        if ref is not None:
            refs[key] = str(ref.artifact_id)
    return refs or None


def _transport_summary_from_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> dict[str, Any] | None:
    report_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    if report_ref is None:
        status = state.params.get("transportability_status")
        mode = state.params.get("transportability_transport_mode")
        engine = state.params.get("transportability_identification_engine")
        capability_hash = state.params.get("transportability_capability_hash")
        degradation_policy = state.params.get("transportability_degradation_policy")
        if isinstance(status, str) or isinstance(engine, str):
            return {
                "status": status if isinstance(status, str) else "not_available",
                "transport_mode": mode if isinstance(mode, str) else "not_available",
                "identification_engine": engine if isinstance(engine, str) else "not_available",
                "capability_hash": capability_hash if isinstance(capability_hash, str) else None,
                "degradation_policy": (
                    degradation_policy if isinstance(degradation_policy, str) else None
                ),
            }
        return None

    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(report_ref.artifact_id))
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="transport_summary_from_state",
            reason="causal_report_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None
    if not isinstance(payload, dict):
        return None
    transport = payload.get("transport_result")
    if not isinstance(transport, dict):
        return None
    summary = {
        "status": transport.get("status"),
        "transport_mode": transport.get("transport_mode"),
        "identification_engine": transport.get("identification_engine"),
        "capability_hash": state.params.get("transportability_capability_hash"),
        "degradation_policy": state.params.get("transportability_degradation_policy"),
        "requires_expert_review": bool(transport.get("requires_expert_review", False)),
        "data_gaps_count": len(transport.get("data_gaps", []))
        if isinstance(transport.get("data_gaps"), list)
        else 0,
        "unsupported_cases": list(transport.get("unsupported_cases", []))
        if isinstance(transport.get("unsupported_cases"), list)
        else [],
        "hard_legal_constraints": list(transport.get("hard_legal_constraints", []))
        if isinstance(transport.get("hard_legal_constraints"), list)
        else [],
    }
    return summary


def _gate_replay_summary(state: ExperimentState) -> dict[str, Any]:
    readiness, missing_refs = _gate_replay_readiness(state)
    why_partial: list[str] = []
    if readiness == "partial":
        why_partial.append("missing_optional_inputs")
    elif readiness == "incomplete":
        if "state_source_ref" in missing_refs:
            why_partial.append("missing_state_source")
        if any(ref in missing_refs for ref in ("trinity_bundle_ref", "registry_bundle_ref")):
            why_partial.append("missing_required_inputs")

    if "input_bindings_ref" in missing_refs:
        suggested_next_step = "Persist input_bindings_ref for replay-grade completeness."
    elif "state_source_ref" in missing_refs:
        suggested_next_step = "Attach data_snapshot_ref, state_snapshot_ref, or input_bindings_ref."
    elif missing_refs:
        suggested_next_step = (
            "Persist the missing replay refs listed in replay_summary.missing_refs."
        )
    else:
        suggested_next_step = None

    return {
        "readiness": readiness,
        "missing_refs": missing_refs,
        "why_partial": why_partial,
        "suggested_next_step": suggested_next_step,
        "determinism_tier": (
            state.params.get("determinism_tier")
            if isinstance(state.params.get("determinism_tier"), str)
            else None
        ),
        "seed_source": "params.random_seed"
        if isinstance(state.params.get("random_seed"), (int, float, str))
        else None,
    }


def _gate_replay_readiness(state: ExperimentState) -> tuple[str, list[str]]:
    missing_refs: list[str] = []
    if INPUT_TRINITY_BUNDLE_REF not in state.inputs:
        missing_refs.append(INPUT_TRINITY_BUNDLE_REF)
    if "registry_bundle_ref" not in state.inputs:
        missing_refs.append("registry_bundle_ref")

    has_snapshot = any(
        key in state.inputs
        for key in ("input_bindings_ref", "data_snapshot_ref", "state_snapshot_ref")
    )
    if not has_snapshot:
        missing_refs.append("state_source_ref")
        return "incomplete", missing_refs

    optional_missing = [
        key
        for key in (
            "input_bindings_ref",
            "norm_pack_ref",
            "knowledge_bundle_ref",
            "research_intent_ref",
        )
        if key not in state.inputs
    ]
    missing_refs.extend(optional_missing)
    if missing_refs:
        if any(key in missing_refs for key in ("trinity_bundle_ref", "registry_bundle_ref")):
            return "incomplete", missing_refs
        return "partial", missing_refs
    return "complete", missing_refs


def _human_review_reason(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    review_items: list[dict[str, Any]],
) -> str:
    transport = _transport_summary_from_state(ctx, state)
    if isinstance(transport, dict) and transport.get("requires_expert_review") is True:
        return "expert_review_required_for_transportability"
    if review_items:
        return "strict_human_review"
    return "governance_human_review_required"


def _parse_gate_request(raw: Any) -> GateRequest | None:
    if isinstance(raw, GateRequest):
        return raw
    if isinstance(raw, dict):
        try:
            return GateRequest.model_validate(raw)
        except _GOVERNANCE_HELPER_ERRORS:
            return None
    return None


def _parse_gate_request_ref(raw: Any) -> ArtifactRef | None:
    if not isinstance(raw, str):
        return None
    try:
        artifact_id = ArtifactID.model_validate(raw)
    except _GOVERNANCE_HELPER_ERRORS:
        return None
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="ir.gate_request",
        media_type="application/json",
    )


def _parse_typed_gate_decision(raw: Any) -> GateDecision | None:
    if isinstance(raw, GateDecision):
        return raw
    if isinstance(raw, dict):
        try:
            return GateDecision.model_validate(raw)
        except _GOVERNANCE_HELPER_ERRORS:
            return None
    return None


def _parse_gate_decision(
    raw: Any,
    *,
    run_id: str,
    request_id: str | None,
) -> GateDecision | None:
    rid = request_id or "unknown"
    if isinstance(raw, GateDecision):
        return raw
    if isinstance(raw, dict):
        if "verdict" in raw:
            try:
                return GateDecision.model_validate(raw)
            except _GOVERNANCE_HELPER_ERRORS:
                return None
        if "approved" in raw:
            approved = bool(raw.get("approved"))
            verdict = GateVerdict.APPROVE if approved else GateVerdict.REJECT
            actor = raw.get("actor")
            reason_codes = raw.get("reason_codes")
            notes = raw.get("notes")
            return GateDecision(
                request_id=rid,
                run_id=run_id,
                verdict=verdict,
                approver_id=str(actor) if actor else "legacy",
                reason_codes=_coerce_reason_codes(reason_codes),
                comment=str(notes) if notes else None,
            )
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in _DECISION_APPROVE:
            verdict = GateVerdict.APPROVE
        elif token in _DECISION_REJECT:
            verdict = GateVerdict.REJECT
        elif token in _DECISION_ESCALATE:
            verdict = GateVerdict.ESCALATE
        else:
            return None
        return GateDecision(
            request_id=rid,
            run_id=run_id,
            verdict=verdict,
            approver_id="legacy",
        )
    return None


def _coerce_reason_codes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if item is None:
            continue
        values.append(str(item))
    return values


def _as_int(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    return value if value >= 1 else 1


def _optional_int(raw: Any) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _resolve_validation_profile(
    raw: Any,
    *,
    execution_profile: str | None = None,
) -> ValidationProfile:
    if isinstance(raw, ValidationProfile):
        return raw
    if isinstance(raw, dict):
        try:
            return ValidationProfile.from_dict(raw)
        except _GOVERNANCE_HELPER_ERRORS:
            return ValidationProfile.mvp()
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token == "fast":
            return ValidationProfile.fast()
        if token == "strict":
            return ValidationProfile.strict()
    profile_token = str(execution_profile or "").strip().lower()
    if profile_token in {"governed", "production"}:
        return ValidationProfile.strict()
    if profile_token == "research":
        return ValidationProfile.mvp()
    return ValidationProfile.mvp()


def _build_governance_links(state: ExperimentState) -> GovernanceReportLinks:
    legal_ref = _coerce_report_ref(
        state.reports_index.get(REPORT_LEGAL_REPORT_REF),
        ref_cls=LegalReportRef,
    )
    change_ref = _coerce_report_ref(
        state.reports_index.get(REPORT_CHANGE_PROPOSAL_REF),
        ref_cls=ChangeProposalRef,
    )
    source_verification_ref = _coerce_report_ref(
        state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF),
        ref_cls=SourceVerificationReportRef,
    )
    verified_policy_ref = _coerce_report_ref(
        state.artifacts_index.get(ARTIFACT_VERIFIED_POLICY_REPORT_REF),
        ref_cls=VerifiedPolicyReportRef,
    )
    claims_ref = state.artifacts_index.get(ARTIFACT_CLAIMS_REF)
    human_review_packet_ref = state.artifacts_index.get(ARTIFACT_HUMAN_REVIEW_PACKET_REF)
    human_review_decision_ref = state.artifacts_index.get(ARTIFACT_HUMAN_REVIEW_DECISION_REF)
    return GovernanceReportLinks(
        legal_report_ref=legal_ref,
        change_proposal_ref=change_ref,
        source_verification_report_ref=source_verification_ref,
        verified_policy_report_ref=verified_policy_ref,
        claims_ref=claims_ref,
        human_review_packet_ref=human_review_packet_ref,
        human_review_decision_ref=human_review_decision_ref,
    )


def _claim_source_artifact_refs(state: ExperimentState) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    refs.extend(state.inputs.values())
    refs.extend(state.artifacts_index.values())
    refs.extend(state.reports_index.values())
    output: list[ArtifactRef] = []
    seen: set[str] = set()
    for ref in refs:
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        output.append(ref)
    return output


def _coerce_report_ref(raw: Any, *, ref_cls: type[ArtifactRef]) -> ArtifactRef | None:
    if raw is None:
        return None
    if isinstance(raw, ref_cls):
        return raw
    if hasattr(raw, "model_dump"):
        payload = raw.model_dump(mode="json")
    else:
        payload = raw
    try:
        return ref_cls.model_validate(payload)
    except _GOVERNANCE_HELPER_ERRORS:
        return None


def _run_governance_checks(
    ctx: ExecutionContext,
    state: ExperimentState,
    profile: ValidationProfile,
) -> _GovernanceCheckResult:
    runtime_profile = build_runtime_profile(profile)
    pii_scan_results = _extract_pii_scan_results(ctx, state)
    pass_state = {
        "artifacts_index": state.artifacts_index,
        "params": state.params,
        "_store": ctx.store,
        "tenant_tier": str(state.params.get("tenant_tier", "shared")),
        "pii_scan_results": pii_scan_results,
        "query_treatment": state.params.get("query_treatment"),
        "strategic_response": state.params.get("strategic_response"),
        "strategic_response_required": state.params.get("strategic_scm") is not None,
        "causal_graph_ref": state.artifacts_index.get(
            "causal_graph_ref",
            state.params.get("causal_graph_ref"),
        ),
    }
    pass_ctx = PassContext(
        ir=None,
        state=pass_state,
        registry_bundle=None,
        profile=runtime_profile,
        run_id=state.run_id,
    )
    issues, trace = _RUNTIME_PIPELINE.validate(pass_ctx, runtime_profile)
    return _GovernanceCheckResult(
        issues=issues,
        trace=trace.to_dict(),
        pass_state=pass_ctx.state,
    )


def _load_normative_arbitration_result(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> NormativeArbitrationResult | None:
    ref = state.artifacts_index.get(ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF)
    if ref is None:
        return None
    try:
        return load_normative_arbitration_result(
            ctx.store,
            NormativeArbitrationResultRef(artifact_id=ref.artifact_id),
        )
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="load_normative_arbitration_result",
            reason="normative_arbitration_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None


def _normative_selects_revision(result: NormativeArbitrationResult) -> bool:
    return result.selected_option in {
        ArbitrationOption.BASELINE,
        ArbitrationOption.INDETERMINATE,
    }


def _has_issue_code(issues: list[ComplianceIssue], code: str) -> bool:
    return any(issue.code == code for issue in issues)


def _extract_pii_scan_results(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> dict[str, Any] | None:
    existing = state.params.get("pii_scan_results")
    if isinstance(existing, dict):
        return existing

    snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if snapshot_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(snapshot_ref.artifact_id))
        snapshot = DataSnapshot.model_validate(payload)
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="extract_pii_scan_results",
            reason="data_snapshot_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None

    summary = snapshot.pii_scan_summary
    if isinstance(summary, dict):
        return summary
    return None


def _issue_to_payload(issue: ComplianceIssue) -> dict[str, Any]:
    return {
        "pass_id": issue.pass_id,
        "path": issue.path,
        "message": issue.message,
        "severity": issue.severity.value,
        "code": issue.code,
        "suggestion": issue.suggestion,
        "input_value": issue.input_value,
    }
