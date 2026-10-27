from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, NoReturn

import pytest

from polisyos.common.async_tools import get_shared_executor
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
