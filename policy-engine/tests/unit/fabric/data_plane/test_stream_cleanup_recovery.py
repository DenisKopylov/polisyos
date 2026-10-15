"""Behavioral checks for streamed-source failure cleanup ownership."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

import polisyos.fabric.connectors.sources.event_stream as event_stream
import polisyos.fabric.data_plane.streaming as streaming
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    SourceConnectorValue,
)
from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.connectors.types import DataChunk
from polisyos.fabric.data_plane.cursor_store import CursorStore, CursorStoreError
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamOwnerConflictError,
    StreamRuntimeOptions,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy


class _ProcessDeath(BaseException):
    """Model process loss without entering the runtime's Exception recovery path."""


def _accept_rows(batch: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    return [dict(row) for row in batch], [], 0


@pytest.mark.asyncio
async def test_streaming_session_accepts_awaitable_iterator_from_connector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The stream adapter awaits coroutine producers without wrapping generators."""
    connector = EventStreamConnector()

    async def coroutine_stream(
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[list[dict[str, int]]]]:
        del handle, request

        async def chunks() -> AsyncIterator[DataChunk[list[dict[str, int]]]]:
            yield DataChunk(
                data=[{"value": 7}],
                chunk_index=0,
                row_count=1,
                is_first=True,
                is_last=True,
            )

        return chunks()

    monkeypatch.setattr(connector, "fetch_stream", coroutine_stream)
    source_path = tmp_path / "awaitable-producer.jsonl"
    source_path.write_text('{"value":0}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)

    session = await StreamingSourceSession.create(
        connector_id="stream.jsonl",
        dataset_id="awaitable-producer",
        registry=registry,
    )
    chunk = await session.poll()
    assert chunk is not None
    assert chunk.data == [{"value": 7}]
    await session.close()


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


class _GatedStreamStartup(_DisconnectOnceEventStream):
    """Block the first subscription so registry teardown can race startup."""

    def __init__(self) -> None:
        super().__init__()
        self.disconnect_failures = 0
        self.startup_entered = asyncio.Event()
        self.startup_cancelled = asyncio.Event()
        self.release_startup = asyncio.Event()
        self.blocked_handle: ConnectionHandle | None = None
        self.handle_was_live_when_cancelled = False

    async def subscribe_stream(self, handle: ConnectionHandle, request: Any) -> object:
        del request
        if self.blocked_handle is None:
            self.blocked_handle = handle
            self.startup_entered.set()
            try:
                await self.release_startup.wait()
            except asyncio.CancelledError:
                self.handle_was_live_when_cancelled = handle not in self.disconnect_handles
                self.startup_cancelled.set()
                raise
        return handle.session_id

    async def poll_stream(
        self,
        handle: ConnectionHandle,
        subscription: object,
    ) -> DataChunk[list[dict[str, Any]]]:
        assert subscription == handle.session_id
        return DataChunk(
            data=[{"_message_id": handle.session_id, "value": 1}],
            chunk_index=0,
            row_count=1,
            is_first=True,
            is_last=True,
        )


class _CancellationResistantStreamStartup(_GatedStreamStartup):
    """Model a callback that observes cancellation but retains its handle until released."""

    async def subscribe_stream(self, handle: ConnectionHandle, request: Any) -> object:
        del request
        if self.blocked_handle is None:
            self.blocked_handle = handle
            self.startup_entered.set()
            try:
                await self.release_startup.wait()
            except asyncio.CancelledError:
                self.handle_was_live_when_cancelled = handle not in self.disconnect_handles
                self.startup_cancelled.set()
                await self.release_startup.wait()
        return handle.session_id


class _CrossLoopGatedStreamStartup(_DisconnectOnceEventStream):
    """Expose thread-safe markers while subscription runs on another event loop."""

    def __init__(self) -> None:
        super().__init__()
        self.disconnect_failures = 0
        self.startup_entered = threading.Event()
        self.startup_cancelled = threading.Event()
        self.blocked_handle: ConnectionHandle | None = None
        self.handle_was_live_when_cancelled = False

    async def subscribe_stream(self, handle: ConnectionHandle, request: Any) -> object:
        del request
        self.blocked_handle = handle
        self.startup_entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.handle_was_live_when_cancelled = handle not in self.disconnect_handles
            self.startup_cancelled.set()
            raise
        return handle.session_id


class _SelfUnregisteringStreamStartup(_DisconnectOnceEventStream):
    """Exercise lifecycle re-entry from the startup task that owns the ticket."""

    def __init__(self) -> None:
        super().__init__()
        self.disconnect_failures = 0
        self.registry: ConnectorRegistry | None = None

    async def subscribe_stream(self, handle: ConnectionHandle, request: Any) -> object:
        del request
        assert self.registry is not None
        await self.registry.unregister_async("stream.jsonl")
        return handle.session_id


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
        assert all(
            disconnected_handle is handle for disconnected_handle in connector.disconnect_handles
        )
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
        assert partial_chunks[0][1]["data"] == [json.loads(raw_lines[0].strip().decode("utf-8"))]
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
        assert (
            _dataset_artifacts(
                unchanged_store,
                kind="fabric.stream_window",
                dataset_id=dataset_id,
            )
            == []
        )
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


@pytest.mark.asyncio
async def test_registry_stream_owner_admission_has_one_winner_and_keyed_scope(
    tmp_path: Path,
) -> None:
    """Only one private pool owns a logical key; other keys and recovery remain usable."""
    dataset_id = "concurrent-stream-owner"
    source_path = tmp_path / f"{dataset_id}.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(
        url=source_path.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
        max_connections=1,
    )
    connector = _DisconnectOnceEventStream()
    connector.disconnect_failures = 0
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    created: list[StreamingSourceSession] = []
    separate_registry: ConnectorRegistry | None = None
    separate_registry_session: StreamingSourceSession | None = None

    async def open_session(*, dataset: str, partition: str = "default") -> StreamingSourceSession:
        session = await StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id=dataset,
            connection_config=config,
            partition_key=partition,
            registry=registry,
        )
        created.append(session)
        return session

    try:
        first_task = asyncio.create_task(open_session(dataset=dataset_id))
        second_task = asyncio.create_task(open_session(dataset=dataset_id))
        first_result, second_result = await asyncio.gather(
            first_task,
            second_task,
            return_exceptions=True,
        )
        assert isinstance(first_result, StreamingSourceSession)
        created.append(first_result)
        assert isinstance(second_result, StreamOwnerConflictError)
        assert second_result.connector_id == "stream.jsonl"
        assert second_result.dataset_id == dataset_id
        assert second_result.partition_key == "default"
        assert len(connector.connect_handles) == 1

        # Exact key composition includes dataset and partition. These sibling
        # scopes may connect while the first owner's handle remains live.
        other_dataset = await open_session(dataset=f"{dataset_id}-other")
        other_partition = await open_session(dataset=dataset_id, partition="other-partition")
        assert other_dataset.handle is not None
        assert other_partition.handle is not None
        assert len(connector.connect_handles) == 3

        # The contract is registry-local. An independently injected registry
        # has its own lease domain and is not a cross-process/global lock.
        separate_registry = ConnectorRegistry()
        separate_registry.register(EventStreamConnector, config=config, factory=lambda: connector)
        separate_registry_session = await StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            connection_config=config,
            registry=separate_registry,
        )
        assert separate_registry_session.handle is not None
        assert separate_registry_session.handle is not first_result.handle
        assert len(connector.connect_handles) == 4
        await separate_registry_session.close()
        await separate_registry.shutdown_async()

        await first_result.close()
        await other_dataset.close()
        await other_partition.close()
        assert len(connector.disconnect_handles) == 4
        assert {handle.session_id for handle in connector.disconnect_handles} == {
            handle.session_id for handle in connector.connect_handles
        }

        active_during_shutdown = await open_session(dataset=dataset_id)
        shutdown_handle = active_during_shutdown.handle
        assert shutdown_handle is not None
        await registry.shutdown_async()
        assert shutdown_handle in connector.disconnect_handles
        assert registry._stream_owner_leases == {}
        assert registry._pending_startup_cleanup == {}

        cas_root = tmp_path / "reopened-cas"
        fresh_result = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=FileSystemCAS(cas_root),
            cursor_store=CursorStore(FileSystemCAS(cas_root)),
            sanitize_rows=_accept_rows,
            runtime_options=StreamRuntimeOptions(batch_size=1),
            connection_config=config,
            registry=registry,
        )
        assert fresh_result.rows_emitted == 1
        latest = CursorStore(FileSystemCAS(cas_root)).find_latest_stream_checkpoint(
            "stream.jsonl",
            dataset_id,
        )
        assert latest is not None
        final_checkpoint = fresh_result.final_checkpoint
        assert final_checkpoint is not None
        assert latest.model_dump(mode="json") == final_checkpoint.model_dump(mode="json")
        assert connector.stream_reads == 1

        active_during_unregister = await open_session(dataset=f"{dataset_id}-unregister")
        unregister_handle = active_during_unregister.handle
        assert unregister_handle is not None
        assert await registry.unregister_async("stream.jsonl") is True
        assert unregister_handle in connector.disconnect_handles
        assert registry._stream_owner_leases == {}
        assert registry._pending_startup_cleanup == {}
    finally:
        if separate_registry_session is not None and not separate_registry_session.pool.is_closed:
            await separate_registry_session.close()
        if separate_registry is not None:
            await separate_registry.shutdown_async()
        for session in created:
            if not session.pool.is_closed:
                await session.close()
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_factory_owner_rejects_registry_bearing_direct_session_before_acquire(
    tmp_path: Path,
) -> None:
    """Direct construction must share the factory's registry admission boundary."""
    dataset_id = "factory-direct-owner"
    source_path = tmp_path / f"{dataset_id}.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    connector = _DisconnectOnceEventStream()
    connector.disconnect_failures = 0
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    owner: StreamingSourceSession | None = None
    direct: StreamingSourceSession | None = None
    direct_pool: ConnectionPool[SourceConnectorValue[object]] | None = None

    try:
        owner = await StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            connection_config=config,
            registry=registry,
        )
        direct_pool = ConnectionPool(
            connector_factory=lambda: connector,
            config=config,
            pool_config=PoolConfig(max_size=1, validate_on_acquire=False),
            pool_id="direct-session-owner-test",
        )

        with pytest.raises(StreamOwnerConflictError):
            direct = StreamingSourceSession(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                pool=direct_pool,
                request=FetchRequest(dataset_id=dataset_id),
                registry=registry,
            )
            await direct.subscribe()

        assert len(connector.connect_handles) == 1
        await owner.close()

        direct = StreamingSourceSession(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            pool=direct_pool,
            request=FetchRequest(dataset_id=dataset_id),
            registry=registry,
        )
        await direct.subscribe()
        assert len(connector.connect_handles) == 2
        assert direct.handle is not None
        await direct.close()
        assert registry._stream_owner_leases == {}
    finally:
        if direct is not None and not direct.pool.is_closed:
            await direct.close()
        elif direct_pool is not None and not direct_pool.is_closed:
            await direct_pool.close_all()
        if owner is not None and not owner.pool.is_closed:
            await owner.close()
        await registry.shutdown_async()


@pytest.mark.parametrize("lifecycle", ["unregister", "shutdown"])
@pytest.mark.asyncio
async def test_registry_lifecycle_cancels_and_drains_stream_start_before_pool_reuse(
    lifecycle: str,
    tmp_path: Path,
) -> None:
    """A cancelled in-flight start cannot publish its handle after lifecycle close."""
    connector = _GatedStreamStartup()
    source_path = tmp_path / "lifecycle-start-race.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    start_task = asyncio.create_task(
        StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id="lifecycle-start-race",
            connection_config=config,
            registry=registry,
        )
    )
    lifecycle_task: asyncio.Task[Any] | None = None
    old_session: StreamingSourceSession | None = None

    try:
        await asyncio.wait_for(connector.startup_entered.wait(), timeout=1)
        old_handle = connector.blocked_handle
        assert old_handle is not None
        if lifecycle == "unregister":
            lifecycle_task = asyncio.create_task(registry.unregister_async("stream.jsonl"))
        else:
            lifecycle_task = asyncio.create_task(registry.shutdown_async())

        await asyncio.wait_for(connector.startup_cancelled.wait(), timeout=1)
        assert connector.handle_was_live_when_cancelled is True
        assert connector.disconnect_handles == []

        start_result, _lifecycle_result = await asyncio.gather(
            start_task,
            lifecycle_task,
            return_exceptions=True,
        )
        if isinstance(start_result, StreamingSourceSession):
            old_session = start_result
        assert isinstance(start_result, asyncio.CancelledError)
        assert connector.disconnect_handles == [old_handle]
        assert registry._stream_owner_leases == {}
        assert registry._pending_startup_cleanup == {}

        if lifecycle == "unregister":
            registry.register(EventStreamConnector, config=config, factory=lambda: connector)
        fresh = await StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id="lifecycle-start-race",
            connection_config=config,
            registry=registry,
        )
        assert fresh.handle is not None and fresh.handle is not old_handle
        chunk = await fresh.poll()
        assert chunk is not None
        assert chunk.data[0]["_message_id"] == fresh.handle.session_id
        await fresh.close()
    finally:
        connector.release_startup.set()
        if not start_task.done():
            start_task.cancel()
        if lifecycle_task is not None and not lifecycle_task.done():
            lifecycle_task.cancel()
        await asyncio.gather(
            start_task,
            *((lifecycle_task,) if lifecycle_task is not None else ()),
            return_exceptions=True,
        )
        if old_session is not None and not old_session.pool.is_closed:
            await old_session.close()
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_direct_session_close_waits_for_subscription_startup(tmp_path: Path) -> None:
    """Session close cannot disconnect a handle while its subscribe callback owns it."""
    connector = _GatedStreamStartup()
    source_path = tmp_path / "direct-close-start-race.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    pool = ConnectionPool[SourceConnectorValue[object]](
        connector_factory=lambda: connector,
        config=config,
        pool_config=PoolConfig(
            max_size=1,
            validate_on_acquire=False,
            validate_on_release=False,
        ),
        pool_id="direct-close-start-race",
    )
    session = StreamingSourceSession(
        connector_id="stream.jsonl",
        dataset_id="direct-close-start-race",
        pool=pool,
        request=FetchRequest(dataset_id="direct-close-start-race"),
        registry=registry,
    )
    subscribe_task = asyncio.create_task(session.subscribe())
    close_task: asyncio.Task[None] | None = None

    try:
        await asyncio.wait_for(connector.startup_entered.wait(), timeout=1)
        close_task = asyncio.create_task(session.close())
        await asyncio.wait_for(connector.startup_cancelled.wait(), timeout=1)
        assert connector.handle_was_live_when_cancelled is True
        subscribe_result, close_result = await asyncio.gather(
            subscribe_task,
            close_task,
            return_exceptions=True,
        )
        assert isinstance(subscribe_result, asyncio.CancelledError)
        assert close_result is None
        assert connector.blocked_handle is not None
        assert connector.disconnect_handles == [connector.blocked_handle]
        assert session._closed is True
    finally:
        connector.release_startup.set()
        if not subscribe_task.done():
            subscribe_task.cancel()
        if close_task is not None and not close_task.done():
            close_task.cancel()
        await asyncio.gather(
            subscribe_task,
            *((close_task,) if close_task is not None else ()),
            return_exceptions=True,
        )
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_ready_commit_wins_before_lifecycle_invalidation(tmp_path: Path) -> None:
    """A startup committed ready before unregister is closed as an active owner."""
    connector = _GatedStreamStartup()
    source_path = tmp_path / "ready-commit-before-unregister.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    start_task = asyncio.create_task(
        StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id="ready-commit-before-unregister",
            connection_config=config,
            registry=registry,
        )
    )
    session: StreamingSourceSession | None = None

    try:
        await asyncio.wait_for(connector.startup_entered.wait(), timeout=1)
        connector.release_startup.set()
        session = await start_task
        assert session.handle is not None
        assert session._owner_lease is not None
        assert session._owner_lease.startup is None
        assert session._owner_lease.invalidated is False

        handle = session.handle
        assert await registry.unregister_async("stream.jsonl") is True
        assert connector.disconnect_handles == [handle]
        assert registry._stream_owner_leases == {}
        # Once invalidated, the session cannot race lifecycle-owned physical close.
        await session.close()
    finally:
        connector.release_startup.set()
        if not start_task.done():
            start_task.cancel()
        await asyncio.gather(start_task, return_exceptions=True)
        if session is not None and not session.pool.is_closed:
            await session.close()
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_shutdown_fences_new_streams_until_resistant_start_drains(
    tmp_path: Path,
) -> None:
    """Shutdown holds admission closed until a resistant startup and pool close settle."""
    connector = _CancellationResistantStreamStartup()
    source_path = tmp_path / "resistant-shutdown-start.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    start_task = asyncio.create_task(
        StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id="resistant-shutdown-start",
            connection_config=config,
            registry=registry,
        )
    )
    shutdown_task: asyncio.Task[None] | None = None
    fresh: StreamingSourceSession | None = None

    try:
        await asyncio.wait_for(connector.startup_entered.wait(), timeout=1)
        old_handle = connector.blocked_handle
        assert old_handle is not None
        shutdown_task = asyncio.create_task(registry.shutdown_async())
        await asyncio.wait_for(connector.startup_cancelled.wait(), timeout=1)
        assert connector.handle_was_live_when_cancelled is True
        assert shutdown_task.done() is False
        assert connector.disconnect_handles == []

        with pytest.raises(StreamOwnerConflictError):
            await StreamingSourceSession.create(
                connector_id="stream.jsonl",
                dataset_id="resistant-shutdown-sibling",
                connection_config=config,
                registry=registry,
            )
        assert len(connector.connect_handles) == 1

        connector.release_startup.set()
        start_result, shutdown_result = await asyncio.gather(
            start_task,
            shutdown_task,
            return_exceptions=True,
        )
        assert isinstance(start_result, StreamOwnerConflictError)
        assert shutdown_result is None
        assert connector.disconnect_handles == [old_handle]
        assert registry._stream_owner_admissions_closed is False
        assert registry._stream_owner_leases == {}

        fresh = await StreamingSourceSession.create(
            connector_id="stream.jsonl",
            dataset_id="resistant-shutdown-start",
            connection_config=config,
            registry=registry,
        )
        assert fresh.handle is not None and fresh.handle is not old_handle
        chunk = await fresh.poll()
        assert chunk is not None
        assert chunk.data[0]["_message_id"] == fresh.handle.session_id
    finally:
        connector.release_startup.set()
        if not start_task.done():
            start_task.cancel()
        if shutdown_task is not None and not shutdown_task.done():
            shutdown_task.cancel()
        await asyncio.gather(
            start_task,
            *((shutdown_task,) if shutdown_task is not None else ()),
            return_exceptions=True,
        )
        if fresh is not None and not fresh.pool.is_closed:
            await fresh.close()
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_lifecycle_reentry_from_its_startup_task_fails_closed_without_deadlock(
    tmp_path: Path,
) -> None:
    """A callback cannot make its own lifecycle drain await itself."""
    connector = _SelfUnregisteringStreamStartup()
    source_path = tmp_path / "self-unregister-start.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    registry = ConnectorRegistry()
    connector.registry = registry
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)

    with pytest.raises(RuntimeError, match="cannot wait for the stream startup"):
        await asyncio.wait_for(
            StreamingSourceSession.create(
                connector_id="stream.jsonl",
                dataset_id="self-unregister-start",
                connection_config=config,
                registry=registry,
            ),
            timeout=1,
        )

    assert len(connector.connect_handles) == 1
    assert connector.disconnect_handles == []
    assert len(registry._pending_startup_cleanup) == 1
    assert registry._stream_owner_leases

    assert await registry.unregister_async("stream.jsonl") is True
    assert connector.disconnect_handles == connector.connect_handles
    assert registry._pending_startup_cleanup == {}
    assert registry._stream_owner_leases == {}
    await registry.shutdown_async()


@pytest.mark.asyncio
async def test_registry_drains_startup_ticket_across_event_loops(tmp_path: Path) -> None:
    """A lifecycle loop can cancel and join startup on the loop that owns its task."""
    connector = _CrossLoopGatedStreamStartup()
    source_path = tmp_path / "cross-loop-start.jsonl"
    source_path.write_text('{"_message_id":"event-a","value":1}\n', encoding="utf-8")
    config = ConnectionConfig(url=source_path.as_uri(), max_connections=1)
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=config, factory=lambda: connector)
    outcomes: list[BaseException | StreamingSourceSession] = []

    def run_startup() -> None:
        async def start() -> None:
            try:
                outcomes.append(
                    await StreamingSourceSession.create(
                        connector_id="stream.jsonl",
                        dataset_id="cross-loop-start",
                        connection_config=config,
                        registry=registry,
                    )
                )
            except BaseException as exc:
                outcomes.append(exc)

        asyncio.run(start())

    worker = threading.Thread(target=run_startup, name="stream-startup-loop")
    worker.start()

    try:
        assert await asyncio.to_thread(connector.startup_entered.wait, 2) is True
        assert await asyncio.wait_for(registry.unregister_async("stream.jsonl"), timeout=2) is True
        await asyncio.to_thread(worker.join, 2)
        assert worker.is_alive() is False
        assert connector.startup_cancelled.is_set()
        assert connector.handle_was_live_when_cancelled is True
        assert len(outcomes) == 1 and isinstance(outcomes[0], asyncio.CancelledError)
        assert connector.blocked_handle is not None
        assert connector.disconnect_handles == [connector.blocked_handle]
        assert registry._stream_owner_leases == {}
        assert registry._pending_startup_cleanup == {}
    finally:
        if worker.is_alive():
            worker.join(2)
        await registry.shutdown_async()
