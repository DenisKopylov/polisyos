from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

import pytest

from polisyos.core.components import (
    Capability,
    ComponentEntry,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    ComponentRegistry,
)
from polisyos.core.components import bootstrap as components_bootstrap
from polisyos.core.components.discovery import DiscoverySourceInfo
from polisyos.fabric.connectors import components_bridge
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
from polisyos.fabric.connectors.registry import ConnectorAlreadyRegisteredError, ConnectorRegistry
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
    namespace: ClassVar[str] = "test"
    short_id: ClassVar[str] = "bridge"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
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
def _clean_registry() -> Generator[None]:
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
            source=DiscoverySourceInfo(source_type="unit_test", location="tests"),
        )
    )

    report = bootstrap_connector_registry_from_components(
        index,
        registry,
    )

    assert report.errors == []
    assert report.registered == ["test.bridge@1.0.0"]
    assert registry.get("test.bridge@1.0.0") is not None


def test_connector_components_bridge_preserves_public_api_and_default_registry(
    _clean_registry,
) -> None:
    component = connector_component_from_class(_TestConnector, tags=["test"])
    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=component.metadata,
            component=component,
            source=DiscoverySourceInfo(source_type="unit_test", location="tests"),
        )
    )

    report = bootstrap_connector_registry_from_components(index)

    assert report.errors == []
    assert report.registered == ["test.bridge@1.0.0"]
    assert ConnectorRegistry.get_instance(bootstrap=False).get("test.bridge@1.0.0") is not None
    assert components_bridge.__all__ == [
        "ComponentsBridgeError",
        "ComponentsBridgeReport",
        "bootstrap_connector_registry_from_components",
    ]
    assert components_bridge.ComponentsBridgeError.__module__ == components_bridge.__name__
    assert components_bridge.ComponentsBridgeReport.__module__ == components_bridge.__name__
    assert components_bridge.ConnectorAlreadyRegisteredError is ConnectorAlreadyRegisteredError


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
    assert report.errors == ["test.missing_metadata@1.0.0: connector class must declare metadata"]


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
            source=DiscoverySourceInfo(source_type="unit_test", location="tests"),
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
            source=DiscoverySourceInfo(source_type="unit_test", location="tests"),
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


def test_registry_lifecycle_bootstraps_without_importing_public_bridge(
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
            source=DiscoverySourceInfo(source_type="unit_test", location="tests"),
        )
    )
    discovery_report = type(
        "DiscoveryReport",
        (),
        {"errors": [], "sources_processed": 1},
    )()
    monkeypatch.setattr(
        components_bootstrap,
        "build_components_index",
        lambda **_: (index, discovery_report),
    )
    monkeypatch.setattr(registry, "_bootstrap_builtin_connectors_direct", lambda: 0)
    monkeypatch.setattr(registry, "_bootstrap_default_configs", lambda: None)
    monkeypatch.setattr(
        components_bridge,
        "bootstrap_connector_registry_from_components",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("registry lifecycle must use the registry-independent bootstrap")
        ),
    )

    registry._bootstrap()

    assert registry.get("test.bridge@1.0.0") is not None


@pytest.mark.usefixtures("_clean_registry")
def test_connector_components_bridge_refuses_unbound_fabric_entrypoint() -> None:
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    metadata = connector_component_from_class(_TestConnector).metadata
    calls = 0

    class _UnboundComponent:
        def __init__(self) -> None:
            self.metadata = metadata

        def create(self) -> type[_TestConnector]:
            nonlocal calls
            calls += 1
            return _TestConnector

    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=metadata,
            component=_UnboundComponent(),
            source=DiscoverySourceInfo(
                source_type="entry_point",
                location="foreign.module:factory",
                group="polisyos.fabric_connectors",
                entry_point="test.unbound",
            ),
        )
    )

    report = bootstrap_connector_registry_from_components(index, registry)

    assert report.registered == []
    assert len(report.errors) == 1
    assert "no verified provider-origin binding" in report.errors[0]
    assert calls == 0
    assert "test.bridge@1.0.0" not in registry
