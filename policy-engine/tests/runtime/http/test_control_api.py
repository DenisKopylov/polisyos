"""Tests for Control Plane API routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.orchestrator import IngestionResult


@pytest.fixture(autouse=True)
def _reset_connector_registry():
    """Reset ConnectorRegistry singleton before each test to avoid bootstrap hang."""
    ConnectorRegistry.reset_instance()
    # Create instance without bootstrap (no component discovery)
    ConnectorRegistry.get_instance(bootstrap=False)
    yield
    ConnectorRegistry.reset_instance()


class TestLaunchRun:
    def test_launch_workflow_run_accepted(self, runtime_api_env):
        client = runtime_api_env["client"]
        # Use an existing artifact from the fixture as data_snapshot_ref
        artifact_id = runtime_api_env["root_artifact_id"]
        resp = client.post(
            "/api/v1/control/runs",
            json={
                "mode": "workflow",
                "data_source": {"data_snapshot_ref": artifact_id},
                "checkpoint_policy": "strict",
                "params": {"seed": 42},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["run_id"].startswith("R_")
        assert "meta" in body
        assert body["meta"]["request_id"]

    def test_launch_run_with_trinity_bundle(self, runtime_api_env):
        client = runtime_api_env["client"]
        artifact_id = runtime_api_env["root_artifact_id"]
        resp = client.post(
            "/api/v1/control/runs",
            json={
                "data_source": {"input_bindings_ref": artifact_id},
                "trinity_bundle_ref": artifact_id,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_launch_run_missing_data_source_returns_400(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs",
            json={
                "data_source": {},
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "missing_data_source"

    def test_launch_run_invalid_body_returns_422(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs",
            json={"invalid_field": "value"},
        )
        assert resp.status_code == 422


class TestLaunchNlRun:
    def test_launch_nl_run_accepted(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Analyze minimum wage impact on small businesses",
                "domain_hint": "fiscal",
                "max_iterations": 2,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["run_id"].startswith("R_")
        assert "mock agents" in body["message"]

    def test_launch_nl_run_with_llm_model(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Study healthcare policy effects",
                "llm_model": "claude-sonnet-4-5-20250929",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert "claude-sonnet" in body["message"]

    def test_launch_nl_run_with_llm_models(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Compare multiple model variants on the same task",
                "llm_models": ["gpt-5-mini", "claude-sonnet-4-5-20250929"],
                "max_parallel_models": 2,
                "run_budget_usd": 2.0,
                "per_model_budget_usd": 1.0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert "model variants" in body["message"]

    def test_launch_nl_run_invalid_parallel_models_returns_422(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Invalid max_parallel_models value",
                "llm_models": ["gpt-5-mini", "claude-sonnet-4-5-20250929"],
                "max_parallel_models": 0,
            },
        )
        assert resp.status_code == 422

    def test_launch_nl_run_empty_request_returns_422(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={"request": ""},
        )
        assert resp.status_code == 422


class TestDataIngestion:
    def test_ingest_data_accepted(self, runtime_api_env):
        client = runtime_api_env["client"]
        mock_result = IngestionResult(datasets_fetched=1)
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
                            "filters": {"country": ["USA"]},
                        }
                    ],
                    "source": "test",
                    "license_name": "open",
                },
            )
        assert resp.status_code == 200

    def test_ingest_data_empty_datasets_returns_422(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/data/ingest",
            json={"datasets": []},
        )
        assert resp.status_code == 422


class TestConnectorsList:
    def test_list_connectors_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/connectors")
        assert resp.status_code == 200
        body = resp.json()
        assert "connectors" in body
        assert isinstance(body["connectors"], list)
        assert "meta" in body


class TestConnectorsAvailableProfiles:
    def test_connectors_include_available_profiles(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/connectors")
        assert resp.status_code == 200
        body = resp.json()
        for c in body["connectors"]:
            assert "available_profiles" in c
            assert isinstance(c["available_profiles"], list)


class TestSourceProfiles:
    def test_list_profiles_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert "profiles" in body
        assert isinstance(body["profiles"], list)
        assert "meta" in body

    def test_list_profiles_has_builtin(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        body = resp.json()
        profile_ids = [p["profile_id"] for p in body["profiles"]]
        assert "worldbank_wdi" in profile_ids
        assert "ecb_sdmx" in profile_ids

    def test_profile_has_expected_fields(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        body = resp.json()
        for p in body["profiles"]:
            assert "profile_id" in p
            assert "display_name" in p
            assert "connector_family" in p
            assert "base_url" in p
            assert "connector_available" in p

    def test_ingest_with_connection_profile(self, runtime_api_env):
        client = runtime_api_env["client"]
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
                    "produce_data_snapshot": True,
                },
            )
        assert resp.status_code == 200

    def test_ingest_response_has_new_fields(self, runtime_api_env):
        client = runtime_api_env["client"]
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
                },
            )
        body = resp.json()
        # New fields should be present regardless of success/failure
        assert "data_snapshot_ref" in body
        assert "warnings" in body


class TestLlmProfiles:
    def test_list_llm_profiles_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/llm/profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert "profiles" in body
        assert isinstance(body["profiles"], list)
        assert "meta" in body

    def test_list_llm_profiles_has_builtin(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/llm/profiles")
        body = resp.json()
        profile_ids = [p["profile_id"] for p in body["profiles"]]
        assert "gpt5_mini_gateway" in profile_ids


class TestCacheStatus:
    def test_cache_status_returns_empty(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/cache")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_entries"] == 0
        assert "entries" in body
        assert "meta" in body


class TestBindingProfiles:
    def test_list_binding_profiles_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/binding-profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert "profiles" in body
        assert isinstance(body["profiles"], list)
        assert "meta" in body

    def test_list_binding_profiles_has_builtins(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/binding-profiles")
        body = resp.json()
        profile_ids = [p["profile_id"] for p in body["profiles"]]
        assert "ts_single_indicator" in profile_ids
        assert "ts_multi_indicator" in profile_ids
        assert "ts_exchange_rate" in profile_ids

    def test_binding_profile_has_expected_fields(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/binding-profiles")
        body = resp.json()
        for p in body["profiles"]:
            assert "profile_id" in p
            assert "display_name" in p
            assert "schema_family" in p
            assert "rule_count" in p
            assert isinstance(p["rule_count"], int)
            assert p["rule_count"] >= 0


class TestIngestStreamingWindowed:
    def test_ingest_streaming_windowed(self, runtime_api_env):
        client = runtime_api_env["client"]
        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset",
            return_value=[
                {
                    "chunk_index": 0,
                    "row_count": 1,
                    "is_first": True,
                    "is_last": True,
                    "data": [{"x": 1}],
                }
            ],
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                json={
                    "datasets": [
                        {
                            "connector_id": "test.conn",
                            "dataset_id": "ds1",
                        }
                    ],
                    "execution_mode": "streaming_windowed",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode_effective"] == "streaming_windowed"


class TestIngestRecordReplay:
    def test_ingest_record_mode(self, runtime_api_env):
        client = runtime_api_env["client"]
        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                json={
                    "datasets": [
                        {
                            "connector_id": "test.conn",
                            "dataset_id": "ds1",
                        }
                    ],
                    "record_mode": True,
                },
            )
        assert resp.status_code == 200

    def test_ingest_response_has_record_and_binding_fields(self, runtime_api_env):
        client = runtime_api_env["client"]
        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                json={
                    "datasets": [
                        {
                            "connector_id": "test.conn",
                            "dataset_id": "ds1",
                        }
                    ],
                },
            )
        body = resp.json()
        # New Phase 4+5 fields should be present in the response
        assert "record_ref" in body
        assert "input_bindings_ref" in body
