from __future__ import annotations

import asyncio
from typing import Any, NoReturn

import pytest

from polisyos.common.async_tools import get_shared_executor
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitAttemptLease,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitLeaseError,
)
from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
from polisyos.runtime.http.resilience import (
    AsyncDependencyGuard,
    BlockingDependencyGuard,
    build_runtime_cas_guard,
    build_runtime_control_store_guard,
)


def test_runtime_blocking_dependency_guards_reuse_shared_executor() -> None:
    cas_guard = build_runtime_cas_guard()
    control_store_guard = build_runtime_control_store_guard()

    try:
        assert cas_guard._executor is get_shared_executor()
        assert control_store_guard._executor is get_shared_executor()
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
