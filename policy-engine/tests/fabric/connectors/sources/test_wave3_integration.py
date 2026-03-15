"""Wave 3 integration tests for REST connector and profiles.

Wave 3 adds:
- RestJsonConnector (rest.json) promoted from reference to production
- 6 REST profiles including Poland open data catalog plus specialized APIs
- Verifies full profile count across all waves
"""
from __future__ import annotations

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
from polisyos.fabric.connectors.registry import ConnectorRegistry


@pytest.fixture(autouse=True)
def _reset_registries():
    ConnectorRegistry.reset_instance()
    SourceProfileRegistry.reset_instance()
    yield
    ConnectorRegistry.reset_instance()
    SourceProfileRegistry.reset_instance()


# ---------------------------------------------------------------------------
# REST connector
# ---------------------------------------------------------------------------


class TestRestJsonConnector:
    def test_connector_registered(self):
        reg = ConnectorRegistry.get_instance()
        assert reg.has("rest.json")

    def test_connector_has_default_config(self):
        reg = ConnectorRegistry.get_instance()
        config = reg.get_default_config("rest.json")
        assert config is not None
        assert isinstance(config, ConnectionConfig)

    def test_connector_capabilities(self):
        from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector
        from polisyos.ir.connectors import ConnectorCapability

        caps = RestJsonConnector.capabilities
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.DATE_RANGE_FILTER
        assert caps & ConnectorCapability.INCREMENTAL_FETCH
        assert caps & ConnectorCapability.RATE_LIMIT_AWARE

    def test_connector_metadata(self):
        from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector

        assert RestJsonConnector.connector_id == "rest.json"
        assert RestJsonConnector.namespace == "rest"
        assert RestJsonConnector.short_id == "json"


# ---------------------------------------------------------------------------
# Wave 3 REST profiles
# ---------------------------------------------------------------------------


class TestWave3RESTProfiles:
    @pytest.mark.parametrize(
        "profile_id,expected_url_contains",
        [
            ("data_gov_pl", "api.dane.gov.pl"),
            ("usgs_earthquake", "earthquake.usgs.gov"),
            ("openaq_v2", "api.openaq.org"),
            ("open_meteo", "api.open-meteo.com"),
            ("eia_api", "api.eia.gov"),
            ("nvd_cve", "nvd.nist.gov"),
        ],
    )
    def test_rest_profile_exists(self, profile_id: str, expected_url_contains: str):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get(profile_id)
        assert profile is not None, f"Profile {profile_id} not found"
        assert profile.connector_family == "rest"
        assert expected_url_contains in profile.base_url

    @pytest.mark.parametrize(
        "profile_id",
        ["data_gov_pl", "usgs_earthquake", "openaq_v2", "open_meteo", "eia_api", "nvd_cve"],
    )
    def test_rest_profile_resolves(self, profile_id: str):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get(profile_id)
        config = resolve_connection_config(profile)
        assert isinstance(config, ConnectionConfig)
        assert config.url.startswith("https://")

    def test_rest_profiles_have_data_path_header(self):
        reg = SourceProfileRegistry.get_instance()
        for pid in ("usgs_earthquake", "openaq_v2", "open_meteo", "eia_api", "nvd_cve"):
            profile = reg.get(pid)
            assert "X-REST-DataPath" in dict(profile.headers), (
                f"Profile {pid} missing X-REST-DataPath header"
            )

    def test_total_rest_profiles(self):
        reg = SourceProfileRegistry.get_instance()
        rest_profiles = reg.list_by_family("rest")
        assert len(rest_profiles) == 6


# ---------------------------------------------------------------------------
# All-waves summary
# ---------------------------------------------------------------------------


class TestAllWavesSummary:
    def test_total_connectors(self):
        reg = ConnectorRegistry.get_instance()
        assert len(reg) == 14

    def test_total_profiles(self):
        reg = SourceProfileRegistry.get_instance()
        assert len(reg.list_all()) == 32

    def test_all_connectors_have_default_configs(self):
        reg = ConnectorRegistry.get_instance()
        for fqid in reg:
            entry = reg.get_entry(fqid.split("@")[0])
            assert entry.default_config is not None, (
                f"Connector {fqid} missing default config"
            )

    def test_connector_family_profile_coverage(self):
        """Every connector namespace has at least one source profile."""
        preg = SourceProfileRegistry.get_instance()
        creg = ConnectorRegistry.get_instance()
        families_with_profiles = {p.connector_family for p in preg.list_all()}
        for ns in creg.list_namespaces():
            assert ns in families_with_profiles, (
                f"Connector namespace {ns!r} has no source profile"
            )

    def test_component_system_count(self):
        from polisyos.fabric.connectors.components import __polisyos_components__

        assert len(__polisyos_components__) == 14
