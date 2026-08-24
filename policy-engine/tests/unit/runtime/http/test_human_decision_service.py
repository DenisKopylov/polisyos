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

from polisyos.core.artifacts.signing import Ed25519Signer, KeyPair
from polisyos.runtime.http.access_audit import RuntimeDataAccessAuditTrail
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

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
    resign_request_bundle: Callable[[Any], dict[str, str]]
    service_with_audit: Callable[[Path], Any]
    empty_audit_path: Path

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


def _signed_current_gate_fixture(tmp_path: Path) -> _SignedGateFixture:
    contracts = _contracts()
    services = _service_module()
    authority = importlib.import_module("polisyos.runtime.quality.agent_action_authority")
    access_audit = importlib.import_module("polisyos.runtime.http.access_audit")
    from polisyos.core.security.identity import PolicyOSRole
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
    ) -> str:
        return _persist_signed(
            harness,
            payload,
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
            signer=signers[family],
            signer_identity=producer_identities[family],
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
    gateway, contract_ref, _ = _prepare_gateway(
        harness,
        contract=_contract(
            _envelope(
                valid_from=NOW - timedelta(minutes=5),
                valid_until=NOW + timedelta(hours=1),
            )
        ),
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
            "requested_at": NOW - timedelta(minutes=2),
            "decision_due_at": NOW + timedelta(minutes=30),
            "decidable_until": NOW + timedelta(hours=1),
            "provenance_refs": list(
                dict.fromkeys([*request.provenance_refs, contract_ref, evidence_ref])
            ),
            "disconfirming_evidence_refs": [evidence_ref],
        }
    )
    source_decision = source_decision.model_copy(update={"human_decision_request": request})
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
        "actor_ref": "human-reviewer-1",
        "actor_key_id": "human-reviewer-key-1",
        "decision_roles": ["mandate_owner"],
        "permissions": ["runs.human_decisions.create"],
        "valid_from": NOW - timedelta(minutes=5),
        "valid_until": NOW + timedelta(hours=1),
        "verifier_epoch": "ds9-test-epoch",
        "authority_boundary": _boundary(
            authoritative_for="human_decision_principal_binding",
            source="institutional_primary_source",
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

    def _persist_bundle(current_request: Any, current_source: Any) -> dict[str, str]:
        current_digest = authority.agent_action_content_hash(current_request)
        source_ref = _persist_model(
            current_source,
            family="source",
            kind=authority.AGENT_ACTION_DECISION_ARTIFACT_KIND,
            schema_name="polisyos.runtime.AgentActionAuthorityDecision",
            schema_version=authority.AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
        )
        separation = contracts.ReviewerSeparationCredential(
            credential_id=f"separation-{current_digest[7:19]}",
            credential_ref=f"governance://separation/{current_digest[7:]}",
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
            case_id=current_request.case_id,
            decision_request_ref=current_request.request_ref,
            decision_request_digest=current_digest,
            reviewer_actor_ref="human-reviewer-1",
            reviewed_actor_refs=("user:agent-operator",),
            independence_established=True,
            change_authority_actions=("approve", "reject"),
            valid_from=NOW - timedelta(minutes=5),
            valid_until=NOW + timedelta(hours=1),
            verifier_epoch="ds9-test-epoch",
            authority_boundary=_boundary(
                authoritative_for="human_decision_reviewer_separation",
                source="institutional_primary_source",
            ),
            rule_version_ref=RULE_VERSION_REF,
            issued_at=NOW - timedelta(minutes=5),
        )
        separation_ref = _persist_model(
            separation,
            family="separation",
            kind=contracts.REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
            schema_name="polisyos.runtime.ReviewerSeparationCredential",
            schema_version=contracts.REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
        )
        presentation = contracts.HumanDecisionPresentationContract(
            contract_id=f"presentation-{current_digest[7:19]}",
            contract_ref=f"governance://presentation/{current_digest[7:]}",
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
            decision_request_ref=current_request.request_ref,
            decision_request_digest=current_digest,
            required_artifact_digests=(contract_ref, evidence_ref),
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
                source="institutional_primary_source",
            ),
            rule_version_ref=RULE_VERSION_REF,
            issued_at=NOW - timedelta(minutes=5),
        )
        presentation_ref = _persist_model(
            presentation,
            family="presentation",
            kind=contracts.HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            schema_name="polisyos.runtime.HumanDecisionPresentationContract",
            schema_version=contracts.HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
        )
        exposure_session = contracts.HumanDecisionExposureSession(
            session_id=f"session-{current_digest[7:19]}",
            session_ref=f"runtime://human-decision/exposure/{current_digest[7:]}",
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
            actor_ref="human-reviewer-1",
            decision_request_ref=current_request.request_ref,
            decision_request_digest=current_digest,
            basis_digest=contract_ref,
            required_artifact_digests=(contract_ref, evidence_ref),
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
        exposure_session_ref = _persist_model(
            exposure_session,
            family="custody",
            kind=contracts.HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            schema_name="polisyos.runtime.HumanDecisionExposureSession",
            schema_version=contracts.HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
        )
        trail = RuntimeDataAccessAuditTrail(path=audit_path)
        for index, artifact_ref in enumerate((contract_ref, evidence_ref)):
            event = access_audit.HumanDecisionExposureAuditEvent(
                timestamp=NOW.timestamp(),
                event_id=f"exposure-{current_digest[7:19]}-{index}",
                event_ref=f"runtime://human-decision/exposure-events/{current_digest[7:]}-{index}",
                event_receipt_ref=None,
                tenant_id="tenant-a",
                actor_ref="human-reviewer-1",
                run_id="run-gy-pa2",
                request_ref=current_request.request_ref,
                request_digest=current_digest,
                basis_digest=contract_ref,
                session_ref=exposure_session_ref,
                artifact_id=artifact_ref,
                content_digest=artifact_ref,
                delivered_bytes=len(harness.store.get_bytes(artifact_ref)),
                verifier_epoch="ds9-test-epoch",
            )
            access_audit.persist_human_decision_exposure_event(
                trail=trail,
                event=event,
                artifact_store=harness.store,
                event_log=harness.event_log,
                signer=signers["custody"],
                signer_identity=producer_identities["custody"],
                verifier=harness.verifier,
            )
        return {
            "source_ref": source_ref,
            "decision_request_ref": current_request.request_ref,
            "principal_binding_ref": principal_ref,
            "reviewer_separation_ref": separation_ref,
            "presentation_contract_ref": presentation_ref,
            "exposure_session_ref": exposure_session_ref,
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
                artifact_kind=access_audit.HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
                schema_name="polisyos.runtime.HumanDecisionExposureAuditEvent",
                schema_version=access_audit.HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
                signer_identity=producer_identities["custody"],
            ),
        ),
    )
    resolver_policy = contracts.HumanDecisionResolverPolicy(
        expected_consumer="polisyos.runtime.quality.agent_action_authority",
        expected_audience="polisyos-runtime",
        principal_audience="polisyos-runtime",
        expected_agent_operation=operation.operation_id,
        required_permission="runs.human_decisions.create",
    )
    service_kwargs = {
        "artifact_store": harness.store,
        "event_log": harness.event_log,
        "reservation_store": ControlPlaneStore(
            backend="sqlite",
            sqlite_path=tmp_path / "human-decisions.sqlite3",
        ),
        "artifact_verifier": harness.verifier,
        "trust_policy": trust_policy,
        "resolver_policy": resolver_policy,
        "clock": lambda: NOW,
    }

    def _service_with_audit(path: Path) -> Any:
        return services.HumanDecisionService(access_audit_path=path, **service_kwargs)

    requirement = RouteAuthorizationRequirement(
        permission=RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE,
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
        granted_permissions=(RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE,),
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
        basis_digest=contract_ref,
        action_kind="search",
        **bundle,
    )

    def _resign_request_bundle(current_request: Any) -> dict[str, str]:
        current_source = source_decision.model_copy(
            update={"human_decision_request": current_request}
        )
        return _persist_bundle(current_request, current_source)

    return _SignedGateFixture(
        service=_service_with_audit(audit_path),
        adapter_input=adapter_input,
        bound_permission=bound_permission,
        store=harness.store,
        principal_payload=principal_payload,
        source_decision=source_decision,
        sign_principal=_sign_principal,
        resign_request_bundle=_resign_request_bundle,
        service_with_audit=_service_with_audit,
        empty_audit_path=empty_audit_path,
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
    assert fixture.resolve().status == "available"
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
