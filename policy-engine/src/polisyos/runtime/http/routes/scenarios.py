"""Runtime counterfactual scenario routes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, cast

from polisyos.core.contracts.runtime import (
    CounterfactualMetricsResponse,
    ScenarioCapabilitiesResponse,
    ScenarioCreateRequest,
    ScenarioListResponse,
    ScenarioManifest,
    ScenarioManifestResponse,
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
from polisyos.runtime.http.errors import conflict
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import scenario_target_from_bound_request
from polisyos.runtime.http.response_policies import add_run_link_relations

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Query, Request, Response

    from polisyos.runtime.http.services.run_index import IndexedRunRecord
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
    return APIRouter(prefix="/api/v1", tags=["runtime-scenarios"])


router = _build_router()
_RUNTIME_CONTEXT_DEPENDENCY = Depends(get_runtime_api_context) if Depends is not None else None
OptionalDateTimeQuery = Annotated[datetime | None, Query()]
OptionalTQuery = Annotated[datetime | None, Query(alias="t")]
OptionalStringQuery = Annotated[str | None, Query()]
RequiredScenarioIdQuery = Annotated[str, Query(min_length=1)]
_CREATE_RUN_SCENARIO_AUTHZ = require_action_permission(
    RuntimePermission.SCENARIOS_CREATE,
    ResourceBindingSpec(
        source=ResourceBindingSource.CANDIDATE_TARGET_SLOT,
        resource_kind="runtime.run.scenario.candidate",
        path_parameter="run_id",
        selector_fields=("id",),
    ),
)


@router.get(
    "/runs/{run_id}/scenarios",
    response_model=ScenarioListResponse,
    operation_id="list_run_scenarios",
)
def list_run_scenarios(
    run_id: str,
    request: Request,
    response: Response,
    valid_at: OptionalDateTimeQuery = None,
    tx_at: OptionalDateTimeQuery = None,
    t: OptionalTQuery = None,
    branch: OptionalStringQuery = None,
    snapshot_id: OptionalStringQuery = None,
    scenario_id: OptionalStringQuery = None,
    regime_shift_forecast_bundle_ref: OptionalStringQuery = None,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> ScenarioListResponse:
    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_scenario_temporal_scope(
        ctx,
        run,
        response,
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.run_scenarios",
    )
    scenarios = ctx.scenarios.list_for_run(
        run=run,
        temporal_scope=temporal_scope,
        regime_shift_forecast_bundle_ref=regime_shift_forecast_bundle_ref,
    )
    record_data_access_audit(
        request,
        resource_id=run_id,
        tenant_id=run.details.tenant_id,
        metadata={"scenario_count": len(scenarios)},
    )
    add_run_link_relations(response, run_id=run_id)
    response.headers["Link"] = response.headers.get("Link", "") + (
        f', </api/v1/runs/{run_id}/metrics>; rel="related"'
    )
    return ScenarioListResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run_id=run_id,
        temporal_scope=temporal_scope,
        scenarios=scenarios,
    )


@router.post(
    "/runs/{run_id}/scenarios",
    response_model=ScenarioManifestResponse,
    operation_id="create_run_scenario",
    dependencies=[Depends(_CREATE_RUN_SCENARIO_AUTHZ)],
)
def create_run_scenario(
    run_id: str,
    body: ScenarioCreateRequest,
    request: Request,
    response: Response,
    valid_at: OptionalDateTimeQuery = None,
    tx_at: OptionalDateTimeQuery = None,
    t: OptionalTQuery = None,
    branch: OptionalStringQuery = None,
    snapshot_id: OptionalStringQuery = None,
    scenario_id: OptionalStringQuery = None,
    regime_shift_forecast_bundle_ref: OptionalStringQuery = None,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> ScenarioManifestResponse:
    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_scenario_temporal_scope(
        ctx,
        run,
        response,
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.run_scenario_create",
    )
    authorized_scenario_id, expected_revision = scenario_target_from_bound_request(
        request,
        run=run,
        requested_id=body.id,
    )
    manifest = ctx.scenarios.create_for_run(
        run=run,
        request=body,
        temporal_scope=temporal_scope,
        regime_shift_forecast_bundle_ref=regime_shift_forecast_bundle_ref,
        authorized_scenario_id=authorized_scenario_id,
        expected_revision=expected_revision,
    )
    record_data_access_audit(
        request,
        resource_id=manifest.id,
        tenant_id=run.details.tenant_id,
        outcome="scenario_draft_saved",
        metadata={"baseline_run_id": run_id},
    )
    response.headers["Location"] = f"/api/v1/scenarios/{manifest.id}"
    return ScenarioManifestResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        temporal_scope=temporal_scope,
        scenario=manifest,
    )


@router.get(
    "/runs/{run_id}/metrics",
    response_model=CounterfactualMetricsResponse,
    operation_id="get_run_counterfactual_metrics",
)
def get_run_counterfactual_metrics(
    run_id: str,
    request: Request,
    response: Response,
    scenario_id: RequiredScenarioIdQuery,
    valid_at: OptionalDateTimeQuery = None,
    tx_at: OptionalDateTimeQuery = None,
    t: OptionalTQuery = None,
    branch: OptionalStringQuery = None,
    snapshot_id: OptionalStringQuery = None,
    regime_shift_forecast_bundle_ref: OptionalStringQuery = None,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> CounterfactualMetricsResponse:
    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_scenario_temporal_scope(
        ctx,
        run,
        response,
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.run_counterfactual_metrics",
    )
    manifest, metrics = ctx.scenarios.build_metrics(
        run=run,
        scenario_id=scenario_id,
        temporal_scope=temporal_scope,
        regime_shift_forecast_bundle_ref=regime_shift_forecast_bundle_ref,
    )
    record_data_access_audit(
        request,
        resource_id=f"{run_id}:{scenario_id}",
        tenant_id=run.details.tenant_id,
        metadata={"metric_count": len(metrics), "scenario_status": manifest.status},
    )
    response.headers["X-Scenario-Scope"] = manifest.id
    add_run_link_relations(response, run_id=run_id)
    return CounterfactualMetricsResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run_id=run_id,
        temporal_scope=temporal_scope,
        scenario=manifest,
        metrics=metrics,
    )


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioManifestResponse,
    operation_id="get_scenario_manifest",
)
def get_scenario_manifest(
    scenario_id: str,
    request: Request,
    response: Response,
    valid_at: OptionalDateTimeQuery = None,
    tx_at: OptionalDateTimeQuery = None,
    t: OptionalTQuery = None,
    branch: OptionalStringQuery = None,
    snapshot_id: OptionalStringQuery = None,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> ScenarioManifestResponse:
    manifest = ctx.scenarios.get_manifest(scenario_id)
    run = ctx.run_index.get_run(manifest.baseline_run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    requested_scope = _resolve_manifest_request_scope(
        ctx,
        run,
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    _validate_manifest_temporal_identity(
        manifest_scope=manifest.temporal_scope,
        requested_scope=requested_scope,
    )
    temporal_scope = requested_scope or manifest.temporal_scope
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(temporal_scope)
    response.headers["ETag"] = _scenario_manifest_etag(manifest, temporal_scope)
    response.headers.setdefault("Vary", "Accept, Authorization")
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.scenario_manifest",
    )
    record_data_access_audit(
        request,
        resource_id=scenario_id,
        tenant_id=run.details.tenant_id,
        metadata={"baseline_run_id": manifest.baseline_run_id},
    )
    return ScenarioManifestResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        temporal_scope=temporal_scope,
        scenario=manifest,
    )


@router.get(
    "/scenarios/{scenario_id}/capabilities",
    response_model=ScenarioCapabilitiesResponse,
    operation_id="get_scenario_capabilities",
)
def get_scenario_capabilities(
    scenario_id: str,
    request: Request,
    response: Response,
    valid_at: OptionalDateTimeQuery = None,
    tx_at: OptionalDateTimeQuery = None,
    t: OptionalTQuery = None,
    branch: OptionalStringQuery = None,
    snapshot_id: OptionalStringQuery = None,
    regime_shift_forecast_bundle_ref: OptionalStringQuery = None,
    ctx: RuntimeApiContext = _RUNTIME_CONTEXT_DEPENDENCY,
) -> ScenarioCapabilitiesResponse:
    manifest = ctx.scenarios.get_manifest(scenario_id)
    run = ctx.run_index.get_run(manifest.baseline_run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    temporal_scope = _resolve_scenario_temporal_scope(
        ctx,
        run,
        response,
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="runtime.scenario_capabilities",
    )
    capabilities = ctx.scenarios.capabilities_for_run(
        run=run,
        temporal_scope=temporal_scope,
        regime_shift_forecast_bundle_ref=regime_shift_forecast_bundle_ref,
    )
    record_data_access_audit(
        request,
        resource_id=scenario_id,
        tenant_id=run.details.tenant_id,
        metadata={"capability_count": len(capabilities)},
    )
    return ScenarioCapabilitiesResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run_id=run.run_id,
        scenario_id=scenario_id,
        temporal_scope=temporal_scope,
        capabilities=capabilities,
    )


def _resolve_scenario_temporal_scope(
    ctx: RuntimeApiContext,
    run: IndexedRunRecord,
    response: Response,
    *,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
) -> TemporalScope | None:
    if not any((valid_at, tx_at, t, branch, snapshot_id)):
        return None
    scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    scope = ctx.temporal.materialize_run_scope(run, scope)
    ctx.temporal.validate_run_scope(run, scope, surface="run_quantities")
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(scope)
    response.headers["ETag"] = ctx.temporal.response_etag(
        run_id=run.run_id,
        surface="run_metrics",
        scope=scope,
    )
    response.headers.setdefault("Vary", "Accept, Authorization")
    return scope


def _resolve_manifest_request_scope(
    ctx: RuntimeApiContext,
    run: IndexedRunRecord,
    *,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str,
) -> TemporalScope | None:
    if not any((valid_at, tx_at, t, branch, snapshot_id)):
        return None
    scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    if scope is None:
        return None
    scope = ctx.temporal.materialize_run_scope(run, scope)
    ctx.temporal.validate_run_scope(run, scope, surface="run_quantities")
    return scope


def _validate_manifest_temporal_identity(
    *,
    manifest_scope: TemporalScope | None,
    requested_scope: TemporalScope | None,
) -> None:
    if manifest_scope is None or requested_scope is None:
        return
    manifest_payload = _scope_identity_payload(manifest_scope)
    requested_payload = _scope_identity_payload(requested_scope)
    mismatches = {
        key: {"manifest": manifest_payload.get(key), "requested": requested_payload.get(key)}
        for key in sorted(set(manifest_payload) | set(requested_payload))
        if manifest_payload.get(key) != requested_payload.get(key)
    }
    if mismatches:
        raise conflict(
            "Scenario manifest temporal scope does not match requested temporal scope",
            code="scenario_temporal_scope_mismatch",
            extensions={
                "manifest_temporal_scope": manifest_payload,
                "requested_temporal_scope": requested_payload,
                "mismatches": mismatches,
            },
        )


def _scope_identity_payload(scope: TemporalScope) -> dict[str, str | None]:
    return {
        "valid_at": scope.valid_at.isoformat() if scope.valid_at else None,
        "tx_at": scope.tx_at.isoformat() if scope.tx_at else None,
        "branch": scope.branch,
        "snapshot_id": scope.snapshot_id,
        "scenario_id": scope.scenario_id,
    }


def _scenario_manifest_etag(
    manifest: ScenarioManifest,
    temporal_scope: TemporalScope | None,
) -> str:
    payload = {
        "manifest_hash": manifest.manifest_hash,
        "revision": manifest.revision,
        "scenario_id": manifest.id,
        "scope": temporal_scope.model_dump(mode="json")
        if temporal_scope is not None
        else "current",
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f'W/"scenario-manifest-{digest[:24]}"'


__all__ = ["router"]
