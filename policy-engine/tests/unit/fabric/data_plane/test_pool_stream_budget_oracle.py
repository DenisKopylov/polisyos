"""Independent B-to-C recovery admission on a real file connector and CAS."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.pool import ConnectionPool
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane import streaming
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.watermark import WindowPolicy


def _rows(batch, **kwargs):
    return [dict(row) for row in batch], [], 0


def _options(cap: int) -> streaming.StreamRuntimeOptions:
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


async def _pending_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "events.jsonl"
    source.write_text(
        "".join(
            json.dumps(
                {
                    "_message_id": f"event-{value}",
                    "value": value,
                    "event_time": f"2024-01-01T00:00:0{second}+00:00",
                }
            )
            + "\n"
            for value, second in ((1, 0), (2, 1), (3, 5))
        ),
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=source.as_uri(), headers={"X-Stream-ChunkSize": "2"}),
    )
    store = FileSystemCAS(tmp_path / "cas")
    cursor = CursorStore(store)
    poll = streaming.StreamingSourceSession.poll
    polls = 0

    async def stop_after_checkpoint(session):
        nonlocal polls
        if polls == 1:
            raise RuntimeError("oracle stop after actual two-row checkpoint")
        chunk = await poll(session)
        if chunk is not None:
            polls += 1
        return chunk

    monkeypatch.setattr(streaming.StreamingSourceSession, "poll", stop_after_checkpoint)
    with pytest.raises(RuntimeError, match="actual two-row checkpoint"):
        await streaming.process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="budget-oracle",
            store=store,
            cursor_store=cursor,
            sanitize_rows=_rows,
            runtime_options=_options(3),
            registry=registry,
        )
    monkeypatch.setattr(streaming.StreamingSourceSession, "poll", poll)
    checkpoint = cursor.find_latest_stream_checkpoint("stream.jsonl", "budget-oracle")
    assert checkpoint is not None
    accumulator = streaming.StreamWindowAccumulator(_options(3).window_policy)
    streaming._restore_stream_operator_state(
        checkpoint.metadata["operator_state"],
        accumulator=accumulator,
        ordering_state=streaming._StreamOrderingState(),
    )
    assert accumulator.buffered_rows() == 2
    assert checkpoint.dedupe_keys == ("_message_id:event-1", "_message_id:event-2")
    return registry, store, checkpoint


@pytest.mark.asyncio
async def test_restored_frontier_above_new_cap_refuses_before_consumer_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry, store, checkpoint = await _pending_checkpoint(tmp_path, monkeypatch)
    events: list[str] = []
    acquisitions: list[tuple[int, str]] = []
    releases: list[tuple[int, str]] = []
    acquire = ConnectionPool.acquire_with_connector
    release = ConnectionPool.release
    poll = streaming.StreamingSourceSession.poll
    flush = streaming.StreamWindowAccumulator.flush_with_refs
    commit = streaming._commit_stream_frontier

    async def observed_acquire(pool):
        result = await acquire(pool)
        events.append("acquire")
        acquisitions.append((id(pool), result[1].session_id))
        return result

    async def observed_release(pool, handle):
        result = await release(pool, handle)
        releases.append((id(pool), handle.session_id))
        events.append("release")
        return result

    async def observed_poll(session):
        events.append("poll")
        return await poll(session)

    def observed_flush(accumulator):
        events.append("flush")
        return flush(accumulator)

    async def observed_commit(**kwargs):
        events.append("commit")
        return await commit(**kwargs)

    monkeypatch.setattr(ConnectionPool, "acquire_with_connector", observed_acquire)
    monkeypatch.setattr(ConnectionPool, "release", observed_release)
    monkeypatch.setattr(streaming.StreamingSourceSession, "poll", observed_poll)
    monkeypatch.setattr(streaming.StreamWindowAccumulator, "flush_with_refs", observed_flush)
    monkeypatch.setattr(streaming, "_commit_stream_frontier", observed_commit)
    reopened = FileSystemCAS(store.root)
    failure = None
    try:
        await streaming.process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="budget-oracle",
            store=reopened,
            cursor_store=CursorStore(reopened),
            sanitize_rows=_rows,
            runtime_options=_options(1),
            registry=registry,
        )
    except (RuntimeError, ValueError) as exc:
        failure = exc
    assert not {"poll", "flush", "commit"}.intersection(events), json.dumps(events)
    assert failure is not None, "over-cap restored frontier was accepted"
    # Schema discovery may own an additional session. Reconcile the real leases
    # instead of assuming a constant count of acquisitions for this consumer.
    assert acquisitions and Counter(acquisitions) == Counter(releases)
    current = CursorStore(reopened).find_latest_stream_checkpoint("stream.jsonl", "budget-oracle")
    assert current is not None
    assert current.model_dump(mode="json") == checkpoint.model_dump(mode="json")


@pytest.mark.asyncio
async def test_admitted_recovery_emits_two_sessions_once_with_original_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry, store, _ = await _pending_checkpoint(tmp_path, monkeypatch)
    reopened = FileSystemCAS(store.root)
    result = await streaming.process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="budget-oracle",
        store=reopened,
        cursor_store=CursorStore(reopened),
        sanitize_rows=_rows,
        runtime_options=_options(3),
        registry=registry,
    )
    windows = [from_canonical_bytes(reopened.get_bytes(ref)) for ref in result.window_refs]
    assert [[row["value"] for row in window["data"]] for window in windows] == [[1, 2], [3]]
    assert all(reopened.verify(ref).ok for ref in result.window_refs)
    for ref, window in zip(result.window_refs, windows, strict=True):
        manifest = reopened.get_manifest(ref)
        assert {str(item.artifact_id) for item in manifest.inputs} == set(
            window["lineage"]["contributor_chunk_refs"]
        )
    repeated = await streaming.process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="budget-oracle",
        store=FileSystemCAS(store.root),
        cursor_store=CursorStore(FileSystemCAS(store.root)),
        sanitize_rows=_rows,
        runtime_options=_options(3),
        registry=registry,
    )
    assert repeated.window_refs == []
