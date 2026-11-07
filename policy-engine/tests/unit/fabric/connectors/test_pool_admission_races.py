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
        self.health_check_started = asyncio.Event()
        self.allow_health_check = asyncio.Event()
        self.allow_health_check.set()
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
        self.health_check_started.set()
        await _wait_for_event(self.allow_health_check)
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        assert handle is self.handle and self.fd is not None
        self.disconnects += 1
        self.disconnect_started.set()
        await _wait_for_event(self.allow_disconnect)
        os.close(self.fd)
        self.fd_closed.set()


@pytest.mark.asyncio
async def test_caller_cancellation_keeps_active_physical_cleanup_shielded(tmp_path: Path) -> None:
    """Caller cancellation settles only after the owned descriptor is physically closed."""
    resource = tmp_path / "cancelled-release-resource"
    contents = b"active-cleanup-owned-resource"
    resource.write_bytes(contents)
    connector = _GatedFDConnector()
    connector.allow_connect.set()
    pool = ConnectionPool(
        lambda: connector,
        ConnectionConfig(url=str(resource)),
        PoolConfig(max_size=1, max_connection_uses=1),
    )
    pool._semaphore = asyncio.BoundedSemaphore(1)
    handle = await pool.acquire()
    release = asyncio.create_task(pool.release(handle))
    try:
        await _wait_for_event(connector.disconnect_started)
        owner = next(iter(pool._pending_cleanup.values()))
        cleanup = owner.cleanup_task
        assert cleanup is not None and not cleanup.done()
        for _ in range(2):
            release.cancel()
            await asyncio.sleep(0)
            assert not release.done() and not cleanup.done()
            assert not cleanup.cancelling()
            assert connector.fd is not None
            assert os.pread(connector.fd, len(contents), 0) == contents
            assert pool._semaphore._value == 0 and owner.pending_permit
        connector.allow_disconnect.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(release, _WAIT_SECONDS)
        assert connector.disconnects == 1 and connector.fd_closed.is_set()
        assert connector.fd is not None
        with pytest.raises(OSError) as caught:
            os.fstat(connector.fd)
        assert caught.value.errno == errno.EBADF
        assert not pool._pending_cleanup and pool._semaphore._value == 1
    finally:
        connector.allow_disconnect.set()
        await asyncio.wait_for(asyncio.gather(release, return_exceptions=True), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)


@pytest.mark.asyncio
async def test_cancelled_mismatched_acquire_settles_closed_owner_before_replacement(
    tmp_path: Path,
) -> None:
    """Acquire failure cannot retain a closed owner or lose its physical reservation."""

    class MismatchedConnector(_GatedFDConnector):
        mismatch = True

        async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
            handle = await super().connect(config)
            if self.mismatch:
                object.__setattr__(handle, "connector_id", "foreign-owner")
            return handle

    resource = tmp_path / "mismatched-acquire-resource"
    resource.write_bytes(b"mismatched-owner")
    connector = MismatchedConnector()
    connector.allow_connect.set()
    pool = ConnectionPool(
        lambda: connector, ConnectionConfig(url=str(resource)), PoolConfig(max_size=1)
    )
    pool._semaphore = asyncio.BoundedSemaphore(1)
    acquire = asyncio.create_task(pool.acquire())
    try:
        await _wait_for_event(connector.disconnect_started)
        assert connector.fd is not None
        old_fd = connector.fd
        acquire.cancel()
        await asyncio.sleep(0)
        assert os.pread(old_fd, 16, 0) == b"mismatched-owner"
        assert pool._semaphore._value == 0
        connector.allow_disconnect.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(acquire, _WAIT_SECONDS)
        with pytest.raises(OSError) as caught:
            os.fstat(old_fd)
        assert caught.value.errno == errno.EBADF
        assert pool._pending_cleanup == {} and pool._handle_owners == {}
        assert pool._semaphore._value == 1 and pool._active_acquires == 0
        connector.mismatch = False
        replacement = await pool.acquire()
        assert replacement.connector_id == connector.connector_id
        await pool.release(replacement)
        await pool.close_all()
        assert pool._semaphore._value == 1 and connector.disconnects == 2
    finally:
        connector.allow_disconnect.set()
        await asyncio.wait_for(asyncio.gather(acquire, return_exceptions=True), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)


@pytest.mark.asyncio
async def test_release_preserves_claimed_permit_when_post_close_logging_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-claim diagnostic failure preserves the original error and returns capacity."""
    from polisyos.fabric.connectors import pool as pool_module

    resource = tmp_path / "post-claim-log-resource"
    resource.write_bytes(b"post-claim-log")
    connector = _GatedFDConnector()
    connector.allow_connect.set()
    connector.allow_disconnect.set()
    pool = ConnectionPool(
        lambda: connector,
        ConnectionConfig(url=str(resource)),
        PoolConfig(max_size=1),
    )
    pool._semaphore = asyncio.BoundedSemaphore(1)
    handle = await pool.acquire()
    assert connector.fd is not None
    fd = connector.fd
    object.__setattr__(handle, "connector_id", "changed-owner")
    primary = RuntimeError("controlled post-claim logger failure")

    def fail_warning(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise primary

    monkeypatch.setattr(pool_module.logger, "warning", fail_warning)
    try:
        with pytest.raises(RuntimeError, match="controlled post-claim logger failure") as caught:
            await pool.release(handle)
        assert caught.value is primary
        with pytest.raises(OSError) as closed:
            os.fstat(fd)
        assert closed.value.errno == errno.EBADF
        assert pool._semaphore._value == 1 and pool._pending_cleanup == {}
        assert connector.disconnects == 1
    finally:
        await pool.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("gate_after_cleanup", [False, True], ids=["settlement", "permit-claim"])
async def test_cancelled_close_retains_atomic_physical_owner_and_permit_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate_after_cleanup: bool,
) -> None:
    """Cancellation at either retirement boundary leaves a settled or retryable owner."""
    resource = tmp_path / "close-settlement-resource"
    resource.write_bytes(b"close-settlement")
    connector = _GatedFDConnector()
    connector.allow_connect.set()
    connector.allow_disconnect.set()
    pool = ConnectionPool(
        lambda: connector, ConnectionConfig(url=str(resource)), PoolConfig(max_size=1)
    )
    pool._semaphore = asyncio.BoundedSemaphore(1)
    await pool.acquire()
    assert connector.fd is not None
    fd = connector.fd
    gated = asyncio.Event()
    original_cleanup = pool._cleanup_pooled
    original_close = pool._close_connection

    async def cleanup_then_hold(pooled):
        cleaned = await original_cleanup(pooled)
        await pool._lock.acquire()
        gated.set()
        return cleaned

    async def close_then_hold(pooled):
        cleaned = await original_close(pooled)
        await pool._lock.acquire()
        gated.set()
        return cleaned

    monkeypatch.setattr(
        pool,
        "_cleanup_pooled" if gate_after_cleanup else "_close_connection",
        cleanup_then_hold if gate_after_cleanup else close_then_hold,
    )
    close = asyncio.create_task(pool.close_all())
    try:
        await _wait_for_event(gated)
        await _wait_for_condition(lambda: bool(pool._lock._waiters))
        close.cancel()
        await asyncio.sleep(0)
        pool._lock.release()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(close, _WAIT_SECONDS)
        with pytest.raises(OSError) as caught:
            os.fstat(fd)
        assert caught.value.errno == errno.EBADF
        if pool._semaphore._value == 0:
            assert len(pool._pending_cleanup) == 1
            owner = next(iter(pool._pending_cleanup.values()))
            assert owner.closed and owner.pending_permit and owner.handle is connector.handle
        monkeypatch.setattr(pool, "_cleanup_pooled", original_cleanup)
        monkeypatch.setattr(pool, "_close_connection", original_close)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)
        assert pool._pending_cleanup == {} and pool._handle_owners == {}
        assert pool._semaphore._value == 1 and connector.disconnects == 1
        await pool.close_all()
        assert pool._semaphore._value == 1 and connector.disconnects == 1
    finally:
        monkeypatch.setattr(pool, "_cleanup_pooled", original_cleanup)
        monkeypatch.setattr(pool, "_close_connection", original_close)
        if pool._lock.locked():
            pool._lock.release()
        await asyncio.wait_for(asyncio.gather(close, return_exceptions=True), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)


@pytest.mark.asyncio
@pytest.mark.parametrize("retire", [False, True], ids=["idle-publication", "physical-retirement"])
async def test_cancelled_release_finalizer_returns_published_permit_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retire: bool,
) -> None:
    """A claimed or published permit cannot disappear while the finalizer waits for metadata."""
    resource = tmp_path / "release-finalizer-resource"
    resource.write_bytes(b"release-finalizer")
    connector = _GatedFDConnector()
    connector.allow_connect.set()
    connector.allow_disconnect.set()
    pool = ConnectionPool(
        lambda: connector,
        ConnectionConfig(url=str(resource)),
        PoolConfig(
            max_size=1, max_connection_uses=1 if retire else 1000, validate_on_release=not retire
        ),
    )
    pool._semaphore = asyncio.BoundedSemaphore(1)
    handle = await pool.acquire()
    assert connector.fd is not None
    fd = connector.fd
    holder_release = asyncio.Event()
    holder_started = asyncio.Event()
    validation_started = asyncio.Event()
    validation_release = asyncio.Event()
    original_claim = pool._claim_permit

    async def claim_then_hold(pooled, owned):
        claimed = await original_claim(pooled, owned)
        await pool._lock.acquire()
        holder_started.set()
        return claimed

    async def gated_validation(_handle: ConnectionHandle) -> HealthStatus:
        validation_started.set()
        await validation_release.wait()
        return HealthStatus(healthy=True)

    async def hold_after_publication() -> None:
        async with pool._lock:
            holder_started.set()
            await holder_release.wait()

    holder: asyncio.Task[None] | None = None
    if retire:
        monkeypatch.setattr(pool, "_claim_permit", claim_then_hold)
    else:
        connector.health_check = gated_validation
        owner = next(iter(pool._in_use.values()))
        owner.last_health_check = None
    release = asyncio.create_task(pool.release(handle))
    try:
        if not retire:
            await _wait_for_event(validation_started)
            await pool._lock.acquire()
            validation_release.set()
            await _wait_for_condition(lambda: bool(pool._lock._waiters))
            holder = asyncio.create_task(hold_after_publication())
            await _wait_for_condition(lambda: len(pool._lock._waiters or ()) == 2)
            pool._lock.release()
        await _wait_for_event(holder_started)
        await _wait_for_condition(lambda: bool(pool._lock._waiters))
        release.cancel()
        await asyncio.sleep(0)
        if retire:
            pool._lock.release()
        else:
            holder_release.set()
            assert holder is not None
            await holder
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(release, _WAIT_SECONDS)
        assert pool._semaphore._value == 1 and pool._pending_cleanup == {}
        await pool.close_all()
        with pytest.raises(OSError) as caught:
            os.fstat(fd)
        assert caught.value.errno == errno.EBADF
        assert connector.disconnects == 1 and pool._semaphore._value == 1
    finally:
        monkeypatch.setattr(pool, "_claim_permit", original_claim)
        validation_release.set()
        holder_release.set()
        if retire and pool._lock.locked():
            pool._lock.release()
        if holder is not None:
            await asyncio.wait_for(holder, _WAIT_SECONDS)
        await asyncio.wait_for(asyncio.gather(release, return_exceptions=True), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)


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


@pytest.mark.asyncio
async def test_maxsize_two_starts_two_connects_before_either_unblocks(tmp_path: Path) -> None:
    """Both connections enter connector I/O before either gated connect is released."""
    resource = tmp_path / "parallel-connect-resource"
    resource.write_bytes(b"parallel-connect")
    connectors = [_GatedFDConnector(), _GatedFDConnector()]
    connector_index = iter(connectors)
    pool = ConnectionPool(
        lambda: next(connector_index),
        ConnectionConfig(url=str(resource)),
        PoolConfig(
            max_size=2,
            validate_on_acquire=False,
            acquire_timeout_seconds=10.0,
            connection_timeout_seconds=10.0,
        ),
    )
    acquires: list[asyncio.Task[ConnectionHandle]] = []

    try:
        acquires = [asyncio.create_task(pool.acquire()) for _ in connectors]
        await asyncio.wait_for(
            asyncio.gather(*(_wait_for_event(item.connect_started) for item in connectors)),
            _WAIT_SECONDS,
        )

        assert all(item.connect_started.is_set() for item in connectors)
        assert all(not task.done() for task in acquires)

        for item in connectors:
            item.allow_connect.set()
        handles = await asyncio.wait_for(asyncio.gather(*acquires), _WAIT_SECONDS)
        assert len({handle.session_id for handle in handles}) == 2
        await asyncio.wait_for(
            asyncio.gather(*(pool.release(handle) for handle in handles)),
            _WAIT_SECONDS,
        )
        for item in connectors:
            item.allow_disconnect.set()
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)
        assert all(item.fd_closed.is_set() for item in connectors)
    finally:
        for item in connectors:
            item.allow_connect.set()
            item.allow_health_check.set()
            item.allow_disconnect.set()
        if acquires:
            await asyncio.wait_for(asyncio.gather(*acquires, return_exceptions=True), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)


@pytest.mark.asyncio
async def test_independent_release_completes_while_connect_and_health_io_are_gated(
    tmp_path: Path,
) -> None:
    """Release progresses during separate gated connect and health-check operations."""
    resource = tmp_path / "gated-network-resource"
    resource.write_bytes(b"gated-network")
    idle_connector = _GatedFDConnector()
    connecting_connector = _GatedFDConnector()
    idle_connector.allow_connect.set()
    connector_queue = iter((idle_connector, connecting_connector))
    pool = ConnectionPool(
        lambda: next(connector_queue),
        ConnectionConfig(url=str(resource)),
        PoolConfig(
            max_size=2,
            acquire_timeout_seconds=10.0,
            connection_timeout_seconds=10.0,
            health_check_interval_seconds=0.0,
        ),
    )
    connecting_acquire: asyncio.Task[ConnectionHandle] | None = None
    health_acquire: asyncio.Task[ConnectionHandle] | None = None
    releases: list[asyncio.Task[None]] = []

    try:
        first_handle = await asyncio.wait_for(pool.acquire(), _WAIT_SECONDS)

        connecting_acquire = asyncio.create_task(pool.acquire())
        await _wait_for_event(connecting_connector.connect_started)
        first_release = asyncio.create_task(pool.release(first_handle))
        releases.append(first_release)
        await asyncio.wait_for(first_release, _WAIT_SECONDS)
        assert not connecting_acquire.done()

        connecting_connector.allow_connect.set()
        second_handle = await asyncio.wait_for(connecting_acquire, _WAIT_SECONDS)

        idle_connector.health_check_started.clear()
        idle_connector.allow_health_check.clear()
        health_acquire = asyncio.create_task(pool.acquire())
        await _wait_for_event(idle_connector.health_check_started)
        second_release = asyncio.create_task(pool.release(second_handle))
        releases.append(second_release)
        await asyncio.wait_for(second_release, _WAIT_SECONDS)
        assert not health_acquire.done()

        idle_connector.allow_health_check.set()
        reused_handle = await asyncio.wait_for(health_acquire, _WAIT_SECONDS)
        assert reused_handle is first_handle
    finally:
        for item in (idle_connector, connecting_connector):
            item.allow_connect.set()
            item.allow_health_check.set()
            item.allow_disconnect.set()
        tasks = [task for task in (connecting_acquire, health_acquire) if task is not None]
        tasks.extend(releases)
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), _WAIT_SECONDS)
        await asyncio.wait_for(pool.close_all(), _WAIT_SECONDS)
