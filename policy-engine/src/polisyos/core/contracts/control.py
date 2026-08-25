"""Control Plane contracts — request/response DTOs for write operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..artifacts.manifest import ArtifactRef
from .decision_validity import (
    DecisionDependencyEvent,
    DecisionLifecycleJob,
    DecisionTriggerRecord,
    DecisionTriggerType,
    DecisionValidityStatus,
    DecisionValidityTransition,
)
from .policy_design_case_projection import PolicyDesignCaseProjection
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
CandidateLane = Literal["fastlane", "explorelane", "catalog"]
PreviewStatus = Literal["ok", "insufficient_coverage", "error"]
PromotionStatus = Literal["pending", "approved", "rejected"]
CapabilityStage = Literal["active", "planned", "deferred"]
ExecutionProfile = Literal["dev", "research", "governed", "production"]
PolicyAuthorityProfile = Literal["research", "governed", "production"]
PolicyValidationProfile = Literal["fast", "mvp", "strict"]
PolicyFallbackProfile = Literal["serious_fallback_fail_closed"]
ControlJobState = Literal["pending", "running", "completed", "failed"]
ControlJobKind = Literal["workflow_run", "natural_language_run", "lex_pipeline"]
OperatorProjectionAuthority = Literal["runtime_authority", "projection_only"]
OperatorProjectionState = Literal[
    "draft",
    "projection_only",
    "redacted",
    "stale",
    "contested",
    "projected",
    "blocked",
    "readiness_closed",
    "approved",
    "rejected",
    "published_blocked",
    "publishable",
]

_SUPPORTED_LOCALES: tuple[Literal["en", "uk"], ...] = ("en", "uk")
_SUPPORTED_EXECUTION_PROFILES: tuple[ExecutionProfile, ...] = (
    "dev",
    "research",
    "governed",
    "production",
)
SUPPORTED_EXECUTION_PROFILES = _SUPPORTED_EXECUTION_PROFILES
EXECUTION_PROFILE_ORDER: dict[ExecutionProfile, int] = {
    "dev": 0,
    "research": 1,
    "governed": 2,
    "production": 3,
}
POLICY_AUTHORITY_PROFILES: tuple[PolicyAuthorityProfile, ...] = (
    "research",
    "governed",
    "production",
)
POLICY_AUTHORITY_TO_EXECUTION_PROFILE: dict[
    PolicyAuthorityProfile,
    ExecutionProfile,
] = {
    "research": "research",
    "governed": "governed",
    "production": "production",
}
POLICY_AUTHORITY_TO_VALIDATION_PROFILE: dict[
    PolicyAuthorityProfile,
    PolicyValidationProfile,
] = {
    "research": "mvp",
    "governed": "strict",
    "production": "strict",
}
POLICY_AUTHORITY_TO_FALLBACK_PROFILE: dict[
    PolicyAuthorityProfile,
    PolicyFallbackProfile,
] = {
    "research": "serious_fallback_fail_closed",
    "governed": "serious_fallback_fail_closed",
    "production": "serious_fallback_fail_closed",
}
EXECUTION_PROFILE_TO_VALIDATION_PROFILE: dict[ExecutionProfile, PolicyValidationProfile] = {
    "dev": "fast",
    "research": "mvp",
    "governed": "strict",
    "production": "strict",
}


@dataclass(frozen=True, slots=True)
class PolicyAuthorityProfileMapping:
    """Canonical mapping from policy authority to existing runtime profiles."""

    authority_profile: PolicyAuthorityProfile
    execution_profile: ExecutionProfile
    validation_profile: PolicyValidationProfile
    fallback_policy: PolicyFallbackProfile


def policy_authority_profile_mapping(
    authority_profile: str,
) -> PolicyAuthorityProfileMapping:
    """Return the one supported mapping for a policy authority profile."""

    normalized = authority_profile.strip().casefold().replace("-", "_")
    if normalized not in POLICY_AUTHORITY_PROFILES:
        raise ValueError(f"unsupported policy authority profile: {authority_profile!r}")
    profile = cast("PolicyAuthorityProfile", normalized)
    return PolicyAuthorityProfileMapping(
        authority_profile=profile,
        execution_profile=POLICY_AUTHORITY_TO_EXECUTION_PROFILE[profile],
        validation_profile=POLICY_AUTHORITY_TO_VALIDATION_PROFILE[profile],
        fallback_policy=POLICY_AUTHORITY_TO_FALLBACK_PROFILE[profile],
    )


def _default_supported_locales() -> list[Literal["en", "uk"]]:
    return list(_SUPPORTED_LOCALES)


def _default_supported_execution_profiles() -> list[ExecutionProfile]:
    return list(_SUPPORTED_EXECUTION_PROFILES)


# ---------------------------------------------------------------------------
# Data source binding
# ---------------------------------------------------------------------------


class DataSourceBinding(BaseModel):
    """Exactly one of these fields must be provided."""

    model_config = ConfigDict(extra="forbid")

    data_snapshot_ref: str | None = None
    input_bindings_ref: str | None = None
    data_view_request_ref: str | None = None


class PolicyFlags(BaseModel):
    """Carry opt-in execution relaxations requested by the client.

    `allow_mock_fallback=True` is privileged in governed/production profiles and
    may be rejected by the runtime execution-policy resolver.
    """

    model_config = ConfigDict(extra="forbid")

    allow_mock_fallback: bool = False


class DecisionValidityEventRequest(BaseModel):
    """Request an append-only decision-validity event and lifecycle re-evaluation."""

    model_config = ConfigDict(extra="forbid")

    trigger_type: DecisionTriggerType
    status: DecisionValidityStatus
    reason: str = Field(..., min_length=1, max_length=512)
    dependency_keys: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    dedupe_key: str | None = None
    occurred_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class DecisionValidityEventResponse(BaseModel):
    """Return the persisted event identity and aggregate impact of the update."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    event_id: str
    dedupe_key: str
    affected_packets: list[str] = Field(default_factory=list)
    affected_statuses: dict[str, int] = Field(default_factory=dict)
    message: str


class DecisionValidityPendingReview(BaseModel):
    """Describe one unresolved human-review gate for a decision packet."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    trigger_type: DecisionTriggerType
    reason: str
    occurred_at: datetime


class DecisionValidityLifecycleSummary(BaseModel):
    """Return event history, transitions, scheduled jobs, and reissue candidates."""

    model_config = ConfigDict(extra="forbid")

    status: DecisionValidityStatus | None = None
    events: list[DecisionDependencyEvent] = Field(default_factory=list)
    transitions: list[DecisionValidityTransition] = Field(default_factory=list)
    pending_reviews: list[DecisionValidityPendingReview] = Field(default_factory=list)
    scheduled_jobs: list[DecisionLifecycleJob] = Field(default_factory=list)
    reissue_candidates: list[ArtifactRef] = Field(default_factory=list)
    latest_transition_at: datetime | None = None


class DecisionValiditySummaryResponse(BaseModel):
    """Expose the current decision-validity verdict and its lifecycle context."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str | None = None
    decision_packet_ref: ArtifactRef
    status: DecisionValidityStatus
    lifecycle_status: DecisionValidityStatus
    checked_at: datetime
    reasons: list[str] = Field(default_factory=list)
    triggers: list[DecisionTriggerRecord] = Field(default_factory=list)
    review_required: bool = False
    supersedes_decision_ref: ArtifactRef | None = None
    superseded_by_ref: ArtifactRef | None = None
    evaluation_ref: ArtifactRef | None = None
    decision_lineage_key: str
    recommended_action: str
    lifecycle: DecisionValidityLifecycleSummary = Field(
        default_factory=DecisionValidityLifecycleSummary
    )


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
    execution_profile: ExecutionProfile | None = None
    policy_flags: PolicyFlags = Field(default_factory=PolicyFlags)
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
    execution_profile: ExecutionProfile | None = None
    policy_flags: PolicyFlags = Field(default_factory=PolicyFlags)
    execution_plan_ref: str | None = None
    execution_plan: dict[str, Any] | None = None
    stop_criteria: dict[str, Any] = Field(default_factory=dict)
    governance_constraints: list[dict[str, Any]] = Field(default_factory=list)
    expected_outputs: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Run launch response (shared by both endpoints)
# ---------------------------------------------------------------------------


class RunLaunchResponse(BaseModel):
    """Return the accepted/rejected control-job id and effective execution profile."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: RunLaunchStatus
    run_id: str
    job_id: str
    effective_execution_profile: ExecutionProfile
    message: str


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------


class DatasetFetchSpecRequest(BaseModel):
    """Describe one direct connector/dataset fetch request for data ingestion."""

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
    fetch_plans: list[FetchPlan] = Field(default_factory=list)
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
    def _validate_fetch_inputs(self) -> IngestRequest:
        if not self.datasets and not self.fetch_plans:
            raise ValueError("Either datasets or fetch_plans must be provided")
        return self


class IngestResponse(BaseModel):
    """Return ingestion outputs, warning messages, and replay/cursor references."""

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
    """Describe one metric/geography/time requirement to resolve into fetch plans."""

    model_config = ConfigDict(extra="forbid")

    metric: str = Field(..., min_length=1, max_length=256)
    geography: str | None = Field(default=None, max_length=128)
    time_start: str | None = Field(default=None, max_length=64)
    time_end: str | None = Field(default=None, max_length=64)
    granularity: str = Field(default="annual", max_length=64)
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    purpose: str = Field(default="policy_drafting", min_length=1, max_length=256)


class MetricCandidate(BaseModel):
    """Represent one catalog-backed source candidate for a requested metric."""

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
    """Represent one explore-lane candidate discovered from source metadata search."""

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
    """Describe one connector/dataset fallback to try when the primary plan fails."""

    model_config = ConfigDict(extra="forbid")

    connector_id: str
    dataset_id: str
    metric_id: str | None = None
    profile_id: str | None = None
    filters: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FetchPlan(BaseModel):
    """Encode one executable data-fetch plan produced by resolver/discovery flows."""

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
    """Return a bounded sample, quality flags, and coverage status for one plan."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: PreviewStatus = "ok"
    connector_id: str
    dataset_id: str
    row_count: int = Field(default=0, ge=0)
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    coverage_ok: bool = False
    quality_min: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    schema_payload: dict[str, Any] = Field(default_factory=dict, alias="schema")
    quality_flags: list[str] = Field(default_factory=list)
    message: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)


class DataContextMetric(BaseModel):
    """Summarize one fetched metric included in a data-context payload."""

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
    """Aggregate fetched metrics and catalog index counters for an agent run."""

    model_config = ConfigDict(extra="forbid")

    metrics: list[DataContextMetric] = Field(default_factory=list)
    metadata_docs_fetched: int = Field(default=0, ge=0)
    index_docs_total: int = Field(default=0, ge=0)
    index_size_bytes: int = Field(default=0, ge=0)


class PromotionCandidate(BaseModel):
    """Represent one explore-lane source proposed for promotion into fastlane."""

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
    """Report catalog index size, source coverage, and last-update counters."""

    model_config = ConfigDict(extra="forbid")

    index_docs_total: int = Field(default=0, ge=0)
    index_size_bytes: int = Field(default=0, ge=0)
    indexed_sources: int = Field(default=0, ge=0)
    docs_added_last_run: int = Field(default=0, ge=0)
    source_coverage: dict[str, int] = Field(default_factory=dict)
    last_updated: datetime | None = None


class DataResolveRequest(BaseModel):
    """Request fastlane/hybrid resolution of data needs into concrete fetch plans."""

    model_config = ConfigDict(extra="forbid")

    data_needs: list[DataNeed] = Field(..., min_length=1)
    mode: RetrievalMode = "hybrid"
    allow_explore_fallback: bool = True


class DataResolveResponse(BaseModel):
    """Return selected fetch plans, ranked candidates, and resolver warnings."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    mode: RetrievalMode
    fetch_plans: list[FetchPlan] = Field(default_factory=list)
    candidates: list[MetricCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DataDiscoverRequest(BaseModel):
    """Request explore-lane candidate discovery within explicit time/cost budgets."""

    model_config = ConfigDict(extra="forbid")

    data_needs: list[DataNeed] = Field(..., min_length=1)
    max_sources_per_query: int = Field(default=5, ge=1, le=50)
    max_discovery_calls_per_source: int = Field(default=25, ge=1, le=500)
    max_candidates_total: int = Field(default=50, ge=1, le=500)
    time_budget_ms: int = Field(default=5000, ge=100, le=120_000)
    cost_budget_usd: float = Field(default=0.0, ge=0.0)


class DataDiscoverResponse(BaseModel):
    """Return discovery candidates plus index telemetry and soft warning messages."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    docs_fetched_total: int = Field(default=0, ge=0)
    index_stats: IndexStats | None = None
    warnings: list[str] = Field(default_factory=list)


class DataPreviewRequest(BaseModel):
    """Request a bounded preview for one fetch plan with optional fallback handling."""

    model_config = ConfigDict(extra="forbid")

    fetch_plan: FetchPlan
    allow_fallback: bool = True


class DataPreviewResponse(BaseModel):
    """Wrap one `FetchPreview` payload with standard API metadata."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    preview: FetchPreview


class CausalFrontierAreaRecord(BaseModel):
    """Inline representation of one area-level SAE row."""

    model_config = ConfigDict(extra="forbid")

    area_id: str = Field(..., min_length=1)
    direct_estimate: float
    direct_variance: float = Field(..., gt=0.0)
    sample_size: int | None = Field(default=None, ge=1)
    regime_id: str | None = None
    policy_indicator: float | int | None = None
    covariates: dict[str, float | int | None] = Field(default_factory=dict)


class CausalFrontierEdgeRecord(BaseModel):
    """Inline representation of one adjacency edge with optional frontier metadata."""

    model_config = ConfigDict(extra="forbid")

    src_area_id: str = Field(..., min_length=1)
    dst_area_id: str = Field(..., min_length=1)
    weight: float = Field(default=1.0, ge=0.0)
    adjacency_type: Literal["contiguity", "distance", "custom"] = "custom"
    frontier_flag: bool = False
    frontier_type: str | None = None
    frontier_source: str | None = None


class CausalFrontierExposureRecord(BaseModel):
    """Optional spillover/exposure row aligned to one area."""

    model_config = ConfigDict(extra="forbid")

    area_id: str = Field(..., min_length=1)
    treatment: float | int | None = None
    spillover_exposure: float | int | None = None
    exposure_mapping_version: str | None = None


class CausalFrontierOutputRefs(BaseModel):
    """Artifact references emitted by runtime causal-frontier SAE execution."""

    model_config = ConfigDict(extra="forbid")

    dependence_ref: ArtifactRef | None = None
    quality_certificate_ref: ArtifactRef | None = None
    sae_estimates_ref: ArtifactRef | None = None
    causal_diagnostics_ref: ArtifactRef | None = None
    governance_artifact_ref: ArtifactRef | None = None


class CausalFrontierSAEEstimate(BaseModel):
    """Output row for `sae_estimates.parquet` and runtime API responses."""

    model_config = ConfigDict(extra="forbid")

    area_id: str
    theta_mean: float
    theta_sd: float
    mse: float
    component_id: int
    borrow_strength_neighbors: int


class CausalFrontierSAERequest(BaseModel):
    """Run boundary-constrained small-area estimation from inline rows or one bundle dir."""

    model_config = ConfigDict(extra="forbid")

    bundle_dir: str | None = None
    output_dir: str | None = None
    areas: list[CausalFrontierAreaRecord] = Field(default_factory=list)
    edges: list[CausalFrontierEdgeRecord] = Field(default_factory=list)
    exposure: list[CausalFrontierExposureRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    covariate_columns: list[str] | None = None
    add_intercept: bool = True
    lambda_spatial: float = Field(default=1.0, ge=0.0)
    component_ridge: float = Field(default=1e-6, ge=0.0)
    contrast_eps: float = Field(default=1e-8, gt=0.0)
    green_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    red_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    calibration_reps: int = Field(default=0, ge=0, le=500)
    calibration_seed: int = 0
    governance_profile: Literal["fast", "mvp", "strict"] = "mvp"
    persist_artifacts: bool = False

    @model_validator(mode="after")
    def _validate_request_shape(self) -> CausalFrontierSAERequest:
        if self.bundle_dir is None and (not self.areas or not self.edges):
            raise ValueError("provide either bundle_dir or both areas and edges")
        if self.green_threshold > self.red_threshold:
            raise ValueError("green_threshold must be less than or equal to red_threshold")
        return self


class CausalFrontierSAEResponse(BaseModel):
    """Runtime response for causal-frontier small-area estimation."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    method_name: str
    estimates: list[CausalFrontierSAEEstimate] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    governance_artifact: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: CausalFrontierOutputRefs = Field(default_factory=CausalFrontierOutputRefs)
    output_bundle: dict[str, str] = Field(default_factory=dict)


class DataCatalogSearchResponse(BaseModel):
    """Return catalog search matches and the total result count for a query."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    query: str
    matches: list[MetricCandidate] = Field(default_factory=list)
    total_matches: int = Field(default=0, ge=0)


class IndexStatsResponse(BaseModel):
    """Wrap catalog index telemetry with standard API metadata."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    stats: IndexStats


class PromotionCandidatesResponse(BaseModel):
    """Return pending/approved/rejected source-promotion candidates."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    candidates: list[PromotionCandidate] = Field(default_factory=list)


class PromotionDecisionRequest(BaseModel):
    """Capture an optional reviewer reason for approving or rejecting promotion."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class PromotionDecisionResponse(BaseModel):
    """Return the stored promotion status and whether bindings were updated."""

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
    """Describe one discovered connector and the datasets/profiles it exposes."""

    model_config = ConfigDict(extra="forbid")

    connector_id: str
    namespace: str
    version: str
    known_datasets: list[str] = Field(default_factory=list)
    loaded: bool = False
    last_health_check: datetime | None = None
    available_profiles: list[str] = Field(default_factory=list)


class ConnectorsListResponse(BaseModel):
    """Return all visible connectors with standard API metadata."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    connectors: list[ConnectorInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Source profiles
# ---------------------------------------------------------------------------


class SourceProfileInfo(BaseModel):
    """Describe one curated data-source profile available to retrieval flows."""

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
    """Return all curated source profiles with standard API metadata."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[SourceProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM model profiles
# ---------------------------------------------------------------------------


class ModelProfileInfo(BaseModel):
    """Describe one LLM model profile exposed to NL control-plane requests."""

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
    """Return all enabled model profiles with standard API metadata."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[ModelProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Binding profiles
# ---------------------------------------------------------------------------


class BindingProfileInfo(BaseModel):
    """Describe one schema-binding profile used to normalize ingested datasets."""

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
    """Return binding profile metadata with standard API metadata."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[BindingProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache status
# ---------------------------------------------------------------------------


class CacheEntryInfo(BaseModel):
    """Expose one materialized data-cache entry and its validity window."""

    model_config = ConfigDict(extra="forbid")

    cache_key: str
    connector_id: str
    dataset_id: str
    created_at: datetime
    expires_at: datetime | None = None
    size_bytes: int = 0
    is_valid: bool = True


class CacheStatusResponse(BaseModel):
    """Return cache inventory and aggregate storage usage."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    total_entries: int = 0
    total_size_bytes: int = 0
    entries: list[CacheEntryInfo] = Field(default_factory=list)


IngestRequest.model_rebuild()


# ---------------------------------------------------------------------------
# Control-plane capabilities
# ---------------------------------------------------------------------------


class CapabilityFeatureInfo(BaseModel):
    """Describe one runtime feature flag and its rollout stage/disable reason."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    description: str
    category: str
    enabled: bool = True
    stage: CapabilityStage = "active"
    disabled_reason: str | None = None


class CapabilityManifestResponse(BaseModel):
    """Expose stable runtime capabilities, defaults, security posture, and limits."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    runtime_api_version: str = "1.0.0"
    shell_flavor: str = "atlas"
    default_locale: Literal["en", "uk"] = "en"
    supported_locales: list[Literal["en", "uk"]] = Field(default_factory=_default_supported_locales)
    default_execution_profile: ExecutionProfile = "dev"
    supported_execution_profiles: list[ExecutionProfile] = Field(
        default_factory=_default_supported_execution_profiles
    )
    worker_backend: str = "embedded"
    state_store_backend: str = "sqlite"
    security_posture: dict[str, Any] = Field(default_factory=dict)
    fallback_rules: dict[str, Any] = Field(default_factory=dict)
    workspaces: list[str] = Field(default_factory=list)
    features: list[CapabilityFeatureInfo] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class OperatorProjectionStateLabel(BaseModel):
    """Projection lifecycle label with explicit authority semantics."""

    model_config = ConfigDict(extra="forbid")

    state: OperatorProjectionState
    label: str
    authority: OperatorProjectionAuthority


class OperatorDiagnostic(BaseModel):
    """Typed operator root-cause projection for serious runtime failures."""

    model_config = ConfigDict(extra="forbid")

    authoritative_runtime_state: str
    projection_source: str
    owner: str
    phase: str
    first_blocking_cause: str
    upstream_missing_input: str | None = None
    downstream_impact: str
    authority_refs: dict[str, str] = Field(default_factory=dict)
    blocker_overridable: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    next_diagnostic_command: str
    projection_labels: list[OperatorProjectionStateLabel] = Field(default_factory=list)


class ControlFailureEnvelope(BaseModel):
    """Stable operator-facing failure envelope for durable control jobs."""

    model_config = ConfigDict(extra="forbid")

    code: str
    layer: str
    phase: str | None = None
    message: str
    retryable: bool = False
    next_action: str | None = None
    model: str | None = None
    provider: str | None = None
    run_id: str | None = None
    job_id: str | None = None
    artifact_refs: dict[str, Any] = Field(default_factory=dict)
    variant_failures: list[dict[str, Any]] = Field(default_factory=list)
    operator_diagnostic: OperatorDiagnostic | None = None


class ControlQualityGate(BaseModel):
    """Stable operator-facing quality gate emitted by canary scorecards."""

    model_config = ConfigDict(extra="forbid")

    name: str
    code: str | None = None
    status: str
    layer: str
    phase: str | None = None
    message: str
    evidence_ref: str | None = None
    next_action: str | None = None
    next_diagnostic_command: str | None = None
    blocking: bool = True
    operator_diagnostic: OperatorDiagnostic | None = None


class ControlQualityFailure(BaseModel):
    """Operator-facing blocking quality failure summary."""

    model_config = ConfigDict(extra="forbid")

    gate: str
    code: str | None = None
    layer: str
    phase: str | None = None
    message: str
    evidence_ref: str | None = None
    next_action: str | None = None
    next_diagnostic_command: str | None = None
    operator_diagnostic: OperatorDiagnostic | None = None


class ControlProjectionSource(BaseModel):
    """Label the projection surface used to shape a dashboard response."""

    model_config = ConfigDict(extra="forbid")

    source_surface: str
    source_detail: str
    authority_level: str
    projection_policy: str


class ControlAuthorityGap(BaseModel):
    """Operator-facing unresolved authority gap exposed through API projections."""

    model_config = ConfigDict(extra="forbid")

    code: str
    layer: str
    phase: str | None = None
    message: str
    owner: str | None = None
    evidence_ref: str | None = None
    next_action: str | None = None
    next_diagnostic_command: str | None = None


class ControlApprovalProjection(BaseModel):
    """Fail-closed approval projection for dashboard readers."""

    model_config = ConfigDict(extra="forbid")

    state: str | None = None
    eligible: bool = False
    reasons: list[str] = Field(default_factory=list)
    source_surface: str
    authority_level: str


ProductionApprovalDecision = Literal["approved", "approved_with_override", "blocked"]


class ProductionApprovalOverrideRequest(BaseModel):
    """Reviewer-attributed override request for exceptional production approval."""

    model_config = ConfigDict(extra="forbid")

    reviewer_identity: str = Field(..., min_length=1, max_length=256)
    reason: str = Field(..., min_length=1, max_length=2_000)
    scope: str = Field(..., min_length=1, max_length=512)
    expires_at: datetime
    evidence_refs: list[str] = Field(..., min_length=1, max_length=50)
    signature: str | None = Field(default=None, min_length=1, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_evidence_refs(self) -> ProductionApprovalOverrideRequest:
        refs = [str(ref).strip() for ref in self.evidence_refs if str(ref).strip()]
        if not refs:
            raise ValueError("override evidence_refs must contain at least one non-empty ref")
        if any(any(char in ref for char in "\r\n\t") for ref in refs):
            raise ValueError("override evidence_refs must not contain control characters")
        self.evidence_refs = refs
        return self


class ProductionApprovalOverridePacket(BaseModel):
    """Persisted reviewer override packet with deterministic attribution signature."""

    model_config = ConfigDict(extra="forbid")

    reviewer_identity: str
    reason: str
    scope: str
    expires_at: datetime
    evidence_refs: list[str] = Field(default_factory=list)
    signed_at: datetime
    signature: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductionApprovalEligibility(BaseModel):
    """Machine-readable production approval eligibility projection."""

    model_config = ConfigDict(extra="forbid")

    eligible: bool
    execution_completed: bool
    quality_passed: bool
    blocking_failure_count: int = Field(ge=0)
    performance_status: str | None = None
    performance_blocking: bool = False
    conflict_status: str | None = None
    conflict_blocking: bool = False
    reasons: list[str] = Field(default_factory=list)


class ProductionApprovalPacket(BaseModel):
    """Immutable approval packet derived from a quality scorecard and optional override."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "policyos.production_approval_packet.v1",
        "policyos.production_approval_packet.v2",
    ] = "policyos.production_approval_packet.v1"
    generated_at: datetime
    run_id: str | None = None
    job_id: str | None = None
    canary_kind: str | None = None
    decision: ProductionApprovalDecision
    eligibility: ProductionApprovalEligibility
    scorecard_ref: str | None = None
    scorecard_digest: str
    scorecard_generated_at: str | None = None
    evidence_refs: dict[str, str] = Field(default_factory=dict)
    override: ProductionApprovalOverridePacket | None = None
    tenant_id: str | None = Field(default=None, min_length=1)
    production_basis_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    production_basis_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    human_decision_record_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    human_decision_record_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    decision_request_ref: str | None = None
    decision_request_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    governed_action_key: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    verifier_epoch: str | None = None
    expected_consumer: str | None = None
    expected_audience: str | None = None
    scorecard_producer_identity: str | None = Field(default=None, min_length=1)
    production_basis_producer_identity: str | None = Field(default=None, min_length=1)
    rule_version_ref: str | None = Field(default=None, min_length=1)
    limitations: tuple[str, ...] | None = None
    operational_authority: Literal[False] = False
    historical_only: bool = True

    @model_validator(mode="after")
    def _versioned_authority_shape(self) -> Self:
        v2_fields = (
            self.production_basis_ref,
            self.production_basis_digest,
            self.human_decision_record_ref,
            self.human_decision_record_digest,
            self.decision_request_ref,
            self.decision_request_digest,
            self.governed_action_key,
            self.valid_from,
            self.valid_until,
            self.verifier_epoch,
            self.expected_consumer,
            self.expected_audience,
            self.tenant_id,
            self.scorecard_producer_identity,
            self.production_basis_producer_identity,
            self.rule_version_ref,
            self.limitations,
        )
        if self.schema_version == "policyos.production_approval_packet.v1":
            if any(value is not None for value in v2_fields) or not self.historical_only:
                raise ValueError("production approval v1 is historical-only")
            return self
        if any(value is None for value in v2_fields):
            raise ValueError("production approval v2 requires exact currentness bindings")
        if self.production_basis_ref != self.production_basis_digest:
            raise ValueError("production basis ref and digest must match")
        if self.human_decision_record_ref != self.human_decision_record_digest:
            raise ValueError("human-decision record ref and digest must match")
        if (
            self.valid_from is None
            or self.valid_until is None
            or self.valid_until <= self.valid_from
        ):
            raise ValueError("production approval v2 validity interval is empty")
        return self


class ProductionApprovalRequest(BaseModel):
    """Request to materialize a production approval packet for one run."""

    model_config = ConfigDict(extra="forbid")

    quality_scorecard_ref: str | None = Field(default=None, min_length=1)
    quality_scorecard: dict[str, Any] | None = None
    production_basis_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    production_basis_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    human_decision_record_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    human_decision_record_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    override: ProductionApprovalOverrideRequest | None = None

    @model_validator(mode="after")
    def _exact_production_bindings(self) -> Self:
        for name, ref, digest in (
            (
                "production basis",
                self.production_basis_ref,
                self.production_basis_digest,
            ),
            (
                "human-decision record",
                self.human_decision_record_ref,
                self.human_decision_record_digest,
            ),
        ):
            if (ref is None) != (digest is None):
                raise ValueError(f"{name} ref and digest must be supplied together")
            if ref is not None and ref != digest:
                raise ValueError(f"{name} ref and digest must match")
        return self


class ProductionApprovalResponse(BaseModel):
    """Return persisted production approval packet metadata and payload."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    decision: ProductionApprovalDecision
    packet: ProductionApprovalPacket
    approval_packet_ref: ArtifactRef
    evidence_bundle_packet_path: str | None = None


class ControlJobResponse(BaseModel):
    """Represent one durable control-plane job and its progress/error state."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    job_id: str
    kind: ControlJobKind
    state: ControlJobState
    run_id: str | None = None
    pipeline_id: str | None = None
    requested_execution_profile: ExecutionProfile | None = None
    effective_execution_profile: ExecutionProfile
    capability_manifest_ref: ArtifactRef | None = None
    submitted_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    failure: ControlFailureEnvelope | None = None
    execution_status: str | None = None
    quality_status: str | None = None
    quality_scorecard_ref: str | None = None
    authoritative_scorecard_ref: str | None = None
    projection_source: ControlProjectionSource = Field(
        default_factory=lambda: ControlProjectionSource(
            source_surface="runtime.control_job",
            source_detail="control_store_progress",
            authority_level="projection_only",
            projection_policy="projection_only",
        )
    )
    runtime_state: str | None = None
    approval_projection: ControlApprovalProjection = Field(
        default_factory=lambda: ControlApprovalProjection(
            state=None,
            eligible=False,
            reasons=[],
            source_surface="runtime.control_job",
            authority_level="projection_only",
        )
    )
    unresolved_authority_gaps: list[ControlAuthorityGap] = Field(default_factory=list)
    next_diagnostic_commands: list[str] = Field(default_factory=list)
    policy_design_case_projection: PolicyDesignCaseProjection | None = None
    quality_evidence_bundle_path: str | None = None
    quality_gates: list[ControlQualityGate] = Field(default_factory=list)
    blocking_quality_failures: list[ControlQualityFailure] = Field(default_factory=list)
    operator_diagnostic: OperatorDiagnostic | None = None
    progress: dict[str, Any] = Field(default_factory=dict)


class ControlWorkerLeaseInfo(BaseModel):
    """Expose one worker lease heartbeat and currently leased job."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str
    state: str
    backend: str | None = None
    active_job_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    heartbeat_at: datetime
    lease_expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ControlWorkersResponse(BaseModel):
    """Return worker leases filtered by active-only mode."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    active_only: bool = True
    workers: list[ControlWorkerLeaseInfo] = Field(default_factory=list)


class ControlOutboxEventInfo(BaseModel):
    """Describe one durable outbox event and its publish retry state."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    topic: str
    event_key: str | None = None
    state: str
    job_id: str | None = None
    run_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    published_at: datetime | None = None
    attempt: int = 0
    error_message: str | None = None


class ControlOutboxEventsResponse(BaseModel):
    """Return outbox events filtered by publish state."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    state: str | None = None
    limit: int = 100
    events: list[ControlOutboxEventInfo] = Field(default_factory=list)


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
    execution_profile: ExecutionProfile | None = None
    policy_flags: PolicyFlags = Field(default_factory=PolicyFlags)


class LexTriggerResponse(BaseModel):
    """Return accepted/rejected Lex pipeline launch metadata."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: Literal["accepted", "rejected"]
    pipeline_id: str
    job_id: str
    effective_execution_profile: ExecutionProfile
    message: str


class LexPipelineStatusResponse(BaseModel):
    """Expose Lex pipeline state, stage progress counters, and failure text."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    pipeline_id: str
    state: LexPipelineState
    progress_summary: dict[str, int] = Field(default_factory=dict)
    error_message: str | None = None


class LexGraphStatsResponse(BaseModel):
    """Return graph-cardinality and top-distribution telemetry for the Lex store."""

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
    """Represent one ranked Lex fact hit with citation and canonicalized metadata."""

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
    """Return ranked Lex fact matches for a text query."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    query: str
    results: list[LexSearchResultItem] = Field(default_factory=list)
    total: int = 0


__all__ = [
    "EXECUTION_PROFILE_ORDER",
    "POLICY_AUTHORITY_PROFILES",
    "POLICY_AUTHORITY_TO_EXECUTION_PROFILE",
    "POLICY_AUTHORITY_TO_FALLBACK_PROFILE",
    "POLICY_AUTHORITY_TO_VALIDATION_PROFILE",
    "SUPPORTED_EXECUTION_PROFILES",
    "BindingProfileInfo",
    "BindingProfilesListResponse",
    "CacheEntryInfo",
    "CachePolicyType",
    "CacheStatusResponse",
    "CandidateLane",
    "CausalFrontierAreaRecord",
    "CausalFrontierEdgeRecord",
    "CausalFrontierExposureRecord",
    "CausalFrontierOutputRefs",
    "CausalFrontierSAEEstimate",
    "CausalFrontierSAERequest",
    "CausalFrontierSAEResponse",
    "CheckpointPolicyType",
    "ConnectorInfo",
    "ConnectorsListResponse",
    "ControlApprovalProjection",
    "ControlAuthorityGap",
    "ControlFailureEnvelope",
    "ControlJobKind",
    "ControlJobResponse",
    "ControlJobState",
    "ControlOutboxEventInfo",
    "ControlOutboxEventsResponse",
    "ControlProjectionSource",
    "ControlQualityFailure",
    "ControlQualityGate",
    "ControlWorkerLeaseInfo",
    "ControlWorkersResponse",
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
    "DataSourceBinding",
    "DatasetFetchSpecRequest",
    "DecisionValidityEventRequest",
    "DecisionValidityEventResponse",
    "DecisionValidityLifecycleSummary",
    "DecisionValidityPendingReview",
    "DecisionValiditySummaryResponse",
    "DiscoveryCandidate",
    "ExecutionMode",
    "ExecutionProfile",
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
    "MetricCandidate",
    "ModelProfileInfo",
    "ModelProfilesListResponse",
    "NaturalLanguageRunRequest",
    "OperatorDiagnostic",
    "OperatorProjectionAuthority",
    "OperatorProjectionState",
    "OperatorProjectionStateLabel",
    "PolicyAuthorityProfile",
    "PolicyAuthorityProfileMapping",
    "PolicyFallbackProfile",
    "PolicyFlags",
    "PolicyValidationProfile",
    "PreviewStatus",
    "ProductionApprovalDecision",
    "ProductionApprovalEligibility",
    "ProductionApprovalOverridePacket",
    "ProductionApprovalOverrideRequest",
    "ProductionApprovalPacket",
    "ProductionApprovalRequest",
    "ProductionApprovalResponse",
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
    "policy_authority_profile_mapping",
]
