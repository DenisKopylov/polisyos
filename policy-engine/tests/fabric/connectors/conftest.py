"""
pytest fixtures for connector tests (Phase 2.10+).

This conftest is placed at tests/fabric/connectors/ so every test
module beneath that directory inherits these fixtures automatically.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    FetchRequest,
    FetchResult,
)
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    GeoGranularity,
    SchemaType,
    SchemaVersion,
    SemanticType,
    TimeGranularity,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.testing.simulator import APISimulator, SimulatorMode
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy

# ---------------------------------------------------------------------------
# CLI option: --record-mode
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the --record-mode flag for APISimulator."""
    parser.addoption(
        "--record-mode",
        action="store_true",
        default=False,
        help="Switch APISimulator to RECORD mode (allows live network access).",
    )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def connectors_root() -> Path:
    """Absolute path to tests/fabric/connectors/."""
    return Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def fixtures_root(connectors_root: Path) -> Path:
    """Absolute path to tests/fabric/connectors/fixtures/."""
    root = connectors_root / "fixtures"
    root.mkdir(exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# Registry isolation
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry() -> ConnectorRegistry:
    """
    Provide a fresh, isolated ConnectorRegistry for each test.

    We reset the singleton so that registrations in one test cannot
    leak into another. After the test, we reset again to leave the
    global state clean.
    """
    ConnectorRegistry.reset()
    registry = ConnectorRegistry.get_instance()
    yield registry
    ConnectorRegistry.reset()


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """
    Session-scoped event loop for pytest-asyncio.

    A single loop for the entire test session avoids the overhead of
    creating and tearing down loops per test while still being safe.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Sample data objects
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_connection_config() -> ConnectionConfig:
    """
    Minimal ConnectionConfig for unit tests.

    Points to localhost so nothing escapes to the network by accident.
    """
    return ConnectionConfig(
        url="http://localhost:8899/api/v1",
        headers={"Accept": "application/json"},
        timeout_seconds=5,
        max_retries=2,
        retry_delay_seconds=0.01,  # Fast retries in tests
    )


@pytest.fixture
def sample_fetch_request() -> FetchRequest:
    """A generic FetchRequest for harness-level tests."""
    return FetchRequest(
        dataset_id="test.sample.dataset",
        date_start=datetime(2020, 1, 1, tzinfo=UTC),
        date_end=datetime(2024, 12, 31, tzinfo=UTC),
    )


@pytest.fixture
def sample_schema() -> DataSchema:
    """
    Realistic 6-field schema matching the GDP-style pattern used
    throughout the connector test suite.
    """
    return DataSchema(
        schema_id="test.sample.economic_data",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(
                name="id",
                data_type=SchemaType.INT64,
                nullable=False,
                semantic_type=SemanticType.IDENTIFIER,
            ),
            FieldSpec(
                name="country_code",
                data_type=SchemaType.STRING,
                nullable=False,
                semantic_type=SemanticType.GEOSPATIAL,
                max_length=3,
            ),
            FieldSpec(
                name="year",
                data_type=SchemaType.INT32,
                nullable=False,
                semantic_type=SemanticType.TEMPORAL,
                bounds=(2000.0, 2030.0),
            ),
            FieldSpec(
                name="gdp_usd",
                data_type=SchemaType.FLOAT64,
                nullable=True,
                unit="usd",
                semantic_type=SemanticType.CURRENCY,
                bounds=(0.0, 1e13),
            ),
            FieldSpec(
                name="unemployment_rate",
                data_type=SchemaType.FLOAT64,
                nullable=True,
                unit="ratio",
                semantic_type=SemanticType.RATIO,
                bounds=(0.0, 1.0),
            ),
            FieldSpec(
                name="region",
                data_type=SchemaType.CATEGORY,
                nullable=False,
                allowed_values=frozenset({"NA", "EU", "APAC", "LATAM", "AF", "ME"}),
            ),
        ),
        primary_key=("id",),
        time_dimension="year",
        time_granularity=TimeGranularity.ANNUAL,
        geo_dimension="country_code",
        geo_granularity=GeoGranularity.COUNTRY,
        required_completeness=0.90,
        allowed_null_fields=frozenset({"gdp_usd", "unemployment_rate"}),
    )


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """
    A hand-crafted DataFrame that conforms to sample_schema.

    5 rows covering the happy path. Used by contract-verification
    tests that don't need a live connector.
    """
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "country_code": ["US", "DE", "JP", "BR", "NG"],
            "year": [2022, 2022, 2023, 2023, 2024],
            "gdp_usd": [25_462.7e9, 4_072.2e9, 4_231.0e9, 1_920.5e9, 366.3e9],
            "unemployment_rate": [0.037, 0.052, 0.025, 0.093, 0.047],
            "region": ["NA", "EU", "APAC", "LATAM", "AF"],
        }
    )


@pytest.fixture
def sample_fetch_result(sample_dataframe: pd.DataFrame) -> FetchResult:
    """
    A FetchResult pre-populated with sample_dataframe.

    Useful for tests that need to exercise downstream processing
    (contract checks, caching, quality gates) without running a
    connector.
    """
    now = datetime.now(UTC)
    return FetchResult(
        data=sample_dataframe,
        row_count=len(sample_dataframe),
        schema_id="test.sample.economic_data",
        schema_version="1.0.0",
        version=DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value=now.isoformat(),
            timestamp=now,
        ),
        fetched_at=now,
        completeness=1.0,
        quality_tier=QualityTier.SILVER,
    )


# ---------------------------------------------------------------------------
# APISimulator fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def api_simulator(request: pytest.FixtureRequest, fixtures_root: Path) -> APISimulator:
    """
    An APISimulator configured based on CLI flags.

    Default mode is REPLAY (CI-safe). Pass --record-mode to switch
    to RECORD.
    """
    record_mode = request.config.getoption("--record-mode", default=False)
    mode = SimulatorMode.RECORD if record_mode else SimulatorMode.REPLAY

    return APISimulator(
        mode=mode,
        fixture_root=fixtures_root,
        dataset_id="default",
    )
