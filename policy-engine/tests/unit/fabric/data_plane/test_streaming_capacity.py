from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamCheckpoint, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import (
    StreamRuntimeOptions,
    StreamWindowAccumulator,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy
from polisyos.fabric.quality.processing_guarantees import (
    BackpressurePolicy,
    BackpressureStrategy,
    stream_processing_contract,
)

_CONNECTOR_ID = "stream.jsonl"
_SESSION_GAP_SECONDS = 5
_START = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)


def _rows(gaps: tuple[int, ...]) -> list[dict[str, Any]]:
    return [
        {
            "_message_id": f"m{index}",
            "event_time": (_START + timedelta(seconds=gap)).isoformat(),
            "value": "x" * 16,
        }
        for index, gap in enumerate(gaps)
    ]


def _encoded_json_bytes(row: dict[str, Any]) -> int:
    """Measure the exact wire encoding used by the retained-state byte contract."""
    return len(json.dumps(row, sort_keys=True, default=str).encode("utf-8"))


def _configure_source(
    tmp_path: Path,
    dataset_id: str,
    rows: list[dict[str, Any]],
    *,
    chunk_size: int = 2,
) -> tuple[ConnectorRegistry, FileSystemCAS, CursorStore]:
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        _CONNECTOR_ID,
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": str(chunk_size)},
        ),
    )
    store = FileSystemCAS(tmp_path / f"{dataset_id}.cas")
    return registry, store, CursorStore(store)


def _window_policy(strategy: WindowStrategy) -> WindowPolicy:
    if strategy == WindowStrategy.COUNT:
        return WindowPolicy(strategy=strategy, size=3)
    if strategy == WindowStrategy.TUMBLING:
        return WindowPolicy(
            strategy=strategy,
            size=5,
            timestamp_field="event_time",
        )
    return WindowPolicy(
        strategy=WindowStrategy.SESSION,
        size=300,
        session_gap_seconds=_SESSION_GAP_SECONDS,
        timestamp_field="event_time",
    )


def _options(
    *,
    strategy: BackpressureStrategy,
    max_rows: int,
    max_bytes: int,
    window_policy: WindowPolicy,
) -> StreamRuntimeOptions:
    contract = stream_processing_contract().model_copy(
        update={
            "backpressure": BackpressurePolicy(
                strategy=strategy,
                max_buffered_rows=max_rows,
                max_buffered_bytes=max_bytes,
                pause_seconds=0.0,
            )
        }
    )
    return StreamRuntimeOptions(
        batch_size=1,
        max_dedupe_keys=8,
        max_buffered_rows=max_rows,
        max_buffered_bytes=max_bytes,
        pause_seconds=0.0,
        window_policy=window_policy,
        processing_contract=contract,
    )


def _observe_live_retained_state(monkeypatch: pytest.MonkeyPatch):
    """Record actual accumulator state at checkpoint and post-add boundaries."""
    import polisyos.fabric.data_plane.streaming as streaming

    live_ids: set[int] = set()
    observations: list[tuple[int, int]] = []
    original_checkpoint_metadata = streaming._stream_checkpoint_metadata
    original_add_rows = StreamWindowAccumulator.add_rows_with_refs

    def record(accumulator: StreamWindowAccumulator) -> None:
        observations.append(
            (accumulator.buffered_rows(), accumulator.buffered_bytes())
        )

    def checkpoint_metadata(**kwargs: Any) -> dict[str, Any]:
        accumulator = kwargs["accumulator"]
        live_ids.add(id(accumulator))
        record(accumulator)
        return original_checkpoint_metadata(**kwargs)

    def add_rows_with_refs(
        accumulator: StreamWindowAccumulator,
        rows: list[dict[str, Any]],
        contributor_refs: tuple[str, ...],
    ) -> list[Any]:
        emissions = original_add_rows(accumulator, rows, contributor_refs)
        if id(accumulator) in live_ids:
            record(accumulator)
        return emissions

    monkeypatch.setattr(streaming, "_stream_checkpoint_metadata", checkpoint_metadata)
    monkeypatch.setattr(StreamWindowAccumulator, "add_rows_with_refs", add_rows_with_refs)
    return observations


def _assert_within_capacity(
    observations: list[tuple[int, int]],
    *,
    max_rows: int,
    max_bytes: int,
) -> None:
    assert observations
    assert all(rows <= max_rows for rows, _ in observations), (
        "retained rows exceed declared capacity"
    )
    assert all(byte_count <= max_bytes for _, byte_count in observations), (
        "retained bytes exceed declared capacity"
    )


def _stream_chunks(store: FileSystemCAS) -> dict[int, tuple[str, dict[str, Any]]]:
    """Read actual stream-chunk records from the isolated CAS inventory."""
    chunks: dict[int, tuple[str, dict[str, Any]]] = {}
    for artifact_id in store.iter_artifact_ids():
        if store.get_manifest(artifact_id).kind != "fabric.stream_chunk":
            continue
        payload = from_canonical_bytes(store.get_bytes(artifact_id))
        chunks[int(payload["chunk_index"])] = (str(artifact_id), payload)
    return chunks


def _read_emitted_message_ids(store: FileSystemCAS, result: Any) -> list[str]:
    return [
        str(row["_message_id"])
        for ref in result.window_refs
        for row in from_canonical_bytes(store.get_bytes(ref.artifact_id))["data"]
    ]


def _assert_frontier(
    cursor_store: CursorStore,
    dataset_id: str,
    *,
    expected_offset: int,
) -> tuple[Any, StreamCheckpoint]:
    cursor = cursor_store.find_latest_cursor(_CONNECTOR_ID, dataset_id)
    checkpoint = cursor_store.find_latest_stream_checkpoint(_CONNECTOR_ID, dataset_id)
    assert cursor is not None
    assert checkpoint is not None
    assert cursor.watermark_value == str(expected_offset)
    assert checkpoint.offset == expected_offset
    return cursor, checkpoint


def _runtime_rows(batch: Any, **kwargs: Any):
    del kwargs
    return [dict(row) for row in batch if isinstance(row, dict)], [], 0


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", list(BackpressureStrategy))
async def test_capacity_overflow_preserves_committed_frontier_and_retries_same_chunk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    strategy: BackpressureStrategy,
) -> None:
    """Overflow refuses chunk 1 before CAS/offset publication; restart retries it."""
    dataset_id = f"capacity-retry-{strategy.value}"
    rows = _rows((0, 1, 2, 3))
    registry, store, cursor_store = _configure_source(tmp_path, dataset_id, rows)
    observations = _observe_live_retained_state(monkeypatch)

    import polisyos.fabric.data_plane.streaming as streaming

    original_commit = streaming._commit_stream_frontier
    committed_pairs: list[tuple[Any, StreamCheckpoint]] = []

    async def capture_committed_pair(**kwargs: Any):
        outcome = await original_commit(**kwargs)
        if int(kwargs["checkpoint"].offset) == 0:
            committed_pairs.append((kwargs["cursor"], outcome[2]))
        return outcome

    monkeypatch.setattr(streaming, "_commit_stream_frontier", capture_committed_pair)
    too_small = _options(
        strategy=strategy,
        max_rows=3,
        max_bytes=100_000,
        window_policy=_window_policy(WindowStrategy.SESSION),
    )

    with pytest.raises(RuntimeError, match="capacity|backpressure|spill"):
        await process_stream_dataset(
            connector_id=_CONNECTOR_ID,
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_runtime_rows,
            runtime_options=too_small,
            registry=registry,
        )

    assert len(committed_pairs) == 1
    prior_cursor, prior_checkpoint = committed_pairs[0]
    stored_cursor, paused_checkpoint = _assert_frontier(
        cursor_store,
        dataset_id,
        expected_offset=0,
    )
    assert stored_cursor.model_dump(mode="json") == prior_cursor.model_dump(mode="json")
    assert paused_checkpoint.checkpoint_id == prior_checkpoint.checkpoint_id
    assert paused_checkpoint.offset == prior_checkpoint.offset
    assert paused_checkpoint.dedupe_keys == prior_checkpoint.dedupe_keys
    assert paused_checkpoint.metadata["operator_state"] == prior_checkpoint.metadata[
        "operator_state"
    ]
    assert paused_checkpoint.metadata["observed_offset"] == 1
    assert paused_checkpoint.metadata["frontier_committed"] is True

    prior_state = paused_checkpoint.metadata["operator_state"]["accumulator"]
    retained_entries = prior_state["session_rows"]
    assert [entry["row"]["_message_id"] for entry in retained_entries] == ["m0", "m1"]
    chunks_after_refusal = _stream_chunks(store)
    assert set(chunks_after_refusal) == {0}
    first_chunk_ref, first_chunk_payload = chunks_after_refusal[0]
    assert first_chunk_payload["row_count"] == 2
    assert all(entry["refs"] == [first_chunk_ref] for entry in retained_entries)
    _assert_within_capacity(observations, max_rows=3, max_bytes=100_000)

    # The source bytes and replay offset remain unchanged.  Raising the runtime
    # allowance makes that same previously refused chunk admissible on restart.
    ConnectorRegistry.reset_instance()
    retry_registry = ConnectorRegistry.get_instance()
    retry_registry.set_default_config(
        _CONNECTOR_ID,
        ConnectionConfig(
            url=(tmp_path / f"{dataset_id}.jsonl").as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )
    retry = await process_stream_dataset(
        connector_id=_CONNECTOR_ID,
        dataset_id=dataset_id,
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_runtime_rows,
        runtime_options=_options(
            strategy=strategy,
            max_rows=4,
            max_bytes=100_000,
            window_policy=_window_policy(WindowStrategy.SESSION),
        ),
        registry=retry_registry,
    )

    retry_chunks = _stream_chunks(store)
    assert set(retry_chunks) == {0, 1}
    assert retry_chunks[1][1]["data"] == rows[2:]
    assert Counter(_read_emitted_message_ids(store, retry)) == Counter(
        row["_message_id"] for row in rows
    )
    _assert_frontier(cursor_store, dataset_id, expected_offset=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", list(BackpressureStrategy))
@pytest.mark.parametrize(
    "window_strategy",
    [
        pytest.param(WindowStrategy.COUNT, id="count"),
        pytest.param(WindowStrategy.SESSION, id="session"),
        pytest.param(WindowStrategy.TUMBLING, id="tumbling"),
    ],
)
@pytest.mark.parametrize(
    "limit_dimension",
    [pytest.param("rows", id="rows"), pytest.param("bytes", id="bytes")],
)
async def test_capacity_exact_limit_accepts_window_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    strategy: BackpressureStrategy,
    window_strategy: WindowStrategy,
    limit_dimension: str,
) -> None:
    """A closing operator transition fits at the exact retained-state cap."""
    gaps = (0, 1, 10, 11)
    rows = _rows(gaps)
    row_bytes = {_encoded_json_bytes(row) for row in rows}
    assert len(row_bytes) == 1
    exact_two_row_bytes = 2 * next(iter(row_bytes))
    max_rows = 2 if limit_dimension == "rows" else 100
    max_bytes = 100_000 if limit_dimension == "rows" else exact_two_row_bytes
    dataset_id = f"capacity-close-{strategy.value}-{window_strategy.value}-{limit_dimension}"
    registry, store, cursor_store = _configure_source(tmp_path, dataset_id, rows)
    observations = _observe_live_retained_state(monkeypatch)

    result = await process_stream_dataset(
        connector_id=_CONNECTOR_ID,
        dataset_id=dataset_id,
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_runtime_rows,
        runtime_options=_options(
            strategy=strategy,
            max_rows=max_rows,
            max_bytes=max_bytes,
            window_policy=_window_policy(window_strategy),
        ),
        registry=registry,
    )

    _assert_within_capacity(observations, max_rows=max_rows, max_bytes=max_bytes)
    assert result.rows_emitted == len(rows)
    assert Counter(_read_emitted_message_ids(store, result)) == Counter(
        row["_message_id"] for row in rows
    )
    _assert_frontier(cursor_store, dataset_id, expected_offset=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", list(BackpressureStrategy))
async def test_capacity_byte_limit_matches_exact_json_utf8_encoding(
    tmp_path: Path,
    strategy: BackpressureStrategy,
) -> None:
    """UTF-8 JSON byte accounting accepts equality and refuses the next row."""
    rows = [
        {
            "_message_id": "m0",
            "event_time": (_START + timedelta(seconds=0)).isoformat(),
            "value": 'quote " slash \\ newline\n snowman ☃',
        },
        {
            "_message_id": "m1",
            "event_time": (_START + timedelta(seconds=1)).isoformat(),
            "value": {"z": [1, True, None], "a": "café"},
        },
        {
            "_message_id": "m2",
            "event_time": (_START + timedelta(seconds=2)).isoformat(),
            "value": ["overshoot", "🧭"],
        },
        {
            "_message_id": "m3",
            "event_time": (_START + timedelta(seconds=3)).isoformat(),
            "value": "unreached",
        },
    ]
    row_sizes = [_encoded_json_bytes(row) for row in rows]
    assert row_sizes == [119, 115, 104, 86]
    exact_cap = row_sizes[0] + row_sizes[1]
    dataset_id = f"capacity-exact-json-{strategy.value}"
    registry, store, cursor_store = _configure_source(tmp_path, dataset_id, rows)
    with pytest.raises(RuntimeError, match="capacity|backpressure|spill"):
        await process_stream_dataset(
            connector_id=_CONNECTOR_ID,
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_runtime_rows,
            runtime_options=_options(
                strategy=strategy,
                max_rows=100,
                max_bytes=exact_cap,
                window_policy=_window_policy(WindowStrategy.SESSION),
            ),
            registry=registry,
        )

    _cursor, checkpoint = _assert_frontier(
        cursor_store,
        dataset_id,
        expected_offset=0,
    )
    retained = checkpoint.metadata["operator_state"]["accumulator"]["session_rows"]
    assert [entry["row"]["_message_id"] for entry in retained] == ["m0", "m1"]
    assert sum(_encoded_json_bytes(entry["row"]) for entry in retained) == exact_cap
    assert set(_stream_chunks(store)) == {0}


@pytest.mark.asyncio
async def test_capacity_oracle_detects_removing_preview_add_row_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The behavioral oracle turns red if preview keeps markers but drops `_add_row`."""
    dataset_id = "capacity-add-row-removal-canary"
    rows = _rows((0, 1, 2, 3))
    registry, store, cursor_store = _configure_source(tmp_path, dataset_id, rows)
    observations = _observe_live_retained_state(monkeypatch)


    original_assert_fit = StreamWindowAccumulator._assert_rows_fit
    original_add_row = StreamWindowAccumulator._add_row

    def remove_preview_transition(
        accumulator: StreamWindowAccumulator,
        rows_to_check: list[dict[str, Any]],
        *,
        max_rows: int,
        max_bytes: int,
        strategy: BackpressureStrategy,
    ) -> None:
        def mutant_add_row(
            selected: StreamWindowAccumulator,
            row: dict[str, Any],
        ) -> list[Any]:
            if selected is not accumulator:
                return []
            return original_add_row(selected, row)

        monkeypatch.setattr(StreamWindowAccumulator, "_add_row", mutant_add_row)
        try:
            original_assert_fit(
                accumulator,
                rows_to_check,
                max_rows=max_rows,
                max_bytes=max_bytes,
                strategy=strategy,
            )
        finally:
            monkeypatch.setattr(StreamWindowAccumulator, "_add_row", original_add_row)

    monkeypatch.setattr(
        StreamWindowAccumulator,
        "_assert_rows_fit",
        remove_preview_transition,
    )

    await process_stream_dataset(
        connector_id=_CONNECTOR_ID,
        dataset_id=dataset_id,
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_runtime_rows,
        runtime_options=_options(
            strategy=BackpressureStrategy.PAUSE,
            max_rows=3,
            max_bytes=100_000,
            window_policy=_window_policy(WindowStrategy.SESSION),
        ),
        registry=registry,
    )
    assert any(rows_seen > 3 for rows_seen, _ in observations)
    with pytest.raises(AssertionError, match="retained rows exceed declared capacity"):
        _assert_within_capacity(observations, max_rows=3, max_bytes=100_000)
