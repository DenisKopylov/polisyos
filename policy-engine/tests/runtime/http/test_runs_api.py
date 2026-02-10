from __future__ import annotations


def test_list_runs_returns_only_core_sources(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/runs?limit=20")
    assert response.status_code == 200

    payload = response.json()
    run_ids = {item["run_id"] for item in payload["runs"]}
    assert runtime_api_env["core_run_id"] in run_ids
    assert runtime_api_env["core_run_id_secondary"] in run_ids

    by_id = {item["run_id"]: item for item in payload["runs"]}
    assert by_id[runtime_api_env["core_run_id"]]["source_kind"] == "core_run"
    assert by_id[runtime_api_env["core_run_id_secondary"]]["source_kind"] == "core_run"


def test_get_run_details_returns_normalized_payload(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    core = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")
    assert core.status_code == 200
    core_payload = core.json()["run"]
    assert core_payload["source_kind"] == "core_run"
    assert core_payload["has_workflow_report"] is True
    assert core_payload["tenant_id"] == runtime_api_env["tenant_a"]

    secondary = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id_secondary']}")
    assert secondary.status_code == 200
    secondary_payload = secondary.json()["run"]
    assert secondary_payload["source_kind"] == "core_run"
    assert secondary_payload["tenant_id"] == runtime_api_env["tenant_a"]


def test_list_runs_cursor_pagination(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    first_page = client.get("/api/v1/runs?limit=1")
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["page"]["count"] == 1
    next_cursor = first_payload["page"]["next_cursor"]
    assert isinstance(next_cursor, str)

    second_page = client.get(f"/api/v1/runs?limit=1&cursor={next_cursor}")
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["page"]["count"] == 1
