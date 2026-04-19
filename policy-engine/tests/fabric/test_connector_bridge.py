from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.fabric._connector_bridge import fabric_get_data, resolve_connector_registry
from polisyos.ir.connectors import DataVersion, FetchResult, VersionStrategy


class _BridgeEntry:
    def __init__(self) -> None:
        self.short_id = "test.bridge"
        self.known_datasets: frozenset[str] = frozenset()
        self.dataset_descriptors: tuple[_BridgeDescriptor, ...] = ()
        self.default_config = object()


class _BridgeDescriptor:
    dataset_id: str = "dataset-1"


class _BridgeConnector:
    async def list_datasets(self, handle: object):
        del handle
        if False:
            yield None

    async def fetch(self, handle: object, request: object) -> FetchResult[object]:
        del handle, request
        now = datetime(2024, 1, 1, tzinfo=UTC)
        return FetchResult(
            data=[{"value": 1}],
            row_count=1,
            schema_id="test.bridge",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=now.isoformat(),
                timestamp=now,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_flags=frozenset(),
        )


class _BridgeRegistry:
    def __init__(self) -> None:
        self.connector = _BridgeConnector()
        self.entry = _BridgeEntry()

    def get(self, connector_id: str) -> _BridgeConnector:
        assert connector_id == "test.bridge"
        return self.connector

    def get_entry(self, connector_id: str) -> _BridgeEntry:
        assert connector_id == "test.bridge"
        return self.entry

    async def get_connection(self, connector_id: str, config: object) -> object:
        del connector_id, config
        return object()

    async def release_connection(self, connector_id: str, handle: object) -> None:
        del connector_id, handle

    def query_entries(self, *, capabilities: object | None = None) -> list[_BridgeEntry]:
        del capabilities
        return []


def test_fabric_get_data_uses_injected_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "polisyos.fabric._connector_bridge._default_connector_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )

    result = fabric_get_data(
        dataset_id="dataset-1",
        connector_id="test.bridge",
        registry=_BridgeRegistry(),
    )

    assert result.row_count == 1
    assert result.schema_id == "test.bridge"


def test_resolve_connector_registry_uses_factory_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _BridgeRegistry()

    monkeypatch.setattr(
        "polisyos.fabric._connector_bridge._default_connector_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )

    resolved = resolve_connector_registry(
        registry_factory=lambda: registry,
    )

    assert resolved is registry
