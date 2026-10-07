"""Independent recovery and lower-cap oracles for the composed stream consumer."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.pool import ConnectionPool
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane import streaming
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.watermark import WindowPolicy


def _clean_rows(
    batch: list[dict[str, Any]], **kwargs: Any
) -> tuple[list[dict[str, Any]], list[Any], int]:
    del kwargs
    return [dict(row) for row in batch], [], 0


def _runtime_options(cap: int) -> streaming.StreamRuntimeOptions:
    return streaming.StreamRuntimeOptions(
        max_buffered_rows=cap,
        checkpoint_every_chunks=1,
        window_policy=WindowPolicy(
            strategy=WindowStrategy.SESSION,
            size=60,
            session_gap_seconds=2,
            timestamp_field="event_time",
        ),
    )


def _source_fixture() -> tuple[bytes, list[dict[str, Any]], list[bytes]]:
    rows = [
        {
            "_message_id": f"event-{value}",
            "value": value,
            "event_time": f"2024-01-01T00:00:0{second}+00:00",
        }
        for value, second in ((1, 0), (2, 1), (3, 5))
    ]
    lines = [json.dumps(row).encode("utf-8") + b"\n" for row in rows]
    return b"".join(lines), rows, lines


def _assert_source_key_identity(checkpoint: Any) -> None:
    """Decode persisted keys independently and compare their field/value identity."""
    decoded_identity = tuple(
        tuple((str(pair[0]), pair[1]) for pair in json.loads(encoded))
        for encoded in checkpoint.dedupe_keys
    )
    assert decoded_identity == (
        (("_message_id", "event-1"),),
        (("_message_id", "event-2"),),
    )


async def _prepare_two_row_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    ConnectorRegistry,
    FileSystemCAS,
    CursorStore,
    Any,
    bytes,
    list[dict[str, Any]],
    list[bytes],
]:
    source_bytes, expected_rows, raw_lines = _source_fixture()
    source = tmp_path / "events.jsonl"
    source.write_bytes(source_bytes)

    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=source.as_uri(), headers={"X-Stream-ChunkSize": "2"}),
    )
    store = FileSystemCAS(tmp_path / "cas")
    cursors = CursorStore(store)
    real_poll = streaming.StreamingSourceSession.poll
    returned_chunks = 0

    async def stop_after_first_checkpoint(session: streaming.StreamingSourceSession):
        nonlocal returned_chunks
        if returned_chunks == 1:
            raise RuntimeError("oracle stop after the two-row checkpoint")
        chunk = await real_poll(session)
        if chunk is not None:
            returned_chunks += 1
        return chunk

    monkeypatch.setattr(
        streaming.StreamingSourceSession,
        "poll",
        stop_after_first_checkpoint,
    )
    try:
        with pytest.raises(RuntimeError, match="two-row checkpoint"):
            await streaming.process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id="net-ing-frontier",
                store=store,
                cursor_store=cursors,
                sanitize_rows=_clean_rows,
                runtime_options=_runtime_options(3),
                registry=registry,
            )
    finally:
        monkeypatch.setattr(streaming.StreamingSourceSession, "poll", real_poll)

    checkpoint = cursors.find_latest_stream_checkpoint(
        "stream.jsonl",
        "net-ing-frontier",
    )
    assert checkpoint is not None
    _assert_source_key_identity(checkpoint)
    accumulator = streaming.StreamWindowAccumulator(_runtime_options(3).window_policy)
    streaming._restore_stream_operator_state(
        checkpoint.metadata["operator_state"],
        accumulator=accumulator,
        ordering_state=streaming._StreamOrderingState(),
    )
    assert accumulator.buffered_rows() == 2
    return registry, store, cursors, checkpoint, source_bytes, expected_rows, raw_lines


def _artifact_payloads(
    store: FileSystemCAS,
    *,
    kind: str,
    dataset_id: str,
) -> list[tuple[str, dict[str, Any], Any]]:
    artifacts: list[tuple[str, dict[str, Any], Any]] = []
    for artifact_id in store.iter_artifact_ids():
        ref = str(artifact_id)
        manifest = store.get_manifest(ref)
        if manifest.kind != kind:
            continue
        payload = from_canonical_bytes(store.get_bytes(ref))
        if payload.get("dataset_id") == dataset_id:
            artifacts.append((ref, payload, manifest))
    return artifacts


def _read_optional(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


@pytest.fixture(autouse=True)
async def _shutdown_registry_after_each_test():
    yield
    registry = ConnectorRegistry._instance
    if registry is not None:
        await registry.shutdown_async()
    ConnectorRegistry.reset_instance()


@pytest.mark.asyncio
async def test_lower_restored_cap_refuses_before_poll_or_frontier_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A two-row predecessor cannot resume under a one-row cap or advance state."""
    (
        registry,
        store,
        _cursors,
        checkpoint,
        source_bytes,
        _expected_rows,
        _raw_lines,
    ) = await _prepare_two_row_frontier(tmp_path, monkeypatch)
    dataset_id = "net-ing-frontier"
    reopened = FileSystemCAS(store.root)
    reopened_cursors = CursorStore(reopened)
    latest_before = reopened_cursors.find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    assert latest_before is not None
    assert latest_before.model_dump(mode="json") == checkpoint.model_dump(mode="json")

    pending_refs = tuple(
        dict.fromkeys(
            str(ref)
            for entry in checkpoint.metadata["operator_state"]["accumulator"]["session_rows"]
            for ref in entry["refs"]
        )
    )
    assert len(pending_refs) == 1
    predecessor_bytes = {ref: reopened.get_bytes(ref) for ref in pending_refs}
    predecessor_manifests = {
        ref: reopened.get_manifest(ref).model_dump(mode="json") for ref in pending_refs
    }
    predecessor_artifact_ids = {str(ref) for ref in reopened.iter_artifact_ids()}
    stream_index_before = _read_optional(reopened_cursors._stream_index_path)
    cursor_index_before = _read_optional(reopened_cursors._index_path)
    cursor_before = reopened_cursors.find_latest_cursor("stream.jsonl", dataset_id)
    assert cursor_before is not None

    poll_events: list[str] = []
    flush_events: list[str] = []
    commit_events: list[str] = []
    cas_writes: list[str] = []
    acquisitions: list[tuple[int, str]] = []
    releases: list[tuple[int, str]] = []
    real_poll = streaming.StreamingSourceSession.poll
    real_flush = streaming.StreamWindowAccumulator.flush_with_refs
    real_commit = streaming._commit_stream_frontier
    real_acquire = ConnectionPool.acquire_with_connector
    real_release = ConnectionPool.release
    real_put_json = reopened.put_json
    real_put_bytes = reopened.put_bytes

    async def record_poll(session: streaming.StreamingSourceSession):
        poll_events.append("poll")
        return await real_poll(session)

    def record_flush(accumulator: streaming.StreamWindowAccumulator):
        flush_events.append("flush")
        return real_flush(accumulator)

    async def record_commit(**kwargs: Any):
        commit_events.append("commit")
        return await real_commit(**kwargs)

    async def record_acquire(pool: ConnectionPool[Any]):
        result = await real_acquire(pool)
        acquisitions.append((id(pool), result[1].session_id))
        return result

    async def record_release(pool: ConnectionPool[Any], handle: Any):
        result = await real_release(pool, handle)
        releases.append((id(pool), handle.session_id))
        return result

    def record_put_json(*args: Any, **kwargs: Any):
        cas_writes.append("put_json")
        return real_put_json(*args, **kwargs)

    def record_put_bytes(*args: Any, **kwargs: Any):
        cas_writes.append("put_bytes")
        return real_put_bytes(*args, **kwargs)

    monkeypatch.setattr(streaming.StreamingSourceSession, "poll", record_poll)
    monkeypatch.setattr(streaming.StreamWindowAccumulator, "flush_with_refs", record_flush)
    monkeypatch.setattr(streaming, "_commit_stream_frontier", record_commit)
    monkeypatch.setattr(ConnectionPool, "acquire_with_connector", record_acquire)
    monkeypatch.setattr(ConnectionPool, "release", record_release)
    monkeypatch.setattr(reopened, "put_json", record_put_json)
    monkeypatch.setattr(reopened, "put_bytes", record_put_bytes)

    try:
        with pytest.raises(streaming.StreamCapacityError) as caught:
            await streaming.process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                store=reopened,
                cursor_store=reopened_cursors,
                sanitize_rows=_clean_rows,
                runtime_options=_runtime_options(1),
                registry=registry,
            )

        assert poll_events == []
        assert flush_events == []
        assert commit_events == []
        assert cas_writes == []
        assert caught.value.stage == "restore"
        assert caught.value.rows == 2 and caught.value.max_rows == 1
        assert Counter(acquisitions) == Counter(releases)

        latest_after = reopened_cursors.find_latest_stream_checkpoint(
            "stream.jsonl",
            dataset_id,
        )
        assert latest_after is not None
        assert latest_after.model_dump(mode="json") == latest_before.model_dump(mode="json")
        assert latest_after.lifecycle_state == latest_before.lifecycle_state
        assert latest_after.offset == latest_before.offset
        cursor_after = reopened_cursors.find_latest_cursor("stream.jsonl", dataset_id)
        assert cursor_after is not None
        assert cursor_after.model_dump(mode="json") == cursor_before.model_dump(mode="json")
        assert _read_optional(reopened_cursors._stream_index_path) == stream_index_before
        assert _read_optional(reopened_cursors._index_path) == cursor_index_before
        assert {str(ref) for ref in reopened.iter_artifact_ids()} == predecessor_artifact_ids
        assert {ref: reopened.get_bytes(ref) for ref in pending_refs} == predecessor_bytes
        assert {
            ref: reopened.get_manifest(ref).model_dump(mode="json") for ref in pending_refs
        } == predecessor_manifests
        assert (
            hashlib.sha256(source_bytes).hexdigest()
            == hashlib.sha256((tmp_path / "events.jsonl").read_bytes()).hexdigest()
        )
    finally:
        await registry.shutdown_async()
        ConnectorRegistry.reset_instance()


@pytest.mark.asyncio
async def test_admitted_restore_recovers_ordered_windows_once_with_original_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The compatible cap resumes the real source and preserves exact row lineage."""
    (
        registry,
        store,
        _cursors,
        checkpoint,
        source_bytes,
        expected_rows,
        raw_lines,
    ) = await _prepare_two_row_frontier(tmp_path, monkeypatch)
    dataset_id = "net-ing-frontier"
    _assert_source_key_identity(checkpoint)

    resumed_store = FileSystemCAS(store.root)
    resumed_cursors = CursorStore(resumed_store)
    result = await streaming.process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=resumed_store,
        cursor_store=resumed_cursors,
        sanitize_rows=_clean_rows,
        runtime_options=_runtime_options(3),
        registry=registry,
    )

    chunk_artifacts = _artifact_payloads(
        resumed_store,
        kind="fabric.stream_chunk",
        dataset_id=dataset_id,
    )
    chunk_artifacts.sort(key=lambda item: int(item[1]["chunk_index"]))
    chunk_rows = [row for _ref, payload, _manifest in chunk_artifacts for row in payload["data"]]
    decoded_source_rows = [json.loads(line.decode("utf-8")) for line in raw_lines]
    assert decoded_source_rows == expected_rows
    assert chunk_rows == decoded_source_rows
    message_ids = [str(row["_message_id"]) for row in chunk_rows]
    assert message_ids == ["event-1", "event-2", "event-3"]
    assert Counter(message_ids) == Counter({"event-1": 1, "event-2": 1, "event-3": 1})
    assert all(resumed_store.verify(ref).ok for ref, _payload, _manifest in chunk_artifacts)

    chunk_by_message = {
        str(row["_message_id"]): ref
        for ref, payload, _manifest in chunk_artifacts
        for row in payload["data"]
    }
    window_artifacts = _artifact_payloads(
        resumed_store,
        kind="fabric.stream_window",
        dataset_id=dataset_id,
    )
    window_artifacts.sort(key=lambda item: int(item[1]["ordinal"]))
    assert [
        [str(row["_message_id"]) for row in payload["data"]]
        for _ref, payload, _manifest in window_artifacts
    ] == [["event-1", "event-2"], ["event-3"]]
    for _ref, payload, manifest in window_artifacts:
        row_ids = [str(row["_message_id"]) for row in payload["data"]]
        expected_contributors = tuple(dict.fromkeys(chunk_by_message[row_id] for row_id in row_ids))
        manifest_inputs = tuple(str(item.artifact_id) for item in manifest.inputs)
        lineage_inputs = tuple(str(item) for item in payload["lineage"]["contributor_chunk_refs"])
        assert manifest_inputs == expected_contributors
        assert lineage_inputs == expected_contributors
        assert all(resumed_store.verify(ref).ok for ref in expected_contributors)

    assert result.final_checkpoint is not None
    assert result.final_checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    assert result.final_checkpoint.metadata["frontier_intent"]["state"] == "committed"
    latest_checkpoint = resumed_cursors.find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    assert latest_checkpoint is not None
    assert latest_checkpoint.model_dump(mode="json") == result.final_checkpoint.model_dump(
        mode="json"
    )
    latest_cursor = resumed_cursors.find_latest_cursor("stream.jsonl", dataset_id)
    assert latest_cursor is not None
    assert latest_cursor.watermark_value == str(latest_checkpoint.offset)

    before_chunk_refs = {ref for ref, _payload, _manifest in chunk_artifacts}
    before_window_refs = {ref for ref, _payload, _manifest in window_artifacts}
    repeated_store = FileSystemCAS(store.root)
    repeated = await streaming.process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=repeated_store,
        cursor_store=CursorStore(repeated_store),
        sanitize_rows=_clean_rows,
        runtime_options=_runtime_options(3),
        registry=registry,
    )
    assert repeated.window_refs == []
    assert repeated.chunk_refs == []
    assert repeated.rows_emitted == 0
    after_chunks = _artifact_payloads(
        FileSystemCAS(store.root),
        kind="fabric.stream_chunk",
        dataset_id=dataset_id,
    )
    after_windows = _artifact_payloads(
        FileSystemCAS(store.root),
        kind="fabric.stream_window",
        dataset_id=dataset_id,
    )
    assert {ref for ref, _payload, _manifest in after_chunks} == before_chunk_refs
    assert {ref for ref, _payload, _manifest in after_windows} == before_window_refs
    latest_after_repeat = CursorStore(FileSystemCAS(store.root))
    repeated_checkpoint = latest_after_repeat.find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    repeated_cursor = latest_after_repeat.find_latest_cursor("stream.jsonl", dataset_id)
    assert repeated_checkpoint is not None
    assert repeated_checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    assert repeated_checkpoint.offset == latest_checkpoint.offset
    assert repeated_cursor is not None
    assert repeated_cursor.watermark_value == latest_cursor.watermark_value
    assert (
        hashlib.sha256(source_bytes).hexdigest()
        == hashlib.sha256((tmp_path / "events.jsonl").read_bytes()).hexdigest()
    )
    await registry.shutdown_async()
    ConnectorRegistry.reset_instance()
