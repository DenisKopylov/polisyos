"""Red-first HTTP witnesses for the run-bound DS9 surface."""

from __future__ import annotations


def test_human_decision_missing_producer_is_typed_not_a_missing_route(
    runtime_api_env,
) -> None:
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/human-decision-gate",
        params={"source_kind": "production_approval"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "producer_missing"
    assert payload["run_id"] == runtime_api_env["core_run_id"]
    assert payload["source_kind"] == "production_approval"
