"""Discovery binds real SQL jobs, payloads and owner-produced phases.

Only the completed NL-to-Core trace resolver is isolated here. The served
model-input integration scenario exercises that resolver and the HTTP boundary.
These locators establish neither numerical results nor current action authority.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    ArtifactWriteOptions,
    EnvInfo,
    FileSystemCAS,
    SchemaInfo,
)
from polisyos.core.contracts.runtime import RunDetails
from polisyos.runtime.http.routes import runs
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.model_input_successor_action import (
    ModelInputSuccessorActionRequest,
    ModelInputUseActionCheckpoint,
    NativeActiveInputUsePins,
    NativeModelInputSuccessorActionRequest,
)
from polisyos.runtime.quality.agent_action_authority import MODEL_INPUT_USE_ACTION_KIND
from polisyos.runtime.quality.model_input_successor_selection import (
    ModelInputUseActionPhase,
    persist_model_input_use_action_phase,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _scope


def _put(store: Any, kind: str, label: str, *, payload: Any = None) -> ArtifactRef:
    value = {"fixture": label} if payload is None else payload
    options = ArtifactWriteOptions(
        kind=kind,
        media_type=(
            "application/vnd.polisyos.epoch+json"
            if kind == "epoch.activated_overlay_admission_receipt"
            else "application/json"
        ),
        schema=SchemaInfo(name=kind, version="1.0"),
        tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a"),
    )
    if kind == "epoch.activated_overlay_admission_receipt":
        return store.put_bytes(
            json.dumps(value, sort_keys=True).encode(), options, return_selected_profile=True
        )
    return store.put_json(value, options, return_selected_profile=True)


def _job(
    case: SimpleNamespace,
    *,
    job_id: str,
    kind: str,
    run_id: str,
    payload_ref: str,
    scope: dict[str, object] | None = None,
) -> Any:
    created = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": kind,
        "pipeline_id": None,
        "payload_ref": payload_ref,
        "submitted_by": "tester",
        "requested_execution_profile": None,
        "effective_execution_profile": "governed",
        "policy_flags": {},
        "capability_manifest_ref": None,
        "execution_scope": _scope() if scope is None else scope,
    }
    return case.database.create_job(
        **{
            name: value
            for name, value in created.items()
            if name not in {"job_kind", "execution_scope"}
        },
        kind=kind,
        creation_event_payload=created,
    )


def _complete(case: SimpleNamespace, job: Any, progress: dict[str, Any]) -> None:
    worker = f"worker-{job.job_id}"
    leased = case.database.lease_next_job(worker_id=worker, lease_seconds=60)
    assert leased is not None and leased.job_id == job.job_id
    with case.database.job_execution_fence(
        job_id=job.job_id, worker_id=worker, attempt=leased.attempt
    ):
        case.database.complete_job(job_id=job.job_id, run_id=job.run_id, progress=progress)


def _case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    control = _build_control_service(tmp_path / "service", artifact_store=store)
    case = SimpleNamespace(
        store=store,
        control=control,
        database=control._control_store,
        sqlite_path=control._resolve_control_sqlite_path(),
    )
    case.compiled_ref = _put(store, "runtime.compiled_recursive_generation_cycle", "compiled")
    manifest_ref = _put(store, "core.run_manifest", "manifest")
    source_payload = _put(store, "runtime.control_job_payload.natural_language_run", "source")
    source = _job(
        case,
        job_id="source-nl",
        kind="natural_language_run",
        run_id="logical-run",
        payload_ref=str(source_payload.artifact_id),
    )
    _complete(case, source, {})
    case.run = SimpleNamespace(
        details=RunDetails(
            run_id="core-attempt-run",
            source_kind="core_run",
            status="completed",
            tenant_id="tenant-a",
            cell_id="cell-a",
            control_job_id=source.job_id,
            manifest_ref=manifest_ref,
        )
    )
    case.source = SimpleNamespace(
        run_id=case.run.details.run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        manifest_ref=manifest_ref,
        manifest=SimpleNamespace(
            run_id=case.run.details.run_id,
            control_job_id=source.job_id,
            outputs=(case.compiled_ref,),
        ),
    )

    def read_source(selected_control: Any, selected_job: Any, **kwargs: Any) -> Any:
        assert selected_control is control
        assert selected_job.job_id == "source-nl"
        assert kwargs == {
            "expected_control_run_id": "logical-run",
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
        }
        return case.source

    monkeypatch.setattr(
        ControlPlaneService, "resolve_completed_control_job_core_run_source", read_source
    )
    return case


def _action(
    case: SimpleNamespace,
    job_id: str,
    *,
    run_id: str = "logical-run",
    action_kind: str = MODEL_INPUT_USE_ACTION_KIND,
    scope: dict[str, object] | None = None,
    phase_updates: dict[str, Any] | None = None,
    compiled_ref: ArtifactRef | None = None,
    native_use: NativeActiveInputUsePins | None = None,
) -> Any:
    direct_request = ModelInputSuccessorActionRequest(
        compiled_ref=case.compiled_ref if compiled_ref is None else compiled_ref,
        blocked_execution_ref=_put(
            case.store, "runtime.quality.generic_cycle_simulation_n5_execution", "blocked"
        ),
        routing_report_ref=_put(case.store, "runtime.quality.model_input_routing_report", "report"),
        activation_receipt_ref=_put(
            case.store, "epoch.activated_overlay_admission_receipt", "activation"
        ),
        observation_id="fixture-observation",
        idempotency_key=job_id,
    )
    request = (
        NativeModelInputSuccessorActionRequest(
            **direct_request.model_dump(mode="python"), native_use=native_use
        )
        if native_use is not None
        else direct_request
    )
    decision_ref = _put(case.store, "runtime_quality.agent_action_authority_decision", job_id)
    route_id = "sha256:" + "a" * 64
    payload_ref = _put(
        case.store,
        "runtime.control_job_payload.acquisition",
        job_id,
        payload={
            "action_kind": action_kind,
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "run_id": run_id,
            "route_id": route_id,
            "decision_ref": str(decision_ref.artifact_id),
            "request": request.model_dump(mode="json"),
        },
    )
    job = _job(
        case,
        job_id=job_id,
        kind="acquisition",
        run_id=run_id,
        payload_ref=str(payload_ref.artifact_id),
        scope=scope,
    )
    phase = ModelInputUseActionPhase.model_validate(
        {
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "run_id": run_id,
            "source_job_id": "source-nl",
            "action_job_id": job_id,
            "route_id": route_id,
            "action_payload_ref": payload_ref,
            "authority_decision_ref": decision_ref,
            **(phase_updates or {}),
        }
    )
    checkpoint = ModelInputUseActionCheckpoint(
        phase_ref=persist_model_input_use_action_phase(case.store, phase),
        semantic_successor_ref=_put(
            case.store, "runtime.quality.model_input_successor_selection", job_id
        ),
    )
    _complete(case, job, {"model_input_use": checkpoint.model_dump(mode="json")})
    return case.database.get_job(job.job_id)


def _discover(case: SimpleNamespace) -> Any:
    return runs._model_input_use_actions_for_indexed_run(
        case.run, store=case.store, control_service=case.control
    )


def _native_action(case: SimpleNamespace, job_id: str) -> Any:
    native_use = NativeActiveInputUsePins(
        predecessor_terminal_ref=_put(
            case.store, "runtime_quality.acquisition_route_loop_receipt", f"{job_id}-predecessor"
        ),
        world_checkpoint_ref=_put(
            case.store,
            "runtime_quality.acquisition_candidate_world_checkpoint",
            f"{job_id}-world-checkpoint",
        ),
        fresh_budget_usd="1",
    )
    return _action(case, job_id, native_use=native_use)


def test_real_phase_and_job_discovery_preserves_control_alias_and_stable_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path, monkeypatch)
    second = _action(case, "action-z")
    first = _action(case, "action-a")

    projection = _discover(case)

    assert projection is not None
    assert projection.model_dump(mode="json") == {
        "run_id": "logical-run",
        "source_job_id": "source-nl",
        "scope": "discovery_only",
        "actions": [
            {"action_job_id": "action-a", "job_state": "completed"},
            {"action_job_id": "action-z", "job_state": "completed"},
        ],
        "inventory_status": "complete",
        "inventory_truncated": False,
        "limitation_codes": [],
    }
    assert case.database.get_job(first.job_id) == first
    assert case.database.get_job(second.job_id) == second


@pytest.mark.parametrize(
    "phase_updates",
    [
        {"source_job_id": "foreign-source"},
        {"action_job_id": "other-action"},
        {"route_id": "sha256:" + "b" * 64},
        {"run_id": "foreign-run"},
    ],
)
def test_discovery_omits_resolving_phase_with_a_mismatched_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase_updates: dict[str, Any]
) -> None:
    case = _case(tmp_path, monkeypatch)
    _action(case, "valid-action")
    _action(case, "mismatched-action", phase_updates=phase_updates)

    projection = _discover(case)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == ["valid-action"]
    assert projection.inventory_status == "limited"
    assert projection.limitation_codes == ("action_binding_not_established",)


@pytest.mark.parametrize(
    ("phase_field", "artifact_kind"),
    [
        ("action_payload_ref", "runtime.control_job_payload.acquisition"),
        ("authority_decision_ref", "runtime_quality.agent_action_authority_decision"),
    ],
)
def test_discovery_excludes_phase_bound_to_other_payload_or_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase_field: str,
    artifact_kind: str,
) -> None:
    case = _case(tmp_path, monkeypatch)
    _action(case, "valid-action")
    foreign_ref = _put(case.store, artifact_kind, "foreign")
    _action(case, "mismatched-action", phase_updates={phase_field: foreign_ref})

    projection = _discover(case)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == ["valid-action"]
    assert projection.inventory_status == "limited"
    assert projection.limitation_codes == ("action_binding_not_established",)


@pytest.mark.parametrize("keep_valid_selector", [True, False])
def test_removing_a_previously_resolved_owner_phase_preserves_the_inventory_limitation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keep_valid_selector: bool
) -> None:
    case = _case(tmp_path, monkeypatch)
    if keep_valid_selector:
        _action(case, "action-a")
    second = _action(case, "action-b")
    before = _discover(case)
    assert before is not None
    assert [item.action_job_id for item in before.actions] == (
        ["action-a", "action-b"] if keep_valid_selector else ["action-b"]
    )
    phase_ref = ArtifactRef.model_validate(second.progress["model_input_use"]["phase_ref"])
    phase_blob, _ = case.store._paths(phase_ref.artifact_id)
    withheld = tmp_path / "withheld-phase"
    phase_blob.rename(withheld)
    try:
        projection = _discover(case)
    finally:
        withheld.rename(phase_blob)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == (
        ["action-a"] if keep_valid_selector else []
    )
    assert projection.inventory_status == "limited"
    assert projection.limitation_codes == ("action_binding_not_established",)


def test_discovery_excludes_other_run_kind_and_action_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path, monkeypatch)
    _action(case, "valid-action")
    _action(case, "foreign-run-action", run_id="foreign-run")
    _action(case, "other-action", action_kind="runtime.evidence.candidate_experiment.reuse")
    _job(
        case,
        job_id="other-job-kind",
        kind="workflow_run",
        run_id="logical-run",
        payload_ref=str(case.compiled_ref.artifact_id),
    )

    projection = _discover(case)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == ["valid-action"]
    assert projection.inventory_status == "complete"


@pytest.mark.parametrize("axis", ["tenant", "cell"])
def test_discovery_excludes_foreign_action_creation_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, axis: str
) -> None:
    case = _case(tmp_path, monkeypatch)
    _action(case, "valid-action")
    _action(case, "foreign-action", scope=_scope(**{axis: "foreign-scope"}))

    projection = _discover(case)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == ["valid-action"]
    assert projection.inventory_status == "limited"


def test_discovery_excludes_other_compiled_source_and_missing_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path, monkeypatch)
    _action(case, "valid-action")
    foreign_compiled = _put(case.store, "runtime.compiled_recursive_generation_cycle", "foreign")
    _action(case, "foreign-compiled-action", compiled_ref=foreign_compiled)
    uncheckpointed = _action(case, "uncheckpointed-action")
    case.database.upsert_progress(job_id=uncheckpointed.job_id, progress={})

    projection = _discover(case)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == ["valid-action"]
    assert projection.inventory_status == "limited"
    assert projection.limitation_codes == ("action_binding_not_established",)


def test_discovery_omits_job_after_creation_event_binding_is_corrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path, monkeypatch)
    _action(case, "valid-action")
    _action(case, "corrupt-action")
    with sqlite3.connect(case.sqlite_path) as connection:
        connection.execute(
            "UPDATE control_jobs SET submitted_by = ? WHERE job_id = ?",
            ("foreign-actor", "corrupt-action"),
        )

    projection = _discover(case)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == ["valid-action"]
    assert projection.inventory_status == "limited"


@pytest.mark.parametrize("action_job_id", ["action-000", "zzz-action"])
def test_discovery_reports_real_bounded_query_truncation_even_without_a_matching_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action_job_id: str
) -> None:
    case = _case(tmp_path, monkeypatch)
    _action(case, action_job_id)
    before = _discover(case)
    assert before is not None
    assert [item.action_job_id for item in before.actions] == [action_job_id]
    other_payload = _put(
        case.store,
        "runtime.control_job_payload.acquisition",
        "other-kind",
        payload={"action_kind": "runtime.evidence.candidate_experiment.reuse"},
    )
    for index in range(128):
        _job(
            case,
            job_id=f"other-{index:03d}",
            kind="acquisition",
            run_id="logical-run",
            payload_ref=str(other_payload.artifact_id),
        )

    projection = _discover(case)

    assert projection is not None
    assert [item.action_job_id for item in projection.actions] == (
        [action_job_id] if action_job_id == "action-000" else []
    )
    assert projection.inventory_status == "limited"
    assert projection.inventory_truncated
    assert projection.limitation_codes == ("action_inventory_truncated",)


def test_unavailable_or_unowned_source_keeps_existing_wire_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path, monkeypatch)
    assert _discover(case) is None
    assert "model_input_use_actions" not in case.run.details.model_dump(mode="json")
    _action(case, "action-a")
    assert _discover(case) is not None
    case.source.manifest_ref = case.compiled_ref
    assert _discover(case) is None
    assert (
        runs._model_input_use_actions_for_indexed_run(
            case.run, store=case.store, control_service=None
        )
        is None
    )


def test_native_completed_result_dispatch_preserves_profile_refusal_without_history_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.runtime.http.services import model_input_successor_action
    from polisyos.runtime.http.services.control import job_diagnostics

    case = _case(tmp_path, monkeypatch)
    job = _native_action(case, "native-action")
    action_service = object()
    native_calls: list[tuple[Any, dict[str, Any]]] = []

    def refuse_selected_native_result(control_service: Any, **kwargs: Any) -> Any:
        native_calls.append((control_service, kwargs))
        raise CanonicalProfileRefusalError("canon_profile_selected_payload_identity_mismatch")

    def forbid_generic_history(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Native integrity refusal must not fall back to direct-use history")

    monkeypatch.setattr(
        job_diagnostics,
        "read_completed_native_model_input_use_n5_result",
        refuse_selected_native_result,
    )
    monkeypatch.setattr(
        model_input_successor_action,
        "resolve_model_input_successor_history",
        forbid_generic_history,
    )

    projection = runs._model_input_use_n5_successor_projection(
        run_id="logical-run",
        action_job_id=job.job_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        store=case.store,
        control_service=case.control,
        action_service=action_service,
    )

    assert projection.schema_version == (
        "policyos.runtime.run_model_input_use_n5_successor_projection.v1"
    )
    assert projection.result_status == "not_established"
    assert projection.limitation_code == "canon_profile_selected_payload_identity_mismatch"
    assert native_calls == [
        (
            case.control,
            {
                "action_service": action_service,
                "tenant_id": "tenant-a",
                "cell_id": "cell-a",
                "run_id": "logical-run",
                "action_job_id": job.job_id,
            },
        )
    ]


def test_direct_model_input_request_does_not_dispatch_to_native_result_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.http.services.control import job_diagnostics

    case = _case(tmp_path, monkeypatch)
    job = _action(case, "direct-action")

    def forbid_native_reader(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Direct-use request must not dispatch to the Native result reader")

    monkeypatch.setattr(
        job_diagnostics,
        "read_completed_native_model_input_use_n5_result",
        forbid_native_reader,
    )

    projection = runs._model_input_use_n5_successor_projection(
        run_id="logical-run",
        action_job_id=job.job_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        store=case.store,
        control_service=case.control,
    )

    assert projection.result_status == "not_established"
    assert projection.limitation_code == "model_input_use_action_terminal_checkpoint_not_established"


def test_native_result_without_exact_action_owner_is_limited_without_history_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.http.services import model_input_successor_action

    case = _case(tmp_path, monkeypatch)
    job = _native_action(case, "native-action-without-owner")

    def forbid_generic_history(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Missing Native owner must not fall back to direct-use history")

    monkeypatch.setattr(
        model_input_successor_action,
        "resolve_model_input_successor_history",
        forbid_generic_history,
    )

    projection = runs._model_input_use_n5_successor_projection(
        run_id="logical-run",
        action_job_id=job.job_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        store=case.store,
        control_service=case.control,
        action_service=None,
    )

    assert projection.result_status == "not_established"
    assert projection.limitation_code == "native_model_input_use_history_owner_missing"


def test_native_model_input_use_expiry_at_sql_commit_rolls_back_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expire a genuine queue publication after its SQL event and before commit."""
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.http.services import control_plane_store
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord

    case = _case(tmp_path, monkeypatch)
    retained = _native_action(case, "native-predecessor")
    payload = case.control._load_payload_ref(
        retained.payload_ref, kind="runtime.control_job_payload.acquisition"
    )
    assert isinstance(payload, dict)
    principal = RuntimePrincipal(
        subject="tester",
        tenant_id="tenant-a",
        cell_id="cell-a",
        roles=frozenset({"operator"}),
        authenticated=True,
    )
    job_id = "model-input-use." + "d" * 64
    deadline = 2_000_000_000
    now = deadline - 1
    monkeypatch.setattr(control_plane_store, "time", SimpleNamespace(time=lambda: now))
    store = case.database._target
    assert type(store) is control_plane_store.ControlPlaneStore
    emit = store._emit_job_outbox_event
    provisional = []

    def expire_after_publication(
        *, record: ControlJobRecord, event_type: str, payload: dict[str, Any]
    ) -> None:
        nonlocal now
        emit(record=record, event_type=event_type, payload=payload)
        event = store.get_job_created_outbox_event(job_id)
        assert event is not None and event.job_id == job_id
        assert store.list_job_state_transitions(job_id) == ["pending"]
        provisional.append(event.event_id)
        now = deadline

    def queue(expires_at: int | None) -> ControlJobRecord:
        return case.control.enqueue_acquisition_job(
            job_id=job_id,
            run_id="logical-run",
            payload=payload,
            principal=principal,
            native_step_up_expires_at=expires_at,
        )

    with monkeypatch.context() as admission:
        admission.setattr(store, "_emit_job_outbox_event", expire_after_publication)
        with pytest.raises(
            control_plane_store._NativeModelInputUseStepUpExpiredError,
            match="native_model_input_use_step_up_expired_before_admission",
        ):
            queue(deadline)
    assert len(provisional) == 1
    assert case.database.get_job(job_id) is None
    assert case.database.list_job_state_transitions(job_id) == []
    assert case.database.get_outbox_event(provisional[0]) is None
    assert case.database.lease_next_job(worker_id="worker-after-expiry", lease_seconds=30) is None
    assert case.database.get_job(retained.job_id) == retained

    with pytest.raises(control_plane_store._NativeModelInputUseStepUpExpiredError):
        queue(None)
    fresh = queue(deadline + 1)
    assert (fresh.job_id, fresh.state, fresh.attempt, fresh.lease_owner) == (
        job_id,
        "pending",
        0,
        None,
    )
    assert case.database.list_job_state_transitions(job_id) == ["pending"]
    event = case.database.get_job_created_outbox_event(job_id)
    assert event is not None and event.payload["state"] == "pending"
    stored = case.control._load_payload_ref(
        fresh.payload_ref, kind="runtime.control_job_payload.acquisition"
    )
    assert stored["request"] == payload["request"]
    assert stored["decision_ref"] == payload["decision_ref"]
    assert queue(deadline + 1) == fresh
    assert case.database.get_job_created_outbox_event(job_id) == event


def test_native_stage_matches_exact_bindings_across_reference_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reopen the persisted selector with exact bindings and a sealed stage view."""
    from dataclasses import replace

    from polisyos.core.contracts import FoundryInputBindingsRef
    from polisyos.runtime.http.services import model_input_successor_action
    from polisyos.runtime.http.services.acquisition_action_service import (
        VerifiedModelInputUseWorker,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError
    from polisyos.runtime.quality.generic_simulation_admission import (
        NativeModelInputUseWorldCheckpointV1,
    )
    from polisyos.runtime.quality.model_input_successor_selection import (
        ModelInputSuccessorSelection,
        persist_model_input_successor_selection,
        read_model_input_use_action_phase,
    )
    from polisyos.runtime.quality.native_generic_context import _read_model_input_use_stage

    case = _case(tmp_path, monkeypatch)
    job = _native_action(case, "native-stage-bindings")
    stage = ModelInputUseActionCheckpoint.model_validate(job.progress["model_input_use"])
    phase = read_model_input_use_action_phase(case.store, stage.phase_ref)
    payload = json.loads(case.store.get_bytes(phase.action_payload_ref))
    request = NativeModelInputSuccessorActionRequest.model_validate(payload["request"])
    bindings = _put(case.store, "foundry.input_bindings", "exact-method-bindings")
    input_ref = FoundryInputBindingsRef.model_validate(bindings.model_dump(mode="python"))
    assert type(bindings) is ArtifactRef
    assert type(input_ref) is FoundryInputBindingsRef
    assert input_ref.model_dump(mode="python") == bindings.model_dump(mode="python")
    observation_hash = "sha256:" + "b" * 64
    window = SimpleNamespace(window_id="1" * 64, record_digest="2" * 64)
    selector = ModelInputSuccessorSelection(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        compiled_ref=request.compiled_ref,
        blocked_execution_ref=request.blocked_execution_ref,
        routing_report_ref=request.routing_report_ref,
        activation_receipt_ref=request.activation_receipt_ref,
        observation_id=request.observation_id,
        observation_content_sha256=observation_hash,
        route_id=phase.route_id,
        action_job_id=phase.action_job_id,
        action_worker_id="fixture-stage-worker",
        action_attempt=job.attempt,
        action_phase_ref=stage.phase_ref,
        authority_decision_ref=phase.authority_decision_ref,
        reentry_budget_window_id=window.window_id,
        reentry_budget_window_digest=window.record_digest,
        semantic_foundry_input_bindings_ref=input_ref,
    )
    selected_stage = stage.model_copy(
        update={
            "semantic_successor_ref": persist_model_input_successor_selection(case.store, selector)
        }
    )
    leased_job = replace(
        job,
        state="running",
        lease_owner=selector.action_worker_id,
        progress={"model_input_use": selected_stage.model_dump(mode="json")},
    )
    # The action and budget owners are upstream of this selected CAS read.
    worker = VerifiedModelInputUseWorker(
        selection=SimpleNamespace(
            tenant_id=phase.tenant_id,
            cell_id=phase.cell_id,
            route_id=phase.route_id,
            origin=SimpleNamespace(compiled_ref=request.compiled_ref),
            request=request,
            observation_content_sha256=observation_hash,
        ),
        admission=None,
        gateway=None,
        decision=None,
    )
    monkeypatch.setattr(
        model_input_successor_action, "_resolve_action_budget_window", lambda *a, **kw: window
    )
    owner = SimpleNamespace(store=case.store, _native_world_action_owner=case.control)

    def read_stage(
        history_ref: ArtifactRef,
        *,
        current_job: ControlJobRecord = leased_job,
        expected_world_checkpoint: NativeModelInputUseWorldCheckpointV1 | None = None,
    ) -> tuple[ModelInputUseActionPhase, ModelInputSuccessorSelection]:
        return _read_model_input_use_stage(
            owner,
            worker=worker,
            job=current_job,
            payload=payload,
            history=SimpleNamespace(checkpoint=SimpleNamespace(input_bindings_ref=history_ref)),
            expected_world_checkpoint=expected_world_checkpoint,
        )

    assert read_stage(bindings) == (phase, selector)
    foreign_profile = case.store.put_json(
        {"fixture": "exact-method-bindings"},
        ArtifactWriteOptions(
            kind="foundry.input_bindings",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.other_foundry_input_view", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert foreign_profile.artifact_id == bindings.artifact_id
    assert foreign_profile.manifest_profile_sha256 != bindings.manifest_profile_sha256
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="generic_native_model_input_use_stage_binding_mismatch",
    ):
        read_stage(foreign_profile)

    # Only these independently verified world-checkpoint refs reach the stage reader.
    expected_world = NativeModelInputUseWorldCheckpointV1.model_construct(
        model_input_use_phase_ref=selected_stage.phase_ref,
        model_input_successor_selection_ref=selected_stage.semantic_successor_ref,
    )
    assert read_stage(bindings, expected_world_checkpoint=expected_world) == (phase, selector)

    manifest = case.store.get_manifest(selected_stage.semantic_successor_ref)
    alternate_view = case.store.put_json(
        selector,
        ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            env=EnvInfo(python="3.14", platform="alternate-stage-view", deps_lock_hash="fixture"),
            inputs=manifest.inputs,
            canon=manifest.canon,
            tenant_context=manifest.tenant_context,
        ),
        return_selected_profile=True,
    )
    assert alternate_view.artifact_id == selected_stage.semantic_successor_ref.artifact_id
    assert (
        alternate_view.manifest_profile_sha256
        != selected_stage.semantic_successor_ref.manifest_profile_sha256
    )
    alternate_stage = selected_stage.model_copy(update={"semantic_successor_ref": alternate_view})
    substituted_job = replace(
        leased_job, progress={"model_input_use": alternate_stage.model_dump(mode="json")}
    )
    assert read_stage(bindings, current_job=substituted_job) == (phase, selector)
    with pytest.raises(
        CycleSubstrateContextOwnerError, match="generic_native_model_input_use_stage_not_replayed"
    ) as refused:
        read_stage(bindings, current_job=substituted_job, expected_world_checkpoint=expected_world)
    assert str(refused.value.__cause__) == (
        "generic_native_model_input_use_stage_selected_view_changed"
    )


@pytest.mark.parametrize("owner_stops", [False, True], ids=["new-progress", "lost-lease"])
def test_native_source_bracket_reopens_actual_worker_after_authority_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owner_stops: bool
) -> None:
    """The closing worker read uses actual SQL, independently of source replay."""
    from polisyos.runtime.http.services.acquisition_action_service import (
        VerifiedModelInputUseWorker,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlJobLeaseLostError
    from polisyos.runtime.quality import native_generic_context

    case = _case(tmp_path, monkeypatch)
    stored = _put(case.store, "runtime.control_job_payload.acquisition", "native-bracket")
    job = _job(
        case,
        job_id="native-source-bracket",
        kind="acquisition",
        run_id="logical-run",
        payload_ref=str(stored.artifact_id),
    )
    leased = case.database.lease_next_job(worker_id="bracket-worker", lease_seconds=60)
    assert leased is not None and leased.job_id == job.job_id
    received = {"job_id": job.job_id}
    scope = object()
    problem = object()
    bridge = object()
    fact = object()
    active = True

    with case.database.job_execution_fence(
        job_id=job.job_id,
        worker_id="bracket-worker",
        attempt=leased.attempt,
        still_active=lambda: active,
    ):
        admission = case.database.current_execution_job_admission()
        worker = VerifiedModelInputUseWorker(
            selection=object(), admission=admission, gateway=None, decision=None
        )
        action = SimpleNamespace(control_service=case.control)
        observed = []

        def reopen_worker(owner, *, expected_worker):
            nonlocal active
            assert owner is scope
            observed.append(expected_worker)
            if len(observed) == 2:
                if owner_stops:
                    active = False
                else:
                    case.database.update_progress_state(
                        job_id=job.job_id,
                        state="running",
                        progress={"model_input_use": {"phase": "changed-after-read"}},
                        expected_lease_owner="bracket-worker",
                        expected_attempt=leased.attempt,
                    )
            # Isolate the upstream B/PA2 replay. This record deliberately
            # carries the earlier progress from the same admitted lease.
            return action, worker, admission.job, received

        def reopen_source(owner, *, bridge, selected_b, problem):
            assert owner is scope
            assert selected_b is worker.selection
            return fact

        monkeypatch.setattr(
            native_generic_context, "_fresh_native_model_input_use_worker", reopen_worker
        )
        monkeypatch.setattr(native_generic_context, "_current_bridge", lambda _owner: bridge)
        monkeypatch.setattr(
            native_generic_context, "_read_native_model_input_use_source_selection", reopen_source
        )

        def read():
            return native_generic_context._read_current_native_model_input_use_sources(
                scope, problem=problem
            )

        if owner_stops:
            with pytest.raises(ControlJobLeaseLostError, match="no longer active"):
                read()
            assert "model_input_use" not in case.database.get_job(job.job_id).progress
        else:
            current_source, current_worker, current_job, current_payload = read()
            assert current_source is fact and current_worker is worker
            assert current_payload == received
            assert "model_input_use" not in admission.job.progress
            assert current_job.progress["model_input_use"] == {"phase": "changed-after-read"}
        assert observed == [None, worker]


def test_native_post_write_world_read_refuses_removed_selected_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A produced world checkpoint still needs its exact selected profile at use."""
    from polisyos.runtime.quality import native_generic_context
    from polisyos.runtime.quality.diagnostic_events import (
        DiagnosticEventContractError,
        validate_diagnostic_event,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
        NativeModelInputUseWorldCheckpointV1,
        NativeModelInputUseWorldSourceRowV1,
    )
    from polisyos.runtime.quality.model_input_successor_selection import (
        MODEL_INPUT_SUCCESSOR_SELECTION_KIND,
    )

    case = _case(tmp_path, monkeypatch)
    store = case.store

    def ref(kind: str, label: str) -> ArtifactRef:
        return _put(store, kind, label)

    checkpoint = NativeModelInputUseWorldCheckpointV1(
        predecessor_terminal_ref=ref("runtime_quality.acquisition_route_loop_receipt", "terminal"),
        historical_native_world_checkpoint_ref=ref(
            "runtime_quality.acquisition_candidate_world_checkpoint", "old-world"
        ),
        historical_native_action_job_id="native-prior",
        native_input_collection_ref=ref(
            "runtime_quality.native_derivation_input_checkpoint", "collection"
        ),
        native_input_bindings_ref=ref("foundry.input_bindings", "bindings"),
        model_input_use_phase_ref=ref("runtime.quality.model_input_use_action_phase", "phase"),
        model_input_successor_selection_ref=ref(MODEL_INPUT_SUCCESSOR_SELECTION_KIND, "selection"),
        context_job_ref=ref("runtime.quality.cycle_substrate_context_job", "context"),
        original_generic_input_ref=ref(
            "runtime.quality.generic_cycle_simulation_n5_input", "input"
        ),
        original_profile_ref=ref("runtime.quality.generic_cycle_simulation_profile", "profile"),
        world_model_ref=ref("runtime.quality.world_model_record", "world"),
        source_job_id="source-nl",
        action_job_id="native-use",
        run_id="logical-run",
        tenant_id="tenant-a",
        cell_id="cell-a",
        route_id="sha256:" + "a" * 64,
        current_profile_selection_ref="sha256:" + "b" * 64,
        selected_b_source_node_id="B",
        source_rows=(
            NativeModelInputUseWorldSourceRowV1(
                source_node_id="B",
                occurrence_ref=ref("catalog.scoped_measurement_occurrence", "occurrence"),
                source_receipt_ref=ref("epoch.activated_overlay_admission_receipt", "receipt"),
                source_passport_ref=ref("epoch.acquisition_passport_snapshot", "passport"),
                observation_id="fixture-b",
                observation_content_sha256="sha256:" + "c" * 64,
                canonical_value="1",
                canonical_unit="dimensionless",
            ),
        ),
    )
    owner = SimpleNamespace(
        store=store, _native_action_event_log=case.control._diagnostic_event_log
    )
    selected = native_generic_context._persist_use_checkpoint(owner, checkpoint)
    assert native_generic_context._is_native_model_input_use_checkpoint(owner, selected)
    assert selected.manifest_profile_sha256 is not None
    manifest = store.get_manifest(selected)
    inputs = checkpoint.lineage_inputs()
    assert sorted(manifest.inputs, key=lambda item: item.role) == sorted(
        inputs, key=lambda item: item.role
    )
    assert manifest.same_input_closure is not None
    input_ids = tuple(sorted({str(item.artifact_id) for item in inputs}))
    assert manifest.same_input_closure.evidence_input_refs == input_ids
    (recorded,) = case.control._diagnostic_event_log.list_events(
        event_id=native_generic_context._use_checkpoint_event_id(checkpoint), limit=2
    )
    event = recorded.event
    assert event.event_type == "polisyos.runtime.native.model_input_use_world_checkpoint.v1"
    assert event.event_source == "polisyos.runtime.quality.native_generic_context"
    assert event.phase == "model_input_use_world_selection"
    assert event.state_after == "cycle_input_candidate_only"
    assert event.artifact_refs == (str(selected.artifact_id),)
    assert event.input_refs == input_ids
    for updates, code in (
        (
            {"event_source": "polisyos.runtime.quality.acquisition_route_loop"},
            "diagnostic_event_source_not_allowed",
        ),
        ({"payload_ref": None}, "authority_cas_missing"),
    ):
        with pytest.raises(DiagnosticEventContractError) as refused:
            validate_diagnostic_event(event.model_copy(update=updates))
        assert refused.value.code == code
    sidecar = store._manifest_path_for_ref(selected.artifact_id, selected.manifest_profile_sha256)
    preserved = sidecar.read_bytes()
    # This control stops at the exact selected CAS read. It does not claim
    # that the fixture's stand-in source bodies can authorize the handoff.
    handoff = GenericCycleNativeWorldContextHandoffV1.model_construct(
        native_world_checkpoint_ref=selected
    )
    sidecar.unlink()
    try:
        assert store.has(selected.artifact_id)
        with pytest.raises(FileNotFoundError):
            native_generic_context.resolve_native_world_handoff(
                owner, handoff=handoff, problem=object(), context_owner=None, repo_root=None
            )
    finally:
        sidecar.write_bytes(preserved)
    assert native_generic_context._is_native_model_input_use_checkpoint(owner, selected)
