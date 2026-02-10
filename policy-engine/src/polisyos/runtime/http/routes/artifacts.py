from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.runtime import (
    ArtifactContentResponse,
    ArtifactLineageResponse,
    ArtifactManifestResponse,
    ArtifactSchemaResponse,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_artifact_tenant_access,
    get_runtime_api_context,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request, not_found

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Query, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/artifacts", tags=["runtime-artifacts"]) if APIRouter else None


if router is not None:

    @router.get(
        "/{artifact_id}",
        response_model=ArtifactManifestResponse,
        operation_id="get_artifact_manifest",
    )
    def get_artifact_manifest(
        artifact_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> ArtifactManifestResponse:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_manifest",
            artifact_id=str(parsed_id),
        )
        try:
            view = ctx.artifacts.get_manifest_view(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        return ArtifactManifestResponse(meta=build_meta(request), artifact=view)

    @router.get(
        "/{artifact_id}/content",
        response_model=ArtifactContentResponse,
        operation_id="get_artifact_content",
    )
    def get_artifact_content(
        artifact_id: str,
        request: Request,
        max_bytes: int | None = Query(default=None, ge=1024, le=2_000_000),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> ArtifactContentResponse:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_content",
            artifact_id=str(parsed_id),
        )
        try:
            view = ctx.artifacts.get_content_preview(parsed_id, max_bytes=max_bytes)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        return ArtifactContentResponse(meta=build_meta(request), artifact=view)

    @router.get(
        "/{artifact_id}/lineage",
        response_model=ArtifactLineageResponse,
        operation_id="get_artifact_lineage",
    )
    def get_artifact_lineage(
        artifact_id: str,
        request: Request,
        max_depth: int | None = Query(default=None, ge=1, le=256),
        max_nodes: int | None = Query(default=None, ge=1, le=20000),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> ArtifactLineageResponse:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_lineage",
            artifact_id=str(parsed_id),
        )
        try:
            lineage = ctx.artifacts.get_lineage_view(
                parsed_id,
                max_depth=max_depth,
                max_nodes=max_nodes,
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        return ArtifactLineageResponse(meta=build_meta(request), lineage=lineage)

    @router.get(
        "/{artifact_id}/schema",
        response_model=ArtifactSchemaResponse,
        operation_id="get_artifact_schema",
    )
    def get_artifact_schema(
        artifact_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> ArtifactSchemaResponse:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_schema",
            artifact_id=str(parsed_id),
        )
        try:
            schema_view = ctx.artifacts.get_schema_view(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        return ArtifactSchemaResponse(meta=build_meta(request), schema_view=schema_view)


def _parse_artifact_id(value: str) -> ArtifactID:
    try:
        return ArtifactID.model_validate(value)
    except Exception as exc:
        raise bad_request(
            "artifact_id must match sha256:<64-hex>",
            code="invalid_artifact_id",
        ) from exc
