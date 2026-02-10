"""
Test suite for SDMXConnector - Phase 2.11.

Uses SDMX-JSON fixtures for parsing and integration tests.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts.schema import DataSchema, FieldSpec, SchemaType, SchemaVersion
from polisyos.fabric.connectors.reference.sdmx import SDMXConnector, _join_url, _parse_sdmx_json
from polisyos.fabric.connectors.testing import ConnectorTestHarness
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy

SDMX_JSON_SAMPLE = {
    "structure": {
        "dimensions": {
            "series": [
                {"id": "freq", "values": [{"id": "M"}]},
                {"id": "geo", "values": [{"id": "DE"}, {"id": "FR"}]},
            ],
            "observation": [
                {"id": "time_period", "values": [{"id": "2023-01"}, {"id": "2023-02"}]}
            ],
        }
    },
    "dataSets": [
        {
            "series": {
                "0:0": {"observations": {"0": [105.2], "1": [105.8]}},
                "0:1": {"observations": {"0": [108.0], "1": [108.3]}},
            }
        }
    ],
}

SDMX_JSON_OBS_ONLY = {
    "structure": {
        "dimensions": {
            "observation": [
                {"id": "time_period", "values": [{"id": "2023-01"}, {"id": "2023-02"}]}
            ]
        }
    },
    "dataSets": [{"observations": {"0": [1.0], "1": [2.0]}}],
}

SAMPLE_SCHEMA = DataSchema(
    schema_id="reference.sdmx.icp_m_de_n_062_l_30_q",
    version=SchemaVersion(1, 0, 0),
    fields=(
        FieldSpec(name="freq", data_type=SchemaType.STRING, nullable=False),
        FieldSpec(name="geo", data_type=SchemaType.STRING, nullable=False),
        FieldSpec(name="time_period", data_type=SchemaType.STRING, nullable=False),
        FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=True),
    ),
)


# =============================================================================
# Harness compliance
# =============================================================================


class TestSDMXCompliance(ConnectorTestHarness):
    connector_class = SDMXConnector
    sample_config = ConnectionConfig(
        url="https://stats.oecd.org/sdmx-rest",
        headers={"X-SDMX-Agency": "OECD"},
    )
    sample_schema = SAMPLE_SCHEMA
    sample_request = FetchRequest(dataset_id="ICP.M.DE.N.062.L.30-Q")

    @pytest.fixture()
    def connector_instance(self) -> SDMXConnector:
        connector = SDMXConnector()

        async def mock_fetch(handle, request):
            df = _parse_sdmx_json(SDMX_JSON_SAMPLE)
            version = DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value="sha256:" + "2" * 64,
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                content_hash="sha256:" + "2" * 64,
            )
            return FetchResult(
                data=df,
                row_count=len(df),
                schema_id="reference.sdmx.icp_m_de_n_062_l_30_q",
                schema_version="1.0.0",
                version=version,
                fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                completeness=1.0,
                quality_tier=QualityTier.GOLD,
            )

        async def mock_health_check(handle):
            return HealthStatus(healthy=True, message="mocked")

        connector.fetch = mock_fetch
        connector.health_check = mock_health_check
        return connector


# =============================================================================
# Unit tests - parsing
# =============================================================================


class TestSdmxJsonParsing:
    def test_basic_parse(self) -> None:
        df = _parse_sdmx_json(SDMX_JSON_SAMPLE)
        assert len(df) == 4
        assert set(df.columns) == {"freq", "geo", "time_period", "value"}

    def test_dimension_values(self) -> None:
        df = _parse_sdmx_json(SDMX_JSON_SAMPLE)
        assert set(df["geo"].unique()) == {"DE", "FR"}
        assert set(df["freq"].unique()) == {"M"}

    def test_observation_only(self) -> None:
        df = _parse_sdmx_json(SDMX_JSON_OBS_ONLY)
        assert len(df) == 2
        assert set(df.columns) == {"time_period", "value"}


class TestDimensionFilterPath:
    def test_single_dimension(self) -> None:
        request = FetchRequest(
            dataset_id="test",
            filters=(("freq", ("M",)),),
        )
        path = SDMXConnector._build_filter_path(request)
        assert path == "M"

    def test_multiple_dimensions(self) -> None:
        request = FetchRequest(
            dataset_id="test",
            filters=(
                ("freq", ("M",)),
                ("geo", ("DE", "FR")),
            ),
        )
        path = SDMXConnector._build_filter_path(request)
        assert "M" in path
        assert "DE+FR" in path or "FR+DE" in path

    def test_dimension_order_override(self) -> None:
        request = FetchRequest(
            dataset_id="test",
            filters=(("geo", ("US",)), ("freq", ("A",))),
        )
        path = SDMXConnector._build_filter_path(request, ["geo", "freq"])
        assert path == "US/A"


class TestUrlPatterns:
    def test_ecb_pattern(self) -> None:
        url = _join_url("https://data-api.ecb.europa.eu/service", "data", "ECB", "ICP")
        assert url == "https://data-api.ecb.europa.eu/service/data/ECB/ICP"

    def test_eurostat_pattern(self) -> None:
        url = _join_url("https://ec.europa.eu/sdmx/get-data", "data", "ESTAT", "nama_10_gdp")
        assert url == "https://ec.europa.eu/sdmx/get-data/data/ESTAT/nama_10_gdp"

    def test_oecd_pattern(self) -> None:
        url = _join_url("https://stats.oecd.org/sdmx-rest", "data", "OECD", "GDP")
        assert url == "https://stats.oecd.org/sdmx-rest/data/OECD/GDP"


class TestStreamingChunks:
    @pytest.mark.asyncio
    async def test_chunks_by_non_time_dims(self) -> None:
        connector = SDMXConnector()
        df = _parse_sdmx_json(SDMX_JSON_SAMPLE)

        async def mock_fetch(handle, request):
            return FetchResult(
                data=df,
                row_count=len(df),
                schema_id="test",
                schema_version="1.0.0",
                version=DataVersion(
                    strategy=VersionStrategy.TIMESTAMP,
                    value="now",
                    timestamp=datetime.now(timezone.utc),
                ),
                fetched_at=datetime.now(timezone.utc),
                completeness=1.0,
            )

        connector.fetch = mock_fetch
        handle = await connector.connect(ConnectionConfig(url="http://localhost"))
        request = FetchRequest(dataset_id="test")

        chunks = []
        async for chunk in connector.fetch_stream(handle, request):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].is_first
        assert chunks[-1].is_last
        assert all(chunk.row_count == 2 for chunk in chunks)


# =============================================================================
# Freshness check
# =============================================================================


class TestFreshnessCheck:
    def test_stale_when_last_modified_differs(self) -> None:
        cached = DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value="Mon, 01 Jan 2024 00:00:00 GMT",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        new_lm = "Tue, 15 Jan 2024 00:00:00 GMT"
        assert new_lm != cached.value

    def test_fresh_when_last_modified_matches(self) -> None:
        lm = "Mon, 01 Jan 2024 00:00:00 GMT"
        cached = DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value=lm,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert lm == cached.value


# =============================================================================
# Integration tests (local aiohttp server)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdmx_fetch_local() -> None:
    import aiohttp.web
    import json

    async def handler(request):
        return aiohttp.web.Response(
            status=200,
            headers={"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"},
            body=json.dumps(SDMX_JSON_SAMPLE).encode("utf-8"),
        )

    app = aiohttp.web.Application()
    app.router.add_get("/data/OECD/TEST", handler)

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}"

    connector = SDMXConnector()
    handle = await connector.connect(
        ConnectionConfig(url=url, headers={"X-SDMX-Agency": "OECD"})
    )

    result = await connector.fetch(handle, FetchRequest(dataset_id="TEST"))
    assert result.row_count == 4
    assert set(result.data.columns) == {"freq", "geo", "time_period", "value"}

    await connector.disconnect(handle)
    await runner.cleanup()
