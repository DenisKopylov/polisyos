"""Control-plane routes — write operations for launching runs and ingesting data."""

from __future__ import annotations

from polisyos.core.contracts.control import (
    BindingProfilesListResponse,
    CacheStatusResponse,
    CapabilityManifestResponse,
    ConnectorsListResponse,
    DataCatalogSearchResponse,
    DataDiscoverRequest,
    DataDiscoverResponse,
    DataPreviewRequest,
    DataPreviewResponse,
    DataResolveRequest,
    DataResolveResponse,
    IngestRequest,
    IngestResponse,
    IndexStatsResponse,
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
from polisyos.runtime.http.dependencies import (
    build_meta,
    ensure_request_id,
    get_runtime_api_context,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Query, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/control", tags=["control-plane"]) if APIRouter else None


def _get_control_service(request: Request):
    """Lazy-init control service from RuntimeApiContext."""
    from polisyos.runtime.http.services.control import ControlPlaneService

    ctx = get_runtime_api_context(request)
    # Cache on app state to avoid re-creating
    svc = getattr(request.app.state, "_control_service", None)
    if svc is None:
        svc = ControlPlaneService(
            cas_root=ctx.cas_root,
            core_runs_root=ctx.core_runs_root,
        )
        request.app.state._control_service = svc
    return svc


if router is not None:

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
        return control.launch_workflow_run(body, request_id=request_id)

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
        return await control.launch_nl_run(body, request_id=request_id)

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
        return control.trigger_lex_pipeline(body, request_id=request_id)

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
