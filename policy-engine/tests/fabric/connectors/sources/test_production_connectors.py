from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.ukons import UKONSConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector, _retry_after_seconds
from polisyos.ir.connectors import VersionStrategy


def _run_async(coro):
    return asyncio.run(coro)


def test_world_bank_fetch_with_mock_http(monkeypatch) -> None:
    connector = WorldBankConnector()
    responses: dict[int, Any] = {
        1: [
            {"pages": 2},
            [
                {
                    "countryiso3code": "USA",
                    "country": {"id": "US", "value": "United States"},
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                    "date": "2022",
                    "value": "25000000000000",
                    "unit": "",
                    "decimal": "0",
                }
            ],
        ],
        2: [
            {"pages": 2},
            [
                {
                    "countryiso3code": "DEU",
                    "country": {"id": "DE", "value": "Germany"},
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                    "date": "2022",
                    "value": "4200000000000",
                    "unit": "",
                    "decimal": "0",
                }
            ],
        ],
    }

    async def _fake_request_json(_session, _url, *, params, connector_id):
        assert connector_id == "worldbank.wdi"
        page = int(params["page"])
        body = responses[page]
        headers = {
            "ETag": '"wdi-etag-1"',
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        }
        return body, headers, json.dumps(body).encode("utf-8")

    async def _fake_get_session(self, _handle):  # noqa: ARG001
        return object()

    monkeypatch.setattr(WorldBankConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(WorldBankConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        request = FetchRequest(dataset_id="NY.GDP.MKTP.CD")
        result = await connector.fetch(handle, request)
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 2
    assert result.schema_id == "worldbank.wdi.generic"
    assert result.version.strategy == VersionStrategy.ETAG
    assert result.version.content_hash is not None
    assert sorted(result.data["country_code"].tolist()) == ["DEU", "USA"]


def test_world_bank_retry_after_falls_back_to_x_ratelimit_reset() -> None:
    reset_in_60s = datetime.now(timezone.utc) + timedelta(seconds=60)
    delay = _retry_after_seconds({"X-RateLimit-Reset": str(reset_in_60s.timestamp())})
    assert delay is not None
    assert 0.0 <= delay <= 61.0


def test_eurostat_fetch_with_mock_http(monkeypatch) -> None:
    connector = EurostatConnector()
    payload = {
        "id": ["geo", "time"],
        "size": [1, 2],
        "dimension": {
            "geo": {"category": {"index": {"DE": 0}, "label": {"DE": "DE"}}},
            "time": {
                "category": {
                    "index": {"2021": 0, "2022": 1},
                    "label": {"2021": "2021", "2022": "2022"},
                }
            },
        },
        "value": {"0": 100.0, "1": 110.5},
    }

    async def _fake_request_json(_session, _url, *, params, connector_id):
        assert connector_id == "eurostat.data"
        assert params["format"] == "JSON"
        headers = {"Last-Modified": "Tue, 02 Jan 2024 00:00:00 GMT"}
        return payload, headers, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):  # noqa: ARG001
        return object()

    monkeypatch.setattr(EurostatConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(EurostatConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        request = FetchRequest(dataset_id="nama_10_gdp")
        result = await connector.fetch(handle, request)
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 2
    assert result.schema_id == "eurostat.data.generic"
    assert result.version.strategy == VersionStrategy.TIMESTAMP
    assert result.source_updated_at is not None
    assert set(result.data["time_period"].tolist()) == {"2021", "2022"}


def test_ukons_fetch_with_mock_http(monkeypatch) -> None:
    connector = UKONSConnector()
    payload = {
        "observations": [
            {
                "observation": "10.5",
                "dimensions": [
                    {"dimension_id": "time", "option_id": "2024-01"},
                    {"dimension_id": "geography", "option_id": "K02000001"},
                ],
            }
        ]
    }

    async def _fake_request_json(_session, _url, *, params, connector_id):
        assert connector_id == "ukons.datasets"
        assert isinstance(params, dict)
        headers: dict[str, str] = {}
        return payload, headers, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):  # noqa: ARG001
        return object()

    monkeypatch.setattr(UKONSConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(UKONSConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        request = FetchRequest(dataset_id="cpih01")
        result = await connector.fetch(handle, request)
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 1
    assert result.schema_id == "ukons.datasets.generic"
    assert result.version.strategy == VersionStrategy.CONTENT_HASH
    assert result.data.iloc[0]["geography"] == "K02000001"
