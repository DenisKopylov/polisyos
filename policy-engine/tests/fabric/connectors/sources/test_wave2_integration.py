"""Wave 2 integration tests for expanded source profiles.

Wave 2 adds:
- ILO, FAO, UN SDMX agencies (all use sdmx.source connector)
- Additional CKAN portals (data.gov.ua, data.gov.ro, EU Open Data)
- Verifies multi-agency SDMX routing and profile diversity
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
# Wave 2 SDMX profiles
# ---------------------------------------------------------------------------


class TestWave2SDMXProfiles:
    """ILO, FAO, UN SDMX profiles resolve correctly."""

    @pytest.mark.parametrize(
        "profile_id,expected_agency",
        [
            ("ilo_sdmx", "ILO"),
            ("fao_sdmx", "FAO"),
            ("unsd_sdmx", "UNSD"),
        ],
    )
    def test_profile_exists(self, profile_id: str, expected_agency: str):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get(profile_id)
        assert profile is not None, f"Profile {profile_id} not found"
        assert profile.connector_family == "sdmx"
        assert expected_agency in str(profile.headers)

    @pytest.mark.parametrize("profile_id", ["ilo_sdmx", "fao_sdmx", "unsd_sdmx"])
    def test_profile_resolves_to_config(self, profile_id: str):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get(profile_id)
        config = resolve_connection_config(profile)
        assert isinstance(config, ConnectionConfig)
        assert config.url.startswith("https://")

    def test_all_sdmx_profiles_count(self):
        """Total SDMX profiles should be 7: ECB, OECD, IMF, BIS + ILO, FAO, UN."""
        reg = SourceProfileRegistry.get_instance()
        sdmx_profiles = reg.list_by_family("sdmx")
        assert len(sdmx_profiles) == 7

    def test_sdmx_connector_shared(self):
        """All SDMX profiles share the single sdmx.source connector."""
        creg = ConnectorRegistry.get_instance()
        assert creg.has("sdmx.source")
        # The default config will be the first alphabetically (bis_sdmx)
        default = creg.get_default_config("sdmx.source")
        assert default is not None


# ---------------------------------------------------------------------------
# Wave 2 CKAN portals
# ---------------------------------------------------------------------------


class TestWave2CKANProfiles:
    """Additional CKAN portals are registered correctly."""

    @pytest.mark.parametrize(
        "profile_id,expected_url_contains",
        [
            ("data_gov_ua", "data.gov.ua"),
            ("data_gov_ro", "data.gov.ro"),
            ("data_gov_md", "dataset.gov.md"),
            ("eu_open_data", "data.europa.eu"),
        ],
    )
    def test_ckan_profile_exists(self, profile_id: str, expected_url_contains: str):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get(profile_id)
        assert profile is not None
        assert profile.connector_family == "ckan"
        assert expected_url_contains in profile.base_url

    def test_total_ckan_profiles(self):
        """6 CKAN profiles: data.gov.uk, data.gov.us, data.gov.ua, data.gov.ro, dataset.gov.md, EU."""
        reg = SourceProfileRegistry.get_instance()
        ckan_profiles = reg.list_by_family("ckan")
        assert len(ckan_profiles) == 6

    @pytest.mark.parametrize("profile_id", ["data_gov_ua", "data_gov_ro", "data_gov_md", "eu_open_data"])
    def test_profile_resolves_to_config(self, profile_id: str):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get(profile_id)
        config = resolve_connection_config(profile)
        assert isinstance(config, ConnectionConfig)
        assert config.url.startswith("https://")


# ---------------------------------------------------------------------------
# Overall profile counts after Wave 2
# ---------------------------------------------------------------------------


class TestWave2ProfileCounts:
    """Profile counts include all waves (Wave 3 profiles also present)."""

    def test_total_profile_count(self):
        reg = SourceProfileRegistry.get_instance()
        assert len(reg.list_all()) >= 21  # at least Wave 1+2, may include Wave 3

    def test_profiles_by_family_distribution(self):
        reg = SourceProfileRegistry.get_instance()
        counts = {}
        for p in reg.list_all():
            counts[p.connector_family] = counts.get(p.connector_family, 0) + 1
        assert counts["sdmx"] == 7
        assert counts["ckan"] == 6
        assert counts["socrata"] == 2
        assert counts["opendatasoft"] == 2
        assert counts["sparql"] == 2
        assert counts["worldbank"] == 1
        assert counts["wvs"] == 1
        assert counts["eurostat"] == 1
        assert counts["ukons"] == 1

    def test_all_connectors_have_at_least_one_profile(self):
        """Each connector family should have at least one profile."""
        preg = SourceProfileRegistry.get_instance()
        creg = ConnectorRegistry.get_instance()
        connector_namespaces = set(creg.list_namespaces())
        profile_families = {p.connector_family for p in preg.list_all()}
        # Every connector namespace should have a profile
        # (ckan has two connectors: catalog + resource, both in "ckan" namespace)
        for ns in connector_namespaces:
            assert ns in profile_families, f"No profile for connector namespace {ns}"
