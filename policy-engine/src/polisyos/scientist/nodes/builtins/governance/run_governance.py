from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.contracts.scientist import GovernanceReportRef
from polisyos.ir.gate import GateContext, GateDecision, GatePriority, GateRequest, GateVerdict
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.passes.base import PassContext
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass
from polisyos.scientist.governance.passes.equity_pass import EquityPass
from polisyos.scientist.governance.passes.pii_check_pass import PIICheckPass
from polisyos.scientist.governance.profiles import ValidationProfile
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.kernel.gate_protocol import HumanGateProtocol
from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF
from polisyos.scientist.nodes.builtins.state_keys import INPUT_DATA_SNAPSHOT_REF

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_governance@1.1.0"),
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
        "artifacts_index.simulation_result_ref",
        "artifacts_index.distributional_report_ref",
    ],
    state_writes=["params", f"reports_index.{REPORT_GOVERNANCE_REPORT_REF}"],
    produces=[REPORT_GOVERNANCE_REPORT_REF],
)

_DECISION_APPROVE = {"approve", "approved", "allow", "allowed"}
_DECISION_REJECT = {"reject", "rejected", "deny", "denied"}
_DECISION_ESCALATE = {"escalate", "escalated"}


@dataclass(frozen=True)
class RunGovernanceNode:
    """Governance node with typed Human Gate protocol."""

    default_verdict: Literal["approve", "needs_revision", "reject", "human_gate"] = "approve"

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> "RunGovernanceNode":
        if not params:
            return self
        verdict = params.get("default_verdict", self.default_verdict)
        return replace(self, default_verdict=str(verdict))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        verdict = self.default_verdict
        issues: list[dict[str, Any]] = []
        events: list[NodeEvent] = []

        protocol = HumanGateProtocol(ctx.run)
        new_state = state.model_copy(deep=True)

        require_human_gate = bool(new_state.params.get("require_human_gate"))
        raw_gate_decision = new_state.params.get("gate_decision")
        gate_request = _parse_gate_request(new_state.params.get("gate_request"))
        gate_request_ref = _parse_gate_request_ref(new_state.params.get("gate_request_ref"))

        if require_human_gate and raw_gate_decision is None:
            if gate_request is None:
                gate_request, gate_request_ref = _create_gate_request(
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

        profile = _resolve_validation_profile(new_state.params.get("governance_profile"))
        governance_issues = _run_governance_checks(ctx, new_state, profile)
        if governance_issues:
            issues.extend([_issue_to_payload(issue) for issue in governance_issues])
            blocker_count = sum(
                1 for issue in governance_issues if issue.severity == IssueSeverity.BLOCKER
            )
            if blocker_count > 0 and verdict != "human_gate":
                verdict = "reject"
                events.append(
                    NodeEvent(
                        level="warn",
                        message=(
                            f"Governance checks blocked decision "
                            f"({blocker_count} blocker(s))"
                        ),
                    )
                )

        report = GovernanceReport(verdict=verdict, issues=issues)
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
        return NodeOutcome(status="ok", state=new_state, artifacts=[report_ref], events=events)


def _create_gate_request(
    *,
    protocol: HumanGateProtocol,
    state: ExperimentState,
) -> tuple[GateRequest, ArtifactRef | None]:
    iteration = _as_int(state.params.get("gate_iteration"))
    is_escalated = bool(state.params.get("gate_escalated"))
    workflow_id = str(state.params.get("workflow_id", "scientist_default"))
    phase = str(state.params.get("phase", "POSTFLIGHT_GOV"))
    governance_profile_raw = state.params.get("governance_profile")
    governance_profile = (
        str(governance_profile_raw) if isinstance(governance_profile_raw, str) else None
    )
    timeout_seconds = _optional_int(state.params.get("gate_timeout_seconds"))

    context = GateContext(
        workflow_id=workflow_id,
        node_alias="run_governance",
        phase=phase,
        governance_profile=governance_profile,
        iteration=iteration,
        is_escalated=is_escalated,
    )
    priority = GatePriority.CRITICAL if is_escalated else GatePriority.NORMAL
    return protocol.request_gate(
        run_id=state.run_id,
        reason="Governance profile requires human approval",
        context=context,
        priority=priority,
        timeout_seconds=timeout_seconds,
        requested_by="scientist.node_run_governance",
    )


def _parse_gate_request(raw: Any) -> GateRequest | None:
    if isinstance(raw, GateRequest):
        return raw
    if isinstance(raw, dict):
        try:
            return GateRequest.model_validate(raw)
        except Exception:
            return None
    return None


def _parse_gate_request_ref(raw: Any) -> ArtifactRef | None:
    if not isinstance(raw, str):
        return None
    try:
        artifact_id = ArtifactID.model_validate(raw)
    except Exception:
        return None
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="ir.gate_request",
        media_type="application/json",
    )


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
            except Exception:
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


def _resolve_validation_profile(raw: Any) -> ValidationProfile:
    if isinstance(raw, ValidationProfile):
        return raw
    if isinstance(raw, dict):
        try:
            return ValidationProfile.from_dict(raw)
        except Exception:
            return ValidationProfile.mvp()
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token == "fast":
            return ValidationProfile.fast()
        if token == "strict":
            return ValidationProfile.strict()
    return ValidationProfile.mvp()


def _run_governance_checks(
    ctx: ExecutionContext,
    state: ExperimentState,
    profile: ValidationProfile,
) -> list[ComplianceIssue]:
    pii_scan_results = _extract_pii_scan_results(ctx, state)
    pass_ctx = PassContext(
        ir=None,
        state={
            "artifacts_index": state.artifacts_index,
            "_store": ctx.store,
            "tenant_tier": str(state.params.get("tenant_tier", "shared")),
            "pii_scan_results": pii_scan_results,
        },
        registry_bundle=None,
        profile=profile,
        run_id=state.run_id,
    )
    issues: list[ComplianceIssue] = []
    if "confidence" in profile.pass_ids:
        issues.extend(ConfidencePass().validate(pass_ctx))
    if "equity" in profile.pass_ids:
        issues.extend(EquityPass().validate(pass_ctx))
    if "pii_check" in profile.pass_ids:
        issues.extend(PIICheckPass().validate(pass_ctx))
    return issues


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
    except Exception:
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
