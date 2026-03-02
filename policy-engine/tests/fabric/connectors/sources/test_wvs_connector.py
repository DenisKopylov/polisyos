from __future__ import annotations

import asyncio
import json
from typing import Any

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.wvs import WVSConnector


def _run_async(coro):
    return asyncio.run(coro)


def test_find_closest_in_wave_returns_wave7_match() -> None:
    connector = WVSConnector()
    survey_year, wave = connector.find_closest_in_wave("DE", 2020, max_distance_years=3)
    assert survey_year == 2018
    assert wave == 7


def test_find_closest_in_wave_rejects_far_distance() -> None:
    connector = WVSConnector()
    survey_year, wave = connector.find_closest_in_wave("DE", 2024, max_distance_years=3)
    assert survey_year is None
    assert wave is None


def test_wvs_fetch_with_mock_http(monkeypatch) -> None:
    connector = WVSConnector()
    payload = {
        "data": [
            {
                "country_code": "DE",
                "country_name": "Germany",
                "survey_year": 2018,
                "wave": 7,
                "indicator_code": "A165",
                "indicator_label": "Most people can be trusted",
                "value": "0.61",
                "sample_size": "1200",
            }
        ]
    }

    async def _fake_request_json(_session, _url, *, params, connector_id):
        assert connector_id == "wvs.wave7"
        assert params["indicator"] == "A165"
        headers = {
            "ETag": '"wvs-etag-1"',
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        }
        return payload, headers, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):  # noqa: ARG001
        return object()

    monkeypatch.setattr(WVSConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(WVSConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        request = FetchRequest(dataset_id="A165", filters=(("country", ("DE",)),))
        result = await connector.fetch(handle, request)
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 1
    assert result.schema_id == "wvs.wave7.generic"
    assert result.fetch_duration_ms > 0.0
    assert result.data.iloc[0]["country_code"] == "DE"
    assert result.data.iloc[0]["survey_year"] == 2018
    assert result.data.iloc[0]["wave"] == 7


def test_wvs_fetch_wave_closest_fallback(monkeypatch) -> None:
    connector = WVSConnector()

    empty_payload: dict[str, Any] = {"data": []}
    fallback_payload = {
        "data": [
            {
                "country_code": "DE",
                "country_name": "Germany",
                "survey_year": 2018,
                "wave": 7,
                "indicator_code": "A165",
                "value": 0.59,
            }
        ]
    }

    async def _fake_request_json(_session, _url, *, params, connector_id):
        assert connector_id == "wvs.wave7"
        survey_year = params.get("survey_year")
        headers = {"ETag": '"wvs-etag-1"'}
        if survey_year == "2020":
            return empty_payload, headers, json.dumps(empty_payload).encode("utf-8")
        if survey_year == "2018":
            return fallback_payload, headers, json.dumps(fallback_payload).encode("utf-8")
        return empty_payload, headers, json.dumps(empty_payload).encode("utf-8")

    async def _fake_get_session(self, _handle):  # noqa: ARG001
        return object()

    monkeypatch.setattr(WVSConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(WVSConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        request = FetchRequest(
            dataset_id="A165",
            filters=(("country", ("DE",)), ("survey_year", ("2020",))),
        )
        result = await connector.fetch(handle, request)
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 1
    assert result.data.iloc[0]["survey_year"] == 2018
