from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.fabric.connectors.cache import (
    ConnectorCacheStore,
    SchemaChangeInvalidationTrigger,
    TTLPolicy,
    make_schema_hash_provider,
)
from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    ContractRegistry,
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy


def _schema(version: SchemaVersion, *, with_extra: bool = False) -> DataSchema:
    fields = [FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False)]
    if with_extra:
        fields.append(FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=True))
    return DataSchema(
        schema_id="cache.test.schema",
        version=version,
        fields=tuple(fields),
        primary_key=("id",),
        required_completeness=0.0,
    )


def _contract(schema: DataSchema) -> ConnectorSchemaContract:
    return ConnectorSchemaContract(
        contract_id="cache.test.contract",
        connector_id="test.cache",
        dataset_id="dataset",
        schema=schema,
        created_by="tests",
    )


def _result() -> FetchResult:
    now = datetime.now(UTC)
    version = DataVersion(
        strategy=VersionStrategy.CONTENT_HASH,
        value="sha256:" + "1" * 64,
        timestamp=now,
        content_hash="sha256:" + "1" * 64,
    )
    return FetchResult(
        data=[{"id": "a"}],
        row_count=1,
        schema_id="cache.test.schema",
        schema_version="1.0.0",
        version=version,
        fetched_at=now,
        completeness=1.0,
        quality_tier=QualityTier.SILVER,
    )


@pytest.fixture
def cache(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    return ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(hours=1)))


def test_make_schema_hash_provider_returns_contract_hash() -> None:
    registry = ContractRegistry()
    contract = _contract(_schema(SchemaVersion(1, 0, 0)))
    registry.register(contract)

    provider = make_schema_hash_provider(registry, connector_id="test.cache")
    hash_value = provider(FetchRequest(dataset_id="dataset"), _result())
    assert hash_value == contract.content_hash


def test_invalidate_by_schema_hash_marks_old_entries_stale(cache: ConnectorCacheStore) -> None:
    request = FetchRequest(dataset_id="dataset")
    old_hash = "sha256:" + "2" * 64
    keep_hash = "sha256:" + "3" * 64

    cache.put(request, _result(), connector_id="test.cache", schema_hash=old_hash)
    invalidated = cache.invalidate_by_schema_hash(connector_id="test.cache", exclude_hash=keep_hash)
    assert invalidated == 1
    assert cache.get(request, connector_id="test.cache") is None


def test_schema_change_invalidation_trigger(cache: ConnectorCacheStore) -> None:
    registry = ContractRegistry()
    trigger = SchemaChangeInvalidationTrigger(cache)
    registry.register_callback(trigger.on_contract_registered)

    v1 = _contract(_schema(SchemaVersion(1, 0, 0)))
    registry.register(v1)
    request = FetchRequest(dataset_id="dataset")
    cache.put(request, _result(), connector_id="test.cache", schema_hash=v1.content_hash)
    assert cache.get(request, connector_id="test.cache") is not None

    v2 = _contract(_schema(SchemaVersion(1, 1, 0), with_extra=True))
    registry.register(v2)
    assert cache.get(request, connector_id="test.cache") is None
