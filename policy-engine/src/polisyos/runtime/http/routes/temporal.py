"""Runtime temporal capability routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.contracts.runtime import TemporalCapabilitiesResponse
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    set_authz_resource,
)

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Query, Request
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Query, Request
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", Any)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/temporal", tags=["runtime-temporal"])


router = _build_router()
_RUNTIME_CONTEXT_DEPENDENCY = (
    Depends(get_runtime_api_context) if Depends is not None else None
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


__all__ = ["router"]
