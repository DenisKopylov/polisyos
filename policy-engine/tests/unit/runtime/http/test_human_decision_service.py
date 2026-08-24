"""Red-first semantic witnesses for the DS9 human-decision service."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import combinations, permutations
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.signing import Ed25519Signer, KeyPair
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.runtime.http.access_audit import RuntimeDataAccessAuditTrail
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent

NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)


def _contracts():
    return importlib.import_module("polisyos.runtime.http.services.human_decision_contracts")


def _service_module():
    return importlib.import_module("polisyos.runtime.http.services.human_decisions")


@dataclass(frozen=True)
class _SignedGateFixture:
    service: Any
    adapter_input: Any
    bound_permission: Any
    store: Any
    principal_payload: dict[str, object]
    source_decision: Any
    sign_principal: Callable[[dict[str, object]], str]
    sign_separation: Callable[[dict[str, object]], str]
    resign_request_bundle: Callable[..., dict[str, str]]
    persist_contract: Callable[[Any, bool], str]
    service_with_audit: Callable[[Path], Any]
    empty_audit_path: Path
    custody_identity: str
    custody_key_id: str
    write_context: Any
    harness: Any
    contract: Any
    operation: Any
    invocation: Any
    intent: Any
    binding: Any
    effects: list[str]
    separation_payload: dict[str, object]

    def resolve(self, **changes: object) -> Any:
        return self.service.resolve_gate(
            self.adapter_input.model_copy(update=changes),
            bound_permission=self.bound_permission,
        )


def _human_decision_record_ids(store: Any) -> set[str]:
    return {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime_quality.agent_action_human_decision"
    }


def _reason_codes(gate: Any) -> set[str]:
    return {reason.code for reason in gate.reasons}


def _persist_unsigned_gate_model(
    fixture: _SignedGateFixture,
    payload: Any,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
) -> str:
    from tests.unit.runtime.quality.test_agent_action_authority import _persist_signed

    return _persist_signed(
        fixture.harness,
        payload,
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        signer=fixture.harness.owner_signer,
        signer_identity="fixture://unsigned",
        sign=False,
    )


def _signed_current_gate_fixture(tmp_path: Path) -> _SignedGateFixture:
    contracts = _contracts()
    services = _service_module()
    authority = importlib.import_module("polisyos.runtime.quality.agent_action_authority")
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification,
        BoundActionPermissionVerification,
        ResourceBindingSource,
        ResourceBindingSpec,
        RouteAuthorizationRequirement,
    )
    from polisyos.runtime.http.deployment_security import (
        DeploymentHumanDecisionCustody,
        VerifierProvenance,
    )
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.resource_binding import (
        BindingAuthority,
        BoundAuthorizationResource,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        HumanDecisionAuthoritySink,
    )
    from tests.unit.runtime.quality.test_agent_action_authority import (
        ADMISSION_PRODUCER_IDENTITY,
        MANDATE_OWNER_REF,
        RULE_VERSION_REF,
        _binding,
        _boundary,
        _contract,
        _envelope,
        _harness,
        _intent,
        _invocation,
        _operation,
        _persist_signed,
        _prepare_gateway,
        _produce,
        _write_context,
    )

    harness = _harness(tmp_path)
    producer_pairs = {
        "source": KeyPair.generate(),
        "principal": KeyPair.generate(),
        "separation": KeyPair.generate(),
        "presentation": KeyPair.generate(),
        "custody": KeyPair.generate(),
    }
    producer_identities = {
        "source": "service://runtime/agent-action-authority",
        "principal": "institution://identity/principal-binding",
        "separation": "institution://governance/reviewer-separation",
        "presentation": "institution://governance/presentation-policy",
        "custody": "service://runtime/human-decision-custody",
    }
    signers = {name: Ed25519Signer(pair.private_key) for name, pair in producer_pairs.items()}
    actor_signer = Ed25519Signer(KeyPair.generate().private_key)
    for name, pair in producer_pairs.items():
        harness.verifier.add_trusted_key(
            pair.public_key,
            identity=producer_identities[name],
        )

    def _persist_model(
        payload: Any,
        *,
        family: str,
        kind: str,
        schema_name: str,
        schema_version: str,
        sign: bool = True,
    ) -> str:
        return _persist_signed(
            harness,
            payload,
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
            signer=signers[family],
            signer_identity=producer_identities[family],
            sign=sign,
            canon_spec=(
                CanonSpec(forbid_floats=False)
                if kind == contracts.HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND
                else None
            ),
        )

    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    evidence_ref = str(
        harness.store.put_bytes(
            b'{"statement":"The exact disconfirming evidence opened by the reviewer."}',
            ArtifactWriteOptions(
                kind="test.human_decision.disconfirming_evidence",
                media_type="application/json",
            ),
        ).artifact_id
    )
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
    gateway, contract_ref, _ = _prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    with patch.object(authority, "_utcnow", return_value=NOW):
        source_decision = _produce(
            gateway=gateway,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    request = source_decision.human_decision_request
    assert request is not None
    request = request.model_copy(
        update={
            "provenance_refs": list(
                dict.fromkeys([*request.provenance_refs, contract_ref, evidence_ref])
            ),
            "disconfirming_evidence_refs": [evidence_ref],
        }
    )
    source_decision = source_decision.model_copy(update={"human_decision_request": request})

    def _persist_contract(current_contract: Any, sign: bool = True) -> str:
        return _persist_signed(
            harness,
            current_contract,
            kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
            schema_name="polisyos.runtime.DelegationContract",
            schema_version=authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            signer=harness.owner_signer,
            signer_identity=MANDATE_OWNER_REF,
            sign=sign,
        )
    audit_path = tmp_path / "access.jsonl"
    empty_audit_path = tmp_path / "empty-access.jsonl"
    empty_audit_path.touch()

    principal_payload: dict[str, object] = {
        "binding_id": "principal-binding-1",
        "binding_ref": "identity://bindings/principal-1",
        "tenant_id": "tenant-a",
        "run_id": "run-gy-pa2",
        "principal_issuer": producer_identities["principal"],
        "principal_audience": "polisyos-runtime",
        "principal_subject": "human-reviewer-1",
        "actor_ref": MANDATE_OWNER_REF,
        "actor_key_id": actor_signer.key_id,
        "decision_roles": ["mandate_owner"],
        # C02 owns the new permission vocabulary. C01 exercises the generic
        # signed-permission property with an existing high-stakes permission.
        "permissions": [RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE.value],
        "valid_from": NOW - timedelta(minutes=5),
        "valid_until": NOW + timedelta(hours=1),
        "verifier_epoch": "ds9-test-epoch",
        "authority_boundary": _boundary(
            authoritative_for="human_decision_principal_binding",
            source="human_governance",
        ),
        "rule_version_ref": RULE_VERSION_REF,
        "issued_at": NOW - timedelta(minutes=5),
    }

    def _sign_principal(payload: dict[str, object]) -> str:
        binding_model = contracts.HumanDecisionPrincipalBinding.model_validate(payload)
        return _persist_model(
            binding_model,
            family="principal",
            kind=contracts.HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
            schema_name="polisyos.runtime.HumanDecisionPrincipalBinding",
            schema_version=contracts.HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
        )

    principal_ref = _sign_principal(principal_payload)
    separation_payload: dict[str, object] = {}

    def _sign_separation(payload: dict[str, object]) -> str:
        separation_model = contracts.ReviewerSeparationCredential.model_validate(payload)
        return _persist_model(
            separation_model,
            family="separation",
            kind=contracts.REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
            schema_name="polisyos.runtime.ReviewerSeparationCredential",
            schema_version=contracts.REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
        )

    def _persist_bundle(
        current_request: Any,
        current_source: Any,
        *,
        basis_ref: str = contract_ref,
        separation_update: dict[str, object] | None = None,
        presentation_update: dict[str, object] | None = None,
        session_update: dict[str, object] | None = None,
        event_timestamp: datetime = NOW,
        event_artifact_refs: tuple[str, ...] | None = None,
        event_update: dict[str, object] | None = None,
        sign_source: bool = True,
        sign_presentation: bool = True,
        sign_session: bool = True,
        sign_events: bool = True,
    ) -> dict[str, str]:
        current_digest = authority.agent_action_content_hash(current_request)
        source_ref = _persist_model(
            current_source,
            family="source",
            kind=authority.AGENT_ACTION_DECISION_ARTIFACT_KIND,
            schema_name="polisyos.runtime.AgentActionAuthorityDecision",
            schema_version=authority.AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
            sign=sign_source,
        )
        separation = contracts.ReviewerSeparationCredential(
            credential_id=f"separation-{current_digest[7:19]}",
            credential_ref=f"governance://separation/{current_digest[7:]}",
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
            case_id=current_request.case_id,
            decision_request_ref=current_request.request_ref,
            decision_request_digest=current_digest,
            reviewer_actor_ref=MANDATE_OWNER_REF,
            reviewed_actor_refs=("user:agent-operator",),
            independence_established=True,
            change_authority_actions=tuple(current_request.available_actions),
            valid_from=NOW - timedelta(minutes=5),
            valid_until=NOW + timedelta(hours=1),
            verifier_epoch="ds9-test-epoch",
            authority_boundary=_boundary(
                authoritative_for="human_decision_reviewer_separation",
                source="human_governance",
            ),
            rule_version_ref=RULE_VERSION_REF,
            issued_at=NOW - timedelta(minutes=5),
        )
        if separation_update:
            separation = separation.model_copy(update=separation_update)
        separation_payload.clear()
        separation_payload.update(separation.model_dump(mode="json"))
        separation_ref = _sign_separation(separation_payload)
        presentation = contracts.HumanDecisionPresentationContract(
            contract_id=f"presentation-{current_digest[7:19]}",
            contract_ref=f"governance://presentation/{current_digest[7:]}",
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
            decision_request_ref=current_request.request_ref,
            decision_request_digest=current_digest,
            required_artifact_digests=(basis_ref, evidence_ref),
            renderer_id="runtime-dashboard.human-decision-gate",
            renderer_version="1",
            channel="reviewer_console",
            representation="full",
            redaction_policy_ref=None,
            truncation_policy_ref=None,
            valid_from=NOW - timedelta(minutes=5),
            valid_until=NOW + timedelta(hours=1),
            verifier_epoch="ds9-test-epoch",
            authority_boundary=_boundary(
                authoritative_for="human_decision_presentation",
                source="human_governance",
            ),
            rule_version_ref=RULE_VERSION_REF,
            issued_at=NOW - timedelta(minutes=5),
        )
        if presentation_update:
            presentation = presentation.model_copy(update=presentation_update)
        presentation_ref = _persist_model(
            presentation,
            family="presentation",
            kind=contracts.HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            schema_name="polisyos.runtime.HumanDecisionPresentationContract",
            schema_version=contracts.HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
            sign=sign_presentation,
        )
        exposure_session = contracts.HumanDecisionExposureSession(
            session_id=f"session-{current_digest[7:19]}",
            session_ref=f"runtime://human-decision/exposure/{current_digest[7:]}",
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
            actor_ref=MANDATE_OWNER_REF,
            decision_request_ref=current_request.request_ref,
            decision_request_digest=current_digest,
            basis_digest=basis_ref,
            required_artifact_digests=(basis_ref, evidence_ref),
            presentation_contract_ref=presentation_ref,
            presentation_contract_digest=presentation_ref,
            renderer_id=presentation.renderer_id,
            renderer_version=presentation.renderer_version,
            channel=presentation.channel,
            representation=presentation.representation,
            valid_from=NOW - timedelta(minutes=1),
            valid_until=NOW + timedelta(minutes=30),
            verifier_epoch="ds9-test-epoch",
            authority_boundary=_boundary(
                authoritative_for="human_decision_evidence_exposure",
                source="deterministic_producer",
            ),
            rule_version_ref=RULE_VERSION_REF,
            issued_at=NOW - timedelta(minutes=1),
        )
        if session_update:
            exposure_session = exposure_session.model_copy(update=session_update)
        exposure_session_ref = _persist_model(
            exposure_session,
            family="custody",
            kind=contracts.HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            schema_name="polisyos.runtime.HumanDecisionExposureSession",
            schema_version=contracts.HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
            sign=sign_session,
        )
        trail = RuntimeDataAccessAuditTrail(path=audit_path)
        for index, artifact_ref in enumerate(
            event_artifact_refs or (basis_ref, evidence_ref)
        ):
            event = contracts.HumanDecisionExposureAuditEvent(
                timestamp=event_timestamp.timestamp(),
                event_id=f"exposure-{current_digest[7:19]}-{index}",
                event_ref=f"runtime://human-decision/exposure-events/{current_digest[7:]}-{index}",
                event_receipt_ref=None,
                tenant_id="tenant-a",
                actor_ref=MANDATE_OWNER_REF,
                run_id="run-gy-pa2",
                request_ref=current_request.request_ref,
                request_digest=current_digest,
                basis_digest=basis_ref,
                session_ref=exposure_session_ref,
                artifact_id=artifact_ref,
                content_digest=artifact_ref,
                delivered_bytes=len(harness.store.get_bytes(artifact_ref)),
                verifier_epoch="ds9-test-epoch",
            )
            if event_update:
                event = event.model_copy(update=event_update)
            event_payload = event.model_dump(mode="json")
            event_receipt_ref = _persist_model(
                event_payload,
                family="custody",
                kind=contracts.HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
                schema_name="polisyos.runtime.HumanDecisionExposureAuditEvent",
                schema_version=contracts.HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
                sign=sign_events,
            )
            trail.append(
                event.model_copy(update={"event_receipt_ref": event_receipt_ref}).model_dump(
                    mode="json"
                )
            )
        return {
            "source_ref": source_ref,
            "decision_request_ref": current_request.request_ref,
            "principal_binding_ref": principal_ref,
            "reviewer_separation_ref": separation_ref,
            "presentation_contract_ref": presentation_ref,
            "exposure_session_ref": exposure_session_ref,
            "basis_digest": basis_ref,
        }

    bundle = _persist_bundle(request, source_decision)
    trust_policy = contracts.HumanDecisionTrustPolicy(
        verifier_epoch="ds9-test-epoch",
        trusted_producers=(
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=authority.AGENT_ACTION_DECISION_ARTIFACT_KIND,
                schema_name="polisyos.runtime.AgentActionAuthorityDecision",
                schema_version=authority.AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
                signer_identity=producer_identities["source"],
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
                schema_name="polisyos.runtime.DelegationContract",
                schema_version=authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
                signer_identity=MANDATE_OWNER_REF,
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=authority.AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
                schema_name="polisyos.runtime.AgentActionAdmissionBundle",
                schema_version=authority.AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
                signer_identity=ADMISSION_PRODUCER_IDENTITY,
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=contracts.HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
                schema_name="polisyos.runtime.HumanDecisionPrincipalBinding",
                schema_version=contracts.HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
                signer_identity=producer_identities["principal"],
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=contracts.REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
                schema_name="polisyos.runtime.ReviewerSeparationCredential",
                schema_version=contracts.REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
                signer_identity=producer_identities["separation"],
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=contracts.HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
                schema_name="polisyos.runtime.HumanDecisionPresentationContract",
                schema_version=contracts.HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
                signer_identity=producer_identities["presentation"],
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=contracts.HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
                schema_name="polisyos.runtime.HumanDecisionExposureSession",
                schema_version=contracts.HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
                signer_identity=producer_identities["custody"],
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=contracts.HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
                schema_name="polisyos.runtime.HumanDecisionExposureAuditEvent",
                schema_version=contracts.HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
                signer_identity=producer_identities["custody"],
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind=contracts.HUMAN_DECISION_RECORD_ARTIFACT_KIND,
                schema_name="polisyos.runtime.HumanDecisionRecord",
                schema_version=contracts.HUMAN_DECISION_RECORD_MANIFEST_VERSION,
                signer_identity=producer_identities["custody"],
            ),
        ),
    )
    resolver_policy = contracts.HumanDecisionResolverPolicy(
        expected_consumer="polisyos.runtime.quality.agent_action_authority",
        expected_audience="polisyos-runtime",
        principal_audience="polisyos-runtime",
        expected_agent_operation=operation.operation_id,
        required_permission=RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE.value,
    )
    reservation_store = harness.control_store
    custody = DeploymentHumanDecisionCustody(
        available=True,
        signer=signers["custody"],
        verifier=harness.verifier,
        signer_identity=producer_identities["custody"],
        verifier_epoch="ds9-test-epoch",
        trust_policy=trust_policy,
        provenance=VerifierProvenance(
            source="unit_test_fixture",
            reference="tests/unit/runtime/http/test_human_decision_service.py",
        ),
    )
    service_kwargs = {
        "authority_sink": HumanDecisionAuthoritySink(
            artifact_store=harness.store,
            event_log=harness.event_log,
            reservation_store=reservation_store,
        ),
        "custody": custody,
        "resolver_policy": resolver_policy,
        "clock": lambda: NOW,
    }

    def _service_with_audit(path: Path) -> Any:
        return services.HumanDecisionService(access_audit_path=path, **service_kwargs)

    requirement = RouteAuthorizationRequirement(
        permission=RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
        resource_binding=ResourceBindingSpec(
            source=ResourceBindingSource.OWNED_EXISTING_PATH,
            resource_kind="runtime.run.human_decision",
            path_parameter="run_id",
        ),
    )
    verification = ActionPermissionVerification(
        requirement=requirement,
        subject="human-reviewer-1",
        tenant_id="tenant-a",
        jwt_id="jwt-human-reviewer-1",
        roles=frozenset({PolicyOSRole.ANALYST}),
        authorization_source="runtime.jwt+opa",
        granted_permissions=(RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,),
    )
    bound_permission = BoundActionPermissionVerification(
        verification=verification,
        bound_resource=BoundAuthorizationResource(
            requirement=requirement,
            tenant_id="tenant-a",
            resource_kind="runtime.run.human_decision.ownership_verified",
            resource_id=("urn:polisyos:runtime-authorization-resource:v1:sha256:" + "d" * 64),
            resource_digest="sha256:" + "d" * 64,
            authority=BindingAuthority.OWNERSHIP_VERIFIED,
            body_sha256="sha256:" + "b" * 64,
            query_sha256="sha256:" + "c" * 64,
            canonical_selectors=(("run_id", '"run-gy-pa2"'),),
        ),
    )
    adapter_input = contracts.HumanDecisionPA2GateInput(
        tenant_id="tenant-a",
        run_id="run-gy-pa2",
        source_kind="agent_action_authority",
        action_kind="search",
        **bundle,
    )

    def _resign_request_bundle(
        current_request: Any,
        *,
        source_update: dict[str, object] | None = None,
        basis_ref: str = contract_ref,
        separation_update: dict[str, object] | None = None,
        presentation_update: dict[str, object] | None = None,
        session_update: dict[str, object] | None = None,
        event_timestamp: datetime = NOW,
        event_artifact_refs: tuple[str, ...] | None = None,
        event_update: dict[str, object] | None = None,
        sign_source: bool = True,
        sign_presentation: bool = True,
        sign_session: bool = True,
        sign_events: bool = True,
    ) -> dict[str, str]:
        current_source = source_decision.model_copy(
            update={
                "human_decision_request": current_request,
                **(source_update or {}),
            }
        )
        return _persist_bundle(
            current_request,
            current_source,
            basis_ref=basis_ref,
            separation_update=separation_update,
            presentation_update=presentation_update,
            session_update=session_update,
            event_timestamp=event_timestamp,
            event_artifact_refs=event_artifact_refs,
            event_update=event_update,
            sign_source=sign_source,
            sign_presentation=sign_presentation,
            sign_session=sign_session,
            sign_events=sign_events,
        )

    agent_write_context = _write_context()
    write_context = contracts.HumanDecisionWriteContext.model_validate(
        agent_write_context.model_dump(mode="json")
    )

    return _SignedGateFixture(
        service=_service_with_audit(audit_path),
        adapter_input=adapter_input,
        bound_permission=bound_permission,
        store=harness.store,
        principal_payload=principal_payload,
        source_decision=source_decision,
        sign_principal=_sign_principal,
        sign_separation=_sign_separation,
        resign_request_bundle=_resign_request_bundle,
        persist_contract=_persist_contract,
        service_with_audit=_service_with_audit,
        empty_audit_path=empty_audit_path,
        custody_identity=producer_identities["custody"],
        custody_key_id=signers["custody"].key_id,
        write_context=write_context,
        harness=harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        binding=binding,
        effects=effects,
        separation_payload=dict(separation_payload),
    )


def test_human_decision_status_precedence_is_permutation_invariant() -> None:
    contracts = _contracts()
    precedence = (
        "invalid_source",
        "artifact_missing",
        "producer_missing",
        "revalidation_required",
        "blocked",
    )
    reasons_by_status = {
        status: contracts.HumanDecisionGateReason(
            code=f"fixture-{status}",
            message=f"Fixture reason for {status}.",
            status=status,
        )
        for status in precedence
    }
    assert contracts.select_human_decision_gate_status(()) == "available"
    for size in range(1, len(precedence) + 1):
        for selected in combinations(precedence, size):
            expected = min(selected, key=precedence.index)
            for ordering in permutations(selected):
                reasons = tuple(reasons_by_status[status] for status in ordering)
                assert contracts.select_human_decision_gate_status(reasons) == expected


def test_human_decision_wrong_role_is_blocked_with_reason(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    before = _human_decision_record_ids(fixture.store)
    baseline = fixture.resolve()
    assert baseline.status == "available", baseline.reasons
    wrong_role = {
        **fixture.principal_payload,
        "decision_roles": ["data_steward"],
    }
    wrong_role_ref = fixture.sign_principal(wrong_role)

    gate = fixture.resolve(principal_binding_ref=wrong_role_ref)

    assert gate.status == "blocked"
    assert "DS9-WRONG-ROLE" in _reason_codes(gate)
    assert _human_decision_record_ids(fixture.store) == before


def test_human_decision_expired_request_is_blocked_with_reason(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    before = _human_decision_record_ids(fixture.store)
    assert fixture.resolve().status == "available"
    request = fixture.source_decision.human_decision_request
    assert request is not None
    expired_request = request.model_copy(
        update={
            "requested_at": NOW - timedelta(minutes=2),
            "decision_due_at": NOW - timedelta(seconds=1),
            "decidable_until": NOW - timedelta(seconds=1),
        }
    )
    resigned = fixture.resign_request_bundle(expired_request)

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-DECISION-TTL-EXPIRED" in _reason_codes(gate)
    assert _human_decision_record_ids(fixture.store) == before


def test_human_decision_requires_attested_principal_to_signing_key_binding(
    tmp_path: Path,
) -> None:
    contracts = _contracts()
    fixture = _signed_current_gate_fixture(tmp_path)
    before = _human_decision_record_ids(fixture.store)
    unsigned_payload = {
        **fixture.principal_payload,
        "binding_id": "principal-binding-unsigned",
        "binding_ref": "identity://bindings/principal-unsigned",
    }
    unsigned_ref = _persist_unsigned_gate_model(
        fixture,
        contracts.HumanDecisionPrincipalBinding.model_validate(unsigned_payload),
        kind=contracts.HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
        schema_name="polisyos.runtime.HumanDecisionPrincipalBinding",
        schema_version=contracts.HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
    )

    unsigned_gate = fixture.resolve(principal_binding_ref=unsigned_ref)
    assert unsigned_gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(unsigned_gate)

    mismatched_issuer_ref = fixture.sign_principal(
        {
            **fixture.principal_payload,
            "binding_id": "principal-binding-wrong-issuer",
            "binding_ref": "identity://bindings/principal-wrong-issuer",
            "principal_issuer": "institution://identity/other-issuer",
        }
    )
    mismatch_gate = fixture.resolve(principal_binding_ref=mismatched_issuer_ref)
    assert mismatch_gate.status == "invalid_source"
    assert "DS9-PRINCIPAL-SIGNING-KEY-MISMATCH" in _reason_codes(mismatch_gate)
    assert _human_decision_record_ids(fixture.store) == before


def test_human_decision_requires_signed_separation_and_change_authority(
    tmp_path: Path,
) -> None:
    contracts = _contracts()
    fixture = _signed_current_gate_fixture(tmp_path)
    before = _human_decision_record_ids(fixture.store)
    unsigned_payload = {
        **fixture.separation_payload,
        "credential_id": "separation-unsigned",
        "credential_ref": "governance://separation/unsigned",
    }
    unsigned_ref = _persist_unsigned_gate_model(
        fixture,
        contracts.ReviewerSeparationCredential.model_validate(unsigned_payload),
        kind=contracts.REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
        schema_name="polisyos.runtime.ReviewerSeparationCredential",
        schema_version=contracts.REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
    )
    unsigned_gate = fixture.resolve(reviewer_separation_ref=unsigned_ref)
    assert unsigned_gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(unsigned_gate)

    no_change_ref = fixture.sign_separation(
        {
            **fixture.separation_payload,
            "credential_id": "separation-no-change-authority",
            "credential_ref": "governance://separation/no-change-authority",
            "change_authority_actions": ["reject"],
        }
    )
    no_change_gate = fixture.resolve(reviewer_separation_ref=no_change_ref)
    assert no_change_gate.status == "blocked"
    assert "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING" in _reason_codes(no_change_gate)
    assert _human_decision_record_ids(fixture.store) == before


def test_human_decision_binds_source_to_exact_contract_bytes(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        source_update={"contract_content_hash": "sha256:" + "f" * 64},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_rejects_arbitrary_source_refusal(tmp_path: Path) -> None:
    """A human approval cannot convert an unrelated producer refusal into authority."""

    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        source_update={
            "refusal_reasons": (
                "operation_out_of_envelope",
                "explicit_permission_missing",
            )
        },
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_requires_exact_source_predicate_provenance(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    checks = tuple(
        check.model_copy(update={"provenance": "recomputed"})
        if check.predicate == "mandate_bounded_delegation"
        else check
        for check in fixture.source_decision.predicate_checks
    )
    resigned = fixture.resign_request_bundle(
        request,
        source_update={"predicate_checks": checks},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_requires_pre_action_human_request_shape(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    contradictory = request.model_copy(
        update={
            "interaction_mode": "delegated_autonomous",
            "disposition": "no_interrupt",
        }
    )
    resigned = fixture.resign_request_bundle(contradictory)

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_requires_exact_live_delegation_envelope(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        source_update={
            "envelope_id": "envelope.missing",
            "envelope_ref": "pdc://gy-pa2/envelopes/missing",
        },
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_expired_signed_envelope_is_blocked(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    envelope = fixture.contract.action_envelopes[0].model_copy(
        update={"valid_until": NOW - timedelta(microseconds=1)}
    )
    contract = fixture.contract.model_copy(update={"action_envelopes": (envelope,)})
    contract_ref = fixture.persist_contract(contract, True)
    request = request.model_copy(
        update={
            "provenance_refs": list(
                dict.fromkeys([*request.provenance_refs, contract_ref])
            )
        }
    )
    resigned = fixture.resign_request_bundle(
        request,
        basis_ref=contract_ref,
        source_update={
            "contract_ref": contract_ref,
            "contract_content_hash": contract_ref,
        },
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-DECISION-TTL-EXPIRED" in _reason_codes(gate)


def test_human_decision_reviewer_separation_names_exact_reviewed_actor(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        separation_update={"reviewed_actor_refs": ("user:unrelated-operator",)},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING" in _reason_codes(gate)


def test_human_decision_rejects_actor_key_reused_as_custody_key(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    aliased_ref = fixture.sign_principal(
        {
            **fixture.principal_payload,
            "binding_id": "principal-binding-custody-key-alias",
            "binding_ref": "identity://bindings/principal-custody-key-alias",
            "actor_key_id": fixture.custody_key_id,
        }
    )

    gate = fixture.resolve(principal_binding_ref=aliased_ref)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_session_cannot_understate_presentation_basis(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    basis_ref = fixture.adapter_input.basis_digest
    assert basis_ref is not None
    resigned = fixture.resign_request_bundle(
        request,
        session_update={"required_artifact_digests": (basis_ref,)},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_coverage_preserves_duplicate_requirements(
    tmp_path: Path,
) -> None:
    """Two receipts cannot satisfy three signed presentation requirements."""

    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    basis_ref = fixture.adapter_input.basis_digest
    assert basis_ref is not None
    evidence_ref = request.disconfirming_evidence_refs[0]
    required = (basis_ref, evidence_ref, evidence_ref)
    resigned = fixture.resign_request_bundle(
        request,
        presentation_update={"required_artifact_digests": required},
        session_update={"required_artifact_digests": required},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_rejects_extra_completed_receipt(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    basis_ref = fixture.adapter_input.basis_digest
    assert basis_ref is not None
    evidence_ref = request.disconfirming_evidence_refs[0]
    resigned = fixture.resign_request_bundle(
        request,
        event_artifact_refs=(basis_ref, evidence_ref, evidence_ref),
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_binds_presentation_session_tuple_order(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    basis_ref = fixture.adapter_input.basis_digest
    assert basis_ref is not None
    evidence_ref = request.disconfirming_evidence_refs[0]
    resigned = fixture.resign_request_bundle(
        request,
        session_update={"required_artifact_digests": (evidence_ref, basis_ref)},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_session_binds_exact_renderer(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        session_update={"renderer_version": "forged-version"},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_event_must_occur_inside_session(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        session_update={
            "session_id": "session-outside-interval",
            "session_ref": "runtime://human-decision/exposure/outside-interval",
        },
        event_timestamp=NOW - timedelta(minutes=2),
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_event_preserves_subsecond_session_boundary(
    tmp_path: Path,
) -> None:
    """A valid event must not be moved outside its session by timestamp truncation."""

    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    valid_from = NOW - timedelta(seconds=30) + timedelta(microseconds=500)
    resigned = fixture.resign_request_bundle(
        request,
        session_update={"valid_from": valid_from},
        event_timestamp=valid_from + timedelta(microseconds=100),
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "available"


def test_human_decision_exposure_event_cannot_arrive_from_the_future(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        event_timestamp=NOW + timedelta(seconds=1),
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)


def test_human_decision_exposure_context_binds_verifier_epoch(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        presentation_update={"verifier_epoch": "foreign-epoch"},
        session_update={"verifier_epoch": "foreign-epoch"},
        event_update={"verifier_epoch": "foreign-epoch"},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert {
        "DS9-PRESENTATION-CONTRACT-INVALID",
        "DS9-EXPOSURE-SESSION-INVALID",
    } & _reason_codes(gate)


def test_human_decision_rejects_unsigned_source(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        source_update={
            "decision_id": "agent-action-authority.unsigned-source",
            "decision_ref": "runtime://agent-action-authority/unsigned-source",
        },
        sign_source=False,
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_rejects_unsigned_contract(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    contract = fixture.contract.model_copy(update={"contract_id": "ds9-unsigned-contract"})
    contract_ref = fixture.persist_contract(contract, False)
    resigned = fixture.resign_request_bundle(
        request,
        basis_ref=contract_ref,
        source_update={
            "contract_ref": contract_ref,
            "contract_content_hash": contract_ref,
        },
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_rejects_unsigned_presentation_contract(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        presentation_update={
            "contract_id": "presentation-unsigned",
            "contract_ref": "governance://presentation/unsigned",
        },
        sign_presentation=False,
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_rejects_unsigned_exposure_session(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        session_update={
            "session_id": "session-unsigned",
            "session_ref": "runtime://human-decision/exposure/unsigned",
        },
        sign_session=False,
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_rejects_unsigned_exposure_events(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        session_update={
            "session_id": "session-unsigned-events",
            "session_ref": "runtime://human-decision/exposure/unsigned-events",
        },
        event_timestamp=NOW - timedelta(seconds=1),
        sign_events=False,
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-EVIDENCE-NOT-OPENED" in _reason_codes(gate)


def test_human_decision_rejects_search_authority_for_data_request(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    before = _human_decision_record_ids(fixture.store)
    assert fixture.resolve().status == "available"

    gate = fixture.resolve(action_kind="data_request")

    assert gate.status == "blocked"
    assert "DS9-AUTHORITY-CROSS-USE" in _reason_codes(gate)
    assert _human_decision_record_ids(fixture.store) == before


def test_human_decision_rubber_stamp_without_mandate_or_evidence_is_blocked(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    before = _human_decision_record_ids(fixture.store)
    assert fixture.resolve().status == "available"
    empty_trail_service = fixture.service_with_audit(fixture.empty_audit_path)

    gate = empty_trail_service.resolve_gate(
        fixture.adapter_input,
        bound_permission=fixture.bound_permission,
    )

    assert gate.status == "blocked"
    assert {
        "DS9-MANDATE-NOT-SHOWN",
        "DS9-EVIDENCE-NOT-OPENED",
        "DS9-RUBBER-STAMP",
    } <= _reason_codes(gate)
    assert _human_decision_record_ids(fixture.store) == before


def test_human_decision_persists_custody_signature_not_actor_signature(
    tmp_path: Path,
) -> None:
    """The human act is signed input; PolicyOS signs only record custody."""

    fixture = _signed_current_gate_fixture(tmp_path)
    contracts = _contracts()
    created = fixture.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=fixture.adapter_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept accountability for this bounded action.",
            dissent_statement="Disconfirming evidence was reviewed and retained.",
            override_reason=None,
            blocking_reason=None,
        ),
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )

    signature = fixture.store.get_signature(created.record_ref)
    assert signature is not None
    assert signature.signer_identity == fixture.custody_identity
    assert signature.signer_identity != created.record.actor_ref
    assert created.record.custody_signer_identity == fixture.custody_identity


def test_human_decision_record_model_rejects_actor_custody_key_alias(
    tmp_path: Path,
) -> None:
    """The persisted v2 contract itself rejects a forgeable shared signing key."""

    fixture = _signed_current_gate_fixture(tmp_path)
    contracts = _contracts()
    created = fixture.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=fixture.adapter_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept accountability for this bounded action.",
            dissent_statement="Disconfirming evidence was reviewed and retained.",
            override_reason=None,
            blocking_reason=None,
        ),
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )
    payload = created.record.model_dump(mode="json")
    canonical_actor = payload["canonical_actor"]
    assert isinstance(canonical_actor, dict)
    canonical_actor["signing_key_id"] = fixture.custody_key_id

    with pytest.raises(ValueError, match="human actor key cannot alias"):
        created.record.__class__.model_validate(payload)


def test_human_decision_record_model_rejects_duplicate_exposure_receipts(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    contracts = _contracts()
    created = fixture.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=fixture.adapter_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept accountability for this bounded action.",
            dissent_statement="Disconfirming evidence was reviewed and retained.",
            override_reason=None,
            blocking_reason=None,
        ),
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )
    payload = created.record.model_dump(mode="json")
    receipt_refs = payload["exposure_event_refs"]
    assert isinstance(receipt_refs, list)
    assert len(receipt_refs) >= 2
    payload["exposure_event_refs"] = [receipt_refs[0], receipt_refs[0]]

    with pytest.raises(ValueError, match="exposure event refs must be unique"):
        created.record.__class__.model_validate(payload)


def test_human_decision_reissued_source_uses_one_stable_action_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source/request clocks cannot mint a second key for the same action join."""

    contracts = _contracts()
    services = _service_module()
    fixture = _signed_current_gate_fixture(tmp_path)
    command = contracts.HumanDecisionCreateCommand(
        gate_input=fixture.adapter_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept accountability for this bounded action.",
        dissent_statement="Disconfirming evidence was reviewed and retained.",
        override_reason=None,
        blocking_reason=None,
    )
    first = fixture.service.create_record(
        command,
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )
    request = fixture.source_decision.human_decision_request
    assert request is not None
    later = NOW + timedelta(seconds=1)
    reissued_request = request.model_copy(
        update={
            "requested_at": later,
            "decision_due_at": request.decision_due_at,
            "decidable_until": request.decidable_until,
        }
    )
    reissued_bundle = fixture.resign_request_bundle(
        reissued_request,
        source_update={"decided_at": later},
        event_timestamp=later,
    )
    reissued_input = fixture.adapter_input.model_copy(update=reissued_bundle)
    monkeypatch.setattr(fixture.service, "_clock", lambda: later)

    first_gate = fixture.adapter_input
    first_projection = fixture.service.resolve_gate(
        first_gate,
        bound_permission=fixture.bound_permission,
    )
    second_projection = fixture.service.resolve_gate(
        reissued_input,
        bound_permission=fixture.bound_permission,
    )
    assert second_projection.status == "available", second_projection.reasons
    assert second_projection.governed_action_key == first.record.governed_action_key

    with pytest.raises(
        services.HumanDecisionOperationalResolutionError,
        match="DS9-OVERLAPPING-REISSUE",
    ):
        fixture.service.create_record(
            command.model_copy(update={"gate_input": reissued_input}),
            bound_permission=fixture.bound_permission,
            write_context=fixture.write_context,
        )


def test_currentness_projection_direct_construction_cannot_satisfy_resolver(
    tmp_path: Path,
) -> None:
    services = _service_module()
    fixture = _signed_current_gate_fixture(tmp_path)
    projection = fixture.resolve()
    assert projection.status == "available"
    assert projection.operational_authority is False

    with pytest.raises(
        services.HumanDecisionOperationalResolutionError,
        match="DS9-DECISION-PRODUCER-MISSING",
    ):
        fixture.service.resolve_gateway_adapter(projection)


def test_human_decision_signed_orphan_is_preserved_as_historical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contracts = _contracts()
    services = _service_module()
    fixture = _signed_current_gate_fixture(tmp_path)
    sink = fixture.service.authority_sink
    from polisyos.runtime.http.services.control_plane_store import HumanDecisionWriteFence

    def _fail_commit(*_args: object, **_kwargs: object) -> None:
        raise ValueError("simulated post-signature commit interruption")

    monkeypatch.setattr(HumanDecisionWriteFence, "commit", _fail_commit)
    with pytest.raises(services.HumanDecisionPersistenceError):
        fixture.service.create_record(
            contracts.HumanDecisionCreateCommand(
                gate_input=fixture.adapter_input,
                decision_action="approve",
                decision_mode="ordinary",
                accountability_statement=("I accept accountability for this exact bounded action."),
                dissent_statement="The disconfirming evidence remains retained.",
                override_reason=None,
                blocking_reason=None,
            ),
            bound_permission=fixture.bound_permission,
            write_context=fixture.write_context,
        )

    gate = fixture.resolve()
    assert gate.governed_action_key is not None
    orphan = sink.get_reservation(
        tenant_id="tenant-a",
        governed_action_key=gate.governed_action_key,
    )
    assert orphan is not None
    assert orphan.state == "reconciled_orphan"
    assert orphan.record_ref is not None
    assert orphan.record_ref == orphan.record_sha256
    assert orphan.durable_event_id is not None


def test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restart recovery discovers signed CAS bytes whose SQL refs rolled back."""

    contracts = _contracts()
    services = _service_module()
    fixture = _signed_current_gate_fixture(tmp_path)
    sink = fixture.service.authority_sink
    from polisyos.runtime.http.services.control_plane_store import HumanDecisionWriteFence

    class _SimulatedProcessDeath(BaseException):
        pass

    def _die_after_signature(*_args: object, **_kwargs: object) -> None:
        raise _SimulatedProcessDeath

    command = contracts.HumanDecisionCreateCommand(
        gate_input=fixture.adapter_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept accountability for this bounded action.",
        dissent_statement="Disconfirming evidence was reviewed and retained.",
        override_reason=None,
        blocking_reason=None,
    )
    with monkeypatch.context() as crash:
        crash.setattr(HumanDecisionWriteFence, "commit", _die_after_signature)
        with pytest.raises(_SimulatedProcessDeath):
            fixture.service.create_record(
                command,
                bound_permission=fixture.bound_permission,
                write_context=fixture.write_context,
            )

    gate = fixture.resolve()
    assert gate.governed_action_key is not None
    crashed = sink.get_reservation(
        tenant_id="tenant-a",
        governed_action_key=gate.governed_action_key,
    )
    assert crashed is not None
    assert crashed.state == "reserved"
    assert crashed.record_ref is None
    assert crashed.record_sha256 is None
    assert crashed.durable_event_id is None
    record_refs = _human_decision_record_ids(fixture.store)
    assert len(record_refs) == 1
    record_ref = next(iter(record_refs))
    verification = fixture.store.verify_signature(
        record_ref,
        fixture.service.custody.verifier,
        strict_identity=True,
    )
    assert verification.ok
    manifest = fixture.store.get_manifest(record_ref)
    assert manifest.authority is not None
    event_ref = manifest.authority.diagnostic_event_ref
    event = DiagnosticEvent.model_validate(
        from_canonical_bytes(fixture.store.get_bytes(event_ref))
    )
    assert fixture.harness.event_log.list_events(event_id=event.event_id) == []

    recovery_time = NOW + timedelta(seconds=61)
    monkeypatch.setattr(fixture.service, "_clock", lambda: recovery_time)
    with pytest.raises(
        services.HumanDecisionOperationalResolutionError,
        match="DS9-RESERVATION-RECOVERY-REQUIRED",
    ):
        fixture.service.create_record(
            command,
            bound_permission=fixture.bound_permission,
            write_context=fixture.write_context,
        )
    recovery_required = sink.get_reservation(
        tenant_id="tenant-a",
        governed_action_key=gate.governed_action_key,
    )
    assert recovery_required is not None
    assert recovery_required.state == "recovery_required"
    assert recovery_required.record_ref is None

    reconciled = sink.reconcile_null_ref_reservation(
        tenant_id="tenant-a",
        governed_action_key=gate.governed_action_key,
        reservation_id=crashed.reservation_id,
        reservation_version=crashed.reservation_version,
        verifier=fixture.service.custody.verifier,
        expected_signer_identity=fixture.custody_identity,
        expected_key_id=fixture.custody_key_id,
        expected_cell_id=fixture.write_context.cell_id,
        expected_run_id=fixture.write_context.run_id,
        expected_job_id=fixture.write_context.job_id,
        reconciled_at=recovery_time,
    )
    assert reconciled.state == "reconciled_orphan"
    assert reconciled.record_ref == record_ref
    assert reconciled.record_sha256 == record_ref
    assert reconciled.durable_event_id == event.event_id
    durable = fixture.harness.event_log.list_events(event_id=event.event_id)
    assert len(durable) == 1
    assert durable[0].event == event

    replacement_time = recovery_time + timedelta(seconds=1)
    monkeypatch.setattr(fixture.service, "_clock", lambda: replacement_time)
    replacement = fixture.service.create_record(
        command,
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )
    assert replacement.reservation_version == crashed.reservation_version + 1
    historical = sink.get_reservation_generation(
        tenant_id="tenant-a",
        governed_action_key=gate.governed_action_key,
        reservation_version=crashed.reservation_version,
    )
    assert historical is not None
    assert historical.state == "reconciled_orphan"
