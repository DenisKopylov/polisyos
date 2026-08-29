"""Run-bound acquisition route and deferred execution API."""

from __future__ import annotations

from typing import Annotated, Any, cast

from polisyos.core.security import AccessScope
from polisyos.runtime.http.authorization import (
    BoundActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.dependencies import (
    ensure_request_id,
    get_acquisition_action_service,
    set_authz_resource,
)
from polisyos.runtime.http.errors import conflict, forbidden, not_found, service_unavailable
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    AcquisitionDecisionRequestResponse,
    AcquisitionExecutionResponse,
    AcquisitionRouteListResponse,
    AcquisitionRouteMutationRequest,
    AcquisitionRouteProjection,
)
from polisyos.runtime.http.step_up import StepUpClass, require_step_up

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = cast("Any", None)
    Depends = cast("Any", None)
    Request = cast("Any", Any)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover
        raise RuntimeError("runtime HTTP routes require FastAPI")
    return APIRouter(prefix="/api/v1/runs", tags=["runtime-acquisition-routes"])


router = _build_router()
_GET_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.acquisition_route",
        allow_empty_body=True,
    ),
)
_MUTATION_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_ACQUIRE,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.acquisition",
        selector_fields=(
            "route_projection_hash",
            "planner_report_hash",
            "replay_pins",
            "idempotency_key",
            "human_decision_record_ref",
        ),
        required_selector_fields=(
            "route_projection_hash",
            "planner_report_hash",
            "replay_pins",
            "idempotency_key",
        ),
    ),
)
_MUTATION_STEP_UP = require_step_up(StepUpClass.ACQUISITION_APPROVAL)
_Service = Annotated[AcquisitionActionService, Depends(get_acquisition_action_service)]


def _scope(request: Request) -> tuple[str, str, RuntimePrincipal]:
    scope = getattr(request.state, "authz_effective_scope", None)
    if isinstance(scope, AccessScope) and scope.cell_id:
        return (
            scope.tenant_id,
            scope.cell_id,
            RuntimePrincipal.from_access_scope(scope),
        )
    tenant_id = getattr(request.state, "tenant_id", None)
    cell_id = getattr(request.state, "cell_id", None)
    if not isinstance(tenant_id, str) or not isinstance(cell_id, str):
        raise forbidden(
            "Acquisition routes require a tenant and cell scope",
            code="acquisition_actor_scope_missing",
        )
    return tenant_id, cell_id, RuntimePrincipal(tenant_id=tenant_id, cell_id=cell_id)


def _bound_proof(request: Request) -> BoundActionPermissionVerification:
    proof = _MUTATION_AUTHZ(request)
    if type(proof) is not BoundActionPermissionVerification:
        raise forbidden(
            "Acquisition mutation lacks its frozen request binding",
            code="authorization_binding_context_missing",
        )
    return proof


def _raise_service_error(exc: AcquisitionActionServiceError) -> None:
    code = exc.code
    if code in {
        "acquisition_authority_producer_missing",
        "acquisition_execution_bridge_missing",
    }:
        raise service_unavailable("Acquisition producer is unavailable", code=code) from exc
    if code in {
        "source_job_not_completed",
        "acquisition_route_not_current",
    }:
        raise not_found("Current acquisition route was not found", code=code) from exc
    raise conflict("Acquisition route requires revalidation", code=code) from exc


@router.get(
    "/{run_id}/acquisition-routes",
    response_model=AcquisitionRouteListResponse,
    operation_id="list_run_acquisition_routes",
    dependencies=[Depends(_GET_AUTHZ)],
)
def list_run_acquisition_routes(
    run_id: str,
    request: Request,
    service: _Service,
) -> AcquisitionRouteListResponse:
    tenant_id, cell_id, _ = _scope(request)
    set_authz_resource(request, tenant_id=tenant_id, kind="runtime.acquisition_route")
    try:
        return service.list_routes(tenant_id=tenant_id, cell_id=cell_id, run_id=run_id)
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.get(
    "/{run_id}/acquisition-routes/{route_id}",
    response_model=AcquisitionRouteProjection,
    operation_id="get_run_acquisition_route",
    dependencies=[Depends(_GET_AUTHZ)],
)
def get_run_acquisition_route(
    run_id: str,
    route_id: str,
    request: Request,
    service: _Service,
) -> AcquisitionRouteProjection:
    tenant_id, cell_id, _ = _scope(request)
    set_authz_resource(request, tenant_id=tenant_id, kind="runtime.acquisition_route")
    try:
        return service.get_route(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.post(
    "/{run_id}/acquisition-routes/{route_id}/decision-request",
    response_model=AcquisitionDecisionRequestResponse,
    operation_id="request_run_acquisition_decision",
    dependencies=[Depends(_MUTATION_AUTHZ), Depends(_MUTATION_STEP_UP)],
)
def request_run_acquisition_decision(
    run_id: str,
    route_id: str,
    body: AcquisitionRouteMutationRequest,
    request: Request,
    service: _Service,
) -> AcquisitionDecisionRequestResponse:
    tenant_id, cell_id, _ = _scope(request)
    set_authz_resource(
        request,
        tenant_id=tenant_id,
        kind="runtime.evidence.acquisition.request_bound",
    )
    try:
        return service.request_decision(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=body,
            bound_permission=_bound_proof(request),
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.post(
    "/{run_id}/acquisition-routes/{route_id}/execute",
    response_model=AcquisitionExecutionResponse,
    operation_id="execute_run_acquisition_route",
    dependencies=[Depends(_MUTATION_AUTHZ), Depends(_MUTATION_STEP_UP)],
)
def execute_run_acquisition_route(
    run_id: str,
    route_id: str,
    body: AcquisitionRouteMutationRequest,
    request: Request,
    service: _Service,
) -> AcquisitionExecutionResponse:
    tenant_id, cell_id, principal = _scope(request)
    set_authz_resource(
        request,
        tenant_id=tenant_id,
        kind="runtime.evidence.acquisition.request_bound",
    )
    try:
        return service.execute(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=body,
            bound_permission=_bound_proof(request),
            request_id=ensure_request_id(request),
            principal=principal,
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


__all__ = ["router"]
