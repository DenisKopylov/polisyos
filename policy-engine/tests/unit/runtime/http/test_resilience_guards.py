from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import CancelledError as FutureCancelledError
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from typing import Any, NoReturn

import pytest

from polisyos.common.async_tools import get_shared_executor
from polisyos.fabric.connectors.resilience import with_rate_limit
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitAttemptLease,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitLeaseError,
)
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)
from polisyos.runtime.http.resilience import (
    AsyncDependencyGuard,
    BlockingDependencyGuard,
    build_runtime_cas_guard,
    build_runtime_control_store_guard,
)


def test_runtime_control_store_guard_reserves_capacity_from_compute() -> None:
    cas_guard = build_runtime_cas_guard()
    control_store_guard = build_runtime_control_store_guard()

    try:
        assert cas_guard._executor is get_shared_executor()
        assert control_store_guard._executor is not get_shared_executor()
        assert control_store_guard._owns_executor is True
    finally:
        cas_guard.close()
        control_store_guard.close()


class _RecordingCircuitBreaker(CircuitBreaker):
    def __init__(self) -> None:
        super().__init__(
            circuit_id="runtime-lease-witness",
            config=CircuitBreakerConfig(failure_threshold=1, min_throughput=1),
        )
        self.released_lease: CircuitAttemptLease | None = None

    def _release_cancelled_lease(self, lease: CircuitAttemptLease | None) -> None:
        self.released_lease = lease
        super()._release_cancelled_lease(lease)


@pytest.mark.asyncio
async def test_runtime_async_cancellation_retires_closed_lease() -> None:
    breaker = _RecordingCircuitBreaker()
    guard = AsyncDependencyGuard(
        dependency_name="runtime-cancellation",
        timeout_seconds=1.0,
        breaker=breaker,
    )
    started = asyncio.Event()

    async def blocked() -> None:
        started.set()
        await asyncio.Future()

    task = asyncio.create_task(guard.run(blocked))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    lease = breaker.released_lease
    assert lease is not None
    with pytest.raises(CircuitLeaseError):
        breaker.record_success(lease)


class _RejectingExecutor:
    def submit(self, *args: Any, **kwargs: Any) -> NoReturn:
        del args, kwargs
        raise RuntimeError("executor is closed")


def test_runtime_executor_submit_failure_retires_closed_lease() -> None:
    breaker = _RecordingCircuitBreaker()
    guard = BlockingDependencyGuard(
        dependency_name="runtime-submit",
        timeout_seconds=1.0,
        breaker=breaker,
        executor=_RejectingExecutor(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeDependencyUnavailableError):
        guard.run(lambda: None)

    lease = breaker.released_lease
    assert lease is not None
    with pytest.raises(CircuitLeaseError):
        breaker.record_success(lease)


def _half_open_plain_breaker(monkeypatch: pytest.MonkeyPatch) -> CircuitBreaker:
    """Create a plain owner whose next admitted attempt is HALF_OPEN."""
    import polisyos.fabric.connectors.resilience.circuit_breaker as breaker_module

    now = [100.0]
    monkeypatch.setattr(breaker_module, "_monotonic", lambda: now[0])
    breaker = CircuitBreaker(
        circuit_id="runtime-plain-half-open",
        config=CircuitBreakerConfig(
            failure_threshold=1,
            min_throughput=1,
            success_threshold=1,
            half_open_max_calls=1,
            timeout_seconds=1.0,
        ),
    )
    breaker.record_failure()
    assert breaker.is_open()
    now[0] += 2.0
    return breaker


@pytest.mark.asyncio
async def test_runtime_async_plain_breaker_releases_half_open_on_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breaker = _half_open_plain_breaker(monkeypatch)
    guard = AsyncDependencyGuard(
        dependency_name="runtime-plain-half-open-cancel",
        timeout_seconds=5.0,
        breaker=breaker,
    )
    started = asyncio.Event()

    async def blocked() -> None:
        started.set()
        await asyncio.Future()

    task = asyncio.create_task(guard.run(blocked))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert breaker.is_half_open()
        assert breaker.get_stats()["half_open_calls"] == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert breaker.get_stats()["half_open_calls"] == 0
        replacement = breaker.acquire_attempt()
        assert replacement is not None
        breaker.record_success(replacement)
        assert breaker.is_closed()
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


def test_runtime_blocking_plain_breaker_releases_half_open_on_submit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breaker = _half_open_plain_breaker(monkeypatch)
    guard = BlockingDependencyGuard(
        dependency_name="runtime-plain-half-open-submit",
        timeout_seconds=1.0,
        breaker=breaker,
        executor=_RejectingExecutor(),  # type: ignore[arg-type]
    )
    try:
        with pytest.raises(RuntimeDependencyUnavailableError):
            guard.run(lambda: pytest.fail("provider must not run"))
        assert breaker.is_half_open()
        assert breaker.get_stats()["half_open_calls"] == 0
        replacement = breaker.acquire_attempt()
        assert replacement is not None
        breaker.record_success(replacement)
        assert breaker.is_closed()
    finally:
        guard.close()


def _half_open_recording_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_RecordingCircuitBreaker, list[float]]:
    """Enter HALF_OPEN through the real breaker and a controlled monotonic clock."""
    import polisyos.fabric.connectors.resilience.circuit_breaker as breaker_module

    now = [100.0]
    monkeypatch.setattr(breaker_module, "_monotonic", lambda: now[0])
    breaker = _RecordingCircuitBreaker()
    breaker.record_failure()
    assert breaker.is_open()
    now[0] += breaker.config.timeout_seconds + 1.0
    return breaker, now


@pytest.mark.asyncio
async def test_runtime_async_cancellation_releases_half_open_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breaker, _now = _half_open_recording_breaker(monkeypatch)
    guard = AsyncDependencyGuard(
        dependency_name="runtime-half-open-cancel",
        timeout_seconds=5.0,
        breaker=breaker,
    )
    started = asyncio.Event()

    async def blocked() -> None:
        started.set()
        await asyncio.Future()

    task = asyncio.create_task(guard.run(blocked))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert breaker.is_half_open()
        assert breaker.acquire_attempt() is None
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        retired = breaker.released_lease
        assert retired is not None and retired.owns_half_open_slot
        replacement = breaker.acquire_attempt()
        assert replacement is not None and replacement.owns_half_open_slot
        with pytest.raises(CircuitLeaseError):
            breaker.record_success(retired)
        assert breaker.acquire_attempt() is None
        breaker.record_success(replacement)
        assert breaker.is_half_open()
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_native_breaker_cancellation_notifies_legacy_override() -> None:
    breaker = _RecordingCircuitBreaker()
    started = asyncio.Event()

    async def blocked() -> None:
        started.set()
        await asyncio.Future()

    task = asyncio.create_task(breaker.execute(blocked))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        retired = breaker.released_lease
        assert retired is not None
        with pytest.raises(CircuitLeaseError):
            breaker.record_success(retired)
        assert breaker.can_attempt()
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_local_rate_refusal_does_not_invoke_legacy_cancel_hook() -> None:
    breaker = _RecordingCircuitBreaker()

    @with_rate_limit(rate_limit_rps=0.0)
    async def provider() -> str:
        raise AssertionError("local admission must precede provider")

    with pytest.raises(ValueError, match="rate_limit_rps"):
        await breaker.execute(provider)
    assert breaker.released_lease is None
    assert breaker.is_closed()

    async def healthy() -> str:
        return "healthy"

    assert await breaker.execute(healthy) == "healthy"


class _ObservedThreadPool(ThreadPoolExecutor):
    """Expose the actual Future produced for a queued guard operation."""

    def __init__(self) -> None:
        super().__init__(max_workers=1)
        self.capture = False
        self.submitted = threading.Event()
        self.captured_future: Future[Any] | None = None

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future[Any]:
        future = super().submit(fn, *args, **kwargs)
        if self.capture:
            self.captured_future = future
            self.submitted.set()
        return future


def test_blocking_guard_preserves_on_time_backend_timeout_and_breaker_policy() -> None:
    error = TimeoutError("backend timeout; test-only detail")
    breaker = _RecordingCircuitBreaker()
    guard = BlockingDependencyGuard(
        dependency_name="test-backend",
        timeout_seconds=1.0,
        breaker=breaker,
    )

    def backend() -> None:
        raise error

    try:
        with pytest.raises(TimeoutError) as caught:
            guard.run(backend)
        assert caught.value is error
        assert not isinstance(caught.value, RuntimeDependencyTimeoutError)
        assert breaker.is_closed()
    finally:
        guard.close()


def test_blocking_guard_preserves_backend_timeout_unavailability_classification() -> None:
    error = TimeoutError("backend raised its own timeout")
    breaker = _RecordingCircuitBreaker()
    guard = BlockingDependencyGuard(
        dependency_name="test-backend",
        timeout_seconds=1.0,
        breaker=breaker,
        unavailable_exception_types=(OSError,),
    )

    def backend() -> None:
        raise error

    try:
        with pytest.raises(RuntimeDependencyUnavailableError) as caught:
            guard.run(backend)
        assert caught.value.__cause__ is error
        assert breaker.is_open()
    finally:
        guard.close()


@pytest.mark.parametrize("raises_timeout", [False, True])
def test_blocking_guard_accepts_finished_outcome_before_delayed_future_delivery(
    raises_timeout: bool,
) -> None:
    """A completed callable, not the delayed Future publication, owns timing."""
    published = threading.Event()
    release = threading.Event()
    error = TimeoutError("completed before deadline")
    returned = object()
    callbacks: list[Future[Any]] = []

    class DelayedFuturePublication(ThreadPoolExecutor):
        def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future[Any]:
            def invoke() -> Any:
                try:
                    return fn(*args, **kwargs)
                finally:
                    published.set()
                    release.wait(timeout=5)

            return super().submit(invoke)

    executor = DelayedFuturePublication(max_workers=1)
    breaker = _RecordingCircuitBreaker()
    guard = BlockingDependencyGuard(
        dependency_name="test-delayed-publication",
        timeout_seconds=0.15,
        breaker=breaker,
        executor=executor,
    )

    def backend() -> object:
        if raises_timeout:
            raise error
        return returned

    try:
        snapshot = replace(guard._snapshot(), on_timeout=callbacks.append)
        if raises_timeout:
            with pytest.raises(TimeoutError) as caught:
                guard._run_snapshot(snapshot, backend)
            assert caught.value is error
        else:
            assert guard._run_snapshot(snapshot, backend) is returned
        assert published.is_set()
        assert callbacks == []
        assert breaker.is_closed()
    finally:
        release.set()
        guard.close()
        executor.shutdown(wait=True, cancel_futures=True)


def test_blocking_guard_queued_deadline_cancels_without_late_callback() -> None:
    executor = _ObservedThreadPool()
    entered = threading.Event()
    release = threading.Event()
    callbacks: list[Future[Any]] = []
    breaker = _RecordingCircuitBreaker()
    guard = BlockingDependencyGuard(
        dependency_name="test-queued",
        timeout_seconds=0.15,
        breaker=breaker,
        executor=executor,
    )

    def occupy() -> None:
        entered.set()
        release.wait(timeout=5)

    try:
        executor.submit(occupy)
        assert entered.wait(timeout=2)
        executor.capture = True
        snapshot = replace(guard._snapshot(), on_timeout=callbacks.append)
        with pytest.raises(RuntimeDependencyTimeoutError) as caught:
            guard._run_snapshot(snapshot, lambda: pytest.fail("queued call ran"))
        diagnostic = caught.value.diagnostic()  # type: ignore[attr-defined]
        assert diagnostic["wait_disposition"] == "cancelled_before_start"
        assert diagnostic["queue_wait_seconds"] is None
        assert executor.captured_future is not None and executor.captured_future.cancelled()
        assert callbacks == []
        assert breaker.is_open()
    finally:
        release.set()
        guard.close()
        executor.shutdown(wait=True, cancel_futures=True)


def test_blocking_guard_running_deadline_retains_future_and_late_backend_exception() -> None:
    entered = threading.Event()
    release = threading.Event()
    callbacks: list[Future[Any]] = []
    backend_error = TimeoutError("late backend timeout")
    breaker = _RecordingCircuitBreaker()
    guard = BlockingDependencyGuard(
        dependency_name="test-running",
        timeout_seconds=0.15,
        breaker=breaker,
    )

    def backend() -> None:
        entered.set()
        release.wait(timeout=5)
        raise backend_error

    try:
        snapshot = replace(guard._snapshot(), on_timeout=callbacks.append)
        with pytest.raises(RuntimeDependencyTimeoutError) as caught:
            guard._run_snapshot(snapshot, backend)
        assert entered.is_set()
        assert len(callbacks) == 1 and callbacks[0].running()
        diagnostic = caught.value.diagnostic()  # type: ignore[attr-defined]
        assert diagnostic["timeout_seconds"] == 0.15
        assert diagnostic["wait_disposition"] == "running_at_observation"
        assert diagnostic["operation"]["qualname"].endswith(".backend")
        assert "late backend timeout" not in str(diagnostic)
        assert breaker.is_open()
        release.set()
        with pytest.raises(TimeoutError) as late:
            callbacks[0].result(timeout=2)
        assert late.value is backend_error
        assert len(callbacks) == 1
    finally:
        release.set()
        guard.close()


def test_blocking_guard_rejects_late_backend_error_even_if_future_has_finished() -> None:
    release = threading.Event()
    error = TimeoutError("backend finished after wait deadline")
    callbacks: list[Future[Any]] = []

    class LateDeliveryExecutor(ThreadPoolExecutor):
        def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future[Any]:
            future = super().submit(fn, *args, **kwargs)
            actual_result = future.result

            def after_wait(timeout: float | None = None) -> Any:
                try:
                    return actual_result(timeout=timeout)
                except TimeoutError:
                    # The waiting thread is scheduled only after the deadline;
                    # let the actual callable finish before returning control.
                    release.set()
                    return actual_result(timeout=3)

            future.result = after_wait  # type: ignore[method-assign]
            return future

    executor = LateDeliveryExecutor(max_workers=1)
    guard = BlockingDependencyGuard(
        dependency_name="test-late-finished",
        timeout_seconds=0.15,
        breaker=_RecordingCircuitBreaker(),
        executor=executor,
    )

    def backend() -> None:
        release.wait(timeout=5)
        raise error

    try:
        snapshot = replace(guard._snapshot(), on_timeout=callbacks.append)
        with pytest.raises(RuntimeDependencyTimeoutError) as caught:
            guard._run_snapshot(snapshot, backend)
        diagnostic = caught.value.diagnostic()  # type: ignore[attr-defined]
        assert diagnostic["wait_disposition"] == "finished_after_deadline"
        assert len(callbacks) == 1 and callbacks[0].done()
        with pytest.raises(TimeoutError) as late:
            callbacks[0].result(timeout=1)
        assert late.value is error
    finally:
        release.set()
        guard.close()
        executor.shutdown(wait=True, cancel_futures=True)


def test_nested_guard_preserves_on_time_backend_timeout() -> None:
    guard = build_runtime_control_store_guard()
    error = TimeoutError("nested backend timeout")

    def backend() -> None:
        raise error

    try:
        with pytest.raises(RuntimeDependencyUnavailableError) as caught:
            guard.run(lambda: guard.run(backend))
        assert caught.value.__cause__ is error
    finally:
        guard.close()


def test_blocking_guard_cancelled_future_releases_half_open_before_late_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breaker, _now = _half_open_recording_breaker(monkeypatch)
    executor = _ObservedThreadPool()
    worker_started = threading.Event()
    release_worker = threading.Event()
    guard_finished = threading.Event()
    outcomes: list[BaseException] = []

    def hold_worker() -> None:
        worker_started.set()
        release_worker.wait(timeout=5)

    guard = BlockingDependencyGuard(
        dependency_name="runtime-half-open-future",
        timeout_seconds=5.0,
        breaker=breaker,
        executor=executor,
    )

    def run_guard() -> None:
        try:
            guard.run(lambda: "must-not-start")
        except BaseException as error:
            outcomes.append(error)
        finally:
            guard_finished.set()

    thread = threading.Thread(target=run_guard)
    try:
        executor.submit(hold_worker)
        assert worker_started.wait(timeout=2)
        executor.capture = True
        thread.start()
        assert executor.submitted.wait(timeout=2)
        future = executor.captured_future
        assert future is not None
        assert future.cancel()
        assert guard_finished.wait(timeout=2)
        assert len(outcomes) == 1 and isinstance(outcomes[0], FutureCancelledError)

        retired = breaker.released_lease
        assert retired is not None and retired.owns_half_open_slot
        replacement = breaker.acquire_attempt()
        assert replacement is not None and replacement.owns_half_open_slot
        callbacks: list[tuple[bool, int, bool]] = []
        caller_thread = threading.get_ident()

        def late_callback(completed: Future[Any]) -> None:
            try:
                breaker.record_success(retired)
            except CircuitLeaseError:
                rejected = True
            else:
                rejected = False
            callbacks.append((completed.cancelled(), threading.get_ident(), rejected))

        future.add_done_callback(late_callback)
        assert callbacks == [(True, caller_thread, True)]
        assert breaker.acquire_attempt() is None
        breaker.record_success(replacement)
        next_probe = breaker.acquire_attempt()
        assert next_probe is not None
        breaker._release_cancelled_lease(next_probe)
    finally:
        release_worker.set()
        if thread.ident is not None:
            thread.join(timeout=5)
        guard.close()
        executor.shutdown(wait=True, cancel_futures=True)
    assert not thread.is_alive()


def test_guard_late_shared_future_callback_keeps_new_half_open_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common.async_tools import _SharedExecutor

    breaker, now = _half_open_recording_breaker(monkeypatch)
    owner = _SharedExecutor(max_workers=1, max_queued=2)
    submitted: list[Future[Any]] = []
    original_submit = owner.submit

    def capture_submit(*args: Any, **kwargs: Any) -> Future[Any]:
        future = original_submit(*args, **kwargs)
        submitted.append(future)
        return future

    monkeypatch.setattr(owner, "submit", capture_submit)
    guard = BlockingDependencyGuard(
        dependency_name="runtime-late-shared-future",
        timeout_seconds=2.0,
        breaker=breaker,
        executor=owner,
    )
    entered = threading.Event()
    release = threading.Event()

    def producer() -> str:
        entered.set()
        if not release.wait(timeout=8):
            raise RuntimeError("late producer test watchdog expired")
        return "late-result"

    try:
        with ThreadPoolExecutor(max_workers=1) as caller:
            guarded = caller.submit(guard.run, producer)
            assert entered.wait(timeout=3)
            with pytest.raises(RuntimeDependencyTimeoutError):
                guarded.result(timeout=5)
        assert breaker.is_open()
        assert len(submitted) == 1
        now[0] += breaker.config.timeout_seconds + 1.0
        replacement = breaker.acquire_attempt()
        assert replacement is not None and replacement.owns_half_open_slot
        assert breaker.acquire_attempt() is None

        release.set()
        owner_future = submitted[0]
        assert owner_future.result(timeout=3) == "late-result"
        observed: list[tuple[str, int]] = []

        def late_callback(done: Future[Any]) -> None:
            observed.append((done.result(), breaker.get_stats()["half_open_calls"]))

        # The test installs this observer after actual producer completion.
        owner_future.add_done_callback(late_callback)
        assert observed == [("late-result", 1)]
        assert breaker.is_half_open()
        assert breaker.acquire_attempt() is None
        breaker.record_success(replacement)
    finally:
        release.set()
        guard.close()
        owner.shutdown(wait=True, cancel_futures=True)


def test_nested_guarded_operation_keeps_one_worker_and_context() -> None:
    guard = build_runtime_control_store_guard()
    caller = threading.get_ident()
    try:
        outer, nested = guard.run(lambda: (threading.get_ident(), guard.run(threading.get_ident)))
        assert outer == nested
        assert outer != caller
    finally:
        guard.close()


def test_nested_guarded_operation_retains_outer_deadline() -> None:
    guard = build_runtime_control_store_guard()
    guard._timeout_seconds = 0.1
    entered = threading.Event()
    release = threading.Event()

    def _blocked() -> None:
        entered.set()
        release.wait(timeout=5)

    try:
        with pytest.raises(RuntimeDependencyTimeoutError):
            guard.run(lambda: guard.run(_blocked))
        assert entered.is_set()
    finally:
        release.set()
        guard.close()


def test_other_threads_cannot_inherit_inline_guard_execution() -> None:
    guard = build_runtime_control_store_guard()
    try:

        def _outer() -> tuple[int, int]:
            with ThreadPoolExecutor(max_workers=1) as other:

                def _other() -> tuple[int, int]:
                    return threading.get_ident(), guard.run(threading.get_ident)

                return other.submit(_other).result(timeout=5)

        submitting_thread, guarded_thread = guard.run(_outer)
        assert submitting_thread != guarded_thread
    finally:
        guard.close()


@pytest.mark.parametrize("caught", [False, True])
def test_nested_dependency_failure_counts_once_even_when_recovered(caught: bool) -> None:
    guard = build_runtime_control_store_guard()
    outcomes: list[str] = []
    success = guard._breaker.record_success
    failure = guard._breaker.record_failure

    def _success(*args, **kwargs) -> None:
        outcomes.append("success")
        success(*args, **kwargs)

    def _failure(*args, **kwargs) -> None:
        outcomes.append("failure")
        failure(*args, **kwargs)

    guard._breaker.record_success = _success
    guard._breaker.record_failure = _failure

    def _unavailable() -> None:
        raise sqlite3.OperationalError("actual nested store failure")

    def _operation() -> None:
        if caught:
            with pytest.raises(RuntimeDependencyUnavailableError) as error:
                guard.run(_unavailable)
            assert isinstance(error.value.__cause__, sqlite3.OperationalError)
        else:
            guard.run(_unavailable)

    try:
        if caught:
            guard.run(_operation)
        else:
            with pytest.raises(RuntimeDependencyUnavailableError):
                guard.run(_operation)
        assert outcomes == ["failure"]
    finally:
        guard.close()


def test_guarded_store_ambient_enforcement_retains_runtime_guard(tmp_path) -> None:
    from polisyos.core.artifacts.backends.config import (
        with_ambient_ownership_enforcement_if_supported,
    )
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.resilience import GuardedDependencyProxy, guard_runtime_cas

    raw_store = FileSystemCAS(tmp_path / "guarded-cas")
    guarded_store = guard_runtime_cas(raw_store)
    active_store = with_ambient_ownership_enforcement_if_supported(guarded_store)

    assert isinstance(active_store, GuardedDependencyProxy)
    assert active_store is not guarded_store
    assert active_store._guard is guarded_store._guard
    with tenant_scope(None, tenant_id="tenant-a"):
        artifact_ref = active_store.put_bytes(
            b"tenant-a guard-bound artifact",
            PutOptions(kind="test.guard_bound_custody", media_type="text/plain"),
        )
        assert active_store.get_bytes(artifact_ref) == b"tenant-a guard-bound artifact"
    with tenant_scope(None, tenant_id="tenant-b"):
        with pytest.raises(ArtifactOwnershipError):
            active_store.get_bytes(artifact_ref)
        assert raw_store.get_bytes(artifact_ref) == b"tenant-a guard-bound artifact"

    ambient_store = FileSystemCAS(tmp_path / "idempotent-cas").with_ambient_ownership_enforcement()
    ambient_guard = guard_runtime_cas(ambient_store)
    assert with_ambient_ownership_enforcement_if_supported(ambient_guard) is ambient_guard
