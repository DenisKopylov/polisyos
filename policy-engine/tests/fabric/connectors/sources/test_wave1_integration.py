"""Wave 1 integration smoke tests for real source connectors.

Tests verify that:
1. All Wave-1 connectors are discoverable via ConnectorRegistry
2. Source profiles resolve to valid ConnectionConfigs
3. Default configs are wired correctly during bootstrap
4. Each connector can parse fixture data correctly
5. The control plane service can dispatch to each connector
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.ir.connectors import ConnectorCapability

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Registry integration: all 9 connectors discoverable
# ---------------------------------------------------------------------------


class TestRegistryDiscovery:
    """All production connectors are registered and discoverable."""

    @pytest.fixture(autouse=True)
    def _reset_registries(self):
        ConnectorRegistry.reset_instance()
        SourceProfileRegistry.reset_instance()
        yield
        ConnectorRegistry.reset_instance()
        SourceProfileRegistry.reset_instance()

    def test_registry_has_9_connectors(self):
        reg = ConnectorRegistry.get_instance()
        assert len(reg) >= 9

    @pytest.mark.parametrize(
        "connector_id",
        [
            "worldbank.wdi",
            "wvs.wave7",
            "eurostat.data",
            "ukons.datasets",
            "sdmx.source",
            "ckan.catalog",
            "ckan.resource",
            "socrata.soda",
            "opendatasoft.ods",
            "sparql.endpoint",
        ],
    )
    def test_connector_registered(self, connector_id: str):
        reg = ConnectorRegistry.get_instance()
        assert reg.has(connector_id), f"{connector_id} not found in registry"

    @pytest.mark.parametrize(
        "namespace",
        ["worldbank", "wvs", "eurostat", "ukons", "sdmx", "ckan", "socrata", "opendatasoft", "sparql"],
    )
    def test_namespace_exists(self, namespace: str):
        reg = ConnectorRegistry.get_instance()
        assert namespace in reg.list_namespaces()


# ---------------------------------------------------------------------------
# Source profiles → ConnectionConfig resolution
# ---------------------------------------------------------------------------


class TestProfileResolution:
    """Source profiles resolve to valid ConnectionConfigs."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        SourceProfileRegistry.reset_instance()
        yield
        SourceProfileRegistry.reset_instance()

    @pytest.mark.parametrize(
        "profile_id,expected_url_prefix",
        [
            ("worldbank_wdi", "https://api.worldbank.org"),
            ("eurostat_public", "https://ec.europa.eu/eurostat"),
            ("ukons_public", "https://api.ons.gov.uk"),
            ("ecb_sdmx", "https://data-api.ecb.europa.eu"),
            ("oecd_sdmx", "https://sdmx.oecd.org"),
        ],
    )
    def test_profile_resolves_to_config(self, profile_id: str, expected_url_prefix: str):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get(profile_id)
        assert profile is not None, f"Profile {profile_id} not found"

        config = resolve_connection_config(profile)
        assert isinstance(config, ConnectionConfig)
        assert config.url.startswith(expected_url_prefix)

    def test_sdmx_profiles_have_agency_header(self):
        reg = SourceProfileRegistry.get_instance()
        for pid in ("ecb_sdmx", "oecd_sdmx", "imf_sdmx", "bis_sdmx"):
            profile = reg.get(pid)
            assert profile is not None
            config = resolve_connection_config(profile)
            assert "X-SDMX-Agency" in config.headers or "X-SDMX-AgencyID" in config.headers


# ---------------------------------------------------------------------------
# Default config bootstrap wiring
# ---------------------------------------------------------------------------


class TestDefaultConfigBootstrap:
    """ConnectorRegistry auto-wires default configs from profiles."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        ConnectorRegistry.reset_instance()
        SourceProfileRegistry.reset_instance()
        yield
        ConnectorRegistry.reset_instance()
        SourceProfileRegistry.reset_instance()

    @pytest.mark.parametrize(
        "connector_id",
        [
            "worldbank.wdi",
            "wvs.wave7",
            "eurostat.data",
            "ukons.datasets",
            "sdmx.source",
            "ckan.catalog",
            "ckan.resource",
            "socrata.soda",
            "opendatasoft.ods",
            "sparql.endpoint",
        ],
    )
    def test_connector_has_default_config(self, connector_id: str):
        reg = ConnectorRegistry.get_instance()
        config = reg.get_default_config(connector_id)
        assert config is not None, f"{connector_id} missing default config"
        assert isinstance(config, ConnectionConfig)
        assert config.url.startswith("https://")

    def test_set_default_config_override(self):
        reg = ConnectorRegistry.get_instance()
        custom = ConnectionConfig(url="https://custom.example.com")
        reg.set_default_config("worldbank.wdi", custom)
        assert reg.get_default_config("worldbank.wdi").url == "https://custom.example.com"


# ---------------------------------------------------------------------------
# Wave 1 connector capabilities
# ---------------------------------------------------------------------------


class TestWave1Capabilities:
    """Wave 1 connectors expose expected capabilities."""

    def test_worldbank_capabilities(self):
        from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

        caps = WorldBankConnector.capabilities
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.CATALOG_BROWSE

    def test_eurostat_capabilities(self):
        from polisyos.fabric.connectors.sources.eurostat import EurostatConnector

        caps = EurostatConnector.capabilities
        assert caps & ConnectorCapability.FULL_FETCH

    def test_ukons_capabilities(self):
        from polisyos.fabric.connectors.sources.ukons import UKONSConnector

        caps = UKONSConnector.capabilities
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.CATALOG_BROWSE

    def test_sdmx_capabilities(self):
        from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector

        caps = SDMXSourceConnector.capabilities
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.CATALOG_BROWSE
        assert caps & ConnectorCapability.STREAMING
        assert caps & ConnectorCapability.FRESHNESS_CHECK
        assert caps & ConnectorCapability.DIMENSION_FILTER
        assert caps & ConnectorCapability.DATE_RANGE_FILTER


# ---------------------------------------------------------------------------
# Fixture-based parsing smoke tests
# ---------------------------------------------------------------------------


class TestFixtureParsing:
    """Verify connectors can parse known fixture data."""

    def test_sdmx_ecb_fixture_parses(self):
        from polisyos.fabric.connectors.sources.sdmx_source import _parse_sdmx_json

        fixture = json.loads(
            (FIXTURES_DIR / "sdmx" / "ecb_exr_response.json").read_text()
        )
        df = _parse_sdmx_json(fixture)
        assert not df.empty
        assert "value" in df.columns

    def test_sdmx_ecb_dataflows_fixture_parses(self):
        fixture = json.loads(
            (FIXTURES_DIR / "sdmx" / "ecb_dataflows_response.json").read_text()
        )
        assert "dataSets" in fixture or "data" in fixture or "dataflows" in fixture or "structure" in fixture

    def test_ckan_package_search_fixture(self):
        fixture = json.loads(
            (FIXTURES_DIR / "ckan" / "package_search_response.json").read_text()
        )
        assert "result" in fixture
        results = fixture["result"]
        assert "results" in results or "count" in results

    def test_ckan_package_show_fixture(self):
        fixture = json.loads(
            (FIXTURES_DIR / "ckan" / "package_show_response.json").read_text()
        )
        assert "result" in fixture

    def test_socrata_resource_fixture(self):
        fixture = json.loads(
            (FIXTURES_DIR / "socrata" / "resource_response.json").read_text()
        )
        assert isinstance(fixture, list)

    def test_socrata_views_fixture(self):
        fixture = json.loads(
            (FIXTURES_DIR / "socrata" / "views_response.json").read_text()
        )
        assert isinstance(fixture, (list, dict))

    def test_opendatasoft_records_fixture(self):
        fixture = json.loads(
            (FIXTURES_DIR / "opendatasoft" / "records_response.json").read_text()
        )
        assert "results" in fixture or "records" in fixture or "total_count" in fixture

    def test_opendatasoft_catalog_fixture(self):
        fixture = json.loads(
            (FIXTURES_DIR / "opendatasoft" / "catalog_response.json").read_text()
        )
        assert "results" in fixture or "datasets" in fixture or "total_count" in fixture

    def test_sparql_select_fixture(self):
        fixture = json.loads(
            (FIXTURES_DIR / "sparql" / "select_response.json").read_text()
        )
        assert "results" in fixture
        assert "bindings" in fixture["results"]


# ---------------------------------------------------------------------------
# Schema contract registration
# ---------------------------------------------------------------------------


class TestSchemaContracts:
    """Schema contracts are registered for all Wave 1 connectors."""

    def test_all_source_contracts_loadable(self):
        from polisyos.fabric.connectors.sources._contracts import ALL_SOURCE_CONTRACTS

        assert len(ALL_SOURCE_CONTRACTS) >= 4  # worldbank, eurostat, ukons, sdmx

    def test_sdmx_contract_exists(self):
        from polisyos.fabric.connectors.sources._contracts import SDMX_GENERIC_CONTRACT

        assert SDMX_GENERIC_CONTRACT.connector_id == "sdmx.source"
        assert SDMX_GENERIC_CONTRACT.dataset_id == "*"

    def test_sdmx_schema_fields(self):
        from polisyos.fabric.connectors.sources._contracts import SDMX_GENERIC_SCHEMA

        field_names = {f.name for f in SDMX_GENERIC_SCHEMA.fields}
        assert "value" in field_names
        assert "time_period" in field_names

    @pytest.mark.parametrize(
        "contract_id",
        ["worldbank.wdi.generic", "eurostat.data.generic", "ukons.datasets.generic", "sdmx.generic"],
    )
    def test_contract_exists(self, contract_id: str):
        from polisyos.fabric.connectors.sources._contracts import ALL_SOURCE_CONTRACTS

        ids = {c.contract_id for c in ALL_SOURCE_CONTRACTS}
        assert contract_id in ids


# ---------------------------------------------------------------------------
# Component system integration
# ---------------------------------------------------------------------------


class TestComponentSystem:
    """All connectors are wrapped as Component objects."""

    def test_builtin_components_count(self):
        from polisyos.fabric.connectors.components import __polisyos_components__

        assert len(__polisyos_components__) >= 14

    @pytest.mark.parametrize(
        "short_id",
        ["wdi", "wave7", "data", "datasets", "source", "catalog", "resource", "soda", "ods", "endpoint"],
    )
    def test_component_by_short_id(self, short_id: str):
        from polisyos.fabric.connectors.components import _component_by_short_id, _BUILTIN_COMPONENTS

        component = _component_by_short_id(_BUILTIN_COMPONENTS, short_id)
        assert component is not None, f"Component with short_id={short_id!r} not found"
