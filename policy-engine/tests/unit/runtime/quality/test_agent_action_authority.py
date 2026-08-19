from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from polisyos.core.security.identity import PolicyOSRole
from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    OperationClass,
    OperationContract,
    OperationInvocationRecord,
)
from polisyos.runtime.http.authorization import (
    ActionPermissionVerification,
    BoundActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    RouteAuthorizationRequirement,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import (
    BindingAuthority,
    BoundAuthorizationResource,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    FiveRightsCheck,
    HumanDecisionRecord,
    HumanDecisionRequest,
    ResponsibilityIntegrityCheck,
    build_decision_rights_matrix,
    build_delegation_contract,
    build_governance_decision_class_registry,
)

NOW = datetime(2026, 8, 19, 12, tzinfo=UTC)
CASE_ID = "gy-pa2-case"
RULE_VERSION_REF = "policyos.gy.pa2.agent-action-authority.v1"
MANDATE_OWNER_REF = "principal://mandate-owner/gy-pa2"
DIGEST = "sha256:" + "a" * 64


def _authority_module() -> Any:
    try:
        return importlib.import_module("polisyos.runtime.quality.agent_action_authority")
    except ModuleNotFoundError as exc:
        pytest.fail(f"GY-PA2 producer is missing: {exc}")


def _delegation_module() -> Any:
    return importlib.import_module(
        "polisyos.runtime.quality.design_axes.mandate_bounded_delegation"
    )


def _boundary(*, authoritative_for: str, source: str = "human_governance") -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=[authoritative_for],
        may_not_use_for=[
            "claim_evidence",
            "publication_authority",
            "promotion_authority",
        ],
        source_authority=source,
        posture="governed",
        rule_version_refs=[RULE_VERSION_REF],
    )


def _proof(
    permission: RuntimePermission = RuntimePermission.KNOWLEDGE_SEARCH,
    *,
    roles: frozenset[PolicyOSRole] = frozenset({PolicyOSRole.ANALYST}),
) -> BoundActionPermissionVerification:
    requirement = RouteAuthorizationRequirement(
        permission=permission,
        resource_binding=ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.agent_action",
        ),
    )
    verification = ActionPermissionVerification(
        requirement=requirement,
        subject="user:agent-operator",
        tenant_id="tenant-a",
        jwt_id="jwt-gy-pa2",
        roles=roles,
        authorization_source="runtime.jwt+opa",
        granted_permissions=(permission,),
    )
    resource = BoundAuthorizationResource(
        requirement=requirement,
        tenant_id="tenant-a",
        resource_kind="runtime.agent_action.tenant_collection",
        resource_id=f"urn:polisyos:runtime-authorization-resource:v1:{DIGEST}",
        resource_digest=DIGEST,
        authority=BindingAuthority.TENANT_COLLECTION,
        body_sha256="sha256:" + "b" * 64,
        query_sha256="sha256:" + "c" * 64,
        canonical_selectors=(("tenant_id", '"tenant-a"'),),
    )
    return BoundActionPermissionVerification(
        verification=verification,
        bound_resource=resource,
    )


def _operation(operation_id: str = "agent.search") -> OperationContract:
    return OperationContract(
        operation_id=operation_id,
        operation_version="v1",
        operation_class=OperationClass.DISCOVER,
        consumes=[],
        produces=[],
        formal_preconditions=[],
        allowed_internal_execution=["tool_call"],
        implementation_refs=[{"module": "tests.spy", "symbol": "effect"}],
        cost_model={"kind": "bounded"},
        authority_transform={"kind": "preserves"},
        failure_modes=["authority_refused"],
        repair_options=[OperationClass.ESCALATE],
    )


def _invocation(
    operation: OperationContract,
    *,
    parameters: dict[str, object] | None = None,
    tool_calls: list[str] | None = None,
) -> OperationInvocationRecord:
    return OperationInvocationRecord(
        invocation_id=f"invoke-{operation.operation_id.replace('.', '-')}",
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        workspace_id="workspace-gy-pa2",
        cycle_index=3,
        selected_by={"producer": "gy-pa2-test"},
        selection_rationale_ref="cas://selection/gy-pa2",
        input_artifacts=[],
        parameters=parameters or {},
        internal_trace={"phase": "pre-action"},
        tool_calls=tool_calls or [],
        human_requests=[],
        output_artifacts=[],
        applicability_result="applicable",
        budget_delta={"actions": 1},
        status="started",
    )


def _envelope(
    *,
    action_kind: str = "search",
    operation_id: str = "agent.search",
    permission: RuntimePermission = RuntimePermission.KNOWLEDGE_SEARCH,
    roles: tuple[PolicyOSRole, ...] = (PolicyOSRole.ANALYST,),
    valid_from: datetime = NOW - timedelta(minutes=5),
    valid_until: datetime = NOW + timedelta(hours=1),
    status: str = "active",
    draft_scope: object | None = None,
) -> object:
    delegation = _delegation_module()
    return delegation.DelegatedActionEnvelope(
        envelope_id=f"envelope.{action_kind}.{operation_id.replace('.', '-')}",
        envelope_ref=f"pdc://gy-pa2/envelopes/{action_kind}/{operation_id}",
        case_id=CASE_ID,
        mandate_owner_ref=MANDATE_OWNER_REF,
        owner_role="mandate_owner",
        action_kind=action_kind,
        operation_id=operation_id,
        operation_version="v1",
        required_permission=permission,
        authorized_subject="user:agent-operator",
        authorized_runtime_roles=roles,
        required_tenant_id="tenant-a",
        required_resource_digest=DIGEST,
        valid_from=valid_from,
        valid_until=valid_until,
        status=status,
        issuance_decision_ref="pdc://gy-pa2/human-decisions/envelope-issuance",
        draft_scope=draft_scope,
        provenance_refs=("pdc://gy-pa2/mandate/owner-declaration",),
        rule_version_ref=RULE_VERSION_REF,
        authority_boundary=_boundary(authoritative_for="agent_action_envelope"),
    )


def _contract(*envelopes: object) -> object:
    registry = build_governance_decision_class_registry(CASE_ID, RULE_VERSION_REF)
    matrix = build_decision_rights_matrix(CASE_ID, registry, RULE_VERSION_REF)
    base = build_delegation_contract(
        case_id=CASE_ID,
        matrix=matrix,
        governance_decision_classes=registry,
        s6_mandate_record_ref="pdc://gy-pa2/mandate",
        s6_mandate_firewall_disposition="pass",
        rule_version_ref=RULE_VERSION_REF,
    )
    return base.model_copy(
        update={
            "mandate_owner_ref": MANDATE_OWNER_REF,
            "action_envelopes": tuple(envelopes),
        }
    )


def _resolved(contract: object) -> object:
    authority = _authority_module()
    assert hasattr(contract, "model_dump")
    payload = contract.model_dump(mode="json")
    ref = ArtifactRef.from_payload(
        artifact_id="gy-pa2.delegation-contract",
        artifact_type="runtime.delegation_contract",
        payload=payload,
        schema_ref="schema://runtime/delegation-contract/v1",
        uri="cas://gy-pa2/delegation-contract",
        version="v1",
    )
    return authority.ResolvedDelegationContract(
        contract=contract,
        contract_ref=ref,
        resolved_for_resource_digest=DIGEST,
        predicate_provenance="independently_reconciled",
    )


def _intent(
    action_kind: str = "search",
    *,
    draft_scope: object | None = None,
    tool_name: str | None = None,
) -> object:
    authority = _authority_module()
    return authority.AgentActionIntent(
        action_kind=action_kind,
        draft_scope=draft_scope,
        tool_name=tool_name,
    )


def _dispatch(
    *,
    contract: object,
    proof: object | None = None,
    operation: OperationContract | None = None,
    invocation: OperationInvocationRecord | None = None,
    intent: object | None = None,
    effect: object,
    records: list[object],
    now: datetime = NOW,
    memory_claim_payload: dict[str, object] | None = None,
    authority_input_payload: dict[str, object] | None = None,
    tool_ledger: object | None = None,
    resolve_human_decision: object | None = None,
) -> object:
    authority = _authority_module()
    selected_operation = operation or _operation()
    selected_invocation = invocation or _invocation(selected_operation)
    return authority.dispatch_agent_external_action(
        bound_permission=proof or _proof(),
        operation=selected_operation,
        invocation=selected_invocation,
        intent=intent or _intent(),
        resolve_delegation_contract=lambda _resource: _resolved(contract),
        resolve_human_decision=resolve_human_decision,
        record_decision=records.append,
        effect=effect,
        now=now,
        memory_claim_payload=memory_claim_payload or {},
        authority_input_payload=authority_input_payload or {},
        tool_ledger=tool_ledger,
    )


def _assert_refused_with_zero_effect(
    *,
    contract: object,
    expected_reason: str,
    **kwargs: object,
) -> object:
    authority = _authority_module()
    effects: list[str] = []
    records: list[object] = []

    with pytest.raises(authority.AgentActionAuthorityRefused) as exc_info:
        _dispatch(
            contract=contract,
            effect=lambda: effects.append("FIRED"),
            records=records,
            **kwargs,
        )

    assert effects == []
    assert len(records) == 1
    decision = records[0]
    assert exc_info.value.decision == decision
    assert decision.outcome == "refused"
    assert expected_reason in decision.refusal_reasons
    assert decision.human_decision_request is not None
    assert decision.invocation_content_hash.startswith("sha256:")
    assert decision.replay_input_refs
    return decision


def _human_record(
    request: HumanDecisionRequest,
    *,
    actor_role: str,
) -> HumanDecisionRecord:
    return HumanDecisionRecord(
        record_id=f"record.{request.request_id}",
        record_ref=f"pdc://gy-pa2/decision/{request.request_id}",
        case_id=CASE_ID,
        human_decision_request_ref=request.request_ref,
        actor_ref=MANDATE_OWNER_REF,
        actor_role=actor_role,
        decided_at=NOW,
        decision_action_exercised="approve",
        evidence_summary_ref="cas://gy-pa2/decision/evidence-summary",
        disconfirming_evidence_refs=["cas://gy-pa2/decision/disconfirming"],
        active_choice=True,
        accountability_statement="I accept accountability for this exact invocation.",
        mandate_record_ref="pdc://gy-pa2/mandate",
        mandate_source_refs=["pdc://gy-pa2/mandate"],
        five_rights_check=FiveRightsCheck(
            right_decision=True,
            right_person=True,
            right_information=True,
            right_format_channel=True,
            right_time=True,
        ),
        responsibility_integrity=ResponsibilityIntegrityCheck(
            status="pass",
            pattern_ids=["P26", "P05"],
            reason="All five rights passed for the exact invocation.",
            missing_requirements=[],
            rule_version_ref=RULE_VERSION_REF,
        ),
        authority_boundary=_boundary(authoritative_for="mandate_bounded_decision_record"),
        provenance_refs=[request.request_ref],
        rule_version_ref=RULE_VERSION_REF,
    )


def test_wrong_role_human_click_is_recorded_and_never_fires_effect() -> None:
    envelope = _envelope()
    contract = _contract(envelope)
    operation = _operation("agent.outside-envelope")
    invocation = _invocation(operation)

    _assert_refused_with_zero_effect(
        contract=contract,
        operation=operation,
        invocation=invocation,
        expected_reason="human_decision_wrong_role",
        resolve_human_decision=lambda request: _human_record(
            request,
            actor_role="data_steward",
        ),
    )


def test_expired_envelope_is_recorded_and_never_fires_effect() -> None:
    contract = _contract(
        _envelope(
            valid_from=NOW - timedelta(hours=2),
            valid_until=NOW - timedelta(seconds=1),
        )
    )

    _assert_refused_with_zero_effect(
        contract=contract,
        expected_reason="delegation_envelope_expired",
    )


def test_search_authority_does_not_grant_data_request() -> None:
    contract = _contract(
        _envelope(action_kind="search"),
        _envelope(
            action_kind="data_request",
            operation_id="agent.data-request",
            permission=RuntimePermission.EVIDENCE_ACQUIRE,
        ),
    )
    operation = _operation("agent.data-request")

    _assert_refused_with_zero_effect(
        contract=contract,
        operation=operation,
        invocation=_invocation(operation),
        intent=_intent("data_request"),
        expected_reason="explicit_permission_mismatch",
    )


def test_memory_record_masquerading_as_policy_fact_never_fires_effect() -> None:
    _assert_refused_with_zero_effect(
        contract=_contract(_envelope()),
        expected_reason="memory_not_admissible_as_policy_fact",
        memory_claim_payload={
            "data_refs": ["memory-influence:prior-policy-fact"],
        },
    )


def test_unadmitted_tool_surface_never_fires_effect() -> None:
    contract = _contract(
        _envelope(action_kind="tool_call", operation_id="agent.tool-call")
    )
    operation = _operation("agent.tool-call")

    _assert_refused_with_zero_effect(
        contract=contract,
        operation=operation,
        invocation=_invocation(operation, tool_calls=["web.search"]),
        intent=_intent("tool_call", tool_name="web.search"),
        expected_reason="tool_admission_missing",
    )


def test_unadmitted_candidate_input_never_fires_effect() -> None:
    _assert_refused_with_zero_effect(
        contract=_contract(_envelope()),
        expected_reason="input_candidate_not_admitted",
        authority_input_payload={
            "selected_norm_refs": ["hypothesis-candidate:policy-fact"],
        },
    )


def test_invocation_supplied_widened_envelope_names_provenance_and_never_fires() -> None:
    operation = _operation()
    invocation = _invocation(
        operation,
        parameters={
            "action_envelope": {
                "action_kind": "search",
                "valid_until": "2099-01-01T00:00:00Z",
            }
        },
    )

    decision = _assert_refused_with_zero_effect(
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        expected_reason="envelope_provenance_caller_controlled",
    )

    assert decision.envelope_predicate_provenance == "recomputed"


def test_draft_scope_is_typed_by_audience_and_externality_and_cannot_widen() -> None:
    authority = _authority_module()
    internal_review = authority.DraftActionScope(
        audience="REVIEWER",
        externality="internal",
    )
    public_external = authority.DraftActionScope(
        audience="PUBLIC",
        externality="external",
    )
    contract = _contract(
        _envelope(
            action_kind="draft",
            operation_id="agent.draft",
            draft_scope=internal_review,
        )
    )
    operation = _operation("agent.draft")

    _assert_refused_with_zero_effect(
        contract=contract,
        operation=operation,
        invocation=_invocation(operation),
        intent=_intent("draft", draft_scope=public_external),
        expected_reason="draft_scope_out_of_envelope",
    )


def test_envelope_is_the_decisive_property_and_allow_is_recorded_before_effect() -> None:
    authority = _authority_module()
    envelope = _envelope()
    allowed_contract = _contract(envelope)
    records: list[object] = []
    observations: list[str] = []

    result = _dispatch(
        contract=allowed_contract,
        records=records,
        effect=lambda: observations.append(f"effect-after-{len(records)}-record") or "done",
    )

    assert result == "done"
    assert observations == ["effect-after-1-record"]
    assert len(records) == 1
    assert records[0].outcome == "allowed"
    assert all(check.satisfied for check in records[0].predicate_checks)

    stripped = allowed_contract.model_copy(update={"action_envelopes": ()})
    _assert_refused_with_zero_effect(
        contract=stripped,
        expected_reason="unknown_action_kind",
    )


def test_new_action_row_free_grows_without_action_kind_code_change() -> None:
    novel_kind = "counterfactual_probe_v17"
    operation = _operation("agent.counterfactual-probe")
    contract = _contract(
        _envelope(
            action_kind=novel_kind,
            operation_id=operation.operation_id,
            permission=RuntimePermission.ANALYSIS_EXECUTE,
        )
    )
    records: list[object] = []

    result = _dispatch(
        contract=contract,
        proof=_proof(RuntimePermission.ANALYSIS_EXECUTE),
        operation=operation,
        invocation=_invocation(operation),
        intent=_intent(novel_kind),
        records=records,
        effect=lambda: "novel-effect",
    )

    assert result == "novel-effect"
    assert records[0].action_kind == novel_kind
    assert records[0].outcome == "allowed"


def test_fake_novel_action_kind_fails_closed_with_zero_effect() -> None:
    _assert_refused_with_zero_effect(
        contract=_contract(_envelope()),
        intent=_intent("caller_invented_action"),
        expected_reason="unknown_action_kind",
    )


def test_an_allow_that_cannot_be_recorded_never_fires_effect() -> None:
    authority = _authority_module()
    effects: list[str] = []

    def broken_recorder(_decision: object) -> None:
        raise OSError("ledger unavailable")

    with pytest.raises(authority.AgentActionAuthorityRecordingError):
        authority.dispatch_agent_external_action(
            bound_permission=_proof(),
            operation=_operation(),
            invocation=_invocation(_operation()),
            intent=_intent(),
            resolve_delegation_contract=lambda _resource: _resolved(
                _contract(_envelope())
            ),
            resolve_human_decision=None,
            record_decision=broken_recorder,
            effect=lambda: effects.append("FIRED"),
            now=NOW,
            memory_claim_payload={},
            authority_input_payload={},
            tool_ledger=None,
        )

    assert effects == []
