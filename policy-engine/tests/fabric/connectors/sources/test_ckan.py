"""Tests for CKAN Catalog and Resource connectors."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.ckan_catalog import CKANCatalogConnector
from polisyos.fabric.connectors.sources.ckan_resource import CKANResourceConnector
from polisyos.fabric.connectors.types import FetchError
from polisyos.ir.connectors import ConnectorCapability, VersionStrategy

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ckan"


def _run_async(coro):
    return asyncio.run(coro)


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


def _ckan_config() -> ConnectionConfig:
    return ConnectionConfig(url="https://data.example.test")


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_fake_request_json(fixture_body):
    raw = json.dumps(fixture_body).encode("utf-8")
    headers = {"ETag": '"ckan-etag-1"', "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"}

    async def _fake(_session, _url, *, params, connector_id):
        return fixture_body, headers, raw

    return staticmethod(_fake)


def _fake_get_session(self, _handle):
    import asyncio as _aio
    fut = _aio.Future()
    fut.set_result(object())
    return fut


# ---------------------------------------------------------------------------
# CKANCatalogConnector
# ---------------------------------------------------------------------------

class TestCKANCatalogMetadata:
    def test_connector_id(self):
        assert CKANCatalogConnector.connector_id == "ckan.catalog"

    def test_capabilities(self):
        caps = CKANCatalogConnector.capabilities
        assert caps & ConnectorCapability.CATALOG_BROWSE
        assert caps & ConnectorCapability.FULL_FETCH


class TestCKANCatalogListDatasets:
    def test_list_datasets(self, monkeypatch):
        connector = CKANCatalogConnector()
        fixture = _load_fixture("package_search_response.json")
        monkeypatch.setattr(CKANCatalogConnector, "_request_json", _make_fake_request_json(fixture))
        monkeypatch.setattr(CKANCatalogConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            datasets = []
            async for ds in connector.list_datasets(handle):
                datasets.append(ds)
            await connector.disconnect(handle)
            return datasets

        datasets = _run_async(_exercise())
        assert len(datasets) == 3
        assert datasets[0].dataset_id == "gdp-annual"
        assert datasets[0].name == "Annual GDP Data"
        assert "ckan" in datasets[0].tags


class TestCKANCatalogFetch:
    def test_fetch_package(self, monkeypatch):
        connector = CKANCatalogConnector()
        fixture = _load_fixture("package_show_response.json")
        monkeypatch.setattr(CKANCatalogConnector, "_request_json", _make_fake_request_json(fixture))
        monkeypatch.setattr(CKANCatalogConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            request = FetchRequest(dataset_id="gdp-annual")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 2
        assert "resource_id" in result.data.columns
        assert result.data["format"].tolist() == ["CSV", "JSON"]


class TestCKANCatalogHealth:
    def test_health_check_ok(self, monkeypatch):
        connector = CKANCatalogConnector()
        status_body = {"success": True, "result": {"site_title": "Test"}}
        monkeypatch.setattr(CKANCatalogConnector, "_request_json", _make_fake_request_json(status_body))
        monkeypatch.setattr(CKANCatalogConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            status = await connector.health_check(handle)
            await connector.disconnect(handle)
            return status

        status = _run_async(_exercise())
        assert status.healthy is True


# ---------------------------------------------------------------------------
# CKANResourceConnector
# ---------------------------------------------------------------------------

class TestCKANResourceMetadata:
    def test_connector_id(self):
        assert CKANResourceConnector.connector_id == "ckan.resource"

    def test_capabilities(self):
        caps = CKANResourceConnector.capabilities
        assert caps & ConnectorCapability.FULL_FETCH


class TestCKANResourceParsing:
    def test_parse_csv(self):
        raw = b"name,value\nfoo,1\nbar,2\n"
        df = CKANResourceConnector._parse_resource(raw, "csv")
        assert len(df) == 2
        assert df["name"].tolist() == ["foo", "bar"]

    def test_parse_json_array(self):
        raw = b'[{"a": 1}, {"a": 2}]'
        df = CKANResourceConnector._parse_resource(raw, "json")
        assert len(df) == 2

    def test_parse_json_object_with_results(self):
        raw = b'{"results": [{"x": 10}, {"x": 20}]}'
        df = CKANResourceConnector._parse_resource(raw, "json")
        assert len(df) == 2

    def test_parse_unknown_format_fallback_csv(self):
        raw = b"col1,col2\na,b\n"
        df = CKANResourceConnector._parse_resource(raw, "xls")
        assert len(df) == 1


class TestCKANResourceResolve:
    def test_resolve_direct_url(self):
        connector = CKANResourceConnector()

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            url, fmt = await connector._resolve_resource(
                handle, "https://data.example.test",
                "https://example.test/data.csv",
            )
            await connector.disconnect(handle)
            return url, fmt

        url, fmt = _run_async(_exercise())
        assert url == "https://example.test/data.csv"
        assert fmt == "csv"

    def test_resolve_package_resource(self, monkeypatch):
        connector = CKANResourceConnector()
        fixture = _load_fixture("package_show_response.json")
        monkeypatch.setattr(CKANResourceConnector, "_request_json", _make_fake_request_json(fixture))
        monkeypatch.setattr(CKANResourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            url, fmt = await connector._resolve_resource(
                handle, "https://data.example.test",
                "gdp-annual/res-001",
            )
            await connector.disconnect(handle)
            return url, fmt

        url, fmt = _run_async(_exercise())
        assert url == "https://example.test/data/gdp_2024.csv"
        assert fmt == "csv"
