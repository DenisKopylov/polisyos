from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
    ContractRegistry,
    ContractValidatingProxy,
    ContractVersionError,
    ContractViolationError,
    DataSchema,
    FieldSpec,
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
    now = datetime.now(timezone.utc)
    return DataVersion(
        strategy=VersionStrategy.CONTENT_HASH,
        value="sha256:" + "0" * 64,
        timestamp=now,
        content_hash="sha256:" + "0" * 64,
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

    def __init__(self, frame: pd.DataFrame, completeness: float = 1.0) -> None:
        self._frame = frame
        self._completeness = completeness

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
            schema_id="test.contract.schema",
            schema_version="1.0.0",
            version=_version(),
            fetched_at=datetime.now(timezone.utc),
            completeness=self._completeness,
            quality_tier=QualityTier.SILVER,
        )


def test_contract_content_hash_is_semantic() -> None:
    base = _contract()
    changed_meta = base.model_copy(
        update={"description": "new desc", "created_by": "other-user"}
    )
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
    registry.register(breaking, allow_breaking=True)


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
