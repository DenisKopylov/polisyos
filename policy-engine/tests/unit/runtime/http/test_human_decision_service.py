"""Red-first semantic witnesses for the DS9 human-decision service."""

from __future__ import annotations

import importlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from itertools import combinations, permutations
from pathlib import Path
from typing import Any, cast
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
    sign_production_basis: Callable[[Any, bool], str]
    sign_scorecard: Callable[[dict[str, object], bool], str]
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


@dataclass(frozen=True)
class _SignedProductionGateFixture:
    base: _SignedGateFixture
    gate_input: Any
    basis: Any
    basis_ref: str
    scorecard: dict[str, object]
    scorecard_ref: str
    scorecard_binding_digest: str

    def resolve(self, **changes: object) -> Any:
        return self.base.service.resolve_gate(
            self.gate_input.model_copy(update=changes),
            bound_permission=self.base.bound_permission,
        )


def _bound_read_permission(
    fixture: _SignedGateFixture,
    *,
    resource_kind: str,
    selectors: dict[str, str],
) -> Any:
    from polisyos.runtime.http.authorization import (
        _BOUND_ACTION_PERMISSION_SEAL,
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

    source = fixture.bound_permission.verification
    requirement = RouteAuthorizationRequirement(
        permission=RuntimePermission.RUNS_REVIEW,
        resource_binding=ResourceBindingSpec(
            source=ResourceBindingSource.OWNED_EXISTING_PATH,
            resource_kind=resource_kind,
            path_parameter="run_id",
            path_selector_parameters=(
                ("artifact_id",) if resource_kind == "runtime.run.human_decision_evidence" else ()
            ),
            query_selector_parameters=(
                ("source_kind",) if resource_kind == "runtime.run.human_decision_gate" else ()
            ),
            allow_empty_body=True,
        ),
    )
    verification = ActionPermissionVerification(
        requirement=requirement,
        subject=source.subject,
        tenant_id=source.tenant_id,
        jwt_id=source.jwt_id,
        roles=source.roles,
        authorization_source=source.authorization_source,
        granted_permissions=(
            RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE,
            RuntimePermission.RUNS_REVIEW,
        ),
    )
    canonical_selectors = tuple(
        sorted(
            (
                name,
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            )
            for name, value in selectors.items()
        )
    )
    return BoundActionPermissionVerification(
        verification=verification,
        bound_resource=BoundAuthorizationResource(
            requirement=requirement,
            tenant_id=source.tenant_id,
            resource_kind=f"{resource_kind}.ownership_verified",
            resource_id=("urn:polisyos:runtime-authorization-resource:v1:sha256:" + "e" * 64),
            resource_digest="sha256:" + "e" * 64,
            authority=BindingAuthority.OWNERSHIP_VERIFIED,
            body_sha256="sha256:" + "b" * 64,
            query_sha256="sha256:" + "c" * 64,
            canonical_selectors=canonical_selectors,
        ),
        _seal=_BOUND_ACTION_PERMISSION_SEAL,
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
    from polisyos.runtime.http.access_audit import (
        PreparedHumanDecisionExposureEvent,
        complete_human_decision_exposure_event,
        reserve_human_decision_exposure_event,
    )
    from polisyos.runtime.http.authorization import (
        _BOUND_ACTION_PERMISSION_SEAL,
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
        "production_basis": KeyPair.generate(),
        "scorecard": KeyPair.generate(),
        "principal": KeyPair.generate(),
        "separation": KeyPair.generate(),
        "presentation": KeyPair.generate(),
        "custody": KeyPair.generate(),
    }
    producer_identities = {
        "source": "service://runtime/agent-action-authority",
        "production_basis": "institution://operations/production-decision-basis",
        "scorecard": "institution://operations/quality-scorecard",
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
            "five_rights_binding": request.five_rights_binding.model_copy(
                update={"required_information_refs": (evidence_ref,)}
            ),
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
        "permissions": [RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE.value],
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

    def _sign_production_basis(payload: Any, sign: bool = True) -> str:
        basis_model = contracts.ProductionHumanDecisionBasis.model_validate(payload)
        return _persist_model(
            basis_model,
            family="production_basis",
            kind=contracts.PRODUCTION_HUMAN_DECISION_BASIS_ARTIFACT_KIND,
            schema_name="polisyos.runtime.ProductionHumanDecisionBasis",
            schema_version=contracts.PRODUCTION_HUMAN_DECISION_BASIS_MANIFEST_VERSION,
            sign=sign,
        )

    def _sign_scorecard(payload: dict[str, object], sign: bool = True) -> str:
        return _persist_model(
            payload,
            family="scorecard",
            kind="runtime.quality_scorecard",
            schema_name="polisyos.runtime.QualityScorecard",
            schema_version="1.0",
            sign=sign,
        )

    def _persist_bundle(
        current_request: Any,
        current_source: Any,
        *,
        basis_ref: str = contract_ref,
        principal_ref_override: str | None = None,
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
        audit_path.write_text("", encoding="utf-8")
        effective_principal_ref = principal_ref_override or principal_ref
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
            principal_binding_ref=effective_principal_ref,
            principal_binding_digest=effective_principal_ref,
            principal_subject="human-reviewer-1",
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
        artifact_multiplicity = Counter(event_artifact_refs or (basis_ref, evidence_ref))
        for index, artifact_ref in enumerate(event_artifact_refs or (basis_ref, evidence_ref)):
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
                allowed_multiplicity=artifact_multiplicity[artifact_ref],
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
            prepared = PreparedHumanDecisionExposureEvent(
                unsigned_event=event,
                completed_event=event.model_copy(update={"event_receipt_ref": event_receipt_ref}),
                receipt_ref=event_receipt_ref,
            )
            if sign_events:
                reserved = reserve_human_decision_exposure_event(
                    trail=trail,
                    prepared=prepared,
                    artifact_store=harness.store,
                    signer=signers["custody"],
                    signer_identity=producer_identities["custody"],
                    verifier=harness.verifier,
                )
                complete_human_decision_exposure_event(
                    trail=trail,
                    reserved=reserved,
                    artifact_store=harness.store,
                    signer=signers["custody"],
                    signer_identity=producer_identities["custody"],
                    verifier=harness.verifier,
                )
            else:
                reserved = trail._reserve_exposure_delivery(prepared)
                trail._append_reserved_exposure(reserved)
        return {
            "source_ref": source_ref,
            "decision_request_ref": current_request.request_ref,
            "principal_binding_ref": effective_principal_ref,
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
                artifact_kind=contracts.PRODUCTION_HUMAN_DECISION_BASIS_ARTIFACT_KIND,
                schema_name="polisyos.runtime.ProductionHumanDecisionBasis",
                schema_version=contracts.PRODUCTION_HUMAN_DECISION_BASIS_MANIFEST_VERSION,
                signer_identity=producer_identities["production_basis"],
            ),
            contracts.HumanDecisionTrustedProducer(
                artifact_kind="runtime.quality_scorecard",
                schema_name="polisyos.runtime.QualityScorecard",
                schema_version="1.0",
                signer_identity=producer_identities["scorecard"],
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
        required_permission=RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE.value,
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
        _seal=_BOUND_ACTION_PERMISSION_SEAL,
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
        principal_ref_override: str | None = None,
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
            principal_ref_override=principal_ref_override,
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
        sign_production_basis=_sign_production_basis,
        sign_scorecard=_sign_scorecard,
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


def _signed_current_production_gate_fixture(tmp_path: Path) -> _SignedProductionGateFixture:
    base = _signed_current_gate_fixture(tmp_path)
    contracts = _contracts()
    authority = importlib.import_module("polisyos.runtime.quality.agent_action_authority")
    request = base.source_decision.human_decision_request
    assert request is not None
    decision_ends = tuple(
        value for value in (request.decision_due_at, request.decidable_until) if value is not None
    )
    scorecard: dict[str, object] = {
        "schema_version": "policyos.quality_scorecard.v1",
        "run_id": "run-gy-pa2",
        "execution_status": "completed",
        "quality_status": "pass",
        "performance_status": "pass",
        "conflict_status": "pass",
        "blocking_quality_failures": [],
        "approval_" + "state": "approval_" + "ready",
        "quality_scorecard_ref": "sha256:" + "6" * 64,
        "scorecard_identity_ref": "sha256:" + "6" * 64,
        "scorecard_identity_verified": True,
    }
    scorecard_ref = base.sign_scorecard(scorecard, True)
    from polisyos.runtime.http.production_approval_binding import (
        production_approval_scorecard_binding_digest,
    )

    scorecard_binding_digest = production_approval_scorecard_binding_digest(
        scorecard,
        ref=scorecard_ref,
        run_id="run-gy-pa2",
    )
    basis = contracts.ProductionHumanDecisionBasis(
        basis_id="production-basis-1",
        basis_ref="operations://production-basis/run-gy-pa2",
        tenant_id="tenant-a",
        run_id="run-gy-pa2",
        case_id=request.case_id,
        governed_action_key="sha256:" + "9" * 64,
        decision_request=request,
        requester_actor_ref="user:agent-operator",
        decision_request_ref=request.request_ref,
        decision_request_digest=authority.agent_action_content_hash(request),
        mandate_record_ref=request.s6_mandate_record_ref,
        mandate_owner_ref="institution://operations/approval-owner",
        operation_id="runtime.production_approval",
        action_kind="production_approval",
        decision_rights_matrix_ref=request.decision_rights_matrix_ref,
        required_role=request.required_role,
        offered_actions=tuple(request.available_actions),
        scorecard_ref=scorecard_ref,
        scorecard_digest=scorecard_ref,
        valid_from=request.requested_at,
        valid_until=min(decision_ends) if decision_ends else NOW + timedelta(minutes=30),
        verifier_epoch="ds9-test-epoch",
        authority_boundary=request.authority_boundary,
        rule_version_ref=request.rule_version_ref,
        issued_at=NOW,
    )
    basis_ref = base.sign_production_basis(basis, True)
    bundle = base.resign_request_bundle(request, basis_ref=basis_ref)
    gate_input = contracts.HumanDecisionProductionGateInput(
        tenant_id="tenant-a",
        run_id="run-gy-pa2",
        source_kind="production_approval",
        source_ref=basis_ref,
        basis_ref=basis_ref,
        basis_digest=basis_ref,
        decision_request_ref=request.request_ref,
        decision_request_digest=authority.agent_action_content_hash(request),
        principal_binding_ref=bundle["principal_binding_ref"],
        reviewer_separation_ref=bundle["reviewer_separation_ref"],
        presentation_contract_ref=bundle["presentation_contract_ref"],
        exposure_session_ref=bundle["exposure_session_ref"],
        production_packet_ref=None,
    )
    return _SignedProductionGateFixture(
        base=base,
        gate_input=gate_input,
        basis=basis,
        basis_ref=basis_ref,
        scorecard=scorecard,
        scorecard_ref=scorecard_ref,
        scorecard_binding_digest=scorecard_binding_digest,
    )


def test_production_basis_content_binds_complete_signed_request(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    payload = fixture.basis.model_dump(mode="python")
    payload["decision_request_digest"] = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="complete signed request"):
        _contracts().ProductionHumanDecisionBasis.model_validate(payload)


def test_production_approval_requires_matching_live_human_decision_record(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    contracts = _contracts()

    gate = fixture.resolve()
    assert gate.status == "available"
    created = fixture.base.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=fixture.gate_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept accountability for this production approval.",
            dissent_statement="No dissent after reviewing all required evidence.",
        ),
        bound_permission=fixture.base.bound_permission,
        write_context=fixture.base.write_context,
    )

    assert created.record.source_kind == "production_approval"
    assert created.record.source_ref == fixture.basis_ref
    assert created.record.source_digest == fixture.basis_ref
    assert created.record.basis_ref == fixture.basis_ref
    assert created.record.basis_digest == fixture.basis_ref
    assert created.record.human_decision_request_ref == fixture.basis.decision_request_ref
    assert created.record.decision_request_digest == fixture.basis.decision_request_digest
    assert created.record.governed_action_key == fixture.basis.governed_action_key
    inputs = fixture.base.service.resolve_production_approval_inputs(
        tenant_id="tenant-a",
        run_id="run-gy-pa2",
        scorecard_ref=fixture.scorecard_ref,
        scorecard_binding_digest=fixture.scorecard_binding_digest,
        production_basis_ref=fixture.basis_ref,
        human_decision_record_ref=created.record_ref,
        evaluated_at=NOW,
    )
    assert inputs.record_ref == created.record_ref
    assert inputs.basis_ref == fixture.basis_ref
    assert inputs.scorecard_ref == fixture.scorecard_ref


def test_production_approval_blocks_unverified_scorecard_producer(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    contracts = _contracts()
    unsigned_scorecard = {
        **fixture.scorecard,
        "quality_status": "passed",
    }
    unsigned_scorecard_ref = fixture.base.sign_scorecard(unsigned_scorecard, False)
    basis = fixture.basis.model_copy(
        update={
            "basis_id": "production-basis-unsigned-scorecard",
            "basis_ref": "operations://production-basis/unsigned-scorecard",
            "scorecard_ref": unsigned_scorecard_ref,
            "scorecard_digest": unsigned_scorecard_ref,
            "governed_action_key": "sha256:" + "7" * 64,
        }
    )
    basis_ref = fixture.base.sign_production_basis(basis, True)
    bundle = fixture.base.resign_request_bundle(basis.decision_request, basis_ref=basis_ref)
    gate_input = fixture.gate_input.model_copy(
        update={
            "source_ref": basis_ref,
            "basis_ref": basis_ref,
            "basis_digest": basis_ref,
            "principal_binding_ref": bundle["principal_binding_ref"],
            "reviewer_separation_ref": bundle["reviewer_separation_ref"],
            "presentation_contract_ref": bundle["presentation_contract_ref"],
            "exposure_session_ref": bundle["exposure_session_ref"],
        }
    )
    created = fixture.base.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=gate_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept accountability for this production approval.",
            dissent_statement="No dissent after reviewing all required evidence.",
        ),
        bound_permission=fixture.base.bound_permission,
        write_context=fixture.base.write_context,
    )
    from polisyos.runtime.http.production_approval_binding import (
        production_approval_scorecard_binding_digest,
    )

    with pytest.raises(
        _service_module().HumanDecisionOperationalResolutionError,
    ) as exc_info:
        fixture.base.service.resolve_production_approval_inputs(
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
            scorecard_ref=unsigned_scorecard_ref,
            scorecard_binding_digest=production_approval_scorecard_binding_digest(
                unsigned_scorecard,
                ref=unsigned_scorecard_ref,
                run_id="run-gy-pa2",
            ),
            production_basis_ref=basis_ref,
            human_decision_record_ref=created.record_ref,
            evaluated_at=NOW,
        )
    assert exc_info.value.code == "DS9-DECISION-SOURCE-INVALID"


def test_production_gate_issues_subject_bound_exposure_session(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    gate_input = fixture.gate_input.model_copy(update={"exposure_session_ref": None})
    proof = _bound_read_permission(
        fixture.base,
        resource_kind="runtime.run.human_decision_gate",
        selectors={
            "run_id": "run-gy-pa2",
            "source_kind": "production_approval",
        },
    )

    issued = fixture.base.service.issue_exposure_session(
        gate_input,
        bound_permission=proof,
    )

    assert issued.session.basis_digest == fixture.basis_ref
    assert issued.session.principal_subject == "human-reviewer-1"
    assert issued.session.actor_ref == fixture.base.principal_payload["actor_ref"]


def test_production_gate_rejects_unsigned_basis_with_typed_refusal(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    unsigned_basis = fixture.basis.model_copy(
        update={
            "basis_id": "production-basis-unsigned",
            "basis_ref": "operations://production-basis/unsigned",
        }
    )
    unsigned_ref = fixture.base.sign_production_basis(unsigned_basis, False)

    gate = fixture.resolve(
        source_ref=unsigned_ref,
        basis_ref=unsigned_ref,
        basis_digest=unsigned_ref,
    )

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)
    assert _human_decision_record_ids(fixture.base.store) == set()


def test_production_gate_blocks_requester_self_review(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    self_review_basis = fixture.basis.model_copy(
        update={"requester_actor_ref": fixture.base.principal_payload["actor_ref"]}
    )
    basis_ref = fixture.base.sign_production_basis(self_review_basis, True)
    bundle = fixture.base.resign_request_bundle(
        self_review_basis.decision_request,
        basis_ref=basis_ref,
    )

    gate = fixture.resolve(
        source_ref=basis_ref,
        basis_ref=basis_ref,
        basis_digest=basis_ref,
        principal_binding_ref=bundle["principal_binding_ref"],
        reviewer_separation_ref=bundle["reviewer_separation_ref"],
        presentation_contract_ref=bundle["presentation_contract_ref"],
        exposure_session_ref=bundle["exposure_session_ref"],
    )

    assert gate.status == "blocked"
    assert "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING" in _reason_codes(gate)


def test_production_gate_stale_basis_requires_revalidation(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    later = fixture.basis.valid_until + timedelta(seconds=1)
    fixture.base.service._clock = lambda: later

    gate = fixture.resolve()

    assert gate.status == "revalidation_required"
    assert "DS9-DECISION-REVALIDATION-REQUIRED" in _reason_codes(gate)
    assert _human_decision_record_ids(fixture.base.store) == set()


def test_production_record_reservation_admits_one_live_winner(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    contracts = _contracts()
    command = contracts.HumanDecisionCreateCommand(
        gate_input=fixture.gate_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept accountability for this production approval.",
        dissent_statement="No dissent after reviewing all required evidence.",
    )

    first = fixture.base.service.create_record(
        command,
        bound_permission=fixture.base.bound_permission,
        write_context=fixture.base.write_context,
    )
    with pytest.raises(
        _service_module().HumanDecisionOperationalResolutionError,
    ) as exc_info:
        fixture.base.service.create_record(
            command,
            bound_permission=fixture.base.bound_permission,
            write_context=fixture.base.write_context,
        )

    assert exc_info.value.code == "DS9-OVERLAPPING-REISSUE"
    assert _human_decision_record_ids(fixture.base.store) == {first.record_ref}


def test_signed_packet_stale_replayed_or_wrong_consumer_is_rejected(tmp_path: Path) -> None:
    fixture = _signed_current_production_gate_fixture(tmp_path)
    contracts = _contracts()
    created = fixture.base.service.create_record(
        contracts.HumanDecisionCreateCommand(
            gate_input=fixture.gate_input,
            decision_action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept accountability for this production approval.",
            dissent_statement="No dissent after reviewing all required evidence.",
        ),
        bound_permission=fixture.base.bound_permission,
        write_context=fixture.base.write_context,
    )
    inputs = fixture.base.service.resolve_production_approval_inputs(
        tenant_id="tenant-a",
        run_id="run-gy-pa2",
        scorecard_ref=fixture.scorecard_ref,
        scorecard_binding_digest=fixture.scorecard_binding_digest,
        production_basis_ref=fixture.basis_ref,
        human_decision_record_ref=created.record_ref,
        evaluated_at=NOW,
    )
    from polisyos.runtime.quality import approval

    authority = approval._ResolvedProductionApprovalAuthority(
        inputs=inputs,
        expected_consumer="polisyos.runtime.quality.agent_action_authority",
        expected_audience="polisyos-runtime",
        evaluated_at=NOW,
        _seal=approval._RESOLVER_SEAL,
    )
    packet_builder = getattr(
        approval,
        "build_resolved_production_" + "approval_" + "packet",
    )
    packet = packet_builder(authority)
    receipt = fixture.base.service._persist_production_decision_packet(
        packet,
        write_context=fixture.base.write_context,
    )
    resolved = fixture.base.service.resolve_production_decision_packet(
        packet_ref=receipt.packet_ref,
        tenant_id="tenant-a",
        run_id="run-gy-pa2",
        expected_consumer="polisyos.runtime.quality.agent_action_authority",
        expected_audience="polisyos-runtime",
        evaluated_at=NOW,
    )
    assert resolved.packet_ref == receipt.packet_ref

    attempts = (
        {
            "run_id": "run-replayed-elsewhere",
            "expected_consumer": "polisyos.runtime.quality.agent_action_authority",
            "evaluated_at": NOW,
        },
        {
            "run_id": "run-gy-pa2",
            "expected_consumer": "polisyos.scientist.decision_compiler",
            "evaluated_at": NOW,
        },
        {
            "run_id": "run-gy-pa2",
            "expected_consumer": "polisyos.runtime.quality.agent_action_authority",
            "evaluated_at": cast("datetime", packet.valid_until) + timedelta(seconds=1),
        },
    )
    for attempt in attempts:
        with pytest.raises(
            _service_module().HumanDecisionOperationalResolutionError,
        ):
            fixture.base.service.resolve_production_decision_packet(
                packet_ref=receipt.packet_ref,
                tenant_id="tenant-a",
                expected_audience="polisyos-runtime",
                **attempt,
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


def test_unbound_contestability_is_omitted_despite_signed_case_strings(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)

    response = fixture.service.resolve_gate_response(
        fixture.adapter_input,
        bound_permission=fixture.bound_permission,
    )

    assert response.status == "available"
    assert response.source_ref is not None
    assert response.decision_request is not None
    assert response.decision_request.case_id
    assert response.contestability is None


def test_available_gate_response_exposes_server_resolved_submission_binding(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    contracts = _contracts()

    response = fixture.service.resolve_gate_response(
        fixture.adapter_input,
        bound_permission=fixture.bound_permission,
    )

    assert response.status == "available"
    assert response.continuation is not None
    assert response.submission is not None
    selector = response.submission.selector
    assert selector == response.continuation
    assert selector.source_kind == "agent_action_authority"
    assert selector.source_ref == fixture.adapter_input.source_ref
    assert selector.basis_ref == fixture.source_decision.contract_ref
    assert selector.basis_digest == fixture.source_decision.contract_ref
    assert selector.principal_binding_ref == fixture.adapter_input.principal_binding_ref
    assert selector.reviewer_separation_ref == fixture.adapter_input.reviewer_separation_ref
    assert selector.presentation_contract_ref == fixture.adapter_input.presentation_contract_ref
    assert selector.exposure_session_ref == fixture.adapter_input.exposure_session_ref
    assert contracts.HumanDecisionPA2GateInput.model_validate(
        {
            **selector.model_dump(mode="json", exclude={"operational_authority"}),
            "tenant_id": response.tenant_id,
            "run_id": response.run_id,
        }
    ) == fixture.adapter_input.model_copy(
        update={
            "basis_ref": fixture.source_decision.contract_ref,
            "basis_digest": fixture.source_decision.contract_ref,
            "decision_request_digest": response.decision_request_digest,
        }
    )
    assert {row.action for row in response.submission.allowed_decisions} == set(
        response.decision_request.available_actions
    )


def test_nonavailable_gate_has_no_submission_binding(tmp_path: Path) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)

    response = fixture.service.resolve_gate_response(
        fixture.adapter_input.model_copy(update={"action_kind": "data_request.other"}),
        bound_permission=fixture.bound_permission,
    )

    assert response.status == "blocked"
    assert response.submission is None
    assert response.continuation is None


def test_missing_exposure_session_has_no_continuation_or_submission(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)

    response = fixture.service.resolve_gate_response(
        fixture.adapter_input.model_copy(update={"exposure_session_ref": None}),
        bound_permission=fixture.bound_permission,
    )

    assert response.status == "producer_missing"
    assert "DS9-EXPOSURE-SESSION-PRODUCER-MISSING" in response.reason_codes
    assert response.continuation is None
    assert response.submission is None


def test_evidence_only_block_exposes_verified_continuation_without_submission(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    service = fixture.service_with_audit(fixture.empty_audit_path)

    response = service.resolve_gate_response(
        fixture.adapter_input,
        bound_permission=fixture.bound_permission,
    )

    assert response.status == "blocked"
    assert set(response.reason_codes) == {
        "DS9-MANDATE-NOT-SHOWN",
        "DS9-EVIDENCE-NOT-OPENED",
        "DS9-RUBBER-STAMP",
    }
    assert response.continuation is not None
    assert response.continuation.exposure_session_ref == fixture.adapter_input.exposure_session_ref
    assert response.submission is None


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

    request = fixture.source_decision.human_decision_request
    assert request is not None
    rebound = fixture.resign_request_bundle(
        request,
        principal_ref_override=wrong_role_ref,
    )
    gate = fixture.resolve(**rebound)

    assert gate.status == "blocked", gate.reasons
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


def test_human_decision_stale_basis_requires_online_revalidation(
    tmp_path: Path,
) -> None:
    """Recoverable signed-input staleness cannot collapse into invalid or blocked."""

    fixture = _signed_current_gate_fixture(tmp_path)
    stale_principal_ref = fixture.sign_principal(
        {
            **fixture.principal_payload,
            "binding_id": "principal-binding-stale",
            "binding_ref": "identity://bindings/principal-stale",
            "valid_from": NOW - timedelta(hours=2),
            "valid_until": NOW - timedelta(seconds=1),
        }
    )

    gate = fixture.resolve(principal_binding_ref=stale_principal_ref)

    assert gate.status == "revalidation_required"
    assert "DS9-DECISION-REVALIDATION-REQUIRED" in _reason_codes(gate)
    assert "DS9-DECISION-SOURCE-INVALID" not in _reason_codes(gate)


def test_exposure_session_is_issued_for_and_resolved_by_exact_live_subject(
    tmp_path: Path,
) -> None:
    """Removing the subject join would let a same-tenant reviewer steal a session."""

    fixture = _signed_current_gate_fixture(tmp_path)
    gate_input = fixture.adapter_input.model_copy(update={"exposure_session_ref": None})
    gate_permission = _bound_read_permission(
        fixture,
        resource_kind="runtime.run.human_decision_gate",
        selectors={
            "run_id": gate_input.run_id,
            "source_kind": gate_input.source_kind,
        },
    )

    issued = fixture.service.issue_exposure_session(
        gate_input,
        bound_permission=gate_permission,
    )

    assert issued.session.principal_subject == gate_permission.verification.subject
    assert issued.session.principal_binding_ref == gate_input.principal_binding_ref
    assert issued.session_ref == issued.session_digest
    artifact_ref = issued.session.required_artifact_digests[0]
    evidence_permission = _bound_read_permission(
        fixture,
        resource_kind="runtime.run.human_decision_evidence",
        selectors={"run_id": gate_input.run_id, "artifact_id": artifact_ref},
    )
    delivery = fixture.service.resolve_exposure_delivery(
        session_ref=issued.session_ref,
        artifact_ref=artifact_ref,
        tenant_id=gate_input.tenant_id,
        run_id=gate_input.run_id,
        bound_permission=evidence_permission,
    )
    assert delivery.session == issued.session
    assert delivery.artifact_ref == artifact_ref
    assert delivery.content == fixture.store.get_bytes(artifact_ref)
    assert delivery.media_type == "application/json"

    other_verification = replace(
        evidence_permission.verification,
        subject="same-tenant-session-thief",
        jwt_id="jwt-same-tenant-session-thief",
    )
    other_permission = replace(
        evidence_permission,
        verification=other_verification,
    )
    services = _service_module()
    with pytest.raises(
        services.HumanDecisionOperationalResolutionError,
        match="DS9-EXPOSURE-SUBJECT-MISMATCH",
    ):
        fixture.service.resolve_exposure_delivery(
            session_ref=issued.session_ref,
            artifact_ref=artifact_ref,
            tenant_id=gate_input.tenant_id,
            run_id=gate_input.run_id,
            bound_permission=other_permission,
        )

    fixture.service.prepare_exposure_audit_event(delivery)
    with pytest.raises(
        services.HumanDecisionOperationalResolutionError,
        match="DS9-EXPOSURE-REVALIDATION-REQUIRED",
    ):
        fixture.service.prepare_exposure_audit_event(delivery)


def test_exposure_session_rejects_sealed_proof_from_wrong_route_binding(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.authorization import ResourceBindingSpec

    fixture = _signed_current_gate_fixture(tmp_path)
    gate_input = fixture.adapter_input.model_copy(update={"exposure_session_ref": None})
    proof = _bound_read_permission(
        fixture,
        resource_kind="runtime.run.human_decision_gate",
        selectors={"run_id": gate_input.run_id, "source_kind": gate_input.source_kind},
    )
    wrong_binding = ResourceBindingSpec(
        source=proof.verification.requirement.resource_binding.source,
        resource_kind="runtime.run.human_decision_gate",
        path_parameter="run_id",
        path_selector_parameters=("source_kind",),
        allow_empty_body=True,
    )
    wrong_requirement = replace(
        proof.verification.requirement,
        resource_binding=wrong_binding,
    )
    wrong_proof = replace(
        proof,
        verification=replace(proof.verification, requirement=wrong_requirement),
        bound_resource=replace(proof.bound_resource, requirement=wrong_requirement),
    )
    services = _service_module()

    with pytest.raises(
        services.HumanDecisionOperationalResolutionError,
        match="DS9-DECISION-PERMISSION-UNVERIFIED",
    ):
        fixture.service.issue_exposure_session(
            gate_input,
            bound_permission=wrong_proof,
        )


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


def test_human_decision_caller_selectors_must_match_signed_packet(
    tmp_path: Path,
) -> None:
    contracts = _contracts()
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    request_digest = "sha256:" + "e" * 64
    basis_ref = "sha256:" + "f" * 64

    wrong_request = contracts.HumanDecisionPA2GateInput.model_validate(
        {
            **fixture.adapter_input.model_dump(mode="json"),
            "decision_request_digest": request_digest,
        }
    )
    wrong_basis = contracts.HumanDecisionPA2GateInput.model_validate(
        {
            **fixture.adapter_input.model_dump(mode="json"),
            "basis_ref": basis_ref,
        }
    )

    request_gate = fixture.service.resolve_gate(
        wrong_request,
        bound_permission=fixture.bound_permission,
    )
    basis_gate = fixture.service.resolve_gate(
        wrong_basis,
        bound_permission=fixture.bound_permission,
    )

    assert request_gate.status == "invalid_source"
    assert basis_gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(request_gate)
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(basis_gate)


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


def test_human_decision_five_rights_binding_cannot_diverge_from_signed_request(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    tampered = request.model_copy(
        update={
            "five_rights_binding": request.five_rights_binding.model_copy(
                update={"required_information_refs": ()}
            )
        }
    )
    resigned = fixture.resign_request_bundle(tampered)

    gate = fixture.resolve(**resigned)

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)


def test_human_decision_format_channel_must_match_signed_rights_binding(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)
    request = fixture.source_decision.human_decision_request
    assert request is not None
    resigned = fixture.resign_request_bundle(
        request,
        presentation_update={"channel": "governed_review"},
    )

    gate = fixture.resolve(**resigned)

    assert gate.status == "blocked"
    assert "DS9-PRESENTATION-CONTRACT-INVALID" in _reason_codes(gate)


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
        update={"provenance_refs": list(dict.fromkeys([*request.provenance_refs, contract_ref]))}
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
    response = fixture.service.resolve_gate_response(
        fixture.adapter_input.model_copy(update=resigned),
        bound_permission=fixture.bound_permission,
    )

    assert gate.status == "blocked"
    assert "DS9-EXPOSURE-SESSION-INVALID" in _reason_codes(gate)
    assert response.continuation is None
    assert response.submission is None


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
    assert "DS9-EVIDENCE-NOT-OPENED" in _reason_codes(gate)


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
    response = fixture.service.resolve_gate_response(
        fixture.adapter_input.model_copy(update=resigned),
        bound_permission=fixture.bound_permission,
    )

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)
    assert response.continuation is None
    assert response.submission is None


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
    response = fixture.service.resolve_gate_response(
        fixture.adapter_input.model_copy(update=resigned),
        bound_permission=fixture.bound_permission,
    )

    assert gate.status == "invalid_source"
    assert "DS9-DECISION-SOURCE-INVALID" in _reason_codes(gate)
    assert response.continuation is None
    assert response.submission is None


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


def test_human_decision_read_normalizes_missing_artifact_to_public_resolution_error(
    tmp_path: Path,
) -> None:
    fixture = _signed_current_gate_fixture(tmp_path)

    with pytest.raises(
        _service_module().HumanDecisionOperationalResolutionError,
    ) as caught:
        fixture.service.read_record(
            "sha256:" + "0" * 64,
            tenant_id="tenant-a",
            run_id="run-gy-pa2",
        )

    assert caught.value.code


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


def test_human_decision_v2_five_rights_are_derived_from_typed_receipts(
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
    receipts = payload["predicate_receipts"]
    assert isinstance(receipts, list)
    evidence_receipt = next(
        receipt for receipt in receipts if receipt["predicate"] == "evidence_exposure"
    )
    evidence_receipt["provenance"] = "recomputed"

    with pytest.raises(ValueError, match="predicate provenance or rule version"):
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
    event = DiagnosticEvent.model_validate(from_canonical_bytes(fixture.store.get_bytes(event_ref)))
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
