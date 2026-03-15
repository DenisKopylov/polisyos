from __future__ import annotations

from polisyos.core.contracts.runtime import (
    GovernanceDebugResponse,
    NodeDebugResponse,
    RunCompareResponse,
    RunErrorsResponse,
    RunFeedbackResponse,
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

    @router.get(
        "/{run_id}/feedback",
        response_model=RunFeedbackResponse,
        operation_id="get_run_feedback",
    )
    def get_run_feedback(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunFeedbackResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_feedback",
        )
        feedback = ctx.feedback.get_run_feedback(run)
        return RunFeedbackResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            feedback=feedback,
        )

    @router.get(
        "/{left_run_id}/compare/{right_run_id}",
        response_model=RunCompareResponse,
        operation_id="get_run_compare",
    )
    def get_run_compare(
        left_run_id: str,
        right_run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunCompareResponse:
        left_run = ctx.run_index.get_run(left_run_id)
        right_run = ctx.run_index.get_run(right_run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=left_run)
        enforce_run_tenant_access(request, ctx=ctx, run=right_run)
        set_authz_resource(
            request,
            tenant_id=left_run.details.tenant_id,
            kind="runtime.run_compare",
        )
        compare = ctx.feedback.compare_runs(left_run, right_run)
        return RunCompareResponse(
            meta=build_meta(request, source_kinds=[left_run.source_kind, right_run.source_kind]),
            compare=compare,
        )
