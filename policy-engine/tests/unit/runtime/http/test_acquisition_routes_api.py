from __future__ import annotations

from types import SimpleNamespace

from _helpers.runtime_http import _runtime_api_request
from fastapi.routing import APIRoute

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.dependencies import get_acquisition_action_service
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionServiceError,
    CandidateExperimentRouteProjection,
    CandidateExperimentRouteReplayPins,
)
from polisyos.runtime.http.step_up import StepUpClass, get_route_step_up_dependency
from tests.unit.runtime.http.test_runtime_api_authz import _build_permissionless_client

_ROUTES = {
    ("GET", "/api/v1/runs/{run_id}/acquisition-routes"),
    ("GET", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"),
    ("GET", "/api/v1/runs/{run_id}/candidate-acquisition-experiment"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"),
}


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
        assert dependency.requirement.permission is RuntimePermission.EVIDENCE_ACQUIRE
        binding = dependency.requirement.resource_binding
        assert binding.source is ResourceBindingSource.REQUEST_COMPOSITE
        assert binding.resource_kind == "runtime.evidence.acquisition"
        step_up = get_route_step_up_dependency(route, action_dependency=dependency)
        assert step_up is not None
        assert step_up.requirement.step_up_class is StepUpClass.ACQUISITION_APPROVAL
