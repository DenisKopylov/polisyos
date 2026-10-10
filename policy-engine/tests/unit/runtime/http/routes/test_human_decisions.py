from __future__ import annotations

from typing import Any


class _CaptureAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)


def test_producer_missing_gate_response_keeps_run_tenant_and_actor_in_access_audit(
    runtime_api_env,
) -> None:
    app = runtime_api_env["app"]
    container = app.state.runtime_container
    audit = _CaptureAudit()
    app.state.runtime_access_audit = audit
    container.runtime_access_audit = audit
    run_id = str(runtime_api_env["core_run_id"])
    tenant_id = str(runtime_api_env["tenant_a"])

    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{run_id}/human-decision-gate",
        params={"source_kind": "production_approval"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "producer_missing"
    assert payload["tenant_id"] == tenant_id
    assert payload["run_id"] == run_id

    data_access_events = [
        event
        for event in audit.entries
        if event.get("operation") == "READ runtime.run.human_decision_gate"
    ]
    assert len(data_access_events) == 1
    event = data_access_events[0]
    assert event["outcome"] == "human_decision_gate_producer_missing"
    assert event["tenant_id"] == tenant_id
    assert event["actor"] == "fixture-analyst"
    assert event["endpoint"] == f"/api/v1/runs/{run_id}/human-decision-gate"
    assert event["resource_id"] == run_id
