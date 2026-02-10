from __future__ import annotations


def test_run_timeline_contains_ordered_events(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/timeline")
    assert response.status_code == 200

    timeline = response.json()["timeline"]
    assert timeline["summary"]["total_events"] > 0
    indices = [event["index"] for event in timeline["events"]]
    assert indices == sorted(indices)

    events = {event["event"] for event in timeline["events"]}
    assert "NODE_OK" in events
    assert "NODE_FAIL" in events


def test_run_nodes_endpoint_reads_workflow_report(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/nodes")
    assert response.status_code == 200
    payload = response.json()
    aliases = {node["alias"]: node for node in payload["nodes"]}

    assert "compile_foundry" in aliases
    assert aliases["compile_foundry"]["status"] == "ok"
    assert "run_governance" in aliases
    assert aliases["run_governance"]["status"] == "fail"
    assert aliases["run_governance"]["error_code"] == "governance.blocked"


def test_run_lineage_endpoint_returns_dependency_graph(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/lineage?max_depth=32&max_nodes=1000"
    )
    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert lineage["total_nodes"] >= 1
    assert len(lineage["root_artifact_ids"]) >= 1

