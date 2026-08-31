"""Integration coverage for deterministic acquisition admission bundle production."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
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
from polisyos.runtime.http.routes.acquisitions import _MUTATION_AUTHZ
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionRouteMutationRequest,
    AcquisitionRouteReplayPins,
)
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionBundleBlocked,
    AcquisitionAdmissionBundleProducer,
    AcquisitionAdmissionSigningSlot,
)
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AGENT_ACTION_AUTHORITY_RULE_VERSION,
    DELEGATION_CONTRACT_ARTIFACT_KIND,
    AgentActionAuthorityGateway,
    AgentActionAuthorityRefused,
    AgentActionAuthorityWriteContext,
    AgentActionEffectBinding,
    AgentActionIntent,
    agent_action_authority_scope,
    agent_action_content_hash,
    agent_action_permission_hash,
    dispatch_agent_external_action,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
    DelegatedActionEnvelope,
    DelegationContract,
    build_decision_rights_matrix,
    build_delegation_contract,
    build_governance_decision_class_registry,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

NOW = datetime(2026, 8, 30, 12, tzinfo=UTC)
TENANT_ID = "tenant-acquisition"
CELL_ID = "cell-acquisition"
RUN_ID = "run-acquisition"
JOB_ID = "job-acquisition"
MANDATE_OWNER_REF = "principal://mandate-owner/acquisition"
MANDATE_AUTHORITY_IDENTITY = "service://institutional-mandate-registry"
ADMISSION_IDENTITY = "service://runtime/acquisition-admission"
ACQUISITION_ROUTE_REQUIREMENT = _MUTATION_AUTHZ.requirement
ACQUISITION_SELECTOR_FIELDS = ACQUISITION_ROUTE_REQUIREMENT.resource_binding.selector_fields
ACQUISITION_REQUIRED_SELECTOR_FIELDS = (
    ACQUISITION_ROUTE_REQUIREMENT.resource_binding.required_selector_fields
)
ACQUISITION_REQUEST = AcquisitionRouteMutationRequest(
    route_projection_hash="sha256:" + "d" * 64,
    planner_report_hash="sha256:" + "e" * 64,
    replay_pins=AcquisitionRouteReplayPins(
        source_job_id="source-job-acquisition",
        compiled_ref="sha256:" + "1" * 64,
        compiled_content_hash="sha256:" + "2" * 64,
        terminal_event_id="terminal-event-acquisition",
        design_problem_ref="sha256:" + "3" * 64,
        cost_basis_hash="sha256:" + "4" * 64,
    ),
    idempotency_key="idempotency-acquisition",
    human_decision_record_ref=None,
)


def _canonical_selector(value: object) -> str:
    """Independently canonicalize one DTO selector like the HTTP JSON contract."""

    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _request_composite_selectors(
    request: AcquisitionRouteMutationRequest,
    *,
    selector_fields: tuple[str, ...] = ACQUISITION_SELECTOR_FIELDS,
) -> tuple[tuple[str, str], ...]:
    """Derive frozen selectors from the production mutation DTO body."""

    body = request.model_dump(mode="json")
    return tuple(
        sorted(
            (
                field,
                '{"present":false}' if body[field] is None else _canonical_selector(body[field]),
            )
            for field in selector_fields
        )
    )


REQUEST_BODY_BYTES = ACQUISITION_REQUEST.model_dump_json().encode("utf-8")
REQUEST_BODY_SHA256 = f"sha256:{sha256(REQUEST_BODY_BYTES).hexdigest()}"
EMPTY_QUERY_SHA256 = f"sha256:{sha256(b'').hexdigest()}"
ACQUISITION_SELECTORS = _request_composite_selectors(ACQUISITION_REQUEST)


def _independent_resource_digest(selectors: tuple[tuple[str, str], ...]) -> str:
    """Return the hand-checked route binding digest without producer helpers."""

    payload = {
        "binding_version": "runtime.authorization.resource.v1",
        "permission": RuntimePermission.EVIDENCE_ACQUIRE.value,
        "resource_kind": "runtime.evidence.acquisition",
        "authority": BindingAuthority.REQUEST_BOUND.value,
        "tenant_id": None,
        "body_sha256": REQUEST_BODY_SHA256,
        "query_sha256": EMPTY_QUERY_SHA256,
        "selectors": selectors,
        "resolved_context_sha256": None,
    }
    return f"sha256:{sha256(_canonical_selector(payload).encode('utf-8')).hexdigest()}"


RESOURCE_DIGEST = "sha256:9474372986dd62a9d754a235da9be00dcc68c344ce7935bf6f8a6a05fb8e77c0"


def _boundary(*, authoritative_for: str, source: str) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=[authoritative_for],
        may_not_use_for=["claim_evidence", "publication_authority", "promotion_authority"],
        source_authority=source,
        posture="governed",
        rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
    )


def _operation() -> OperationContract:
    return OperationContract(
        operation_id=ACQUISITION_ACTION_KIND,
        operation_version="v1",
        operation_class=OperationClass.DISCOVER,
        consumes=[],
        produces=[],
        formal_preconditions=[],
        allowed_internal_execution=["tool_call"],
        implementation_refs=[{"module": "tests.acquisition", "symbol": "effect"}],
        cost_model={"kind": "bounded"},
        authority_transform={"kind": "preserves"},
        failure_modes=["authority_refused"],
        repair_options=[OperationClass.ESCALATE],
    )


def _invocation(operation: OperationContract) -> OperationInvocationRecord:
    return OperationInvocationRecord(
        invocation_id="invoke-acquisition",
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        workspace_id="case-acquisition",
        cycle_index=1,
        selected_by={"producer": "integration-test"},
        selection_rationale_ref="cas://selection/acquisition",
        input_artifacts=[],
        parameters={},
        internal_trace={"phase": "pre-action"},
        tool_calls=[],
        human_requests=[],
        output_artifacts=[],
        applicability_result="applicable",
        budget_delta={"actions": 1},
        status="started",
    )


def _proof(
    *,
    resource_digest: str = RESOURCE_DIGEST,
    requirement: RouteAuthorizationRequirement = ACQUISITION_ROUTE_REQUIREMENT,
    canonical_selectors: tuple[tuple[str, str], ...] = ACQUISITION_SELECTORS,
) -> BoundActionPermissionVerification:
    verification = ActionPermissionVerification(
        requirement=requirement,
        subject="user:acquisition-operator",
        tenant_id=TENANT_ID,
        jwt_id="jwt-acquisition",
        roles=frozenset({PolicyOSRole.ANALYST}),
        authorization_source="runtime.jwt+opa",
        granted_permissions=(RuntimePermission.EVIDENCE_ACQUIRE,),
    )
    resource = BoundAuthorizationResource(
        requirement=requirement,
        tenant_id=None,
        resource_kind="runtime.evidence.acquisition.request_bound",
        resource_id=f"urn:polisyos:runtime-authorization-resource:v1:{resource_digest}",
        resource_digest=resource_digest,
        authority=BindingAuthority.REQUEST_BOUND,
        body_sha256=REQUEST_BODY_SHA256,
        query_sha256=EMPTY_QUERY_SHA256,
        canonical_selectors=canonical_selectors,
    )
    return BoundActionPermissionVerification(
        verification=verification,
        bound_resource=resource,
        _seal=_BOUND_ACTION_PERMISSION_SEAL,
    )


def _contract() -> DelegationContract:
    registry = build_governance_decision_class_registry(
        "case-acquisition", AGENT_ACTION_AUTHORITY_RULE_VERSION
    )
    matrix = build_decision_rights_matrix(
        "case-acquisition", registry, AGENT_ACTION_AUTHORITY_RULE_VERSION
    )
    legacy = build_delegation_contract(
        case_id="case-acquisition",
        matrix=matrix,
        governance_decision_classes=registry,
        s6_mandate_record_ref="pdc://acquisition/mandate",
        s6_mandate_firewall_disposition="pass",
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
    ).model_dump(mode="json")
    envelope = DelegatedActionEnvelope(
        envelope_id="envelope-acquisition",
        envelope_ref="pdc://acquisition/envelope",
        case_id="case-acquisition",
        mandate_owner_ref=MANDATE_OWNER_REF,
        owner_role="mandate_owner",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=ACQUISITION_ACTION_KIND,
        operation_version="v1",
        required_permission=RuntimePermission.EVIDENCE_ACQUIRE,
        authorized_subject="user:acquisition-operator",
        authorized_runtime_roles=(PolicyOSRole.ANALYST,),
        required_tenant_id=TENANT_ID,
        required_resource_digest=RESOURCE_DIGEST,
        valid_from=NOW - timedelta(minutes=5),
        valid_until=NOW + timedelta(hours=1),
        status="active",
        issuance_decision_ref="pdc://acquisition/issuance",
        provenance_refs=("pdc://acquisition/mandate-owner",),
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
        authority_boundary=_boundary(
            authoritative_for="agent_action_envelope", source="human_governance"
        ),
    )
    legacy.update(
        {
            "schema_version": LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            "mandate_owner_ref": MANDATE_OWNER_REF,
            "action_envelopes": [envelope.model_dump(mode="json")],
        }
    )
    return DelegationContract.model_validate(legacy)


def _write_context() -> AgentActionAuthorityWriteContext:
    return AgentActionAuthorityWriteContext(
        tenant_id=TENANT_ID,
        cell_id=CELL_ID,
        run_id=RUN_ID,
        job_id=JOB_ID,
        trace_id="trace-acquisition",
        span_id="span-acquisition",
        parent_span_id="span-parent",
        owner="team-runtime-acquisition",
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
            component="polisyos.runtime.acquisition_admission_bundle_test",
            version="2026.08.30+integration-test",
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=[],
    )


def _persist_signed(
    *,
    store: FileSystemCAS,
    event_log: RuntimeDiagnosticEventLog,
    payload: object,
    kind: str,
    schema_name: str,
    schema_version: str,
    signer: Ed25519Signer,
    signer_identity: str,
) -> str:
    result = write_runtime_authority_artifact(
        store,
        event_log,
        payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload,
        _artifact_options(kind=kind, schema_name=schema_name, schema_version=schema_version),
        evidence_id=f"acquisition-{kind}",
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner=signer_identity,
        reader_contract="runtime.acquisition_admission_bundle.reader",
        reader_contract_version="1.0",
        tenant_id=TENANT_ID,
        cell_id=CELL_ID,
        run_id=RUN_ID,
        job_id=JOB_ID,
        trace_id="trace-acquisition",
        span_id="span-acquisition-source",
        parent_span_id="span-parent",
        requested_execution_profile="governed",
        effective_execution_profile="governed",
        phase="acquisition_admission_source",
        generated_at=NOW.isoformat(),
        as_of_time=NOW.isoformat(),
        same_input_closure={
            "closure_id": "closure-acquisition-source",
            "status": "closed",
            "run_id": RUN_ID,
            "job_id": JOB_ID,
            "tenant_id": TENANT_ID,
            "cell_id": CELL_ID,
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
            authority_boundary="runtime.acquisition_admission_test",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="owner_signature_required",
        ),
    )
    store.sign_artifact(result.cas_ref.artifact_id, signer, signer_identity=signer_identity)
    return str(result.cas_ref.artifact_id)


def _harness(tmp_path: Path) -> tuple[FileSystemCAS, RuntimeDiagnosticEventLog, RuntimeIdempotencyStore]:
    store = FileSystemCAS(tmp_path / "cas").for_tenant(TENANT_ID, cell_id=CELL_ID)
    control_store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    return (
        store,
        RuntimeDiagnosticEventLog(store=control_store, artifact_store=store),
        RuntimeIdempotencyStore(root=tmp_path / "idempotency"),
    )


def _gateway(
    *,
    store: FileSystemCAS,
    event_log: RuntimeDiagnosticEventLog,
    idempotency_store: RuntimeIdempotencyStore,
    verifier: Ed25519Verifier,
    contract_ref: str | None,
    admission_mapping: Mapping[str, str],
    binding: AgentActionEffectBinding,
) -> AgentActionAuthorityGateway:
    return AgentActionAuthorityGateway(
        artifact_store=store,
        event_log=event_log,
        idempotency_store=idempotency_store,
        artifact_verifier=verifier,
        bound_permission=_proof(),
        admission_producer_identity=ADMISSION_IDENTITY,
        write_context=_write_context(),
        contract_refs_by_resource_digest=(
            {} if contract_ref is None else {RESOURCE_DIGEST: contract_ref}
        ),
        mandate_authority_evidence_refs_by_owner_ref={},
        admission_refs_by_invocation_hash=admission_mapping,
        effect_bindings=(binding,),
    )


def test_empty_signer_slot_blocks_before_authority_artifact_write(tmp_path: Path) -> None:
    store, event_log, _ = _harness(tmp_path)
    operation = _operation()
    invocation = _invocation(operation)
    intent = AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND)
    binding = AgentActionEffectBinding(
        binding_id="acquisition-effect",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref="adapter://acquisition/v1",
        handler=lambda _invocation: "must-not-run",
    )
    before_events = event_log.list_events(limit=10)
    producer = AcquisitionAdmissionBundleProducer(
        artifact_store=store,
        event_log=event_log,
        signing_slot=AcquisitionAdmissionSigningSlot.empty(),
        write_context=_write_context(),
    )

    with pytest.raises(AcquisitionAdmissionBundleBlocked) as exc_info:
        producer.admit(
            delegation_contract_ref="sha256:" + "d" * 64,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bound_permission=_proof(),
            effect_binding=binding,
            admitted_at=NOW,
        )

    assert exc_info.value.code == "acquisition_admission_signer_unconfigured"
    assert event_log.list_events(limit=10) == before_events


def test_non_acquisition_tuple_is_rejected_before_authority_artifact_write(tmp_path: Path) -> None:
    store, event_log, _ = _harness(tmp_path)
    pair = KeyPair.generate()
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(pair.public_key, identity=ADMISSION_IDENTITY)
    operation = _operation()
    invocation = _invocation(operation)
    intent = AgentActionIntent(action_kind="search")
    binding = AgentActionEffectBinding(
        binding_id="search-effect",
        action_kind="search",
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref="adapter://search/v1",
        handler=lambda _invocation: "must-not-run",
    )
    before_events = event_log.list_events(limit=10)
    producer = AcquisitionAdmissionBundleProducer(
        artifact_store=store,
        event_log=event_log,
        signing_slot=AcquisitionAdmissionSigningSlot.configured(
            signer=Ed25519Signer(pair.private_key),
            verifier=verifier,
            signer_identity=ADMISSION_IDENTITY,
        ),
        write_context=_write_context(),
    )

    with pytest.raises(AcquisitionAdmissionBundleBlocked) as exc_info:
        producer.admit(
            delegation_contract_ref="sha256:" + "d" * 64,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bound_permission=_proof(),
            effect_binding=binding,
            admitted_at=NOW,
        )

    assert exc_info.value.code == "acquisition_action_tuple_invalid"
    assert event_log.list_events(limit=10) == before_events


def test_mismatched_resource_digest_is_rejected_before_authority_artifact_write(
    tmp_path: Path,
) -> None:
    store, event_log, _ = _harness(tmp_path)
    owner_pair = KeyPair.generate()
    admission_pair = KeyPair.generate()
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(owner_pair.public_key, identity=MANDATE_OWNER_REF)
    verifier.add_trusted_key(admission_pair.public_key, identity=ADMISSION_IDENTITY)
    contract_ref = _persist_signed(
        store=store,
        event_log=event_log,
        payload=_contract(),
        kind=DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=Ed25519Signer(owner_pair.private_key),
        signer_identity=MANDATE_OWNER_REF,
    )
    operation = _operation()
    invocation = _invocation(operation)
    intent = AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND)
    binding = AgentActionEffectBinding(
        binding_id="acquisition-effect",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref="adapter://acquisition/v1",
        handler=lambda _invocation: "must-not-run",
    )
    producer = AcquisitionAdmissionBundleProducer(
        artifact_store=store,
        event_log=event_log,
        signing_slot=AcquisitionAdmissionSigningSlot.configured(
            signer=Ed25519Signer(admission_pair.private_key),
            verifier=verifier,
            signer_identity=ADMISSION_IDENTITY,
        ),
        write_context=_write_context(),
    )
    before_events = event_log.list_events(limit=10)

    with pytest.raises(AcquisitionAdmissionBundleBlocked) as exc_info:
        producer.admit(
            delegation_contract_ref=contract_ref,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bound_permission=_proof(resource_digest="sha256:" + "a" * 64),
            effect_binding=binding,
            admitted_at=NOW,
        )

    assert exc_info.value.code == "acquisition_resource_digest_mismatch"
    assert event_log.list_events(limit=10) == before_events


def test_incomplete_request_composite_denominator_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    store, event_log, _ = _harness(tmp_path)
    owner_pair = KeyPair.generate()
    admission_pair = KeyPair.generate()
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(owner_pair.public_key, identity=MANDATE_OWNER_REF)
    verifier.add_trusted_key(admission_pair.public_key, identity=ADMISSION_IDENTITY)
    contract_ref = _persist_signed(
        store=store,
        event_log=event_log,
        payload=_contract(),
        kind=DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=Ed25519Signer(owner_pair.private_key),
        signer_identity=MANDATE_OWNER_REF,
    )
    operation = _operation()
    invocation = _invocation(operation)
    intent = AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND)
    binding = AgentActionEffectBinding(
        binding_id="acquisition-effect",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref="adapter://acquisition/v1",
        handler=lambda _invocation: "must-not-run",
    )
    producer = AcquisitionAdmissionBundleProducer(
        artifact_store=store,
        event_log=event_log,
        signing_slot=AcquisitionAdmissionSigningSlot.configured(
            signer=Ed25519Signer(admission_pair.private_key),
            verifier=verifier,
            signer_identity=ADMISSION_IDENTITY,
        ),
        write_context=_write_context(),
    )
    incomplete_selector_fields = ACQUISITION_SELECTOR_FIELDS[:-1]
    incomplete_selectors = _request_composite_selectors(
        ACQUISITION_REQUEST,
        selector_fields=incomplete_selector_fields,
    )
    incomplete_requirement = RouteAuthorizationRequirement(
        permission=RuntimePermission.EVIDENCE_ACQUIRE,
        resource_binding=ResourceBindingSpec(
            source=ResourceBindingSource.REQUEST_COMPOSITE,
            resource_kind="runtime.evidence.acquisition",
            selector_fields=incomplete_selector_fields,
            required_selector_fields=ACQUISITION_REQUIRED_SELECTOR_FIELDS,
        ),
    )
    before_events = event_log.list_events(limit=10)

    with pytest.raises(AcquisitionAdmissionBundleBlocked) as exc_info:
        producer.admit(
            delegation_contract_ref=contract_ref,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bound_permission=_proof(
                resource_digest=_independent_resource_digest(incomplete_selectors),
                requirement=incomplete_requirement,
                canonical_selectors=incomplete_selectors,
            ),
            effect_binding=binding,
            admitted_at=NOW,
        )

    assert exc_info.value.code == "acquisition_resource_binding_invalid"
    assert event_log.list_events(limit=10) == before_events


def test_ephemeral_signer_produces_reconciled_bundle_for_gateway(tmp_path: Path) -> None:
    store, event_log, idempotency_store = _harness(tmp_path)
    owner_pair = KeyPair.generate()
    admission_pair = KeyPair.generate()
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(owner_pair.public_key, identity=MANDATE_OWNER_REF)
    verifier.add_trusted_key(admission_pair.public_key, identity=ADMISSION_IDENTITY)
    contract_ref = _persist_signed(
        store=store,
        event_log=event_log,
        payload=_contract(),
        kind=DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=Ed25519Signer(owner_pair.private_key),
        signer_identity=MANDATE_OWNER_REF,
    )
    operation = _operation()
    invocation = _invocation(operation)
    intent = AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND)
    effects: list[str] = []
    binding = AgentActionEffectBinding(
        binding_id="acquisition-effect",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref="adapter://acquisition/v1",
        handler=lambda _invocation: effects.append("fired"),
    )
    producer = AcquisitionAdmissionBundleProducer(
        artifact_store=store,
        event_log=event_log,
        signing_slot=AcquisitionAdmissionSigningSlot.configured(
            signer=Ed25519Signer(admission_pair.private_key),
            verifier=verifier,
            signer_identity=ADMISSION_IDENTITY,
        ),
        write_context=_write_context(),
    )

    receipt = producer.admit(
        delegation_contract_ref=contract_ref,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bound_permission=_proof(),
        effect_binding=binding,
        admitted_at=NOW,
    )

    invocation_hash = agent_action_content_hash(invocation)
    assert ACQUISITION_REQUEST.human_decision_record_ref is None
    assert tuple(AcquisitionRouteMutationRequest.model_fields) == ACQUISITION_SELECTOR_FIELDS
    assert tuple(
        field_name
        for field_name, field in AcquisitionRouteMutationRequest.model_fields.items()
        if field.is_required()
    ) == ACQUISITION_REQUIRED_SELECTOR_FIELDS
    assert (
        ("human_decision_record_ref", '{"present":false}'),
        ("idempotency_key", '"idempotency-acquisition"'),
        ("planner_report_hash", '"sha256:' + "e" * 64 + '"'),
        (
            "replay_pins",
            _canonical_selector(ACQUISITION_REQUEST.replay_pins.model_dump(mode="json")),
        ),
        ("route_projection_hash", '"sha256:' + "d" * 64 + '"'),
    ) == ACQUISITION_SELECTORS
    assert _independent_resource_digest(ACQUISITION_SELECTORS) == RESOURCE_DIGEST
    assert _proof().bound_resource.resource_digest == RESOURCE_DIGEST
    assert receipt.invocation_refs == {invocation_hash: receipt.artifact_ref}
    with pytest.raises(TypeError):
        receipt.invocation_refs[invocation_hash] = "sha256:" + "f" * 64
    assert receipt.bundle.invocation_content_hash == invocation_hash
    assert receipt.bundle.operation_content_hash == agent_action_content_hash(operation)
    assert receipt.bundle.intent_content_hash == agent_action_content_hash(intent)
    assert receipt.bundle.permission_proof_hash == agent_action_permission_hash(_proof())
    assert receipt.bundle.bound_resource_digest == RESOURCE_DIGEST
    assert receipt.bundle.effect_binding_digest == binding.binding_digest
    report = reconcile_authority_ref(
        artifact_store=store,
        event_log=event_log,
        cas_ref=receipt.artifact_ref,
        expected_tenant_id=TENANT_ID,
        expected_cell_id=CELL_ID,
        expected_run_id=RUN_ID,
        expected_job_id=JOB_ID,
    )
    assert report.status == "pass"
    assert receipt.payload_sha256 == f"sha256:{receipt.artifact_ref.removeprefix('sha256:')}"
    gateway_without_contract = _gateway(
        store=store,
        event_log=event_log,
        idempotency_store=RuntimeIdempotencyStore(root=tmp_path / "idempotency-without-contract"),
        verifier=verifier,
        contract_ref=None,
        admission_mapping=receipt.invocation_refs,
        binding=binding,
    )
    assert gateway_without_contract.resolve_admission_bundle(invocation_hash) == (
        receipt.bundle,
        receipt.artifact_ref,
    )
    with agent_action_authority_scope(gateway_without_contract), pytest.raises(
        AgentActionAuthorityRefused
    ) as no_contract_exc_info:
        dispatch_agent_external_action(
            bound_permission=gateway_without_contract.bound_permission,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    assert "delegation_contract_not_persisted" in no_contract_exc_info.value.decision.refusal_reasons
    assert effects == []
    assert gateway_without_contract.resolve_admission_bundle(invocation_hash) == (
        receipt.bundle,
        receipt.artifact_ref,
    )
    gateway = _gateway(
        store=store,
        event_log=event_log,
        idempotency_store=idempotency_store,
        verifier=verifier,
        contract_ref=contract_ref,
        admission_mapping=receipt.invocation_refs,
        binding=binding,
    )

    resolved, resolved_ref = gateway.resolve_admission_bundle(invocation_hash)

    assert resolved_ref == receipt.artifact_ref
    assert resolved == receipt.bundle
    with agent_action_authority_scope(gateway), pytest.raises(AgentActionAuthorityRefused) as exc_info:
        dispatch_agent_external_action(
            bound_permission=gateway.bound_permission,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    assert "current_mandate_authority_not_established" in exc_info.value.decision.refusal_reasons
    assert effects == []
    assert gateway.resolve_admission_bundle(invocation_hash) == (receipt.bundle, receipt.artifact_ref)


def test_untrusted_signed_bundle_is_refused_without_effect(tmp_path: Path) -> None:
    store, event_log, _ = _harness(tmp_path)
    owner_pair = KeyPair.generate()
    trusted_admission_pair = KeyPair.generate()
    untrusted_admission_pair = KeyPair.generate()
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(owner_pair.public_key, identity=MANDATE_OWNER_REF)
    verifier.add_trusted_key(trusted_admission_pair.public_key, identity=ADMISSION_IDENTITY)
    contract_ref = _persist_signed(
        store=store,
        event_log=event_log,
        payload=_contract(),
        kind=DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=Ed25519Signer(owner_pair.private_key),
        signer_identity=MANDATE_OWNER_REF,
    )
    operation = _operation()
    invocation = _invocation(operation)
    intent = AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND)
    effects: list[str] = []
    binding = AgentActionEffectBinding(
        binding_id="acquisition-effect",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref="adapter://acquisition/v1",
        handler=lambda _invocation: effects.append("fired"),
    )
    producer = AcquisitionAdmissionBundleProducer(
        artifact_store=store,
        event_log=event_log,
        signing_slot=AcquisitionAdmissionSigningSlot.configured(
            signer=Ed25519Signer(untrusted_admission_pair.private_key),
            verifier=verifier,
            signer_identity=ADMISSION_IDENTITY,
        ),
        write_context=_write_context(),
    )
    with pytest.raises(AcquisitionAdmissionBundleBlocked) as exc_info:
        producer.admit(
            delegation_contract_ref=contract_ref,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bound_permission=_proof(),
            effect_binding=binding,
            admitted_at=NOW,
        )

    assert exc_info.value.code == "acquisition_admission_signer_untrusted"
    assert effects == []
