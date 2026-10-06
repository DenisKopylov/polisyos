"""Real JSONL/CAS stream cleanup consumers, independent of the pool author.

The file connector does not retain an OS descriptor between reads.  The measured
resource is its actual ConnectionHandle and the pool's disconnect confirmation;
FD observations are reported separately and are not turned into a descriptor leak.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import StreamCheckpoint
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.pool import ConnectionPool, PoolClosedError, PoolConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.connectors.types import DataChunk
from polisyos.fabric.data_plane import streaming as streaming_module
from polisyos.fabric.data_plane.cursor_store import CursorStore, CursorStoreError
from polisyos.fabric.data_plane.streaming import StreamingSourceSession, process_stream_dataset
from polisyos.ir.connectors import FetchRequest


class ConnectorStageError(RuntimeError):
    """A deliberate failure at a real file-connector operation boundary."""


class ObservedFileConnector(EventStreamConnector):
    """Delegate real file operations and record actual handle confirmation."""

    def __init__(self, stage: str) -> None:
        super().__init__()
        self.stage = stage
        self.fetch_calls = 0
        self.disconnect_failures = (
            3 if stage == "startup-owner-retry" else int(stage == "process-disconnect-failure")
        )
        self.primary_fault = ConnectorStageError(stage)
        self.active: dict[str, ConnectionHandle] = {}
        self.disconnect_calls: list[str] = []
        self.disconnected: list[str] = []
        self.poll_entered = asyncio.Event()
        self.poll_release = asyncio.Event()

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = await super().connect(config)
        self.active[handle.session_id] = handle
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnect_calls.append(handle.session_id)
        if self.disconnect_failures:
            self.disconnect_failures -= 1
            raise ConnectorStageError("actual-disconnect-refused")
        await super().disconnect(handle)
        self.active.pop(handle.session_id, None)
        self.disconnected.append(handle.session_id)

    def fetch_stream(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> AsyncIterator[DataChunk[Any]]:
        self.fetch_calls += 1
        stream = super().fetch_stream(handle, request)
        if self.stage in {"subscribe-failure", "startup-owner-retry"}:
            raise self.primary_fault
        if self.stage == "rewind-failure" and self.fetch_calls == 2:
            raise self.primary_fault
        if self.stage == "caller-cancel":
            return self._gated_file_read(stream)
        return stream

    async def _gated_file_read(
        self, stream: AsyncIterator[DataChunk[Any]]
    ) -> AsyncIterator[DataChunk[Any]]:
        self.poll_entered.set()
        await self.poll_release.wait()
        async for chunk in stream:
            yield chunk


def _valid_rows(
    batch: list[dict[str, Any]], **kwargs: Any
) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    return [dict(row) for row in batch], [], 0


def _file_fds(path: Path) -> list[str]:
    """Observe actual Linux file descriptors without inventing retained file I/O."""
    result: list[str] = []
    for fd in Path("/proc/self/fd").iterdir():
        try:
            if os.readlink(fd) == str(path):
                result.append(fd.name)
        except FileNotFoundError:
            continue
    return sorted(result)


def _snapshot(
    pool: ConnectionPool[Any],
    connector: ObservedFileConnector,
    registry: ConnectorRegistry,
    path: Path,
) -> dict[str, Any]:
    return {
        "stats": asdict(pool.get_stats()),
        "available_permits": pool._semaphore._value,
        "pool_closed": pool._closed,
        "pending_cleanup": {
            key: {
                "pending_permit": item.pending_permit,
                "closed": item.closed,
                "task_done": item.cleanup_task.done() if item.cleanup_task else None,
            }
            for key, item in pool._pending_cleanup.items()
        },
        "registry_pending_owner_count": len(registry._pending_startup_cleanup),
        "actual_handles_without_disconnect_confirmation": sorted(connector.active),
        "confirmed_disconnects": list(connector.disconnected),
        "disconnect_calls": list(connector.disconnect_calls),
        "jsonl_open_fds": _file_fds(path),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage",
    [
        "healthy",
        "subscribe-failure",
        "checkpoint-read-failure",
        "rewind-failure",
        "caller-cancel",
        "startup-owner-retry",
        "process-disconnect-failure",
    ],
)
async def test_process_file_stream_cleanup_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    """A finished process consumer must clean or transfer its acquired handle."""
    path = tmp_path / "events.jsonl"
    path.write_text('{"_message_id":"m1","value":1}\n{"_message_id":"m2","value":2}\n')
    connector = ObservedFileConnector(stage)
    config = ConnectionConfig(url=path.as_uri(), max_connections=1)
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    captured: list[ConnectionPool[Any]] = []
    real_pool = ConnectionPool

    def observe_real_pool(*args: Any, **kwargs: Any) -> ConnectionPool[Any]:
        pool = real_pool(*args, **kwargs)
        captured.append(pool)
        return pool

    # Observation only: create still receives the canonical production pool.
    monkeypatch.setattr(streaming_module, "ConnectionPool", observe_real_pool)
    store = FileSystemCAS(tmp_path / "cas")
    cursors = CursorStore(store)
    if stage == "checkpoint-read-failure":
        cursors._stream_index_path.write_text("{broken-json")
    if stage == "rewind-failure":
        cursors.save_stream_checkpoint(
            StreamCheckpoint(
                checkpoint_id="stream.jsonl:events:default:0",
                stream_id="stream.jsonl:events:default",
                connector_id="stream.jsonl",
                dataset_id="events",
                offset=0,
                created_at=datetime.now(UTC),
            )
        )

    task = asyncio.create_task(
        process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="events",
            store=store,
            cursor_store=cursors,
            sanitize_rows=_valid_rows,
            registry=registry,
        )
    )
    if stage == "caller-cancel":
        await asyncio.wait_for(connector.poll_entered.wait(), 2)
        task.cancel()
    caught: BaseException | None = None
    result = None
    try:
        result = await task
    except BaseException as exc:
        caught = exc

    assert len(captured) == 1  # Actual C-created pool, not a substitute.
    pool = captured[0]
    before_retry = _snapshot(pool, connector, registry, path)
    same_pool_acquire: str
    try:
        handle = await pool.acquire()
    except PoolClosedError:
        same_pool_acquire = "PoolClosedError"
    else:
        same_pool_acquire = "acquired"
        await pool.release(handle)

    # Real registry retry establishes whether a production owner can finish it.
    await registry.shutdown_async()
    after_registry_retry = _snapshot(pool, connector, registry, path)
    connector.stage = "healthy"
    fresh = await StreamingSourceSession.create(
        connector_id="stream.jsonl",
        dataset_id="fresh",
        registry=registry,
    )
    fresh_chunk = await fresh.poll()
    during_fresh = _snapshot(pool, connector, registry, path)
    await fresh.close()
    after_fresh = _snapshot(pool, connector, registry, path)
    # Test observer cleanup is outside the measured production retry. It cannot
    # rescue the assertion or establish an owner for the finished consumer.
    await pool.close_all()
    final = _snapshot(pool, connector, registry, path)
    observation = {
        "stage": stage,
        "primary_exception_type": type(caught).__name__ if caught else None,
        "primary_exception_is_injected": caught is connector.primary_fault,
        "primary_notes": getattr(caught, "__notes__", []),
        "before_retry": before_retry,
        "same_pool_acquire": same_pool_acquire,
        "after_registry_retry": after_registry_retry,
        "during_fresh": during_fresh,
        "after_fresh": after_fresh,
        "observer_final_cleanup": final,
        "fresh_real_file_rows": fresh_chunk.row_count if fresh_chunk else None,
        "initial_rows": result.rows_emitted if result else None,
    }
    print("STREAM_CLEANUP_OBSERVATION " + json.dumps(observation, default=str, sort_keys=True))
    ConnectorRegistry.reset_instance()

    assert fresh_chunk is not None and fresh_chunk.row_count == 2
    assert final["pending_cleanup"] == {} and final["available_permits"] == 1
    assert final["actual_handles_without_disconnect_confirmation"] == []
    if stage == "healthy":
        assert caught is None and result is not None and result.rows_emitted == 2
    elif stage == "checkpoint-read-failure":
        assert isinstance(caught, CursorStoreError)
    elif stage == "caller-cancel":
        assert isinstance(caught, asyncio.CancelledError)
    elif stage != "process-disconnect-failure":
        assert caught is connector.primary_fault
    else:
        assert isinstance(caught, RuntimeError)
    # No local observer may supply the absent production retry authority.
    assert after_registry_retry["pending_cleanup"] == {}, observation
    assert after_registry_retry["actual_handles_without_disconnect_confirmation"] == [], observation


@pytest.mark.asyncio
async def test_direct_file_session_second_close_finishes_pending_cleanup(tmp_path: Path) -> None:
    """Retaining the actual session allows a transient disconnect to be retried."""
    path = tmp_path / "events.jsonl"
    path.write_text('{"_message_id":"m1","value":1}\n')
    connector = ObservedFileConnector("process-disconnect-failure")
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url=path.as_uri()),
        pool_config=PoolConfig(max_size=1, validate_on_acquire=False, acquire_timeout_seconds=0.05),
    )
    session = StreamingSourceSession(
        connector_id="stream.jsonl",
        dataset_id="events",
        pool=pool,
        request=FetchRequest(dataset_id="events"),
    )
    await session.subscribe()
    chunk = await session.poll()
    with pytest.raises(RuntimeError, match="cleanup remains pending"):
        await session.close()
    before = {
        "session_closed": session._closed,
        "pending": list(pool._pending_cleanup),
        "active": sorted(connector.active),
    }
    await session.close()
    await session.close()
    after = {
        "session_closed": session._closed,
        "pending": list(pool._pending_cleanup),
        "active": sorted(connector.active),
        "permits": pool._semaphore._value,
    }
    print("STREAM_DIRECT_RETRY " + json.dumps({"before": before, "after": after}, sort_keys=True))
    assert chunk is not None and chunk.row_count == 1
    assert before["session_closed"] is False and before["pending"]
    assert after == {"session_closed": True, "pending": [], "active": [], "permits": 1}
