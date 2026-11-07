"""Exact retained serialization accounting across canonical window transitions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.graph import resolve_dependency_graph
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.cursor import WindowStrategy
from polisyos.fabric.connectors.types import DataChunk
from polisyos.fabric.data_plane import streaming
from polisyos.fabric.data_plane.streaming import StreamCapacityError, StreamWindowAccumulator
from polisyos.fabric.data_plane.watermark import WindowAssignment, WindowPolicy
from polisyos.fabric.quality.processing_guarantees import stream_processing_contract

if TYPE_CHECKING:
    from pathlib import Path

_BUFFER_NAMES = ("count_buffer", "sliding_rows", "bucket_rows", "session_rows", "sliding_time_rows")


def _serialized_size(row: object) -> int:
    # Independent full-scan oracle for the existing public serialization-size contract.
    return len(json.dumps(row, sort_keys=True, default=str).encode("utf-8"))


def _assert_accounting(accumulator: StreamWindowAccumulator) -> None:
    state = accumulator.snapshot()
    rows = [entry["row"] for name in _BUFFER_NAMES for entry in state[name]]
    assert accumulator.buffered_rows() == len(rows)
    assert accumulator.buffered_bytes() == sum(_serialized_size(row) for row in rows)


def _row(index: int, seconds: int | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"index": index, "nested": {"values": [index, "é"]}}
    if seconds is not None:
        row["event_time"] = (
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
        ).isoformat()
    return row


@pytest.mark.parametrize(
    ("policy", "timestamps", "expected"),
    [
        (WindowPolicy(WindowStrategy.COUNT, size=3), [None] * 5, [[0, 1, 2], [3, 4]]),
        (WindowPolicy(WindowStrategy.TUMBLING, size=3), [None] * 5, [[0, 1, 2], [3, 4]]),
        (WindowPolicy(WindowStrategy.TUMBLING, size=10), [0, 1, 10, 11, 23], [[0, 1], [2, 3], [4]]),
        (
            WindowPolicy(WindowStrategy.SESSION, size=10, session_gap_seconds=2),
            [0, 1, 6, 7, 10],
            [[0, 1], [2, 3], [4]],
        ),
        (WindowPolicy(WindowStrategy.SLIDING, size=3, slide=2), [None] * 5, [[0, 1, 2], [2, 3, 4]]),
        (
            WindowPolicy(WindowStrategy.SLIDING, size=4, slide=2),
            [0, 1, 2, 7, 8],
            [[0], [0, 1, 2], [3], [3, 4]],
        ),
    ],
    ids=["count", "tumbling-count", "tumbling-time", "session", "sliding-count", "sliding-time"],
)
def test_exact_bytes_survive_preview_transitions_restart_and_flush(
    policy: WindowPolicy,
    timestamps: list[int | None],
    expected: list[list[int]],
) -> None:
    accumulator = StreamWindowAccumulator(policy, max_rows=20, max_bytes=100_000)
    emissions = []
    for index, timestamp in enumerate(timestamps):
        row = _row(index, timestamp)
        before = accumulator.snapshot()
        bytes_before = accumulator.buffered_bytes()
        accumulator.admit_rows([row])
        assert accumulator.snapshot() == before
        assert accumulator.buffered_bytes() == bytes_before
        _assert_accounting(accumulator)
        emissions.extend(accumulator.add_rows_with_refs([row], (f"raw-{index}",)))
        _assert_accounting(accumulator)

        # This remains a version-1 legacy checkpoint without a trusted byte counter.
        state = json.loads(json.dumps(accumulator.snapshot(), sort_keys=True))
        assert state["version"] == 1
        resumed = StreamWindowAccumulator(policy, max_rows=20, max_bytes=100_000)
        resumed.restore(state)
        assert resumed.snapshot() == accumulator.snapshot()
        _assert_accounting(resumed)
        accumulator = resumed

    emissions.extend(accumulator.flush_with_refs())
    _assert_accounting(accumulator)
    assert accumulator.buffered_rows() == accumulator.buffered_bytes() == 0
    assert [[row["index"] for row in item.assignment.rows] for item in emissions] == expected
    assert [item.assignment.ordinal for item in emissions] == list(range(len(emissions)))
    for emission in emissions:
        assert emission.contributor_refs == tuple(
            f"raw-{row['index']}" for row in emission.assignment.rows
        )


@pytest.mark.parametrize("size", [20, 40, 80])
def test_session_byte_estimation_is_once_per_owned_occurrence_and_restore(
    monkeypatch: pytest.MonkeyPatch,
    size: int,
) -> None:
    calls = 0
    estimate = streaming._estimate_row_bytes

    def measured(row: object) -> int:
        nonlocal calls
        calls += 1
        return estimate(row)

    monkeypatch.setattr(streaming, "_estimate_row_bytes", measured)
    policy = WindowPolicy(WindowStrategy.SESSION, size=1_000)
    accumulator = StreamWindowAccumulator(policy, max_rows=100, max_bytes=100_000)
    repeated = {"nested": {"value": ["same-object"]}}
    for _ in range(size):
        accumulator.add_rows([repeated])
        _assert_accounting(accumulator)
        accumulator.buffered_bytes()
    assert calls == size
    assert accumulator.buffered_bytes() == size * _serialized_size(repeated)
    assert calls == size, "buffered_bytes must not serialize retained payloads"

    checkpoint = json.loads(json.dumps(accumulator.snapshot()))
    resumed = StreamWindowAccumulator(policy)
    resumed.restore(checkpoint)
    assert calls == 2 * size, "restore must rebuild each retained occurrence exactly once"
    _assert_accounting(resumed)
    assert calls == 2 * size


def test_repeated_mutable_input_occurrences_own_payloads_and_provenance() -> None:
    accumulator = StreamWindowAccumulator(WindowPolicy(WindowStrategy.SESSION, size=1_000))
    shared = {"nested": {"value": ["first"]}}
    accumulator.add_rows_with_refs([shared], ("raw-first",))
    shared["nested"]["value"].append("second")
    accumulator.add_rows_with_refs([shared], ("raw-second",))
    shared["nested"]["value"].append("caller-mutated-after-admission")
    expected = [
        {"nested": {"value": ["first"]}},
        {"nested": {"value": ["first", "second"]}},
    ]
    assert [entry["row"] for entry in accumulator.snapshot()["session_rows"]] == expected
    _assert_accounting(accumulator)
    (emission,) = accumulator.flush_with_refs()
    assert list(emission.assignment.rows) == expected
    assert emission.contributor_refs == ("raw-first", "raw-second")
    _assert_accounting(accumulator)


@pytest.mark.parametrize("timed", [False, True], ids=["count", "time"])
def test_snapshot_and_retained_sliding_emission_do_not_expose_owned_mutability(timed: bool) -> None:
    policy = WindowPolicy(WindowStrategy.SLIDING, size=2, slide=1)
    accumulator = StreamWindowAccumulator(policy)
    first = _row(0, 0 if timed else None)
    accumulator.add_rows_with_refs([first], ("raw-0",))
    emissions = accumulator.add_rows_with_refs([_row(1, 1 if timed else None)], ("raw-1",))
    before = accumulator.snapshot()
    bytes_before = accumulator.buffered_bytes()
    for emission in emissions:
        for row in emission.assignment.rows:
            row["nested"]["values"].append("mutated-output")
    snapshot = accumulator.snapshot()
    buffer_name = "sliding_time_rows" if timed else "sliding_rows"
    snapshot[buffer_name][0]["row"]["nested"]["values"].append("mutated-snapshot")
    first["nested"]["values"].append("mutated-input")
    assert accumulator.snapshot() == before
    assert accumulator.buffered_bytes() == bytes_before
    _assert_accounting(accumulator)


@pytest.mark.parametrize(
    "strategy", ["count", "tumbling", "session", "sliding-count", "sliding-time"]
)
def test_exact_capacity_closing_transition_and_rejected_preview_preserve_state(
    strategy: str,
) -> None:
    timed = strategy in {"tumbling", "session", "sliding-time"}
    first = _row(0, 0 if timed else None)
    closing = _row(1, 10 if timed else None)
    policies = {
        "count": WindowPolicy(WindowStrategy.COUNT, size=2),
        "tumbling": WindowPolicy(WindowStrategy.TUMBLING, size=10),
        "session": WindowPolicy(WindowStrategy.SESSION, size=10, session_gap_seconds=2),
        "sliding-count": WindowPolicy(WindowStrategy.SLIDING, size=1, slide=1),
        "sliding-time": WindowPolicy(WindowStrategy.SLIDING, size=2, slide=1),
    }
    max_rows = 2 if strategy == "count" else 1
    cap = _serialized_size(first) + (_serialized_size(closing) if strategy == "count" else 0)
    accumulator = StreamWindowAccumulator(policies[strategy], max_rows=max_rows, max_bytes=cap)
    accumulator.add_rows_with_refs([first], ("raw-0",))
    _assert_accounting(accumulator)
    before = accumulator.snapshot()
    oversized = {**first, "oversized": "x" * (cap + 1)}
    with pytest.raises(StreamCapacityError):
        accumulator.admit_rows([oversized])
    assert accumulator.snapshot() == before
    _assert_accounting(accumulator)
    accumulator.admit_rows([closing])
    emissions = accumulator.add_rows_with_refs([closing], ("raw-1",))
    assert emissions, "a legitimate logical window close must stay useful at the exact cap"
    _assert_accounting(accumulator)
    assert accumulator.buffered_bytes() <= cap
    accumulator.flush_with_refs()
    _assert_accounting(accumulator)


@pytest.mark.asyncio
async def test_selected_chunk_refs_survive_owned_accumulator_restart_and_actual_window_graph(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    adapter = AsyncArtifactStoreAdapter(store)
    contract = stream_processing_contract()
    policy = WindowPolicy(WindowStrategy.COUNT, size=2)
    accumulator = StreamWindowAccumulator(policy)
    refs = []
    emissions = []
    for index in range(2):
        rows = [{"index": index}]
        chunk = DataChunk(
            data=rows,
            chunk_index=index,
            row_count=len(rows),
            is_first=index == 0,
            is_last=index == 1,
        )
        ref = await streaming._persist_stream_chunk_async(
            store=adapter,
            connector_id="finite-selected-fixture",
            dataset_id="rows",
            partition_key="default",
            chunk=chunk,
            rows=rows,
            dedupe_dropped=0,
            processing_contract=contract,
        )
        assert ref.manifest_profile_sha256 is not None
        refs.append(ref)
        emissions.extend(accumulator.add_rows_with_refs(rows, (ref,)))
        if index == 0:
            state = json.loads(json.dumps(accumulator.snapshot()))
            resumed = StreamWindowAccumulator(policy)
            resumed.restore(state)
            accumulator = resumed
    (emission,) = emissions
    assert emission.contributor_refs == tuple(refs)
    selected = await streaming._persist_stream_window_async(
        store=adapter,
        connector_id="finite-selected-fixture",
        dataset_id="rows",
        partition_key="default",
        assignment=emission.assignment,
        processing_contract=contract,
        window_policy=policy,
        input_refs=emission.contributor_refs,
    )
    assert selected.manifest_profile_sha256 is not None
    fresh = FileSystemCAS(tmp_path / "cas")
    graph = resolve_dependency_graph(fresh, selected, preserve_manifest_profiles=True)
    assert graph.is_complete
    assert {(str(edge.child_id), edge.child_manifest_profile_sha256) for edge in graph.edges} == {
        (str(ref.artifact_id), ref.manifest_profile_sha256) for ref in refs
    }
    reader = getattr(streaming, "read_stream_window", None)
    assert callable(reader), "window consumption needs the canonical complete-basis reader"
    payload = reader(fresh, selected)
    assert payload["data"] == [{"index": 0}, {"index": 1}]
    assert payload["lineage"]["selected_contributor_chunk_refs"] == [
        ref.model_dump(mode="json") for ref in refs
    ]


@pytest.mark.parametrize("selected", [True, False], ids=["selected-views", "legacy-unbound"])
def test_window_writer_keeps_same_blob_selected_views_and_explicit_legacy_limit(
    tmp_path: Path,
    selected: bool,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    refs = [
        store.put_json(
            {"data": [{"index": 0}]},
            ArtifactWriteOptions(
                kind="fabric.stream_chunk",
                media_type="application/json",
                schema=SchemaInfo(name="fabric.StreamChunk", version=version),
            ),
            return_selected_profile=True,
        )
        for version in ("1.0", "2.0")
    ]
    assert refs[0].artifact_id == refs[1].artifact_id
    assert refs[0].manifest_profile_sha256 != refs[1].manifest_profile_sha256
    window = streaming.persist_stream_window(
        store=store,
        connector_id="finite-selected-fixture",
        dataset_id="rows",
        partition_key="default",
        assignment=WindowAssignment("count:0", WindowStrategy.COUNT, 1, ({"index": 0},)),
        input_refs=tuple(refs) if selected else (str(refs[0].artifact_id),),
    )
    assert window.manifest_profile_sha256 is not None
    fresh = FileSystemCAS(tmp_path / "cas")
    graph = resolve_dependency_graph(fresh, window, preserve_manifest_profiles=True)
    payload = load_core_json_artifact(fresh, window)
    reader = getattr(streaming, "read_stream_window", None)
    assert callable(reader)
    if selected:
        assert graph.is_complete
        assert len(graph.edges) == 2, "equal blob IDs cannot collapse distinct selected views"
        assert payload["lineage"]["selected_contributor_chunk_refs"] == [
            ref.model_dump(mode="json") for ref in refs
        ]
        assert payload["lineage"]["unbound_contributor_chunk_refs"] == []
        assert reader(fresh, window)["data"] == [{"index": 0}]
    else:
        assert not graph.is_complete
        assert payload["lineage"]["unbound_contributor_chunk_refs"] == [str(refs[0].artifact_id)]
        with pytest.raises(RuntimeError, match="unbound"):
            reader(fresh, window)


def test_rejected_owned_add_does_not_retain_an_unbuffered_ref_entry() -> None:
    accumulator = StreamWindowAccumulator(
        WindowPolicy(WindowStrategy.SESSION, size=100), max_rows=1, max_bytes=100
    )
    accumulator.add_rows_with_refs([{"value": 1}], ("retained",))
    before = accumulator.snapshot()
    with pytest.raises(StreamCapacityError):
        accumulator.add_rows_with_refs([{"value": "x" * 100}], ("rejected",))
    assert accumulator.snapshot() == before
    assert len(accumulator._row_refs) == accumulator.buffered_rows() == 1
    with pytest.raises(StreamCapacityError):
        accumulator.add_rows([{"value": "y" * 100}])
    assert accumulator.snapshot() == before
    assert len(accumulator._row_refs) == accumulator.buffered_rows() == 1
    _assert_accounting(accumulator)


def test_closing_window_iterator_prunes_exposed_copies_but_keeps_retained_refs() -> None:
    accumulator = StreamWindowAccumulator(WindowPolicy(WindowStrategy.SLIDING, size=1, slide=1))
    iterator = accumulator.iter_rows_with_refs([{"value": 1}], ("retained",))
    emission = next(iterator)
    assert emission.contributor_refs == ("retained",)
    iterator.close()
    assert len(accumulator._row_refs) == accumulator.buffered_rows() == 1
    _assert_accounting(accumulator)
    assert accumulator._refs_for_row(accumulator._sliding_rows[0]) == ("retained",)
    assert accumulator.flush_with_refs() == [], (
        "count-sliding close still drops its incomplete tail"
    )
    assert accumulator._row_refs == {}
