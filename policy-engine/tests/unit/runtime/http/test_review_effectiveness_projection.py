"""Red-first review-effectiveness witnesses over the existing access trail."""

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.runtime.http.access_audit import (
    RuntimeAuthorizationAuditEvent,
    RuntimeAuthorizationOutcome,
)


def test_review_effectiveness_does_not_count_authorization_allow_as_success(
    runtime_api_env,
) -> None:
    run_id = runtime_api_env["core_run_id"]
    trail = runtime_api_env["client"].app.state.runtime_container.runtime_access_audit
    event = RuntimeAuthorizationAuditEvent(
        timestamp=datetime.now(UTC).timestamp(),
        request_id="ds9-authorization-allow",
        outcome=RuntimeAuthorizationOutcome.ALLOW,
        denial_reason="",
        method="POST",
        route_path="/api/v1/runs/{run_id}/human-decisions",
        permission="runs.human_decisions.create",
        resource_id=run_id,
        resource_digest="sha256:" + "d" * 64,
        resource_kind="runtime.run.human_decision",
        binding_authority="ownership_verified",
        step_up_class="human_decision",
        step_up_outcome="verified",
        subject="user:reviewer",
        tenant_id=runtime_api_env["tenant_a"],
        principal_type="user",
        opa_policy="runtime.action_permission",
        opa_reasons=[],
    )
    trail.append(event.model_dump(mode="json"))

    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{run_id}/human-decisions/review-effectiveness"
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authorization_allow_count"] == 1
    assert payload["completed_human_decision_count"] == 0
    assert payload["coverage_status"] == "incomplete"
