"""Opt-in races on a dedicated disposable PostgreSQL control store."""

from __future__ import annotations

import importlib
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from tests.unit.runtime.http.test_control_plane_store import (
    _cancellation_proof,
    _job_creation_event,
    _job_execution_scope,
    _sql_cancel,
)

_DSN = os.getenv("POLISYOS_TEST_C57_DISPOSABLE_PG_DSN")
pytestmark = pytest.mark.skipif(not _DSN, reason="disposable PostgreSQL DSN not supplied")


def _await_postgres_lock_wait(pid: int) -> None:
    """Observe the contender's actual PostgreSQL lock wait, not elapsed time."""
    psycopg = importlib.import_module("psycopg")
    deadline = time.monotonic() + 10
    with psycopg.connect(_DSN, autocommit=True) as conn, conn.cursor() as cursor:
        while time.monotonic() < deadline:
            cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", (pid,))
            row = cursor.fetchone()
            if row is not None and row[0] == "Lock":
                return
            time.sleep(0.01)
    raise AssertionError("PostgreSQL contender did not expose the expected lock wait")


def _capture_contender_pid(store, started, pid_list) -> None:
    """Observe the actual transaction-bound backend before the competing read."""
    original_fetchone = store._fetchone

    def fetchone(sql, params):
        if not started.is_set():
            cursor = getattr(store._human_decision_transaction, "postgres_cursor", None)
            if cursor is not None:
                cursor.execute("SELECT pg_backend_pid()")
                pid_list.append(int(cursor.fetchone()[0]))
                started.set()
        return original_fetchone(sql, params)

    store._fetchone = fetchone


def _hold_cancel_before_commit(store, entered, release) -> None:
    """Pause the real cancellation transaction without wrapping it in another."""
    original_emit = store._emit_job_outbox_event

    def emit(**kwargs):
        original_emit(**kwargs)
        if kwargs["event_type"] == "job_cancelled":
            entered.set()
            assert release.wait(10)

    store._emit_job_outbox_event = emit


def _job(store: ControlPlaneStore):
    suffix = uuid.uuid4().hex
    job_id = f"job_c57_{suffix}"
    run_id = f"run_c57_{suffix}"
    creation = _job_creation_event(execution_scope=_job_execution_scope())
    creation["job_id"] = job_id
    creation["run_id"] = run_id
    return store.create_job(
        job_id=job_id,
        kind="workflow_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref="sha256:manifest-admission",
        payload_ref="sha256:payload-b",
        submitted_by="denis",
        creation_event_payload=creation,
    )


def _stores(tmp_path: Path) -> tuple[ControlPlaneStore, ControlPlaneStore]:
    assert _DSN
    # The explicit variable must identify a dedicated disposable test database.
    return (
        ControlPlaneStore(backend="postgres", sqlite_path=tmp_path / "unused", postgres_dsn=_DSN),
        ControlPlaneStore(backend="postgres", sqlite_path=tmp_path / "unused", postgres_dsn=_DSN),
    )


@pytest.mark.parametrize("first", ["progress", "cancel"])
def test_pg_progress_cancel_serializes_without_losing_cancellation_or_prior_progress(
    tmp_path: Path, first: str
) -> None:
    owner, contender = _stores(tmp_path)
    job = _job(owner)
    leased = owner.lease_next_job(worker_id="race-owner", lease_seconds=60)
    assert leased is not None and leased.job_id == job.job_id
    proof = _cancellation_proof(
        job.job_id,
        operation_id="pg-cancel",
        expected_lease_owner="race-owner",
        expected_attempt=leased.attempt,
    )
    first_holds_row = threading.Event()
    second_started = threading.Event()
    second_pid: list[int] = []
    release = threading.Event()

    def cancel(store: ControlPlaneStore):
        return _sql_cancel(
            store,
            job_id=job.job_id,
            authorization_proof=proof,
            operation_id="pg-cancel",
            expected_lease_owner="race-owner",
            expected_attempt=leased.attempt,
        )

    if first == "cancel":
        _hold_cancel_before_commit(owner, first_holds_row, release)
    _capture_contender_pid(contender, second_started, second_pid)

    def run_first():
        if first == "cancel":
            return cancel(owner)
        with owner._job_transaction():  # noqa: SLF001
            owner.upsert_progress(job_id=job.job_id, progress={"marker": "before-cancel"})
            first_holds_row.set()
            assert release.wait(10)
        return None

    def run_second():
        if first == "progress":
            return cancel(contender)
        with pytest.raises(ControlJobLeaseLostError):
            contender.upsert_progress(job_id=job.job_id, progress={"marker": "after-cancel"})
        return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(run_first)
        assert first_holds_row.wait(10)
        second_future = pool.submit(run_second)
        try:
            assert second_started.wait(10)
            _await_postgres_lock_wait(second_pid[0])
        finally:
            release.set()
        first_future.result(timeout=10)
        second_future.result(timeout=10)

    result = contender.get_cancelled_job_verified_record(job.job_id)
    assert result.state == "cancelled"
    assert result.progress["cancellation"]["operation_id"] == "pg-cancel"
    if first == "progress":
        assert result.progress["marker"] == "before-cancel"
    else:
        assert result.progress.get("marker") != "after-cancel"


def test_pg_identical_cancel_retry_reconciles_the_committed_winner(tmp_path: Path) -> None:
    owner, contender = _stores(tmp_path)
    job = _job(owner)
    leased = owner.lease_next_job(worker_id="retry-owner", lease_seconds=60)
    assert leased is not None and leased.job_id == job.job_id
    proof = _cancellation_proof(
        job.job_id,
        operation_id="pg-retry",
        expected_lease_owner="retry-owner",
        expected_attempt=leased.attempt,
    )
    written = threading.Event()
    second_started = threading.Event()
    second_pid: list[int] = []
    release = threading.Event()

    def cancel(store: ControlPlaneStore):
        return _sql_cancel(
            store,
            job_id=job.job_id,
            authorization_proof=proof,
            operation_id="pg-retry",
            expected_lease_owner="retry-owner",
            expected_attempt=leased.attempt,
        )

    _hold_cancel_before_commit(owner, written, release)
    _capture_contender_pid(contender, second_started, second_pid)

    def first():
        return cancel(owner)

    def second():
        return cancel(contender)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(first)
        assert written.wait(10)
        second_future = pool.submit(second)
        try:
            assert second_started.wait(10)
            _await_postgres_lock_wait(second_pid[0])
        finally:
            release.set()
        assert first_future.result(timeout=10).state == "cancelled"
        assert second_future.result(timeout=10).state == "cancelled"
    assert contender.get_cancelled_job_verified_record(job.job_id).state == "cancelled"


@pytest.mark.parametrize("first", ["complete", "cancel"])
def test_pg_completion_and_cancellation_use_one_row_first_order(tmp_path: Path, first: str) -> None:
    owner, contender = _stores(tmp_path)
    job = _job(owner)
    leased = owner.lease_next_job(worker_id="terminal-race-owner", lease_seconds=60)
    assert leased is not None and leased.job_id == job.job_id
    proof = _cancellation_proof(
        job.job_id,
        operation_id="pg-terminal-race",
        expected_lease_owner="terminal-race-owner",
        expected_attempt=leased.attempt,
    )
    written = threading.Event()
    second_started = threading.Event()
    second_pid: list[int] = []
    release = threading.Event()

    def cancel(store):
        return _sql_cancel(
            store,
            job_id=job.job_id,
            authorization_proof=proof,
            operation_id="pg-terminal-race",
            expected_lease_owner="terminal-race-owner",
            expected_attempt=leased.attempt,
        )

    if first == "cancel":
        _hold_cancel_before_commit(owner, written, release)
    else:
        original_progress = owner._upsert_progress_unchecked

        def hold_progress(**kwargs):
            original_progress(**kwargs)
            written.set()
            assert release.wait(10)

        owner._upsert_progress_unchecked = hold_progress
    _capture_contender_pid(contender, second_started, second_pid)

    def winner():
        if first == "cancel":
            return cancel(owner)
        return owner.complete_job(job_id=job.job_id, progress={"marker": "completed"})

    def loser():
        if first == "cancel":
            with pytest.raises(ControlJobLeaseLostError):
                contender.complete_job(job_id=job.job_id, progress={"marker": "late-completion"})
        else:
            with pytest.raises(ControlJobLeaseLostError):
                cancel(contender)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(winner)
        assert written.wait(10)
        second_future = pool.submit(loser)
        try:
            assert second_started.wait(10)
            _await_postgres_lock_wait(second_pid[0])
        finally:
            release.set()
        first_future.result(timeout=10)
        second_future.result(timeout=10)

    final = contender.get_job(job.job_id)
    assert final is not None
    assert final.state == ("cancelled" if first == "cancel" else "completed")
    if first == "cancel":
        assert contender.get_cancelled_job_verified_record(job.job_id).state == "cancelled"
    else:
        assert final.progress["marker"] == "completed"
