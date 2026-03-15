from __future__ import annotations


def test_node_debug_endpoint_returns_node_context(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(
        f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/nodes/run_governance"
    )
    assert response.status_code == 200

    payload = response.json()["debug"]
    assert payload["alias"] == "run_governance"
    assert payload["record"]["status"] == "fail"
    assert payload["record"]["error_code"] == "governance.blocked"
    assert payload["record"]["error_details"]["api_token"] == "[REDACTED]"
    assert payload["cache_bypasses"] >= 1


def test_governance_debug_prefers_governance_report(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/governance")
    assert response.status_code == 200

    payload = response.json()["debug"]
    assert payload["verdict"] == "reject"
    assert payload["issue_summary"] == {"blocker_count": 1, "warning_count": 0, "info_count": 0}
    assert payload["legal_executed"] is True
    assert payload["transport_summary"]["status"] == "blocked"
    assert payload["normative_summary"]["selected_policy"] == "weighted_welfare"
    assert payload["normative_summary"]["selected_option"] == "baseline"
    assert payload["normative_arbitration_result_ref"] is not None
    assert payload["fallback_from_decision_packet"] is False
    assert payload["report_ref"] is not None


def test_run_errors_endpoint_aggregates_manifest_and_workflow_errors(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/errors")
    assert response.status_code == 200

    errors = response.json()["errors"]
    codes = {item["code"] for item in errors}
    assert "run.failed" in codes
    assert "governance.blocked" in codes
    workflow_error = next(item for item in errors if item["code"] == "governance.blocked")
    assert workflow_error["details"]["api_token"] == "[REDACTED]"


def test_feedback_endpoint_returns_feedback_loop(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/feedback")
    assert response.status_code == 200

    payload = response.json()["feedback"]
    assert payload["feedback_loop"]["monitoring_contract_ref"] is not None
    assert payload["monitoring_contract"]["metrics"][0]["metric_id"] == "policy_cost"


def test_compare_endpoint_surfaces_law_delta(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(
        f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/compare/"
        f"{runtime_api_env['core_run_id_secondary']}"
    )
    assert response.status_code == 200

    payload = response.json()["compare"]
    assert payload["report"]["deltas"]["law"]["changed"] is True
    assert "law" in payload["report"]["root_cause"]
