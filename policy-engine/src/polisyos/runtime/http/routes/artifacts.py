"""Public routes artifacts module API."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.canonical_profile import (
    CanonicalProfileDeclaration,
    CanonicalProfileRefusalError,
)
from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactManifest,
    ArtifactOwnershipError,
    ArtifactRef,
    CoreJsonManifestBoundedRead,
    CoreJsonReadBoundsRefusalError,
    artifact_manifest_profile_sha256,
    read_core_manifest_profile_bounded,
)
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
    PredictiveCoverageDiagnosticPreview,
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
from polisyos.runtime.http.errors import (
    bad_request,
    conflict,
    not_acceptable,
    not_found,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.response_policies import (
    add_artifact_link_relations,
    build_artifact_etag,
    build_not_modified_response,
    set_artifact_view_headers,
)
from polisyos.runtime.http.routes._export_replay import bind_export_replay_or_conflict
from polisyos.runtime.http.services.artifact_inspector import (
    CORE_TAG_POLICY_ID,
    INSPECTOR_BOUNDED_READ_POLICY_ID,
    INSPECTOR_JSON_MAX_DEPTH,
    INSPECTOR_JSON_MAX_ELEMENTS,
    INSPECTOR_MANIFEST_MAX_BYTES,
    SCHEMA_INSPECTION_POLICY_ID,
    ArtifactSurfaceAdmissionError,
)
from polisyos.runtime.http.services.export_replay import EXPORT_REPLAY_RESPONSE_HEADERS
from polisyos.runtime.quality.authority import authority_surface_decision
from polisyos.runtime.quality.technical_inspection_evidence import (
    TECHNICAL_INSPECTION_EVIDENCE_KIND,
    TECHNICAL_INSPECTION_EVIDENCE_MEDIA_TYPE,
    TECHNICAL_INSPECTION_PURPOSE,
)

_PREDICTIVE_COVERAGE_DIAGNOSTIC_SCAN_SCOPE = "dashboard/public/export packets"

_ARTIFACT_PROFILE_RESOLUTION_RESPONSES = {
    409: {
        "description": (
            "A route-specific conflict or refusal; the response code identifies the cause."
        ),
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/RuntimeApiProblem"}
            }
        },
    }
}

_ARTIFACT_BATCH_RESPONSES = {
    409: {
        "description": (
            "The batch is refused when manifest-read usage cannot establish its byte budget "
            "or composed surface admission blocks a selected artifact."
        ),
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/RuntimeApiProblem"},
                "examples": {
                    "manifest_read_budget_exceeded": {
                        "summary": "Measured manifest reads exceed the batch byte budget.",
                        "value": {
                            "type": "about:blank",
                            "title": "Conflict",
                            "status": 409,
                            "detail": (
                                "The selected artifact manifest reads exceed or cannot prove "
                                "the batch byte budget."
                            ),
                            "code": "artifact_batch_manifest_read_budget_exceeded",
                            "instance": "/api/v1/artifacts/batch",
                            "request_id": "req_artifact_batch_budget",
                            "error": "artifact_batch_manifest_read_budget_exceeded",
                            "status_code": 409,
                            "extensions": {
                                "artifact_ref_or_route": (
                                    "/api/v1/artifacts/sha256:"
                                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                ),
                                "requested_id_count": 1,
                                "limit_source_bytes": 2000000,
                                "consumed_source_bytes": 1999999,
                                "observed_source_bytes": 2,
                            },
                        },
                    },
                    "manifest_read_usage_unavailable": {
                        "summary": (
                            "The Core read did not provide a trustworthy byte-usage receipt."
                        ),
                        "value": {
                            "type": "about:blank",
                            "title": "Conflict",
                            "status": 409,
                            "detail": (
                                "The selected artifact manifest reads exceed or cannot prove "
                                "the batch byte budget."
                            ),
                            "code": "artifact_batch_manifest_read_usage_unavailable",
                            "instance": "/api/v1/artifacts/batch",
                            "request_id": "req_artifact_batch_usage",
                            "error": "artifact_batch_manifest_read_usage_unavailable",
                            "status_code": 409,
                            "extensions": {
                                "artifact_ref_or_route": (
                                    "/api/v1/artifacts/sha256:"
                                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                ),
                                "requested_id_count": 1,
                                "limit_source_bytes": 2000000,
                                "consumed_source_bytes": 4096,
                                "observed_source_bytes": None,
                            },
                        },
                    },
                    "surface_admission_blocked": {
                        "summary": "A selected artifact is blocked by surface admission.",
                        "value": {
                            "type": "about:blank",
                            "title": "Conflict",
                            "status": 409,
                            "detail": (
                                "Artifact surface blocked or downgraded by composed authority "
                                "surface admission."
                            ),
                            "code": "authority_surface_admission_blocked",
                            "instance": "/api/v1/artifacts/batch",
                            "request_id": "req_artifact_batch_admission",
                            "error": "authority_surface_admission_blocked",
                            "status_code": 409,
                        },
                    },
                },
            }
        },
    }
}

_BUREAUCRATIC_OBSERVATION_TIMESTAMP = re.compile(
    r"(?<=Дата формування: )\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    + r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)


def _single_manifest_profile_selection(
    request: Request,
    parsed_value: str | None,
) -> str | None:
    """Reject repeated profile selectors instead of choosing one value."""
    values = request.query_params.getlist("manifest_profile_sha256")
    if len(values) > 1:
        raise bad_request(
            "manifest_profile_sha256 must be supplied at most once",
            code="ambiguous_manifest_profile_selector",
        )
    if not values:
        return None
    if values[0] != parsed_value:
        raise bad_request(
            "manifest_profile_sha256 did not resolve to the supplied selector",
            code="invalid_manifest_profile_selector",
        )
    return parsed_value


def _technical_inspection_evidence_selection(
    request: Request, evidence_id: str | None, evidence_profile: str | None
) -> ArtifactRef | None:
    """Accept only an explicit, unambiguous full selected evidence reference."""
    for key in ("technical_inspection_evidence_id", "technical_inspection_evidence_profile_sha256"):
        if len(request.query_params.getlist(key)) > 1:
            raise bad_request(
                "Repeated inspection evidence selector", code="ambiguous_inspection_evidence"
            )
    if evidence_id is None and evidence_profile is None:
        return None
    if evidence_id is None or evidence_profile is None:
        raise bad_request(
            "Both inspection evidence selectors are required", code="incomplete_inspection_evidence"
        )
    return ArtifactRef(
        artifact_id=_parse_artifact_id(evidence_id),
        kind=TECHNICAL_INSPECTION_EVIDENCE_KIND,
        media_type=TECHNICAL_INSPECTION_EVIDENCE_MEDIA_TYPE,
        manifest_profile_sha256=evidence_profile,
    )


def _artifact_ref_for_manifest(manifest: ArtifactManifest) -> ArtifactRef:
    """Bind a route's selected CAS manifest to its exact artifact reference."""
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )


def _is_json_artifact_media_type(media_type: str) -> bool:
    """Match the inspector's JSON representation classifier, including +json."""
    normalized = media_type.lower()
    return normalized == "application/json" or normalized.endswith("+json")


def _require_json_artifact_profile(
    manifest: ArtifactManifest,
    declaration: CanonicalProfileDeclaration,
) -> None:
    """Require a verified profile only when the selected representation is JSON."""
    if not _is_json_artifact_media_type(manifest.media_type):
        return
    if declaration.status == "absent":
        raise CanonicalProfileRefusalError("canon_profile_absent")
    if declaration.status != "declared":
        raise CanonicalProfileRefusalError("canon_profile_not_verified")


def _canonical_profile_conflict(
    exc: CanonicalProfileRefusalError,
    *,
    artifact_ref_or_route: str,
) -> Exception:
    """Map exact owner refusals and typed absence separately from profile conflicts."""
    if isinstance(exc, CoreJsonReadBoundsRefusalError):
        if exc.original_exception_type == "ArtifactOwnershipError":
            return not_found(
                "Selected artifact manifest profile is unavailable",
                code="artifact_manifest_profile_not_found",
            )
        if exc.code == "selected_artifact_not_found":
            return not_found("Artifact not found", code="artifact_not_found")
    return conflict(
        "The selected artifact canon profile is malformed or does not reproduce its bytes",
        code=exc.code,
        extensions={"artifact_ref_or_route": artifact_ref_or_route},
    )


if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Query, Request, Response

    from polisyos.core.artifacts import ArtifactStore
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
        responses=_ARTIFACT_BATCH_RESPONSES,
        dependencies=[Depends(_GET_ARTIFACT_BATCH_AUTHZ)],
    )
    def get_artifact_batch(
        body: ArtifactBatchRequest,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactBatchResponse:
        parsed_ids = _parse_artifact_ids(body.artifact_ids)
        views = []
        manifest_read_budget = _new_artifact_batch_manifest_read_budget(len(parsed_ids))
        for parsed_id in parsed_ids:
            tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
            set_authz_resource(
                request,
                tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
                kind="runtime.artifact_manifest_batch",
                artifact_id=str(parsed_id),
            )
            try:
                manifest_read = _resolve_selected_artifact_manifest(
                    ctx.store,
                    parsed_id,
                    None,
                    artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
                    read_budget=manifest_read_budget,
                )
                manifest = manifest_read.manifest
                _require_json_artifact_profile(manifest, manifest_read.declaration)
                _ensure_surface_admission_allowed(
                    manifest.model_dump(mode="json"),
                    artifact_ref_or_route=f"cas-manifest://{parsed_id}",
                    surface="artifact",
                    scope="CAS manifests",
                    artifact_store=ctx.store,
                    artifact_id=parsed_id,
                )
                view = ctx.artifacts.get_manifest_view(parsed_id, manifest=manifest)
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
        responses=_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
    )
    def get_artifact_manifest(
        artifact_id: str,
        request: Request,
        response: Response,
        manifest_profile_sha256: str | None = Query(
            default=None,
            description=(
                "Optional exact manifest profile. Supply at most once; repeated values are "
                "ambiguous and rejected."
            ),
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactManifestResponse | Response:
        manifest_profile_sha256 = _single_manifest_profile_selection(
            request,
            manifest_profile_sha256,
        )
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_manifest",
            artifact_id=str(parsed_id),
        )
        try:
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                manifest_profile_sha256,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
            )
            manifest = manifest_read.manifest
            _require_json_artifact_profile(manifest, manifest_read.declaration)
            _ensure_surface_admission_allowed(
                manifest.model_dump(mode="json"),
                artifact_ref_or_route=f"cas-manifest://{parsed_id}",
                surface="artifact",
                scope="CAS manifests",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                artifact_ref=_artifact_ref_for_manifest(manifest),
            )
            view = ctx.artifacts.get_manifest_view(parsed_id, manifest=manifest)
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
            ) from exc
        _ensure_surface_admission_allowed(
            view.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}",
            surface="dashboard",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            artifact_ref=_artifact_ref_for_manifest(manifest),
        )
        etag = build_artifact_etag(
            view.artifact_id,
            view.integrity_sha256,
            "manifest",
            view.manifest_profile_sha256 or "unqualified",
        )
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=view.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        if not_modified is not None:
            add_artifact_link_relations(
                not_modified,
                artifact_id=str(parsed_id),
                manifest_profile_sha256=view.manifest_profile_sha256,
            )
            return not_modified
        set_artifact_view_headers(
            response,
            etag=etag,
            last_modified=view.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        add_artifact_link_relations(
            response,
            artifact_id=str(parsed_id),
            manifest_profile_sha256=view.manifest_profile_sha256,
        )
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
        )
        return ArtifactManifestResponse(meta=build_meta(request), artifact=view)

    @router.get(
        "/{artifact_id}/predictive-coverage-diagnostic",
        response_model=PredictiveCoverageDiagnosticPreview,
        operation_id="get_predictive_coverage_diagnostic",
        responses=_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
    )
    def get_predictive_coverage_diagnostic(
        artifact_id: str,
        request: Request,
        response: Response,
        manifest_profile_sha256: str | None = Query(
            default=None,
            description=(
                "Optional exact manifest profile. Supply at most once; repeated values are "
                "ambiguous and rejected."
            ),
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> PredictiveCoverageDiagnosticPreview | Response:
        """Return a reader-materialized predictive diagnostic, never raw report bytes."""
        manifest_profile_sha256 = _single_manifest_profile_selection(
            request,
            manifest_profile_sha256,
        )
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact.predictive_coverage_diagnostic",
            artifact_id=str(parsed_id),
        )
        if not ctx.allow_candidate_predictive_diagnostic_surface:
            raise conflict(
                "Predictive coverage diagnostics are not admitted on this server",
                code="predictive_coverage_diagnostic_not_admitted",
            )
        route_ref = f"/api/v1/artifacts/{parsed_id}/predictive-coverage-diagnostic"
        try:
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                manifest_profile_sha256,
                artifact_ref_or_route=route_ref,
            )
            manifest = manifest_read.manifest
            _require_json_artifact_profile(manifest, manifest_read.declaration)
            projection = ctx.artifacts.get_predictive_coverage_diagnostic(
                parsed_id,
                manifest=manifest,
            )
            if projection is None:
                raise conflict(
                    "The selected manifest is not a supported predictive report view",
                    code="predictive_coverage_source_unsupported",
                    extensions={"artifact_ref_or_route": route_ref},
                )
            _ensure_predictive_coverage_diagnostic_admission_allowed(
                projection.model_dump(mode="json"),
                artifact_ref_or_route=route_ref,
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                artifact_ref=_artifact_ref_for_manifest(manifest),
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except CanonicalProfileRefusalError as exc:
            raise _canonical_profile_conflict(exc, artifact_ref_or_route=route_ref) from exc
        except ArtifactIntegrityError as exc:
            raise conflict(
                "The selected predictive report failed CAS integrity verification",
                code="artifact_integrity_failed",
            ) from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=route_ref,
            ) from exc

        selected_profile = projection.source_manifest_profile_sha256
        etag = build_artifact_etag(
            str(parsed_id),
            manifest.integrity.sha256,
            "predictive-coverage-diagnostic",
            selected_profile,
        )
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        if not_modified is not None:
            return not_modified
        set_artifact_view_headers(
            response,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        response.headers["X-Manifest-Profile-SHA256"] = selected_profile
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={
                "representation": "predictive_coverage_diagnostic",
                "manifest_profile_sha256": selected_profile,
                "measurement_status": projection.measurement_status,
            },
        )
        return projection

    @router.get(
        "/{artifact_id}/content",
        response_model=ArtifactContentResponse,
        operation_id="get_artifact_content",
        responses=_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
    )
    def get_artifact_content(
        artifact_id: str,
        request: Request,
        response: Response,
        max_bytes: int | None = Query(default=None, ge=1024, le=2_000_000),
        manifest_profile_sha256: str | None = Query(
            default=None,
            description=(
                "Optional exact manifest profile. Supply at most once; repeated values are "
                "ambiguous and rejected."
            ),
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        technical_inspection_evidence_id: str | None = Query(
            default=None, description="Exact technical-inspection evidence artifact ID."
        ),
        technical_inspection_evidence_profile_sha256: str | None = Query(
            default=None,
            description="Exact selected profile of the technical-inspection evidence.",
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactContentResponse | Response:
        manifest_profile_sha256 = _single_manifest_profile_selection(
            request,
            manifest_profile_sha256,
        )
        evidence_ref = _technical_inspection_evidence_selection(
            request, technical_inspection_evidence_id, technical_inspection_evidence_profile_sha256
        )
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_content",
            artifact_id=str(parsed_id),
        )
        route_ref = f"/api/v1/artifacts/{parsed_id}/content"
        try:
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                manifest_profile_sha256,
                artifact_ref_or_route=route_ref,
            )
            manifest = manifest_read.manifest
            declaration = manifest_read.declaration
            raw_representation = _prefers_raw_representation(
                request,
                media_type=manifest.media_type,
            )
            if raw_representation and evidence_ref is not None:
                raise bad_request(
                    "Technical-inspection evidence does not authorize raw downloads",
                    code="inspection_evidence_raw_unsupported",
                )
            if not raw_representation:
                _require_json_artifact_profile(manifest, declaration)
            selected_ref = _artifact_ref_for_manifest(manifest)
            selected_profile = artifact_manifest_profile_sha256(manifest)
            if raw_representation:
                etag = build_artifact_etag(
                    str(parsed_id),
                    manifest.integrity.sha256,
                    "content",
                    "raw-bytes@1",
                    f"kind:{manifest.kind}",
                    f"media-type:{manifest.media_type}",
                    selected_profile or "unqualified",
                )
                payload = ctx.store.get_bytes(selected_ref)
                _ensure_surface_admission_allowed(
                    payload,
                    artifact_ref_or_route=route_ref,
                    surface="artifact",
                    scope="raw artifact content/download routes",
                    artifact_store=ctx.store,
                    artifact_id=parsed_id,
                    artifact_ref=selected_ref,
                    require_cas_integrity=True,
                )
                not_modified = build_not_modified_response(
                    request.headers,
                    etag=etag,
                    last_modified=manifest.created_at,
                    profile_selected=manifest_profile_sha256 is not None and evidence_ref is None,
                )
                if not_modified is not None:
                    add_artifact_link_relations(
                        not_modified,
                        artifact_id=str(parsed_id),
                        manifest_profile_sha256=selected_profile,
                    )
                    return not_modified
                raw_response = Response(content=payload, media_type=manifest.media_type)
                set_artifact_view_headers(
                    raw_response,
                    etag=etag,
                    last_modified=manifest.created_at,
                    profile_selected=manifest_profile_sha256 is not None and evidence_ref is None,
                )
                raw_response.headers["X-Manifest-Profile-SHA256"] = (
                    selected_profile or "unqualified"
                )
                add_artifact_link_relations(
                    raw_response,
                    artifact_id=str(parsed_id),
                    manifest_profile_sha256=selected_profile,
                )
                filename = _artifact_filename(str(parsed_id), manifest.kind, manifest.media_type)
                raw_response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
                record_data_access_audit(
                    request,
                    resource_id=str(parsed_id),
                    tenant_id=tenant_id,
                    metadata={"max_bytes": max_bytes, "representation": "raw"},
                )
                return raw_response

            view = ctx.artifacts.get_content_preview(
                parsed_id,
                max_bytes=max_bytes,
                technical_inspection_evidence_ref=evidence_ref,
                manifest=manifest,
                manifest_read=manifest_read,
                allow_candidate_predictive_diagnostic_surface=(
                    ctx.allow_candidate_predictive_diagnostic_surface
                ),
            )
            reader_policy = (
                CORE_TAG_POLICY_ID
                if _is_json_artifact_media_type(manifest.media_type)
                else "untyped-preview@1"
            )
            schema = manifest.artifact_schema
            etag = build_artifact_etag(
                str(parsed_id),
                manifest.integrity.sha256,
                "content",
                "semantic-preview@1",
                reader_policy,
                f"kind:{manifest.kind}",
                f"media-type:{manifest.media_type}",
                f"schema:{schema.name if schema is not None else 'absent'}:"
                f"{schema.version if schema is not None else 'absent'}",
                INSPECTOR_BOUNDED_READ_POLICY_ID,
                f"max-bytes:{view.max_bytes}",
                f"max-depth:{INSPECTOR_JSON_MAX_DEPTH}",
                f"max-elements:{INSPECTOR_JSON_MAX_ELEMENTS}",
                f"max-manifest-bytes:{INSPECTOR_MANIFEST_MAX_BYTES}",
                (
                    "candidate-diagnostic:on"
                    if ctx.allow_candidate_predictive_diagnostic_surface
                    else "candidate-diagnostic:off"
                ),
                selected_profile or "unqualified",
            )
            _ensure_surface_admission_allowed(
                view.model_dump(mode="json"),
                artifact_ref_or_route=route_ref,
                surface="dashboard",
                scope="raw artifact content/download routes",
                technical_inspection_evidence_ref=evidence_ref,
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                artifact_ref=_artifact_ref_for_manifest(manifest),
            )
            not_modified = (
                build_not_modified_response(
                    request.headers,
                    etag=etag,
                    last_modified=manifest.created_at,
                    profile_selected=manifest_profile_sha256 is not None,
                )
                if evidence_ref is None
                else None
            )
            if not_modified is not None:
                add_artifact_link_relations(
                    not_modified,
                    artifact_id=str(parsed_id),
                    manifest_profile_sha256=view.manifest_profile_sha256,
                )
                return not_modified
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except CanonicalProfileRefusalError as exc:
            raise _canonical_profile_conflict(exc, artifact_ref_or_route=route_ref) from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=route_ref,
            ) from exc
        set_artifact_view_headers(
            response,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None and evidence_ref is None,
        )
        add_artifact_link_relations(
            response,
            artifact_id=str(parsed_id),
            manifest_profile_sha256=view.manifest_profile_sha256,
        )
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={
                "max_bytes": max_bytes,
                **(
                    {
                        "technical_inspection_subject": _artifact_ref_for_manifest(
                            manifest
                        ).model_dump(mode="json"),
                        "technical_inspection_evidence": evidence_ref.model_dump(mode="json"),
                    }
                    if evidence_ref is not None
                    else {}
                ),
            },
        )
        return ArtifactContentResponse(meta=build_meta(request), artifact=view)

    @router.get(
        "/{artifact_id}/lineage",
        response_model=ArtifactLineageResponse,
        operation_id="get_artifact_lineage",
        responses=_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
    )
    def get_artifact_lineage(
        artifact_id: str,
        request: Request,
        response: Response,
        max_depth: int | None = Query(default=None, ge=1, le=256),
        max_nodes: int | None = Query(default=None, ge=1, le=20000),
        manifest_profile_sha256: str | None = Query(
            default=None,
            description=(
                "Optional exact manifest profile. Supply at most once; repeated values are "
                "ambiguous and rejected."
            ),
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactLineageResponse | Response:
        manifest_profile_sha256 = _single_manifest_profile_selection(
            request,
            manifest_profile_sha256,
        )
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_lineage",
            artifact_id=str(parsed_id),
        )
        try:
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                manifest_profile_sha256,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/lineage",
            )
            manifest = manifest_read.manifest
            _require_json_artifact_profile(manifest, manifest_read.declaration)
            lineage = ctx.artifacts.get_lineage_view(
                parsed_id,
                max_depth=max_depth,
                max_nodes=max_nodes,
                manifest=manifest,
                manifest_profile_sha256=manifest_profile_sha256,
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/lineage",
            ) from exc
        resolved_profile = manifest_profile_sha256 or next(
            (
                str(ref.manifest_profile_sha256)
                for ref in lineage.root_artifact_refs
                if str(ref.artifact_id) == str(parsed_id)
                and ref.manifest_profile_sha256 is not None
            ),
            None,
        )
        etag = build_artifact_etag(
            str(parsed_id),
            manifest.integrity.sha256,
            "lineage",
            resolved_profile or "unqualified",
        )
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        if not_modified is not None:
            add_artifact_link_relations(
                not_modified,
                artifact_id=str(parsed_id),
                manifest_profile_sha256=resolved_profile,
            )
            return not_modified
        _ensure_surface_admission_allowed(
            lineage.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/lineage",
            surface="lineage",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            artifact_ref=_artifact_ref_for_manifest(manifest),
        )
        set_artifact_view_headers(
            response,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        add_artifact_link_relations(
            response,
            artifact_id=str(parsed_id),
            manifest_profile_sha256=resolved_profile,
        )
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
        responses=_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
    )
    def get_artifact_schema(
        artifact_id: str,
        request: Request,
        response: Response,
        manifest_profile_sha256: str | None = Query(
            default=None,
            description=(
                "Optional exact manifest profile. Supply at most once; repeated values are "
                "ambiguous and rejected."
            ),
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        technical_inspection_evidence_id: str | None = Query(
            default=None, description="Exact technical-inspection evidence artifact ID."
        ),
        technical_inspection_evidence_profile_sha256: str | None = Query(
            default=None,
            description="Exact selected profile of the technical-inspection evidence.",
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ArtifactSchemaResponse | Response:
        manifest_profile_sha256 = _single_manifest_profile_selection(
            request,
            manifest_profile_sha256,
        )
        evidence_ref = _technical_inspection_evidence_selection(
            request, technical_inspection_evidence_id, technical_inspection_evidence_profile_sha256
        )
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_schema",
            artifact_id=str(parsed_id),
        )
        try:
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                manifest_profile_sha256,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/schema",
            )
            manifest = manifest_read.manifest
            declaration = manifest_read.declaration
            _require_json_artifact_profile(manifest, declaration)
            schema_view = ctx.artifacts.get_schema_view(
                parsed_id,
                manifest=manifest,
                manifest_read=manifest_read,
                technical_inspection_evidence_ref=evidence_ref,
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except CanonicalProfileRefusalError as exc:
            raise _canonical_profile_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/schema",
            ) from exc
        except ArtifactSurfaceAdmissionError as exc:
            raise _artifact_surface_admission_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/schema",
            ) from exc
        etag = build_artifact_etag(
            str(parsed_id),
            manifest.integrity.sha256,
            "schema",
            SCHEMA_INSPECTION_POLICY_ID,
            CORE_TAG_POLICY_ID,
            INSPECTOR_BOUNDED_READ_POLICY_ID,
            f"max-bytes:{min(max(ctx.max_preview_bytes, 1024), 2_000_000)}",
            f"max-depth:{INSPECTOR_JSON_MAX_DEPTH}",
            f"max-elements:{INSPECTOR_JSON_MAX_ELEMENTS}",
            f"max-manifest-bytes:{INSPECTOR_MANIFEST_MAX_BYTES}",
            (
                f"schema:{schema_view.schema_name}:{schema_view.schema_version}"
                if schema_view.schema_name is not None and schema_view.schema_version is not None
                else "schema:absent"
            ),
            schema_view.manifest_profile_sha256 or "unqualified",
        )
        _ensure_surface_admission_allowed(
            schema_view.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/schema",
            surface="dashboard",
            scope="dashboard/public/export packets",
            technical_inspection_evidence_ref=evidence_ref,
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            artifact_ref=_artifact_ref_for_manifest(manifest),
        )
        not_modified = (
            build_not_modified_response(
                request.headers,
                etag=etag,
                last_modified=manifest.created_at,
                profile_selected=manifest_profile_sha256 is not None,
            )
            if evidence_ref is None
            else None
        )
        if not_modified is not None:
            add_artifact_link_relations(
                not_modified,
                artifact_id=str(parsed_id),
                manifest_profile_sha256=schema_view.manifest_profile_sha256,
            )
            return not_modified
        set_artifact_view_headers(
            response,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None and evidence_ref is None,
        )
        add_artifact_link_relations(
            response,
            artifact_id=str(parsed_id),
            manifest_profile_sha256=schema_view.manifest_profile_sha256,
        )
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata=(
                {
                    "technical_inspection_subject": _artifact_ref_for_manifest(manifest).model_dump(
                        mode="json"
                    ),
                    "technical_inspection_evidence": evidence_ref.model_dump(mode="json"),
                }
                if evidence_ref is not None
                else None
            ),
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
        responses={
            **_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
            200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS},
        },
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
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                body.manifest_profile_sha256,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/render",
            )
            selected_manifest = manifest_read.manifest
            _require_json_artifact_profile(selected_manifest, manifest_read.declaration)
            selected_ref = _artifact_ref_for_manifest(selected_manifest)
            payload = ctx.store.get_bytes(selected_ref)
            _ensure_surface_admission_allowed(
                payload,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/render",
                surface="dashboard",
                scope="raw artifact content/download routes",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                artifact_ref=selected_ref,
                require_cas_integrity=True,
            )
            document = ctx.bureaucratic_rendering.render_document(
                parsed_id, body, manifest=selected_manifest
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except CanonicalProfileRefusalError as exc:
            raise _canonical_profile_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/render",
            ) from exc
        _ensure_surface_admission_allowed(
            document.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/render",
            surface="dashboard",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            artifact_ref=selected_ref,
        )
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={
                "genre": body.genre,
                "manifest_profile_sha256": body.manifest_profile_sha256,
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
        responses={
            **_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
            200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS},
        },
    )
    def export_bureaucratic_artifact(
        packet_id: str,
        request: Request,
        response: Response,
        format: BureaucraticExportFormat = Query(default="html"),
        genre: BureaucraticGenre = Query(default="postanova_kmu"),
        jurisdiction: str = Query(default="ua", min_length=1),
        template_version: str | None = Query(default=None),
        manifest_profile_sha256: str | None = Query(
            default=None,
            description=(
                "Optional exact manifest profile. Supply at most once; repeated values are "
                "ambiguous and rejected."
            ),
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        trust_view: bool = Query(default=False),
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        export_projection_hash: str | None = Query(default=None, max_length=128),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> BureaucraticExportResponse:
        manifest_profile_sha256 = _single_manifest_profile_selection(
            request,
            manifest_profile_sha256,
        )
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
            manifest_profile_sha256=manifest_profile_sha256,
            temporal_scope=temporal_scope,
            trust_view=trust_view,
        )
        try:
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                manifest_profile_sha256,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/export",
            )
            selected_manifest = manifest_read.manifest
            _require_json_artifact_profile(selected_manifest, manifest_read.declaration)
            selected_ref = _artifact_ref_for_manifest(selected_manifest)
            payload = ctx.store.get_bytes(selected_ref)
            _ensure_surface_admission_allowed(
                payload,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/export",
                surface="export",
                scope="raw artifact content/download routes",
                artifact_store=ctx.store,
                artifact_id=parsed_id,
                artifact_ref=selected_ref,
                require_cas_integrity=True,
            )
            export = ctx.bureaucratic_rendering.export_document(
                parsed_id,
                render_request,
                export_format=format,
                meta=build_meta(request),
                manifest=selected_manifest,
            )
        except FileNotFoundError as exc:
            raise not_found(str(exc), code="artifact_not_found") from exc
        except CanonicalProfileRefusalError as exc:
            raise _canonical_profile_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/export",
            ) from exc
        _ensure_surface_admission_allowed(
            export.model_dump(mode="json"),
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/export",
            surface="export",
            scope="dashboard/public/export packets",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            artifact_ref=selected_ref,
        )
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={
                "format": format,
                "genre": genre,
                "manifest_profile_sha256": manifest_profile_sha256,
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
            **_ARTIFACT_PROFILE_RESOLUTION_RESPONSES,
            "200": {
                "description": "Raw artifact bytes",
                "content": {
                    "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
                },
            },
        },
    )
    def download_artifact_content(
        artifact_id: str,
        request: Request,
        manifest_profile_sha256: str | None = Query(
            default=None,
            description=(
                "Optional exact manifest profile. Supply at most once; repeated values are "
                "ambiguous and rejected."
            ),
            min_length=71,
            max_length=71,
            pattern=r"^sha256:[0-9a-f]{64}$",
        ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> Response:
        manifest_profile_sha256 = _single_manifest_profile_selection(
            request,
            manifest_profile_sha256,
        )
        parsed_id = _parse_artifact_id(artifact_id)
        tenant_id = enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=parsed_id)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.artifact_download",
            artifact_id=str(parsed_id),
        )
        try:
            manifest_read = _resolve_selected_artifact_manifest(
                ctx.store,
                parsed_id,
                manifest_profile_sha256,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/download",
            )
            manifest = manifest_read.manifest
            payload = ctx.store.get_bytes(_artifact_ref_for_manifest(manifest))
        except CanonicalProfileRefusalError as exc:
            raise _canonical_profile_conflict(
                exc,
                artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/download",
            ) from exc
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
            artifact_ref=_artifact_ref_for_manifest(manifest),
            require_cas_integrity=True,
        )
        _ensure_surface_admission_allowed(
            payload,
            artifact_ref_or_route=f"/api/v1/artifacts/{parsed_id}/download",
            surface="artifact",
            scope="raw artifact content/download routes",
            artifact_store=ctx.store,
            artifact_id=parsed_id,
            artifact_ref=_artifact_ref_for_manifest(manifest),
            require_cas_integrity=True,
        )
        resolved_profile = artifact_manifest_profile_sha256(manifest)
        etag = build_artifact_etag(
            str(parsed_id),
            manifest.integrity.sha256,
            "download",
            resolved_profile,
        )
        not_modified = build_not_modified_response(
            request.headers,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        if not_modified is not None:
            add_artifact_link_relations(
                not_modified,
                artifact_id=str(parsed_id),
                manifest_profile_sha256=resolved_profile,
            )
            return not_modified
        response = Response(content=payload, media_type=manifest.media_type)
        set_artifact_view_headers(
            response,
            etag=etag,
            last_modified=manifest.created_at,
            profile_selected=manifest_profile_sha256 is not None,
        )
        add_artifact_link_relations(
            response,
            artifact_id=str(parsed_id),
            manifest_profile_sha256=resolved_profile,
        )
        filename = _artifact_filename(str(parsed_id), manifest.kind, manifest.media_type)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        record_data_access_audit(
            request,
            resource_id=str(parsed_id),
            tenant_id=tenant_id,
            metadata={
                "representation": "download",
                "manifest_profile_sha256": resolved_profile,
            },
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


@dataclass(slots=True)
class _ArtifactBatchManifestReadBudget:
    """Track actual Core-reported manifest transfer bytes for one batch request."""

    requested_id_count: int
    limit_source_bytes: int
    consumed_source_bytes: int = 0


def _new_artifact_batch_manifest_read_budget(
    requested_id_count: int,
) -> _ArtifactBatchManifestReadBudget:
    """Derive the batch ceiling from request IDs and the resolver's two bounded reads."""
    if type(requested_id_count) is not int or requested_id_count < 1:
        raise ValueError("artifact_batch_manifest_budget_requires_nonempty_ids")
    max_reads_per_id = 2  # profileless selection reads default metadata, then its exact view
    return _ArtifactBatchManifestReadBudget(
        requested_id_count=requested_id_count,
        limit_source_bytes=(requested_id_count * max_reads_per_id * INSPECTOR_MANIFEST_MAX_BYTES),
    )


def _artifact_batch_manifest_budget_refusal(
    budget: _ArtifactBatchManifestReadBudget,
    *,
    artifact_id: ArtifactID,
    code: str,
    observed_source_bytes: int | None,
) -> Exception:
    """Return an explicit fail-closed batch refusal without exposing a partial batch."""
    return conflict(
        "The selected artifact manifest reads exceed or cannot prove the batch byte budget",
        code=code,
        extensions={
            "artifact_ref_or_route": f"/api/v1/artifacts/{artifact_id}",
            "requested_id_count": budget.requested_id_count,
            "limit_source_bytes": budget.limit_source_bytes,
            "consumed_source_bytes": budget.consumed_source_bytes,
            "observed_source_bytes": observed_source_bytes,
        },
    )


def _consume_artifact_batch_manifest_read(
    budget: _ArtifactBatchManifestReadBudget,
    *,
    artifact_id: ArtifactID,
    observed_source_bytes: int | None,
) -> None:
    """Charge only the immutable physical-transfer receipt returned by Core."""
    if type(observed_source_bytes) is not int or observed_source_bytes < 0:
        raise _artifact_batch_manifest_budget_refusal(
            budget,
            artifact_id=artifact_id,
            code="artifact_batch_manifest_read_usage_unavailable",
            observed_source_bytes=observed_source_bytes,
        )
    budget.consumed_source_bytes += observed_source_bytes
    if budget.consumed_source_bytes > budget.limit_source_bytes:
        raise _artifact_batch_manifest_budget_refusal(
            budget,
            artifact_id=artifact_id,
            code="artifact_batch_manifest_read_budget_exceeded",
            observed_source_bytes=observed_source_bytes,
        )


def _read_selected_artifact_manifest_profile(
    store: ArtifactStore,
    artifact_id: ArtifactID,
    manifest_profile_sha256: str | None,
    *,
    artifact_ref_or_route: str,
    read_budget: _ArtifactBatchManifestReadBudget | None,
) -> CoreJsonManifestBoundedRead:
    """Read one exact metadata selection under both the per-manifest and batch bounds."""
    max_manifest_bytes = INSPECTOR_MANIFEST_MAX_BYTES
    if read_budget is not None:
        remaining_source_bytes = read_budget.limit_source_bytes - read_budget.consumed_source_bytes
        if remaining_source_bytes <= 0:
            raise _artifact_batch_manifest_budget_refusal(
                read_budget,
                artifact_id=artifact_id,
                code="artifact_batch_manifest_read_budget_exceeded",
                observed_source_bytes=0,
            )
        max_manifest_bytes = min(max_manifest_bytes, remaining_source_bytes)

    try:
        manifest_read = read_core_manifest_profile_bounded(
            store,
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
            allow_profile_absent=True,
        )
    except CoreJsonReadBoundsRefusalError as exc:
        if read_budget is not None:
            observed_source_bytes = exc.observed_source_bytes
            if observed_source_bytes is not None:
                _consume_artifact_batch_manifest_read(
                    read_budget,
                    artifact_id=artifact_id,
                    observed_source_bytes=observed_source_bytes,
                )
            if not exc.source_usage_complete or observed_source_bytes is None:
                raise _artifact_batch_manifest_budget_refusal(
                    read_budget,
                    artifact_id=artifact_id,
                    code="artifact_batch_manifest_read_usage_unavailable",
                    observed_source_bytes=observed_source_bytes,
                ) from exc
            if (
                max_manifest_bytes < INSPECTOR_MANIFEST_MAX_BYTES
                and exc.limit_name == "max_manifest_bytes"
            ):
                raise _artifact_batch_manifest_budget_refusal(
                    read_budget,
                    artifact_id=artifact_id,
                    code="artifact_batch_manifest_read_budget_exceeded",
                    observed_source_bytes=observed_source_bytes,
                ) from exc
        raise
    if read_budget is not None:
        _consume_artifact_batch_manifest_read(
            read_budget,
            artifact_id=artifact_id,
            observed_source_bytes=manifest_read.observed_source_bytes,
        )
    return manifest_read


def _resolve_selected_artifact_manifest(
    store: ArtifactStore,
    artifact_id: ArtifactID,
    manifest_profile_sha256: str | None,
    *,
    artifact_ref_or_route: str,
    read_budget: _ArtifactBatchManifestReadBudget | None = None,
) -> CoreJsonManifestBoundedRead:
    """Resolve a default or exact view only through Core's owner-bound bounded reader."""
    try:
        default_read: CoreJsonManifestBoundedRead | None = None
        selected_profile = manifest_profile_sha256
        if selected_profile is None:
            default_read = _read_selected_artifact_manifest_profile(
                store,
                artifact_id,
                None,
                artifact_ref_or_route=artifact_ref_or_route,
                read_budget=read_budget,
            )
            selected_profile = artifact_manifest_profile_sha256(default_read.manifest)

        selected_read = _read_selected_artifact_manifest_profile(
            store,
            artifact_id,
            selected_profile,
            artifact_ref_or_route=artifact_ref_or_route,
            read_budget=read_budget,
        )
        if default_read is not None and selected_read.manifest != default_read.manifest:
            raise CanonicalProfileRefusalError("canon_profile_selected_manifest_changed")
        return selected_read
    except CanonicalProfileRefusalError as exc:
        raise _canonical_profile_conflict(
            exc,
            artifact_ref_or_route=artifact_ref_or_route,
        ) from exc
    except FileNotFoundError as exc:
        if not store.has(artifact_id):
            raise not_found(str(exc), code="artifact_not_found") from exc
        raise not_found(
            "Selected artifact manifest profile is unavailable",
            code="artifact_manifest_profile_not_found",
        ) from exc
    except ArtifactIntegrityError as exc:
        raise conflict(
            "The selected artifact failed CAS integrity verification",
            code="artifact_integrity_failed",
        ) from exc
    except ArtifactOwnershipError as exc:
        raise not_found(
            "Selected artifact manifest profile is unavailable",
            code="artifact_manifest_profile_not_found",
        ) from exc
    except (TypeError, ValueError) as exc:
        raise _canonical_profile_conflict(
            CanonicalProfileRefusalError("canon_profile_selected_manifest_invalid"),
            artifact_ref_or_route=artifact_ref_or_route,
        ) from exc


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


def _ensure_predictive_coverage_diagnostic_admission_allowed(
    payload: object,
    *,
    artifact_ref_or_route: str,
    artifact_store: object,
    artifact_id: ArtifactID,
    artifact_ref: ArtifactRef,
) -> None:
    """Admit only the limited dashboard projection under its candidate policy.

    The projection deliberately has no authority claim, so one exact missing
    base-surface signal is carried as a downgrade. Any selected manifest
    restriction, failed integrity check, scanner finding, or other downgrade
    remains a refusal.
    """
    decision = authority_surface_decision(
        cast("Any", payload),
        surface="dashboard",
        purpose="dashboard_display",
        artifact_ref_or_route=artifact_ref_or_route,
        secret_pii_scope=_PREDICTIVE_COVERAGE_DIAGNOSTIC_SCAN_SCOPE,
        block_on_secret_findings=True,
        artifact_store=cast("Any", artifact_store),
        artifact_id=artifact_id,
        artifact_ref=artifact_ref,
        require_cas_integrity=True,
        missing_authority_disposition="downgrade",
        missing_boundary_disposition="downgrade",
    )
    base_rows = [row for row in decision.authority_contributors if row.basis == "base_surface"]
    selected_rows = [
        row for row in decision.authority_contributors if row.basis == "selected_manifest"
    ]
    expected_projection_downgrade = (
        len(base_rows) == 1
        and base_rows[0].status == "downgraded"
        and base_rows[0].reason == "authority_surface_signal_missing"
        and not base_rows[0].blocking
    )
    selected_manifest_allows_dashboard = all(
        row.status == "allowed" and not row.blocking for row in selected_rows
    )
    if (
        decision.blocking
        or not expected_projection_downgrade
        or not selected_manifest_allows_dashboard
        or decision.integrity_status != "verified"
        or decision.secret_pii_finding_kinds
        or decision.time_source_dispositions
        or decision.s12_issue_codes
        or decision.candidate_firewall_issue_codes
        or "dashboard_display" in decision.may_not_use_for
    ):
        raise conflict(
            "Predictive coverage diagnostic is blocked by composed surface admission",
            code="authority_surface_admission_blocked",
            extensions={
                "artifact_ref_or_route": artifact_ref_or_route,
                "authority_surface_decision": decision.model_dump(mode="json"),
            },
        )


def _ensure_surface_admission_allowed(
    payload: object,
    *,
    artifact_ref_or_route: str,
    surface: str,
    scope: str,
    artifact_store: object | None = None,
    artifact_id: ArtifactID | None = None,
    artifact_ref: ArtifactRef | None = None,
    require_cas_integrity: bool = False,
    technical_inspection_evidence_ref: ArtifactRef | None = None,
) -> None:
    if (
        artifact_ref is not None
        and artifact_id is not None
        and artifact_ref.artifact_id != artifact_id
    ):
        raise bad_request(
            "artifact_ref does not match artifact_id",
            code="artifact_reference_mismatch",
        )
    decision = authority_surface_decision(
        payload,
        surface=surface,
        purpose=TECHNICAL_INSPECTION_PURPOSE if technical_inspection_evidence_ref else None,
        technical_inspection_evidence_ref=technical_inspection_evidence_ref,
        artifact_ref_or_route=artifact_ref_or_route,
        secret_pii_scope=scope,
        block_on_secret_findings=True,
        artifact_store=artifact_store,
        artifact_id=artifact_id,
        artifact_ref=artifact_ref,
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
