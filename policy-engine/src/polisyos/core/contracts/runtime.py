from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef, InputRef

SourceKind = Literal["core_run"]
NodeStatus = Literal["ok", "skip", "fail", "unknown"]
PreviewMode = Literal["json", "text", "binary"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApiMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    generated_at: datetime = Field(default_factory=_utc_now)
    source_kinds: list[SourceKind] = Field(default_factory=list)


class RuntimeApiProblem(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None
    next_cursor: str | None = None
    count: int = Field(default=0, ge=0)
    total: int | None = Field(default=None, ge=0)


class RunRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    tenant_id: str | None = None
    cell_id: str | None = None
    has_trace: bool = False


class RunSummary(RunRecordV1):
    root_artifact_count: int = Field(default=0, ge=0)
    has_workflow_report: bool = False
    warnings: list[str] = Field(default_factory=list)


class RunDetails(RunRecordV1):
    manifest_ref: ArtifactRef | None = None
    trace_ref: ArtifactRef | None = None
    root_artifacts: list[ArtifactRef] = Field(default_factory=list)
    has_workflow_report: bool = False
    workflow_report_ref: ArtifactRef | None = None
    warnings: list[str] = Field(default_factory=list)


class RunTimelineEvent(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    summary: RunTimelineSummary
    events: list[RunTimelineEvent] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunNodeRecord(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    verdict: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    report_ref: ArtifactRef | None = None
    validation_trace: dict[str, Any] | None = None
    fallback_from_decision_packet: bool = False


class RunErrorView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["manifest", "workflow_report", "trace", "runtime"]
    code: str
    message: str
    node_alias: str | None = None
    timestamp: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AgentPipelineStep(BaseModel):
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
    latency_ms: int | None = Field(default=None, ge=0)
    token_usage: dict[str, int] = Field(default_factory=dict)


class AgentPipelineAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    status: str = "unknown"
    verdict: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    steps: list[AgentPipelineStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AgentPipelineView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    total_attempts: int = Field(default=0, ge=0)
    latest_verdict: str | None = None
    attempts: list[AgentPipelineAttempt] = Field(default_factory=list)
    decision_packet_ref: ArtifactRef | None = None
    reflexion_terminal_ref: ArtifactRef | None = None
    source: str | None = None
    notes: list[str] = Field(default_factory=list)


class RunWorkflowNodeView(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    from_alias: str
    to_alias: str


class RunWorkflowSummary(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    role: str | None = None
    kind: str | None = None
    status: str
    byte_size: int = Field(default=0, ge=0)
    depth: int = Field(default=0, ge=0)


class ArtifactLineageEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_artifact_id: str
    child_artifact_id: str
    role: str


class ArtifactLineageView(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    media_type: str
    schema_name: str | None = None
    schema_version: str | None = None
    top_level_keys: list[str] = Field(default_factory=list)


class RunsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    page: CursorPage
    runs: list[RunSummary] = Field(default_factory=list)


class RunDetailsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run: RunDetails


class RunTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    timeline: RunTimelineView


class RunNodesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    source_kind: SourceKind
    nodes: list[RunNodeRecord] = Field(default_factory=list)


class RunLineageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    lineage: ArtifactLineageView


class NodeDebugResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    debug: NodeDebugView


class GovernanceDebugResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    debug: GovernanceDebugView


class RunErrorsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    errors: list[RunErrorView] = Field(default_factory=list)


class AgentPipelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    pipeline: AgentPipelineView


class RunWorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    workflow: RunWorkflowView


class ArtifactManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifact: ArtifactManifestView


class ArtifactContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifact: ArtifactContentPreview


class ArtifactLineageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    lineage: ArtifactLineageView


class ArtifactSchemaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    meta: ApiMeta
    schema_view: ArtifactSchemaView = Field(alias="schema")


__all__ = [
    "AgentPipelineAttempt",
    "AgentPipelineResponse",
    "AgentPipelineStep",
    "AgentPipelineView",
    "ApiMeta",
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
    "GovernanceDebugResponse",
    "GovernanceDebugView",
    "NodeDebugResponse",
    "NodeDebugView",
    "NodeStatus",
    "PreviewMode",
    "RunDetails",
    "RunDetailsResponse",
    "RunErrorView",
    "RunErrorsResponse",
    "RunLineageResponse",
    "RunNodeRecord",
    "RunNodesResponse",
    "RunRecordV1",
    "RunSummary",
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
