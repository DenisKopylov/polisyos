"""Physical file ownership through the actual pool and stream cleanup consumer.

The POSIX fixture owns and reads a persistent FD. It proves a finite same-pool
refusal/retry path, not a capacity law across separately created private pools.
"""

from __future__ import annotations

import errno
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    HealthStatus,
)
from polisyos.fabric.connectors.pool import PoolClosedError
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.connectors.types import DataChunk
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamRuntimeOptions,
    process_stream_dataset,
)

pytestmark = pytest.mark.skipif(
    not hasattr(os, "pread"),
    reason="the physical file oracle requires POSIX pread",
)


def _assert_closed_fd(fd: int) -> None:
    with pytest.raises(OSError) as caught:
        os.fstat(fd)
    assert caught.value.errno == errno.EBADF


class _FileDescriptorEventStream(EventStreamConnector):
    """Own a real descriptor and use it for the consumer's actual row reads."""

    def __init__(self, sources: dict[str, Path]) -> None:
        self.sources = sources
        self.resources: dict[str, tuple[ConnectionHandle, int]] = {}
        self.live_fds: set[int] = set()
        self.disconnect_failures = 0
        self.connect_handles: list[ConnectionHandle] = []
        self.disconnect_attempts: list[ConnectionHandle] = []
        self.successful_disconnects: list[ConnectionHandle] = []
        self.stream_reads: list[tuple[ConnectionHandle, int, bytes]] = []
        self.events: list[tuple[str, str, int]] = []

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = await super().connect(config)
        fd = os.open(self.sources[config.url], os.O_RDONLY)
        self.resources[handle.session_id] = (handle, fd)
        self.live_fds.add(fd)
        self.connect_handles.append(handle)
        self.events.append(("connect", handle.session_id, fd))
        return handle

    def _resource(self, handle: ConnectionHandle) -> int:
        owner, fd = self.resources[handle.session_id]
        assert owner is handle
        stat = os.fstat(fd)
        source_stat = self.sources[handle.config.url].stat()
        assert (stat.st_dev, stat.st_ino) == (source_stat.st_dev, source_stat.st_ino)
        return fd

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        fd = self._resource(handle)
        assert os.pread(fd, 1, 0), "the real source must be nonempty"
        return HealthStatus(healthy=True, message="persistent source FD is readable")

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[Any]]:
        del request
        fd = self._resource(handle)
        payload = os.pread(fd, os.fstat(fd).st_size, 0)
        self.stream_reads.append((handle, fd, payload))
        self.events.append(("read", handle.session_id, fd))
        rows = [json.loads(line) for line in payload.splitlines() if line.strip()]
        assert rows and all(type(row) is dict for row in rows)
        yield DataChunk(
            data=rows,
            chunk_index=0,
            row_count=len(rows),
            bytes_size=len(payload),
            is_first=True,
            is_last=True,
        )

    @staticmethod
    def _close_physical_file(fd: int) -> None:
        os.close(fd)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        fd = self._resource(handle)
        self.disconnect_attempts.append(handle)
        self.events.append(("disconnect", handle.session_id, fd))
        if self.disconnect_failures:
            self.disconnect_failures -= 1
            raise RuntimeError("injected disconnect failure before physical FD close")
        self._close_physical_file(fd)
        # Preserve the declared success/counters in the matched close removal.
        # The consumer's independent fstat assertion must detect the live FD even
        # when this call returns and the pool has forgotten its logical owner.
        self.live_fds.remove(fd)
        self.successful_disconnects.append(handle)
        self.events.append(("closed", handle.session_id, fd))
        await super().disconnect(handle)

    def emergency_fixture_cleanup(self) -> None:
        """Avoid leaving test resources open after an already-observed failure."""
        for owner, fd in self.resources.values():
            try:
                stat = os.fstat(fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise
                continue
            source_stat = self.sources[owner.config.url].stat()
            # Numeric FDs may be reused. Never close another resource merely
            # because an earlier descriptor had the same integer.
            if (stat.st_dev, stat.st_ino) == (source_stat.st_dev, source_stat.st_ino):
                os.close(fd)
            self.live_fds.discard(fd)


def _accept_rows(batch: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    return [dict(row) for row in batch], [], 0


@pytest.mark.asyncio
async def test_pending_physical_file_is_retained_refused_and_closed_before_fresh_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_row = {"_message_id": "old-event", "value": 1}
    fresh_row = {"_message_id": "fresh-event", "value": 2}
    old_source = tmp_path / "old-events.jsonl"
    fresh_source = tmp_path / "fresh-events.jsonl"
    old_source.write_text(json.dumps(old_row) + "\n", encoding="utf-8")
    fresh_source.write_text(json.dumps(fresh_row) + "\n", encoding="utf-8")
    old_config = ConnectionConfig(url=old_source.as_uri(), max_connections=1)
    fresh_config = ConnectionConfig(url=fresh_source.as_uri(), max_connections=1)
    connector = _FileDescriptorEventStream(
        {old_config.url: old_source, fresh_config.url: fresh_source}
    )
    connector.disconnect_failures = 2
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=old_config, factory=lambda: connector)
    sessions: list[StreamingSourceSession] = []
    original_create = StreamingSourceSession.create

    async def capture_session(
        cls: type[StreamingSourceSession],
        **kwargs: Any,
    ) -> StreamingSourceSession:
        del cls
        session = await original_create(**kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(StreamingSourceSession, "create", classmethod(capture_session))
    primary = RuntimeError("primary sanitizer failure")

    def fail_sanitization(batch: Any, **kwargs: Any) -> Any:
        del batch, kwargs
        raise primary

    cas_root = tmp_path / "cas"
    observations: dict[str, Any] = {}
    try:
        with pytest.raises(RuntimeError, match="primary sanitizer failure") as caught:
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id="old-fd-owner",
                store=FileSystemCAS(cas_root),
                cursor_store=CursorStore(FileSystemCAS(cas_root)),
                sanitize_rows=fail_sanitization,
                runtime_options=StreamRuntimeOptions(batch_size=1),
                connection_config=old_config,
                registry=registry,
            )
        assert caught.value is primary
        assert len(sessions) == len(connector.connect_handles) == 1
        old_session = sessions[0]
        old_pool = old_session.pool
        old_handle = connector.connect_handles[0]
        old_owner, old_fd = connector.resources[old_handle.session_id]
        assert old_owner is old_handle
        assert connector.stream_reads == [(old_handle, old_fd, old_source.read_bytes())]
        assert connector.disconnect_attempts == [old_handle]
        assert connector.successful_disconnects == []
        old_stat = os.fstat(old_fd)
        assert os.pread(old_fd, old_stat.st_size, 0) == old_source.read_bytes()
        fqid = registry.get_entry("stream.jsonl").fqid
        owners = tuple(registry._pending_startup_cleanup.values())
        assert owners == ((fqid, old_pool),)
        pending = old_pool._pending_cleanup[old_handle.session_id]
        assert pending.handle is old_handle
        assert pending.closed is False
        assert pending.pending_permit is False
        assert old_pool._semaphore._value == 1
        assert old_pool.is_closed is True
        observations["first_failure"] = {
            "fd": old_fd,
            "device": old_stat.st_dev,
            "inode": old_stat.st_ino,
            "readable": True,
            "permit_free": old_pool._semaphore._value,
            "pending_permit": pending.pending_permit,
            "registry_owner_count": len(owners),
        }

        # The old pool's public admission refuses even though its permit is free.
        # No new factory invocation or descriptor opening is allowed in that pool.
        with pytest.raises(PoolClosedError):
            await old_pool.acquire_with_connector()
        assert connector.connect_handles == [old_handle]
        assert connector._resource(old_handle) == old_fd

        with pytest.raises(RuntimeError, match="cleanup"):
            await registry.shutdown_async()
        assert connector.disconnect_attempts == [old_handle, old_handle]
        assert connector.successful_disconnects == []
        assert tuple(registry._pending_startup_cleanup.values()) == ((fqid, old_pool),)
        assert old_pool._pending_cleanup[old_handle.session_id].handle is old_handle
        assert connector._resource(old_handle) == old_fd
        assert os.pread(old_fd, old_stat.st_size, 0) == old_source.read_bytes()
        with pytest.raises(PoolClosedError):
            await old_pool.acquire_with_connector()
        assert connector.connect_handles == [old_handle]
        observations["failed_registry_retry"] = {
            "fd_still_readable": True,
            "same_handle": True,
            "same_pool": True,
            "connect_count": len(connector.connect_handles),
            "permit_free": old_pool._semaphore._value,
            "registry_owner_count": len(registry._pending_startup_cleanup),
        }

        await registry.shutdown_async()
        assert connector.disconnect_attempts == [old_handle, old_handle, old_handle]
        assert connector.successful_disconnects == [old_handle]
        assert old_pool._pending_cleanup == {}
        assert registry._pending_startup_cleanup == {}
        assert old_pool._semaphore._value == 1
        _assert_closed_fd(old_fd)
        assert connector.live_fds == set()
        await old_pool.close_all()
        await registry.shutdown_async()
        assert connector.disconnect_attempts == [old_handle, old_handle, old_handle]
        observations["successful_retry"] = {
            "old_fd_ebadf_before_fresh_connect": True,
            "same_handle_disconnect_attempts": 3,
            "actual_close_confirmations": 1,
        }

        # Fresh private-pool creation is deliberately sequenced after the actual
        # close above. This does not assert automatic fencing across private pools.
        fresh_result = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="fresh-fd-owner",
            store=FileSystemCAS(cas_root),
            cursor_store=CursorStore(FileSystemCAS(cas_root)),
            sanitize_rows=_accept_rows,
            runtime_options=StreamRuntimeOptions(batch_size=1),
            connection_config=fresh_config,
            registry=registry,
        )
        assert len(sessions) == len(connector.connect_handles) == 2
        fresh_handle = connector.connect_handles[1]
        assert fresh_handle is not old_handle
        assert sessions[1].pool is not old_pool
        fresh_fd = connector.resources[fresh_handle.session_id][1]
        assert connector.stream_reads[-1] == (
            fresh_handle,
            fresh_fd,
            fresh_source.read_bytes(),
        )
        assert connector.disconnect_attempts == [
            old_handle,
            old_handle,
            old_handle,
            fresh_handle,
        ]
        assert connector.successful_disconnects == [old_handle, fresh_handle]
        _assert_closed_fd(fresh_fd)
        assert connector.live_fds == set()
        assert fresh_result.rows_emitted == 1
        assert len(fresh_result.chunk_refs) == 1
        store = FileSystemCAS(cas_root)
        fresh_ref = fresh_result.chunk_refs[0]
        assert store.verify(fresh_ref).ok
        assert store.get_manifest(fresh_ref).kind == "fabric.stream_chunk"
        assert from_canonical_bytes(store.get_bytes(fresh_ref))["data"] == [fresh_row]
        assert fresh_result.final_checkpoint is not None
        latest = CursorStore(store).find_latest_stream_checkpoint("stream.jsonl", "fresh-fd-owner")
        assert latest is not None
        assert latest.model_dump(mode="json") == fresh_result.final_checkpoint.model_dump(
            mode="json"
        )
        closed_index = connector.events.index(("closed", old_handle.session_id, old_fd))
        fresh_index = connector.events.index(("connect", fresh_handle.session_id, fresh_fd))
        assert closed_index < fresh_index
        observations["fresh_consumer"] = {
            "new_handle": True,
            "different_private_pool": True,
            "rows": fresh_result.rows_emitted,
            "verified_chunk_ref": str(fresh_ref),
            "old_close_before_fresh_connect": True,
        }
        print("PHYSICAL_FILE_CLEANUP_OBSERVATION " + json.dumps(observations, sort_keys=True))
    finally:
        connector.disconnect_failures = 0
        try:
            for session in sessions:
                await session.pool.close_all()
            await registry.shutdown_async()
        finally:
            # This is emergency test teardown, never deciding production evidence.
            connector.emergency_fixture_cleanup()
