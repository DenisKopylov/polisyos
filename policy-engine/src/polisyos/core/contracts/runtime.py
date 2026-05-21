"""Runtime API contracts for run explorer, debug, evidence, and artifact-inspection endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
from .foundry import EquilibriumMultiplicityReport

SourceKind = Literal["core_run"]
NodeStatus = Literal["ok", "skip", "fail", "unknown"]
PreviewMode = Literal["json", "text", "binary"]
VerificationStatus = Literal["verified", "pending", "disputed", "untraced"]
LineageFreshness = Literal["current", "stale", "unknown"]
DisputeStatus = Literal["none", "disputed", "under_review", "resolved"]
QuantityClass = Literal["decision", "telemetry", "layout", "debug"]
ComparabilityStatus = Literal["compatible", "warning", "blocked"]
CompareCandidateRelation = Literal["baseline", "previous", "selected", "recommended"]
CompareResponseStatus = Literal["computed", "client_computable"]
DeltaSignificance = Literal["improved", "worsened", "mixed", "uncertain", "not_comparable"]
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
DeltaDominance = Literal["a", "b", "none", "mixed", "unknown"]
CounterfactualMode = Literal["actual", "actual_vs_scenario", "scenario_only"]
ScenarioStatus = Literal["draft", "computed", "stale", "failed"]
ScenarioLifecycleStatus = Literal["generated", "draft", "saved", "promoted"]
ScenarioAssumptionStatus = Literal[
    "operator_assumption",
    "model_assumption",
    "observed_evidence",
    "disputed",
]
ScenarioInterventionOperator = Literal["set", "add", "multiply", "remove"]
ScenarioConstraintSeverity = Literal["error", "warning"]
ScenarioSurfaceSupport = Literal[
    "run_metrics",
    "quantities",
    "lineage",
    "charts",
    "whatif",
]
BureaucraticGenre = Literal[
    "postanova_kmu",
    "zakonoproekt",
    "expert_vysnovok",
    "analitichna_zapyska",
]
BureaucraticBlockKind = Literal[
    "header",
    "requisites",
    "preamble",
    "legal_basis",
    "section",
    "article",
    "clause",
    "subclause",
    "paragraph",
    "list",
    "table",
    "quantity",
    "annex",
    "signature",
    "appendix",
]
BureaucraticEpistemicKind = Literal[
    "evidence_filled",
    "model_generated",
    "operator_filled",
    "imported",
]
BureaucraticDocumentStatus = Literal["draft", "signed_external", "archived"]
BureaucraticExportFormat = Literal["html", "pdf", "docx"]
TemporalSurfaceSupport = Literal[
    "run_details",
    "run_timeline",
    "run_lineage",
    "run_quantities",
    "run_fabric_decision_data",
    "run_compare",
    "run_agents",
    "run_evidence_context",
    "run_workflow",
    "run_nodes",
    "artifact_content",
]
TemporalEventKind = Literal[
    "run_start",
    "run_finish",
    "trace_event",
    "policy_change",
    "late_evidence",
    "correction",
    "snapshot",
    "now",
]
LineageSummaryKind = Literal[
    "source",
    "transform",
    "model",
    "agent",
    "result",
    "artifact",
    "dataset",
    "method",
    "unknown",
]
FabricImpactSubjectKind = Literal["lineage", "source_contract", "run", "decision_data"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


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


class UnitRef(BaseModel):
    """Machine-readable unit identity plus a human display label."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    system: str = Field(default="ucum", min_length=1)
    display: str | None = None


class TemporalRef(BaseModel):
    """Bitemporal and snapshot scope carried by a decision-bearing value."""

    model_config = ConfigDict(extra="forbid")

    valid_at: datetime | None = None
    tx_at: datetime | None = None
    snapshot_id: str | None = None
    branch: str | None = None
    scenario_id: str | None = None


class TemporalScope(BaseModel):
    """Canonical bitemporal cursor used by runtime API and dashboard cache keys."""

    model_config = ConfigDict(extra="forbid")

    valid_at: datetime | None = None
    tx_at: datetime | None = None
    branch: str | None = None
    snapshot_id: str | None = None
    scenario_id: str | None = None


class TemporalRange(BaseModel):
    """Inclusive range in which a temporal cursor can be used."""

    model_config = ConfigDict(extra="forbid")

    earliest: datetime | None = None
    latest: datetime | None = None


class TemporalGapRange(BaseModel):
    """Typed unavailable interval for a temporal surface."""

    model_config = ConfigDict(extra="forbid")

    start: datetime | None = None
    end: datetime | None = None
    reason_code: str
    label: str | None = None


class TemporalEventPoint(BaseModel):
    """Known event point used by scrubber snapping and capability diagnostics."""

    model_config = ConfigDict(extra="forbid")

    id: str
    timestamp: datetime
    kind: TemporalEventKind = "trace_event"
    label: str
    valid_at: datetime | None = None
    tx_at: datetime | None = None
    observed: bool = True


class TemporalSurfaceCapability(BaseModel):
    """Support declaration for one time-sensitive runtime surface."""

    model_config = ConfigDict(extra="forbid")

    surface: TemporalSurfaceSupport
    supported: bool
    resolution: str = "event"
    reason_code: str | None = None
    valid_range: TemporalRange | None = None
    tx_range: TemporalRange | None = None
    nearest_event_points: list[TemporalEventPoint] = Field(default_factory=list)
    gaps: list[TemporalGapRange] = Field(default_factory=list)


class TemporalIndexEvidence(BaseModel):
    """Index and slow-query evidence for temporal world lookups."""

    model_config = ConfigDict(extra="forbid")

    table: str
    adapter: str = "duckdb"
    index_name: str
    columns: list[str] = Field(default_factory=list)
    status: Literal["implemented", "recommended", "missing", "not_applicable"] = "implemented"
    slow_query_gate_ms: int = Field(default=500, ge=1)
    evidence_ref: str | None = None


class TemporalCapabilitiesView(BaseModel):
    """Temporal capability manifest for one run or the runtime as a whole."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    default_scope: TemporalScope | None = None
    valid_range: TemporalRange = Field(default_factory=TemporalRange)
    tx_range: TemporalRange = Field(default_factory=TemporalRange)
    resolution: str = "event"
    surfaces: list[TemporalSurfaceCapability] = Field(default_factory=list)
    event_points: list[TemporalEventPoint] = Field(default_factory=list)
    nearest_event_points: list[TemporalEventPoint] = Field(default_factory=list)
    supported_tables: list[str] = Field(default_factory=list)
    unsupported_surfaces: list[TemporalSurfaceSupport] = Field(default_factory=list)
    branch_support: bool = False
    snapshot_support: bool = False
    scenario_branch_support: Literal["explicit_only", "unsupported"] = "unsupported"
    graph_temporal_scope: Literal["full", "partial", "unsupported"] = "unsupported"
    slow_query_evidence: list[TemporalIndexEvidence] = Field(default_factory=list)


class TemporalCapabilitiesResponse(BaseModel):
    """Response envelope for temporal capabilities and gaps."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    capabilities: TemporalCapabilitiesView


class FabricSourceScorecardsResponse(BaseModel):
    """Response envelope for generated Fabric source scorecards."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    schema_version: str = "fabric.source_scorecard.v1"
    generated_at: datetime | None = None
    count: int = Field(default=0, ge=0)
    scorecards: dict[str, dict[str, Any]] = Field(default_factory=dict)


class FabricQualityTrustBatchRequest(BaseModel):
    """Run-scoped batch request for Fabric quality/trust metadata."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    decision_data_ids: list[str] = Field(default_factory=list, max_length=100)
    temporal_scope: TemporalScope | None = None


class FabricQualityBatchResponse(BaseModel):
    """Batch response for Fabric quality refs without client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    quality_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)


class FabricTrustBatchResponse(BaseModel):
    """Batch response for Fabric trust-envelope refs without client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    trust_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)


class FabricReplayRunResponse(BaseModel):
    """Run-scoped replay metadata extracted from Fabric decision-data envelopes."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    replay_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)


class FabricImpactAnalysisRequest(BaseModel):
    """Request body for Fabric-backed impact analysis."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    lineage_ids: list[str] = Field(default_factory=list, max_length=100)
    source_contract_ids: list[str] = Field(default_factory=list, max_length=100)
    temporal_scope: TemporalScope | None = None
    max_depth: int = Field(default=2, ge=1, le=8)


class FabricImpactRecord(BaseModel):
    """One origin/impact row for a Fabric lineage or source-contract subject."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str
    subject_kind: FabricImpactSubjectKind
    lineage_status: VerificationStatus = "untraced"
    quality_status: str | None = None
    replay_status: str | None = None
    downstream_refs: list[str] = Field(default_factory=list)
    upstream_refs: list[str] = Field(default_factory=list)
    affected_decision_data_ids: list[str] = Field(default_factory=list)
    source_contract_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FabricImpactAnalysisResponse(BaseModel):
    """Response envelope for Fabric impact analysis."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    impacts: list[FabricImpactRecord] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class VerificationMetadata(BaseModel):
    """Audit metadata used by Trust View without changing the underlying truth."""

    model_config = ConfigDict(extra="forbid")

    hash: str | None = None
    verification_status: VerificationStatus = "untraced"
    verified_by: str | None = None
    verified_at: datetime | None = None
    verification_method: str | None = None
    freshness: LineageFreshness = "unknown"
    dispute_status: DisputeStatus = "none"
    temporal_scope: TemporalScope | None = None


class TrustMetadataRef(BaseModel):
    """Selected runtime object and its Trust View metadata payload."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1)
    subject_kind: Literal["quantity", "authored_text", "artifact", "lineage", "chart"] = "lineage"
    trust_metadata: VerificationMetadata


class LineageCompactSummaryItem(BaseModel):
    """One compact lineage crumb suitable for inline and hover surfaces."""

    model_config = ConfigDict(extra="forbid")

    kind: LineageSummaryKind = "unknown"
    label: str
    id: str | None = None


class LineageRef(BaseModel):
    """Typed lineage reference embedded inside `QuantityValue` envelopes."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    hash: str | None = None
    status: VerificationStatus = "untraced"
    freshness: LineageFreshness = "unknown"
    summary: dict[str, str] = Field(default_factory=dict)
    compact_summary: list[LineageCompactSummaryItem] = Field(default_factory=list)
    reason_code: str | None = None
    tracking_issue: str | None = None
    trust_metadata: VerificationMetadata | None = None

    @model_validator(mode="after")
    def _validate_untraced_contract(self) -> LineageRef:
        if self.id == "untraced" and self.status != "untraced":
            raise ValueError('lineage id "untraced" requires status="untraced"')
        if self.status == "untraced":
            if not self.reason_code:
                raise ValueError("untraced lineage requires reason_code")
            if not self.tracking_issue:
                raise ValueError("untraced lineage requires tracking_issue")
        return self


class QuantityUncertainty(BaseModel):
    """Uncertainty envelope for a decision-bearing quantity."""

    model_config = ConfigDict(extra="forbid")

    ci_80: tuple[float, float] | None = None
    ci_95: tuple[float, float] | None = None
    quantiles: dict[str, float] = Field(default_factory=dict)
    method: Literal["bootstrap", "bayesian", "analytic", "simulation", "none"] | str | None = None
    identifiability: Literal["identified", "estimated", "assumed", "unknown"] = "unknown"
    disputed: bool = False


class QuantityValue(BaseModel):
    """Canonical envelope for every numeric value that can influence a decision."""

    model_config = ConfigDict(extra="forbid")

    point: float | None = None
    unit: UnitRef
    metric_id: str | None = None
    lineage: LineageRef
    uncertainty: QuantityUncertainty | None = None
    time: TemporalRef | None = None
    quantity_class: QuantityClass = "decision"
    label: str | None = None


class LineageGraphNode(BaseModel):
    """Runtime lineage graph node projected from artifact or Fabric provenance."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "unknown"
    label: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageGraphEdge(BaseModel):
    """Runtime lineage graph edge projected from artifact or Fabric provenance."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    relation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageExportLinks(BaseModel):
    """Stable export links for external lineage interoperability formats."""

    model_config = ConfigDict(extra="forbid")

    openlineage: str
    prov: str


class LineageGraphView(BaseModel):
    """Compact plus full runtime lineage graph view."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: VerificationStatus = "untraced"
    hash: str | None = None
    freshness: LineageFreshness = "unknown"
    compact_summary: list[LineageCompactSummaryItem] = Field(default_factory=list)
    nodes: list[LineageGraphNode] = Field(default_factory=list)
    edges: list[LineageGraphEdge] = Field(default_factory=list)
    exports: LineageExportLinks
    metadata: dict[str, Any] = Field(default_factory=dict)
    trust_metadata: VerificationMetadata | None = None


class LineageBatchRequest(BaseModel):
    """Batch lineage lookup request used to avoid client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    lineage_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)


class LineageResponse(BaseModel):
    """Response envelope returned by one runtime lineage lookup."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    lineage: LineageGraphView


class LineageBatchResponse(BaseModel):
    """Response envelope returned by runtime lineage batch lookup."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    lineages: list[LineageGraphView] = Field(default_factory=list)


class LineageExportResponse(BaseModel):
    """Response envelope returned by runtime lineage export endpoints."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    lineage_id: str
    format: Literal["openlineage", "prov"]
    payload: dict[str, Any]


class QuantityCoverageEntry(BaseModel):
    """One numeric field discovered by the quantity coverage inventory."""

    model_config = ConfigDict(extra="forbid")

    path: str
    quantity_class: QuantityClass
    status: VerificationStatus
    lineage_id: str | None = None
    metric_id: str | None = None
    reason_code: str | None = None
    tracking_issue: str | None = None


class QuantityCoverageSummary(BaseModel):
    """Class-aware coverage counts for quantity law migration."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(default=0, ge=0)
    decision: int = Field(default=0, ge=0)
    telemetry: int = Field(default=0, ge=0)
    layout: int = Field(default=0, ge=0)
    debug: int = Field(default=0, ge=0)
    traced: int = Field(default=0, ge=0)
    untraced: int = Field(default=0, ge=0)


class RunQuantitiesResponse(BaseModel):
    """Response envelope returned by the run quantity inventory endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    source_kind: SourceKind
    temporal_scope: TemporalScope | None = None
    quantities: list[QuantityValue] = Field(default_factory=list)
    coverage: QuantityCoverageSummary = Field(default_factory=QuantityCoverageSummary)
    entries: list[QuantityCoverageEntry] = Field(default_factory=list)


class ComparisonFrame(BaseModel):
    """Canonical scope that makes two run payloads comparable."""

    model_config = ConfigDict(extra="forbid")

    run_a: str
    run_b: str
    metric_set: list[str] = Field(default_factory=list)
    population: str | None = None
    unit_policy: Literal["canonical", "source", "mixed"] = "canonical"
    temporal_scope: TemporalScope | None = None
    scenario_scope: dict[str, Any] = Field(default_factory=dict)
    assumption_set: list[str] = Field(default_factory=list)


class ComparabilityReport(BaseModel):
    """Pre-flight report that prevents misleading run comparisons."""

    model_config = ConfigDict(extra="forbid")

    status: ComparabilityStatus
    warnings: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)


class LineageDelta(BaseModel):
    """Compact provenance drift summary for one compared metric."""

    model_config = ConfigDict(extra="forbid")

    source_changed: bool = False
    model_changed: bool = False
    hash_changed: bool = False
    freshness_changed: bool = False
    verification_changed: str | None = None
    notes: list[str] = Field(default_factory=list)


class DeltaDistribution(BaseModel):
    """Distributional summary of a metric delta."""

    model_config = ConfigDict(extra="forbid")

    quantiles: dict[str, float] = Field(default_factory=dict)
    mean_shift: float | None = None
    median_shift: float | None = None
    ci_overlap: bool | None = None


class DeltaQuantity(BaseModel):
    """One decision-bearing metric comparison with quantity-law envelopes."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str
    a: QuantityValue | None = None
    b: QuantityValue | None = None
    delta_absolute: QuantityValue | None = None
    delta_relative: QuantityValue | None = None
    delta_distribution: DeltaDistribution = Field(default_factory=DeltaDistribution)
    significance: DeltaSignificance = "uncertain"
    dominance: DeltaDominance = "unknown"
    decision_salience: float = Field(default=0.0, ge=0.0, le=1.0)
    lineage_delta: LineageDelta = Field(default_factory=LineageDelta)


class CompareCandidate(BaseModel):
    """One candidate run suggested as a meaningful comparator."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    label: str | None = None
    relation: CompareCandidateRelation = "recommended"
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    comparability: ComparabilityReport


class CompareRunResponse(BaseModel):
    """Response envelope for the best-in-class policy diff endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: CompareResponseStatus = "computed"
    temporal_scope: TemporalScope | None = None
    comparison_frame: ComparisonFrame
    comparability: ComparabilityReport
    deltas: list[DeltaQuantity] = Field(default_factory=list)


class CompareCandidatesResponse(BaseModel):
    """Response envelope for compare-candidate discovery."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    candidates: list[CompareCandidate] = Field(default_factory=list)


class ScenarioConstraint(BaseModel):
    """One explicit constraint that bounds a scenario intervention."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str
    field: str | None = None
    severity: ScenarioConstraintSeverity = "warning"
    operator: str | None = None
    value: QuantityValue | None = None
    message: str | None = None


class ScenarioAssumption(BaseModel):
    """Named scenario assumption with provenance."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str
    status: ScenarioAssumptionStatus
    lineage: LineageRef
    description: str | None = None


class ScenarioIntervention(BaseModel):
    """One operator-visible policy intervention inside a scenario manifest."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    operator: ScenarioInterventionOperator
    value: QuantityValue
    baseline_value: QuantityValue | None = None
    constraint_ids: list[str] = Field(default_factory=list)


class ScenarioRef(BaseModel):
    """Stable reference carried by every counterfactual value."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    status: ScenarioStatus
    baseline_run_id: str = Field(min_length=1)
    temporal_scope: TemporalScope | None = None
    lineage: LineageRef
    assumption_ids: list[str] = Field(min_length=1)
    manifest_hash: str | None = None


class ScenarioManifest(BaseModel):
    """Manifest that makes a counterfactual named, reproducible and auditable."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    baseline_run_id: str = Field(min_length=1)
    status: ScenarioStatus
    lifecycle_status: ScenarioLifecycleStatus = "generated"
    revision: int = Field(default=1, ge=1)
    manifest_hash: str = ""
    temporal_scope: TemporalScope | None = None
    policy_question: str = Field(min_length=1)
    author: str = Field(min_length=1)
    affected_population: str | None = None
    temporal_window: TemporalRange | None = None
    model_family: str = Field(min_length=1)
    model_version: str | None = None
    model_lineage: LineageRef
    baseline_lineage: LineageRef | None = None
    baseline_hash: str | None = None
    computed_at: datetime | None = None
    saved_at: datetime | None = None
    promoted_at: datetime | None = None
    validity_window: TemporalRange | None = None
    known_limitations: list[str] = Field(default_factory=list)
    stale_reasons: list[str] = Field(default_factory=list)
    interventions: list[ScenarioIntervention] = Field(min_length=1)
    assumptions: list[ScenarioAssumption] = Field(min_length=1)
    constraints: list[ScenarioConstraint] = Field(default_factory=list)
    phase4_gate_verdict: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_scenario_manifest(self) -> ScenarioManifest:
        assumption_ids = {assumption.id for assumption in self.assumptions}
        constraint_ids = {constraint.id for constraint in self.constraints}
        for intervention in self.interventions:
            unknown_constraints = [
                constraint_id
                for constraint_id in intervention.constraint_ids
                if constraint_id not in constraint_ids
            ]
            if unknown_constraints:
                raise ValueError(
                    "intervention references unknown constraints: "
                    + ",".join(sorted(unknown_constraints))
                )
        if not assumption_ids:
            raise ValueError("scenario manifest requires at least one assumption")
        return self


class CounterfactualMetric(BaseModel):
    """Actual, scenario and delta values for one metric."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(min_length=1)
    label: str
    actual: QuantityValue
    counterfactual: QuantityValue
    delta: QuantityValue
    scenario_ref: ScenarioRef
    assumption_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_counterfactual_metric(self) -> CounterfactualMetric:
        if not set(self.assumption_ids).issubset(set(self.scenario_ref.assumption_ids)):
            raise ValueError("counterfactual metric references assumptions outside ScenarioRef")
        for field_name in ("counterfactual", "delta"):
            quantity = getattr(self, field_name)
            if quantity.time is None or quantity.time.scenario_id != self.scenario_ref.id:
                raise ValueError(
                    f"{field_name} quantity must carry time.scenario_id={self.scenario_ref.id}"
                )
        return self


class ScenarioCapability(BaseModel):
    """Support declaration for one counterfactual runtime surface or metric."""

    model_config = ConfigDict(extra="forbid")

    surface: ScenarioSurfaceSupport
    supported: bool
    reason_code: str | None = None
    metric_id: str | None = None
    supported_modes: list[CounterfactualMode] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ScenarioCreateRequest(BaseModel):
    """Request body for saving a scenario draft under a baseline run."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    policy_question: str = Field(min_length=1)
    author: str = Field(default="operator", min_length=1)
    interventions: list[ScenarioIntervention] = Field(min_length=1)
    assumptions: list[ScenarioAssumption] = Field(min_length=1)
    constraints: list[ScenarioConstraint] = Field(default_factory=list)
    affected_population: str | None = None
    model_family: str = Field(default="operator-specified", min_length=1)
    model_version: str | None = None
    known_limitations: list[str] = Field(default_factory=list)
    regime_shift_forecast_bundle_ref: str | None = None


class ScenarioListResponse(BaseModel):
    """Response envelope for scenarios available on a run."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    scenarios: list[ScenarioManifest] = Field(default_factory=list)


class ScenarioManifestResponse(BaseModel):
    """Response envelope for one scenario manifest."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    scenario: ScenarioManifest


class ScenarioCapabilitiesResponse(BaseModel):
    """Response envelope for scenario support and unsupported surfaces."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str | None = None
    scenario_id: str | None = None
    temporal_scope: TemporalScope | None = None
    capabilities: list[ScenarioCapability] = Field(default_factory=list)


class CounterfactualMetricsResponse(BaseModel):
    """Response envelope for normalized actual + scenario metrics."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    scenario: ScenarioManifest
    metrics: dict[str, CounterfactualMetric] = Field(default_factory=dict)


class BureaucraticTemplateRef(BaseModel):
    """Versioned jurisdictional template identity used by bureaucratic renderers."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    genre: BureaucraticGenre
    jurisdiction: str = Field(default="ua", min_length=1)
    locale: str = Field(default="uk-UA", min_length=1)
    legal_review_status: Literal["pending_external_review", "approved", "rejected"] = (
        "pending_external_review"
    )


class BureaucraticAuthorship(BaseModel):
    """Authorship, agent and review attribution for one document block."""

    model_config = ConfigDict(extra="forbid")

    author: str = "PolicyOS"
    author_role: str = "system"
    agent_version: str | None = None
    timestamp: datetime | None = None
    reviewed_by_human: bool = False


class BureaucraticBlock(BaseModel):
    """Canonical document AST block independent of HTML/PDF/DOCX renderers."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: BureaucraticBlockKind
    title: str | None = None
    text: str | None = None
    level: int = Field(default=1, ge=1, le=6)
    number: str | None = None
    items: list[str] = Field(default_factory=list)
    quantity: QuantityValue | None = None
    epistemic_origin: BureaucraticEpistemicKind
    authorship: BureaucraticAuthorship = Field(default_factory=BureaucraticAuthorship)
    provenance: list[LineageCompactSummaryItem] = Field(default_factory=list)
    raw_source_refs: list[str] = Field(default_factory=list)
    children: list[BureaucraticBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BureaucraticEpistemicSummary(BaseModel):
    """Document-level block-origin proportions shown in the epistemic legend."""

    model_config = ConfigDict(extra="forbid")

    evidence_filled: float = Field(default=0.0, ge=0.0, le=1.0)
    model_generated: float = Field(default=0.0, ge=0.0, le=1.0)
    operator_filled: float = Field(default=0.0, ge=0.0, le=1.0)
    imported: float = Field(default=0.0, ge=0.0, le=1.0)


class BureaucraticDocument(BaseModel):
    """Machine-checkable bureaucratic document AST rendered from a decision packet."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    packet_id: str = Field(min_length=1)
    genre: BureaucraticGenre
    jurisdiction: str = Field(default="ua", min_length=1)
    template: BureaucraticTemplateRef
    status: BureaucraticDocumentStatus = "draft"
    title: str
    language: str = "uk"
    watermark: str
    render_timestamp: datetime = Field(default_factory=_utc_now)
    packet_hash: str
    temporal_scope: TemporalScope | None = None
    trust_view: bool = False
    blocks: list[BureaucraticBlock] = Field(default_factory=list)
    annexes: list[BureaucraticBlock] = Field(default_factory=list)
    epistemic_summary: BureaucraticEpistemicSummary = Field(
        default_factory=BureaucraticEpistemicSummary
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class BureaucraticRenderRequest(BaseModel):
    """Request body for rendering one packet into a jurisdictional document AST."""

    model_config = ConfigDict(extra="forbid")

    genre: BureaucraticGenre
    jurisdiction: str = Field(default="ua", min_length=1)
    template_version: str | None = None
    temporal_scope: TemporalScope | None = None
    trust_view: bool = False


class BureaucraticRenderResponse(BaseModel):
    """Response envelope for bureaucratic document AST rendering."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    document: BureaucraticDocument


class BureaucraticExportResponse(BaseModel):
    """Deterministic export packet for HTML/PDF/DOCX generation."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    document_id: str
    packet_id: str
    format: BureaucraticExportFormat
    content_type: str
    filename: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class RunOperatorProjectionStateLabel(BaseModel):
    """Projection lifecycle label with explicit authority semantics."""

    model_config = ConfigDict(extra="forbid")

    state: OperatorProjectionState
    label: str
    authority: OperatorProjectionAuthority


class RunOperatorDiagnostic(BaseModel):
    """Typed operator root-cause projection attached to run details."""

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
    projection_labels: list[RunOperatorProjectionStateLabel] = Field(default_factory=list)


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
    operator_diagnostic: RunOperatorDiagnostic | None = None
    policy_design_case_projection: dict[str, Any] | None = None


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
    fabric_retrieval_trace_ref: ArtifactRef | None = None
    data_snapshot_ref: ArtifactRef | None = None
    input_bindings_ref: ArtifactRef | None = None
    materialization_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    production_data_evidence_context: dict[str, Any] = Field(default_factory=dict)
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
    performance_summary: dict[str, Any] | None = None
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


class DecisionPacketOutlineEntry(BaseModel):
    """Typed outline entry surfaced for decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str
    section_type: str | None = None


class DecisionPacketEffectSize(BaseModel):
    """Structured uncertainty payload used by typed decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    point: float | None = None
    ci_80: tuple[float, float] | None = None
    ci_95: tuple[float, float] | None = None
    quantiles: dict[str, float] | None = None
    identifiability: Literal["identified", "estimated", "assumed"] | None = None
    disputed: bool | None = None
    method: str | None = None


class DecisionPacketMetricSignificance(BaseModel):
    """Typed metric-significance entry embedded in decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    baseline_model_id: str | None = None
    candidate_model_id: str | None = None
    metric_direction: str | None = None
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None
    test_id: str | None = None
    test_label: str | None = None
    p_value: float | None = None
    p_adj: float | None = None
    alpha: float | None = None
    significant: bool | None = None
    effect_size: DecisionPacketEffectSize | None = None
    assumption_warnings: list[str] = Field(default_factory=list)
    calibration_warnings: list[str] = Field(default_factory=list)


class DecisionPacketMetricComparisonRow(BaseModel):
    """Typed metric-comparison row embedded in decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    metric_direction: str | None = None
    baseline_model_id: str | None = None
    candidate_model_id: str | None = None
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None
    family_id: str | None = None
    family_scope: str | None = None
    sample_size_effective: int | None = None
    resampling_method: str | None = None
    test_id: str | None = None
    test_label: str | None = None
    statistic: float | None = None
    effect_size: DecisionPacketEffectSize | None = None
    p_value: float | None = None
    p_adj: float | None = None
    alpha: float | None = None
    significant: bool | None = None
    assumption_warnings: list[str] = Field(default_factory=list)
    calibration_warnings: list[str] = Field(default_factory=list)


class DecisionPacketAuthoredBlock(BaseModel):
    """Typed authored-text block embedded in decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    content: str
    author: Literal["citation", "human", "drafter", "formalizer", "critic"] | None = None
    author_agent_version: str | None = None
    sources: list[dict[str, str]] = Field(default_factory=list)
    timestamp: str | None = None
    confidence: float | None = None
    reviewed_by_human: bool | None = None


class DecisionPacketPreview(BaseModel):
    """Typed additive sidecar for decision-packet artifact previews."""

    model_config = ConfigDict(extra="allow")

    document_outline: list[DecisionPacketOutlineEntry] = Field(default_factory=list)
    metric_significance_by_metric: dict[str, DecisionPacketMetricSignificance] = Field(
        default_factory=dict
    )
    metric_validation_comparison_rows: list[DecisionPacketMetricComparisonRow] = Field(
        default_factory=list
    )
    blocks: list[DecisionPacketAuthoredBlock] = Field(default_factory=list)
    narrative_blocks: list[DecisionPacketAuthoredBlock] = Field(default_factory=list)
    evidence_summary_blocks: list[DecisionPacketAuthoredBlock] = Field(default_factory=list)


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
    decision_packet_preview: DecisionPacketPreview | None = None


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


class ArtifactBatchRequest(BaseModel):
    """Batch artifact lookup request used to avoid client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    artifact_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)


class RunsBatchRequest(BaseModel):
    """Batch run lookup request used to avoid client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    run_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)


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


class RunEquilibriaView(BaseModel):
    """Runtime view of a Foundry equilibrium multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    report_ref: ArtifactRef | None = None
    report: EquilibriumMultiplicityReport | None = None
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
    temporal_scope: TemporalScope | None = None
    run: RunDetails


class RunTimelineResponse(BaseModel):
    """Response envelope returned by the run timeline endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
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
    temporal_scope: TemporalScope | None = None
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


class ArtifactBatchResponse(BaseModel):
    """Response envelope returned by the artifact batch endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifacts: list[ArtifactManifestView] = Field(default_factory=list)


class MobilityEstimateRequest(BaseModel):
    """Request payload for runtime mobility estimation endpoints."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal[
        "complete_case",
        "attrition_adjusted",
        "sequential_attrition_adjusted",
        "refreshment_anchored",
    ] = "attrition_adjusted"
    n_classes: int = Field(default=5, ge=2)
    origin_classes: list[int] = Field(default_factory=list)
    destination_classes: list[int | None] = Field(default_factory=list)
    retention_indicators: list[int] | None = None
    retention_indicators_by_wave: list[list[int]] | None = None
    attrition_features: list[list[float]] | None = None
    attrition_features_by_wave: list[list[list[float]]] | None = None
    sample_weights: list[float] | None = None
    retention_probabilities: list[float] | None = None
    retention_probabilities_by_wave: list[list[float]] | None = None
    destination_marginals: list[float] | None = None
    refreshment_destination_classes: list[int] | None = None
    refreshment_weights: list[float] | None = None
    feature_names: list[str] = Field(default_factory=list)
    estimator: Literal["ipcw", "aipw"] = "aipw"
    positivity_floor: float = Field(default=0.05, ge=0.0, le=0.49)
    compute_bounds: bool = True
    monotone: bool = True
    panel_length: int | None = Field(default=None, ge=2)
    waves_used: list[int] = Field(default_factory=list)
    persist_artifact: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MobilityBoundsRequest(BaseModel):
    """Request payload for runtime mobility bounds endpoints."""

    model_config = ConfigDict(extra="forbid")

    observed_joint_matrix: list[list[float]]
    row_marginals: list[float]
    column_marginals: list[float] | None = None
    headline_metric: str = "upward_rate"
    persist_artifact: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MobilityEstimateResponse(BaseModel):
    """Response envelope returned after estimating a mobility report."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    report: dict[str, Any]
    mobility_report_ref: ArtifactRef | None = None
    bounds_bundle_ref: ArtifactRef | None = None


class MobilityBoundsResponse(BaseModel):
    """Response envelope returned for direct or report-linked mobility bounds."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    bounds: dict[str, Any]
    bounds_bundle_ref: ArtifactRef | None = None
    mobility_report_ref: ArtifactRef | None = None
    cell_bounds: dict[str, list[float]] = Field(default_factory=dict)
    summary_bounds: dict[str, list[float]] = Field(default_factory=dict)


class MobilityReportResponse(BaseModel):
    """Response envelope returned when loading one persisted mobility report."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    report: dict[str, Any]
    mobility_report_ref: ArtifactRef


class MobilityDiagnosticsResponse(BaseModel):
    """Response envelope returned when loading mobility diagnostics only."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    diagnostics: dict[str, Any]
    mobility_report_ref: ArtifactRef


class RunsBatchResponse(BaseModel):
    """Response envelope returned by the run batch endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    runs: list[RunDetails] = Field(default_factory=list)


class RunFeedbackResponse(BaseModel):
    """Response envelope returned by the run feedback endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    feedback: RunFeedbackView


class RunEquilibriaResponse(BaseModel):
    """Response envelope returned by the run equilibria endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    equilibria: RunEquilibriaView


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
    "AuthMeResponse",
    "BureaucraticAuthorship",
    "BureaucraticBlock",
    "BureaucraticBlockKind",
    "BureaucraticDocument",
    "BureaucraticDocumentStatus",
    "BureaucraticEpistemicKind",
    "BureaucraticEpistemicSummary",
    "BureaucraticExportFormat",
    "BureaucraticExportResponse",
    "BureaucraticGenre",
    "BureaucraticRenderRequest",
    "BureaucraticRenderResponse",
    "BureaucraticTemplateRef",
    "ComparabilityReport",
    "ComparabilityStatus",
    "CompareCandidate",
    "CompareCandidatesResponse",
    "CompareResponseStatus",
    "CompareRunResponse",
    "ComparisonFrame",
    "CounterfactualMetric",
    "CounterfactualMetricsResponse",
    "CounterfactualMode",
    "CursorPage",
    "DecisionCompareReport",
    "DecisionMonitoringContract",
    "DecisionMonitoringReport",
    "DecisionPacketAuthoredBlock",
    "DecisionPacketEffectSize",
    "DecisionPacketMetricComparisonRow",
    "DecisionPacketMetricSignificance",
    "DecisionPacketOutlineEntry",
    "DecisionPacketPreview",
    "DecisionReissuePlan",
    "DeltaDistribution",
    "DeltaDominance",
    "DeltaQuantity",
    "DeltaSignificance",
    "DisputeStatus",
    "EvaluatorReportView",
    "EvaluatorScoresView",
    "FabricImpactAnalysisRequest",
    "FabricImpactAnalysisResponse",
    "FabricImpactRecord",
    "FabricImpactSubjectKind",
    "FabricQualityBatchResponse",
    "FabricQualityTrustBatchRequest",
    "FabricReplayRunResponse",
    "FabricSourceScorecardsResponse",
    "FabricTrustBatchResponse",
    "FeedbackActionResponse",
    "GovernanceDebugResponse",
    "GovernanceDebugView",
    "IterationLifecycleView",
    "LineageBatchRequest",
    "LineageBatchResponse",
    "LineageCompactSummaryItem",
    "LineageDelta",
    "LineageExportLinks",
    "LineageExportResponse",
    "LineageFreshness",
    "LineageGraphEdge",
    "LineageGraphNode",
    "LineageGraphView",
    "LineageRef",
    "LineageResponse",
    "LineageSummaryKind",
    "MobilityBoundsRequest",
    "MobilityBoundsResponse",
    "MobilityDiagnosticsResponse",
    "MobilityEstimateRequest",
    "MobilityEstimateResponse",
    "MobilityReportResponse",
    "NodeDebugResponse",
    "NodeDebugView",
    "NodeStatus",
    "PreflightDiagnosticView",
    "PreflightReportView",
    "PreviewMode",
    "QuantityClass",
    "QuantityCoverageEntry",
    "QuantityCoverageSummary",
    "QuantityUncertainty",
    "QuantityValue",
    "ReproducibilityView",
    "RetrievalPhaseTelemetry",
    "RetrievalTelemetryView",
    "RunCompareResponse",
    "RunCompareView",
    "RunDetails",
    "RunDetailsResponse",
    "RunEquilibriaResponse",
    "RunEquilibriaView",
    "RunErrorView",
    "RunErrorsResponse",
    "RunEvidenceContextResponse",
    "RunEvidenceContextView",
    "RunEvidenceNeedView",
    "RunEvidencePlanView",
    "RunEvidencePromotionView",
    "RunFeedbackResponse",
    "RunFeedbackView",
    "RunLineageResponse",
    "RunNodeRecord",
    "RunNodesResponse",
    "RunOperatorDiagnostic",
    "RunOperatorProjectionStateLabel",
    "RunQuantitiesResponse",
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
    "ScenarioAssumption",
    "ScenarioAssumptionStatus",
    "ScenarioCapabilitiesResponse",
    "ScenarioCapability",
    "ScenarioConstraint",
    "ScenarioConstraintSeverity",
    "ScenarioCreateRequest",
    "ScenarioIntervention",
    "ScenarioInterventionOperator",
    "ScenarioLifecycleStatus",
    "ScenarioListResponse",
    "ScenarioManifest",
    "ScenarioManifestResponse",
    "ScenarioRef",
    "ScenarioStatus",
    "ScenarioSurfaceSupport",
    "SourceKind",
    "TemporalCapabilitiesResponse",
    "TemporalCapabilitiesView",
    "TemporalEventKind",
    "TemporalEventPoint",
    "TemporalGapRange",
    "TemporalIndexEvidence",
    "TemporalRange",
    "TemporalRef",
    "TemporalScope",
    "TemporalSurfaceCapability",
    "TemporalSurfaceSupport",
    "TrustMetadataRef",
    "UnitRef",
    "VerificationMetadata",
    "VerificationStatus",
]
