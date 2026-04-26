"""Runtime attractor-analysis and dynamical sidecar routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.foundry import (
    AttractorAnalysisRequest,
    AttractorAnalysisResponse,
    AttractorAnalysisResult,
    BasinMap,
    BasinMapRef,
    ContinuationBranch,
    ContinuationBranchRef,
    DerivedArtifact,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    enforce_artifact_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request, not_found

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
    return APIRouter(prefix="/api/v1/analysis", tags=["runtime-analysis"])


router = _build_router()
_RUNTIME_CONTEXT_DEPENDENCY = (
    Depends(get_runtime_api_context) if Depends is not None else None
)


if router is not None:

    @router.post(
        "/attractors",
        response_model=AttractorAnalysisResponse,
        operation_id="analyze_attractors",
    )
    def analyze_attractors(
        body: AttractorAnalysisRequest,
        request: Request,
        ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
    ) -> AttractorAnalysisResponse:
        return _run_analysis(body, request, ctx, resource_kind="runtime.attractor_analysis")

    @router.post(
        "/lyapunov",
        response_model=AttractorAnalysisResponse,
        operation_id="analyze_lyapunov_diagnostics",
    )
    def analyze_lyapunov_diagnostics(
        body: AttractorAnalysisRequest,
        request: Request,
        ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
    ) -> AttractorAnalysisResponse:
        requested = body.model_copy(update={"analysis_modes": ["lyapunov", "attractors"]})
        return _run_analysis(requested, request, ctx, resource_kind="runtime.lyapunov_analysis")

    @router.post(
        "/basin-map",
        response_model=BasinMapRef,
        operation_id="persist_basin_map",
    )
    def persist_basin_map(
        body: BasinMap,
        request: Request,
        ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
    ) -> BasinMapRef:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.basin_map",
        )
        try:
            ref = ctx.analysis.persist_basin_map(body)
        except ValueError as exc:
            raise bad_request(str(exc), code="basin_map_invalid") from exc
        record_data_access_audit(
            request,
            resource_id=str(ref.artifact_id),
            tenant_id=getattr(request.state, "tenant_id", None),
            metadata={"kind": "basin_map"},
        )
        return ref

    @router.post(
        "/continuation",
        response_model=ContinuationBranchRef,
        operation_id="persist_continuation_branch",
    )
    def persist_continuation_branch(
        body: ContinuationBranch,
        request: Request,
        ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
    ) -> ContinuationBranchRef:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.continuation_branch",
        )
        try:
            ref = ctx.analysis.persist_continuation_branch(body)
        except ValueError as exc:
            raise bad_request(str(exc), code="continuation_branch_invalid") from exc
        record_data_access_audit(
            request,
            resource_id=str(ref.artifact_id),
            tenant_id=getattr(request.state, "tenant_id", None),
            metadata={"kind": "continuation_branch"},
        )
        return ref

    @router.get(
        "/{analysis_id}",
        response_model=AttractorAnalysisResult,
        operation_id="get_attractor_analysis",
    )
    def get_attractor_analysis(
        analysis_id: str,
        request: Request,
        ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
    ) -> AttractorAnalysisResult:
        parsed_id = _parse_artifact_id(analysis_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.attractor_analysis",
            artifact_id=str(parsed_id),
        )
        try:
            result, _ref = ctx.analysis.load_analysis(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="attractor_analysis_not_found") from exc
        except ValueError as exc:
            raise bad_request(str(exc), code="invalid_attractor_analysis") from exc
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"kind": "attractor_analysis_result"},
        )
        return result

    @router.get(
        "/{analysis_id}/basin/{basin_id}",
        response_model=BasinMap,
        operation_id="get_analysis_basin_map",
    )
    def get_analysis_basin_map(
        analysis_id: str,
        basin_id: str,
        request: Request,
        ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
    ) -> BasinMap:
        parsed_id = _parse_artifact_id(basin_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.basin_map",
            artifact_id=str(parsed_id),
        )
        try:
            basin_map, _ref = ctx.analysis.load_basin_map(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="basin_map_not_found") from exc
        except ValueError as exc:
            raise bad_request(str(exc), code="invalid_basin_map") from exc
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"analysis_id": analysis_id, "kind": "basin_map"},
        )
        return basin_map

    @router.get(
        "/{analysis_id}/branch/{branch_id}",
        response_model=ContinuationBranch,
        operation_id="get_analysis_continuation_branch",
    )
    def get_analysis_continuation_branch(
        analysis_id: str,
        branch_id: str,
        request: Request,
        ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
    ) -> ContinuationBranch:
        parsed_id = _parse_artifact_id(branch_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.continuation_branch",
            artifact_id=str(parsed_id),
        )
        try:
            branch, _ref = ctx.analysis.load_continuation_branch(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="continuation_branch_not_found") from exc
        except ValueError as exc:
            raise bad_request(str(exc), code="invalid_continuation_branch") from exc
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"analysis_id": analysis_id, "kind": "continuation_branch"},
        )
        return branch


def _run_analysis(
    body: AttractorAnalysisRequest,
    request: Request,
    ctx: RuntimeApiContext,
    *,
    resource_kind: str,
) -> AttractorAnalysisResponse:
    set_authz_resource(
        request,
        tenant_id=getattr(request.state, "tenant_id", None),
        kind=resource_kind,
    )
    try:
        result, result_ref, basin_ref = ctx.analysis.analyze_attractors(body)
    except ValueError as exc:
        raise bad_request(str(exc), code="attractor_analysis_invalid") from exc
    derived_refs: list[DerivedArtifact] = []
    if result_ref is not None:
        derived_refs.append(DerivedArtifact(role="attractor_analysis_result", ref=result_ref))
    if basin_ref is not None:
        derived_refs.append(DerivedArtifact(role="basin_map", ref=basin_ref))
    record_data_access_audit(
        request,
        resource_id=str(result_ref.artifact_id) if result_ref is not None else result.analysis_id,
        tenant_id=getattr(request.state, "tenant_id", None),
        metadata={"analysis_modes": body.analysis_modes, "persist_artifact": body.persist_artifact},
    )
    return AttractorAnalysisResponse(
        ok=True,
        analysis_result=result,
        analysis_result_ref=result_ref,
        derived_refs=derived_refs,
        notes=result.notes,
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
