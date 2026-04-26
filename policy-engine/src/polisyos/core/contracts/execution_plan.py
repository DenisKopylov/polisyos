"""Execution-plan contracts for unified LLM policy cycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.common.timestamps import ensure_utc, utc_now
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import fingerprint
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.core.observability.truthfulness import (
    TruthfulnessTier,
    parse_truthfulness_scope,
    parse_truthfulness_status,
    parse_truthfulness_tier,
    reconcile_truthfulness_tiers,
)

DiagnosticSeverity = Literal["info", "warning", "error", "blocker"]
EvaluatorVerdict = Literal[
    "APPROVE",
    "REPLAN_DATA",
    "REPLAN_METHOD",
    "REPLAN_PARAMS",
    "STOP_BUDGET",
]
IterationLifecycleState = Literal[
    "plan_created",
    "preflight_running",
    "preflight_failed",
    "ready_to_run",
    "executing",
    "evaluating",
    "replanning",
    "approved",
    "stopped_budget",
    "stopped_no_delta",
    "stopped_guardrail",
]
StopReason = Literal[
    "approved",
    "budget_exhausted",
    "no_delta",
    "guardrail_violation",
]


class ExecutionPlanRef(ArtifactRef):
    """Artifact reference for the execution plan driving a Scientist iteration."""

    kind: str = "scientist.execution_plan"
    media_type: str = "application/json"


class MethodCatalogSnapshotRef(ArtifactRef):
    """Artifact reference for the method-catalog snapshot available during planning."""

    kind: str = "foundry.method_catalog_snapshot"
    media_type: str = "application/json"


class PreflightReportRef(ArtifactRef):
    """Artifact reference for readiness diagnostics generated before execution starts."""

    kind: str = "scientist.preflight_report"
    media_type: str = "application/json"


class EvaluatorReportRef(ArtifactRef):
    """Artifact reference for the evaluator verdict emitted after an iteration runs."""

    kind: str = "scientist.evaluator_report"
    media_type: str = "application/json"


class IterationStateRef(ArtifactRef):
    """Artifact reference for persisted lifecycle state of one planning iteration."""

    kind: str = "scientist.iteration_state"
    media_type: str = "application/json"


class ReproducibilityManifestRef(ArtifactRef):
    """Artifact reference for the hashes and seeds required to replay an iteration."""

    kind: str = "scientist.reproducibility_manifest"
    media_type: str = "application/json"


class PlanDataNeed(BaseModel):
    """Plan data need public type."""

    model_config = ConfigDict(extra="forbid")

    metric: str = Field(..., min_length=1, max_length=256)
    geography: str | None = Field(default=None, max_length=128)
    time_start: str | None = Field(default=None, max_length=64)
    time_end: str | None = Field(default=None, max_length=64)
    granularity: str = Field(default="annual", max_length=64)
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    purpose: str = Field(default="policy_drafting", min_length=1, max_length=256)


class MethodDagNode(BaseModel):
    """One planned method invocation in the execution DAG, including dependencies and slots."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., min_length=1, max_length=128)
    method_fqn: str = Field(..., min_length=1, max_length=256)
    method_version: str | None = Field(default=None, max_length=32)
    backend: str | None = Field(default=None, max_length=32)
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    reads_slots: list[str] = Field(default_factory=list)
    writes_slots: list[str] = Field(default_factory=list)
    incompatibilities: list[str] = Field(default_factory=list)
    deprecations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MethodDagEdge(BaseModel):
    """Method dag edge public type."""

    model_config = ConfigDict(extra="forbid")

    src: str = Field(..., min_length=1, max_length=128)
    dst: str = Field(..., min_length=1, max_length=128)
    relation: str = Field(default="depends_on", max_length=64)


class BudgetSpec(BaseModel):
    """Budget ceilings that bound iterations, spend, wall time, and token consumption."""

    model_config = ConfigDict(extra="forbid")

    max_iterations: int = Field(default=3, ge=1, le=100)
    run_budget_usd: float | None = Field(default=None, ge=0.0)
    per_model_budget_usd: float | None = Field(default=None, ge=0.0)
    max_wall_time_ms: int | None = Field(default=None, ge=1)
    max_tokens_total: int | None = Field(default=None, ge=1)


class StopCriteria(BaseModel):
    """Stop criteria public type."""

    model_config = ConfigDict(extra="forbid")

    min_delta_improvement: float = Field(default=0.0, ge=0.0, le=1.0)
    max_no_delta_iterations: int = Field(default=1, ge=1, le=100)
    block_on_guardrail_violation: bool = True
    block_on_preflight_error: bool = True


class GovernanceConstraint(BaseModel):
    """Governance constraint public type."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str = Field(..., min_length=1, max_length=128)
    kind: str = Field(..., min_length=1, max_length=64)
    severity: DiagnosticSeverity = "warning"
    value: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExpectedOutputSpec(BaseModel):
    """Target metric and tolerance that the planned run is expected to satisfy."""

    model_config = ConfigDict(extra="forbid")

    output_id: str = Field(..., min_length=1, max_length=128)
    metric_id: str = Field(..., min_length=1, max_length=256)
    comparator: str = Field(default=">=", min_length=1, max_length=16)
    target_value: str = Field(default="", max_length=128)
    tolerance: float | None = Field(default=None, ge=0.0)
    notes: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """First-class planning artifact for unified LLM execution loops."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    plan_id: str = Field(..., min_length=1, max_length=128)
    run_id: str | None = Field(default=None, max_length=128)
    iteration: int = Field(default=1, ge=1, le=1000)
    data_needs: list[PlanDataNeed] = Field(default_factory=list)
    method_dag: list[MethodDagNode] = Field(default_factory=list)
    method_edges: list[MethodDagEdge] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    budgets: BudgetSpec = Field(default_factory=BudgetSpec)
    stop_criteria: StopCriteria = Field(default_factory=StopCriteria)
    governance_constraints: list[GovernanceConstraint] = Field(default_factory=list)
    expected_outputs: list[ExpectedOutputSpec] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    notes: list[str] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    def stable_hash(self) -> str:
        return fingerprint(
            self.model_dump(mode="json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )


class MethodCatalogEntry(BaseModel):
    """Semantically rich description of one runnable method candidate exposed to the planner."""

    model_config = ConfigDict(extra="forbid")

    fqn: str = Field(..., min_length=1)
    namespace: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    backend: str = Field(..., min_length=1)
    execution_backend: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1)
    family: str = Field(..., min_length=1)
    variant: str = Field(..., min_length=1)
    fidelity_tier: str = Field(..., min_length=1)
    data_modalities: list[str] = Field(default_factory=list)
    runtime_stack: list[str] = Field(default_factory=list)
    determinism_tier: str | None = None
    required_deps: list[str] = Field(default_factory=list)
    optional_deps: list[str] = Field(default_factory=list)
    fallback_policy: str = Field(default="none")
    side_effect_profile: str = Field(default="none")
    runnable: bool = True
    disabled_reasons: list[str] = Field(default_factory=list)
    dependency_posture: dict[str, Any] = Field(default_factory=dict)
    capability_matrix: dict[str, Any] = Field(default_factory=dict)
    input_slots: list[dict[str, Any]] = Field(default_factory=list)
    output_slots: list[dict[str, Any]] = Field(default_factory=list)
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    incompatibilities: list[str] = Field(default_factory=list)
    deprecations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    causal_capability_requirements: list[str] = Field(default_factory=list)
    causal_available: bool | None = None
    causal_disabled_reasons: list[str] = Field(default_factory=list)
    truthfulness_tier: str = Field(default=TruthfulnessTier.UNVERIFIED.value)
    implementation_depth_tier: str = Field(default="production_method")
    implementation_depth_notes: str = Field(default="")
    declared_truthfulness_tier: str | None = None
    runtime_truthfulness_tier: str | None = None
    effective_truthfulness_tier: str | None = None
    truthfulness_scope: str | None = None
    truthfulness_status: str | None = None
    truthfulness_evidence_ref: str | None = None
    truthfulness_notes: str = Field(default="")
    effect_semantics: dict[str, Any] = Field(default_factory=dict)
    shape_semantics: dict[str, Any] = Field(default_factory=dict)
    dependency_semantics: dict[str, Any] = Field(default_factory=dict)
    # Rich semantic metadata for LLM planning
    description: str = Field(default="")
    citations: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    when_to_use: str = Field(default="")
    when_not_to_use: str = Field(default="")
    prerequisites: list[str] = Field(default_factory=list)
    diagnostic_checks: list[str] = Field(default_factory=list)
    typical_min_obs: int | None = Field(default=None)
    output_interpretation: str = Field(default="")
    simulator_regime_schema: dict[str, Any] = Field(default_factory=dict)
    summary_schema_ref: str | None = Field(default=None)
    identifiable_target: dict[str, Any] = Field(default_factory=dict)
    coverage_contract: dict[str, Any] = Field(default_factory=dict)
    diagnostic_contract: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _synchronize_truthfulness_fields(self) -> MethodCatalogEntry:
        legacy_depth_tiers = {
            "heuristic_baseline",
            "structural_scoring",
            "frontier_trainable",
            "production_method",
        }
        alias_value = str(self.truthfulness_tier or "").strip().lower()
        implementation_depth = str(self.implementation_depth_tier or "").strip().lower()
        if alias_value in legacy_depth_tiers:
            implementation_depth = alias_value
        if not implementation_depth:
            implementation_depth = "production_method"

        declared = parse_truthfulness_tier(self.declared_truthfulness_tier)
        runtime = parse_truthfulness_tier(self.runtime_truthfulness_tier)
        effective = parse_truthfulness_tier(self.effective_truthfulness_tier)
        if effective is None:
            alias_tier = parse_truthfulness_tier(alias_value)
            if alias_tier is not None and (
                alias_tier is not TruthfulnessTier.UNVERIFIED
                or (declared is None and runtime is None)
            ):
                effective = alias_tier
            else:
                effective, _ = reconcile_truthfulness_tiers(declared, runtime)

        status = parse_truthfulness_status(self.truthfulness_status)
        if status is None:
            _, status = reconcile_truthfulness_tiers(declared, runtime)
        scope = parse_truthfulness_scope(self.truthfulness_scope)

        self.truthfulness_tier = effective.value
        self.effective_truthfulness_tier = effective.value
        self.truthfulness_status = status.value
        self.truthfulness_scope = None if scope is None else scope.value
        self.implementation_depth_tier = implementation_depth
        return self


class MethodCatalogSnapshot(BaseModel):
    """Point-in-time inventory of the methods and capabilities available to a run planner."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    snapshot_id: str = Field(..., min_length=1, max_length=128)
    run_id: str | None = Field(default=None, max_length=128)
    generated_at: datetime = Field(default_factory=utc_now)
    causal_capability_hash: str | None = None
    causal_runtime_posture: dict[str, Any] = Field(default_factory=dict)
    entries: list[MethodCatalogEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def _ensure_generated_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    def stable_hash(self) -> str:
        return fingerprint(
            self.model_dump(mode="json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )


class PreflightDiagnostic(BaseModel):
    """Preflight diagnostic public type."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=128)
    severity: DiagnosticSeverity = "error"
    message: str = Field(..., min_length=1, max_length=2000)
    path: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class PreflightReport(BaseModel):
    """Readiness diagnostics indicating whether a plan can execute or must be replanned."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    plan_ref: ExecutionPlanRef | None = None
    catalog_snapshot_ref: MethodCatalogSnapshotRef | None = None
    ready_to_run: bool = False
    diagnostics: list[PreflightDiagnostic] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvaluatorScores(BaseModel):
    """Evaluator scores public type."""

    model_config = ConfigDict(extra="forbid")

    kpi_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    constraints_score: float = Field(default=0.0, ge=0.0, le=1.0)
    data_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    budget_score: float = Field(default=0.0, ge=0.0, le=1.0)
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)


class EvaluatorReport(BaseModel):
    """Evaluator verdict plus scores, reasons, and replanning hints for an iteration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    verdict: EvaluatorVerdict
    scores: EvaluatorScores = Field(default_factory=EvaluatorScores)
    reasons: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    diagnostics: list[PreflightDiagnostic] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IterationState(BaseModel):
    """Persisted lifecycle state for one execution-plan iteration within a run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    iteration: int = Field(default=1, ge=1)
    lifecycle_state: IterationLifecycleState = "plan_created"
    stop_reason: StopReason | None = None
    last_verdict: EvaluatorVerdict | None = None
    plan_ref: ExecutionPlanRef | None = None
    preflight_report_ref: PreflightReportRef | None = None
    evaluator_report_ref: EvaluatorReportRef | None = None
    started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    notes: list[str] = Field(default_factory=list)

    @field_validator("started_at", "updated_at")
    @classmethod
    def _ensure_iteration_timestamps_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ReproducibilityManifest(BaseModel):
    """Hashes, refs, and seed material required to replay one iteration deterministically."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    iteration: int = Field(default=1, ge=1)
    seed: int = Field(default=0, ge=0)
    plan_hash: str = Field(default="", max_length=256)
    registry_bundle_ref: str | None = None
    registry_hash: str | None = None
    method_catalog_snapshot_ref: str | None = None
    method_catalog_hash: str | None = None
    data_snapshot_ref: str | None = None
    data_snapshot_hash: str | None = None
    input_bindings_ref: str | None = None
    input_bindings_hash: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    notes: list[str] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def _ensure_reproducibility_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


__all__ = [
    "BudgetSpec",
    "DiagnosticSeverity",
    "EvaluatorReport",
    "EvaluatorReportRef",
    "EvaluatorScores",
    "EvaluatorVerdict",
    "ExecutionPlan",
    "ExecutionPlanRef",
    "ExpectedOutputSpec",
    "GovernanceConstraint",
    "IterationLifecycleState",
    "IterationState",
    "IterationStateRef",
    "MethodCatalogEntry",
    "MethodCatalogSnapshot",
    "MethodCatalogSnapshotRef",
    "MethodDagEdge",
    "MethodDagNode",
    "PlanDataNeed",
    "PreflightDiagnostic",
    "PreflightReport",
    "PreflightReportRef",
    "ReproducibilityManifest",
    "ReproducibilityManifestRef",
    "StopCriteria",
    "StopReason",
]
