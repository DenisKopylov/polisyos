"""Tests for SocrataConnector."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.socrata import SocrataConnector
from polisyos.fabric.safety import UnsafeFilterExpressionError, UnsafeIdentifierError
from polisyos.ir.connectors import ConnectorCapability

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "socrata"


def _run_async(coro):
    return asyncio.run(coro)


def _load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text())


def _socrata_config() -> ConnectionConfig:
    return ConnectionConfig(url="https://data.cityofnewyork.us")


def _make_fake_request_json(fixture_body):
    raw = json.dumps(fixture_body).encode("utf-8")
    headers = {"ETag": '"socrata-etag-1"'}

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


class TestSocrataMetadata:
    def test_connector_id(self):
        assert SocrataConnector.connector_id == "socrata.soda"

    def test_capabilities(self):
        caps = SocrataConnector.capabilities
        assert caps & ConnectorCapability.CATALOG_BROWSE
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.INCREMENTAL_FETCH
        assert caps & ConnectorCapability.DATE_RANGE_FILTER
        assert caps & ConnectorCapability.DIMENSION_FILTER


# ---------------------------------------------------------------------------
# SoQL params
# ---------------------------------------------------------------------------


class TestSoQLParams:
    def test_basic_params(self):
        req = FetchRequest(dataset_id="abc1-2345")
        params = SocrataConnector._build_soql_params(req)
        assert "$limit" in params
        assert "$order" in params
        assert "$where" not in params

    def test_dimension_filter(self):
        req = FetchRequest(
            dataset_id="abc1-2345",
            filters=(("borough", ("MANHATTAN",)),),
        )
        params = SocrataConnector._build_soql_params(req)
        assert "$where" in params
        assert "borough = 'MANHATTAN'" in params["$where"]

    def test_multi_value_filter(self):
        req = FetchRequest(
            dataset_id="abc1-2345",
            filters=(("borough", ("MANHATTAN", "BROOKLYN")),),
        )
        params = SocrataConnector._build_soql_params(req)
        assert "borough IN (" in params["$where"]

    def test_date_range(self):
        req = FetchRequest(
            dataset_id="abc1-2345",
            date_start=datetime(2024, 1, 1, tzinfo=UTC),
            date_end=datetime(2024, 12, 31, tzinfo=UTC),
        )
        params = SocrataConnector._build_soql_params(req)
        assert ":updated_at >=" in params["$where"]
        assert ":updated_at <=" in params["$where"]

    def test_explicit_where(self):
        req = FetchRequest(
            dataset_id="abc1-2345",
            filters=(("$where", ("complaint_type='Noise'",)),),
        )
        with pytest.raises(
            UnsafeFilterExpressionError,
            match="Raw \\$where filters are not allowed",
        ):
            SocrataConnector._build_soql_params(req)

    def test_escapes_literal_values(self):
        req = FetchRequest(
            dataset_id="abc1-2345",
            filters=(("borough", ("MANHATTAN' OR 1=1",)),),
        )
        params = SocrataConnector._build_soql_params(req)
        assert "borough = 'MANHATTAN'' OR 1=1'" in params["$where"]

    def test_rejects_unknown_filter_key_when_schema_is_available(self):
        req = FetchRequest(
            dataset_id="abc1-2345",
            filters=(("unknown_field", ("x",)),),
        )
        with pytest.raises(UnsafeIdentifierError, match="Unknown SoQL filter field"):
            SocrataConnector._build_soql_params(req, schema_fields={"borough"})


# ---------------------------------------------------------------------------
# List datasets
# ---------------------------------------------------------------------------


class TestSocrataListDatasets:
    def test_list_views(self, monkeypatch):
        connector = SocrataConnector()
        fixture = _load_fixture("views_response.json")
        monkeypatch.setattr(SocrataConnector, "_request_json", _make_fake_request_json(fixture))
        monkeypatch.setattr(SocrataConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_socrata_config())
            datasets = []
            async for ds in connector.list_datasets(handle):
                datasets.append(ds)
            await connector.disconnect(handle)
            return datasets

        datasets = _run_async(_exercise())
        assert len(datasets) == 2
        assert datasets[0].dataset_id == "abc1-2345"
        assert "socrata" in datasets[0].tags


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


class TestSocrataFetch:
    def test_fetch_resource(self, monkeypatch):
        connector = SocrataConnector()
        fixture = _load_fixture("resource_response.json")
        monkeypatch.setattr(SocrataConnector, "_request_json", _make_fake_request_json(fixture))
        monkeypatch.setattr(SocrataConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_socrata_config())
            request = FetchRequest(dataset_id="abc1-2345")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 3
        assert "borough" in result.data.columns
        assert result.schema_id == "socrata.soda.abc1-2345"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestSocrataHealth:
    def test_health_ok(self, monkeypatch):
        connector = SocrataConnector()
        monkeypatch.setattr(SocrataConnector, "_request_json", _make_fake_request_json([]))
        monkeypatch.setattr(SocrataConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_socrata_config())
            status = await connector.health_check(handle)
            await connector.disconnect(handle)
            return status

        status = _run_async(_exercise())
        assert status.healthy is True
