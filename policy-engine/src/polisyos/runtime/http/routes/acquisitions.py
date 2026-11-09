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
from polisyos.runtime.http.permissions import (
    CANDIDATE_EXPERIMENT_REUSE_PERMISSION,
    CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND,
    RuntimePermission,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    AcquisitionDecisionRequestResponse,
    AcquisitionExecutionResponse,
    AcquisitionRouteListResponse,
    AcquisitionRouteMutationRequest,
    AcquisitionRouteProjection,
    CandidateExperimentReuseActionExecutionRequest,
    CandidateExperimentRouteExecutionRequest,
    CandidateExperimentRouteMutationRequest,
    CandidateExperimentRouteProjection,
)
from polisyos.runtime.http.services.model_input_successor_action import (
    MODEL_INPUT_USE_PERMISSION,
    MODEL_INPUT_USE_RESOURCE_KIND,
    ModelInputSuccessorActionRequest,
    ModelInputSuccessorDecisionResponse,
    ModelInputSuccessorExecutionRequest,
)
from polisyos.runtime.http.step_up import (
    StepUpAssertionVerification,
    StepUpClass,
    require_step_up,
)
from polisyos.runtime.quality.candidate_experiment_reuse import (
    CandidateExperimentReuseActionRequest,
)

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
_CANDIDATE_EXPERIMENT_MUTATION_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_ACQUIRE,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.acquisition.candidate_experiment",
        selector_fields=tuple(CandidateExperimentRouteMutationRequest.model_fields),
        required_selector_fields=tuple(
            name
            for name, field in CandidateExperimentRouteMutationRequest.model_fields.items()
            if field.is_required()
        ),
    ),
)
_CANDIDATE_EXPERIMENT_EXECUTION_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_ACQUIRE,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.acquisition.candidate_experiment",
        selector_fields=tuple(CandidateExperimentRouteExecutionRequest.model_fields),
        required_selector_fields=tuple(
            name
            for name, field in CandidateExperimentRouteExecutionRequest.model_fields.items()
            if field.is_required()
        ),
    ),
)
_CANDIDATE_EXPERIMENT_REUSE_AUTHZ = require_action_permission(
    CANDIDATE_EXPERIMENT_REUSE_PERMISSION,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind=CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND,
        selector_fields=tuple(CandidateExperimentReuseActionRequest.model_fields),
        required_selector_fields=tuple(
            name
            for name, field in CandidateExperimentReuseActionRequest.model_fields.items()
            if field.is_required()
        ),
    ),
)
_CANDIDATE_EXPERIMENT_REUSE_EXECUTION_AUTHZ = require_action_permission(
    CANDIDATE_EXPERIMENT_REUSE_PERMISSION,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind=CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND,
        selector_fields=tuple(CandidateExperimentReuseActionExecutionRequest.model_fields),
        required_selector_fields=tuple(
            name
            for name, field in CandidateExperimentReuseActionExecutionRequest.model_fields.items()
            if field.is_required()
        ),
    ),
)
_MODEL_INPUT_USE_MUTATION_AUTHZ = require_action_permission(
    MODEL_INPUT_USE_PERMISSION,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind=MODEL_INPUT_USE_RESOURCE_KIND,
        selector_fields=tuple(ModelInputSuccessorActionRequest.model_fields),
        required_selector_fields=tuple(
            name
            for name, field in ModelInputSuccessorActionRequest.model_fields.items()
            if field.is_required()
        ),
    ),
)
_MODEL_INPUT_USE_EXECUTION_AUTHZ = require_action_permission(
    MODEL_INPUT_USE_PERMISSION,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind=MODEL_INPUT_USE_RESOURCE_KIND,
        selector_fields=tuple(ModelInputSuccessorExecutionRequest.model_fields),
        required_selector_fields=tuple(ModelInputSuccessorExecutionRequest.model_fields),
    ),
)
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


def _candidate_experiment_bound_proof(
    request: Request,
) -> BoundActionPermissionVerification:
    proof = _CANDIDATE_EXPERIMENT_MUTATION_AUTHZ(request)
    if type(proof) is not BoundActionPermissionVerification:
        raise forbidden(
            "Candidate-experiment mutation lacks its frozen request binding",
            code="authorization_binding_context_missing",
        )
    return proof


def _candidate_experiment_execution_bound_proof(
    request: Request,
) -> BoundActionPermissionVerification:
    proof = _CANDIDATE_EXPERIMENT_EXECUTION_AUTHZ(request)
    if type(proof) is not BoundActionPermissionVerification:
        raise forbidden(
            "Candidate-experiment execution lacks its frozen request binding",
            code="authorization_binding_context_missing",
        )
    return proof


def _raise_service_error(exc: AcquisitionActionServiceError) -> None:
    code = exc.code
    if code in {
        "acquisition_authority_producer_missing",
        "acquisition_execution_bridge_missing",
        "candidate_experiment_n5_result_storage_unavailable",
        "candidate_experiment_current_action_head_not_established",
        "candidate_experiment_reuse_authority_producer_missing",
        "candidate_experiment_reuse_lifecycle_owner_unavailable",
        "candidate_experiment_reuse_execution_owner_missing",
        "model_input_use_authority_producer_missing",
        "model_input_use_successor_owner_unavailable",
    }:
        raise service_unavailable("Acquisition producer is unavailable", code=code) from exc
    if code in {
        "candidate_experiment_n5_result_scope_refused",
        "candidate_experiment_reuse_source_scope_refused",
        "model_input_use_source_scope_refused",
    }:
        raise forbidden("The selected candidate result is not accessible", code=code) from exc
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


@router.post(
    "/{run_id}/candidate-acquisition-experiment/{route_id}/reuse/execute",
    response_model=AcquisitionExecutionResponse,
    operation_id="execute_run_candidate_acquisition_experiment_reuse",
)
def execute_run_candidate_acquisition_experiment_reuse(
    run_id: str,
    route_id: str,
    body: CandidateExperimentReuseActionExecutionRequest,
    request: Request,
    bound_permission: Annotated[
        BoundActionPermissionVerification,
        Depends(_CANDIDATE_EXPERIMENT_REUSE_EXECUTION_AUTHZ),
    ],
    _step_up: Annotated[StepUpAssertionVerification, Depends(_MUTATION_STEP_UP)],
    service: _Service,
) -> AcquisitionExecutionResponse:
    """Queue one PA2-approved no-fetch reuse under the ordinary Control worker."""
    tenant_id, cell_id, principal = _scope(request)
    set_authz_resource(
        request,
        tenant_id=tenant_id,
        kind=CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND,
    )
    if type(bound_permission) is not BoundActionPermissionVerification:
        raise forbidden(
            "Candidate reuse lacks its frozen execution binding",
            code="authorization_binding_context_missing",
        )
    try:
        return service.execute_candidate_experiment_reuse(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=body,
            request_id=ensure_request_id(request),
            principal=principal,
        )
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


@router.get(
    "/{run_id}/candidate-acquisition-experiment",
    response_model=CandidateExperimentRouteProjection,
    operation_id="get_run_candidate_acquisition_experiment",
    dependencies=[Depends(_GET_AUTHZ)],
)
def get_run_candidate_acquisition_experiment(
    run_id: str,
    request: Request,
    service: _Service,
) -> CandidateExperimentRouteProjection:
    tenant_id, cell_id, _ = _scope(request)
    set_authz_resource(request, tenant_id=tenant_id, kind="runtime.acquisition_route")
    try:
        return service.get_candidate_experiment_route(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.post(
    "/{run_id}/candidate-acquisition-experiment/{route_id}/decision-request",
    response_model=AcquisitionDecisionRequestResponse,
    operation_id="request_run_candidate_acquisition_experiment_decision",
    dependencies=[
        Depends(_CANDIDATE_EXPERIMENT_MUTATION_AUTHZ),
        Depends(_MUTATION_STEP_UP),
    ],
)
def request_run_candidate_acquisition_experiment_decision(
    run_id: str,
    route_id: str,
    body: CandidateExperimentRouteMutationRequest,
    request: Request,
    service: _Service,
) -> AcquisitionDecisionRequestResponse:
    tenant_id, cell_id, _ = _scope(request)
    set_authz_resource(
        request,
        tenant_id=tenant_id,
        kind="runtime.evidence.acquisition.candidate_experiment",
    )
    try:
        return service.request_candidate_experiment_decision(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=body,
            bound_permission=_candidate_experiment_bound_proof(request),
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.post(
    "/{run_id}/candidate-acquisition-experiment/{route_id}/execute",
    response_model=AcquisitionExecutionResponse,
    operation_id="execute_run_candidate_acquisition_experiment",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": AcquisitionExecutionResponse(
                        run_id="run-example",
                        route_id="sha256:" + "a" * 64,
                        job_id="candidate-experiment-job-example",
                        authority_decision_ref="sha256:" + "b" * 64,
                    ).model_dump(mode="json")
                }
            }
        }
    },
    dependencies=[
        Depends(_CANDIDATE_EXPERIMENT_EXECUTION_AUTHZ),
        Depends(_MUTATION_STEP_UP),
    ],
)
def execute_run_candidate_acquisition_experiment(
    run_id: str,
    route_id: str,
    body: CandidateExperimentRouteExecutionRequest,
    request: Request,
    service: _Service,
) -> AcquisitionExecutionResponse:
    """Queue a candidate experiment from its exact request and PA2 decision ref."""
    tenant_id, cell_id, principal = _scope(request)
    set_authz_resource(
        request,
        tenant_id=tenant_id,
        kind="runtime.evidence.acquisition.candidate_experiment",
    )
    _candidate_experiment_execution_bound_proof(request)
    try:
        return service.execute_candidate_experiment(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=body.request,
            decision_ref=body.decision_ref,
            request_id=ensure_request_id(request),
            principal=principal,
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.post(
    "/{run_id}/candidate-acquisition-experiment/{route_id}/reuse/decision-request",
    response_model=AcquisitionDecisionRequestResponse,
    operation_id="request_run_candidate_acquisition_experiment_reuse_decision",
)
def request_run_candidate_acquisition_experiment_reuse_decision(
    run_id: str,
    route_id: str,
    bound_permission: Annotated[
        BoundActionPermissionVerification, Depends(_CANDIDATE_EXPERIMENT_REUSE_AUTHZ)
    ],
    _step_up: Annotated[StepUpAssertionVerification, Depends(_MUTATION_STEP_UP)],
    body: CandidateExperimentReuseActionRequest,
    request: Request,
    service: _Service,
) -> AcquisitionDecisionRequestResponse:
    """Request a signed PA2 decision to reuse one exact prior candidate N5 result."""
    tenant_id, cell_id, _ = _scope(request)
    set_authz_resource(
        request,
        tenant_id=tenant_id,
        kind=CANDIDATE_EXPERIMENT_REUSE_RESOURCE_KIND,
    )
    try:
        return service.request_candidate_experiment_reuse_decision(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=body,
            bound_permission=bound_permission,
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.post(
    "/{run_id}/model-input-use/decision-request",
    response_model=ModelInputSuccessorDecisionResponse,
    operation_id="request_run_model_input_use_decision",
    dependencies=[Depends(_MODEL_INPUT_USE_MUTATION_AUTHZ), Depends(_MUTATION_STEP_UP)],
)
def request_run_model_input_use_decision(
    run_id: str,
    body: ModelInputSuccessorActionRequest,
    request: Request,
    service: _Service,
) -> ModelInputSuccessorDecisionResponse:
    """Request approval to use a selected active observation for candidate N5."""
    tenant_id, cell_id, _ = _scope(request)
    set_authz_resource(
        request, tenant_id=tenant_id, kind=f"{MODEL_INPUT_USE_RESOURCE_KIND}.request_bound"
    )
    proof = _MODEL_INPUT_USE_MUTATION_AUTHZ(request)
    if type(proof) is not BoundActionPermissionVerification:
        raise forbidden(
            "Candidate model-input use lacks its frozen request binding",
            code="authorization_binding_context_missing",
        )
    try:
        return service.request_model_input_use_decision(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=body,
            bound_permission=proof,
        )
    except AcquisitionActionServiceError as exc:
        _raise_service_error(exc)


@router.post(
    "/{run_id}/model-input-use/execute",
    response_model=AcquisitionExecutionResponse,
    operation_id="execute_run_model_input_use",
    dependencies=[Depends(_MODEL_INPUT_USE_EXECUTION_AUTHZ), Depends(_MUTATION_STEP_UP)],
)
def execute_run_model_input_use(
    run_id: str,
    body: ModelInputSuccessorExecutionRequest,
    request: Request,
    service: _Service,
) -> AcquisitionExecutionResponse:
    """Queue one exact approved use of an active candidate model input."""
    tenant_id, cell_id, principal = _scope(request)
    set_authz_resource(request, tenant_id=tenant_id, kind=MODEL_INPUT_USE_RESOURCE_KIND)
    if type(_MODEL_INPUT_USE_EXECUTION_AUTHZ(request)) is not BoundActionPermissionVerification:
        raise forbidden(
            "Candidate model-input use lacks its frozen request binding",
            code="authorization_binding_context_missing",
        )
    try:
        return service.execute_model_input_use(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=body,
            request_id=ensure_request_id(request),
            principal=principal,
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
