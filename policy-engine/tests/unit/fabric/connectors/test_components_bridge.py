from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from polisyos.core.components import (
    Capability,
    ComponentEntry,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    ComponentRegistry,
)
from polisyos.core.components.discovery import DiscoverySourceInfo
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.components import connector_component_from_class
from polisyos.fabric.connectors.components_bridge import (
    bootstrap_connector_registry_from_components,
)
from polisyos.fabric.connectors.discovery import ConnectorDiscovery
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


class _TestConnector(BaseConnector[dict[str, str]]):
    namespace = "test"
    short_id = "bridge"
    connector_id = f"{namespace}.{short_id}"
    capabilities = ConnectorCapability.FULL_FETCH
    metadata = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="Test Connector",
        source_organization="PolicyOS",
        source_url="https://example.invalid",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        del handle
        return HealthStatus(healthy=True, message="ok")

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[dict[str, str]]:
        del handle, request
        now = datetime.now(UTC)
        content_hash = "sha256:" + ("0" * 64)
        return FetchResult(
            data={"status": "ok"},
            row_count=1,
            schema_id="test.schema",
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=content_hash,
                timestamp=now,
                content_hash=content_hash,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
            bytes_transferred=1,
        )


class _ConnectorWithoutMetadata:
    def fetch_preview(self) -> list[dict[str, int]]:
        return [{"value": 1}]


@dataclass(frozen=True)
class _ComponentWithoutConnectorMetadata:
    metadata: ComponentMetadata

    def create(self) -> _ConnectorWithoutMetadata:
        return _ConnectorWithoutMetadata()


@pytest.fixture
def _clean_registry() -> None:
    ConnectorRegistry.reset_instance()
    ConnectorDiscovery.reset()
    yield
    ConnectorRegistry.reset_instance()
    ConnectorDiscovery.reset()


def test_connector_components_bridge_registers_component_connector(_clean_registry) -> None:
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    component = connector_component_from_class(_TestConnector, tags=["test"])

    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=component.metadata,
            component=component,
            source=DiscoverySourceInfo(source_type="entry_point", location="tests"),
        )
    )

    report = bootstrap_connector_registry_from_components(
        index,
        registry,
    )

    assert report.errors == []
    assert report.registered == ["test.bridge@1.0.0"]
    assert registry.get("test.bridge@1.0.0") is not None


def test_connector_components_bridge_reports_missing_connector_metadata(
    _clean_registry,
) -> None:
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    metadata = ComponentMetadata(
        component_id=ComponentId.parse("test.missing_metadata@1.0.0"),
        kind=ComponentKind.FABRIC_CONNECTOR,
        abi_targets={"fabric_connectors_api": ">=2.2.0,<3.0.0"},
        domains=["test"],
        jurisdictions=[],
        tags=["test"],
        capabilities=Capability.FABRIC_CONNECTOR | Capability.FABRIC_QUERY,
        deps=[],
    )
    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=metadata,
            component=_ComponentWithoutConnectorMetadata(metadata=metadata),
            source=DiscoverySourceInfo(source_type="dev_scan", location="tests"),
        )
    )

    report = bootstrap_connector_registry_from_components(index, registry)

    assert report.registered == []
    assert report.errors == [
        "test.missing_metadata@1.0.0: connector class must declare metadata"
    ]


def test_connector_components_bridge_reports_duplicates_on_second_bootstrap(
    _clean_registry,
) -> None:
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    component = connector_component_from_class(_TestConnector, tags=["test"])
    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=component.metadata,
            component=component,
            source=DiscoverySourceInfo(source_type="entry_point", location="tests"),
        )
    )

    first = bootstrap_connector_registry_from_components(index, registry)
    second = bootstrap_connector_registry_from_components(index, registry)

    assert first.errors == []
    assert first.registered == ["test.bridge@1.0.0"]
    assert second.errors == []
    assert second.registered == []
    assert second.duplicates == ["test.bridge@1.0.0"]


def test_connector_components_bridge_uses_injected_registry_without_default_singleton(
    _clean_registry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    component = connector_component_from_class(_TestConnector, tags=["test"])
    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=component.metadata,
            component=component,
            source=DiscoverySourceInfo(source_type="entry_point", location="tests"),
        )
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.components_bridge._default_connector_registry",
        lambda: (_ for _ in ()).throw(
            AssertionError(
                "default connector registry lookup should not run when registry is injected"
            )
        ),
    )

    report = bootstrap_connector_registry_from_components(index, registry)

    assert report.errors == []
    assert report.registered == ["test.bridge@1.0.0"]
    assert registry.get("test.bridge@1.0.0") is not None
