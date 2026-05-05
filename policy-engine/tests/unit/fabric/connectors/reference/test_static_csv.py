"""
Test suite for StaticCSVConnector - Phase 2.11.

Includes harness compliance and connector-specific unit/integration tests.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pandas as pd
import pytest
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.reference.static_csv import StaticCSVConnector
from polisyos.fabric.connectors.testing import ConnectorTestHarness
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy

SAMPLE_CSV = "id,country,gdp_usd,year\n1,US,21433226,2019\n2,DE,3863344,2019\n3,FR,2716692,2019\n"

SAMPLE_SCHEMA = DataSchema(
    schema_id="reference.static_csv.test_dataset",
    version=SchemaVersion(1, 0, 0),
    fields=(
        FieldSpec(name="id", data_type=SchemaType.INT64, nullable=False),
        FieldSpec(name="country", data_type=SchemaType.STRING, nullable=False),
        FieldSpec(name="gdp_usd", data_type=SchemaType.INT64, nullable=False),
        FieldSpec(name="year", data_type=SchemaType.INT64, nullable=False),
    ),
)


@pytest.fixture
def connector() -> StaticCSVConnector:
    return StaticCSVConnector()


# =============================================================================
# Harness compliance
# =============================================================================


class TestStaticCSVCompliance(ConnectorTestHarness):
    connector_class = StaticCSVConnector
    sample_config = ConnectionConfig(url="http://localhost:9999/test.csv")
    sample_schema = SAMPLE_SCHEMA
    sample_request = FetchRequest(dataset_id="test_dataset")

    @pytest.fixture
    def connector_instance(self) -> StaticCSVConnector:
        connector = StaticCSVConnector()

        async def mock_fetch(handle, request):
            state = handle.setdefault_state("static_csv", {})
            state["schema_by_dataset"] = {
                "test_dataset": {
                    "schema_id": "reference.static_csv.test_dataset",
                    "version": "1.0.0",
                    "fields": [
                        {"name": "id", "data_type": "int64", "nullable": False},
                        {"name": "country", "data_type": "string", "nullable": False},
                        {"name": "gdp_usd", "data_type": "int64", "nullable": False},
                        {"name": "year", "data_type": "int64", "nullable": False},
                    ],
                }
            }
            df = pd.read_csv(io.StringIO(SAMPLE_CSV))
            version = DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value="sha256:" + "0" * 64,
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                content_hash="sha256:" + "0" * 64,
            )
            return FetchResult(
                data=df,
                row_count=len(df),
                schema_id="reference.static_csv.test_dataset",
                schema_version="1.0.0",
                version=version,
                fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
                completeness=1.0,
                quality_tier=QualityTier.SILVER,
            )

        async def mock_health_check(handle):
            return HealthStatus(healthy=True, message="mocked")

        connector.fetch = mock_fetch
        connector.health_check = mock_health_check
        return connector


# =============================================================================
# Unit tests
# =============================================================================


class TestCSVParsing:
    def test_parses_standard_csv(self) -> None:
        df = pd.read_csv(io.StringIO(SAMPLE_CSV))
        assert len(df) == 3
        assert list(df.columns) == ["id", "country", "gdp_usd", "year"]

    def test_no_header_csv(self) -> None:
        no_header = "1,US,100\n2,DE,200\n"
        df = pd.read_csv(io.StringIO(no_header), header=None)
        assert list(df.columns) == [0, 1, 2]
        assert len(df) == 2


class TestSchemaInference:
    def test_infer_schema_populates_fields(self) -> None:
        df = pd.read_csv(io.StringIO(SAMPLE_CSV))
        connector = StaticCSVConnector()
        schema = connector._infer_schema(df, "test_dataset")

        assert schema["schema_id"] == "reference.static_csv.test_dataset"
        field_names = [f["name"] for f in schema["fields"]]
        assert "id" in field_names
        assert "country" in field_names
        assert "gdp_usd" in field_names

    @pytest.mark.asyncio
    async def test_cached_schema_returned_on_repeat(self, connector: StaticCSVConnector) -> None:
        df = pd.read_csv(io.StringIO(SAMPLE_CSV))
        handle = await connector.connect(ConnectionConfig(url="http://localhost"))
        state = handle.setdefault_state("static_csv", {})
        state["schema_by_dataset"] = {"ds": connector._infer_schema(df, "ds")}
        result = await connector.get_dataset_schema(handle, "ds")
        assert result == state["schema_by_dataset"]["ds"]

    @pytest.mark.asyncio
    async def test_schema_not_yet_inferred(self, connector: StaticCSVConnector) -> None:
        handle = await connector.connect(ConnectionConfig(url="http://localhost"))
        result = await connector.get_dataset_schema(handle, "ds")
        assert "error" in result


class TestETagVersioning:
    def test_etag_version_strategy(self) -> None:
        connector = StaticCSVConnector()
        version = connector._current_version('W/"abc123"', None, None)
        assert version.strategy == VersionStrategy.ETAG
        assert version.value == 'W/"abc123"'

    def test_last_modified_fallback(self) -> None:
        connector = StaticCSVConnector()
        version = connector._current_version(None, "Mon, 01 Jan 2024 00:00:00 GMT", None)
        assert version.strategy == VersionStrategy.TIMESTAMP
        assert "2024" in version.value


class TestConfigValidation:
    def test_validate_config_missing_url(self) -> None:
        result = StaticCSVConnector.validate_config(ConnectionConfig(url=""))
        assert not result.valid


# =============================================================================
# Integration tests (local aiohttp server)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_static_csv_etag_roundtrip() -> None:
    import aiohttp.web

    etag = 'W/"abc123"'
    last_modified = "Mon, 01 Jan 2024 00:00:00 GMT"
    body_bytes = SAMPLE_CSV.encode("utf-8")

    async def handler(request):
        if request.method == "HEAD":
            return aiohttp.web.Response(
                status=200, headers={"ETag": etag, "Last-Modified": last_modified}
            )
        if request.headers.get("If-None-Match") == etag:
            return aiohttp.web.Response(
                status=304, headers={"ETag": etag, "Last-Modified": last_modified}
            )
        return aiohttp.web.Response(
            status=200, body=body_bytes, headers={"ETag": etag, "Last-Modified": last_modified}
        )

    app = aiohttp.web.Application()
    app.router.add_route("GET", "/data.csv", handler)
    app.router.add_route("HEAD", "/data.csv", handler)

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}/data.csv"

    connector = StaticCSVConnector()
    handle = await connector.connect(ConnectionConfig(url=url))
    request = FetchRequest(dataset_id="integration_dataset")

    first = await connector.fetch(handle, request)
    assert first.row_count == 3
    assert not first.not_modified

    second = await connector.fetch(handle, request)
    assert second.not_modified
    assert second.row_count == 0

    await connector.disconnect(handle)
    await runner.cleanup()
