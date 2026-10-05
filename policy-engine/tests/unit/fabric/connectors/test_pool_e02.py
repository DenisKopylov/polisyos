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

    def __init__(self, *, gate: str | None = None, disconnect_failures: int = 0) -> None:
        self.gate = gate
        self.started = asyncio.Event()
        self.proceed = asyncio.Event()
        self.disconnected: list[str] = []
        self.disconnect_failures = disconnect_failures

    async def _wait(self, operation: str) -> None:
        if self.gate == operation:
            self.started.set()
            await self.proceed.wait()

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        await self._wait("connect")
        return ConnectionHandle(connector_id="e02-gated", config=config)

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        await self._wait("health")
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
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
