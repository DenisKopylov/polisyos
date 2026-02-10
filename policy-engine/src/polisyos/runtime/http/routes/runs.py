from __future__ import annotations

from datetime import datetime

from polisyos.core.contracts.runtime import (
    RunDetailsResponse,
    RunLineageResponse,
    RunNodesResponse,
    RunsListResponse,
    RunTimelineResponse,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_access_scope,
    get_runtime_api_context,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Query, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/runs", tags=["runtime-runs"]) if APIRouter else None


if router is not None:

    @router.get("", response_model=RunsListResponse, operation_id="list_runs")
    def list_runs(
        request: Request,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        status: str | None = Query(default=None),
        from_ts: datetime | None = Query(default=None),  # noqa: B008
        to_ts: datetime | None = Query(default=None),  # noqa: B008
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunsListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.run_list",
        )
        scope = get_access_scope(request)
        runs, page = ctx.run_index.list_runs(
            limit=limit,
            cursor=cursor,
            status=status,
            from_ts=from_ts,
            to_ts=to_ts,
            tenant_id=scope.tenant_id if scope else None,
        )
        source_kinds = [run.source_kind for run in runs]
        return RunsListResponse(
            meta=build_meta(request, source_kinds=source_kinds),
            page=page,
            runs=runs,
        )

    @router.get("/{run_id}", response_model=RunDetailsResponse, operation_id="get_run_details")
    def get_run_details(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunDetailsResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id)
                if run.details.manifest_ref
                else None
            ),
        )
        return RunDetailsResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run=run.details,
        )

    @router.get(
        "/{run_id}/timeline",
        response_model=RunTimelineResponse,
        operation_id="get_run_timeline",
    )
    def get_run_timeline(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunTimelineResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_timeline",
        )
        timeline = ctx.timeline.build_for_run(run).timeline
        return RunTimelineResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            timeline=timeline,
        )

    @router.get("/{run_id}/nodes", response_model=RunNodesResponse, operation_id="get_run_nodes")
    def get_run_nodes(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunNodesResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_nodes",
        )
        nodes = ctx.debug.list_run_nodes(run)
        return RunNodesResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            source_kind=run.source_kind,
            nodes=nodes,
        )

    @router.get(
        "/{run_id}/lineage",
        response_model=RunLineageResponse,
        operation_id="get_run_lineage",
    )
    def get_run_lineage(
        run_id: str,
        request: Request,
        root_artifact_id: list[str] | None = Query(default=None),  # noqa: B008
        max_depth: int | None = Query(default=None, ge=1, le=256),
        max_nodes: int | None = Query(default=None, ge=1, le=20000),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunLineageResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_lineage",
        )

        root_ids = ctx.run_index.resolve_root_artifact_ids(
            run,
            requested_root_ids=root_artifact_id or None,
        )
        if not root_ids:
            raise bad_request(
                "No root artifacts available for lineage resolution",
                code="lineage_roots_missing",
            )

        lineage = ctx.lineage.build_for_artifact_ids(
            root_ids,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
        return RunLineageResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            lineage=lineage,
        )
