"""E02 behavioral discriminators for pool deadlines and physical ownership."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.fabric.connectors.pool import (
    ConnectionPool,
    PoolClosedError,
    PoolConfig,
    PoolExhaustedError,
)


class _GatedConnector:
    """A physical connector boundary whose I/O is controlled by events."""

    def __init__(
        self,
        *,
        gate: str | None = None,
        disconnect_failures: int = 0,
        suppress_cancellation: bool = False,
    ) -> None:
        self.gate = gate
        self.started = asyncio.Event()
        self.proceed = asyncio.Event()
        self.disconnect_started = asyncio.Event()
        self.disconnected: list[str] = []
        self.disconnect_failures = disconnect_failures
        self.suppress_cancellation = suppress_cancellation
        self.cancellation_observed = asyncio.Event()
        self.created: list[str] = []

    async def _wait(self, operation: str) -> None:
        if self.gate == operation:
            self.started.set()
            try:
                await self.proceed.wait()
            except asyncio.CancelledError:
                self.cancellation_observed.set()
                if not self.suppress_cancellation:
                    raise
                await self.proceed.wait()

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        await self._wait("connect")
        handle = ConnectionHandle(connector_id="e02-gated", config=config)
        self.created.append(handle.session_id)
        return handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        await self._wait("health")
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnect_started.set()
        self.disconnected.append(handle.session_id)
        if self.disconnect_failures:
            self.disconnect_failures -= 1
            raise OSError("injected first disconnect failure")
        await self._wait("disconnect")


def _pool(factory: Any, **overrides: Any) -> ConnectionPool:
    options = {
        "max_size": 1,
        "acquire_timeout_seconds": 0.03,
        "connection_timeout_seconds": 0.5,
        "validate_on_acquire": False,
    }
    options.update(overrides)
    return ConnectionPool(
        connector_factory=factory,
        config=ConnectionConfig(url="https://e02.invalid"),
        pool_config=PoolConfig(**options),
        pool_id="e02-discriminator",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["connect", "health"])
async def test_acquire_deadline_covers_network_work(operation: str) -> None:
    """A ready semaphore is insufficient when the physical acquire still blocks."""
    connector = _GatedConnector(gate=operation)
    pool = _pool(lambda: connector, validate_on_acquire=operation == "health")
    task = asyncio.create_task(pool.acquire())
    await asyncio.wait_for(connector.started.wait(), timeout=0.5)
    try:
        with pytest.raises(PoolExhaustedError):
            await asyncio.wait_for(asyncio.shield(task), timeout=0.15)
    finally:
        connector.proceed.set()
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError, PoolExhaustedError, TimeoutError):
            await task
        await pool.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["connect", "health"])
@pytest.mark.parametrize("suppress_cancellation", [False, True])
async def test_expired_acquire_cannot_publish_connector_returned_after_cancellation(
    operation: str,
    suppress_cancellation: bool,
) -> None:
    """A returned handle is usable only while the absolute acquire budget remains."""
    connector = _GatedConnector(gate=operation, suppress_cancellation=suppress_cancellation)
    pool = _pool(lambda: connector, validate_on_acquire=operation == "health")
    acquire = asyncio.create_task(pool.acquire())
    try:
        await asyncio.wait_for(connector.started.wait(), timeout=0.5)
        await asyncio.wait_for(connector.cancellation_observed.wait(), timeout=0.5)
        connector.proceed.set()
        with pytest.raises(PoolExhaustedError):
            await asyncio.wait_for(asyncio.shield(acquire), timeout=0.5)
        assert not pool._in_use and not pool._pending_cleanup
        assert pool._active_acquires == 0
        assert pool._semaphore._value == 1
        assert connector.disconnected == connector.created
    finally:
        connector.proceed.set()
        if not acquire.done():
            acquire.cancel()
        await asyncio.gather(acquire, return_exceptions=True)
        await pool.close_all()


@pytest.mark.asyncio
async def test_successful_acquire_does_not_await_metadata_after_publication() -> None:
    """Successful commit gives the caller its handle before another lock owner can wait."""
    connector = _GatedConnector(gate="health")
    pool = _pool(lambda: connector, validate_on_acquire=True, acquire_timeout_seconds=0.5)
    acquire = asyncio.create_task(pool.acquire())
    holder_started = asyncio.Event()
    holder_release = asyncio.Event()
    holder: asyncio.Task[None] | None = None

    async def next_metadata_owner() -> None:
        async with pool._lock:
            holder_started.set()
            await holder_release.wait()

    try:
        await asyncio.wait_for(connector.started.wait(), timeout=0.5)
        await pool._lock.acquire()
        connector.proceed.set()
        # Observe publication queued on the real lock before adding its next owner.
        async with asyncio.timeout(0.5):
            while not pool._lock._waiters:
                await asyncio.sleep(0)
        holder = asyncio.create_task(next_metadata_owner())
        async with asyncio.timeout(0.5):
            while len(pool._lock._waiters) < 2:
                await asyncio.sleep(0)
        pool._lock.release()
        await asyncio.wait_for(holder_started.wait(), timeout=0.5)
        assert acquire.done(), "published acquisition waited behind the next metadata owner"
        handle = acquire.result()
        assert pool._active_acquires == 0
        assert list(pool._in_use) == [handle.session_id]
    finally:
        holder_release.set()
        if holder is not None:
            await holder
        if pool._lock.locked():
            pool._lock.release()
        connector.proceed.set()
        await asyncio.gather(acquire, return_exceptions=True)
        await pool.close_all()


@pytest.mark.asyncio
async def test_expired_handle_cleanup_failure_retains_one_permit_until_retry() -> None:
    """A late handle never escapes, even when its physical disconnect first fails."""
    connector = _GatedConnector(gate="connect", suppress_cancellation=True, disconnect_failures=2)
    pool = _pool(lambda: connector)
    acquire = asyncio.create_task(pool.acquire())
    try:
        await asyncio.wait_for(connector.cancellation_observed.wait(), timeout=0.5)
        connector.proceed.set()
        with pytest.raises(PoolExhaustedError):
            await acquire
        assert not pool._in_use
        assert list(pool._pending_cleanup) == connector.created
        assert pool._active_acquires == 0
        assert pool._semaphore._value == 0
        with pytest.raises(RuntimeError, match="cleanup remains pending"):
            await pool.close_all()
        assert list(pool._pending_cleanup) == connector.created
        assert pool._semaphore._value == 0
    finally:
        connector.proceed.set()
        connector.disconnect_failures = 0
        await asyncio.gather(acquire, return_exceptions=True)
        await pool.close_all()
    assert connector.disconnected == connector.created * 3
    assert pool._semaphore._value == 1
    assert pool.get_stats().total_closes == 1


@pytest.mark.asyncio
async def test_shorter_connection_timeout_preserves_primary_error() -> None:
    connector = _GatedConnector(gate="connect")
    pool = _pool(lambda: connector, acquire_timeout_seconds=0.5, connection_timeout_seconds=0.03)
    try:
        with pytest.raises(TimeoutError, match="Connection creation timed out after 0.03s"):
            await pool.acquire()
        assert pool._active_acquires == 0
        assert pool._semaphore._value == 1
        assert not connector.created
    finally:
        await pool.close_all()


@pytest.mark.asyncio
async def test_connector_failure_after_deadline_preserves_primary_error() -> None:
    primary = ValueError("actual provider failure after suppressed cancellation")

    class FailingConnector(_GatedConnector):
        async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
            await self._wait("connect")
            raise primary

    connector = FailingConnector(gate="connect", suppress_cancellation=True)
    pool = _pool(lambda: connector)
    acquire = asyncio.create_task(pool.acquire())
    try:
        await asyncio.wait_for(connector.cancellation_observed.wait(), timeout=0.5)
        connector.proceed.set()
        with pytest.raises(ValueError) as caught:
            await acquire
        assert caught.value is primary
        assert pool._active_acquires == 0
        assert pool._semaphore._value == 1
        assert not pool._in_use and not pool._pending_cleanup
    finally:
        connector.proceed.set()
        await asyncio.gather(acquire, return_exceptions=True)
        await pool.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["connect", "health"])
async def test_blocked_network_work_allows_independent_release(operation: str) -> None:
    """The actual metadata lock must remain available during connector I/O."""
    fast = _GatedConnector()
    slow = _GatedConnector(gate=operation)
    connectors = iter([fast, slow])
    pool = _pool(
        lambda: next(connectors),
        max_size=2,
        acquire_timeout_seconds=0.5,
        validate_on_acquire=operation == "health",
    )
    first = await pool.acquire()
    task = asyncio.create_task(pool.acquire())
    await asyncio.wait_for(slow.started.wait(), timeout=0.5)
    try:
        await asyncio.wait_for(pool.release(first), timeout=0.15)
        replacement = await asyncio.wait_for(pool.acquire(), timeout=0.15)
        assert replacement.session_id == first.session_id
        await pool.release(replacement)
    finally:
        slow.proceed.set()
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await pool.close_all()


@pytest.mark.asyncio
async def test_failed_disconnect_retry_and_close_share_one_physical_owner() -> None:
    """The P40 falsifier keeps the first owner until its teardown is confirmed."""
    connector = _GatedConnector(gate="disconnect", disconnect_failures=1)
    pool = _pool(lambda: connector, max_connection_uses=1)
    handle = await pool.acquire()
    with pytest.raises(RuntimeError, match="cleanup is pending"):
        await pool.release(handle)
    with pytest.raises(PoolExhaustedError):
        await pool.acquire()

    first_retry = asyncio.create_task(pool.release(handle))
    await asyncio.wait_for(connector.started.wait(), timeout=0.5)
    second_retry = asyncio.create_task(pool.release(handle))
    close = asyncio.create_task(pool.close_all())
    await asyncio.sleep(0)
    try:
        assert not close.done()
        with pytest.raises(PoolClosedError):
            await pool.acquire()
        assert set(connector.disconnected) == {handle.session_id}
        assert pool._semaphore._value == 0
    finally:
        connector.proceed.set()
        await asyncio.gather(first_retry, second_retry, close)

    assert connector.disconnected == [handle.session_id, handle.session_id]
    assert pool._semaphore._value == 1
    assert pool.get_stats().total_closes == 1


@pytest.mark.asyncio
async def test_cancelled_semaphore_waiter_cannot_hide_connect_from_close() -> None:
    """An unadmitted waiter cannot retire another acquire's physical ownership."""
    connector = _GatedConnector(gate="connect")
    pool = _pool(lambda: connector, acquire_timeout_seconds=0.5)
    physical_acquire = asyncio.create_task(pool.acquire())
    await asyncio.wait_for(connector.started.wait(), timeout=0.5)
    queued = asyncio.create_task(pool.acquire())
    await asyncio.sleep(0)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued

    close = asyncio.create_task(pool.close_all())
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(close), timeout=0.03)
    finally:
        connector.proceed.set()
        with pytest.raises(PoolClosedError):
            await physical_acquire
        await close

    assert len(connector.disconnected) == 1
    assert pool._semaphore._value == 1


@pytest.mark.asyncio
async def test_semaphore_wait_cannot_restart_absolute_network_deadline() -> None:
    """A slow admission consumes the same time budget used by later connector work."""
    fast = _GatedConnector()
    slow = _GatedConnector(gate="connect")
    connectors = iter([fast, slow])
    pool = _pool(
        lambda: next(connectors),
        acquire_timeout_seconds=0.1,
        max_connection_uses=1,
    )
    first = await pool.acquire()
    waiter = asyncio.create_task(pool.acquire())
    loop = asyncio.get_running_loop()
    release_tasks: list[asyncio.Task[None]] = []
    release_timer = loop.call_later(
        0.06, lambda: release_tasks.append(asyncio.create_task(pool.release(first)))
    )
    try:
        await asyncio.wait_for(slow.started.wait(), timeout=0.5)
        with pytest.raises(PoolExhaustedError):
            await asyncio.wait_for(asyncio.shield(waiter), timeout=0.07)
    finally:
        release_timer.cancel()
        slow.proceed.set()
        if not waiter.done():
            waiter.cancel()
        with suppress(asyncio.CancelledError, PoolExhaustedError):
            await waiter
        await asyncio.gather(*release_tasks)
        await pool.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_during_cleanup", [False, True])
async def test_expired_acquire_retains_physical_owner_until_cleanup_settles(
    cancel_during_cleanup: bool,
) -> None:
    """Neither expiry nor repeated cancellation frees an undischarged physical slot."""
    connector = _GatedConnector(gate="health")
    pool = _pool(lambda: connector, validate_on_acquire=True)
    acquire = asyncio.create_task(pool.acquire())
    await asyncio.wait_for(connector.started.wait(), timeout=0.5)
    connector.gate = "disconnect"
    await asyncio.wait_for(connector.disconnect_started.wait(), timeout=0.5)
    try:
        assert not acquire.done()
        with pytest.raises(PoolExhaustedError):
            await pool.acquire()
        if cancel_during_cleanup:
            acquire.cancel()
        close = asyncio.create_task(pool.close_all())
        await asyncio.sleep(0)
        assert not close.done()
        assert pool._semaphore._value == 0
    finally:
        connector.proceed.set()
        expected = asyncio.CancelledError if cancel_during_cleanup else PoolExhaustedError
        with pytest.raises(expected):
            await acquire
        await close

    assert len(connector.disconnected) == 1
    assert pool._semaphore._value == 1
