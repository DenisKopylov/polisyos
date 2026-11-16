"""Store mechanics for Generic initial reconciliation only.

The fixture uses real ControlPlaneStore job creation, lease, completion, lifecycle
rows, and diagnostic preparation. Its synthetic Core/N5 refs and test-only private
owner grant exercise SQL publication and accessor checks; they are not evidence
of a real Generic source, N5 execution, ledger reconciliation, or authority proof.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.http.services.control_plane_store as store_module
import polisyos.runtime.quality.acquisition_evaluation as evaluation_module
from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.http.services.adapters.core_run import derive_control_job_core_run_id
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmissionError,
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
from tests.unit.runtime.http.test_control_plane_store_generic_initial import (
    _artifact_ref,
    _create_job,
    _initial_frontier_bundle,
    _lease_job,
    _sha,
)

_EVENT_TYPE = "polisyos.runtime.generic.initial_reconciliation.v1"
_EVENT_PHASE = "generic_initial_reconciliation"


@dataclass(frozen=True)
class _PublicationFixture:
    store: ControlPlaneStore
    sqlite_path: Path
    job: ControlJobRecord
    initial: Any
    event_log: RuntimeDiagnosticEventLog
    event: DiagnosticEvent
    selector_payload: dict[str, Any]
    prepared_event: Any
    proof: object
    publication: Any


def _read_row(
    sqlite_path: Path,
    query: str,
    parameters: tuple[Any, ...],
) -> dict[str, Any] | None:
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(query, parameters).fetchone()
    return dict(row) if row is not None else None


def _count(sqlite_path: Path, query: str, parameters: tuple[Any, ...]) -> int:
    with sqlite3.connect(sqlite_path) as connection:
        row = connection.execute(query, parameters).fetchone()
    assert row is not None
    return int(row[0])


def _source_snapshot(fixture: _PublicationFixture) -> dict[str, Any]:
    job_id = fixture.job.job_id
    values = {
        "job": _read_row(
            fixture.sqlite_path,
            "SELECT * FROM control_jobs WHERE job_id = ?",
            (job_id,),
        ),
        "progress": _read_row(
            fixture.sqlite_path,
            "SELECT * FROM control_job_progress WHERE job_id = ?",
            (job_id,),
        ),
        "creation_event": _read_row(
            fixture.sqlite_path,
            "SELECT event_id, payload_json FROM control_job_events "
            "WHERE job_id = ? AND event_type = 'job_created'",
            (job_id,),
        ),
        "terminal_event": _read_row(
            fixture.sqlite_path,
            "SELECT event_id, payload_json FROM control_job_events "
            "WHERE job_id = ? AND event_type = 'job_completed'",
            (job_id,),
        ),
        "completion_outbox": _read_row(
            fixture.sqlite_path,
            "SELECT event_id, event_key, payload_json FROM control_outbox_events "
            "WHERE topic = 'control.job.completed' AND job_id = ?",
            (job_id,),
        ),
    }
    assert all(value is not None for value in values.values())
    return values


def _publication_counts(fixture: _PublicationFixture) -> dict[str, int]:
    event_id = fixture.event.event_id
    key = fixture.initial.key
    key_values = (
        key.tenant_id,
        key.cell_id,
        key.source_job_id,
        key.design_problem_ref,
        key.candidate_id,
        key.family,
    )
    return {
        "origin_events": _count(
            fixture.sqlite_path,
            "SELECT COUNT(*) FROM control_diagnostic_events WHERE event_id = ?",
            (event_id,),
        ),
        "frontier_heads": _count(
            fixture.sqlite_path,
            "SELECT COUNT(*) FROM runtime_generic_model_input_evaluation_frontier_heads "
            "WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ? "
            "AND design_problem_ref = ? AND candidate_id = ? AND family = ?",
            key_values,
        ),
        "frontier_versions": _count(
            fixture.sqlite_path,
            "SELECT COUNT(*) FROM runtime_generic_model_input_evaluation_frontier_versions "
            "WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ? "
            "AND design_problem_ref = ? AND candidate_id = ? AND family = ?",
            key_values,
        ),
    }


def _register_owner_grant(
    store: ControlPlaneStore,
    *,
    initial: Any,
    prepared_event: Any,
    publication: Any,
) -> object:
    """Install the test-only grant needed to exercise Store's real accessor."""
    proof = evaluation_module._VerifiedGenericInitialReconciliation()
    event, payload = prepared_event.publication_values()
    with evaluation_module._GENERIC_INITIAL_RECONCILIATION_PROOF_LOCK:
        evaluation_module._GENERIC_INITIAL_RECONCILIATION_PROOFS[proof] = (
            store,
            evaluation_module._generic_initial_cas_identity(initial),
            exact_n5_content_hash({"event": event.model_dump(mode="json"), "payload": payload}),
            publication,
        )
    return proof


def _fixture(
    tmp_path: Path,
    *,
    ordinary_initial: bool = False,
) -> _PublicationFixture:
    sqlite_path = tmp_path / "generic-initial-reconciliation.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    job = _create_job(store, job_id="reconciliation-source", run_id="run-reconciliation")
    worker, attempt = _lease_job(store, job, "worker-reconciliation")
    key, _, _, _, initial = _initial_frontier_bundle(tmp_path, job)

    core_manifest_ref = _artifact_ref(
        tmp_path,
        "selected-core-manifest",
        "core.run_manifest",
    )
    compiled_ref = _artifact_ref(
        tmp_path,
        "selected-compiled-cycle",
        "runtime.compiled_recursive_generation_cycle",
    )
    assert job.run_id is not None
    core_run_id = derive_control_job_core_run_id(
        job_id=job.job_id,
        control_run_id=job.run_id,
        attempt=attempt,
    )
    progress: dict[str, Any] = {
        "phase": "source_completed",
        "core_run_id": core_run_id,
        "core_run_attempt": attempt,
        "core_manifest_artifact_ref": core_manifest_ref.model_dump(mode="json"),
        "manifest_ref": str(core_manifest_ref.artifact_id),
        "compiled_recursive_generation_cycle_artifact_ref": compiled_ref.model_dump(mode="json"),
        "compiled_recursive_generation_cycle_ref": str(compiled_ref.artifact_id),
    }
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            progress=progress,
            generic_model_input_initial_frontiers=(initial,) if ordinary_initial else (),
        )

    completed_job = store.get_job(job.job_id)
    assert completed_job is not None and completed_job.state == "completed"
    creation = store._get_job_created_source_event_record(job.job_id)
    terminal = store.get_job_terminal_source_event_record(job.job_id)
    outbox = store.get_job_completed_outbox_event(job.job_id)
    assert terminal.event_type == "job_completed"
    assert outbox is not None

    value = store_module._generic_model_input_initial_frontier_value(initial)
    frontier = store_module._generic_model_input_frontier_record(
        key=key,
        revision=1,
        value=value,
    )
    event_id = evaluation_module._generic_initial_reconciliation_selector_event_id(
        frontier.frontier_ref
    )
    reconciliation_ref = _artifact_ref(
        tmp_path,
        "synthetic-reconciliation-record",
        evaluation_module.GenericModelInputInitialReconciliation.ARTIFACT_KIND,
    )
    selector_payload = {
        "frontier_ref": frontier.frontier_ref,
        "reconciliation_ref": reconciliation_ref.model_dump(mode="json"),
    }
    event = DiagnosticEvent(
        event_id=event_id,
        event_source=evaluation_module.PRODUCER,
        event_type=_EVENT_TYPE,
        event_time=datetime(2026, 11, 15, 12, 0, tzinfo=UTC),
        event_subject=f"run/{job.run_id}/candidate/{key.candidate_id}",
        schema_name="polisyos.runtime.quality.diagnostic_event",
        schema_version="1.0",
        trace_id=f"trace-{job.job_id}",
        span_id="span-initial-reconciliation",
        parent_span_id=None,
        run_id=job.run_id,
        job_id=job.job_id,
        tenant_id=key.tenant_id,
        cell_id=key.cell_id,
        producer_component=evaluation_module.PRODUCER,
        producer_version="1.0",
        execution_profile=completed_job.effective_execution_profile,
        phase=_EVENT_PHASE,
        state_before="original_simulation_blocked",
        state_after="historical_reconciliation",
        payload_ref=None,
        artifact_refs=(str(reconciliation_ref.artifact_id),),
        input_refs=tuple(
            sorted(
                {
                    str(compiled_ref.artifact_id),
                    str(core_manifest_ref.artifact_id),
                    str(initial.basis.initial_observation.execution_ref.artifact_id),
                }
            )
        ),
        blocking_status="non_blocking",
        redaction_policy_ref=None,
        duplicate_of=None,
        dedupe_key=event_id,
    )
    event_log = RuntimeDiagnosticEventLog(
        store=store,
        artifact_store=FileSystemCAS(tmp_path / "diagnostic-event-artifacts"),
    )
    prepared_event = event_log.prepare(
        event,
        payload=selector_payload,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )
    event, prepared_payload = prepared_event.publication_values()
    publication = evaluation_module._GenericInitialReconciliationPublication(
        source_job_id=job.job_id,
        run_id=job.run_id,
        tenant_id=key.tenant_id,
        cell_id=key.cell_id,
        source_attempt=attempt,
        source_creation_event_id=creation.event_id,
        source_creation_payload_sha256=creation.payload_sha256,
        source_terminal_event_id=terminal.event_id,
        source_terminal_payload_sha256=terminal.payload_sha256,
        source_completion_outbox_event_id=outbox.event_id,
        source_completion_outbox_payload_sha256=exact_n5_content_hash(outbox.payload),
        source_core_run_id=core_run_id,
        source_core_manifest_ref=core_manifest_ref,
        source_compiled_ref=compiled_ref,
        reconciliation_ref=reconciliation_ref,
        reconciliation_content_hash=_sha("synthetic-reconciliation-content"),
        frontier_ref=frontier.frontier_ref,
        event_id=event_id,
    )
    proof = _register_owner_grant(
        store,
        initial=initial,
        prepared_event=prepared_event,
        publication=publication,
    )
    assert prepared_payload == selector_payload
    return _PublicationFixture(
        store=store,
        sqlite_path=sqlite_path,
        job=completed_job,
        initial=initial,
        event_log=event_log,
        event=event,
        selector_payload=selector_payload,
        prepared_event=prepared_event,
        proof=proof,
        publication=publication,
    )


def _commit(fixture: _PublicationFixture, *, store: ControlPlaneStore | None = None) -> Any:
    owner = store or fixture.store
    return owner.commit_generic_initial_reconciliation(
        proof=fixture.proof,
        prepared_event=fixture.prepared_event,
        initial=fixture.initial,
    )


def _assert_no_new_publication(fixture: _PublicationFixture) -> None:
    assert fixture.store.list_diagnostic_events(event_id=fixture.event.event_id, limit=2) == []
    assert fixture.store.read_generic_model_input_frontier(fixture.initial.key) is None
    assert _publication_counts(fixture) == {
        "origin_events": 0,
        "frontier_heads": 0,
        "frontier_versions": 0,
    }


def _mutate_source(fixture: _PublicationFixture, mutation: str) -> None:
    job_id = fixture.job.job_id
    with sqlite3.connect(fixture.sqlite_path) as connection:
        if mutation == "creation_bytes":
            connection.execute(
                "UPDATE control_job_events SET payload_json = payload_json || ' ' "
                "WHERE job_id = ? AND event_type = 'job_created'",
                (job_id,),
            )
        elif mutation == "creation_scope":
            row = connection.execute(
                "SELECT payload_json FROM control_job_events "
                "WHERE job_id = ? AND event_type = 'job_created'",
                (job_id,),
            ).fetchone()
            assert row is not None
            payload = json.loads(row[0])
            payload["execution_scope"]["tenant_id"] = "changed-tenant"
            connection.execute(
                "UPDATE control_job_events SET payload_json = ? "
                "WHERE job_id = ? AND event_type = 'job_created'",
                (json.dumps(payload, sort_keys=True), job_id),
            )
        elif mutation == "terminal_bytes":
            connection.execute(
                "UPDATE control_job_events SET payload_json = payload_json || ' ' "
                "WHERE job_id = ? AND event_type = 'job_completed'",
                (job_id,),
            )
        elif mutation == "outbox_payload":
            row = connection.execute(
                "SELECT payload_json FROM control_outbox_events "
                "WHERE topic = 'control.job.completed' AND job_id = ?",
                (job_id,),
            ).fetchone()
            assert row is not None
            payload = json.loads(row[0])
            payload["progress"]["tampered_after_grant"] = True
            connection.execute(
                "UPDATE control_outbox_events SET payload_json = ? "
                "WHERE topic = 'control.job.completed' AND job_id = ?",
                (json.dumps(payload, sort_keys=True), job_id),
            )
        elif mutation == "job_state":
            connection.execute(
                "UPDATE control_jobs SET state = 'failed' WHERE job_id = ?",
                (job_id,),
            )
        elif mutation == "attempt":
            connection.execute(
                "UPDATE control_jobs SET attempt = attempt + 1 WHERE job_id = ?",
                (job_id,),
            )


def test_store_commit_publishes_one_origin_and_exact_retry_preserves_source_bytes(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source_before = _source_snapshot(fixture)
    original_job = fixture.store.get_job(fixture.job.job_id)
    assert original_job == fixture.job

    first = _commit(fixture)
    second = _commit(fixture)

    assert first == second
    assert first.revision == 1
    assert first.frontier_ref == fixture.publication.frontier_ref
    assert first.selected_evaluation == fixture.initial.basis.initial_observation
    assert fixture.store.read_generic_model_input_frontier(fixture.initial.key) == first
    (origin,) = fixture.store.list_diagnostic_events(
        event_id=fixture.event.event_id,
        limit=2,
    )
    assert origin.event == fixture.event
    assert origin.event.event_type == _EVENT_TYPE
    assert origin.payload_ref == fixture.prepared_event.payload_ref
    assert origin.payload_sha256 == fixture.prepared_event.payload_sha256
    assert _source_snapshot(fixture) == source_before
    assert fixture.store.get_job(fixture.job.job_id) == original_job
    assert _publication_counts(fixture) == {
        "origin_events": 1,
        "frontier_heads": 1,
        "frontier_versions": 1,
    }


def test_unregistered_or_foreign_store_proof_cannot_publish(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    fabricated = evaluation_module._VerifiedGenericInitialReconciliation()
    with pytest.raises(ValueError, match="generic_initial_reconciliation_owner_proof_missing"):
        fixture.store.commit_generic_initial_reconciliation(
            proof=fabricated,
            prepared_event=fixture.prepared_event,
            initial=fixture.initial,
        )

    foreign_store = ControlPlaneStore(backend="sqlite", sqlite_path=fixture.sqlite_path)
    with pytest.raises(ValueError, match="generic_initial_reconciliation_owner_proof_missing"):
        _commit(fixture, store=foreign_store)
    _assert_no_new_publication(fixture)


def test_changed_initial_or_prepared_event_is_refused_before_publication(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    _, _, _, _, changed_initial = _initial_frontier_bundle(
        tmp_path,
        fixture.job,
        candidate_id="different-candidate",
    )
    with pytest.raises(
        ValueError,
        match="generic_initial_reconciliation_publication_substituted",
    ):
        fixture.store.commit_generic_initial_reconciliation(
            proof=fixture.proof,
            prepared_event=fixture.prepared_event,
            initial=changed_initial,
        )

    altered_event = fixture.event.model_copy(update={"state_after": "substituted"})
    changed_prepared = fixture.event_log.prepare(
        altered_event,
        payload=fixture.selector_payload,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )
    with pytest.raises(
        ValueError,
        match="generic_initial_reconciliation_publication_substituted",
    ):
        fixture.store.commit_generic_initial_reconciliation(
            proof=fixture.proof,
            prepared_event=changed_prepared,
            initial=fixture.initial,
        )
    _assert_no_new_publication(fixture)


@pytest.mark.parametrize(
    ("mutation", "error", "exception_type"),
    [
        ("terminal_bytes", "generic_initial_reconciliation_source_changed", ValueError),
        ("outbox_payload", "generic_initial_reconciliation_source_changed", ValueError),
        ("job_state", "generic_initial_reconciliation_completion_changed", ValueError),
        ("attempt", "generic_initial_reconciliation_completion_changed", ValueError),
    ],
)
def test_changed_source_after_owner_grant_refuses_without_origin_or_frontier(
    tmp_path: Path,
    mutation: str,
    error: str,
    exception_type: type[Exception],
) -> None:
    fixture = _fixture(tmp_path)
    _mutate_source(fixture, mutation)

    with pytest.raises(exception_type, match=error):
        _commit(fixture)

    assert fixture.store.list_diagnostic_events(event_id=fixture.event.event_id, limit=2) == []
    assert fixture.store.read_generic_model_input_frontier(fixture.initial.key) is None
    assert _publication_counts(fixture) == {
        "origin_events": 0,
        "frontier_heads": 0,
        "frontier_versions": 0,
    }


@pytest.mark.parametrize("field", ["source_core_manifest_ref", "source_compiled_ref"])
def test_owner_publication_does_not_override_independent_selected_source_refs(
    tmp_path: Path, field: str
) -> None:
    fixture = _fixture(tmp_path)
    before = _source_snapshot(fixture)
    original_ref = getattr(fixture.publication, field)
    changed_ref = original_ref.model_copy(
        update={"manifest_profile_sha256": _sha("changed-selected-profile")}
    )
    changed_publication = replace(fixture.publication, **{field: changed_ref})
    # Script a dishonest upstream snapshot while leaving the real SQL source,
    # outbox and initial/event bytes unchanged. Store must check its own owner.
    proof = _register_owner_grant(
        fixture.store,
        initial=fixture.initial,
        prepared_event=fixture.prepared_event,
        publication=changed_publication,
    )
    with pytest.raises(ValueError, match="generic_initial_reconciliation_compiled_source_changed"):
        fixture.store.commit_generic_initial_reconciliation(
            proof=proof, prepared_event=fixture.prepared_event, initial=fixture.initial
        )
    assert _source_snapshot(fixture) == before
    _assert_no_new_publication(fixture)


def test_completion_outbox_hash_uses_decoded_payload_not_sql_whitespace(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with sqlite3.connect(fixture.sqlite_path) as connection:
        connection.execute(
            "UPDATE control_outbox_events SET payload_json = payload_json || ' ' "
            "WHERE topic = 'control.job.completed' AND job_id = ?",
            (fixture.job.job_id,),
        )
    after_whitespace = _source_snapshot(fixture)
    committed = _commit(fixture)
    assert committed.revision == 1
    assert _source_snapshot(fixture) == after_whitespace


def test_creation_bytes_and_scope_changes_after_grant_refuse_without_publication(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    _mutate_source(fixture, "creation_bytes")
    with pytest.raises(
        ValueError,
        match="generic_initial_reconciliation_source_changed",
    ):
        _commit(fixture)

    _mutate_source(fixture, "creation_scope")
    with pytest.raises(
        ControlJobExecutionAdmissionError,
        match="control_job_created_event_outbox_mismatch",
    ):
        _commit(fixture)
    _assert_no_new_publication(fixture)


def test_existing_ordinary_initial_origin_blocks_second_origin(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, ordinary_initial=True)
    existing = fixture.store.read_generic_model_input_frontier(fixture.initial.key)
    assert existing is not None and existing.revision == 1

    with pytest.raises(
        ValueError,
        match="generic_initial_reconciliation_origin_ambiguous",
    ):
        _commit(fixture)

    assert fixture.store.read_generic_model_input_frontier(fixture.initial.key) == existing
    assert fixture.store.list_diagnostic_events(event_id=fixture.event.event_id, limit=2) == []
    assert _publication_counts(fixture) == {
        "origin_events": 0,
        "frontier_heads": 1,
        "frontier_versions": 1,
    }


def test_conflicting_existing_selector_event_refuses_frontier_publication(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    conflicting_event = fixture.event.model_copy(update={"state_after": "conflicting-origin"})
    conflicting_prepared = fixture.event_log.prepare(
        conflicting_event,
        payload=fixture.selector_payload,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )
    event, payload = conflicting_prepared.publication_values()
    fixture.store.append_diagnostic_event(
        event=event,
        payload_ref=conflicting_prepared.payload_ref,
        payload_inline=payload if conflicting_prepared.inline_payload else None,
        payload_sha256=conflicting_prepared.payload_sha256,
    )

    with pytest.raises(
        ValueError,
        match="generic_initial_reconciliation_selector_conflict",
    ):
        _commit(fixture)

    (persisted,) = fixture.store.list_diagnostic_events(event_id=fixture.event.event_id, limit=2)
    assert persisted.event == conflicting_event
    assert fixture.store.read_generic_model_input_frontier(fixture.initial.key) is None
    assert _publication_counts(fixture) == {
        "origin_events": 1,
        "frontier_heads": 0,
        "frontier_versions": 0,
    }


def test_frontier_insert_failure_rolls_back_origin_event_head_and_version(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source_before = _source_snapshot(fixture)
    with sqlite3.connect(fixture.sqlite_path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_generic_initial_frontier_version "
            "BEFORE INSERT ON runtime_generic_model_input_evaluation_frontier_versions "
            "BEGIN SELECT RAISE(ABORT, 'injected_generic_initial_frontier_version_failure'); END"
        )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="injected_generic_initial_frontier_version_failure",
    ):
        _commit(fixture)

    assert fixture.store.list_diagnostic_events(event_id=fixture.event.event_id, limit=2) == []
    assert fixture.store.read_generic_model_input_frontier(fixture.initial.key) is None
    assert _source_snapshot(fixture) == source_before
    assert _publication_counts(fixture) == {
        "origin_events": 0,
        "frontier_heads": 0,
        "frontier_versions": 0,
    }


def test_concurrent_store_owners_reconcile_to_one_exact_occurrence(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    second_store = ControlPlaneStore(backend="sqlite", sqlite_path=fixture.sqlite_path)
    second_proof = _register_owner_grant(
        second_store,
        initial=fixture.initial,
        prepared_event=fixture.prepared_event,
        publication=fixture.publication,
    )
    barrier = threading.Barrier(2)

    def commit_after_barrier(store: ControlPlaneStore, proof: object) -> Any:
        barrier.wait(timeout=10)
        return store.commit_generic_initial_reconciliation(
            proof=proof,
            prepared_event=fixture.prepared_event,
            initial=fixture.initial,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(commit_after_barrier, fixture.store, fixture.proof)
        second_future = executor.submit(commit_after_barrier, second_store, second_proof)
        first = first_future.result(timeout=30)
        second = second_future.result(timeout=30)

    assert first == second
    assert first.revision == 1
    assert fixture.store.read_generic_model_input_frontier(fixture.initial.key) == first
    (origin,) = fixture.store.list_diagnostic_events(
        event_id=fixture.event.event_id,
        limit=2,
    )
    assert origin.event == fixture.event
    assert _publication_counts(fixture) == {
        "origin_events": 1,
        "frontier_heads": 1,
        "frontier_versions": 1,
    }
