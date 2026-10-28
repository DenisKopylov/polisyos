"""Real scoped candidate byte admission; no source-purpose authority is inferred."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    artifact_ref_for_manifest,
    read_core_json_artifact,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control.job_diagnostics import (
    _OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY,
)
from polisyos.runtime.http.services.control.observational_source_access import (
    _reader_source_read_scope,
)
from polisyos.runtime.http.services.control.run_lifecycle import (
    _validate_direct_method_execution_selection_artifacts,
)
from polisyos.scientist.compute.runner import MethodExecutionWork
from tests._helpers.observational_source_runtime import (
    scoped_source_runtime as scoped_source_runtime,
)
from tests.unit.runtime.http.test_observational_method_runtime import (
    _direct_method_cas_case,
    _put_runtime_legacy_observational_source,
    _put_runtime_observational_source,
)


def _source(case: dict[str, Any], *, bound_metadata: bool = True) -> Any:
    owner = (case["tenant_a"], case["cell"])
    return _put_runtime_observational_source(
        case["service"],
        owner_scope=owner,
        tenant_context=ArtifactTenantContextInfo(tenant_id=owner[0], cell_id=owner[1])
        if bound_metadata
        else None,
    )


def _post(
    case: dict[str, Any],
    ref: Any,
    actor: str = "a",
    protocol: str = "method_input_envelope_v1",
) -> Any:
    return case["client"].post(
        "/api/v1/control/runs",
        headers=case["headers_" + actor],
        json={
            "observational_input": {
                "protocol": protocol,
                "source_ref": ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )


def _grant_fixture_job_views(
    case: dict[str, Any],
    job: Any,
    source: ArtifactRef,
    accepted: dict[str, Any],
    target_tenant: str,
    origin_tenant: str,
) -> None:
    """Give a second genuine Core owner every selected input, not a fake resolver."""
    owner = FileSystemCAS(case["cas_root"], ownership_enforced=True)
    intent_ref = ArtifactRef.model_validate(accepted["observational_run_intent_ref"])
    with tenant_scope(None, tenant_id=origin_tenant, cell_id=case["cell"]):
        intent = read_core_json_artifact(owner, intent_ref).value
        assert isinstance(intent, dict)
        payload_ref = artifact_ref_for_manifest(
            owner.get_manifest(ArtifactID.model_validate(job.payload_ref))
        )
    for ref in (
        source,
        intent_ref,
        payload_ref,
        ArtifactRef.model_validate(intent["resource_policy_ref"]),
    ):
        owner.record_artifact_owner(ref.artifact_id, tenant_id=target_tenant, cell_id=case["cell"])
        owner._ownership_index.record_view_owner(
            ref.artifact_id,
            ref.manifest_profile_sha256,
            tenant_id=target_tenant,
            cell_id=case["cell"],
        )
    with tenant_scope(None, tenant_id=target_tenant, cell_id=case["cell"]):
        assert (
            read_core_manifest_profile_bounded(
                owner, source, max_manifest_bytes=65_536
            ).effective_ref
            == source
        )


def test_authenticated_post_binds_scoped_source_to_durable_job(
    request: pytest.FixtureRequest,
) -> None:
    case = request.getfixturevalue("scoped_source_runtime")
    source = _source(case)
    response = _post(case, source)
    assert response.status_code == 200, response.text
    accepted = response.json()
    created = case["service"]._control_store.get_job_created_event_payload(accepted["job_id"])
    assert created["execution_scope"]["tenant_id"] == case["tenant_a"]
    assert created["execution_scope"]["cell_id"] == case["cell"]
    marker = created[_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY]
    assert marker["requested_source_ref"] == source.model_dump(mode="json")
    with tenant_scope(None, tenant_id=case["tenant_a"], cell_id=case["cell"]):
        fresh = FileSystemCAS(case["cas_root"], ownership_enforced=True)
        bounded = read_core_manifest_profile_bounded(fresh, source, max_manifest_bytes=65_536)
        assert bounded.effective_ref == source
        assert bounded.manifest.tenant_context.tenant_id == case["tenant_a"]


@pytest.mark.parametrize("bound_metadata", [False, True])
@pytest.mark.parametrize(
    "unsafe_handle", ["bound_foreign", "bound_wrong_cell", "enforcement_disabled"]
)
def test_post_refuses_actual_core_owner_other_than_actor_before_selected_read(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    bound_metadata: bool,
    unsafe_handle: str,
) -> None:
    case = request.getfixturevalue("scoped_source_runtime")
    service = case["service"]
    source = _source(case, bound_metadata=bound_metadata)
    actor = "a" if unsafe_handle == "bound_wrong_cell" else "b"
    if unsafe_handle == "bound_wrong_cell":
        wrong_cell = "fixture-other-cell"
        grants = FileSystemCAS(case["cas_root"], ownership_enforced=True)
        grants.record_artifact_owner(
            source.artifact_id, tenant_id=case["tenant_a"], cell_id=wrong_cell
        )
        grants._ownership_index.record_view_owner(
            source.artifact_id,
            source.manifest_profile_sha256,
            tenant_id=case["tenant_a"],
            cell_id=wrong_cell,
        )
        unsafe = grants.for_tenant(case["tenant_a"], wrong_cell)
    elif unsafe_handle == "bound_foreign":
        unsafe = FileSystemCAS(case["cas_root"], ownership_enforced=True).for_tenant(
            case["tenant_a"], case["cell"]
        )
    else:
        unsafe = FileSystemCAS(case["cas_root"], ownership_enforced=False)
    # Establish the exact divergent premise: Core genuinely reads this source
    # through the unsafe configured handle under another Runtime scope, not a fake resolver.
    with tenant_scope(None, tenant_id=case["tenant_" + actor], cell_id=case["cell"]):
        assert (
            read_core_manifest_profile_bounded(
                unsafe, source, max_manifest_bytes=65_536
            ).effective_ref
            == source
        )
    monkeypatch.setattr(service, "_artifact_store", unsafe)
    reads: list[object] = []
    original = service._read_observational_source_manifest

    def observed(*args: Any, **kwargs: Any) -> Any:
        reads.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_read_observational_source_manifest", observed)
    response = _post(case, source, actor)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "observational_source_current_access_not_established"
    assert reads == [], "wrong-owner source bytes must not be read before refusal"


def test_fresh_selection_reader_uses_active_owner_not_configured_foreign_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tenant_scope(None, tenant_id="source-a", cell_id="cell-a"):
        store, selection, limits = _direct_method_cas_case(tmp_path)
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
            source_scope=_reader_source_read_scope("source-a", "cell-a"),
        )
    # Reopen the real CAS and preserve genuine A claims and all metadata markers.
    fresh = FileSystemCAS(store.root, ownership_enforced=True).for_tenant("source-a", "cell-a")
    reads: list[object] = []
    original = FileSystemCAS._read_raw_manifest_bytes_bounded_owned

    def observed(owner: Any, *args: Any, **kwargs: Any) -> Any:
        result = original(owner, *args, **kwargs)
        reads.append(args)
        return result

    monkeypatch.setattr(FileSystemCAS, "_read_raw_manifest_bytes_bounded_owned", observed)
    with (
        tenant_scope(None, tenant_id="source-b", cell_id="cell-b"),
        pytest.raises(ValueError, match="observational_source_effective_owner_scope_mismatch"),
    ):
        _validate_direct_method_execution_selection_artifacts(
            store=fresh, selection=selection, limits=limits
        )

    assert reads == [], "fresh reader transferred private metadata before scope binding"


def test_selected_subclass_profile_is_not_replaced_by_default(
    request: pytest.FixtureRequest,
) -> None:
    case = request.getfixturevalue("scoped_source_runtime")
    source = _source(case)
    with tenant_scope(None, tenant_id=case["tenant_a"], cell_id=case["cell"]):
        store = case["service"]._artifact_store
        payload = read_core_json_artifact(store, source).value
        other = store.put_json(
            payload,
            PutOptions(
                kind=source.kind,
                media_type=source.media_type,
                schema=SchemaInfo(name="polisyos.ir.ObservationMethodInputEnvelope", version="1.0"),
                governance=ArtifactGovernanceInfo(
                    classification="public", column_classification={"view": "public"}
                ),
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=case["tenant_a"], cell_id=case["cell"]
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert other.artifact_id == source.artifact_id
        assert other.manifest_profile_sha256 != source.manifest_profile_sha256
        assert store.get_manifest(source.artifact_id).governance.column_classification == {}
        subclass = DataSnapshotRef.model_validate(other.model_dump(mode="json"))
        try:
            selected = case["service"]._read_observational_source_manifest(subclass)[0]
        except ValueError as exc:
            pytest.fail("selected subclass manifest view was not preserved: " + str(exc))
        assert selected.effective_ref == other
        assert selected.manifest.governance.column_classification == {"view": "public"}
    assert _post(case, subclass).status_code == 200


def test_worker_rechecks_reconciled_scope_before_loading_job_payload(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = request.getfixturevalue("scoped_source_runtime")
    service = case["service"]
    source = _source(case)
    response = _post(case, source)
    assert response.status_code == 200, response.text
    accepted = response.json()
    control = service._control_store
    control.mark_running(job_id=accepted["job_id"], worker_id="source-worker", lease_seconds=120)
    job = control.get_job(accepted["job_id"])
    assert job is not None
    _grant_fixture_job_views(case, job, source, accepted, case["tenant_b"], case["tenant_a"])
    work = MethodExecutionWork(
        job_id=job.job_id,
        run_id=str(job.run_id),
        attempt=job.attempt,
        requested_source_ref=source,
        observational_run_intent_ref=ArtifactRef.model_validate(
            accepted["observational_run_intent_ref"]
        ),
    )
    monkeypatch.setattr(
        service,
        "_artifact_store",
        FileSystemCAS(case["cas_root"], ownership_enforced=True).for_tenant(
            case["tenant_b"], case["cell"]
        ),
    )
    payload_reads: list[object] = []
    original = service._load_payload_ref

    def observed(*args: Any, **kwargs: Any) -> Any:
        payload_reads.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_load_payload_ref", observed)
    with (
        control.job_execution_fence(
            job_id=job.job_id, worker_id="source-worker", attempt=job.attempt
        ),
        service._install_execution_scope(control.current_execution_job_admission().scope),
        pytest.raises(ValueError, match="observational_source_effective_owner_scope_mismatch"),
    ):
        service.resolve_method_execution_admission(work=work)
    assert payload_reads == []


def test_pre_effect_persistence_rechecks_changed_owner_after_real_admission(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.foundry.data_plane import prepare_hte_observational_input

    case = request.getfixturevalue("scoped_source_runtime")
    service = case["service"]
    source = _source(case)
    response = _post(case, source)
    assert response.status_code == 200, response.text
    accepted = response.json()
    control = service._control_store
    control.mark_running(job_id=accepted["job_id"], worker_id="source-effect", lease_seconds=120)
    job = control.get_job(accepted["job_id"])
    assert job is not None
    _grant_fixture_job_views(case, job, source, accepted, case["tenant_b"], case["tenant_a"])
    work = MethodExecutionWork(
        job_id=job.job_id,
        run_id=str(job.run_id),
        attempt=job.attempt,
        requested_source_ref=source,
        observational_run_intent_ref=ArtifactRef.model_validate(
            accepted["observational_run_intent_ref"]
        ),
    )
    with (
        control.job_execution_fence(
            job_id=job.job_id, worker_id="source-effect", attempt=job.attempt
        ),
        service._install_execution_scope(control.current_execution_job_admission().scope),
    ):
        admission = service.resolve_method_execution_admission(work=work)
        prepared = prepare_hte_observational_input(
            store=admission.store,
            source_ref=source,
            protocol=admission.protocol,
            method_fqn=admission.method_fqn,
            limits=admission.limits,
        )
        shared = FileSystemCAS(case["cas_root"], ownership_enforced=True)
        for ref in (prepared.submitted_ref, prepared.effective_ref):
            shared.record_artifact_owner(
                ref.artifact_id, tenant_id=case["tenant_b"], cell_id=case["cell"]
            )
            shared._ownership_index.record_view_owner(
                ref.artifact_id,
                ref.manifest_profile_sha256,
                tenant_id=case["tenant_b"],
                cell_id=case["cell"],
            )
        assert (
            read_core_manifest_profile_bounded(
                shared.for_tenant(case["tenant_b"], case["cell"]),
                prepared.effective_ref,
                max_manifest_bytes=65_536,
            ).effective_ref
            == prepared.effective_ref
        )
        monkeypatch.setattr(
            service,
            "_artifact_store",
            FileSystemCAS(case["cas_root"], ownership_enforced=True).for_tenant(
                case["tenant_b"], case["cell"]
            ),
        )
        writes: list[object] = []
        original = service._put_json_artifact_ref

        def observed(*args: Any, **kwargs: Any) -> Any:
            writes.append(args)
            return original(*args, **kwargs)

        monkeypatch.setattr(service, "_put_json_artifact_ref", observed)
        with pytest.raises(ValueError, match="observational_source_effective_owner_scope_mismatch"):
            service.persist_content_admitted_intent(
                work=work,
                admission=admission,
                submitted_ref=prepared.submitted_ref,
                effective_ref=prepared.effective_ref,
                contract_target=prepared.contract_target,
                method_fqn=prepared.method_fqn,
                source_protocol=prepared.source_protocol,
                normalization=prepared.normalization,
                limitations=prepared.limitations,
                source_governance=prepared.source_governance,
                source_tenant_context=prepared.source_tenant_context,
                observed_bytes=prepared.observed_bytes,
                observed_depth=prepared.observed_depth,
                observed_elements=prepared.observed_elements,
                observed_manifest_bytes=prepared.observed_manifest_bytes,
                observed_manifest_selection_bytes=prepared.observed_manifest_selection_bytes,
                observed_manifest_verification_bytes=prepared.observed_manifest_verification_bytes,
                observed_payload_bytes=prepared.observed_payload_bytes,
                observed_source_bytes=prepared.observed_source_bytes,
                payload_integrity_verified=prepared.payload_integrity_verified,
            )
        assert writes == [], "changed owner must be rejected before persistence/dispatch"


def test_new_owner_generation_withdrawal_after_enqueue_reaches_actual_core_guard(
    request: pytest.FixtureRequest,
) -> None:
    """Change a fixture-owned signed generation, not a claimed external revoke API."""
    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError

    case = request.getfixturevalue("scoped_source_runtime")
    service = case["service"]
    source = _source(case)
    response = _post(case, source)
    assert response.status_code == 200, response.text
    control = service._control_store
    accepted = response.json()
    control.mark_running(
        job_id=accepted["job_id"], worker_id="source-generation", lease_seconds=120
    )
    job = control.get_job(accepted["job_id"])
    assert job is not None
    work = MethodExecutionWork(
        job_id=job.job_id,
        run_id=str(job.run_id),
        attempt=job.attempt,
        requested_source_ref=source,
        observational_run_intent_ref=ArtifactRef.model_validate(
            accepted["observational_run_intent_ref"]
        ),
    )
    fresh = FileSystemCAS(case["cas_root"], ownership_enforced=True)
    index = fresh._ownership_index
    # The controlled fixture owns this CAS root. Use its real owner generation
    # writer/signature path; do not edit manifest bytes, signatures or pointers.
    with index._lock, index._cross_instance_write_lock():
        previous = index._load_snapshot()
        payload = previous.payload
        for field in ("artifacts", "blob_readers"):
            rows = payload[field][str(source.artifact_id)]
            remaining = [
                row
                for row in rows
                if row["tenant_id"] != case["tenant_a"] or row.get("cell_id") != case["cell"]
            ]
            if remaining:
                payload[field][str(source.artifact_id)] = remaining
            else:
                payload[field].pop(str(source.artifact_id))
        index._write_payload(payload, previous_snapshot=previous)
    assert not fresh._ownership_index.is_blob_readable_by(
        source.artifact_id, tenant_id=case["tenant_a"], cell_id=case["cell"]
    )
    with (
        control.job_execution_fence(
            job_id=job.job_id, worker_id="source-generation", attempt=job.attempt
        ),
        service._install_execution_scope(control.current_execution_job_admission().scope),
        pytest.raises(CoreJsonReadBoundsRefusalError) as caught,
    ):
        service.resolve_method_execution_admission(work=work)
    cause = caught.value.__cause__
    assert cause is not None
    assert isinstance(getattr(cause, "original_exception", cause), ArtifactOwnershipError)
    refused = _post(case, source)
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "observational_source_current_access_not_established"


def test_real_shared_view_grant_uses_reader_scope_without_rewriting_source_tenant(
    request: pytest.FixtureRequest,
) -> None:
    case = request.getfixturevalue("scoped_source_runtime")
    source = _source(case)
    owner = FileSystemCAS(case["cas_root"], ownership_enforced=True)
    owner.record_artifact_owner(
        source.artifact_id, tenant_id=case["tenant_b"], cell_id=case["cell"]
    )
    owner._ownership_index.record_view_owner(
        source.artifact_id,
        source.manifest_profile_sha256,
        tenant_id=case["tenant_b"],
        cell_id=case["cell"],
    )
    with tenant_scope(None, tenant_id=case["tenant_b"], cell_id=case["cell"]):
        selected = read_core_manifest_profile_bounded(owner, source, max_manifest_bytes=65_536)
        assert selected.manifest.tenant_context.tenant_id == case["tenant_a"]
    response = _post(case, source, "b")
    assert response.status_code == 200, response.text

    accepted = response.json()
    with tenant_scope(None, tenant_id=case["tenant_b"], cell_id=case["cell"]):
        intent = read_core_json_artifact(
            owner, ArtifactRef.model_validate(accepted["observational_run_intent_ref"])
        )
        assert intent.manifest.tenant_context.tenant_id == case["tenant_b"]
        assert intent.value["source_tenant_context"]["tenant_id"] == case["tenant_a"]
        assert intent.value["requested_source_ref"] == source.model_dump(mode="json")
        policy = read_core_json_artifact(
            owner, ArtifactRef.model_validate(intent.value["resource_policy_ref"])
        )
        assert policy.manifest.tenant_context.tenant_id == case["tenant_b"]


def test_real_job_admission_cannot_borrow_another_ambient_owner(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = request.getfixturevalue("scoped_source_runtime")
    service = case["service"]
    source = _put_runtime_observational_source(
        service, owner_scope=(case["tenant_b"], case["cell"]), tenant_context=None
    )
    response = _post(case, source, "b")
    assert response.status_code == 200, response.text
    accepted = response.json()
    control = service._control_store
    control.mark_running(job_id=accepted["job_id"], worker_id="source-context", lease_seconds=120)
    job = control.get_job(accepted["job_id"])
    assert job is not None
    _grant_fixture_job_views(case, job, source, accepted, case["tenant_a"], case["tenant_b"])
    work = MethodExecutionWork(
        job_id=job.job_id,
        run_id=str(job.run_id),
        attempt=job.attempt,
        requested_source_ref=source,
        observational_run_intent_ref=ArtifactRef.model_validate(
            accepted["observational_run_intent_ref"]
        ),
    )
    monkeypatch.setattr(
        service,
        "_artifact_store",
        FileSystemCAS(case["cas_root"], ownership_enforced=True).for_tenant(
            case["tenant_a"], case["cell"]
        ),
    )
    reads: list[object] = []
    original = service._load_payload_ref

    def observed(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        reads.append(args[0])
        return result

    monkeypatch.setattr(service, "_load_payload_ref", observed)
    with (
        control.job_execution_fence(
            job_id=job.job_id, worker_id="source-context", attempt=job.attempt
        ),
        tenant_scope(None, tenant_id=case["tenant_a"], cell_id=case["cell"]),
        pytest.raises(ValueError) as caught,
    ):
        service.resolve_method_execution_admission(work=work)

    assert reads == [], "job read private payload through another ambient owner"
    assert str(caught.value) == "observational_source_active_scope_mismatch"


def test_worker_without_live_fence_cannot_reuse_admitted_request_scope(
    request: pytest.FixtureRequest,
) -> None:
    from polisyos.runtime.http.services.control_plane_store import ControlJobLeaseLostError

    case = request.getfixturevalue("scoped_source_runtime")
    source = _source(case)
    response = _post(case, source)
    assert response.status_code == 200, response.text
    accepted = response.json()
    job = case["service"]._control_store.get_job(accepted["job_id"])
    assert job is not None
    work = MethodExecutionWork(
        job_id=job.job_id,
        run_id=str(job.run_id),
        attempt=job.attempt,
        requested_source_ref=source,
        observational_run_intent_ref=ArtifactRef.model_validate(
            accepted["observational_run_intent_ref"]
        ),
    )
    with (
        tenant_scope(None, tenant_id=case["tenant_a"], cell_id=case["cell"]),
        pytest.raises(ControlJobLeaseLostError),
    ):
        case["service"].resolve_method_execution_admission(work=work)


@pytest.mark.parametrize("protocol", ["method_input_envelope_v1", "legacy_hte_json_v1"])
def test_shared_source_keeps_origin_and_uses_actual_job_writer_through_preparation(
    request: pytest.FixtureRequest,
    protocol: str,
) -> None:
    from polisyos.foundry.data_plane import (
        HTEInputPreparationRefusal,
        load_hte_physical_source_materialization_binding,
        prepare_hte_observational_input,
    )
    from polisyos.foundry.data_plane.bindings import _persist_hte_physical_source_binding

    case = request.getfixturevalue("scoped_source_runtime")
    service = case["service"]
    source_factory = (
        _put_runtime_observational_source
        if protocol == "method_input_envelope_v1"
        else _put_runtime_legacy_observational_source
    )
    source = source_factory(
        service,
        owner_scope=(case["tenant_a"], case["cell"]),
        tenant_context=ArtifactTenantContextInfo(tenant_id=case["tenant_a"], cell_id=case["cell"]),
    )
    owner = FileSystemCAS(case["cas_root"], ownership_enforced=True)
    owner.record_artifact_owner(
        source.artifact_id, tenant_id=case["tenant_b"], cell_id=case["cell"]
    )
    owner._ownership_index.record_view_owner(
        source.artifact_id,
        source.manifest_profile_sha256,
        tenant_id=case["tenant_b"],
        cell_id=case["cell"],
    )
    response = _post(case, source, "b", protocol)
    assert response.status_code == 200, response.text
    accepted = response.json()
    control = service._control_store
    control.mark_running(job_id=accepted["job_id"], worker_id="derived-writer", lease_seconds=120)
    job = control.get_job(accepted["job_id"])
    assert job is not None
    work = MethodExecutionWork(
        job_id=job.job_id,
        run_id=str(job.run_id),
        attempt=job.attempt,
        requested_source_ref=source,
        observational_run_intent_ref=ArtifactRef.model_validate(
            accepted["observational_run_intent_ref"]
        ),
    )
    with (
        control.job_execution_fence(
            job_id=job.job_id, worker_id="derived-writer", attempt=job.attempt
        ),
        service._install_execution_scope(control.current_execution_job_admission().scope),
    ):
        admission = service.resolve_method_execution_admission(work=work)
        assert admission.source_tenant_context.tenant_id == case["tenant_a"]
        assert admission.derived_tenant_context.tenant_id == case["tenant_b"]
        prepared = prepare_hte_observational_input(
            store=admission.store,
            source_ref=source,
            protocol=admission.protocol,
            method_fqn=admission.method_fqn,
            limits=admission.limits,
            materialization_binding_version="physical_v1",
            derived_tenant_context=admission.derived_tenant_context,
        )
        assert prepared.source_tenant_context.tenant_id == case["tenant_a"]
        assert prepared.write_tenant_context.tenant_id == case["tenant_b"]
        assert prepared.materialization_binding_ref is not None
        physical = read_core_manifest_profile_bounded(
            owner, prepared.materialization_binding_ref, max_manifest_bytes=65_536
        )
        assert physical.manifest.tenant_context.tenant_id == case["tenant_b"]
        # Re-enter the actual resolve/recompute consumer, not only its manifest.
        reopened = load_hte_physical_source_materialization_binding(
            store=owner,
            binding_ref=prepared.materialization_binding_ref,
            expected_submitted_ref=source,
            expected_effective_ref=prepared.effective_ref,
            limits=admission.limits,
            expected_data=prepared.data,
        )
        assert reopened.submitted_ref == source
        assert reopened.effective_ref == prepared.effective_ref
        assert reopened.binding_scope == "physical_materialization_only"
        assert reopened.semantic_alignment_status == "not_established"
        if protocol == "legacy_hte_json_v1":
            effective = read_core_manifest_profile_bounded(
                owner, prepared.effective_ref, max_manifest_bytes=65_536
            )
            assert effective.manifest.tenant_context.tenant_id == case["tenant_b"]
            # Genuine Core-produced alternate binding profile: all bytes,
            # selected input refs and recomputation agree, but its derived
            # custody conflicts with the normalized artifact's writer B.
            owner.record_artifact_owner(
                prepared.effective_ref.artifact_id,
                tenant_id=case["tenant_a"],
                cell_id=case["cell"],
            )
            owner._ownership_index.record_view_owner(
                prepared.effective_ref.artifact_id,
                prepared.effective_ref.manifest_profile_sha256,
                tenant_id=case["tenant_a"],
                cell_id=case["cell"],
            )
            with tenant_scope(None, tenant_id=case["tenant_a"], cell_id=case["cell"]):
                conflicting = _persist_hte_physical_source_binding(
                    store=owner.for_tenant(case["tenant_a"], cell_id=case["cell"]),
                    binding=reopened,
                    source_governance=prepared.source_governance,
                    tenant_context=prepared.source_tenant_context,
                    limits=admission.limits,
                )
            assert conflicting.artifact_id == prepared.materialization_binding_ref.artifact_id
            assert conflicting.manifest_profile_sha256 != (
                prepared.materialization_binding_ref.manifest_profile_sha256
            )
            owner._ownership_index.record_view_owner(
                conflicting.artifact_id,
                conflicting.manifest_profile_sha256,
                tenant_id=case["tenant_b"],
                cell_id=case["cell"],
            )
            conflicting_read = read_core_manifest_profile_bounded(
                owner, conflicting, max_manifest_bytes=65_536
            )
            assert conflicting_read.manifest.tenant_context.tenant_id == case["tenant_a"]
            with pytest.raises(
                HTEInputPreparationRefusal,
                match="source_binding_legacy_derived_custody_mismatch",
            ):
                load_hte_physical_source_materialization_binding(
                    store=owner,
                    binding_ref=conflicting,
                    expected_submitted_ref=source,
                    expected_effective_ref=prepared.effective_ref,
                    limits=admission.limits,
                    expected_data=prepared.data,
                )
        admitted_ref = service.persist_content_admitted_intent(
            work=work,
            admission=admission,
            submitted_ref=prepared.submitted_ref,
            effective_ref=prepared.effective_ref,
            contract_target=prepared.contract_target,
            method_fqn=prepared.method_fqn,
            source_protocol=prepared.source_protocol,
            normalization=prepared.normalization,
            limitations=prepared.limitations,
            source_governance=prepared.source_governance,
            source_tenant_context=prepared.source_tenant_context,
            observed_bytes=prepared.observed_bytes,
            observed_depth=prepared.observed_depth,
            observed_elements=prepared.observed_elements,
            observed_manifest_bytes=prepared.observed_manifest_bytes,
            observed_manifest_selection_bytes=prepared.observed_manifest_selection_bytes,
            observed_manifest_verification_bytes=prepared.observed_manifest_verification_bytes,
            observed_payload_bytes=prepared.observed_payload_bytes,
            observed_source_bytes=prepared.observed_source_bytes,
            payload_integrity_verified=prepared.payload_integrity_verified,
        )
        admitted = read_core_json_artifact(owner, admitted_ref)
        assert admitted.manifest.tenant_context.tenant_id == case["tenant_b"]
        assert admitted.value["source_tenant_context"]["tenant_id"] == case["tenant_a"]
        assert admitted.value["requested_source_ref"] == source.model_dump(mode="json")
        assert admitted.value["source_access_revalidation_status"] == "not_established"


def test_shared_source_native_result_is_owned_by_job_and_reopened_by_fresh_service(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the real supported backend; source A never becomes writer B by metadata."""
    pytest.importorskip("econml")
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.selection.history import SelectionHistoryStore
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.runtime_http import _build_registry_providers, _NoOpRetrievalService
    from tests.unit.runtime.http.test_observational_method_runtime import _put_selected_json
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import _put_v2_hte_source

    case = request.getfixturevalue("scoped_source_runtime")
    service = case["service"]
    with tenant_scope(None, tenant_id=case["tenant_a"], cell_id=case["cell"]):
        raw = _put_v2_hte_source(
            service._artifact_store, tenant_id=case["tenant_a"], cell_id=case["cell"]
        )
        payload = read_core_json_artifact(service._artifact_store, raw).value
        source = _put_selected_json(
            service._artifact_store,
            payload,
            kind=raw.kind,
            schema=SchemaInfo(name="polisyos.ir.ObservationMethodInputEnvelope", version="1.0"),
            governance=ArtifactGovernanceInfo(classification="public"),
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=case["tenant_a"], cell_id=case["cell"]
            ),
        )
    owner = FileSystemCAS(case["cas_root"], ownership_enforced=True)
    owner.record_artifact_owner(
        source.artifact_id, tenant_id=case["tenant_b"], cell_id=case["cell"]
    )
    owner._ownership_index.record_view_owner(
        source.artifact_id,
        source.manifest_profile_sha256,
        tenant_id=case["tenant_b"],
        cell_id=case["cell"],
    )
    history = SelectionHistoryStore(
        persist_path=tmp_path / "native-history" / "executions.jsonl", auto_persist=True
    )
    monkeypatch.setattr(MethodDispatcher, "_instance", MethodDispatcher(runtime_history=history))
    response = case["client"].post(
        "/api/v1/control/runs",
        headers=case["headers_b"],
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.causal_forest@2.0.0"},
                "hte_request": {
                    "schema_version": "polisyos.runtime.observational_hte_request.v2",
                    "estimand": "mean_effect_over_selected_x",
                    "target_scope": "selected_evaluation_rows",
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_id": "treatment.policy",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "alpha": 0.05,
                    "requested_guarantee": "backend_conditional_interval",
                },
            }
        },
    )
    assert response.status_code == 200, response.text
    accepted = response.json()
    dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=accepted["job_id"],
    )
    completed = service._control_store.get_job(accepted["job_id"])
    assert completed is not None and completed.state == "completed", (
        completed.error_message if completed is not None else "missing durable job"
    )
    sqlite_path = str(service._control_store._sqlite_path)
    fresh_control = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    fresh_owner = FileSystemCAS(case["cas_root"]).with_ambient_ownership_enforcement()
    fresh = ControlPlaneService(
        cas_root=case["cas_root"],
        core_runs_root=case["cas_root"] / "runs",
        repo_root=Path(request.config.rootpath),
        artifact_store=fresh_owner,
        control_store=fresh_control,
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=sqlite_path,
            postgres_dsn=None,
        ),
        retrieval_service=_NoOpRetrievalService(),
        registry_providers=_build_registry_providers(),
    )
    try:
        with tenant_scope(None, tenant_id=case["tenant_b"], cell_id=case["cell"]):
            selection = fresh.get_method_execution_selection(
                run_id=accepted["run_id"], tenant_id=case["tenant_b"], cell_id=case["cell"]
            )
            assert selection is not None
            assert selection.requested_source_ref == source
            assert selection.source_access_revalidation_status == "not_established"
            for ref in (
                selection.method_result_ref,
                selection.method_evidence_ref,
                selection.observational_run_intent_ref,
                selection.content_admitted_intent_ref,
                selection.resource_policy_ref,
                selection.owned_attempt_anchor_ref,
            ):
                assert ref is not None
                manifest = read_core_manifest_profile_bounded(
                    fresh_owner, ref, max_manifest_bytes=65_536
                ).manifest
                assert manifest.tenant_context.tenant_id == case["tenant_b"]
            requested = read_core_json_artifact(fresh_owner, selection.observational_run_intent_ref)
            assert requested.value["source_tenant_context"]["tenant_id"] == case["tenant_a"]
            assert requested.value["requested_source_ref"] == source.model_dump(mode="json")
    finally:
        fresh.close()
        fresh_control.close()
