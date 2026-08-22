from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.case_inspection import CaseInspectionService
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)


def _secure_client(runtime_api_env, *, role: PolicyOSRole, suffix: str):
    bearer = _fixture_bearer(suffix)
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
            jti=f"jwt-{suffix}",
            roles=frozenset({role}),
        ),
    )
    return client, {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }


def test_case_inspection_returns_artifact_missing_without_defaulting_stage_facts(
    runtime_api_env,
) -> None:
    run_id = runtime_api_env["core_run_id"]
    response = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/case-inspection")
    paper = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/paper")

    assert response.status_code == 200, response.text
    assert response.content == paper.content
    packet = response.json()
    assert packet["case_record"] == {
        "availability": "artifact_missing",
        "capability_state": "producer_missing",
        "reason_code": "case-record-not-run-bound",
        "owner_route": "team-runtime",
        "closure_signal": "case-record-not-run-bound",
        "may_not_use_for": [
            "case_identity",
            "design_record",
            "grounding_state",
            "admission_state",
            "promotion_state",
            "blockers",
            "limitations",
            "objections",
            "abstentions",
        ],
    }
    assert set(packet["case_record"]) == {
        "availability",
        "capability_state",
        "reason_code",
        "owner_route",
        "closure_signal",
        "may_not_use_for",
    }
    assert packet["stage_trace"]["availability"] in {
        "available",
        "not_established",
        "invalid_source",
    }


def test_case_inspection_requires_complete_closed_case_replay_tuple(
    runtime_api_env,
) -> None:
    run_id = runtime_api_env["core_run_id"]
    endpoint = f"/api/v1/runs/{run_id}/case-inspection"
    stable = runtime_api_env["client"].get(endpoint)
    assert stable.status_code == 200, stable.text
    pins = stable.json()["replay_pins"]

    replay = runtime_api_env["client"].get(endpoint, params=pins)
    assert replay.status_code == 200, replay.text
    assert replay.content == stable.content

    partial = runtime_api_env["client"].get(
        endpoint,
        params={"manifest_artifact_id": pins["manifest_artifact_id"]},
    )
    assert partial.status_code == 409
    assert partial.json()["code"] == "case_inspection_replay_pin_mismatch"

    mismatched = {**pins, "paper_projection_hash": "sha256:" + "0" * 64}
    stale = runtime_api_env["client"].get(endpoint, params=mismatched)
    assert stale.status_code == 409
    assert stale.json()["code"] == "case_inspection_replay_pin_mismatch"


def test_case_inspection_names_a_missing_run_at_its_public_boundary(
    runtime_api_env,
) -> None:
    response = runtime_api_env["client"].get(
        "/api/v1/runs/run-that-does-not-exist/case-inspection"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "case_inspection_run_not_found"


def test_case_inspection_names_a_run_that_disappears_during_projection(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _disappeared_after_preflight(_service, _run_id: str, **_kwargs):
        raise KeyError("run disappeared after authorization preflight")

    monkeypatch.setattr(CaseInspectionService, "get", _disappeared_after_preflight)
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/case-inspection"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "case_inspection_run_not_found"


def test_case_inspection_authorizes_before_resolving(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    viewer, headers = _secure_client(
        runtime_api_env,
        role=PolicyOSRole.VIEWER,
        suffix="case-inspection-viewer",
    )
    routes = [route for route in viewer.app.routes if isinstance(route, APIRoute)]
    matches = [
        route
        for route in routes
        if route.path == "/api/v1/runs/{run_id}/case-inspection" and "GET" in route.methods
    ]
    assert len(matches) == 1
    dependency = get_route_action_permission_dependency(matches[0])
    assert dependency.requirement.permission is RuntimePermission.RUNS_REVIEW
    assert dependency.requirement.resource_binding.source is ResourceBindingSource.TENANT_COLLECTION
    assert dependency.requirement.resource_binding.resource_kind == "runtime.case_inspection"

    calls: list[str] = []

    def _must_not_resolve(_service, run_id: str, **_kwargs):
        calls.append(run_id)
        raise AssertionError("case inspection resolved before review authorization")

    monkeypatch.setattr(CaseInspectionService, "get", _must_not_resolve)
    denied = viewer.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/case-inspection",
        headers=headers,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "action_permission_denied"
    assert calls == []


def test_openapi_exposes_case_inspection_through_the_frozen_strict_union(
    runtime_api_env,
) -> None:
    schema = runtime_api_env["client"].get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/runs/{run_id}/case-inspection"]["get"]
    assert operation["operationId"] == "get_case_inspection"
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    packet_name = response_schema["$ref"].rsplit("/", 1)[-1]
    assert packet_name == "RunPaperPacket"
    case_schema = schema["components"]["schemas"][packet_name]["properties"]["case_record"]
    assert case_schema["discriminator"]["propertyName"] == "availability"
    assert len(case_schema["oneOf"]) == 2
