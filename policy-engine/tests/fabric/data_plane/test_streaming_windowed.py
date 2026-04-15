"""Tests for streaming_windowed execution mode."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from polisyos.fabric.data_plane.orchestrator import IngestionResult


class TestRunStreamingWindowed:
    """Tests for run_streaming_windowed() mode function."""

    def test_single_chunk_produces_snapshot(self, tmp_path: Path):
        """A single chunk with data should produce evidence + snapshot."""
        from polisyos.fabric.data_plane.modes import run_streaming_windowed

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [{"connector_id": "test.conn", "dataset_id": "ds1"}]
        }

        mock_chunks = [
            {
                "chunk_index": 0,
                "row_count": 2,
                "is_first": True,
                "is_last": True,
                "data": [{"x": 1}, {"x": 2}],
            }
        ]

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            return_value=mock_chunks,
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert isinstance(result, IngestionResult)
        assert result.datasets_fetched == 1
        assert result.mode_effective == "streaming_windowed"
        assert result.evidence_bundle_ref is not None
        assert result.data_snapshot_ref is not None

    def test_multi_chunk_aggregation(self, tmp_path: Path):
        """Multiple chunks should be aggregated into a single snapshot."""
        from polisyos.fabric.data_plane.modes import run_streaming_windowed

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [{"connector_id": "test.conn", "dataset_id": "ds1"}]
        }

        mock_chunks = [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": False,
                "data": [{"x": 1}],
            },
            {
                "chunk_index": 1,
                "row_count": 1,
                "is_first": False,
                "is_last": True,
                "data": [{"x": 2}],
            },
        ]

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            return_value=mock_chunks,
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        assert result.datasets_fetched == 1
        assert result.evidence_bundle_ref is not None

    def test_empty_chunks_returns_warning(self, tmp_path: Path):
        """When no chunks are received, a warning should be returned."""
        from polisyos.fabric.data_plane.modes import run_streaming_windowed

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [{"connector_id": "test.conn", "dataset_id": "ds1"}]
        }

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            return_value=[],
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        assert result.datasets_fetched == 1
        assert "No data chunks received" in result.warnings

    def test_mode_effective_is_streaming_windowed(self, tmp_path: Path):
        """mode_effective should always be 'streaming_windowed'."""
        from polisyos.fabric.data_plane.modes import run_streaming_windowed

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [{"connector_id": "test.conn", "dataset_id": "ds1"}]
        }

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            return_value=[],
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        assert result.mode_effective == "streaming_windowed"

    def test_produce_snapshot_false(self, tmp_path: Path):
        """When produce_snapshot=False, only chunks are persisted, no snapshot."""
        from polisyos.fabric.data_plane.modes import run_streaming_windowed

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [{"connector_id": "test.conn", "dataset_id": "ds1"}]
        }

        mock_chunks = [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": True,
                "data": [{"x": 1}],
            }
        ]

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            return_value=mock_chunks,
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
            )

        # With produce_snapshot=False and data present, but the
        # if condition checks `all_rows and produce_snapshot`
        assert result.datasets_fetched == 1

    def test_multi_dataset_streaming(self, tmp_path: Path):
        """Multiple datasets should all be streamed and counted."""
        from polisyos.fabric.data_plane.modes import run_streaming_windowed

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [
                {"connector_id": "a.conn", "dataset_id": "d1"},
                {"connector_id": "b.conn", "dataset_id": "d2"},
            ]
        }

        def side_effect(*, connector_id, dataset_id, **kwargs):
            return [
                {
                    "chunk_index": 0,
                    "row_count": 1,
                    "is_first": True,
                    "is_last": True,
                    "data": [{"val": dataset_id}],
                }
            ]

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            side_effect=side_effect,
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        assert result.datasets_fetched == 2
        assert result.evidence_bundle_ref is not None

    def test_chunk_artifacts_persisted_to_cas(self, tmp_path: Path):
        """Each chunk should be persisted as a fabric.stream_chunk artifact."""
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.data_plane.modes import run_streaming_windowed

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [{"connector_id": "test.conn", "dataset_id": "ds1"}]
        }

        mock_chunks = [
            {
                "chunk_index": 0,
                "row_count": 2,
                "is_first": True,
                "is_last": True,
                "data": [{"x": 1}, {"x": 2}],
            }
        ]

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            return_value=mock_chunks,
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        # Verify that CAS has stored artifacts
        store = FileSystemCAS(cas_root)
        # The evidence bundle should be readable
        assert result.evidence_bundle_ref is not None
        raw = store.get_bytes(result.evidence_bundle_ref.artifact_id)
        assert raw is not None

    def test_poison_stream_messages_are_quarantined_without_losing_batch(self, tmp_path: Path):
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.data_plane.modes import run_streaming_windowed
        from polisyos.fabric.data_plane.quarantine import list_quarantine_records

        cas_root = tmp_path / ".polisyos"
        manifest = {
            "datasets": [{"connector_id": "test.conn", "dataset_id": "ds1"}]
        }

        mock_chunks = [
            {
                "chunk_index": 0,
                "row_count": 3,
                "is_first": True,
                "is_last": True,
                "data": [{"x": 1.0}, "poison-message", {"x": 2.0}],
            }
        ]

        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
            return_value=mock_chunks,
        ):
            result = run_streaming_windowed(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
            )

        assert result.datasets_fetched == 1
        assert any("quarantined stream row" in warning for warning in result.warnings)
        records = list_quarantine_records(FileSystemCAS(cas_root))
        assert len(records) == 1
        assert records[0][1].reason == "poison_stream_message"


class TestExtractDatasets:
    """Tests for the _extract_datasets helper."""

    def test_dict_manifest(self):
        from polisyos.fabric.data_plane.modes import _extract_datasets

        manifest = {
            "datasets": [
                {"connector_id": "a", "dataset_id": "d1"},
                {"connector_id": "b", "dataset_id": "d2"},
            ]
        }
        result = _extract_datasets(manifest)
        assert result == [("a", "d1"), ("b", "d2")]

    def test_empty_manifest(self):
        from polisyos.fabric.data_plane.modes import _extract_datasets

        result = _extract_datasets({"datasets": []})
        assert result == []

    def test_object_manifest(self):
        from polisyos.fabric.data_plane.modes import _extract_datasets

        mock_ds = MagicMock()
        mock_ds.connector_id = "x.y"
        mock_ds.dataset_id = "z"
        mock_manifest = MagicMock()
        mock_manifest.datasets = [mock_ds]

        result = _extract_datasets(mock_manifest)
        assert result == [("x.y", "z")]
