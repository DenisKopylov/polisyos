"""Public routes artifacts module API."""

from __future__ import annotations

import mimetypes
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.runtime import (
    ArtifactBatchRequest,
    ArtifactBatchResponse,
    ArtifactContentResponse,
    ArtifactLineageResponse,
    ArtifactManifestResponse,
    ArtifactSchemaResponse,
    BureaucraticExportFormat,
    BureaucraticExportResponse,
    BureaucraticGenre,
    BureaucraticRenderRequest,
    BureaucraticRenderResponse,
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
    enforce_artifact_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request, conflict, not_acceptable, not_found
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.response_policies import (
    add_artifact_link_relations,
    build_artifact_etag,
    build_not_modified_response,
    set_immutable_resource_headers,
)
from polisyos.runtime.http.routes._export_replay import bind_export_replay_or_conflict
from polisyos.runtime.http.services.artifact_inspector import ArtifactSurfaceAdmissionError
from polisyos.runtime.http.services.export_replay import EXPORT_REPLAY_RESPONSE_HEADERS
from polisyos.runtime.quality.authority import authority_surface_decision

_BUREAUCRATIC_OBSERVATION_TIMESTAMP = re.compile(
    r"(?<=Дата формування: )\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    + r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)

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
    return APIRouter(prefix="/api/v1/artifacts", tags=["runtime-artifacts"])


router = _build_router()
_GET_ARTIFACT_BATCH_AUTHZ = require_action_permission(
    RuntimePermission.ARTIFACTS_BATCH_READ,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_BATCH,
        resource_kind="runtime.artifact.batch",
        body_field="artifact_ids",
    ),
)
_RENDER_BUREAUCRATIC_ARTIFACT_AUTHZ = require_action_permission(
    RuntimePermission.ARTIFACTS_RENDER,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.artifact.bureaucratic_render",
        path_parameter="packet_id",
    ),
)


if router is not None:

    @router.post(
        "/batch",
        response_model=ArtifactBatchResponse,
        operation_id="get_artifact_batch",
        dependencies=[Depends(_GET_ARTIFACT_BATCH_AUTHZ)],
    )
    def get_artifact_batch(
        body: ArtifactBatchRequest,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactBatchResponse:
        parsed_ids = _parse_artifact_ids(body.artifact_ids)
        views = []
        for parsed_id in parsed_ids:
            tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
            set_authz_resource(
                request,
                tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
                kind="runtime.artifact_manifest_batch",
                artifact_id=str(parsed_id),
            )
            try:
                manifest = ctx.store.get_manifest(parsed_id)
                _ensure_surface_admission_allowed(
                    manifest.model_dump(mode="json"),
                    artifact_ref_or_route=f"cas-manifest://{parsed_id}",
                    surface="artifact",
                    scope="CAS manifests",
                    artifact_store=ctx.store,
                    artifact_id=parsed_id,
                )
                view = ctx.artifacts.get_manifest_view(parsed_id)
                _ensure_surface_admission_allowed(
                    view.model_dump(mode="json"),
                    artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
                    surface="dashboard",
                    scope="dashboard/public/export packets",
                    artifact_store=ctx.store,
                    artifact_id=parsed_id,
                )
                views.append(view)
            except FileNotFoundError as exc:
                raise not_found(str(exc), code="artifact_not_found") from exc
            except ArtifactSurfaceAdmissionError as exc:
                raise _artifact_surface_admission_conflict(
                    exc,
                    artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
                ) from exc
        record_data_access_audit(
            request,
            resource_id="artifact.batch",
            tenant_id=getattr(request.state, "tenant_id", None),
            metadata={"count": len(views)},
        )
        return ArtifactBatchResponse(meta=build_meta(request), artifacts=views)

    @router.get(
        "/{artifact_id}",
        response_model=ArtifactManifestResponse,
        operation_id="get_artifact_manifest",
    )
    def get_artifact_manifest(
        artifact_id: str,
        request: Request,
        response: Response,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactManifestResponse | Response:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_manifest",
            artifact_id=str(parsed_id),
        )
        try:
            manifest = ctx.store.get_manifest(parsed_id)
            _ensure_surface_admission_allowed(
                manifest.model_dump(mode="json"),
                artifact_ref_or_route=f"cas-manifest://{parsed_id}",
                surface="artifact",
                scope="CAS manifests",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
            )
            view = ctx.artifacts.get_manifest_view(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
            ) from exc
        etag = build_artifact_etag(view.artifact_id, view.integrity_sha256, "manifest")
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=view.created_at,
        )
        if not_modified is not None:
            add_artifact_link_relations(not_modified, artifact_id=str(parsed_id))
            return not_modified
        _ensure_surface_admission_allowed(
            view.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
            surface="dashboard",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
        )
        set_immutable_resource_headers(response, etag=etag, last_modified=view.created_at)
        add_artifact_link_relations(response, artifact_id=str(parsed_id))
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
        )
        return ArtifactManifestResponse(meta=build_meta(request), artifact=view)

    @router.get(
        "/{artifact_id}/content",
        response_model=ArtifactContentResponse,
        operation_id="get_artifact_content",
    )
    def get_artifact_content(
        artifact_id: str,
        request: Request,
        response: Response,
        max_bytes: int | None = Query(default=None, ge=1024, le=2_000_000),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactContentResponse | Response:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_content",
            artifact_id=str(parsed_id),
        )
        try:
            manifest = ctx.store.get_manifest(parsed_id)
            payload = ctx.store.get_bytes(parsed_id)
            _ensure_surface_admission_allowed(
                payload,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/content",
                surface="artifact",
                scope="raw artifact content/download routes",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                require_cas_integrity=True,
            )
            view = ctx.artifacts.get_content_preview(parsed_id, max_bytes=max_bytes)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/content",
            ) from exc
        etag = build_artifact_etag(str(parsed_id), manifest.integrity.sha256, "content")
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=manifest.created_at,
        )
        if not_modified is not None:
            add_artifact_link_relations(not_modified, artifact_id=str(parsed_id))
            return not_modified
        if _prefers_raw_representation(request, media_type=manifest.media_type):
            _ensure_surface_admission_allowed(
                payload,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/content",
                surface="artifact",
                scope="raw artifact content/download routes",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                require_cas_integrity=True,
            )
            raw_response = Response(
                content=payload,
                media_type=manifest.media_type,
            )
            set_immutable_resource_headers(
                raw_response,
                etag=etag,
                last_modified=manifest.created_at,
            )
            add_artifact_link_relations(raw_response, artifact_id=str(parsed_id))
            filename = _artifact_filename(str(parsed_id), manifest.kind, manifest.media_type)
            raw_response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
            record_data_access_audit(
                request,
                resource_id=str(parsed_id),
                tenant_id=tenant_id,
                metadata={"max_bytes": max_bytes, "representation": "raw"},
            )
            return raw_response
        _ensure_surface_admission_allowed(
            view.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/content",
            surface="dashboard",
            scope="raw artifact content/download routes",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
        )
        set_immutable_resource_headers(response, etag=etag, last_modified=manifest.created_at)
        add_artifact_link_relations(response, artifact_id=str(parsed_id))
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"max_bytes": max_bytes},
        )
        return ArtifactContentResponse(meta=build_meta(request), artifact=view)

    @router.get(
        "/{artifact_id}/lineage",
        response_model=ArtifactLineageResponse,
        operation_id="get_artifact_lineage",
    )
    def get_artifact_lineage(
        artifact_id: str,
        request: Request,
        response: Response,
        max_depth: int | None = Query(default=None, ge=1, le=256),
        max_nodes: int | None = Query(default=None, ge=1, le=20000),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactLineageResponse | Response:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_lineage",
            artifact_id=str(parsed_id),
        )
        try:
            manifest = ctx.store.get_manifest(parsed_id)
            lineage = ctx.artifacts.get_lineage_view(
                parsed_id,
                max_depth=max_depth,
                max_nodes=max_nodes,
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/lineage",
            ) from exc
        etag = build_artifact_etag(str(parsed_id), manifest.integrity.sha256, "lineage")
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=manifest.created_at,
        )
        if not_modified is not None:
            add_artifact_link_relations(not_modified, artifact_id=str(parsed_id))
            return not_modified
        _ensure_surface_admission_allowed(
            lineage.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/lineage",
            surface="lineage",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
        )
        set_immutable_resource_headers(response, etag=etag, last_modified=manifest.created_at)
        add_artifact_link_relations(response, artifact_id=str(parsed_id))
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"max_depth": max_depth, "max_nodes": max_nodes},
        )
        return ArtifactLineageResponse(meta=build_meta(request), lineage=lineage)

    @router.get(
        "/{artifact_id}/schema",
        response_model=ArtifactSchemaResponse,
        operation_id="get_artifact_schema",
    )
    def get_artifact_schema(
        artifact_id: str,
        request: Request,
        response: Response,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactSchemaResponse | Response:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_schema",
            artifact_id=str(parsed_id),
        )
        try:
            manifest = ctx.store.get_manifest(parsed_id)
            schema_view = ctx.artifacts.get_schema_view(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/schema",
            ) from exc
        etag = build_artifact_etag(str(parsed_id), manifest.integrity.sha256, "schema")
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=manifest.created_at,
        )
        if not_modified is not None:
            add_artifact_link_relations(not_modified, artifact_id=str(parsed_id))
            return not_modified
        _ensure_surface_admission_allowed(
            schema_view.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/schema",
            surface="dashboard",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
        )
        set_immutable_resource_headers(response, etag=etag, last_modified=manifest.created_at)
        add_artifact_link_relations(response, artifact_id=str(parsed_id))
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
        )
        return ArtifactSchemaResponse.model_validate(
            {
                "meta": build_meta(request),
                "schema": schema_view.model_dump(mode="json"),
            }
        )

    @router.post(
        "/{packet_id}/render",
        response_model=BureaucraticRenderResponse,
        operation_id="render_bureaucratic_artifact",
        responses={200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS}},
        dependencies=[Depends(_RENDER_BUREAUCRATIC_ARTIFACT_AUTHZ)],
    )
    def render_bureaucratic_artifact(
        packet_id: str,
        body: BureaucraticRenderRequest,
        request: Request,
        response: Response,
        export_projection_hash: str | None = Query(default=None, max_length=128),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> BureaucraticRenderResponse:
        parsed_id = _parse_artifact_id(packet_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_bureaucratic_render",
            artifact_id=str(parsed_id),
        )
        try:
            payload = ctx.store.get_bytes(parsed_id)
            _ensure_surface_admission_allowed(
                payload,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/render",
                surface="dashboard",
                scope="raw artifact content/download routes",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                require_cas_integrity=True,
            )
            document = ctx.bureaucratic_rendering.render_document(parsed_id, body)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        _ensure_surface_admission_allowed(
            document.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/render",
            surface="dashboard",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
        )
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={
                "genre": body.genre,
                "template_version": body.template_version,
                "trust_view": body.trust_view,
            },
        )
        render_response = BureaucraticRenderResponse(
            meta=build_meta(request),
            document=document,
        )
        bind_export_replay_or_conflict(
            request=request,
            response=response,
            semantic_projection=_bureaucratic_replay_projection(
                document.model_dump(mode="json"),
            ),
            as_of=_bureaucratic_replay_as_of(
                temporal_scope=document.temporal_scope,
                observed_at=document.render_timestamp,
            ),
            requested_projection_hash=export_projection_hash,
        )
        return render_response

    @router.get(
        "/{packet_id}/export",
        response_model=BureaucraticExportResponse,
        operation_id="export_bureaucratic_artifact",
        responses={200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS}},
    )
    def export_bureaucratic_artifact(
        packet_id: str,
        request: Request,
        response: Response,
        format: BureaucraticExportFormat = Query(default="html"),
        genre: BureaucraticGenre = Query(default="postanova_kmu"),
        jurisdiction: str = Query(default="ua", min_length=1),
        template_version: str | None = Query(default=None),
        trust_view: bool = Query(default=False),
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        export_projection_hash: str | None = Query(default=None, max_length=128),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> BureaucraticExportResponse:
        parsed_id = _parse_artifact_id(packet_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_bureaucratic_export",
            artifact_id=str(parsed_id),
        )
        temporal_scope = None
        if valid_at is not None or tx_at is not None:
            temporal_scope = TemporalScope(valid_at=valid_at, tx_at=tx_at)
        render_request = BureaucraticRenderRequest(
            genre=genre,
            jurisdiction=jurisdiction,
            template_version=template_version,
            temporal_scope=temporal_scope,
            trust_view=trust_view,
        )
        try:
            payload = ctx.store.get_bytes(parsed_id)
            _ensure_surface_admission_allowed(
                payload,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/export",
                surface="export",
                scope="raw artifact content/download routes",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                require_cas_integrity=True,
            )
            export = ctx.bureaucratic_rendering.export_document(
                parsed_id,
                render_request,
                export_format=format,
                meta=build_meta(request),
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        _ensure_surface_admission_allowed(
            export.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/export",
            surface="export",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
        )
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={
                "format": format,
                "genre": genre,
                "template_version": template_version,
                "trust_view": trust_view,
            },
        )
        semantic_projection = _bureaucratic_replay_projection(
            export.model_dump(mode="json", exclude={"meta"}),
        )
        render_timestamp = datetime.fromisoformat(
            cast("str", export.metadata["render_timestamp"]),
        )
        bind_export_replay_or_conflict(
            request=request,
            response=response,
            semantic_projection=semantic_projection,
            as_of=_bureaucratic_replay_as_of(
                temporal_scope=temporal_scope,
                observed_at=render_timestamp,
            ),
            requested_projection_hash=export_projection_hash,
        )
        return export

    @router.get(
        "/{artifact_id}/download",
        operation_id="download_artifact_content",
        responses={
            "200": {
                "description": "Raw artifact bytes",
                "content": {
                    "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
                },
            }
        },
    )
    def download_artifact_content(
        artifact_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> Response:
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_download",
            artifact_id=str(parsed_id),
        )
        try:
            manifest = ctx.store.get_manifest(parsed_id)
            payload = ctx.store.get_bytes(parsed_id)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        if not _accepts_raw_representation(request, media_type=manifest.media_type):
            raise not_acceptable(
                "Requested Accept header does not support artifact raw download",
                code="artifact_representation_not_acceptable",
            )
        _ensure_surface_admission_allowed(
            payload,
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/download",
            surface="artifact",
            scope="raw artifact content/download routes",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            require_cas_integrity=True,
        )
        _ensure_surface_admission_allowed(
            payload,
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/download",
            surface="artifact",
            scope="raw artifact content/download routes",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            require_cas_integrity=True,
        )
        etag = build_artifact_etag(str(parsed_id), manifest.integrity.sha256, "download")
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=manifest.created_at,
        )
        if not_modified is not None:
            add_artifact_link_relations(not_modified, artifact_id=str(parsed_id))
            return not_modified
        response = Response(content=payload, media_type=manifest.media_type)
        set_immutable_resource_headers(response, etag=etag, last_modified=manifest.created_at)
        add_artifact_link_relations(response, artifact_id=str(parsed_id))
        filename = _artifact_filename(str(parsed_id), manifest.kind, manifest.media_type)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={"representation": "download"},
        )
        return response


def _bureaucratic_replay_projection(value: object) -> object:
    """Remove renderer observation clocks from the semantic replay projection."""
    if isinstance(value, dict):
        mapping = cast("dict[str, object]", value)
        return {
            key: _bureaucratic_replay_projection(item)
            for key, item in mapping.items()
            if key != "render_timestamp"
        }
    if isinstance(value, list):
        return [_bureaucratic_replay_projection(item) for item in value]
    if isinstance(value, str):
        return _BUREAUCRATIC_OBSERVATION_TIMESTAMP.sub("observation-time", value)
    return value


def _bureaucratic_replay_as_of(
    *,
    temporal_scope: TemporalScope | None,
    observed_at: datetime,
) -> datetime:
    """Resolve replay time by semantic role: validity, transaction, observation."""
    if temporal_scope is None:
        return observed_at
    return temporal_scope.valid_at or temporal_scope.tx_at or observed_at


def _parse_artifact_id(value: str) -> ArtifactID:
    try:
        return ArtifactID.model_validate(value)
    except (TypeError, ValueError) as exc:
        raise bad_request(
            "artifact_id must match sha256:<64-hex>",
            code="invalid_artifact_id",
        ) from exc


def _parse_artifact_ids(values: list[str]) -> list[ArtifactID]:
    try:
        return [ArtifactID.model_validate(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise bad_request(
            "artifact_ids must contain only sha256:<64-hex> references",
            code="invalid_artifact_id",
        ) from exc


def _accepts_raw_representation(request: Request, *, media_type: str) -> bool:
    accept = str(request.headers.get("accept", "")).strip().lower()
    if not accept or accept == "*/*":
        return True
    accepted = {token.split(";", 1)[0].strip() for token in accept.split(",") if token.strip()}
    normalized_media_type = media_type.lower()
    return (
        "*/*" in accepted
        or "application/octet-stream" in accepted
        or normalized_media_type in accepted
        or ("text/plain" in accepted and normalized_media_type.startswith("text/"))
    )


def _prefers_raw_representation(request: Request, *, media_type: str) -> bool:
    accept = str(request.headers.get("accept", "")).strip().lower()
    if not accept or accept == "*/*":
        return False
    accepted = {token.split(";", 1)[0].strip() for token in accept.split(",") if token.strip()}
    if "application/json" in accepted:
        return False
    if _accepts_raw_representation(request, media_type=media_type):
        return True
    raise not_acceptable(
        "Requested Accept header does not support this artifact representation",
        code="artifact_representation_not_acceptable",
    )


def _artifact_filename(artifact_id: str, kind: str, media_type: str) -> str:
    suffix = mimetypes.guess_extension(media_type.split(";", 1)[0].strip()) or ".bin"
    safe_kind = re.sub(r"[^a-z0-9._-]+", "-", kind.lower()).strip("-") or "artifact"
    short_id = artifact_id.split(":", 1)[-1][:12]
    return f"{safe_kind}-{short_id}{suffix}"


def _ensure_surface_admission_allowed(
    payload: object,
    *,
    artifact_ref_or_route: str,
    surface: str,
    scope: str,
    artifact_store: object | None = None,
    artifact_id: ArtifactID | None = None,
    require_cas_integrity: bool = False,
) -> None:
    decision = authority_surface_decision(
        payload,
        surface=surface,
        artifact_ref_or_route=artifact_ref_or_route,
        secret_pii_scope=scope,
        block_on_secret_findings=True,
        artifact_store=artifact_store,
        artifact_id=artifact_id,
        require_cas_integrity=require_cas_integrity,
    )
    if not (decision.blocking or decision.visible_downgrade):
        return
    raise conflict(
        "Artifact surface blocked or downgraded by composed authority surface admission",
        code="authority_surface_admission_blocked",
        extensions={
            "artifact_ref_or_route": artifact_ref_or_route,
            "authority_surface_decision": decision.model_dump(mode="json"),
        },
    )


def _artifact_surface_admission_conflict(
    exc: ArtifactSurfaceAdmissionError,
    *,
    artifact_ref_or_route: str,
) -> Exception:
    return conflict(
        "Artifact surface blocked or downgraded by composed authority surface admission",
        code="authority_surface_admission_blocked",
        extensions={
            "artifact_ref_or_route": artifact_ref_or_route,
            "authority_surface_decision": exc.decision.model_dump(mode="json"),
        },
    )
