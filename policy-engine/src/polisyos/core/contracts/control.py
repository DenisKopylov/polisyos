"""Control Plane contracts — request/response DTOs for write operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime import ApiMeta

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

RunMode = Literal["workflow", "agent_circuit"]
CheckpointPolicyType = Literal["strict", "lenient", "disabled"]
CachePolicyType = Literal["default", "static", "volatile", "smart"]
RunLaunchStatus = Literal["accepted", "rejected"]
IngestStatus = Literal["completed", "partial", "failed"]
ExecutionMode = Literal["batch_full", "batch_incremental", "streaming_windowed"]
RetrievalMode = Literal["fastlane", "explorelane", "hybrid"]
CandidateLane = Literal["fastlane", "explorelane"]
PreviewStatus = Literal["ok", "insufficient_coverage", "error"]
PromotionStatus = Literal["pending", "approved", "rejected"]

# ---------------------------------------------------------------------------
# Data source binding
# ---------------------------------------------------------------------------


class DataSourceBinding(BaseModel):
    """Exactly one of these fields must be provided."""

    model_config = ConfigDict(extra="forbid")

    data_snapshot_ref: str | None = None
    input_bindings_ref: str | None = None
    data_view_request_ref: str | None = None


# ---------------------------------------------------------------------------
# Workflow run launch
# ---------------------------------------------------------------------------


class WorkflowRunRequest(BaseModel):
    """POST /api/v1/control/runs — launch a workflow run."""

    model_config = ConfigDict(extra="forbid")

    mode: RunMode = "workflow"
    data_source: DataSourceBinding
    trinity_bundle_ref: str | None = None
    policy_spec_ref: str | None = None
    model_spec_ref: str | None = None
    research_intent_ref: str | None = None
    knowledge_bundle_ref: str | None = None
    norm_pack_ref: str | None = None
    calibration_report_ref: str | None = None
    checkpoint_policy: CheckpointPolicyType = "strict"
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Natural-language run launch (agent circuit)
# ---------------------------------------------------------------------------


class NaturalLanguageRunRequest(BaseModel):
    """POST /api/v1/control/runs/nl — NL request triggering agent circuit."""

    model_config = ConfigDict(extra="forbid")

    request: str = Field(..., min_length=1, max_length=10_000)
    context: dict[str, Any] = Field(default_factory=dict)
    domain_hint: str | None = None
    data_source: DataSourceBinding | None = None
    max_iterations: int = Field(default=3, ge=1, le=10)
    llm_model: str | None = None
    llm_models: list[str] | None = None
    max_parallel_models: int = Field(default=1, ge=1, le=16)
    run_budget_usd: float | None = Field(default=None, ge=0.0)
    per_model_budget_usd: float | None = Field(default=None, ge=0.0)
    checkpoint_policy: CheckpointPolicyType = "strict"
    execution_plan_ref: str | None = None
    execution_plan: dict[str, Any] | None = None
    stop_criteria: dict[str, Any] = Field(default_factory=dict)
    governance_constraints: list[dict[str, Any]] = Field(default_factory=list)
    expected_outputs: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Run launch response (shared by both endpoints)
# ---------------------------------------------------------------------------


class RunLaunchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: RunLaunchStatus
    run_id: str
    message: str


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------


class DatasetFetchSpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    dataset_id: str
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_start: str | None = None
    date_end: str | None = None


class IngestRequest(BaseModel):
    """POST /api/v1/control/data/ingest — trigger data collection."""

    model_config = ConfigDict(extra="forbid")

    datasets: list[DatasetFetchSpecRequest] = Field(default_factory=list)
    fetch_plans: list["FetchPlan"] = Field(default_factory=list)
    source: str = "dashboard"
    license_name: str = "open"
    cache_policy: str = "default"
    connection_profile: str | None = None
    execution_mode: ExecutionMode = "batch_full"
    produce_data_snapshot: bool = True
    record_mode: bool = False
    replay_ref: str | None = None
    binding_profile_id: str | None = None
    produce_input_bindings: bool = False

    @model_validator(mode="after")
    def _validate_fetch_inputs(self) -> "IngestRequest":
        if not self.datasets and not self.fetch_plans:
            raise ValueError("Either datasets or fetch_plans must be provided")
        return self


class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: IngestStatus
    evidence_bundle_ref: str | None = None
    data_snapshot_ref: str | None = None
    datasets_fetched: int = 0
    message: str
    warnings: list[str] = Field(default_factory=list)
    cursor_ref: str | None = None
    mode_effective: str | None = None
    record_ref: str | None = None
    input_bindings_ref: str | None = None


# ---------------------------------------------------------------------------
# Retrieval control contracts
# ---------------------------------------------------------------------------


class DataNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str = Field(..., min_length=1, max_length=256)
    geography: str | None = Field(default=None, max_length=128)
    time_start: str | None = Field(default=None, max_length=64)
    time_end: str | None = Field(default=None, max_length=64)
    granularity: str = Field(default="annual", max_length=64)
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    purpose: str = Field(default="policy_drafting", min_length=1, max_length=256)


class MetricCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., min_length=1)
    metric_id: str = Field(..., min_length=1)
    connector_id: str = Field(..., min_length=1)
    dataset_id: str = Field(..., min_length=1)
    profile_id: str | None = None
    source_lane: CandidateLane = "fastlane"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rank: int = Field(default=1, ge=1)
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    coverage_estimate: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_estimate_ms: int | None = Field(default=None, ge=0)
    filters_template: dict[str, list[str]] = Field(default_factory=dict)
    match_reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    metric_id: str
    connector_id: str
    dataset_id: str
    dataset_name: str | None = None
    description: str = ""
    profile_id: str | None = None
    source_lane: CandidateLane = "explorelane"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    coverage_estimate: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_estimate_ms: int | None = Field(default=None, ge=0)
    schema_excerpt: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FetchPlanFallback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    dataset_id: str
    profile_id: str | None = None
    filters: dict[str, list[str]] = Field(default_factory=dict)


class FetchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(..., min_length=1)
    metric_id: str = Field(..., min_length=1)
    connector_id: str = Field(..., min_length=1)
    dataset_id: str = Field(..., min_length=1)
    profile_id: str | None = None
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_start: str | None = Field(default=None, max_length=64)
    date_end: str | None = Field(default=None, max_length=64)
    granularity: str | None = Field(default=None, max_length=64)
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    source_lane: CandidateLane = "fastlane"
    persist_payload: bool = False
    max_preview_rows: int = Field(default=20, ge=1, le=200)
    fallbacks: list[FetchPlanFallback] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FetchPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PreviewStatus = "ok"
    connector_id: str
    dataset_id: str
    row_count: int = Field(default=0, ge=0)
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    coverage_ok: bool = False
    quality_min: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    schema: dict[str, Any] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)
    message: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)


class DataContextMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    plan_id: str
    connector_id: str
    dataset_id: str
    row_count: int = Field(default=0, ge=0)
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    source_lane: CandidateLane = "fastlane"
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class DataContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[DataContextMetric] = Field(default_factory=list)
    metadata_docs_fetched: int = Field(default=0, ge=0)
    index_docs_total: int = Field(default=0, ge=0)
    index_size_bytes: int = Field(default=0, ge=0)


class PromotionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    promotion_id: str
    metric_id: str
    connector_id: str
    dataset_id: str
    profile_id: str | None = None
    source_lane: CandidateLane = "explorelane"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    status: PromotionStatus = "pending"
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_docs_total: int = Field(default=0, ge=0)
    index_size_bytes: int = Field(default=0, ge=0)
    indexed_sources: int = Field(default=0, ge=0)
    docs_added_last_run: int = Field(default=0, ge=0)
    source_coverage: dict[str, int] = Field(default_factory=dict)
    last_updated: datetime | None = None


class DataResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_needs: list[DataNeed] = Field(..., min_length=1)
    mode: RetrievalMode = "hybrid"
    allow_explore_fallback: bool = True


class DataResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    mode: RetrievalMode
    fetch_plans: list[FetchPlan] = Field(default_factory=list)
    candidates: list[MetricCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DataDiscoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_needs: list[DataNeed] = Field(..., min_length=1)
    max_sources_per_query: int = Field(default=5, ge=1, le=50)
    max_discovery_calls_per_source: int = Field(default=25, ge=1, le=500)
    max_candidates_total: int = Field(default=50, ge=1, le=500)
    time_budget_ms: int = Field(default=5000, ge=100, le=120_000)
    cost_budget_usd: float = Field(default=0.0, ge=0.0)


class DataDiscoverResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    docs_fetched_total: int = Field(default=0, ge=0)
    index_stats: IndexStats | None = None
    warnings: list[str] = Field(default_factory=list)


class DataPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fetch_plan: FetchPlan
    allow_fallback: bool = True


class DataPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    preview: FetchPreview


class DataCatalogSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    query: str
    matches: list[MetricCandidate] = Field(default_factory=list)
    total_matches: int = Field(default=0, ge=0)


class IndexStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    stats: IndexStats


class PromotionCandidatesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    candidates: list[PromotionCandidate] = Field(default_factory=list)


class PromotionDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class PromotionDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    promotion_id: str
    status: Literal["approved", "rejected"]
    message: str
    binding_updated: bool = False


# ---------------------------------------------------------------------------
# Connectors listing
# ---------------------------------------------------------------------------


class ConnectorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    namespace: str
    version: str
    known_datasets: list[str] = Field(default_factory=list)
    loaded: bool = False
    last_health_check: datetime | None = None
    available_profiles: list[str] = Field(default_factory=list)


class ConnectorsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    connectors: list[ConnectorInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Source profiles
# ---------------------------------------------------------------------------


class SourceProfileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    description: str = ""
    connector_family: str
    base_url: str
    auth_policy: str = "none"
    tags: list[str] = Field(default_factory=list)
    source_organization: str = ""
    estimated_datasets: int | None = None
    connector_available: bool = False


class SourceProfilesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[SourceProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM model profiles
# ---------------------------------------------------------------------------


class ModelProfileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    description: str = ""
    provider: str
    model_id: str
    base_url: str
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    input_cost_per_mtoken_usd: float | None = Field(default=None, ge=0.0)
    output_cost_per_mtoken_usd: float | None = Field(default=None, ge=0.0)
    enabled: bool = True


class ModelProfilesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[ModelProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Binding profiles
# ---------------------------------------------------------------------------


class BindingProfileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    description: str = ""
    schema_family: str
    strategy: str = "auto"
    rule_count: int = 0
    expected_columns: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class BindingProfilesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[BindingProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache status
# ---------------------------------------------------------------------------


class CacheEntryInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cache_key: str
    connector_id: str
    dataset_id: str
    created_at: datetime
    expires_at: datetime | None = None
    size_bytes: int = 0
    is_valid: bool = True


class CacheStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    total_entries: int = 0
    total_size_bytes: int = 0
    entries: list[CacheEntryInfo] = Field(default_factory=list)


IngestRequest.model_rebuild()


# ---------------------------------------------------------------------------
# Lex Knowledge Graph pipeline
# ---------------------------------------------------------------------------

LexPipelineState = Literal["pending", "running", "completed", "failed"]


class LexPipelineStageConfig(BaseModel):
    """Toggle individual pipeline stages on/off."""

    model_config = ConfigDict(extra="forbid")

    parse: bool = True
    structure: bool = True
    spo: bool = True
    graph: bool = True
    embed: bool = True


class LexTriggerRequest(BaseModel):
    """POST /api/v1/control/lex/trigger — start batch pipeline."""

    model_config = ConfigDict(extra="forbid")

    cards_path: str = Field(..., min_length=1)
    texts_path: str = Field(..., min_length=1)
    output_dir: str = Field(..., min_length=1)
    stages: LexPipelineStageConfig = Field(default_factory=LexPipelineStageConfig)
    status_filter: list[str] | None = None
    llm_model: str = "qwen/qwen3-235b-a22b-instruct-2507-fp8"
    resume: bool = False


class LexTriggerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: Literal["accepted", "rejected"]
    pipeline_id: str
    message: str


class LexPipelineStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    pipeline_id: str
    state: LexPipelineState
    progress_summary: dict[str, int] = Field(default_factory=dict)
    error_message: str | None = None


class LexGraphStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    total_entities: int = 0
    total_facts: int = 0
    total_provisions: int = 0
    top_predicates: list[dict[str, Any]] = Field(default_factory=list)
    top_entity_types: list[dict[str, Any]] = Field(default_factory=list)
    db_exists: bool = False


class LexSearchRequest(BaseModel):
    """POST /api/v1/control/lex/search — search knowledge graph facts."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=20, ge=1, le=100)
    output_dir: str = Field(..., min_length=1)


class LexSearchResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    subject_name: str
    predicate: str
    object_name: str
    fact_text: str
    confidence: float
    norm_type: str
    action_canon: str = ""
    norm_type_canon: str = ""
    condition_text_uk: str = ""
    exception_text_uk: str = ""
    procedure_text_uk: str = ""
    thresholds_json: str = ""
    source_quote_uk: str = ""
    doc_name: str
    doc_reestr_code: str
    provision_citation: str


class LexSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    query: str
    results: list[LexSearchResultItem] = Field(default_factory=list)
    total: int = 0


__all__ = [
    "BindingProfileInfo",
    "BindingProfilesListResponse",
    "CandidateLane",
    "CacheEntryInfo",
    "CachePolicyType",
    "CacheStatusResponse",
    "CheckpointPolicyType",
    "ConnectorInfo",
    "ConnectorsListResponse",
    "DataSourceBinding",
    "DataCatalogSearchResponse",
    "DataContext",
    "DataContextMetric",
    "DataDiscoverRequest",
    "DataDiscoverResponse",
    "DataNeed",
    "DataPreviewRequest",
    "DataPreviewResponse",
    "DataResolveRequest",
    "DataResolveResponse",
    "DiscoveryCandidate",
    "DatasetFetchSpecRequest",
    "ExecutionMode",
    "FetchPlan",
    "FetchPlanFallback",
    "FetchPreview",
    "IndexStats",
    "IndexStatsResponse",
    "IngestRequest",
    "IngestResponse",
    "IngestStatus",
    "LexGraphStatsResponse",
    "LexPipelineStageConfig",
    "LexPipelineState",
    "LexPipelineStatusResponse",
    "LexSearchRequest",
    "LexSearchResponse",
    "LexSearchResultItem",
    "LexTriggerRequest",
    "LexTriggerResponse",
    "NaturalLanguageRunRequest",
    "MetricCandidate",
    "ModelProfileInfo",
    "ModelProfilesListResponse",
    "PreviewStatus",
    "PromotionCandidate",
    "PromotionCandidatesResponse",
    "PromotionDecisionRequest",
    "PromotionDecisionResponse",
    "PromotionStatus",
    "RetrievalMode",
    "RunLaunchResponse",
    "RunLaunchStatus",
    "RunMode",
    "SourceProfileInfo",
    "SourceProfilesListResponse",
    "WorkflowRunRequest",
]
