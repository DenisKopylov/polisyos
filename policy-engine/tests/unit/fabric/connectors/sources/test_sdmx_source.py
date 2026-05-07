"""Tests for SDMXSourceConnector (production SDMX connector)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.sdmx_source import (
    SDMXSourceConnector,
    _parse_sdmx_json,
)
from polisyos.fabric.connectors.types import FetchError
from polisyos.ir.connectors import (
    ConnectorCapability,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
)

FIXTURES_DIR = (
    Path(__file__).resolve().parents[4] / "_data" / "fabric" / "connectors" / "sources" / "sdmx"
)
_NOW = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)


def _run_async(coro):
    return asyncio.run(coro)


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


# ---------------------------------------------------------------------------
# ECB ConnectionConfig for tests
# ---------------------------------------------------------------------------


def _ecb_config() -> ConnectionConfig:
    return ConnectionConfig(
        url="https://data-api.ecb.europa.eu/service",
        headers={
            "X-SDMX-Agency": "ECB",
            "X-SDMX-DataPath": "data",
            "X-SDMX-DataflowPath": "dataflow",
            "X-SDMX-DimensionOrder": "FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX",
        },
    )


def _oecd_config() -> ConnectionConfig:
    return ConnectionConfig(
        url="https://sdmx.oecd.org/public/rest",
        headers={
            "X-SDMX-Agency": "OECD",
            "X-SDMX-Version": "3",
            "X-SDMX-DataPath": "data",
            "X-SDMX-DataflowPath": "dataflow",
            "X-SDMX-IncludeAgencyInDataPath": "false",
        },
    )


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_fake_sdmx_request_json(fixture_body: dict[str, Any]):
    """Return a mock for _sdmx_request_json that returns fixture data."""
    raw = json.dumps(fixture_body).encode("utf-8")
    headers = {
        "ETag": '"sdmx-test-etag-1"',
        "Last-Modified": "Mon, 15 Jan 2024 10:00:00 GMT",
    }

    async def _fake(self, handle, url, *, accept="data"):
        return fixture_body, headers, raw

    return _fake


def _make_fake_sdmx_request_head(head_headers: dict[str, str] | None = None):
    default_headers = {
        "ETag": '"sdmx-test-etag-1"',
        "Last-Modified": "Mon, 15 Jan 2024 10:00:00 GMT",
    }

    async def _fake(self, handle, url):
        return head_headers or default_headers

    return _fake


def _fake_get_session(self, _handle):
    """Return a dummy session (never used by mocked methods)."""
    import asyncio as _asyncio

    fut = _asyncio.Future()
    fut.set_result(object())
    return fut


# ---------------------------------------------------------------------------
# Metadata / class attributes
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_connector_id(self):
        assert SDMXSourceConnector.connector_id == "sdmx.source"

    def test_namespace_and_short_id(self):
        assert SDMXSourceConnector.namespace == "sdmx"
        assert SDMXSourceConnector.short_id == "source"

    def test_capabilities_flags(self):
        caps = SDMXSourceConnector.capabilities
        assert caps & ConnectorCapability.CATALOG_BROWSE
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.STREAMING
        assert caps & ConnectorCapability.FRESHNESS_CHECK
        assert caps & ConnectorCapability.DIMENSION_FILTER
        assert caps & ConnectorCapability.DATE_RANGE_FILTER
        assert caps & ConnectorCapability.RATE_LIMIT_AWARE

    def test_metadata_trust_and_quality(self):
        meta = SDMXSourceConnector.metadata
        assert meta.trust_level == TrustLevel.AUTHORITATIVE
        assert meta.quality_tier == QualityTier.GOLD
        assert meta.namespace == "sdmx"

    def test_resilience_profile(self):
        profile = SDMXSourceConnector.resilience_profile
        assert profile.base_delay == 2.0
        assert profile.max_delay == 120.0
        assert profile.rate_limit_rps == 5.0


# ---------------------------------------------------------------------------
# SDMX JSON parsing (pure function)
# ---------------------------------------------------------------------------


class TestParseSDMXJson:
    def test_parse_ecb_fixture(self):
        body = _load_fixture("ecb_exr_response.json")
        df = _parse_sdmx_json(body)
        assert len(df) == 6  # 2 series × 3 observations
        assert "value" in df.columns
        assert "FREQ" in df.columns
        assert "TIME_PERIOD" in df.columns
        assert "CURRENCY" in df.columns
        assert df["FREQ"].iloc[0] == "M"
        assert df["CURRENCY"].iloc[0] == "USD"

    def test_parse_empty_datasets(self):
        body = {"dataSets": []}
        df = _parse_sdmx_json(body)
        assert df.empty

    def test_parse_no_datasets_key(self):
        body = {"header": {}}
        df = _parse_sdmx_json(body)
        assert df.empty

    def test_parse_flat_observations(self):
        body = {
            "dataSets": [
                {
                    "observations": {
                        "0": [42.0],
                        "1": [43.0],
                    }
                }
            ],
            "structure": {
                "dimensions": {
                    "observation": [
                        {
                            "id": "TIME_PERIOD",
                            "values": [
                                {"id": "2024-01"},
                                {"id": "2024-02"},
                            ],
                        }
                    ]
                }
            },
        }
        df = _parse_sdmx_json(body)
        assert len(df) == 2
        assert df["TIME_PERIOD"].tolist() == ["2024-01", "2024-02"]
        assert df["value"].tolist() == [42.0, 43.0]

    def test_parse_nested_data_wrapper(self):
        body = {
            "meta": {"schema": "test"},
            "data": {
                "dataSets": [
                    {
                        "observations": {
                            "0": [42.0],
                        }
                    }
                ],
                "structure": {
                    "dimensions": {
                        "observation": [
                            {
                                "id": "TIME_PERIOD",
                                "values": [
                                    {"id": "2024"},
                                ],
                            }
                        ]
                    }
                },
            },
        }
        df = _parse_sdmx_json(body)
        assert len(df) == 1
        assert df["TIME_PERIOD"].tolist() == ["2024"]


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


class TestConfigParsing:
    def test_parse_ecb_config(self):
        config = _ecb_config()
        result = SDMXSourceConnector._parse_sdmx_config(config)
        assert result["agency"] == "ECB"
        assert result["data_path"] == "data"
        assert result["dataflow_path"] == "dataflow"
        assert result["dimension_order"] == [
            "FREQ",
            "CURRENCY",
            "CURRENCY_DENOM",
            "EXR_TYPE",
            "EXR_SUFFIX",
        ]

    def test_parse_oecd_config(self):
        config = _oecd_config()
        result = SDMXSourceConnector._parse_sdmx_config(config)
        assert result["agency"] == "OECD"
        assert result["version"] == "3"
        assert result["include_agency_in_data_path"] is False

    def test_defaults_for_missing_headers(self):
        config = ConnectionConfig(url="https://example.test")
        result = SDMXSourceConnector._parse_sdmx_config(config)
        assert result["agency"] == "ECB"
        assert result["version"] == "2"
        assert result["data_path"] == "data"
        assert result["dimension_order"] is None

    def test_strip_internal_headers(self):
        headers = {
            "X-SDMX-Agency": "ECB",
            "Accept": "application/json",
            "Authorization": "Bearer tok",
        }
        stripped = SDMXSourceConnector._strip_internal_headers(headers)
        assert "X-SDMX-Agency" not in stripped
        assert stripped["Accept"] == "application/json"
        assert stripped["Authorization"] == "Bearer tok"

    def test_validate_config_missing_url(self):
        config = ConnectionConfig(url="")
        result = SDMXSourceConnector.validate_config(config)
        assert not result.valid

    def test_validate_config_with_url(self):
        config = ConnectionConfig(url="https://example.test")
        result = SDMXSourceConnector.validate_config(config)
        assert result.valid


class TestCapabilityDescribe:
    def test_describe_dataset_extracts_dimensions_and_constraints(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture_body = {
            "structure": {
                "dataflows": [
                    {"id": "CPI_DATA", "version": "1.2.3"},
                ],
                "dataStructures": [
                    {
                        "dataStructureComponents": {
                            "dimensionList": {
                                "dimensions": [
                                    {"id": "FREQ"},
                                    {"id": "REF_AREA"},
                                    {"id": "MEASURE"},
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
                                    "REF_AREA": {"values": [{"id": "UKR"}, {"id": "DEU"}]},
                                    "FREQ": {"values": [{"id": "A"}]},
                                }
                            }
                        ]
                    }
                ],
            }
        }

        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_json",
            _make_fake_sdmx_request_json(fixture_body),
        )

        async def _exercise():
            handle = await connector.connect(_oecd_config())
            snapshot = await connector.describe_dataset(handle, "CPI_DATA")
            await connector.disconnect(handle)
            return snapshot

        snapshot = _run_async(_exercise())
        assert snapshot.resolved_dataset_id == "CPI_DATA"
        assert snapshot.dimension_order == ("FREQ", "REF_AREA", "MEASURE")
        assert list(snapshot.allowed_positions["REF_AREA"]) == ["DEU", "UKR"]
        assert snapshot.version_hint == "1.2.3"
        assert snapshot.estimated_cardinality == 2

    def test_describe_dataset_missing_version_coerces_to_empty_string(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture_body = {
            "structure": {
                "dataflows": [
                    {
                        "id": "CPI_DATA",
                    }
                ],
                "dataStructures": [
                    {
                        "id": "DSD_CPI_DATA",
                        "dataStructureComponents": {
                            "dimensionList": {
                                "dimensions": [
                                    {"id": "FREQ"},
                                    {"id": "REF_AREA"},
                                ]
                            }
                        },
                    }
                ],
            }
        }

        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_json",
            _make_fake_sdmx_request_json(fixture_body),
        )

        async def _exercise():
            handle = await connector.connect(_oecd_config())
            snapshot = await connector.describe_dataset(handle, "CPI_DATA")
            await connector.disconnect(handle)
            return snapshot

        snapshot = _run_async(_exercise())
        assert snapshot.version_hint == ""


# ---------------------------------------------------------------------------
# Filter / time helpers
# ---------------------------------------------------------------------------


class TestFilterAndTimeHelpers:
    def test_build_filter_path_empty(self):
        req = FetchRequest(dataset_id="EXR")
        path = SDMXSourceConnector._build_filter_path(req)
        assert path == ""

    def test_build_filter_path_with_key(self):
        req = FetchRequest(
            dataset_id="EXR",
            filters=(("key", ("M.USD.EUR.SP00.A",)),),
        )
        path = SDMXSourceConnector._build_filter_path(req)
        assert path == "M.USD.EUR.SP00.A"

    def test_build_filter_path_with_dimensions(self):
        req = FetchRequest(
            dataset_id="EXR",
            filters=(
                ("freq", ("M",)),
                ("geo", ("DE", "FR")),
            ),
        )
        order = ["freq", "geo", "indicator"]
        path = SDMXSourceConnector._build_filter_path(req, order)
        assert path == "M/DE+FR"

    def test_build_filter_path_trailing_empty_stripped(self):
        req = FetchRequest(
            dataset_id="EXR",
            filters=(("freq", ("M",)),),
        )
        order = ["freq", "geo", "indicator"]
        path = SDMXSourceConnector._build_filter_path(req, order)
        assert path == "M"

    def test_build_time_params_both(self):
        req = FetchRequest(
            dataset_id="EXR",
            date_start=datetime(2023, 1, 1, tzinfo=UTC),
            date_end=datetime(2024, 6, 30, tzinfo=UTC),
        )
        params = SDMXSourceConnector._build_time_params(req)
        assert params == {"startPeriod": "2023-01-01", "endPeriod": "2024-06-30"}

    def test_build_time_params_start_only(self):
        req = FetchRequest(
            dataset_id="EXR",
            date_start=datetime(2023, 1, 1, tzinfo=UTC),
        )
        params = SDMXSourceConnector._build_time_params(req)
        assert params == {"startPeriod": "2023-01-01"}

    def test_extract_structure_dimension_order_from_nested_data_payload(self):
        payload = {
            "data": {
                "dataStructures": [
                    {
                        "components": {
                            "dimensions": {
                                "dimension": [
                                    {"id": "REF_AREA"},
                                    {"id": "FREQ"},
                                    {"id": "MEASURE"},
                                    {"id": "SEX"},
                                    {"id": "AGE"},
                                ]
                            }
                        }
                    }
                ]
            }
        }

        order = SDMXSourceConnector._extract_structure_dimension_order(payload)

        assert order == ["REF_AREA", "FREQ", "MEASURE", "SEX", "AGE"]

    def test_build_time_params_none(self):
        req = FetchRequest(dataset_id="EXR")
        params = SDMXSourceConnector._build_time_params(req)
        assert params == {}


# ---------------------------------------------------------------------------
# Connect / disconnect lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_connect_stores_sdmx_config(self, monkeypatch):
        connector = SDMXSourceConnector()
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            assert "sdmx" in handle.state
            assert handle.state["sdmx"]["agency"] == "ECB"
            await connector.disconnect(handle)

        _run_async(_exercise())


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


class TestFetch:
    def test_fetch_ecb_exr(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_exr_response.json")

        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_json",
            _make_fake_sdmx_request_json(fixture),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            request = FetchRequest(dataset_id="EXR")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 6
        assert result.schema_id == "sdmx.source.exr"
        assert result.version.strategy == VersionStrategy.ETAG
        assert result.version.content_hash is not None
        assert result.fetch_duration_ms > 0.0
        assert result.quality_tier == QualityTier.GOLD
        assert result.bytes_transferred > 0

    def test_fetch_with_time_filters(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_exr_response.json")

        captured_urls: list[str] = []
        raw = json.dumps(fixture).encode("utf-8")

        async def _capture_url(self, handle, url, *, accept="data"):
            captured_urls.append(url)
            return fixture, {"ETag": '"e1"'}, raw

        monkeypatch.setattr(SDMXSourceConnector, "_sdmx_request_json", _capture_url)
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            request = FetchRequest(
                dataset_id="EXR",
                date_start=datetime(2023, 1, 1, tzinfo=UTC),
                date_end=datetime(2024, 12, 31, tzinfo=UTC),
            )
            await connector.fetch(handle, request)
            await connector.disconnect(handle)

        _run_async(_exercise())
        assert len(captured_urls) == 1
        assert "startPeriod=2023-01-01" in captured_urls[0]
        assert "endPeriod=2024-12-31" in captured_urls[0]

    def test_fetch_with_dimension_filters(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_exr_response.json")

        captured_urls: list[str] = []
        raw = json.dumps(fixture).encode("utf-8")

        async def _capture_url(self, handle, url, *, accept="data"):
            captured_urls.append(url)
            return fixture, {}, raw

        monkeypatch.setattr(SDMXSourceConnector, "_sdmx_request_json", _capture_url)
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            request = FetchRequest(
                dataset_id="EXR",
                filters=(("key", ("M.USD.EUR.SP00.A",)),),
            )
            await connector.fetch(handle, request)
            await connector.disconnect(handle)

        _run_async(_exercise())
        assert "M.USD.EUR.SP00.A" in captured_urls[0]

    def test_fetch_omits_agency_segment_when_profile_requests_it(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_exr_response.json")

        captured_urls: list[str] = []
        raw = json.dumps(fixture).encode("utf-8")

        async def _capture_url(self, handle, url, *, accept="data"):
            captured_urls.append(url)
            return fixture, {}, raw

        monkeypatch.setattr(SDMXSourceConnector, "_sdmx_request_json", _capture_url)
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_oecd_config())
            await connector.fetch(handle, FetchRequest(dataset_id="DF_TEST"))
            await connector.disconnect(handle)

        _run_async(_exercise())
        assert captured_urls
        assert "/data/DF_TEST" in captured_urls[0]
        assert "/data/OECD/DF_TEST" not in captured_urls[0]

    def test_fetch_empty_response(self, monkeypatch):
        connector = SDMXSourceConnector()
        empty_body = {"dataSets": []}

        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_json",
            _make_fake_sdmx_request_json(empty_body),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            request = FetchRequest(dataset_id="EXR")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 0
        assert result.data.empty

    def test_fetch_retries_transient_server_errors(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_exr_response.json")
        raw = json.dumps(fixture).encode("utf-8")
        calls = {"count": 0}

        async def _fake_request_json(
            self,
            session,
            url,
            *,
            params,
            connector_id,
            headers=None,
        ):
            calls["count"] += 1
            if calls["count"] < 3:
                status_code = 500 if calls["count"] == 1 else 503
                error = FetchError(
                    message=f"HTTP {status_code}",
                    connector_id=connector_id,
                    request_params={"url": url},
                )
                error.status_code = status_code  # type: ignore[attr-defined]
                raise error
            return fixture, {"ETag": '"retry-etag"'}, raw

        monkeypatch.setattr(SDMXSourceConnector, "_request_json", _fake_request_json)
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            result = await connector.fetch(handle, FetchRequest(dataset_id="EXR"))
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 6
        assert calls["count"] == 3


# ---------------------------------------------------------------------------
# List datasets (catalog browse)
# ---------------------------------------------------------------------------


class TestListDatasets:
    def test_list_ecb_dataflows(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_dataflows_response.json")

        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_json",
            _make_fake_sdmx_request_json(fixture),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            datasets = []
            async for ds in connector.list_datasets(handle):
                datasets.append(ds)
            await connector.disconnect(handle)
            return datasets

        datasets = _run_async(_exercise())
        assert len(datasets) == 3
        ids = [d.dataset_id for d in datasets]
        assert "ECB.EXR" in ids
        assert "ECB.ICP" in ids
        assert "ECB.BSI" in ids
        assert datasets[0].name == "Exchange Rates"
        assert "sdmx" in datasets[0].tags
        assert "ecb" in datasets[0].tags


# ---------------------------------------------------------------------------
# Streaming fetch
# ---------------------------------------------------------------------------


class TestFetchStream:
    def test_stream_produces_chunks(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_exr_response.json")

        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_json",
            _make_fake_sdmx_request_json(fixture),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            request = FetchRequest(dataset_id="EXR")
            chunks = []
            async for chunk in connector.fetch_stream(handle, request):
                chunks.append(chunk)
            await connector.disconnect(handle)
            return chunks

        chunks = _run_async(_exercise())
        assert len(chunks) >= 1
        total_rows = sum(c.row_count for c in chunks)
        assert total_rows == 6
        assert chunks[0].is_first
        assert chunks[-1].is_last


# ---------------------------------------------------------------------------
# Freshness check
# ---------------------------------------------------------------------------


class TestFreshness:
    def test_freshness_etag_fresh(self, monkeypatch):
        connector = SDMXSourceConnector()
        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_head",
            _make_fake_sdmx_request_head({"ETag": '"etag-v1"'}),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            result = await connector.check_freshness(
                handle,
                "EXR",
                DataVersion(strategy=VersionStrategy.ETAG, value='"etag-v1"', timestamp=_NOW),
            )
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.status.value == "fresh"

    def test_freshness_etag_stale(self, monkeypatch):
        connector = SDMXSourceConnector()
        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_head",
            _make_fake_sdmx_request_head({"ETag": '"etag-v2"'}),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            result = await connector.check_freshness(
                handle,
                "EXR",
                DataVersion(strategy=VersionStrategy.ETAG, value='"etag-v1"', timestamp=_NOW),
            )
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.status.value == "stale"
        assert result.new_version_available is True

    def test_freshness_timestamp_fresh(self, monkeypatch):
        connector = SDMXSourceConnector()
        lm = "Mon, 15 Jan 2024 10:00:00 GMT"
        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_head",
            _make_fake_sdmx_request_head({"Last-Modified": lm}),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            result = await connector.check_freshness(
                handle,
                "EXR",
                DataVersion(strategy=VersionStrategy.TIMESTAMP, value=lm, timestamp=_NOW),
            )
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.status.value == "fresh"

    def test_freshness_head_error_returns_unknown(self, monkeypatch):
        connector = SDMXSourceConnector()

        async def _raise(self, handle, url):
            raise Exception("network error")

        monkeypatch.setattr(SDMXSourceConnector, "_sdmx_request_head", _raise)
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            result = await connector.check_freshness(
                handle,
                "EXR",
                DataVersion(strategy=VersionStrategy.ETAG, value='"old"', timestamp=_NOW),
            )
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.status.value == "unknown"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_check_ok(self, monkeypatch):
        connector = SDMXSourceConnector()
        fixture = _load_fixture("ecb_dataflows_response.json")

        monkeypatch.setattr(
            SDMXSourceConnector,
            "_sdmx_request_json",
            _make_fake_sdmx_request_json(fixture),
        )
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            status = await connector.health_check(handle)
            await connector.disconnect(handle)
            return status

        status = _run_async(_exercise())
        assert status.healthy is True
        assert status.latency_ms > 0

    def test_health_check_failure(self, monkeypatch):
        connector = SDMXSourceConnector()

        async def _raise(self, handle, url, *, accept="data"):
            raise FetchError(message="HTTP 503", connector_id="sdmx.source")

        monkeypatch.setattr(SDMXSourceConnector, "_sdmx_request_json", _raise)
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            status = await connector.health_check(handle)
            await connector.disconnect(handle)
            return status

        status = _run_async(_exercise())
        assert status.healthy is False


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_get_dataset_schema(self, monkeypatch):
        connector = SDMXSourceConnector()
        monkeypatch.setattr(SDMXSourceConnector, "_get_session", _fake_get_session)

        async def _exercise():
            handle = await connector.connect(_ecb_config())
            schema = await connector.get_dataset_schema(handle, "EXR")
            await connector.disconnect(handle)
            return schema

        schema = _run_async(_exercise())
        assert schema["schema_id"] == "sdmx.source.EXR"
        assert schema["format"] == "sdmx-json"


# ---------------------------------------------------------------------------
# Dataflow extraction edge cases
# ---------------------------------------------------------------------------


class TestDataflowExtraction:
    def test_extract_dataflows_from_structure(self):
        body = {"structure": {"dataflows": [{"id": "A"}, {"id": "B"}]}}
        result = list(SDMXSourceConnector._extract_dataflows(body))
        assert len(result) == 2

    def test_extract_dataflows_alt_key(self):
        body = {"structure": {"dataFlows": [{"id": "X"}]}}
        result = list(SDMXSourceConnector._extract_dataflows(body))
        assert len(result) == 1

    def test_extract_dataflows_dict_format(self):
        body = {"dataflows": {"EXR": {"id": "EXR"}, "ICP": {"id": "ICP"}}}
        result = list(SDMXSourceConnector._extract_dataflows(body))
        assert len(result) == 2

    def test_extract_dataflows_empty(self):
        body = {}
        result = list(SDMXSourceConnector._extract_dataflows(body))
        assert len(result) == 0
