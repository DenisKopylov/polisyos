from __future__ import annotations

import hashlib
import json
import time
from types import SimpleNamespace

import pytest
from _helpers.runtime_http import _runtime_api_request
from fastapi import Request
from fastapi.routing import APIRoute

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    BoundActionPermissionVerification,
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.dependencies import get_acquisition_action_service
from polisyos.runtime.http.permissions import (
    CANDIDATE_EXPERIMENT_REUSE_PERMISSION,
    CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND,
    RuntimePermission,
)
from polisyos.runtime.http.routes import acquisitions
from polisyos.runtime.http.services.acquisition_action_service import (
    CANDIDATE_MODEL_REVISION_TERMINAL_CUSTODY_RESOURCE_KIND,
    AcquisitionActionServiceError,
    AcquisitionDecisionRequestResponse,
    AcquisitionExecutionResponse,
    AcquisitionRouteMutationRequest,
    CandidateExperimentRouteExecutionRequest,
    CandidateExperimentRouteMutationRequest,
    CandidateExperimentRouteProjection,
    CandidateExperimentRouteReplayPins,
    CandidateModelRevisionTerminalCustodyRequest,
)
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionBundleBlocked,
    require_acquisition_bound_permission,
    require_candidate_experiment_terminal_custody_bound_permission,
    require_candidate_model_revision_terminal_custody_bound_permission,
)
from polisyos.runtime.http.step_up import StepUpClass, get_route_step_up_dependency
from polisyos.runtime.quality.candidate_experiment_reuse import (
    CandidateExperimentReuseActionRequest,
)
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_permissionless_client,
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)

_ROUTES = {
    ("GET", "/api/v1/runs/{run_id}/acquisition-routes"),
    ("GET", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"),
    ("GET", "/api/v1/runs/{run_id}/candidate-acquisition-experiment"),
    (
        "POST",
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/decision-request",
    ),
    (
        "POST",
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute",
    ),
    (
        "POST",
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/reuse/decision-request",
    ),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/terminal-custody"),
}


def test_native_draft_approval_binds_body_and_bearer_but_keeps_draft_out_of_opa(
    runtime_api_env,
) -> None:
    raw_draft = '{"draft_id":"private-settled-content"}'
    digest = "sha256:" + "d" * 64
    body = AcquisitionRouteMutationRequest.model_validate(
        {
            "route_projection_hash": digest,
            "planner_report_hash": digest,
            "replay_pins": {
                "source_job_id": "native-source",
                "compiled_ref": digest,
                "compiled_content_hash": digest,
                "terminal_event_id": "native-original-terminal",
                "design_problem_ref": digest,
                "cost_basis_hash": digest,
            },
            "idempotency_key": "same-action",
            "custody_recovery": {
                "failed_attempt": 5,
                "head_ref": {
                    "artifact_id": digest,
                    "kind": "runtime_quality.acquisition_route_phase_receipt",
                    "media_type": "application/json",
                    "manifest_profile_sha256": digest,
                },
                "settled_draft": {
                    "producer_event_id": "llm-provider:" + "f" * 32,
                    "ledger_revision": 18,
                    "response_text": raw_draft,
                },
            },
        }
    )
    opa = _CaptureOPA()
    client, cell, provider = _build_secure_client(
        runtime_api_env, opa_client=opa, claims_by_token={}, raise_server_exceptions=False
    )
    bearer = _fixture_bearer("native-draft-recovery")
    expiry = int(time.time()) + 45
    claims = _claims(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        jti="jwt-native-draft-recovery",
        roles=frozenset({PolicyOSRole.ANALYST}),
    ).model_copy(update={"exp": expiry})
    provider.put_claim(bearer, claims)
    calls = []
    policy_projections = []

    def execute(**kwargs):
        calls.append(kwargs)
        return AcquisitionExecutionResponse(
            run_id="native-run",
            route_id=digest,
            job_id="same-native-action",
            authority_decision_ref=digest,
        )

    def service(request: Request) -> SimpleNamespace:
        policy_projections.append(request.state.authz_resource)
        return SimpleNamespace(execute=execute)

    client.app.dependency_overrides[get_acquisition_action_service] = service
    try:
        step_up = _install_bound_test_step_up(client)
        result = client.post(
            f"/api/v1/runs/native-run/acquisition-routes/{digest}/execute",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": step_up,
            },
            json=body.model_dump(mode="json"),
        )
    finally:
        client.close()
    assert result.status_code == 200, result.text
    assert len(calls) == len(opa.inputs) == len(policy_projections) == 1
    assert calls[0]["request"] == body
    assert calls[0]["recovery_approval_expires_at"] == expiry
    bound = calls[0]["bound_permission"]
    local_selector = dict(bound.bound_resource.canonical_selectors)["custody_recovery"]
    middleware_projection = policy_projections[0]
    policy_selectors = dict(middleware_projection["selectors"])
    policy_resource = opa.inputs[0].to_opa_input()["resource"]
    assert raw_draft == json.loads(local_selector)["settled_draft"]["response_text"]
    assert "private-settled-content" not in json.dumps(policy_resource)
    assert "private-settled-content" not in json.dumps(policy_selectors)
    assert json.loads(policy_selectors["custody_recovery"]) == {
        "sha256": hashlib.sha256(local_selector.encode()).hexdigest(),
    }
    assert middleware_projection["resource_digest"] == require_acquisition_bound_permission(
        bound, body
    )
    assert policy_resource["artifact_id"] == middleware_projection["artifact_id"]


def _route(app: object, method: str, path: str) -> APIRoute:
    matches = [
        candidate
        for candidate in getattr(app, "routes", ())
        if isinstance(candidate, APIRoute)
        and candidate.path == path
        and method in candidate.methods
    ]
    assert len(matches) == 1
    return matches[0]


def test_acquisition_routes_have_exact_get_resource_binding(runtime_openapi_app) -> None:
    app = runtime_openapi_app
    for method, path in sorted(_ROUTES):
        _route(app, method, path)

    candidate_experiment = _route(
        app,
        "GET",
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment",
    )
    assert candidate_experiment.operation_id == "get_run_candidate_acquisition_experiment"

    for path in sorted(path for method, path in _ROUTES if method == "GET"):
        dependency = get_route_action_permission_dependency(_route(app, "GET", path))
        assert dependency.requirement.permission is RuntimePermission.RUNS_REVIEW
        binding = dependency.requirement.resource_binding
        assert binding.source is ResourceBindingSource.TENANT_COLLECTION
        assert binding.resource_kind == "runtime.acquisition_route"


def test_candidate_experiment_decision_route_has_exact_binding_and_step_up(
    runtime_openapi_app,
) -> None:
    route = _route(
        runtime_openapi_app,
        "POST",
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/decision-request",
    )
    assert route.operation_id == "request_run_candidate_acquisition_experiment_decision"
    dependency = get_route_action_permission_dependency(route)
    assert dependency.requirement.permission is RuntimePermission.EVIDENCE_ACQUIRE
    binding = dependency.requirement.resource_binding
    assert binding.source is ResourceBindingSource.REQUEST_COMPOSITE
    assert binding.resource_kind == "runtime.evidence.acquisition.candidate_experiment"
    assert binding.selector_fields == tuple(CandidateExperimentRouteMutationRequest.model_fields)
    assert binding.required_selector_fields == tuple(
        name
        for name, field in CandidateExperimentRouteMutationRequest.model_fields.items()
        if field.is_required()
    )
    step_up = get_route_step_up_dependency(route, action_dependency=dependency)
    assert step_up is not None
    assert step_up.requirement.step_up_class is StepUpClass.ACQUISITION_APPROVAL


def test_candidate_experiment_execute_route_has_exact_binding_and_step_up(
    runtime_openapi_app,
) -> None:
    route = _route(
        runtime_openapi_app,
        "POST",
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute",
    )
    assert route.operation_id == "execute_run_candidate_acquisition_experiment"
    response_example = runtime_openapi_app.openapi()["paths"][route.path]["post"]["responses"][
        "200"
    ]["content"]["application/json"]["example"]
    assert response_example == AcquisitionExecutionResponse(
        run_id="run-example",
        route_id="sha256:" + "a" * 64,
        job_id="candidate-experiment-job-example",
        authority_decision_ref="sha256:" + "b" * 64,
    ).model_dump(mode="json")
    dependency = get_route_action_permission_dependency(route)
    assert dependency.requirement.permission is RuntimePermission.EVIDENCE_ACQUIRE
    binding = dependency.requirement.resource_binding
    assert binding.source is ResourceBindingSource.REQUEST_COMPOSITE
    assert binding.resource_kind == "runtime.evidence.acquisition.candidate_experiment"
    assert binding.selector_fields == tuple(CandidateExperimentRouteExecutionRequest.model_fields)
    assert binding.selector_fields == ("request", "decision_ref")
    assert binding.required_selector_fields == tuple(
        name
        for name, field in CandidateExperimentRouteExecutionRequest.model_fields.items()
        if field.is_required()
    )
    assert binding.required_selector_fields == ("request", "decision_ref")
    step_up = get_route_step_up_dependency(route, action_dependency=dependency)
    assert step_up is not None
    assert step_up.requirement.step_up_class is StepUpClass.ACQUISITION_APPROVAL


def test_candidate_experiment_reuse_decision_route_has_distinct_exact_binding_and_step_up(
    runtime_openapi_app,
) -> None:
    route = _route(
        runtime_openapi_app,
        "POST",
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/reuse/decision-request",
    )
    assert route.operation_id == "request_run_candidate_acquisition_experiment_reuse_decision"
    dependency = get_route_action_permission_dependency(route)
    assert dependency.requirement.permission is CANDIDATE_EXPERIMENT_REUSE_PERMISSION
    binding = dependency.requirement.resource_binding
    assert binding.source is ResourceBindingSource.REQUEST_COMPOSITE
    assert binding.resource_kind == CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND
    assert binding.selector_fields == tuple(CandidateExperimentReuseActionRequest.model_fields)
    assert binding.required_selector_fields == tuple(
        name
        for name, field in CandidateExperimentReuseActionRequest.model_fields.items()
        if field.is_required()
    )
    step_up = get_route_step_up_dependency(route, action_dependency=dependency)
    assert step_up is not None
    assert step_up.requirement.step_up_class is StepUpClass.ACQUISITION_APPROVAL


def _candidate_experiment_projection() -> CandidateExperimentRouteProjection:
    def artifact_ref(digit: str, kind: str) -> ArtifactRef:
        digest = "sha256:" + digit * 64
        return ArtifactRef(
            artifact_id=digest,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=digest,
        )

    return CandidateExperimentRouteProjection(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
        run_id="run-candidate-experiment",
        route_id="sha256:" + "a" * 64,
        replay_pins=CandidateExperimentRouteReplayPins(
            source_job_id="job-candidate-experiment",
            source_payload_ref="sha256:" + "b" * 64,
            request_content_hash="sha256:" + "c" * 64,
            compiled_ref=artifact_ref("1", "runtime.compiled_recursive_generation_cycle"),
            planner_report_ref=artifact_ref("2", "runtime.acquisition_planner_report"),
            compiler_report_ref=artifact_ref("3", "runtime.data_requirement_compilation_report"),
            configured_port_source_ref=artifact_ref(
                "4", "runtime.quality.n7_configured_candidate_port_source"
            ),
            policy_ref=artifact_ref("5", "runtime_quality.candidate_unpriced_acquisition_policy"),
            candidate_digest="sha256:" + "d" * 64,
        ),
        scheduler_action="limited_experiment",
        scheduler_reason="bounded_experiment_voi_unknown",
    )


def _candidate_experiment_request() -> CandidateExperimentRouteMutationRequest:
    projection = _candidate_experiment_projection()
    return CandidateExperimentRouteMutationRequest(
        route_id=projection.route_id,
        replay_pins=projection.replay_pins,
        idempotency_key="candidate-experiment-decision-request",
    )


def _candidate_experiment_reuse_request() -> CandidateExperimentReuseActionRequest:
    def artifact_ref(digit: str, kind: str) -> ArtifactRef:
        digest = "sha256:" + digit * 64
        return ArtifactRef(
            artifact_id=digest,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=digest,
        )

    return CandidateExperimentReuseActionRequest(
        route_id="sha256:" + "a" * 64,
        predecessor_terminal_ref=artifact_ref(
            "1", "runtime_quality.acquisition_route_loop_receipt"
        ),
        predecessor_action_ref=artifact_ref(
            "2", "runtime_quality.acquisition_candidate_action_receipt"
        ),
        source_ref=artifact_ref("3", "runtime.quality.candidate_acquisition_source"),
        n5_input_ref=artifact_ref("4", "runtime.quality.candidate_simulation_n5_input"),
        n5_execution_ref=artifact_ref("5", "runtime.quality.candidate_simulation_execution"),
        n5_result_ref=artifact_ref("6", "polisyos.runtime.joint_simulation_result"),
        policy_ref=artifact_ref("7", "runtime_quality.candidate_unpriced_acquisition_policy"),
        idempotency_key="candidate-experiment-reuse-decision-request",
    )


def test_candidate_experiment_decision_transport_uses_bound_proof_and_step_up(
    runtime_api_env,
) -> None:
    """Exercise HTTP/auth transport only; the service is a test-owned seam."""
    request_body = _candidate_experiment_request()
    path = (
        "/api/v1/runs/run-candidate-experiment/candidate-acquisition-experiment/"
        f"{request_body.route_id}/decision-request"
    )
    calls: list[dict[str, object]] = []

    def request_decision(
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: CandidateExperimentRouteMutationRequest,
        bound_permission: BoundActionPermissionVerification,
    ) -> AcquisitionDecisionRequestResponse:
        calls.append(
            {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": route_id,
                "request": request,
                "bound_permission": bound_permission,
            }
        )
        return AcquisitionDecisionRequestResponse(
            run_id=run_id,
            route_id=route_id,
            authority_decision_ref="sha256:" + "f" * 64,
            outcome="decision_required",
        )

    service = SimpleNamespace(request_candidate_experiment_decision=request_decision)

    permissionless_client, permissionless_token = _build_permissionless_client(runtime_api_env)
    permissionless_client.app.dependency_overrides[get_acquisition_action_service] = lambda: (
        service
    )
    try:
        denied = permissionless_client.post(
            path,
            headers={
                "Authorization": f"Bearer {permissionless_token}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=request_body.model_dump(mode="json"),
        )
    finally:
        permissionless_client.close()
    assert denied.status_code == 403, denied.text
    assert denied.json()["code"] == "action_permission_denied"
    assert calls == []

    secure_client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    bearer = _fixture_bearer("candidate-experiment-step-up")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-candidate-experiment-step-up",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    secure_client.app.dependency_overrides[get_acquisition_action_service] = lambda: service
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    try:
        missing_step_up = secure_client.post(
            path,
            headers=headers,
            json=request_body.model_dump(mode="json"),
        )
        assert missing_step_up.status_code == 403, missing_step_up.text
        assert missing_step_up.json()["code"] == "step_up_required"
        assert calls == []

        step_up = _install_bound_test_step_up(secure_client)
        accepted = secure_client.post(
            path,
            headers={**headers, "X-PolicyOS-Step-Up": step_up},
            json=request_body.model_dump(mode="json"),
        )
    finally:
        secure_client.close()

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["run_id"] == "run-candidate-experiment"
    assert accepted.json()["route_id"] == request_body.route_id
    assert accepted.json()["outcome"] == "decision_required"
    assert len(calls) == 1
    call = calls[0]
    assert call["tenant_id"] == runtime_api_env["tenant_a"]
    assert call["cell_id"] == cell.cell_id
    assert call["run_id"] == "run-candidate-experiment"
    assert call["route_id"] == request_body.route_id
    assert call["request"] == request_body
    bound_permission = call["bound_permission"]
    assert type(bound_permission) is BoundActionPermissionVerification
    assert (
        bound_permission.verification.requirement.resource_binding.resource_kind
        == "runtime.evidence.acquisition.candidate_experiment"
    )


def test_candidate_experiment_reuse_decision_transport_uses_distinct_bound_proof_and_step_up(
    runtime_api_env,
) -> None:
    request_body = _candidate_experiment_reuse_request()
    path = (
        "/api/v1/runs/run-candidate-experiment/candidate-acquisition-experiment/"
        f"{request_body.route_id}/reuse/decision-request"
    )
    calls: list[dict[str, object]] = []

    def request_reuse_decision(
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: CandidateExperimentReuseActionRequest,
        bound_permission: BoundActionPermissionVerification,
    ) -> AcquisitionDecisionRequestResponse:
        calls.append(
            {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": route_id,
                "request": request,
                "bound_permission": bound_permission,
            }
        )
        return AcquisitionDecisionRequestResponse(
            run_id=run_id,
            route_id=route_id,
            authority_decision_ref="sha256:" + "f" * 64,
            outcome="decision_required",
        )

    service = SimpleNamespace(request_candidate_experiment_reuse_decision=request_reuse_decision)
    permissionless_client, permissionless_token = _build_permissionless_client(runtime_api_env)
    permissionless_client.app.dependency_overrides[get_acquisition_action_service] = lambda: (
        service
    )
    try:
        denied = permissionless_client.post(
            path,
            headers={
                "Authorization": f"Bearer {permissionless_token}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=request_body.model_dump(mode="json"),
        )
    finally:
        permissionless_client.close()
    assert denied.status_code == 403, denied.text
    assert denied.json()["code"] == "action_permission_denied"
    assert calls == []

    secure_client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    bearer = _fixture_bearer("candidate-experiment-reuse-step-up")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-candidate-experiment-reuse-step-up",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    secure_client.app.dependency_overrides[get_acquisition_action_service] = lambda: service
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    try:
        missing_step_up = secure_client.post(
            path,
            headers=headers,
            json=request_body.model_dump(mode="json"),
        )
        assert missing_step_up.status_code == 403, missing_step_up.text
        assert missing_step_up.json()["code"] == "step_up_required"
        assert calls == []
        step_up = _install_bound_test_step_up(secure_client)
        accepted = secure_client.post(
            path,
            headers={**headers, "X-PolicyOS-Step-Up": step_up},
            json=request_body.model_dump(mode="json"),
        )
    finally:
        secure_client.close()

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["run_id"] == "run-candidate-experiment"
    assert accepted.json()["route_id"] == request_body.route_id
    assert accepted.json()["outcome"] == "decision_required"
    assert len(calls) == 1
    call = calls[0]
    assert call["tenant_id"] == runtime_api_env["tenant_a"]
    assert call["cell_id"] == cell.cell_id
    assert call["run_id"] == "run-candidate-experiment"
    assert call["route_id"] == request_body.route_id
    assert call["request"] == request_body
    bound_permission = call["bound_permission"]
    assert type(bound_permission) is BoundActionPermissionVerification
    assert (
        bound_permission.verification.requirement.resource_binding.resource_kind
        == CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND
    )


def test_candidate_experiment_execute_transport_is_scoped_and_step_up_protected(
    runtime_api_env,
) -> None:
    """Exercise HTTP/auth transport only; service authority remains separately verified."""
    original_request = _candidate_experiment_request()
    decision_ref = "sha256:" + "e" * 64
    body = CandidateExperimentRouteExecutionRequest(
        request=original_request,
        decision_ref=decision_ref,
    )
    path = (
        "/api/v1/runs/run-candidate-experiment/candidate-acquisition-experiment/"
        f"{original_request.route_id}/execute"
    )
    calls: list[dict[str, object]] = []
    completed_retry = False
    expired_at_admission = False

    def execute_candidate_experiment(
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: CandidateExperimentRouteMutationRequest,
        decision_ref: str,
        request_id: str | None,
        principal: object,
        step_up_expires_at: int,
    ) -> AcquisitionExecutionResponse:
        if expired_at_admission:
            raise AcquisitionActionServiceError(
                "candidate_experiment_step_up_expired_before_admission"
            )
        status = "completed" if completed_retry else "accepted"
        receipt_phase = "terminal" if completed_retry else "requested"
        calls.append(
            {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": route_id,
                "request": request,
                "decision_ref": decision_ref,
                "request_id": request_id,
                "principal": principal,
                "step_up_expires_at": step_up_expires_at,
            }
        )
        return AcquisitionExecutionResponse(
            run_id=run_id,
            route_id=route_id,
            job_id="job-candidate-experiment",
            authority_decision_ref=decision_ref,
            status=status,
            receipt_phase=receipt_phase,
        )

    service = SimpleNamespace(execute_candidate_experiment=execute_candidate_experiment)

    permissionless_client, permissionless_token = _build_permissionless_client(runtime_api_env)
    permissionless_client.app.dependency_overrides[get_acquisition_action_service] = lambda: (
        service
    )
    try:
        denied = permissionless_client.post(
            path,
            headers={
                "Authorization": f"Bearer {permissionless_token}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body.model_dump(mode="json"),
        )
    finally:
        permissionless_client.close()
    assert denied.status_code == 403, denied.text
    assert denied.json()["code"] == "action_permission_denied"
    assert calls == []

    secure_client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    bearer = _fixture_bearer("candidate-experiment-execute-step-up")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-candidate-experiment-execute-step-up",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    secure_client.app.dependency_overrides[get_acquisition_action_service] = lambda: service
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    try:
        missing_step_up = secure_client.post(
            path,
            headers=headers,
            json=body.model_dump(mode="json"),
        )
        assert missing_step_up.status_code == 403, missing_step_up.text
        assert missing_step_up.json()["code"] == "step_up_required"
        assert calls == []

        step_up = _install_bound_test_step_up(secure_client)
        accepted = secure_client.post(
            path,
            headers={**headers, "X-PolicyOS-Step-Up": step_up},
            json=body.model_dump(mode="json"),
        )
        completed_retry = True
        retry_step_up = _install_bound_test_step_up(secure_client)
        retry = secure_client.post(
            path,
            headers={**headers, "X-PolicyOS-Step-Up": retry_step_up},
            json=body.model_dump(mode="json"),
        )
        expired_at_admission = True
        expiring_step_up = _install_bound_test_step_up(secure_client)
        expired = secure_client.post(
            path,
            headers={**headers, "X-PolicyOS-Step-Up": expiring_step_up},
            json=body.model_dump(mode="json"),
        )
    finally:
        secure_client.close()

    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {
        "run_id": "run-candidate-experiment",
        "route_id": original_request.route_id,
        "job_id": "job-candidate-experiment",
        "authority_decision_ref": decision_ref,
        "status": "accepted",
        "receipt_phase": "requested",
        "world_growth": "not_established",
    }
    assert len(calls) == 2
    call = calls[0]
    assert call["tenant_id"] == runtime_api_env["tenant_a"]
    assert call["cell_id"] == cell.cell_id
    assert call["run_id"] == "run-candidate-experiment"
    assert call["route_id"] == original_request.route_id
    assert call["request"] == original_request
    assert call["decision_ref"] == decision_ref
    assert type(call["step_up_expires_at"]) is int and call["step_up_expires_at"] > 0
    assert isinstance(call["request_id"], str) and call["request_id"]
    principal = call["principal"]
    assert principal.tenant_id == runtime_api_env["tenant_a"]
    assert principal.cell_id == cell.cell_id
    assert principal.authenticated is True
    retry_call = calls[1]
    assert retry_call["request"] == original_request
    assert retry_call["decision_ref"] == decision_ref
    assert retry_call["route_id"] == original_request.route_id

    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "completed"
    assert retry.json()["receipt_phase"] == "terminal"
    assert retry.json()["world_growth"] == "not_established"
    assert expired.status_code == 403, expired.text
    assert expired.json()["code"] == "candidate_experiment_step_up_expired_before_admission"


def test_candidate_experiment_terminal_custody_requires_a_fresh_bound_request(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run-candidate-experiment"
    route_id = "sha256:" + "a" * 64
    path = f"/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/terminal-custody"
    body = {
        "run_id": run_id,
        "route_id": route_id,
        "job_id": "job-candidate-experiment",
        "failed_attempt": 5,
        "pending_head_ref": {
            "artifact_id": "sha256:" + "b" * 64,
            "kind": "runtime_quality.acquisition_candidate_experiment_phase_receipt",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "c" * 64,
        },
        "terminal_ref": {
            "artifact_id": "sha256:" + "d" * 64,
            "kind": "runtime_quality.acquisition_route_loop_receipt",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "e" * 64,
        },
    }
    calls = []
    expire_before_effect = False

    def settle_candidate_experiment_terminal_custody(**kwargs):
        request = kwargs["request"]
        proof = kwargs["bound_permission"]
        assert request.model_dump(mode="json") == body
        assert kwargs["principal"].authenticated
        assert proof.bound_resource.resource_kind == (
            "runtime.evidence.acquisition.candidate_experiment.terminal_custody.request_bound"
        )
        assert (
            require_candidate_experiment_terminal_custody_bound_permission(proof, request)
            == proof.bound_resource.resource_digest
        )
        with pytest.raises(
            AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
        ):
            require_candidate_experiment_terminal_custody_bound_permission(
                proof, request.model_copy(update={"failed_attempt": 6})
            )
        if expire_before_effect:
            with monkeypatch.context() as clock:
                clock.setattr(acquisitions.time, "time", lambda: kwargs["step_up"].expires_at)
                kwargs["authorize_effect"]()
            pytest.fail("Expired Step-Up was accepted for terminal custody")
        assert kwargs["authorize_effect"]() > 0
        calls.append(kwargs)
        return {
            "run_id": run_id,
            "route_id": route_id,
            "job_id": body["job_id"],
            "terminal_ref": body["terminal_ref"],
            "frontier_revision": 4,
        }

    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    bearer = _fixture_bearer("candidate-experiment-terminal-custody")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-candidate-experiment-terminal-custody",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    client.app.dependency_overrides[get_acquisition_action_service] = lambda: SimpleNamespace(
        settle_candidate_experiment_terminal_custody=settle_candidate_experiment_terminal_custody
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    try:
        missing = client.post(path, headers=headers, json=body)
        assert missing.status_code == 403, missing.text
        assert missing.json()["code"] == "step_up_required"
        assert not calls
        step_up = _install_bound_test_step_up(client)
        bound_headers = {**headers, "X-PolicyOS-Step-Up": step_up}
        settled = client.post(path, headers=bound_headers, json=body)
        assert settled.status_code == 200, settled.text
        assert settled.json()["frontier_revision"] == 4
        assert len(calls) == 1
        replay = client.post(path, headers=bound_headers, json=body)
        assert replay.status_code == 403, replay.text
        assert replay.json()["code"] == "step_up_replayed"
        fresh_step_up = _install_bound_test_step_up(client)
        foreign_path = client.post(
            path.replace(run_id, "different-run"),
            headers={**headers, "X-PolicyOS-Step-Up": fresh_step_up},
            json=body,
        )
        assert foreign_path.status_code == 403, foreign_path.text
        assert foreign_path.json()["code"] == "candidate_experiment_terminal_custody_scope_refused"
        assert len(calls) == 1
        expire_before_effect = True
        fresh_step_up = _install_bound_test_step_up(client)
        expired = client.post(
            path, headers={**headers, "X-PolicyOS-Step-Up": fresh_step_up}, json=body
        )
        assert expired.status_code == 403, expired.text
        assert expired.json()["code"] == "step_up_expired"
        assert len(calls) == 1
    finally:
        client.close()


def test_model_revision_terminal_custody_requires_fresh_exact_user_approval(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run-model-revision"
    route_id = "sha256:" + "a" * 64
    path = f"/api/v1/runs/{run_id}/acquisition-routes/{route_id}/terminal-custody"
    body = {
        "run_id": run_id,
        "route_id": route_id,
        "job_id": "job-model-revision",
        "failed_attempt": 5,
        "pending_receipt_ref": "sha256:" + "b" * 64,
        "reentry_ref": {
            "artifact_id": "sha256:" + "c" * 64,
            "kind": "runtime_quality.acquisition_overlay_reentry_receipt",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "d" * 64,
        },
        "decision_ref": {
            "artifact_id": "sha256:" + "e" * 64,
            "kind": "runtime_quality.acquisition_evaluation_decision",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "f" * 64,
        },
        "selected_basis_ref": {
            "artifact_id": "sha256:" + "0" * 64,
            "kind": "runtime_quality.acquisition_evaluation_basis",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "1" * 64,
        },
        "expected_frontier_revision": 4,
        "expected_frontier_ref": "sha256:" + "2" * 64,
    }
    calls = []
    expire_before_effect = False

    def settle_model_revision_terminal_custody(**kwargs):
        request = kwargs["request"]
        proof = kwargs["bound_permission"]
        assert type(request) is CandidateModelRevisionTerminalCustodyRequest
        assert request.model_dump(mode="json") == body
        assert kwargs["principal"].authenticated
        assert proof.bound_resource.resource_kind == (
            f"{CANDIDATE_MODEL_REVISION_TERMINAL_CUSTODY_RESOURCE_KIND}.request_bound"
        )
        assert (
            require_candidate_model_revision_terminal_custody_bound_permission(proof, request)
            == proof.bound_resource.resource_digest
        )
        with pytest.raises(
            AcquisitionAdmissionBundleBlocked, match="acquisition_resource_binding_invalid"
        ):
            require_candidate_model_revision_terminal_custody_bound_permission(
                proof, request.model_copy(update={"expected_frontier_revision": 5})
            )
        if expire_before_effect:
            with monkeypatch.context() as clock:
                clock.setattr(acquisitions.time, "time", lambda: kwargs["step_up"].expires_at)
                kwargs["authorize_effect"]()
            pytest.fail("Expired Step-Up was accepted for model-revision terminal custody")
        assert kwargs["authorize_effect"]() > 0
        calls.append(kwargs)
        terminal_ref = {
            "artifact_id": "sha256:" + "3" * 64,
            "kind": "runtime_quality.acquisition_route_loop_receipt",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "4" * 64,
        }
        return {
            "run_id": run_id,
            "route_id": route_id,
            "job_id": body["job_id"],
            "terminal_ref": terminal_ref,
            "frontier_revision": body["expected_frontier_revision"],
        }

    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    bearer = _fixture_bearer("model-revision-terminal-custody")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-model-revision-terminal-custody",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    client.app.dependency_overrides[get_acquisition_action_service] = lambda: SimpleNamespace(
        settle_candidate_model_revision_terminal_custody=settle_model_revision_terminal_custody
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    try:
        missing = client.post(path, headers=headers, json=body)
        assert missing.status_code == 403, missing.text
        assert missing.json()["code"] == "step_up_required"
        assert not calls

        step_up = _install_bound_test_step_up(client)
        bound_headers = {**headers, "X-PolicyOS-Step-Up": step_up}
        settled = client.post(path, headers=bound_headers, json=body)
        assert settled.status_code == 200, settled.text
        assert settled.json()["frontier_revision"] == 4
        assert settled.json()["terminal_ref"]["kind"] == (
            "runtime_quality.acquisition_route_loop_receipt"
        )
        assert len(calls) == 1
        call = calls[0]
        assert call["request"] == CandidateModelRevisionTerminalCustodyRequest.model_validate(body)
        assert call["step_up"].context.step_up_class is StepUpClass.ACQUISITION_APPROVAL

        replay = client.post(path, headers=bound_headers, json=body)
        assert replay.status_code == 403, replay.text
        assert replay.json()["code"] == "step_up_replayed"

        fresh_step_up = _install_bound_test_step_up(client)
        foreign_path = client.post(
            path.replace(run_id, "different-run"),
            headers={**headers, "X-PolicyOS-Step-Up": fresh_step_up},
            json=body,
        )
        assert foreign_path.status_code == 403, foreign_path.text
        assert foreign_path.json()["code"] == (
            "candidate_model_revision_terminal_custody_scope_refused"
        )
        assert len(calls) == 1

        expire_before_effect = True
        fresh_step_up = _install_bound_test_step_up(client)
        expired = client.post(
            path, headers={**headers, "X-PolicyOS-Step-Up": fresh_step_up}, json=body
        )
        assert expired.status_code == 403, expired.text
        assert expired.json()["code"] == "step_up_expired"
        assert len(calls) == 1
    finally:
        client.close()


def test_candidate_experiment_route_projects_candidate_and_fails_closed(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    projection = _candidate_experiment_projection()
    calls: list[tuple[str, str, str]] = []
    unavailable = False

    def read_candidate_experiment(
        *, tenant_id: str, cell_id: str, run_id: str
    ) -> CandidateExperimentRouteProjection:
        calls.append((tenant_id, cell_id, run_id))
        if unavailable:
            raise AcquisitionActionServiceError("acquisition_route_not_current")
        return projection

    service = SimpleNamespace(get_candidate_experiment_route=read_candidate_experiment)
    client.app.dependency_overrides[get_acquisition_action_service] = lambda: service
    try:
        response = _runtime_api_request(
            runtime_api_env,
            client.get,
            "/api/v1/runs/run-candidate-experiment/candidate-acquisition-experiment",
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["monetary_cost"] == "not_established"
        assert payload["information_value"] == "not_established"
        assert payload["action_authority"] == "not_established"
        assert payload["publication_authority"] is False
        assert calls == [
            (runtime_api_env["tenant_a"], runtime_api_env["cell_a"], "run-candidate-experiment")
        ]

        permissionless_client, token = _build_permissionless_client(runtime_api_env)
        permissionless_client.app.dependency_overrides[get_acquisition_action_service] = lambda: (
            service
        )
        denied = permissionless_client.get(
            "/api/v1/runs/run-candidate-experiment/candidate-acquisition-experiment",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )
        permissionless_client.close()
        assert denied.status_code == 403, denied.text
        assert denied.json()["code"] == "action_permission_denied"
        assert len(calls) == 1

        unavailable = True
        stale_source = _runtime_api_request(
            runtime_api_env,
            client.get,
            "/api/v1/runs/run-candidate-experiment/candidate-acquisition-experiment",
        )
    finally:
        client.app.dependency_overrides.pop(get_acquisition_action_service, None)

    assert stale_source.status_code == 404, stale_source.text
    assert stale_source.json()["code"] == "acquisition_route_not_current"
    assert (
        calls
        == [(runtime_api_env["tenant_a"], runtime_api_env["cell_a"], "run-candidate-experiment")]
        * 2
    )


def test_acquisition_mutations_are_request_bound_and_step_up_protected(
    runtime_openapi_app,
) -> None:
    app = runtime_openapi_app
    for path in sorted(path for method, path in _ROUTES if method == "POST"):
        route = _route(app, "POST", path)
        dependency = get_route_action_permission_dependency(route)
        if "/reuse/" in path:
            expected_permission = CANDIDATE_EXPERIMENT_REUSE_PERMISSION
            expected_kind = CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND
        elif path.endswith("/acquisition-routes/{route_id}/terminal-custody"):
            expected_permission = RuntimePermission.EVIDENCE_ACQUIRE
            expected_kind = CANDIDATE_MODEL_REVISION_TERMINAL_CUSTODY_RESOURCE_KIND
        else:
            expected_permission = RuntimePermission.EVIDENCE_ACQUIRE
            expected_kind = (
                "runtime.evidence.acquisition.candidate_experiment"
                if "candidate-acquisition-experiment" in path
                else "runtime.evidence.acquisition"
            )
        assert dependency.requirement.permission is expected_permission
        binding = dependency.requirement.resource_binding
        assert binding.source is ResourceBindingSource.REQUEST_COMPOSITE
        assert binding.resource_kind == expected_kind
        step_up = get_route_step_up_dependency(route, action_dependency=dependency)
        assert step_up is not None
        assert step_up.requirement.step_up_class is StepUpClass.ACQUISITION_APPROVAL
