"""Actual admission publication, source recheck and control-capacity witnesses."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.resilience import GuardedDependencyProxy
from polisyos.runtime.http.services._control_contracts import _ControlJobAdmissionDiagnosticBinding
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmissionError,
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
from tests.unit.runtime.http.test_control_plane_store import (
    _cancellation_proof,
    _job_creation_event,
    _job_execution_scope,
    _sql_cancel,
)
from tests.unit.runtime.http.test_control_service_di import _fixture_claims
from tests.unit.runtime.quality.test_runtime_event_log import _event


def _stores(tmp_path: Path, backend: str) -> tuple[ControlPlaneStore, ControlPlaneStore]:
    kwargs: dict[str, Any] = {
        "backend": backend,
        "sqlite_path": tmp_path / "admission-publication.sqlite3",
    }
    if backend == "postgres":
        dsn = os.getenv("POLISYOS_TEST_C57_DISPOSABLE_PG_DSN")
        if not dsn:
            pytest.skip("dedicated disposable PostgreSQL DSN not supplied")
        kwargs["postgres_dsn"] = dsn
    return ControlPlaneStore(**kwargs), ControlPlaneStore(**kwargs)


def _creation_args(*, initial_state: str = "pending") -> dict[str, Any]:
    job_id = f"admission-publication-{uuid.uuid4().hex}"
    run_id = f"run-{job_id}"
    created = _job_creation_event(execution_scope=_job_execution_scope())
    created.update(job_id=job_id, run_id=run_id)
    return {
        "job_id": job_id,
        "kind": "workflow_run",
        "run_id": run_id,
        "pipeline_id": None,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {"candidate": True},
        "capability_manifest_ref": "sha256:manifest-admission",
        "payload_ref": "sha256:payload-b",
        "submitted_by": "denis",
        "creation_event_payload": created,
        "initial_state": initial_state,
        "initial_error_message": "controlled_admission_refusal"
        if initial_state == "failed"
        else None,
        "initial_progress": {"state": initial_state, "phase": "job_admission"},
    }


def _row_count(store: ControlPlaneStore, table: str, job_id: str) -> int:
    queries = {
        "control_job_progress": "SELECT count(*) AS count FROM control_job_progress WHERE job_id = ?",
        "control_job_events": "SELECT count(*) AS count FROM control_job_events WHERE job_id = ?",
        "control_outbox_events": "SELECT count(*) AS count FROM control_outbox_events WHERE job_id = ?",
        "control_diagnostic_events": (
            "SELECT count(*) AS count FROM control_diagnostic_events WHERE job_id = ?"
        ),
    }
    row = store._fetchone(queries[table], (job_id,))  # noqa: SLF001
    assert row is not None
    return int(row["count"] if isinstance(row, Mapping) else row[0])


def _assert_absent(store: ControlPlaneStore, job_id: str) -> None:
    assert store.get_job(job_id) is None
    for table in (
        "control_job_progress",
        "control_job_events",
        "control_outbox_events",
        "control_diagnostic_events",
    ):
        assert _row_count(store, table, job_id) == 0


def _prepare(owner: ControlPlaneStore, log: RuntimeDiagnosticEventLog, args: dict[str, Any]):
    basis = owner.prepare_job_creation(
        job_id=args["job_id"],
        initial_state=args["initial_state"],
        creation_event_payload=args["creation_event_payload"],
    )
    binding = _ControlJobAdmissionDiagnosticBinding(
        control_job_id=args["job_id"],
        control_run_id=args["run_id"],
        source_event_job_state=args["initial_state"],
        source_event_payload_sha256=basis.source_payload_sha256,
        prepared_at=basis.prepared_at,
        bound_job_record_refs=(args["payload_ref"], args["capability_manifest_ref"]),
    )
    event = _event(
        producer_component="polisyos.runtime.control",
        event_id=f"evt-{uuid.uuid4().hex}",
        event_source="polisyos.runtime.control",
        event_type="polisyos.runtime.diagnostic.phase_transition.v1",
        event_time=datetime.now(UTC),
        job_id=args["job_id"],
        run_id=args["run_id"],
        tenant_id="tenant-b",
        cell_id="cell-b",
        execution_profile="dev",
        phase="job_admission",
        state_before=None,
        state_after=args["initial_state"],
        artifact_refs=(),
        input_refs=(),
        dedupe_key=None,
    )
    payload = {
        "execution_scope": {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": "established",
            "source": "job_admission",
            "limitation_code": None,
        },
        "control_job_execution_binding": binding.model_dump(mode="json"),
    }
    prepared = log.prepare(
        event, payload=payload, payload_policy=DiagnosticEventPayloadPolicy(inline_max_bytes=0)
    )
    return basis, prepared


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize("initial_state", ["pending", "failed"])
def test_prepared_values_publish_atomically_with_actual_event_time_and_fresh_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str, initial_state: str
) -> None:
    owner, reader = _stores(tmp_path, backend)
    cas = FileSystemCAS(tmp_path / "cas")
    log = RuntimeDiagnosticEventLog(store=owner, artifact_store=cas)
    args = _creation_args(initial_state=initial_state)
    basis, prepared = _prepare(owner, log, args)
    _assert_absent(reader, args["job_id"])
    assert not hasattr(basis, "source_event_id")
    assert not hasattr(basis, "fact_created_at")
    original_emit = owner._emit_job_outbox_event  # noqa: SLF001
    observations: list[str] = []

    def observe_uncommitted(**kwargs: Any) -> None:
        original_emit(**kwargs)
        observations.append(args["job_id"])
        _assert_absent(reader, args["job_id"])

    monkeypatch.setattr(owner, "_emit_job_outbox_event", observe_uncommitted)
    try:
        result = owner.create_job(
            **args, creation_basis=basis, prepared_admission_diagnostics=(prepared,)
        )
        assert observations == [args["job_id"]]
        current = reader.get_job(result.job_id)
        assert current is not None and current.state == initial_state
        assert current.progress["diagnostic_event_ids"]
        assert current.progress["evidence_spine_handoffs"]
        diagnostic = reader.list_diagnostic_events(job_id=result.job_id)[0]
        fresh_log = RuntimeDiagnosticEventLog(
            store=reader, artifact_store=FileSystemCAS(tmp_path / "cas")
        )
        payload = fresh_log.load_payload(diagnostic)
        assert payload is not None
        source = reader.get_job_admission_diagnostic_source_event_record(
            event_id=diagnostic.event.event_id, payload=payload
        )
        assert source.job_id == result.job_id and source.event_id > 0
        assert source.payload_sha256 == basis.source_payload_sha256
        # A phase event carries the precise source time. The diagnostic row's
        # recording time is a distinct, whole-second Store value, not a clock
        # ordering assertion against the source's microsecond timestamp.
        assert diagnostic.event.event_time == source.created_at
        persisted = reader._fetchone(  # noqa: SLF001
            "SELECT created_at FROM control_diagnostic_events WHERE row_id = ? AND event_id = ?",
            (diagnostic.row_id, diagnostic.event.event_id),
        )
        assert persisted is not None
        stored_time = persisted["created_at"]
        persisted_time = (
            stored_time
            if isinstance(stored_time, datetime)
            else datetime.fromisoformat(stored_time)
        )
        assert persisted_time.tzinfo is not None
        assert diagnostic.created_at == persisted_time.astimezone(UTC)
        assert diagnostic.created_at.microsecond == 0
        assert payload["control_job_execution_binding"]["prepared_at"]
        assert "source_event_created_at" not in payload["control_job_execution_binding"]
        if initial_state == "pending":
            reader.mark_running(job_id=result.job_id, worker_id="ready-reader")
            assert reader.get_job(result.job_id).progress["diagnostic_event_ids"] == [
                diagnostic.event.event_id
            ]
        else:
            with pytest.raises(ControlJobLeaseLostError):
                reader.mark_running(job_id=result.job_id, worker_id="no-terminal-revival")
    finally:
        reader.close()
        owner.close()


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_prepared_retry_after_rollback_preserves_bytes_without_advertising_event_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    owner, reader = _stores(tmp_path, backend)
    cas = FileSystemCAS(tmp_path / "cas")
    log = RuntimeDiagnosticEventLog(store=owner, artifact_store=cas)
    args = _creation_args()
    basis, prepared = _prepare(owner, log, args)
    original_append = owner.append_diagnostic_event

    def append_then_fail(**kwargs: Any) -> Any:
        original_append(**kwargs)
        raise RuntimeError("controlled_after_diagnostic_insert")

    try:
        with monkeypatch.context() as patcher:
            patcher.setattr(owner, "append_diagnostic_event", append_then_fail)
            with pytest.raises(RuntimeError, match="controlled_after_diagnostic_insert"):
                owner.create_job(
                    **args, creation_basis=basis, prepared_admission_diagnostics=(prepared,)
                )
        _assert_absent(reader, args["job_id"])
        assert prepared.payload_ref is not None
        from polisyos.core.artifacts import ArtifactID

        assert cas.get_bytes(ArtifactID.model_validate(prepared.payload_ref))
        result = owner.create_job(
            **args, creation_basis=basis, prepared_admission_diagnostics=(prepared,)
        )
        diagnostic = reader.list_diagnostic_events(job_id=result.job_id)[0]
        assert diagnostic.payload_sha256 == prepared.payload_sha256
        assert diagnostic.event.event_id == json.loads(prepared.event_json)["event_id"]
        assert reader.list_job_state_transitions(result.job_id) == ["pending"]
    finally:
        reader.close()
        owner.close()


@pytest.mark.parametrize("tamper", ["job", "scope", "hash", "purpose", "state", "unknown_profile"])
def test_present_but_wrong_prepared_basis_refuses_without_any_job_publication(
    tmp_path: Path, tamper: str
) -> None:
    owner, reader = _stores(tmp_path, "sqlite")
    log = RuntimeDiagnosticEventLog(store=owner, artifact_store=FileSystemCAS(tmp_path / "cas"))
    args = _creation_args()
    basis, prepared = _prepare(owner, log, args)
    event, payload = prepared.publication_values()
    assert payload is not None
    if tamper == "job":
        payload["control_job_execution_binding"]["control_job_id"] = "another-job"
    elif tamper == "scope":
        event = event.model_copy(update={"tenant_id": "another-tenant"})
    elif tamper == "hash":
        payload["control_job_execution_binding"]["source_event_payload_sha256"] = (
            "sha256:" + "f" * 64
        )
    elif tamper == "purpose":
        payload["control_job_execution_binding"]["purpose"] = "worker_authority"
    elif tamper == "state":
        payload["control_job_execution_binding"]["source_event_job_state"] = "failed"
    else:
        payload["control_job_execution_binding"]["schema_version"] = "unknown_admission_profile"
    bad = log.prepare(event, payload=payload)
    try:
        with pytest.raises((ControlJobExecutionAdmissionError, ValidationError)):
            owner.create_job(**args, creation_basis=basis, prepared_admission_diagnostics=(bad,))
        _assert_absent(reader, args["job_id"])
    finally:
        reader.close()
        owner.close()


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_prepare_a_publish_b_publish_a_preserves_actual_job_sources_and_append_order(
    tmp_path: Path, backend: str
) -> None:
    owner, reader = _stores(tmp_path, backend)
    log = RuntimeDiagnosticEventLog(store=owner, artifact_store=FileSystemCAS(tmp_path / "cas"))
    first_args, second_args = _creation_args(), _creation_args()
    first_basis, first_prepared = _prepare(owner, log, first_args)
    second_basis, second_prepared = _prepare(owner, log, second_args)
    try:
        second = owner.create_job(
            **second_args,
            creation_basis=second_basis,
            prepared_admission_diagnostics=(second_prepared,),
        )
        second_source = reader._get_job_created_source_event_record(second.job_id)  # noqa: SLF001
        first = owner.create_job(
            **first_args,
            creation_basis=first_basis,
            prepared_admission_diagnostics=(first_prepared,),
        )
        first_source = reader._get_job_created_source_event_record(first.job_id)  # noqa: SLF001
        assert first_source.event_id > second_source.event_id
        assert reader.list_job_state_transitions(first.job_id) == ["pending"]
        assert reader.list_job_state_transitions(second.job_id) == ["pending"]
        selected = {
            record.event.job_id: record
            for record in reader.list_diagnostic_events(limit=1000)
            if record.event.job_id in {first.job_id, second.job_id}
        }
        assert selected[first.job_id].row_id > selected[second.job_id].row_id
        for job_id in (first.job_id, second.job_id):
            diagnostic = selected[job_id]
            payload = log.load_payload(diagnostic)
            assert payload is not None
            assert (
                reader.get_job_admission_diagnostic_source_event_record(
                    event_id=diagnostic.event.event_id, payload=payload
                ).job_id
                == job_id
            )
    finally:
        reader.close()
        owner.close()


@pytest.mark.asyncio
async def test_stalled_admission_cas_does_not_hold_other_job_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _build_control_service(tmp_path)
    store = service._control_store  # noqa: SLF001
    raw = store._target  # noqa: SLF001
    admin = ControlPlaneStore(backend="sqlite", sqlite_path=raw._sqlite_path)  # noqa: SLF001
    other = admin.create_job(**_creation_args())
    entered, release = threading.Event(), threading.Event()
    log = service._diagnostic_event_log  # noqa: SLF001
    original_prepare, original_put = log.prepare, log.artifact_store.put_json
    basis_ids: list[str] = []
    prepare_creation = raw.prepare_job_creation

    def observe_basis(**kwargs: Any):
        basis = prepare_creation(**kwargs)
        basis_ids.append(basis.job_id)
        return basis

    def force_supported_cas(event, **kwargs: Any):
        policy = kwargs["payload_policy"]
        kwargs["payload_policy"] = replace(policy, inline_max_bytes=0)
        return original_prepare(event, **kwargs)

    def stalled_put(payload, options, **kwargs: Any):
        if options.kind == "runtime.diagnostic_event_payload":
            entered.set()
            assert release.wait(10), "CAS control was not released"
        return original_put(payload, options, **kwargs)

    monkeypatch.setattr(raw, "prepare_job_creation", observe_basis)
    monkeypatch.setattr(log, "prepare", force_supported_cas)
    monkeypatch.setattr(log.artifact_store, "put_json", stalled_put)
    claims = _fixture_claims()
    request = NaturalLanguageRunRequest(
        request="Prepare an admission with a controlled CAS pause.", llm_model="simulated-qwen"
    )

    async def launch():
        return await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: asyncio.run(launch()))
            try:
                assert entered.wait(10), "admission did not reach actual diagnostic CAS"
                assert len(basis_ids) == 1
                _assert_absent(admin, basis_ids[0])
                operation_id = "other-job-cancel-during-cas"
                cancelled = _sql_cancel(
                    admin,
                    job_id=other.job_id,
                    operation_id=operation_id,
                    authorization_proof=_cancellation_proof(
                        other.job_id, operation_id=operation_id
                    ),
                )
                assert cancelled.state == "cancelled"
                assert admin.get_cancelled_job_verified_record(other.job_id).state == "cancelled"
                assert not release.is_set()
            finally:
                release.set()
            launched = future.result(timeout=10)
        assert admin.get_job(launched.job_id).state == "pending"
    finally:
        release.set()
        admin.close()
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("worker_state", ["running", "completed", "failed", "cancelled"])
async def test_fast_worker_or_cancellation_cannot_be_overwritten_by_late_admission_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker_state: str
) -> None:
    """The real worker runs immediately after create returns, before enqueue resumes."""
    service = _build_control_service(tmp_path)
    store = service._control_store  # noqa: SLF001
    assert isinstance(store, GuardedDependencyProxy)
    raw = store._target  # noqa: SLF001
    admin = ControlPlaneStore(backend="sqlite", sqlite_path=raw._sqlite_path)  # noqa: SLF001
    create = raw.create_job
    before_claim: list[dict[str, Any]] = []
    advanced_progress: list[dict[str, Any]] = []
    claims = _fixture_claims().model_copy(update={"tenant_id": "tenant-b", "cell_id": "cell-b"})

    def handle(job: ControlJobRecord) -> None:
        before_claim.append(dict(job.progress))
        progress = {**job.progress, "state": worker_state, "phase": "actual_worker_advanced"}
        if worker_state == "completed":
            store.complete_job(job_id=job.job_id, progress=progress)
        elif worker_state == "failed":
            store.fail_job(job_id=job.job_id, progress=progress, error_message="controlled_failure")
        elif worker_state == "cancelled":
            operation_id = f"cancel-{job.job_id}"
            # This reused proof is a SQL-isolation fixture, not an HTTP authorization witness.
            _sql_cancel(
                admin,
                job_id=job.job_id,
                authorization_proof=_cancellation_proof(
                    job.job_id,
                    operation_id=operation_id,
                    expected_lease_owner=job.lease_owner,
                    expected_attempt=job.attempt,
                ),
                operation_id=operation_id,
                expected_lease_owner=job.lease_owner,
                expected_attempt=job.attempt,
            )
        else:
            store.update_progress_state(job_id=job.job_id, state="running", progress=progress)
        advanced = admin.get_job(job.job_id)
        assert advanced is not None
        advanced_progress.append(advanced.progress)

    def create_then_dispatch(**kwargs: Any) -> ControlJobRecord:
        record = create(**kwargs)
        worker = ControlWorker(store=store, handler=handle, worker_id="fast-admission-worker")
        try:
            assert worker.dispatch_once()
        finally:
            worker.stop()
        return record

    monkeypatch.setattr(raw, "create_job", create_then_dispatch)
    try:
        request = NaturalLanguageRunRequest(
            request="A finite candidate request.", llm_model="simulated-qwen", context={}
        )
        launched = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        current = admin.get_job(launched.job_id)
        assert current is not None and current.state == worker_state
        assert len(before_claim) == len(advanced_progress) == 1
        assert len(before_claim[0]["diagnostic_event_ids"]) == 3
        # Compare the full durable owner result before enqueue resumes; generic
        # worker progress does not become the cancellation authority band.
        assert current.progress == advanced_progress[0]
        if worker_state == "cancelled":
            verified = admin.get_cancelled_job_verified_record(launched.job_id)
            assert verified.state == "cancelled"
            assert verified.progress == advanced_progress[0]
            assert current.progress["state"] == before_claim[0]["state"]
            assert current.progress["cancellation"]["disposition"] == "publication_fenced"
            assert current.progress["cancellation"]["physical_stop_status"] == "not_established"
        else:
            assert current.progress["state"] == worker_state
        admission_ids = set(before_claim[0]["diagnostic_event_ids"])
        diagnostics = store.list_diagnostic_events(job_id=launched.job_id)
        assert admission_ids.issubset({event.event.event_id for event in diagnostics})
        assert all(
            event.event.phase == "job_admission"
            for event in diagnostics
            if event.event.event_id in admission_ids
        )
        response = service.get_job_status(launched.job_id)
        assert response.state == response.execution_status == worker_state
        if worker_state == "cancelled":
            assert response.progress == advanced_progress[0]
            assert response.cancellation_disposition == "publication_fenced"
            assert response.physical_stop_status == "not_established"
        if worker_state != "running":
            with pytest.raises(ControlJobLeaseLostError):
                store.update_progress_state(
                    job_id=launched.job_id, state="pending", progress={"state": "pending"}
                )
        assert admin.get_job(launched.job_id).progress == current.progress
    finally:
        admin.close()
        service.close()


@pytest.mark.asyncio
async def test_slow_job_is_claimed_with_real_admission_diagnostic_links(tmp_path: Path) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="A finite pending request.", llm_model="simulated-qwen", context={}
        )
        claims = _fixture_claims()
        launched = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        store = service._control_store  # noqa: SLF001
        pending = store.get_job(launched.job_id)
        assert pending is not None and pending.state == "pending"
        admission_ids = set(pending.progress["diagnostic_event_ids"])
        assert len(admission_ids) == 3
        leased = store.lease_next_job(worker_id="slow-admission-worker")
        assert leased is not None and leased.job_id == launched.job_id
        assert set(leased.progress["diagnostic_event_ids"]) == admission_ids
        assert store.list_job_state_transitions(launched.job_id) == ["pending", "running"]
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("proof_state", ["running", "completed", "failed"])
async def test_diagnostic_source_is_reconciled_again_after_actual_cas_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, proof_state: str
) -> None:
    service = _build_control_service(tmp_path)
    store = service._control_store  # noqa: SLF001
    raw = store._target  # noqa: SLF001
    admin = ControlPlaneStore(backend="sqlite", sqlite_path=raw._sqlite_path)  # noqa: SLF001
    args = _creation_args()
    job = store.create_job(**args)
    entered, release = threading.Event(), threading.Event()
    log = service._diagnostic_event_log  # noqa: SLF001
    original_prepare, original_put = log.prepare, log.artifact_store.put_json
    emissions: list[object] = []

    def force_supported_cas(event, **kwargs: Any):
        kwargs["payload_policy"] = replace(kwargs["payload_policy"], inline_max_bytes=0)
        return original_prepare(event, **kwargs)

    def stalled_put(payload, options, **kwargs: Any):
        if options.kind == "runtime.diagnostic_event_payload":
            entered.set()
            assert release.wait(10), "CAS source control was not released"
        return original_put(payload, options, **kwargs)

    monkeypatch.setattr(log, "prepare", force_supported_cas)
    monkeypatch.setattr(log.artifact_store, "put_json", stalled_put)

    def handle(leased: ControlJobRecord) -> None:
        admission = store.current_execution_job_admission()
        if proof_state == "completed":
            store.complete_job(job_id=leased.job_id, progress={"state": "completed"})
        elif proof_state == "failed":
            store.fail_job(
                job_id=leased.job_id,
                progress={"state": "failed"},
                error_message="controlled terminal source",
            )
        emissions.append(
            service._emit_runtime_diagnostic_event(  # noqa: SLF001
                execution_scope=admission.scope,
                job_id=leased.job_id,
                run_id=leased.run_id,
                execution_profile="dev",
                phase="controlled_io_recheck",
                event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                state_before="running",
                state_after=proof_state,
                event_payload={"attempt": leased.attempt},
            )
        )

    worker = ControlWorker(store=store, handler=handle, worker_id="io-recheck-worker")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker.dispatch_once)
            try:
                assert entered.wait(10), "worker did not reach the actual diagnostic CAS"
                current = admin.get_job(job.job_id)
                assert current is not None
                if proof_state == "running":
                    operation_id = "cancel-during-diagnostic-cas"
                    _sql_cancel(
                        admin,
                        job_id=job.job_id,
                        operation_id=operation_id,
                        expected_lease_owner=current.lease_owner,
                        expected_attempt=current.attempt,
                        authorization_proof=_cancellation_proof(
                            job.job_id,
                            operation_id=operation_id,
                            expected_lease_owner=current.lease_owner,
                            expected_attempt=current.attempt,
                        ),
                    )
                else:
                    source = admin.get_job_terminal_source_event_record(job.job_id)
                    altered = {**source.payload, "controlled_content_change_after_prepare": True}
                    admin._execute(  # noqa: SLF001
                        "UPDATE control_job_events SET payload_json = ? WHERE job_id = ? "
                        "AND event_id = ?",
                        (json.dumps(altered, sort_keys=True), job.job_id, source.event_id),
                    )
                    # State/owner/attempt and JSON shape remain valid; only the
                    # actual content identity changed after the first proof.
                    assert admin.get_job_terminal_source_event_record(
                        job.job_id
                    ).payload_sha256 != (source.payload_sha256)
                assert not release.is_set()
            finally:
                release.set()
            assert future.result(timeout=10)
        assert len(emissions) == 1 and emissions[0].status == "not_persisted"
        assert not any(
            record.event.phase == "controlled_io_recheck"
            for record in store.list_diagnostic_events(job_id=job.job_id)
        )
        if proof_state == "running":
            assert admin.get_cancelled_job_verified_record(job.job_id).state == "cancelled"
        else:
            assert admin.get_job(job.job_id).state == proof_state
    finally:
        release.set()
        worker.stop()
        admin.close()
        service.close()


@pytest.mark.asyncio
async def test_dev_preparation_failure_keeps_only_real_ids_and_a_typed_initial_limitation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _build_control_service(tmp_path)
    log = service._diagnostic_event_log  # noqa: SLF001

    def unavailable(*_args: object, **_kwargs: object):
        raise OSError("controlled_diagnostic_cas_unavailable")

    monkeypatch.setattr(log, "prepare", unavailable)
    try:
        request = NaturalLanguageRunRequest(
            request="A candidate with unavailable optional diagnostics.", llm_model="simulated-qwen"
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert job is not None and job.state == "pending"
        assert job.progress["diagnostic_event_ids"] == []
        assert job.progress["diagnostic_event_preparation_status"] == "limited"
        assert job.progress["diagnostic_event_preparation_limitation_code"] == (
            "runtime_diagnostic_event_persistence_failed"
        )
        assert service._control_store.list_diagnostic_events(job_id=job.job_id) == []  # noqa: SLF001
    finally:
        service.close()


def test_preparation_reentry_refuses_before_cas_when_caller_holds_a_writer_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, reader = _stores(tmp_path, "sqlite")
    cas = FileSystemCAS(tmp_path / "cas")
    log = RuntimeDiagnosticEventLog(store=owner, artifact_store=cas)
    args = _creation_args()
    reached: list[str] = []

    def forbidden(*_args: object, **_kwargs: object):
        reached.append("cas")
        raise AssertionError("CAS called under the Store writer transaction")

    monkeypatch.setattr(cas, "put_json", forbidden)
    try:
        with (
            owner._job_transaction(),  # noqa: SLF001
            pytest.raises(RuntimeError, match="diagnostic_preparation_inside_store_transaction"),
        ):
            _prepare(owner, log, args)
        assert reached == []
        _assert_absent(reader, args["job_id"])
    finally:
        reader.close()
        owner.close()
