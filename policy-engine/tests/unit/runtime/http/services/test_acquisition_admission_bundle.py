from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.routes.acquisitions import _MODEL_INPUT_USE_MUTATION_AUTHZ
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionBundleBlocked,
    AcquisitionAdmissionBundleProducer,
    AcquisitionAdmissionSigningSlot,
    model_input_use_request_resource_digest,
    require_model_input_use_bound_permission,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.model_input_successor_action import (
    MODEL_INPUT_USE_PERMISSION,
    ModelInputSuccessorActionRequest,
)
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
    AgentActionAdmissionBundle,
    AgentActionEffectBinding,
    AgentActionIntent,
)
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.integration.core_runtime import test_acquisition_admission_bundle as fixture


def _bundle_refs(store: FileSystemCAS) -> frozenset[str]:
    snapshot = store.manifest_inventory_snapshot(kind=AGENT_ACTION_ADMISSION_ARTIFACT_KIND)
    assert snapshot.verdict == "pass"
    return frozenset(str(entry.manifest.artifact_id) for entry in snapshot.entries)


def test_bundle_producer_reopens_signed_artifact_and_refuses_digest_mutation(
    tmp_path: Path,
) -> None:
    """The producer writes a signed, event-bound bundle and refuses changed resource scope."""
    store, event_log, _idempotency = fixture._harness(tmp_path)
    owner_pair = KeyPair.generate()
    admission_pair = KeyPair.generate()
    owner_signer = Ed25519Signer(owner_pair.private_key)
    admission_signer = Ed25519Signer(admission_pair.private_key)
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(owner_pair.public_key, identity=fixture.MANDATE_OWNER_REF)
    verifier.add_trusted_key(admission_pair.public_key, identity=fixture.ADMISSION_IDENTITY)

    contract_ref = fixture._persist_signed(
        store=store,
        event_log=event_log,
        payload=fixture._contract(),
        kind=fixture.DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=fixture.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=owner_signer,
        signer_identity=fixture.MANDATE_OWNER_REF,
    )
    operation = fixture._operation()
    invocation = fixture._invocation(operation)
    intent = AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND)
    binding = AgentActionEffectBinding(
        binding_id="acquisition-effect-owner-mirror",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        implementation_ref="adapter://acquisition/owner-mirror-v1",
        handler=lambda _invocation: "must-not-run-during-admission",
    )
    producer = AcquisitionAdmissionBundleProducer(
        artifact_store=store,
        event_log=event_log,
        signing_slot=AcquisitionAdmissionSigningSlot.configured(
            signer=admission_signer,
            verifier=verifier,
            signer_identity=fixture.ADMISSION_IDENTITY,
        ),
        write_context=fixture._write_context(),
    )

    receipt = producer.admit(
        delegation_contract_ref=contract_ref,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bound_permission=fixture._proof(),
        effect_binding=binding,
        admitted_at=fixture.NOW,
    )
    assert receipt.bundle.bound_resource_digest == fixture.RESOURCE_DIGEST
    assert receipt.bundle.operation_content_hash == fixture.agent_action_content_hash(operation)
    assert receipt.bundle.invocation_content_hash == fixture.agent_action_content_hash(invocation)
    assert receipt.invocation_refs == {
        fixture.agent_action_content_hash(invocation): receipt.artifact_ref
    }
    assert _bundle_refs(store) == frozenset({receipt.artifact_ref})

    reopened_store = FileSystemCAS(tmp_path / "cas").for_tenant(
        fixture.TENANT_ID,
        cell_id=fixture.CELL_ID,
    )
    reopened_control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    reopened_event_log = RuntimeDiagnosticEventLog(
        store=reopened_control_store,
        artifact_store=reopened_store,
    )
    try:
        signature = reopened_store.verify_signature(
            receipt.artifact_ref,
            verifier,
            strict_identity=True,
        )
        assert signature.status is SignatureVerificationStatus.VALID
        assert signature.signer_identity == fixture.ADMISSION_IDENTITY
        reopened_bundle = AgentActionAdmissionBundle.model_validate(
            canon.from_canonical_bytes(reopened_store.get_bytes(receipt.artifact_ref))
        )
        assert reopened_bundle == receipt.bundle
        report = reconcile_authority_ref(
            artifact_store=reopened_store,
            event_log=reopened_event_log,
            cas_ref=receipt.artifact_ref,
            expected_tenant_id=fixture.TENANT_ID,
            expected_cell_id=fixture.CELL_ID,
            expected_run_id=fixture.RUN_ID,
            expected_job_id=fixture.JOB_ID,
        )
        assert report.status == "pass"
        assert report.durable_event_id == receipt.durable_event_id
        assert len(reopened_event_log.list_events(event_id=receipt.durable_event_id)) == 1
    finally:
        reopened_control_store.close()

    events_before = tuple(event_log.list_events(limit=100))
    bundle_refs_before = _bundle_refs(store)
    with pytest.raises(AcquisitionAdmissionBundleBlocked) as blocked:
        producer.admit(
            delegation_contract_ref=contract_ref,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bound_permission=fixture._proof(resource_digest="sha256:" + "a" * 64),
            effect_binding=binding,
            admitted_at=fixture.NOW,
        )
    assert blocked.value.code == "acquisition_resource_digest_mismatch"
    assert tuple(event_log.list_events(limit=100)) == events_before
    assert _bundle_refs(store) == bundle_refs_before


def test_model_input_use_permission_binds_the_selected_activation_profile() -> None:
    """Exercise the actual route's frozen binding and its historical PA2 replay."""

    def selected_ref(kind: str, number: int, media_type: str = "application/json") -> ArtifactRef:
        return ArtifactRef.model_validate(
            {
                "artifact_id": f"sha256:{number:064x}",
                "kind": kind,
                "media_type": media_type,
                "manifest_profile_sha256": f"sha256:{number + 10:064x}",
            }
        )

    request = ModelInputSuccessorActionRequest(
        compiled_ref=selected_ref("runtime.compiled_recursive_generation_cycle", 1),
        blocked_execution_ref=selected_ref(
            "runtime.quality.generic_cycle_simulation_n5_execution", 2
        ),
        routing_report_ref=selected_ref("runtime.quality.model_input_routing_report", 3),
        activation_receipt_ref=selected_ref(
            "epoch.activated_overlay_admission_receipt", 4, "application/vnd.polisyos.epoch+json"
        ),
        observation_id="catalog-observation-selected",
        idempotency_key="one-use",
    )
    requirement = _MODEL_INPUT_USE_MUTATION_AUTHZ.requirement
    body = request.model_dump(mode="json")
    selectors = tuple(
        sorted(
            (
                field,
                '{"present":false}'
                if body[field] is None
                else fixture._canonical_selector(body[field]),
            )
            for field in type(request).model_fields
        )
    )
    body_hash = f"sha256:{sha256(request.model_dump_json().encode()).hexdigest()}"
    digest = (
        "sha256:"
        + sha256(
            fixture._canonical_selector(
                {
                    "binding_version": "runtime.authorization.resource.v1",
                    "permission": MODEL_INPUT_USE_PERMISSION.value,
                    "resource_kind": "runtime.evidence.model_input.use",
                    "authority": "request_bound",
                    "tenant_id": None,
                    "body_sha256": body_hash,
                    "query_sha256": fixture.EMPTY_QUERY_SHA256,
                    "selectors": selectors,
                    "resolved_context_sha256": None,
                }
            ).encode()
        ).hexdigest()
    )
    proof = fixture._proof(
        resource_digest=digest,
        requirement=requirement,
        canonical_selectors=selectors,
        body_sha256=body_hash,
    )
    proof = replace(
        proof,
        verification=replace(proof.verification, granted_permissions=(MODEL_INPUT_USE_PERMISSION,)),
    )
    assert require_model_input_use_bound_permission(proof, request) == digest
    assert (
        model_input_use_request_resource_digest(
            request, body_sha256=body_hash, query_sha256=fixture.EMPTY_QUERY_SHA256
        )
        == digest
    )

    sibling_ref = request.activation_receipt_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "9" * 64}
    )
    changed = request.model_copy(update={"activation_receipt_ref": sibling_ref})
    assert sibling_ref.artifact_id == request.activation_receipt_ref.artifact_id
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
    ):
        require_model_input_use_bound_permission(proof, changed)
    assert (
        model_input_use_request_resource_digest(
            changed, body_sha256=body_hash, query_sha256=fixture.EMPTY_QUERY_SHA256
        )
        != digest
    )
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
    ):
        require_model_input_use_bound_permission(fixture._proof(), request)
