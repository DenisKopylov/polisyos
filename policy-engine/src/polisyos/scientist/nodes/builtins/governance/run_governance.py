"""Public governance run governance module API."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
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
from polisyos.ir.registry.refs import NormativeArbitrationResultRef
from polisyos.scientist.evidence.claims.projections import project_governance_report_claims
from polisyos.scientist.evidence.claims.validators import (
    is_claim_spine_enabled,
    is_fail_on_naked_claims_enabled,
    validate_state_claim_projection,
)
from polisyos.scientist.governance.pass_registry import (
    build_governance_pipeline,
)
from polisyos.scientist.governance.pass_registry import (
    runtime_profile as build_runtime_profile,
)
from polisyos.scientist.governance.report import GovernanceReport, GovernanceReportLinks
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
from polisyos.scientist.orchestration.engine.context import (
    ClaimCapableExecutionContext,
    ExecutionContext,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.kernel.gate_protocol import HumanGateProtocol

from .governance_gate_requests import (
    _GOVERNANCE_HELPER_ERRORS as _GOVERNANCE_HELPER_ERRORS,
)
from .governance_gate_requests import (
    _as_int as _as_int,
)
from .governance_gate_requests import (
    _build_gate_context as _build_gate_context,
)
from .governance_gate_requests import (
    _collect_gate_artifact_refs as _collect_gate_artifact_refs,
)
from .governance_gate_requests import (
    _create_gate_request as _create_gate_request,
)
from .governance_gate_requests import (
    _create_human_review_gate_request as _create_human_review_gate_request,
)
from .governance_gate_requests import (
    _ensure_human_review_gate_request as _ensure_human_review_gate_request,
)
from .governance_gate_requests import (
    _gate_replay_readiness as _gate_replay_readiness,
)
from .governance_gate_requests import (
    _gate_replay_summary as _gate_replay_summary,
)
from .governance_gate_requests import (
    _gate_request_spec as _gate_request_spec,
)
from .governance_gate_requests import (
    _human_review_reason as _human_review_reason,
)
from .governance_gate_requests import (
    _optional_int as _optional_int,
)
from .governance_gate_requests import (
    _parse_gate_request as _parse_gate_request,
)
from .governance_gate_requests import (
    _parse_gate_request_ref as _parse_gate_request_ref,
)
from .governance_gate_requests import (
    _policy_summary_from_state as _policy_summary_from_state,
)
from .governance_gate_requests import (
    _resolve_cached_gate_request as _resolve_cached_gate_request,
)
from .governance_gate_requests import (
    _serialize_gate_request_ref as _serialize_gate_request_ref,
)
from .governance_gate_requests import (
    _simulation_results_from_state as _simulation_results_from_state,
)
from .governance_gate_requests import (
    _transport_summary_from_state as _transport_summary_from_state,
)

logger = get_logger(__name__)


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
_PHASE2_REQUIRED_SIX_JUDGES = frozenset(
    {"structural", "statistical", "robustness", "governance", "reproducibility", "compute"}
)
_RUNTIME_PIPELINE = build_governance_pipeline()


class _Phase2GovernanceApplicability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_id: str
    invocation_id: str
    status: str
    checked_preconditions: list[dict[str, Any]] = []
    failed_preconditions: list[dict[str, Any]] = []
    repair_options: list[dict[str, Any]] = []


class _Phase2GovernanceBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    blocker_id: str
    workspace_id: str
    blocked_port: str
    missing_input: str
    reason: str
    applicability_result_ref: str
    repair_options: list[dict[str, Any]] = []
    producer_missing_label: str = "verification_missing"
    severity: str = "blocks_authority"


class _Phase2GovernanceTailResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    applicability: _Phase2GovernanceApplicability
    blocker: _Phase2GovernanceBlocker | None = None


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
        events: list[NodeEvent] = []
        issues: list[dict[str, Any]] = []
        protocol = HumanGateProtocol(ctx.run)
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        verdict = _handle_initial_gate_request(
            ctx=ctx,
            protocol=protocol,
            state=new_state,
            verdict=self.default_verdict,
            issues=issues,
            events=events,
        )

        profile = _resolve_validation_profile(
            new_state.params.get("governance_profile"),
            execution_profile=new_state.execution_profile,
        )
        checks = _run_governance_checks(ctx, new_state, profile)
        new_state.params["validation_trace"] = checks.trace
        verdict = _apply_governance_check_outcomes(
            ctx=ctx,
            protocol=protocol,
            state=new_state,
            checks=checks,
            verdict=verdict,
            issues=issues,
            events=events,
        )
        verdict = _apply_claim_projection(
            state=new_state,
            verdict=verdict,
            issues=issues,
            events=events,
        )
        verdict = _apply_phase2_governance_tail(
            ctx=ctx,
            state=new_state,
            verdict=verdict,
            issues=issues,
            events=events,
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
            if isinstance(ctx, ClaimCapableExecutionContext):
                claims_ref = ctx.claim_ledger_owner.persist_candidate_ledger(ledger=claim_ledger)
                new_state.artifacts_index[ARTIFACT_CLAIMS_REF] = claims_ref
                report = report.model_copy(
                    update={"links": report.links.model_copy(update={"claims_ref": claims_ref})}
                )
            else:
                report = report.model_copy(
                    update={
                        "issues": [
                            *report.issues,
                            {
                                "code": "claim_ledger_owner_not_established",
                                "message": (
                                    "Claim candidate persistence requires the "
                                    "canonical Claim owner port."
                                ),
                            },
                        ]
                    }
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


def _handle_initial_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    verdict: str,
    issues: list[dict[str, Any]],
    events: list[NodeEvent],
) -> str:
    require_human_gate = bool(state.params.get("require_human_gate"))
    raw_gate_decision = state.params.get("gate_decision")
    gate_request_pair = _resolve_cached_gate_request(
        ctx=ctx,
        protocol=protocol,
        state=state,
        raw_request=state.params.get("gate_request"),
        raw_ref=state.params.get("gate_request_ref"),
        spec=_gate_request_spec(ctx=ctx, state=state),
    )
    gate_request, gate_request_ref = gate_request_pair or (None, None)

    if require_human_gate and raw_gate_decision is None:
        if gate_request is None:
            gate_request, gate_request_ref = _create_gate_request(
                ctx=ctx,
                protocol=protocol,
                state=state,
            )
            state.params["gate_request"] = gate_request.model_dump(mode="json")
            if gate_request_ref is not None:
                state.params["gate_request_ref"] = _serialize_gate_request_ref(gate_request_ref)
            events.append(
                NodeEvent(
                    level="info",
                    message=f"Human gate requested: {gate_request.request_id}",
                )
            )
        verdict = "human_gate"
    elif raw_gate_decision is not None:
        if gate_request is None or gate_request_ref is None:
            gate_request, gate_request_ref = _create_gate_request(
                ctx=ctx,
                protocol=protocol,
                state=state,
            )
            state.params["gate_request"] = gate_request.model_dump(mode="json")
            if gate_request_ref is not None:
                state.params["gate_request_ref"] = _serialize_gate_request_ref(gate_request_ref)
            state.params.pop("gate_decision", None)
            events.append(
                NodeEvent(
                    level="warn",
                    message="Unmatched gate decision was discarded; a current request was issued.",
                )
            )
            issues.append(
                {
                    "code": "gate.request.unverified",
                    "message": "Gate decision has no current persisted request to authorize it.",
                }
            )
            return "human_gate"
        verdict = _handle_gate_decision(
            ctx=ctx,
            protocol=protocol,
            state=state,
            raw_gate_decision=raw_gate_decision,
            gate_request=gate_request,
            gate_request_ref=gate_request_ref,
            verdict=verdict,
            issues=issues,
            events=events,
        )
    return verdict


def _handle_gate_decision(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    raw_gate_decision: Any,
    gate_request: GateRequest | None,
    gate_request_ref: ArtifactRef | None,
    verdict: str,
    issues: list[dict[str, Any]],
    events: list[NodeEvent],
) -> str:
    decision = _parse_gate_decision(
        raw_gate_decision,
        run_id=state.run_id,
        request_id=gate_request.request_id if gate_request else None,
    )
    if decision is None:
        issues.append(
            {
                "code": "gate.decision.invalid",
                "message": "Invalid gate decision format",
            }
        )
        state.params.pop("gate_decision", None)
        return "human_gate"
    if (
        gate_request is None
        or gate_request_ref is None
        or decision.run_id != state.run_id
        or decision.request_id != gate_request.request_id
    ):
        issues.append(
            {
                "code": "gate.decision.request_mismatch",
                "message": "Gate decision does not match the current persisted request.",
            }
        )
        state.params.pop("gate_decision", None)
        return "human_gate"

    protocol.persist_decision(decision, request_ref=gate_request_ref)
    state.params["gate_decision_typed"] = decision.model_dump(mode="json")
    state.params.pop("gate_decision", None)

    if decision.verdict == GateVerdict.REJECT:
        return "reject"
    if decision.verdict == GateVerdict.APPROVE:
        return "approve"
    if decision.verdict == GateVerdict.TIMEOUT:
        return "reject"
    if decision.verdict == GateVerdict.ESCALATE:
        state.params["gate_escalated"] = True
        next_iteration = _as_int(state.params.get("gate_iteration")) + 1
        state.params["gate_iteration"] = next_iteration
        state.params.pop("gate_request", None)
        state.params.pop("gate_request_ref", None)
        next_request, next_request_ref = _create_gate_request(
            ctx=ctx,
            protocol=protocol,
            state=state,
        )
        state.params["gate_request"] = next_request.model_dump(mode="json")
        if next_request_ref is not None:
            state.params["gate_request_ref"] = _serialize_gate_request_ref(next_request_ref)
        events.append(
            NodeEvent(
                level="warn",
                message=(
                    "Gate escalated; new request created "
                    f"(iteration={next_request.context.iteration})"
                ),
            )
        )
        return "human_gate"
    return verdict


def _apply_governance_check_outcomes(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    checks: _GovernanceCheckResult,
    verdict: str,
    issues: list[dict[str, Any]],
    events: list[NodeEvent],
) -> str:
    governance_issues = checks.issues
    if _has_issue_code(governance_issues, "HUMAN_REVIEW_REQUESTED"):
        _ensure_human_review_gate_request(
            ctx=ctx,
            protocol=protocol,
            state=state,
            pass_state=checks.pass_state,
            events=events,
        )
        typed_gate_decision = _parse_typed_gate_decision(state.params.get("gate_decision_typed"))
        if typed_gate_decision is None:
            verdict = "human_gate"
    if governance_issues:
        issues.extend([_issue_to_payload(issue) for issue in governance_issues])
    return _resolve_governance_verdict(
        ctx=ctx,
        state=state,
        governance_issues=governance_issues,
        verdict=verdict,
        events=events,
    )


def _resolve_governance_verdict(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    governance_issues: list[ComplianceIssue],
    verdict: str,
    events: list[NodeEvent],
) -> str:
    if governance_issues:
        blocker_count = sum(
            1 for issue in governance_issues if issue.severity == IssueSeverity.BLOCKER
        )
        normative_result = _load_normative_arbitration_result(ctx, state)
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
                verdict = _apply_normative_verdict(normative_result, verdict, events)
    else:
        normative_result = _load_normative_arbitration_result(ctx, state)
        verdict = _apply_normative_verdict(normative_result, verdict, events)

    if governance_issues:
        blocker_count = sum(
            1 for issue in governance_issues if issue.severity == IssueSeverity.BLOCKER
        )
        if blocker_count > 0 and verdict != "human_gate":
            verdict = "reject"
    return verdict


def _apply_normative_verdict(
    normative_result: NormativeArbitrationResult | None,
    verdict: str,
    events: list[NodeEvent],
) -> str:
    if verdict in {"human_gate", "reject"} or normative_result is None:
        return verdict
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
    return verdict


def _apply_claim_projection(
    *,
    state: ExperimentState,
    verdict: str,
    issues: list[dict[str, Any]],
    events: list[NodeEvent],
) -> str:
    fail_on_naked_claims = is_fail_on_naked_claims_enabled(state.params)
    claim_projection = validate_state_claim_projection(
        workflow_id=str(state.params.get("workflow_id") or ""),
        artifacts_index=state.artifacts_index,
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
    return verdict


def _apply_phase2_governance_tail(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    verdict: str,
    issues: list[dict[str, Any]],
    events: list[NodeEvent],
) -> str:
    if not _phase2_governance_tail_required(state):
        return verdict
    normative_result = _load_normative_arbitration_result(ctx, state)
    tail = verify_phase2_governance_tail(
        workspace_id=state.run_id,
        invocation_id="invoke-run-governance",
        normative_result=_normative_tail_payload(normative_result),
        judge_verdict=_judge_verdict_payload(state.params.get("judge_verdict")),
    )
    if tail.blocker is not None:
        issues.append(
            {
                "code": "GY_PHASE2_GOVERNANCE_TAIL_BLOCKED",
                "message": tail.blocker.reason,
                "details": {
                    "blocker": tail.blocker.model_dump(mode="json"),
                    "applicability": tail.applicability.model_dump(mode="json"),
                },
            }
        )
        if verdict != "human_gate":
            verdict = "reject"
        events.append(
            NodeEvent(
                level="warn",
                message="Phase-2 governance tail blocked authority promotion.",
            )
        )
    return verdict


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
            _ensure_ir_artifact_store(ctx.store),
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


def _phase2_governance_tail_required(state: ExperimentState) -> bool:
    return (
        state.execution_profile == "gy_phase2"
        or state.params.get("gy_phase2_governance_tail_required") is True
    )


def _normative_tail_payload(result: NormativeArbitrationResult | None) -> dict[str, Any]:
    if result is None:
        return {
            "warnings": ["normative_arbitration_result_missing"],
            "model_completeness": "missing",
        }
    model_source = str(result.metadata.get("model_source") or "")
    completeness = getattr(result.model_completeness, "value", result.model_completeness)
    return {
        "warnings": list(result.warnings),
        "model_completeness": (
            "declared_complete"
            if completeness == "complete" and model_source == "declared"
            else str(completeness)
        ),
    }


def _judge_verdict_payload(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return {}


def verify_phase2_governance_tail(
    *,
    workspace_id: str,
    invocation_id: str,
    normative_result: dict[str, Any],
    judge_verdict: dict[str, Any],
) -> _Phase2GovernanceTailResult:
    """Validate the Phase-2 governance tail before any authority movement."""

    failures: list[dict[str, Any]] = []
    warnings = normative_result.get("warnings") or []
    if warnings:
        failures.append(
            {
                "predicate_id": "phase2.normative.warnings_empty",
                "reason": "normative_arbitration_warnings_present",
                "severity": "hard",
                "observed": warnings,
            }
        )
    if normative_result.get("model_completeness") not in {"declared_complete", "complete"}:
        failures.append(
            {
                "predicate_id": "phase2.normative.model_complete",
                "reason": "model_completeness_not_declared",
                "severity": "hard",
            }
        )
    if judge_verdict.get("composite_decision") != "promote":
        failures.append(
            {
                "predicate_id": "phase2.judge_stack.promotable",
                "reason": "judge_stack_did_not_promote",
                "severity": "hard",
            }
        )
    per_judge = judge_verdict.get("per_judge")
    present_judges = {str(item) for item in per_judge} if isinstance(per_judge, dict) else set()
    if not _PHASE2_REQUIRED_SIX_JUDGES.issubset(present_judges):
        failures.append(
            {
                "predicate_id": "phase2.judge_stack.six_judges_present",
                "reason": "judge_stack_missing_required_six_judges",
                "severity": "hard",
                "missing_judges": sorted(_PHASE2_REQUIRED_SIX_JUDGES - present_judges),
            }
        )
    applicability = _Phase2GovernanceApplicability(
        result_id="applicability-governance-tail",
        invocation_id=invocation_id,
        status="repair_required" if failures else "applicable",
        checked_preconditions=[
            {
                "predicate_id": "phase2.governance_tail.promotable",
                "status": "failed" if failures else "passed",
                "rule_version": "policyos.gy.phase2.spine_repair.v1",
            }
        ],
        failed_preconditions=failures,
        repair_options=[
            {
                "operation_class": "VERIFY",
                "reason": "Persist a complete normative result and promotable judge verdict.",
            }
        ]
        if failures
        else [],
    )
    blocker = None
    if failures:
        blocker = _Phase2GovernanceBlocker(
            blocker_id="blocker-governance-tail",
            workspace_id=workspace_id,
            blocked_port="governance.authority",
            missing_input="promotable_judge_verdict",
            reason="Governance tail is not promotable; authority must be withheld.",
            applicability_result_ref=applicability.result_id,
            repair_options=applicability.repair_options,
        )
    return _Phase2GovernanceTailResult(applicability=applicability, blocker=blocker)


def _verify_phase2_governance_tail(
    *,
    workspace_id: str,
    invocation_id: str,
    normative_result: dict[str, Any],
    judge_verdict: dict[str, Any],
) -> _Phase2GovernanceTailResult:
    """Compatibility shim for older internal callers."""

    return verify_phase2_governance_tail(
        workspace_id=workspace_id,
        invocation_id=invocation_id,
        normative_result=normative_result,
        judge_verdict=judge_verdict,
    )


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
        payload = from_canonical_bytes(ctx.store.get_bytes(snapshot_ref))
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
