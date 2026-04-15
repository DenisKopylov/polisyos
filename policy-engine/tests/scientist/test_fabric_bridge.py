from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataViewRequestRef
from polisyos.ir.connectors import DataVersion, FetchResult, QualityTier, VersionStrategy
from polisyos.ir.queries import DataViewRequest
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort, ExecutionTierViolation


class _DatasetRecord:
    def __init__(self, execution_tier: str) -> None:
        self.execution_tier = execution_tier


class _CatalogStore:
    def __init__(self, execution_tier: str) -> None:
        self._dataset = _DatasetRecord(execution_tier)

    def get_dataset(self, dataset_id: str) -> _DatasetRecord | None:
        assert dataset_id == "social_trust"
        return self._dataset


class _RegistryDescriptor:
    dataset_id: str = "social_trust"


class _RegistryEntry:
    def __init__(self) -> None:
        self.short_id = "fabric.mock"
        self.known_datasets: frozenset[str] = frozenset()
        self.dataset_descriptors: tuple[_RegistryDescriptor, ...] = ()
        self.default_config = object()


class _UnusedConnector:
    async def list_datasets(self, handle: object):
        del handle
        if False:
            yield None

    async def fetch(self, handle: object, request: object) -> FetchResult[object]:
        del handle, request
        raise AssertionError("unexpected connector fetch")


class _Registry:
    def get(self, connector_id: str) -> _UnusedConnector:
        raise AssertionError(f"unexpected connector lookup: {connector_id}")

    def get_entry(self, connector_id: str) -> _RegistryEntry:
        raise AssertionError(f"unexpected connector entry lookup: {connector_id}")

    def query_entries(self, *, capabilities: object | None = None) -> list[_RegistryEntry]:
        del capabilities
        return []

    async def get_connection(self, connector_id: str, config: object) -> object:
        raise AssertionError(f"unexpected connection lookup: {connector_id} {config}")

    async def release_connection(self, connector_id: str, handle: object) -> None:
        raise AssertionError(f"unexpected connection release: {connector_id} {handle}")


def test_default_fabric_port_snapshot_marks_survey_repeated_cross_section(tmp_path) -> None:
    now = datetime.now(UTC)
    seen: dict[str, object] = {}
    registry = _Registry()

    def _fake_get_data(
        *,
        dataset_id: str,
        connector_id: str | None = None,
        constraints: dict[str, object] | None = None,
        registry: object | None = None,
    ) -> FetchResult[object]:
        seen["dataset_id"] = dataset_id
        seen["constraints"] = constraints
        seen["registry"] = registry
        return FetchResult(
            data=[
                {
                    "country_code": "UA",
                    "survey_year": 2020,
                    "wave": 7,
                    "sample_weight": 1.25,
                    "value": 0.61,
                }
            ],
            row_count=1,
            schema_id="wvs.timeseries",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=now.isoformat(),
                timestamp=now,
            ),
            fetched_at=now,
            source_updated_at=now,
            completeness=1.0,
            quality_tier=QualityTier.GOLD,
            quality_flags=frozenset(),
            bytes_transferred=256,
        )

    store = FileSystemCAS(tmp_path)
    request_payload = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="req_wvs",
            view_type="table",
            metrics=["social_trust"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )

    snapshot_ref = DefaultFabricPort(
        fetch_data=_fake_get_data,
        connector_registry=registry,
    ).snapshot(
        store,
        DataViewRequestRef(artifact_id=request_payload.artifact_id),
    )
    snapshot_payload = from_canonical_bytes(store.get_bytes(snapshot_ref.artifact_id))
    snapshot = DataSnapshot.model_validate(snapshot_payload)

    assert snapshot.stats["data_shape"] == "survey_repeated_cross_section"
    assert snapshot.stats["survey_year_field"] == "survey_year"
    assert snapshot.stats["wave_field"] == "wave"
    assert snapshot.stats["sample_weight_field"] == "sample_weight"
    assert "allowed_workflows=transport,survey,hte,repeated_cross_section" in snapshot.notes
    assert seen["dataset_id"] == "social_trust"
    assert seen["registry"] is registry
    assert seen["constraints"] == {"page_size": 100}


def test_default_fabric_port_enforces_execution_tier_from_injected_catalog_store(tmp_path) -> None:
    now = datetime.now(UTC)

    def _fake_get_data(
        *,
        dataset_id: str,
        connector_id: str | None = None,
        constraints: dict[str, object] | None = None,
        registry: object | None = None,
    ) -> FetchResult[object]:
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="catalog.only",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=now.isoformat(),
                timestamp=now,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
            quality_flags=frozenset(),
            bytes_transferred=0,
        )

    store = FileSystemCAS(tmp_path)
    request_payload = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="req_catalog",
            view_type="table",
            metrics=["social_trust"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )

    with pytest.raises(ExecutionTierViolation):
        DefaultFabricPort(
            fetch_data=_fake_get_data,
            catalog_store=_CatalogStore("catalog"),
        ).snapshot(
            store,
            DataViewRequestRef(artifact_id=request_payload.artifact_id),
        )
