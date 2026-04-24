"""Tests for CKAN Catalog and Resource connectors."""

from __future__ import annotations

import asyncio
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.ckan_catalog import CKANCatalogConnector
from polisyos.fabric.connectors.sources.ckan_resource import CKANResourceConnector
from polisyos.fabric.connectors.types import FetchError
from polisyos.ir.connectors import ConnectorCapability

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

    def test_list_datasets_rejects_repeated_page_fingerprint(self, monkeypatch):
        connector = CKANCatalogConnector()

        async def _fake(_session, _url, *, params, connector_id):
            del connector_id
            rows = int(params["rows"])
            results = [
                {"id": f"pkg-{idx}", "name": f"pkg-{idx}", "title": f"Package {idx}"}
                for idx in range(rows)
            ]
            body = {"result": {"results": results}}
            raw = json.dumps(body).encode("utf-8")
            return body, {}, raw

        monkeypatch.setattr(CKANCatalogConnector, "_request_json", staticmethod(_fake))
        monkeypatch.setattr(CKANCatalogConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            try:
                async for _ in connector.list_datasets(handle):
                    pass
            finally:
                await connector.disconnect(handle)

        with pytest.raises(FetchError, match="repeated a prior page fingerprint"):
            _run_async(_exercise())


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
        monkeypatch.setattr(
            CKANCatalogConnector, "_request_json", _make_fake_request_json(status_body)
        )
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
        df = CKANResourceConnector._parse_resource(raw, "bin")
        assert len(df) == 1

    def test_parse_xlsx_uses_excel_reader(self, monkeypatch):
        called: dict[str, object] = {}

        def _fake_read_excel(*args, **kwargs):
            called["engine"] = kwargs.get("engine")
            return {"Sheet1": pd.DataFrame([{"name": "foo", "value": 1}])}

        monkeypatch.setattr(pd, "read_excel", _fake_read_excel)

        df = CKANResourceConnector._parse_resource(b"fake-xlsx", "xlsx")
        assert len(df) == 1
        assert "__sheet_name" in df.columns

    def test_parse_ods_uses_excel_reader(self, monkeypatch):
        def _fake_read_excel(*args, **kwargs):
            return {"Data": pd.DataFrame([{"name": "bar"}])}

        monkeypatch.setattr(pd, "read_excel", _fake_read_excel)

        df = CKANResourceConnector._parse_resource(b"fake-ods", "ods")
        assert len(df) == 1
        assert df.iloc[0]["__sheet_name"] == "Data"

    def test_parse_zip_csv(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("table.csv", "name,value\nfoo,1\nbar,2\n")

        df = CKANResourceConnector._parse_resource(buffer.getvalue(), "zip")
        assert len(df) == 2
        assert "__source_file" in df.columns
        assert set(df["name"].tolist()) == {"foo", "bar"}

    def test_parse_zip_rejects_traversal_member(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../evil.csv", "name,value\nfoo,1\n")

        with pytest.raises(FetchError, match="traversal member"):
            CKANResourceConnector._parse_resource(buffer.getvalue(), "zip")

    def test_parse_zip_rejects_excessive_member_count(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for idx in range(CKANResourceConnector._MAX_ZIP_MEMBERS + 1):
                archive.writestr(f"file-{idx}.csv", "name,value\nfoo,1\n")

        with pytest.raises(FetchError, match="member count"):
            CKANResourceConnector._parse_resource(buffer.getvalue(), "zip")

    def test_parse_zip_rejects_excessive_decompression_ratio(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("huge.csv", ("value\n" + ("1\n" * 5000)))

        with pytest.raises(FetchError, match="decompression ratio"):
            CKANResourceConnector._parse_resource(buffer.getvalue(), "zip")


class TestCKANResourceResolve:
    def test_resolve_direct_url(self):
        connector = CKANResourceConnector()

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            url, fmt = await connector._resolve_resource(
                handle,
                "https://data.example.test",
                "https://example.test/data.csv",
            )
            await connector.disconnect(handle)
            return url, fmt

        url, fmt = _run_async(_exercise())
        assert url == "https://example.test/data.csv"
        assert fmt == "csv"

    def test_resolve_direct_url_xlsx(self):
        connector = CKANResourceConnector()

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            url, fmt = await connector._resolve_resource(
                handle,
                "https://data.example.test",
                "https://example.test/data.xlsx",
            )
            await connector.disconnect(handle)
            return url, fmt

        url, fmt = _run_async(_exercise())
        assert url == "https://example.test/data.xlsx"
        assert fmt == "xlsx"

    def test_resolve_package_resource(self, monkeypatch):
        connector = CKANResourceConnector()
        fixture = _load_fixture("package_show_response.json")
        monkeypatch.setattr(
            CKANResourceConnector, "_request_json", _make_fake_request_json(fixture)
        )
        monkeypatch.setattr(CKANResourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ckan_config())
            url, fmt = await connector._resolve_resource(
                handle,
                "https://data.example.test",
                "gdp-annual/res-001",
            )
            await connector.disconnect(handle)
            return url, fmt

        url, fmt = _run_async(_exercise())
        assert url == "https://example.test/data/gdp_2024.csv"
        assert fmt == "csv"
