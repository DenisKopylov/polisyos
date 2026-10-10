from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pandas as pd
import pytest

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    ContractGovernanceError,
    ContractRegistry,
    ContractValidatingProxy,
    ContractVersionError,
    ContractViolationError,
    DataSchema,
    FieldSpec,
    MigrationStatus,
    SchemaApprovalMetadata,
    SchemaRiskLevel,
    SchemaType,
    SchemaValidationMode,
    SchemaVersion,
)
from polisyos.fabric.connectors.types import SchemaError
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


def _schema(version: SchemaVersion, *, include_extra: bool = False) -> DataSchema:
    fields = [
        FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),
        FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=True),
    ]
    if include_extra:
        fields.append(FieldSpec(name="year", data_type=SchemaType.INT64, nullable=True))
    return DataSchema(
        schema_id="test.contract.schema",
        version=version,
        fields=tuple(fields),
        primary_key=("id",),
        required_completeness=0.0,
    )


def _contract(
    *,
    dataset_id: str = "dataset",
    schema: DataSchema | None = None,
    contract_id: str = "test.contract.main",
) -> ConnectorSchemaContract:
    return ConnectorSchemaContract(
        contract_id=contract_id,
        connector_id="test.contract",
        dataset_id=dataset_id,
        schema=schema or _schema(SchemaVersion(1, 0, 0)),
        min_completeness=0.5,
        field_completeness={"id": 1.0},
        created_by="tests",
    )


def _version() -> DataVersion:
    now = datetime.now(UTC)
    return DataVersion(
        strategy=VersionStrategy.CONTENT_HASH,
        value="sha256:" + "0" * 64,
        timestamp=now,
        content_hash="sha256:" + "0" * 64,
    )


def test_contract_id_and_expected_row_count_range_are_strict() -> None:
    for contract_id in ("test.", "test..bad", "test._bad", "test_.bad"):
        with pytest.raises(ValueError):
            _contract(contract_id=contract_id)

    with pytest.raises(ValueError, match="exactly two"):
        ConnectorSchemaContract(
            contract_id="test.contract.range",
            connector_id="test.contract",
            dataset_id="dataset",
            schema=_schema(SchemaVersion(1, 0, 0)),
            expected_row_count_range=(1, 2, 3),
        )

    with pytest.raises(ValueError, match="min must be <= max"):
        ConnectorSchemaContract(
            contract_id="test.contract.range",
            connector_id="test.contract",
            dataset_id="dataset",
            schema=_schema(SchemaVersion(1, 0, 0)),
            expected_row_count_range=(10, 1),
        )


def test_contract_rejects_non_finite_quality_thresholds() -> None:
    with pytest.raises(ValueError, match="finite"):
        ConnectorSchemaContract(
            contract_id="test.contract.quality",
            connector_id="test.contract",
            dataset_id="dataset",
            schema=_schema(SchemaVersion(1, 0, 0)),
            min_completeness=float("nan"),
        )

    with pytest.raises(ValueError, match="finite"):
        ConnectorSchemaContract(
            contract_id="test.contract.quality",
            connector_id="test.contract",
            dataset_id="dataset",
            schema=_schema(SchemaVersion(1, 0, 0)),
            max_staleness_hours=float("inf"),
        )


class _MockConnector(BaseConnector[pd.DataFrame]):
    connector_id: ClassVar[str] = "test.contract"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="contract",
        version="1.0.0",
        namespace="test",
        source_name="Contract Test",
        source_organization="Tests",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    def __init__(
        self,
        frame: pd.DataFrame,
        completeness: float = 1.0,
        *,
        source_updated_at: datetime | None = None,
        reported_schema_id: str = "test.contract.schema",
        reported_schema_version: str = "1.0.0",
    ) -> None:
        self._frame = frame
        self._completeness = completeness
        self._source_updated_at = source_updated_at
        self._reported_schema_id = reported_schema_id
        self._reported_schema_version = reported_schema_version

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True, message="ok")

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        return FetchResult(
            data=self._frame,
            row_count=len(self._frame),
            schema_id=self._reported_schema_id,
            schema_version=self._reported_schema_version,
            version=_version(),
            fetched_at=datetime.now(UTC),
            source_updated_at=self._source_updated_at,
            completeness=self._completeness,
            quality_tier=QualityTier.SILVER,
        )


def test_contract_content_hash_is_semantic() -> None:
    base = _contract()
    changed_meta = base.model_copy(update={"description": "new desc", "created_by": "other-user"})
    assert base.content_hash == changed_meta.content_hash


def test_contract_registry_resolves_exact_over_wildcard() -> None:
    registry = ContractRegistry()
    wildcard = _contract(dataset_id="*", contract_id="test.contract.any")
    exact = _contract(dataset_id="gdp", contract_id="test.contract.gdp")
    registry.register(wildcard)
    registry.register(exact)

    resolved = registry.resolve("test.contract", "gdp")
    assert resolved is not None
    assert resolved.contract_id == "test.contract.gdp"


def test_contract_registry_enforces_version_bump_rules() -> None:
    registry = ContractRegistry()
    v1 = _contract(schema=_schema(SchemaVersion(1, 0, 0)))
    registry.register(v1)

    v1_patch_with_addition = _contract(schema=_schema(SchemaVersion(1, 0, 1), include_extra=True))
    with pytest.raises(ContractVersionError):
        registry.register(v1_patch_with_addition)


def test_contract_registry_blocks_breaking_without_allow_breaking() -> None:
    registry = ContractRegistry()
    base = _contract(schema=_schema(SchemaVersion(1, 0, 0), include_extra=True))
    registry.register(base)

    breaking = ConnectorSchemaContract(
        contract_id=base.contract_id,
        connector_id=base.connector_id,
        dataset_id=base.dataset_id,
        schema=DataSchema(
            schema_id=base.schema.schema_id,
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),),
            primary_key=("id",),
            required_completeness=0.0,
        ),
        min_completeness=0.5,
        created_by="tests",
    )

    with pytest.raises(ContractViolationError):
        registry.register(breaking)
    with pytest.raises(ContractGovernanceError):
        registry.register(breaking, allow_breaking=True)


def test_contract_registry_allow_breaking_requires_approval_metadata() -> None:
    registry = ContractRegistry()
    base = _contract(schema=_schema(SchemaVersion(1, 0, 0), include_extra=True))
    registry.register(base)

    breaking = ConnectorSchemaContract(
        contract_id=base.contract_id,
        connector_id=base.connector_id,
        dataset_id=base.dataset_id,
        schema=DataSchema(
            schema_id=base.schema.schema_id,
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),),
            primary_key=("id",),
            required_completeness=0.0,
        ),
        min_completeness=0.5,
        created_by="tests",
    )

    with pytest.raises(ContractGovernanceError, match="impacted=connector:test.contract"):
        registry.register(breaking, allow_breaking=True)


def test_contract_registry_allow_breaking_with_approval_metadata_passes() -> None:
    registry = ContractRegistry()
    base = _contract(schema=_schema(SchemaVersion(1, 0, 0), include_extra=True))
    registry.register(base)

    approval = SchemaApprovalMetadata(
        owner="fabric-owner",
        reviewer="fabric-reviewer",
        risk_level=SchemaRiskLevel.HIGH,
        migration_status=MigrationStatus.PLANNED,
        downstream_impact_summary="world.claims, retrieval projections",
        migration_note="Backfill downstream materialized views.",
        adr_refs=("ADR-0053",),
        approved_major_bump=True,
    )
    breaking = ConnectorSchemaContract(
        contract_id=base.contract_id,
        connector_id=base.connector_id,
        dataset_id=base.dataset_id,
        schema=DataSchema(
            schema_id=base.schema.schema_id,
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),),
            primary_key=("id",),
            required_completeness=0.0,
        ),
        min_completeness=0.5,
        created_by="tests",
        approval=approval,
    )

    report = registry.register(breaking, allow_breaking=True)
    assert report is not None
    assert report.breaking_changes


def test_contract_validating_proxy_strict_mode_raises() -> None:
    contract_registry = ContractRegistry()
    contract_registry.register(_contract())

    frame = pd.DataFrame([{"id": None, "value": 1.0}])
    connector = _MockConnector(frame, completeness=0.4)
    proxy = ContractValidatingProxy(
        connector,
        contract_registry,
        mode=SchemaValidationMode.STRICT,
    )

    async def _exercise() -> None:
        handle = await proxy.connect(ConnectionConfig(url="http://example.com"))
        await proxy.fetch(handle, FetchRequest(dataset_id="dataset"))

    with pytest.raises(SchemaError):
        asyncio.run(_exercise())


def test_contract_validating_proxy_warn_mode_passes_with_warning_counter() -> None:
    contract_registry = ContractRegistry()
    contract_registry.register(_contract())

    frame = pd.DataFrame([{"id": None, "value": 1.0}])
    connector = _MockConnector(frame, completeness=0.4)
    proxy = ContractValidatingProxy(
        connector,
        contract_registry,
        mode=SchemaValidationMode.WARN,
    )

    async def _exercise() -> FetchResult[pd.DataFrame]:
        handle = await proxy.connect(ConnectionConfig(url="http://example.com"))
        return await proxy.fetch(handle, FetchRequest(dataset_id="dataset"))

    result = asyncio.run(_exercise())

    assert result.row_count == 1
    assert proxy.validation_errors_total > 0
    assert proxy.validation_warnings_total > 0


def test_contract_validating_proxy_rejects_reported_schema_version_drift() -> None:
    contract_registry = ContractRegistry()
    contract_registry.register(_contract())

    frame = pd.DataFrame([{"id": "a", "value": 1.0}])
    connector = _MockConnector(frame, reported_schema_version="2.0.0")
    proxy = ContractValidatingProxy(
        connector,
        contract_registry,
        mode=SchemaValidationMode.STRICT,
    )

    async def _exercise() -> None:
        handle = await proxy.connect(ConnectionConfig(url="http://example.com"))
        await proxy.fetch(handle, FetchRequest(dataset_id="dataset"))

    with pytest.raises(SchemaError):
        asyncio.run(_exercise())


def test_contract_validating_proxy_rejects_future_source_timestamp() -> None:
    contract_registry = ContractRegistry()
    contract = _contract()
    contract = contract.model_copy(update={"max_staleness_hours": 24.0})
    contract_registry.register(contract)

    frame = pd.DataFrame([{"id": "a", "value": 1.0}])
    connector = _MockConnector(
        frame,
        source_updated_at=datetime.now(UTC) + timedelta(days=2),
    )
    proxy = ContractValidatingProxy(
        connector,
        contract_registry,
        mode=SchemaValidationMode.STRICT,
    )

    async def _exercise() -> FetchResult[pd.DataFrame]:
        handle = await proxy.connect(ConnectionConfig(url="http://example.com"))
        return await connector.fetch(handle, FetchRequest(dataset_id="dataset"))

    result = asyncio.run(_exercise())
    errors = proxy._validate_staleness(result, contract)

    assert errors
    assert "clock-skew tolerance" in errors[0]


def test_contract_validating_proxy_bounds_resolution_cache() -> None:
    contract_registry = ContractRegistry()
    contract_registry.register(_contract(dataset_id="dataset-a"))
    contract_registry.register(_contract(dataset_id="dataset-b", contract_id="test.contract.b"))
    contract_registry.register(_contract(dataset_id="dataset-c", contract_id="test.contract.c"))

    connector = _MockConnector(pd.DataFrame([{"id": "a", "value": 1.0}]))
    proxy = ContractValidatingProxy(
        connector,
        contract_registry,
        mode=SchemaValidationMode.WARN,
        resolution_cache_max_entries=2,
        resolution_cache_ttl_seconds=0.01,
    )

    assert proxy._resolve_contract("dataset-a") is not None
    assert proxy._resolve_contract("dataset-b") is not None
    assert len(proxy._resolution_cache) == 2

    assert proxy._resolve_contract("dataset-c") is not None
    assert len(proxy._resolution_cache) == 2
    assert ("test.contract", "dataset-a", contract_registry.revision) not in proxy._resolution_cache

    time.sleep(0.02)
    assert proxy._resolve_contract("dataset-b") is not None
    assert len(proxy._resolution_cache) == 1
