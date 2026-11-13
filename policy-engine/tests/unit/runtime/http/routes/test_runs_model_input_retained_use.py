"""Current-use projection keeps genuine lifecycle selection and original N5 identity.

These are API boundary tests: CAS, completion event and outbox are real; the
historical semantic/PA2/N5 replay owner is isolated at its typed return seam.
They do not establish a numerical producer or an institutional appointment.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    ArtifactTenantContextInfo,
    ArtifactWriteOptions,
    FileSystemCAS,
    SchemaInfo,
    artifact_ref_for_manifest,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.runtime import (
    RunModelInputUseN5SuccessorProjectionV2,
    RunModelInputUseN5SuccessorResponse,
)
from polisyos.runtime.http.routes import runs
from polisyos.runtime.http.services import acquisition_n5_projection, model_input_successor_action
from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
from polisyos.runtime.quality.acquisition_evaluation import GenericModelInputSelectedEvaluation
from polisyos.runtime.quality.agent_action_authority import MODEL_INPUT_USE_ACTION_KIND
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationN5ExecutionV5,
    GenericN5ResolvedResult,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.core.contracts.test_runtime_n5_bodies import (
    _artifact_ref,
    _model_input_retained_projection_payload,
    _result_body_payload,
)
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _scope


def _case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, retained: bool = True):
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    control = _build_control_service(tmp_path / "service", artifact_store=store)
    database = control._control_store
    sqlite_path = control._resolve_control_sqlite_path()
    dto = _model_input_retained_projection_payload()
    run_id, action_job_id = dto["run_id"], dto["action_job_id"]
    original_job = dto["original_action_job_id"] if retained else action_job_id
    semantic_ref = (
        dto["original_semantic_successor_ref"]
        if retained
        else dto["current_semantic_successor_ref"]
    )
    result_ref = store.put_json(
        {"numerical_fixture": "preserved original bytes"},
        ArtifactWriteOptions(
            kind="polisyos.runtime.joint_simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="policyos.runtime.n5.joint_simulation_result", version="1.0.0"),
            tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    result_ref = artifact_ref_for_manifest(store.get_manifest(result_ref))
    original = GenericModelInputSelectedEvaluation(
        input_ref=dto["original_input_ref"],
        execution_ref=dto["original_execution_ref"],
        result_ref=result_ref,
        semantic_successor_ref=semantic_ref,
        action_job_id=original_job,
    )
    request = {
        "compiled_ref": _artifact_ref("runtime.compiled_recursive_generation_cycle", "a"),
        "blocked_execution_ref": dto["blocked_source"]["blocked_execution_ref"],
        "routing_report_ref": dto["blocked_source"]["routing_report_ref"],
        "activation_receipt_ref": _artifact_ref(
            "epoch.activated_overlay_admission_receipt", "b"
        ).model_copy(update={"media_type": "application/vnd.polisyos.epoch+json"}),
        "observation_id": "new-observation-occurrence",
        "idempotency_key": "new-current-use",
    }
    payload = {
        "action_kind": MODEL_INPUT_USE_ACTION_KIND,
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": run_id,
        "route_id": "current-route",
        "decision_ref": str(dto["current_authority_decision_ref"].artifact_id),
        "request": {
            name: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
            for name, value in request.items()
        },
    }
    payload_ref = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="runtime.control_job_payload.acquisition",
            media_type="application/json",
            schema=SchemaInfo(name="runtime.control_job_payload.acquisition", version="1.0"),
            tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    created = {
        "job_id": action_job_id,
        "run_id": run_id,
        "job_kind": "acquisition",
        "pipeline_id": None,
        "payload_ref": str(payload_ref.artifact_id),
        "submitted_by": "tester",
        "requested_execution_profile": None,
        "effective_execution_profile": "governed",
        "policy_flags": {},
        "capability_manifest_ref": None,
        "execution_scope": _scope(),
    }
    database.create_job(
        **{
            name: value
            for name, value in created.items()
            if name not in {"job_kind", "execution_scope"}
        },
        kind="acquisition",
        creation_event_payload=created,
    )
    worker = "current-use-worker"
    leased = database.lease_next_job(worker_id=worker, lease_seconds=60)
    assert leased is not None and leased.job_id == action_job_id
    checkpoint = model_input_successor_action.ModelInputUseActionCheckpoint(
        phase_ref=dto["current_action_phase_ref"],
        semantic_successor_ref=dto["current_semantic_successor_ref"],
        execution_ref=None if retained else original.execution_ref,
        result_ref=None if retained else original.result_ref,
        schema_version="polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
        evaluation_decision_ref=dto["current_use_decision_ref"],
        evaluation_current_basis_ref=dto["current_basis_ref"],
    )
    terminal_selector = checkpoint.execution_ref or checkpoint.evaluation_decision_ref
    progress = {
        "receipt_phase": "terminal",
        "terminal_receipt_ref": str(terminal_selector.artifact_id),
        "model_input_use": checkpoint.model_dump(mode="json", exclude_none=True),
    }
    with database.job_execution_fence(
        job_id=action_job_id, worker_id=worker, attempt=leased.attempt
    ):
        database.complete_job(job_id=action_job_id, run_id=run_id, progress=progress)
    origin = SimpleNamespace(
        run_id=run_id,
        source_job_id="source-model-input",
        source_cycle=SimpleNamespace(
            design_problem_ref=dto["blocked_source"]["design_problem_ref"],
            cycle_index=0,
            selected_candidate_ref="candidate-model-input",
            selected_candidate_content_hash=dto["blocked_source"]["candidate_content_hash"],
        ),
        n5_execution_ref=request["blocked_execution_ref"],
        routing_report=SimpleNamespace(
            obligation_set_ref=dto["blocked_source"]["model_input_obligation_set_ref"]
        ),
        routing_report_ref=request["routing_report_ref"],
    )
    selection = SimpleNamespace(job_id=action_job_id, route_id=payload["route_id"], origin=origin)
    frontier = SimpleNamespace(
        selected_evaluation=original,
        basis_ref=dto["selected_basis_ref"],
        frontier_ref=dto["frontier_ref"],
        revision=1,
    )
    resolved = GenericN5ResolvedResult(
        result=SimpleNamespace(
            verified_semantic_input_limitation_codes=("candidate_binding_only",)
        ),
        request=None,
    )
    execution = GenericCycleSimulationN5ExecutionV5.model_construct(
        input_ref=original.input_ref,
        result_ref=original.result_ref,
        semantic_successor_ref=original.semantic_successor_ref,
        action_job_id=original.action_job_id,
    )
    history = model_input_successor_action.GenericModelInputUseHistory(
        key=None,
        use=SimpleNamespace(
            comparison_result="equivalent" if retained else "initial",
            decision_ref=dto["current_use_decision_ref"],
            current_basis_ref=dto["current_basis_ref"],
        ),
        decision=SimpleNamespace(
            authority_decision_ref=dto["current_authority_decision_ref"],
            predicate_provenance="recomputed",
        ),
        current_basis=SimpleNamespace(limitations=("current_binding_candidate_only",)),
        selected_basis=SimpleNamespace(limitations=("original_numerical_candidate_only",)),
        prior_evaluation=original if retained else None,
        prior_frontier=frontier if retained else None,
        selected_frontier=frontier,
        frontier_relation="superseded" if retained else "selected",
        selected_frontier_execution=execution,
        selected_frontier_result=resolved,
        prior_execution=execution if retained else None,
        prior_result=resolved if retained else None,
        current_action_result=None if retained else resolved,
    )
    owner_reads = []

    def read_history(selected_control, **kwargs):
        assert selected_control is control
        assert kwargs["selection"] is selection
        assert kwargs["checkpoint"] == checkpoint
        assert kwargs["action_payload_ref"] == str(payload_ref.artifact_id)
        assert kwargs["authority_decision_ref"] == payload["decision_ref"]
        owner_reads.append(checkpoint)
        return history

    monkeypatch.setattr(
        model_input_successor_action,
        "resolve_model_input_successor_history",
        lambda *args, **kwargs: selection,
    )
    monkeypatch.setattr(
        model_input_successor_action, "resolve_model_input_use_evaluation_history", read_history
    )
    action_service = object.__new__(AcquisitionActionService)
    action_service.control_service = control
    authority_reads = []
    monkeypatch.setattr(
        AcquisitionActionService,
        "require_model_input_use_decision_history",
        lambda *args, **kwargs: authority_reads.append(kwargs["decision_ref"]),
    )
    body = {
        **_result_body_payload(candidate=False),
        "artifact_ref": result_ref,
        "selected_manifest_profile_sha256": result_ref.manifest_profile_sha256,
    }
    monkeypatch.setattr(
        acquisition_n5_projection, "n5_numerical_body_payload", lambda **kwargs: body
    )
    return SimpleNamespace(
        control=control,
        database=database,
        sqlite_path=sqlite_path,
        store=store,
        history=history,
        original=original,
        run_id=run_id,
        action_job_id=action_job_id,
        action_service=action_service,
        owner_reads=owner_reads,
        authority_reads=authority_reads,
        checkpoint=checkpoint,
        payload_ref=payload_ref,
    )


def _project(case):
    return runs._model_input_use_n5_successor_projection(
        run_id=case.run_id,
        action_job_id=case.action_job_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        store=case.store,
        control_service=case.control,
        action_service=case.action_service,
    )


@pytest.mark.parametrize("retained", [False, True])
def test_completed_current_use_projects_its_original_selected_result(
    tmp_path, monkeypatch, retained
):
    case = _case(tmp_path, monkeypatch, retained=retained)
    value = _project(case)
    assert type(value) is RunModelInputUseN5SuccessorProjectionV2
    assert value.result_status == "resolved", value.model_dump(mode="json")
    assert value.original_action_job_id == case.original.action_job_id
    assert value.original_execution_ref == case.original.execution_ref
    assert value.original_result_ref == case.original.result_ref
    assert value.current_use_decision_ref == case.checkpoint.evaluation_decision_ref
    assert value.evaluation_provenance == ("retained_prior" if retained else "new_execution")
    assert value.frontier_selection == ("superseded" if retained else "selected")
    assert (value.original_action_job_id != value.action_job_id) is retained
    restored = RunModelInputUseN5SuccessorResponse.model_validate_json(
        RunModelInputUseN5SuccessorResponse.model_validate(
            {"meta": {"request_id": "read-use"}, "result": value}
        ).model_dump_json()
    )
    assert restored.result == value
    assert value.currentness_status == "not_established" and value.publication_authority is False
    assert len(case.owner_reads) == len(case.authority_reads) == 1


@pytest.mark.parametrize(
    "removed", ["terminal_event", "outbox", "owner_history", "result_manifest"]
)
def test_current_use_requires_lifecycle_history_and_original_selected_bytes(
    tmp_path, monkeypatch, removed
):
    case = _case(tmp_path, monkeypatch)
    if removed in {"terminal_event", "outbox"}:
        with sqlite3.connect(case.sqlite_path) as connection:
            if removed == "terminal_event":
                connection.execute(
                    "DELETE FROM control_job_events WHERE job_id=? AND event_type='job_completed'",
                    (case.action_job_id,),
                )
            else:
                connection.execute(
                    "DELETE FROM control_outbox_events WHERE job_id=? AND topic='control.job.completed'",
                    (case.action_job_id,),
                )
    elif removed == "owner_history":
        monkeypatch.setattr(
            model_input_successor_action,
            "resolve_model_input_use_evaluation_history",
            lambda *args, **kwargs: None,
        )
    else:
        ref = case.original.result_ref
        case.store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256).unlink()
    value = _project(case)
    assert value.result_status == "not_established"
    assert value.result_body is None
    assert getattr(value, "original_execution_ref", None) is None
    if removed in {"terminal_event", "outbox"}:
        assert case.owner_reads == []


def test_success_shaped_mutable_progress_does_not_replace_the_completed_use(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    before = _project(case)
    with sqlite3.connect(case.sqlite_path) as connection:
        connection.execute(
            "UPDATE control_job_progress SET progress_json=? WHERE job_id=?",
            ('{"model_input_use":{"forged":true}}', case.action_job_id),
        )
    assert _project(case) == before


def test_retained_use_cannot_relabel_an_original_execution_as_the_current_action(
    tmp_path, monkeypatch
):
    case = _case(tmp_path, monkeypatch)
    wrong = case.history.selected_frontier_execution.model_copy(
        update={"action_job_id": case.action_job_id}
    )
    history = replace(case.history, selected_frontier_execution=wrong)
    monkeypatch.setattr(
        model_input_successor_action,
        "resolve_model_input_use_evaluation_history",
        lambda *args, **kwargs: history,
    )
    value = _project(case)
    assert value.result_status == "not_established" and value.result_body is None


def test_current_use_cannot_substitute_same_bytes_under_another_manifest(tmp_path, monkeypatch):
    from polisyos.core.artifacts import ProducerInfo
    from tests.unit.runtime.quality.test_candidate_experiment_reuse_occurrence import (
        _write_profile_variant,
    )

    case = _case(tmp_path, monkeypatch)
    selected = case.original.result_ref
    foreign = _write_profile_variant(
        case.store, selected, producer=ProducerInfo(component="different.producer", version="1")
    )
    assert foreign.artifact_id == selected.artifact_id
    assert foreign.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert case.store.get_bytes(foreign) == case.store.get_bytes(selected)
    monkeypatch.setattr(
        acquisition_n5_projection,
        "read_selected_n5_result_manifest",
        lambda *args, **kwargs: case.store.get_manifest(foreign),
    )
    value = _project(case)
    assert value.result_status == "not_established"
    assert value.result_body is None and value.original_result_ref is None


def test_current_use_requires_the_historical_authority_owner(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    case.action_service = None
    value = _project(case)
    assert value.result_status == "not_established"
    assert value.result_body is None and value.original_result_ref is None
    assert case.owner_reads == []


def test_unestablished_current_comparison_cannot_reuse_an_old_frontier(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    assert case.checkpoint.execution_ref is None
    assert case.history.selected_frontier.selected_evaluation == case.original
    use = SimpleNamespace(**{**vars(case.history.use), "comparison_result": "not_established"})
    decision = SimpleNamespace(
        **{**vars(case.history.decision), "predicate_provenance": "not_established"}
    )
    history = replace(case.history, use=use, decision=decision)
    monkeypatch.setattr(
        model_input_successor_action,
        "resolve_model_input_use_evaluation_history",
        lambda *args, **kwargs: history,
    )
    value = _project(case)
    assert type(value) is RunModelInputUseN5SuccessorProjectionV2
    assert value.result_status == "not_established"
    assert value.result_body is None and value.original_result_ref is None
    assert value.evaluation_provenance is None
