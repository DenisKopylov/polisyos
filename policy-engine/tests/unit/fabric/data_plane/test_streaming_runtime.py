from __future__ import annotations

import asyncio
import gc
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamCheckpoint, StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.pool import ConnectionPool, PoolClosedError, PoolConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane.cursor_store import (
    AsyncCursorStoreAdapter,
    CursorStore,
    CursorStoreError,
)
from polisyos.fabric.data_plane.quarantine import list_quarantine_records
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamWindowAccumulator,
    StreamRuntimeOptions,
    iter_record_batches,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy
from polisyos.fabric.quality.processing_guarantees import (
    BackpressurePolicy,
    stream_processing_contract,
)
from polisyos.ir.connectors import FetchRequest

if TYPE_CHECKING:
    from pathlib import Path


class _Net01StreamingConnector:
    """Controlled stream connector for acquisition and close ownership probes."""

    def __init__(
        self,
        *,
        fail_subscribe: bool = False,
        close_failures: int = 0,
        disconnect_failures: int = 0,
    ) -> None:
        self.fail_subscribe = fail_subscribe
        self.close_failures = close_failures
        self.disconnect_failures = disconnect_failures
        self.disconnect_calls: list[str] = []

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(connector_id="net01-stream", config=config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnect_calls.append(handle.session_id)
        if self.disconnect_failures:
            self.disconnect_failures -= 1
            raise RuntimeError("controlled disconnect failure")

    async def health_check(self, handle: ConnectionHandle) -> Any:
        del handle
        return type("Health", (), {"healthy": True})()

    async def subscribe_stream(self, handle: ConnectionHandle, request: Any) -> object:
        del handle, request
        if self.fail_subscribe:
            raise RuntimeError("controlled subscribe failure")
        return object()

    async def close_stream(self, handle: ConnectionHandle) -> None:
        del handle
        if self.close_failures:
            self.close_failures -= 1
            raise RuntimeError("controlled close failure")


def _valid_rows(batch, **kwargs):
    del kwargs
    return [dict(row) for row in batch if isinstance(row, dict)], [], 0


def _collect_state_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        raw_refs = value.get("refs", ())
        if isinstance(raw_refs, list | tuple):
            refs.update(str(ref) for ref in raw_refs if ref)
        for child in value.values():
            refs.update(_collect_state_refs(child))
    elif isinstance(value, list | tuple):
        for child in value:
            refs.update(_collect_state_refs(child))
    return refs


@pytest.mark.asyncio
async def test_net01_subscribe_failure_releases_acquired_handle() -> None:
    """A failed subscription must hand its acquired permit back to the pool."""

    connector = _Net01StreamingConnector(fail_subscribe=True)
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="https://stream.example"),
        pool_config=PoolConfig(
            max_size=1,
            validate_on_acquire=False,
            acquire_timeout_seconds=0.02,
        ),
    )
    session = StreamingSourceSession(
        connector_id="net01-stream",
        dataset_id="subscribe-failure",
        pool=pool,
        request=FetchRequest(dataset_id="subscribe-failure"),
    )

    with pytest.raises(RuntimeError, match="controlled subscribe failure"):
        await session.subscribe()

    assert pool.get_stats().in_use_connections == 0
    with pytest.raises(PoolClosedError):
        await pool.acquire()
    assert session._closed is True
    assert session.handle is None


@pytest.mark.asyncio
async def test_net01_close_failure_can_finish_cleanup_on_retry() -> None:
    """A stream close failure must not make a later close a no-op."""

    connector = _Net01StreamingConnector(close_failures=1)
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="https://stream.example"),
        pool_config=PoolConfig(max_size=1, validate_on_acquire=False),
    )
    session = StreamingSourceSession(
        connector_id="net01-stream",
        dataset_id="close-retry",
        pool=pool,
        request=FetchRequest(dataset_id="close-retry"),
    )
    await session.subscribe()

    with pytest.raises(RuntimeError, match="controlled close failure"):
        await session.close()
    assert session._closed is False
    assert session.handle is not None
    await session.close()

    assert pool.get_stats().in_use_connections == 0
    await pool.close_all()
    assert len(connector.disconnect_calls) == 1
    assert session._closed is True
    assert session.handle is None


@pytest.mark.asyncio
async def test_net01_subscribe_failure_retains_handle_when_release_cleanup_fails() -> None:
    """A failed release remains retryable without losing the subscription handle."""

    connector = _Net01StreamingConnector(
        fail_subscribe=True,
        disconnect_failures=2,
    )
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="https://stream.example"),
        pool_config=PoolConfig(
            max_size=1,
            max_connection_uses=1,
            validate_on_acquire=False,
            acquire_timeout_seconds=0.02,
        ),
    )
    session = StreamingSourceSession(
        connector_id="net01-stream",
        dataset_id="subscribe-cleanup-retry",
        pool=pool,
        request=FetchRequest(dataset_id="subscribe-cleanup-retry"),
    )

    with pytest.raises(RuntimeError, match="controlled subscribe failure"):
        await session.subscribe()

    assert session._closed is False
    assert session._cleanup_pending is True
    assert session.handle is not None
    failed_handle_id = session.handle.session_id
    assert connector.disconnect_calls == [failed_handle_id, failed_handle_id]
    assert pool._pending_cleanup[failed_handle_id].pending_permit is True

    await session.close()

    assert session._closed is True
    assert session.handle is None
    assert connector.disconnect_calls == [failed_handle_id] * 3


@pytest.mark.asyncio
async def test_net01_create_failure_retries_session_cleanup_before_reraising() -> None:
    """The create entrypoint must not orphan a handle after startup cleanup fails."""

    connector = _Net01StreamingConnector(
        fail_subscribe=True,
        disconnect_failures=1,
    )
    entry = SimpleNamespace(
        factory=lambda: connector,
        default_config=ConnectionConfig(
            url="https://stream.example",
            max_connections=1,
        ),
    )
    registry = SimpleNamespace(get_entry=lambda _connector_id: entry)

    with pytest.raises(RuntimeError, match="controlled subscribe failure"):
        await StreamingSourceSession.create(
            connector_id="net01-stream",
            dataset_id="create-cleanup-retry",
            registry=registry,
        )

    assert len(connector.disconnect_calls) == 2
    assert len(set(connector.disconnect_calls)) == 1


@pytest.mark.asyncio
async def test_net01_create_transfers_unresolved_startup_owner_to_registry() -> None:
    """Repeated startup cleanup failure remains reachable after create raises."""

    connector = _Net01StreamingConnector(
        fail_subscribe=True,
        disconnect_failures=4,
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    registry.register(
        EventStreamConnector,
        config=ConnectionConfig(
            url="https://stream.example",
            max_connections=1,
        ),
        factory=lambda: connector,
    )

    with pytest.raises(RuntimeError, match="controlled subscribe failure"):
        await StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id="registry-owned-startup-cleanup",
            registry=registry,
        )

    assert len(registry._pending_startup_cleanup) == 1
    pending_pool = next(iter(registry._pending_startup_cleanup.values()))[1]
    pending_session_ids = tuple(pending_pool._pending_cleanup)
    assert pending_session_ids
    assert pending_pool._pending_cleanup[pending_session_ids[0]].pending_permit is True
    assert len(set(connector.disconnect_calls)) == 1
    with pytest.raises(PoolClosedError):
        await pending_pool.acquire()

    with pytest.raises(RuntimeError):
        await registry.shutdown_async()
    assert len(registry._pending_startup_cleanup) == 1

    connector.disconnect_failures = 0
    await registry.shutdown_async()
    assert registry._pending_startup_cleanup == {}
    assert tuple(pending_pool._pending_cleanup) == ()
    assert connector.disconnect_calls == [pending_session_ids[0]] * 5
    ConnectorRegistry.reset_instance()


@pytest.mark.asyncio
async def test_net01_checkpoint_lookup_failure_closes_owned_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checkpoint preparation errors still finalize an acquired stream session."""

    connector = _Net01StreamingConnector()
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="https://stream.example"),
        pool_config=PoolConfig(max_size=1, validate_on_acquire=False),
    )
    session = StreamingSourceSession(
        connector_id="net01-stream",
        dataset_id="checkpoint-failure",
        pool=pool,
        request=FetchRequest(dataset_id="checkpoint-failure"),
    )
    await session.subscribe()

    async def fake_create(cls, **kwargs: Any) -> StreamingSourceSession:
        del cls, kwargs
        return session

    async def fail_lookup(self, *args: Any, **kwargs: Any) -> None:
        del self, args, kwargs
        raise RuntimeError("controlled checkpoint lookup failure")

    monkeypatch.setattr(StreamingSourceSession, "create", classmethod(fake_create))
    monkeypatch.setattr(
        AsyncCursorStoreAdapter,
        "find_latest_stream_checkpoint",
        fail_lookup,
    )

    store = FileSystemCAS(tmp_path / ".polisyos")
    with pytest.raises(RuntimeError, match="controlled checkpoint lookup failure"):
        await process_stream_dataset(
            connector_id="net01-stream",
            dataset_id="checkpoint-failure",
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
        )

    assert session._closed is True
    assert session.handle is None
    assert len(connector.disconnect_calls) == 1


@pytest.mark.asyncio
async def test_net01_rewind_failure_closes_owned_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rewind preparation errors cannot bypass the session finalizer."""

    connector = _Net01StreamingConnector()
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="https://stream.example"),
        pool_config=PoolConfig(max_size=1, validate_on_acquire=False),
    )
    session = StreamingSourceSession(
        connector_id="net01-stream",
        dataset_id="rewind-failure",
        pool=pool,
        request=FetchRequest(dataset_id="rewind-failure"),
    )
    await session.subscribe()
    checkpoint = StreamCheckpoint(
        checkpoint_id="net01-stream:rewind-failure:default:1",
        stream_id="net01-stream:rewind-failure:default",
        connector_id="net01-stream",
        dataset_id="rewind-failure",
        offset=1,
        created_at=datetime.now(UTC),
    )

    async def fake_create(cls, **kwargs: Any) -> StreamingSourceSession:
        del cls, kwargs
        return session

    async def fake_lookup(self, *args: Any, **kwargs: Any) -> StreamCheckpoint:
        del self, args, kwargs
        return checkpoint

    async def fail_rewind(_checkpoint: StreamCheckpoint) -> None:
        raise RuntimeError("controlled rewind failure")

    monkeypatch.setattr(StreamingSourceSession, "create", classmethod(fake_create))
    monkeypatch.setattr(
        AsyncCursorStoreAdapter,
        "find_latest_stream_checkpoint",
        fake_lookup,
    )
    monkeypatch.setattr(session, "rewind", fail_rewind)

    store = FileSystemCAS(tmp_path / ".polisyos")
    with pytest.raises(RuntimeError, match="controlled rewind failure"):
        await process_stream_dataset(
            connector_id="net01-stream",
            dataset_id="rewind-failure",
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
        )

    assert session._closed is True
    assert session.handle is None
    assert len(connector.disconnect_calls) == 1


@pytest.mark.asyncio
async def test_net01_stream_cleanup_does_not_mask_primary_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finalizer failure is evidence on, not a replacement for, the run error."""

    connector = _Net01StreamingConnector()
    pool = ConnectionPool(
        connector_factory=lambda: connector,
        config=ConnectionConfig(url="https://stream.example"),
        pool_config=PoolConfig(max_size=1, validate_on_acquire=False),
    )
    session = StreamingSourceSession(
        connector_id="net01-stream",
        dataset_id="primary-and-cleanup-failure",
        pool=pool,
        request=FetchRequest(dataset_id="primary-and-cleanup-failure"),
    )

    async def fake_create(cls, **kwargs: Any) -> StreamingSourceSession:
        del cls, kwargs
        return session

    async def fail_poll() -> None:
        raise RuntimeError("controlled primary stream failure")

    async def fail_close() -> None:
        raise RuntimeError("controlled cleanup failure")

    monkeypatch.setattr(StreamingSourceSession, "create", classmethod(fake_create))
    monkeypatch.setattr(session, "poll", fail_poll)
    monkeypatch.setattr(session, "close", fail_close)

    store = FileSystemCAS(tmp_path / ".polisyos")
    with pytest.raises(RuntimeError, match="controlled primary stream failure") as exc_info:
        await process_stream_dataset(
            connector_id="net01-stream",
            dataset_id="primary-and-cleanup-failure",
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
        )

    assert any("controlled cleanup failure" in note for note in exc_info.value.__notes__)


@pytest.mark.asyncio
async def test_process_stream_dataset_recovers_from_checkpoint_and_dedupes_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    stream_path = tmp_path / "events.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","value":1}',
                '{"_message_id":"m2","value":2}',
                '{"_message_id":"m2","value":2}',
                '{"_message_id":"m3","value":3,"new_field":"x"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )

    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    original_poll = StreamingSourceSession.poll
    state = {"calls": 0}

    async def flaky_poll(self):
        if state["calls"] == 1:
            raise RuntimeError("poll boom")
        chunk = await original_poll(self)
        if chunk is not None:
            state["calls"] += 1
        return chunk

    monkeypatch.setattr(StreamingSourceSession, "poll", flaky_poll)
    with pytest.raises(RuntimeError, match="poll boom"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="events",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
        )

    paused = cursor_store.find_latest_stream_checkpoint("stream.jsonl", "events")
    assert paused is not None
    assert paused.lifecycle_state == StreamLifecycleState.PAUSED
    assert paused.offset == 0
    assert paused.dedupe_keys == ("_message_id:m1", "_message_id:m2")

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    recovered = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="events",
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
    )

    assert recovered.rows_emitted == 1
    assert recovered.dedupe_dropped == 1
    assert len(recovered.cdc_event_refs) == 1
    latest = cursor_store.find_latest_stream_checkpoint("stream.jsonl", "events")
    assert latest is not None
    assert latest.lifecycle_state == StreamLifecycleState.CLOSED
    assert latest.offset == 1


@pytest.mark.asyncio
async def test_stream_failure_before_chunk_persistence_replays_dedupe_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observed poll/dedupe state must not become a resumable frontier."""

    stream_path = tmp_path / "pre-chunk-failure.jsonl"
    stream_path.write_text(
        '{"_message_id":"m1","value":1}\n'
        '{"_message_id":"m2","value":2}\n',
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    original_persist = __import__(
        "polisyos.fabric.data_plane.streaming",
        fromlist=["_persist_stream_chunk_async"],
    )._persist_stream_chunk_async

    async def fail_before_persist(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise RuntimeError("pre-chunk persistence failure")

    monkeypatch.setattr(
        "polisyos.fabric.data_plane.streaming._persist_stream_chunk_async",
        fail_before_persist,
    )
    with pytest.raises(RuntimeError, match="pre-chunk persistence failure"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="pre-chunk-failure",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
            registry=registry,
        )

    paused = cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        "pre-chunk-failure",
    )
    assert paused is not None
    assert paused.offset == 0
    assert paused.dedupe_keys == ()

    monkeypatch.setattr(
        "polisyos.fabric.data_plane.streaming._persist_stream_chunk_async",
        original_persist,
    )
    recovered = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="pre-chunk-failure",
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
        registry=registry,
    )
    assert recovered.rows_emitted == 2
    assert recovered.dedupe_dropped == 0


@pytest.mark.asyncio
async def test_stream_failure_after_raw_chunk_before_checkpoint_replays_pending_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An uncheckpointed raw chunk cannot advance dedupe or window frontier."""

    stream_path = tmp_path / "post-raw-failure.jsonl"
    stream_path.write_text(
        '{"_message_id":"m1","value":1}\n'
        '{"_message_id":"m2","value":2}\n'
        '{"_message_id":"m3","value":3}\n',
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "2"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    original_poll = StreamingSourceSession.poll
    state = {"calls": 0}

    async def fail_on_second_poll(self):
        if state["calls"] == 1:
            raise RuntimeError("post-raw checkpoint failure")
        state["calls"] += 1
        return await original_poll(self)

    monkeypatch.setattr(StreamingSourceSession, "poll", fail_on_second_poll)
    with pytest.raises(RuntimeError, match="post-raw checkpoint failure"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="post-raw-failure",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(
                checkpoint_every_chunks=2,
                window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=3),
            ),
            registry=registry,
        )

    paused = cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        "post-raw-failure",
    )
    assert paused is not None
    assert paused.offset == 0
    assert paused.dedupe_keys == ()

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    recovered = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="post-raw-failure",
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            checkpoint_every_chunks=1,
            window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=3),
        ),
        registry=registry,
    )
    assert recovered.rows_emitted == 3
    assert len(recovered.window_refs) == 1
    assert list(store.get_bytes(recovered.window_refs[0].artifact_id))


@pytest.mark.parametrize(
    ("policy", "rows"),
    [
        (WindowPolicy(strategy=WindowStrategy.COUNT, size=3), [{"value": 1}, {"value": 2}]),
        (
            WindowPolicy(
                strategy=WindowStrategy.SESSION,
                size=60,
                session_gap_seconds=60,
                timestamp_field="event_time",
            ),
            [
                {"value": 1, "event_time": "2024-01-01T00:00:00+00:00"},
                {"value": 2, "event_time": "2024-01-01T00:00:10+00:00"},
            ],
        ),
        (
            WindowPolicy(strategy=WindowStrategy.SLIDING, size=3, slide=1),
            [{"value": 1}, {"value": 2}],
        ),
    ],
)
def test_stream_window_operator_state_round_trips_pending_rows(
    policy: WindowPolicy,
    rows: list[dict[str, Any]],
) -> None:
    """COUNT, SESSION, and SLIDING keep pending rows and ordinal on restart."""

    first = StreamWindowAccumulator(policy)
    first.add_rows(rows)
    state = first.snapshot()

    resumed = StreamWindowAccumulator(policy)
    resumed.restore(state)
    assert resumed.snapshot() == state
    assert resumed.buffered_rows() == len(rows)


@pytest.mark.parametrize(
    ("policy", "rows"),
    [
        (
            WindowPolicy(strategy=WindowStrategy.COUNT, size=3),
            [
                {"_message_id": "count-1", "value": 1},
                {"_message_id": "count-2", "value": 2},
                {"_message_id": "count-3", "value": 3},
            ],
        ),
        (
            WindowPolicy(
                strategy=WindowStrategy.SESSION,
                size=60,
                session_gap_seconds=60,
                timestamp_field="event_time",
            ),
            [
                {
                    "_message_id": "session-1",
                    "event_time": "2024-01-01T00:00:00+00:00",
                    "value": 1,
                },
                {
                    "_message_id": "session-2",
                    "event_time": "2024-01-01T00:00:10+00:00",
                    "value": 2,
                },
                {
                    "_message_id": "session-3",
                    "event_time": "2024-01-01T00:00:20+00:00",
                    "value": 3,
                },
            ],
        ),
        (
            WindowPolicy(strategy=WindowStrategy.SLIDING, size=3, slide=1),
            [
                {"_message_id": "sliding-1", "value": 1},
                {"_message_id": "sliding-2", "value": 2},
                {"_message_id": "sliding-3", "value": 3},
            ],
        ),
    ],
)
@pytest.mark.asyncio
async def test_stream_interrupted_pending_window_resumes_with_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy: WindowPolicy,
    rows: list[dict[str, Any]],
) -> None:
    """Committed COUNT/SESSION/SLIDING state resumes and retains source refs."""

    stream_path = tmp_path / f"resume-{policy.strategy.value}.jsonl"
    stream_path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    original_poll = StreamingSourceSession.poll
    state = {"calls": 0}

    async def fail_after_first_checkpoint(self: StreamingSourceSession):
        if state["calls"] == 1:
            raise RuntimeError("interrupted pending window")
        state["calls"] += 1
        return await original_poll(self)

    monkeypatch.setattr(StreamingSourceSession, "poll", fail_after_first_checkpoint)
    with pytest.raises(RuntimeError, match="interrupted pending window"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=f"resume-{policy.strategy.value}",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(
                checkpoint_every_chunks=1,
                window_policy=policy,
            ),
            registry=registry,
        )

    paused = cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        f"resume-{policy.strategy.value}",
    )
    assert paused is not None
    paused_refs = _collect_state_refs(paused.metadata["operator_state"])
    assert len(paused_refs) == 1

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    recovered = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=f"resume-{policy.strategy.value}",
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            checkpoint_every_chunks=1,
            window_policy=policy,
        ),
        registry=registry,
    )

    assert recovered.rows_emitted == 2
    assert len(recovered.window_refs) == 1
    manifest = store.get_manifest(recovered.window_refs[0].artifact_id)
    manifest_refs = {str(item.artifact_id) for item in manifest.inputs}
    assert paused_refs <= manifest_refs
    assert len(manifest_refs) == 3
    latest = cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        f"resume-{policy.strategy.value}",
    )
    assert latest is not None
    assert latest.lifecycle_state == StreamLifecycleState.CLOSED


@pytest.mark.asyncio
async def test_stream_window_manifest_contains_all_contributor_chunks(tmp_path: Path) -> None:
    """A window spanning chunks carries both raw chunk refs in its manifest."""

    stream_path = tmp_path / "lineage.jsonl"
    stream_path.write_text(
        '{"_message_id":"m1","value":1}\n'
        '{"_message_id":"m2","value":2}\n'
        '{"_message_id":"m3","value":3}\n',
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "2"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="lineage",
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=3),
        ),
        registry=registry,
    )

    assert len(result.chunk_refs) == 2
    assert len(result.window_refs) == 1
    manifest = store.get_manifest(result.window_refs[0].artifact_id)
    assert {str(item.artifact_id) for item in manifest.inputs} == {
        str(ref.artifact_id) for ref in result.chunk_refs
    }
    window_payload = from_canonical_bytes(store.get_bytes(result.window_refs[0].artifact_id))
    assert window_payload["window_policy"] == {
        "version": 1,
        "strategy": WindowStrategy.COUNT.value,
        "size": 3,
        "slide": None,
        "session_gap_seconds": None,
        "timestamp_field": "event_time",
    }


@pytest.mark.asyncio
async def test_stream_window_lineage_covers_trigger_and_final_flush(tmp_path: Path) -> None:
    """Trigger and closing flushes retain only their actual contributor chunks."""

    stream_path = tmp_path / "trigger-final-lineage.jsonl"
    stream_path.write_text(
        "".join(
            json.dumps({"_message_id": f"m{index}", "value": index}) + "\n"
            for index in range(1, 4)
        ),
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="trigger-final-lineage",
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            checkpoint_every_chunks=1,
            window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=2),
        ),
        registry=registry,
    )

    assert len(result.chunk_refs) == 3
    assert len(result.window_refs) == 2
    trigger_manifest = store.get_manifest(result.window_refs[0].artifact_id)
    final_manifest = store.get_manifest(result.window_refs[1].artifact_id)
    assert {str(item.artifact_id) for item in trigger_manifest.inputs} == {
        str(result.chunk_refs[0].artifact_id),
        str(result.chunk_refs[1].artifact_id),
    }
    assert {str(item.artifact_id) for item in final_manifest.inputs} == {
        str(result.chunk_refs[2].artifact_id),
    }


@pytest.mark.asyncio
async def test_stream_checkpoint_missing_operator_state_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A current-format checkpoint without operator state cannot resume silently."""

    stream_path = tmp_path / "missing-state.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri()),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    original_lookup = AsyncCursorStoreAdapter.find_latest_stream_checkpoint

    async def corrupt_lookup(self, *args: Any, **kwargs: Any) -> StreamCheckpoint | None:
        checkpoint = await original_lookup(self, *args, **kwargs)
        if checkpoint is None:
            checkpoint = StreamCheckpoint(
                checkpoint_id="stream.jsonl:missing-state:default:0",
                stream_id="stream.jsonl:missing-state:default",
                connector_id="stream.jsonl",
                dataset_id="missing-state",
                metadata={
                    "operator_state_required": True,
                    "rows_emitted": 1,
                },
                created_at=datetime.now(UTC),
            )
        else:
            checkpoint = checkpoint.model_copy(
                update={
                    "metadata": {
                        **checkpoint.metadata,
                        "operator_state_required": True,
                    },
                }
            )
        return checkpoint

    monkeypatch.setattr(
        AsyncCursorStoreAdapter,
        "find_latest_stream_checkpoint",
        corrupt_lookup,
    )
    with pytest.raises(CursorStoreError, match="operator state"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="missing-state",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            registry=registry,
        )


@pytest.mark.asyncio
async def test_stream_source_commit_failure_does_not_promote_local_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source commit failure must not leave a local cursor ahead of source state."""

    stream_path = tmp_path / "source-commit-failure.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    source_commits: list[StreamCheckpoint] = []

    async def fail_source_commit(
        self: StreamingSourceSession,
        checkpoint: StreamCheckpoint,
    ) -> None:
        del self
        source_commits.append(checkpoint)
        raise RuntimeError("source commit failed")

    monkeypatch.setattr(StreamingSourceSession, "commit", fail_source_commit)
    with pytest.raises(RuntimeError, match="source commit failed"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="source-commit-failure",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
            registry=registry,
        )

    assert len(source_commits) == 1
    assert cursor_store.find_latest_cursor("stream.jsonl", "source-commit-failure") is None
    paused = cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        "source-commit-failure",
    )
    assert paused is not None
    assert paused.lifecycle_state == StreamLifecycleState.PAUSED
    assert paused.metadata["frontier_committed"] is False
    assert paused.metadata["frontier_intent"]["state"] == "unresolved"
    assert paused.dedupe_keys == ()


@pytest.mark.asyncio
async def test_stream_local_pair_failure_compensates_source_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local pair failure after source commit must invoke bounded compensation."""

    stream_path = tmp_path / "local-pair-failure.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    source_commits: list[StreamCheckpoint] = []
    compensating_rewinds: list[StreamCheckpoint] = []

    async def record_source_commit(
        self: StreamingSourceSession,
        checkpoint: StreamCheckpoint,
    ) -> None:
        del self
        source_commits.append(checkpoint)

    async def compensate_source_commit(
        self: StreamingSourceSession,
        checkpoint: StreamCheckpoint,
    ) -> None:
        del self
        compensating_rewinds.append(checkpoint)

    async def fail_local_pair(
        self: AsyncCursorStoreAdapter,
        *,
        cursor: Any,
        checkpoint: StreamCheckpoint | None = None,
    ) -> Any:
        del self, cursor, checkpoint
        raise RuntimeError("local pair failed")

    monkeypatch.setattr(StreamingSourceSession, "commit", record_source_commit)
    monkeypatch.setattr(StreamingSourceSession, "rewind", compensate_source_commit)
    monkeypatch.setattr(AsyncCursorStoreAdapter, "commit_stream_progress", fail_local_pair)

    with pytest.raises(RuntimeError, match="local pair failed"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="local-pair-failure",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
            registry=registry,
        )

    assert len(source_commits) == 1
    assert len(compensating_rewinds) == 1
    assert compensating_rewinds[0].offset == 0
    assert compensating_rewinds[0].metadata["frontier_committed"] is False
    assert cursor_store.find_latest_cursor("stream.jsonl", "local-pair-failure") is None


@pytest.mark.asyncio
async def test_stream_cancelled_source_commit_leaves_prepared_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation after intent persistence must block the next recovery."""

    stream_path = tmp_path / "cancelled-frontier.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)

    async def cancel_source_commit(
        self: StreamingSourceSession,
        checkpoint: StreamCheckpoint,
    ) -> None:
        del self, checkpoint
        raise asyncio.CancelledError()

    monkeypatch.setattr(StreamingSourceSession, "commit", cancel_source_commit)
    with pytest.raises(asyncio.CancelledError):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="cancelled-frontier",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
            registry=registry,
        )

    prepared = cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        "cancelled-frontier",
    )
    assert prepared is not None
    intent = prepared.metadata["frontier_intent"]
    assert intent["version"] == 1
    assert intent["state"] == "prepared"
    assert intent["intent_id"]
    assert intent["target_checkpoint_id"] == prepared.checkpoint_id
    assert intent["target_cursor_id"] == "stream.jsonl:cancelled-frontier"
    assert intent["target_digest"]
    assert "prior_checkpoint_id" in intent
    assert prepared.metadata["frontier_committed"] is False
    assert cursor_store.find_latest_cursor("stream.jsonl", "cancelled-frontier") is None

    with pytest.raises(CursorStoreError, match="frontier intent"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="cancelled-frontier",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
            registry=registry,
        )


@pytest.mark.asyncio
async def test_stream_rewind_failure_leaves_unresolved_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed source compensation keeps an unresolved marker for retry review."""

    stream_path = tmp_path / "rewind-failure.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)

    async def source_commit_succeeds(
        self: StreamingSourceSession,
        checkpoint: StreamCheckpoint,
    ) -> None:
        del self, checkpoint

    async def fail_local_pair(
        self: AsyncCursorStoreAdapter,
        *,
        cursor: Any,
        checkpoint: StreamCheckpoint | None = None,
    ) -> Any:
        del self, cursor, checkpoint
        raise RuntimeError("local pair failed")

    async def fail_rewind(
        self: StreamingSourceSession,
        checkpoint: StreamCheckpoint,
    ) -> None:
        del self, checkpoint
        raise RuntimeError("source rewind failed")

    monkeypatch.setattr(StreamingSourceSession, "commit", source_commit_succeeds)
    monkeypatch.setattr(StreamingSourceSession, "rewind", fail_rewind)
    monkeypatch.setattr(AsyncCursorStoreAdapter, "commit_stream_progress", fail_local_pair)

    with pytest.raises(RuntimeError, match="local pair failed"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="rewind-failure",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
            registry=registry,
        )

    unresolved = cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        "rewind-failure",
    )
    assert unresolved is not None
    assert unresolved.metadata["frontier_intent"]["state"] == "unresolved"
    assert unresolved.metadata["frontier_committed"] is False
    assert cursor_store.find_latest_cursor("stream.jsonl", "rewind-failure") is None

    with pytest.raises(CursorStoreError, match="frontier intent"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="rewind-failure",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
            registry=registry,
        )


@pytest.mark.asyncio
async def test_stream_legacy_paused_nonzero_checkpoint_without_state_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy paused progress with offset/dedupe evidence cannot resume empty."""

    stream_path = tmp_path / "legacy-paused.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config("stream.jsonl", ConnectionConfig(url=stream_path.as_uri()))
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)

    async def legacy_lookup(
        self: AsyncCursorStoreAdapter,
        *args: Any,
        **kwargs: Any,
    ) -> StreamCheckpoint:
        del self, args, kwargs
        return StreamCheckpoint(
            checkpoint_id="stream.jsonl:legacy-paused:default:2",
            stream_id="stream.jsonl:legacy-paused:default",
            connector_id="stream.jsonl",
            dataset_id="legacy-paused",
            offset=2,
            lifecycle_state=StreamLifecycleState.PAUSED,
            dedupe_keys=("_message_id:m1",),
            metadata={"observed_offset": 2},
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(
        AsyncCursorStoreAdapter,
        "find_latest_stream_checkpoint",
        legacy_lookup,
    )
    with pytest.raises(CursorStoreError, match="operator state"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="legacy-paused",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            registry=registry,
        )


@pytest.mark.asyncio
async def test_stream_operator_state_without_max_event_time_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A state blob missing its ordering watermark is not a complete snapshot."""

    stream_path = tmp_path / "missing-watermark.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config("stream.jsonl", ConnectionConfig(url=stream_path.as_uri()))
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    policy = WindowPolicy(strategy=WindowStrategy.COUNT, size=2)
    operator_state = {
        "version": 1,
        "accumulator": StreamWindowAccumulator(policy).snapshot(),
    }

    async def incomplete_lookup(
        self: AsyncCursorStoreAdapter,
        *args: Any,
        **kwargs: Any,
    ) -> StreamCheckpoint:
        del self, args, kwargs
        return StreamCheckpoint(
            checkpoint_id="stream.jsonl:missing-watermark:default:0",
            stream_id="stream.jsonl:missing-watermark:default",
            connector_id="stream.jsonl",
            dataset_id="missing-watermark",
            metadata={
                "operator_state_required": True,
                "operator_state": operator_state,
                "frontier_committed": True,
            },
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(
        AsyncCursorStoreAdapter,
        "find_latest_stream_checkpoint",
        incomplete_lookup,
    )
    with pytest.raises(CursorStoreError, match="operator state"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="missing-watermark",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            registry=registry,
        )


def test_stream_window_refs_do_not_inherit_reused_dict_id() -> None:
    """A recycled dict id must not inherit provenance from its prior object."""

    accumulator = StreamWindowAccumulator(
        WindowPolicy(strategy=WindowStrategy.COUNT, size=2),
    )
    old_row = {"value": "old"}
    old_id = id(old_row)
    accumulator.add_rows_with_refs([old_row], ("chunk-old",))
    accumulator.flush()
    del old_row
    gc.collect()

    replacement: dict[str, Any] | None = None
    for _ in range(10_000):
        candidate = {"value": "replacement"}
        if id(candidate) == old_id:
            replacement = candidate
            break
        del candidate

    if replacement is None:
        # The probe is still meaningful on allocators that do not immediately
        # recycle this dict slot: the flushed object must have no stale entry.
        assert old_id not in accumulator._row_refs
        return

    assignments = accumulator.add_rows(
        [replacement, {"value": "second"}],
    )
    assert len(assignments) == 1
    assert accumulator._refs_for_assignment(assignments[0]) == ()


def test_stream_window_refs_bind_distinct_row_objects() -> None:
    """Contributor refs remain attached to each concrete dict object."""

    accumulator = StreamWindowAccumulator(
        WindowPolicy(strategy=WindowStrategy.COUNT, size=3),
    )
    first = {"value": "same"}
    second = {"value": "same"}
    assert first is not second
    accumulator.add_rows_with_refs([first], ("chunk-first",))
    accumulator.add_rows_with_refs([second], ("chunk-second",))

    first_entry = accumulator._row_refs[id(first)]
    second_entry = accumulator._row_refs[id(second)]
    assert first_entry.row is first
    assert second_entry.row is second
    assert first_entry.refs == ("chunk-first",)
    assert second_entry.refs == ("chunk-second",)


def test_stream_window_restore_rejects_empty_contributor_ref() -> None:
    """An empty lineage ref is corruption, not a value to silently discard."""

    accumulator = StreamWindowAccumulator(
        WindowPolicy(strategy=WindowStrategy.COUNT, size=2),
    )
    state = accumulator.snapshot()
    state["count_buffer"] = [
        {"row": {"value": 1}, "refs": ["chunk-valid", ""]},
    ]

    with pytest.raises(ValueError, match="empty"):
        accumulator.restore(state)


@pytest.mark.asyncio
async def test_iter_record_batches_keeps_event_loop_responsive():
    frame = pd.DataFrame([{"value": index} for index in range(5_000)])
    ticks = {"count": 0, "done": False}

    async def heartbeat():
        while not ticks["done"]:
            ticks["count"] += 1
            await asyncio.sleep(0)

    import asyncio

    task = asyncio.create_task(heartbeat())
    total_rows = 0
    async for batch in iter_record_batches(frame, batch_size=200):
        total_rows += len(batch)
    ticks["done"] = True
    await task

    assert total_rows == 5_000
    assert ticks["count"] > 0


@pytest.mark.asyncio
async def test_iter_record_batches_uses_shared_blocking_bridge(monkeypatch: pytest.MonkeyPatch):
    frame = pd.DataFrame([{"value": index} for index in range(512)])
    calls = {"count": 0}

    async def _fake_run_blocking_async(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del timeout_seconds
        calls["count"] += 1
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "polisyos.fabric.data_plane.streaming.run_blocking_async",
        _fake_run_blocking_async,
    )

    total_rows = 0
    async for batch in iter_record_batches(frame, batch_size=128):
        total_rows += len(batch)

    assert total_rows == 512
    assert calls["count"] == 4


@pytest.mark.asyncio
async def test_process_stream_dataset_propagates_backpressure(tmp_path: Path):
    stream_path = tmp_path / "backpressure.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","event_time":"2024-06-15T12:00:00+00:00","value":1}',
                '{"_message_id":"m2","event_time":"2024-06-15T12:00:10+00:00","value":2}',
                '{"_message_id":"m3","event_time":"2024-06-15T12:00:20+00:00","value":3}',
                '{"_message_id":"m4","event_time":"2024-06-15T12:00:30+00:00","value":4}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )

    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="backpressure",
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            max_buffered_rows=1,
            pause_seconds=0.0,
            window_policy=WindowPolicy(
                strategy=WindowStrategy.SESSION,
                size=300,
                session_gap_seconds=300,
                timestamp_field="event_time",
            ),
        ),
    )

    assert result.rows_emitted == 4
    assert result.backpressure_events >= 1
    assert len(result.window_refs) == 1


@pytest.mark.asyncio
async def test_process_stream_dataset_propagates_byte_backpressure(tmp_path: Path):
    stream_path = tmp_path / "byte-backpressure.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","event_time":"2024-06-15T12:00:00+00:00","value":"long"}',
                '{"_message_id":"m2","event_time":"2024-06-15T12:00:10+00:00","value":"long"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )

    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="byte-backpressure",
        store=FileSystemCAS(tmp_path / ".polisyos"),
        cursor_store=CursorStore(FileSystemCAS(tmp_path / ".polisyos")),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            max_buffered_rows=10_000,
            max_buffered_bytes=1,
            pause_seconds=0.0,
            window_policy=WindowPolicy(
                strategy=WindowStrategy.SESSION,
                size=300,
                session_gap_seconds=300,
                timestamp_field="event_time",
            ),
        ),
        registry=registry,
    )

    assert result.rows_emitted == 2
    assert result.backpressure_events >= 1


@pytest.mark.asyncio
async def test_process_stream_dataset_enforces_backpressure_event_budget(tmp_path: Path):
    stream_path = tmp_path / "backpressure-budget.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","event_time":"2024-06-15T12:00:00+00:00","value":1}',
                '{"_message_id":"m2","event_time":"2024-06-15T12:00:10+00:00","value":2}',
                '{"_message_id":"m3","event_time":"2024-06-15T12:00:20+00:00","value":3}',
                '{"_message_id":"m4","event_time":"2024-06-15T12:00:30+00:00","value":4}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )
    processing = stream_processing_contract().model_copy(
        update={
            "backpressure": BackpressurePolicy(max_backpressure_events=1),
        }
    )

    with pytest.raises(RuntimeError, match="backpressure event budget"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="backpressure-budget",
            store=FileSystemCAS(tmp_path / ".polisyos"),
            cursor_store=CursorStore(FileSystemCAS(tmp_path / ".polisyos")),
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(
                max_buffered_rows=1,
                pause_seconds=0.0,
                processing_contract=processing,
                window_policy=WindowPolicy(
                    strategy=WindowStrategy.SESSION,
                    size=300,
                    session_gap_seconds=300,
                    timestamp_field="event_time",
                ),
            ),
            registry=registry,
        )


@pytest.mark.asyncio
async def test_process_stream_dataset_uses_async_adapters_and_injected_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream_path = tmp_path / "async-stream.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","value":1}',
                '{"_message_id":"m2","value":2}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )

    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=2.0)
    async_cursor_store = AsyncCursorStoreAdapter(
        CursorStore(sync_store),
        timeout_seconds=2.0,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.streaming._default_connector_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )

    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="async-events",
        store=async_store,
        cursor_store=async_cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
        registry=registry,
    )

    assert result.rows_emitted == 2
    latest = await async_cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        "async-events",
    )
    assert latest is not None
    assert latest.lifecycle_state == StreamLifecycleState.CLOSED


@pytest.mark.asyncio
async def test_streaming_source_session_create_uses_registry_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream_path = tmp_path / "provider-stream.jsonl"
    stream_path.write_text('{"_message_id":"m1","value":1}\n', encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )

    monkeypatch.setattr(
        "polisyos.fabric.data_plane.streaming._default_connector_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )

    session = await StreamingSourceSession.create(
        connector_id="stream.jsonl",
        dataset_id="provider-events",
        registry_provider=lambda: registry,
    )
    try:
        chunk = await session.poll()
        assert chunk is not None
        assert chunk.row_count == 1
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_process_stream_dataset_persists_cdc_events_via_async_store_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream_path = tmp_path / "cdc-stream.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","value":1}',
                '{"_message_id":"m2","value":2,"new_field":"x"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )

    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=2.0)
    async_cursor_store = AsyncCursorStoreAdapter(
        CursorStore(sync_store),
        timeout_seconds=2.0,
    )
    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: Any, canon_spec: Any = None):
        seen_kinds.append(str(opts.kind))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.streaming.persist_cdc_schema_change_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("sync CDC persistence should not run on async path")
        ),
    )

    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="cdc-events",
        store=async_store,
        cursor_store=async_cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
        registry=registry,
    )

    assert result.rows_emitted == 2
    assert len(result.cdc_event_refs) == 1
    assert "fabric.cdc_schema_change" in seen_kinds
    cdc_payload = from_canonical_bytes(sync_store.get_bytes(result.cdc_event_refs[0].artifact_id))
    assert cdc_payload["compatibility"] == "compatible_additive"
    assert cdc_payload["handling_action"] == "accept"
    assert cdc_payload["processing"]["guarantee"] == "at_least_once_with_dedupe"


@pytest.mark.asyncio
async def test_process_stream_dataset_quarantines_incompatible_cdc_breaking_change(
    tmp_path: Path,
) -> None:
    stream_path = tmp_path / "breaking-cdc-stream.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","value":1}',
                '{"_message_id":"m2"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )

    store = FileSystemCAS(tmp_path / ".polisyos")
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="breaking-cdc-events",
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
        registry=registry,
    )

    assert result.rows_emitted == 1
    assert len(result.chunk_refs) == 1
    assert len(result.cdc_event_refs) == 1
    assert result.quarantined_rows == 1
    cdc_payload = from_canonical_bytes(store.get_bytes(result.cdc_event_refs[0].artifact_id))
    assert cdc_payload["compatibility"] == "incompatible_breaking"
    assert cdc_payload["handling_action"] == "quarantine"
    assert cdc_payload["processing"]["cdc_schema_changes"]["breaking_change_action"] == "quarantine"
    records = list_quarantine_records(
        store,
        source="stream:stream.jsonl:breaking-cdc-events",
        reason="cdc_schema_change_incompatible_breaking",
    )
    assert len(records) == 1
    assert records[0][1].context["cdc_event_ref"] == str(result.cdc_event_refs[0].artifact_id)
