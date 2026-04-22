"""Control-plane routes — write operations for launching runs and ingesting data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.control import (
    BindingProfilesListResponse,
    CacheStatusResponse,
    CapabilityManifestResponse,
    CausalFrontierSAEResponse,
    CausalFrontierSAERequest,
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
    IndexStatsResponse,
    IngestRequest,
    IngestResponse,
    LexGraphStatsResponse,
    LexPipelineStatusResponse,
    LexSearchRequest,
    LexSearchResponse,
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
from polisyos.runtime.http.container import resolve_control_service
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
from polisyos.runtime.http.services.sae_spatial_service import SAESpatialService

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Query, Request

    from polisyos.runtime.http.services.control import ControlPlaneService
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Query, Request
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", object)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/control", tags=["control-plane"])


router = _build_router()


def _get_control_service(request: Request) -> ControlPlaneService:
    """Return the startup-initialized control service instance."""
    svc = resolve_control_service(request)
    if svc is None:
        raise RuntimeError("ControlPlaneService was not initialized during application startup")
    return svc


def _get_principal(request: Request) -> RuntimePrincipal:
    claims = getattr(request.state, "user_claims", None)
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
        _, monitoring_report_ref, compare_report_ref, reissue_plan_ref = ctx.feedback.evaluate_run_feedback(run)
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

    @router.get(
        "/runs/{run_id}/decision-validity",
        response_model=DecisionValiditySummaryResponse,
        operation_id="get_run_decision_validity",
        summary="Read full decision validity lifecycle for a run",
    )
    def get_run_decision_validity(
        run_id: str,
        request: Request,
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
        return control.get_decision_validity_summary(
            str(run.decision_packet_ref.artifact_id),
            run_id=run.run_id,
            request_id=request_id,
        )

    @router.get(
        "/decision-packets/{decision_packet_ref}/decision-validity",
        response_model=DecisionValiditySummaryResponse,
        operation_id="get_packet_decision_validity",
        summary="Read full decision validity lifecycle for a decision packet",
    )
    def get_packet_decision_validity(
        decision_packet_ref: str,
        request: Request,
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
        return control.get_decision_validity_summary(
            str(artifact_id),
            request_id=request_id,
        )

    @router.post(
        "/data/ingest",
        response_model=IngestResponse,
        operation_id="ingest_data",
        summary="Trigger data collection from connectors",
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
