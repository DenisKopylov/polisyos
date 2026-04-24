"""Tests for Control Plane API routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.decision_validity import (
    DecisionTriggerRecord,
    DecisionTriggerType,
    DecisionValidityStatus,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.scientist.decision_validity import DecisionValidityService


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
        assert body["job_id"]
        assert body["effective_execution_profile"] == "dev"
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
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["job_id"]

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


class TestCapabilities:
    def test_get_control_capabilities_returns_manifest(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["shell_flavor"] == "atlas"
        assert body["default_locale"] == "en"
        assert body["default_execution_profile"] == "dev"
        assert body["worker_backend"] == "embedded"
        assert body["state_store_backend"] == "sqlite"
        assert "features" in body
        assert isinstance(body["features"], list)
        feature_keys = {item["key"] for item in body["features"]}
        assert "natural_language_runs" in feature_keys
        assert "required_preflight" in feature_keys
        assert "security_admin_layer" in feature_keys
        assert "durable_control_plane" in feature_keys
        assert "control_plane_local_waiver" in feature_keys
        assert body["constraints"]["max_parallel_models"] == 16
        assert body["constraints"]["durable_control_profiles"] == [
            "research",
            "governed",
            "production",
        ]

    def test_get_control_workers_returns_worker_leases(self, runtime_api_env):
        client = runtime_api_env["client"]
        response = client.get("/api/v1/control/workers")
        assert response.status_code == 200
        body = response.json()
        assert body["active_only"] is True
        assert len(body["workers"]) >= 1
        assert body["workers"][0]["worker_id"]
        assert body["workers"][0]["state"] in {"idle", "running", "stopped"}

    def test_get_control_outbox_returns_events(self, runtime_api_env):
        service = runtime_api_env["app"].state._control_service
        record = service._control_store.enqueue_outbox_event(
            topic="control.fixture",
            event_key="fixture-event",
            payload={"fixture": True},
        )

        client = runtime_api_env["client"]
        response = client.get("/api/v1/control/outbox?state=pending&limit=10")
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "pending"
        assert body["limit"] == 10
        assert any(item["event_id"] == record.event_id for item in body["events"])

    def test_get_control_job_status_returns_record(self, runtime_api_env):
        client = runtime_api_env["client"]
        launch = client.post(
            "/api/v1/control/runs",
            json={
                "mode": "workflow",
                "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            },
        )
        assert launch.status_code == 200
        job_id = launch.json()["job_id"]
        status = client.get(f"/api/v1/control/jobs/{job_id}")
        assert status.status_code == 200
        body = status.json()
        assert body["job_id"] == job_id
        assert body["kind"] == "workflow_run"
        assert body["effective_execution_profile"] == "dev"


class TestDecisionValidity:
    def test_get_run_decision_validity_returns_lifecycle_summary(self, runtime_api_env):
        client = runtime_api_env["client"]
        response = client.get(
            f"/api/v1/control/runs/{runtime_api_env['core_run_id']}/decision-validity"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == runtime_api_env["core_run_id"]
        assert (
            body["decision_packet_ref"]["artifact_id"]
            == runtime_api_env["decision_packet_artifact_id"]
        )
        assert body["status"] == "warning"
        assert body["decision_lineage_key"] == runtime_api_env["decision_packet_artifact_id"]
        assert body["evaluation_ref"]["kind"] == "scientist.decision_validity_evaluation"
        assert body["lifecycle"]["events"] == []
        assert body["lifecycle"]["transitions"] == []
        assert body["lifecycle"]["scheduled_jobs"] == []
        assert body["lifecycle"]["reissue_candidates"] == []

    def test_get_packet_decision_validity_exposes_pending_reviews(self, runtime_api_env):
        service = DecisionValidityService(FileSystemCAS(runtime_api_env["cas_root"]))
        service.mark_packet_trigger(
            packet_ref=runtime_api_env["decision_packet_artifact_id"],
            trigger=DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
                status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                reason="target_applicability_changed",
            ),
        )

        client = runtime_api_env["client"]
        response = client.get(
            "/api/v1/control/decision-packets/"
            f"{runtime_api_env['decision_packet_artifact_id']}/decision-validity"
        )
        assert response.status_code == 200
        body = response.json()
        assert (
            body["decision_packet_ref"]["artifact_id"]
            == runtime_api_env["decision_packet_artifact_id"]
        )
        assert body["status"] == "requires_human_review"
        assert body["review_required"] is True
        assert body["lifecycle"]["events"][0]["trigger_type"] == "context_profile_drift"
        assert body["lifecycle"]["pending_reviews"][0]["reason"] == "target_applicability_changed"
        assert body["lifecycle"]["transitions"][-1]["current_status"] == "requires_human_review"


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
        assert body["job_id"]
        assert body["effective_execution_profile"] == "dev"
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
        assert body["job_id"]
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
        assert body["job_id"]
        assert "model variants" in body["message"]

    def test_launch_nl_run_accepts_execution_plan_payload(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Plan-first NL cycle",
                "execution_plan": {
                    "plan_id": "plan_contract_test",
                    "schema_version": "1.0",
                    "data_needs": [{"metric": "macro.gdp"}],
                    "method_dag": [],
                    "method_edges": [],
                    "params": {},
                    "budgets": {"max_iterations": 2},
                    "stop_criteria": {
                        "min_delta_improvement": 0.01,
                        "max_no_delta_iterations": 1,
                    },
                    "governance_constraints": [],
                    "expected_outputs": [],
                },
                "stop_criteria": {"max_no_delta_iterations": 1},
                "governance_constraints": [{"constraint_id": "g1", "kind": "policy"}],
                "expected_outputs": [{"output_id": "o1", "metric_id": "macro.gdp"}],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["job_id"]

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
        IngestionResult(datasets_fetched=1)
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


class TestDataRetrievalControl:
    def test_data_resolve_returns_payload(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/data/resolve",
            json={
                "data_needs": [
                    {
                        "metric": "us.macro.gdp_nominal",
                        "geography": "USA",
                        "granularity": "annual",
                        "quality_min": 0.6,
                        "purpose": "test",
                    }
                ],
                "mode": "hybrid",
                "allow_explore_fallback": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "hybrid"
        assert isinstance(body["fetch_plans"], list)
        assert isinstance(body["candidates"], list)
        assert "meta" in body

    def test_data_discover_returns_payload(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/data/discover",
            json={
                "data_needs": [
                    {
                        "metric": "us.macro.gdp_nominal",
                        "granularity": "annual",
                        "quality_min": 0.6,
                        "purpose": "test",
                    }
                ],
                "max_sources_per_query": 2,
                "max_discovery_calls_per_source": 3,
                "max_candidates_total": 5,
                "time_budget_ms": 1000,
                "cost_budget_usd": 0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["candidates"], list)
        assert isinstance(body["docs_fetched_total"], int)
        assert "index_stats" in body
        assert "meta" in body

    def test_data_preview_returns_preview(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/data/preview",
            json={
                "fetch_plan": {
                    "plan_id": "plan_test_preview",
                    "metric_id": "us.macro.gdp_nominal",
                    "connector_id": "missing.connector",
                    "dataset_id": "missing.dataset",
                    "profile_id": None,
                    "filters": {},
                    "date_start": None,
                    "date_end": None,
                    "granularity": "annual",
                    "quality_min": 0.6,
                    "source_lane": "fastlane",
                    "persist_payload": False,
                    "max_preview_rows": 10,
                    "fallbacks": [],
                    "metadata": {},
                },
                "allow_fallback": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "preview" in body
        assert body["preview"]["connector_id"] == "missing.connector"
        assert body["preview"]["dataset_id"] == "missing.dataset"
        assert "meta" in body

    def test_data_catalog_search_returns_matches(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/catalog/search?metric=us.macro&limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert "matches" in body
        assert isinstance(body["matches"], list)
        assert body["query"] == "us.macro"
        assert "meta" in body

    def test_data_index_stats_returns_stats(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/index/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "stats" in body
        assert "index_docs_total" in body["stats"]
        assert "index_size_bytes" in body["stats"]
        assert "meta" in body

    def test_data_promotion_endpoints(self, runtime_api_env):
        client = runtime_api_env["client"]
        list_resp = client.get("/api/v1/control/data/promotion/candidates")
        assert list_resp.status_code == 200
        assert isinstance(list_resp.json()["candidates"], list)

        approve_resp = client.post(
            "/api/v1/control/data/promotion/nonexistent/approve",
            json={"reason": "test"},
        )
        assert approve_resp.status_code == 200
        approve_body = approve_resp.json()
        assert approve_body["status"] == "rejected"
        assert approve_body["binding_updated"] is False

        reject_resp = client.post(
            "/api/v1/control/data/promotion/nonexistent/reject",
            json={"reason": "test"},
        )
        assert reject_resp.status_code == 200
        reject_body = reject_resp.json()
        assert reject_body["status"] == "rejected"
        assert reject_body["binding_updated"] is False


class TestIngestStreamingWindowed:
    def test_ingest_streaming_windowed(self, runtime_api_env):
        client = runtime_api_env["client"]
        with patch(
            "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
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
