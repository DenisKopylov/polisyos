"""Mandate-bounded, replay-linked authority decisions before agent effects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    Layer2ReadinessModel,
    OperationContract,
    OperationInvocationRecord,
    gy_content_hash,
)
from polisyos.runtime.quality.candidate_firewall import (
    CandidateFirewallError,
    assert_no_candidate_authority_laundering,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    DecisionOption,
    DelegatedActionEnvelope,
    DelegationContract,
    DraftActionScope,
    FiveRightsRequirement,
    HumanDecisionRecord,
    HumanDecisionRequest,
    build_human_decision_request,
)
from polisyos.runtime.quality.memory_influence import (
    memory_influence_claim_evidence_issues,
)

if TYPE_CHECKING:
    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.http.resource_binding import BoundAuthorizationResource
    from polisyos.runtime.quality.hypothesis_ledger import HypothesisLedgerInput
    from polisyos.runtime.quality.prompt_tool_ledger import ModelAssistedStepLedger

AGENT_ACTION_AUTHORITY_SCHEMA_VERSION = "policyos.runtime.agent_action_authority.v1"
AGENT_ACTION_AUTHORITY_RULE_VERSION = "policyos.gy.pa2.agent-action-authority.v1"

AgentActionOutcome = Literal["allowed", "refused"]
PredicateName = Literal[
    "verified_identity",
    "explicit_permission",
    "mandate_bounded_delegation",
    "operation_in_envelope",
    "live_accountability",
]
PredicateProvenance = Literal["recomputed", "independently_reconciled"]

_PREDICATE_NAMES: tuple[PredicateName, ...] = (
    "verified_identity",
    "explicit_permission",
    "mandate_bounded_delegation",
    "operation_in_envelope",
    "live_accountability",
)
_AUTHORITY_SCOPE_KEY_PARTS = frozenset(
    {
        "authority_scope",
        "delegation_scope",
        "mandate_scope",
        "scope",
        "scope_selector",
    }
)
_AUTHORITY_SCOPE_VALUE_MARKERS = (
    "action_envelope",
    "delegation-envelope:",
    "delegation_contract",
    "delegation-contract",
    "/delegation-contract",
    "mandate_scope",
)
_DECISION_MAY_NOT_USE_FOR = [
    "claim_evidence",
    "publication_authority",
    "promotion_authority",
    "legal_authority",
    "data_authority",
    "permission_vocabulary",
]
class AgentActionIntent(Layer2ReadinessModel):
    """Caller intent whose authority is resolved only from an owner contract."""

    action_kind: str = Field(..., pattern=r"^[a-z][a-z0-9_.:-]*$", max_length=120)
    draft_scope: DraftActionScope | None = None
    tool_name: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _validate_typed_surfaces(self) -> AgentActionIntent:
        if self.action_kind == "draft" and self.draft_scope is None:
            raise ValueError("draft action requires audience and externality")
        if self.action_kind != "draft" and self.draft_scope is not None:
            raise ValueError("draft scope is valid only for the draft action kind")
        if self.action_kind == "tool_call" and self.tool_name is None:
            raise ValueError("tool_call action requires a tool name")
        return self


class ResolvedDelegationContract(Layer2ReadinessModel):
    """Server-resolved, content-bound mandate artifact used by the gate."""

    contract: DelegationContract
    contract_ref: ArtifactRef
    resolved_for_resource_digest: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    predicate_provenance: PredicateProvenance


class AgentActionPermissionSnapshot(Layer2ReadinessModel):
    """Serializable snapshot of the exact DS20 proof consumed by the gate."""

    subject: str
    tenant_id: str
    jwt_id: str
    roles: tuple[str, ...]
    authorization_source: str
    required_permission: str
    granted_permissions: tuple[str, ...]
    resource_digest: str
    resource_kind: str
    resource_authority: str
    body_sha256: str
    query_sha256: str


class AgentActionPredicateCheck(Layer2ReadinessModel):
    """One recomputed conjunct in the pre-action authority decision."""

    predicate: PredicateName
    satisfied: bool
    provenance: PredicateProvenance
    reason: str = Field(..., min_length=1, max_length=500)


class AgentActionAuthorityDecision(Layer2ReadinessModel):
    """Recorded allow or refusal with one shared replay-linked shape."""

    schema_version: Literal["policyos.runtime.agent_action_authority.v1"] = (
        AGENT_ACTION_AUTHORITY_SCHEMA_VERSION
    )
    decision_id: str = Field(..., min_length=1, max_length=220)
    decision_ref: str = Field(..., min_length=1, max_length=300)
    outcome: AgentActionOutcome
    refusal_reasons: tuple[str, ...]
    action_kind: str = Field(..., min_length=1, max_length=120)
    draft_scope: DraftActionScope | None
    case_id: str = Field(..., min_length=1, max_length=200)
    operation_id: str
    operation_version: str
    invocation_id: str
    invocation_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    contract_ref: ArtifactRef | None
    contract_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    envelope_id: str | None = None
    envelope_ref: str | None = None
    envelope_predicate_provenance: PredicateProvenance
    permission_snapshot: AgentActionPermissionSnapshot | None
    predicate_checks: tuple[AgentActionPredicateCheck, ...]
    human_decision_request: HumanDecisionRequest | None
    human_decision_record_ref: str | None = None
    replay_input_refs: tuple[str, ...] = Field(..., min_length=1)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_decision_shape(self) -> AgentActionAuthorityDecision:
        names = tuple(check.predicate for check in self.predicate_checks)
        if names != _PREDICATE_NAMES:
            raise ValueError("agent action decision requires the five ordered conjuncts")
        if self.outcome == "allowed":
            if self.refusal_reasons:
                raise ValueError("allowed decision cannot carry refusal reasons")
            if not all(check.satisfied for check in self.predicate_checks):
                raise ValueError("allowed decision requires all five conjuncts")
        else:
            if not self.refusal_reasons:
                raise ValueError("refused decision requires a refusal reason")
            if self.human_decision_request is None:
                raise ValueError("refused decision requires a human decision request")
            if all(check.satisfied for check in self.predicate_checks):
                raise ValueError("refused decision requires a failed conjunct")
        return self


class AgentActionAuthorityRefused(ValueError):  # noqa: N818 - governed outcome, then raise
    """Raised after a governed refusal decision has been recorded."""

    def __init__(self, decision: AgentActionAuthorityDecision) -> None:
        self.decision = decision
        super().__init__(";".join(decision.refusal_reasons))


class AgentActionAuthorityRecordingError(RuntimeError):
    """Raised when a decision cannot be recorded before the external effect."""


def produce_agent_action_authority_decision(
    *,
    bound_permission: BoundActionPermissionVerification,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: AgentActionIntent,
    resolve_delegation_contract: Callable[
        [BoundAuthorizationResource], ResolvedDelegationContract
    ],
    resolve_human_decision: Callable[[HumanDecisionRequest], HumanDecisionRecord | None]
    | None,
    now: datetime,
    memory_claim_payload: Mapping[str, object],
    authority_input_payload: Mapping[str, object],
    tool_ledger: ModelAssistedStepLedger | None,
    hypothesis_ledger: HypothesisLedgerInput | None = None,
) -> AgentActionAuthorityDecision:
    """Recompute the five-conjunct authority decision without executing an effect."""

    instant = _aware_utc(now)
    invocation_hash = gy_content_hash(invocation.model_dump(mode="json"))
    reasons: list[str] = []
    satisfied: dict[PredicateName, bool] = dict.fromkeys(_PREDICATE_NAMES, False)
    proof_snapshot, bound_resource = _consume_ds20_floor(bound_permission, reasons)
    satisfied["verified_identity"] = proof_snapshot is not None
    satisfied["explicit_permission"] = proof_snapshot is not None

    resolved: ResolvedDelegationContract | None = None
    contract: DelegationContract | None = None
    contract_hash: str | None = None
    if bound_resource is not None:
        try:
            candidate = resolve_delegation_contract(bound_resource)
        except Exception:
            reasons.append("delegation_contract_unavailable")
        else:
            if type(candidate) is not ResolvedDelegationContract:
                reasons.append("delegation_contract_resolution_untyped")
            else:
                try:
                    validated_contract = DelegationContract.model_validate(
                        candidate.contract.model_dump(mode="python")
                    )
                except (AttributeError, TypeError, ValueError):
                    reasons.append("delegation_contract_invalid")
                else:
                    candidate_hash = gy_content_hash(
                        validated_contract.model_dump(mode="json")
                    )
                    if candidate.contract_ref.content_hash != candidate_hash:
                        reasons.append("delegation_contract_content_hash_mismatch")
                    elif (
                        candidate.resolved_for_resource_digest
                        != bound_resource.resource_digest
                    ):
                        reasons.append("delegation_contract_resource_mismatch")
                    else:
                        resolved = candidate
                        contract = validated_contract
                        contract_hash = candidate_hash

    caller_scope_path = _caller_controlled_scope_path(invocation)
    if caller_scope_path is not None:
        reasons.append("envelope_provenance_caller_controlled")

    invocation_matches_operation = (
        invocation.operation_id == operation.operation_id
        and invocation.operation_version == operation.operation_version
    )
    if not invocation_matches_operation:
        reasons.append("operation_invocation_mismatch")

    if memory_influence_claim_evidence_issues(memory_claim_payload):
        reasons.append("memory_not_admissible_as_policy_fact")

    try:
        assert_no_candidate_authority_laundering(
            authority_input_payload,
            hypothesis_ledger=hypothesis_ledger,
            surface="agent_action_authority_input",
        )
    except CandidateFirewallError:
        reasons.append("input_candidate_not_admitted")

    if intent.tool_name is not None and not _tool_is_admitted(intent.tool_name, tool_ledger):
        reasons.append("tool_admission_missing")

    selected: DelegatedActionEnvelope | None = None
    kind_rows: tuple[DelegatedActionEnvelope, ...] = ()
    if contract is not None:
        kind_rows = tuple(
            envelope
            for envelope in contract.action_envelopes
            if envelope.action_kind == intent.action_kind
        )
        if not kind_rows:
            reasons.append("unknown_action_kind")
        else:
            operation_rows = tuple(
                envelope
                for envelope in kind_rows
                if envelope.operation_id == operation.operation_id
                and envelope.operation_version == operation.operation_version
            )
            if not operation_rows:
                reasons.append("operation_out_of_envelope")
                selected = kind_rows[0]
            elif len(operation_rows) > 1:
                reasons.append("delegation_envelope_ambiguous")
            else:
                selected = operation_rows[0]

    if selected is not None and proof_snapshot is not None and bound_resource is not None:
        if selected.required_permission.value != proof_snapshot.required_permission:
            reasons.append("explicit_permission_mismatch")
            satisfied["explicit_permission"] = False
        if selected.authorized_subject != proof_snapshot.subject:
            reasons.append("delegation_subject_mismatch")
        if selected.required_tenant_id != proof_snapshot.tenant_id:
            reasons.append("delegation_tenant_mismatch")
        if selected.required_resource_digest != bound_resource.resource_digest:
            reasons.append("delegation_resource_mismatch")
        if selected.draft_scope != intent.draft_scope:
            reasons.append("draft_scope_out_of_envelope")

    mandate_blockers = {
        "delegation_contract_unavailable",
        "delegation_contract_resolution_untyped",
        "delegation_contract_content_hash_mismatch",
        "delegation_contract_invalid",
        "delegation_contract_resource_mismatch",
        "envelope_provenance_caller_controlled",
        "memory_not_admissible_as_policy_fact",
        "input_candidate_not_admitted",
        "tool_admission_missing",
        "unknown_action_kind",
        "delegation_envelope_ambiguous",
        "delegation_subject_mismatch",
        "delegation_tenant_mismatch",
        "delegation_resource_mismatch",
        "draft_scope_out_of_envelope",
    }
    satisfied["mandate_bounded_delegation"] = (
        contract is not None
        and selected is not None
        and contract.mandate_owner_ref is not None
        and not mandate_blockers.intersection(reasons)
    )
    satisfied["operation_in_envelope"] = (
        invocation_matches_operation
        and selected is not None
        and selected.operation_id == operation.operation_id
        and selected.operation_version == operation.operation_version
        and "delegation_envelope_ambiguous" not in reasons
    )

    if selected is not None and proof_snapshot is not None:
        if selected.status != "active":
            reasons.append("delegation_envelope_revoked")
        if instant < selected.valid_from:
            reasons.append("delegation_envelope_not_yet_valid")
        if instant >= selected.valid_until:
            reasons.append("delegation_envelope_expired")
        if not set(proof_snapshot.roles).intersection(
            role.value for role in selected.authorized_runtime_roles
        ):
            reasons.append("delegation_runtime_role_mismatch")
        satisfied["live_accountability"] = not {
            "delegation_envelope_revoked",
            "delegation_envelope_not_yet_valid",
            "delegation_envelope_expired",
            "delegation_runtime_role_mismatch",
        }.intersection(reasons)

    request = _human_decision_request(
        contract=contract,
        invocation=invocation,
        action_kind=intent.action_kind,
        now=instant,
        selected_envelope=selected,
    )
    decision_record_ref: str | None = None
    if (
        contract is not None
        and selected is not None
        and "operation_out_of_envelope" in reasons
        and not (set(reasons) - {"operation_out_of_envelope"})
        and resolve_human_decision is not None
    ):
        human_record = resolve_human_decision(request)
        human_issue = _human_override_issue(
            contract=contract,
            request=request,
            record=human_record,
            now=instant,
            envelope=selected,
        )
        if human_issue is None and human_record is not None:
            reasons.remove("operation_out_of_envelope")
            satisfied["operation_in_envelope"] = True
            decision_record_ref = human_record.record_ref
        elif human_issue is not None:
            reasons.append(human_issue)

    reasons = list(dict.fromkeys(reasons))
    allowed = all(satisfied.values()) and not reasons
    outcome: AgentActionOutcome = "allowed" if allowed else "refused"
    checks = _predicate_checks(satisfied, resolved)
    replay_refs = _replay_refs(
        invocation_hash=invocation_hash,
        resolved=resolved,
        selected=selected,
        human_decision_record_ref=decision_record_ref,
    )
    case_id = contract.case_id if contract is not None else invocation.workspace_id
    suffix = f"{invocation.invocation_id}.{intent.action_kind}"
    return AgentActionAuthorityDecision(
        decision_id=f"agent-action-authority.{suffix}",
        decision_ref=f"runtime://agent-action-authority/{suffix}",
        outcome=outcome,
        refusal_reasons=tuple(reasons),
        action_kind=intent.action_kind,
        draft_scope=intent.draft_scope,
        case_id=case_id,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        invocation_id=invocation.invocation_id,
        invocation_content_hash=invocation_hash,
        contract_ref=resolved.contract_ref if resolved is not None else None,
        contract_content_hash=contract_hash,
        envelope_id=selected.envelope_id if selected is not None else None,
        envelope_ref=selected.envelope_ref if selected is not None else None,
        envelope_predicate_provenance="recomputed",
        permission_snapshot=proof_snapshot,
        predicate_checks=checks,
        human_decision_request=None if allowed else request,
        human_decision_record_ref=decision_record_ref,
        replay_input_refs=replay_refs,
        authority_boundary=_decision_authority_boundary(),
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
        decided_at=instant,
    )


def dispatch_agent_external_action[T](
    *,
    bound_permission: BoundActionPermissionVerification,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: AgentActionIntent,
    resolve_delegation_contract: Callable[
        [BoundAuthorizationResource], ResolvedDelegationContract
    ],
    resolve_human_decision: Callable[[HumanDecisionRequest], HumanDecisionRecord | None]
    | None,
    record_decision: Callable[[AgentActionAuthorityDecision], object],
    effect: Callable[[], T],
    now: datetime,
    memory_claim_payload: Mapping[str, object],
    authority_input_payload: Mapping[str, object],
    tool_ledger: ModelAssistedStepLedger | None,
    hypothesis_ledger: HypothesisLedgerInput | None = None,
) -> T:
    """Record the authority decision, then execute only a recorded allow."""

    decision = produce_agent_action_authority_decision(
        bound_permission=bound_permission,
        operation=operation,
        invocation=invocation,
        intent=intent,
        resolve_delegation_contract=resolve_delegation_contract,
        resolve_human_decision=resolve_human_decision,
        now=now,
        memory_claim_payload=memory_claim_payload,
        authority_input_payload=authority_input_payload,
        tool_ledger=tool_ledger,
        hypothesis_ledger=hypothesis_ledger,
    )
    try:
        record_decision(decision)
    except Exception as exc:
        raise AgentActionAuthorityRecordingError(
            "agent action authority decision was not recorded; effect refused"
        ) from exc
    if decision.outcome == "refused":
        raise AgentActionAuthorityRefused(decision)
    return effect()


def _consume_ds20_floor(
    bound_permission: object,
    reasons: list[str],
) -> tuple[AgentActionPermissionSnapshot | None, BoundAuthorizationResource | None]:
    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification,
        BoundActionPermissionVerification,
    )
    from polisyos.runtime.http.resource_binding import BoundAuthorizationResource

    if type(bound_permission) is not BoundActionPermissionVerification:
        reasons.append("verified_identity_proof_missing")
        return None, None
    verification = bound_permission.verification
    resource = bound_permission.bound_resource
    if (
        type(verification) is not ActionPermissionVerification
        or type(resource) is not BoundAuthorizationResource
    ):
        reasons.append("verified_identity_proof_invalid")
        return None, None
    if resource.requirement != verification.requirement:
        reasons.append("bound_resource_requirement_mismatch")
        return None, None
    required_permission = verification.requirement.permission
    if required_permission not in verification.granted_permissions:
        reasons.append("explicit_permission_missing")
        return None, None
    if (
        not verification.subject.strip()
        or not verification.tenant_id.strip()
        or not verification.jwt_id.strip()
        or not verification.roles
        or not verification.authorization_source.strip()
    ):
        reasons.append("verified_identity_incomplete")
        return None, None
    if resource.tenant_id is not None and resource.tenant_id != verification.tenant_id:
        reasons.append("bound_resource_tenant_mismatch")
        return None, None
    return (
        AgentActionPermissionSnapshot(
            subject=verification.subject,
            tenant_id=verification.tenant_id,
            jwt_id=verification.jwt_id,
            roles=tuple(sorted(role.value for role in verification.roles)),
            authorization_source=verification.authorization_source,
            required_permission=required_permission.value,
            granted_permissions=tuple(
                sorted(permission.value for permission in verification.granted_permissions)
            ),
            resource_digest=resource.resource_digest,
            resource_kind=resource.resource_kind,
            resource_authority=resource.authority.value,
            body_sha256=resource.body_sha256,
            query_sha256=resource.query_sha256,
        ),
        resource,
    )


def _caller_controlled_scope_path(invocation: OperationInvocationRecord) -> str | None:
    for root, payload in (
        ("parameters", invocation.parameters),
        ("selected_by", invocation.selected_by),
        ("internal_trace", invocation.internal_trace),
    ):
        path = _scope_path(payload, root)
        if path is not None:
            return path
    return None


def _scope_path(value: object, path: str) -> str | None:
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key).strip().casefold().replace("-", "_")
            nested_path = f"{path}.{raw_key}"
            if "envelope" in key or key in _AUTHORITY_SCOPE_KEY_PARTS or key.endswith("_scope"):
                return nested_path
            found = _scope_path(nested, nested_path)
            if found is not None:
                return found
        return None
    if isinstance(value, list | tuple | set):
        for index, nested in enumerate(value):
            found = _scope_path(nested, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    if isinstance(value, str):
        normalized = value.casefold().replace("-", "_")
        if any(marker.replace("-", "_") in normalized for marker in _AUTHORITY_SCOPE_VALUE_MARKERS):
            return path
    return None


def _tool_is_admitted(tool_name: str, ledger: object) -> bool:
    from polisyos.runtime.quality.prompt_tool_ledger import ModelAssistedStepLedger

    if type(ledger) is not ModelAssistedStepLedger:
        return False
    if tool_name not in ledger.tool_allowlist:
        return False
    calls = [call for call in ledger.tool_call_refs if call.tool_name == tool_name]
    return bool(calls) and all(call.status == "pass" for call in calls)


def _human_decision_request(
    *,
    contract: DelegationContract | None,
    invocation: OperationInvocationRecord,
    action_kind: str,
    now: datetime,
    selected_envelope: DelegatedActionEnvelope | None,
) -> HumanDecisionRequest:
    request_id = f"agent-action.{invocation.invocation_id}.{action_kind}"[:120]
    request_ref = f"runtime://agent-action-authority/requests/{request_id}"
    decidable_until = (
        selected_envelope.valid_until
        if selected_envelope is not None and selected_envelope.valid_until > now
        else now
    )
    if contract is not None:
        base = build_human_decision_request(
            case_id=contract.case_id,
            contract=contract,
            decision_class_id="mandate_boundary",
            need_reasons=["out_of_envelope"],
            voi_rank=1,
            s6_mandate_record_ref=contract.s6_mandate_record_ref,
            s6_mandate_firewall_disposition=contract.s6_mandate_firewall_disposition,
            rule_version_ref=contract.rule_version_ref,
        )
        return base.model_copy(
            update={
                "request_id": request_id,
                "request_ref": request_ref,
                "requested_at": now,
                "decision_due_at": now,
                "decidable_until": decidable_until,
                "provenance_refs": [
                    contract.contract_ref,
                    f"runtime://operation-invocation/{invocation.invocation_id}",
                ],
            }
        )
    return HumanDecisionRequest(
        request_id=request_id,
        request_ref=request_ref,
        case_id=invocation.workspace_id,
        delegation_contract_ref="runtime://delegation-contract/unresolved",
        decision_rights_matrix_ref="runtime://decision-rights/unresolved",
        decision_class_id="mandate_boundary",
        required_role="mandate_owner",
        interaction_mode="request_driven",
        disposition="request_human_decision",
        need_reasons=["out_of_envelope"],
        requested_at=now,
        decision_due_at=now,
        decidable_until=now,
        decision_options=[
            DecisionOption(
                option_id="escalate",
                action="escalate",
                label="Escalate",
                consequence="No action occurs until mandate authority is resolved.",
            )
        ],
        provenance_refs=[f"runtime://operation-invocation/{invocation.invocation_id}"],
        material_limitations=["Delegation contract could not be resolved."],
        value_stakes_impact="An external agent action is blocked pending accountable review.",
        what_changes_under_each_choice=["Escalation preserves zero external effects."],
        five_rights_requirements=FiveRightsRequirement(
            right_decision=f"Decide whether to authorize {action_kind}.",
            right_person="mandate_owner",
            right_information="Identity, permission, operation, envelope, and refusal reasons.",
            right_format_channel="governed_review",
            right_time="Before any external effect.",
        ),
        available_actions=["escalate"],
        attention_cost_rank=1,
        voi_rank=1,
        s6_mandate_record_ref="runtime://mandate/unresolved",
        s6_mandate_firewall_disposition="block",
        authority_boundary=AuthorityBoundary(
            authoritative_for=["human_decision_routing"],
            may_not_use_for=_DECISION_MAY_NOT_USE_FOR,
            source_authority="deterministic_producer",
            posture="shadow",
            rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
        ),
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
    )


def _human_override_issue(
    *,
    contract: DelegationContract,
    request: HumanDecisionRequest,
    record: HumanDecisionRecord | None,
    now: datetime,
    envelope: DelegatedActionEnvelope,
) -> str | None:
    if record is None:
        return "human_decision_record_missing"
    if record.human_decision_request_ref != request.request_ref:
        return "human_decision_request_mismatch"
    if record.case_id != contract.case_id:
        return "human_decision_case_mismatch"
    if record.actor_ref != contract.mandate_owner_ref or record.actor_role != request.required_role:
        return "human_decision_wrong_role"
    if record.decision_action_exercised != "approve" or not record.active_choice:
        return "human_decision_not_approved"
    if not record.five_rights_check.all_pass():
        return "human_decision_five_rights_failed"
    if record.responsibility_integrity.status != "pass":
        return "human_decision_integrity_failed"
    if record.decided_at > now or record.decided_at > envelope.valid_until:
        return "human_decision_outside_ttl"
    if request.decidable_until is None or record.decided_at > request.decidable_until:
        return "human_decision_outside_ttl"
    return None


def _predicate_checks(
    satisfied: Mapping[PredicateName, bool],
    resolved: ResolvedDelegationContract | None,
) -> tuple[AgentActionPredicateCheck, ...]:
    reasons = {
        "verified_identity": "Exact DS20 bound identity proof is present and internally bound.",
        "explicit_permission": "The exact DS20 permission equals the owner envelope permission.",
        "mandate_bounded_delegation": "The server-resolved owner contract bounds the action.",
        "operation_in_envelope": (
            "Operation and invocation match one owner envelope or exact override."
        ),
        "live_accountability": "The envelope is active, in TTL, and role-accountable.",
    }
    return tuple(
        AgentActionPredicateCheck(
            predicate=name,
            satisfied=satisfied[name],
            provenance=(
                resolved.predicate_provenance
                if name == "mandate_bounded_delegation" and resolved is not None
                else "recomputed"
            ),
            reason=reasons[name],
        )
        for name in _PREDICATE_NAMES
    )


def _replay_refs(
    *,
    invocation_hash: str,
    resolved: ResolvedDelegationContract | None,
    selected: DelegatedActionEnvelope | None,
    human_decision_record_ref: str | None,
) -> tuple[str, ...]:
    refs = [invocation_hash]
    if resolved is not None:
        refs.extend((resolved.contract_ref.uri, resolved.contract_ref.content_hash))
    if selected is not None:
        refs.extend((selected.envelope_ref, selected.issuance_decision_ref))
    if human_decision_record_ref is not None:
        refs.append(human_decision_record_ref)
    return tuple(dict.fromkeys(refs))


def _decision_authority_boundary() -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["agent_action_dispatch_decision"],
        may_not_use_for=_DECISION_MAY_NOT_USE_FOR,
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("agent action authority decision time must be timezone-aware")
    return value.astimezone(UTC)


__all__ = [
    "AGENT_ACTION_AUTHORITY_RULE_VERSION",
    "AGENT_ACTION_AUTHORITY_SCHEMA_VERSION",
    "AgentActionAuthorityDecision",
    "AgentActionAuthorityRecordingError",
    "AgentActionAuthorityRefused",
    "AgentActionIntent",
    "AgentActionPermissionSnapshot",
    "AgentActionPredicateCheck",
    "DraftActionScope",
    "ResolvedDelegationContract",
    "dispatch_agent_external_action",
    "produce_agent_action_authority_decision",
]
