"""Runtime mobility estimation and report retrieval routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.runtime import (
    MobilityBoundsRequest,
    MobilityBoundsResponse,
    MobilityDiagnosticsResponse,
    MobilityEstimateRequest,
    MobilityEstimateResponse,
    MobilityReportResponse,
)
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_artifact_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request, not_found
from polisyos.runtime.http.permissions import RuntimePermission

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
    return APIRouter(prefix="/api/v1/mobility", tags=["runtime-mobility"])


router = _build_router()
_ESTIMATE_MOBILITY_AUTHZ = require_action_permission(
    RuntimePermission.MOBILITY_ANALYZE,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.mobility_estimate",
    ),
)
_COMPUTE_MOBILITY_BOUNDS_AUTHZ = require_action_permission(
    RuntimePermission.MOBILITY_ANALYZE,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.mobility_bounds",
    ),
)


if router is not None:

    @router.post(
        "/estimate",
        response_model=MobilityEstimateResponse,
        operation_id="estimate_mobility",
        dependencies=[Depends(_ESTIMATE_MOBILITY_AUTHZ)],
    )
    def estimate_mobility(
        body: MobilityEstimateRequest,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> MobilityEstimateResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.mobility_estimate",
        )
        try:
            report, report_ref, bounds_ref = ctx.mobility.estimate(body)
        except ValueError as exc:
            raise bad_request(str(exc), code="mobility_estimate_invalid") from exc
        record_data_access_audit(
            request,
            resource_id="mobility.estimate",
            tenant_id=getattr(request.state, "tenant_id", None),
            metadata={"mode": body.mode, "persist_artifact": body.persist_artifact},
        )
        return MobilityEstimateResponse(
            meta=build_meta(request),
            report=report.model_dump(mode="json"),
            mobility_report_ref=report_ref,
            bounds_bundle_ref=bounds_ref,
        )

    @router.post(
        "/bounds",
        response_model=MobilityBoundsResponse,
        operation_id="compute_mobility_bounds",
        dependencies=[Depends(_COMPUTE_MOBILITY_BOUNDS_AUTHZ)],
    )
    def compute_mobility_bounds(
        body: MobilityBoundsRequest,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> MobilityBoundsResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.mobility_bounds",
        )
        try:
            bundle, bounds_ref, cell_bounds, summary_bounds = ctx.mobility.compute_bounds(body)
        except ValueError as exc:
            raise bad_request(str(exc), code="mobility_bounds_invalid") from exc
        record_data_access_audit(
            request,
            resource_id="mobility.bounds",
            tenant_id=getattr(request.state, "tenant_id", None),
            metadata={"persist_artifact": body.persist_artifact},
        )
        return MobilityBoundsResponse(
            meta=build_meta(request),
            bounds=bundle.model_dump(mode="json"),
            bounds_bundle_ref=bounds_ref,
            cell_bounds=cell_bounds,
            summary_bounds=summary_bounds,
        )

    @router.get(
        "/reports/{artifact_id}",
        response_model=MobilityReportResponse,
        operation_id="get_mobility_report",
    )
    def get_mobility_report(
        artifact_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> MobilityReportResponse:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.mobility_report",
            artifact_id=str(parsed_id),
        )
        try:
            report, report_ref = ctx.mobility.load_report(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="mobility_report_not_found") from exc
        except ValueError as exc:
            raise bad_request(str(exc), code="invalid_mobility_report") from exc
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"kind": "mobility_report"},
        )
        return MobilityReportResponse(
            meta=build_meta(request),
            report=report.model_dump(mode="json"),
            mobility_report_ref=report_ref,
        )

    @router.get(
        "/reports/{artifact_id}/bounds",
        response_model=MobilityBoundsResponse,
        operation_id="get_mobility_report_bounds",
    )
    def get_mobility_report_bounds(
        artifact_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> MobilityBoundsResponse:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.mobility_bounds",
            artifact_id=str(parsed_id),
        )
        try:
            report, _ = ctx.mobility.load_report(parsed_id)
            bundle, report_ref, bounds_ref = ctx.mobility.load_bounds_for_report(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="mobility_bounds_not_found") from exc
        except ValueError as exc:
            raise bad_request(str(exc), code="invalid_mobility_report") from exc
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"kind": "mobility_bounds"},
        )
        return MobilityBoundsResponse(
            meta=build_meta(request),
            bounds=bundle.model_dump(mode="json"),
            bounds_bundle_ref=bounds_ref,
            mobility_report_ref=report_ref,
            cell_bounds={key: list(value) for key, value in report.bounds.cell_bounds.items()},
            summary_bounds={
                key: list(value) for key, value in report.bounds.summary_bounds.items()
            },
        )

    @router.get(
        "/reports/{artifact_id}/diagnostics",
        response_model=MobilityDiagnosticsResponse,
        operation_id="get_mobility_report_diagnostics",
    )
    def get_mobility_report_diagnostics(
        artifact_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> MobilityDiagnosticsResponse:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.mobility_diagnostics",
            artifact_id=str(parsed_id),
        )
        try:
            diagnostics, report_ref = ctx.mobility.load_diagnostics(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="mobility_report_not_found") from exc
        except ValueError as exc:
            raise bad_request(str(exc), code="invalid_mobility_report") from exc
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"kind": "mobility_diagnostics"},
        )
        return MobilityDiagnosticsResponse(
            meta=build_meta(request),
            diagnostics=diagnostics,
            mobility_report_ref=report_ref,
        )


def _parse_artifact_id(value: str) -> ArtifactID:
    try:
        return ArtifactID.model_validate(value)
    except (TypeError, ValueError) as exc:
        raise bad_request(
            "artifact_id must match sha256:<64-hex>",
            code="invalid_artifact_id",
        ) from exc


__all__ = ["router"]
