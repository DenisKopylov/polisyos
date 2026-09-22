from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.pool import ConnectionPool, PoolClosedError, PoolConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import AsyncCursorStoreAdapter, CursorStore
from polisyos.fabric.data_plane.quarantine import list_quarantine_records
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
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

    await session.close()

    assert session._closed is True
    assert session.handle is None
    assert connector.disconnect_calls == [failed_handle_id] * 3


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
