"""Tests for incremental ingestion mode and cursor advancement."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.fabric.ingestion import IngestionDependencies
from polisyos.ir.connectors import DataVersion, FetchRequest, VersionStrategy


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
                side_effect=_successful_orchestrator(mock_result),
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
                side_effect=_successful_orchestrator(mock_result),
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
                side_effect=_successful_orchestrator(mock_result),
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

    def test_incremental_passes_legacy_cursor_to_typed_and_dict_dataset_requests(
        self,
        tmp_path: Path,
    ):
        """Typed and mapping manifests both pass the stored cursor to FetchRequest."""
        for manifest_index, manifest in enumerate((_make_manifest(), _make_dict_manifest())):
            cas_root = tmp_path / f".polisyos-{manifest_index}"
            store = FileSystemCAS(cas_root)
            cursor_store = CursorStore(store)
            cursor_store.save_cursor(
                CursorState(
                    cursor_id="worldbank.wdi:NY.GDP.MKTP.CD",
                    connector_id="worldbank.wdi",
                    dataset_id="NY.GDP.MKTP.CD",
                    watermark_type=WatermarkType.TIMESTAMP,
                    watermark_value="2024-01-01T00:00:00+00:00",
                    created_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            observed_requests: list[FetchRequest] = []

            class _Connector:
                def fetch(self, handle: object, request: FetchRequest) -> object:
                    del handle
                    observed_requests.append(request)
                    return _fetch_result("2024-01-02T00:00:00+00:00")

            dependencies = _test_dependencies(_Connector())
            evidence_ref = _make_evidence_bundle(store)
            mock_result = IngestionResult(
                evidence_bundle_ref=evidence_ref,
                datasets_fetched=1,
            )

            with patch(
                "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
                side_effect=_request_observing_orchestrator(
                    mock_result,
                    observed_requests,
                ),
            ):
                from polisyos.fabric.data_plane.modes import run_batch_incremental

                run_batch_incremental(
                    connector_manifest=manifest,
                    source="test",
                    license_name="open",
                    cas_root=cas_root,
                    produce_snapshot=False,
                    ingestion_dependencies=dependencies,
                )

            assert len(observed_requests) == 1
            assert observed_requests[0].incremental_since is not None
            assert observed_requests[0].incremental_since.value == (
                "2024-01-01T00:00:00+00:00"
            )
            assert observed_requests[0].incremental_since.strategy is VersionStrategy.TIMESTAMP

    def test_incremental_advances_only_confirmed_dataset_boundaries(self, tmp_path: Path):
        """An aggregate success advances only datasets with a confirmed fetch result."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        manifest = {
            "datasets": [
                {"connector_id": "alpha.source", "dataset_id": "A"},
                {"connector_id": "beta.source", "dataset_id": "B"},
            ]
        }
        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )
        confirmed_result = _fetch_result("2024-01-09T00:00:00+00:00")

        def _partial_orchestrator(**kwargs: object) -> IngestionResult:
            sink = kwargs["raw_result_sink"]
            assert callable(sink)
            sink(
                "alpha.source",
                "A",
                FetchRequest(dataset_id="A"),
                confirmed_result,
            )
            return mock_result

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=_partial_orchestrator,
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
            )

        cursor_store = CursorStore(store)
        cursor_a = cursor_store.find_latest_cursor("alpha.source", "A")
        cursor_b = cursor_store.find_latest_cursor("beta.source", "B")
        assert result.cursor_ref is not None
        assert cursor_a is not None
        assert cursor_a.watermark_value == "2024-01-09T00:00:00+00:00"
        assert cursor_b is None


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


def _make_dict_manifest() -> dict[str, list[dict[str, str]]]:
    return {
        "datasets": [
            {
                "connector_id": "worldbank.wdi",
                "dataset_id": "NY.GDP.MKTP.CD",
            }
        ]
    }


def _fetch_result(source_updated_at: str) -> SimpleNamespace:
    boundary = datetime.fromisoformat(source_updated_at)
    return SimpleNamespace(
        source_updated_at=boundary,
        fetched_at=boundary,
        version=DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value=source_updated_at,
            timestamp=boundary,
        ),
        evidence_ref=None,
    )


def _test_dependencies(connector: object) -> IngestionDependencies:
    class _Registry:
        def get(self, connector_id: str) -> object:
            del connector_id
            return connector

    return IngestionDependencies(
        registry=_Registry(),
        tracer=SimpleNamespace(),
        metrics=SimpleNamespace(),
    )


def _successful_orchestrator(mock_result: IngestionResult):
    def _run(**kwargs: object) -> IngestionResult:
        sink = kwargs["raw_result_sink"]
        assert callable(sink)
        manifest = kwargs["connector_manifest"]
        datasets = manifest.datasets if hasattr(manifest, "datasets") else manifest["datasets"]
        for dataset in datasets:
            connector_id = (
                dataset.connector_id if hasattr(dataset, "connector_id") else dataset["connector_id"]
            )
            dataset_id = (
                dataset.dataset_id if hasattr(dataset, "dataset_id") else dataset["dataset_id"]
            )
            sink(
                connector_id,
                dataset_id,
                FetchRequest(dataset_id=dataset_id),
                _fetch_result("2024-01-02T00:00:00+00:00"),
            )
        return mock_result

    return _run


def _request_observing_orchestrator(
    mock_result: IngestionResult,
    observed_requests: list[FetchRequest],
):
    def _run(**kwargs: object) -> IngestionResult:
        dependencies = kwargs["ingestion_dependencies"]
        assert isinstance(dependencies, IngestionDependencies)
        manifest = kwargs["connector_manifest"]
        dataset = manifest.datasets[0] if hasattr(manifest, "datasets") else manifest["datasets"][0]
        connector_id = (
            dataset.connector_id if hasattr(dataset, "connector_id") else dataset["connector_id"]
        )
        dataset_id = (
            dataset.dataset_id if hasattr(dataset, "dataset_id") else dataset["dataset_id"]
        )
        connector = dependencies.registry.get(connector_id)
        connector.fetch(None, FetchRequest(dataset_id=dataset_id))
        assert observed_requests
        sink = kwargs["raw_result_sink"]
        assert callable(sink)
        sink(
            connector_id,
            dataset_id,
            observed_requests[-1],
            _fetch_result("2024-01-02T00:00:00+00:00"),
        )
        return mock_result

    return _run
