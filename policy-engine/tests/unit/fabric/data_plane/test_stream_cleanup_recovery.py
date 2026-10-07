"""Behavioral checks for streamed-source failure cleanup ownership."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import polisyos.fabric.connectors.sources.event_stream as event_stream
import polisyos.fabric.data_plane.streaming as streaming
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane.cursor_store import CursorStore, CursorStoreError
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamRuntimeOptions,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy


class _ProcessDeath(BaseException):
    """Model process loss without entering the runtime's Exception recovery path."""


def _accept_rows(batch: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    return [dict(row) for row in batch], [], 0


class _DisconnectOnceEventStream(EventStreamConnector):
    """Use the real JSONL reader while exposing one physical disconnect fault."""

    def __init__(self) -> None:
        self.disconnect_failures = 1
        self.connect_handles: list[ConnectionHandle] = []
        self.disconnect_handles: list[ConnectionHandle] = []
        self.stream_reads = 0

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = await super().connect(config)
        self.connect_handles.append(handle)
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnect_handles.append(handle)
        if self.disconnect_failures:
            self.disconnect_failures -= 1
            raise RuntimeError("controlled physical disconnect failure")
        await super().disconnect(handle)

    async def fetch_stream(self, handle: ConnectionHandle, request: Any):
        self.stream_reads += 1
        async for chunk in super().fetch_stream(handle, request):
            yield chunk


@pytest.mark.parametrize(
    ("failure_type", "failure_message"),
    [
        (RuntimeError, "primary sanitizer failure"),
        (asyncio.CancelledError, "primary stream cancellation"),
    ],
)
@pytest.mark.asyncio
async def test_process_failure_keeps_real_private_pool_reachable_for_same_handle_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_type: type[BaseException],
    failure_message: str,
) -> None:
    """A cleanup fault cannot mask the primary error or orphan its physical handle."""
    dataset_id = "cleanup-recovery"
    source_path = tmp_path / f"{dataset_id}.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(
        url=source_path.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
        max_connections=1,
    )
    connector = _DisconnectOnceEventStream()
    connector.disconnect_failures = 2
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    sessions: list[StreamingSourceSession] = []
    original_create = StreamingSourceSession.create

    async def _capture_created_session(
        cls: type[StreamingSourceSession],
        **kwargs: Any,
    ) -> StreamingSourceSession:
        session = await original_create(**kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(
        StreamingSourceSession,
        "create",
        classmethod(_capture_created_session),
    )

    def _fail_sanitization(batch: Any, **kwargs: Any):
        del batch, kwargs
        raise primary_error

    store = FileSystemCAS(tmp_path / "cas")
    primary_error = failure_type(failure_message)
    try:
        with pytest.raises(failure_type, match=failure_message) as caught:
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                store=store,
                cursor_store=CursorStore(store),
                sanitize_rows=_fail_sanitization,
                runtime_options=StreamRuntimeOptions(batch_size=1),
                registry=registry,
            )

        assert caught.value is primary_error
        assert len(sessions) == 1
        session = sessions[0]
        assert connector.stream_reads == 1
        assert len(connector.connect_handles) == 1
        handle = connector.connect_handles[0]
        assert connector.disconnect_handles == [handle]
        assert any(
            "stream session final cleanup failed" in note
            and "Connection cleanup remains pending for the closed pool" in note
            for note in getattr(caught.value, "__notes__", ())
        )

        pending_owners = tuple(registry._pending_startup_cleanup.values())
        assert len(pending_owners) == 1, "registry must retain the failed private stream pool"
        owner_connector_id, owner_pool = pending_owners[0]
        assert owner_connector_id == registry.get_entry("stream.jsonl").fqid
        assert owner_pool is session.pool
        assert owner_pool._pending_cleanup[handle.session_id].handle is handle
        assert owner_pool._pending_cleanup[handle.session_id].pending_permit is False
        assert owner_pool._semaphore._value == 1

        # A failed registry retry remains owned and retryable; the same physical
        # handle and the single released permit remain intact until disconnect.
        with pytest.raises(RuntimeError, match="Connection cleanup remains pending"):
            await registry.shutdown_async()
        retry_owner = tuple(registry._pending_startup_cleanup.values())
        assert retry_owner == ((owner_connector_id, owner_pool),)
        assert owner_pool._pending_cleanup[handle.session_id].handle is handle
        assert owner_pool._pending_cleanup[handle.session_id].pending_permit is False
        assert owner_pool._semaphore._value == 1

        # Only after the verdicts, let the production registry finish cleanup.
        connector.disconnect_failures = 0
        await registry.shutdown_async()
        assert connector.disconnect_handles == [handle, handle, handle]
        assert all(disconnected_handle is handle for disconnected_handle in connector.disconnect_handles)
        assert registry._pending_startup_cleanup == {}
        assert owner_pool._pending_cleanup == {}
        assert owner_pool._semaphore._value == 1
    finally:
        # The baseline is intentionally red on registry retention. Clean the
        # captured owner only after the semantic assertions have run.
        if sessions:
            connector.disconnect_failures = 0
            await sessions[0].pool.close_all()
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_successful_stream_surfaces_final_cleanup_failure_and_registry_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A committed stream remains readable when only final physical cleanup fails."""
    dataset_id = "cleanup-after-success"
    source_path = tmp_path / f"{dataset_id}.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(
        url=source_path.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
        max_connections=1,
    )
    connector = _DisconnectOnceEventStream()
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    sessions: list[StreamingSourceSession] = []
    original_create = StreamingSourceSession.create

    async def _capture_created_session(
        cls: type[StreamingSourceSession],
        **kwargs: Any,
    ) -> StreamingSourceSession:
        session = await original_create(**kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(
        StreamingSourceSession,
        "create",
        classmethod(_capture_created_session),
    )
    store = FileSystemCAS(tmp_path / "cas")

    try:
        with pytest.raises(RuntimeError, match="Connection cleanup remains pending"):
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                store=store,
                cursor_store=CursorStore(store),
                sanitize_rows=_accept_rows,
                runtime_options=StreamRuntimeOptions(batch_size=1),
                registry=registry,
            )

        latest = CursorStore(FileSystemCAS(tmp_path / "cas")).find_latest_stream_checkpoint(
            "stream.jsonl",
            dataset_id,
        )
        assert latest is not None
        assert latest.lifecycle_state == StreamLifecycleState.CLOSED
        assert latest.metadata["frontier_intent"]["state"] == "committed"
        assert connector.stream_reads == 1
        handle = connector.connect_handles[0]
        assert connector.disconnect_handles == [handle]

        retained_owners = tuple(registry._pending_startup_cleanup.values())
        assert len(retained_owners) == 1
        _connector_id, pool = retained_owners[0]
        assert pool._pending_cleanup[handle.session_id].handle is handle
        assert pool._pending_cleanup[handle.session_id].pending_permit is False
        assert pool._semaphore._value == 1

        connector.disconnect_failures = 0
        await registry.shutdown_async()
        assert connector.disconnect_handles == [handle, handle]
        assert connector.disconnect_handles[1] is handle
        assert registry._pending_startup_cleanup == {}
        assert pool._pending_cleanup == {}
        assert pool._semaphore._value == 1
    finally:
        connector.disconnect_failures = 0
        if sessions:
            await sessions[0].pool.close_all()
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_actual_task_cancellation_after_real_source_yield_retains_cleanup_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task.cancel after an actual JSONL yield preserves the handle for registry retry."""
    dataset_id = "actual-task-cancel"
    source_path = tmp_path / f"{dataset_id}.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(
        url=source_path.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
        max_connections=1,
    )
    connector = _DisconnectOnceEventStream()
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    sessions: list[StreamingSourceSession] = []
    original_create = StreamingSourceSession.create
    original_poll = StreamingSourceSession.poll
    first_source_yield = asyncio.Event()
    release_poll = asyncio.Event()

    async def _capture_created_session(
        cls: type[StreamingSourceSession],
        **kwargs: Any,
    ) -> StreamingSourceSession:
        session = await original_create(**kwargs)
        sessions.append(session)
        return session

    async def _pause_after_real_yield(
        session: StreamingSourceSession,
    ):
        chunk = await original_poll(session)
        if chunk is not None and not first_source_yield.is_set():
            first_source_yield.set()
            await release_poll.wait()
        return chunk

    monkeypatch.setattr(
        StreamingSourceSession,
        "create",
        classmethod(_capture_created_session),
    )
    monkeypatch.setattr(StreamingSourceSession, "poll", _pause_after_real_yield)

    task = asyncio.create_task(
        process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=FileSystemCAS(tmp_path / "cas"),
            cursor_store=CursorStore(FileSystemCAS(tmp_path / "cas")),
            sanitize_rows=_accept_rows,
            runtime_options=StreamRuntimeOptions(batch_size=1),
            registry=registry,
        )
    )
    try:
        await asyncio.wait_for(first_source_yield.wait(), timeout=5)
        assert connector.stream_reads == 1
        assert len(connector.connect_handles) == 1
        handle = connector.connect_handles[0]
        assert sessions[0].handle is handle

        assert task.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task

        assert task.cancelled()
        assert any(
            "stream session final cleanup failed" in note
            and "Connection cleanup remains pending for the closed pool" in note
            for note in getattr(caught.value, "__notes__", ())
        )
        assert connector.disconnect_handles == [handle]
        retained_owners = tuple(registry._pending_startup_cleanup.values())
        assert len(retained_owners) == 1
        _connector_id, pool = retained_owners[0]
        assert pool is sessions[0].pool
        assert pool._pending_cleanup[handle.session_id].handle is handle
        assert pool._pending_cleanup[handle.session_id].pending_permit is False
        assert pool._semaphore._value == 1

        connector.disconnect_failures = 0
        await registry.shutdown_async()
        assert connector.disconnect_handles == [handle, handle]
        assert connector.disconnect_handles[1] is handle
        assert registry._pending_startup_cleanup == {}
        assert pool._pending_cleanup == {}
        assert pool._semaphore._value == 1
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        connector.disconnect_failures = 0
        if sessions:
            await sessions[0].pool.close_all()
        await registry.shutdown_async()


def _raw_stream_fixture() -> tuple[bytes, list[dict[str, Any]], list[bytes]]:
    """Build a source whose byte lines define the independent row/order oracle."""
    expected_rows = [
        {"_message_id": "a", "event_id": "a", "value": 1},
        {"_message_id": "b", "event_id": "b", "value": 2},
        {"_message_id": "c", "event_id": "c", "value": 3},
    ]
    raw_lines = [
        b" \t" + json.dumps(row, sort_keys=True).encode("utf-8") + b" \t\r\n"
        for row in expected_rows
    ]
    parsed_rows = [json.loads(line.strip().decode("utf-8")) for line in raw_lines]
    assert parsed_rows == expected_rows
    return b"".join(raw_lines), expected_rows, raw_lines


def _dataset_artifacts(
    store: FileSystemCAS,
    *,
    kind: str,
    dataset_id: str,
) -> list[tuple[str, dict[str, Any], Any]]:
    """Read real CAS artifacts of one kind for the fixture dataset."""
    artifacts: list[tuple[str, dict[str, Any], Any]] = []
    for artifact_id in store.iter_artifact_ids():
        manifest = store.get_manifest(artifact_id)
        if manifest.kind != kind:
            continue
        payload = from_canonical_bytes(store.get_bytes(str(artifact_id)))
        if payload.get("dataset_id") == dataset_id:
            artifacts.append((str(artifact_id), payload, manifest))
    return artifacts


@pytest.mark.parametrize("crash_phase", ["before_commit", "after_commit"])
@pytest.mark.asyncio
async def test_frontier_crash_reopen_matches_raw_rows_and_ordered_window_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_phase: str,
) -> None:
    """A crash leaves unresolved state blocked or resumes a committed pair exactly."""
    dataset_id = f"frontier-crash-{crash_phase}"
    source_bytes, expected_rows, raw_lines = _raw_stream_fixture()
    source_path = tmp_path / f"{dataset_id}.jsonl"
    source_path.write_bytes(source_bytes)
    config = ConnectionConfig(
        url=source_path.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
        max_connections=1,
    )
    connector = _DisconnectOnceEventStream()
    connector.disconnect_failures = 0
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    cas_root = tmp_path / f"{dataset_id}-cas"
    source_reads: list[bytes] = []
    original_read = event_stream.read_location_bytes
    original_commit = streaming._commit_stream_frontier
    injected = False

    async def _capture_source_read(*args: Any, **kwargs: Any):
        payload, headers = await original_read(*args, **kwargs)
        source_reads.append(bytes(payload))
        return payload, headers

    async def _crash_around_commit(**kwargs: Any):
        nonlocal injected
        if not injected and crash_phase == "before_commit":
            injected = True
            raise _ProcessDeath("crash before frontier source/local commit")
        committed = await original_commit(**kwargs)
        if not injected and crash_phase == "after_commit":
            injected = True
            raise _ProcessDeath("crash after committed frontier persistence")
        return committed

    monkeypatch.setattr(event_stream, "read_location_bytes", _capture_source_read)
    monkeypatch.setattr(streaming, "_commit_stream_frontier", _crash_around_commit)
    options = StreamRuntimeOptions(
        checkpoint_every_chunks=1,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=2),
    )
    first_store = FileSystemCAS(cas_root)
    with pytest.raises(_ProcessDeath, match="crash"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=first_store,
            cursor_store=CursorStore(first_store),
            sanitize_rows=lambda batch, **kwargs: ([dict(row) for row in batch], [], 0),
            runtime_options=options,
            registry=registry,
        )

    monkeypatch.setattr(streaming, "_commit_stream_frontier", original_commit)
    crash_store = FileSystemCAS(cas_root)
    crash_cursor_store = CursorStore(crash_store)
    crash_checkpoint = crash_cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    assert crash_checkpoint is not None
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    assert source_reads
    assert all(hashlib.sha256(payload).hexdigest() == source_digest for payload in source_reads)
    assert connector.stream_reads == 1

    if crash_phase == "before_commit":
        assert crash_checkpoint.metadata["frontier_intent"]["state"] == "prepared"
        assert crash_cursor_store.find_latest_cursor("stream.jsonl", dataset_id) is None
        partial_chunks = _dataset_artifacts(
            crash_store,
            kind="fabric.stream_chunk",
            dataset_id=dataset_id,
        )
        assert len(partial_chunks) == 1
        assert partial_chunks[0][1]["data"] == [
            json.loads(raw_lines[0].strip().decode("utf-8"))
        ]
        before_ids = set(map(str, crash_store.iter_artifact_ids()))
        checkpoint_before_retry = crash_checkpoint.model_dump(mode="json")
        reads_before_retry = connector.stream_reads

        retry_store = FileSystemCAS(cas_root)
        with pytest.raises(CursorStoreError, match="unresolved stream frontier intent"):
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                store=retry_store,
                cursor_store=CursorStore(retry_store),
                sanitize_rows=lambda batch, **kwargs: ([dict(row) for row in batch], [], 0),
                runtime_options=options,
                registry=registry,
            )

        unchanged_store = FileSystemCAS(cas_root)
        unchanged_cursors = CursorStore(unchanged_store)
        unchanged_checkpoint = unchanged_cursors.find_latest_stream_checkpoint(
            "stream.jsonl",
            dataset_id,
        )
        assert unchanged_checkpoint is not None
        assert unchanged_checkpoint.model_dump(mode="json") == checkpoint_before_retry
        assert unchanged_cursors.find_latest_cursor("stream.jsonl", dataset_id) is None
        assert set(map(str, unchanged_store.iter_artifact_ids())) == before_ids
        assert connector.stream_reads == reads_before_retry
        assert _dataset_artifacts(
            unchanged_store,
            kind="fabric.stream_window",
            dataset_id=dataset_id,
        ) == []
        await registry.shutdown_async()
        return

    assert crash_checkpoint.metadata["frontier_intent"]["state"] == "committed"
    crash_cursor = crash_cursor_store.find_latest_cursor("stream.jsonl", dataset_id)
    assert crash_cursor is not None
    assert crash_cursor.watermark_value == "0"

    resumed_store = FileSystemCAS(cas_root)
    resumed_cursors = CursorStore(resumed_store)
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=resumed_store,
        cursor_store=resumed_cursors,
        sanitize_rows=lambda batch, **kwargs: ([dict(row) for row in batch], [], 0),
        runtime_options=options,
        registry=registry,
    )

    assert connector.stream_reads == 2
    assert all(hashlib.sha256(payload).hexdigest() == source_digest for payload in source_reads)
    assert len(source_reads) >= 2

    chunk_artifacts = _dataset_artifacts(
        resumed_store,
        kind="fabric.stream_chunk",
        dataset_id=dataset_id,
    )
    chunk_artifacts.sort(key=lambda item: int(item[1]["chunk_index"]))
    assert [int(payload["chunk_index"]) for _ref, payload, _manifest in chunk_artifacts] == [
        0,
        1,
        2,
    ]
    assert [row for _ref, payload, _manifest in chunk_artifacts for row in payload["data"]] == (
        expected_rows
    )
    for (_ref, payload, _manifest), raw_line, expected_row in zip(
        chunk_artifacts,
        raw_lines,
        expected_rows,
        strict=True,
    ):
        assert payload["data"] == [json.loads(raw_line.strip().decode("utf-8"))]
        assert payload["data"] == [expected_row]

    chunk_by_message = {
        str(row["_message_id"]): ref
        for ref, payload, _manifest in chunk_artifacts
        for row in payload["data"]
    }
    window_artifacts = _dataset_artifacts(
        resumed_store,
        kind="fabric.stream_window",
        dataset_id=dataset_id,
    )
    window_artifacts.sort(key=lambda item: int(item[1]["ordinal"]))
    assert [
        [str(row["_message_id"]) for row in payload["data"]]
        for _ref, payload, _manifest in window_artifacts
    ] == [["a", "b"], ["c"]]
    for _ref, payload, manifest in window_artifacts:
        row_ids = [str(row["_message_id"]) for row in payload["data"]]
        expected_inputs = tuple(dict.fromkeys(chunk_by_message[row_id] for row_id in row_ids))
        assert tuple(str(item.artifact_id) for item in manifest.inputs) == expected_inputs
        assert tuple(payload["lineage"]["contributor_chunk_refs"]) == expected_inputs

    assert result.final_checkpoint is not None
    assert result.final_checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    assert result.final_checkpoint.offset == 2
    assert result.final_checkpoint.metadata["frontier_intent"]["state"] == "committed"
    latest_checkpoint = CursorStore(FileSystemCAS(cas_root)).find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    assert latest_checkpoint is not None
    assert latest_checkpoint.model_dump(mode="json") == result.final_checkpoint.model_dump(
        mode="json"
    )
    latest_cursor = CursorStore(FileSystemCAS(cas_root)).find_latest_cursor(
        "stream.jsonl",
        dataset_id,
    )
    assert latest_cursor is not None
    assert latest_cursor.watermark_value == "2"
    await registry.shutdown_async()
