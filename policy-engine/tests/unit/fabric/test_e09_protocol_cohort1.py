"""Behavioral and source-owner checks for the Fabric E09 protocol cohort."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest
from pydantic import BaseModel

from polisyos.core.artifacts import FileSystemCAS
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.cache.invalidation import InvalidationOrchestrator
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.quality.completeness import CompletenessAnalyzer
from polisyos.fabric.connectors.types import FreshnessResult, FreshnessStatus
from polisyos.fabric.data_plane import cli as quarantine_cli
from polisyos.fabric.data_plane.quarantine import (
    IndexedArtifactStore,
    QuarantineRecord,
    list_quarantine_records,
    load_quarantine_payload,
    persist_quarantine_record,
)
from polisyos.fabric.retrieval import custody as fetch_custody
from polisyos.fabric.retrieval.custody import FabricFetchCustodyError
from polisyos.fabric.world.query import _open_snapshot_backend
from polisyos.fabric.world.store.snapshots import WorldSnapshotRecord
from polisyos.ir.connectors import ConnectorCapability, DataVersion, VersionStrategy


def test_completeness_consumer_accepts_frozen_data_schema() -> None:
    schema = DataSchema(
        schema_id="fabric.e09.completeness",
        version=SchemaVersion.parse("1.0.0"),
        fields=(FieldSpec(name="population", data_type=SchemaType.INT32),),
    )

    result = CompletenessAnalyzer().analyze(pd.DataFrame({"other": [10]}), schema)

    assert isinstance(schema.fields, tuple)
    assert result.hard_fail
    assert result.field_completeness == {"population": 0.0}


def test_world_query_opens_frozen_snapshot_record_and_refuses_unknown_adapter(tmp_path) -> None:
    database_path = tmp_path / "snapshot.duckdb"
    connection = duckdb.connect(str(database_path))
    connection.execute("CREATE TABLE snapshot_probe (value INTEGER)")
    connection.execute("INSERT INTO snapshot_probe VALUES (7)")
    connection.close()

    record = WorldSnapshotRecord(
        snapshot_id="snapshot-e09",
        snapshot_path=str(database_path),
        created_at="2026-10-23T00:00:00Z",
        storage_adapter="duckdb_native_file_copy",
    )
    backend = _open_snapshot_backend(record)
    try:
        assert backend.execute("SELECT value FROM snapshot_probe").fetchall() == [(7,)]
    finally:
        backend.close()

    unsupported = WorldSnapshotRecord(
        snapshot_id="snapshot-unsupported",
        snapshot_path=str(database_path),
        created_at="2026-10-23T00:00:00Z",
        storage_adapter="unsupported",
    )
    with pytest.raises(ValueError):
        _open_snapshot_backend(unsupported)


class _InvalidationCache:
    def __init__(self, version: DataVersion) -> None:
        self.version = version
        self.invalidations: list[tuple[str, dict[str, object]]] = []

    def list_dataset_connectors(self) -> list[tuple[str, str]]:
        return [("fabric.e09.connector", "dataset-e09")]

    def get_latest_metadata(self, dataset_id: str) -> object:
        assert dataset_id == "dataset-e09"
        return SimpleNamespace(source_version=self.version, cache_key="cache-e09")

    def get_source_signature(self, cache_key: str) -> None:
        assert cache_key == "cache-e09"
        return None

    def invalidate(self, strategy: str, **kwargs: object) -> int:
        self.invalidations.append((strategy, kwargs))
        return 1


class _FreshnessConnector:
    capabilities = ConnectorCapability.FRESHNESS_CHECK

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def check_freshness(
        self, handle: ConnectionHandle, dataset_id: str, cached_version: DataVersion
    ) -> FreshnessResult:
        assert handle.connector_id == "fabric.e09.connector"
        assert dataset_id == "dataset-e09"
        assert cached_version.value == "version-e09"
        if self.fail:
            raise RuntimeError("freshness source unavailable")
        return FreshnessResult(status=FreshnessStatus.STALE, message="source changed")


class _ReleasingRegistry:
    def __init__(self, connector: _FreshnessConnector) -> None:
        self.connector = connector
        self.handle = ConnectionHandle(
            connector_id="fabric.e09.connector",
            config=ConnectionConfig(url="https://example.test/data"),
        )
        self.released: list[tuple[str, ConnectionHandle]] = []

    def get(self, connector_id: str) -> _FreshnessConnector:
        assert connector_id == "fabric.e09.connector"
        return self.connector

    async def get_connection(self, connector_id: str) -> ConnectionHandle:
        assert connector_id == "fabric.e09.connector"
        return self.handle

    async def release_connection(self, connector_id: str, handle: ConnectionHandle) -> None:
        self.released.append((connector_id, handle))


def _version() -> DataVersion:
    now = datetime.now(UTC)
    return DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value="version-e09",
        timestamp=now,
    )


class _ProfileProbe(BaseModel):
    value: int


class _DefaultProfileOnlyStore:
    def __init__(self, delegate: FileSystemCAS) -> None:
        self.delegate = delegate

    def __getattr__(self, name: str) -> object:
        if name == "get_manifest_by_profile":
            raise AttributeError(name)
        return getattr(self.delegate, name)


def test_retrieval_custody_uses_profile_addressed_manifest_capability(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    kind = "fabric.e09.profile_probe"
    schema_name = "polisyos.fabric.E09ProfileProbe"
    ref = fetch_custody._put_json(
        store,
        _ProfileProbe(value=7),
        kind=kind,
        schema=schema_name,
        inputs=[],
    )

    assert isinstance(store, fetch_custody._RuntimeProfileAddressedStore)
    raw = fetch_custody._read(
        store,
        ref,
        kind=kind,
        media_type="application/json",
        schema=schema_name,
        inputs=[],
    )
    assert json.loads(raw) == {"value": 7}

    default_only_store = _DefaultProfileOnlyStore(store)
    assert not isinstance(default_only_store, fetch_custody._RuntimeProfileAddressedStore)
    assert json.loads(
        fetch_custody._read(
            default_only_store,
            ref,
            kind=kind,
            media_type="application/json",
            schema=schema_name,
            inputs=[],
        )
    ) == {"value": 7}
    incorrect_profile_ref = ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + ("0" * 64)}
    )
    with pytest.raises(TypeError, match="cannot resolve a non-default manifest profile"):
        fetch_custody._read(
            default_only_store,
            incorrect_profile_ref,
            kind=kind,
            media_type="application/json",
            schema=schema_name,
            inputs=[],
        )

    unprofiled_ref = ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(FabricFetchCustodyError, match="fabric_fetch_profile_unverified"):
        fetch_custody._read(
            store,
            unprofiled_ref,
            kind=kind,
            media_type="application/json",
            schema=schema_name,
            inputs=[],
        )


def test_invalidation_releases_real_acquired_handle_after_stale_result() -> None:
    cache = _InvalidationCache(_version())
    registry = _ReleasingRegistry(_FreshnessConnector())

    events = asyncio.run(InvalidationOrchestrator(cache, registry).scan_and_invalidate())

    assert [event.trigger_type for event in events] == ["freshness_check"]
    assert cache.invalidations == [("soft_mark", {"dataset_id": "dataset-e09"})]
    assert registry.released == [("fabric.e09.connector", registry.handle)]


def test_invalidation_releases_handle_when_freshness_check_fails() -> None:
    cache = _InvalidationCache(_version())
    registry = _ReleasingRegistry(_FreshnessConnector(fail=True))

    events = asyncio.run(InvalidationOrchestrator(cache, registry).scan_and_invalidate())

    assert events == []
    assert cache.invalidations == []
    assert registry.released == [("fabric.e09.connector", registry.handle)]


def test_quarantine_cli_builds_and_consumes_indexed_filesystem_store(tmp_path) -> None:
    store = quarantine_cli._build_store(str(tmp_path / "cas"))

    assert isinstance(store, IndexedArtifactStore)
    persist_quarantine_record(
        store,
        record=QuarantineRecord.new(
            reason="test_quarantine",
            severity="error",
            source="fabric.e09",
        ),
        raw_payload={"value": 7},
    )
    records = list_quarantine_records(store)

    assert len(records) == 1
    assert load_quarantine_payload(store, records[0][1].raw_payload_ref) == {"value": 7}


def test_quarantine_cli_refuses_store_without_index_capability(monkeypatch) -> None:
    monkeypatch.setattr(
        quarantine_cli,
        "build_artifact_store",
        lambda _config: object(),
    )

    with pytest.raises(TypeError, match="filesystem-indexed"):
        quarantine_cli._build_store("/unused")
