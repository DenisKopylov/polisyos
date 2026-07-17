"""HTTP producers for governed artifact projections and realtime channel contracts."""

from __future__ import annotations

import os
from datetime import datetime  # noqa: TC003 - FastAPI resolves this annotation at runtime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

from polisyos.runtime.http.dependencies import set_authz_resource
from polisyos.runtime.http.errors import conflict
from polisyos.runtime.http.services.governed_projections import (
    CHANNEL_REGISTRY,
    ChannelRegistryResponse,
    GovernedProjectionPacket,
    GovernedProjectionService,
    ProjectionCatalogResponse,
    ProjectionId,
    ReplayPinMismatchError,
)

if TYPE_CHECKING:
    from fastapi import APIRouter, Query, Request
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Query, Request
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", Any)


def _build_router() -> APIRouter | None:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        return None
    return APIRouter(prefix="/api/v1/exports", tags=["runtime-exports"])


router = _build_router()


@lru_cache(maxsize=1)
def _get_projection_service() -> GovernedProjectionService:
    configured_root = os.getenv("POLISYOS_GOVERNED_ARTIFACT_ROOT")
    repository_root = (
        Path(configured_root) if configured_root else Path(__file__).resolve().parents[5]
    )
    return GovernedProjectionService(repository_root)


if router is not None:

    @router.get(
        "/governed-projections",
        response_model=ProjectionCatalogResponse,
        operation_id="list_governed_projections",
        summary="List governed artifact projection contracts",
    )
    def list_governed_projections(request: Request) -> ProjectionCatalogResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.governed_projection_catalog",
        )
        return ProjectionCatalogResponse(projections=_get_projection_service().catalog())

    @router.get(
        "/governed-projections/{projection_id}",
        response_model=GovernedProjectionPacket,
        operation_id="get_governed_projection",
        summary="Get a replayable governed artifact projection",
    )
    def get_governed_projection(
        projection_id: ProjectionId,
        request: Request,
        artifact_content_hash: str | None = Query(default=None, max_length=128),
        projection_hash: str | None = Query(default=None, max_length=128),
        source_as_of: Annotated[datetime | None, Query()] = None,
    ) -> GovernedProjectionPacket:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind=f"runtime.governed_projection.{projection_id.value}",
        )
        try:
            return _get_projection_service().get(
                projection_id,
                artifact_content_hash=artifact_content_hash,
                projection_hash=projection_hash,
                source_as_of=source_as_of,
            )
        except ReplayPinMismatchError as exc:
            raise conflict(
                str(exc),
                code="governed_projection_replay_pin_mismatch",
                extensions={
                    "field": exc.field,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
            ) from exc

    @router.get(
        "/channel-registry",
        response_model=ChannelRegistryResponse,
        operation_id="get_runtime_channel_registry",
        summary="Get governed non-OpenAPI runtime channels",
    )
    def get_runtime_channel_registry(request: Request) -> ChannelRegistryResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.channel_registry",
        )
        return ChannelRegistryResponse(channels=CHANNEL_REGISTRY)


__all__ = ["router"]
