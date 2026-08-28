"""Runtime temporal capability routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.contracts.runtime import (
    EpochStalenessProjectionResponse,
    TemporalCapabilitiesResponse,
    TemporalScope,
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
from polisyos.runtime.http.routes._export_replay import bind_export_replay_or_conflict
from polisyos.runtime.http.services.export_replay import EXPORT_REPLAY_RESPONSE_HEADERS

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
    return APIRouter(prefix="/api/v1/temporal", tags=["runtime-temporal"])


router = _build_router()
_RUNTIME_CONTEXT_DEPENDENCY = (
    Depends(get_runtime_api_context) if Depends is not None else None
)
_GET_EPOCH_STALENESS_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.epoch_staleness",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)


@router.get(
    "/capabilities",
    response_model=TemporalCapabilitiesResponse,
    operation_id="get_temporal_capabilities",
)
def get_temporal_capabilities(
    request: Request,
    run_id: str | None = Query(default=None),
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> TemporalCapabilitiesResponse:
    run = ctx.run_index.get_run(run_id) if run_id else None
    source_kinds = []
    tenant_id = None
    if run is not None:
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        source_kinds.append(run.source_kind)
        tenant_id = run.details.tenant_id
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="runtime.temporal_capabilities",
        )
    else:
        set_authz_resource(
            request,
            tenant_id=None,
            kind="runtime.temporal_capabilities",
        )

    capabilities = ctx.temporal.build_capabilities(run=run)
    record_data_access_audit(
        request,
        resource_id=run_id or "runtime.temporal_capabilities",
        tenant_id=tenant_id,
        metadata={"supported_surface_count": len(capabilities.surfaces)},
    )
    return TemporalCapabilitiesResponse(
        meta=build_meta(request, source_kinds=source_kinds),
        capabilities=capabilities,
    )


@router.get(
    "/runs/{run_id}/epoch-staleness",
    response_model=EpochStalenessProjectionResponse,
    operation_id="get_run_epoch_staleness",
    responses={200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS}},
    dependencies=[Depends(_GET_EPOCH_STALENESS_AUTHZ)],
)
def get_run_epoch_staleness(
    run_id: str,
    request: Request,
    response: Response,
    valid_at: datetime | None = Query(default=None),  # noqa: B008
    tx_at: datetime | None = Query(default=None),  # noqa: B008
    branch: str | None = Query(default=None),
    snapshot_id: str | None = Query(default=None),
    scenario_id: str | None = Query(default=None),
    export_projection_hash: str | None = Query(
        default=None,
        max_length=128,
    ),
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> EpochStalenessProjectionResponse:
    """Return replay-bound epoch and staleness chrome for one tenant-owned run."""

    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    ) or TemporalScope()
    ctx.temporal.validate_run_scope(run, scope, surface="epoch_staleness")
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.run.epoch_staleness",
        artifact_id=(
            str(run.decision_packet_ref.artifact_id)
            if run.decision_packet_ref is not None
            else None
        ),
    )
    projection = ctx.temporal.build_epoch_staleness_projection(
        run=run,
        scope=scope,
        observed_at=datetime.now(UTC),
    )
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(scope)
    bind_export_replay_or_conflict(
        request=request,
        response=response,
        semantic_projection={
            "projection_semantic_hash": projection.projection_semantic_hash,
        },
        as_of=projection.observed_at,
        requested_projection_hash=export_projection_hash,
    )
    record_data_access_audit(
        request,
        resource_id=run_id,
        tenant_id=run.details.tenant_id,
        outcome="epoch_staleness_projected",
        metadata={
            "status": projection.status,
            "predicate_provenance": projection.predicate_provenance,
        },
    )
    return EpochStalenessProjectionResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        projection=projection,
    )


__all__ = ["router"]
