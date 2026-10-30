"""Actual shared-worker completion is distinct from Future.done and effects."""

from __future__ import annotations

import json
import threading
from concurrent.futures import CancelledError
from dataclasses import dataclass
from pathlib import Path

import pytest

import polisyos.common.async_tools as async_tools
from polisyos.fabric.connectors.resilience.circuit_breaker import CircuitBreaker
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)
from polisyos.runtime.http.resilience import BlockingDependencyGuard
from polisyos.runtime.http.services.control.child_execution_budget import (
    ChildExecutionBudgetPolicy,
    _require_attempt_budget,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker
from tests.unit.runtime.http.test_child_control_authorization import _job


@dataclass(frozen=True)
class _TestNoWorkOutcome:
    """Test-only typed result; not a production no-effects assertion."""

    status: str = "no_work"


def _test_owner_no_work(_grant: object) -> _TestNoWorkOutcome:
    """Fixed test-appointed callback with no service calls or descendants."""
    return _TestNoWorkOutcome()


class _ReleaseBarrier:
    def __init__(self) -> None:
        self.slot = threading.BoundedSemaphore(1)
        self.releasing = threading.Event()
        self.allow = threading.Event()

    def acquire(self) -> None:
        self.slot.acquire()

    def release(self) -> None:
        self.releasing.set()
        assert self.allow.wait(5)
        self.slot.release()


def test_physical_owner_does_not_promote_proxy_done_before_release() -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    barrier = _ReleaseBarrier()
    pool._physical_slot_guard = barrier
    try:
        future = pool.submit(lambda: "result")
        assert future.result(timeout=3) == "result"
        assert barrier.releasing.wait(3)
        assert future.done()
        assert future._physical_completion_state() == "pending"
        barrier.allow.set()
        future._worker_future.result(timeout=3)
        assert future._physical_completion_state() == "returned"
        assert pool.submit(lambda: "successor").result(timeout=3) == "successor"
    finally:
        barrier.allow.set()
        pool.shutdown(wait=True)


@pytest.mark.parametrize("timeout", [False, True])
def test_sqlite_claim_bound_real_guard_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, timeout: bool
) -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", pool)
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(store, kind="workflow_run")
    job = store.get_job("job-a")
    assert job is not None
    release = threading.Event()
    entered = threading.Event()
    saved: list[object] = []

    def handler(_job_record: object) -> None:
        budget = _require_attempt_budget("job-a", "run-a", attempt)
        guard = BlockingDependencyGuard(
            dependency_name="completion",
            timeout_seconds=0.1 if timeout else 2,
            breaker=CircuitBreaker("completion"),
            executor=pool,
        )
        handle = guard.create_parent_completion(store, budget)
        saved.append(handle)
        other = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
        with pytest.raises(ValueError, match="claim_owner_mismatch"):
            guard.create_parent_completion(other, budget)

        def parent(_grant) -> str:
            entered.set()
            if timeout:
                assert release.wait(3)
                with pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"):
                    _grant.check_current()
            return "actual result"

        try:
            if timeout:
                with pytest.raises(RuntimeDependencyTimeoutError):
                    guard.run_with_parent_admission(
                        parent, deadline_monotonic=budget.deadline_monotonic, completion=handle
                    )
                assert entered.is_set()
                observation = handle.observe()
                assert observation.physical_state == "pending"
                assert observation.interrupted
                release.set()
                handle._future._worker_future.result(timeout=3)
                observation = handle.observe()
                assert observation.physical_state == "returned"
                assert observation.interrupted
            else:
                assert (
                    guard.run_with_parent_admission(
                        _test_owner_no_work,
                        deadline_monotonic=budget.deadline_monotonic,
                        completion=handle,
                    )
                    == _TestNoWorkOutcome()
                )
                assert handle.matches_callback(_test_owner_no_work)
                assert not handle.matches_callback(parent)
                handle._future._worker_future.result(timeout=3)
                observation = handle.observe()
                assert observation.physical_state == "returned"
                assert not observation.interrupted
                with pytest.raises(ValueError, match="guard_completion_handle_not_current"):
                    guard.run_with_parent_admission(
                        parent, deadline_monotonic=budget.deadline_monotonic, completion=handle
                    )

            def lost_readback(*_args: object) -> None:
                raise OSError("actual claim readback unavailable")

            with monkeypatch.context() as failing:
                failing.setattr(store, "read_child_attempt_budget", lost_readback)
                with pytest.raises(OSError, match="claim readback unavailable"):
                    handle.observe()
        finally:
            release.set()
            guard.close()

    worker = ControlWorker(
        store=store,
        handler=handler,
        worker_id="worker-a",
        child_execution_budget_policy=ChildExecutionBudgetPolicy("test", "1", 10),
    )
    try:
        worker._run_with_lease_heartbeat(job)
        # Historical observation uses the original retained owner and actual claim
        # after scope revocation; it is not authority to mark effects settled.
        assert saved[0].observe().physical_state == "returned"
    finally:
        release.set()
        pool.shutdown(wait=True)


def test_physical_return_is_not_descendant_or_effect_settlement() -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    started = threading.Event()
    release = threading.Event()
    completed = threading.Event()
    threads: list[threading.Thread] = []

    def background() -> None:
        started.set()
        assert release.wait(3)
        completed.set()

    def parent() -> str:
        thread = threading.Thread(target=background)
        threads.append(thread)
        thread.start()
        assert started.wait(3)
        return "caller returned"

    try:
        future = pool.submit(parent)
        assert future.result(timeout=3) == "caller returned"
        future._worker_future.result(timeout=3)
        assert future._physical_completion_state() == "returned"
        assert not completed.is_set()
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=3)
        pool.shutdown(wait=True)


def test_timeout_tracking_waits_for_actual_slot_release() -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    barrier = _ReleaseBarrier()
    pool._physical_slot_guard = barrier
    unblock = threading.Event()
    entered = threading.Event()
    guard = BlockingDependencyGuard(
        dependency_name="cas-proof",
        timeout_seconds=0.1,
        breaker=CircuitBreaker("cas-proof"),
        executor=pool,
    )

    def operation() -> str:
        entered.set()
        assert unblock.wait(3)
        return "returned"

    try:
        with pytest.raises(RuntimeDependencyTimeoutError):
            guard.run(operation)
        assert entered.is_set()
        assert guard.has_unsettled_operations()
        unblock.set()
        assert barrier.releasing.wait(3)
        tracked = next(iter(guard._timed_out_futures))
        assert tracked.done()
        assert guard.has_unsettled_operations()
        barrier.allow.set()
        tracked._worker_future.result(timeout=3)
        assert not guard.has_unsettled_operations()
    finally:
        unblock.set()
        barrier.allow.set()
        guard.close()
        pool.shutdown(wait=True)


def test_cancelled_worker_waits_for_owner_callback_and_reservation_cleanup() -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    first_entered = threading.Event()
    release_first = threading.Event()
    callback_waiting = threading.Event()
    actual_callback_runner = pool.run_callback_sync

    def first() -> None:
        first_entered.set()
        assert release_first.wait(4)

    def observed_callback_runner(callback, *args):
        callback_waiting.set()
        return actual_callback_runner(callback, *args)

    pool.run_callback_sync = observed_callback_runner
    first_future = pool.submit(first)
    assert first_entered.wait(2)
    second = pool.submit(lambda: "never called")
    second.add_done_callback(lambda _future: None)
    worker = second._worker_future
    assert worker is not None
    cancel_thread = threading.Thread(target=worker.cancel)
    try:
        cancel_thread.start()
        assert callback_waiting.wait(2)
        assert worker.done()
        assert second._physical_completion_state() == "pending"
        release_first.set()
        cancel_thread.join(timeout=4)
        assert not cancel_thread.is_alive()
        assert second._physical_completion_state() == "not_started"
        first_future._worker_future.result(timeout=3)
    finally:
        release_first.set()
        cancel_thread.join(timeout=4)
        pool.shutdown(wait=True)


@pytest.mark.parametrize("signal_name", ["lease_lost", "heartbeat_unknown"])
@pytest.mark.parametrize("decision", ["admission", "publication"])
def test_owner_uncertainty_revokes_child_grant_and_marks_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, signal_name: str, decision: str
) -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", pool)
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(store, kind="workflow_run")
    job = store.get_job("job-a")
    assert job is not None
    started = threading.Event()
    renewal_returning = threading.Event()
    saved: list[object] = []

    def renew(**_kwargs: object) -> bool:
        assert started.wait(3)
        renewal_returning.set()
        if signal_name == "lease_lost":
            return False
        raise RuntimeDependencyUnavailableError("test-heartbeat")

    monkeypatch.setattr(store, "renew_job_lease", renew)

    def handler(_job_record: object) -> None:
        budget = _require_attempt_budget("job-a", "run-a", attempt)
        guard = BlockingDependencyGuard(
            dependency_name="completion-signal",
            timeout_seconds=3,
            breaker=CircuitBreaker("completion-signal"),
            executor=pool,
        )
        handle = guard.create_parent_completion(store, budget)
        saved.append(handle)

        def parent(grant) -> str:
            basis = json.dumps(
                {
                    "artifact_id": "sha256:" + "1" * 64,
                    "kind": "test.basis",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "2" * 64,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            grant.bind_parent(
                run_id="run-a", job_id="job-a", attempt_id="test-parent", basis_ref=basis
            )
            signal = budget.interrupt.lost if signal_name == "lease_lost" else budget.uncertain
            with getattr(grant, decision)():
                started.set()
                assert renewal_returning.wait(3)
                assert not signal.is_set()
            assert signal.wait(3)
            with pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"):
                grant.check_current()
            with pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"):
                grant.run_child(lambda: None)
            with (
                pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"),
                grant.publication(),
            ):
                pytest.fail("publication after owner uncertainty")
            return "stale result"

        try:
            assert (
                guard.run_with_parent_admission(
                    parent, deadline_monotonic=budget.deadline_monotonic, completion=handle
                )
                == "stale result"
            )
            handle._future._worker_future.result(timeout=3)
            assert handle.observe().physical_state == "returned"
            assert handle.observe().interrupted
        finally:
            guard.close()

    worker = ControlWorker(
        store=store,
        handler=handler,
        worker_id="worker-a",
        lease_seconds=1,
        child_execution_budget_policy=ChildExecutionBudgetPolicy("test", "1", 10),
    )
    try:
        worker._run_with_lease_heartbeat(job)
        assert saved[0].observe().interrupted
    finally:
        pool.shutdown(wait=True)


def test_foreign_executor_timeout_remains_unknown_after_future_done() -> None:
    release = threading.Event()
    entered = threading.Event()
    guard = BlockingDependencyGuard(
        dependency_name="foreign",
        timeout_seconds=0.1,
        breaker=CircuitBreaker("foreign"),
        executor_max_workers=1,
    )

    def operation() -> None:
        entered.set()
        assert release.wait(3)

    try:
        with pytest.raises(RuntimeDependencyTimeoutError):
            guard.run(operation)
        assert entered.is_set()
        release.set()
        guard._executor.shutdown(wait=True)
        assert guard.has_unsettled_operations()
    finally:
        release.set()
        guard.close()


def test_timeout_revoke_and_worker_share_issuer_lock_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A paused revocation fences worker admission even before invocation starts."""
    import contextvars

    from polisyos.common.borrowed_execution import _BlockingAttempt

    pool = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", pool)
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt_id = _job(store, kind="workflow_run")
    job = store.get_job("job-a")
    assert job is not None
    worker_gate = threading.Event()
    worker_waiting = threading.Event()
    revoke_held = threading.Event()
    release_revoke = threading.Event()
    callback_started = threading.Event()
    outcomes: list[BaseException] = []
    caller_id: list[int] = []
    original_revoke = _BlockingAttempt.revoke

    def handler(_job_record: object) -> None:
        budget = _require_attempt_budget("job-a", "run-a", attempt_id)
        guard = BlockingDependencyGuard(
            dependency_name="completion-lock",
            timeout_seconds=0.2,
            breaker=CircuitBreaker("completion-lock"),
            executor=pool,
        )
        handle = guard.create_parent_completion(store, budget)
        original_check = handle._require_current
        checks = 0

        def gated_check() -> None:
            nonlocal checks
            checks += 1
            if checks == 2:
                worker_waiting.set()
                assert worker_gate.wait(5)
            original_check()

        def held_revoke(self: _BlockingAttempt) -> None:
            if caller_id and threading.get_ident() == caller_id[0] and not revoke_held.is_set():
                with self.transition_lock:
                    revoke_held.set()
                    assert release_revoke.wait(5)
                    original_revoke(self)
            else:
                original_revoke(self)

        monkeypatch.setattr(handle, "_require_current", gated_check)
        monkeypatch.setattr(_BlockingAttempt, "revoke", held_revoke)

        def callback(_grant: object) -> None:
            callback_started.set()

        def run() -> None:
            caller_id.append(threading.get_ident())
            try:
                guard.run_with_parent_admission(
                    callback, deadline_monotonic=budget.deadline_monotonic, completion=handle
                )
            except BaseException as exc:
                outcomes.append(exc)

        context = contextvars.copy_context()
        caller = threading.Thread(target=context.run, args=(run,))
        try:
            caller.start()
            assert worker_waiting.wait(3)
            assert revoke_held.wait(3)
            worker_gate.set()
            # The worker cannot cross the authority decision while revocation
            # holds the issuer lock, including when it wins the scheduling race.
            assert not callback_started.wait(0.2)
            release_revoke.set()
            caller.join(timeout=3)
            assert not caller.is_alive()
            assert len(outcomes) == 1
            assert isinstance(outcomes[0], RuntimeDependencyTimeoutError)
            handle._future._worker_future.result(timeout=3)
            assert not callback_started.is_set()
            observation = handle.observe()
            assert observation.physical_state == "failed"
            assert observation.interrupted
        finally:
            worker_gate.set()
            release_revoke.set()
            caller.join(timeout=3)
            guard.close()

    worker = ControlWorker(
        store=store,
        handler=handler,
        worker_id="worker-a",
        child_execution_budget_policy=ChildExecutionBudgetPolicy("test", "1", 10),
    )
    try:
        worker._run_with_lease_heartbeat(job)
    finally:
        worker_gate.set()
        release_revoke.set()
        pool.shutdown(wait=True)


def test_timeout_of_queued_cancel_stays_unsettled_until_owner_cleanup() -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    entered = threading.Event()
    release = threading.Event()
    callback_started = threading.Event()

    def occupying() -> None:
        entered.set()
        assert release.wait(5)

    running = pool.submit(occupying)
    guard = BlockingDependencyGuard(
        dependency_name="queued-cancel",
        timeout_seconds=0.1,
        breaker=CircuitBreaker("queued-cancel"),
        executor=pool,
    )
    try:
        assert entered.wait(3)
        with pytest.raises(RuntimeDependencyTimeoutError):
            guard.run(callback_started.set)
        assert not callback_started.is_set()
        assert guard.has_unsettled_operations()
        release.set()
        running._worker_future.result(timeout=3)
        pool.shutdown(wait=True)
        assert not callback_started.is_set()
        assert not guard.has_unsettled_operations()
    finally:
        release.set()
        guard.close()
        pool.shutdown(wait=True)


def test_external_queued_cancel_stays_unsettled_until_owner_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    entered = threading.Event()
    release_worker = threading.Event()
    queued = threading.Event()
    cleaning = threading.Event()
    release_cleanup = threading.Event()
    outcomes: list[BaseException] = []

    def occupying() -> None:
        entered.set()
        assert release_worker.wait(5)

    pool.submit(occupying)
    original_submit = pool.submit
    original_finish = async_tools._SharedFuture._finish_work

    def submit(*args: object, **kwargs: object):
        future = original_submit(*args, **kwargs)
        queued.set()
        return future

    def finish(future: object) -> None:
        worker = future._worker_future
        if worker is not None and worker.cancelled():
            cleaning.set()
            assert release_cleanup.wait(5)
        original_finish(future)

    monkeypatch.setattr(pool, "submit", submit)
    monkeypatch.setattr(async_tools._SharedFuture, "_finish_work", finish)
    guard = BlockingDependencyGuard(
        dependency_name="external-cancel",
        timeout_seconds=4,
        breaker=CircuitBreaker("external-cancel"),
        executor=pool,
    )

    def invoke() -> None:
        try:
            guard.run(lambda: None)
        except BaseException as exc:
            outcomes.append(exc)

    caller = threading.Thread(target=invoke)
    stopper = threading.Thread(target=lambda: pool.shutdown(wait=False, cancel_futures=True))
    try:
        assert entered.wait(3)
        caller.start()
        assert queued.wait(3)
        stopper.start()
        assert cleaning.wait(3)
        caller.join(timeout=3)
        assert not caller.is_alive()
        assert len(outcomes) == 1
        assert isinstance(outcomes[0], CancelledError)
        assert guard.has_unsettled_operations()
        release_cleanup.set()
        stopper.join(timeout=3)
        release_worker.set()
        pool.shutdown(wait=True)
        assert not guard.has_unsettled_operations()
    finally:
        release_cleanup.set()
        release_worker.set()
        caller.join(timeout=3)
        if stopper.ident is not None:
            stopper.join(timeout=3)
        guard.close()
        pool.shutdown(wait=True)
