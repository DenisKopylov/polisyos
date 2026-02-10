from __future__ import annotations

from polisyos.core.contracts.runtime import (
    GovernanceDebugResponse,
    NodeDebugResponse,
    RunErrorsResponse,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_runtime_api_context,
    set_authz_resource,
)

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/debug/runs", tags=["runtime-debug"]) if APIRouter else None


if router is not None:

    @router.get(
        "/{run_id}/nodes/{alias}",
        response_model=NodeDebugResponse,
        operation_id="get_node_debug",
    )
    def get_node_debug(
        run_id: str,
        alias: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> NodeDebugResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.node_debug",
        )
        debug_view = ctx.debug.get_node_debug(run, alias=alias)
        return NodeDebugResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            debug=debug_view,
        )

    @router.get(
        "/{run_id}/governance",
        response_model=GovernanceDebugResponse,
        operation_id="get_governance_debug",
    )
    def get_governance_debug(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> GovernanceDebugResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.governance_debug",
        )
        debug_view = ctx.debug.get_governance_debug(run)
        return GovernanceDebugResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            debug=debug_view,
        )

    @router.get("/{run_id}/errors", response_model=RunErrorsResponse, operation_id="get_run_errors")
    def get_run_errors(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunErrorsResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_errors",
        )
        errors = ctx.debug.get_run_errors(run)
        return RunErrorsResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            errors=errors,
        )
