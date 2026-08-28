from __future__ import annotations

from fastapi.routing import APIRoute

from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.step_up import StepUpClass, get_route_step_up_dependency

_ROUTES = {
    ("GET", "/api/v1/runs/{run_id}/acquisition-routes"),
    ("GET", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"),
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


def test_acquisition_routes_have_exact_get_resource_binding(runtime_api_env) -> None:
    app = runtime_api_env["client"].app
    for method, path in sorted(_ROUTES):
        _route(app, method, path)

    for path in sorted(path for method, path in _ROUTES if method == "GET"):
        dependency = get_route_action_permission_dependency(_route(app, "GET", path))
        assert dependency.requirement.permission is RuntimePermission.RUNS_REVIEW
        binding = dependency.requirement.resource_binding
        assert binding.source is ResourceBindingSource.TENANT_COLLECTION
        assert binding.resource_kind == "runtime.acquisition_route"


def test_acquisition_mutations_are_request_bound_and_step_up_protected(
    runtime_api_env,
) -> None:
    app = runtime_api_env["client"].app
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
