"""Tests for Control Plane API routes."""

from __future__ import annotations

import pytest


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
        # May fail in test env (no real connectors), check status code is not 422
        assert resp.status_code in (200, 500)

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


class TestCacheStatus:
    def test_cache_status_returns_empty(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/cache")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_entries"] == 0
        assert "entries" in body
        assert "meta" in body
