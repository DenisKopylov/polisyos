"""Pool admission invariants exercised through real connector operations."""

from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig, PoolExhaustedError


class _GatedConnector:
    connector_id = "e02-gated"

    def __init__(self, phase: str, suppress: bool = False) -> None:
        self.phase = phase
        self.suppress = suppress
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.disconnects = 0
        self.disconnect_handles: list[ConnectionHandle] = []
        self.connects = 0

    async def _gate(self, phase: str) -> None:
        if phase != self.phase:
            return
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            if not self.suppress:
                raise
            await self.release.wait()

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        self.connects += 1
        await self._gate("connect")
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        await self._gate("health")
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnects += 1
        self.disconnect_handles.append(handle)


def _pool(connector: _GatedConnector, *, timeout: float = 0.03) -> ConnectionPool:
    return ConnectionPool(
        lambda: connector,
        ConnectionConfig(url="synthetic://e02"),
        PoolConfig(max_size=1, acquire_timeout_seconds=timeout),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["connect", "health"])
@pytest.mark.parametrize("suppress", [False, True])
async def test_whole_acquisition_budget_rejects_late_handle(phase: str, suppress: bool) -> None:
    connector = _GatedConnector(phase, suppress)
    pool = _pool(connector)
    task = asyncio.create_task(pool.acquire())
    await connector.started.wait()
    # The timer is the property under test. The release cannot run before expiry.
    await asyncio.sleep(0.06)
    connector.release.set()
    try:
        with pytest.raises(PoolExhaustedError):
            await task
        assert pool.get_stats().in_use_connections == 0
        assert pool._active_acquires == 0
        assert pool._active_acquires_done.is_set()
        assert pool._semaphore._value == 1
        if phase == "health" or suppress:
            assert connector.disconnects == 1
    finally:
        connector.release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await pool.close_all()


@pytest.mark.asyncio
async def test_cancelled_waiter_cannot_retire_another_acquisition() -> None:
    connector = _GatedConnector("connect")
    pool = _pool(connector, timeout=1.0)
    owner = asyncio.create_task(pool.acquire())
    await connector.started.wait()
    waiter = asyncio.create_task(pool.acquire())
    await asyncio.sleep(0)
    waiter.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert pool._active_acquires == 1
        assert not pool._active_acquires_done.is_set()
    finally:
        connector.release.set()
        handle = await owner
        await pool.release(handle)
        await pool.close_all()


@pytest.mark.asyncio
async def test_success_returns_without_waiting_for_registration_retirement() -> None:
    connector = _GatedConnector("health")
    pool = _pool(connector, timeout=0.15)
    owner = asyncio.create_task(pool.acquire())
    await connector.started.wait()
    await pool._lock.acquire()
    connector.release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    holder_started = asyncio.Event()
    holder_release = asyncio.Event()

    async def hold_next() -> None:
        async with pool._lock:
            holder_started.set()
            await holder_release.wait()

    holder = asyncio.create_task(hold_next())
    await asyncio.sleep(0)
    pool._lock.release()
    await holder_started.wait()
    try:
        await asyncio.sleep(0)
        assert owner.done(), "successful publication must retire registration before releasing lock"
        assert pool._active_acquires == 0
    finally:
        holder_release.set()
        await holder
        handle = await owner
        await pool.release(handle)
        await pool.close_all()


@pytest.mark.asyncio
async def test_metadata_wait_is_inside_absolute_acquire_budget() -> None:
    connector = _GatedConnector("none")
    pool = _pool(connector)
    await pool._lock.acquire()
    owner = asyncio.create_task(pool.acquire())
    try:
        await asyncio.sleep(0.06)
        assert owner.done()
        with pytest.raises(PoolExhaustedError):
            await owner
        assert connector.connects == 0
        assert pool._semaphore._value == 1
    finally:
        pool._lock.release()
        await pool.close_all()


@pytest.mark.asyncio
async def test_disconnect_finishes_before_expired_acquisition_releases_capacity() -> None:
    connector = _GatedConnector("health")
    disconnect_started = asyncio.Event()
    disconnect_release = asyncio.Event()

    async def disconnect(handle: ConnectionHandle) -> None:
        connector.disconnects += 1
        disconnect_started.set()
        await disconnect_release.wait()

    connector.disconnect = disconnect
    pool = _pool(connector)
    owner = asyncio.create_task(pool.acquire())
    await connector.started.wait()
    await disconnect_started.wait()
    try:
        assert not owner.done()
        assert pool._semaphore._value == 0
        assert len(pool._pending_cleanup) == 1
        owner.cancel()
        owner.cancel()
        await asyncio.sleep(0)
        assert pool._semaphore._value == 0
    finally:
        disconnect_release.set()
        with pytest.raises(PoolExhaustedError):
            await owner
        assert connector.disconnects == 1
        assert pool._semaphore._value == 1
        await pool.close_all()


@pytest.mark.asyncio
async def test_persistent_disconnect_failure_retains_exactly_one_permit() -> None:
    connector = _GatedConnector("health")
    fail = True

    async def disconnect(handle: ConnectionHandle) -> None:
        connector.disconnects += 1
        if fail:
            raise OSError("actual disconnect unavailable")

    connector.disconnect = disconnect
    pool = _pool(connector)
    with pytest.raises(PoolExhaustedError):
        await pool.acquire()
    assert pool._semaphore._value == 0
    assert len(pool._pending_cleanup) == 1
    with pytest.raises(RuntimeError, match="cleanup remains pending"):
        await pool.close_all()
    assert pool._semaphore._value == 0
    fail = False
    await pool.close_all()
    assert pool._semaphore._value == 1
    await pool.close_all()
    assert pool._semaphore._value == 1
    assert connector.disconnects == 3


@pytest.mark.asyncio
async def test_provider_timeout_is_not_reclassified_as_acquisition_expiry() -> None:
    connector = _GatedConnector("none")

    async def connect(config: ConnectionConfig) -> ConnectionHandle:
        raise TimeoutError("provider-owned timeout")

    connector.connect = connect
    pool = _pool(connector, timeout=1.0)
    with pytest.raises(TimeoutError, match="provider-owned timeout"):
        await pool.acquire()
    assert pool._semaphore._value == 1
    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_specific_deadline_rejects_suppressed_late_handle() -> None:
    connector = _GatedConnector("connect", suppress=True)
    pool = _pool(connector, timeout=1.0)
    pool._config.connection_timeout_seconds = 0.03
    owner = asyncio.create_task(pool.acquire())
    await connector.started.wait()
    await connector.cancelled.wait()
    connector.release.set()
    with pytest.raises(TimeoutError, match="configured deadline"):
        await owner
    assert connector.disconnects == 1
    assert pool._semaphore._value == 1
    await pool.close_all()


@pytest.mark.asyncio
async def test_external_cancellation_of_cooperative_connect_retires_registration() -> None:
    connector = _GatedConnector("connect")
    pool = _pool(connector, timeout=1.0)
    owner = asyncio.create_task(pool.acquire())
    await connector.started.wait()
    owner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owner
    assert pool._active_acquires == 0
    assert pool._semaphore._value == 1
    await pool.close_all()


@pytest.mark.asyncio
async def test_both_acquisition_paths_share_deadline_admission() -> None:
    connector = _GatedConnector("connect", suppress=True)
    pool = _pool(connector)
    owner = asyncio.create_task(pool.acquire_with_connector())
    await connector.started.wait()
    await connector.cancelled.wait()
    connector.release.set()
    with pytest.raises(PoolExhaustedError):
        await owner
    assert connector.disconnects == 1
    assert pool._semaphore._value == 1
    await pool.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["connect", "health"])
async def test_cancelled_caller_cannot_receive_suppressed_late_handle(phase: str) -> None:
    connector = _GatedConnector(phase, suppress=True)
    pool = _pool(connector, timeout=1.0)
    owner = asyncio.create_task(pool.acquire())
    await connector.started.wait()
    owner.cancel()
    await connector.cancelled.wait()
    connector.release.set()
    try:
        with pytest.raises(asyncio.CancelledError):
            await owner
        assert connector.disconnects == 1
        assert pool._active_acquires == 0
        assert pool._semaphore._value == 1
        assert pool.get_stats().in_use_connections == 0
    finally:
        await pool.close_all()


@pytest.mark.asyncio
async def test_preexisting_cancellation_count_is_not_a_new_pool_cancellation() -> None:
    connector = _GatedConnector("none")
    pool = _pool(connector)

    async def previously_cancelled() -> ConnectionHandle:
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.sleep(0)
        assert task.cancelling() == 1
        return await pool.acquire()

    handle = await asyncio.create_task(previously_cancelled())
    assert pool.get_stats().in_use_connections == 1
    await pool.release(handle)
    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_factory_owner_is_checked_before_publication() -> None:
    class WrongOwnerConnector(_GatedConnector):
        async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
            self.connects += 1
            await self._gate("connect")
            return ConnectionHandle(connector_id="foreign.owner", config=config)

    connector = WrongOwnerConnector("none")
    pool = _pool(connector)
    with pytest.raises(ValueError, match="connection_pool_factory_handle_admission_mismatch"):
        await pool.acquire()

    stats = pool.get_stats()
    assert connector.disconnects == 1
    assert stats.total_connections == 0
    assert stats.in_use_connections == 0
    assert stats.idle_connections == 0
    assert pool._semaphore._value == 1
    await pool.close_all()


@pytest.mark.asyncio
async def test_selected_pool_owner_is_checked_before_connect() -> None:
    connector = _GatedConnector("none")
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="synthetic://selected-owner"),
        pool_config=PoolConfig(max_size=1),
        expected_connector_id="selected.owner",
    )

    with pytest.raises(ValueError, match="connector_owner_id_mismatch"):
        await pool.acquire()

    stats = pool.get_stats()
    assert connector.connects == 0
    assert stats.total_connections == 0
    assert stats.in_use_connections == 0
    assert pool._semaphore._value == pool._config.max_size
    await pool.close_all()


@pytest.mark.asyncio
async def test_blank_factory_owner_is_rejected_before_connect() -> None:
    class BlankOwnerConnector(_GatedConnector):
        connector_id = "   "

    connector = BlankOwnerConnector("none")
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="synthetic://blank-owner"),
        pool_config=PoolConfig(max_size=1),
    )

    with pytest.raises(ValueError, match="connector_owner_id_missing_or_invalid"):
        await pool.acquire()

    assert connector.connects == 0
    assert pool.get_stats().total_connections == 0
    assert pool._semaphore._value == pool._config.max_size
    await pool.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("connector_id", "foreign.owner"),
        ("session_id", "foreign-session"),
        ("config", ConnectionConfig(url="synthetic://changed")),
        ("created_at", None),
        ("_state", object()),
    ],
)
async def test_release_retires_handle_when_admitted_owner_fields_change(
    field: str,
    replacement: object,
) -> None:
    connector = _GatedConnector("none")
    pool = _pool(connector)
    handle = await pool.acquire()
    admitted_config = handle.config
    admitted_created_at = handle.created_at
    admitted_state = handle._state

    if field == "created_at":
        replacement = admitted_created_at.replace(year=admitted_created_at.year - 1)
    object.__setattr__(handle, field, replacement)
    release_result = await pool.release(handle)

    stats = pool.get_stats()
    assert release_result is None
    assert connector.disconnects == 1
    assert connector.disconnect_handles == [handle]
    assert handle.connector_id == connector.connector_id
    assert handle.session_id != "foreign-session"
    assert handle.config == admitted_config
    assert handle.created_at == admitted_created_at
    assert handle._state is admitted_state
    assert stats.in_use_connections == 0
    assert stats.idle_connections == 0
    assert len(pool._pending_cleanup) == 0
    assert pool._semaphore._value == 1
    await pool.close_all()


@pytest.mark.asyncio
async def test_release_rejects_same_session_clone_without_releasing_real_lease() -> None:
    connector = _GatedConnector("none")
    config = ConnectionConfig(url="synthetic://e02", max_connections=2)
    pool = ConnectionPool(
        lambda: connector,
        config,
        PoolConfig(max_size=2, acquire_timeout_seconds=0.15),
    )
    first = await pool.acquire()
    second = await pool.acquire()
    clone = ConnectionHandle(
        connector_id=first.connector_id,
        config=first.config,
        session_id=first.session_id,
    )

    await pool.release(clone)

    assert pool.get_stats().in_use_connections == 2
    assert pool.get_stats().total_releases == 0
    assert pool._semaphore._value == 0
    assert connector.disconnects == 0
    await pool.release(first)
    await pool.release(second)
    await pool.close_all()
    assert connector.disconnects == 2


@pytest.mark.asyncio
async def test_idle_handle_mutation_is_retired_before_reacquire() -> None:
    connector = _GatedConnector("none")
    pool = _pool(connector)
    original = await pool.acquire()
    await pool.release(original)
    object.__setattr__(original, "connector_id", "foreign.owner")

    replacement = await pool.acquire()

    assert replacement is not original
    assert replacement.connector_id == connector.connector_id
    assert connector.disconnects == 1
    assert pool.get_stats().in_use_connections == 1
    await pool.release(replacement)
    await pool.close_all()
    assert connector.disconnects == 2


@pytest.mark.asyncio
async def test_changed_handle_cleanup_failure_retains_owner_and_permit() -> None:
    connector = _GatedConnector("none")
    original_disconnect = connector.disconnect

    async def disconnect_once_fails(handle: ConnectionHandle) -> None:
        if connector.disconnects == 0:
            connector.disconnects += 1
            raise RuntimeError("controlled disconnect failure")
        await original_disconnect(handle)

    connector.disconnect = disconnect_once_fails
    pool = _pool(connector)
    handle = await pool.acquire()
    object.__setattr__(handle, "connector_id", "foreign.owner")

    with pytest.raises(RuntimeError, match="Connection cleanup is pending"):
        await pool.release(handle)

    assert pool.get_stats().in_use_connections == 0
    assert len(pool._pending_cleanup) == 1
    assert pool._semaphore._value == 0
    await pool.close_all()
    assert len(pool._pending_cleanup) == 0
    assert pool._semaphore._value == 1
    assert connector.disconnects == 2
