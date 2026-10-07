"""Independent registry-owner oracle across an intervening fresh stream."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamRuntimeOptions,
    process_stream_dataset,
)


class _ObservedEventStream(EventStreamConnector):
    """Use the real JSONL connector while recording physical disconnects."""

    def __init__(self) -> None:
        self.disconnect_failures = 0
        self.connect_handles: list[ConnectionHandle] = []
        self.disconnect_attempts: list[ConnectionHandle] = []
        self.successful_disconnects: list[ConnectionHandle] = []
        self.stream_reads = 0

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = await super().connect(config)
        self.connect_handles.append(handle)
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnect_attempts.append(handle)
        if self.disconnect_failures:
            self.disconnect_failures -= 1
            raise RuntimeError("controlled physical disconnect failure")
        await super().disconnect(handle)
        self.successful_disconnects.append(handle)

    async def fetch_stream(self, handle: ConnectionHandle, request: Any):
        self.stream_reads += 1
        async for chunk in super().fetch_stream(handle, request):
            yield chunk


def _accept_rows(batch: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    return [dict(row) for row in batch], [], 0


def _one_chunk(store: FileSystemCAS, dataset_id: str) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    for artifact_id in store.iter_artifact_ids():
        manifest = store.get_manifest(str(artifact_id))
        if manifest.kind != "fabric.stream_chunk":
            continue
        payload = from_canonical_bytes(store.get_bytes(str(artifact_id)))
        if payload.get("dataset_id") == dataset_id:
            chunks.append(payload)
    assert len(chunks) == 1, "the fresh stream must persist exactly one real chunk"
    return chunks[0]


@pytest.mark.asyncio
async def test_fresh_stream_does_not_replace_older_pending_cleanup_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful new session leaves the failed session's exact owner retryable."""
    old_source = tmp_path / "old-events.jsonl"
    old_source.write_text('{"_message_id":"old-event","value":1}\n', encoding="utf-8")
    fresh_source = tmp_path / "fresh-events.jsonl"
    fresh_row = {"_message_id": "fresh-event", "value": 2}
    fresh_source.write_text(json.dumps(fresh_row) + "\n", encoding="utf-8")

    old_config = ConnectionConfig(
        url=old_source.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
        max_connections=1,
    )
    fresh_config = ConnectionConfig(
        url=fresh_source.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
        max_connections=1,
    )
    connector = _ObservedEventStream()
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

    monkeypatch.setattr(
        StreamingSourceSession,
        "create",
        classmethod(capture_session),
    )

    primary_error = RuntimeError("primary sanitizer failure")

    def fail_sanitization(batch: Any, **kwargs: Any):
        del batch, kwargs
        raise primary_error

    cas_root = tmp_path / "cas"
    try:
        with pytest.raises(RuntimeError, match="primary sanitizer failure") as caught:
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id="old-owner",
                store=FileSystemCAS(cas_root),
                cursor_store=CursorStore(FileSystemCAS(cas_root)),
                sanitize_rows=fail_sanitization,
                runtime_options=StreamRuntimeOptions(batch_size=1),
                connection_config=old_config,
                registry=registry,
            )

        assert caught.value is primary_error
        assert len(sessions) == 1
        old_session = sessions[0]
        assert connector.stream_reads == 1
        assert len(connector.connect_handles) == 1
        old_handle = connector.connect_handles[0]
        assert connector.disconnect_attempts == [old_handle]
        assert connector.successful_disconnects == []

        owners_before_fresh = tuple(registry._pending_startup_cleanup.values())
        assert len(owners_before_fresh) == 1, "registry must retain the old cleanup obligation"
        old_connector_id, old_pool = owners_before_fresh[0]
        assert old_connector_id == registry.get_entry("stream.jsonl").fqid
        assert old_pool is old_session.pool
        assert old_pool._pending_cleanup[old_handle.session_id].handle is old_handle
        assert old_pool._pending_cleanup[old_handle.session_id].pending_permit is False
        assert old_pool._semaphore._value == 1

        # Let a new private pool complete while the old physical owner remains
        # unresolved in the registry. This crosses the boundary a retry-only
        # test does not exercise.
        connector.disconnect_failures = 0
        fresh_result = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="fresh-owner",
            store=FileSystemCAS(cas_root),
            cursor_store=CursorStore(FileSystemCAS(cas_root)),
            sanitize_rows=_accept_rows,
            runtime_options=StreamRuntimeOptions(batch_size=1),
            connection_config=fresh_config,
            registry=registry,
        )

        assert len(sessions) == 2
        fresh_session = sessions[1]
        assert fresh_session.pool is not old_pool
        assert connector.stream_reads == 2
        assert len(connector.connect_handles) == 2
        fresh_handle = connector.connect_handles[1]
        assert fresh_handle is not old_handle
        assert connector.disconnect_attempts == [old_handle, fresh_handle]
        assert connector.successful_disconnects == [fresh_handle]

        assert fresh_result.rows_emitted == 1
        assert fresh_result.final_checkpoint is not None
        assert fresh_result.final_checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
        fresh_store = FileSystemCAS(cas_root)
        assert _one_chunk(fresh_store, "fresh-owner")["data"] == [fresh_row]
        latest_fresh = CursorStore(fresh_store).find_latest_stream_checkpoint(
            "stream.jsonl",
            "fresh-owner",
        )
        assert latest_fresh is not None
        assert latest_fresh.model_dump(mode="json") == fresh_result.final_checkpoint.model_dump(
            mode="json"
        )

        owners_after_fresh = tuple(registry._pending_startup_cleanup.values())
        assert owners_after_fresh == ((old_connector_id, old_pool),), (
            "completing a fresh session must not erase or replace the prior owner"
        )
        assert old_pool._pending_cleanup[old_handle.session_id].handle is old_handle
        assert old_pool._pending_cleanup[old_handle.session_id].pending_permit is False
        assert old_pool._semaphore._value == 1
        assert old_handle not in connector.successful_disconnects

        await registry.shutdown_async()
        assert connector.disconnect_attempts == [old_handle, fresh_handle, old_handle]
        assert connector.successful_disconnects == [fresh_handle, old_handle]
        assert registry._pending_startup_cleanup == {}
        assert old_pool._pending_cleanup == {}
        assert old_pool._semaphore._value == 1
    finally:
        connector.disconnect_failures = 0
        for session in sessions:
            await session.pool.close_all()
        await registry.shutdown_async()
