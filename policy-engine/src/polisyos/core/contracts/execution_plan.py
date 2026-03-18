"""Execution-plan contracts for unified LLM policy cycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import fingerprint
from polisyos.core.canon.canon_json import CanonSpec

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
    kind: Literal["scientist.execution_plan"] = "scientist.execution_plan"
    media_type: Literal["application/json"] = "application/json"


class MethodCatalogSnapshotRef(ArtifactRef):
    kind: Literal["foundry.method_catalog_snapshot"] = "foundry.method_catalog_snapshot"
    media_type: Literal["application/json"] = "application/json"


class PreflightReportRef(ArtifactRef):
    kind: Literal["scientist.preflight_report"] = "scientist.preflight_report"
    media_type: Literal["application/json"] = "application/json"


class EvaluatorReportRef(ArtifactRef):
    kind: Literal["scientist.evaluator_report"] = "scientist.evaluator_report"
    media_type: Literal["application/json"] = "application/json"


class IterationStateRef(ArtifactRef):
    kind: Literal["scientist.iteration_state"] = "scientist.iteration_state"
    media_type: Literal["application/json"] = "application/json"


class ReproducibilityManifestRef(ArtifactRef):
    kind: Literal["scientist.reproducibility_manifest"] = "scientist.reproducibility_manifest"
    media_type: Literal["application/json"] = "application/json"


class PlanDataNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str = Field(..., min_length=1, max_length=256)
    geography: str | None = Field(default=None, max_length=128)
    time_start: str | None = Field(default=None, max_length=64)
    time_end: str | None = Field(default=None, max_length=64)
    granularity: str = Field(default="annual", max_length=64)
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    purpose: str = Field(default="policy_drafting", min_length=1, max_length=256)


class MethodDagNode(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    src: str = Field(..., min_length=1, max_length=128)
    dst: str = Field(..., min_length=1, max_length=128)
    relation: str = Field(default="depends_on", max_length=64)


class BudgetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_iterations: int = Field(default=3, ge=1, le=100)
    run_budget_usd: float | None = Field(default=None, ge=0.0)
    per_model_budget_usd: float | None = Field(default=None, ge=0.0)
    max_wall_time_ms: int | None = Field(default=None, ge=1)
    max_tokens_total: int | None = Field(default=None, ge=1)


class StopCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_delta_improvement: float = Field(default=0.0, ge=0.0, le=1.0)
    max_no_delta_iterations: int = Field(default=1, ge=1, le=100)
    block_on_guardrail_violation: bool = True
    block_on_preflight_error: bool = True


class GovernanceConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_id: str = Field(..., min_length=1, max_length=128)
    kind: str = Field(..., min_length=1, max_length=64)
    severity: DiagnosticSeverity = "warning"
    value: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExpectedOutputSpec(BaseModel):
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: list[str] = Field(default_factory=list)

    def stable_hash(self) -> str:
        return fingerprint(
            self.model_dump(mode="json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )


class MethodCatalogEntry(BaseModel):
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


class MethodCatalogSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    snapshot_id: str = Field(..., min_length=1, max_length=128)
    run_id: str | None = Field(default=None, max_length=128)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    causal_capability_hash: str | None = None
    causal_runtime_posture: dict[str, Any] = Field(default_factory=dict)
    entries: list[MethodCatalogEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def stable_hash(self) -> str:
        return fingerprint(
            self.model_dump(mode="json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )


class PreflightDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=128)
    severity: DiagnosticSeverity = "error"
    message: str = Field(..., min_length=1, max_length=2000)
    path: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class PreflightReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    plan_ref: ExecutionPlanRef | None = None
    catalog_snapshot_ref: MethodCatalogSnapshotRef | None = None
    ready_to_run: bool = False
    diagnostics: list[PreflightDiagnostic] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvaluatorScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    constraints_score: float = Field(default=0.0, ge=0.0, le=1.0)
    data_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    budget_score: float = Field(default=0.0, ge=0.0, le=1.0)
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)


class EvaluatorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    verdict: EvaluatorVerdict
    scores: EvaluatorScores = Field(default_factory=EvaluatorScores)
    reasons: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    diagnostics: list[PreflightDiagnostic] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IterationState(BaseModel):
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
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: list[str] = Field(default_factory=list)


class ReproducibilityManifest(BaseModel):
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "DiagnosticSeverity",
    "EvaluatorVerdict",
    "IterationLifecycleState",
    "StopReason",
    "ExecutionPlanRef",
    "MethodCatalogSnapshotRef",
    "PreflightReportRef",
    "EvaluatorReportRef",
    "IterationStateRef",
    "ReproducibilityManifestRef",
    "PlanDataNeed",
    "MethodDagNode",
    "MethodDagEdge",
    "BudgetSpec",
    "StopCriteria",
    "GovernanceConstraint",
    "ExpectedOutputSpec",
    "ExecutionPlan",
    "MethodCatalogEntry",
    "MethodCatalogSnapshot",
    "PreflightDiagnostic",
    "PreflightReport",
    "EvaluatorScores",
    "EvaluatorReport",
    "IterationState",
    "ReproducibilityManifest",
]
