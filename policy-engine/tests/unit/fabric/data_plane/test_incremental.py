"""Tests for incremental ingestion mode and cursor advancement."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.fabric.ingestion import IngestionDependencies
from polisyos.ir.connectors import (
    ConnectorCapability,
    DataVersion,
    FetchRequest,
    FetchResult,
    VersionStrategy,
)


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
                ingestion_dependencies=_supported_dependencies(),
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
                ingestion_dependencies=_supported_dependencies(),
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
            dependencies = _supported_dependencies()

            # First run
            run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
                ingestion_dependencies=dependencies,
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
                ingestion_dependencies=dependencies,
            )

            second_cursor = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
            assert second_cursor is not None
            assert second_cursor.watermark_value >= first_value

    def test_incremental_does_not_pass_unproven_legacy_cursor_to_requests(
        self,
        tmp_path: Path,
    ):
        """Legacy cursors without admitted provenance remain in full mode."""
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
                capabilities = (
                    ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH
                )

                def __init__(self, observed_requests: list[FetchRequest]) -> None:
                    self._observed_requests = observed_requests

                def fetch(self, handle: object, request: FetchRequest) -> object:
                    del handle
                    self._observed_requests.append(request)
                    return _fetch_result("2024-01-02T00:00:00+00:00")

            dependencies = _test_dependencies(_Connector(observed_requests))
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
            assert observed_requests[0].incremental_since is None

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
                ingestion_dependencies=_supported_dependencies(),
            )

        cursor_store = CursorStore(store)
        cursor_a = cursor_store.find_latest_cursor("alpha.source", "A")
        cursor_b = cursor_store.find_latest_cursor("beta.source", "B")
        assert result.cursor_ref is not None
        assert cursor_a is not None
        assert cursor_a.watermark_value == "2024-01-09T00:00:00+00:00"
        assert cursor_b is None

    def test_incremental_does_not_promote_fetched_at_without_source_boundary(
        self,
        tmp_path: Path,
    ):
        """A local fetch time is not an incremental source boundary."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        fetched_at = datetime(2024, 1, 2, tzinfo=UTC)
        connector = _RecordingConnector(
            _typed_fetch_result(source_updated_at=None, fetched_at=fetched_at),
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert result.cursor_ref is None
        assert CursorStore(store).find_latest_cursor(
            "worldbank.wdi", "NY.GDP.MKTP.CD"
        ) is None

    @pytest.mark.parametrize(
        ("has_more", "next_page_token", "completeness"),
        [
            (True, "page-2", 1.0),
            (False, None, 0.5),
        ],
    )
    def test_incremental_does_not_advance_incomplete_result(
        self,
        tmp_path: Path,
        has_more: bool,
        next_page_token: str | None,
        completeness: float,
    ):
        """Pagination or partial coverage leaves the prior cursor unchanged."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        cursor_store = CursorStore(store)
        previous_value = "2024-01-01T00:00:00+00:00"
        cursor_store.save_cursor(
            CursorState(
                cursor_id="worldbank.wdi:NY.GDP.MKTP.CD",
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                watermark_type=WatermarkType.TIMESTAMP,
                watermark_value=previous_value,
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        evidence_ref = _make_evidence_bundle(store)
        connector = _RecordingConnector(
            _typed_fetch_result(
                source_updated_at=datetime(2024, 1, 2, tzinfo=UTC),
                fetched_at=datetime(2024, 1, 3, tzinfo=UTC),
                has_more=has_more,
                next_page_token=next_page_token,
                completeness=completeness,
            ),
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        cursor = cursor_store.find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
        assert result.cursor_ref is None
        assert cursor is not None
        assert cursor.watermark_value == previous_value

    def test_incremental_full_only_connector_stays_full_mode(self, tmp_path: Path):
        """A connector without incremental capability gets no cursor hint or promotion."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        cursor_store = CursorStore(store)
        previous_value = "2024-01-01T00:00:00+00:00"
        cursor_store.save_cursor(
            CursorState(
                cursor_id="reference.static_csv:dataset",
                connector_id="reference.static_csv",
                dataset_id="dataset",
                watermark_type=WatermarkType.TIMESTAMP,
                watermark_value=previous_value,
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        evidence_ref = _make_evidence_bundle(store)
        connector = _RecordingConnector(
            _typed_fetch_result(
                source_updated_at=datetime(2024, 1, 2, tzinfo=UTC),
                fetched_at=datetime(2024, 1, 3, tzinfo=UTC),
            ),
            capabilities=ConnectorCapability.FULL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )
        manifest = {"datasets": [{"connector_id": "reference.static_csv", "dataset_id": "dataset"}]}

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="reference.static_csv",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=manifest,
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert len(connector.requests) == 1
        assert connector.requests[0].incremental_since is None
        cursor = cursor_store.find_latest_cursor("reference.static_csv", "dataset")
        assert result.cursor_ref is None
        assert cursor is not None
        assert cursor.watermark_value == previous_value

    @pytest.mark.parametrize(
        ("watermark_type", "watermark_value"),
        [
            (WatermarkType.TIMESTAMP, "not-a-timestamp"),
            (WatermarkType.REVISION, "not-a-revision"),
        ],
    )
    def test_incremental_ignores_malformed_legacy_cursor(
        self,
        tmp_path: Path,
        watermark_type: WatermarkType,
        watermark_value: str,
    ):
        """Malformed supported-kind cursors remain full mode conservatively."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        cursor_store = CursorStore(store)
        cursor_store.save_cursor(
            CursorState(
                cursor_id="worldbank.wdi:NY.GDP.MKTP.CD",
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                watermark_type=watermark_type,
                watermark_value=watermark_value,
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        evidence_ref = _make_evidence_bundle(store)
        connector = _RecordingConnector(
            _typed_fetch_result(
                source_updated_at=datetime(2024, 1, 2, tzinfo=UTC),
                fetched_at=datetime(2024, 1, 3, tzinfo=UTC),
            ),
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert len(connector.requests) == 1
        assert connector.requests[0].incremental_since is None

    def test_incremental_promotes_complete_source_boundary_not_fetch_time(self, tmp_path: Path):
        """A supported complete result persists its source boundary, not fetch time."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        source_boundary = datetime(2024, 1, 2, tzinfo=UTC)
        fetched_at = datetime(2024, 1, 3, tzinfo=UTC)
        connector = _RecordingConnector(
            _typed_fetch_result(
                source_updated_at=source_boundary,
                fetched_at=fetched_at,
            ),
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest=_make_manifest(),
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        cursor = CursorStore(store).find_latest_cursor("worldbank.wdi", "NY.GDP.MKTP.CD")
        assert result.cursor_ref is not None
        assert cursor is not None
        assert cursor.watermark_value == source_boundary.isoformat()
        assert cursor.watermark_value != fetched_at.isoformat()

    def test_incremental_promotes_native_rest_last_modified_version(self, tmp_path: Path):
        """A REST Last-Modified version is valid with its explicit source marker."""
        from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        fetched_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
        version = GenericRESTConnector()._build_version(
            content_hash=f"sha256:{'a' * 64}",
            etag=None,
            last_modified="Wed, 02 Oct 2002 13:00:00 GMT",
            fetched_at=fetched_at,
        )
        fetch_result = _typed_fetch_result(
            source_updated_at=version.timestamp,
            fetched_at=fetched_at,
            version=version,
        )
        connector = _RecordingConnector(
            fetch_result,
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(evidence_bundle_ref=evidence_ref, datasets_fetched=1)

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        cursor = CursorStore(store).find_latest_cursor("rest.json", "dataset")
        assert result.cursor_ref is not None
        assert cursor is not None
        assert cursor.watermark_value == version.value
        assert cursor.watermark_value != fetched_at.isoformat()

    def test_incremental_accepts_marked_rest_version_equal_to_fetched_at(
        self,
        tmp_path: Path,
    ):
        """A marked source version may equal fetch time without using fetch time as proof."""
        from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        fetched_at = datetime(2024, 1, 1, tzinfo=UTC)
        version = GenericRESTConnector()._build_version(
            content_hash=f"sha256:{'e' * 64}",
            etag=None,
            last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
            fetched_at=fetched_at,
        )
        assert version.value == fetched_at.isoformat()
        fetch_result = _typed_fetch_result(
            source_updated_at=fetched_at,
            fetched_at=fetched_at,
            version=version,
        )
        connector = _RecordingConnector(
            fetch_result,
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(evidence_bundle_ref=evidence_ref, datasets_fetched=1)

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        cursor = CursorStore(store).find_latest_cursor("rest.json", "dataset")
        assert result.cursor_ref is not None
        assert cursor is not None
        assert cursor.watermark_value == fetched_at.isoformat()

    def test_incremental_rejects_legacy_timestamp_version_without_source_marker(
        self,
        tmp_path: Path,
    ):
        """A legacy timestamp version without a source marker cannot promote."""
        from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        fetched_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
        version = GenericRESTConnector()._build_version(
            content_hash=f"sha256:{'f' * 64}",
            etag=None,
            last_modified="Wed, 02 Oct 2002 13:00:00 GMT",
            fetched_at=fetched_at,
        )
        connector = _RecordingConnector(
            _typed_fetch_result(
                source_updated_at=None,
                fetched_at=fetched_at,
                version=version,
            ),
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(evidence_bundle_ref=evidence_ref, datasets_fetched=1)

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert result.cursor_ref is None
        assert CursorStore(store).find_latest_cursor("rest.json", "dataset") is None

    def test_incremental_rejects_invalid_source_marker_with_consistent_version(
        self,
        tmp_path: Path,
    ):
        """An invalid source marker cannot be replaced by an internally consistent version."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        fetched_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
        source_version = datetime(2002, 10, 2, 13, tzinfo=UTC)
        version = DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value=source_version.isoformat(),
            timestamp=source_version,
        )
        fetch_result = FetchResult.model_construct(
            data=[{"value": "row"}],
            row_count=1,
            schema_id="test.schema",
            schema_version="1.0",
            version=version,
            fetched_at=fetched_at,
            source_updated_at="invalid-last-modified",
            completeness=1.0,
            has_more=False,
            next_page_token=None,
        )
        connector = _RecordingConnector(
            fetch_result,
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(evidence_bundle_ref=evidence_ref, datasets_fetched=1)

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert result.cursor_ref is None
        assert CursorStore(store).find_latest_cursor("rest.json", "dataset") is None

    def test_incremental_rejects_native_rest_version_disagreeing_with_fetch_time(
        self,
        tmp_path: Path,
    ):
        """A version-only source boundary is rejected when its source value disagrees."""
        from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        fetched_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
        version = GenericRESTConnector()._build_version(
            content_hash=f"sha256:{'b' * 64}",
            etag=None,
            last_modified="Wed, 02 Oct 2002 13:00:00 GMT",
            fetched_at=fetched_at,
        )
        fetch_result = _typed_fetch_result(
            source_updated_at=fetched_at,
            fetched_at=fetched_at,
            version=version,
        )
        connector = _RecordingConnector(
            fetch_result,
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(evidence_bundle_ref=evidence_ref, datasets_fetched=1)

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert result.cursor_ref is None
        assert CursorStore(store).find_latest_cursor("rest.json", "dataset") is None

    @pytest.mark.parametrize(
        ("has_more", "next_page_token", "completeness"),
        [
            (True, "page-2", 1.0),
            (False, None, 0.5),
        ],
    )
    def test_incremental_rejects_incomplete_native_rest_version(
        self,
        tmp_path: Path,
        has_more: bool,
        next_page_token: str | None,
        completeness: float,
    ):
        """A valid REST source version cannot advance an incomplete result."""
        from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        cursor_store = CursorStore(store)
        previous_value = "2001-01-01T00:00:00+00:00"
        cursor_store.save_cursor(
            CursorState(
                cursor_id="rest.json:dataset",
                connector_id="rest.json",
                dataset_id="dataset",
                watermark_type=WatermarkType.TIMESTAMP,
                watermark_value=previous_value,
                created_at=datetime(2001, 1, 1, tzinfo=UTC),
            )
        )
        evidence_ref = _make_evidence_bundle(store)
        fetched_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
        version = GenericRESTConnector()._build_version(
            content_hash=f"sha256:{'c' * 64}",
            etag=None,
            last_modified="Wed, 02 Oct 2002 13:00:00 GMT",
            fetched_at=fetched_at,
        )
        connector = _RecordingConnector(
            _typed_fetch_result(
                source_updated_at=None,
                fetched_at=fetched_at,
                version=version,
                has_more=has_more,
                next_page_token=next_page_token,
                completeness=completeness,
            ),
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(evidence_bundle_ref=evidence_ref, datasets_fetched=1)

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        cursor = cursor_store.find_latest_cursor("rest.json", "dataset")
        assert result.cursor_ref is None
        assert cursor is not None
        assert cursor.watermark_value == previous_value

    def test_incremental_native_rest_version_requires_persisted_evidence(self, tmp_path: Path):
        """A valid native source version cannot promote without evidence persistence."""
        from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        fetched_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
        version = GenericRESTConnector()._build_version(
            content_hash=f"sha256:{'d' * 64}",
            etag=None,
            last_modified="Wed, 02 Oct 2002 13:00:00 GMT",
            fetched_at=fetched_at,
        )
        connector = _RecordingConnector(
            _typed_fetch_result(
                source_updated_at=None,
                fetched_at=fetched_at,
                version=version,
            ),
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)
        mock_result = IngestionResult(evidence_bundle_ref=None, datasets_fetched=1)

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert result.cursor_ref is None
        assert CursorStore(store).find_latest_cursor("rest.json", "dataset") is None

    @pytest.mark.parametrize("evidence_case", ["malformed", "nonexistent", "stale"])
    def test_incremental_rejects_unverified_evidence_reference(
        self,
        tmp_path: Path,
        evidence_case: str,
    ):
        """A present evidence reference must resolve and bind before promotion."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        source_boundary = datetime(2024, 1, 2, tzinfo=UTC)
        fetched_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
        fetch_result = _typed_fetch_result(
            source_updated_at=source_boundary,
            fetched_at=fetched_at,
        )
        connector = _RecordingConnector(
            fetch_result,
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH,
        )
        dependencies = _test_dependencies(connector)

        if evidence_case == "malformed":
            evidence_ref = SimpleNamespace(artifact_id="not-a-cas-reference")
        elif evidence_case == "nonexistent":
            evidence_ref = SimpleNamespace(artifact_id=f"sha256:{'0' * 64}")
        else:
            evidence_ref = _make_evidence_bundle(store)

        mock_result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=1,
        )

        with patch(
            "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
            side_effect=partial(
                _orchestrate_one_fetch,
                connector_id="rest.json",
                dataset_id="dataset",
                mock_result=mock_result,
            ),
        ):
            from polisyos.fabric.data_plane.modes import run_batch_incremental

            result = run_batch_incremental(
                connector_manifest={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        assert result.cursor_ref is None
        assert CursorStore(store).find_latest_cursor("rest.json", "dataset") is None


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


def _typed_fetch_result(
    *,
    source_updated_at: datetime | None,
    fetched_at: datetime,
    version: DataVersion | None = None,
    has_more: bool = False,
    next_page_token: str | None = None,
    completeness: float = 1.0,
) -> FetchResult:
    version_value = (source_updated_at or fetched_at).isoformat()
    return FetchResult(
        data=[{"value": "row"}],
        row_count=1,
        schema_id="test.schema",
        schema_version="1.0",
        version=version
        or DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value=version_value,
            timestamp=source_updated_at or fetched_at,
        ),
        fetched_at=fetched_at,
        source_updated_at=source_updated_at,
        completeness=completeness,
        has_more=has_more,
        next_page_token=next_page_token,
    )


class _RecordingConnector:
    def __init__(
        self,
        fetch_result: FetchResult,
        *,
        capabilities: ConnectorCapability,
    ) -> None:
        self._fetch_result = fetch_result
        self.capabilities = capabilities
        self.requests: list[FetchRequest] = []

    def fetch(self, handle: object, request: FetchRequest) -> FetchResult:
        del handle
        self.requests.append(request)
        return self._fetch_result


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


def _supported_dependencies() -> IngestionDependencies:
    return _test_dependencies(
        SimpleNamespace(
            capabilities=ConnectorCapability.FULL_FETCH | ConnectorCapability.INCREMENTAL_FETCH
        )
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


def _orchestrate_one_fetch(
    *,
    connector_id: str,
    dataset_id: str,
    mock_result: IngestionResult,
    **kwargs: object,
) -> IngestionResult:
    dependencies = kwargs["ingestion_dependencies"]
    assert isinstance(dependencies, IngestionDependencies)
    connector = dependencies.registry.get(connector_id)
    request = FetchRequest(dataset_id=dataset_id)
    fetch_result = connector.fetch(None, request)
    sink = kwargs["raw_result_sink"]
    assert callable(sink)
    sink(connector_id, dataset_id, request, fetch_result)
    return mock_result


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
