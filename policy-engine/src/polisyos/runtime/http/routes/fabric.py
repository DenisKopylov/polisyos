"""Runtime routes for product-facing Fabric integration payloads."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - FastAPI inspects runtime annotations.
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.contracts.runtime import (
    FabricImpactAnalysisRequest,
    FabricImpactAnalysisResponse,
    FabricQualityBatchResponse,
    FabricQualityTrustBatchRequest,
    FabricReplayRunResponse,
    FabricSourceScorecardsResponse,
    FabricTrustBatchResponse,
    TemporalScope,
    TemporalSurfaceSupport,
)
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    set_authz_resource,
)
from polisyos.runtime.http.permissions import RuntimePermission

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Query, Request, Response

    from polisyos.runtime.http.services.run_index import IndexedRunRecord
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Query, Request, Response
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", None)
        Response = cast("Any", None)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/fabric", tags=["runtime-fabric"])


router = _build_router()
_RUNTIME_CONTEXT_DEPENDENCY = Depends(get_runtime_api_context) if Depends is not None else None
_VALID_AT_QUERY = Query(default=None) if Query is not None else None
_TX_AT_QUERY = Query(default=None) if Query is not None else None
_T_QUERY = Query(default=None, alias="t") if Query is not None else None
_BRANCH_QUERY = Query(default=None) if Query is not None else None
_SNAPSHOT_ID_QUERY = Query(default=None) if Query is not None else None
_SCENARIO_ID_QUERY = Query(default=None) if Query is not None else None
_FABRIC_QUALITY_BATCH_AUTHZ = require_action_permission(
    RuntimePermission.FABRIC_QUALITY_READ,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_PARENT_OR_REQUEST_COMPOSITE,
        resource_kind="runtime.fabric.quality_batch",
        parent_field="run_id",
        selector_fields=("decision_data_ids",),
        parent_required=True,
    ),
)
_FABRIC_TRUST_BATCH_AUTHZ = require_action_permission(
    RuntimePermission.FABRIC_TRUST_READ,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_PARENT_OR_REQUEST_COMPOSITE,
        resource_kind="runtime.fabric.trust_batch",
        parent_field="run_id",
        selector_fields=("decision_data_ids",),
        parent_required=True,
    ),
)
_FABRIC_IMPACT_AUTHZ = require_action_permission(
    RuntimePermission.FABRIC_IMPACT_ANALYZE,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_PARENT_OR_REQUEST_COMPOSITE,
        resource_kind="runtime.fabric.impact",
        parent_field="run_id",
        selector_fields=("lineage_ids", "source_contract_ids"),
    ),
)


@router.get(
    "/source-scorecards",
    response_model=FabricSourceScorecardsResponse,
    operation_id="get_fabric_source_scorecards",
)
def get_fabric_source_scorecards(
    request: Request,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> FabricSourceScorecardsResponse:
    set_authz_resource(request, tenant_id=None, kind="runtime.fabric_source_scorecards")
    response = ctx.fabric.build_source_scorecards_response(meta=build_meta(request))
    record_data_access_audit(
        request,
        resource_id="fabric.source_scorecards",
        metadata={"scorecard_count": response.count},
    )
    return response


@router.post(
    "/quality/batch",
    response_model=FabricQualityBatchResponse,
    operation_id="get_fabric_quality_batch",
    dependencies=[Depends(_FABRIC_QUALITY_BATCH_AUTHZ)],
)
def get_fabric_quality_batch(
    body: FabricQualityTrustBatchRequest,
    request: Request,
    response: Response,
    valid_at: datetime | None = _VALID_AT_QUERY,
    tx_at: datetime | None = _TX_AT_QUERY,
    t: datetime | None = _T_QUERY,
    branch: str | None = _BRANCH_QUERY,
    snapshot_id: str | None = _SNAPSHOT_ID_QUERY,
    scenario_id: str | None = _SCENARIO_ID_QUERY,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> FabricQualityBatchResponse:
    run = ctx.run_index.get_run(body.run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_run_temporal_scope(
        ctx,
        run=run,
        body_scope=body.temporal_scope,
        response=response,
        surface="run_fabric_decision_data",
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.fabric_quality_batch",
        artifact_id=run.run_id,
    )
    result = ctx.fabric.build_quality_batch_response(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run=run,
        temporal_scope=temporal_scope,
        decision_data_ids=body.decision_data_ids,
    )
    record_data_access_audit(
        request,
        resource_id=run.run_id,
        tenant_id=run.details.tenant_id,
        metadata={"decision_data_count": len(result.quality_refs)},
    )
    return result


@router.post(
    "/trust/batch",
    response_model=FabricTrustBatchResponse,
    operation_id="get_fabric_trust_batch",
    dependencies=[Depends(_FABRIC_TRUST_BATCH_AUTHZ)],
)
def get_fabric_trust_batch(
    body: FabricQualityTrustBatchRequest,
    request: Request,
    response: Response,
    valid_at: datetime | None = _VALID_AT_QUERY,
    tx_at: datetime | None = _TX_AT_QUERY,
    t: datetime | None = _T_QUERY,
    branch: str | None = _BRANCH_QUERY,
    snapshot_id: str | None = _SNAPSHOT_ID_QUERY,
    scenario_id: str | None = _SCENARIO_ID_QUERY,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> FabricTrustBatchResponse:
    run = ctx.run_index.get_run(body.run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_run_temporal_scope(
        ctx,
        run=run,
        body_scope=body.temporal_scope,
        response=response,
        surface="run_fabric_decision_data",
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.fabric_trust_batch",
        artifact_id=run.run_id,
    )
    result = ctx.fabric.build_trust_batch_response(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run=run,
        temporal_scope=temporal_scope,
        decision_data_ids=body.decision_data_ids,
    )
    record_data_access_audit(
        request,
        resource_id=run.run_id,
        tenant_id=run.details.tenant_id,
        metadata={"decision_data_count": len(result.trust_refs)},
    )
    return result


@router.get(
    "/runs/{run_id}/replay",
    response_model=FabricReplayRunResponse,
    operation_id="get_fabric_run_replay",
)
def get_fabric_run_replay(
    run_id: str,
    request: Request,
    response: Response,
    valid_at: datetime | None = _VALID_AT_QUERY,
    tx_at: datetime | None = _TX_AT_QUERY,
    t: datetime | None = _T_QUERY,
    branch: str | None = _BRANCH_QUERY,
    snapshot_id: str | None = _SNAPSHOT_ID_QUERY,
    scenario_id: str | None = _SCENARIO_ID_QUERY,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> FabricReplayRunResponse:
    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_run_temporal_scope(
        ctx,
        run=run,
        body_scope=None,
        response=response,
        surface="run_fabric_decision_data",
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.fabric_run_replay",
        artifact_id=run.run_id,
    )
    result = ctx.fabric.build_replay_response(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run=run,
        temporal_scope=temporal_scope,
    )
    record_data_access_audit(
        request,
        resource_id=run.run_id,
        tenant_id=run.details.tenant_id,
        metadata={"status_counts": result.status_counts},
    )
    return result


@router.post(
    "/impact",
    response_model=FabricImpactAnalysisResponse,
    operation_id="analyze_fabric_impact",
    dependencies=[Depends(_FABRIC_IMPACT_AUTHZ)],
)
def analyze_fabric_impact(
    body: FabricImpactAnalysisRequest,
    request: Request,
    response: Response,
    valid_at: datetime | None = _VALID_AT_QUERY,
    tx_at: datetime | None = _TX_AT_QUERY,
    t: datetime | None = _T_QUERY,
    branch: str | None = _BRANCH_QUERY,
    snapshot_id: str | None = _SNAPSHOT_ID_QUERY,
    scenario_id: str | None = _SCENARIO_ID_QUERY,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> FabricImpactAnalysisResponse:
    run = ctx.run_index.get_run(body.run_id) if body.run_id else None
    if run is not None:
        enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_run_temporal_scope(
        ctx,
        run=run,
        body_scope=body.temporal_scope,
        response=response,
        surface="run_fabric_decision_data",
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id if run is not None else None,
        kind="runtime.fabric_impact",
        artifact_id=run.run_id if run is not None else None,
    )
    result = ctx.fabric.build_impact_response(
        meta=build_meta(request, source_kinds=[run.source_kind] if run is not None else []),
        request=body,
        run=run,
        temporal_scope=temporal_scope,
    )
    record_data_access_audit(
        request,
        resource_id=run.run_id if run is not None else "fabric.impact",
        tenant_id=run.details.tenant_id if run is not None else None,
        metadata=result.summary,
    )
    return result


def _resolve_run_temporal_scope(
    ctx: RuntimeApiContext,
    *,
    run: IndexedRunRecord | None,
    body_scope: TemporalScope | None,
    response: Response,
    surface: TemporalSurfaceSupport,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
) -> TemporalScope | None:
    query_scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    scope = body_scope or query_scope
    if run is not None:
        scope = ctx.temporal.materialize_run_scope(run, scope)
        ctx.temporal.validate_run_scope(run, scope, surface=surface)
        response.headers["ETag"] = ctx.temporal.response_etag(
            run_id=run.run_id,
            surface=surface,
            scope=scope,
        )
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(scope)
    response.headers.setdefault("Vary", "Accept, Authorization")
    return scope


__all__ = ["router"]
