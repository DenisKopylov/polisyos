"""Tests for record/replay mode and deterministic regression comparison."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.fabric.data_plane.regression import (
    RegressionResult,
    compare_artifact_hashes,
    compare_ingestion_runs,
)
from polisyos.fabric.data_plane.replay_store import (
    RecordSession,
    ReplayStore,
    collect_fixtures_from_dir,
    make_record_session,
)


# ---------------------------------------------------------------------------
# ReplayStore tests
# ---------------------------------------------------------------------------


class TestReplayStore:
    def test_save_and_load_session_roundtrip(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        replay_store = ReplayStore(store)

        session = RecordSession(
            session_id="sess_001",
            fixtures=[
                {
                    "connector_id": "worldbank.wdi",
                    "dataset_id": "NY.GDP.MKTP.CD",
                    "request_hash": "abc123",
                    "url": "https://api.worldbank.org/v2/...",
                    "method": "GET",
                    "status": 200,
                    "body_b64": "eyJkYXRhIjogW119",
                }
            ],
            connector_datasets=[
                {"connector_id": "worldbank.wdi", "dataset_id": "NY.GDP.MKTP.CD"}
            ],
            recorded_at="2026-02-12T10:00:00Z",
        )

        ref = replay_store.save_record_session(session)
        assert ref is not None
        assert ref.artifact_id is not None

        loaded = replay_store.load_record_session(ref.artifact_id)
        assert loaded.session_id == "sess_001"
        assert len(loaded.fixtures) == 1
        assert loaded.fixtures[0]["connector_id"] == "worldbank.wdi"
        assert loaded.recorded_at == "2026-02-12T10:00:00Z"

    def test_empty_session(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        replay_store = ReplayStore(store)

        session = RecordSession(session_id="empty_sess")
        ref = replay_store.save_record_session(session)
        loaded = replay_store.load_record_session(ref.artifact_id)

        assert loaded.session_id == "empty_sess"
        assert loaded.fixtures == []
        assert loaded.connector_datasets == []

    def test_build_replay_fixture_dir(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        replay_store = ReplayStore(store)

        # Create a session with a fixture that SimulatorFixture can parse
        fixture_dict = {
            "connector_id": "test.conn",
            "dataset_id": "ds1",
            "request_hash": "hash123",
            "url": "https://example.com/api",
            "method": "GET",
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body_b64": "eyJvayI6IHRydWV9",
        }
        session = RecordSession(
            session_id="fixture_sess",
            fixtures=[fixture_dict],
        )

        target = tmp_path / "replay_fixtures"
        target.mkdir()

        # Mock SimulatorFixture where it's actually imported (lazy import inside method)
        with patch(
            "polisyos.fabric.connectors.testing.simulator.SimulatorFixture"
        ) as MockFixture:
            mock_instance = MagicMock()
            mock_instance.connector_id = "test.conn"
            mock_instance.dataset_id = "ds1"
            mock_instance.request_hash = "hash123"
            MockFixture.from_dict.return_value = mock_instance

            result = replay_store.build_replay_fixture_dir(session, target)

        assert result == target
        MockFixture.from_dict.assert_called_once_with(fixture_dict)
        mock_instance.write.assert_called_once()


# ---------------------------------------------------------------------------
# collect_fixtures_from_dir tests
# ---------------------------------------------------------------------------


class TestCollectFixtures:
    def test_empty_dir(self, tmp_path: Path):
        fixtures = collect_fixtures_from_dir(tmp_path)
        assert fixtures == []

    def test_nonexistent_dir(self, tmp_path: Path):
        fixtures = collect_fixtures_from_dir(tmp_path / "nonexistent")
        assert fixtures == []

    def test_invalid_json_skipped(self, tmp_path: Path):
        fixture_dir = tmp_path / "conn" / "ds"
        fixture_dir.mkdir(parents=True)
        (fixture_dir / "bad.json").write_text("not valid json")

        fixtures = collect_fixtures_from_dir(tmp_path)
        assert fixtures == []


# ---------------------------------------------------------------------------
# make_record_session tests
# ---------------------------------------------------------------------------


class TestMakeRecordSession:
    def test_make_session_empty(self, tmp_path: Path):
        session = make_record_session(
            session_id="test_session",
            fixture_root=tmp_path,
        )
        assert session.session_id == "test_session"
        assert session.fixtures == []
        assert session.recorded_at != ""

    def test_make_session_with_connector_datasets(self, tmp_path: Path):
        session = make_record_session(
            session_id="test_session",
            fixture_root=tmp_path,
            connector_datasets=[
                {"connector_id": "a.b", "dataset_id": "d1"},
            ],
        )
        assert len(session.connector_datasets) == 1


# ---------------------------------------------------------------------------
# Regression comparison tests
# ---------------------------------------------------------------------------


class TestRegressionComparison:
    def test_matching_results(self):
        r1 = IngestionResult(datasets_fetched=2, warnings=["w1", "w2"])
        r2 = IngestionResult(datasets_fetched=2, warnings=["w2", "w1"])
        result = compare_ingestion_runs(r1, r2)
        assert result.match is True
        assert result.mismatches == []

    def test_mismatched_datasets_fetched(self):
        r1 = IngestionResult(datasets_fetched=3)
        r2 = IngestionResult(datasets_fetched=2)
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert len(result.mismatches) == 1
        assert "datasets_fetched" in result.mismatches[0]

    def test_mismatched_evidence_presence(self):
        mock_ref = MagicMock()
        r1 = IngestionResult(evidence_bundle_ref=mock_ref)
        r2 = IngestionResult(evidence_bundle_ref=None)
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert any("evidence_bundle_ref" in m for m in result.mismatches)

    def test_mismatched_snapshot_presence(self):
        mock_ref = MagicMock()
        r1 = IngestionResult(data_snapshot_ref=mock_ref)
        r2 = IngestionResult(data_snapshot_ref=None)
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert any("data_snapshot_ref" in m for m in result.mismatches)

    def test_mismatched_warnings(self):
        r1 = IngestionResult(warnings=["w1", "w2"])
        r2 = IngestionResult(warnings=["w1", "w3"])
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert any("warnings" in m for m in result.mismatches)

    def test_regression_result_is_frozen(self):
        result = RegressionResult(match=True, mismatches=[])
        with pytest.raises(AttributeError):
            result.match = False  # type: ignore[misc]


class TestArtifactHashComparison:
    def test_matching_hashes(self):
        mock_store = MagicMock()
        manifest = MagicMock()
        manifest.content_hash = "abc123"
        mock_store.get_manifest.return_value = manifest

        mismatches = compare_artifact_hashes(mock_store, "ref1", "ref2", label="test")
        assert mismatches == []

    def test_mismatched_hashes(self):
        mock_store = MagicMock()
        m1 = MagicMock()
        m1.content_hash = "abc123"
        m2 = MagicMock()
        m2.content_hash = "def456"
        mock_store.get_manifest.side_effect = [m1, m2]

        mismatches = compare_artifact_hashes(mock_store, "ref1", "ref2", label="test")
        assert len(mismatches) == 1
        assert "content_hash" in mismatches[0]

    def test_comparison_error_handled(self):
        mock_store = MagicMock()
        mock_store.get_manifest.side_effect = RuntimeError("not found")

        mismatches = compare_artifact_hashes(mock_store, "ref1", "ref2")
        assert len(mismatches) == 1
        assert "failed" in mismatches[0]
