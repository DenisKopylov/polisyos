"""Pool admission races that must retire owned resources and permits exactly once."""

from __future__ import annotations

import asyncio
import errno
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.fabric.connectors.pool import ConnectionPool, PoolClosedError, PoolConfig

_WAIT_SECONDS = 5.0


async def _wait_for_event(event: asyncio.Event) -> None:
    """Wait for a gated transition with a bounded timeout."""
    await asyncio.wait_for(event.wait(), _WAIT_SECONDS)


async def _wait_for_condition(predicate: Callable[[], bool]) -> None:
    """Yield until a state transition occurs, with a bounded timeout."""

    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), _WAIT_SECONDS)


class _GatedFDConnector:
    """Connector that owns a real file descriptor until disconnect completes."""

    connector_id = "pool-admission-close-race"

    def __init__(self) -> None:
        self.connect_started = asyncio.Event()
        self.allow_connect = asyncio.Event()
        self.disconnect_started = asyncio.Event()
        self.allow_disconnect = asyncio.Event()
        self.fd_closed = asyncio.Event()
        self.fd: int | None = None
        self.handle: ConnectionHandle | None = None
        self.disconnects = 0

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        self.connect_started.set()
        await _wait_for_event(self.allow_connect)
        self.fd = os.open(config.url, os.O_RDONLY)
        self.handle = ConnectionHandle(connector_id=self.connector_id, config=config)
        return self.handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        assert handle is self.handle and self.fd is not None
        self.disconnects += 1
        self.disconnect_started.set()
        await _wait_for_event(self.allow_disconnect)
        os.close(self.fd)
        self.fd_closed.set()


@pytest.mark.asyncio
async def test_close_all_during_connect_waits_for_physical_fd_retirement(tmp_path: Path) -> None:
    """Close racing with connect rejects publication and retains capacity through FD close."""
    resource = tmp_path / "owned-pool-resource"
    contents = b"ownedpoolresource"
    resource.write_bytes(contents)

    connector = _GatedFDConnector()
    pool = ConnectionPool(
        lambda: connector,
        ConnectionConfig(url=str(resource)),
        PoolConfig(max_size=1, validate_on_acquire=False, acquire_timeout_seconds=10.0),
    )
    pool._semaphore = asyncio.BoundedSemaphore(1)
    acquire: asyncio.Task[ConnectionHandle] | None = None
    close: asyncio.Task[None] | None = None

    try:
        acquire = asyncio.create_task(pool.acquire())
        await _wait_for_event(connector.connect_started)
        assert pool._active_acquires == 1
        assert pool._semaphore._value == 0
        generation = pool._generation

        close = asyncio.create_task(pool.close_all())
        await _wait_for_condition(lambda: pool.is_closed)
        assert pool._generation == generation + 1
        assert not close.done()

        connector.allow_connect.set()
        await _wait_for_event(connector.disconnect_started)
        assert connector.fd is not None
        assert os.fstat(connector.fd).st_size == len(contents)
        os.lseek(connector.fd, 0, os.SEEK_SET)
        assert os.read(connector.fd, len(contents)) == contents
        assert not acquire.done() and not close.done()
        assert pool._active_acquires == 1
        assert len(pool._pending_cleanup) == 1
        assert next(iter(pool._pending_cleanup.values())).handle is connector.handle
        assert pool._semaphore._value == 0

        connector.allow_disconnect.set()
        await _wait_for_event(connector.fd_closed)
        with pytest.raises(PoolClosedError):
            await asyncio.wait_for(acquire, _WAIT_SECONDS)
        await asyncio.wait_for(close, _WAIT_SECONDS)

        assert connector.fd is not None
        with pytest.raises(OSError) as closed_fd:
            os.fstat(connector.fd)
        assert closed_fd.value.errno == errno.EBADF
        stats = pool.get_stats()
        assert connector.disconnects == 1
        assert stats.total_connections == stats.idle_connections == stats.in_use_connections == 0
        assert pool._active_acquires == 0
        assert pool._active_acquires_done.is_set()
        assert not pool._in_use and not pool._idle and not pool._pending_cleanup
        with pool._handle_owners_lock:
            assert all(record.connector is not connector for record in pool._handle_owners.values())
        assert pool._semaphore._value == 1
        with pytest.raises(PoolClosedError):
            await asyncio.wait_for(pool.acquire(), _WAIT_SECONDS)
        assert pool._semaphore._value == 1
    finally:
        connector.allow_connect.set()
        connector.allow_disconnect.set()
        if close is None:
            close = asyncio.create_task(pool.close_all())
        tasks = [task for task in (acquire, close) if task is not None]
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), _WAIT_SECONDS)
        if connector.fd is not None and not connector.fd_closed.is_set():
            try:
                os.fstat(connector.fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise
            else:
                os.close(connector.fd)


class _ImmediateConnector:
    """Connector that records public connection lifecycle calls."""

    connector_id = "pool-admission-permit-race"

    def __init__(self) -> None:
        self.connects = 0
        self.disconnects = 0

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        self.connects += 1
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnects += 1


class _LiveFileDescriptorConnector:
    """Connector that exposes physical resource ownership for sibling-pool assertions."""

    connector_id = "pool-admission-sibling-live-fd"

    def __init__(self) -> None:
        self.connects = 0
        self.disconnects = 0
        self.fd: int | None = None
        self.fd_closed = asyncio.Event()

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        self.connects += 1
        self.fd = os.open(config.url, os.O_RDONLY)
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        assert self.fd is not None
        self.disconnects += 1
        os.close(self.fd)
        self.fd_closed.set()


@pytest.mark.asyncio
async def test_cancel_after_permit_before_registration_restores_slot_once(tmp_path: Path) -> None:
    """Cancellation in the permit-to-registration window restores one usable slot."""
    connector = _ImmediateConnector()
    pool = ConnectionPool(
        lambda: connector,
        ConnectionConfig(url="synthetic://post-permit-lock"),
        PoolConfig(max_size=1, validate_on_acquire=False, acquire_timeout_seconds=10.0),
    )
    permit_and_lock_held = asyncio.Event()

    class _HandoffSemaphore(asyncio.BoundedSemaphore):
        gated = True
        lock_held = False

        async def acquire(self) -> bool:
            acquired = await super().acquire()
            if self.gated:
                # Hold the registration lock after acquiring a real permit.
                await pool._lock.acquire()
                self.lock_held = True
                permit_and_lock_held.set()
            return acquired

    semaphore = _HandoffSemaphore(1)
    pool._semaphore = semaphore
    sibling_resource = tmp_path / "sibling-live-resource"
    sibling_contents = b"siblingpoolresource"
    sibling_resource.write_bytes(sibling_contents)
    sibling_connector = _LiveFileDescriptorConnector()
    sibling_pool = ConnectionPool(
        lambda: sibling_connector,
        ConnectionConfig(url=str(sibling_resource)),
        PoolConfig(max_size=1, validate_on_acquire=False, acquire_timeout_seconds=10.0),
    )
    sibling_handle: ConnectionHandle | None = None
    sibling_fd: int | None = None
    owner: asyncio.Task[ConnectionHandle] | None = None

    try:
        sibling_handle = await asyncio.wait_for(sibling_pool.acquire(), _WAIT_SECONDS)
        assert sibling_handle is not None
        assert sibling_connector.fd is not None
        sibling_fd = sibling_connector.fd
        sibling_owner_key = id(sibling_handle)
        with sibling_pool._handle_owners_lock:
            sibling_owner = sibling_pool._handle_owners[sibling_owner_key]
        with pool._handle_owners_lock:
            if pool._handle_owners is not sibling_pool._handle_owners:
                assert sibling_owner_key not in pool._handle_owners
                # Keep a real sibling-pool owner in this registry as a foreign-owner control.
                pool._handle_owners[sibling_owner_key] = sibling_owner
            assert pool._handle_owners.get(sibling_owner_key) is sibling_owner
            assert all(record.connector is not connector for record in pool._handle_owners.values())

        owner = asyncio.create_task(pool.acquire())
        await _wait_for_event(permit_and_lock_held)
        assert semaphore._value == 0
        assert pool._lock.locked() and not owner.done()
        assert pool._active_acquires == 0
        assert connector.connects == connector.disconnects == 0
        assert not pool._in_use and not pool._idle and not pool._pending_cleanup
        with pool._handle_owners_lock:
            assert all(record.connector is not connector for record in pool._handle_owners.values())
            assert pool._handle_owners.get(sibling_owner_key) is sibling_owner

        owner.cancel()
        # Deliver cancellation while the registration lock remains held.
        await asyncio.sleep(0)
        assert not owner.done()
        assert semaphore._value == 0

        semaphore.gated = False
        semaphore.lock_held = False
        pool._lock.release()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(owner, _WAIT_SECONDS)

        assert semaphore._value == 1
        assert pool._active_acquires == 0
        assert pool._active_acquires_done.is_set()
        assert connector.connects == connector.disconnects == 0
        assert not pool._in_use and not pool._idle and not pool._pending_cleanup
        with pool._handle_owners_lock:
            assert all(record.connector is not connector for record in pool._handle_owners.values())
            assert pool._handle_owners.get(sibling_owner_key) is sibling_owner

        handle = await asyncio.wait_for(pool.acquire(), _WAIT_SECONDS)
        assert semaphore._value == 0
        assert connector.connects == 1
        await asyncio.wait_for(pool.release(handle), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)
        assert semaphore._value == 1
        assert connector.connects == connector.disconnects == 1
        with pool._handle_owners_lock:
            assert all(record.connector is not connector for record in pool._handle_owners.values())
            assert pool._handle_owners.get(sibling_owner_key) is sibling_owner

        assert sibling_connector.disconnects == 0
        assert sibling_fd is not None
        assert os.fstat(sibling_fd).st_size == len(sibling_contents)
        os.lseek(sibling_fd, 0, os.SEEK_SET)
        assert os.read(sibling_fd, len(sibling_contents)) == sibling_contents

        assert sibling_handle is not None
        await asyncio.wait_for(sibling_pool.release(sibling_handle), _WAIT_SECONDS)
        reacquired_sibling = await asyncio.wait_for(sibling_pool.acquire(), _WAIT_SECONDS)
        assert reacquired_sibling is sibling_handle
        assert sibling_connector.connects == 1
        assert sibling_connector.disconnects == 0
        assert os.fstat(sibling_fd).st_size == len(sibling_contents)
        os.lseek(sibling_fd, 0, os.SEEK_SET)
        assert os.read(sibling_fd, len(sibling_contents)) == sibling_contents

        if pool._handle_owners is not sibling_pool._handle_owners:
            with pool._handle_owners_lock:
                assert pool._handle_owners.get(sibling_owner_key) is sibling_owner
                pool._handle_owners.pop(sibling_owner_key)
        await asyncio.wait_for(sibling_pool.close_all(), _WAIT_SECONDS)
        assert sibling_connector.connects == sibling_connector.disconnects == 1
        assert sibling_connector.fd_closed.is_set()
        assert sibling_fd is not None
        with pytest.raises(OSError) as closed_sibling_fd:
            os.fstat(sibling_fd)
        assert closed_sibling_fd.value.errno == errno.EBADF
        with pool._handle_owners_lock:
            assert all(
                record.connector is not sibling_connector for record in pool._handle_owners.values()
            )
    finally:
        semaphore.gated = False
        if semaphore.lock_held:
            semaphore.lock_held = False
            pool._lock.release()
        if owner is not None and not owner.done():
            owner.cancel()
        if owner is not None:
            await asyncio.wait_for(asyncio.gather(owner, return_exceptions=True), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)
        await asyncio.wait_for(sibling_pool.close_all(), _WAIT_SECONDS)
        if sibling_handle is not None:
            with pool._handle_owners_lock:
                sibling_owner_key = id(sibling_handle)
                sibling_owner = pool._handle_owners.get(sibling_owner_key)
                if sibling_owner is not None and sibling_owner.connector is sibling_connector:
                    pool._handle_owners.pop(sibling_owner_key, None)
        if sibling_fd is not None and not sibling_connector.fd_closed.is_set():
            try:
                os.fstat(sibling_fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise
            else:
                os.close(sibling_fd)
