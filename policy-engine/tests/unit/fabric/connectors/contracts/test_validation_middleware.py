from __future__ import annotations

import asyncio
from datetime import UTC, datetime
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


def _version() -> DataVersion:
    now = datetime.now(UTC)
    digest = "sha256:" + "0" * 64
    return DataVersion(
        strategy=VersionStrategy.CONTENT_HASH,
        value=digest,
        timestamp=now,
        content_hash=digest,
    )


def _contract(
    *,
    version: SchemaVersion,
    min_completeness: float,
    field_completeness: dict[str, float] | None = None,
) -> ConnectorSchemaContract:
    return ConnectorSchemaContract(
        contract_id="test.middleware.fetch",
        connector_id="test.middleware",
        dataset_id="dataset",
        schema=DataSchema(
            schema_id="test.middleware.schema",
            version=version,
            fields=(
                FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),
                FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=True),
            ),
            primary_key=("id",),
            required_completeness=0.0,
        ),
        min_completeness=min_completeness,
        field_completeness=field_completeness or {},
        created_by="tests",
    )


class _FrameConnector(BaseConnector[pd.DataFrame]):
    connector_id: ClassVar[str] = "test.middleware"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="middleware",
        version="1.0.0",
        namespace="test",
        source_name="Middleware Test",
        source_organization="Tests",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    def __init__(self) -> None:
        self.reported_schema_version = "1.0.0"
        self._frame = pd.DataFrame([{"id": "row-1", "value": None}])

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
            schema_id="test.middleware.schema",
            schema_version=self.reported_schema_version,
            version=_version(),
            fetched_at=datetime.now(UTC),
            completeness=0.5,
            quality_tier=QualityTier.SILVER,
        )


async def _fetch(proxy: ContractValidatingProxy[pd.DataFrame]) -> FetchResult[pd.DataFrame]:
    handle = await proxy.connect(ConnectionConfig(url="https://example.test"))
    return await proxy.fetch(handle, FetchRequest(dataset_id="dataset"))


def test_registry_revision_replaces_cached_contract_and_preserves_modes() -> None:
    registry = ContractRegistry()
    registry.register(_contract(version=SchemaVersion(1, 0, 0), min_completeness=0.2))
    connector = _FrameConnector()
    strict = ContractValidatingProxy(connector, registry, mode=SchemaValidationMode.STRICT)
    warn = ContractValidatingProxy(connector, registry, mode=SchemaValidationMode.WARN)
    disabled = ContractValidatingProxy(connector, registry, mode=SchemaValidationMode.DISABLED)

    # Exercise each mode before replacement so strict and warn have resolved the
    # original contract; disabled intentionally bypasses resolution.
    assert asyncio.run(_fetch(strict)).row_count == 1
    assert asyncio.run(_fetch(warn)).row_count == 1
    assert asyncio.run(_fetch(disabled)).row_count == 1
    old_revision = registry.revision

    registry.register(
        _contract(
            version=SchemaVersion(1, 0, 1),
            min_completeness=0.9,
            field_completeness={"value": 1.0},
        )
    )
    assert registry.revision == old_revision + 1
    connector.reported_schema_version = "1.0.1"

    with pytest.raises(SchemaError) as raised:
        asyncio.run(_fetch(strict))
    assert raised.value.expected_version == "1.0.1"
    assert raised.value.actual_version == "1.0.1"
    # Both checks belong to the replacement policy. A stale cached v1 contract
    # would see only a version mismatch and would not apply these thresholds.
    assert strict.validation_errors_total == 2
    assert strict.validation_warnings_total == 0

    warned_result = asyncio.run(_fetch(warn))
    assert warned_result.row_count == 1
    assert warn.validation_errors_total == 2
    assert warn.validation_warnings_total == 2

    disabled_result = asyncio.run(_fetch(disabled))
    assert disabled_result.row_count == 1
    assert disabled.validation_errors_total == 0
    assert disabled.validation_warnings_total == 0
