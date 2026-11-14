"""Control-store mechanics for the Generic initial-observation frontier.

Synthetic typed records and artifact refs below exercise SQL, lifecycle-event,
worker-fence, and tenant-scope behavior only. They are not evidence of a real
Generic N5 producer or its physical proof chain.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.http.services.control_plane_store as store_module
from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, FileSystemCAS, SchemaInfo
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlPlaneStore,
)


def _sha(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _scope(tenant_id: str = "tenant-a", cell_id: str = "cell-a") -> dict[str, object]:
    return {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "actor_subject": "store-test",
        "actor_authenticated": True,
        "actor_roles": ["operator"],
    }


def _create_job(
    store: ControlPlaneStore,
    *,
    job_id: str,
    run_id: str,
    tenant_id: str = "tenant-a",
    cell_id: str = "cell-a",
) -> ControlJobRecord:
    payload = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": "natural_language_run",
        "pipeline_id": None,
        "payload_ref": _sha(f"{job_id}:payload"),
        "submitted_by": "store-test",
        "requested_execution_profile": None,
        "effective_execution_profile": "governed",
        "policy_flags": {},
        "capability_manifest_ref": _sha(f"{job_id}:manifest"),
        "execution_scope": _scope(tenant_id, cell_id),
    }
    return store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="governed",
        policy_flags={},
        capability_manifest_ref=payload["capability_manifest_ref"],
        payload_ref=payload["payload_ref"],
        submitted_by="store-test",
        creation_event_payload=payload,
    )


def _lease_job(store: ControlPlaneStore, job: ControlJobRecord, worker_id: str) -> tuple[str, int]:
    leased = store.lease_next_job(worker_id=worker_id, lease_seconds=60)
    assert leased is not None
    assert leased.job_id == job.job_id
    return worker_id, leased.attempt


def _artifact_ref(tmp_path: Path, label: str, kind: str) -> ArtifactRef:
    cas = FileSystemCAS(tmp_path / "initial-frontier-artifacts")
    return cas.put_json(
        {"fixture_label": label, "kind": kind},
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.test.generic_initial_frontier", version="1.0"),
        ),
        return_selected_profile=True,
    )


def _persist_record(tmp_path: Path, record: Any) -> ArtifactRef:
    return FileSystemCAS(tmp_path / "initial-frontier-artifacts").put_json(
        record.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=record.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=record.ARTIFACT_SCHEMA_NAME, version="1.1"),
        ),
        return_selected_profile=True,
    )


def _rehash_record(record_type: type[Any], fields: dict[str, Any]) -> Any:
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash

    provisional = record_type.model_construct(**fields, content_hash=_sha("placeholder"))
    payload = provisional.model_dump(mode="json", exclude={"content_hash"})
    return record_type.model_validate({**payload, "content_hash": exact_n5_content_hash(payload)})


def _initial_frontier_bundle(
    tmp_path: Path,
    job: ControlJobRecord,
    *,
    tenant_id: str = "tenant-a",
    cell_id: str = "cell-a",
    candidate_id: str = "candidate-a",
) -> tuple[Any, Any, Any, Any, Any]:
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputInitialEvaluation,
        GenericModelInputInitialEvaluationBasis,
        GenericModelInputInitialEvaluationDecision,
    )

    run_id = job.run_id
    assert run_id is not None
    selected = GenericModelInputInitialEvaluation(
        execution_job_id=job.job_id,
        run_id=run_id,
        source_run_id=f"core-{run_id}",
        candidate_content_hash=_sha("candidate-content"),
        input_ref=_artifact_ref(
            tmp_path, "initial-input", "runtime.quality.generic_cycle_simulation_n5_input"
        ),
        execution_ref=_artifact_ref(
            tmp_path,
            "initial-execution",
            "runtime.quality.generic_cycle_simulation_n5_execution",
        ),
        result_ref=_artifact_ref(
            tmp_path, "initial-result", "polisyos.runtime.joint_simulation_result"
        ),
        current_method_input_bindings_ref=_artifact_ref(
            tmp_path, "method-bindings", "foundry.input_bindings"
        ),
        model_input_obligation_set_ref=_artifact_ref(
            tmp_path, "obligation-set", "runtime.quality.model_input_obligation_set"
        ),
        context_job_ref=_artifact_ref(
            tmp_path, "context-job", "runtime.quality.cycle_substrate_context_job"
        ),
        n4_source_ref=_artifact_ref(tmp_path, "n4-source", "runtime.generation_source_handoff"),
        profile_ref=_artifact_ref(
            tmp_path, "profile", "runtime.quality.generic_cycle_simulation_profile"
        ),
        observation_content_hash=_sha("observation-content"),
    )
    key = store_module.GenericModelInputEvaluationFrontierKey(
        tenant_id=tenant_id,
        cell_id=cell_id,
        source_job_id=job.job_id,
        design_problem_ref=_sha("design-problem"),
        candidate_id=candidate_id,
    )
    intent = b"synthetic transaction-only numerical intent"
    basis_fields: dict[str, Any] = {
        "schema_version": "GenericModelInputEvaluationBasis@1.1",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": "generic_program_graph_mapped_numpy_methods_v3",
        "basis_role": "evaluated",
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "run_id": run_id,
        "source_job_id": job.job_id,
        "design_problem_ref": key.design_problem_ref,
        "design_problem_basis_ref": _sha("design-problem-basis"),
        "candidate_id": key.candidate_id,
        "initial_observation": selected,
        "bound_state_snapshot_ref": _artifact_ref(
            tmp_path, "state-snapshot", "foundry.state_snapshot"
        ),
        "predicate_provenance": "recomputed",
        "reason_codes": (),
        "limitations": ("synthetic_store_transaction_fixture",),
        "numerical_intent_hex": intent.hex(),
        "numerical_intent_sha256": "sha256:" + hashlib.sha256(intent).hexdigest(),
    }
    basis = _rehash_record(GenericModelInputInitialEvaluationBasis, basis_fields)
    basis_ref = _persist_record(tmp_path, basis)
    decision_fields: dict[str, Any] = {
        "schema_version": "GenericModelInputEvaluationDecision@1.1",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_rule": "generic-program-graph-initial-observation.v1",
        "decision_kind": "initial_observation",
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "run_id": run_id,
        "source_job_id": job.job_id,
        "design_problem_ref": key.design_problem_ref,
        "design_problem_basis_ref": basis.design_problem_basis_ref,
        "candidate_id": key.candidate_id,
        "initial_observation": selected,
        "current_basis_ref": basis_ref,
        "generated_at": "2026-11-14T00:00:00+00:00",
    }
    decision = _rehash_record(GenericModelInputInitialEvaluationDecision, decision_fields)
    decision_ref = _persist_record(tmp_path, decision)
    cas = store_module.GenericModelInputInitialFrontierCAS(
        key=key,
        decision_ref=decision_ref,
        decision=decision,
        basis=basis,
    )
    return key, selected, basis, decision, cas


def _sqlite_counts(
    sqlite_path: Path,
    *,
    job_id: str,
    key: Any,
) -> dict[str, int]:
    key_values = (
        key.tenant_id,
        key.cell_id,
        key.source_job_id,
        key.design_problem_ref,
        key.candidate_id,
        key.family,
    )
    queries = {
        "completion_event": (
            "SELECT COUNT(*) FROM control_job_events "
            "WHERE job_id = ? AND event_type = 'job_completed'",
            (job_id,),
        ),
        "completion_outbox": (
            "SELECT COUNT(*) FROM control_outbox_events "
            "WHERE topic = 'control.job.completed' AND event_key = ? AND job_id = ?",
            (f"{job_id}:job_completed", job_id),
        ),
        "frontier_head": (
            "SELECT COUNT(*) FROM runtime_generic_model_input_evaluation_frontier_heads "
            "WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ? "
            "AND design_problem_ref = ? AND candidate_id = ? AND family = ?",
            key_values,
        ),
        "frontier_version": (
            "SELECT COUNT(*) FROM runtime_generic_model_input_evaluation_frontier_versions "
            "WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ? "
            "AND design_problem_ref = ? AND candidate_id = ? AND family = ?",
            key_values,
        ),
        "use_row": (
            "SELECT COUNT(*) FROM runtime_generic_model_input_evaluation_uses "
            "WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ? "
            "AND design_problem_ref = ? AND candidate_id = ? AND family = ?",
            key_values,
        ),
    }
    with sqlite3.connect(sqlite_path) as connection:
        return {
            name: int(connection.execute(sql, params).fetchone()[0])
            for name, (sql, params) in queries.items()
        }


def _assert_no_completion_or_frontier(
    store: ControlPlaneStore,
    sqlite_path: Path,
    *,
    job_id: str,
    key: Any,
    state: str,
) -> None:
    job = store.get_job(job_id)
    assert job is not None and job.state == state
    assert store.read_generic_model_input_frontier(key) is None
    assert _sqlite_counts(sqlite_path, job_id=job_id, key=key) == {
        "completion_event": 0,
        "completion_outbox": 0,
        "frontier_head": 0,
        "frontier_version": 0,
        "use_row": 0,
    }


def test_default_complete_job_does_not_seed_generic_initial_frontier(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "generic-initial-default.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    job = _create_job(store, job_id="ordinary-default", run_id="run-default")
    worker, attempt = _lease_job(store, job, "worker-default")
    key = store_module.GenericModelInputEvaluationFrontierKey(
        tenant_id="tenant-a",
        cell_id="cell-a",
        source_job_id=job.job_id,
        design_problem_ref=_sha("design-problem"),
        candidate_id="candidate-a",
    )

    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        result = store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            progress={"legacy_progress": "preserved"},
        )

    completed = store.get_job(job.job_id)
    assert result is None
    assert completed is not None and completed.state == "completed"
    assert completed.progress == {
        "legacy_progress": "preserved",
        "execution_owner_binding": {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "requested_execution_profile": None,
            "effective_execution_profile": "governed",
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "lease_owner": worker,
            "attempt": attempt,
        },
    }
    event = store.get_job_terminal_source_event_record(job.job_id)
    assert event.event_type == "job_completed"
    assert "generic_model_input_initial_observations" not in event.payload
    outbox = store.get_job_completed_outbox_event(job.job_id)
    assert "generic_model_input_initial_observations" not in outbox.payload
    assert store.read_generic_model_input_frontier(key) is None
    counts = _sqlite_counts(sqlite_path, job_id=job.job_id, key=key)
    assert counts == {
        "completion_event": 1,
        "completion_outbox": 1,
        "frontier_head": 0,
        "frontier_version": 0,
        "use_row": 0,
    }


def test_initial_frontier_commits_revision_one_without_action_use(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "generic-initial-success.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    job = _create_job(store, job_id="ordinary-initial", run_id="run-initial")
    worker, attempt = _lease_job(store, job, "worker-initial")
    key, selected, basis, decision, cas = _initial_frontier_bundle(tmp_path, job)

    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        result = store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            progress={"ordinary_output": "complete"},
            generic_model_input_initial_frontiers=(cas,),
        )

    assert result is None
    completed = store.get_job(job.job_id)
    assert completed is not None and completed.state == "completed"
    assert completed.progress["ordinary_output"] == "complete"
    (projection,) = completed.progress["generic_model_input_initial_observations"]
    assert (
        projection["schema_version"] == "polisyos.control.generic_initial_observation_checkpoint.v1"
    )
    assert projection["family"] == "generic_program_graph"
    assert projection["subject_kind"] == "initial_observation"
    assert projection["source_job_id"] == job.job_id
    assert projection["selected_evaluation"] == selected.model_dump(mode="json")
    assert projection["basis_ref"] == decision.current_basis_ref.model_dump(mode="json")
    assert projection["basis_content_hash"] == basis.content_hash
    assert projection["decision_ref"] == cas.decision_ref.model_dump(mode="json")
    assert projection["decision_content_hash"] == decision.content_hash
    assert projection["frontier_revision"] == 1
    assert projection["observed_admission"] is False
    assert projection["publication_authority"] is False
    assert selected.execution_job_id == job.job_id
    assert selected.run_id == basis.run_id == decision.run_id == job.run_id
    assert selected.source_run_id != selected.run_id

    event = store.get_job_terminal_source_event_record(job.job_id)
    assert event.event_type == "job_completed"
    assert event.payload["lease_owner"] == worker
    assert event.payload["attempt"] == attempt
    assert event.payload["generic_model_input_initial_observations"] == [projection]
    outbox = store.get_job_completed_outbox_event(job.job_id)
    assert outbox.payload["generic_model_input_initial_observations"] == [projection]
    assert outbox.payload["progress"]["generic_model_input_initial_observations"] == [projection]

    record = store.read_generic_model_input_frontier(key)
    assert record is not None and record.revision == 1
    assert record.selected_evaluation == selected
    assert record.basis_ref == decision.current_basis_ref
    assert record.basis_content_hash == basis.content_hash
    assert record.selection_decision_ref == cas.decision_ref
    assert projection["frontier_ref"] == record.frontier_ref
    assert store.get_generic_model_input_frontier_by_ref(record.frontier_ref) == record
    assert store.get_generic_model_input_use(key=key, action_job_id=job.job_id) is None
    counts = _sqlite_counts(sqlite_path, job_id=job.job_id, key=key)
    assert counts == {
        "completion_event": 1,
        "completion_outbox": 1,
        "frontier_head": 1,
        "frontier_version": 1,
        "use_row": 0,
    }


def test_initial_frontier_discovery_is_scoped_ordered_and_explicitly_truncated(
    tmp_path: Path,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "initial-discovery.sqlite3")
    job = _create_job(store, job_id="ordinary-discovery", run_id="run-discovery")
    worker, attempt = _lease_job(store, job, "worker-discovery")
    first = _initial_frontier_bundle(tmp_path, job, candidate_id="candidate-a")
    second = _initial_frontier_bundle(tmp_path, job, candidate_id="candidate-b")
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            generic_model_input_initial_frontiers=(second[4], first[4]),
        )
    selection = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "source_job_id": job.job_id,
    }
    rows, truncated = store.list_generic_model_input_initial_frontiers_by_source(
        **selection,
        limit=1,
    )
    assert truncated is True
    assert tuple(row.key.candidate_id for row in rows) == ("candidate-a",)
    complete, truncated = store.list_generic_model_input_initial_frontiers_by_source(
        **selection,
        limit=2,
    )
    assert truncated is False
    assert tuple(row.key.candidate_id for row in complete) == ("candidate-a", "candidate-b")
    assert rows[0] == complete[0]
    for changed in (
        {"tenant_id": "foreign-tenant"},
        {"cell_id": "foreign-cell"},
        {"source_job_id": "foreign-job"},
    ):
        assert store.list_generic_model_input_initial_frontiers_by_source(
            **{**selection, **changed},
            limit=2,
        ) == ((), False)


def test_initial_frontier_requires_current_worker_fence(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "generic-initial-no-fence.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    job = _create_job(store, job_id="ordinary-unfenced", run_id="run-unfenced")
    key, _, _, _, cas = _initial_frontier_bundle(tmp_path, job)

    with pytest.raises(
        ControlJobLeaseLostError,
        match="generic_initial_frontier_requires_current_job_fence",
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            progress={},
            generic_model_input_initial_frontiers=(cas,),
        )

    _assert_no_completion_or_frontier(
        store, sqlite_path, job_id=job.job_id, key=key, state="pending"
    )


@pytest.mark.parametrize("mismatch", ["tenant", "cell"])
def test_initial_frontier_requires_admitted_tenant_and_cell(
    tmp_path: Path,
    mismatch: str,
) -> None:
    sqlite_path = tmp_path / f"generic-initial-wrong-{mismatch}.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    job = _create_job(store, job_id=f"ordinary-wrong-{mismatch}", run_id="run-wrong")
    worker, attempt = _lease_job(store, job, f"worker-wrong-{mismatch}")
    tenant_id = "tenant-other" if mismatch == "tenant" else "tenant-a"
    cell_id = "cell-other" if mismatch == "cell" else "cell-a"
    key, _, _, _, cas = _initial_frontier_bundle(
        tmp_path, job, tenant_id=tenant_id, cell_id=cell_id
    )

    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(
            store_module.ControlJobExecutionAdmissionError,
            match="generic_initial_frontier_scope_mismatch",
        ),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            progress={},
            generic_model_input_initial_frontiers=(cas,),
        )

    _assert_no_completion_or_frontier(
        store, sqlite_path, job_id=job.job_id, key=key, state="running"
    )


def test_initial_frontier_duplicate_subject_is_rejected_before_completion(
    tmp_path: Path,
) -> None:
    sqlite_path = tmp_path / "generic-initial-duplicate.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    job = _create_job(store, job_id="ordinary-duplicate", run_id="run-duplicate")
    worker, attempt = _lease_job(store, job, "worker-duplicate")
    key, _, _, _, cas = _initial_frontier_bundle(tmp_path, job)

    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match="generic_initial_frontier_duplicate_subject"),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            progress={},
            generic_model_input_initial_frontiers=(cas, cas),
        )

    _assert_no_completion_or_frontier(
        store, sqlite_path, job_id=job.job_id, key=key, state="running"
    )


def test_initial_frontier_insert_failure_rolls_back_completion_and_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path = tmp_path / "generic-initial-rollback.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    job = _create_job(store, job_id="ordinary-rollback", run_id="run-rollback")
    worker, attempt = _lease_job(store, job, "worker-rollback")
    key, _, _, _, cas = _initial_frontier_bundle(tmp_path, job)
    execute = store._execute

    def fail_initial_version_insert(sql: str, params: tuple[Any, ...]) -> int:
        if "INSERT INTO runtime_generic_model_input_evaluation_frontier_versions" in sql:
            raise RuntimeError("generic_initial_frontier_version_insert_interrupted")
        return execute(sql, params)

    monkeypatch.setattr(store, "_execute", fail_initial_version_insert)
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(RuntimeError, match="generic_initial_frontier_version_insert_interrupted"),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            progress={},
            generic_model_input_initial_frontiers=(cas,),
        )

    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    _assert_no_completion_or_frontier(
        reopened, sqlite_path, job_id=job.job_id, key=key, state="running"
    )
