from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.security.identity import PolicyOSRole
from polisyos.pdc import (
    AuthorityBoundary,
    OperationClass,
    OperationContract,
    OperationInvocationRecord,
)
from polisyos.runtime.http.authorization import (
    _BOUND_ACTION_PERMISSION_SEAL,
    ActionPermissionVerification,
    BoundActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    RouteAuthorizationRequirement,
)
from polisyos.runtime.http.mutation_policy import RuntimeIdempotencyStore
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import (
    BindingAuthority,
    BoundAuthorizationResource,
)
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
    LAYER2_S7_DELEGATION_SCHEMA_VERSION,
    DelegationContract,
    FiveRightsCheck,
    HumanDecisionRecord,
    HumanDecisionRequest,
    ResponsibilityIntegrityCheck,
    build_decision_rights_matrix,
    build_delegation_contract,
    build_governance_decision_class_registry,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.scientist.agent.tools.registry import ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition

NOW = datetime(2026, 8, 19, 12, tzinfo=UTC)
CASE_ID = "gy-pa2-case"
RULE_VERSION_REF = "policyos.gy.pa2.agent-action-authority.v1"
MANDATE_OWNER_REF = "principal://mandate-owner/gy-pa2"
ADMISSION_PRODUCER_IDENTITY = "service://runtime/agent-action-admission"
DIGEST = "sha256:" + "a" * 64


@pytest.fixture(autouse=True)
def _freeze_agent_action_live_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    authority = _authority_module()
    monkeypatch.setattr(authority, "_utcnow", lambda: NOW)


def _authority_module() -> Any:
    return importlib.import_module("polisyos.runtime.quality.agent_action_authority")


def _delegation_module() -> Any:
    return importlib.import_module(
        "polisyos.runtime.quality.design_axes.mandate_bounded_delegation"
    )


def _boundary(*, authoritative_for: str, source: str) -> AuthorityBoundary:
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
        _seal=_BOUND_ACTION_PERMISSION_SEAL,
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
    suffix: str = "base",
    parameters: dict[str, object] | None = None,
    tool_calls: list[str] | None = None,
) -> OperationInvocationRecord:
    return OperationInvocationRecord(
        invocation_id=f"invoke-{operation.operation_id.replace('.', '-')}-{suffix}",
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
        authority_boundary=_boundary(
            authoritative_for="agent_action_envelope",
            source="human_governance",
        ),
    )


def _legacy_contract() -> DelegationContract:
    registry = build_governance_decision_class_registry(CASE_ID, RULE_VERSION_REF)
    matrix = build_decision_rights_matrix(CASE_ID, registry, RULE_VERSION_REF)
    return build_delegation_contract(
        case_id=CASE_ID,
        matrix=matrix,
        governance_decision_classes=registry,
        s6_mandate_record_ref="pdc://gy-pa2/mandate",
        s6_mandate_firewall_disposition="pass",
        rule_version_ref=RULE_VERSION_REF,
    )


def _contract(*envelopes: object) -> DelegationContract:
    payload = _legacy_contract().model_dump(mode="json")
    payload.update(
        {
            "schema_version": LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            "mandate_owner_ref": MANDATE_OWNER_REF,
            "action_envelopes": [envelope.model_dump(mode="json") for envelope in envelopes],
        }
    )
    return DelegationContract.model_validate(payload)


@dataclass
class Harness:
    root: Path
    store: FileSystemCAS
    control_store: ControlPlaneStore
    event_log: RuntimeDiagnosticEventLog
    idempotency_store: RuntimeIdempotencyStore
    verifier: Ed25519Verifier
    owner_signer: Ed25519Signer
    admission_signer: Ed25519Signer


def _harness(tmp_path: Path) -> Harness:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=store,
    )
    owner_pair = KeyPair.generate()
    admission_pair = KeyPair.generate()
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(owner_pair.public_key, identity=MANDATE_OWNER_REF)
    verifier.add_trusted_key(
        admission_pair.public_key,
        identity=ADMISSION_PRODUCER_IDENTITY,
    )
    return Harness(
        root=tmp_path,
        store=store,
        control_store=control_store,
        event_log=event_log,
        idempotency_store=RuntimeIdempotencyStore(root=tmp_path / "idempotency"),
        verifier=verifier,
        owner_signer=Ed25519Signer(owner_pair.private_key),
        admission_signer=Ed25519Signer(admission_pair.private_key),
    )


def _write_context() -> object:
    authority = _authority_module()
    return authority.AgentActionAuthorityWriteContext(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-gy-pa2",
        job_id="job-gy-pa2",
        trace_id="trace-gy-pa2",
        span_id="span-gy-pa2",
        parent_span_id="span-parent",
        owner="team-runtime-quality",
        requested_execution_profile="governed",
        effective_execution_profile="governed",
        effective_mode_ref="sha256:" + "2" * 64,
        degradation_ledger_ref="sha256:" + "3" * 64,
    )


def _artifact_options(*, kind: str, schema_name: str, schema_version: str) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version=schema_version),
        producer=ProducerInfo(
            component="polisyos.runtime.quality.agent_action_test_owner",
            version="2026.08.19+gy-pa2-test",
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=[],
    )


def _persist_signed(
    harness: Harness,
    payload: object,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    signer: Ed25519Signer,
    signer_identity: str,
    sign: bool = True,
    canon_spec: CanonSpec | None = None,
) -> str:
    dumped = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    result = write_runtime_authority_artifact(
        harness.store,
        harness.event_log,
        dumped,
        _artifact_options(
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
        ),
        evidence_id=f"gy-pa2-{kind}",
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner=signer_identity,
        reader_contract="runtime_quality.agent_action_test.reader",
        reader_contract_version="1.0",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-gy-pa2",
        job_id="job-gy-pa2",
        trace_id="trace-gy-pa2",
        span_id="span-gy-pa2-source",
        parent_span_id="span-parent",
        requested_execution_profile="governed",
        effective_execution_profile="governed",
        phase="agent_action_authority_source",
        generated_at=NOW.isoformat(),
        as_of_time=NOW.isoformat(),
        same_input_closure={
            "closure_id": "closure-gy-pa2-source",
            "status": "closed",
            "run_id": "run-gy-pa2",
            "job_id": "job-gy-pa2",
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "evidence_input_refs": [],
            "closure_sha256": "1" * 64,
        },
        input_refs=[],
        effective_mode_ref="sha256:" + "2" * 64,
        degradation_ledger_ref="sha256:" + "3" * 64,
        validation_status="pass",
        blocking_status="non_blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime.agent_action_test_source",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="owner_signature_required",
        ),
        canon_spec=canon_spec or CanonSpec(),
    )
    if sign:
        harness.store.sign_artifact(
            result.cas_ref.artifact_id,
            signer,
            signer_identity=signer_identity,
        )
    return str(result.cas_ref.artifact_id)


def _binding(
    operation: OperationContract,
    effects: list[str],
    *,
    action_kind: str = "search",
    implementation_ref: str = "adapter://tests/search/v1",
    tool_name: str | None = None,
    handler: object | None = None,
) -> object:
    authority = _authority_module()
    callback = handler or (lambda _invocation: effects.append(action_kind) or action_kind)
    return authority.AgentActionEffectBinding(
        binding_id=f"binding.{action_kind}.{operation.operation_id}",
        action_kind=action_kind,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref=implementation_ref,
        handler=callback,
        tool_name=tool_name,
    )


def _admission_bundle(
    *,
    contract_ref: str,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: object,
    binding: object,
    bound_permission: object,
    memory_claim_payload: dict[str, object] | None = None,
    authority_input_payload: dict[str, object] | None = None,
    tool_ledger: object | None = None,
) -> object:
    authority = _authority_module()
    return authority.AgentActionAdmissionBundle(
        bundle_id=f"admission.{invocation.invocation_id}",
        bundle_ref=f"runtime://agent-action-admission/{invocation.invocation_id}",
        invocation_content_hash=authority.agent_action_content_hash(invocation),
        operation_content_hash=authority.agent_action_content_hash(operation),
        intent_content_hash=authority.agent_action_content_hash(intent),
        permission_proof_hash=authority.agent_action_permission_hash(bound_permission),
        bound_resource_digest=DIGEST,
        delegation_contract_ref=contract_ref,
        effect_binding_digest=binding.binding_digest,
        memory_claim_payload=memory_claim_payload or {},
        authority_input_payload=authority_input_payload or {},
        tool_ledger=tool_ledger,
        hypothesis_ledger=None,
        authority_boundary=_boundary(
            authoritative_for="agent_action_input_admission",
            source="deterministic_producer",
        ),
        rule_version_ref=RULE_VERSION_REF,
        admitted_at=NOW,
    )


def _prepare_gateway(
    harness: Harness,
    *,
    contract: DelegationContract,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: object,
    bindings: tuple[object, ...],
    binding_for_admission: object | None = None,
    memory_claim_payload: dict[str, object] | None = None,
    authority_input_payload: dict[str, object] | None = None,
    tool_ledger: object | None = None,
    include_admission: bool = True,
    contract_ref_override: str | None = None,
    contract_signer: Ed25519Signer | None = None,
    admission_signer: Ed25519Signer | None = None,
    human_decision_refs: dict[str, str] | None = None,
    human_decision_service: Any | None = None,
    human_decision_adapters: dict[str, Any] | None = None,
    production_approval_resolver: Any | None = None,
    bound_permission: object | None = None,
) -> tuple[object, str, str | None]:
    authority = _authority_module()
    owner_proof = bound_permission or _proof()
    contract_ref = contract_ref_override or _persist_signed(
        harness,
        contract,
        kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=contract_signer or harness.owner_signer,
        signer_identity=MANDATE_OWNER_REF,
    )
    admission_ref: str | None = None
    admission_mapping: dict[str, str] = {}
    if include_admission:
        selected_binding = binding_for_admission or next(
            binding
            for binding in bindings
            if binding.action_kind == intent.action_kind
            and binding.operation_id == operation.operation_id
            and binding.operation_version == operation.operation_version
        )
        bundle = _admission_bundle(
            contract_ref=contract_ref,
            operation=operation,
            invocation=invocation,
            intent=intent,
            binding=selected_binding,
            bound_permission=owner_proof,
            memory_claim_payload=memory_claim_payload,
            authority_input_payload=authority_input_payload,
            tool_ledger=tool_ledger,
        )
        admission_ref = _persist_signed(
            harness,
            bundle,
            kind=authority.AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
            schema_name="polisyos.runtime.AgentActionAdmissionBundle",
            schema_version=authority.AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
            signer=admission_signer or harness.admission_signer,
            signer_identity=ADMISSION_PRODUCER_IDENTITY,
        )
        admission_mapping[authority.agent_action_content_hash(invocation)] = admission_ref
    gateway = authority.AgentActionAuthorityGateway(
        artifact_store=harness.store,
        event_log=harness.event_log,
        idempotency_store=harness.idempotency_store,
        artifact_verifier=harness.verifier,
        bound_permission=owner_proof,
        admission_producer_identity=ADMISSION_PRODUCER_IDENTITY,
        write_context=_write_context(),
        contract_refs_by_resource_digest={DIGEST: contract_ref},
        admission_refs_by_invocation_hash=admission_mapping,
        effect_bindings=bindings,
        human_decision_refs_by_request_ref=human_decision_refs or {},
        human_decision_service=human_decision_service,
        human_decision_adapters_by_request_ref=human_decision_adapters or {},
        production_approval_resolver=production_approval_resolver,
    )
    return gateway, contract_ref, admission_ref


def _dispatch(
    *,
    gateway: object,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: object,
    proof: object | None = None,
    now: datetime = NOW,
) -> object:
    authority = _authority_module()
    del now  # Live dispatch time is owned by the producer, never by the caller.
    with authority.agent_action_authority_scope(gateway):
        return authority.dispatch_agent_external_action(
            bound_permission=proof or gateway.bound_permission,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )


def _produce(
    *,
    gateway: object,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: object,
) -> object:
    authority = _authority_module()
    with authority.agent_action_authority_scope(gateway):
        return authority.produce_agent_action_authority_decision(
            bound_permission=gateway.bound_permission,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )


def _assert_refused_with_zero_effect(
    harness: Harness,
    *,
    gateway: object,
    operation: OperationContract,
    invocation: OperationInvocationRecord,
    intent: object,
    effects: list[str],
    expected_reason: str,
    proof: object | None = None,
    now: datetime = NOW,
) -> object:
    authority = _authority_module()
    effect_count_before = len(effects)
    with pytest.raises(authority.AgentActionAuthorityRefused) as exc_info:
        _dispatch(
            gateway=gateway,
            proof=proof,
            operation=operation,
            invocation=invocation,
            intent=intent,
            now=now,
        )
    assert len(effects) == effect_count_before
    decision = exc_info.value.decision
    assert decision.outcome == "refused"
    assert expected_reason in decision.refusal_reasons
    assert decision.human_decision_request is not None
    assert decision.replay_input_refs
    receipt_ref = str(exc_info.value.persistence_receipt.cas_ref.artifact_id)
    assert harness.store.has(receipt_ref)
    report = reconcile_authority_ref(
        artifact_store=harness.store,
        event_log=harness.event_log,
        cas_ref=receipt_ref,
        expected_tenant_id="tenant-a",
        expected_cell_id="cell-a",
        expected_run_id="run-gy-pa2",
        expected_job_id="job-gy-pa2",
    )
    assert report.durable_event_id == exc_info.value.durable_event_id
    return decision


def _human_record(
    request: HumanDecisionRequest,
    *,
    actor_role: str = "mandate_owner",
    decided_at: datetime = NOW,
    all_rights: bool = True,
) -> HumanDecisionRecord:
    return HumanDecisionRecord(
        record_id=f"record.{request.request_id}",
        record_ref=f"pdc://gy-pa2/decision/{request.request_id}",
        case_id=CASE_ID,
        human_decision_request_ref=request.request_ref,
        actor_ref=MANDATE_OWNER_REF,
        actor_role=actor_role,
        decided_at=decided_at,
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
            right_time=all_rights,
        ),
        responsibility_integrity=ResponsibilityIntegrityCheck(
            status="pass",
            pattern_ids=["P26", "P05"],
            reason="All five rights passed for the exact invocation.",
            missing_requirements=[],
            rule_version_ref=RULE_VERSION_REF,
        ),
        authority_boundary=_boundary(
            authoritative_for="mandate_bounded_decision_record",
            source="human_governance",
        ),
        provenance_refs=[request.request_ref],
        rule_version_ref=RULE_VERSION_REF,
    )


def _persist_human_record(
    harness: Harness,
    record: HumanDecisionRecord,
    *,
    signed: bool = True,
) -> str:
    authority = _authority_module()
    return _persist_signed(
        harness,
        record,
        kind=authority.HUMAN_DECISION_ARTIFACT_KIND,
        schema_name="polisyos.runtime.HumanDecisionRecord",
        schema_version=LAYER2_S7_DELEGATION_SCHEMA_VERSION,
        signer=harness.owner_signer,
        signer_identity=MANDATE_OWNER_REF,
        sign=signed,
    )


def test_wrong_role_human_click_is_persisted_and_never_fires_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    contract = _contract(_envelope())
    operation = _operation("agent.outside-envelope")
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    base_gateway, _contract_ref, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    request = _produce(
        gateway=base_gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
    ).human_decision_request
    record_ref = _persist_human_record(
        harness,
        _human_record(request, actor_role="data_steward"),
    )
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        human_decision_refs={request.request_ref: record_ref},
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="human_decision_wrong_role",
    )


def test_human_decision_v1_replays_as_revalidation_required(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    contract = _contract(_envelope())
    operation = _operation("agent.outside-envelope")
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    base_gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    request = _produce(
        gateway=base_gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
    ).human_decision_request
    record_ref = _persist_human_record(harness, _human_record(request))
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        human_decision_refs={request.request_ref: record_ref},
    )
    decision = _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="DS9-DECISION-V1-REVALIDATION",
    )
    assert decision.human_decision_record_ref is None


def test_agent_gateway_rejects_cross_arm_fields() -> None:
    """PA2 and production adapter fields cannot coexist in one accepted DTO."""

    from pydantic import TypeAdapter, ValidationError

    contracts = importlib.import_module("polisyos.runtime.http.services.human_decision_contracts")
    common = {
        "tenant_id": "tenant-a",
        "run_id": "run-gy-pa2",
        "decision_request_ref": "runtime://human-decision/request/1",
        "decision_request_digest": "sha256:" + "1" * 64,
        "record_ref": "sha256:" + "2" * 64,
        "record_digest": "sha256:" + "2" * 64,
        "source_ref": "sha256:" + "3" * 64,
        "source_digest": "sha256:" + "3" * 64,
        "basis_digest": "sha256:" + "4" * 64,
        "record_schema_version": "policyos.runtime.human_decision_record.v2",
        "rule_version_ref": RULE_VERSION_REF,
        "verifier_epoch": "ds9-test-epoch",
        "valid_from": NOW - timedelta(minutes=1),
        "valid_until": NOW + timedelta(minutes=10),
        "expected_consumer": "polisyos.runtime.quality.agent_action_authority",
        "expected_operation": "agent.outside-envelope",
        "expected_audience": "polisyos-runtime",
    }
    pa2 = {
        **common,
        "source_kind": "agent_action_authority",
        "delegation_contract_ref": "sha256:" + "5" * 64,
        "delegation_contract_digest": "sha256:" + "5" * 64,
        "delegation_envelope_ref": "pdc://delegation/envelope/1",
        "delegation_envelope_digest": "sha256:" + "6" * 64,
    }
    adapter = TypeAdapter(contracts.HumanDecisionGatewayAdapterInput)
    assert adapter.validate_python(pa2).source_kind == "agent_action_authority"
    production = {
        **common,
        "source_kind": "production_approval",
        "production_packet_ref": "sha256:" + "7" * 64,
        "production_packet_digest": "sha256:" + "7" * 64,
    }
    assert adapter.validate_python(production).source_kind == "production_approval"

    with pytest.raises(ValidationError):
        adapter.validate_python({**pa2, "production_packet_ref": "sha256:" + "7" * 64})
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                **production,
                "delegation_contract_ref": "sha256:" + "5" * 64,
            }
        )


def test_agent_gateway_production_arm_requires_packet_ref_and_concrete_resolver(
    tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import resolve_production_approval_resolver
    from polisyos.runtime.quality.approval import ProductionApprovalCurrentnessProjection
    from tests.unit.runtime.http.test_runtime_deployment_security import (
        _config_mapping_with_human_decision_custody,
        _deployment_security_module,
    )

    harness = _harness(tmp_path / "gateway")
    operation = _operation("agent.outside-envelope")
    invocation = _invocation(operation)
    intent = _intent("search")
    effects: list[str] = []
    binding = _binding(operation, effects)
    contract = _contract(
        _envelope(
            valid_from=NOW - timedelta(minutes=5),
            valid_until=NOW + timedelta(hours=1),
        )
    )
    initial_gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    with patch.object(_authority_module(), "_utcnow", return_value=NOW):
        source = _produce(
            gateway=initial_gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    request = source.human_decision_request
    assert request is not None
    request_digest = _authority_module().agent_action_content_hash(request)
    contracts = importlib.import_module("polisyos.runtime.http.services.human_decision_contracts")
    adapter = contracts.HumanDecisionProductionGatewayAdapterInput(
        tenant_id="tenant-a",
        run_id="run-gy-pa2",
        source_kind="production_approval",
        decision_request_ref=request.request_ref,
        decision_request_digest=request_digest,
        record_ref="sha256:" + "2" * 64,
        record_digest="sha256:" + "2" * 64,
        source_ref="sha256:" + "3" * 64,
        source_digest="sha256:" + "3" * 64,
        basis_digest="sha256:" + "3" * 64,
        record_schema_version="policyos.runtime.human_decision_record.v2",
        rule_version_ref=RULE_VERSION_REF,
        verifier_epoch="ds9-test-epoch",
        valid_from=NOW - timedelta(minutes=1),
        valid_until=NOW + timedelta(minutes=10),
        expected_consumer="polisyos.runtime.quality.agent_action_authority",
        expected_operation=operation.operation_id,
        expected_audience="polisyos-runtime",
        production_packet_ref="sha256:" + "7" * 64,
        production_packet_digest="sha256:" + "7" * 64,
    )
    projection = ProductionApprovalCurrentnessProjection(
        status="current",
        packet_ref=adapter.production_packet_ref,
        checked_at=NOW,
        expected_consumer=adapter.expected_consumer,
        expected_audience=adapter.expected_audience,
    )
    for candidate in (None, object(), projection):
        with pytest.raises(TypeError, match="concrete approval resolver"):
            _prepare_gateway(
                harness,
                contract=contract,
                operation=operation,
                invocation=invocation,
                intent=intent,
                bindings=(binding,),
                human_decision_adapters={request.request_ref: adapter},
                production_approval_resolver=candidate,
            )

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(
            _config_mapping_with_human_decision_custody(tmp_path / "runtime")
        )
    )
    app = create_runtime_api_app(
        cas_root=tmp_path / "runtime-cas",
        deployment_security=runtime,
    )
    with TestClient(app) as client:
        resolver = resolve_production_approval_resolver(client.app)
        assert resolver is not None
        gateway, _, _ = _prepare_gateway(
            harness,
            contract=contract,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bindings=(binding,),
            human_decision_adapters={request.request_ref: adapter},
            production_approval_resolver=resolver,
        )
        _assert_refused_with_zero_effect(
            harness,
            gateway=gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
            effects=effects,
            expected_reason="DS9-DECISION-ARTIFACT-MISSING",
        )
    assert effects == []


def _prepared_v2_human_decision(
    tmp_path: Path,
    *,
    signed_source_permission_jwt_id: str | None = None,
) -> tuple[Any, Any, Any]:
    from tests.unit.runtime.http.test_human_decision_service import (
        _signed_current_gate_fixture,
    )

    contracts = importlib.import_module("polisyos.runtime.http.services.human_decision_contracts")
    fixture = _signed_current_gate_fixture(tmp_path)
    source = fixture.source_decision
    gate_input = fixture.adapter_input
    if signed_source_permission_jwt_id is not None:
        request = source.human_decision_request
        snapshot = source.permission_snapshot
        assert request is not None
        assert snapshot is not None
        source = source.model_copy(
            update={
                "permission_snapshot": snapshot.model_copy(
                    update={"jwt_id": signed_source_permission_jwt_id}
                )
            }
        )
        gate_input = gate_input.model_copy(
            update=fixture.resign_request_bundle(
                request,
                source_update={"permission_snapshot": source.permission_snapshot},
            )
        )
    receipt = fixture.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=gate_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement=("I accept accountability for this exact bounded action."),
            dissent_statement="Disconfirming evidence remains visible and retained.",
            override_reason=None,
            blocking_reason=None,
        ),
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )
    record = receipt.record
    envelope = next(
        row for row in fixture.contract.action_envelopes if row.envelope_id == source.envelope_id
    )
    adapter = contracts.HumanDecisionPA2GatewayAdapterInput(
        tenant_id=record.tenant_id,
        run_id=record.run_id,
        source_kind="agent_action_authority",
        decision_request_ref=record.human_decision_request_ref,
        decision_request_digest=record.decision_request_digest,
        record_ref=receipt.record_ref,
        record_digest=receipt.record_digest,
        source_ref=record.source_ref,
        source_digest=record.source_digest,
        basis_digest=record.basis_digest,
        record_schema_version=record.schema_version,
        rule_version_ref=record.rule_version_ref,
        verifier_epoch=record.verifier_epoch,
        valid_from=record.valid_from,
        valid_until=record.valid_until,
        expected_consumer="polisyos.runtime.quality.agent_action_authority",
        expected_operation=source.operation_id,
        expected_audience="polisyos-runtime",
        delegation_contract_ref=record.basis_ref,
        delegation_contract_digest=record.basis_digest,
        delegation_envelope_ref=envelope.envelope_ref,
        delegation_envelope_digest=_authority_module().agent_action_content_hash(envelope),
    )
    return fixture, receipt, adapter


def test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.runtime.http.test_human_decision_service import (
        _signed_current_gate_fixture,
    )

    contracts = importlib.import_module("polisyos.runtime.http.services.human_decision_contracts")
    fixture = _signed_current_gate_fixture(tmp_path)
    receipt = fixture.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=fixture.adapter_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement=("I accept accountability for this exact bounded action."),
            dissent_statement="Disconfirming evidence remains visible and retained.",
            override_reason=None,
            blocking_reason=None,
        ),
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )
    record = receipt.record
    source = fixture.source_decision
    envelope = next(
        row for row in fixture.contract.action_envelopes if row.envelope_id == source.envelope_id
    )
    adapter = contracts.HumanDecisionPA2GatewayAdapterInput(
        tenant_id=record.tenant_id,
        run_id=record.run_id,
        source_kind="agent_action_authority",
        decision_request_ref=record.human_decision_request_ref,
        decision_request_digest=record.decision_request_digest,
        record_ref=receipt.record_ref,
        record_digest=receipt.record_digest,
        source_ref=record.source_ref,
        source_digest=record.source_digest,
        basis_digest=record.basis_digest,
        record_schema_version=record.schema_version,
        rule_version_ref=record.rule_version_ref,
        verifier_epoch=record.verifier_epoch,
        valid_from=record.valid_from,
        valid_until=record.valid_until,
        expected_consumer="polisyos.runtime.quality.agent_action_authority",
        expected_operation=source.operation_id,
        expected_audience="polisyos-runtime",
        delegation_contract_ref=record.basis_ref,
        delegation_contract_digest=record.basis_digest,
        delegation_envelope_ref=envelope.envelope_ref,
        delegation_envelope_digest=_authority_module().agent_action_content_hash(envelope),
    )
    gateway, _, _ = _prepare_gateway(
        fixture.harness,
        contract=fixture.contract,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
        bindings=(fixture.binding,),
        contract_ref_override=record.basis_ref,
        human_decision_service=fixture.service,
        human_decision_adapters={record.human_decision_request_ref: adapter},
    )
    later = record.recorded_at + timedelta(seconds=1)
    monkeypatch.setattr(fixture.service, "_clock", lambda: later)
    monkeypatch.setattr(_authority_module(), "_utcnow", lambda: later)

    assert (
        _dispatch(
            gateway=gateway,
            operation=fixture.operation,
            invocation=fixture.invocation,
            intent=fixture.intent,
        )
        == "search"
    )
    assert fixture.effects == ["search"]


def test_agent_gateway_rejects_changed_admission_under_same_request_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A newly admitted packet cannot reuse an older human authorization."""

    fixture, receipt, adapter = _prepared_v2_human_decision(tmp_path)
    record = receipt.record
    monkeypatch.setattr(_authority_module(), "_utcnow", lambda: record.recorded_at)
    gateway, _, _ = _prepare_gateway(
        fixture.harness,
        contract=fixture.contract,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
        bindings=(fixture.binding,),
        contract_ref_override=record.basis_ref,
        authority_input_payload={"independently_admitted_note": "changed"},
        human_decision_service=fixture.service,
        human_decision_adapters={record.human_decision_request_ref: adapter},
    )

    _assert_refused_with_zero_effect(
        fixture.harness,
        gateway=gateway,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
        effects=fixture.effects,
        expected_reason="DS9-DECISION-SOURCE-INVALID",
    )
    assert fixture.effects == []


def test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh DS20 snapshot must equal the one in the signed refusal packet."""

    fixture, receipt, adapter = _prepared_v2_human_decision(
        tmp_path,
        signed_source_permission_jwt_id="jwt-before-operational-revalidation",
    )
    record = receipt.record
    monkeypatch.setattr(_authority_module(), "_utcnow", lambda: record.recorded_at)
    gateway, _, _ = _prepare_gateway(
        fixture.harness,
        contract=fixture.contract,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
        bindings=(fixture.binding,),
        contract_ref_override=record.basis_ref,
        human_decision_service=fixture.service,
        human_decision_adapters={record.human_decision_request_ref: adapter},
    )

    _assert_refused_with_zero_effect(
        fixture.harness,
        gateway=gateway,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
        effects=fixture.effects,
        expected_reason="DS9-DECISION-SOURCE-INVALID",
    )
    assert fixture.effects == []


def test_currentness_projection_round_trip_cannot_feed_operational_consumer(
    tmp_path: Path,
) -> None:
    from tests.unit.runtime.http.test_human_decision_service import (
        _signed_current_gate_fixture,
    )

    fixture = _signed_current_gate_fixture(tmp_path)
    projection = fixture.resolve()
    round_tripped = type(projection).model_validate(projection.model_dump(mode="json"))
    assert round_tripped.operational_authority is False

    with pytest.raises(TypeError, match="adapter mapping is not exact"):
        _prepare_gateway(
            fixture.harness,
            contract=fixture.contract,
            operation=fixture.operation,
            invocation=fixture.invocation,
            intent=fixture.intent,
            bindings=(fixture.binding,),
            human_decision_service=fixture.service,
            human_decision_adapters={
                round_tripped.decision_request_ref or "missing": round_tripped
            },
        )


def test_persisted_but_unsigned_human_record_never_fires_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    contract = _contract(_envelope())
    operation = _operation("agent.outside-envelope")
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    base_gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    request = _produce(
        gateway=base_gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
    ).human_decision_request
    record_ref = _persist_human_record(
        harness,
        _human_record(request),
        signed=False,
    )
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        human_decision_refs={request.request_ref: record_ref},
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="human_decision_authority_unverified",
    )


def test_failed_five_rights_record_is_persisted_and_never_fires_effect(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    contract = _contract(_envelope())
    operation = _operation("agent.outside-envelope")
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    base_gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    request = _produce(
        gateway=base_gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
    ).human_decision_request
    record_ref = _persist_human_record(
        harness,
        _human_record(request, all_rights=False),
    )
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        human_decision_refs={request.request_ref: record_ref},
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="human_decision_five_rights_failed",
    )


def test_click_after_envelope_ttl_is_persisted_and_never_fires_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    contract = _contract(
        _envelope(
            valid_from=NOW - timedelta(hours=2),
            valid_until=NOW - timedelta(seconds=1),
        )
    )
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="delegation_envelope_expired",
    )


def test_caller_clock_cannot_revive_an_expired_envelope(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    contract = _contract(
        _envelope(
            valid_from=NOW - timedelta(hours=3),
            valid_until=NOW - timedelta(hours=1),
        )
    )
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="delegation_envelope_expired",
        now=NOW - timedelta(hours=2),
    )


def test_envelope_expiring_after_decision_is_rechecked_before_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority_module()
    clock_values = iter((NOW - timedelta(hours=2), NOW))
    monkeypatch.setattr(authority, "_utcnow", lambda: next(clock_values))
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(
            _envelope(
                valid_from=NOW - timedelta(hours=3),
                valid_until=NOW - timedelta(hours=1),
            )
        ),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    with pytest.raises(
        authority.AgentActionAuthorityRecordingError,
        match="envelope is no longer live",
    ):
        _dispatch(
            gateway=gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    assert effects == []


def test_well_typed_caller_minted_ds20_proof_is_not_owner_bound(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    owner_proof = _proof(RuntimePermission.KNOWLEDGE_SEARCH)
    fabricated_proof = _proof(RuntimePermission.ANALYSIS_EXECUTE)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope(permission=RuntimePermission.ANALYSIS_EXECUTE)),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        bound_permission=owner_proof,
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="verified_identity_proof_not_owner_bound",
        proof=fabricated_proof,
    )


def test_search_authority_does_not_grant_data_request(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation("agent.data-request")
    invocation = _invocation(operation)
    intent = _intent("data_request")
    effects: list[str] = []
    binding = _binding(operation, effects, action_kind="data_request")
    contract = _contract(
        _envelope(
            action_kind="data_request",
            operation_id=operation.operation_id,
            permission=RuntimePermission.EVIDENCE_ACQUIRE,
        )
    )
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="explicit_permission_mismatch",
    )


@pytest.mark.parametrize(
    ("surface", "payload", "expected_reason"),
    [
        (
            "memory",
            {"data_refs": ["memory-influence:prior-policy-fact"]},
            "memory_not_admissible_as_policy_fact",
        ),
        (
            "input",
            {"selected_norm_refs": ["hypothesis-candidate:policy-fact"]},
            "input_candidate_not_admitted",
        ),
    ],
)
def test_signed_untrusted_memory_and_input_surfaces_never_fire_effect(
    tmp_path: Path,
    surface: str,
    payload: dict[str, object],
    expected_reason: str,
) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        memory_claim_payload=payload if surface == "memory" else None,
        authority_input_payload=payload if surface == "input" else None,
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason=expected_reason,
    )


def test_signed_policy_fact_ref_memory_payload_is_refused_before_effect(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        memory_claim_payload={
            "policy_fact_ref": "memory-influence:prior-policy-fact",
        },
    )

    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="memory_not_admissible_as_policy_fact",
    )


def test_runtime_invented_memory_key_is_refused_before_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    novel_key = f"runtime_invented_memory_position_{id(effects)}"
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        memory_claim_payload={
            novel_key: {"carrier": ["memory-influence:prior-policy-fact"]},
        },
    )

    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="memory_not_admissible_as_policy_fact",
    )


def test_unadmitted_tool_surface_never_fires_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation("agent.tool-call")
    invocation = _invocation(operation, tool_calls=["web.search"])
    intent = _intent("tool_call", tool_name="web.search")
    effects: list[str] = []
    binding = _binding(
        operation,
        effects,
        action_kind="tool_call",
        tool_name="web.search",
    )
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope(action_kind="tool_call", operation_id=operation.operation_id)),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        tool_ledger=None,
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="tool_admission_missing",
    )


def test_invocation_supplied_widened_envelope_names_provenance_and_never_fires(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(
        operation,
        parameters={"action_envelope": {"valid_until": "2099-01-01T00:00:00Z"}},
    )
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    decision = _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="envelope_provenance_caller_controlled",
    )
    assert decision.envelope_predicate_provenance == "recomputed"


def test_draft_audience_and_externality_cannot_widen(tmp_path: Path) -> None:
    authority = _authority_module()
    harness = _harness(tmp_path)
    operation = _operation("agent.draft")
    invocation = _invocation(operation)
    internal_review = authority.DraftActionScope(audience="REVIEWER", externality="internal")
    public_external = authority.DraftActionScope(audience="PUBLIC", externality="external")
    intent = _intent("draft", draft_scope=public_external)
    effects: list[str] = []
    binding = _binding(operation, effects, action_kind="draft")
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(
            _envelope(
                action_kind="draft",
                operation_id=operation.operation_id,
                draft_scope=internal_review,
            )
        ),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="draft_scope_out_of_envelope",
    )


def test_envelope_is_decisive_while_happy_path_remains_valid(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    effects: list[str] = []
    operation = _operation()
    intent = _intent()
    allowed_invocation = _invocation(operation, suffix="allowed")
    binding = _binding(operation, effects)
    allowed_gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=allowed_invocation,
        intent=intent,
        bindings=(binding,),
    )
    assert (
        _dispatch(
            gateway=allowed_gateway,
            operation=operation,
            invocation=allowed_invocation,
            intent=intent,
        )
        == "search"
    )
    assert effects == ["search"]

    stripped_invocation = _invocation(operation, suffix="stripped")
    stripped_gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(),
        operation=operation,
        invocation=stripped_invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=stripped_gateway,
        operation=operation,
        invocation=stripped_invocation,
        intent=intent,
        effects=effects,
        expected_reason="unknown_action_kind",
    )
    assert effects == ["search"]


def test_effect_rejects_allowed_model_with_unrelated_persisted_receipt(
    tmp_path: Path,
) -> None:
    authority = _authority_module()
    harness = _harness(tmp_path)
    effects: list[str] = []
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    allowed = _produce(
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
    )
    unrelated = allowed.model_copy(update={"decision_id": "decision.unrelated-receipt"})
    unrelated_persisted = gateway.persist_decision(unrelated)
    forged = authority.PersistedAgentActionDecision(
        decision=allowed,
        write_result=unrelated_persisted.write_result,
        durable_event_id=unrelated_persisted.durable_event_id,
    )

    with pytest.raises(
        authority.AgentActionAuthorityRecordingError,
        match="exact persisted decision",
    ):
        gateway.execute_bound_effect(
            operation=operation,
            invocation=invocation,
            intent=intent,
            persisted=forged,
        )

    assert effects == []


def test_new_action_row_and_binding_free_grow_without_action_kind_code_change(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    action_kind = "counterfactual_probe_v17"
    operation = _operation("agent.counterfactual-probe")
    invocation = _invocation(operation)
    intent = _intent(action_kind)
    proof = _proof(RuntimePermission.ANALYSIS_EXECUTE)
    effects: list[str] = []
    binding = _binding(operation, effects, action_kind=action_kind)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(
            _envelope(
                action_kind=action_kind,
                operation_id=operation.operation_id,
                permission=RuntimePermission.ANALYSIS_EXECUTE,
            )
        ),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        bound_permission=proof,
    )
    result = _dispatch(
        gateway=gateway,
        proof=proof,
        operation=operation,
        invocation=invocation,
        intent=intent,
    )
    assert result == action_kind
    assert effects == [action_kind]


def test_fake_novel_action_kind_fails_closed_with_zero_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent("caller_invented_action")
    effects: list[str] = []
    binding = _binding(operation, effects, action_kind="caller_invented_action")
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="unknown_action_kind",
    )


def test_caller_minted_contract_ref_cannot_reach_registered_tool_handler(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="external_search",
            description="External search transport witness.",
            parameters={"type": "object", "properties": {}},
        ),
        lambda: effects.append("FIRED"),
    )
    binding = _binding(
        operation,
        effects,
        handler=lambda _invocation: registry.execute("external_search", {}),
    )
    forged_ref = "sha256:" + "f" * 64
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        binding_for_admission=binding,
        contract_ref_override=forged_ref,
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="delegation_contract_authority_unverified",
    )


def test_missing_governed_admission_bundle_never_fires_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        include_admission=False,
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="governed_admission_bundle_missing",
    )


def test_search_decision_cannot_select_data_request_adapter(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    data_binding = _binding(operation, effects, action_kind="data_request")
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(data_binding,),
        binding_for_admission=data_binding,
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="effect_binding_missing",
    )


def test_human_approval_cannot_replay_after_invocation_content_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, receipt, adapter = _prepared_v2_human_decision(tmp_path)
    record = receipt.record
    monkeypatch.setattr(_authority_module(), "_utcnow", lambda: record.recorded_at)
    first_gateway, _, _ = _prepare_gateway(
        fixture.harness,
        contract=fixture.contract,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
        bindings=(fixture.binding,),
        contract_ref_override=record.basis_ref,
        human_decision_service=fixture.service,
        human_decision_adapters={record.human_decision_request_ref: adapter},
    )
    assert (
        _dispatch(
            gateway=first_gateway,
            operation=fixture.operation,
            invocation=fixture.invocation,
            intent=fixture.intent,
        )
        == "search"
    )
    assert fixture.effects == ["search"]

    changed_invocation = fixture.invocation.model_copy(update={"parameters": {"limit": 1_000_000}})
    changed_gateway, _, _ = _prepare_gateway(
        fixture.harness,
        contract=fixture.contract,
        operation=fixture.operation,
        invocation=changed_invocation,
        intent=fixture.intent,
        bindings=(fixture.binding,),
        contract_ref_override=record.basis_ref,
        human_decision_service=fixture.service,
        human_decision_adapters={record.human_decision_request_ref: adapter},
    )
    decision = _assert_refused_with_zero_effect(
        fixture.harness,
        gateway=changed_gateway,
        operation=fixture.operation,
        invocation=changed_invocation,
        intent=fixture.intent,
        effects=fixture.effects,
        expected_reason="operation_out_of_envelope",
    )
    assert decision.human_decision_record_ref is None
    assert decision.human_decision_request.request_ref != record.human_decision_request_ref
    assert fixture.effects == ["search"]


def test_malformed_inner_ds20_proof_is_persisted_as_refusal(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    valid = _proof()
    malformed_verification = ActionPermissionVerification(
        requirement=valid.verification.requirement,
        subject=valid.verification.subject,
        tenant_id=valid.verification.tenant_id,
        jwt_id=valid.verification.jwt_id,
        roles=frozenset({"analyst"}),  # type: ignore[arg-type]
        authorization_source=valid.verification.authorization_source,
        granted_permissions=valid.verification.granted_permissions,
    )
    malformed = BoundActionPermissionVerification(
        verification=malformed_verification,
        bound_resource=valid.bound_resource,
        _seal=_BOUND_ACTION_PERMISSION_SEAL,
    )
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        proof=malformed,
        expected_reason="verified_identity_proof_invalid",
    )


def test_decision_writer_failure_never_fires_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority_module()
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )

    def fail_write(*_args: object, **_kwargs: object) -> object:
        raise OSError("ledger unavailable")

    monkeypatch.setattr(authority, "write_runtime_authority_artifact", fail_write)
    with pytest.raises(authority.AgentActionAuthorityRecordingError):
        _dispatch(
            gateway=gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    assert effects == []


def test_receipt_for_different_bytes_never_fires_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority_module()
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    wrong_result = write_runtime_authority_artifact(
        harness.store,
        harness.event_log,
        {"different": "decision"},
        _artifact_options(
            kind=authority.AGENT_ACTION_DECISION_ARTIFACT_KIND,
            schema_name="polisyos.runtime.AgentActionAuthorityDecision",
            schema_version=authority.AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
        ),
        evidence_id="wrong-decision",
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner="team-runtime-quality",
        reader_contract="runtime_quality.agent_action_authority.reader",
        reader_contract_version="1.0",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-gy-pa2",
        job_id="job-gy-pa2",
        trace_id="trace-wrong",
        span_id="span-wrong",
        parent_span_id=None,
        requested_execution_profile="governed",
        effective_execution_profile="governed",
        phase="agent_action_authority",
        generated_at=NOW.isoformat(),
        as_of_time=NOW.isoformat(),
        same_input_closure={
            "closure_id": "closure-wrong",
            "status": "closed",
            "run_id": "run-gy-pa2",
            "job_id": "job-gy-pa2",
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "evidence_input_refs": [],
            "closure_sha256": "4" * 64,
        },
        input_refs=[],
        effective_mode_ref="sha256:" + "2" * 64,
        validation_status="pass",
        blocking_status="non_blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime.agent_action_dispatch",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="owner_required",
        ),
    )
    monkeypatch.setattr(
        authority,
        "write_runtime_authority_artifact",
        lambda *_args, **_kwargs: wrong_result,
    )
    with pytest.raises(authority.AgentActionAuthorityRecordingError):
        _dispatch(
            gateway=gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    assert effects == []


def test_allowed_invocation_is_single_use_across_gateway_reconstruction(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    effects: list[str] = []
    binding = _binding(operation, effects)
    gateway, contract_ref, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    assert (
        _dispatch(
            gateway=gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
        == "search"
    )
    rebuilt_gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        contract_ref_override=contract_ref,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    _assert_refused_with_zero_effect(
        harness,
        gateway=rebuilt_gateway,
        operation=operation,
        invocation=invocation,
        intent=intent,
        effects=effects,
        expected_reason="agent_action_invocation_already_consumed",
    )
    assert effects == ["search"]


def test_allowed_decision_is_durable_before_effect(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = _intent()
    observations: list[int] = []

    def observe_events(_invocation: OperationInvocationRecord) -> str:
        observations.append(len(harness.event_log.list_events(run_id="run-gy-pa2")))
        return "done"

    binding = _binding(operation, [], handler=observe_events)
    gateway, _, _ = _prepare_gateway(
        harness,
        contract=_contract(_envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    assert (
        _dispatch(
            gateway=gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
        == "done"
    )
    assert observations and observations[0] >= 3


@pytest.mark.parametrize(
    ("schema_version", "owner", "envelopes", "accepted"),
    [
        (LAYER2_S7_DELEGATION_SCHEMA_VERSION, None, [], True),
        (LAYER2_S7_DELEGATION_SCHEMA_VERSION, MANDATE_OWNER_REF, [_envelope()], False),
        (
            LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            MANDATE_OWNER_REF,
            [_envelope()],
            True,
        ),
        (LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION, None, [], False),
        ("policyos.policy_design_case.layer2_s7_delegation.v99", None, [], False),
    ],
)
def test_delegation_contract_schema_identity_is_symmetric(
    schema_version: str,
    owner: str | None,
    envelopes: list[object],
    accepted: bool,
) -> None:
    payload = _legacy_contract().model_dump(mode="json")
    payload["schema_version"] = schema_version
    if owner is not None:
        payload["mandate_owner_ref"] = owner
    if envelopes:
        payload["action_envelopes"] = [item.model_dump(mode="json") for item in envelopes]
    if accepted:
        DelegationContract.model_validate(payload)
    else:
        with pytest.raises(ValueError):
            DelegationContract.model_validate(payload)


def test_legacy_v1_serialization_and_hash_remain_stable() -> None:
    authority = _authority_module()
    legacy = _legacy_contract()
    payload = legacy.model_dump(mode="json")
    assert "mandate_owner_ref" not in payload
    assert "action_envelopes" not in payload
    assert authority.agent_action_content_hash(payload) == (
        "sha256:9b3628ad4efc5d85f9cf0c9e8adfc2e32062025a507323611459f3853fa38810"
    )
