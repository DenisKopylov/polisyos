"""HTTP producers for governed artifact projections and realtime channel contracts."""

from __future__ import annotations

import os
from datetime import datetime  # noqa: TC003 - FastAPI resolves this annotation at runtime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.dependencies import (
    get_runtime_api_context,
    require_access_scope,
    set_authz_resource,
)
from polisyos.runtime.http.errors import conflict
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.confidence_ledger_risk_spend_contracts import (
    ConfidenceLedgerRiskSpendPacket,
)
from polisyos.runtime.http.services.confidence_ledger_risk_spend_projection import (
    ConfidenceLedgerRiskSpendProjectionService,
)
from polisyos.runtime.http.services.cycle_board_projection import (
    CycleBoardExportResponse,
    CycleBoardProjectionPacket,
    CycleBoardProjectionService,
    CycleBoardReplayConflictError,
)
from polisyos.runtime.http.services.governed_projections import (
    CHANNEL_REGISTRY,
    ChannelRegistryResponse,
    GovernedProjectionPacket,
    GovernedProjectionService,
    ProjectionCatalogResponse,
    ProjectionId,
    ReplayPinMismatchError,
)
from polisyos.runtime.http.services.run_paper_projection import RunPaperProjectionService

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


def _build_router() -> APIRouter | None:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        return None
    return APIRouter(prefix="/api/v1/exports", tags=["runtime-exports"])


router = _build_router()


def _repository_root() -> Path:
    configured_root = os.getenv("POLISYOS_GOVERNED_ARTIFACT_ROOT")
    return Path(configured_root) if configured_root else Path(__file__).resolve().parents[5]


@lru_cache(maxsize=1)
def _get_projection_service() -> GovernedProjectionService:
    return GovernedProjectionService(_repository_root())


def _get_cycle_board_projection_service(request: Request) -> CycleBoardProjectionService:
    context = get_runtime_api_context(request)
    access_scope = require_access_scope(request)
    return CycleBoardProjectionService(
        projection_service=_get_projection_service(),
        run_index=context.run_index,
        repository_root=_repository_root(),
        stage_trace_resolver=RunPaperProjectionService(
            store=context.store,
            core_runs_root=context.core_runs_root,
            tenant_id=access_scope.tenant_id,
        ),
    )


@lru_cache(maxsize=1)
def _get_confidence_ledger_risk_spend_projection_service(
) -> ConfidenceLedgerRiskSpendProjectionService:
    return ConfidenceLedgerRiskSpendProjectionService(_repository_root())


_CYCLE_BOARD_EXPORT_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.governed_projection.depth_n_cycle_board",
        allow_empty_body=True,
    ),
)

_CONFIDENCE_LEDGER_RISK_SPEND_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.governed_projection.confidence_ledger_risk_spend",
        allow_empty_body=True,
    ),
)


if router is not None:
    _CYCLE_BOARD_SERVICE_DEPENDENCY = Depends(_get_cycle_board_projection_service)
    _CONFIDENCE_LEDGER_RISK_SPEND_SERVICE_DEPENDENCY = Depends(
        _get_confidence_ledger_risk_spend_projection_service
    )

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
        "/governed-projections/depth-n-cycle-board",
        response_model=CycleBoardExportResponse,
        operation_id="get_depth_n_cycle_board_projection",
        summary="Get the reviewer Cycle Board or replay its raw owner packet",
        dependencies=[Depends(_CYCLE_BOARD_EXPORT_AUTHZ)],
    )
    def get_depth_n_cycle_board_projection(
        request: Request,
        replay_target: Literal["raw_v1", "composed_v2"] | None = Query(default=None),
        artifact_content_hash: str | None = Query(default=None, max_length=128),
        projection_hash: str | None = Query(default=None, max_length=128),
        source_dependency_hash: str | None = Query(default=None, max_length=128),
        source_as_of: Annotated[datetime | None, Query()] = None,
        projection_rule_version: str | None = Query(default=None, max_length=128),
        composition_manifest_hash: str | None = Query(default=None, max_length=128),
        service: CycleBoardProjectionService = _CYCLE_BOARD_SERVICE_DEPENDENCY,
    ) -> CycleBoardExportResponse | Response:
        try:
            result = service.get(
                replay_target=replay_target,
                artifact_content_hash=artifact_content_hash,
                projection_hash=projection_hash,
                source_dependency_hash=source_dependency_hash,
                source_as_of=source_as_of,
                projection_rule_version=projection_rule_version,
                composition_manifest_hash=composition_manifest_hash,
            )
        except CycleBoardReplayConflictError as exc:
            raise conflict(str(exc), code="cycle_board_replay_conflict") from exc
        if isinstance(result, CycleBoardProjectionPacket):
            return result
        return Response(
            content=result.model_dump_json().encode("utf-8"),
            media_type="application/json",
        )

    @router.get(
        "/governed-projections/confidence-ledger-risk-spend",
        response_model=ConfidenceLedgerRiskSpendPacket,
        operation_id="get_confidence_ledger_risk_spend_projection",
        summary="Get owner-validated confidence-ledger risk spend",
        dependencies=[Depends(_CONFIDENCE_LEDGER_RISK_SPEND_AUTHZ)],
    )
    def get_confidence_ledger_risk_spend_projection(
        artifact_content_hash: str | None = Query(default=None, max_length=128),
        projection_hash: str | None = Query(default=None, max_length=128),
        source_dependency_hash: str | None = Query(default=None, max_length=128),
        source_as_of: Annotated[datetime | None, Query()] = None,
        projection_rule_version: str | None = Query(default=None, max_length=128),
        service: ConfidenceLedgerRiskSpendProjectionService = (
            _CONFIDENCE_LEDGER_RISK_SPEND_SERVICE_DEPENDENCY
        ),
    ) -> ConfidenceLedgerRiskSpendPacket:
        try:
            return service.get(
                artifact_content_hash=artifact_content_hash,
                projection_hash=projection_hash,
                source_dependency_hash=source_dependency_hash,
                source_as_of=source_as_of,
                projection_rule_version=projection_rule_version,
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
        source_dependency_hash: str | None = Query(default=None, max_length=128),
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
                source_dependency_hash=source_dependency_hash,
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
