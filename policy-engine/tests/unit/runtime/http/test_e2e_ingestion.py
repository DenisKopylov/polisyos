"""E2E ingestion API tests verifying full connector registry bootstrap.

Unlike test_control_api.py which uses bootstrap=False, these tests verify
that the real ConnectorRegistry bootstrap works end-to-end: all 9 connectors
are discovered, default configs are wired from profiles, and the control
plane API exposes them correctly.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from polisyos.core.security.identity import PolicyOSRole
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.registry import ConnectorRegistry
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


@pytest.fixture(autouse=True)
def _bootstrap_real_registry():
    """Use the real bootstrapped registry (all 9 connectors + default configs)."""
    ConnectorRegistry.reset_instance()
    SourceProfileRegistry.reset_instance()
    yield
    ConnectorRegistry.reset_instance()
    SourceProfileRegistry.reset_instance()


@pytest.fixture
def secured_ingestion_request(runtime_api_env, request: pytest.FixtureRequest):
    """Provide genuine analyst authorization and one fresh bound step-up."""
    bearer = _fixture_bearer(f"e2e-ingestion-{request.node.name}")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-e2e-ingestion-{request.node.name}",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    with client:
        step_up = f"{_install_bound_test_step_up(client)}-{bearer}"
        yield client, {
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": step_up,
        }


# ---------------------------------------------------------------------------
# Connectors API: all connectors visible
# ---------------------------------------------------------------------------


class TestE2EConnectorsList:
    def test_lists_all_9_connectors(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/connectors")
        assert resp.status_code == 200
        body = resp.json()
        # Connector IDs may include version suffix (e.g. "worldbank.wdi@1.0.0")
        connector_ids = {c["connector_id"].split("@")[0] for c in body["connectors"]}
        expected = {
            "worldbank.wdi",
            "eurostat.data",
            "ukons.datasets",
            "sdmx.source",
            "ckan.catalog",
            "ckan.resource",
            "socrata.soda",
            "opendatasoft.ods",
            "sparql.endpoint",
        }
        assert expected.issubset(connector_ids), f"Missing connectors: {expected - connector_ids}"

    def test_each_connector_has_default_config(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/connectors")
        body = resp.json()
        for c in body["connectors"]:
            cid = c["connector_id"]
            assert c.get("has_default_config") or c.get("available_profiles"), (
                f"{cid} has no default config or profiles"
            )

    def test_connectors_have_available_profiles(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/connectors")
        body = resp.json()
        connectors_with_profiles = [
            c
            for c in body["connectors"]
            if c.get("available_profiles") and len(c["available_profiles"]) > 0
        ]
        # At least the Wave-1 connectors should have profiles
        assert len(connectors_with_profiles) >= 5


# ---------------------------------------------------------------------------
# Source profiles API: all profiles visible
# ---------------------------------------------------------------------------


class TestE2ESourceProfiles:
    def test_lists_all_15_profiles(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["profiles"]) >= 15

    def test_wave1_profiles_present(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        body = resp.json()
        ids = {p["profile_id"] for p in body["profiles"]}
        wave1 = {"worldbank_wdi", "eurostat_public", "ukons_public", "ecb_sdmx", "oecd_sdmx"}
        assert wave1.issubset(ids), f"Missing Wave-1 profiles: {wave1 - ids}"

    def test_wave2_profiles_present(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        body = resp.json()
        ids = {p["profile_id"] for p in body["profiles"]}
        wave2 = {"imf_sdmx", "bis_sdmx", "data_gov_uk", "data_gov_us"}
        assert wave2.issubset(ids), f"Missing Wave-2 profiles: {wave2 - ids}"

    def test_profile_connector_available_flag(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        body = resp.json()
        for p in body["profiles"]:
            assert "connector_available" in p
            # All profiles should have their connectors available now
            assert p["connector_available"] is True, (
                f"Profile {p['profile_id']} connector not available"
            )


# ---------------------------------------------------------------------------
# Ingestion API: dispatch with connection_profile
# ---------------------------------------------------------------------------


class TestE2EIngestionDispatch:
    def test_ingest_with_worldbank_profile(self, secured_ingestion_request):
        client, headers = secured_ingestion_request
        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                json={
                    "datasets": [
                        {
                            "connector_id": "worldbank.wdi",
                            "dataset_id": "NY.GDP.MKTP.CD",
                        }
                    ],
                    "connection_profile": "worldbank_wdi",
                    "source": "test",
                    "license_name": "open",
                },
                headers=headers,
            )
        assert resp.status_code == 200

    def test_ingest_with_sdmx_ecb_profile(self, secured_ingestion_request):
        client, headers = secured_ingestion_request
        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                json={
                    "datasets": [
                        {
                            "connector_id": "sdmx.source",
                            "dataset_id": "EXR",
                        }
                    ],
                    "connection_profile": "ecb_sdmx",
                    "source": "test",
                    "license_name": "open",
                },
                headers=headers,
            )
        assert resp.status_code == 200

    def test_ingest_without_profile_uses_default_config(self, secured_ingestion_request):
        """When no connection_profile is specified, the connector should use
        its default_config (wired from source profiles during bootstrap)."""
        client, headers = secured_ingestion_request
        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                json={
                    "datasets": [
                        {
                            "connector_id": "eurostat.data",
                            "dataset_id": "nama_10_gdp",
                        }
                    ],
                    "source": "test",
                    "license_name": "open",
                },
                headers=headers,
            )
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        ("connector_id", "dataset_id", "profile_id"),
        [
            ("worldbank.wdi", "SP.POP.TOTL", "worldbank_wdi"),
            ("eurostat.data", "nama_10_gdp", "eurostat_public"),
            ("ukons.datasets", "cpih01", "ukons_public"),
            ("sdmx.source", "EXR", "ecb_sdmx"),
            ("ckan.catalog", "gdp", "data_gov_uk"),
            ("socrata.soda", "erm2-nwe9", "nyc_opendata"),
        ],
    )
    def test_ingest_all_wave1_connectors(
        self, secured_ingestion_request, connector_id, dataset_id, profile_id
    ):
        client, headers = secured_ingestion_request
        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                json={
                    "datasets": [
                        {
                            "connector_id": connector_id,
                            "dataset_id": dataset_id,
                        }
                    ],
                    "connection_profile": profile_id,
                    "source": "test",
                    "license_name": "open",
                },
                headers=headers,
            )
        assert resp.status_code == 200, (
            f"Ingestion failed for {connector_id} with profile {profile_id}: "
            f"{resp.status_code} {resp.text}"
        )
