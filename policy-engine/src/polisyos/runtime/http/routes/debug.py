"""Public routes debug module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.contracts.runtime import (
    GovernanceDebugResponse,
    NodeDebugResponse,
    RunCompareResponse,
    RunEquilibriaResponse,
    RunErrorsResponse,
    RunFeedbackResponse,
    SimulationResultCandidateResponse,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    set_authz_resource,
)
from polisyos.runtime.http.errors import conflict, forbidden, not_found
from polisyos.runtime.http.services.debug import SimulationResultProjectionError

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Request
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Request
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Request = cast("Any", Any)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/debug/runs", tags=["runtime-debug"])


router = _build_router()


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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
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
        "/{run_id}/nodes/{alias}/simulation-result",
        response_model=SimulationResultCandidateResponse,
        operation_id="get_node_simulation_result_candidate",
    )
    def get_node_simulation_result_candidate(
        run_id: str,
        alias: str,
        request: Request,
        artifact_id: str | None = None,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> SimulationResultCandidateResponse:
        """Read a verified candidate result without opening generic authority surfaces."""
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.simulation_result_candidate",
        )
        try:
            debug_view = ctx.debug.get_simulation_result_candidate(
                run,
                alias=alias,
                artifact_id=artifact_id,
            )
        except KeyError as exc:
            raise not_found(
                "The named workflow node was not found in the persisted run",
                code="simulation_result_node_not_found",
            ) from exc
        except SimulationResultProjectionError as exc:
            raise conflict(exc.detail, code=exc.code) from exc
        artifact_id_text = str(debug_view.artifact_ref.artifact_id)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.simulation_result_candidate",
            artifact_id=artifact_id_text,
        )
        record_data_access_audit(
            request,
            resource_id=f"{run_id}:{alias}:{artifact_id_text}",
            resource_kind="runtime.simulation_result_candidate",
            tenant_id=run.details.tenant_id,
            metadata={
                "run_id": run_id,
                "node_alias": alias,
                "artifact_id": artifact_id_text,
                "projection_class": debug_view.projection_class,
            },
        )
        return SimulationResultCandidateResponse(
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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
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
        "/{run_id}/equilibria",
        response_model=RunEquilibriaResponse,
        operation_id="get_run_equilibria",
    )
    def get_run_equilibria(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunEquilibriaResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_equilibria",
        )
        equilibria = ctx.feedback.get_run_equilibria(run)
        return RunEquilibriaResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            equilibria=equilibria,
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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunCompareResponse:
        left_run = ctx.run_index.get_run(left_run_id)
        right_run = ctx.run_index.get_run(right_run_id)
        if left_run.details.tenant_id != right_run.details.tenant_id:
            raise forbidden(
                "Cross-tenant run comparison requires an explicit privileged capability",
                code="cross_tenant_compare_forbidden",
            )
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
