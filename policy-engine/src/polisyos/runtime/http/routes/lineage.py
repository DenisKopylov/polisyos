"""Runtime lineage lookup routes."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - FastAPI inspects runtime annotations.
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.runtime import (
    LineageBatchRequest,
    LineageBatchResolution,
    LineageBatchResponse,
    LineageExportResponse,
    LineageGraphView,
    LineageResponse,
    ScenarioManifest,
    TemporalScope,
    VerificationMetadata,
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
from polisyos.runtime.http.errors import bad_request, conflict, forbidden
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import lineage_batch_from_bound_request
from polisyos.runtime.http.routes._export_replay import bind_export_replay_or_conflict
from polisyos.runtime.http.services.export_replay import EXPORT_REPLAY_RESPONSE_HEADERS
from polisyos.runtime.http.services.lineage import LineageSurfaceAdmissionError

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    return APIRouter(prefix="/api/v1/lineage", tags=["runtime-lineage"])


router = _build_router()
_GET_LINEAGE_BATCH_AUTHZ = require_action_permission(
    RuntimePermission.LINEAGE_BATCH_READ,
    ResourceBindingSpec(
        source=ResourceBindingSource.RESOLVED_SELECTOR_BATCH,
        resource_kind="runtime.lineage.batch",
        body_field="lineage_ids",
    ),
)


if router is not None:

    @router.get(
        "/{lineage_id}",
        response_model=LineageResponse,
        operation_id="get_lineage",
    )
    def get_lineage(
        lineage_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageResponse:
        temporal_scope = _resolve_lineage_temporal_scope(
            ctx,
            lineage_id=lineage_id,
            response=response,
            surface="lineage",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        tenant_id = _enforce_lineage_scope(lineage_id, request=request, ctx=ctx)
        set_authz_resource(
            request,
            tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
            kind="runtime.lineage",
            artifact_id=lineage_id,
        )
        try:
            lineage = _build_runtime_lineage(ctx, lineage_id, temporal_scope=temporal_scope)
        except LineageSurfaceAdmissionError as exc:
            raise _lineage_admission_conflict(exc, lineage_id=lineage_id) from exc
        record_data_access_audit(
            request,
            resource_id=lineage_id,
            tenant_id=tenant_id,
            metadata={"status": lineage.status, "node_count": len(lineage.nodes)},
        )
        return LineageResponse(
            meta=build_meta(request),
            temporal_scope=temporal_scope,
            lineage=lineage,
        )

    @router.post(
        "/batch",
        response_model=LineageBatchResponse,
        operation_id="get_lineage_batch",
        dependencies=[Depends(_GET_LINEAGE_BATCH_AUTHZ)],
    )
    def get_lineage_batch(
        body: LineageBatchRequest,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageBatchResponse:
        (
            authorized_lineage_ids,
            scenario_manifest_payloads,
            selected_artifact_refs,
            artifact_ref_provenances,
            request_run_id,
            source_run_ids,
        ) = lineage_batch_from_bound_request(
            request,
            ctx=ctx,
            requested_lineage_ids=body.lineage_ids,
            requested_selected_artifact_refs=body.selected_artifact_refs,
            requested_run_id=body.run_id,
        )
        try:
            scenario_manifests = {
                lineage_id: ScenarioManifest.model_validate(payload)
                for lineage_id, payload in scenario_manifest_payloads.items()
            }
        except ValidationError as exc:
            raise forbidden(
                "The authorized scenario lineage manifest is invalid",
                code="authorization_binding_context_invalid",
            ) from exc
        if len(authorized_lineage_ids) != len(body.lineage_ids):
            raise forbidden(
                "The authorized lineage resolutions do not cover the requested batch",
                code="authorization_binding_context_mismatch",
            )
        temporal_scope = _resolve_lineage_temporal_scope(
            ctx,
            lineage_id="lineage.batch",
            response=response,
            surface="lineage_batch",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        tenant_ids = [
            tenant_id
            for lineage_id in authorized_lineage_ids
            if (tenant_id := _enforce_lineage_scope(lineage_id, request=request, ctx=ctx))
        ]
        set_authz_resource(
            request,
            tenant_id=tenant_ids[0] if tenant_ids else getattr(request.state, "tenant_id", None),
            kind="runtime.lineage_batch",
        )
        try:
            lineages = _build_runtime_lineage_batch(
                ctx,
                list(authorized_lineage_ids),
                scenario_manifests=scenario_manifests,
                selected_artifact_refs=selected_artifact_refs,
                artifact_ref_provenances=artifact_ref_provenances,
                request_run_id=request_run_id,
                source_run_ids=source_run_ids,
                temporal_scope=temporal_scope,
            )
        except LineageSurfaceAdmissionError as exc:
            raise _lineage_admission_conflict(exc, lineage_id="lineage.batch") from exc
        except CanonicalProfileRefusalError as exc:
            raise conflict(
                "Selected artifact profile changed during lineage projection",
                code=exc.code,
            ) from exc
        except ValueError as exc:
            raise conflict(
                "Selected artifact profile no longer matches its lineage selector",
                code="authorization_binding_profile_mismatch",
            ) from exc
        if len(lineages) != len(authorized_lineage_ids) or any(
            lineage.id != resolved_id
            for lineage, resolved_id in zip(
                lineages,
                authorized_lineage_ids,
                strict=True,
            )
        ):
            raise conflict(
                "The lineage batch response differs from its authorized resolutions",
                code="lineage_batch_resolution_mismatch",
            )
        # The bound resolver returns one canonical ID per input selector in request order.
        lineage_resolutions = [
            LineageBatchResolution(
                requested_lineage_id=requested_id,
                resolved_lineage_id=resolved_id,
            )
            for requested_id, resolved_id in zip(
                body.lineage_ids,
                authorized_lineage_ids,
                strict=True,
            )
        ]
        record_data_access_audit(
            request,
            resource_id="lineage.batch",
            tenant_id=tenant_ids[0] if tenant_ids else getattr(request.state, "tenant_id", None),
            metadata={"count": len(lineages)},
        )
        return LineageBatchResponse(
            meta=build_meta(request),
            temporal_scope=temporal_scope,
            lineages=lineages,
            lineage_resolutions=lineage_resolutions,
        )

    @router.get(
        "/{lineage_id}/export/openlineage",
        response_model=LineageExportResponse,
        operation_id="export_lineage_openlineage",
        responses={200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS}},
    )
    def export_lineage_openlineage(
        lineage_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        export_projection_hash: str | None = Query(default=None, max_length=128),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageExportResponse:
        return _export_lineage(
            lineage_id,
            format_name="openlineage",
            request=request,
            response=response,
            ctx=ctx,
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
            export_projection_hash=export_projection_hash,
        )

    @router.get(
        "/{lineage_id}/export/prov",
        response_model=LineageExportResponse,
        operation_id="export_lineage_prov",
        responses={200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS}},
    )
    def export_lineage_prov(
        lineage_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        export_projection_hash: str | None = Query(default=None, max_length=128),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> LineageExportResponse:
        return _export_lineage(
            lineage_id,
            format_name="prov",
            request=request,
            response=response,
            ctx=ctx,
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
            export_projection_hash=export_projection_hash,
        )


def _export_lineage(
    lineage_id: str,
    *,
    format_name: str,
    request: Request,
    response: Response,
    ctx: RuntimeApiContext,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
    export_projection_hash: str | None,
) -> LineageExportResponse:
    temporal_scope = _resolve_lineage_temporal_scope(
        ctx,
        lineage_id=lineage_id,
        response=response,
        surface=f"lineage_export.{format_name}",
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    tenant_id = _enforce_lineage_scope(lineage_id, request=request, ctx=ctx)
    set_authz_resource(
        request,
        tenant_id=tenant_id or getattr(request.state, "tenant_id", None),
        kind=f"runtime.lineage_export.{format_name}",
        artifact_id=lineage_id,
    )
    try:
        if ctx.scenarios.is_scenario_lineage(lineage_id):
            payload = ctx.scenarios.export_lineage(lineage_id, format_name=format_name)
        else:
            payload = ctx.lineage.export_runtime_lineage(lineage_id, format_name=format_name)
    except ValueError as exc:
        raise bad_request(str(exc), code="unsupported_lineage_export") from exc
    except LineageSurfaceAdmissionError as exc:
        raise _lineage_admission_conflict(exc, lineage_id=lineage_id) from exc
    record_data_access_audit(
        request,
        resource_id=lineage_id,
        tenant_id=tenant_id,
        metadata={"format": format_name},
    )
    export_response = LineageExportResponse(
        meta=build_meta(request),
        temporal_scope=temporal_scope,
        lineage_id=lineage_id,
        format=cast("Any", format_name),
        payload=payload,
    )
    bind_export_replay_or_conflict(
        request=request,
        response=response,
        semantic_projection=export_response.model_dump(mode="json", exclude={"meta"}),
        as_of=(
            temporal_scope.valid_at or temporal_scope.tx_at
            if temporal_scope is not None
            else export_response.meta.generated_at
        ),
        requested_projection_hash=export_projection_hash,
    )
    return export_response


def _build_runtime_lineage(
    ctx: RuntimeApiContext,
    lineage_id: str,
    *,
    temporal_scope: TemporalScope | None = None,
) -> LineageGraphView:
    if ctx.scenarios.is_scenario_lineage(lineage_id):
        lineage = ctx.scenarios.build_lineage(lineage_id)
    else:
        lineage = ctx.lineage.build_runtime_lineage(lineage_id, enforce_missing_authority=True)
    return _with_trust_metadata(lineage, temporal_scope=temporal_scope)


def _lineage_admission_conflict(
    exc: LineageSurfaceAdmissionError,
    *,
    lineage_id: str,
) -> Exception:
    return conflict(
        "Lineage surface blocked or downgraded by composed authority surface admission",
        code="authority_surface_admission_blocked",
        extensions={
            "lineage_id": lineage_id,
            "authority_surface_decision": exc.decision.model_dump(mode="json"),
        },
    )


def _build_runtime_lineage_batch(
    ctx: RuntimeApiContext,
    lineage_ids: list[str],
    *,
    scenario_manifests: Mapping[str, ScenarioManifest],
    selected_artifact_refs: tuple[Any | None, ...] | None = None,
    artifact_ref_provenances: tuple[str | None, ...] | None = None,
    request_run_id: str | None = None,
    source_run_ids: tuple[str | None, ...] | None = None,
    temporal_scope: TemporalScope | None = None,
) -> list[LineageGraphView]:
    if selected_artifact_refs is not None and len(selected_artifact_refs) != len(lineage_ids):
        raise forbidden(
            "Selected artifact profiles do not align with authorized lineage selectors",
            code="authorization_binding_context_mismatch",
        )
    if artifact_ref_provenances is not None and len(artifact_ref_provenances) != len(lineage_ids):
        raise forbidden(
            "Profile provenance does not align with authorized lineage selectors",
            code="authorization_binding_context_mismatch",
        )
    if source_run_ids is None or len(source_run_ids) != len(lineage_ids):
        raise forbidden(
            "Source run relations do not align with authorized lineage selectors",
            code="authorization_binding_context_mismatch",
        )

    scenario_by_id: dict[str, LineageGraphView] = {}
    runtime_positions: list[int] = []
    runtime_ids: list[str] = []
    runtime_refs: list[Any | None] = []
    resolver_provenances: list[str | None] = []
    resolver_source_run_ids: list[str | None] = []
    authorized_refs = selected_artifact_refs or tuple(None for _ in lineage_ids)
    authorized_provenances = artifact_ref_provenances or tuple(None for _ in lineage_ids)
    for index, lineage_id in enumerate(lineage_ids):
        selected_ref = authorized_refs[index]
        expected_provenance = authorized_provenances[index]
        expected_source_run_id = source_run_ids[index]
        if ctx.scenarios.is_scenario_lineage(lineage_id):
            if selected_ref is not None:
                raise forbidden(
                    "Scenario lineage cannot be bound to a CAS artifact profile",
                    code="authorization_binding_profile_lineage_mismatch",
                )
            if lineage_id not in scenario_by_id:
                manifest = scenario_manifests.get(lineage_id)
                if manifest is None:
                    raise forbidden(
                        "The scenario lineage is absent from its authorized context",
                        code="authorization_binding_context_mismatch",
                    )
                try:
                    scenario_by_id[lineage_id] = ctx.scenarios.build_lineage_for_manifest(
                        lineage_id, manifest
                    )
                except ValueError as exc:
                    raise forbidden(
                        "The scenario lineage differs from its authorized manifest",
                        code="authorization_binding_context_invalid",
                    ) from exc
            if expected_provenance is not None or expected_source_run_id is not None:
                raise forbidden(
                    "Scenario lineage cannot inherit artifact profile provenance",
                    code="authorization_binding_profile_lineage_mismatch",
                )
            continue
        runtime_positions.append(index)
        runtime_ids.append(lineage_id)
        runtime_refs.append(selected_ref)
        resolver_provenances.append(expected_provenance)
        resolver_source_run_ids.append(expected_source_run_id)

    runtime_lineages = ctx.lineage.build_runtime_lineage_batch(
        runtime_ids,
        selected_artifact_refs=runtime_refs,
        run_id=request_run_id,
        enforce_missing_authority=True,
    )
    if len(runtime_lineages) != len(runtime_positions):
        raise conflict(
            "The runtime lineage builder returned an incomplete batch",
            code="lineage_batch_resolution_mismatch",
        )

    result: list[LineageGraphView | None] = [None] * len(lineage_ids)
    for index, lineage_id in enumerate(lineage_ids):
        if ctx.scenarios.is_scenario_lineage(lineage_id):
            lineage = scenario_by_id[lineage_id]
            lineage = lineage.model_copy(
                update={
                    "profile_binding_status": "not_established",
                    "selected_artifact_ref": None,
                    "artifact_ref_provenance": None,
                    "source_run_id": None,
                    "trust_metadata": None,
                }
            )
            result[index] = lineage
    for offset, (position, lineage) in enumerate(
        zip(runtime_positions, runtime_lineages, strict=True)
    ):
        original_index = position
        expected_ref = authorized_refs[original_index]
        expected_provenance = resolver_provenances[offset]
        expected_source_run_id = resolver_source_run_ids[offset]
        if expected_ref is None:
            expected_provenance = None
            expected_source_run_id = None
        if (
            lineage.selected_artifact_ref != expected_ref
            or lineage.artifact_ref_provenance != expected_provenance
            or lineage.source_run_id != expected_source_run_id
            or lineage.profile_binding_status
            != ("verified" if expected_ref is not None else "not_established")
        ):
            raise conflict(
                "The lineage service result differs from its authorized profile context",
                code="lineage_batch_resolution_mismatch",
            )
        result[position] = _with_trust_metadata(lineage, temporal_scope=temporal_scope)
    if any(lineage is None for lineage in result):
        raise conflict(
            "The runtime lineage builder returned an incomplete batch",
            code="lineage_batch_resolution_mismatch",
        )
    return [lineage for lineage in result if lineage is not None]


def _with_trust_metadata(
    lineage: LineageGraphView,
    *,
    temporal_scope: TemporalScope | None,
) -> LineageGraphView:
    if lineage.profile_binding_status == "not_established":
        return lineage.model_copy(update={"trust_metadata": None})
    dispute_status = "disputed" if lineage.status == "disputed" else "none"
    verification_method = (
        "lineage_id_resolution" if lineage.status == "untraced" else "lineage_hash_match"
    )
    return lineage.model_copy(
        update={
            "trust_metadata": VerificationMetadata(
                hash=lineage.hash,
                verification_status=lineage.status,
                verified_by=None,
                verified_at=_latest_lineage_timestamp(lineage),
                verification_method=verification_method,
                freshness=lineage.freshness,
                dispute_status=dispute_status,
                temporal_scope=temporal_scope,
            )
        }
    )


def _latest_lineage_timestamp(lineage: LineageGraphView) -> datetime | None:
    timestamps = [node.timestamp for node in lineage.nodes if node.timestamp is not None]
    if not timestamps:
        return None
    return max(timestamps)


def _resolve_lineage_temporal_scope(
    ctx: RuntimeApiContext,
    *,
    lineage_id: str,
    response: Response,
    surface: str,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
) -> TemporalScope | None:
    scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(scope)
    response.headers["ETag"] = ctx.temporal.response_etag(
        run_id=lineage_id,
        surface=surface,
        scope=scope,
    )
    response.headers.setdefault("Vary", "Accept, Authorization")
    return scope


def _enforce_lineage_scope(
    lineage_id: str,
    *,
    request: Request,
    ctx: RuntimeApiContext,
) -> str | None:
    artifact_id = _parse_artifact_lineage_id(lineage_id)
    if artifact_id is None:
        return getattr(request.state, "tenant_id", None)
    return enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=artifact_id)


def _parse_artifact_lineage_id(lineage_id: str) -> ArtifactID | None:
    candidate = lineage_id.removeprefix("artifact:")
    try:
        return ArtifactID.model_validate(candidate)
    except TypeError, ValueError:
        return None
