"""Tests for CursorStore (CAS-backed cursor persistence)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.fabric.data_plane.cursor_store import CursorStore

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


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


class TestCursorStateModel:
    def test_cursor_state_valid(self):
        cursor = _make_cursor()
        assert cursor.cursor_id == "worldbank.wdi:NY.GDP.MKTP.CD"
        assert cursor.watermark_type == WatermarkType.TIMESTAMP

    def test_cursor_state_extra_forbid(self):
        with pytest.raises(Exception):
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
