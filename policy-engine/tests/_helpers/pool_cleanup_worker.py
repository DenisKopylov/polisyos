"""Bounded child oracle for terminally cancelled physical pool cleanup."""

from __future__ import annotations

import asyncio
import errno
import json
import os
import sys
from pathlib import Path

from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig, PoolExhaustedError


class _CancelledFDConnector:
    connector_id = "terminal-cleanup-fd"

    def __init__(self) -> None:
        self.handle: ConnectionHandle | None = None
        self.fd: int | None = None
        self.disconnects = 0
        self.cancel_disconnect = True

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        self.fd = os.open(config.url, os.O_RDONLY)
        self.handle = ConnectionHandle(connector_id=self.connector_id, config=config)
        return self.handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        assert handle is self.handle and self.fd is not None
        os.fstat(self.fd)
        return HealthStatus(healthy=True)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        assert handle is self.handle and self.fd is not None
        self.disconnects += 1
        if self.cancel_disconnect:
            raise asyncio.CancelledError
        os.close(self.fd)


async def _exercise(resource: Path, entrypoint: str) -> None:
    connector = _CancelledFDConnector()
    pool = ConnectionPool(
        lambda: connector,
        ConnectionConfig(url=str(resource)),
        PoolConfig(max_size=1, max_connection_uses=1, acquire_timeout_seconds=0.01),
    )
    pool._semaphore = asyncio.BoundedSemaphore(1)
    handle = await pool.acquire()
    assert connector.fd is not None
    fd = connector.fd
    expected = resource.read_bytes()
    assert os.pread(fd, len(expected), 0) == expected
    heartbeat = 0
    finished = False

    async def pulse() -> None:
        nonlocal heartbeat
        while not finished:
            heartbeat += 1
            await asyncio.sleep(0)

    pulse_task = asyncio.create_task(pulse())
    operation = pool.release(handle) if entrypoint == "release" else pool.close_all()
    try:
        await operation
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("terminal cleanup cancellation must propagate")
    prior_heartbeat = heartbeat
    await asyncio.sleep(0)
    assert heartbeat > prior_heartbeat
    assert len(pool._pending_cleanup) == 1
    owner = next(iter(pool._pending_cleanup.values()))
    assert owner.handle is handle and owner.pending_permit
    assert owner.cleanup_task is None and not owner.closing and not owner.closed
    assert pool._semaphore._value == 0
    assert os.pread(fd, len(expected), 0) == expected
    if entrypoint == "release":
        try:
            await pool.acquire()
        except PoolExhaustedError:
            pass
        else:
            raise AssertionError("unclosed physical owner must retain capacity")
    connector.cancel_disconnect = False
    await pool.close_all()
    assert connector.disconnects == 2
    assert not pool._pending_cleanup and not pool._handle_owners
    assert pool._semaphore._value == 1
    try:
        os.fstat(fd)
    except OSError as exc:
        if exc.errno != errno.EBADF:
            raise AssertionError("descriptor close returned an unexpected OS error") from exc
    else:
        raise AssertionError("physical descriptor was not closed")
    await pool.close_all()
    assert pool._semaphore._value == 1 and connector.disconnects == 2
    finished = True
    await pulse_task
    print(json.dumps({"entrypoint": entrypoint, "heartbeat": heartbeat, "closed_fd": True}))


if __name__ == "__main__":
    asyncio.run(_exercise(Path(sys.argv[1]), sys.argv[2]))
