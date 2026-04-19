from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import AsyncCursorStoreAdapter, CursorStore
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamRuntimeOptions,
    iter_record_batches,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy

if TYPE_CHECKING:
    from pathlib import Path


def _valid_rows(batch, **kwargs):
    del kwargs
    return [dict(row) for row in batch if isinstance(row, dict)], [], 0


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
