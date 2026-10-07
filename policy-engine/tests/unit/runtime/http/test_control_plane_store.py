from __future__ import annotations

import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import pytest

import polisyos.runtime.http.services.control_worker as control_worker_module
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
from polisyos.runtime.http.resilience import guard_runtime_control_store
from polisyos.runtime.http.services.control.run_lifecycle import HumanDecisionAuthoritySink
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmissionError,
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests._helpers.policy_design_case_projection import policy_design_case, sha

if TYPE_CHECKING:
    from pathlib import Path


def _make_store(tmp_path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def _job_execution_scope() -> dict[str, object]:
    return {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": "tenant-b",
        "cell_id": "cell-b",
        "actor_subject": "denis",
        "actor_authenticated": True,
        "actor_roles": ["analyst", "operator"],
    }


def _job_creation_event(*, execution_scope: dict[str, object] | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "job_id": "job_execution_admission",
        "run_id": "run_execution_admission",
        "job_kind": "workflow_run",
        "pipeline_id": None,
        "payload_ref": "sha256:payload-b",
        "submitted_by": "denis",
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {"candidate": True},
        "capability_manifest_ref": "sha256:manifest-admission",
    }
    if execution_scope is not None:
        payload["execution_scope"] = execution_scope
    return payload


def _human_decision_sink(
    tmp_path,
    store: ControlPlaneStore,
) -> HumanDecisionAuthoritySink:
    artifact_store = FileSystemCAS(tmp_path / "human-decision-cas")
    return HumanDecisionAuthoritySink(
        artifact_store=artifact_store,
        event_log=RuntimeDiagnosticEventLog(
            store=store,
            artifact_store=artifact_store,
        ),
        reservation_store=store,
    )


def test_human_decision_concurrent_reservation_has_one_sqlite_winner(tmp_path) -> None:
    """Two independent stores cannot reserve one live governed action twice."""

    sqlite_path = tmp_path / "human-decision-reservations.sqlite3"
    stores = (
        ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path),
        ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path),
    )
    barrier = threading.Barrier(2)
    now = datetime(2026, 8, 24, 12, tzinfo=UTC)

    def _reserve(index: int):
        barrier.wait(timeout=10)
        return stores[index].reserve_human_decision_action(
            tenant_id="tenant-a",
            governed_action_key="sha256:" + "a" * 64,
            reservation_id=f"reservation-{index}",
            binding_sha256="sha256:" + "b" * 64,
            now=now,
            lease_seconds=30,
            record_valid_until=now + timedelta(hours=1),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(_reserve, range(2)))

    assert sorted(result.acquired for result in results) == [False, True]
    losing = next(result for result in results if not result.acquired)
    assert losing.issue_code == "DS9-OVERLAPPING-REISSUE"
    assert losing.reservation.state == "reserved"
    winner = next(result for result in results if result.acquired)
    stored = stores[0].get_human_decision_reservation(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "a" * 64,
    )
    assert stored == winner.reservation


def test_human_decision_crash_reservation_requires_reconciliation_before_reuse(
    tmp_path,
) -> None:
    """An expired partial write becomes recovery-required, never a new winner."""

    store = _make_store(tmp_path)
    started_at = datetime(2026, 8, 24, 12, tzinfo=UTC)
    first = store.reserve_human_decision_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "c" * 64,
        reservation_id="reservation-crashed",
        binding_sha256="sha256:" + "d" * 64,
        now=started_at,
        lease_seconds=5,
        record_valid_until=started_at + timedelta(hours=1),
    )
    assert first.acquired is True

    retry = store.reserve_human_decision_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "c" * 64,
        reservation_id="reservation-too-early",
        binding_sha256="sha256:" + "d" * 64,
        now=started_at + timedelta(seconds=6),
        lease_seconds=5,
        record_valid_until=started_at + timedelta(hours=1),
    )

    assert retry.acquired is False
    assert retry.issue_code == "DS9-RESERVATION-RECOVERY-REQUIRED"
    assert retry.reservation.state == "recovery_required"
    reconciled = _human_decision_sink(tmp_path, store).reconcile_empty_reservation(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "c" * 64,
        reservation_id="reservation-crashed",
        reservation_version=first.reservation.reservation_version,
        reconciled_at=started_at + timedelta(seconds=7),
    )
    assert reconciled.state == "reconciled_empty"

    replacement = store.reserve_human_decision_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "c" * 64,
        reservation_id="reservation-replacement",
        binding_sha256="sha256:" + "d" * 64,
        now=started_at + timedelta(seconds=8),
        lease_seconds=5,
        record_valid_until=started_at + timedelta(hours=1),
    )
    assert replacement.acquired is True
    assert replacement.reservation.reservation_version == 2
    historical = store.get_human_decision_reservation_generation(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "c" * 64,
        reservation_version=1,
    )
    assert historical is not None
    assert historical.reservation_id == "reservation-crashed"
    assert historical.state == "reconciled_empty"


def test_human_decision_empty_reconciliation_scans_record_artifacts(tmp_path) -> None:
    """A present record defeats an empty claim even before reservation commit."""

    store = _make_store(tmp_path)
    artifact_store = FileSystemCAS(tmp_path / "human-decision-reconciliation-cas")
    sink = HumanDecisionAuthoritySink(
        artifact_store=artifact_store,
        event_log=RuntimeDiagnosticEventLog(
            store=store,
            artifact_store=artifact_store,
        ),
        reservation_store=store,
    )
    started_at = datetime(2026, 8, 24, 12, tzinfo=UTC)
    first = sink.reserve_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "e" * 64,
        reservation_id="reservation-with-record",
        binding_sha256="sha256:" + "f" * 64,
        now=started_at,
        lease_seconds=1,
        record_valid_until=started_at + timedelta(hours=1),
    )
    retry = sink.reserve_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "e" * 64,
        reservation_id="reservation-retry",
        binding_sha256="sha256:" + "f" * 64,
        now=started_at + timedelta(seconds=2),
        lease_seconds=1,
        record_valid_until=started_at + timedelta(hours=1),
    )
    assert retry.reservation.state == "recovery_required"
    artifact_store.put_json(
        {
            "reservation_id": first.reservation.reservation_id,
            "reservation_version": first.reservation.reservation_version,
        },
        ArtifactWriteOptions(
            kind="runtime_quality.agent_action_human_decision",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.HumanDecisionRecord",
                version="2.0",
            ),
        ),
    )

    with pytest.raises(ValueError, match="DS9-RESERVATION-RECOVERY-REQUIRED"):
        sink.reconcile_empty_reservation(
            tenant_id="tenant-a",
            governed_action_key="sha256:" + "e" * 64,
            reservation_id="reservation-with-record",
            reservation_version=first.reservation.reservation_version,
            reconciled_at=started_at + timedelta(seconds=3),
        )


@pytest.mark.parametrize(
    ("lease_seconds", "valid_seconds", "commit_seconds"),
    [(1, 60, 2), (60, 1, 2)],
)
def test_human_decision_commit_rejects_expired_lease_or_record_validity(
    tmp_path,
    lease_seconds: int,
    valid_seconds: int,
    commit_seconds: int,
) -> None:
    store = _make_store(tmp_path)
    started_at = datetime(2026, 8, 24, 12, tzinfo=UTC)
    reserved = store.reserve_human_decision_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "1" * 64,
        reservation_id="reservation-expiry",
        binding_sha256="sha256:" + "2" * 64,
        now=started_at,
        lease_seconds=lease_seconds,
        record_valid_until=started_at + timedelta(seconds=valid_seconds),
    )
    assert reserved.acquired is True
    commit_at = started_at + timedelta(seconds=commit_seconds)

    with (
        pytest.raises(ValueError, match="DS9-RESERVATION-RECOVERY-REQUIRED"),
        store.hold_human_decision_write_fence(
            tenant_id="tenant-a",
            governed_action_key="sha256:" + "1" * 64,
            reservation_id="reservation-expiry",
            reservation_version=reserved.reservation.reservation_version,
            binding_sha256="sha256:" + "2" * 64,
            acquired_at=commit_at,
            expected_record_valid_until=reserved.reservation.record_valid_until,
        ) as fence,
    ):
        fence.commit(
            record_ref="sha256:" + "3" * 64,
            record_sha256="sha256:" + "3" * 64,
            durable_event_id="event-expired-commit",
            committed_at=commit_at,
        )

    historical = store.get_human_decision_reservation_generation(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "1" * 64,
        reservation_version=reserved.reservation.reservation_version,
    )
    assert historical is not None
    assert historical.state == "reserved"
    assert historical.record_ref is None


def test_human_decision_reservation_preserves_microsecond_lease_boundary(tmp_path) -> None:
    store = _make_store(tmp_path)
    started_at = datetime(2026, 8, 24, 12, 0, 0, 500_000, tzinfo=UTC)
    reserved = store.reserve_human_decision_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "4" * 64,
        reservation_id="reservation-microsecond-boundary",
        binding_sha256="sha256:" + "5" * 64,
        now=started_at,
        lease_seconds=1,
        record_valid_until=started_at + timedelta(minutes=1),
    )

    commit_at = started_at + timedelta(microseconds=750_000)
    with store.hold_human_decision_write_fence(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "4" * 64,
        reservation_id=reserved.reservation.reservation_id,
        reservation_version=reserved.reservation.reservation_version,
        binding_sha256="sha256:" + "5" * 64,
        acquired_at=commit_at,
        expected_record_valid_until=reserved.reservation.record_valid_until,
    ) as fence:
        committed = fence.commit(
            record_ref="sha256:" + "6" * 64,
            record_sha256="sha256:" + "6" * 64,
            durable_event_id="event-before-exact-microsecond-expiry",
            committed_at=commit_at,
        )

    assert committed.state == "committed"
    assert committed.lease_expires_at == started_at + timedelta(seconds=1)


def test_human_decision_empty_reconciliation_cas_rejects_attached_refs(tmp_path) -> None:
    store = _make_store(tmp_path)
    started_at = datetime(2026, 8, 24, 12, tzinfo=UTC)
    reserved = store.reserve_human_decision_action(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "7" * 64,
        reservation_id="reservation-attached-orphan",
        binding_sha256="sha256:" + "8" * 64,
        now=started_at,
        lease_seconds=10,
        record_valid_until=started_at + timedelta(hours=1),
    )
    store.mark_human_decision_recovery_required(
        tenant_id="tenant-a",
        governed_action_key="sha256:" + "7" * 64,
        reservation_id=reserved.reservation.reservation_id,
        reservation_version=reserved.reservation.reservation_version,
        record_ref="sha256:" + "9" * 64,
        record_sha256="sha256:" + "9" * 64,
        durable_event_id="event-attached-orphan",
    )

    with pytest.raises(ValueError, match="DS9-RESERVATION-RECOVERY-REQUIRED"):
        store._reconcile_empty_human_decision_reservation(
            tenant_id="tenant-a",
            governed_action_key="sha256:" + "7" * 64,
            reservation_id=reserved.reservation.reservation_id,
            reservation_version=reserved.reservation.reservation_version,
            reconciled_at=started_at + timedelta(seconds=1),
        )


def test_human_decision_write_fence_prevents_recovery_overtaking_paused_signer(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path = tmp_path / "human-decision-write-fence.sqlite3"
    writer_store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    contender_store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    started_at = datetime(2026, 8, 24, 12, tzinfo=UTC)
    valid_until = started_at + timedelta(hours=1)
    governed_action_key = "sha256:" + "a" * 64
    binding_sha256 = "sha256:" + "b" * 64
    reserved = writer_store.reserve_human_decision_action(
        tenant_id="tenant-a",
        governed_action_key=governed_action_key,
        reservation_id="reservation-paused-writer",
        binding_sha256=binding_sha256,
        now=started_at,
        lease_seconds=1,
        record_valid_until=valid_until,
    )
    hold_fence = getattr(writer_store, "hold_human_decision_write_fence", None)
    assert callable(hold_fence), "durable human-decision write fence is absent"
    writer_entered = threading.Event()
    contender_sql_entered = threading.Event()
    release_writer = threading.Event()
    original_sqlite_connection = contender_store._sqlite_connection

    @contextmanager
    def _witnessed_sqlite_connection():
        contender_sql_entered.set()
        with original_sqlite_connection() as connection:
            yield connection

    monkeypatch.setattr(
        contender_store,
        "_sqlite_connection",
        _witnessed_sqlite_connection,
    )

    def _writer():
        with hold_fence(
            tenant_id="tenant-a",
            governed_action_key=governed_action_key,
            reservation_id=reserved.reservation.reservation_id,
            reservation_version=reserved.reservation.reservation_version,
            binding_sha256=binding_sha256,
            acquired_at=started_at + timedelta(microseconds=500_000),
            expected_record_valid_until=valid_until,
        ) as fence:
            writer_entered.set()
            assert release_writer.wait(timeout=10)
            return fence.commit(
                record_ref="sha256:" + "c" * 64,
                record_sha256="sha256:" + "c" * 64,
                durable_event_id="event-paused-writer",
                committed_at=started_at + timedelta(microseconds=750_000),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer_future = executor.submit(_writer)
        assert writer_entered.wait(timeout=10)
        contender_future = executor.submit(
            contender_store.reserve_human_decision_action,
            tenant_id="tenant-a",
            governed_action_key=governed_action_key,
            reservation_id="reservation-contender",
            binding_sha256=binding_sha256,
            now=started_at + timedelta(seconds=2),
            lease_seconds=1,
            record_valid_until=valid_until,
        )
        assert contender_sql_entered.wait(timeout=10)
        assert not contender_future.done()
        release_writer.set()
        committed = writer_future.result(timeout=10)
        contender = contender_future.result(timeout=10)

    assert committed.state == "committed"
    assert contender.acquired is False
    assert contender.issue_code == "DS9-OVERLAPPING-REISSUE"
    assert contender.reservation.record_ref == "sha256:" + "c" * 64


def test_human_decision_fence_reuses_store_transaction_for_durable_event(
    tmp_path,
) -> None:
    """The existing diagnostic log and reservation finalize in one SQLite lane."""

    from polisyos.runtime.quality.diagnostic_events import (
        DIAGNOSTIC_EVENT_SCHEMA_NAME,
        DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        DiagnosticEvent,
    )

    store = _make_store(tmp_path)
    artifact_store = FileSystemCAS(tmp_path / "human-decision-event-lane-cas")
    event_log = RuntimeDiagnosticEventLog(store=store, artifact_store=artifact_store)
    sink = HumanDecisionAuthoritySink(
        artifact_store=artifact_store,
        event_log=event_log,
        reservation_store=store,
    )
    started_at = datetime.now(UTC).replace(microsecond=0)
    valid_until = started_at + timedelta(hours=1)
    governed_action_key = "sha256:" + "d" * 64
    binding_sha256 = "sha256:" + "e" * 64
    reserved = sink.reserve_action(
        tenant_id="tenant-a",
        governed_action_key=governed_action_key,
        reservation_id="reservation-shared-event-lane",
        binding_sha256=binding_sha256,
        now=started_at,
        lease_seconds=30,
        record_valid_until=valid_until,
    )
    event = DiagnosticEvent(
        event_id="evt_ds9_shared_transaction_lane",
        event_source="polisyos.runtime.control",
        event_type="polisyos.runtime.diagnostic.cas_write.v1",
        event_time=started_at,
        event_subject="run/run-ds9/job/job-ds9/phase/human_decision",
        schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
        schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        trace_id="trace-ds9-shared-lane",
        span_id="span-ds9-shared-lane",
        parent_span_id=None,
        run_id="run-ds9",
        job_id="job-ds9",
        tenant_id="tenant-a",
        cell_id="cell-a",
        producer_component="polisyos.runtime.human_decisions",
        producer_version="2026.08.24+ds9-c01",
        execution_profile="governed",
        phase="human_decision_record",
        state_before="reserved",
        state_after="committed",
        payload_ref=None,
        artifact_refs=("sha256:" + "f" * 64,),
        input_refs=(governed_action_key,),
        blocking_status="non_blocking",
        redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
        duplicate_of=None,
        dedupe_key="ds9-shared-transaction-lane",
        sampling_decision="always_record",
        sampling_rate=1.0,
    )

    with sink.hold_write_fence(
        tenant_id="tenant-a",
        governed_action_key=governed_action_key,
        reservation_id=reserved.reservation.reservation_id,
        reservation_version=reserved.reservation.reservation_version,
        binding_sha256=binding_sha256,
        acquired_at=started_at + timedelta(seconds=1),
        expected_record_valid_until=valid_until,
    ) as fence:
        event_log.append(event)
        assert len(event_log.list_events(event_id=event.event_id)) == 1
        committed = fence.commit(
            record_ref="sha256:" + "f" * 64,
            record_sha256="sha256:" + "f" * 64,
            durable_event_id=event.event_id,
            committed_at=started_at + timedelta(seconds=1),
        )

    assert committed.state == "committed"
    assert len(event_log.list_events(event_id=event.event_id)) == 1


def test_completed_natural_language_lookup_ignores_newer_acquisition_and_rejects_ambiguity(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    common = {
        "run_id": "run-acquisition-closure",
        "pipeline_id": None,
        "requested_execution_profile": "governed",
        "effective_execution_profile": "governed",
        "policy_flags": {},
        "capability_manifest_ref": None,
        "payload_ref": None,
        "submitted_by": "tester",
    }
    store.create_job(job_id="job-nl", kind="natural_language_run", **common)
    store.complete_job(job_id="job-nl", run_id=common["run_id"])
    store.create_job(job_id="job-acquisition", kind="acquisition", **common)
    store.complete_job(job_id="job-acquisition", run_id=common["run_id"])

    resolved = store.get_unique_completed_job_by_run_and_kind(
        run_id=common["run_id"],
        kind="natural_language_run",
    )

    assert resolved is not None
    assert resolved.job_id == "job-nl"
    store.create_job(job_id="job-nl-duplicate", kind="natural_language_run", **common)
    store.complete_job(job_id="job-nl-duplicate", run_id=common["run_id"])
    with pytest.raises(ValueError, match="control_job_completion_ambiguous"):
        store.get_unique_completed_job_by_run_and_kind(
            run_id=common["run_id"],
            kind="natural_language_run",
        )


def test_acquisition_action_head_requires_exact_predecessor(tmp_path) -> None:
    store = _make_store(tmp_path)
    identity = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "job-source",
        "route_id": "sha256:" + "a" * 64,
        "action_generation": 1,
    }
    first_ref = "sha256:" + "b" * 64
    first = store.advance_acquisition_action_head(
        **identity,
        expected_head_generation=0,
        receipt_ref=first_ref,
        receipt_sha256=first_ref,
        durable_event_id="evt-requested",
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        job_id="job-acquisition",
        predecessor_receipt_ref=None,
    )
    assert first.head_generation == 1
    with pytest.raises(ValueError, match="acquisition_action_predecessor_conflict"):
        store.advance_acquisition_action_head(
            **identity,
            expected_head_generation=1,
            receipt_ref="sha256:" + "c" * 64,
            receipt_sha256="sha256:" + "c" * 64,
            durable_event_id="evt-fork",
            coarse_phase="executing",
            receipt_phase="executing",
            recovery_state="none",
            job_id="job-acquisition",
            predecessor_receipt_ref="sha256:" + "d" * 64,
        )


def test_control_plane_store_tracks_worker_leases_and_outbox(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.heartbeat_worker(
        worker_id="worker-a",
        state="idle",
        lease_seconds=30,
        backend="external",
        metadata={"zone": "lab"},
    )

    workers = store.list_worker_leases()
    assert len(workers) == 1
    assert workers[0].worker_id == "worker-a"
    assert workers[0].state == "idle"
    assert workers[0].metadata["zone"] == "lab"

    record = store.create_job(
        job_id="job_fixture_001",
        kind="workflow_run",
        run_id="R_fixture_001",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    leased = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert leased is not None
    assert leased.job_id == record.job_id

    store.heartbeat_worker(
        worker_id="worker-a",
        state="running",
        lease_seconds=30,
        backend="external",
        active_job_id=record.job_id,
        metadata={"job_kind": record.kind},
    )
    store.update_progress_state(
        job_id=record.job_id,
        state="running",
        progress={"phase": "dispatch"},
    )
    store.complete_job(
        job_id=record.job_id,
        progress={"phase": "completed"},
    )

    first = store.enqueue_outbox_event(
        topic="control.decision_validity.event_published",
        event_key="decision_evt_fixture",
        payload={"trigger_type": "law_change"},
    )
    second = store.enqueue_outbox_event(
        topic="control.decision_validity.event_published",
        event_key="decision_evt_fixture",
        payload={"trigger_type": "law_change"},
    )
    assert first.event_id == second.event_id

    topics = {item.topic for item in store.list_outbox_events(state=None, limit=16)}
    assert "control.job.created" in topics
    assert "control.job.running" in topics
    assert "control.job.progress" in topics
    assert "control.job.completed" in topics
    assert "control.decision_validity.event_published" in topics

    store.mark_outbox_published(event_id=first.event_id)
    published = store.get_outbox_event(first.event_id)
    assert published is not None
    assert published.state == "published"

    store.release_worker(worker_id="worker-a")
    all_workers = store.list_worker_leases(active_only=False)
    assert all_workers[0].state == "stopped"


def test_control_worker_renews_job_lease_while_handler_runs(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_renewal",
        kind="workflow_run",
        run_id="R_fixture_renewal",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    observed: dict[str, object] = {}

    def _handler(job) -> None:
        initial = store.get_job(job.job_id)
        assert initial is not None
        observed["initial_expiry"] = initial.lease_expires_at
        deadline = time.time() + 4.0
        renewed = None
        while time.time() < deadline:
            current = store.get_job(job.job_id)
            assert current is not None
            if (
                current.lease_expires_at is not None
                and initial.lease_expires_at is not None
                and current.lease_expires_at > initial.lease_expires_at
            ):
                renewed = current.lease_expires_at
                break
            time.sleep(0.1)
        observed["renewed_expiry"] = renewed
        store.complete_job(job_id=job.job_id)

    worker = ControlWorker(
        store=store,
        handler=_handler,
        lease_seconds=2,
        poll_interval_s=0.05,
        worker_id="ctrl-worker-test",
    )

    assert worker.dispatch_once() is True
    assert observed["renewed_expiry"] is not None
    assert observed["renewed_expiry"] > observed["initial_expiry"]

    workers = store.list_worker_leases(active_only=False)
    assert len(workers) == 1
    assert workers[0].worker_id == "ctrl-worker-test"
    assert workers[0].state == "idle"
    assert workers[0].metadata["last_job_id"] == "job_fixture_renewal"


def test_control_plane_store_dead_letters_terminal_failures(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_failed",
        kind="workflow_run",
        run_id="R_fixture_failed",
        pipeline_id="pipeline_fixture",
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.fail_job(job_id="job_fixture_failed", error_message="permanent failure")

    failed = store.get_job("job_fixture_failed")
    assert failed is not None
    assert failed.state == "failed"

    dead_letters = store.list_dead_letter_jobs()
    assert len(dead_letters) == 1
    assert dead_letters[0].job_id == "job_fixture_failed"
    assert dead_letters[0].run_id == "R_fixture_failed"
    assert dead_letters[0].pipeline_id == "pipeline_fixture"
    assert dead_letters[0].error_message == "permanent failure"
    assert dead_letters[0].acknowledged_at is None

    store.acknowledge_dead_letter_job(
        job_id="job_fixture_failed",
        acknowledged_by="operator@example.test",
    )
    assert store.list_dead_letter_jobs() == []
    acknowledged = store.list_dead_letter_jobs(acknowledged=True)
    assert acknowledged[0].acknowledged_by == "operator@example.test"


def test_control_job_response_promotes_progress_failure_to_stable_envelope(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_preflight_failed",
        kind="natural_language_run",
        run_id="R_fixture_preflight_failed",
        pipeline_id=None,
        requested_execution_profile="research",
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.fail_job(
        job_id="job_fixture_preflight_failed",
        error_message="llm provider preflight failed",
        progress={
            "phase": "provider_preflight",
            "failure": {
                "code": "llm_provider_preflight_failed",
                "layer": "llm_gateway",
                "phase": "provider_preflight",
                "message": "Model is missing from /v1/models",
                "retryable": False,
                "model": "missing-model",
                "provider": "gonka_proxy",
                "next_action": "Check provider credentials and model configuration.",
                "owner": "team-runtime-ops",
                "upstream_missing_input": "llm_provider_model_catalog",
                "downstream_impact": "No serious decision packet can be materialized.",
                "authority_refs": {
                    "provider_preflight_ref": "sha256:" + "a" * 64,
                    "runtime_event_log": "sha256:" + "b" * 64,
                },
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/scientist/orchestration/llm/test_provider_verification.py -q"
                ),
            },
        },
    )

    record = store.get_job("job_fixture_preflight_failed")
    assert record is not None
    response = record.to_response(request_id="req-preflight")

    assert response.failure is not None
    assert response.failure.code == "llm_provider_preflight_failed"
    assert response.failure.layer == "llm_gateway"
    assert response.failure.phase == "provider_preflight"
    assert response.failure.model == "missing-model"
    assert response.failure.provider == "gonka_proxy"
    assert response.failure.next_action == "Check provider credentials and model configuration."
    body = response.model_dump(mode="json")
    diagnostic = body["failure"]["operator_diagnostic"]
    assert body["failure"]["retryable"] is False
    assert diagnostic["authoritative_runtime_state"] == "failed"
    assert diagnostic["projection_source"] == "runtime_control_job_failure"
    assert diagnostic["owner"] == "team-runtime-ops"
    assert diagnostic["phase"] == "provider_preflight"
    assert diagnostic["first_blocking_cause"] == "llm_provider_preflight_failed"
    assert diagnostic["upstream_missing_input"] == "llm_provider_model_catalog"
    assert diagnostic["downstream_impact"] == "No serious decision packet can be materialized."
    assert diagnostic["authority_refs"]["runtime_event_log"].startswith("sha256:")
    assert diagnostic["blocker_overridable"] is False
    assert diagnostic["next_diagnostic_command"].startswith("uv run pytest ")


def test_control_job_response_marks_completed_without_quality_evidence_as_failed(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_quality_missing",
        kind="natural_language_run",
        run_id="R_fixture_quality_missing",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_quality_missing",
        progress={"phase": "completed"},
    )

    record = store.get_job("job_fixture_quality_missing")
    assert record is not None
    response = record.to_response(request_id="req-quality-missing")
    body = response.model_dump(mode="json")

    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "fail"
    assert body["quality_gates"][0]["name"] == "quality_evidence_present"
    assert body["quality_gates"][0]["status"] == "fail"
    assert body["blocking_quality_failures"][0]["gate"] == "quality_evidence_present"


def test_control_plane_store_rejects_clean_completion_for_failed_workflow_progress(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_failed_progress",
        kind="workflow_run",
        run_id="R_fixture_failed_progress",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.complete_job(
        job_id="job_fixture_failed_progress",
        progress={
            "state": "failed",
            "runtime_state": "blocked",
            "authority_path": "workflow_failure",
            "authority_result": "repair_required",
            "legacy_path_disposition": "blocked_workflow_failure_ring2_withheld",
            "failure": {
                "code": "workflow_failed_non_authority",
                "message": "workflow returned fail",
            },
        },
    )

    record = store.get_job("job_fixture_failed_progress")
    assert record is not None
    assert record.state == "failed"
    assert record.error_message == "workflow returned fail"
    assert store.list_dead_letter_jobs()[0].job_id == "job_fixture_failed_progress"


def test_control_job_response_projects_operator_diagnostic_for_serious_quality_failure(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_operator_quality_failure",
        kind="natural_language_run",
        run_id="R_fixture_operator_quality_failure",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_operator_quality_failure",
        progress={
            "phase": "quality_evidence",
            "quality_scorecard": {
                "execution_status": "completed",
                "quality_status": "fail",
                "approval_state": "quality_failed",
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-operator",
                "evidence_refs": {
                    "quality_scorecard": "quality_evidence/quality_scorecard.json",
                    "policy_grounding_matrix": ("quality_evidence/policy_grounding_matrix.json"),
                },
                "quality_gates": [
                    {
                        "name": "policy_grounding_matrix_present",
                        "code": "policy_grounding_matrix_ref_missing",
                        "status": "fail",
                        "layer": "scientist_policy_artifacts",
                        "phase": "policy_grounding",
                        "message": "Policy grounding matrix ref is missing.",
                        "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                        "next_action": "Re-run final claim grounding before approval.",
                        "blocking": True,
                        "owner": "team-policy-semantics",
                        "upstream_missing_input": "policy_grounding_matrix_ref",
                        "downstream_impact": ("Readiness and approval projections remain closed."),
                        "authority_refs": {
                            "quality_scorecard": "quality_evidence/quality_scorecard.json",
                            "runtime_event_log": "sha256:" + "c" * 64,
                        },
                        "next_diagnostic_command": (
                            "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q"
                        ),
                    }
                ],
                "blocking_quality_failures": [],
            },
        },
    )

    record = store.get_job("job_fixture_operator_quality_failure")
    assert record is not None
    body = record.to_response(request_id="req-operator-quality").model_dump(mode="json")

    diagnostic = body["operator_diagnostic"]
    first_failure = body["blocking_quality_failures"][0]
    assert diagnostic["authoritative_runtime_state"] == "completed"
    assert diagnostic["projection_source"] == "runtime_quality_scorecard"
    assert diagnostic["owner"] == "team-policy-semantics"
    assert diagnostic["first_blocking_cause"] == "policy_grounding_matrix_ref_missing"
    assert diagnostic["upstream_missing_input"] == "policy_grounding_matrix_ref"
    assert diagnostic["downstream_impact"] == "Readiness and approval projections remain closed."
    assert diagnostic["authority_refs"]["quality_scorecard"] == (
        "quality_evidence/quality_scorecard.json"
    )
    assert diagnostic["next_diagnostic_command"].endswith(
        "tests/unit/runtime/quality/test_scorecard.py -q"
    )
    assert first_failure["operator_diagnostic"] == diagnostic


def test_control_job_response_fails_completed_scorecard_missing_runtime_quality_refs(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_missing_runtime_quality_refs",
        kind="natural_language_run",
        run_id="R_fixture_missing_runtime_quality_refs",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_missing_runtime_quality_refs",
        progress={
            "phase": "completed",
            "details": {
                "data_snapshot_ref": "sha256:" + "1" * 64,
                "input_bindings_ref": "sha256:" + "2" * 64,
                "registry_bundle_ref": "sha256:" + "3" * 64,
                "quality_report_ref": "sha256:" + "4" * 64,
            },
            "quality_scorecard": {
                "execution_status": "completed",
                "quality_status": "pass",
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-missing-refs",
                "evidence_refs": {
                    "quality_scorecard": "quality_evidence/quality_scorecard.json",
                    "normative_evidence": "quality_evidence/normative_evidence.json",
                    "fabric_retrieval_trace": "quality_evidence/fabric_retrieval_trace.json",
                    "foundry_method_report": "quality_evidence/foundry_method_report.json",
                    "policy_grounding_matrix": ("quality_evidence/policy_grounding_matrix.json"),
                    "conflict_check": "quality_evidence/conflict_check.json",
                },
                "quality_gates": [
                    {
                        "name": "normative_evidence_present",
                        "code": "normative_evidence_present",
                        "status": "pass",
                        "layer": "lex",
                        "phase": "quality_evidence",
                        "message": "Normative applicability evidence is present.",
                        "blocking": True,
                    },
                    {
                        "name": "fabric_retrieval_trace_present",
                        "code": "fabric_retrieval_trace_present",
                        "status": "pass",
                        "layer": "fabric_retrieval",
                        "phase": "quality_evidence",
                        "message": "Fabric source-selection evidence is present.",
                        "blocking": True,
                    },
                    {
                        "name": "foundry_method_evidence_present",
                        "code": "foundry_method_evidence_present",
                        "status": "pass",
                        "layer": "foundry_methods",
                        "phase": "quality_evidence",
                        "message": "Foundry method validity evidence is present.",
                        "blocking": True,
                    },
                    {
                        "name": "policy_grounding_matrix_present",
                        "code": "policy_grounding_matrix_present",
                        "status": "pass",
                        "layer": "scientist_policy_artifacts",
                        "phase": "quality_evidence",
                        "message": "Policy grounding matrix is present.",
                        "blocking": True,
                    },
                    {
                        "name": "conflict_check_present",
                        "code": "conflict_check_present",
                        "status": "pass",
                        "layer": "normative_conflict",
                        "phase": "quality_evidence",
                        "message": "Policy conflict check is present.",
                        "blocking": True,
                    },
                ],
                "blocking_quality_failures": [],
            },
        },
    )

    record = store.get_job("job_fixture_missing_runtime_quality_refs")
    assert record is not None
    response = record.to_response(request_id="req-runtime-quality-refs")
    body = response.model_dump(mode="json")
    gates = {gate["name"]: gate for gate in body["quality_gates"]}
    failures = {failure["gate"]: failure for failure in body["blocking_quality_failures"]}
    expected = {
        "normative_evidence_present": "normative_applicability_report_ref_missing",
        "fabric_retrieval_trace_present": "fabric_retrieval_trace_ref_missing",
        "foundry_method_evidence_present": "foundry_method_report_ref_missing",
        "policy_grounding_matrix_present": "policy_grounding_matrix_ref_missing",
        "conflict_check_present": "conflict_check_ref_missing",
        "causal_statistical_validity_present": ("causal_statistical_validity_report_ref_missing"),
        "replay_manifest_present": "replay_manifest_ref_missing",
        "drift_explanation_present": "drift_explanation_ref_missing",
        "resilience_matrix_present": "resilience_report_ref_missing",
        "human_review_calibration_present": "human_review_calibration_report_ref_missing",
        "privacy_compliance_report_present": "privacy_compliance_report_ref_missing",
        "decision_artifact_quality_present": "decision_artifact_quality_report_ref_missing",
    }

    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "fail"
    for gate_name, expected_code in expected.items():
        assert gates[gate_name]["status"] == "fail"
        assert gates[gate_name]["code"] == expected_code
        assert gates[gate_name]["next_action"]
        assert failures[gate_name]["code"] == expected_code
        assert failures[gate_name]["next_action"] == gates[gate_name]["next_action"]


def test_control_job_response_promotes_quality_scorecard_to_top_level(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_quality_scorecard",
        kind="natural_language_run",
        run_id="R_fixture_quality_scorecard",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_quality_scorecard",
        progress={
            "phase": "completed",
            "details": {
                "normative_applicability_report_ref": "sha256:" + "1" * 64,
                "fabric_retrieval_trace_ref": "sha256:" + "2" * 64,
                "foundry_method_report_ref": "sha256:" + "3" * 64,
                "policy_grounding_matrix_ref": "sha256:" + "4" * 64,
                "conflict_check_ref": "sha256:" + "5" * 64,
                "causal_statistical_validity_report_ref": "sha256:" + "6" * 64,
                "replay_manifest_ref": "sha256:" + "7" * 64,
                "drift_explanation_ref": "sha256:" + "8" * 64,
                "resilience_report_ref": "sha256:" + "9" * 64,
                "human_review_calibration_report_ref": "sha256:" + "a" * 64,
                "privacy_compliance_report_ref": "sha256:" + "b" * 64,
                "decision_artifact_quality_report_ref": "sha256:" + "c" * 64,
            },
            "quality_scorecard": {
                "execution_status": "completed",
                "quality_status": "warn",
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-1",
                "quality_gates": [
                    {
                        "name": "conflict_check_present",
                        "code": "indirect_policy_conflict",
                        "status": "warn",
                        "layer": "normative_conflict",
                        "phase": "corpus_compatibility",
                        "message": "Indirect conflict needs review.",
                        "evidence_ref": "quality_evidence/conflict_check.json",
                        "next_action": "Review medium severity compatibility conflict.",
                        "blocking": False,
                    }
                ],
                "blocking_quality_failures": [],
            },
        },
    )

    record = store.get_job("job_fixture_quality_scorecard")
    assert record is not None
    response = record.to_response(request_id="req-quality-scorecard")
    body = response.model_dump(mode="json")

    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "warn"
    assert body["quality_gates"][0]["name"] == "conflict_check_present"
    assert body["quality_gates"][0]["code"] == "indirect_policy_conflict"
    assert body["quality_gates"][0]["layer"] == "normative_conflict"
    assert body["quality_gates"][0]["phase"] == "corpus_compatibility"
    assert body["quality_gates"][0]["evidence_ref"] == "quality_evidence/conflict_check.json"
    assert body["quality_scorecard_ref"] == "quality_evidence/quality_scorecard.json"
    assert body["quality_evidence_bundle_path"] == ".polisyos/canary_evidence/run-1"
    assert body["blocking_quality_failures"] == []


def test_control_plane_store_persists_scorecard_refs_in_progress(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_scorecard_refs",
        kind="natural_language_run",
        run_id="R_fixture_scorecard_refs",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.complete_job(
        job_id="job_fixture_scorecard_refs",
        progress={
            "phase": "completed",
            "quality_status": "fail",
            "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
            "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-scorecard",
            "evidence_refs": {
                "quality_scorecard": "quality_evidence/quality_scorecard.json",
                "fabric_retrieval_trace_ref": "sha256:" + "6" * 64,
            },
            "quality_gates": [
                {
                    "name": "fabric_retrieval_trace_present",
                    "code": "fabric_retrieval_trace_failed",
                    "status": "fail",
                    "layer": "fabric_retrieval",
                    "phase": "quality_evidence",
                    "message": "Fabric source-selection evidence failed.",
                    "evidence_ref": "quality_evidence/fabric_retrieval_trace.json",
                    "next_action": "Inspect source-selection diagnostics.",
                    "blocking": True,
                }
            ],
            "blocking_quality_failures": [
                {
                    "gate": "fabric_retrieval_trace_present",
                    "code": "fabric_retrieval_trace_failed",
                    "layer": "fabric_retrieval",
                    "phase": "quality_evidence",
                    "message": "Fabric source-selection evidence failed.",
                    "evidence_ref": "quality_evidence/fabric_retrieval_trace.json",
                    "next_action": "Inspect source-selection diagnostics.",
                }
            ],
        },
    )

    record = store.get_job("job_fixture_scorecard_refs")
    assert record is not None
    progress_scorecard = record.progress["quality_scorecard"]
    response = record.to_response(request_id="req-scorecard-refs")
    body = response.model_dump(mode="json")

    assert progress_scorecard["quality_scorecard_ref"] == (
        "quality_evidence/quality_scorecard.json"
    )
    assert progress_scorecard["quality_evidence_bundle_path"] == (
        ".polisyos/canary_evidence/run-scorecard"
    )
    assert progress_scorecard["evidence_refs"]["fabric_retrieval_trace_ref"].startswith("sha256:")
    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "fail"
    assert body["quality_scorecard_ref"] == "quality_evidence/quality_scorecard.json"
    assert body["quality_evidence_bundle_path"] == ".polisyos/canary_evidence/run-scorecard"


def test_control_job_response_projects_policy_design_case_semantics_without_authority(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_policy_design_projection",
        kind="natural_language_run",
        run_id="run-24",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_policy_design_projection",
        progress={
            "policy_design_case": policy_design_case(),
            "final_decision_artifact": {
                "artifact_kind": "publishable_decision_artifact",
                "publishability": "publishable",
                "decision_context": {"public_export_status": "publishable"},
                "authority_role": "final_decision_artifact",
            },
            "final_decision_artifact_ref": sha("9"),
        },
    )

    record = store.get_job("job_fixture_policy_design_projection")
    assert record is not None
    body = record.to_response(request_id="req-policy-design-projection").model_dump(mode="json")

    projection = body["policy_design_case_projection"]
    assert projection["primary_state"] == "publishable"
    assert projection["authority_role"] == "projection_only"
    assert projection["projection_policy"] == "reads_policy_design_case_only"
    assert "publishable" in projection["states"]
    assert body["approval_projection"]["authority_level"] == "projection_only"


def test_control_plane_sqlite_uses_wal_journaling(tmp_path) -> None:
    db_path = tmp_path / "control-plane.sqlite3"
    _ = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)

    with sqlite3.connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert synchronous in {1, 2}


def test_scenario_head_create_cas_has_one_winner_across_store_instances(tmp_path) -> None:
    db_path = tmp_path / "control-plane.sqlite3"
    first_store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    second_store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    barrier = threading.Barrier(2)

    def _claim(store: ControlPlaneStore, artifact_ref: str, manifest_hash: str) -> bool:
        barrier.wait()
        return store.compare_and_set_scenario_head(
            scenario_id="scenario-shared",
            baseline_run_id="run-authorized",
            expected_revision=0,
            new_revision=1,
            artifact_ref=artifact_ref,
            manifest_hash=manifest_hash,
        )

    contenders = (
        (first_store, "sha256:first", "sha256:manifest-first"),
        (second_store, "sha256:second", "sha256:manifest-second"),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_claim, *contender) for contender in contenders]
        outcomes = [future.result() for future in futures]

    assert sorted(outcomes) == [False, True]
    winner = contenders[outcomes.index(True)]
    assert first_store.get_scenario_head("scenario-shared") == second_store.get_scenario_head(
        "scenario-shared"
    )
    head = first_store.get_scenario_head("scenario-shared")
    assert head is not None
    assert head.baseline_run_id == "run-authorized"
    assert head.revision == 1
    assert head.artifact_ref == winner[1]
    assert head.manifest_hash == winner[2]


def test_scenario_head_update_cas_denies_baseline_run_rebinding(tmp_path) -> None:
    store = _make_store(tmp_path)
    assert store.compare_and_set_scenario_head(
        scenario_id="scenario-bound",
        baseline_run_id="run-original",
        expected_revision=0,
        new_revision=1,
        artifact_ref="sha256:revision-one",
        manifest_hash="sha256:manifest-one",
    )

    assert not store.compare_and_set_scenario_head(
        scenario_id="scenario-bound",
        baseline_run_id="run-other",
        expected_revision=1,
        new_revision=2,
        artifact_ref="sha256:revision-two",
        manifest_hash="sha256:manifest-two",
    )

    head = store.get_scenario_head("scenario-bound")
    assert head is not None
    assert head.baseline_run_id == "run-original"
    assert head.revision == 1
    assert head.artifact_ref == "sha256:revision-one"
    assert head.manifest_hash == "sha256:manifest-one"
    assert store.list_scenario_heads(baseline_run_id="run-original") == [head]
    assert store.list_scenario_heads(baseline_run_id="run-other") == []


class _FlakyHeartbeatStore:
    def __init__(self) -> None:
        self.fail = threading.Event()

    def heartbeat_worker(self, **_kwargs) -> None:
        if self.fail.is_set():
            raise RuntimeDependencyUnavailableError(
                "control_plane_store",
                detail="control_plane_store executor is unavailable",
            )

    def renew_job_lease(self, **_kwargs) -> None:
        if self.fail.is_set():
            raise RuntimeDependencyUnavailableError(
                "control_plane_store",
                detail="control_plane_store executor is unavailable",
            )


class _FlakyReleaseStore:
    def release_worker(self, **_kwargs) -> None:
        raise RuntimeDependencyUnavailableError(
            "control_plane_store",
            detail="control_plane_store circuit breaker is open",
        )


def test_control_worker_stop_suppresses_store_unavailable_release() -> None:
    worker = ControlWorker(
        store=cast("ControlPlaneStore", _FlakyReleaseStore()),
        handler=lambda _job: None,
        lease_seconds=1,
        worker_id="ctrl-worker-release-unavailable",
    )

    worker.stop()


def test_control_worker_shutdown_suppresses_heartbeat_store_unavailable_logs(
    monkeypatch,
) -> None:
    store = _FlakyHeartbeatStore()
    warnings: list[tuple[object, ...]] = []
    exceptions: list[tuple[object, ...]] = []
    worker = ControlWorker(
        store=cast("ControlPlaneStore", store),
        handler=lambda _job: None,
        lease_seconds=1,
        worker_id="ctrl-worker-shutdown",
    )
    job = ControlJobRecord(
        job_id="job_shutdown",
        kind="workflow_run",
        state="running",
        run_id="R_shutdown",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=None,
        lease_owner=worker.worker_id,
        lease_expires_at=None,
        attempt=1,
        error_message=None,
        progress={},
    )

    def _handler(_job: ControlJobRecord) -> None:
        store.fail.set()
        worker._stop.set()
        time.sleep(worker._heartbeat_interval_s + 0.05)

    monkeypatch.setattr(worker, "_handler", _handler)
    monkeypatch.setattr(
        control_worker_module.logger,
        "warning",
        lambda *args, **kwargs: warnings.append(args),
    )
    monkeypatch.setattr(
        control_worker_module.logger,
        "exception",
        lambda *args, **kwargs: exceptions.append(args),
    )

    worker._run_with_lease_heartbeat(job)

    assert warnings == []
    assert exceptions == []


def test_normative_head_compare_and_append_has_one_sqlite_winner(tmp_path) -> None:
    """The event owner serializes two independent connections on the actual predecessor."""
    path = tmp_path / "normative.sqlite3"
    stores = tuple(ControlPlaneStore(backend="sqlite", sqlite_path=path) for _ in range(2))
    source = "sha256:" + "a" * 64
    stores[0].create_job(
        job_id="job",
        kind="natural_language_run",
        run_id="run",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by=None,
    )
    stores[0].complete_job(
        job_id="job",
        run_id="run",
        capability_manifest_ref=None,
        progress={"compiled_recursive_generation_cycle_ref": source},
    )
    barrier = threading.Barrier(2)

    def append(index):
        barrier.wait(timeout=10)
        return stores[index].append_normative_evidence_head(
            job_id="job",
            run_id="run",
            compiled_run_ref=source,
            expected_prior_head_ref=None,
            head_ref="sha256:" + str(index + 1) * 64,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(append, range(2)))
    assert sorted(results) == [False, True]
    winner = "sha256:" + str(results.index(True) + 1) * 64
    assert stores[0].get_normative_evidence_head("job")["head_ref"] == winner
    assert stores[1].append_normative_evidence_head(
        job_id="job",
        run_id="run",
        compiled_run_ref=source,
        expected_prior_head_ref=winner,
        head_ref="sha256:" + "3" * 64,
    )
    assert stores[0].get_normative_evidence_head("job")["previous_head_ref"] == winner
    for invalid in ({"run_id": "foreign"}, {"compiled_run_ref": "sha256:" + "f" * 64}):
        with pytest.raises(ValueError, match="normative_evidence_job"):
            stores[0].append_normative_evidence_head(
                **{
                    "job_id": "job",
                    "run_id": "run",
                    "compiled_run_ref": source,
                    "expected_prior_head_ref": "sha256:" + "3" * 64,
                    "head_ref": "sha256:" + "4" * 64,
                    **invalid,
                }
            )
    assert stores[0].get_job("job").progress["compiled_recursive_generation_cycle_ref"] == source


def test_acquisition_action_heads_enumerate_latest_per_generation_in_exact_scope(tmp_path):
    store = _make_store(tmp_path)
    identity = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "source-job",
        "route_id": "sha256:" + "a" * 64,
    }

    def append(scope, generation, expected=0, predecessor=None):
        ref = "sha256:" + str(generation + expected) * 64
        return store.advance_acquisition_action_head(
            **scope,
            action_generation=generation,
            expected_head_generation=expected,
            receipt_ref=ref,
            receipt_sha256=ref,
            durable_event_id=f"event-{expected}",
            coarse_phase="executing" if expected else "requested",
            receipt_phase="executing" if expected else "requested",
            recovery_state="none",
            job_id=f"job-{generation}",
            predecessor_receipt_ref=predecessor,
        )

    assert store.list_acquisition_action_heads(**identity) == ()
    first = append(identity, 1)
    latest = append(identity, 1, expected=1, predecessor=first.receipt_ref)
    second = append(identity, 2)
    for field in identity:
        append({**identity, field: "other-" + identity[field]}, 1)
    assert store.list_acquisition_action_heads(**identity) == (latest, second)


def _create_execution_admission_job(
    store: ControlPlaneStore,
    *,
    execution_scope: dict[str, object] | None,
    capability_manifest_ref: str | None = "sha256:manifest-admission",
) -> ControlJobRecord:
    return store.create_job(
        job_id="job_execution_admission",
        kind="workflow_run",
        run_id="run_execution_admission",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref=capability_manifest_ref,
        payload_ref="sha256:payload-b",
        submitted_by="denis",
        creation_event_payload=_job_creation_event(execution_scope=execution_scope),
    )


def _fence_leased_execution(
    store: ControlPlaneStore,
    *,
    job: ControlJobRecord,
    worker_id: str = "worker-execution-admission",
) -> AbstractContextManager[None]:
    leased = store.lease_next_job(worker_id=worker_id, lease_seconds=30)
    assert leased is not None
    return store.job_execution_fence(
        job_id=job.job_id,
        worker_id=worker_id,
        attempt=leased.attempt,
    )


@pytest.mark.parametrize("guarded", [False, True])
def test_completed_proof_publication_preserves_progress_and_journals_exact_attempt(
    tmp_path: Path,
    guarded: bool,
) -> None:
    raw = _make_store(tmp_path)
    admin = _make_store(tmp_path)  # Independent unbound sibling/admin writer on the same DB.
    store = guard_runtime_control_store(raw) if guarded else raw
    job = _create_execution_admission_job(raw, execution_scope=_job_execution_scope())
    with _fence_leased_execution(store, job=job):
        store.complete_job(
            job_id=job.job_id,
            progress={
                "phase": "completed",
                "unrelated": {"retained": True},
                "artifacts_index": {"search_exit_contract_ref": "search-ref"},
                "quality_scorecard": {"evidence_refs": {"search_exit_contract_ref": "search-ref"}},
            },
        )
        completed = store.current_execution_completed_job_record()
        proof_ref = "sha256:" + "7" * 64
        proof = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "worker_id": "worker-execution-admission",
            "observed_job_state": "completed",
            "control_store_state_transitions": store.list_job_state_transitions(job.job_id),
        }
        with pytest.raises(ControlJobLeaseLostError):
            raw.upsert_progress(job_id=job.job_id, progress={"forbidden_bound_write": True})
        assert raw.get_job(job.job_id) == completed
        admin.upsert_progress(
            job_id=job.job_id,
            progress={**completed.progress, "sibling_update": {"retained": True}},
        )
        store.publish_completed_job_proof(
            job_id=job.job_id,
            expected_progress=completed.progress,
            proof_payload=proof,
            proof_ref=proof_ref,
        )
        updated = store.get_job(job.job_id)
        assert updated is not None
        assert updated.progress["unrelated"] == {"retained": True}
        assert updated.progress["sibling_update"] == {"retained": True}
        assert updated.progress["artifacts_index"]["search_exit_contract_ref"] == "search-ref"
        assert updated.progress["production_loop_run_proof"] == proof
        assert updated.progress["production_loop_run_proof_ref"] == proof_ref
        assert store.list_job_state_transitions(job.job_id) == ["pending", "running", "completed"]
        events = [
            e
            for e in store.list_outbox_events(state=None, limit=100)
            if e.topic == "control.job.proof_finalized"
        ]
        assert len(events) == 1
        assert events[0].payload["proof_ref"] == proof_ref
        assert events[0].payload["attempt"] == completed.attempt
        with pytest.raises(ControlJobLeaseLostError, match="progress changed"):
            store.publish_completed_job_proof(
                job_id=job.job_id,
                expected_progress=completed.progress,
                proof_payload=proof,
                proof_ref=proof_ref,
            )
    with pytest.raises(ControlJobLeaseLostError, match="identity is not bound"):
        store.publish_completed_job_proof(
            job_id=job.job_id,
            expected_progress=updated.progress,
            proof_payload=proof,
            proof_ref=proof_ref,
        )


@pytest.mark.parametrize("guarded", [False, True])
@pytest.mark.parametrize(
    "mutation",
    [
        "completion_owner",
        "attempt",
        "restarted",
        "lease_owner",
        "lease_expiry",
        "proof_basis",
        "proof_basis_primitive_type",
        "proof_basis_key_presence",
        "history",
    ],
)
def test_completed_proof_publication_refuses_foreign_or_replaced_attempt(
    tmp_path: Path,
    guarded: bool,
    mutation: str,
) -> None:
    raw = _make_store(tmp_path)
    admin = _make_store(tmp_path)  # Independent unbound sibling/admin writer on the same DB.
    store = guard_runtime_control_store(raw) if guarded else raw
    job = _create_execution_admission_job(raw, execution_scope=_job_execution_scope())
    with _fence_leased_execution(store, job=job):
        store.complete_job(
            job_id=job.job_id,
            progress={"phase": "completed", "search_exit_contract": {"verified": True}},
        )
        completed = store.current_execution_completed_job_record()
        if mutation == "completion_owner":
            admin.append_event(
                job_id=job.job_id,
                event_type="job_completed",
                payload={
                    "state": "completed",
                    "lease_owner": "foreign-worker",
                    "attempt": completed.attempt,
                },
            )
        elif mutation == "attempt":
            admin._execute(
                "UPDATE control_jobs SET attempt = attempt + 1 WHERE job_id = ?", (job.job_id,)
            )
        elif mutation == "restarted":
            admin.mark_running(job_id=job.job_id, worker_id="replacement-worker")
        elif mutation == "lease_owner":
            admin._execute(
                "UPDATE control_jobs SET lease_owner = ? WHERE job_id = ?",
                ("foreign-worker", job.job_id),
            )
        elif mutation == "lease_expiry":
            admin._execute(
                "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                ((datetime.now(UTC) + timedelta(minutes=1)).isoformat(), job.job_id),
            )
        elif mutation == "proof_basis":
            admin.upsert_progress(
                job_id=job.job_id,
                progress={**completed.progress, "search_exit_contract_ref": "replaced-source"},
            )
        elif mutation == "proof_basis_primitive_type":
            admin.upsert_progress(
                job_id=job.job_id,
                progress={**completed.progress, "search_exit_contract": {"verified": 1}},
            )
        elif mutation == "proof_basis_key_presence":
            admin.upsert_progress(
                job_id=job.job_id,
                progress={**completed.progress, "authority_path": None},
            )
        else:
            admin.append_event(
                job_id=job.job_id, event_type="job_progress", payload={"state": "pending"}
            )
        before = raw.get_job(job.job_id)
        assert before is not None
        before_outbox = raw.list_outbox_events(state=None, limit=100)
        with pytest.raises(ControlJobLeaseLostError):
            store.publish_completed_job_proof(
                job_id=job.job_id,
                expected_progress=completed.progress,
                proof_payload={
                    "job_id": job.job_id,
                    "run_id": job.run_id,
                    "worker_id": "worker-execution-admission",
                    "control_store_state_transitions": ["pending", "running", "completed"],
                },
                proof_ref="sha256:" + "7" * 64,
            )
        after = raw.get_job(job.job_id)
        assert after is not None and after.progress == before.progress
        assert raw.list_outbox_events(state=None, limit=100) == before_outbox


def test_control_job_execution_admission_uses_event_and_allows_fenced_pointer_refresh(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    job = _create_execution_admission_job(
        store,
        execution_scope=_job_execution_scope(),
    )
    with pytest.raises(ControlJobLeaseLostError, match="execution fence"):
        store.update_manifest_ref(
            job_id=job.job_id,
            capability_manifest_ref="sha256:manifest-refreshed",
        )

    with _fence_leased_execution(store, job=job):
        admission = store.current_execution_job_admission()
        assert admission.job.job_id == job.job_id
        assert admission.scope.status == "established"
        assert admission.scope.tenant_id == "tenant-b"
        assert admission.scope.cell_id == "cell-b"
        assert admission.scope.actor_subject == "denis"
        assert admission.scope.actor_authenticated is True
        assert admission.scope.actor_roles == ("analyst", "operator")
        assert admission.admission_capability_manifest_ref == "sha256:manifest-admission"
        assert admission.manifest_pointer_state == "admission_current"

        store.update_manifest_ref(
            job_id=job.job_id,
            capability_manifest_ref="sha256:manifest-refreshed",
        )
        refreshed = store.current_execution_job_admission()
        assert refreshed.scope == admission.scope
        assert refreshed.admission_capability_manifest_ref == "sha256:manifest-admission"
        assert refreshed.manifest_pointer_state == "refreshed_current"

    event = store.get_job_created_event_payload(job.job_id)
    assert event["capability_manifest_ref"] == "sha256:manifest-admission"


def test_control_job_execution_admission_keeps_scope_less_legacy_unknown(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    job = store.create_job(
        job_id="job_execution_admission",
        kind="workflow_run",
        run_id="run_execution_admission",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref=None,
        payload_ref="sha256:payload-b",
        submitted_by="denis",
    )

    with _fence_leased_execution(store, job=job):
        admission = store.current_execution_job_admission()

    assert admission.scope.status == "not_established"
    assert admission.scope.tenant_id is None
    assert admission.scope.cell_id is None
    assert admission.scope.actor_subject is None
    assert admission.scope.actor_authenticated is False
    assert admission.scope.actor_roles == ()
    assert admission.manifest_pointer_state == "missing_current"


def test_control_job_execution_admission_accepts_typed_unknown_scope(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    unknown_scope: dict[str, object] = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "not_established",
        "tenant_id": None,
        "cell_id": None,
        "actor_subject": None,
        "actor_authenticated": False,
        "actor_roles": [],
    }
    job = _create_execution_admission_job(
        store,
        execution_scope=unknown_scope,
        capability_manifest_ref=None,
    )

    with _fence_leased_execution(store, job=job):
        admission = store.current_execution_job_admission()

    assert admission.scope.status == "not_established"
    assert admission.scope.tenant_id is None
    assert admission.scope.actor_authenticated is False


def test_control_job_execution_admission_rejects_malformed_scope_and_row_mismatch(
    tmp_path: Path,
) -> None:
    malformed_store = _make_store(tmp_path / "malformed")
    malformed_scope = _job_execution_scope()
    malformed_scope["actor_authenticated"] = False
    malformed_job = _create_execution_admission_job(
        malformed_store,
        execution_scope=malformed_scope,
    )
    with (
        _fence_leased_execution(malformed_store, job=malformed_job),
        pytest.raises(
            ControlJobExecutionAdmissionError,
            match="control_job_execution_scope_incomplete",
        ),
    ):
        malformed_store.current_execution_job_admission()

    mismatch_store = _make_store(tmp_path / "mismatch")
    mismatched_event = _job_creation_event(execution_scope=_job_execution_scope())
    mismatched_event["job_id"] = "another-job"
    mismatch_job = mismatch_store.create_job(
        job_id="job_execution_admission",
        kind="workflow_run",
        run_id="run_execution_admission",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref="sha256:manifest-admission",
        payload_ref="sha256:payload-b",
        submitted_by="denis",
        creation_event_payload=mismatched_event,
    )
    with (
        _fence_leased_execution(mismatch_store, job=mismatch_job),
        pytest.raises(
            ControlJobExecutionAdmissionError,
            match="control_job_created_stable_field_mismatch",
        ),
    ):
        mismatch_store.current_execution_job_admission()


def test_control_job_execution_admission_requires_exactly_one_creation_event(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    job = _create_execution_admission_job(
        store,
        execution_scope=_job_execution_scope(),
    )
    store.append_event(
        job_id=job.job_id,
        event_type="job_created",
        payload=_job_creation_event(execution_scope=_job_execution_scope()),
    )
    with (
        _fence_leased_execution(store, job=job),
        pytest.raises(
            ControlJobExecutionAdmissionError,
            match="control_job_created_event_unavailable",
        ),
    ):
        store.current_execution_job_admission()


def test_control_job_execution_admission_rejects_bool_int_outbox_scope_drift(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    job = _create_execution_admission_job(
        store,
        execution_scope=_job_execution_scope(),
    )
    outbox = store.get_job_created_outbox_event(job.job_id)
    assert outbox is not None
    outbox_payload = outbox.payload
    execution_scope = outbox_payload["execution_scope"]
    assert isinstance(execution_scope, dict)
    execution_scope["actor_authenticated"] = 1
    store._execute(
        "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
        (json.dumps(outbox_payload, sort_keys=True), outbox.event_id),
    )

    with (
        _fence_leased_execution(store, job=job),
        pytest.raises(
            ControlJobExecutionAdmissionError,
            match="control_job_created_event_outbox_mismatch",
        ),
    ):
        store.current_execution_job_admission()


def test_control_job_execution_admission_rejects_nested_bool_int_outbox_drift(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    job = _create_execution_admission_job(
        store,
        execution_scope=_job_execution_scope(),
    )
    outbox = store.get_job_created_outbox_event(job.job_id)
    assert outbox is not None
    outbox_payload = outbox.payload
    policy_flags = outbox_payload["policy_flags"]
    assert isinstance(policy_flags, dict)
    policy_flags["candidate"] = 1
    store._execute(
        "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
        (json.dumps(outbox_payload, sort_keys=True), outbox.event_id),
    )

    with (
        _fence_leased_execution(store, job=job),
        pytest.raises(
            ControlJobExecutionAdmissionError,
            match="control_job_created_event_outbox_mismatch",
        ),
    ):
        store.current_execution_job_admission()


def test_control_job_execution_admission_rejects_nested_bool_int_row_drift(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    job = _create_execution_admission_job(
        store,
        execution_scope=_job_execution_scope(),
    )
    event_payload = store.get_job_created_event_payload(job.job_id)
    policy_flags = event_payload["policy_flags"]
    assert isinstance(policy_flags, dict)
    policy_flags["candidate"] = 1
    serialized_event = json.dumps(event_payload, sort_keys=True)
    store._execute(
        "UPDATE control_job_events SET payload_json = ? WHERE job_id = ? AND event_type = ?",
        (serialized_event, job.job_id, "job_created"),
    )
    outbox = store.get_job_created_outbox_event(job.job_id)
    assert outbox is not None
    outbox_payload = outbox.payload
    outbox_policy_flags = outbox_payload["policy_flags"]
    assert isinstance(outbox_policy_flags, dict)
    outbox_policy_flags["candidate"] = 1
    store._execute(
        "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
        (json.dumps(outbox_payload, sort_keys=True), outbox.event_id),
    )

    with (
        _fence_leased_execution(store, job=job),
        pytest.raises(
            ControlJobExecutionAdmissionError,
            match="control_job_created_stable_field_mismatch",
        ),
    ):
        store.current_execution_job_admission()


def test_control_job_execution_admission_binds_actor_subject_to_submitter(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    scope = _job_execution_scope()
    scope["actor_subject"] = "different-actor"
    job = _create_execution_admission_job(store, execution_scope=scope)

    with (
        _fence_leased_execution(store, job=job),
        pytest.raises(
            ControlJobExecutionAdmissionError,
            match="control_job_execution_actor_subject_mismatch",
        ),
    ):
        store.current_execution_job_admission()


def test_control_job_execution_admission_ignores_json_object_key_order(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    job = _create_execution_admission_job(
        store,
        execution_scope=_job_execution_scope(),
    )
    outbox = store.get_job_created_outbox_event(job.job_id)
    assert outbox is not None

    def reverse_object_key_order(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: reverse_object_key_order(child)
                for key, child in reversed(tuple(value.items()))
            }
        if isinstance(value, list):
            return [reverse_object_key_order(child) for child in value]
        return value

    reordered = reverse_object_key_order(outbox.payload)
    assert isinstance(reordered, dict)
    store._execute(
        "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
        (json.dumps(reordered), outbox.event_id),
    )

    with _fence_leased_execution(store, job=job):
        admission = store.current_execution_job_admission()

    assert admission.scope.status == "established"
