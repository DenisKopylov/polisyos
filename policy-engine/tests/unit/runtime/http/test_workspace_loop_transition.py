from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread, current_thread

import pytest

from polisyos.core.contracts import ControlFailureEnvelope
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.core.security.tenant_context import clear_tenant_context, tenant_scope
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
from polisyos.pdc import OperationClass, SearchTerminalKind
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control.workspace_loop_transition import (
    RunBoundDesignRecordTenantNonReceipt,
)
from polisyos.runtime.quality.authority import ProductionLoopRunProof
from polisyos.runtime.quality.workspace import loop as workspace_loop_module
from polisyos.runtime.quality.workspace.loop import WorkspaceLoopRunProof
from polisyos.runtime.quality.workspace.s2_design_search_operation import (
    S2_DESIGN_SEARCH_OPERATION_ID,
)
from tests._helpers.control_worker import (
    dispatch_one_control_job,
    stop_embedded_control_worker,
)


def _await_terminal_job(service: ControlPlaneService, job_id: str):
    deadline = time.monotonic() + 15.0
    response = service.get_job_status(job_id)
    while response.state in {"pending", "running"} and time.monotonic() < deadline:
        if service._worker is not None:
            service._worker.dispatch_once()
        time.sleep(0.02)
        response = service.get_job_status(job_id)
    return response


def _build_slice0_catalog(tmp_path: Path):
    return build_slice0_fixture_catalog_graph(tmp_path)


def _put_tenant_owned_json_artifact(
    service: ControlPlaneService,
    payload: object,
    *,
    tenant_id: str,
    cell_id: str,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs=None,
):
    from polisyos.core.artifacts.manifest import (
        ArtifactTenantContextInfo,
        ProducerInfo,
        SchemaInfo,
    )
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec

    store = service._artifact_store  # noqa: SLF001
    ref = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            producer=ProducerInfo(
                component="polisyos.tests.workspace_loop_transition",
                version="1.0",
            ),
            inputs=inputs,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=tenant_id,
                cell_id=cell_id,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    store.record_artifact_owner(
        ref.artifact_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        writer="tests.unit.runtime.http.test_workspace_loop_transition",
    )
    return ref


def _owner_bound_data_snapshot_ref(
    service: ControlPlaneService,
    *,
    tenant_id: str,
    cell_id: str,
    params: dict[str, object],
):
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.contracts.fabric import DataSnapshot

    source_ref = _put_tenant_owned_json_artifact(
        service,
        {"source": "workspace_loop_control_fixture", "params": params},
        tenant_id=tenant_id,
        cell_id=cell_id,
        kind="fabric.retrieval_payload",
        schema_name="polisyos.fabric.RetrievalPayload",
        schema_version="1.0",
    )
    snapshot = DataSnapshot(
        data_ref=source_ref,
        stats={"source": "workspace_loop_control_fixture"},
        notes=["tenant-bound workspace-loop test input"],
    )
    return _put_tenant_owned_json_artifact(
        service,
        snapshot,
        tenant_id=tenant_id,
        cell_id=cell_id,
        kind="fabric.data_snapshot",
        schema_name="polisyos.core.DataSnapshot",
        schema_version="0.2.0",
        inputs=[input_ref_from_artifact_ref(source_ref, role="data_ref")],
    )


def _launch_owner_bound_workflow(
    runtime_api_env,
    request: WorkflowRunRequest,
):
    """Use a tenant-owned DataSnapshot and source edge for a controller positive control."""
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    principal = RuntimePrincipal(
        subject="workspace-owner-control",
        authenticated=True,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        roles=frozenset({"analyst"}),
    )
    with tenant_scope(
        None,
        tenant_id=principal.tenant_id,
        cell_id=principal.cell_id,
    ):
        snapshot_ref = _owner_bound_data_snapshot_ref(
            service,
            tenant_id=principal.tenant_id,
            cell_id=principal.cell_id,
            params=request.params,
        )
        request = request.model_copy(
            update={
                "data_source": request.data_source.model_copy(
                    update={"data_snapshot_ref": str(snapshot_ref.artifact_id)}
                )
            }
        )
        return service.launch_workflow_run(request, principal=principal)


def _layer2_s2_design_search_input() -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[4]
    proving_case = json.loads(
        (
            repository_root / "architecture/policy_design_case/layer2_first_proving_case.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (
            repository_root
            / "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
        ).read_text(encoding="utf-8")
    )
    candidate_space = manifest["candidate_space"]
    return {
        "schema_version": "policyos.policy_design_case.layer2_s2_design_search.v1",
        "case_id": str(proving_case["case_id"]),
        "intent_ref": "repo://architecture/policy_design_case/layer2_first_proving_case.json",
        "grammar_ref": "repo://src/polisyos/policy_grammar",
        "instrument_families": candidate_space["instrument_families"],
        "parameter_space": candidate_space["parameter_space"],
        "actor_ref": "actor://ua/ministry-of-economy",
        "domain": "ukrainian_msme_credit",
        "objective_refs": [f"objective://{item}" for item in proving_case["constructs"]],
        "construct_refs": [f"construct://{item}" for item in proving_case["constructs"]],
        "authority_profile_ref": "authority_profile.shadow",
        "requested_posture": "shadow",
        "generated_at": "2026-05-30T00:00:00Z",
        "rule_version_ref": "policyos.layer2.s2.design_search.v1",
    }


def _s2_artifact_census(cas_root: Path) -> dict[str, dict[str, int]]:
    """Count distinct typed blob identities across every manifest view."""
    expected = {
        "policyos.layer2_s2.design_record_v0",
        "policyos.layer2_s2.search_ledger",
        "policyos.pdc.run_bound_design_record_binding",
    }
    identities: dict[str, set[str]] = {kind: set() for kind in expected}
    manifest_views = dict.fromkeys(expected, 0)
    for path in cas_root.glob("artifacts/sha256/*/*/*.manifest.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["kind"] in identities:
            identities[manifest["kind"]].add(manifest["artifact_id"])
            manifest_views[manifest["kind"]] += 1
    return {
        "typed_artifacts": {kind: len(artifact_ids) for kind, artifact_ids in identities.items()},
        "manifest_views": manifest_views,
    }


def _s2_registry_with_fault(fault: str):
    registry = workspace_loop_module.build_workspace_operation_registry()
    operations = dict(registry.operations)
    registration = operations[S2_DESIGN_SEARCH_OPERATION_ID]
    if fault == "removed":
        operations.pop(S2_DESIGN_SEARCH_OPERATION_ID)
    elif fault == "disabled":
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"executable": False}
        )
    elif fault == "registration_id":
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"operation_id": "phase2.refine.substituted_design_search"}
        )
    elif fault == "operation_class":
        substituted_contract = registration.contract.model_copy(
            update={"operation_class": OperationClass.BIND}
        )
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={
                "operation_class": OperationClass.BIND,
                "contract": substituted_contract,
            }
        )
    elif fault == "contract_id":
        substituted_contract = registration.contract.model_copy(
            update={"operation_id": "phase2.refine.substituted_design_search"}
        )
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"contract": substituted_contract}
        )
    elif fault == "contract_class":
        substituted_contract = registration.contract.model_copy(
            update={"operation_class": OperationClass.BIND}
        )
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"contract": substituted_contract}
        )
    else:  # pragma: no cover - the parametrization is the complete mutation set
        raise AssertionError(f"unsupported registry fault: {fault}")
    return registry.model_copy(update={"operations": operations})


def _assert_surface_packet_consumes_boundary(
    progress: dict[str, object],
    *,
    expected_result: str,
) -> None:
    boundary = progress["authority_boundary"]
    assert isinstance(boundary, dict)
    assert boundary["decision_grade"] == "unsupported"
    assert boundary["posture"] == "shadow"
    assert "runtime_closeout_authority" in boundary["may_not_use_for"]
    packet = progress["authority_surface_packet"]
    assert isinstance(packet, dict)
    assert packet["boundary"] == boundary
    surfaces = packet["surfaces"]
    assert isinstance(surfaces, dict)
    assert set(surfaces) >= {
        "run",
        "artifact",
        "lineage",
        "export",
        "dashboard",
        "public_packet",
    }
    for surface_name in (
        "run",
        "artifact",
        "lineage",
        "export",
        "dashboard",
        "public_packet",
    ):
        surface = surfaces[surface_name]
        assert isinstance(surface, dict)
        assert surface["consumed_boundary_id"] == boundary["boundary_id"]
        assert surface["authority_result"] == expected_result
        assert surface["decision_grade"] == "unsupported"
        assert set(surface["may_not_use_for"]) >= set(boundary["may_not_use_for"])
    assert progress["artifact_projection"] == surfaces["artifact"]
    assert progress["lineage_projection"] == surfaces["lineage"]
    assert progress["export_projection"] == surfaces["export"]
    assert progress["public_packet"] == {
        "authority_boundary": boundary,
        "projection": surfaces["public_packet"],
    }
    artifacts_index = progress["artifacts_index"]
    assert isinstance(artifacts_index, dict)
    assert artifacts_index["authority_boundary"] == boundary["boundary_id"]
    assert artifacts_index["authority_surface_packet"] == "progress.authority_surface_packet"
    scorecard = progress["quality_scorecard"]
    assert isinstance(scorecard, dict)
    assert scorecard["authority_boundary"] == boundary
    assert scorecard["authority_surface_packet"] == packet
    assert scorecard["approval_ready"] is False
    assert scorecard["approval_state"] == "candidate_only"
    for row in scorecard["quality_gates"] + scorecard["blocking_quality_failures"]:
        assert row["authority_refs"]["authority_boundary"] == boundary["boundary_id"]


def test_workspace_loop_input_reader_rejects_missing_kind_from_valid_ref(runtime_api_env) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    typed_ref = ArtifactRef(
        artifact_id=runtime_api_env["data_snapshot_artifact_id"],
        kind="fabric.data_snapshot",
        media_type="application/json",
    )
    input_payload = typed_ref.model_dump(mode="json")
    del input_payload["kind"]
    state_payload = {"inputs": {"data_snapshot_ref": input_payload}}

    with (
        tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ),
        pytest.raises(ValueError, match="workspace_loop_input_ref_invalid"),
    ):
        service._resolved_input_artifact_payloads(state_payload)  # noqa: SLF001


def test_workspace_loop_input_reader_rejects_kind_from_another_slot(runtime_api_env) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        unrelated_ref = _put_tenant_owned_json_artifact(
            service,
            {"payload": "not a snapshot"},
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
            kind="test.workspace_loop_unrelated_input",
            schema_name="test.WorkspaceLoopUnrelatedInput",
            schema_version="1.0",
        )
        state_payload = {
            "inputs": {
                "data_snapshot_ref": unrelated_ref.model_dump(mode="json"),
            }
        }
        with pytest.raises(ValueError, match="workspace_loop_input_kind_mismatch"):
            service._resolved_input_artifact_payloads(state_payload)  # noqa: SLF001


def test_workspace_loop_input_reader_preserves_selected_profile(
    runtime_api_env, monkeypatch
) -> None:
    from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.fabric import DataSnapshot

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        source_ref = _put_tenant_owned_json_artifact(
            service,
            {"source": "selected-profile-source"},
            tenant_id=tenant_id,
            cell_id=cell_id,
            kind="fabric.retrieval_payload",
            schema_name="polisyos.fabric.RetrievalPayload",
            schema_version="1.0",
        )
        snapshot = DataSnapshot(data_ref=source_ref)
        store = service._artifact_store  # noqa: SLF001
        store.put_json(
            snapshot,
            ArtifactWriteOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="test.InvalidSnapshotSchema", version="1.0"),
                producer=None,
                tenant_context=None,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        selected_ref = _put_tenant_owned_json_artifact(
            service,
            snapshot,
            tenant_id=tenant_id,
            cell_id=cell_id,
            kind="fabric.data_snapshot",
            schema_name="polisyos.core.DataSnapshot",
            schema_version="0.2.0",
            inputs=[input_ref_from_artifact_ref(source_ref, role="data_ref")],
        )
        assert selected_ref.manifest_profile_sha256 is not None
        seen_profiles: list[str | None] = []
        original_get_manifest = store.get_manifest

        def capture_manifest(ref):
            if str(ref.artifact_id) == str(selected_ref.artifact_id):
                seen_profiles.append(ref.manifest_profile_sha256)
            return original_get_manifest(ref)

        monkeypatch.setattr(store, "get_manifest", capture_manifest)
        state_payload = {"inputs": {"data_snapshot_ref": selected_ref.model_dump(mode="json")}}
        payloads = service._resolved_input_artifact_payloads(state_payload)  # noqa: SLF001

    assert seen_profiles
    assert set(seen_profiles) == {selected_ref.manifest_profile_sha256}
    assert DataSnapshot.model_validate(payloads[str(selected_ref.artifact_id)]) == snapshot


def test_workspace_loop_input_reader_rejects_selected_ref_from_wrong_cell_even_with_params(
    runtime_api_env,
) -> None:
    from polisyos.core.artifacts import ArtifactOwnershipError

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        selected_ref = _owner_bound_data_snapshot_ref(
            service,
            tenant_id=tenant_id,
            cell_id=cell_id,
            params={"fixture_id": "wrong-cell-input-control"},
        )
    state_payload = {
        "inputs": {"data_snapshot_ref": selected_ref.model_dump(mode="json")},
        "params": {"tenant_id": tenant_id, "cell_id": cell_id},
    }

    with (
        tenant_scope(None, tenant_id=tenant_id, cell_id=f"{cell_id}-wrong"),
        pytest.raises(ArtifactOwnershipError),
    ):
        service._resolved_input_artifact_payloads(state_payload)  # noqa: SLF001


def test_workspace_loop_authority_payload_refuses_missing_active_tenant(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.security import TenantContextNotSetError

    store = FileSystemCAS(tmp_path / "cas")
    loop = workspace_loop_module.WorkspaceLoop(artifact_store=store)
    payload = {"fixture_id": "missing-scope"}
    expected_artifact_id = workspace_loop_module.gy_content_hash(payload)

    with clear_tenant_context(), pytest.raises(TenantContextNotSetError):
        loop._persist_loop_payload(  # noqa: SLF001
            payload,
            kind="test.workspace_loop_scope_refusal",
        )

    assert not store.has(expected_artifact_id)


def test_workflow_request_defaults_to_workspace_loop_transition(
    runtime_api_env, monkeypatch
) -> None:
    from polisyos.core.security import get_current_cell_id, get_current_tenant_id_or_none
    from polisyos.runtime.http.services.control import artifacts as control_artifacts

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    writer_diagnostics = []
    original_write_authority_artifact = control_artifacts.write_authority_artifact

    def trace_authority_write(store, payload, opts, **authority_fields):
        diagnostic = {
            "active_tenant": get_current_tenant_id_or_none(),
            "active_cell": get_current_cell_id(),
            "store_tenant": getattr(store, "_tenant_id", None),
            "store_cell": getattr(store, "_cell_id", None),
            "writer_tenant": authority_fields.get("tenant_id"),
            "writer_cell": authority_fields.get("cell_id"),
            "closure_tenant": authority_fields.get("same_input_closure", {}).get("tenant_id"),
            "closure_cell": authority_fields.get("same_input_closure", {}).get("cell_id"),
        }
        try:
            result = original_write_authority_artifact(store, payload, opts, **authority_fields)
        except Exception as exc:
            diagnostic["error"] = f"{type(exc).__name__}: {exc}"
            writer_diagnostics.append(diagnostic)
            raise
        writer_diagnostics.append(diagnostic)
        return result

    monkeypatch.setattr(control_artifacts, "write_authority_artifact", trace_authority_write)
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        params={"slice0_fixture_id": "ua_msme_credit_worldbank_measurement"},
    )

    launch = _launch_owner_bound_workflow(runtime_api_env, request)
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "completed", (
        f"{response.progress.get('failure', {}).get('message')}; "
        f"authority_writes={writer_diagnostics!r}"
    )
    assert response.progress["authority_path"] == "workspace_loop"
    assert response.progress["authority_result"] == "verifier_stamped"
    assert response.progress["search_exit_contract_ref"].startswith("sha256:")
    assert response.progress["production_loop_run_proof_ref"].startswith("sha256:")
    assert response.approval_projection.eligible is False

    proof = WorkspaceLoopRunProof.model_validate(response.progress["production_loop_run_proof"])
    assert proof.job_id == launch.job_id
    assert proof.run_id == launch.run_id
    assert proof.endpoint == "/api/v1/control/runs"
    assert proof.legacy_path_disposition == "routed_to_workspace_loop"
    assert proof.output_search_exit_contract_ref == response.progress["search_exit_contract_ref"]
    assert "control_store_current_execution_completed_job_record" in proof.surface_reads_checked
    assert "served_control_job_status_not_established" in proof.surface_reads_checked
    assert "runs_readback" not in proof.surface_reads_checked
    assert proof.surface_readbacks
    readback = proof.surface_readbacks[0]
    assert readback["surface"] == "control_plane_store"
    assert readback["read_method"] == "ControlPlaneStore.current_execution_completed_job_record"
    assert readback["requested_endpoint"] == "/api/v1/control/runs"
    assert readback["observed_job_state"] == "completed"
    assert (
        readback["observed_search_exit_contract_ref"]
        == response.progress["search_exit_contract_ref"]
    )
    assert readback["matched_search_exit_contract_ref"] is True

    exit_payload = response.progress["search_exit_contract"]
    assert isinstance(exit_payload, dict)
    workspace_contract_ref = exit_payload["workspace_contract_ref"]
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    store = service._artifact_store  # noqa: SLF001
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        workspace_manifest = store.get_manifest(workspace_contract_ref)
        assert workspace_manifest.tenant_context is not None
        assert workspace_manifest.tenant_context.tenant_id == tenant_id
        assert workspace_manifest.tenant_context.cell_id == cell_id
        assert workspace_manifest.same_input_closure is not None
        assert workspace_manifest.same_input_closure.tenant_id == tenant_id
        assert workspace_manifest.same_input_closure.cell_id == cell_id
        assert workspace_manifest.authority is not None

        authority_envelope = json.loads(
            store.get_bytes(workspace_manifest.authority.authority_envelope_ref)
        )
        assert authority_envelope["tenant_id"] == tenant_id
        assert authority_envelope["cell_id"] == cell_id
        attestation_ref = authority_envelope["attestation_ref"]
        attestation_manifest = store.get_manifest(attestation_ref)
        assert attestation_manifest.tenant_context is not None
        assert attestation_manifest.tenant_context.tenant_id == tenant_id
        assert attestation_manifest.tenant_context.cell_id == cell_id
        assert store.verify(attestation_ref).ok
        attestation = json.loads(store.get_bytes(attestation_ref))

    assert attestation["environment_identity"]["tenant_id"] == tenant_id
    assert attestation["environment_identity"]["cell_id"] == cell_id
    assert any(
        material["key"] == "tenant_identity" and material["ref"] == tenant_id
        for material in attestation["observed_materials"]
    )


def test_control_store_job_status_read_does_not_write_while_worker_finalizes_proof(
    runtime_api_env,
    monkeypatch,
) -> None:
    """A status reader observes completion without borrowing the worker's custody."""
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    finalizer_entered = Event()
    release_finalizer = Event()
    worker_done = Event()
    worker_errors: list[BaseException] = []
    finalize = service._finalize_workspace_loop_run_proof

    def paused_worker_finalizer(*, job_id: str, endpoint: str) -> None:
        if current_thread() is dispatch_thread:
            finalizer_entered.set()
            if not release_finalizer.wait(15):
                raise AssertionError("reader did not release the worker finalizer")
        finalize(job_id=job_id, endpoint=endpoint)

    def dispatch() -> None:
        try:
            assert service._worker is not None
            assert service._worker.dispatch_once()
        except BaseException as exc:
            worker_errors.append(exc)
        finally:
            worker_done.set()

    dispatch_thread = Thread(target=dispatch, name="proof-finalization-worker")
    monkeypatch.setattr(service, "_finalize_workspace_loop_run_proof", paused_worker_finalizer)
    launch = _launch_owner_bound_workflow(
        runtime_api_env,
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            params={"slice0_fixture_id": "tourism_local_development_ceiling_probe"},
        ),
    )
    dispatch_thread.start()
    try:
        assert finalizer_entered.wait(15), (
            "worker never reached post-completion finalization; "
            f"worker_done={worker_done.is_set()}, errors={worker_errors!r}, "
            f"job={service._control_store.get_job(launch.job_id)!r}"
        )
        before = service._control_store.get_job(launch.job_id)
        assert before is not None and before.state == "completed"
        with clear_tenant_context():
            response = service.get_job_status(launch.job_id)
        after = service._control_store.get_job(launch.job_id)
        assert after is not None
        assert response.state == "completed"
        assert response.approval_projection.eligible is False
        assert after.progress == before.progress
        pending_proof = ProductionLoopRunProof.model_validate(
            response.progress["production_loop_run_proof"]
        )
        assert "control_store_current_execution_completed_job_record" not in (
            pending_proof.surface_reads_checked
        )
        assert "served_control_job_status_not_established" in pending_proof.surface_reads_checked
        assert not pending_proof.surface_readbacks
        assert not worker_done.is_set()
    finally:
        release_finalizer.set()
        dispatch_thread.join(15)
    assert not dispatch_thread.is_alive()
    assert not worker_errors
    final = service.get_job_status(launch.job_id)
    final_proof = ProductionLoopRunProof.model_validate(final.progress["production_loop_run_proof"])
    assert final_proof.control_store_state_transitions == ["pending", "running", "completed"]
    assert "served_control_job_status_not_established" in final_proof.surface_reads_checked
    assert final_proof.surface_readbacks[0]["surface"] == "control_plane_store"
    assert (
        final_proof.surface_readbacks[0]["read_method"]
        == "ControlPlaneStore.current_execution_completed_job_record"
    )
    assert final_proof.surface_readbacks[0]["observed_job_state"] == "completed"
    assert final_proof.surface_readbacks[0]["matched_search_exit_contract_ref"] is True


def test_unclaimed_candidate_worker_carries_limitation_to_served_readback(
    runtime_api_env,
    monkeypatch,
) -> None:
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.tenant_context import (
        clear_tenant_context,
        get_current_access_scope_or_none,
        get_current_cell_id,
        get_current_tenant_id_or_none,
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )
    from polisyos.pdc import (
        AuthorityBoundary,
        assert_ring2_verifier_provenance,
        gy_content_hash,
    )
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _ControlJobExecutionScopeLimitation,
    )
    from polisyos.runtime.quality.authority import authority_surface_decision
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    if service._worker is not None:
        service._worker.stop()
    # This controller/worker witness starts from genuinely unclaimed candidate
    # input. It does not waive HTTP authentication or tenant-owned CAS access,
    # and does not establish the R1 owner-bound N4 -> N5 -> S8 capability.
    with clear_tenant_context():
        input_ref = service._put_json_artifact(  # noqa: SLF001
            {"root": True, "candidate_input": "unclaimed-r14-control"},
            kind="test.unclaimed_candidate_input",
            schema_name="test.UnclaimedCandidateInput",
        )
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": input_ref},
                params={
                    "slice0_fixture_id": "ua_msme_credit_worldbank_measurement",
                    "tenant_id": "tenant-forged-payload",
                    "cell_id": "cell-forged-payload",
                    "runtime_identity": {
                        "tenant_id": "tenant-runtime-forged",
                        "cell_id": "cell-runtime-forged",
                    },
                },
            ),
            principal=RuntimePrincipal(),
        )
    job_id = launch.job_id

    reads: list[tuple[str | None, str | None, object]] = []
    original_load = service._load_payload_ref  # noqa: SLF001

    def observe_worker_scope(ref: str, *, kind: str):
        reads.append(
            (
                get_current_tenant_id_or_none(),
                get_current_cell_id(),
                get_current_access_scope_or_none(),
            )
        )
        return original_load(ref, kind=kind)

    monkeypatch.setattr(service, "_load_payload_ref", observe_worker_scope)
    transition_calls: list[dict[str, object]] = []
    original_transition = service._execute_workflow_control_transition  # noqa: SLF001

    def observe_real_transition(state_payload, checkpoint_policy, **kwargs):
        transition_calls.append(dict(state_payload))
        return original_transition(state_payload, checkpoint_policy, **kwargs)

    monkeypatch.setattr(
        service,
        "_execute_workflow_control_transition",
        observe_real_transition,
    )
    unadmitted_contracts: list[dict[str, object]] = []
    original_output_admission = service._limit_workspace_contract_authority_for_execution_scope  # noqa: SLF001

    def observe_output_admission(contract, *, execution_scope_status):
        unadmitted_contracts.append(contract.model_dump(mode="json"))
        return original_output_admission(
            contract,
            execution_scope_status=execution_scope_status,
        )

    monkeypatch.setattr(
        service,
        "_limit_workspace_contract_authority_for_execution_scope",
        observe_output_admission,
    )
    poison = AccessScope.for_service(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        spiffe_id="spiffe://r14/unknown-workflow-poison",
    )
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        token = set_current_access_scope(poison)
        try:
            dispatched_job_id = dispatch_one_control_job(
                store=service._control_store,  # noqa: SLF001
                handler=service._process_control_job,  # noqa: SLF001
                expected_job_id=job_id,
            )
        finally:
            reset_current_access_scope(token)
    assert dispatched_job_id == job_id

    completed = service.get_job_status(job_id)
    assert completed.state == "completed"
    assert transition_calls
    assert not {"tenant_id", "cell_id", "runtime_identity"}.intersection(
        transition_calls[0]["params"]
    )
    assert reads and all(
        tenant is None and cell is None and scope is None for tenant, cell, scope in reads
    )
    assert completed.progress["execution_scope_status"] == "not_established"
    assert completed.progress["execution_scope_limitation"] == {
        "schema_version": "polisyos.runtime.control_execution_scope_limitation.v1",
        "status": "not_established",
        "code": "control_job_execution_scope_not_established",
        "candidate_work": "unclaimed_only",
        "authority": "withheld",
    }
    assert completed.progress["authority_result"] == "candidate_only"
    assert completed.approval_projection.eligible is False
    contract_ref = completed.progress["search_exit_contract_ref"]
    assert contract_ref.startswith("sha256:")
    stored_contract = from_canonical_bytes(service._artifact_store.get_bytes(contract_ref))  # noqa: SLF001
    contract_payload = completed.progress["search_exit_contract"]
    assert stored_contract == contract_payload
    assert_ring2_verifier_provenance(
        workspace_loop_module.WorkspaceSearchExitContract.model_validate(stored_contract),
        context={"writer_role": "workspace_candidate_output"},
    )
    assert stored_contract["decision_grade"] == "unsupported"
    assert stored_contract["authority_derivation_traces"] == []
    assert stored_contract["authority_boundary"] is None
    for envelope in stored_contract["artifact_envelopes"]:
        assert envelope["certified_operation_envelope"] is None
        assert envelope["authority_boundary"] is None
        assert envelope["verification"]["latest_promotion_result"] is None

    limited_decision = authority_surface_decision(
        stored_contract,
        surface="run",
        purpose="estimate:ua_msme_credit_worldbank_measurement",
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    assert limited_decision.status == "blocked"
    assert limited_decision.reason == "authority_boundary_missing"
    limited_cas_decision = authority_surface_decision(
        None,
        surface="run",
        purpose="estimate:ua_msme_credit_worldbank_measurement",
        artifact_store=service._artifact_store,  # noqa: SLF001
        artifact_id=contract_ref,
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    assert limited_cas_decision.status == "blocked"
    assert limited_cas_decision.reason == "authority_boundary_missing"
    assert limited_cas_decision.integrity_status == "verified"
    assert "cas_integrity" in limited_cas_decision.composed_gate_inputs

    # Removal probe: restore the real pre-admission contract while preserving
    # the served unknown-scope marker. The same consumer must expose the precise
    # boundary this owner gate removes.
    assert len(unadmitted_contracts) == 1
    unadmitted_contract = unadmitted_contracts[0]
    assert unadmitted_contract["authority_boundary"] is not None
    unadmitted_with_marker = {
        **unadmitted_contract,
        "execution_scope_status": "not_established",
        "execution_scope_limitation": completed.progress["execution_scope_limitation"],
    }
    removal_probe = authority_surface_decision(
        unadmitted_with_marker,
        surface="run",
        purpose="estimate:ua_msme_credit_worldbank_measurement",
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    assert removal_probe.status == "allowed"

    served_readback = runtime_api_env["client"].get(f"/api/v1/control/jobs/{job_id}")
    assert served_readback.status_code == 200, served_readback.text
    served_progress = served_readback.json()["progress"]
    assert (
        served_progress["execution_scope_limitation"]
        == completed.progress["execution_scope_limitation"]
    )
    assert served_progress["authority_result"] == "candidate_only"
    assert served_progress["search_exit_contract"] == stored_contract
    typed_limitation = _ControlJobExecutionScopeLimitation.model_validate(
        served_progress["execution_scope_limitation"]
    )
    assert typed_limitation.status == "not_established"
    assert typed_limitation.authority == "withheld"

    proof = ProductionLoopRunProof.model_validate(completed.progress["production_loop_run_proof"])
    assert proof.output_replay_proof_ref is not None
    output_refs = {
        *proof.output_cas_refs,
        proof.output_search_exit_contract_ref,
        *(completed.progress.get("authority_derivation_trace_refs") or []),
        *(completed.progress.get("artifacts_index", {}).get("output_artifact_payload_refs") or []),
        completed.progress["production_loop_run_proof_ref"],
        stored_contract["workspace_contract_ref"],
    }
    if proof.output_replay_proof_ref is not None:
        output_refs.add(proof.output_replay_proof_ref)
    assert output_refs
    assert not completed.progress.get("authority_derivation_trace_refs")
    assert proof.output_search_exit_contract_ref == contract_ref
    assert completed.progress["search_ledger_ref"] in proof.output_cas_refs
    assert proof.output_replay_proof_ref in proof.output_cas_refs

    # Census the full owner-emitted artifact family. No typed boundary may
    # survive in its contract or ledger; replay/run proofs use the same refs.
    output_payload_refs = set(
        completed.progress.get("artifacts_index", {}).get("output_artifact_payload_refs", [])
    )
    workspace_contract_ref = stored_contract["workspace_contract_ref"]
    owner_output_refs = output_refs - output_payload_refs - {workspace_contract_ref}
    persisted_output_payloads = {
        artifact_ref: from_canonical_bytes(service._artifact_store.get_bytes(artifact_ref))  # noqa: SLF001
        for artifact_ref in owner_output_refs
    }
    assert (
        persisted_output_payloads[completed.progress["search_ledger_ref"]]
        == (stored_contract["search_ledger"])
    )

    def collect_authority_boundaries(value):
        if isinstance(value, dict):
            if set(AuthorityBoundary.model_fields).issubset(value):
                yield value
                return
            for item in value.values():
                yield from collect_authority_boundaries(item)
        elif isinstance(value, list):
            for item in value:
                yield from collect_authority_boundaries(item)

    emitted_boundaries = [
        boundary_payload
        for payload in persisted_output_payloads.values()
        for boundary_payload in collect_authority_boundaries(payload)
    ]
    assert not emitted_boundaries
    for payload in persisted_output_payloads.values():
        decision = authority_surface_decision(
            payload,
            surface="run",
            purpose="estimate:ua_msme_credit_worldbank_measurement",
            enforce_time_source=False,
            enforce_s12=False,
            enforce_candidate_firewall=False,
        )
        assert decision.status != "allowed"

    assert persisted_output_payloads[contract_ref] == stored_contract
    assert (
        persisted_output_payloads[proof.output_replay_proof_ref]["output_hash"]
        == (completed.progress["outcome_replay_proof"]["output_hash"])
    )
    assert persisted_output_payloads[proof.output_replay_proof_ref]["output_hash"] == (
        gy_content_hash(stored_contract)
    )
    persisted_run_proof = ProductionLoopRunProof.model_validate(
        persisted_output_payloads[completed.progress["production_loop_run_proof_ref"]]
    )
    assert persisted_run_proof.output_cas_refs == proof.output_cas_refs

    runtime_container = runtime_api_env["app"].state.runtime_container
    artifact_client, artifact_cell, artifact_provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=runtime_container.runtime_api_context,
            control_service=service,
            decision_validity_service=service._decision_validity_service,
            claim_ledger_owner=service._epoch_claim_lifecycle_bridge.claim_owner,
            epoch_claim_lifecycle_bridge=service._epoch_claim_lifecycle_bridge,
        ),
    )
    for tenant_id in (runtime_api_env["tenant_a"], runtime_api_env["tenant_b"]):
        bearer = _fixture_bearer(f"r14-unscoped-output-{tenant_id}")
        artifact_provider.put_claim(
            bearer,
            _claims(
                tenant_id=tenant_id,
                cell_id=artifact_cell.cell_id,
                jti=f"jwt-r14-unscoped-output-{tenant_id}",
            ),
        )
        headers = {
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": tenant_id,
        }
        for artifact_ref in sorted(output_refs):
            artifact_response = artifact_client.get(
                f"/api/v1/artifacts/{artifact_ref}",
                headers=headers,
            )
            assert artifact_response.status_code == 403, artifact_response.text
            assert artifact_response.json()["code"] in {
                "artifact_tenant_unscoped",
                "artifact_tenant_mismatch",
            }
    artifact_client.close()

    admission = service._control_store.get_job_created_event_payload(job_id)  # noqa: SLF001
    assert admission["execution_scope"]["status"] == "not_established"
    diagnostic = next(
        item
        for item in service._control_store.list_diagnostic_events(job_id=job_id)  # noqa: SLF001
        if item.event.phase == "job_execution"
        and item.event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
    )
    assert diagnostic.event.tenant_id == "tenant-unknown"
    assert diagnostic.event.cell_id == "cell-unknown"
    assert diagnostic.payload_inline is not None
    assert diagnostic.payload_inline["job_kind"] == "workflow_run"
    assert diagnostic.payload_inline["execution_scope"]["status"] == "not_established"
    assert diagnostic.payload_inline["execution_scope"]["source"] == "job_admission"


def test_phase2_run_context_uses_worker_tenant_without_access_scope(tmp_path) -> None:
    """Workspace RunContext carries admitted storage identity, never ambient auth."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
    from polisyos.core.security.tenant_context import (
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )

    loop = workspace_loop_module.WorkspaceLoop(
        artifact_store=FileSystemCAS(tmp_path / "workspace-cas")
    )
    poisoned_access = AccessScope(
        tenant_id="tenant-poison",
        cell_id="cell-poison",
        principal_type="user",
        user_sub="poisoned-request",
        roles=frozenset({PolicyOSRole.ADMIN}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
    )
    with tenant_scope(None, tenant_id="tenant-admitted", cell_id="cell-admitted"):
        token = set_current_access_scope(poisoned_access)
        try:
            execution_context, _ = loop._phase2_context(workspace_id="admitted-scope")
        finally:
            reset_current_access_scope(token)

    assert execution_context.run.tenant_id == "tenant-admitted"
    assert execution_context.run.cell_id == "cell-admitted"
    assert execution_context.run.access_scope is None


def test_http_control_route_persists_production_and_replay_proofs(
    runtime_api_env, monkeypatch
) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import (
        get_current_access_scope_or_none,
        get_current_cell_id,
        get_current_tenant_id_or_none,
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.quality.authority import authority_surface_decision
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    runtime_container = runtime_api_env["app"].state.runtime_container
    bearer = _fixture_bearer("r14-served-workflow-custody")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=runtime_container.runtime_api_context,
            control_service=service,
            decision_validity_service=service._decision_validity_service,
            claim_ledger_owner=service._epoch_claim_lifecycle_bridge.claim_owner,
            epoch_claim_lifecycle_bridge=service._epoch_claim_lifecycle_bridge,
        ),
    )
    admitted_tenant = runtime_api_env["tenant_b"]
    admitted_cell = cell.cell_id
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=admitted_tenant,
            cell_id=admitted_cell,
            jti="jwt-r14-served-workflow-custody",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    service._artifact_store.record_artifact_owner(
        runtime_api_env["root_artifact_id"],
        tenant_id=admitted_tenant,
        cell_id=admitted_cell,
        writer="test_http_control_route_persists_production_and_replay_proofs",
    )
    stop_embedded_control_worker(service)
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": admitted_tenant,
    }
    launch_response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {
                "data_snapshot_ref": runtime_api_env["root_artifact_id"],
            },
            "params": {
                "slice0_fixture_id": "ua_msme_credit_worldbank_measurement",
            },
        },
        headers={**headers, "X-Request-ID": "gy-l-http-route-proof"},
    )
    assert launch_response.status_code == 200, launch_response.text
    launch = launch_response.json()
    job = service._control_store.get_job(str(launch["job_id"]))
    assert job is not None
    reads: list[tuple[str, str | None, str | None, object]] = []
    capture = {"active": True}
    original_load_payload = service._load_payload_ref

    def capture_job_reads(ref: str, *, kind: str):
        if capture["active"] and ref in {job.payload_ref, job.capability_manifest_ref}:
            reads.append(
                (
                    ref,
                    get_current_tenant_id_or_none(),
                    get_current_cell_id(),
                    get_current_access_scope_or_none(),
                )
            )
        return original_load_payload(ref, kind=kind)

    monkeypatch.setattr(service, "_load_payload_ref", capture_job_reads)
    poison = AccessScope.for_service(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=admitted_cell,
        spiffe_id="spiffe://r14/poisoned-dispatch-context",
    )

    access_token = set_current_access_scope(poison)
    try:
        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=admitted_cell,
        ):
            dispatched_job_id = dispatch_one_control_job(
                store=service._control_store,  # noqa: SLF001
                handler=service._process_control_job,  # noqa: SLF001
                expected_job_id=str(launch["job_id"]),
            )
    finally:
        reset_current_access_scope(access_token)
    assert dispatched_job_id == launch["job_id"]
    readback_response = client.get(
        f"/api/v1/control/jobs/{launch['job_id']}",
        headers={**headers, "X-Request-ID": "gy-l-http-readback-proof"},
    )
    capture["active"] = False
    assert readback_response.status_code == 200
    progress = readback_response.json()["progress"]
    proof = ProductionLoopRunProof.model_validate(progress["production_loop_run_proof"])

    assert proof.job_id == launch["job_id"]
    assert proof.run_id == launch["run_id"]
    assert proof.http_request_id == "gy-l-http-route-proof"
    assert proof.control_store_state_transitions == ["pending", "running", "completed"]
    assert proof.output_replay_proof_ref.startswith("sha256:")
    assert progress["authority_result"] == "verifier_stamped"
    assert progress["search_exit_contract"]["authority_boundary"]["authoritative_for"] != ["none"]
    assert (
        "control_job_execution_scope_not_established"
        not in progress["search_exit_contract"]["authority_boundary"]["known_limits"]
    )
    estimate_decision = authority_surface_decision(
        progress,
        surface="run",
        purpose="estimate:ua_msme_credit_worldbank_measurement",
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    closeout_decision = authority_surface_decision(
        progress,
        surface="run",
        purpose="runtime_closeout_authority",
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    assert estimate_decision.status == "allowed"
    # This direct reader is outside the authenticated HTTP request; supply the
    # same admitted storage owner rather than relying on a leaked request scope.
    with tenant_scope(None, tenant_id=admitted_tenant, cell_id=admitted_cell):
        estimate_cas_decision = authority_surface_decision(
            None,
            surface="run",
            purpose="estimate:ua_msme_credit_worldbank_measurement",
            artifact_store=service._artifact_store,  # noqa: SLF001
            artifact_id=progress["search_exit_contract_ref"],
            enforce_time_source=False,
            enforce_s12=False,
            enforce_candidate_firewall=False,
        )
    assert estimate_cas_decision.status == "allowed"
    assert estimate_cas_decision.integrity_status == "verified"
    assert closeout_decision.status == "downgraded"
    assert closeout_decision.reason == "authority_purpose_not_authorized"
    assert "outcome_replay_proof_ref" in proof.artifacts_index_refs
    assert progress["outcome_replay_proof"]["replay_levels"] == ["A", "B", "C"]
    assert progress["outcome_replay_proof"]["output_hash"].startswith("sha256:")
    assert progress["outcome_replay_proof"]["input_hashes"]
    assert {row[0] for row in reads} >= {job.payload_ref, job.capability_manifest_ref}
    assert all(
        tenant_id == admitted_tenant and cell_id == admitted_cell and access_scope is None
        for _, tenant_id, cell_id, access_scope in reads
    )
    diagnostics = service._control_store.list_diagnostic_events(job_id=job.job_id)
    service_diagnostics = [
        item for item in diagnostics if item.event.event_source == "polisyos.runtime.control"
    ]
    worker_diagnostics = [
        item for item in diagnostics if item.event.event_source == "polisyos.runtime.worker"
    ]
    assert service_diagnostics
    assert worker_diagnostics
    assert all(
        item.event.tenant_id == admitted_tenant and item.event.cell_id == admitted_cell
        for item in service_diagnostics
    )
    assert all(
        item.event.tenant_id == "tenant-unknown" and item.event.cell_id == "cell-unknown"
        for item in worker_diagnostics
    )
    client.close()


def test_s2_design_search_real_http_worker_closes_run_bound_case(
    runtime_api_env,
) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import (
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    runtime_container = runtime_api_env["app"].state.runtime_container
    bearer = _fixture_bearer("r14-s2-admitted-scope-candidate")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=runtime_container.runtime_api_context,
            control_service=service,
            decision_validity_service=service._decision_validity_service,
            claim_ledger_owner=service._epoch_claim_lifecycle_bridge.claim_owner,
            epoch_claim_lifecycle_bridge=service._epoch_claim_lifecycle_bridge,
        ),
    )
    admitted_tenant = runtime_api_env["tenant_b"]
    admitted_cell = cell.cell_id
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=admitted_tenant,
            cell_id=admitted_cell,
            jti="jwt-r14-s2-admitted-scope-candidate",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    service._artifact_store.record_artifact_owner(
        runtime_api_env["root_artifact_id"],
        tenant_id=admitted_tenant,
        cell_id=admitted_cell,
        writer="test_s2_design_search_real_http_worker_closes_run_bound_case",
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": admitted_tenant,
    }
    search_input = _layer2_s2_design_search_input()
    before = _s2_artifact_census(Path(runtime_api_env["cas_root"]))
    stop_embedded_control_worker(service)

    launch_response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            "params": {
                "control_plane_transition": "workspace_loop",
                "workspace_operation_id": "phase2.refine.layer2_s2_design_search",
                "layer2_s2_design_search_input": search_input,
            },
        },
        headers=headers,
    )
    assert launch_response.status_code == 200, launch_response.text
    launch = launch_response.json()
    poison = AccessScope.for_service(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        spiffe_id="spiffe://r14/s2-poisoned-dispatch-context",
    )
    token = set_current_access_scope(poison)
    try:
        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ):
            dispatched_job_id = dispatch_one_control_job(
                store=service._control_store,  # noqa: SLF001
                handler=service._process_control_job,  # noqa: SLF001
                expected_job_id=str(launch["job_id"]),
            )
    finally:
        reset_current_access_scope(token)
    assert dispatched_job_id == launch["job_id"]
    job_response = client.get(f"/api/v1/control/jobs/{launch['job_id']}", headers=headers)

    assert job_response.status_code == 200
    job = job_response.json()
    assert job["state"] == "completed", job
    assert job["progress"]["workspace_operation_id"] == ("phase2.refine.layer2_s2_design_search")
    assert job["progress"]["authority_result"] == "candidate_only"
    assert job["progress"]["approval_projection"]["eligible"] is False
    after = _s2_artifact_census(Path(runtime_api_env["cas_root"]))
    assert {
        kind: after["typed_artifacts"][kind] - before["typed_artifacts"][kind]
        for kind in before["typed_artifacts"]
    } == {
        "policyos.layer2_s2.design_record_v0": 1,
        "policyos.layer2_s2.search_ledger": 1,
        "policyos.pdc.run_bound_design_record_binding": 1,
    }
    assert all(
        after["manifest_views"][kind] > before["manifest_views"][kind]
        for kind in before["typed_artifacts"]
    )

    paper_response = client.get(f"/api/v1/runs/{launch['run_id']}/paper", headers=headers)
    assert paper_response.status_code == 200, paper_response.text
    packet = paper_response.json()
    binding = packet["case_record"]["design_record_binding"]
    assert packet["case_record"]["availability"] == ("record_available_authority_abstaining")
    assert binding["run_id"] == launch["run_id"]
    assert binding["tenant_id"] == admitted_tenant
    assert binding["cell_id"] == admitted_cell
    assert binding["case_id"] == search_input["case_id"]
    assert packet["run"]["tenant_id"] == admitted_tenant
    assert packet["run"]["cell_id"] == admitted_cell
    assert packet["source"]["manifest_ref"] == job["progress"]["manifest_ref"]
    client.close()


def test_s2_unclaimed_controller_worker_tenantless_refuses_with_zero_pdc_writes(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = runtime_api_env["client"]
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    producer_calls: list[object] = []

    def _producer_must_not_run(value: object):
        producer_calls.append(value)
        raise AssertionError("S2 producer ran without tenant authority")

    monkeypatch.setattr(
        "polisyos.runtime.quality.workspace.s2_design_search_operation.run_s2_shadow_design_loop",
        _producer_must_not_run,
    )
    before = _s2_artifact_census(Path(runtime_api_env["cas_root"]))
    stop_embedded_control_worker(service)
    # Reach the S2 owner gate through genuinely unclaimed controller input.
    # Anonymous HTTP intake and tenant-owned artifact access remain protected.
    with clear_tenant_context():
        input_ref = service._put_json_artifact(  # noqa: SLF001
            {"candidate_input": "unclaimed-s2-owner-negative"},
            kind="test.unclaimed_s2_input",
            schema_name="test.UnclaimedS2Input",
        )
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": input_ref},
                params={
                    "control_plane_transition": "workspace_loop",
                    "workspace_operation_id": "phase2.refine.layer2_s2_design_search",
                    "layer2_s2_design_search_input": _layer2_s2_design_search_input(),
                    "tenant_id": runtime_api_env["tenant_a"],
                    "cell_id": runtime_api_env["cell_a"],
                },
            ),
            principal=RuntimePrincipal(),
        ).model_dump(mode="json")
    assert service._worker is not None
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.tenant_context import (
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )

    poison = AccessScope.for_service(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        spiffe_id="spiffe://r14/s2-unknown-scope-poison",
    )
    token = set_current_access_scope(poison)
    try:
        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ):
            dispatched_job_id = dispatch_one_control_job(
                store=service._control_store,  # noqa: SLF001
                handler=service._process_control_job,  # noqa: SLF001
                expected_job_id=str(launch["job_id"]),
            )
    finally:
        reset_current_access_scope(token)
    assert dispatched_job_id == launch["job_id"]
    response = service.get_job_status(str(launch["job_id"]))

    assert response.state == "failed"
    assert response.runtime_state == "blocked"
    assert response.progress["authority_result"] == "repair_required"
    nonreceipt = RunBoundDesignRecordTenantNonReceipt.model_validate(
        response.progress["run_bound_design_record_nonreceipt"]
    )
    assert nonreceipt == RunBoundDesignRecordTenantNonReceipt()
    assert response.failure is not None
    expected_failure = ControlFailureEnvelope(
        code="run_bound_design_record_tenant_scope_missing",
        layer="pdc.gy",
        phase="s2_design_search_persist",
        message=("Run-bound DesignRecord persistence requires a verified ambient tenant scope."),
        retryable=False,
        next_action=(
            "Re-launch under an authenticated principal with a verified tenant scope; "
            "tenant_id is not caller-supplied."
        ),
        run_id=launch["run_id"],
        job_id=launch["job_id"],
        artifact_refs={},
    )
    assert type(response.failure) is ControlFailureEnvelope
    assert response.failure.model_dump(exclude={"operator_diagnostic"}) == (
        expected_failure.model_dump(exclude={"operator_diagnostic"})
    )
    assert response.failure.code == "run_bound_design_record_tenant_scope_missing"
    assert response.failure.layer == "pdc.gy"
    assert response.failure.phase == "s2_design_search_persist"
    assert response.failure.artifact_refs == {}
    assert producer_calls == []
    assert _s2_artifact_census(Path(runtime_api_env["cas_root"])) == before
    served = client.get(f"/api/v1/control/jobs/{launch['job_id']}")
    assert served.status_code == 200, served.text
    assert served.json()["failure"]["code"] == expected_failure.code
    rendered_progress = json.dumps(response.progress, sort_keys=True)
    assert runtime_api_env["tenant_a"] not in rendered_progress
    assert runtime_api_env["cell_a"] not in rendered_progress


@pytest.mark.parametrize(
    "registry_fault",
    [
        "removed",
        "disabled",
        "registration_id",
        "operation_class",
        "contract_id",
        "contract_class",
    ],
)
def test_s2_design_search_real_http_worker_refuses_untrusted_registry_rows_before_writes(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    registry_fault: str,
) -> None:
    client = runtime_api_env["client"]
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    producer_calls: list[object] = []
    faulting_registry = _s2_registry_with_fault(registry_fault)

    monkeypatch.setattr(
        workspace_loop_module,
        "build_workspace_operation_registry",
        lambda: faulting_registry,
    )

    def _producer_must_not_run(value: object):
        producer_calls.append(value)
        raise AssertionError("S2 producer ran without a trusted executable registration")

    monkeypatch.setattr(
        "polisyos.runtime.quality.workspace.s2_design_search_operation.run_s2_shadow_design_loop",
        _producer_must_not_run,
    )
    before = _s2_artifact_census(Path(runtime_api_env["cas_root"]))
    launch_response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            "params": {
                "control_plane_transition": "workspace_loop",
                "workspace_operation_id": S2_DESIGN_SEARCH_OPERATION_ID,
                "layer2_s2_design_search_input": _layer2_s2_design_search_input(),
            },
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch = launch_response.json()
    assert service._worker is not None
    service._worker.dispatch_once()
    response = _await_terminal_job(service, launch["job_id"])

    assert response.state == "failed"
    assert response.failure is not None
    assert response.failure.code == "s2_design_search_failed_non_authority"
    assert producer_calls == []
    assert _s2_artifact_census(Path(runtime_api_env["cas_root"])) == before


@pytest.mark.parametrize("scope_established", [True, False])
@pytest.mark.parametrize(
    "terminal_kind", ["acquisition_required", "search_ceiling_repair_required"]
)
@pytest.mark.parametrize("boundary_present", [True, False])
def test_workspace_loop_non_authority_terminal_is_not_verifier_stamped(
    runtime_api_env,
    monkeypatch,
    scope_established: bool,
    terminal_kind: str,
    boundary_present: bool,
) -> None:
    from polisyos.runtime.quality.authority import authority_surface_decision

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    original_fixture = service._run_workspace_loop_fixture  # noqa: SLF001

    def run_non_authority_fixture(**kwargs):
        contract = original_fixture(**kwargs)
        assert (contract.authority_boundary is not None) is boundary_present
        if boundary_present or terminal_kind == "search_ceiling_repair_required":
            # Inject a typed search-repair result at the owner/consumer boundary;
            # the real controller must preserve it under either custody scope.
            terminal = contract.terminal_state.model_copy(
                update={
                    "kind": SearchTerminalKind(terminal_kind),
                    "reason": "Controlled non-authority terminal.",
                }
            )
            # Preserve the actual verifier-owned estimate objects. Recreating
            # their Ring-2 fields from JSON would rightly fail writer admission
            # before reaching the terminal/authority composition under test.
            contract = contract.model_copy(update={"terminal_state": terminal})
        return contract

    monkeypatch.setattr(service, "_run_workspace_loop_fixture", run_non_authority_fixture)
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        params={
            "slice0_fixture_id": (
                "ua_msme_credit_worldbank_measurement"
                if boundary_present
                else "tourism_local_development_ceiling_probe"
            )
        },
    )
    if scope_established:
        launch = _launch_owner_bound_workflow(runtime_api_env, request)
    else:
        with clear_tenant_context():
            input_ref = service._put_json_artifact(  # noqa: SLF001
                {"candidate_input": f"non-authority-{terminal_kind}"},
                kind="test.unclaimed_search_terminal_input",
                schema_name="test.UnclaimedSearchTerminalInput",
            )
            request = request.model_copy(
                update={
                    "data_source": request.data_source.model_copy(
                        update={"data_snapshot_ref": input_ref}
                    )
                }
            )
            launch = service.launch_workflow_run(request, principal=RuntimePrincipal())
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "completed"
    assert response.progress["authority_path"] == "workspace_loop"
    expected_result = (
        "acquisition_required" if terminal_kind == "acquisition_required" else "repair_required"
    )
    assert response.progress["authority_result"] == expected_result
    assert response.progress["search_exit_contract"]["terminal_state"]["kind"] == (terminal_kind)
    if not scope_established or not boundary_present:
        assert response.progress["search_exit_contract"]["authority_boundary"] is None
        assert response.progress["authority_derivation_trace_refs"] == []
    assert response.quality_status == "fail"
    assert any(gate.code == terminal_kind for gate in response.quality_gates)
    assert response.approval_projection.eligible is False
    projected_decision = authority_surface_decision(
        response.progress,
        surface="run",
        purpose="runtime_closeout_authority",
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    assert projected_decision.status != "allowed"
    assert projected_decision.blocking or projected_decision.visible_downgrade
    if scope_established and boundary_present:
        # An independently scoped estimate survives; it cannot approve the run.
        boundary = response.progress["search_exit_contract"]["authority_boundary"]
        assert boundary is not None
        assert "runtime_closeout_authority" not in boundary["authoritative_for"]
        estimate_decision = authority_surface_decision(
            response.progress["search_exit_contract"],
            surface="run",
            purpose="estimate:ua_msme_credit_worldbank_measurement",
            enforce_time_source=False,
            enforce_s12=False,
            enforce_candidate_firewall=False,
        )
        assert estimate_decision.status == "allowed"
        assert estimate_decision.consumed_authority_boundary
        wrong_purpose_decision = authority_surface_decision(
            response.progress["search_exit_contract"],
            surface="run",
            purpose="estimate:another_case",
            enforce_time_source=False,
            enforce_s12=False,
            enforce_candidate_firewall=False,
        )
        assert wrong_purpose_decision.status != "allowed"
        assert wrong_purpose_decision.visible_downgrade
    if not scope_established:
        assert response.progress["execution_scope_status"] == "not_established"


def test_workflow_transition_uses_injected_catalog_and_persists_measurement_payload(
    runtime_api_env,
    monkeypatch,
    tmp_path,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    catalog = _build_slice0_catalog(tmp_path)
    service._registry_providers = replace(
        service._registry_providers,
        gy_catalog_graph=catalog,
    )

    launch = _launch_owner_bound_workflow(
        runtime_api_env,
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            params={"slice0_fixture_id": "ua_msme_credit_worldbank_measurement"},
        ),
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    proof = WorkspaceLoopRunProof.model_validate(response.progress["production_loop_run_proof"])
    envelopes = response.progress["search_exit_contract"]["artifact_envelopes"]
    measurement_payload_ref = envelopes[0]["payload_ref"]

    assert response.state == "completed"
    assert measurement_payload_ref in proof.output_cas_refs
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        assert service._artifact_store.get_bytes(measurement_payload_ref)
    assert proof.artifacts_index_refs[0] == "search_exit_contract_ref"
    assert "authority_derivation_trace_refs" in proof.artifacts_index_refs


def test_legacy_workflow_shadow_cannot_emit_authority_completed_result(
    runtime_api_env, monkeypatch
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        params={"control_plane_transition": "legacy_shadow"},
    )
    called = {"run_experiment": False}

    def _legacy_success(*_args, **_kwargs):
        called["run_experiment"] = True
        return {
            "status": "success",
            "authority_boundary": {"decision_grade": "decision_admissible"},
        }

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _legacy_success)

    launch = service.launch_workflow_run(request)
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert called["run_experiment"] is True
    assert response.state == "completed"
    assert response.progress["authority_path"] == "legacy_shadow"
    assert response.progress["authority_result"] == "candidate_only"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="candidate_only",
    )
    assert response.operator_diagnostic is not None
    assert (
        response.operator_diagnostic.authority_refs["authority_boundary"]
        == response.progress["authority_boundary"]["boundary_id"]
    )
    assert response.quality_status == "fail"
    assert any(
        gap.code == "legacy_shadow_candidate_only" for gap in response.unresolved_authority_gaps
    )


def test_failed_workflow_result_is_blocked_across_authority_surfaces(
    runtime_api_env,
    monkeypatch,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    def _workflow_failure_result(_state_payload, _checkpoint_policy):
        return {
            "status": "fail",
            "state": "completed",
            "authority_boundary": {
                "decision_grade": "decision_admissible",
                "authoritative_for": ["runtime_closeout_authority"],
            },
        }

    monkeypatch.setattr(
        ControlPlaneService,
        "_execute_workflow",
        staticmethod(_workflow_failure_result),
    )

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "failed"
    assert response.progress["authority_path"] == "workflow_failure"
    assert response.progress["authority_result"] == "repair_required"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="blocked",
    )
    assert response.operator_diagnostic is not None
    assert (
        response.operator_diagnostic.authority_refs["authority_boundary"]
        == response.progress["authority_boundary"]["boundary_id"]
    )
    assert response.failure is not None
    assert response.failure.code == "workflow_failed_non_authority"
    assert response.failure.operator_diagnostic is not None
    assert (
        response.failure.operator_diagnostic.authority_refs["authority_boundary"]
        == (response.progress["authority_boundary"]["boundary_id"])
    )
    assert response.quality_status == "fail"
    assert response.approval_projection.eligible is False
    assert any(
        gap.code == "workflow_failed_non_authority" for gap in response.unresolved_authority_gaps
    )


def test_workspace_loop_exception_is_blocked_across_authority_surfaces(
    runtime_api_env,
    monkeypatch,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    def _run_fixture_failure(self, fixture_id):
        del self, fixture_id
        raise RuntimeError("workspace loop failed before contract")

    monkeypatch.setattr(
        "polisyos.runtime.quality.workspace.loop.WorkspaceLoop.run_fixture",
        _run_fixture_failure,
    )

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "failed"
    assert response.progress["authority_path"] == "workflow_failure"
    assert response.progress["authority_result"] == "repair_required"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="blocked",
    )
    assert response.failure is not None
    assert response.failure.code == "workspace_loop_failed_non_authority"
    assert response.failure.operator_diagnostic is not None
    assert (
        response.failure.operator_diagnostic.authority_refs["authority_boundary"]
        == (response.progress["authority_boundary"]["boundary_id"])
    )
    assert any(
        gap.code == "workspace_loop_failed_non_authority"
        for gap in response.unresolved_authority_gaps
    )


def test_failed_workflow_authority_packet_is_visible_through_http_job_route(
    runtime_api_env,
    monkeypatch,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    def _workflow_failure_result(_state_payload, _checkpoint_policy):
        return {"status": "fail", "message": "fixture fail"}

    monkeypatch.setattr(
        ControlPlaneService,
        "_execute_workflow",
        staticmethod(_workflow_failure_result),
    )

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()
    _await_terminal_job(service, launch.job_id)

    response = runtime_api_env["client"].get(f"/api/v1/control/jobs/{launch.job_id}")
    assert response.status_code == 200
    body = response.json()
    boundary = body["progress"]["authority_boundary"]
    packet = body["progress"]["authority_surface_packet"]
    assert body["state"] == "failed"
    assert body["failure"]["code"] == "workflow_failed_non_authority"
    assert (
        body["operator_diagnostic"]["authority_refs"]["authority_boundary"]
        == (boundary["boundary_id"])
    )
    assert (
        body["failure"]["operator_diagnostic"]["authority_refs"]["authority_boundary"]
        == (boundary["boundary_id"])
    )
    assert packet["boundary"] == boundary
    for surface_name in ("run", "artifact", "lineage", "export", "dashboard", "public_packet"):
        surface = packet["surfaces"][surface_name]
        assert surface["authority_result"] == "blocked"
        assert surface["consumed_boundary_id"] == boundary["boundary_id"]
    assert body["progress"]["public_packet"] == {
        "authority_boundary": boundary,
        "projection": packet["surfaces"]["public_packet"],
    }


def test_failed_legacy_workflow_does_not_complete_clean_as_authority(
    runtime_api_env, monkeypatch
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        params={"control_plane_transition": "legacy_shadow"},
    )

    def _legacy_failure(*_args, **_kwargs):
        raise RuntimeError("workflow fail")

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _legacy_failure)

    launch = service.launch_workflow_run(request)
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "failed"
    assert response.progress["authority_result"] == "repair_required"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="blocked",
    )
    assert response.failure is not None
    assert response.failure.code == "legacy_workflow_failed_non_authority"


@pytest.mark.asyncio
async def test_public_nl_route_persists_n4_candidate_without_n6_s8_or_publication(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The authorized public route persists N4 while authority stages remain unrun."""
    import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import (
        get_current_access_scope_or_none,
        get_current_cell_id,
        get_current_tenant_id_or_none,
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _design_problem_tool_args,
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
        _intent_context,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )
    from tests.unit.runtime.quality.test_design_generation import (
        RecordedClientWithCatalog,
        _recording_with_successful_first_response,
    )

    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated UAH 10b budget cap."
    )
    compiler_arguments = _design_problem_tool_args()
    compiler_arguments["nl_provenance"]["source_context"] = {
        "tenant_id": "tenant-llm-foreign",
        "cell_id": "cell-llm-foreign",
        "job_id": "job-llm-foreign",
        "run_id": "run-llm-foreign",
        "runtime_identity": {
            "tenant_id": "tenant-llm-runtime-foreign",
            "cell_id": "cell-llm-runtime-foreign",
            "job_id": "job-llm-runtime-foreign",
            "run_id": "run-llm-runtime-foreign",
        },
    }
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=compiler_arguments,
    )
    generation_gateway = RecordedClientWithCatalog(recording, model_ids=[model_id])
    original_compiler = nl_pipeline.build_design_problem_from_nl_request

    async def compile_with_deterministic_gateway(**kwargs):
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_with_deterministic_gateway,
    )
    monkeypatch.setattr(
        llm_factory,
        "create_traced_gateway_client",
        lambda **_kwargs: generation_gateway,
    )

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    runtime_container = runtime_api_env["app"].state.runtime_container
    bearer = _fixture_bearer("control-r5-n4-positive-candidate")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=runtime_container.runtime_api_context,
            control_service=service,
            decision_validity_service=service._decision_validity_service,
            claim_ledger_owner=service._epoch_claim_lifecycle_bridge.claim_owner,
            epoch_claim_lifecycle_bridge=service._epoch_claim_lifecycle_bridge,
        ),
    )
    admitted_tenant = runtime_api_env["tenant_b"]
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=admitted_tenant,
            cell_id=cell.cell_id,
            jti="jwt-control-r5-n4-positive-candidate",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    cell_id = cell.cell_id
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": admitted_tenant,
    }
    stop_embedded_control_worker(service)
    request_body = {
        "request": raw_request,
        "llm_model": model_id,
        "max_iterations": 1,
        "context": _intent_context(
            as_of="2026-05-12",
            tenant_id="tenant-request-foreign",
            cell_id="cell-request-foreign",
            job_id="job-request-foreign",
            run_id="run-request-foreign",
            runtime_identity={
                "tenant_id": "tenant-request-runtime-foreign",
                "cell_id": "cell-request-runtime-foreign",
                "job_id": "job-request-runtime-foreign",
                "run_id": "run-request-runtime-foreign",
            },
        ),
    }
    try:
        launch_response = client.post(
            "/api/v1/control/runs/nl",
            json=request_body,
            headers=headers,
        )
        assert launch_response.status_code == 200, launch_response.text
        launch = launch_response.json()
        assert launch["status"] == "accepted"
        job_id = str(launch["job_id"])
        job = service._control_store.get_job(job_id)
        assert job is not None
        reads: list[tuple[str, str | None, str | None, object]] = []
        original_load = service._load_payload_ref
        original_require_binding = service._require_nl_job_execution_intent_binding
        binding_results: list[dict[str, object]] = []
        read_events: list[str] = []

        def capture_job_artifact_read(ref: str, *, kind: str):
            if ref in {job.payload_ref, job.capability_manifest_ref}:
                read_kind = "payload" if ref == job.payload_ref else "manifest"
                read_events.append(read_kind)
                reads.append(
                    (
                        read_kind,
                        get_current_tenant_id_or_none(),
                        get_current_cell_id(),
                        get_current_access_scope_or_none(),
                    )
                )
            return original_load(ref, kind=kind)

        def capture_execution_binding(**kwargs):
            result = original_require_binding(**kwargs)
            binding_results.append(result)
            read_events.append("binding")
            return result

        monkeypatch.setattr(service, "_load_payload_ref", capture_job_artifact_read)
        monkeypatch.setattr(
            service,
            "_require_nl_job_execution_intent_binding",
            capture_execution_binding,
        )

        def reject_downstream(*_args, **_kwargs):
            pytest.fail("candidate-only N4 entered a downstream authority stage")

        monkeypatch.setattr(service, "resolve_generation_value_choices", reject_downstream)
        monkeypatch.setattr(service, "_publish_generation_run", reject_downstream)
        monkeypatch.setattr(
            generation_cycle_service,
            "build_default_recursive_generation_cycle_controller",
            reject_downstream,
        )
        poison = AccessScope.for_service(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell_id,
            spiffe_id="spiffe://r14/poisoned-nl-dispatch-context",
        )

        access_token = set_current_access_scope(poison)
        try:
            with tenant_scope(
                None,
                tenant_id=runtime_api_env["tenant_a"],
                cell_id=cell_id,
            ):
                dispatched_job_id = dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=job_id,
                )
        finally:
            reset_current_access_scope(access_token)
        assert dispatched_job_id == job_id
        completed = service.get_job_status(job_id)
        assert completed.state == "completed"
        assert compiler_gateway.generate_calls
        assert generation_gateway._cursor > 0
        assert completed.progress["execution_intent_band"] == "candidate_only"
        assert completed.progress["execution_band"] == "candidate"
        assert completed.progress["status"] == "candidate_limited"
        assert completed.progress["candidate_computation_status"] == "completed"
        assert completed.progress["n5_status"] == "not_run"
        assert completed.progress["n8_status"] == "not_run"
        assert completed.progress["n9_status"] == "not_run"
        assert completed.progress["s8_status"] == "not_run"
        assert "compiled_recursive_generation_cycle_ref" not in completed.progress
        assert completed.progress.get("normative_disposition_ref") is None
        assert completed.progress.get("manifest_ref") is None

        assert binding_results
        intent_binding = binding_results[0]
        assert {item[0] for item in reads} >= {"payload", "manifest"}
        assert all(
            tenant_id == admitted_tenant and observed_cell == cell_id and access_scope is None
            for _kind, tenant_id, observed_cell, access_scope in reads
        )
        assert read_events.index("payload") < read_events.index("manifest")
        assert read_events.index("manifest") < read_events.index("binding")
        assert intent_binding["admission_surface"] == "served_route"
        assert intent_binding["intent_band"] == "candidate_only"
        authorization_receipt = intent_binding["authorization_receipt"]
        assert authorization_receipt["route_id"] == "POST /api/v1/control/runs/nl"
        permission_snapshot = authorization_receipt["permission_snapshot"]
        assert permission_snapshot["required_permission"] == RuntimePermission.RUNS_LAUNCH.value
        assert permission_snapshot["subject"] == "user-1"
        assert permission_snapshot["jwt_id"] == "jwt-control-r5-n4-positive-candidate"
        assert permission_snapshot["tenant_id"] == admitted_tenant
        assert permission_snapshot["roles"] == [PolicyOSRole.ANALYST.value]
        assert authorization_receipt["resource"]["tenant_id"] == admitted_tenant
        proposal_locator = completed.progress["candidate_proposal_ref"]
        assert proposal_locator["schema_version"] == (
            "policyos.runtime.quality.n4_candidate_proposal_locator.v1"
        )
        assert proposal_locator["artifact_ref"]["kind"] == ("runtime.quality.n4_candidate_proposal")
        with tenant_scope(None, tenant_id=admitted_tenant, cell_id=cell_id):
            proposal = GenerationSourceRepository(
                service._artifact_store
            ).load_candidate_proposal_for_served_job(
                proposal_locator,
                job_id=job_id,
                run_id=str(job.run_id),
                tenant_id=admitted_tenant,
                cell_id=cell_id,
                raw_request=raw_request,
            )
        assert proposal.problem.nl_provenance.raw_request == raw_request
        assert proposal.problem.nl_provenance.source_context["tenant_id"] == (admitted_tenant)
        assert proposal.problem.nl_provenance.source_context["cell_id"] == cell_id
        assert proposal.problem.nl_provenance.source_context["job_id"] == job.job_id
        assert proposal.problem.nl_provenance.source_context["run_id"] == str(job.run_id)
        assert "runtime_identity" not in proposal.problem.nl_provenance.source_context
        intent_envelope = proposal.problem.to_policy_intent_envelope()
        assert intent_envelope["tenant_id"] == admitted_tenant
        assert intent_envelope["job_id"] == job.job_id
        assert intent_envelope["run_id"] == str(job.run_id)
        assert intent_envelope["authoring_provenance"]["source_context"]["cell_id"] == cell_id
        compiler_context = json.loads(compiler_gateway.generate_calls[0]["user"])["context"]
        assert "runtime_identity" not in compiler_context
        assert not set(compiler_context["candidate_context"]).intersection(
            {"tenant_id", "cell_id", "job_id", "run_id", "runtime_identity"}
        )
        assert compiler_context["tenant_id"] == admitted_tenant
        assert compiler_context["cell_id"] == cell_id
        assert compiler_context["job_id"] == job.job_id
        assert compiler_context["run_id"] == str(job.run_id)
        with tenant_scope(None, tenant_id=admitted_tenant, cell_id=cell_id):
            persisted_request = original_load(
                str(job.payload_ref), kind="runtime.control_job_payload.natural_language_run"
            )
        assert persisted_request["context"]["tenant_id"] == "tenant-request-foreign"
        assert (
            persisted_request["context"]["runtime_identity"]["cell_id"]
            == "cell-request-runtime-foreign"
        )
        assert proposal.proposal.trinity_bundle.policy_spec.interventions
        assert proposal.proposal.limitation_code == "cycle_substrate_context_unavailable"
    finally:
        client.close()


def test_declared_legacy_production_case_id_persists_as_profileless_input(runtime_api_env) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    intake_id = "sha256:" + "a" * 64
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        production_case_intake_ref=intake_id,
        params={"slice0_fixture_id": "ua_msme_credit_worldbank_measurement"},
    )
    launch = _launch_owner_bound_workflow(runtime_api_env, request)
    job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
    assert job is not None and job.payload_ref is not None
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        payload = service._load_payload_ref(  # noqa: SLF001
            job.payload_ref,
            kind="runtime.control_job_payload.workflow_run",
        )
    selected_ref = ArtifactRef.model_validate(
        payload["state_payload"]["inputs"]["production_case_intake_ref"]
    )
    assert str(selected_ref.artifact_id) == intake_id
    assert selected_ref.kind == "gy.loop.proof.root"
    assert selected_ref.media_type == "application/json"
    assert selected_ref.manifest_profile_sha256 is None


def test_workspace_loop_actual_production_case_intake_runs_as_candidate_a_spec_gap(
    runtime_api_env,
    tmp_path: Path,
    monkeypatch,
) -> None:
    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.quality.workspace.loop import (
        WorkspaceLoop,
        resolve_production_case_admission,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )
    from tests.unit.runtime.quality.workspace.test_production_case_admission import (
        actual_pinned_intake_payload,
    )

    api_service: ControlPlaneService = runtime_api_env["app"].state._control_service
    runtime_container = runtime_api_env["app"].state.runtime_container
    tenant_id = runtime_api_env["tenant_a"]
    bearer = _fixture_bearer("workspace-production-case-a-spec-gap")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=runtime_container.runtime_api_context,
            control_service=api_service,
            decision_validity_service=api_service._decision_validity_service,  # noqa: SLF001
            claim_ledger_owner=api_service._epoch_claim_lifecycle_bridge.claim_owner,  # noqa: SLF001
            epoch_claim_lifecycle_bridge=api_service._epoch_claim_lifecycle_bridge,  # noqa: SLF001
        ),
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=tenant_id,
            cell_id=cell.cell_id,
            jti="workspace-production-case-a-spec-gap",
        ),
    )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell.cell_id):
        production_payload = actual_pinned_intake_payload()
        # Keep a different profile as the default for identical bytes, then
        # explicitly select the valid, tenant-owned request view below.
        api_service._artifact_store.put_json(  # noqa: SLF001
            production_payload,
            ArtifactWriteOptions(
                kind="gy.loop.proof.root",
                media_type="application/json",
                schema=SchemaInfo(name="test.InvalidProductionIntakeView", version="1.0"),
                producer=ProducerInfo(component="test.alternate_intake_view", version="1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        intake_ref = _put_tenant_owned_json_artifact(
            api_service,
            production_payload,
            tenant_id=tenant_id,
            cell_id=cell.cell_id,
            kind="gy.loop.proof.root",
            schema_name="polisyos.gy.loop.proof.root",
            schema_version="1.0",
        )
        assert intake_ref.manifest_profile_sha256 is not None
        snapshot_ref = _owner_bound_data_snapshot_ref(
            api_service,
            tenant_id=tenant_id,
            cell_id=cell.cell_id,
            params={"fixture_id": production_payload["scope_source_fixture_id"]},
        )

    store = api_service._artifact_store  # noqa: SLF001
    before_denied_reads = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    with (
        tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_b"],
            cell_id="cell-b",
        ),
        pytest.raises(ArtifactOwnershipError),
    ):
        WorkspaceLoop(
            catalog_graph=api_service._registry_providers.gy_catalog_graph,  # noqa: SLF001
            artifact_store=store,
        ).run_production_case(
            request_ref=intake_ref,
            fixture_id=production_payload["scope_source_fixture_id"],
        )
    with clear_tenant_context(), pytest.raises(ArtifactOwnershipError):
        WorkspaceLoop(
            catalog_graph=api_service._registry_providers.gy_catalog_graph,  # noqa: SLF001
            artifact_store=store,
        ).run_production_case(
            request_ref=intake_ref,
            fixture_id=production_payload["scope_source_fixture_id"],
        )
    with (
        tenant_scope(
            None,
            tenant_id=tenant_id,
            cell_id=f"{cell.cell_id}-wrong",
        ),
        pytest.raises(ArtifactOwnershipError),
    ):
        WorkspaceLoop(
            catalog_graph=api_service._registry_providers.gy_catalog_graph,  # noqa: SLF001
            artifact_store=store,
        ).run_production_case(
            request_ref=intake_ref,
            fixture_id=production_payload["scope_source_fixture_id"],
        )
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == before_denied_reads

    selected_reads: list[tuple[str, str | None]] = []
    original_get_bytes = store.get_bytes
    original_get_manifest = store.get_manifest

    def record_selected_read(ref):
        if str(getattr(ref, "artifact_id", ref)) == str(intake_ref.artifact_id):
            selected_reads.append(("bytes", getattr(ref, "manifest_profile_sha256", None)))
        return original_get_bytes(ref)

    def record_selected_manifest(ref):
        if str(getattr(ref, "artifact_id", ref)) == str(intake_ref.artifact_id):
            selected_reads.append(("manifest", getattr(ref, "manifest_profile_sha256", None)))
        return original_get_manifest(ref)

    monkeypatch.setattr(store, "get_bytes", record_selected_read)
    monkeypatch.setattr(store, "get_manifest", record_selected_manifest)

    post = client.post(
        "/api/v1/control/runs",
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant_id},
        json={
            "data_source": {"data_snapshot_ref": str(snapshot_ref.artifact_id)},
            "production_case_intake_ref": intake_ref.model_dump(mode="json"),
            "params": {
                "slice0_fixture_id": production_payload["scope_source_fixture_id"],
                "production_case_intake_ref": str(intake_ref.artifact_id),
            },
        },
    )
    assert post.status_code == 200, post.text
    launch = post.json()
    service: ControlPlaneService = client.app.state._control_service
    stop_embedded_control_worker(service)
    assert service._worker is not None
    service._worker.dispatch_once()
    _await_terminal_job(service, launch["job_id"])

    completed_record_before_get = service._control_store.get_job(launch["job_id"])
    assert completed_record_before_get is not None
    proof_before_get = WorkspaceLoopRunProof.model_validate(
        completed_record_before_get.progress["production_loop_run_proof"]
    )
    assert "served_control_job_status_not_established" in proof_before_get.surface_reads_checked
    assert not any(
        row.get("surface") == "/api/v1/control/jobs/{job_id}"
        for row in proof_before_get.surface_readbacks
    )

    served = client.get(
        f"/api/v1/control/jobs/{launch['job_id']}",
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant_id},
    )
    assert served.status_code == 200, served.text
    progress = served.json()["progress"]
    assert served.json()["state"] == "completed"
    assert progress["authority_path"] == "workspace_loop"
    assert progress["authority_result"] == "repair_required"
    assert progress["approval_projection"]["eligible"] is False
    assert progress["quality_scorecard"]["quality_status"] == "fail"
    assert any(
        gate["code"] == "a_spec_gap" for gate in progress["quality_scorecard"]["quality_gates"]
    )
    assert progress["search_exit_contract"]["terminal_state"]["kind"] == "a_spec_gap"
    assert progress["search_exit_contract"]["authority_boundary"] is None
    assert progress["authority_derivation_trace_refs"] == []

    proof = WorkspaceLoopRunProof.model_validate(progress["production_loop_run_proof"])
    assert proof == proof_before_get
    assert proof.control_store_state_transitions == ["pending", "running", "completed"]
    assert proof.output_search_exit_contract_ref == progress["search_exit_contract_ref"]
    assert "served_control_job_status_not_established" in proof.surface_reads_checked
    assert any(
        readback.get("surface") == "control_plane_store"
        and readback.get("read_method")
        == "ControlPlaneStore.current_execution_completed_job_record"
        and readback.get("requested_endpoint") == "/api/v1/control/runs"
        and readback.get("observed_job_state") == "completed"
        and readback.get("matched_search_exit_contract_ref") is True
        for readback in proof.surface_readbacks
    )
    assert not any(
        readback.get("surface") == "/api/v1/control/jobs/{job_id}"
        for readback in proof.surface_readbacks
    )

    exit_ref = progress["search_exit_contract_ref"]
    proof_ref = progress["production_loop_run_proof_ref"]
    fresh_store = FileSystemCAS(api_service._artifact_store.root)  # noqa: SLF001
    assert fresh_store.verify(exit_ref).ok
    assert fresh_store.verify(proof_ref).ok
    exit_payload = from_canonical_bytes(fresh_store.get_bytes(exit_ref))
    proof_payload = from_canonical_bytes(fresh_store.get_bytes(proof_ref))
    assert exit_payload["terminal_state"]["kind"] == "a_spec_gap"
    assert proof_payload == progress["production_loop_run_proof"]
    assert proof_payload["output_search_exit_contract_ref"] == exit_ref

    workspace = exit_payload["workspace_contract"]
    selected_intake_ref = workspace["intent_ref"]
    assert selected_intake_ref["content_hash"] == str(intake_ref.artifact_id)
    admission_ref = workspace["refusal_source_admission_ref"]
    assert ("bytes", intake_ref.manifest_profile_sha256) in selected_reads
    assert ("manifest", intake_ref.manifest_profile_sha256) in selected_reads
    admission_manifest = fresh_store.get_manifest(admission_ref)
    expected_request_edge = (
        str(intake_ref.artifact_id),
        "production_case_input",
        intake_ref.manifest_profile_sha256,
    )
    assert [
        (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256)
        for edge in admission_manifest.inputs
    ] == [expected_request_edge]
    workspace_manifest = fresh_store.get_manifest(exit_payload["workspace_contract_ref"])
    assert (
        str(workspace_manifest.inputs[0].artifact_id),
        workspace_manifest.inputs[0].role,
        workspace_manifest.inputs[0].manifest_profile_sha256,
    ) == expected_request_edge
    resolved_admission = resolve_production_case_admission(
        store=fresh_store,
        receipt_ref=admission_ref,
        request_ref=intake_ref,
        catalog=service._registry_providers.gy_catalog_graph,
    )
    assert resolved_admission.request_ref == str(intake_ref.artifact_id)
    assert resolved_admission.substantive_source_support == "not_established"
    wrong_profile_ref = intake_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises((ArtifactOwnershipError, FileNotFoundError)):
        resolve_production_case_admission(
            store=fresh_store,
            receipt_ref=admission_ref,
            request_ref=wrong_profile_ref,
            catalog=service._registry_providers.gy_catalog_graph,
        )

    params_only_post = client.post(
        "/api/v1/control/runs",
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant_id},
        json={
            "data_source": {"data_snapshot_ref": str(snapshot_ref.artifact_id)},
            "params": {
                "slice0_fixture_id": production_payload["scope_source_fixture_id"],
                "production_case_intake_ref": str(intake_ref.artifact_id),
            },
        },
    )
    assert params_only_post.status_code == 200, params_only_post.text
    params_only_job_id = params_only_post.json()["job_id"]
    assert service._worker is not None
    assert service._worker.dispatch_once()
    params_only = _await_terminal_job(service, params_only_job_id)
    assert params_only.state == "failed"
    assert params_only.error_message == "production_case_intake_requires_declared_input_ref"
    assert not params_only.progress.get("search_exit_contract_ref")
    assert not params_only.progress.get("production_loop_run_proof_ref")


def test_workflow_run_request_rejects_wrong_or_conflicting_production_case_ref() -> None:
    from pydantic import ValidationError

    from polisyos.core.artifacts.manifest import ArtifactRef

    source_ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="gy.loop.proof.root",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    WorkflowRunRequest(
        data_source={"data_snapshot_ref": "sha256:" + "2" * 64},
        production_case_intake_ref=source_ref,
        params={"production_case_intake_ref": str(source_ref.artifact_id)},
    )
    legacy_profileless = WorkflowRunRequest(
        data_source={"data_snapshot_ref": "sha256:" + "2" * 64},
        production_case_intake_ref=str(source_ref.artifact_id),
        params={"production_case_intake_ref": str(source_ref.artifact_id)},
    )
    assert legacy_profileless.production_case_intake_ref == str(source_ref.artifact_id)
    with pytest.raises(ValidationError, match="production_case_intake_ref_legacy_param_mismatch"):
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": "sha256:" + "2" * 64},
            production_case_intake_ref=source_ref,
            params={"production_case_intake_ref": "sha256:" + "3" * 64},
        )
    with pytest.raises(ValidationError, match="production_case_intake_ref_legacy_param_mismatch"):
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": "sha256:" + "2" * 64},
            production_case_intake_ref=source_ref,
            params={
                "production_case_intake_ref": source_ref.model_copy(
                    update={"manifest_profile_sha256": "sha256:" + "b" * 64}
                ).model_dump(mode="json")
            },
        )
    with pytest.raises(
        ValidationError, match="production_case_intake_ref_kind_or_media_type_invalid"
    ):
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": "sha256:" + "2" * 64},
            production_case_intake_ref=source_ref.model_copy(
                update={"kind": "fabric.data_snapshot"}
            ),
        )
    with pytest.raises(ValidationError, match="production_case_intake_ref_legacy_id_invalid"):
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": "sha256:" + "2" * 64},
            production_case_intake_ref="not-an-artifact-id",
        )


def test_workflow_run_request_schema_matches_typed_intake_admission() -> None:
    from jsonschema import Draft202012Validator

    from polisyos.core.artifacts.manifest import ArtifactRef

    schema = WorkflowRunRequest.model_json_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    intake_schema = schema["properties"]["production_case_intake_ref"]
    assert isinstance(intake_schema, dict)
    intake_branches = intake_schema["anyOf"]
    assert [branch.get("type") for branch in intake_branches[1:]] == ["string", "null"]
    typed_ref_branch = intake_branches[0]
    assert typed_ref_branch["allOf"][0]["$ref"].endswith("/ArtifactRef")
    typed_ref_constraint = typed_ref_branch["allOf"][1]
    assert typed_ref_constraint["type"] == "object"
    assert typed_ref_constraint["properties"] == {
        "kind": {"const": "gy.loop.proof.root"},
        "media_type": {"const": "application/json"},
    }
    assert typed_ref_constraint["required"] == ["kind", "media_type"]
    artifact_id = "sha256:" + "1" * 64
    cases: list[tuple[str, dict[str, object], bool]] = [
        ("omitted", {}, True),
        ("none", {"production_case_intake_ref": None}, True),
        ("legacy string", {"production_case_intake_ref": artifact_id}, True),
        (
            "typed profileless",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "kind": "gy.loop.proof.root",
                    "media_type": "application/json",
                }
            },
            True,
        ),
        (
            "typed selected profile",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "kind": "gy.loop.proof.root",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "a" * 64,
                }
            },
            True,
        ),
        (
            "wrong kind",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "kind": "fabric.data_snapshot",
                    "media_type": "application/json",
                }
            },
            False,
        ),
        (
            "wrong media type",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "kind": "gy.loop.proof.root",
                    "media_type": "text/plain",
                }
            },
            False,
        ),
        (
            "missing kind",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "media_type": "application/json",
                }
            },
            False,
        ),
        (
            "missing media type",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "kind": "gy.loop.proof.root",
                }
            },
            False,
        ),
        (
            "malformed selected profile",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "kind": "gy.loop.proof.root",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:bad",
                }
            },
            False,
        ),
        (
            "unknown typed-ref property",
            {
                "production_case_intake_ref": {
                    "artifact_id": artifact_id,
                    "kind": "gy.loop.proof.root",
                    "media_type": "application/json",
                    "unrecognized": True,
                }
            },
            False,
        ),
    ]

    for name, field_payload, expected in cases:
        payload: dict[str, object] = {
            "data_source": {"data_snapshot_ref": "sha256:" + "2" * 64},
            **field_payload,
        }
        schema_accepts = validator.is_valid(payload)
        try:
            parsed = WorkflowRunRequest.model_validate(payload)
        except (TypeError, ValueError):
            model_accepts = False
        else:
            model_accepts = True
            if name == "typed selected profile":
                selected_ref = parsed.production_case_intake_ref
                assert isinstance(selected_ref, ArtifactRef)
                assert selected_ref.manifest_profile_sha256 == "sha256:" + "a" * 64
        assert schema_accepts is expected, name
        assert model_accepts is expected, name
