"""Control-plane routes — write operations for launching runs and ingesting data."""

from __future__ import annotations

from polisyos.core.contracts.control import (
    CacheStatusResponse,
    ConnectorsListResponse,
    IngestRequest,
    IngestResponse,
    NaturalLanguageRunRequest,
    RunLaunchResponse,
    WorkflowRunRequest,
)
from polisyos.runtime.http.dependencies import (
    build_meta,
    ensure_request_id,
    get_runtime_api_context,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/control", tags=["control-plane"]) if APIRouter else None


def _get_control_service(request: Request):
    """Lazy-init control service from RuntimeApiContext."""
    from polisyos.runtime.http.services.control import ControlPlaneService

    ctx = get_runtime_api_context(request)
    # Cache on app state to avoid re-creating
    svc = getattr(request.app.state, "_control_service", None)
    if svc is None:
        svc = ControlPlaneService(
            cas_root=ctx.cas_root,
            core_runs_root=ctx.core_runs_root,
        )
        request.app.state._control_service = svc
    return svc


if router is not None:

    @router.post(
        "/runs",
        response_model=RunLaunchResponse,
        operation_id="launch_run",
        summary="Launch a workflow run",
    )
    def launch_run(
        body: WorkflowRunRequest,
        request: Request,
    ) -> RunLaunchResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.launch_run",
        )
        # Validate that at least one data source is provided
        ds = body.data_source
        if not ds.data_snapshot_ref and not ds.input_bindings_ref and not ds.data_view_request_ref:
            raise bad_request(
                "At least one data source must be provided",
                code="missing_data_source",
            )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.launch_workflow_run(body, request_id=request_id)

    @router.post(
        "/runs/nl",
        response_model=RunLaunchResponse,
        operation_id="launch_nl_run",
        summary="Launch a natural-language run via agent circuit",
    )
    async def launch_nl_run(
        body: NaturalLanguageRunRequest,
        request: Request,
    ) -> RunLaunchResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.launch_nl_run",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return await control.launch_nl_run(body, request_id=request_id)

    @router.post(
        "/data/ingest",
        response_model=IngestResponse,
        operation_id="ingest_data",
        summary="Trigger data collection from connectors",
    )
    def ingest_data(
        body: IngestRequest,
        request: Request,
    ) -> IngestResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.ingest_data",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.run_data_ingestion(body, request_id=request_id)

    @router.get(
        "/data/connectors",
        response_model=ConnectorsListResponse,
        operation_id="list_connectors",
        summary="List available data connectors",
    )
    def list_connectors(
        request: Request,
    ) -> ConnectorsListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.list_connectors",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_connectors(request_id=request_id)

    @router.get(
        "/data/cache",
        response_model=CacheStatusResponse,
        operation_id="get_cache_status",
        summary="Get data cache status",
    )
    def get_cache_status(
        request: Request,
    ) -> CacheStatusResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.cache_status",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.get_cache_status(request_id=request_id)


__all__ = ["router"]
