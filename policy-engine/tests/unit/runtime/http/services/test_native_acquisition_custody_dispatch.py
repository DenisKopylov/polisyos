"""Custody consumer controls; scripted source facts do not establish admission."""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
)
from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionScope
from polisyos.runtime.quality import acquisition_world_growth as world_owner
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteClosureError,
    NativeDerivationInputsPending,
)
from tests.unit.runtime.http.services.test_acquisition_custody_recovery_binding import (
    _bound_permission_for_request,
    _request_with_custody_recovery,
)
from tests.unit.runtime.http.test_native_acquisition_custody_recovery import (
    _failed_action,
    _request,
)


@pytest.mark.parametrize("existing", [False, True], ids=["missing-job", "changed-request"])
def test_custody_execute_cannot_fall_back_to_new_action(existing: bool) -> None:
    request = _request_with_custody_recovery()
    proof, _ = _bound_permission_for_request(request)
    principal = RuntimePrincipal(
        subject=proof.verification.subject,
        tenant_id=proof.verification.tenant_id,
        cell_id="cell-custody",
        roles=proof.verification.roles,
        authenticated=True,
    )
    job = SimpleNamespace(
        kind="acquisition",
        run_id="run-custody",
        payload_ref="sha256:" + "a" * 64,
        submitted_by=principal.subject,
    )
    scope = ControlJobExecutionScope(
        status="established",
        tenant_id=principal.tenant_id,
        cell_id=principal.cell_id,
        actor_subject=principal.subject,
        actor_authenticated=True,
        actor_roles=tuple(sorted(principal.roles)),
    )
    source_request = request.model_copy(
        update={
            "custody_recovery": None,
            "idempotency_key": "different-original-command",
        }
    )
    service = object.__new__(AcquisitionActionService)
    service.control_service = SimpleNamespace(
        _control_store=SimpleNamespace(
            get_job=lambda _job_id: job if existing else None,
            _reconcile_control_job_creation_envelope=lambda _job: (scope, None),
        ),
        _load_payload_ref=lambda *_args, **_kwargs: {
            "request": source_request.model_dump(mode="json"),
        },
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("custody refusal reached fresh action owner")

    service._require_authority_provider = forbidden
    service._validated_mutation = forbidden
    with pytest.raises(AcquisitionActionServiceError) as refused:
        service.execute(
            tenant_id=principal.tenant_id,
            cell_id=principal.cell_id,
            run_id="run-custody",
            route_id="sha256:" + "b" * 64,
            request=request,
            bound_permission=proof,
            principal=principal,
            request_id=None,
        )
    assert refused.value.code == (
        "acquisition_custody_recovery_request_changed"
        if existing
        else "acquisition_custody_recovery_existing_job_required"
    )


def _scripted_custody_case(tmp_path, monkeypatch: pytest.MonkeyPatch, *, pending: bool):
    """Return real restrictive SQL custody with explicitly opaque source collaborators."""
    action = _failed_action(tmp_path)
    _request(action)
    leased = action.store.lease_next_job(worker_id="custody-branch-worker", lease_seconds=60)
    assert leased is not None
    bridge = object.__new__(world_owner.AcquisitionWorldGrowthBridge)
    bridge.promotion_runtime = None
    bridge.artifact_store = SimpleNamespace(
        get_manifest=lambda _ref: SimpleNamespace(kind=world_owner._GROWTH_KIND),
    )
    bridge.control_store = action.store
    bridge.event_log = SimpleNamespace(list_events=lambda **_kwargs: ())
    bridge._source_control_service = None
    bridge.selection = lambda _closure: object()
    bridge._paths = lambda _selection: (tmp_path / "overlay", None)
    bridge._verified_growth = lambda *_args: (object(), object())
    bridge._native_derivation_configuration = lambda _closure: object()
    collection_ref = ArtifactRef(
        artifact_id="sha256:" + "d" * 64,
        kind="runtime_quality.native_derivation_input_checkpoint",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "e" * 64,
    )
    bridge._collect_current_native_derivation_inputs = lambda *_args: collection_ref
    protected_calls = []

    def protected(*_args, **_kwargs):
        protected_calls.append(True)
        raise AssertionError("custody reached materialization/N4/N5")

    bridge._native_derivation_context_handoff = protected
    bridge._native_derivation_complete_requests = lambda *_args: (object(),)
    monkeypatch.setattr(
        world_owner,
        "replay_native_derivation_input_collection",
        lambda *_args: SimpleNamespace(
            collection=SimpleNamespace(
                pending_actions=("unbound-role",) if pending else (),
            )
        ),
    )
    monkeypatch.setattr(
        world_owner.data_forge_read_api.catalog,
        "acquisition_overlay_admission_fence",
        lambda _path: nullcontext(),
    )
    closure = SimpleNamespace(native_derivation_leaf_scope=None)
    return action, leased, bridge, closure, collection_ref, protected_calls


@pytest.mark.parametrize("pending", [True, False], ids=["pending", "complete"])
def test_custody_collection_never_reaches_protected_reentry(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    pending: bool,
) -> None:
    """Consume a real SQL restriction without promoting scripted input facts."""
    action, leased, bridge, closure, collection_ref, protected_calls = _scripted_custody_case(
        tmp_path,
        monkeypatch,
        pending=pending,
    )
    with action.store.job_execution_fence(
        job_id=leased.job_id,
        worker_id="custody-branch-worker",
        attempt=leased.attempt,
    ):
        if pending:
            result = bridge.resume(closure, ("sha256:" + "c" * 64,))
            assert type(result) is NativeDerivationInputsPending
            assert result.collection_ref == collection_ref
        else:
            with pytest.raises(
                ValueError, match="native_custody_recovery_protected_reentry_refused"
            ) as refused:
                bridge.resume(closure, ("sha256:" + "c" * 64,))
            assert refused.value.code == "native_custody_recovery_protected_reentry_refused"
    assert protected_calls == []


def test_recorded_owner_return_precedes_complete_collection_custody_refusal(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed historical owner return is read before any fresh work.

    This is a control-flow test with an opaque verified-owner boundary, not
    evidence of a complete Native world or a numerical result.
    """
    action, leased, bridge, closure, collection_ref, protected = _scripted_custody_case(
        tmp_path,
        monkeypatch,
        pending=False,
    )
    recorded = "sha256:" + "f" * 64
    lookups = []

    def recorded_owner(**kwargs):
        lookups.append(kwargs)
        return recorded

    bridge._read_existing_reentry = recorded_owner
    with action.store.job_execution_fence(
        job_id=leased.job_id,
        worker_id="custody-branch-worker",
        attempt=leased.attempt,
    ):
        assert bridge.resume(closure, ("sha256:" + "c" * 64,)) == recorded
    assert len(lookups) == 1
    assert lookups[0]["custody_collection_ref"] == collection_ref
    assert protected == []


def test_selected_phase_reader_keeps_full_profile_and_never_falls_back(tmp_path) -> None:
    """Real CAS view/removal control; source admission is outside this reader test."""
    from tests.unit.runtime.quality.test_native_derivation_action_history import _native_requested

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    phase = _native_requested(store, index=1, now=datetime.now(UTC))
    ref = store.put_json(
        phase.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(
            kind="runtime_quality.acquisition_route_phase_receipt",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.runtime.AcquisitionRoutePhaseReceipt", version="1.3"
            ),
            producer=artifacts.ProducerInfo(component="tests.selected-phase-reader", version="1.0"),
        ),
        canon.CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    service = object.__new__(AcquisitionActionService)
    service.control_service = SimpleNamespace(_artifact_store=store)
    default = store._manifest_path_for_ref(ref.artifact_id, None)
    selected = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    old_default = default.read_bytes()
    held = selected.with_suffix(selected.suffix + ".held")
    changed = json.loads(old_default)
    changed["producer"]["component"] = "tests.competing-default"
    try:
        default.write_text(json.dumps(changed, sort_keys=True, separators=(",", ":")))
        assert service._read_phase_receipt(ref) == phase
        selected.rename(held)
        with pytest.raises(AcquisitionActionServiceError) as refused:
            service._read_phase_receipt(ref)
        assert refused.value.code == "acquisition_phase_readback_failed"
    finally:
        if held.exists():
            held.rename(selected)
        default.write_bytes(old_default)
    assert service._read_phase_receipt(ref) == phase
    with pytest.raises(AcquisitionActionServiceError) as refused:
        service._read_phase_receipt(ref.model_copy(update={"manifest_profile_sha256": None}))
    assert refused.value.code == "acquisition_phase_profile_required"


@pytest.mark.parametrize("pointer_kind", ["foreign-kind", "ambiguous-profile"])
def test_custody_reentry_pointer_cannot_launder_unselected_or_foreign_view(
    tmp_path,
    pointer_kind: str,
) -> None:
    """Real same-payload inventory must select a unique profile before owner reads."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    payload = {"authority_purpose": "test_candidate_only"}
    kind = world_owner._REENTRY_KIND if pointer_kind == "ambiguous-profile" else "fixture.other"
    options = artifacts.ArtifactWriteOptions(
        kind=kind,
        media_type="application/json",
        producer=artifacts.ProducerInfo(component="tests.candidate-only", version="1"),
    )
    ref = store.put_json(payload, options, return_selected_profile=True)
    if pointer_kind == "ambiguous-profile":
        other = store.put_json(
            payload,
            replace(
                options,
                producer=artifacts.ProducerInfo(
                    component="tests.other-candidate",
                    version="1",
                ),
            ),
            return_selected_profile=True,
        )
        assert ref.artifact_id == other.artifact_id
        assert ref.manifest_profile_sha256 != other.manifest_profile_sha256
    pointer = tmp_path / "reentry.json"
    pointer.write_text(json.dumps({"receipt_ref": str(ref.artifact_id)}))
    before = pointer.read_bytes()
    bridge = object.__new__(world_owner.AcquisitionWorldGrowthBridge)
    bridge.artifact_store = store
    with pytest.raises(AcquisitionRouteClosureError) as refused:
        bridge._read_existing_reentry(
            closure=object(),
            growth=object(),
            growth_ref="sha256:" + "a" * 64,
            pointer=pointer,
            custody_collection_ref=ArtifactRef(
                artifact_id="sha256:" + "b" * 64,
                kind="runtime_quality.native_derivation_input_checkpoint",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "c" * 64,
            ),
        )
    assert refused.value.code == "native_custody_reentry_profile_not_established"
    assert pointer.read_bytes() == before


def test_event_only_custody_locator_hands_full_profile_to_canonical_owner(tmp_path) -> None:
    """Prove selected addressing over real CAS; stop at the semantic-owner boundary."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        {"authority_purpose": "test_candidate_only"},
        artifacts.ArtifactWriteOptions(
            kind=world_owner._REENTRY_KIND, media_type="application/json"
        ),
        return_selected_profile=True,
    )

    class SelectedReader:
        def __getattr__(self, name):
            return getattr(store, name)

        def get_manifest(self, selected):
            assert isinstance(selected, ArtifactRef), "event locator downgraded to default view"
            return store.get_manifest(selected)

    bridge = object.__new__(world_owner.AcquisitionWorldGrowthBridge)
    bridge.artifact_store = SelectedReader()
    bridge.event_log = SimpleNamespace(
        list_events=lambda **_kwargs: (
            SimpleNamespace(
                event=SimpleNamespace(
                    payload_ref=str(ref.artifact_id),
                    artifact_refs=(str(ref.artifact_id),),
                )
            ),
        )
    )
    reached = []

    def semantic_owner(selected, kind):
        reached.append((selected, kind))
        raise RuntimeError("semantic_owner_boundary_reached")

    bridge._read = semantic_owner
    with pytest.raises(RuntimeError, match="semantic_owner_boundary_reached"):
        bridge._read_existing_reentry(
            closure=object(),
            growth=object(),
            growth_ref="sha256:" + "a" * 64,
            pointer=tmp_path / "absent-pointer.json",
            custody_collection_ref=ref,
        )
    assert reached == [(ref, world_owner._REENTRY_KIND)]
