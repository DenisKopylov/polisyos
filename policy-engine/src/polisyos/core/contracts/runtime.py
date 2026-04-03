"""Runtime API contracts for run explorer, debug, evidence, and artifact-inspection endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef, InputRef
from .decision_validity import DecisionValidityStatus
from .execution_plan import (
    EvaluatorVerdict,
    IterationLifecycleState,
    StopReason,
)
from .feedback import (
    DecisionCompareReport,
    DecisionMonitoringContract,
    DecisionMonitoringReport,
    DecisionReissuePlan,
)

SourceKind = Literal["core_run"]
NodeStatus = Literal["ok", "skip", "fail", "unknown"]
PreviewMode = Literal["json", "text", "binary"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApiMeta(BaseModel):
    """Api meta public type."""
    model_config = ConfigDict(extra="forbid")

    request_id: str
    generated_at: datetime = Field(default_factory=_utc_now)
    source_kinds: list[SourceKind] = Field(default_factory=list)


class AuthMeResponse(BaseModel):
    """Authenticated principal payload returned by the runtime ``/auth/me`` endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    user_id: str
    display_name: str
    tenant_id: str
    principal_type: Literal["anonymous", "service", "user"] = "user"
    cell_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    mfa_verified: bool = False
    feature_overrides: dict[str, bool] = Field(default_factory=dict)


class RuntimeApiProblem(BaseModel):
    """Runtime api problem public type."""
    model_config = ConfigDict(extra="forbid")

    type: str = Field(default="about:blank")
    title: str
    status: int = Field(default=500, ge=100, le=599)
    detail: str
    code: str
    instance: str | None = None
    request_id: str | None = None
    # Backward-compatible fields for existing clients.
    error: str | None = None
    status_code: int = Field(default=500, ge=100, le=599)


class RuntimeApiError(RuntimeApiProblem):
    """Backward-compatible alias for runtime API error payloads."""


class CursorPage(BaseModel):
    """Cursor page public type."""
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None
    next_cursor: str | None = None
    count: int = Field(default=0, ge=0)
    total: int | None = Field(default=None, ge=0)


class RunRecordV1(BaseModel):
    """Run record V 1 public type."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    tenant_id: str | None = None
    cell_id: str | None = None
    execution_profile: str | None = None
    control_job_id: str | None = None
    has_trace: bool = False


class RunSummary(RunRecordV1):
    """List-view projection of a run with artifact counts, warnings, and decision status."""
    root_artifact_count: int = Field(default=0, ge=0)
    has_workflow_report: bool = False
    warnings: list[str] = Field(default_factory=list)
    decision_validity_status: DecisionValidityStatus | None = None
    decision_validity_checked_at: datetime | None = None
    decision_review_required: bool = False
    decision_superseded_by_ref: ArtifactRef | None = None


class RunDetails(RunRecordV1):
    """Run details public type."""
    manifest_ref: ArtifactRef | None = None
    trace_ref: ArtifactRef | None = None
    capability_manifest_ref: ArtifactRef | None = None
    root_artifacts: list[ArtifactRef] = Field(default_factory=list)
    has_workflow_report: bool = False
    workflow_report_ref: ArtifactRef | None = None
    warnings: list[str] = Field(default_factory=list)
    decision_validity_status: DecisionValidityStatus | None = None
    decision_validity_checked_at: datetime | None = None
    decision_review_required: bool = False
    decision_superseded_by_ref: ArtifactRef | None = None


class RunTimelineEvent(BaseModel):
    """One timestamped event emitted into the runtime timeline for a run."""
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    timestamp: datetime
    phase: str
    event: str
    span_id: str | None = None
    parent_span_id: str | None = None
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, int | float] = Field(default_factory=dict)
    warning_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)


class RunTimelineSummary(BaseModel):
    """Aggregate counters and latency totals derived from a run's timeline events."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    total_events: int = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    node_status_counts: dict[str, int] = Field(default_factory=dict)
    phase_counts: dict[str, int] = Field(default_factory=dict)
    cache_hits: int = Field(default=0, ge=0)
    cache_stores: int = Field(default=0, ge=0)
    cache_bypasses: int = Field(default=0, ge=0)


class RunTimelineView(BaseModel):
    """Timeline payload returned by runtime endpoints, including summary and ordered events."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    summary: RunTimelineSummary
    events: list[RunTimelineEvent] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunNodeRecord(BaseModel):
    """Per-node execution summary used by node listings and debug surfaces."""
    model_config = ConfigDict(extra="forbid")

    alias: str
    node_id: str | None = None
    status: NodeStatus = "unknown"
    duration_ms: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] = Field(default_factory=dict)
    skip_reason: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)


class NodeDebugView(BaseModel):
    """Detailed node-debug payload with timeline slices, cache activity, and notes."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    alias: str
    record: RunNodeRecord
    timeline_events: list[RunTimelineEvent] = Field(default_factory=list)
    cache_hits: int = Field(default=0, ge=0)
    cache_stores: int = Field(default=0, ge=0)
    cache_bypasses: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)


class GovernanceDebugView(BaseModel):
    """Detailed governance payload exposing verdicts, report refs, and contract warnings."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    verdict: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    issue_summary: dict[str, int] | None = None
    notes: list[str] = Field(default_factory=list)
    report_ref: ArtifactRef | None = None
    report_kind: str | None = None
    report_schema_version: str | None = None
    links: dict[str, ArtifactRef | None] | None = None
    legal_executed: bool | None = None
    transport_summary: dict[str, Any] | None = None
    validation_trace: dict[str, Any] | None = None
    contract_warnings: list[str] = Field(default_factory=list)
    decision_validity: dict[str, Any] | None = None
    normative_summary: dict[str, Any] | None = None
    normative_arbitration_result_ref: ArtifactRef | None = None
    fallback_from_decision_packet: bool = False


class RunErrorView(BaseModel):
    """Normalized error record assembled from manifests, traces, reports, or runtime faults."""
    model_config = ConfigDict(extra="forbid")

    source: Literal["manifest", "workflow_report", "trace", "runtime"]
    code: str
    message: str
    node_alias: str | None = None
    timestamp: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AgentPipelineStep(BaseModel):
    """Agent pipeline step public type."""
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(default=1, ge=1)
    agent: str
    action: str
    status: Literal["ok", "warn", "fail", "info"] = "info"
    timestamp: datetime | None = None
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    prompt: str | None = None
    response: str | None = None
    model: str | None = None
    provider: str | None = None
    model_variant_id: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    token_usage: dict[str, int] = Field(default_factory=dict)


class AgentPipelineAttempt(BaseModel):
    """Agent pipeline attempt public type."""
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    status: str = "unknown"
    verdict: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    steps: list[AgentPipelineStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RetrievalPhaseTelemetry(BaseModel):
    """Retrieval phase telemetry public type."""
    model_config = ConfigDict(extra="forbid")

    phase: str
    lane: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    candidates_total: int = Field(default=0, ge=0)
    candidates_selected: int = Field(default=0, ge=0)
    docs_fetched: int = Field(default=0, ge=0)


class RetrievalTelemetryView(BaseModel):
    """Retrieval telemetry summary for agent pipelines, including lane and phase counters."""
    model_config = ConfigDict(extra="forbid")

    mode: str = "hybrid"
    lane_used: str = "fastlane"
    metadata_docs_fetched: int = Field(default=0, ge=0)
    local_index_size_bytes: int = Field(default=0, ge=0)
    local_index_docs_total: int = Field(default=0, ge=0)
    candidates_filtered: int = Field(default=0, ge=0)
    candidates_promoted: int = Field(default=0, ge=0)
    phases: list[RetrievalPhaseTelemetry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PreflightDiagnosticView(BaseModel):
    """API view of one preflight diagnostic surfaced to runtime clients."""
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: str = "error"
    message: str
    path: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class PreflightReportView(BaseModel):
    """API view of preflight readiness, diagnostics, and the persisted report reference."""
    model_config = ConfigDict(extra="forbid")

    ready_to_run: bool = False
    diagnostics: list[PreflightDiagnosticView] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    report_ref: ArtifactRef | None = None


class EvaluatorScoresView(BaseModel):
    """Normalized evaluator score breakdown exposed by runtime agent-pipeline views."""
    model_config = ConfigDict(extra="forbid")

    kpi_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    constraints_score: float = Field(default=0.0, ge=0.0, le=1.0)
    data_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    budget_score: float = Field(default=0.0, ge=0.0, le=1.0)
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)


class EvaluatorReportView(BaseModel):
    """API view of evaluator verdicts, scores, reasons, and replanning hints."""
    model_config = ConfigDict(extra="forbid")

    verdict: EvaluatorVerdict | None = None
    scores: EvaluatorScoresView = Field(default_factory=EvaluatorScoresView)
    reasons: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    diagnostics: list[PreflightDiagnosticView] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    report_ref: ArtifactRef | None = None


class IterationLifecycleView(BaseModel):
    """Current iteration state with stop reason and latest evaluator verdict."""
    model_config = ConfigDict(extra="forbid")

    iteration: int = Field(default=1, ge=1)
    state: IterationLifecycleState = "plan_created"
    stop_reason: StopReason | None = None
    last_verdict: EvaluatorVerdict | None = None
    state_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class ReproducibilityView(BaseModel):
    """Hashes, seeds, and missing refs used to assess whether a run can be replayed."""
    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=0, ge=0)
    seed_source: str | None = None
    determinism_tier: str | None = None
    plan_hash: str | None = None
    registry_hash: str | None = None
    method_catalog_hash: str | None = None
    data_snapshot_hash: str | None = None
    input_bindings_hash: str | None = None
    readiness: str | None = None
    why_partial: list[str] = Field(default_factory=list)
    missing_refs: list[str] = Field(default_factory=list)
    suggested_next_step: str | None = None
    manifest_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class RunEvidenceNeedView(BaseModel):
    """One evidence need derived from the execution plan for retrieval and promotion flows."""
    model_config = ConfigDict(extra="forbid")

    need_id: str
    metric: str
    geography: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    granularity: str = "annual"
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    purpose: str = "policy_drafting"
    matched_plan_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunEvidencePlanView(BaseModel):
    """Fetch plan describing how a connector/profile can satisfy a run evidence need."""
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    metric_id: str
    connector_id: str
    dataset_id: str
    profile_id: str | None = None
    source_lane: str = "fastlane"
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_start: str | None = None
    date_end: str | None = None
    granularity: str | None = None
    fallback_count: int = Field(default=0, ge=0)
    matched_need_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunEvidencePromotionView(BaseModel):
    """Candidate evidence promotion surfaced while reviewing retrieved data options."""
    model_config = ConfigDict(extra="forbid")

    promotion_id: str
    metric_id: str
    connector_id: str
    dataset_id: str
    profile_id: str | None = None
    source_lane: str = "explorelane"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "pending"
    created_at: datetime | None = None
    signals: list[str] = Field(default_factory=list)
    matched_plan_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunEvidenceContextView(BaseModel):
    """Joined evidence context linking plans, snapshots, promotions, and related artifacts."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    execution_plan_ref: ArtifactRef | None = None
    evidence_bundle_ref: ArtifactRef | None = None
    data_snapshot_ref: ArtifactRef | None = None
    input_bindings_ref: ArtifactRef | None = None
    related_artifacts: list[ArtifactRef] = Field(default_factory=list)
    data_needs: list[RunEvidenceNeedView] = Field(default_factory=list)
    fetch_plans: list[RunEvidencePlanView] = Field(default_factory=list)
    promotion_candidates: list[RunEvidencePromotionView] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AgentPipelineView(BaseModel):
    """Composite runtime view of agent attempts, retrieval, evaluation, and iteration state."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    total_attempts: int = Field(default=0, ge=0)
    latest_verdict: str | None = None
    attempts: list[AgentPipelineAttempt] = Field(default_factory=list)
    decision_packet_ref: ArtifactRef | None = None
    reflexion_terminal_ref: ArtifactRef | None = None
    retrieval: RetrievalTelemetryView | None = None
    execution_plan_ref: ArtifactRef | None = None
    method_catalog_snapshot_ref: ArtifactRef | None = None
    preflight: PreflightReportView | None = None
    evaluator: EvaluatorReportView | None = None
    iteration_lifecycle: IterationLifecycleView | None = None
    reproducibility: ReproducibilityView | None = None
    source: str | None = None
    notes: list[str] = Field(default_factory=list)


class RunWorkflowNodeView(BaseModel):
    """Workflow graph node annotated with runtime status, duration, and artifact IO."""
    model_config = ConfigDict(extra="forbid")

    alias: str
    node_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    depth: int = Field(default=0, ge=0)
    status: NodeStatus = "unknown"
    duration_ms: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    heat: float = Field(default=0.0, ge=0.0)


class RunWorkflowEdgeView(BaseModel):
    """Run workflow edge view data model."""
    model_config = ConfigDict(extra="forbid")

    from_alias: str
    to_alias: str


class RunWorkflowSummary(BaseModel):
    """Summary statistics for the workflow graph executed by a run."""
    model_config = ConfigDict(extra="forbid")

    workflow_id: str | None = None
    error_policy: str | None = None
    status: str | None = None
    node_count: int = Field(default=0, ge=0)
    edge_count: int = Field(default=0, ge=0)
    ok_count: int = Field(default=0, ge=0)
    skip_count: int = Field(default=0, ge=0)
    fail_count: int = Field(default=0, ge=0)
    max_depth: int = Field(default=0, ge=0)
    critical_path_duration_ms: int | None = Field(default=None, ge=0)


class RunWorkflowView(BaseModel):
    """Workflow graph payload returned by runtime explorer endpoints."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    summary: RunWorkflowSummary
    nodes: list[RunWorkflowNodeView] = Field(default_factory=list)
    edges: list[RunWorkflowEdgeView] = Field(default_factory=list)
    workflow_spec_ref: ArtifactRef | None = None
    workflow_report_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class ArtifactManifestView(BaseModel):
    """Metadata returned when a client inspects a stored artifact manifest."""
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    media_type: str
    byte_size: int = Field(ge=0)
    created_at: datetime
    schema_name: str | None = None
    schema_version: str | None = None
    producer_component: str | None = None
    producer_version: str | None = None
    inputs: list[InputRef] = Field(default_factory=list)
    integrity_sha256: str


class ArtifactContentPreview(BaseModel):
    """Artifact content preview public type."""
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    media_type: str
    mode: PreviewMode
    size_bytes: int = Field(ge=0)
    max_bytes: int = Field(ge=1)
    truncated: bool = False
    preview: Any = None


class ArtifactLineageNode(BaseModel):
    """One node in the artifact-lineage graph with status, size, role, and depth."""
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    role: str | None = None
    kind: str | None = None
    status: str
    byte_size: int = Field(default=0, ge=0)
    depth: int = Field(default=0, ge=0)


class ArtifactLineageEdge(BaseModel):
    """Artifact lineage edge public type."""
    model_config = ConfigDict(extra="forbid")

    parent_artifact_id: str
    child_artifact_id: str
    role: str


class ArtifactLineageView(BaseModel):
    """Artifact lineage graph plus completeness and corruption indicators."""
    model_config = ConfigDict(extra="forbid")

    root_artifact_ids: list[str] = Field(default_factory=list)
    total_nodes: int = Field(default=0, ge=0)
    total_edges: int = Field(default=0, ge=0)
    total_size_bytes: int = Field(default=0, ge=0)
    is_complete: bool = False
    missing_artifact_ids: list[str] = Field(default_factory=list)
    corrupted_artifact_ids: list[str] = Field(default_factory=list)
    nodes: list[ArtifactLineageNode] = Field(default_factory=list)
    edges: list[ArtifactLineageEdge] = Field(default_factory=list)


class ArtifactSchemaView(BaseModel):
    """Schema metadata exposed for an artifact's serialized payload."""
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    media_type: str
    schema_name: str | None = None
    schema_version: str | None = None
    top_level_keys: list[str] = Field(default_factory=list)


class RunFeedbackView(BaseModel):
    """Runtime view of monitoring, compare, and reissue artifacts attached to a run."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    decision_packet_ref: ArtifactRef | None = None
    feedback_loop: dict[str, Any] | None = None
    monitoring_contract: DecisionMonitoringContract | None = None
    monitoring_report: DecisionMonitoringReport | None = None
    compare_report: DecisionCompareReport | None = None
    reissue_plan: DecisionReissuePlan | None = None
    decision_validity: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)


class RunCompareView(BaseModel):
    """Side-by-side comparison payload for two runtime runs."""
    model_config = ConfigDict(extra="forbid")

    left_run_id: str
    right_run_id: str
    report: DecisionCompareReport


class RunsListResponse(BaseModel):
    """Paginated response envelope returned by the runs listing endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    page: CursorPage
    runs: list[RunSummary] = Field(default_factory=list)


class RunDetailsResponse(BaseModel):
    """Response envelope returned when a client requests one run's detailed record."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run: RunDetails


class RunTimelineResponse(BaseModel):
    """Response envelope returned by the run timeline endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    timeline: RunTimelineView


class RunNodesResponse(BaseModel):
    """Response envelope returned by the run nodes endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    source_kind: SourceKind
    nodes: list[RunNodeRecord] = Field(default_factory=list)


class RunLineageResponse(BaseModel):
    """Response envelope returned by the run artifact-lineage endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    lineage: ArtifactLineageView


class RunEvidenceContextResponse(BaseModel):
    """Response envelope returned by the run evidence-context endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    context: RunEvidenceContextView


class NodeDebugResponse(BaseModel):
    """Response envelope returned by the node debug endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    debug: NodeDebugView


class GovernanceDebugResponse(BaseModel):
    """Response envelope returned by the governance debug endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    debug: GovernanceDebugView


class RunErrorsResponse(BaseModel):
    """Response envelope returned by the run errors endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    errors: list[RunErrorView] = Field(default_factory=list)


class AgentPipelineResponse(BaseModel):
    """Response envelope returned by the agent-pipeline endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    pipeline: AgentPipelineView


class RunWorkflowResponse(BaseModel):
    """Response envelope returned by the workflow graph endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    workflow: RunWorkflowView


class ArtifactManifestResponse(BaseModel):
    """Response envelope returned by the artifact manifest endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifact: ArtifactManifestView


class ArtifactContentResponse(BaseModel):
    """Response envelope returned by the artifact preview/content endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifact: ArtifactContentPreview


class ArtifactLineageResponse(BaseModel):
    """Response envelope returned by the artifact lineage endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    lineage: ArtifactLineageView


class ArtifactSchemaResponse(BaseModel):
    """Response envelope returned by the artifact schema endpoint."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    meta: ApiMeta
    schema_view: ArtifactSchemaView = Field(alias="schema")


class RunFeedbackResponse(BaseModel):
    """Response envelope returned by the run feedback endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    feedback: RunFeedbackView


class RunCompareResponse(BaseModel):
    """Response envelope returned by the run comparison endpoint."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    compare: RunCompareView


class FeedbackActionResponse(BaseModel):
    """Outcome payload returned after evaluating feedback or reissuing a decision."""
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    action: Literal["evaluate_feedback", "reissue"]
    status: Literal["completed", "accepted"] = "completed"
    monitoring_report_ref: ArtifactRef | None = None
    compare_report_ref: ArtifactRef | None = None
    reissue_plan_ref: ArtifactRef | None = None
    reissued_run_id: str | None = None
    message: str


__all__ = [
    "AgentPipelineAttempt",
    "AgentPipelineResponse",
    "AgentPipelineStep",
    "AgentPipelineView",
    "ApiMeta",
    "AuthMeResponse",
    "ArtifactContentPreview",
    "ArtifactContentResponse",
    "ArtifactLineageEdge",
    "ArtifactLineageNode",
    "ArtifactLineageResponse",
    "ArtifactLineageView",
    "ArtifactManifestResponse",
    "ArtifactManifestView",
    "ArtifactSchemaResponse",
    "ArtifactSchemaView",
    "CursorPage",
    "DecisionCompareReport",
    "DecisionMonitoringContract",
    "DecisionMonitoringReport",
    "DecisionReissuePlan",
    "FeedbackActionResponse",
    "GovernanceDebugResponse",
    "GovernanceDebugView",
    "NodeDebugResponse",
    "NodeDebugView",
    "NodeStatus",
    "PreflightDiagnosticView",
    "PreflightReportView",
    "PreviewMode",
    "EvaluatorScoresView",
    "EvaluatorReportView",
    "IterationLifecycleView",
    "ReproducibilityView",
    "RunEvidenceContextResponse",
    "RunEvidenceContextView",
    "RunEvidenceNeedView",
    "RunEvidencePlanView",
    "RunEvidencePromotionView",
    "RetrievalPhaseTelemetry",
    "RetrievalTelemetryView",
    "RunDetails",
    "RunDetailsResponse",
    "RunErrorView",
    "RunErrorsResponse",
    "RunFeedbackResponse",
    "RunFeedbackView",
    "RunLineageResponse",
    "RunNodeRecord",
    "RunNodesResponse",
    "RunRecordV1",
    "RunSummary",
    "RunCompareResponse",
    "RunCompareView",
    "RunTimelineEvent",
    "RunTimelineResponse",
    "RunTimelineSummary",
    "RunTimelineView",
    "RunWorkflowEdgeView",
    "RunWorkflowNodeView",
    "RunWorkflowResponse",
    "RunWorkflowSummary",
    "RunWorkflowView",
    "RunsListResponse",
    "RuntimeApiError",
    "RuntimeApiProblem",
    "SourceKind",
]
