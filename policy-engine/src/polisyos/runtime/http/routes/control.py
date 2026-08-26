"""Control-plane routes — write operations for launching runs and ingesting data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.control import (
    BindingProfilesListResponse,
    CacheStatusResponse,
    CapabilityManifestResponse,
    CausalFrontierSAERequest,
    CausalFrontierSAEResponse,
    ConnectorsListResponse,
    ControlJobResponse,
    ControlOutboxEventsResponse,
    ControlWorkersResponse,
    DataCatalogSearchResponse,
    DataDiscoverRequest,
    DataDiscoverResponse,
    DataPreviewRequest,
    DataPreviewResponse,
    DataResolveRequest,
    DataResolveResponse,
    DecisionValidityEventRequest,
    DecisionValidityEventResponse,
    DecisionValiditySummaryResponse,
    EpochValidityBatchRequest,
    EpochValidityBatchResponse,
    IndexStatsResponse,
    IngestRequest,
    IngestResponse,
    LexGraphStatsResponse,
    LexPipelineStatusResponse,
    LexSearchRequest,
    LexTriggerRequest,
    LexTriggerResponse,
    ModelProfilesListResponse,
    NaturalLanguageRunRequest,
    PromotionCandidatesResponse,
    PromotionDecisionRequest,
    PromotionDecisionResponse,
    RunLaunchResponse,
    SourceProfilesListResponse,
    WorkflowRunRequest,
)
from polisyos.core.contracts.runtime import FeedbackActionResponse
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.container import resolve_control_service
from polisyos.runtime.http.dependencies import (
    RuntimeAccessScope as AccessScope,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_artifact_tenant_access,
    enforce_run_tenant_access,
    ensure_request_id,
    get_runtime_api_context,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request, not_found
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.routes._export_replay import bind_export_replay_or_conflict
from polisyos.runtime.http.security import is_fixture_identity_claims
from polisyos.runtime.http.services.control.lex_search_projection import LexSearchResponse
from polisyos.runtime.http.services.export_replay import EXPORT_REPLAY_RESPONSE_HEADERS
from polisyos.runtime.http.services.sae_spatial_service import SAESpatialService
from polisyos.runtime.http.step_up import StepUpClass, require_step_up

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Query, Request, Response

    from polisyos.runtime.http.services.control import ControlPlaneService
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Query, Request, Response
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", object)
        Response = cast("Any", object)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/control", tags=["control-plane"])


router = _build_router()
_LAUNCH_RUN_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_LAUNCH,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.run_collection",
    ),
)
_EVALUATE_RUN_FEEDBACK_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_FEEDBACK_EVALUATE,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.feedback_evaluation",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)
_LAUNCH_NL_RUN_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_LAUNCH,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.run_collection.nl",
    ),
)
_REISSUE_RUN_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REISSUE,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.reissue",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)
_PUBLISH_DECISION_VALIDITY_AUTHZ = require_action_permission(
    RuntimePermission.DECISIONS_VALIDITY_PUBLISH,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.decision_validity.event",
        selector_fields=("source_ref", "dependency_keys", "dedupe_key"),
    ),
)
_ADMIT_EPOCH_VALIDITY_BATCH_AUTHZ = require_action_permission(
    RuntimePermission.DECISIONS_VALIDITY_PUBLISH,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.decision_validity.epoch_batch",
        selector_fields=("transition_artifact_ref", "requested_query_context_ref"),
        required_selector_fields=(
            "transition_artifact_ref",
            "requested_query_context_ref",
        ),
    ),
)
_INGEST_DATA_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_ACQUIRE,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.acquisition",
        selector_fields=(
            "binding_profile_id",
            "connection_profile",
            "datasets",
            "fetch_plans",
        ),
        required_selector_alternatives=(("datasets",), ("fetch_plans",)),
    ),
)
_RESOLVE_DATA_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_RESOLVE,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.resolve",
        selector_fields=("data_needs",),
        required_selector_fields=("data_needs",),
    ),
)
_DISCOVER_DATA_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_DISCOVER,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.discover",
        selector_fields=("data_needs",),
        required_selector_fields=("data_needs",),
    ),
)
_PREVIEW_DATA_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_PREVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.preview",
        selector_fields=("fetch_plan",),
        required_selector_fields=("fetch_plan",),
    ),
)
_ESTIMATE_SAE_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_SAE_ANALYZE,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.evidence.sae_causal_frontier",
        selector_fields=("bundle_dir", "areas", "edges", "exposure", "output_dir"),
        required_selector_alternatives=(("bundle_dir",), ("areas", "edges")),
    ),
)
_APPROVE_PROMOTION_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
    ResourceBindingSpec(
        source=ResourceBindingSource.RESOLVED_SELECTOR,
        resource_kind="runtime.evidence.promotion.approve",
        path_parameter="promotion_id",
    ),
)
_REJECT_PROMOTION_AUTHZ = require_action_permission(
    RuntimePermission.EVIDENCE_PROMOTIONS_REJECT,
    ResourceBindingSpec(
        source=ResourceBindingSource.RESOLVED_SELECTOR,
        resource_kind="runtime.evidence.promotion.reject",
        path_parameter="promotion_id",
    ),
)
_TRIGGER_LEX_AUTHZ = require_action_permission(
    RuntimePermission.KNOWLEDGE_TRIGGER,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.lex_workspace.trigger",
    ),
)
_SEARCH_LEX_AUTHZ = require_action_permission(
    RuntimePermission.KNOWLEDGE_SEARCH,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.lex_workspace.search",
    ),
)
_REISSUE_RUN_STEP_UP = require_step_up(StepUpClass.REVOCATION)
_PUBLISH_DECISION_VALIDITY_STEP_UP = require_step_up(StepUpClass.PUBLICATION)
_INGEST_DATA_STEP_UP = require_step_up(StepUpClass.ACQUISITION_APPROVAL)
_APPROVE_PROMOTION_STEP_UP = require_step_up(StepUpClass.PROMOTION)
_REJECT_PROMOTION_STEP_UP = require_step_up(StepUpClass.PROMOTION)


def _get_control_service(request: Request) -> ControlPlaneService:
    """Return the startup-initialized control service instance."""
    svc = resolve_control_service(request)
    if svc is None:
        raise RuntimeError("ControlPlaneService was not initialized during application startup")
    return svc


def _get_principal(request: Request) -> RuntimePrincipal:
    claims = getattr(request.state, "user_claims", None)
    effective_scope = getattr(request.state, "authz_effective_scope", None)
    if isinstance(effective_scope, AccessScope):
        return RuntimePrincipal.from_access_scope(
            effective_scope,
            fixture_identity=is_fixture_identity_claims(claims),
        )
    return RuntimePrincipal.from_user_claims(claims)


def _artifact_ref(artifact_id: str | None, *, kind: str, media_type: str) -> ArtifactRef | None:
    if artifact_id is None:
        return None
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(artifact_id),
        kind=kind,
        media_type=media_type,
    )


@router.post(
    "/runs",
    response_model=RunLaunchResponse,
    operation_id="launch_run",
    summary="Launch a workflow run",
    dependencies=[Depends(_LAUNCH_RUN_AUTHZ)],
)
def launch_run(
    body: WorkflowRunRequest,
    request: Request,
) -> RunLaunchResponse:
    set_authz_resource(
        request,
        tenant_id=getattr(request.state, "tenant_id", None),
        kind="control.launch_run",
    )
    # Validate that at least one data source is provided
    ds = body.data_source
    if not ds.data_snapshot_ref and not ds.input_bindings_ref and not ds.data_view_request_ref:
        raise bad_request(
            "At least one data source must be provided",
            code="missing_data_source",
        )
    control = _get_control_service(request)
    request_id = ensure_request_id(request)
    return control.launch_workflow_run(
        body,
        request_id=request_id,
        principal=_get_principal(request),
    )


@router.post(
    "/runs/{run_id}/feedback/evaluate",
    response_model=FeedbackActionResponse,
    operation_id="evaluate_run_feedback",
    summary="Evaluate post-deployment monitoring for a run",
    dependencies=[Depends(_EVALUATE_RUN_FEEDBACK_AUTHZ)],
)
def evaluate_run_feedback(
    run_id: str,
    request: Request,
    ctx: RuntimeApiContext = Depends(get_runtime_api_context),
) -> FeedbackActionResponse:
    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="control.evaluate_feedback",
    )
    _, monitoring_report_ref, compare_report_ref, reissue_plan_ref = (
        ctx.feedback.evaluate_run_feedback(run)
    )
    return FeedbackActionResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run_id=run_id,
        action="evaluate_feedback",
        status="completed",
        monitoring_report_ref=_artifact_ref(
            monitoring_report_ref,
            kind="scientist.decision_monitoring_report",
            media_type="application/json",
        ),
        compare_report_ref=_artifact_ref(
            compare_report_ref,
            kind="scientist.decision_compare_report",
            media_type="application/json",
        ),
        reissue_plan_ref=_artifact_ref(
            reissue_plan_ref,
            kind="scientist.decision_reissue_plan",
            media_type="application/json",
        ),
        message=f"Feedback evaluation for run {run_id} completed.",
    )


@router.post(
    "/runs/nl",
    response_model=RunLaunchResponse,
    operation_id="launch_nl_run",
    summary="Launch a natural-language run via agent circuit",
    dependencies=[Depends(_LAUNCH_NL_RUN_AUTHZ)],
)
async def launch_nl_run(
    body: NaturalLanguageRunRequest,
    request: Request,
) -> RunLaunchResponse:
    set_authz_resource(
        request,
        tenant_id=getattr(request.state, "tenant_id", None),
        kind="control.launch_nl_run",
    )
    control = _get_control_service(request)
    request_id = ensure_request_id(request)
    return await control.launch_nl_run(
        body,
        request_id=request_id,
        principal=_get_principal(request),
    )


@router.post(
    "/runs/{run_id}/reissue",
    response_model=FeedbackActionResponse,
    operation_id="reissue_run",
    summary="Create a human-gated reissue run",
    dependencies=[Depends(_REISSUE_RUN_AUTHZ), Depends(_REISSUE_RUN_STEP_UP)],
)
def reissue_run(
    run_id: str,
    request: Request,
    ctx: RuntimeApiContext = Depends(get_runtime_api_context),
) -> FeedbackActionResponse:
    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    set_authz_resource(
        request,
        tenant_id=run.details.tenant_id,
        kind="control.reissue_run",
    )
    control = _get_control_service(request)
    payload = control.reissue_run(
        run_id,
        request_id=ensure_request_id(request),
        principal=_get_principal(request),
    )
    return FeedbackActionResponse(
        meta=build_meta(request, source_kinds=[run.source_kind]),
        run_id=run_id,
        action="reissue",
        status="accepted",
        monitoring_report_ref=_artifact_ref(
            payload.get("monitoring_report_ref"),
            kind="scientist.decision_monitoring_report",
            media_type="application/json",
        ),
        compare_report_ref=_artifact_ref(
            payload.get("compare_report_ref"),
            kind="scientist.decision_compare_report",
            media_type="application/json",
        ),
        reissue_plan_ref=_artifact_ref(
            payload.get("reissue_plan_ref"),
            kind="scientist.decision_reissue_plan",
            media_type="application/json",
        ),
        reissued_run_id=payload.get("run_id"),
        message=str(payload.get("message") or f"Reissue for run {run_id} accepted."),
    )


if router is not None:

    @router.get(
        "/jobs/{job_id}",
        response_model=ControlJobResponse,
        operation_id="get_control_job_status",
        summary="Get durable control job status",
    )
    def get_control_job_status(
        job_id: str,
        request: Request,
    ) -> ControlJobResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.job_status",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.get_job_status(job_id, request_id=request_id)

    @router.get(
        "/workers",
        response_model=ControlWorkersResponse,
        operation_id="list_control_workers",
        summary="List control-plane worker leases",
    )
    def list_control_workers(
        request: Request,
        active_only: bool = Query(default=True),
    ) -> ControlWorkersResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.workers",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_control_workers(
            active_only=active_only,
            request_id=request_id,
        )

    @router.get(
        "/outbox",
        response_model=ControlOutboxEventsResponse,
        operation_id="list_control_outbox",
        summary="List durable control-plane outbox events",
    )
    def list_control_outbox(
        request: Request,
        state: str | None = Query(default="pending"),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> ControlOutboxEventsResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.outbox",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_control_outbox(
            state=state,
            limit=limit,
            request_id=request_id,
        )

    @router.post(
        "/decision-validity/events",
        response_model=DecisionValidityEventResponse,
        operation_id="publish_decision_validity_event",
        summary="Publish a durable decision invalidation event",
        dependencies=[
            Depends(_PUBLISH_DECISION_VALIDITY_AUTHZ),
            Depends(_PUBLISH_DECISION_VALIDITY_STEP_UP),
        ],
    )
    def publish_decision_validity_event(
        body: DecisionValidityEventRequest,
        request: Request,
    ) -> DecisionValidityEventResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.publish_decision_validity_event",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.publish_decision_validity_event(body, request_id=request_id)

    @router.post(
        "/decision-validity/epoch-batches",
        response_model=EpochValidityBatchResponse,
        operation_id="admit_epoch_validity_batch",
        summary="Admit one owner-verified semantic-epoch validity batch",
        dependencies=[
            Depends(_ADMIT_EPOCH_VALIDITY_BATCH_AUTHZ),
            Depends(_PUBLISH_DECISION_VALIDITY_STEP_UP),
        ],
    )
    def admit_epoch_validity_batch(
        body: EpochValidityBatchRequest,
        request: Request,
    ) -> EpochValidityBatchResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.admit_epoch_validity_batch",
        )
        control = _get_control_service(request)
        return control.admit_epoch_validity_batch(
            body,
            request_id=ensure_request_id(request),
        )

    @router.get(
        "/runs/{run_id}/decision-validity",
        response_model=DecisionValiditySummaryResponse,
        operation_id="get_run_decision_validity",
        summary="Read full decision validity lifecycle for a run",
        responses={200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS}},
    )
    def get_run_decision_validity(
        run_id: str,
        request: Request,
        response: Response,
        export_projection_hash: str | None = Query(default=None, max_length=128),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> DecisionValiditySummaryResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        if run.decision_packet_ref is None:
            raise not_found(
                f"Run {run_id} does not have a decision packet.",
                code="decision_packet_missing",
            )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="control.read_decision_validity",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        summary = control.get_decision_validity_summary(
            str(run.decision_packet_ref.artifact_id),
            run_id=run.run_id,
            request_id=request_id,
        )
        bind_export_replay_or_conflict(
            request=request,
            response=response,
            semantic_projection=summary.model_dump(
                mode="json",
                exclude={"meta", "checked_at"},
            ),
            as_of=summary.checked_at,
            requested_projection_hash=export_projection_hash,
        )
        return summary

    @router.get(
        "/decision-packets/{decision_packet_ref}/decision-validity",
        response_model=DecisionValiditySummaryResponse,
        operation_id="get_packet_decision_validity",
        summary="Read full decision validity lifecycle for a decision packet",
        responses={200: {"headers": EXPORT_REPLAY_RESPONSE_HEADERS}},
    )
    def get_packet_decision_validity(
        decision_packet_ref: str,
        request: Request,
        response: Response,
        export_projection_hash: str | None = Query(default=None, max_length=128),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> DecisionValiditySummaryResponse:
        artifact_id = ArtifactID.model_validate(decision_packet_ref)
        tenant_id = enforce_artifact_tenant_access(
            request,
            ctx=ctx,
            artifact_id=artifact_id,
        )
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="control.read_decision_validity",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        summary = control.get_decision_validity_summary(
            str(artifact_id),
            request_id=request_id,
        )
        bind_export_replay_or_conflict(
            request=request,
            response=response,
            semantic_projection=summary.model_dump(
                mode="json",
                exclude={"meta", "checked_at"},
            ),
            as_of=summary.checked_at,
            requested_projection_hash=export_projection_hash,
        )
        return summary

    @router.post(
        "/data/ingest",
        response_model=IngestResponse,
        operation_id="ingest_data",
        summary="Trigger data collection from connectors",
        dependencies=[Depends(_INGEST_DATA_AUTHZ), Depends(_INGEST_DATA_STEP_UP)],
    )
    def ingest_data(
        body: IngestRequest,
        request: Request,
    ) -> IngestResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.ingest_data",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.run_data_ingestion(body, request_id=request_id)

    @router.post(
        "/data/resolve",
        response_model=DataResolveResponse,
        operation_id="resolve_data_needs",
        summary="Resolve DataNeeds into FetchPlans",
        dependencies=[Depends(_RESOLVE_DATA_AUTHZ)],
    )
    def resolve_data_needs(
        body: DataResolveRequest,
        request: Request,
    ) -> DataResolveResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.resolve_data",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.data_resolve(body, request_id=request_id)

    @router.post(
        "/data/discover",
        response_model=DataDiscoverResponse,
        operation_id="discover_data_sources",
        summary="Run bounded ExploreLane discovery",
        dependencies=[Depends(_DISCOVER_DATA_AUTHZ)],
    )
    def discover_data_sources(
        body: DataDiscoverRequest,
        request: Request,
    ) -> DataDiscoverResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.discover_data",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.data_discover(body, request_id=request_id)

    @router.post(
        "/data/preview",
        response_model=DataPreviewResponse,
        operation_id="preview_fetch_plan",
        summary="Preview FetchPlan with quality gate",
        dependencies=[Depends(_PREVIEW_DATA_AUTHZ)],
    )
    def preview_fetch_plan(
        body: DataPreviewRequest,
        request: Request,
    ) -> DataPreviewResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.preview_data",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.data_preview(body, request_id=request_id)

    @router.post(
        "/analytics/sae/causal-frontier",
        response_model=CausalFrontierSAEResponse,
        operation_id="estimate_causal_frontier_sae",
        summary="Run boundary-constrained causal-frontier small-area estimation",
        dependencies=[Depends(_ESTIMATE_SAE_AUTHZ)],
    )
    def estimate_causal_frontier_sae(
        body: CausalFrontierSAERequest,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> CausalFrontierSAEResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.causal_frontier_sae",
        )
        service = SAESpatialService(store=ctx.store)
        try:
            payload = service.estimate_causal_frontier(body)
        except (FileNotFoundError, OSError, KeyError, TypeError, ValueError) as exc:
            raise bad_request(str(exc), code="causal_frontier_sae_invalid") from exc

        estimates = payload["estimates"].to_dict(orient="records")
        return CausalFrontierSAEResponse(
            meta=build_meta(request),
            method_name=payload["result"].method_name,
            estimates=estimates,
            diagnostics=payload["diagnostics"],
            governance_artifact=payload["governance_artifact"],
            artifact_refs=payload["output_refs"],
            output_bundle=payload["output_bundle"],
        )

    @router.get(
        "/capabilities",
        response_model=CapabilityManifestResponse,
        operation_id="get_control_capabilities",
        summary="Get control-plane capability manifest",
    )
    def get_control_capabilities(request: Request) -> CapabilityManifestResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.capabilities",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.get_capabilities(request_id=request_id)

    @router.get(
        "/data/catalog/search",
        response_model=DataCatalogSearchResponse,
        operation_id="search_data_catalog",
        summary="Search metric catalog candidates",
    )
    def search_data_catalog(
        request: Request,
        metric: str = Query(..., min_length=1),
        geo: str | None = Query(default=None),
        limit: int = Query(default=25, ge=1, le=200),
    ) -> DataCatalogSearchResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.search_data_catalog",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.search_data_catalog(
            metric_query=metric,
            geography=geo,
            limit=limit,
            request_id=request_id,
        )

    @router.get(
        "/data/index/stats",
        response_model=IndexStatsResponse,
        operation_id="get_data_index_stats",
        summary="Get local retrieval index statistics",
    )
    def get_data_index_stats(request: Request) -> IndexStatsResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.data_index_stats",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.get_data_index_stats(request_id=request_id)

    @router.get(
        "/data/promotion/candidates",
        response_model=PromotionCandidatesResponse,
        operation_id="list_data_promotion_candidates",
        summary="List PromotionLane candidates",
    )
    def list_data_promotion_candidates(request: Request) -> PromotionCandidatesResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.list_promotion_candidates",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_promotion_candidates(request_id=request_id)

    @router.post(
        "/data/promotion/{promotion_id}/approve",
        response_model=PromotionDecisionResponse,
        operation_id="approve_data_promotion",
        summary="Approve PromotionLane candidate",
        dependencies=[
            Depends(_APPROVE_PROMOTION_AUTHZ),
            Depends(_APPROVE_PROMOTION_STEP_UP),
        ],
    )
    def approve_data_promotion(
        promotion_id: str,
        body: PromotionDecisionRequest,
        request: Request,
    ) -> PromotionDecisionResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.approve_promotion_candidate",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.approve_promotion_candidate(
            promotion_id,
            body,
            request_id=request_id,
        )

    @router.post(
        "/data/promotion/{promotion_id}/reject",
        response_model=PromotionDecisionResponse,
        operation_id="reject_data_promotion",
        summary="Reject PromotionLane candidate",
        dependencies=[
            Depends(_REJECT_PROMOTION_AUTHZ),
            Depends(_REJECT_PROMOTION_STEP_UP),
        ],
    )
    def reject_data_promotion(
        promotion_id: str,
        body: PromotionDecisionRequest,
        request: Request,
    ) -> PromotionDecisionResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.reject_promotion_candidate",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.reject_promotion_candidate(
            promotion_id,
            body,
            request_id=request_id,
        )

    @router.get(
        "/data/connectors",
        response_model=ConnectorsListResponse,
        operation_id="list_connectors",
        summary="List available data connectors",
    )
    def list_connectors(
        request: Request,
    ) -> ConnectorsListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.list_connectors",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_connectors(request_id=request_id)

    @router.get(
        "/data/cache",
        response_model=CacheStatusResponse,
        operation_id="get_cache_status",
        summary="Get data cache status",
    )
    def get_cache_status(
        request: Request,
    ) -> CacheStatusResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.cache_status",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.get_cache_status(request_id=request_id)

    @router.get(
        "/llm/profiles",
        response_model=ModelProfilesListResponse,
        operation_id="list_llm_profiles",
        summary="List available LLM model profiles",
    )
    def list_llm_profiles(
        request: Request,
    ) -> ModelProfilesListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.list_llm_profiles",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_model_profiles(request_id=request_id)

    @router.get(
        "/data/profiles",
        response_model=SourceProfilesListResponse,
        operation_id="list_source_profiles",
        summary="List available source profiles",
    )
    def list_source_profiles(
        request: Request,
    ) -> SourceProfilesListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.list_profiles",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_source_profiles(request_id=request_id)

    @router.get(
        "/data/binding-profiles",
        response_model=BindingProfilesListResponse,
        operation_id="list_binding_profiles",
        summary="List available binding profiles",
    )
    def list_binding_profiles(
        request: Request,
    ) -> BindingProfilesListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.list_binding_profiles",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.list_binding_profiles(request_id=request_id)

    # ---- Lex Knowledge Graph -----------------------------------------------

    @router.post(
        "/lex/trigger",
        response_model=LexTriggerResponse,
        operation_id="trigger_lex_pipeline",
        summary="Start Lex batch pipeline in background",
        dependencies=[Depends(_TRIGGER_LEX_AUTHZ)],
    )
    def trigger_lex_pipeline(
        body: LexTriggerRequest,
        request: Request,
    ) -> LexTriggerResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.lex_trigger",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.trigger_lex_pipeline(
            body,
            request_id=request_id,
            principal=_get_principal(request),
        )

    @router.get(
        "/lex/status/{pipeline_id}",
        response_model=LexPipelineStatusResponse,
        operation_id="get_lex_pipeline_status",
        summary="Get Lex pipeline execution status",
    )
    def get_lex_pipeline_status(
        pipeline_id: str,
        request: Request,
    ) -> LexPipelineStatusResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.lex_status",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.get_lex_pipeline_status(pipeline_id, request_id=request_id)

    @router.get(
        "/lex/graph/stats",
        response_model=LexGraphStatsResponse,
        operation_id="get_lex_graph_stats",
        summary="Get Lex knowledge graph statistics",
    )
    def get_lex_graph_stats(
        request: Request,
        output_dir: str = Query(..., min_length=1),
    ) -> LexGraphStatsResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.lex_stats",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.get_lex_graph_stats(output_dir, request_id=request_id)

    @router.post(
        "/lex/search",
        response_model=LexSearchResponse,
        operation_id="search_lex_graph",
        summary="Search Lex knowledge graph facts",
        dependencies=[Depends(_SEARCH_LEX_AUTHZ)],
    )
    def search_lex_graph(
        body: LexSearchRequest,
        request: Request,
    ) -> LexSearchResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="control.lex_search",
        )
        control = _get_control_service(request)
        request_id = ensure_request_id(request)
        return control.search_lex_graph(body, request_id=request_id)


__all__ = ["router"]
