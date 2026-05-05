from __future__ import annotations


def test_runs_api_emits_only_core_run_source_kind(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/runs?limit=50")
    assert response.status_code == 200

    payload = response.json()
    assert payload["meta"]["source_kinds"] == ["core_run"]
    assert payload["page"]["total"] >= 2

    for run in payload["runs"]:
        assert run["source_kind"] == "core_run"


def test_run_details_payload_has_no_legacy_artifact_paths(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")
    assert response.status_code == 200

    payload = response.json()["run"]
    assert payload["source_kind"] == "core_run"
    assert "legacy_artifact_paths" not in payload
