"""Tests for OpendatasoftConnector."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from polisyos.fabric.safety import UnsafeFilterExpressionError, UnsafeIdentifierError
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.opendatasoft import OpendatasoftConnector
from polisyos.ir.connectors import ConnectorCapability

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "opendatasoft"


def _run_async(coro):
    return asyncio.run(coro)


def _load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text())


def _ods_config(*, export_mode: str = "records") -> ConnectionConfig:
    headers = {}
    if export_mode != "records":
        headers["X-ODS-ExportMode"] = export_mode
    return ConnectionConfig(url="https://public.opendatasoft.com", headers=headers)


def _make_fake_request_json(fixture_body):
    raw = json.dumps(fixture_body).encode("utf-8")
    headers = {"ETag": '"ods-etag-1"'}

    async def _fake(_session, _url, *, params, connector_id):
        return fixture_body, headers, raw

    return staticmethod(_fake)


def _fake_get_session(self, _handle):
    import asyncio as _aio
    fut = _aio.Future()
    fut.set_result(object())
    return fut


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestODSMetadata:
    def test_connector_id(self):
        assert OpendatasoftConnector.connector_id == "opendatasoft.ods"

    def test_capabilities(self):
        caps = OpendatasoftConnector.capabilities
        assert caps & ConnectorCapability.CATALOG_BROWSE
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.DATE_RANGE_FILTER


# ---------------------------------------------------------------------------
# Where builder
# ---------------------------------------------------------------------------

class TestODSWhereBuilder:
    def test_empty(self):
        req = FetchRequest(dataset_id="test")
        assert OpendatasoftConnector._build_where(req) == ""

    def test_dimension_filter(self):
        req = FetchRequest(
            dataset_id="test",
            filters=(("station", ("Bastille",)),),
        )
        result = OpendatasoftConnector._build_where(req)
        assert "station = 'Bastille'" in result

    def test_date_range(self):
        req = FetchRequest(
            dataset_id="test",
            date_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            date_end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )
        result = OpendatasoftConnector._build_where(req)
        assert "date >= '2024-01-01'" in result
        assert "date <= '2024-12-31'" in result

    def test_rejects_raw_where_clause(self):
        req = FetchRequest(
            dataset_id="test",
            filters=(("where", ("station = 'Bastille'",)),),
        )
        with pytest.raises(
            UnsafeFilterExpressionError,
            match="Raw ODSQL where clauses are not allowed",
        ):
            OpendatasoftConnector._build_where(req)

    def test_escapes_literal_values(self):
        req = FetchRequest(
            dataset_id="test",
            filters=(("station", ("Bastille' OR 1=1",)),),
        )
        result = OpendatasoftConnector._build_where(req)
        assert "station = 'Bastille'' OR 1=1'" in result

    def test_rejects_unknown_filter_key_when_schema_is_available(self):
        req = FetchRequest(
            dataset_id="test",
            filters=(("unknown_field", ("x",)),),
        )
        with pytest.raises(UnsafeIdentifierError, match="Unknown ODSQL filter field"):
            OpendatasoftConnector._build_where(req, schema_fields={"station"})


# ---------------------------------------------------------------------------
# List datasets
# ---------------------------------------------------------------------------

class TestODSListDatasets:
    def test_list_catalog(self, monkeypatch):
        connector = OpendatasoftConnector()
        fixture = _load_fixture("catalog_response.json")
        monkeypatch.setattr(OpendatasoftConnector, "_request_json", _make_fake_request_json(fixture))
        monkeypatch.setattr(OpendatasoftConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ods_config())
            datasets = []
            async for ds in connector.list_datasets(handle):
                datasets.append(ds)
            await connector.disconnect(handle)
            return datasets

        datasets = _run_async(_exercise())
        assert len(datasets) == 2
        assert datasets[0].dataset_id == "air-quality-paris"
        assert "opendatasoft" in datasets[0].tags


# ---------------------------------------------------------------------------
# Fetch (records mode)
# ---------------------------------------------------------------------------

class TestODSFetchRecords:
    def test_fetch_records(self, monkeypatch):
        connector = OpendatasoftConnector()
        fixture = _load_fixture("records_response.json")
        monkeypatch.setattr(OpendatasoftConnector, "_request_json", _make_fake_request_json(fixture))
        monkeypatch.setattr(OpendatasoftConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ods_config())
            request = FetchRequest(dataset_id="air-quality-paris")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 3
        assert "pm25" in result.data.columns
        assert "station" in result.data.columns


# ---------------------------------------------------------------------------
# Fetch (exports mode)
# ---------------------------------------------------------------------------

class TestODSFetchExports:
    def test_fetch_exports(self, monkeypatch):
        connector = OpendatasoftConnector()
        export_body = [
            {"date": "2024-01-15", "value": 12.5},
            {"date": "2024-01-16", "value": 15.3},
        ]
        monkeypatch.setattr(
            OpendatasoftConnector, "_request_json",
            _make_fake_request_json(export_body),
        )
        monkeypatch.setattr(OpendatasoftConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ods_config(export_mode="exports"))
            request = FetchRequest(dataset_id="air-quality-paris")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 2


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestODSHealth:
    def test_health_ok(self, monkeypatch):
        connector = OpendatasoftConnector()
        monkeypatch.setattr(
            OpendatasoftConnector, "_request_json",
            _make_fake_request_json({"results": []}),
        )
        monkeypatch.setattr(OpendatasoftConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ods_config())
            status = await connector.health_check(handle)
            await connector.disconnect(handle)
            return status

        status = _run_async(_exercise())
        assert status.healthy is True
