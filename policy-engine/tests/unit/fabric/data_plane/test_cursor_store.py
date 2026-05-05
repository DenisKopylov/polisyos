"""Tests for CursorStore (CAS-backed cursor persistence)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import (
    CursorState,
    PartitionCursorState,
    StreamCheckpoint,
    StreamLifecycleState,
    WatermarkType,
)
from polisyos.fabric.data_plane.cursor_store import (
    AsyncCursorStoreAdapter,
    CursorStore,
    CursorStoreError,
)
from pydantic import ValidationError

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


def _make_cursor(
    connector_id: str = "worldbank.wdi",
    dataset_id: str = "NY.GDP.MKTP.CD",
    watermark_value: str = "2024-06-15T12:00:00+00:00",
) -> CursorState:
    return CursorState(
        cursor_id=f"{connector_id}:{dataset_id}",
        connector_id=connector_id,
        dataset_id=dataset_id,
        watermark_type=WatermarkType.TIMESTAMP,
        watermark_value=watermark_value,
        created_at=_NOW,
    )


def _make_stream_checkpoint(
    connector_id: str = "stream.jsonl",
    dataset_id: str = "events",
    partition_key: str = "default",
    offset: int = 3,
) -> StreamCheckpoint:
    return StreamCheckpoint(
        checkpoint_id=f"{connector_id}:{dataset_id}:{partition_key}:{offset}",
        stream_id=f"{connector_id}:{dataset_id}:{partition_key}",
        connector_id=connector_id,
        dataset_id=dataset_id,
        partition_key=partition_key,
        offset=offset,
        resume_token=f"resume-{offset}",
        lifecycle_state=StreamLifecycleState.ACTIVE,
        dedupe_keys=("m1", "m2"),
        created_at=_NOW,
        metadata={"schema_fields": ["value"]},
    )


def _make_partition_state(
    plan_id: str = "plan.test",
    partition_id: str = "partition-0",
    status: str = "pending",
) -> PartitionCursorState:
    return PartitionCursorState(
        plan_id=plan_id,
        partition_id=partition_id,
        connector_id="stream.jsonl",
        dataset_id="events",
        partition_key="region",
        partition_bounds={"region": "ua"},
        source_cursor="cursor-0",
        expected_cardinality=10,
        merge_policy="append",
        status=status,
        updated_at=_NOW,
        metadata={"tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
    )


class TestCursorStateModel:
    def test_cursor_state_valid(self):
        cursor = _make_cursor()
        assert cursor.cursor_id == "worldbank.wdi:NY.GDP.MKTP.CD"
        assert cursor.watermark_type == WatermarkType.TIMESTAMP

    def test_cursor_state_extra_forbid(self):
        with pytest.raises(ValidationError):
            CursorState(
                cursor_id="x:y",
                connector_id="x",
                dataset_id="y",
                watermark_type=WatermarkType.TIMESTAMP,
                watermark_value="val",
                created_at=_NOW,
                unknown_field="boom",  # type: ignore[call-arg]
            )


class TestCursorStore:
    def test_accepts_protocol_store_with_explicit_index_root(self, tmp_path: Path):
        class _RootlessStoreProxy:
            def __init__(self, inner: FileSystemCAS) -> None:
                self._inner = inner

            def has(self, artifact_id: Any) -> bool:
                return self._inner.has(artifact_id)

            def get_bytes(self, artifact_id: Any) -> bytes:
                return self._inner.get_bytes(artifact_id)

            def get_manifest(self, artifact_id: Any) -> Any:
                return self._inner.get_manifest(artifact_id)

            def put_bytes(self, data: bytes, opts: Any) -> Any:
                return self._inner.put_bytes(data, opts)

            def put_json(self, obj: object, opts: Any, canon_spec: Any = None) -> Any:
                return self._inner.put_json(obj, opts, canon_spec=canon_spec)

            def verify(self, artifact_id: Any) -> Any:
                return self._inner.verify(artifact_id)

            def iter_artifact_ids(self) -> list[Any]:
                return self._inner.iter_artifact_ids()

        store = _RootlessStoreProxy(FileSystemCAS(tmp_path / ".polisyos"))
        cursor_store = CursorStore(store, index_root=tmp_path / ".cursor-index")
        ref = cursor_store.save_cursor(_make_cursor())

        assert ref is not None
        assert cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD") is not None

    def test_save_and_load_cursor(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)

        cursor = _make_cursor()
        ref = cursor_store.save_cursor(cursor)
        assert ref is not None

        loaded = cursor_store.load_cursor(ref.artifact_id)
        assert loaded.cursor_id == cursor.cursor_id
        assert loaded.watermark_value == cursor.watermark_value
        assert loaded.watermark_type == WatermarkType.TIMESTAMP

    def test_find_latest_cursor(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)

        cursor = _make_cursor()
        cursor_store.save_cursor(cursor)

        found = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
        assert found is not None
        assert found.cursor_id == "worldbank.wdi:NY.GDP.MKTP.CD"

    def test_find_latest_cursor_returns_none_for_unknown(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)

        found = cursor_store.find_latest_cursor("unknown.connector", "unknown.dataset")
        assert found is None

    def test_save_cursor_updates_index(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)

        c1 = _make_cursor(watermark_value="2024-01-01T00:00:00+00:00")
        cursor_store.save_cursor(c1)

        c2 = _make_cursor(watermark_value="2024-06-15T12:00:00+00:00")
        cursor_store.save_cursor(c2)

        # Latest should be c2
        found = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
        assert found is not None
        assert found.watermark_value == "2024-06-15T12:00:00+00:00"

    def test_list_cursors(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)

        cursor_store.save_cursor(_make_cursor(dataset_id="NY.GDP.MKTP.CD"))
        cursor_store.save_cursor(_make_cursor(dataset_id="SP.POP.TOTL"))

        cursors = cursor_store.list_cursors()
        assert len(cursors) == 2
        ids = {c.cursor_id for c in cursors}
        assert "worldbank.wdi:NY.GDP.MKTP.CD" in ids
        assert "worldbank.wdi:SP.POP.TOTL" in ids

    def test_index_persistence_across_instances(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)

        # First instance: save cursor
        cs1 = CursorStore(store)
        cs1.save_cursor(_make_cursor())

        # Second instance: should find cursor
        cs2 = CursorStore(store)
        found = cs2.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
        assert found is not None

    def test_concurrent_writers_do_not_lose_cursor_updates(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"

        def _write(index: int) -> None:
            store = FileSystemCAS(cas_root)
            cursor_store = CursorStore(store)
            cursor_store.save_cursor(
                _make_cursor(
                    connector_id="worldbank.wdi",
                    dataset_id=f"dataset.{index}",
                    watermark_value=f"2024-06-{index + 1:02d}T00:00:00+00:00",
                )
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(_write, range(20)))

        cursor_store = CursorStore(FileSystemCAS(cas_root))
        cursors = cursor_store.list_cursors()
        assert {cursor.dataset_id for cursor in cursors} == {
            f"dataset.{index}" for index in range(20)
        }

    def test_orphan_tmp_file_is_removed_without_replacing_valid_index(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        cursor_store = CursorStore(store)
        cursor_store.save_cursor(_make_cursor())
        tmp_file = cas_root / ".cursor_index.json.interrupted.tmp"
        tmp_file.write_text("{not-json", encoding="utf-8")

        reopened = CursorStore(FileSystemCAS(cas_root))

        assert not tmp_file.exists()
        assert reopened.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD") is not None

    def test_corrupt_cursor_index_fails_closed(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        cas_root.mkdir(parents=True)
        (cas_root / "cursor_index.json").write_text("{not-json", encoding="utf-8")

        with pytest.raises(CursorStoreError):
            CursorStore(FileSystemCAS(cas_root))

    def test_save_find_pause_resume_and_rewind_stream_checkpoint(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)
        resume_marker = "resume-7"
        rewound_marker = "resume-2"

        checkpoint = _make_stream_checkpoint(offset=7)
        ref = cursor_store.save_stream_checkpoint(checkpoint)
        loaded = cursor_store.load_stream_checkpoint(ref.artifact_id)
        assert loaded.offset == 7

        found = cursor_store.find_latest_stream_checkpoint("stream.jsonl", "events")
        assert found is not None
        assert found.resume_token == resume_marker

        paused = cursor_store.pause_stream(
            "stream.jsonl", "events", metadata={"reason": "backpressure"}
        )
        assert paused.lifecycle_state == StreamLifecycleState.PAUSED
        assert paused.metadata["reason"] == "backpressure"

        resumed = cursor_store.resume_stream("stream.jsonl", "events")
        assert resumed.lifecycle_state == StreamLifecycleState.ACTIVE

        rewound = cursor_store.rewind_stream(
            "stream.jsonl",
            "events",
            offset=2,
            resume_token=rewound_marker,
        )
        assert rewound.offset == 2
        assert rewound.resume_token == rewound_marker
        assert rewound.metadata["rewound"] is True

        closed = cursor_store.close_stream("stream.jsonl", "events")
        assert closed.lifecycle_state == StreamLifecycleState.CLOSED

    def test_commit_stream_progress_updates_cursor_and_checkpoint_indices(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)

        cursor = _make_cursor(
            connector_id="stream.jsonl", dataset_id="events", watermark_value="42"
        )
        checkpoint = _make_stream_checkpoint(offset=42)
        cursor_ref, checkpoint_ref = cursor_store.commit_stream_progress(
            cursor=cursor,
            checkpoint=checkpoint,
        )

        assert str(cursor_ref.artifact_id)
        assert checkpoint_ref is not None
        assert cursor_store.find_latest_cursor("stream.jsonl", "events") is not None
        loaded_checkpoint = cursor_store.find_latest_stream_checkpoint("stream.jsonl", "events")
        assert loaded_checkpoint is not None
        assert loaded_checkpoint.offset == 42

    @pytest.mark.asyncio
    async def test_async_cursor_store_commit_stream_progress_soak_smoke(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = AsyncCursorStoreAdapter(CursorStore(store), timeout_seconds=2.0)

        for index in range(48):
            cursor = _make_cursor(
                connector_id="stream.jsonl",
                dataset_id="events",
                watermark_value=str(index),
            )
            checkpoint = _make_stream_checkpoint(offset=index)
            cursor_ref, checkpoint_ref = await cursor_store.commit_stream_progress(
                cursor=cursor,
                checkpoint=checkpoint,
            )
            assert str(cursor_ref.artifact_id)
            assert checkpoint_ref is not None

        latest_cursor = await cursor_store.find_latest_cursor("stream.jsonl", "events")
        latest_checkpoint = await cursor_store.find_latest_stream_checkpoint(
            "stream.jsonl",
            "events",
        )
        assert latest_cursor is not None
        assert latest_cursor.watermark_value == "47"
        assert latest_checkpoint is not None
        assert latest_checkpoint.offset == 47

    def test_save_and_list_partition_states(self, tmp_path: Path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        cursor_store = CursorStore(store)

        first = _make_partition_state(partition_id="partition-0", status="failed")
        second = _make_partition_state(partition_id="partition-1", status="succeeded")
        cursor_store.save_partition_state(first)
        cursor_store.save_partition_state(second)

        listed = cursor_store.list_partition_states(plan_id="plan.test")
        assert {state.partition_id for state in listed} == {"partition-0", "partition-1"}
        failed = cursor_store.find_partition_state("plan.test", "partition-0")
        assert failed is not None
        assert failed.status == "failed"
