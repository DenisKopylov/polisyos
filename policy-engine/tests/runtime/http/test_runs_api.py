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
    assert by_id[runtime_api_env["core_run_id"]]["execution_profile"] == "governed"
    assert by_id[runtime_api_env["core_run_id"]]["control_job_id"] == "job_ctrl_fixture_001"
    assert by_id[runtime_api_env["core_run_id_secondary"]]["source_kind"] == "core_run"


def test_get_run_details_returns_normalized_payload(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    core = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")
    assert core.status_code == 200
    core_payload = core.json()["run"]
    assert core_payload["source_kind"] == "core_run"
    assert core_payload["has_workflow_report"] is True
    assert core_payload["tenant_id"] == runtime_api_env["tenant_a"]
    assert core_payload["execution_profile"] == "governed"
    assert core_payload["control_job_id"] == "job_ctrl_fixture_001"
    assert (
        core_payload["capability_manifest_ref"]["artifact_id"]
        == runtime_api_env["capability_manifest_artifact_id"]
    )

    secondary = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id_secondary']}")
    assert secondary.status_code == 200
    secondary_payload = secondary.json()["run"]
    assert secondary_payload["source_kind"] == "core_run"
    assert secondary_payload["tenant_id"] == runtime_api_env["tenant_a"]
    assert secondary_payload["execution_profile"] is None


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


def test_list_runs_applies_server_side_query_filter_before_pagination(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    target_query = runtime_api_env["core_run_id"].lower()
    response = client.get(f"/api/v1/runs?limit=20&q={target_query}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["page"]["total"] == 1
    assert payload["page"]["count"] == 1
    assert [item["run_id"] for item in payload["runs"]] == [runtime_api_env["core_run_id"]]


def test_evaluate_feedback_endpoint_persists_monitoring_report(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.post(
        f"/api/v1/control/runs/{runtime_api_env['core_run_id']}/feedback/evaluate"
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["action"] == "evaluate_feedback"
    assert payload["monitoring_report_ref"] is not None
    assert payload["compare_report_ref"] is not None
    assert payload["reissue_plan_ref"] is not None


def test_reissue_endpoint_fails_closed_without_durable_control_plane(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.post(f"/api/v1/control/runs/{runtime_api_env['core_run_id']}/reissue")
    assert response.status_code == 422

    payload = response.json()
    assert payload["code"] == "durable_worker_required"
