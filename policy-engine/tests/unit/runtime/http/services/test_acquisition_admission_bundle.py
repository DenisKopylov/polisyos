from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.authorization import (
    BoundActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    RouteAuthorizationRequirement,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.routes.acquisitions import _MODEL_INPUT_USE_MUTATION_AUTHZ
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionBundleBlocked,
    AcquisitionAdmissionBundleProducer,
    AcquisitionAdmissionSigningSlot,
    model_input_use_request_resource_digest,
    require_candidate_experiment_reuse_bound_permission,
    require_model_input_use_bound_permission,
    require_request_bound_action_snapshot,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.model_input_successor_action import (
    MODEL_INPUT_USE_PERMISSION,
    ModelInputSuccessorActionError,
    ModelInputSuccessorActionRequest,
    ModelInputSuccessorExecutionRequest,
    NativeModelInputSuccessorActionRequest,
    _model_input_successor_ids,
    _require_native_model_input_use_budget_limits,
    unwrap_native_model_input_use_request,
)
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
    CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
    MODEL_INPUT_USE_ACTION_KIND,
    AgentActionAdmissionBundle,
    AgentActionEffectBinding,
    AgentActionIntent,
    _consume_ds20_floor,
)
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.candidate_experiment_reuse import (
    CandidateExperimentReuseActionRequest,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.model_input_successor_selection import (
    ModelInputUseActionPhase,
)
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


def _selected_ref(kind: str, number: int, media_type: str = "application/json") -> ArtifactRef:
    return ArtifactRef.model_validate(
        {
            "artifact_id": f"sha256:{number:064x}",
            "kind": kind,
            "media_type": media_type,
            "manifest_profile_sha256": f"sha256:{number + 10:064x}",
        }
    )


def _candidate_bound_proof(
    request: ModelInputSuccessorActionRequest | CandidateExperimentReuseActionRequest,
    requirement: RouteAuthorizationRequirement,
) -> tuple[BoundActionPermissionVerification, str]:
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
                    "permission": requirement.permission.value,
                    "resource_kind": requirement.resource_binding.resource_kind,
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
        verification=replace(proof.verification, granted_permissions=(requirement.permission,)),
    )
    return proof, digest


def _model_input_use_request() -> ModelInputSuccessorActionRequest:
    return ModelInputSuccessorActionRequest(
        compiled_ref=_selected_ref("runtime.compiled_recursive_generation_cycle", 1),
        blocked_execution_ref=_selected_ref(
            "runtime.quality.generic_cycle_simulation_n5_execution", 2
        ),
        routing_report_ref=_selected_ref("runtime.quality.model_input_routing_report", 3),
        activation_receipt_ref=_selected_ref(
            "epoch.activated_overlay_admission_receipt", 4, "application/vnd.polisyos.epoch+json"
        ),
        observation_id="catalog-observation-selected",
        idempotency_key="one-use",
    )


def _legacy_model_input_use_requirement() -> RouteAuthorizationRequirement:
    current = _MODEL_INPUT_USE_MUTATION_AUTHZ.requirement
    return replace(
        current,
        resource_binding=replace(
            current.resource_binding,
            selector_fields=tuple(ModelInputSuccessorActionRequest.model_fields),
            omit_absent_selector_fields=(),
        ),
    )


def test_model_input_use_permission_binds_the_selected_activation_profile() -> None:
    """Exercise the actual route's frozen binding and its historical PA2 replay."""
    request = _model_input_use_request()
    requirement = _MODEL_INPUT_USE_MUTATION_AUTHZ.requirement
    assert requirement.permission is MODEL_INPUT_USE_PERMISSION
    assert requirement.resource_binding.resource_kind == "runtime.evidence.model_input.use"
    proof, digest = _candidate_bound_proof(request, requirement)
    legacy_proof, legacy_digest = _candidate_bound_proof(
        request, _legacy_model_input_use_requirement()
    )
    assert digest == legacy_digest
    snapshot, _, identity_ok, permission_ok = _consume_ds20_floor(legacy_proof, [])
    assert snapshot is not None and identity_ok and permission_ok
    body_hash = snapshot.body_sha256
    assert require_model_input_use_bound_permission(proof, request) == digest
    assert require_model_input_use_bound_permission(legacy_proof, request) == digest
    assert (
        require_request_bound_action_snapshot(
            snapshot, action_kind=MODEL_INPUT_USE_ACTION_KIND, request=request
        )
        == digest
    )
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


def test_native_model_input_use_permission_binds_exact_allowance_and_phase() -> None:
    request = _model_input_use_request()
    direct_wire = request.model_dump(mode="json")
    native_request = NativeModelInputSuccessorActionRequest.model_validate(
        {
            **direct_wire,
            "native_use": {
                "predecessor_terminal_ref": _selected_ref(
                    "runtime_quality.acquisition_route_loop_receipt", 5
                ).model_dump(mode="json"),
                "world_checkpoint_ref": _selected_ref(
                    "runtime_quality.acquisition_candidate_world_checkpoint", 6
                ).model_dump(mode="json"),
                "fresh_budget_usd": "0.50",
            },
        }
    )
    assert native_request.model_dump(mode="json", exclude={"native_use"}) == direct_wire
    assert request.model_dump(mode="json") == direct_wire
    assert native_request.native_use.fresh_budget_usd == Decimal("0.50")
    assert native_request.model_dump(mode="json")["native_use"]["fresh_budget_usd"] == "0.50"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ModelInputSuccessorActionRequest.model_validate(native_request.model_dump(mode="json"))
    direct_proof, direct_digest = _candidate_bound_proof(
        request, _legacy_model_input_use_requirement()
    )
    direct_snapshot, _, identity_ok, permission_ok = _consume_ds20_floor(direct_proof, [])
    assert direct_snapshot is not None and identity_ok and permission_ok
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
    ):
        require_model_input_use_bound_permission(direct_proof, native_request)
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_digest_mismatch"
    ):
        require_request_bound_action_snapshot(
            direct_snapshot, action_kind=MODEL_INPUT_USE_ACTION_KIND, request=native_request
        )
    native_requirement = _MODEL_INPUT_USE_MUTATION_AUTHZ.requirement
    native_proof, native_digest = _candidate_bound_proof(native_request, native_requirement)
    snapshot, _, identity_ok, permission_ok = _consume_ds20_floor(native_proof, [])
    assert snapshot is not None and identity_ok and permission_ok
    assert native_digest != direct_digest
    assert require_model_input_use_bound_permission(native_proof, native_request) == native_digest
    decision_ref = "sha256:" + "b" * 64
    for selected_request in (request, native_request):
        wire = {
            "request": selected_request.model_dump(mode="json"),
            "decision_ref": decision_ref,
        }
        execution = ModelInputSuccessorExecutionRequest.model_validate(wire)
        assert type(execution.request) is type(selected_request)
        assert execution.model_dump(mode="json") == wire
    assert (
        require_request_bound_action_snapshot(
            snapshot, action_kind=MODEL_INPUT_USE_ACTION_KIND, request=native_request
        )
        == native_digest
    )
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_digest_mismatch"
    ):
        require_request_bound_action_snapshot(
            snapshot, action_kind=MODEL_INPUT_USE_ACTION_KIND, request=request
        )
    unprofiled = native_request.model_dump(mode="json")
    del unprofiled["native_use"]["world_checkpoint_ref"]["manifest_profile_sha256"]
    with pytest.raises(
        ValidationError, match="native_model_input_use_exact_selected_refs_required"
    ):
        NativeModelInputSuccessorActionRequest.model_validate(unprofiled)

    wrong_amount = native_request.model_dump(mode="json")
    wrong_amount["native_use"]["fresh_budget_usd"] = 0.50
    with pytest.raises(ValidationError, match="native_model_input_use_budget_amount_invalid"):
        NativeModelInputSuccessorActionRequest.model_validate(wrong_amount)
    with pytest.raises(
        ModelInputSuccessorActionError, match="native_model_input_use_budget_amount_refused"
    ):
        _require_native_model_input_use_budget_limits(
            requested=Decimal("0.51"), configured=Decimal("0.50"), global_limit=Decimal("5")
        )
    with pytest.raises(
        ModelInputSuccessorActionError, match="native_model_input_use_budget_amount_refused"
    ):
        _require_native_model_input_use_budget_limits(
            requested=Decimal("0.50"), configured=Decimal("0.50"), global_limit=Decimal("0.49")
        )
    changed_amount = native_request.model_dump(mode="json")
    changed_amount["native_use"]["fresh_budget_usd"] = "0.49"
    reselected = NativeModelInputSuccessorActionRequest.model_validate(changed_amount)
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
    ):
        require_model_input_use_bound_permission(native_proof, reselected)
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_digest_mismatch"
    ):
        require_request_bound_action_snapshot(
            snapshot, action_kind=MODEL_INPUT_USE_ACTION_KIND, request=reselected
        )
    origin = SimpleNamespace(
        tenant_id="tenant-current",
        cell_id="cell-current",
        run_id="run-current",
        source_job_id="source-original",
    )
    ids = _model_input_successor_ids(origin, native_request, "sha256:" + "a" * 64)
    changed_ids = _model_input_successor_ids(origin, reselected, "sha256:" + "a" * 64)
    assert changed_ids[0] != ids[0]
    assert changed_ids[1] != ids[1]

    phase = ModelInputUseActionPhase(
        tenant_id="tenant-current",
        cell_id="cell-current",
        run_id="run-current",
        source_job_id="source-original",
        action_job_id="model-input-use.current",
        route_id="sha256:" + "a" * 64,
        action_payload_ref=_selected_ref("runtime.control_job_payload.acquisition", 7),
        authority_decision_ref=_selected_ref("runtime_quality.agent_action_authority_decision", 8),
    )
    payload = {
        "action_kind": MODEL_INPUT_USE_ACTION_KIND,
        "job_id": phase.action_job_id,
        "tenant_id": phase.tenant_id,
        "cell_id": phase.cell_id,
        "run_id": phase.run_id,
        "route_id": phase.route_id,
        "decision_ref": str(phase.authority_decision_ref.artifact_id),
        "request": native_request.model_dump(mode="json"),
    }
    assert unwrap_native_model_input_use_request(payload, phase=phase) == native_request
    persisted_payload = {key: value for key, value in payload.items() if key != "job_id"}
    assert unwrap_native_model_input_use_request(persisted_payload, phase=phase) == native_request
    with pytest.raises(
        ModelInputSuccessorActionError, match="native_model_input_use_job_payload_scope_mismatch"
    ):
        unwrap_native_model_input_use_request(
            {**payload, "decision_ref": "sha256:" + "f" * 64}, phase=phase
        )
    with pytest.raises(
        ModelInputSuccessorActionError, match="native_model_input_use_job_payload_scope_mismatch"
    ):
        unwrap_native_model_input_use_request({**payload, "job_id": "other-job"}, phase=phase)
    with pytest.raises(
        ModelInputSuccessorActionError, match="native_model_input_use_job_payload_invalid"
    ):
        unwrap_native_model_input_use_request({**payload, "request": direct_wire}, phase=phase)


def test_candidate_reuse_permission_replays_exact_predecessor_and_distinct_resource() -> None:
    request = CandidateExperimentReuseActionRequest(
        route_id="sha256:" + "a" * 64,
        predecessor_terminal_ref=_selected_ref("runtime_quality.acquisition_route_loop_receipt", 1),
        predecessor_action_ref=_selected_ref(
            "runtime_quality.acquisition_candidate_action_receipt", 2
        ),
        source_ref=_selected_ref("runtime.quality.candidate_acquisition_source", 3),
        n5_input_ref=_selected_ref("runtime.quality.candidate_simulation_n5_input", 4),
        n5_execution_ref=_selected_ref("runtime.quality.candidate_simulation_execution", 5),
        n5_result_ref=_selected_ref("polisyos.runtime.joint_simulation_result", 6),
        policy_ref=_selected_ref("runtime_quality.candidate_unpriced_acquisition_policy", 7),
        idempotency_key="reuse-once",
    )
    requirement = RouteAuthorizationRequirement(
        permission=RuntimePermission.RUNS_LAUNCH,
        resource_binding=ResourceBindingSpec(
            source=ResourceBindingSource.REQUEST_COMPOSITE,
            resource_kind="runtime.evidence.candidate_experiment.reuse",
            selector_fields=tuple(type(request).model_fields),
            required_selector_fields=tuple(
                name for name, field in type(request).model_fields.items() if field.is_required()
            ),
        ),
    )
    proof, digest = _candidate_bound_proof(request, requirement)
    snapshot, _, identity_ok, permission_ok = _consume_ds20_floor(proof, [])
    assert snapshot is not None and identity_ok and permission_ok
    assert require_candidate_experiment_reuse_bound_permission(proof, request) == digest
    assert (
        require_request_bound_action_snapshot(
            snapshot, action_kind=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND, request=request
        )
        == digest
    )

    original = request.predecessor_terminal_ref
    sibling = original.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    assert sibling.artifact_id == original.artifact_id
    changed = request.model_copy(update={"predecessor_terminal_ref": sibling})
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
    ):
        require_candidate_experiment_reuse_bound_permission(proof, changed)
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_digest_mismatch"
    ):
        require_request_bound_action_snapshot(
            snapshot, action_kind=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND, request=changed
        )
    crossed = snapshot.model_copy(
        update={"resource_kind": "runtime.evidence.model_input.use.request_bound"}
    )
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
    ):
        require_request_bound_action_snapshot(
            crossed, action_kind=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND, request=request
        )
    with pytest.raises(
        AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
    ):
        require_candidate_experiment_reuse_bound_permission(fixture._proof(), request)
