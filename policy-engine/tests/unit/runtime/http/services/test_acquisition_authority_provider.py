"""Behavioral mirror for signed currentness refusal before acquisition admission.

The evidence and keys are generated for a local test-only CAS. Passing fixture
signatures do not establish external institutional currentness or custody.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from polisyos.core.artifacts import ArtifactID, SignatureVerificationStatus
from polisyos.core.artifacts.signing import Ed25519Signer, KeyPair
from polisyos.runtime.http import deployment_security as security
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
)
from polisyos.runtime.http.services.acquisition_authority_configuration import (
    AcquisitionAdmissionSignerConfig,
    AcquisitionAuthorityConfig,
    AcquisitionDecisionSignerConfig,
    AcquisitionMandateSlot,
)
from polisyos.runtime.quality import agent_action_authority as authority
from polisyos.runtime.quality.agent_action_authority import (
    AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
    CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
    CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
    DELEGATION_CONTRACT_ARTIFACT_KIND,
    LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
    CurrentMandateOwnerEvidence,
)
from tests.integration.core_runtime import test_acquisition_admission_bundle as fixtures
from tests.unit.runtime.http.test_runtime_deployment_security import _config_mapping

_OWNER_IDENTITY = fixtures.MANDATE_OWNER_REF
_CURRENTNESS_IDENTITY = fixtures.MANDATE_AUTHORITY_IDENTITY
_ADMISSION_IDENTITY = fixtures.ADMISSION_IDENTITY
_DECISION_IDENTITY = "service://runtime/acquisition-decision/currentness-test"
_ROUTE_ID = "sha256:" + "5" * 64


def _write_pair(tmp_path: Path, name: str) -> tuple[KeyPair, Path, Path]:
    pair = KeyPair.generate()
    private_path = tmp_path / f"{name}.private.pem"
    public_path = tmp_path / f"{name}.public.pem"
    private_path.write_bytes(pair.private_pem())
    public_path.write_bytes(pair.public_pem())
    return pair, private_path, public_path


def _closure() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=fixtures.TENANT_ID,
        cell_id=fixtures.CELL_ID,
        run_id=fixtures.RUN_ID,
        route_id=_ROUTE_ID,
        cost_basis_hash="sha256:" + "4" * 64,
        compiled_ref="sha256:" + "1" * 64,
        source_cycle=SimpleNamespace(cycle_index=1),
    )


def test_provider_persists_refusal_for_signed_noncurrent_mandate_without_admission(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A real signed but noncurrent head cannot produce an admission or call the effect."""
    monkeypatch.setattr(authority, "_utcnow", lambda: fixtures.NOW)
    store, event_log, idempotency = fixtures._harness(tmp_path)
    owner = _write_pair(tmp_path, "owner")
    current = _write_pair(tmp_path, "current")
    admission = _write_pair(tmp_path, "admission")
    decision = _write_pair(tmp_path, "decision")

    contract_ref = fixtures._persist_signed(
        store=store,
        event_log=event_log,
        payload=fixtures._contract(),
        kind=DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=Ed25519Signer(owner[0].private_key),
        signer_identity=_OWNER_IDENTITY,
    )
    current_evidence = CurrentMandateOwnerEvidence(
        evidence_id="mandate-authority.currentness-test",
        evidence_ref="institution://test-only/mandate-head",
        mandate_owner_ref=_OWNER_IDENTITY,
        authority_purpose="agent_action_delegation",
        current=False,
        effective_from=fixtures.NOW - timedelta(hours=1),
        effective_until=fixtures.NOW + timedelta(hours=1),
        delegation_rule_version_ref=authority.AGENT_ACTION_AUTHORITY_RULE_VERSION,
        evidence_signer_identity=_CURRENTNESS_IDENTITY,
        verifier_provenance="independently_reconciled",
        provenance_refs=("institution://test-only/synthetic-source",),
    )
    current_ref = fixtures._persist_signed(
        store=store,
        event_log=event_log,
        payload=current_evidence,
        kind=CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
        schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
        schema_version=CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
        signer=Ed25519Signer(current[0].private_key),
        signer_identity=_CURRENTNESS_IDENTITY,
    )

    base = security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    acquisition_config = AcquisitionAuthorityConfig(
        mandates=(
            AcquisitionMandateSlot(
                tenant_id=fixtures.TENANT_ID,
                cell_id=fixtures.CELL_ID,
                run_id=fixtures.RUN_ID,
                route_id=_ROUTE_ID,
                resource_digest=fixtures.RESOURCE_DIGEST,
                delegation_contract_ref=contract_ref,
                mandate_owner_ref=_OWNER_IDENTITY,
                delegation_public_key_path=owner[2],
                current_mandate_evidence_ref=current_ref,
                current_mandate_signer_identity=_CURRENTNESS_IDENTITY,
                current_mandate_public_key_path=current[2],
                verifier_provenance_ref="synthetic-test-only",
            ),
        ),
        admission_signer=AcquisitionAdmissionSignerConfig(
            signer_identity=_ADMISSION_IDENTITY,
            private_key_path=admission[1],
            public_key_path=admission[2],
            verifier_provenance_ref="synthetic-test-only",
        ),
        decision_signer=AcquisitionDecisionSignerConfig(
            signer_identity=_DECISION_IDENTITY,
            private_key_path=decision[1],
            public_key_path=decision[2],
            verifier_provenance_ref="synthetic-test-only",
        ),
    )
    deployment = security.build_deployment_security(
        base.model_copy(update={"acquisition_authority": acquisition_config})
    )
    current_signature = store.verify_signature(
        ArtifactID.model_validate(current_ref),
        deployment.acquisition_authority.verifier,
        strict_identity=True,
    )
    assert current_signature.status is SignatureVerificationStatus.VALID
    assert current_signature.signer_identity == _CURRENTNESS_IDENTITY
    assert store.get_manifest(current_ref).kind == CURRENT_MANDATE_OWNER_ARTIFACT_KIND
    assert store.get_manifest(contract_ref).kind == DELEGATION_CONTRACT_ARTIFACT_KIND

    from polisyos.runtime.http.services.acquisition_authority_provider import (
        ProductionAcquisitionAuthorityProvider,
    )

    provider = ProductionAcquisitionAuthorityProvider(
        deployment_security=deployment,
        artifact_store=store,
        event_log=event_log,
        idempotency_store=idempotency,
        execution_profile="governed",
    )
    closure = _closure()
    request = fixtures.ACQUISITION_REQUEST
    proof = fixtures._proof()
    effects: list[object] = []
    before_provider_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    gateway = provider.for_request(
        closure=closure,
        request=request,
        job_id=fixtures.JOB_ID,
        bound_permission=proof,
        effect_handler=effects.append,
    )

    # Provider rejected the signed-but-noncurrent source before writing any
    # admission artifact. This CAS is an isolated tmp_path fixture, not a
    # production store census.
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == before_provider_ids
    operation, invocation, intent = AcquisitionActionService._action_tuple(closure, request)
    with authority.agent_action_authority_scope(gateway):
        refusal = authority.produce_agent_action_authority_decision(
            bound_permission=proof,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
        persisted = gateway.persist_decision(refusal)

    loaded = gateway.load_persisted_decision(str(persisted.write_result.cas_ref.artifact_id))
    assert loaded.durable_event_id
    assert loaded.decision.outcome == "refused"
    assert loaded.decision.admission_bundle_ref is None
    assert "delegation_contract_not_persisted" in loaded.decision.refusal_reasons
    assert "governed_admission_bundle_missing" in loaded.decision.refusal_reasons
    assert effects == []
    new_kinds = {
        store.get_manifest(ArtifactID.model_validate(artifact_id)).kind
        for artifact_id in {str(value) for value in store.iter_artifact_ids()} - before_provider_ids
    }
    assert AGENT_ACTION_ADMISSION_ARTIFACT_KIND not in new_kinds
