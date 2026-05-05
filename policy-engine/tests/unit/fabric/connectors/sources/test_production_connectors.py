from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from polisyos.fabric.connectors.base import AsyncFetchLease, ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.ukons import UKONSConnector
from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
from polisyos.fabric.connectors.sources.unpd import UNPDConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector, _retry_after_seconds
from polisyos.fabric.connectors.sources.wvs import WVSConnector
from polisyos.fabric.safety import UnsafePathSegmentError
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

    async def _fake_get_session(self, _handle):
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
    assert result.fetch_duration_ms > 0.0
    assert sorted(result.data["country_code"].tolist()) == ["DEU", "USA"]


def test_world_bank_retry_after_falls_back_to_x_ratelimit_reset() -> None:
    reset_in_60s = datetime.now(UTC) + timedelta(seconds=60)
    delay = _retry_after_seconds({"X-RateLimit-Reset": str(reset_in_60s.timestamp())})
    assert delay is not None
    assert 0.0 <= delay <= 61.0


def test_world_bank_fetch_batches_multiple_indicators_and_incremental_params(monkeypatch) -> None:
    connector = WorldBankConnector()
    captured: list[dict[str, Any]] = []
    response = [
        {"pages": 1},
        [
            {
                "countryiso3code": "UKR",
                "country": {"id": "UA", "value": "Ukraine"},
                "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"},
                "date": "2024",
                "value": "100",
                "unit": "",
                "decimal": "0",
            },
            {
                "countryiso3code": "UKR",
                "country": {"id": "UA", "value": "Ukraine"},
                "indicator": {"id": "SP.POP.TOTL", "value": "Population"},
                "date": "2024",
                "value": "200",
                "unit": "",
                "decimal": "0",
            },
        ],
    ]

    async def _fake_request_json(_session, url, *, params, connector_id):
        captured.append({"url": url, "params": dict(params), "connector_id": connector_id})
        headers = {"ETag": '"wdi-etag-2"'}
        return response, headers, json.dumps(response).encode("utf-8")

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(WorldBankConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(WorldBankConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        result = await connector.fetch(
            handle,
            FetchRequest(
                dataset_id="NY.GDP.MKTP.CD;SP.POP.TOTL",
                filters=(
                    ("country", ("UKR", "DEU")),
                    ("mrv", ("2",)),
                    ("frequency", ("Y",)),
                ),
                page_size=500,
            ),
        )
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 2
    assert len(captured) == 1
    assert captured[0]["url"].endswith("/country/DEU;UKR/indicator/NY.GDP.MKTP.CD;SP.POP.TOTL")
    assert captured[0]["params"]["per_page"] == "500"
    assert captured[0]["params"]["mrv"] == "2"
    assert captured[0]["params"]["frequency"] == "Y"
    assert sorted(result.data["indicator_id"].tolist()) == ["NY.GDP.MKTP.CD", "SP.POP.TOTL"]


def test_world_bank_rejects_unsafe_path_segments() -> None:
    with pytest.raises(UnsafePathSegmentError, match="World Bank indicator id"):
        WorldBankConnector._normalize_indicator_batch("../etc/passwd")

    request = FetchRequest(
        dataset_id="NY.GDP.MKTP.CD",
        filters=(("country", ("../",)),),
    )
    with pytest.raises(UnsafePathSegmentError, match="World Bank country code"):
        WorldBankConnector._parse_countries(request)


def test_eurostat_fetch_with_mock_http(monkeypatch) -> None:
    connector = EurostatConnector()
    payload = {
        "id": ["geo", "unit", "time"],
        "size": [1, 1, 2],
        "dimension": {
            "geo": {"category": {"index": {"DE": 0}, "label": {"DE": "Germany"}}},
            "unit": {
                "category": {
                    "index": {"PC_GDP": 0},
                    "label": {"PC_GDP": "Percentage of gross domestic product (GDP)"},
                }
            },
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

    async def _fake_get_session(self, _handle):
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
    assert result.fetch_duration_ms > 0.0
    assert result.quality_flags == frozenset()
    assert set(result.data["time_period"].tolist()) == {"2021", "2022"}
    assert set(result.data["unit"].tolist()) == {"PC_GDP"}
    dimensions = [json.loads(value) for value in result.data["dimensions_json"].tolist()]
    assert {item["geo"] for item in dimensions} == {"DE"}
    assert {item["unit"] for item in dimensions} == {"PC_GDP"}


def test_eurostat_uses_since_and_until_time_period_params(monkeypatch) -> None:
    connector = EurostatConnector()
    payload = {
        "id": ["geo", "time"],
        "size": [1, 1],
        "dimension": {
            "geo": {"category": {"index": {"UA": 0}, "label": {"UA": "UA"}}},
            "time": {
                "category": {
                    "index": {"2023": 0},
                    "label": {"2023": "2023"},
                }
            },
        },
        "value": {"0": 100.0},
    }

    async def _fake_request_json(_session, _url, *, params, connector_id):
        assert connector_id == "eurostat.data"
        assert params["format"] == "JSON"
        assert params["geo"] == "UA"
        assert params["sinceTimePeriod"] == "2020"
        assert params["untilTimePeriod"] == "2022"
        assert "time" not in params
        headers = {"Last-Modified": "Tue, 02 Jan 2024 00:00:00 GMT"}
        return payload, headers, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(EurostatConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(EurostatConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        result = await connector.fetch(
            handle,
            FetchRequest(
                dataset_id="ilc_test",
                filters=(("geo", ("UA",)),),
                date_start=datetime(2020, 1, 1, tzinfo=UTC),
                date_end=datetime(2022, 12, 31, tzinfo=UTC),
            ),
        )
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 1
    assert result.data.iloc[0]["time_period"] == "2023"


def test_eurostat_describe_dataset_extracts_structure_constraints(monkeypatch) -> None:
    connector = EurostatConnector()
    payload = {
        "structure": {
            "dataflows": [{"id": "ilc_test", "version": "2026-01"}],
            "dataStructures": [
                {
                    "dataStructureComponents": {
                        "dimensionList": {
                            "dimensions": [
                                {"id": "geo"},
                                {"id": "time"},
                                {"id": "hhtyp"},
                            ]
                        }
                    }
                }
            ],
            "contentConstraints": [
                {
                    "cubeRegions": [
                        {
                            "keyValues": {
                                "geo": {"values": [{"id": "DE"}, {"id": "UA"}]},
                                "hhtyp": {"values": [{"id": "A1"}, {"id": "A2"}]},
                            }
                        }
                    ]
                }
            ],
        }
    }

    async def _fake_request_json(_session, _url, *, params, connector_id, headers=None):
        return payload, {}, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(EurostatConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(EurostatConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        snapshot = await connector.describe_dataset(handle, "ilc_test")
        await connector.disconnect(handle)
        return snapshot

    snapshot = _run_async(_exercise())
    assert snapshot.dimension_order == ("geo", "time", "hhtyp")
    assert list(snapshot.allowed_positions["geo"]) == ["DE", "UA"]
    assert snapshot.version_hint == "2026-01"
    assert snapshot.estimated_cardinality == 4


def test_eurostat_async_lease_lifecycle(monkeypatch) -> None:
    connector = EurostatConnector()
    submit_xml = b"""
    <env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
      <env:Body>
        <syncResponse>
          <queued>
            <id>lease-123</id>
            <status>SUBMITTED</status>
          </queued>
        </syncResponse>
      </env:Body>
    </env:Envelope>
    """
    processing_xml = b"""
    <env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
      <env:Body>
        <asyncResponse>
          <status>
            <key>lease-123</key>
            <status>PROCESSING</status>
          </status>
        </asyncResponse>
      </env:Body>
    </env:Envelope>
    """
    available_xml = b"""
    <env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
      <env:Body>
        <asyncResponse>
          <status>
            <key>lease-123</key>
            <status>AVAILABLE</status>
          </status>
        </asyncResponse>
      </env:Body>
    </env:Envelope>
    """
    payload = {
        "id": ["geo", "time"],
        "size": [1, 1],
        "dimension": {
            "geo": {"category": {"index": {"UA": 0}, "label": {"UA": "UA"}}},
            "time": {"category": {"index": {"2022": 0}, "label": {"2022": "2022"}}},
        },
        "value": {"0": 42.0},
    }
    describe_payload = {
        "structure": {
            "dataflows": [{"id": "ilc_test", "version": "2026-01"}],
            "dataStructures": [
                {
                    "dataStructureComponents": {
                        "dimensionList": {
                            "dimensions": [{"id": "geo"}, {"id": "time"}, {"id": "hhtyp"}]
                        }
                    }
                }
            ],
            "contentConstraints": [
                {
                    "cubeRegions": [
                        {
                            "keyValues": {
                                "geo": {"values": [{"id": "UA"}]},
                                "hhtyp": {"values": [{"id": "A1"}, {"id": "A2"}]},
                            }
                        }
                    ]
                }
            ],
        }
    }
    poll_state = {"count": 0}

    async def _fake_request_json(_session, _url, *, params, connector_id, headers=None):
        return describe_payload, {}, json.dumps(describe_payload).encode("utf-8")

    async def _fake_request_raw(self, _session, url, *, params, connector_id, headers=None):
        if "/data/ilc_test" in url:
            return submit_xml, {}
        if url.endswith("/status/lease-123"):
            poll_state["count"] += 1
            return (processing_xml if poll_state["count"] == 1 else available_xml), {}
        if url.endswith("/data/lease-123"):
            return json.dumps(payload).encode("utf-8"), {}
        raise AssertionError(url)

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(EurostatConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(EurostatConnector, "_request_raw", _fake_request_raw)
    monkeypatch.setattr(EurostatConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        request = FetchRequest(
            dataset_id="ilc_test",
            filters=(("geo", ("UA",)),),
            date_start=datetime(2022, 1, 1, tzinfo=UTC),
            date_end=datetime(2022, 12, 31, tzinfo=UTC),
        )
        lease = await connector.fetch_async(handle, request)
        first = await connector.poll_async_fetch(handle, lease)
        second = await connector.poll_async_fetch(
            handle,
            first if isinstance(first, AsyncFetchLease) else lease,
        )
        await connector.disconnect(handle)
        return lease, first, second

    lease, first, second = _run_async(_exercise())
    assert lease.lease_id == "lease-123"
    assert lease.status == "submitted"
    assert isinstance(first, AsyncFetchLease)
    assert first.status == "processing"
    assert second.row_count == 1
    assert second.data.iloc[0]["time_period"] == "2022"


def test_eurostat_rejects_unsafe_path_segments() -> None:
    snapshot = type(
        "Snapshot",
        (),
        {"dimension_order": ("geo", "time")},
    )()
    request = FetchRequest(
        dataset_id="nama_10_gdp",
        filters=(("geo", ("../",)),),
    )
    with pytest.raises(UnsafePathSegmentError, match="Eurostat dimension 'geo'"):
        EurostatConnector._build_sdmx_key(request, snapshot=snapshot)


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

    async def _fake_get_session(self, _handle):
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
    assert result.fetch_duration_ms > 0.0
    assert "freshness:source_timestamp_missing" in result.quality_flags
    assert result.data.iloc[0]["geography"] == "K02000001"


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
                "value": 0.61,
                "sample_size": 1200,
            }
        ]
    }

    async def _fake_request_json(_session, _url, *, params, connector_id):
        assert connector_id == "wvs.wave7"
        assert params["indicator"] == "A165"
        headers = {"ETag": '"wvs-etag-1"'}
        return payload, headers, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):
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
    assert result.version.strategy == VersionStrategy.ETAG
    assert result.fetch_duration_ms > 0.0
    assert result.data.iloc[0]["country_code"] == "DE"


def test_who_fetch_with_mock_http(monkeypatch) -> None:
    connector = WHOConnector()
    payload = {
        "value": [
            {
                "IndicatorCode": "WHOSIS_000001",
                "SpatialDim": "UKR",
                "TimeDim": 2020,
                "NumericValue": 72.5,
                "Dim1": "SEX_BTSX",
                "Date": "2024-08-02T09:43:39.193+02:00",
            }
        ]
    }

    async def _fake_request_json(_session, _url, *, params, connector_id, headers=None):
        del headers
        assert connector_id == "who.indicators"
        assert "SpatialDim eq 'UKR'" in params["$filter"]
        return payload, {}, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(WHOConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(WHOConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        result = await connector.fetch(
            handle,
            FetchRequest(
                dataset_id="WHOSIS_000001",
                filters=(("country", ("UA",)),),
                date_start=datetime(2020, 1, 1, tzinfo=UTC),
                date_end=datetime(2020, 12, 31, tzinfo=UTC),
            ),
        )
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 1
    assert result.schema_id == "who.indicators.generic"
    assert result.data.iloc[0]["country_code"] == "UKR"


def test_unpd_fetch_with_mock_http(monkeypatch) -> None:
    connector = UNPDConnector()
    payload = {
        "data": [
            {
                "indicatorId": "1",
                "iso3": "UKR",
                "locationId": 804,
                "timeLabel": "2020",
                "value": 55.1,
                "variantId": 4,
                "sexId": 2,
            }
        ]
    }

    async def _fake_request_json(_session, _url, *, params, connector_id, headers=None):
        del params
        assert connector_id == "unpd.data"
        assert headers == {"Authorization": "Bearer token-123"}
        return payload, {}, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(UNPDConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(UNPDConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(
            ConnectionConfig(
                url="https://example.test",
                auth_credentials={"token": "token-123"},
            )
        )
        result = await connector.fetch(
            handle,
            FetchRequest(
                dataset_id="1",
                filters=(("country", ("UA",)),),
                date_start=datetime(2020, 1, 1, tzinfo=UTC),
                date_end=datetime(2020, 12, 31, tzinfo=UTC),
            ),
        )
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 1
    assert result.schema_id == "unpd.data.generic"
    assert result.data.iloc[0]["country_code"] == "UKR"


def test_unesco_uis_fetch_with_mock_http(monkeypatch) -> None:
    connector = UNESCOUISConnector()
    payload = {
        "records": [
            {
                "indicatorId": "200101",
                "geoUnit": "UKR",
                "year": 2020,
                "value": 44835.87,
                "magnitude": None,
                "qualifier": None,
            }
        ]
    }

    async def _fake_request_json(_session, _url, *, params, connector_id, headers=None):
        del headers
        assert connector_id == "unesco_uis.data"
        assert params["indicator"] == "200101"
        return payload, {}, json.dumps(payload).encode("utf-8")

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(UNESCOUISConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(UNESCOUISConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        result = await connector.fetch(
            handle,
            FetchRequest(
                dataset_id="200101",
                filters=(("country", ("UA",)),),
                date_start=datetime(2020, 1, 1, tzinfo=UTC),
                date_end=datetime(2020, 12, 31, tzinfo=UTC),
            ),
        )
        await connector.disconnect(handle)
        return result

    result = _run_async(_exercise())
    assert result.row_count == 1
    assert result.schema_id == "unesco_uis.data.generic"
    assert result.data.iloc[0]["country_code"] == "UKR"
