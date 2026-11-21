from __future__ import annotations

import ctypes
import os
import select
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from contextvars import Context
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import TYPE_CHECKING, cast

import pytest

from polisyos.common.job_execution_interrupt import require_current_job_execution_owner
from polisyos.runtime.http.resilience import guard_runtime_control_store
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord

_DURATION_ENV = "POLISYOS_CONTROL_SQLITE_LEASE_RENEWAL_MAX_SECONDS"


def _create_store(path: Path) -> ControlPlaneStore:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    store.create_job(
        job_id="job-lease-pulse",
        kind="workflow_run",
        run_id="run-lease-pulse",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="fixture",
    )
    return store


@pytest.mark.skipif(
    os.name != "posix" or sys.implementation.name != "cpython" or not sys._is_gil_enabled(),
    reason="Uses a deliberate PyDLL call that retains the CPython GIL",
)
@pytest.mark.parametrize("independent", [False, True])
def test_dispatch_lease_through_interpreter_stall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, independent: bool
) -> None:
    if independent:
        monkeypatch.setenv(_DURATION_ENV, "15")
    else:
        monkeypatch.delenv(_DURATION_ENV, raising=False)
    store = _create_store(tmp_path / "control.sqlite3")
    libc_sleep = ctypes.PyDLL(None).sleep
    libc_sleep.argtypes = [ctypes.c_uint]
    libc_sleep.restype = ctypes.c_uint
    state_before_settlement: list[ControlJobRecord] = []

    def handler(job: ControlJobRecord) -> None:
        assert libc_sleep(4) == 0
        current = store.get_job(job.job_id)
        assert current is not None
        state_before_settlement.append(current)
        require_current_job_execution_owner(job.job_id)
        authority.complete_job(job_id=job.job_id)

    with closing(guard_runtime_control_store(store)) as authority:
        worker = ControlWorker(
            store=cast("ControlPlaneStore", authority),
            handler=handler,
            worker_id="lease-worker",
            lease_seconds=3,
        )
        assert worker.dispatch_once()
    [observed] = state_before_settlement
    final = store.get_job(observed.job_id)
    assert final is not None
    assert observed.lease_owner == "lease-worker"
    assert observed.attempt == final.attempt == 1
    assert observed.lease_expires_at is not None
    if independent:
        assert final.state == "completed"
        assert final.lease_expires_at is None
    else:
        assert observed.lease_expires_at <= datetime.now(UTC)
        assert final.state == "running"


@pytest.mark.skipif(os.name != "posix", reason="Independent pulse is POSIX only")
def test_dispatch_refuses_effect_after_pulse_process_dies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_DURATION_ENV, "30")
    store = _create_store(tmp_path / "control.sqlite3")
    completed: list[str] = []

    def handler(job: ControlJobRecord) -> None:
        peer = worker._active_sqlite_lease_pulse
        assert peer is not None
        peer._process.kill()
        assert peer._process.wait(timeout=2) < 0
        current = store.get_job(job.job_id)
        assert current is not None and current.lease_expires_at is not None
        assert current.lease_expires_at > datetime.now(UTC)
        with pytest.raises(ControlJobLeaseLostError):
            store.complete_job(job_id=job.job_id)
        require_current_job_execution_owner(job.job_id)
        store.complete_job(job_id=job.job_id)
        completed.append(job.job_id)

    worker = ControlWorker(store=store, handler=handler, worker_id="lease-worker", lease_seconds=10)

    assert worker.dispatch_once()
    assert completed == []
    assert worker._active_sqlite_lease_pulse is None
    current = store.get_job("job-lease-pulse")
    assert current is not None
    assert current.state == "running"
    assert current.attempt == 1


@pytest.mark.skipif(os.name != "posix", reason="Independent pulse is POSIX only")
def test_dispatch_refuses_replaced_configured_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_DURATION_ENV, "30")
    path = tmp_path / "control.sqlite3"
    store = _create_store(path)
    ran: list[str] = []
    worker = ControlWorker(
        store=store, handler=lambda job: ran.append(job.job_id), lease_seconds=10
    )

    other_path = tmp_path / "replacement.sqlite3"
    _create_store(other_path)
    other_path.replace(path)

    with pytest.raises(ControlJobLeaseLostError, match="pulse database changed"):
        worker.dispatch_once()

    assert ran == []
    assert worker._active_sqlite_lease_pulse is None
    current = store.get_job("job-lease-pulse")
    assert current is not None and current.state == "pending" and current.attempt == 0


@pytest.mark.skipif(os.name != "posix", reason="Independent pulse is POSIX only")
def test_pulse_stops_on_abrupt_worker_process_death(tmp_path: Path) -> None:
    path = tmp_path / "control.sqlite3"
    store = _create_store(path)
    owner_entry = """
import sys
from time import sleep

sys.path.insert(0, sys.argv[1])
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker

def handler(job):
    print('ready', flush=True)
    sleep(15)

store = ControlPlaneStore(backend='sqlite', sqlite_path=sys.argv[2])
ControlWorker(store=store, handler=handler, worker_id='lease-worker', lease_seconds=6).dispatch_once()
"""
    source = Path(__file__).parents[5] / "src"
    with subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", owner_entry, str(source), str(path)],
        env={_DURATION_ENV: "15"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as owner:
        try:
            assert owner.stdout is not None and owner.stderr is not None
            assert select.select([owner.stdout], [], [], 8)[0]
            assert owner.stdout.readline() == b"ready\n"
            before = store.get_job("job-lease-pulse")
            assert before is not None and before.lease_expires_at is not None
            assert before.lease_owner == "lease-worker" and before.attempt == 1
            # Retain the writer across the first scheduled independent pulse.
            with closing(sqlite3.connect(path)) as writer:
                writer.execute("BEGIN IMMEDIATE")
                sleep(2.5)
                owner.kill()
                assert owner.wait(timeout=2) < 0
                writer.rollback()
            # The actual peer inherited this stderr endpoint from the killed owner.
            end = monotonic() + 2
            while True:
                assert select.select([owner.stderr], [], [], max(0, end - monotonic()))[0]
                if os.read(owner.stderr.fileno(), 4096) == b"":
                    break
                assert monotonic() < end
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=2)

    remaining = (before.lease_expires_at - datetime.now(UTC)).total_seconds()
    sleep(max(0.0, remaining) + 0.05)
    unchanged = store.get_job(before.job_id)
    assert unchanged == before
    successor = store.lease_next_job(worker_id="successor", lease_seconds=3)
    assert successor is not None
    assert successor.job_id == before.job_id and successor.attempt == 2


@pytest.mark.skipif(os.name != "posix", reason="Independent pulse is POSIX only")
def test_stop_works_when_a_live_descendant_holds_the_lifetime_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_DURATION_ENV, "30")
    store = _create_store(tmp_path / "control.sqlite3")

    def handler(job: ControlJobRecord) -> None:
        peer = worker._active_sqlite_lease_pulse
        assert peer is not None and peer._process.stdin is not None
        lifetime_fd = peer._process.stdin.fileno()
        holder = (
            "import os,sys,time; os.fstat(int(sys.argv[1])); "
            "print('holding', flush=True); time.sleep(10)"
        )
        with subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", "-c", holder, str(lifetime_fd)],
            pass_fds=(lifetime_fd,),
            stdout=subprocess.PIPE,
        ) as descendant:
            try:
                assert descendant.stdout is not None
                assert select.select([descendant.stdout], [], [], 2)[0]
                assert descendant.stdout.readline() == b"holding\n"
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(Context().run, worker.stop).result(timeout=2)
                assert peer._process.wait(timeout=2) == 0
                assert descendant.poll() is None
            finally:
                descendant.kill()
        with pytest.raises(ControlJobLeaseLostError):
            store.complete_job(job_id=job.job_id)

    worker = ControlWorker(store=store, handler=handler, worker_id="lease-worker", lease_seconds=10)

    assert worker.dispatch_once()
    assert worker._active_sqlite_lease_pulse is None
    assert not worker.dispatch_once()


@pytest.mark.skipif(os.name != "posix", reason="Independent pulse is POSIX only")
def test_pulse_retries_a_busy_writer_while_same_lease_is_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_DURATION_ENV, "40")
    path = tmp_path / "control.sqlite3"
    store = _create_store(path)

    def handler(job: ControlJobRecord) -> None:
        admitted_expiry = store.current_execution_job_record().lease_expires_at
        assert admitted_expiry is not None
        with closing(sqlite3.connect(path)) as writer:
            writer.execute("BEGIN IMMEDIATE")
            # The first 5s pulse reaches SQLite's 5s busy deadline during the hold.
            sleep(11.2)
            assert store.current_execution_job_record().lease_expires_at == admitted_expiry
            writer.rollback()
        deadline = monotonic() + 3
        while True:
            refreshed = store.current_execution_job_record()
            assert refreshed.lease_expires_at is not None
            if refreshed.lease_expires_at > admitted_expiry:
                break
            assert monotonic() < deadline
            sleep(0.05)
        store.complete_job(job_id=job.job_id)

    worker = ControlWorker(store=store, handler=handler, worker_id="lease-worker", lease_seconds=20)

    assert worker.dispatch_once()
    final = store.get_job("job-lease-pulse")
    assert final is not None and final.state == "completed" and final.attempt == 1
