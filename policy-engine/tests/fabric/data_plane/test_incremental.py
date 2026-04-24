"""Tests for incremental ingestion mode and cursor advancement."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.orchestrator import IngestionResult


def _make_evidence_bundle(store: FileSystemCAS):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions

    return store.put_json(
        {
            "schema_version": "1.0",
            "sources": [],
            "notes": ["test"],
        },
        PutOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="EvidenceBundle", version="1.0"),
        ),
    )


class TestBatchIncremental:
    def test_incremental_with_no_prior_cursor(self, tmp_path: Path):
        """batch_incremental with no prior cursor behaves like batch_full."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)

        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with (
            patch(
                "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
                return_value=mock_result,
            ),
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=evidence_ref,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
            )

        assert result.datasets_fetched == 1
        # Cursor should be saved
        cursor_store = CursorStore(store)
        found = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
        assert found is not None

    def test_incremental_saves_cursor_after_success(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)

        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with (
            patch(
                "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
                return_value=mock_result,
            ),
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=evidence_ref,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        assert result.cursor_ref is not None

        cursor_store = CursorStore(store)
        cursor = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
        assert cursor is not None
        assert cursor.watermark_type == WatermarkType.TIMESTAMP
        assert cursor.connector_id == "worldbank.wdi"
        assert cursor.dataset_id == "NY.GDP.MKTP.CD"

    def test_incremental_does_not_save_cursor_on_zero_fetched(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)

        mock_result = IngestionResult(datasets_fetched=0)

        with (
            patch(
                "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
                return_value=mock_result,
            ),
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=None,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        assert result.cursor_ref is None
        cursor_store = CursorStore(store)
        assert cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD") is None

    def test_multiple_incremental_runs_advance_cursor(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)

        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with (
            patch(
                "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
                return_value=mock_result,
            ),
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=evidence_ref,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            # First run
            run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
            )
            cursor_store = CursorStore(store)
            first_cursor = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
            assert first_cursor is not None
            first_value = first_cursor.watermark_value

            # Second run
            import time

            time.sleep(0.01)  # ensure timestamp differs

            run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

            second_cursor = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
            assert second_cursor is not None
            assert second_cursor.watermark_value >= first_value


class TestIncrementalCheckpoint:
    def test_cursor_serialization_roundtrip(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        cursor_store = CursorStore(store)

        now = datetime.now(UTC)
        cursor = CursorState(
            cursor_id="sdmx.source:ECB.EXR",
            connector_id="sdmx.source",
            dataset_id="ECB.EXR",
            watermark_type=WatermarkType.ETAG,
            watermark_value='"etag-v42"',
            created_at=now,
            ingestion_run_id="R_test_001",
            evidence_bundle_ref="sha256:abc123",
            metadata={"note": "test run"},
        )
        ref = cursor_store.save_cursor(cursor)
        loaded = cursor_store.load_cursor(ref.artifact_id)

        assert loaded.cursor_id == cursor.cursor_id
        assert loaded.watermark_type == WatermarkType.ETAG
        assert loaded.watermark_value == '"etag-v42"'
        assert loaded.ingestion_run_id == "R_test_001"
        assert loaded.evidence_bundle_ref == "sha256:abc123"
        assert loaded.metadata == {"note": "test run"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest():
    """Build a lightweight manifest-like object."""
    from types import SimpleNamespace

    return SimpleNamespace(
        datasets=[
            SimpleNamespace(
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                filters={},
            ),
        ],
    )
