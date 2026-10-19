from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.fabric import api as fabric_api
from polisyos.fabric.api import fabric_get_data
from polisyos.fabric.connectors import CatalogRegistrySchemaError, ConnectorNotFoundError
from polisyos.fabric.connectors.sources import wvs
from polisyos.ir.connectors import DataVersion, FetchResult, VersionStrategy

_DATASET_ID = "dataset-1"
_WVS_CONNECTOR_ID = wvs.WVSConnector.connector_id


class _Descriptor:
    def __init__(self, dataset_id: str) -> None:
        self.dataset_id = dataset_id


class _Entry:
    def __init__(self, short_id: str, *, known: tuple[str, ...] = ()) -> None:
        self.short_id = short_id
        self.known_datasets = frozenset(known)
        self.dataset_descriptors: tuple[_Descriptor, ...] = ()
        self.default_config = object()


class _MatchingConnector:
    async def list_datasets(self, handle: object):
        del handle
        yield _Descriptor(_DATASET_ID)

    async def fetch(self, handle: object, request: object) -> FetchResult[object]:
        del handle, request
        now = datetime(2024, 1, 1, tzinfo=UTC)
        return FetchResult(
            data=[{"value": 1}],
            row_count=1,
            schema_id="test.match",
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


class _NoMatchConnector:
    async def list_datasets(self, handle: object):
        del handle
        yield _Descriptor("other-dataset")

    async def fetch(self, handle: object, request: object) -> FetchResult[object]:
        raise AssertionError("no-match connector must not be fetched")


class _Registry:
    def __init__(self, *, sibling_matches: bool, wvs_metadata_selects: bool = False) -> None:
        self.entries = [
            _Entry(_WVS_CONNECTOR_ID, known=(_DATASET_ID,) if wvs_metadata_selects else ()),
            _Entry("test.match" if sibling_matches else "test.no_match"),
        ]
        self.connectors = {
            _WVS_CONNECTOR_ID: wvs.WVSConnector(),
            self.entries[1].short_id: (
                _MatchingConnector() if sibling_matches else _NoMatchConnector()
            ),
        }
        self.connection_calls: list[str] = []

    def query_entries(self, *, capabilities: object | None = None) -> list[_Entry]:
        del capabilities
        return self.entries

    def get(self, connector_id: str) -> object:
        return self.connectors[connector_id]

    def get_entry(self, connector_id: str) -> _Entry:
        return next(entry for entry in self.entries if entry.short_id == connector_id)

    async def get_connection(self, connector_id: str, config: object) -> object:
        del config
        self.connection_calls.append(connector_id)
        return object()

    async def release_connection(self, connector_id: str, handle: object) -> None:
        del connector_id, handle


@pytest.fixture
def malformed_wvs_registry(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "wvs_indicator_registry.yaml"
    path.write_text("indicators: []\n", encoding="utf-8")
    monkeypatch.setattr(wvs, "catalog_default_resource_path", lambda _name: path)
    return path


def test_unselected_malformed_wvs_registry_does_not_hide_matching_sibling(
    malformed_wvs_registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _Registry(sibling_matches=True)
    original_probe = fabric_api._probe_catalog
    failures: list[tuple[str, CatalogRegistrySchemaError]] = []

    def record_registry_failure(
        registry_arg: _Registry, connector_id: str, dataset_id: str
    ) -> bool:
        try:
            return original_probe(registry_arg, connector_id, dataset_id)
        except CatalogRegistrySchemaError as exc:
            failures.append((connector_id, exc))
            raise

    monkeypatch.setattr(fabric_api, "_probe_catalog", record_registry_failure)
    result = fabric_get_data(dataset_id=_DATASET_ID, registry=registry)

    assert len(failures) == 1
    assert failures[0][0] == _WVS_CONNECTOR_ID
    assert failures[0][1].connector_id == _WVS_CONNECTOR_ID
    assert result.schema_id == "test.match"
    assert registry.connection_calls == [_WVS_CONNECTOR_ID, "test.match", "test.match"]


def test_no_sibling_match_keeps_malformed_registry_as_incomplete_discovery(
    malformed_wvs_registry,
) -> None:
    registry = _Registry(sibling_matches=False)

    with pytest.raises(CatalogRegistrySchemaError, match="discovery is incomplete") as caught:
        fabric_get_data(dataset_id=_DATASET_ID, registry=registry)

    assert caught.value.connector_id == _WVS_CONNECTOR_ID
    assert isinstance(caught.value.__cause__, CatalogRegistrySchemaError)
    assert registry.connection_calls == [_WVS_CONNECTOR_ID, "test.no_match"]


def test_complete_no_match_remains_connector_not_found(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "wvs_indicator_registry.yaml"
    path.write_text(
        "indicators:\n  A001:\n    title: Not a wave-seven match\n    waves: [1]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(wvs, "catalog_default_resource_path", lambda _name: path)
    registry = _Registry(sibling_matches=False)

    with pytest.raises(ConnectorNotFoundError):
        fabric_get_data(dataset_id=_DATASET_ID, registry=registry)


@pytest.mark.parametrize("explicit_connector", [None, _WVS_CONNECTOR_ID])
def test_selected_wvs_provider_refuses_malformed_registry_before_http(
    malformed_wvs_registry, explicit_connector: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _Registry(sibling_matches=True, wvs_metadata_selects=True)

    async def unexpected_http(*_args, **_kwargs):
        raise AssertionError("malformed registry must refuse before HTTP")

    monkeypatch.setattr(wvs.WVSConnector, "_resilient_request_json", unexpected_http)

    with pytest.raises(
        CatalogRegistrySchemaError, match="Invalid WVS indicator registry"
    ) as caught:
        fabric_get_data(
            dataset_id=_DATASET_ID,
            connector_id=explicit_connector,
            registry=registry,
        )

    assert caught.value.connector_id == _WVS_CONNECTOR_ID
