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
    FileSystemCAS,
    SchemaInfo,
)
from polisyos.core.contracts.runtime import RunDetails
from polisyos.runtime.http.routes import runs
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.model_input_successor_action import (
    ModelInputSuccessorActionRequest,
    ModelInputUseActionCheckpoint,
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
) -> Any:
    request = ModelInputSuccessorActionRequest(
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
