"""Tests for the Data Plane orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    EvidenceBundle,
    EvidenceBundleRef,
)
from polisyos.fabric.data_plane.orchestrator import (
    IngestionResult,
    run_orchestrated_ingestion,
)


def _make_evidence_bundle(store: FileSystemCAS) -> EvidenceBundleRef:
    """Create a minimal EvidenceBundle in CAS and return its ref."""
    # First, create a data artifact that will be referenced by the evidence bundle
    data_ref = store.put_json(
        {"rows": [{"x": 1}]},
        PutOptions(
            kind="fabric.data_payload",
            media_type="application/json",
            schema=SchemaInfo(name="test.data", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    bundle = EvidenceBundle(
        sources=[data_ref],
        notes=["test evidence bundle"],
    )
    ref = store.put_json(
        bundle,
        PutOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.EvidenceBundle", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EvidenceBundleRef(artifact_id=ref.artifact_id)


class TestIngestionResult:
    def test_defaults(self):
        result = IngestionResult()
        assert result.evidence_bundle_ref is None
        assert result.data_snapshot_ref is None
        assert result.datasets_fetched == 0
        assert result.warnings == []

    def test_with_values(self):
        result = IngestionResult(datasets_fetched=3, warnings=["w1"])
        assert result.datasets_fetched == 3
        assert result.warnings == ["w1"]


class TestRunOrchestratedIngestion:
    def test_produce_snapshot_false(self, tmp_path: Path):
        """When produce_snapshot=False, snapshot_ref should be None."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=evidence_ref,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": [{"connector_id": "test", "dataset_id": "ds1"}]},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
            )

        assert result.evidence_bundle_ref == evidence_ref
        assert result.data_snapshot_ref is None
        assert result.datasets_fetched == 1

    def test_produce_snapshot_true(self, tmp_path: Path):
        """When produce_snapshot=True, a DataSnapshot should be built from evidence."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=evidence_ref,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": [{"connector_id": "test", "dataset_id": "ds1"}]},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert result.evidence_bundle_ref == evidence_ref
        assert result.data_snapshot_ref is not None
        assert result.datasets_fetched == 1

        # Verify the snapshot was persisted in CAS and is a valid DataSnapshot
        from polisyos.core.canon import from_canonical_bytes

        snapshot_payload = from_canonical_bytes(
            store.get_bytes(result.data_snapshot_ref.artifact_id)
        )
        snapshot = DataSnapshot.model_validate(snapshot_payload)
        assert snapshot.evidence_ref == evidence_ref
        assert snapshot.quality_report_ref is not None
        assert snapshot.stats["datasets_fetched"] == 1
        assert "fabric.data_plane.orchestrator" in snapshot.notes

    def test_no_evidence_ref_returns_none_snapshot(self, tmp_path: Path):
        """When ingestion returns None, snapshot should also be None."""
        cas_root = tmp_path / ".polisyos"

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": []},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert result.evidence_bundle_ref is None
        assert result.data_snapshot_ref is None

    def test_empty_evidence_sources_skips_snapshot(self, tmp_path: Path):
        """When evidence bundle has no sources, snapshot should be None."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)

        # Create evidence bundle with empty sources
        bundle = EvidenceBundle(sources=[], notes=["empty"])
        ref = store.put_json(
            bundle,
            PutOptions(
                kind="fabric.evidence_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="fabric.EvidenceBundle", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        evidence_ref = EvidenceBundleRef(artifact_id=ref.artifact_id)

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=evidence_ref,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": [{"connector_id": "x", "dataset_id": "y"}]},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert result.evidence_bundle_ref == evidence_ref
        assert result.data_snapshot_ref is None

    def test_connection_config_passed_through(self, tmp_path: Path):
        """connection_config should be forwarded to run_connectors_ingestion."""
        cas_root = tmp_path / ".polisyos"
        fake_config = {"url": "https://test.api.com", "timeout": 30}

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ) as mock_ingest:
            run_orchestrated_ingestion(
                connector_manifest={"datasets": []},
                source="test",
                license_name="open",
                cas_root=cas_root,
                connection_config=fake_config,
                produce_snapshot=False,
            )

        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args.kwargs
        assert call_kwargs["connection_config"] == fake_config

    def test_datasets_counted_from_dict_manifest(self, tmp_path: Path):
        """datasets_fetched should reflect the number of datasets in manifest dict."""
        cas_root = tmp_path / ".polisyos"

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={
                    "datasets": [
                        {"connector_id": "a", "dataset_id": "d1"},
                        {"connector_id": "b", "dataset_id": "d2"},
                        {"connector_id": "c", "dataset_id": "d3"},
                    ]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
            )

        assert result.datasets_fetched == 3
