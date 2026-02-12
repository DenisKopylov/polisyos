from __future__ import annotations


def test_run_agents_endpoint_returns_attempt_pipeline(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/agents")
    assert response.status_code == 200

    pipeline = response.json()["pipeline"]
    assert pipeline["run_id"] == runtime_api_env["core_run_id"]
    assert pipeline["source_kind"] == "core_run"
    assert pipeline["source"] == "decision_packet.audit_trail"
    assert pipeline["total_attempts"] == 1
    assert pipeline["reflexion_terminal_ref"]["artifact_id"] == runtime_api_env[
        "reflexion_terminal_artifact_id"
    ]

    attempts = pipeline["attempts"]
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["attempt"] == 1
    assert attempt["status"] == "failed"

    agent_order = [step["agent"] for step in attempt["steps"]]
    assert agent_order == ["pi_agent", "drafter", "formalizer", "critic", "reflexion"]


def test_run_workflow_endpoint_returns_dag(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/workflow")
    assert response.status_code == 200

    workflow = response.json()["workflow"]
    assert workflow["run_id"] == runtime_api_env["core_run_id"]
    assert workflow["source_kind"] == "core_run"
    assert workflow["workflow_spec_ref"]["artifact_id"] == runtime_api_env["workflow_spec_artifact_id"]
    assert workflow["workflow_report_ref"]["artifact_id"] == runtime_api_env[
        "workflow_report_artifact_id"
    ]

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
