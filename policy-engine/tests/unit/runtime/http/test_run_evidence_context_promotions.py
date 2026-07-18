from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.identity import PolicyOSRole
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


def _promotion_status(body: dict[str, object], promotion_id: str) -> str:
    context = body["context"]
    assert isinstance(context, dict)
    candidates = context["promotion_candidates"]
    assert isinstance(candidates, list)
    for candidate in candidates:
        assert isinstance(candidate, dict)
        if candidate.get("promotion_id") == promotion_id:
            status = candidate.get("status")
            assert isinstance(status, str)
            return status
    raise AssertionError(f"promotion candidate {promotion_id!r} not found")


def test_run_evidence_context_reflects_live_promotion_decisions(runtime_api_env) -> None:
    bearer = _fixture_bearer("live-promotion-decisions")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-live-promotion-decisions",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    run_id = runtime_api_env["core_run_id"]
    promotion_id = runtime_api_env["promotion_candidate_id"]
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    store = FileSystemCAS(runtime_api_env["cas_root"])
    for artifact_id in (
        runtime_api_env["experiment_state_artifact_id"],
        runtime_api_env["decision_packet_artifact_id"],
        runtime_api_env["execution_plan_artifact_id"],
    ):
        store.record_artifact_owner(
            artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.runtime_http.live_promotion_decisions",
        )

    with client:
        source_candidates = (
            runtime_api_env["app"].state._control_service.list_promotion_candidates().candidates
        )
        candidate = next(
            item for item in source_candidates if item.promotion_id == promotion_id
        )
        retrieval = client.app.state._control_service._retrieval
        with retrieval._state_lock:
            retrieval._store_promotion_candidate_locked(candidate)

        response = client.get(f"/api/v1/runs/{run_id}/evidence-context", headers=headers)
        assert response.status_code == 200
        assert _promotion_status(response.json(), promotion_id) == "pending"

        approve = client.post(
            f"/api/v1/control/data/promotion/{promotion_id}/approve",
            headers={
                **headers,
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={"reason": "fixture smoke approve"},
        )
        assert approve.status_code == 200
        assert approve.json()["status"] == "approved"

        response = client.get(f"/api/v1/runs/{run_id}/evidence-context", headers=headers)
        assert response.status_code == 200
        assert _promotion_status(response.json(), promotion_id) == "approved"

        reject = client.post(
            f"/api/v1/control/data/promotion/{promotion_id}/reject",
            headers={
                **headers,
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={"reason": "fixture smoke reject"},
        )
        assert reject.status_code == 200
        assert reject.json()["status"] == "rejected"

        response = client.get(f"/api/v1/runs/{run_id}/evidence-context", headers=headers)
        assert response.status_code == 200
        assert _promotion_status(response.json(), promotion_id) == "rejected"


def test_run_evidence_context_links_fabric_trace_materialization_and_timeline(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(f"/api/v1/runs/{run_id}/evidence-context")
    assert response.status_code == 200
    context = response.json()["context"]

    fabric_ref = context["fabric_retrieval_trace_ref"]
    materialization_refs = context["materialization_refs"]
    production_context = context["production_data_evidence_context"]
    related_artifact_ids = {item["artifact_id"] for item in context["related_artifacts"]}

    assert fabric_ref["artifact_id"].startswith("sha256:")
    assert fabric_ref["artifact_id"] in related_artifact_ids
    assert materialization_refs["data_snapshot_ref"]["artifact_id"] == (
        runtime_api_env["data_snapshot_artifact_id"]
    )
    assert materialization_refs["input_bindings_ref"]["artifact_id"] == (
        runtime_api_env["input_bindings_artifact_id"]
    )
    assert production_context["fabric_retrieval_trace_ref"] == fabric_ref["artifact_id"]
    assert production_context["materialization_refs"]["quality_report_ref"] == (
        runtime_api_env["quality_artifact_id"]
    )

    timeline_response = client.get(f"/api/v1/runs/{run_id}/timeline")
    assert timeline_response.status_code == 200
    events = timeline_response.json()["timeline"]["events"]
    selection_events = [
        event
        for event in events
        if event["phase"] == "fabric.source_selection"
        and event["event"].startswith("SOURCE_SELECTION_TRACE_PERSISTED")
    ]
    assert selection_events
    selection_event = selection_events[0]
    assert "prod-msme-panel" in selection_event["event"]
    assert fabric_ref["artifact_id"] in selection_event["output_artifact_ids"]
    assert materialization_refs["data_snapshot_ref"]["artifact_id"] in (
        selection_event["input_artifact_ids"]
    )
