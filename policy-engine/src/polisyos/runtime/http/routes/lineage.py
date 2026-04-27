"""Runtime lineage lookup routes."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - FastAPI inspects runtime annotations.
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.runtime import (
    LineageBatchRequest,
    LineageBatchResponse,
    LineageExportResponse,
    LineageGraphView,
    LineageResponse,
    TemporalScope,
    VerificationMetadata,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_artifact_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Query, Request, Response
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Query, Request, Response
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", Any)
        Response = cast("Any", Any)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/lineage", tags=["runtime-lineage"])


router = _build_router()


if router is not None:

    @router.get(
        "/{lineage_id}",
        response_model=LineageResponse,
        operation_id="get_lineage",
    )
    def get_lineage(
        lineage_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageResponse:
        temporal_scope = _resolve_lineage_temporal_scope(
            ctx,
            lineage_id=lineage_id,
            response=response,
            surface="lineage",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        tenant_id = _enforce_lineage_scope(lineage_id, request=request, ctx=ctx)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.lineage",
            artifact_id=lineage_id,
        )
        lineage = _build_runtime_lineage(ctx, lineage_id, temporal_scope=temporal_scope)
        record_data_access_audit(
            request,
            resource_id=lineage_id,
            tenant_id=tenant_id,
            metadata={"status": lineage.status, "node_count": len(lineage.nodes)},
        )
        return LineageResponse(
            meta=build_meta(request),
            temporal_scope=temporal_scope,
            lineage=lineage,
        )

    @router.post(
        "/batch",
        response_model=LineageBatchResponse,
        operation_id="get_lineage_batch",
    )
    def get_lineage_batch(
        body: LineageBatchRequest,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageBatchResponse:
        temporal_scope = _resolve_lineage_temporal_scope(
            ctx,
            lineage_id="lineage.batch",
            response=response,
            surface="lineage_batch",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        tenant_ids = [
            tenant_id
            for lineage_id in body.lineage_ids
            if (tenant_id := _enforce_lineage_scope(lineage_id, request=request, ctx=ctx))
        ]
        set_authz_resource(
            request,
            tenant_id=tenant_ids[0] if tenant_ids else getattr(request.state, "tenant_id", None),
            kind="runtime.lineage_batch",
        )
        lineages = _build_runtime_lineage_batch(
            ctx,
            body.lineage_ids,
            temporal_scope=temporal_scope,
        )
        record_data_access_audit(
            request,
            resource_id="lineage.batch",
            tenant_id=tenant_ids[0] if tenant_ids else getattr(request.state, "tenant_id", None),
            metadata={"count": len(lineages)},
        )
        return LineageBatchResponse(
            meta=build_meta(request),
            temporal_scope=temporal_scope,
            lineages=lineages,
        )

    @router.get(
        "/{lineage_id}/export/openlineage",
        response_model=LineageExportResponse,
        operation_id="export_lineage_openlineage",
    )
    def export_lineage_openlineage(
        lineage_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageExportResponse:
        return _export_lineage(
            lineage_id,
            format_name="openlineage",
            request=request,
            response=response,
            ctx=ctx,
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )

    @router.get(
        "/{lineage_id}/export/prov",
        response_model=LineageExportResponse,
        operation_id="export_lineage_prov",
    )
    def export_lineage_prov(
        lineage_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageExportResponse:
        return _export_lineage(
            lineage_id,
            format_name="prov",
            request=request,
            response=response,
            ctx=ctx,
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )


def _export_lineage(
    lineage_id: str,
    *,
    format_name: str,
    request: Request,
    response: Response,
    ctx: RuntimeApiContext,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
) -> LineageExportResponse:
    temporal_scope = _resolve_lineage_temporal_scope(
        ctx,
        lineage_id=lineage_id,
        response=response,
        surface=f"lineage_export.{format_name}",
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    tenant_id = _enforce_lineage_scope(lineage_id, request=request, ctx=ctx)
    set_authz_resource(
        request,
        tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
        kind=f"runtime.lineage_export.{format_name}",
        artifact_id=lineage_id,
    )
    try:
        if ctx.scenarios.is_scenario_lineage(lineage_id):
            payload = ctx.scenarios.export_lineage(lineage_id, format_name=format_name)
        else:
            payload = ctx.lineage.export_runtime_lineage(lineage_id, format_name=format_name)
    except ValueError as exc:
        raise bad_request(str(exc), code="unsupported_lineage_export") from exc
    record_data_access_audit(
        request,
        resource_id=lineage_id,
        tenant_id=tenant_id,
        metadata={"format": format_name},
    )
    return LineageExportResponse(
        meta=build_meta(request),
        temporal_scope=temporal_scope,
        lineage_id=lineage_id,
        format=cast("Any", format_name),
        payload=payload,
    )


def _build_runtime_lineage(
    ctx: RuntimeApiContext,
    lineage_id: str,
    *,
    temporal_scope: TemporalScope | None = None,
) -> LineageGraphView:
    if ctx.scenarios.is_scenario_lineage(lineage_id):
        lineage = ctx.scenarios.build_lineage(lineage_id)
    else:
        lineage = ctx.lineage.build_runtime_lineage(lineage_id)
    return _with_trust_metadata(lineage, temporal_scope=temporal_scope)


def _build_runtime_lineage_batch(
    ctx: RuntimeApiContext,
    lineage_ids: list[str],
    *,
    temporal_scope: TemporalScope | None = None,
) -> list[LineageGraphView]:
    scenario_lineage_by_id: dict[str, LineageGraphView] = {}
    runtime_ids: list[str] = []
    for lineage_id in lineage_ids:
        if ctx.scenarios.is_scenario_lineage(lineage_id):
            if lineage_id not in scenario_lineage_by_id:
                scenario_lineage_by_id[lineage_id] = ctx.scenarios.build_lineage(lineage_id)
        elif lineage_id not in runtime_ids:
            runtime_ids.append(lineage_id)

    runtime_lineage_by_id = {
        lineage.id: lineage for lineage in ctx.lineage.build_runtime_lineage_batch(runtime_ids)
    }
    lineages: list[LineageGraphView] = []
    for lineage_id in lineage_ids:
        if lineage_id in scenario_lineage_by_id:
            lineage = scenario_lineage_by_id[lineage_id]
        else:
            lineage = runtime_lineage_by_id[lineage_id]
        lineages.append(_with_trust_metadata(lineage, temporal_scope=temporal_scope))
    return lineages


def _with_trust_metadata(
    lineage: LineageGraphView,
    *,
    temporal_scope: TemporalScope | None,
) -> LineageGraphView:
    dispute_status = "disputed" if lineage.status == "disputed" else "none"
    verification_method = (
        "lineage_id_resolution"
        if lineage.status == "untraced"
        else "lineage_hash_match"
    )
    return lineage.model_copy(
        update={
            "trust_metadata": VerificationMetadata(
                hash=lineage.hash,
                verification_status=lineage.status,
                verified_by=(
                    None
                    if lineage.status == "untraced"
                    else "PolicyOSLineageVerifier@1.0"
                ),
                verified_at=_latest_lineage_timestamp(lineage),
                verification_method=verification_method,
                freshness=lineage.freshness,
                dispute_status=dispute_status,
                temporal_scope=temporal_scope,
            )
        }
    )


def _latest_lineage_timestamp(lineage: LineageGraphView) -> datetime | None:
    timestamps = [node.timestamp for node in lineage.nodes if node.timestamp is not None]
    if not timestamps:
        return None
    return max(timestamps)


def _resolve_lineage_temporal_scope(
    ctx: RuntimeApiContext,
    *,
    lineage_id: str,
    response: Response,
    surface: str,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
) -> TemporalScope | None:
    scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(scope)
    response.headers["ETag"] = ctx.temporal.response_etag(
        run_id=lineage_id,
        surface=surface,
        scope=scope,
    )
    response.headers.setdefault("Vary", "Accept, Authorization")
    return scope


def _enforce_lineage_scope(
    lineage_id: str,
    *,
    request: Request,
    ctx: RuntimeApiContext,
) -> str | None:
    artifact_id = _parse_artifact_lineage_id(lineage_id)
    if artifact_id is None:
        return getattr(request.state, "tenant_id", None)
    return enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=artifact_id)


def _parse_artifact_lineage_id(lineage_id: str) -> ArtifactID | None:
    candidate = lineage_id.removeprefix("artifact:")
    try:
        return ArtifactID.model_validate(candidate)
    except (TypeError, ValueError):
        return None
