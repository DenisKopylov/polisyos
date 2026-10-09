from __future__ import annotations

import hashlib
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.llm.settlement import LLMProducerEvent
from tests._helpers.runtime_http import (
    build_runtime_api_env,
    close_runtime_api_env,
    submit_ordinary_nl_post,
)


def test_run_agents_endpoint_returns_attempt_pipeline(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/agents")
    assert response.status_code == 200

    pipeline = response.json()["pipeline"]
    assert pipeline["run_id"] == runtime_api_env["core_run_id"]
    assert pipeline["source_kind"] == "core_run"
    assert pipeline["source"] == "decision_packet.audit_trail"
    assert pipeline["total_attempts"] == 1
    performance_summary = pipeline["performance_summary"]
    assert performance_summary["schema_version"] == "1.0"
    assert performance_summary["budget_summary"]["over_budget_count"] == 2
    assert {row["phase"] for row in performance_summary["phase_budgets"]} >= {
        "llm.total",
        "retrieval.materialize",
    }
    assert (
        pipeline["reflexion_terminal_ref"]["artifact_id"]
        == runtime_api_env["reflexion_terminal_artifact_id"]
    )

    attempts = pipeline["attempts"]
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["attempt"] == 1
    assert attempt["status"] == "failed"

    agent_order = [step["agent"] for step in attempt["steps"]]
    assert agent_order == ["pi_agent", "drafter", "formalizer", "critic", "reflexion"]


def test_fresh_agents_get_preserves_producer_cost_events_and_unknown_totals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")

    def _forbid_gateway(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("simulated NL run must not construct a real gateway")

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.GatewayLLMClient",
        _forbid_gateway,
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.FallbackRouter",
        _forbid_gateway,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.RetrievalService.resolve",
        lambda *_args, **_kwargs: SimpleNamespace(
            fetch_plans=[{"id": "plan-1"}],
            telemetry={"lane_used": "fastlane", "metadata_docs_fetched": 1, "phases": []},
            mode="hybrid",
        ),
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.RetrievalService.execute_fetch_plans",
        lambda *_args, **_kwargs: SimpleNamespace(
            previews=[SimpleNamespace(preview=SimpleNamespace(coverage_ok=True))],
            fallback_triggered_count=0,
            promoted_count=1,
            data_context=SimpleNamespace(
                metrics=[], metadata_docs_fetched=1, index_docs_total=1, index_size_bytes=10
            ),
        ),
    )
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        assert env["client"] is not None
        ordinary_run = submit_ordinary_nl_post(env)
        run_id = str(ordinary_run["run_id"])
        binding = ordinary_run["binding"]
        store = env["app"].state.runtime_container.llm_producer_settlement_store
        model = "simulated-qwen"
        provider = "simulated_gateway"
        reported_event_id = "llm-provider:reported-zero"
        fixtures = (
            (reported_event_id, "reported", Decimal(0), "provider", None),
            ("llm-provider:estimated", "estimated", Decimal("0.25"), "provider", None),
            ("llm-provider:unknown", "unknown", None, "provider", None),
            ("llm-reuse:cache-hit", "reuse", Decimal(0), "reuse", reported_event_id),
        )
        events = []
        with store.producer_run_binding_scope(binding):
            for event_id, origin, amount, kind, origin_event_id in fixtures:
                request_digest = hashlib.sha256(f"request:{event_id}".encode()).hexdigest()
                event = LLMProducerEvent(
                    event_id=event_id,
                    request_digest=request_digest,
                    response_digest=hashlib.sha256(f"response:{event_id}".encode()).hexdigest(),
                    model=model,
                    provider=provider,
                    amount=amount,
                    cost_origin=origin,
                    kind=kind,
                    origin_event_id=origin_event_id,
                )
                key = f"nl-run:{binding.run_id}"
                store.begin_producer_event_safe(
                    event.event_id,
                    event.request_digest,
                    key=key,
                    model=event.model,
                    provider=event.provider,
                )
                record = store.settle_producer_event_safe(
                    event.event_id,
                    event.request_digest,
                    event.payload_digest,
                    key=key,
                    model=event.model,
                    provider=event.provider,
                    amount=event.amount,
                    cost_origin=event.cost_origin,
                    origin_event_id=event.origin_event_id,
                )
                assert record.run_binding == binding
                events.append(record)

        response = env["client"].get(f"/api/v1/runs/{run_id}/agents")
        assert response.status_code == 200, response.text
        pipeline = response.json()["pipeline"]
        assert pipeline["cost_usd"] is None
        assert pipeline["reported_cost_usd"] == 0.0
        assert pipeline["estimated_cost_usd"] >= 0.25
        assert pipeline["cost_origin_counts"]["reported"] >= 1
        assert pipeline["cost_origin_counts"]["estimated"] >= 1
        assert pipeline["cost_origin_counts"]["unknown"] >= 1
        assert pipeline["cost_origin_counts"]["reuse"] == 1

        step = next(
            item
            for item in pipeline["attempts"][0]["steps"]
            if item["agent"] == "llm_producer_settlement"
        )
        served = {row["event_id"]: row for row in step["cost_events"]}
        for record in events:
            row = served[record.event_id]
            assert row["cost_origin"] == record.cost_origin
            assert row["settlement_status"] == record.status
            assert row["durability"] == "ledger"
            assert row["receipts"] == ([record.event_id] if record.status == "committed" else [])
            assert row["amount"] == (str(record.amount) if record.amount is not None else None)
            assert row["model"] == model
            assert row["provider"] == provider
        assert served[reported_event_id]["amount"] == "0"
        assert served["llm-provider:estimated"]["amount"] == "0.25"
        assert served["llm-provider:unknown"]["amount"] is None
        assert served["llm-reuse:cache-hit"]["amount"] == "0"
        assert served["llm-reuse:cache-hit"]["origin_event_id"] == reported_event_id
    finally:
        close_runtime_api_env(env)


def test_agents_get_refuses_malformed_cost_event_collection(tmp_path) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        agent_cost_events="not-an-event-list",
    )
    try:
        response = env["client"].get(f"/api/v1/runs/{env['core_run_id']}/agents")
        assert response.status_code == 400
        assert response.json()["detail"] == "agent_pipeline_cost_events_invalid"
    finally:
        close_runtime_api_env(env)


def test_fresh_agents_get_projects_and_deduplicates_nl_preflight_events(tmp_path) -> None:
    # This fixture exercises state/audit deduplication only. Durable custody is
    # covered by the ordinary POST and exact owner-bound ledger test above.
    event = {
        "event_id": "llm-provider:nl-preflight",
        "origin_event_id": None,
        "cost_origin": "reported",
        "amount": "0.17",
        "cost_usd": 0.17,
        "settlement_status": "unmanaged",
        "durability": "none",
        "receipts": [],
        "payload_digest": hashlib.sha256(b"nl-preflight").hexdigest(),
        "model": "model-a",
        "provider": "gateway-a",
    }
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        agent_cost_events=[event],
        nl_preflight_cost_events=[event],
    )
    try:
        response = env["client"].get(f"/api/v1/runs/{env['core_run_id']}/agents")
        assert response.status_code == 200, response.text

        pipeline = response.json()["pipeline"]
        assert pipeline["cost_usd"] == 0.17
        all_steps = [step for attempt in pipeline["attempts"] for step in attempt["steps"]]
        compiler = next(step for step in all_steps if step["agent"] == "design_problem_compiler")
        drafter = next(step for step in all_steps if step["agent"] == "drafter")
        assert compiler["action"] == "nl_preflight"
        assert compiler["cost_events"] == [event]
        assert drafter["cost_events"] == []
        projected_events = [cost_event for step in all_steps for cost_event in step["cost_events"]]
        assert [cost_event["event_id"] for cost_event in projected_events] == [event["event_id"]]
    finally:
        close_runtime_api_env(env)


def test_agents_get_refuses_ledger_cost_claim_without_exact_durable_event(tmp_path) -> None:
    event_id = "llm-provider:unreconciled-ledger-claim"
    event = {
        "event_id": event_id,
        "origin_event_id": None,
        "cost_origin": "reported",
        "amount": "0.31",
        "cost_usd": 0.31,
        "settlement_status": "committed",
        "durability": "ledger",
        "receipts": [event_id],
        "payload_digest": hashlib.sha256(b"unreconciled").hexdigest(),
        "model": "model-a",
        "provider": "gateway-a",
    }
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        agent_cost_events=[event],
        seed_ledger_cost_events=False,
        raise_server_exceptions=False,
    )
    try:
        response = env["client"].get(f"/api/v1/runs/{env['core_run_id']}/agents")
        assert response.status_code >= 400, response.text
        assert "pipeline" not in response.json()
    finally:
        close_runtime_api_env(env)


def test_agents_get_refuses_conflicting_cost_event_identity_across_sources(tmp_path) -> None:
    state_event = {
        "event_id": "llm-provider:conflicting-id",
        "cost_origin": "reported",
        "amount": "0.17",
        "cost_usd": 0.17,
        "settlement_status": "committed",
        "durability": "ledger",
        "receipts": ["llm-provider:conflicting-id"],
        "payload_digest": "sha256:state",
    }
    audit_event = {**state_event, "amount": "0.18", "cost_usd": 0.18}
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        agent_cost_events=[audit_event],
        nl_preflight_cost_events=[state_event],
    )
    try:
        response = env["client"].get(f"/api/v1/runs/{env['core_run_id']}/agents")
        assert response.status_code == 400
        assert response.json()["detail"] == "agent_pipeline_cost_event_ledger_reconciliation_failed"
    finally:
        close_runtime_api_env(env)


def test_run_workflow_endpoint_returns_dag(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/workflow")
    assert response.status_code == 200

    workflow = response.json()["workflow"]
    assert workflow["run_id"] == runtime_api_env["core_run_id"]
    assert workflow["source_kind"] == "core_run"
    assert (
        workflow["workflow_spec_ref"]["artifact_id"] == runtime_api_env["workflow_spec_artifact_id"]
    )
    assert (
        workflow["workflow_report_ref"]["artifact_id"]
        == runtime_api_env["workflow_report_artifact_id"]
    )

    summary = workflow["summary"]
    assert summary["workflow_id"] == "scientist_default"
    assert summary["error_policy"] == "fail_fast"
    assert summary["status"] == "fail"
    assert summary["node_count"] >= 2
    assert summary["edge_count"] >= 1
    assert summary["critical_path_duration_ms"] is not None
    assert summary["critical_path_duration_ms"] >= 18

    edges = {(edge["from_alias"], edge["to_alias"]) for edge in workflow["edges"]}
    assert ("compile_foundry", "run_governance") in edges

    nodes = {node["alias"]: node for node in workflow["nodes"]}
    assert nodes["compile_foundry"]["status"] == "ok"
    assert nodes["run_governance"]["status"] == "fail"
    assert nodes["run_governance"]["depth"] >= 1


def test_run_evidence_context_endpoint_returns_run_scoped_evidence(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/evidence-context")
    assert response.status_code == 200

    context = response.json()["context"]
    assert context["run_id"] == runtime_api_env["core_run_id"]
    assert (
        context["execution_plan_ref"]["artifact_id"]
        == runtime_api_env["execution_plan_artifact_id"]
    )
    assert (
        context["data_snapshot_ref"]["artifact_id"] == runtime_api_env["data_snapshot_artifact_id"]
    )
    assert (
        context["input_bindings_ref"]["artifact_id"]
        == runtime_api_env["input_bindings_artifact_id"]
    )
    assert (
        context["evidence_bundle_ref"]["artifact_id"]
        == runtime_api_env["evidence_bundle_artifact_id"]
    )

    needs = context["data_needs"]
    assert len(needs) == 1
    assert needs[0]["metric"] == "macro.gdp.real"
    assert needs[0]["matched_plan_ids"] == ["plan_fixture_fetch_001"]

    plans = context["fetch_plans"]
    assert len(plans) == 1
    assert plans[0]["matched_need_ids"] == [needs[0]["need_id"]]
    assert plans[0]["connector_id"] == "worldbank.wdi"

    promotions = context["promotion_candidates"]
    assert len(promotions) == 1
    assert promotions[0]["matched_plan_id"] == "plan_fixture_fetch_001"

    related_ids = {item["artifact_id"] for item in context["related_artifacts"]}
    assert runtime_api_env["decision_packet_artifact_id"] in related_ids
    assert runtime_api_env["execution_plan_artifact_id"] in related_ids
