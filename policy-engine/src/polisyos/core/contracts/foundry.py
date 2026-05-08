"""Stable Foundry contracts for compile-time graphs, execution plans, and simulation outputs."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.registry.refs import WelfareBundleRef

from ..artifacts.environment import EnvironmentManifestRef as EnvironmentManifestRef
from ..artifacts.manifest import ArtifactRef
from .distributional import DistributionalReportRef
from .scientist import FairnessAuditReportRef, MetricValidationReportRef
from .uncertainty import UncertaintyEnvelopeRef


class ProgramGraphRef(ArtifactRef):
    """Artifact reference for the compiled program graph a Foundry run will execute."""

    kind: str = "foundry.program_graph"
    media_type: str = "application/json"


class LoweredIRRef(ArtifactRef):
    """Artifact reference for the lowered IR produced before execution planning."""

    kind: str = "foundry.lowered_ir"
    media_type: str = "application/json"


class ExecPlanRef(ArtifactRef):
    """Artifact reference for the resolved Foundry execution plan and runtime posture."""

    kind: str = "foundry.exec_plan"
    media_type: str = "application/json"


class StateSnapshotRef(ArtifactRef):
    """Artifact reference for a persisted state snapshot emitted by a simulation."""

    kind: str = "foundry.state_snapshot"
    media_type: str = "application/json"


class FoundryInputBindingsRef(ArtifactRef):
    """Artifact reference for the slot-binding bundle used to seed a Foundry execution."""

    kind: str = "foundry.input_bindings"
    media_type: str = "application/json"


class FoundryInputBindingReportRef(ArtifactRef):
    """Artifact reference for the report describing how external data was bound to slots."""

    kind: str = "foundry.input_binding_report"
    media_type: str = "application/json"


class FeedbackConfigRef(ArtifactRef):
    """Artifact reference for feedback fixed-point configuration."""

    kind: str = "foundry.feedback_config"
    media_type: str = "application/json"


class FeedbackTraceRef(ArtifactRef):
    """Artifact reference for the feedback iteration trace."""

    kind: str = "foundry.feedback_trace"
    media_type: str = "application/json"


class FeedbackJacobianDiagnosticsRef(ArtifactRef):
    """Artifact reference for Jacobian diagnostics around the solved fixed point."""

    kind: str = "foundry.feedback_jacobian_diagnostics"
    media_type: str = "application/json"


class FeedbackConvergenceCertificateRef(ArtifactRef):
    """Artifact reference for the feedback convergence certificate."""

    kind: str = "foundry.feedback_convergence_certificate"
    media_type: str = "application/json"


class FeedbackResultRef(ArtifactRef):
    """Artifact reference for the top-level feedback solve result."""

    kind: str = "foundry.feedback_result"
    media_type: str = "application/json"


class EquilibriumMultiplicityReportRef(ArtifactRef):
    """Artifact reference for a structured fixed-point multiplicity report."""

    kind: str = "foundry.equilibrium_multiplicity_report"
    media_type: str = "application/json"


class IdentifiabilityDiagnosticRef(ArtifactRef):
    """Artifact reference for aggregate-moment identifiability diagnostics."""

    kind: str = "foundry.identifiability_diagnostic"
    media_type: str = "application/json"


class AttractorAnalysisResultRef(ArtifactRef):
    """Artifact reference for a multi-attractor analysis summary."""

    kind: str = "foundry.attractor_analysis_result"
    media_type: str = "application/json"


class BasinMapRef(ArtifactRef):
    """Artifact reference for dense basin membership samples."""

    kind: str = "foundry.basin_map"
    media_type: str = "application/json"


class ContinuationBranchRef(ArtifactRef):
    """Artifact reference for an equilibrium, cycle, or bifurcation continuation branch."""

    kind: str = "foundry.continuation_branch"
    media_type: str = "application/json"


class PeriodicOrbitDiagnosticsRef(ArtifactRef):
    """Artifact reference for periodic-orbit diagnostics such as Floquet multipliers."""

    kind: str = "foundry.periodic_orbit_diagnostics"
    media_type: str = "application/json"


class TreasurySeedRef(ArtifactRef):
    """Artifact reference for deterministic random-stream seeds used during execution."""

    kind: str = "foundry.treasury_seed"
    media_type: str = "application/json"


class ExecConfigRef(ArtifactRef):
    """Artifact reference for the executor configuration applied to a simulation run."""

    kind: str = "foundry.exec_config"
    media_type: str = "application/json"


class MethodArtifactRef(ArtifactRef):
    """Method artifact ref data model."""

    kind: str = "foundry.method_artifact"
    media_type: str = "application/json"


class ChainArtifactRef(ArtifactRef):
    """Chain artifact ref data model."""

    kind: str = "foundry.chain_artifact"
    media_type: str = "application/json"


class ExecutionEvidenceRef(ArtifactRef):
    """Execution evidence ref data model."""

    kind: str = "foundry.execution_evidence"
    media_type: str = "application/json"


class AgentPolicyRef(ArtifactRef):
    """
    Typed reference to an AgentPolicyArtifact in CAS.

    Used in simulation configs to reference trained policies without
    embedding full weights in configuration files.
    """

    kind: str = "foundry.agent_policy"
    media_type: str = "application/octet-stream"

    policy_type: str = Field(description="ActorCritic, MLP, etc.")
    determinism_tier: str = Field(description="strict_cpu, best_effort_gpu, nondeterministic")
    training_steps: int = Field(ge=0, description="Steps when artifact was created")
    env_hash: str = Field(description="16-char environment fingerprint hash")


class StateDeltaRef(ArtifactRef):
    """Artifact reference for the patch set that transforms one state snapshot into the next."""

    kind: str = "foundry.state_delta"
    media_type: str = "application/json"


class MetricsRef(ArtifactRef):
    """Artifact reference for the scalar metrics emitted by a Foundry execution."""

    kind: str = "foundry.metrics"
    media_type: str = "application/json"


class MetricObservationBundleRef(ArtifactRef):
    """Artifact reference for per-example observations required for formal metric validation."""

    kind: str = "foundry.metric_observation_bundle"
    media_type: str = "application/json"


class ConstraintReportRef(ArtifactRef):
    """Constraint report ref data model."""

    kind: str = "foundry.constraint_report"
    media_type: str = "application/json"


class CalibrationReportRef(ArtifactRef):
    """Artifact reference for calibration diagnostics emitted alongside simulation outputs."""

    kind: str = "foundry.calibration_report"
    media_type: str = "application/json"


class ParameterOverrideBundleRef(ArtifactRef):
    """Artifact reference for parameter overrides layered onto a baseline execution config."""

    kind: str = "foundry.parameter_override_bundle"
    media_type: str = "application/json"


class ObservedRangeBundleRef(ArtifactRef):
    """Artifact reference for calibrated numeric envelopes used by decision-sidecar reports."""

    kind: str = "foundry.observed_range_bundle"
    media_type: str = "application/json"


class TraceSliceRef(ArtifactRef):
    """Artifact reference for the structured execution trace slice captured during a run."""

    kind: str = "foundry.trace_slice"
    media_type: str = "application/jsonl"


class SimulationResultRef(ArtifactRef):
    """Artifact reference for the top-level simulation result bundle returned by Foundry."""

    kind: str = "foundry.simulation_result"
    media_type: str = "application/json"


class WelfareBoundReportRef(ArtifactRef):
    """Artifact reference for a mechanism-level welfare-loss certificate."""

    kind: str = "foundry.welfare_bound_report"
    media_type: str = "application/json"


class ProgramNode(BaseModel):
    """One executable node in a program graph, representing a mechanism, op, or method call."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_kind: Literal["mechanism", "op", "method"] = "mechanism"
    mechanism_type: str | None = None
    method_fqn: str | None = None
    method_version: str | None = None
    method_params: dict[str, Any] = Field(default_factory=dict)
    params_ref: ArtifactRef | None = None
    op: ProgramOp | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kind(self) -> ProgramNode:
        if self.node_kind == "mechanism" and not self.mechanism_type:
            raise ValueError("mechanism node requires mechanism_type")
        if self.node_kind == "op" and self.op is None:
            raise ValueError("op node requires op")
        if self.node_kind == "method" and not self.method_fqn:
            raise ValueError("method node requires method_fqn")
        return self


class ProgramOp(BaseModel):
    """Program op public type."""

    model_config = ConfigDict(extra="forbid")

    op_kind: Literal[
        "merge_state",
        "check_constraints",
        "read_view",
        "make_mask",
        "apply_mechanism",
        "apply_method",
    ]
    params: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


ProgramNode.model_rebuild()


class ProgramEdge(BaseModel):
    """Program edge public type."""

    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    relation: str = "depends_on"


class ProgramGraph(BaseModel):
    """Program graph public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("0.2", pattern=r"^\d+\.\d+$")
    ir_ref: ArtifactRef
    lowered_ir_ref: LoweredIRRef | None = None
    nodes: list[ProgramNode] = Field(default_factory=list)
    edges: list[ProgramEdge] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class LoweredMechanism(BaseModel):
    """Lowered mechanism public type."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    mechanism_id: str
    intervention_ids: list[str] = Field(default_factory=list)
    effective_params_ref: ArtifactRef | None = None
    effective_schedule: dict[str, Any] | None = None
    selected_fidelity: str | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    legacy_kind_alias_used: bool = False
    target_selector: dict[str, Any] | None = None
    priority: int | None = None
    notes: list[str] = Field(default_factory=list)


class LoweredConstraint(BaseModel):
    """Lowered constraint public type."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    severity: Literal["hard", "soft"]
    slot_id: str
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    expected: Any
    unit_id: str | None = None
    penalty: Decimal | None = None
    aggregation: str = "scalar"
    quantile_param: float | None = None
    weights_slot_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class CompositeConstraint(BaseModel):
    """Constraint involving multiple slots combined via arithmetic expression."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    expression: str
    slot_refs: list[str]
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    expected: str
    severity: Literal["hard", "soft"] = "hard"
    penalty: Decimal | None = None
    notes: list[str] = Field(default_factory=list)


class LoweredIR(BaseModel):
    """Lowered IR public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("0.2", pattern=r"^\d+\.\d+$")
    ir_ref: ArtifactRef
    mechanisms: list[LoweredMechanism] = Field(default_factory=list)
    constraints: list[LoweredConstraint] = Field(default_factory=list)
    composite_constraints: list[CompositeConstraint] = Field(default_factory=list)
    parameter_specs: list[dict[str, Any]] = Field(default_factory=list)
    time_semantics: dict[str, Any] | None = None
    environment_config: dict[str, Any] | None = None
    policy_fidelity_level: str | None = None
    constraint_mode: str = "hard_soft_v1"
    notes: list[str] = Field(default_factory=list)


class ExecPlan(BaseModel):
    """Execution-order artifact that pairs a program graph with resolved runtime posture."""

    model_config = ConfigDict(extra="forbid")

    program_ref: ProgramGraphRef
    order: list[str] = Field(default_factory=list)
    environment_ref: EnvironmentManifestRef | None = Field(
        default=None,
        description="Reference to captured environment at plan creation time",
    )
    environment_fingerprint: str | None = Field(
        default=None,
        description="Fingerprint of critical environment factors",
    )
    determinism_tier: str | None = Field(
        default=None,
        description="Determinism tier for reproducibility expectations",
    )
    random_seed: int | None = Field(
        default=None,
        description="Random seed associated with determinism tier",
    )
    nan_guard_enabled: bool = Field(
        default=False,
        description="Enable NaN/Inf guard checks during execution",
    )
    policy_fidelity_level: str | None = Field(
        default=None,
        description="Resolved policy-level fidelity from Trinity lowering",
    )
    constraint_mode: str = Field(
        default="hard_soft_v1",
        description="Constraint semantics mode used by executor",
    )
    mode: Literal["dev", "perf", "audit"] = "dev"
    jit: bool = True
    max_steps: int | None = None
    notes: list[str] = Field(default_factory=list)


class FoundryValidationFlags(BaseModel):
    """Foundry validation flags public type."""

    model_config = ConfigDict(extra="forbid")

    strict_schema: bool = True
    strict_link: bool = True
    allow_extra_params: bool = False
    strict_conflict_check: bool = True
    allow_legacy_units: bool = False


class FoundryCompileConfig(BaseModel):
    """Compiler options controlling lowering mode, cost budgets, and determinism hints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    mode: Literal["dev", "perf", "audit"] = "dev"
    jit: bool = True
    max_steps: int | None = None
    nan_guard_enabled: bool = False

    determinism_tier: str | None = None
    random_seed: int | None = None

    cost_budget_max_total_ms: int | None = None
    cost_budget_max_memory_mb: int | None = None
    cost_budget_max_compile_ms: int | None = None
    cost_budget_max_per_mechanism_ms: int | None = None

    estimate_n_agents: int | None = None
    estimate_time_steps: int | None = None


class CompileRequest(BaseModel):
    """Input contract for compiling a policy artifact into Foundry execution artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    input_kind: Literal["auto", "trinity"] = "auto"
    policy_ref: ArtifactRef

    registry_bundle_ref: ArtifactRef | None = None
    compile_config: FoundryCompileConfig = Field(
        default_factory=lambda: FoundryCompileConfig(schema_version="1.0")
    )
    validation_flags: FoundryValidationFlags = Field(default_factory=FoundryValidationFlags)

    notes: list[str] = Field(default_factory=list)


class DerivedArtifact(BaseModel):
    """Derived artifact public type."""

    model_config = ConfigDict(extra="forbid")

    role: str
    ref: ArtifactRef


class CompileResult(BaseModel):
    """Compilation outcome pointing to the compile report and any derived Foundry artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool

    exec_plan_ref: ExecPlanRef | None = None
    compile_report_ref: ArtifactRef

    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FoundryExecConfig(BaseModel):
    """Runtime overrides controlling execution mode, seed handling, and env capture."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    seed: int = 0
    mode: Literal["dev", "perf", "audit"] = "dev"
    max_steps: int | None = None
    deterministic: bool = True
    capture_env: bool = False


class FoundryInputBindingTransform(BaseModel):
    """Foundry input binding transform public type."""

    model_config = ConfigDict(extra="forbid")

    op: Literal[
        "identity",
        "to_bool",
        "to_int",
        "to_decimal",
        "fillna",
        "scale",
        "offset",
        "clip",
        "round",
    ] = "identity"
    params: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FoundryInputBindingRule(BaseModel):
    """Rule mapping one external source path into a Foundry slot through optional transforms."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    source_path: str
    target_slot_id: str
    required: bool = True
    default_value: Any = None
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FoundryInputBindings(BaseModel):
    """Foundry input bindings public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    data_snapshot_ref: ArtifactRef
    registry_bundle_ref: ArtifactRef
    rules: list[FoundryInputBindingRule] = Field(default_factory=list)
    bound_state_snapshot_ref: StateSnapshotRef
    quality_report_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class FeedbackObservationSpec(BaseModel):
    """Scalar observable extracted from post-execution state or metrics."""

    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["state_path", "metric"]
    source_ref: str
    reduction: Literal["identity", "mean", "sum", "min", "max"] = "identity"
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FeedbackVariableSpec(BaseModel):
    """One compact feedback-state component with extraction and injection metadata."""

    model_config = ConfigDict(extra="forbid")

    variable_id: str
    source_kind: Literal["state_path", "metric"]
    source_ref: str
    reduction: Literal["identity", "mean", "sum", "min", "max"] = "identity"
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    target_kind: Literal["state_path", "parameter_override"] = "state_path"
    target_ref: str
    target_param: str | None = None
    initial_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    scale: float | None = Field(default=None, gt=0.0)
    weight: float = Field(default=1.0, gt=0.0)
    finite_difference_step: float | None = Field(default=None, gt=0.0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> FeedbackVariableSpec:
        if self.target_kind == "parameter_override" and not self.target_param:
            raise ValueError("Feedback parameter_override targets require target_param")
        if self.target_kind == "state_path" and self.target_param is not None:
            raise ValueError("Feedback state_path targets must not set target_param")
        return self


class FeedbackDiagnosticSpec(BaseModel):
    """Additional scalar diagnostic emitted alongside the solve trace."""

    model_config = ConfigDict(extra="forbid")

    diagnostic_id: str
    source_kind: Literal["state_path", "metric"]
    source_ref: str
    reduction: Literal["identity", "mean", "sum", "min", "max"] = "identity"
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FeedbackSolverConfig(BaseModel):
    """Numerical controls for the fixed-point outer loop."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mode: Literal["picard", "anderson", "hybrid"] = "hybrid"
    max_iter: int = Field(default=50, ge=1)
    homotopy_grid: list[float] = Field(default_factory=lambda: [0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
    damping_init: float = Field(default=0.5, gt=0.0, le=1.0)
    damping_min: float = Field(default=0.05, gt=0.0, le=1.0)
    anderson_memory: int = Field(default=5, ge=1)
    anderson_start: int = Field(default=3, ge=0)
    anderson_accept_ratio: float = Field(default=0.95, gt=0.0, le=1.0)
    newton_start: int = Field(default=4, ge=0)
    trust_radius_init: float = Field(default=1.0, gt=0.0)
    max_restarts: int = Field(default=3, ge=0)
    stagnation_patience: int = Field(default=4, ge=1)
    divergence_patience: int = Field(default=2, ge=1)
    oscillation_patience: int = Field(default=4, ge=2)
    atol: float = Field(default=1e-6, ge=0.0)
    rtol: float = Field(default=1e-5, ge=0.0)
    xtol: float = Field(default=1e-7, ge=0.0)
    budget_diagnostic_id: str | None = None
    budget_tolerance: float | None = Field(default=None, ge=0.0)
    jacobian_eps: float = Field(default=1e-4, gt=0.0)
    compute_jacobian_diagnostics: bool = True
    multi_start_values: list[list[float]] = Field(default_factory=list)
    fixed_point_merge_tol: float = Field(default=1e-4, gt=0.0)
    store_alternative_fixed_points: bool = True
    detect_multiplicity: bool = False
    multiplicity_mode: Literal["off", "baseline", "continuation"] = "off"
    multiplicity_max_attempts: int = Field(default=256, ge=1)
    multiplicity_sobol_draws: int = Field(default=128, ge=0)
    continuation_parameter: str | None = None
    continuation_grid: list[float] = Field(default_factory=list)
    basin_draws: int = Field(default=0, ge=0)
    basin_seed: int = Field(default=0, ge=0)
    svd_bifurcation_tol: float = Field(default=1e-3, gt=0.0)
    spectral_radius_warn_tol: float = Field(default=5e-2, gt=0.0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_homotopy_grid(self) -> FeedbackSolverConfig:
        if not self.homotopy_grid:
            raise ValueError("homotopy_grid must not be empty")
        if any(value < 0.0 or value > 1.0 for value in self.homotopy_grid):
            raise ValueError("homotopy_grid values must lie in [0, 1]")
        if list(self.homotopy_grid) != sorted(self.homotopy_grid):
            raise ValueError("homotopy_grid must be sorted in nondecreasing order")
        if self.homotopy_grid[0] != 0.0 or self.homotopy_grid[-1] != 1.0:
            raise ValueError("homotopy_grid must start at 0.0 and end at 1.0")
        return self


class FeedbackConfig(BaseModel):
    """Opt-in fixed-point solve configuration for feedback-consistent execution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mode: Literal["off", "fixed_point"] = "fixed_point"
    variables: list[FeedbackVariableSpec] = Field(default_factory=list)
    diagnostics: list[FeedbackDiagnosticSpec] = Field(default_factory=list)
    solver: FeedbackSolverConfig = Field(
        default_factory=lambda: FeedbackSolverConfig(schema_version="1.0")
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_variables(self) -> FeedbackConfig:
        if self.mode == "fixed_point" and not self.variables:
            raise ValueError("feedback fixed_point mode requires at least one variable")
        return self


class FeedbackStateSnapshot(BaseModel):
    """Compact feedback vector plus solver scaling metadata."""

    model_config = ConfigDict(extra="forbid")

    variable_ids: list[str]
    values: list[float]
    scales: list[float]
    lower_bounds: list[float | None]
    upper_bounds: list[float | None]
    weights: list[float]
    notes: list[str] = Field(default_factory=list)


class FeedbackIterationRecord(BaseModel):
    """One outer-loop iteration record persisted into the feedback trace."""

    model_config = ConfigDict(extra="forbid")

    stage_alpha: float
    iteration: int
    residual_norm: float
    step_norm: float
    damping: float
    method: str
    accepted: bool
    iterate: list[float]
    residual: list[float]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FeedbackFixedPointCandidate(BaseModel):
    """One converged fixed-point candidate returned by a multi-start solve."""

    model_config = ConfigDict(extra="forbid")

    state: FeedbackStateSnapshot
    residual_norm: float | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FeedbackTrace(BaseModel):
    """Residual and step trace emitted by a feedback solve."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    records: list[FeedbackIterationRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FeedbackJacobianDiagnostics(BaseModel):
    """Finite-difference Jacobian diagnostics near the solved fixed point."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    dimension: int = Field(ge=1)
    jacobian: list[list[float]] = Field(default_factory=list)
    spectral_radius: float | None = None
    operator_norm_inf: float | None = None
    condition_number: float | None = None
    smallest_singular_value_i_minus_j: float | None = None
    near_fold: bool = False
    near_flip: bool = False
    near_loss_of_stability: bool = False
    near_bifurcation: bool = False
    notes: list[str] = Field(default_factory=list)


class EquilibriumBasinInterval(BaseModel):
    """Confidence interval for a basin-share estimate."""

    model_config = ConfigDict(extra="forbid")

    lower: float = Field(ge=0.0, le=1.0)
    upper: float = Field(ge=0.0, le=1.0)


class EquilibriumSearchProtocol(BaseModel):
    """Protocol metadata for a fixed-point multiplicity search."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["baseline", "research", "continuation"] = "baseline"
    start_domain: dict[str, Any] = Field(default_factory=dict)
    n_attempts: int = Field(ge=1)
    continuation_parameter: str | None = None
    continuation_grid: list[float] = Field(default_factory=list)
    merge_tol: float | None = Field(default=None, gt=0.0)
    residual_tol: float | None = Field(default=None, ge=0.0)
    basin_draws: int = Field(default=0, ge=0)


class EquilibriumCandidateJacobian(BaseModel):
    """Jacobian summaries attached to one equilibrium candidate."""

    model_config = ConfigDict(extra="forbid")

    spectral_radius: float | None = None
    operator_norm_inf: float | None = None
    condition_number: float | None = None
    smallest_singular_value_i_minus_j: float | None = None
    near_fold: bool = False
    near_flip: bool = False
    near_loss_of_stability: bool = False
    near_bifurcation: bool = False


class BasinEstimate(BaseModel):
    """Estimated basin share for one clustered fixed point."""

    model_config = ConfigDict(extra="forbid")

    equilibrium_id: str
    draws: int = Field(ge=0)
    hits: int = Field(ge=0)
    share_hat: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_95: EquilibriumBasinInterval | None = None
    notes: list[str] = Field(default_factory=list)


class EquilibriumCandidate(BaseModel):
    """One clustered fixed-point candidate in a multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    equilibrium_id: str
    state: FeedbackStateSnapshot
    residual_norm: float | None = None
    step_norm: float | None = None
    jacobian: EquilibriumCandidateJacobian | None = None
    local_stability: Literal[
        "attractive",
        "unstable",
        "neutral_or_near_bifurcation",
        "unknown",
    ] = "unknown"
    branch_id: str | None = None
    basin_share_hat: float | None = Field(default=None, ge=0.0, le=1.0)
    basin_ci_95: EquilibriumBasinInterval | None = None
    discovered_from_starts: int = Field(default=1, ge=1)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class EquilibriumBranchPoint(BaseModel):
    """One point on a continuation branch."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    lambda_value: float = Field(alias="lambda")
    equilibrium_id: str


class EquilibriumBranch(BaseModel):
    """A continuation branch through discovered equilibria."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    branch_id: str
    points: list[EquilibriumBranchPoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BifurcationCandidate(BaseModel):
    """Potential bifurcation event detected from local diagnostics."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["fold", "flip", "loss_of_stability"]
    lambda_value: float | None = Field(default=None, alias="lambda")
    equilibrium_id: str
    confidence: Literal["low", "medium", "high"] = "low"
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class UnresolvedEquilibriumStart(BaseModel):
    """A start point that did not converge or could not be assigned to a cluster."""

    model_config = ConfigDict(extra="forbid")

    start_state: FeedbackStateSnapshot
    status: str
    failure_reason: str | None = None
    residual_norm: float | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class EquilibriumMultiplicityDiagnostics(BaseModel):
    """Search-level diagnostics for a multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    num_attempts: int = Field(ge=0)
    num_converged: int = Field(ge=0)
    num_equilibria: int = Field(ge=0)
    num_unresolved: int = Field(default=0, ge=0)
    two_cycle_failures: int = Field(default=0, ge=0)
    stagnation_failures: int = Field(default=0, ge=0)
    divergence_failures: int = Field(default=0, ge=0)
    unresolved_starts_share: float | None = Field(default=None, ge=0.0, le=1.0)
    max_pairwise_cluster_overlap: float | None = None
    branch_switch_events: int = Field(default=0, ge=0)
    continuation_failures: int = Field(default=0, ge=0)
    false_merge_risk: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class EquilibriumMultiplicityProvenance(BaseModel):
    """Reproducibility metadata for a multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    solver_version: str = "polisyos-foundry-feedback-1.0"
    git_sha: str = "unknown"
    runtime_refs: list[str] = Field(default_factory=list)
    random_seed: int | None = None


class EquilibriumMultiplicityReport(BaseModel):
    """Structured report for discovered fixed-point multiplicity."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    model_id: str
    parameter_hash: str | None = None
    search_protocol: EquilibriumSearchProtocol
    equilibria: list[EquilibriumCandidate] = Field(default_factory=list)
    branches: list[EquilibriumBranch] = Field(default_factory=list)
    bifurcation_candidates: list[BifurcationCandidate] = Field(default_factory=list)
    basin_estimates: list[BasinEstimate] = Field(default_factory=list)
    unresolved_starts: list[UnresolvedEquilibriumStart] = Field(default_factory=list)
    global_diagnostics: EquilibriumMultiplicityDiagnostics
    provenance: EquilibriumMultiplicityProvenance = Field(
        default_factory=EquilibriumMultiplicityProvenance
    )
    notes: list[str] = Field(default_factory=list)


class FeedbackConvergenceCertificate(BaseModel):
    """Certificate summarizing whether and how the feedback solve converged."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    status: Literal[
        "converged",
        "max_iter_exceeded",
        "restarts_exhausted",
        "diverged",
        "oscillating",
        "stagnated",
        "failed",
    ]
    converged: bool
    final_stage_alpha: float | None = None
    final_iteration: int | None = Field(default=None, ge=0)
    final_residual_norm: float | None = None
    final_step_norm: float | None = None
    budget_gap: float | None = None
    budget_tolerance: float | None = None
    multiple_fixed_points: bool = False
    oscillation_detected: bool = False
    divergence_detected: bool = False
    stagnation_detected: bool = False
    near_bifurcation: bool = False
    notes: list[str] = Field(default_factory=list)


class FeedbackSolveResult(BaseModel):
    """Top-level feedback-solver outcome persisted as a CAS artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    status: str = "converged"
    converged: bool
    initial_state: FeedbackStateSnapshot
    final_state: FeedbackStateSnapshot
    trace_ref: FeedbackTraceRef | None = None
    jacobian_diagnostics_ref: FeedbackJacobianDiagnosticsRef | None = None
    convergence_certificate_ref: FeedbackConvergenceCertificateRef | None = None
    final_parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None
    multiplicity_report_ref: EquilibriumMultiplicityReportRef | None = None
    alternative_fixed_points: list[FeedbackFixedPointCandidate] = Field(default_factory=list)
    failure_reason: str | None = None
    final_diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class AttractorStateProjection(BaseModel):
    """Reduced observable state on which attractor claims are made."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str] = Field(default_factory=list)
    reduced_dimension: int = Field(ge=0)
    quotient_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimension(self) -> AttractorStateProjection:
        if self.variables and self.reduced_dimension != len(self.variables):
            raise ValueError("reduced_dimension must match variables length")
        return self


class AttractorParameterPoint(BaseModel):
    """Parameter coordinate associated with an attractor-analysis result."""

    model_config = ConfigDict(extra="forbid")

    names: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shapes(self) -> AttractorParameterPoint:
        if len(self.names) != len(self.values):
            raise ValueError("parameter names and values must have equal length")
        return self


class AttractorSpectralValue(BaseModel):
    """JSON-safe representation of a real or complex spectral value."""

    model_config = ConfigDict(extra="forbid")

    real: float
    imag: float = 0.0


class AttractorStateRepresentation(BaseModel):
    """Compact state, orbit, or invariant-set representation for one attractor."""

    model_config = ConfigDict(extra="forbid")

    equilibrium: dict[str, float] | None = None
    section_definition: str | None = None
    orbit_artifact_ref: ArtifactRef | None = None
    orbit_points: list[dict[str, float]] = Field(default_factory=list)
    invariant_set_artifact_ref: ArtifactRef | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class AttractorStability(BaseModel):
    """Local or finite-time stability diagnostics for an attractor candidate."""

    model_config = ConfigDict(extra="forbid")

    local_class: Literal[
        "asymptotically_stable",
        "orbitally_stable",
        "neutral",
        "unstable",
        "mixed",
        "unknown",
    ] = "unknown"
    jacobian_eigenvalues: list[AttractorSpectralValue] = Field(default_factory=list)
    spectral_radius: float | None = Field(default=None, ge=0.0)
    floquet_multipliers: list[AttractorSpectralValue] | None = None
    lyapunov_spectrum: list[float] | None = None
    largest_lyapunov_exponent: float | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class AttractorCertificate(BaseModel):
    """Declare the certificate or evidence supporting an attractor claim."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str = "none"
    status: Literal[
        "not_attempted",
        "not_applicable",
        "numerically_supported",
        "proved_local",
        "proved_global",
        "failed",
    ] = "not_attempted"
    evidence_strength: float | None = Field(default=None, ge=0.0, le=1.0)
    v_description: str | None = Field(default=None, alias="V_description")
    proof_artifact_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class PeriodicOrbitDiagnostics(BaseModel):
    """Diagnostics for a periodic orbit or Poincare-map fixed point."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    period: float = Field(gt=0.0)
    section_definition: str | None = None
    orbit_artifact_ref: ArtifactRef | None = None
    floquet_multipliers: list[AttractorSpectralValue] = Field(default_factory=list)
    spectral_radius: float | None = Field(default=None, ge=0.0)
    transverse_certificate: AttractorCertificate | None = None
    notes: list[str] = Field(default_factory=list)


class AttractorBasinEstimate(BaseModel):
    """Basin-of-attraction estimate for one attractor."""

    model_config = ConfigDict(extra="forbid")

    estimation_method: str | None = None
    basin_measure_estimate: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_interval: tuple[float, float] | None = None
    boundary_complexity: str | None = None
    basin_map_ref: BasinMapRef | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_confidence_interval(self) -> AttractorBasinEstimate:
        if self.confidence_interval is None:
            return self
        lower, upper = self.confidence_interval
        if lower < 0.0 or upper > 1.0 or lower > upper:
            raise ValueError("confidence_interval must be ordered within [0, 1]")
        return self


class AttractorObservableSummary(BaseModel):
    """Human-scale observable properties of one attractor."""

    model_config = ConfigDict(extra="forbid")

    period: float | None = Field(default=None, gt=0.0)
    max_amplitude: float | None = Field(default=None, ge=0.0)
    terminal_residual_norm: float | None = Field(default=None, ge=0.0)
    summary: dict[str, Any] = Field(default_factory=dict)


class AttractorUncertainty(BaseModel):
    """Numerical and stochastic uncertainty attached to one attractor claim."""

    model_config = ConfigDict(extra="forbid")

    seeds_used: int | None = Field(default=None, ge=0)
    numerical_tolerance: float | None = Field(default=None, ge=0.0)
    continuation_step: float | None = Field(default=None, gt=0.0)
    finite_time_horizon: int | None = Field(default=None, ge=0)
    notes: list[str] = Field(default_factory=list)


class AttractorSummary(BaseModel):
    """One attractor, invariant set, or rejected divergent regime."""

    model_config = ConfigDict(extra="forbid")

    attractor_id: str
    kind: Literal[
        "fixed_point",
        "limit_cycle",
        "chaotic",
        "torus",
        "invariant_set",
        "divergent",
    ]
    existence_status: Literal[
        "candidate",
        "numerically_confirmed",
        "analytically_confirmed",
        "rejected",
        "unknown",
    ] = "candidate"
    state_representation: AttractorStateRepresentation = Field(
        default_factory=AttractorStateRepresentation
    )
    stability: AttractorStability = Field(default_factory=AttractorStability)
    certificate: AttractorCertificate = Field(default_factory=AttractorCertificate)
    basin: AttractorBasinEstimate = Field(default_factory=AttractorBasinEstimate)
    observables: AttractorObservableSummary = Field(default_factory=AttractorObservableSummary)
    uncertainty: AttractorUncertainty = Field(default_factory=AttractorUncertainty)
    notes: list[str] = Field(default_factory=list)


class BifurcationEvent(BaseModel):
    """Detected local or global bifurcation event on a branch or sweep."""

    model_config = ConfigDict(extra="forbid")

    bifurcation_id: str
    kind: Literal[
        "saddle_node",
        "hopf",
        "period_doubling",
        "neimark_sacker",
        "torus",
        "branch_point",
        "homoclinic",
        "regime_change",
        "unknown",
    ]
    parameter_values: dict[str, float] = Field(default_factory=dict)
    branch_from: str | None = None
    branch_to: str | None = None
    detection_method: str
    normal_form: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class AttractorUncertaintySummary(BaseModel):
    """Top-level uncertainty summary for an attractor-analysis run."""

    model_config = ConfigDict(extra="forbid")

    stochastic_model: bool = False
    seed_ensemble_size: int | None = Field(default=None, ge=0)
    unresolved_items: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AttractorAnalysisProvenance(BaseModel):
    """Toolchain and upstream artifacts used to produce an attractor report."""

    model_config = ConfigDict(extra="forbid")

    toolchain: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AttractorAnalysisResult(BaseModel):
    """Top-level Foundry artifact for attractors, bifurcations, and certificates."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["foundry.attractor_analysis_result"] = "foundry.attractor_analysis_result"
    analysis_id: str
    model_ref: ArtifactRef | None = None
    simulation_result_ref: SimulationResultRef | None = None
    exec_plan_ref: ExecPlanRef | None = None
    feedback_result_ref: FeedbackResultRef | None = None
    state_projection: AttractorStateProjection
    parameter_point: AttractorParameterPoint = Field(default_factory=AttractorParameterPoint)
    attractors: list[AttractorSummary] = Field(default_factory=list)
    bifurcations: list[BifurcationEvent] = Field(default_factory=list)
    uncertainty_summary: AttractorUncertaintySummary = Field(
        default_factory=AttractorUncertaintySummary
    )
    provenance: AttractorAnalysisProvenance = Field(default_factory=AttractorAnalysisProvenance)
    notes: list[str] = Field(default_factory=list)


class BasinMapSample(BaseModel):
    """One initial-condition sample and its assigned attractor label."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    initial_state: dict[str, float]
    attractor_id: str | None = None
    seed: int | None = None
    terminal_residual_norm: float | None = Field(default=None, ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class BasinMap(BaseModel):
    """Dense basin-map sidecar for attractor analysis."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["foundry.basin_map"] = "foundry.basin_map"
    basin_id: str
    analysis_id: str | None = None
    state_projection: AttractorStateProjection
    sampling_method: str
    samples: list[BasinMapSample] = Field(default_factory=list)
    basin_measure_estimates: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ContinuationBranchPoint(BaseModel):
    """One continuation branch point with optional stability summaries."""

    model_config = ConfigDict(extra="forbid")

    point_id: str
    parameter_values: dict[str, float] = Field(default_factory=dict)
    state: dict[str, float] = Field(default_factory=dict)
    period: float | None = Field(default=None, gt=0.0)
    stability: AttractorStability = Field(default_factory=AttractorStability)
    bifurcation_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class ContinuationBranch(BaseModel):
    """Continuation sidecar for equilibria, periodic orbits, or bifurcation curves."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["foundry.continuation_branch"] = "foundry.continuation_branch"
    branch_id: str
    analysis_id: str | None = None
    branch_kind: Literal["equilibrium", "periodic_orbit", "bifurcation_curve", "parameter_sweep"]
    parameters: list[str] = Field(default_factory=list)
    points: list[ContinuationBranchPoint] = Field(default_factory=list)
    bifurcations: list[BifurcationEvent] = Field(default_factory=list)
    toolchain: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AttractorAnalysisRequest(BaseModel):
    """Input contract for Foundry attractor-analysis endpoints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    model_ref: ArtifactRef | None = None
    simulation_result_ref: SimulationResultRef | None = None
    exec_plan_ref: ExecPlanRef | None = None
    feedback_result_ref: FeedbackResultRef | None = None
    feedback_jacobian_diagnostics_ref: FeedbackJacobianDiagnosticsRef | None = None
    state_projection: AttractorStateProjection | None = None
    parameter_point: AttractorParameterPoint = Field(default_factory=AttractorParameterPoint)
    variable_ids: list[str] = Field(default_factory=list)
    trajectory: list[list[float]] | None = None
    trajectories: list[list[list[float]]] = Field(default_factory=list)
    initial_states: list[dict[str, float]] = Field(default_factory=list)
    seeds: list[int] = Field(default_factory=list)
    analysis_modes: list[
        Literal["attractors", "continuation", "basin_map", "lyapunov"]
    ] = Field(default_factory=lambda: ["attractors"])
    tolerance: float = Field(default=1.0e-6, ge=0.0)
    rtol: float = Field(default=1.0e-5, ge=0.0)
    window: int = Field(default=32, ge=2)
    max_period: int = Field(default=12, ge=2)
    largest_lyapunov_exponent: float | None = None
    stochastic_model: bool = False
    persist_artifact: bool = True
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_ref(self) -> AttractorAnalysisRequest:
        if self.trajectory is not None and self.trajectories:
            raise ValueError("use either trajectory or trajectories, not both")
        trajectory_count = 1 if self.trajectory is not None else len(self.trajectories)
        if self.initial_states and len(self.initial_states) != trajectory_count:
            raise ValueError("initial_states length must match trajectory count")
        if self.seeds and len(self.seeds) != trajectory_count:
            raise ValueError("seeds length must match trajectory count")
        if (
            self.model_ref is None
            and self.simulation_result_ref is None
            and self.exec_plan_ref is None
            and self.feedback_result_ref is None
            and self.trajectory is None
            and not self.trajectories
        ):
            raise ValueError(
                "attractor analysis requires a model/run reference or direct trajectory data"
            )
        if not self.variable_ids and self.state_projection is not None:
            self.variable_ids = list(self.state_projection.variables)
        return self


class AttractorAnalysisResponse(BaseModel):
    """Response contract for Foundry attractor-analysis endpoints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool
    analysis_result: AttractorAnalysisResult | None = None
    analysis_result_ref: AttractorAnalysisResultRef | None = None
    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ParameterOverrideBundle(BaseModel):
    """Collection of parameter overrides plus provenance for who supplied each change."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sources: dict[str, list[str]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ObservedRange(BaseModel):
    """Numeric lower/upper envelope used by welfare-bound providers."""

    model_config = ConfigDict(extra="forbid")

    lower: float | list[float] | None = None
    upper: float | list[float] | None = None
    notes: list[str] = Field(default_factory=list)


class ObservedRangeBundle(BaseModel):
    """Optional calibrated ranges attached to execution for welfare certification."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    data_snapshot_ref: ArtifactRef | None = None
    ranges: dict[str, ObservedRange] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    """Input contract for running a compiled Foundry plan against bound evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    exec_plan_ref: ExecPlanRef
    input_bindings_ref: FoundryInputBindingsRef

    registry_bundle_ref: ArtifactRef | None = None
    feedback_config_ref: FeedbackConfigRef | None = None
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None
    observed_range_bundle_ref: ObservedRangeBundleRef | None = None
    welfare_bound_mode: Literal["ex_ante", "ex_post", "both"] = "ex_ante"
    welfare_bound_required: bool = False
    exec_config: FoundryExecConfig = Field(
        default_factory=lambda: FoundryExecConfig(schema_version="1.0")
    )
    notes: list[str] = Field(default_factory=list)


class ExecuteResult(BaseModel):
    """Execution outcome pointing to the simulation result and any additional derived artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool

    simulation_result_ref: SimulationResultRef | None = None
    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WelfareBoundReport(BaseModel):
    """Node-level welfare-loss envelope relative to a planner first-best benchmark."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanism_type: str
    node_id: str | None = None
    mode: Literal["ex_ante", "ex_post", "both"] = "ex_ante"
    welfare_loss_lower: float | None = None
    welfare_loss_upper: float | None = None
    first_best_lower: float | None = None
    first_best_upper: float | None = None
    mechanism_value: float | None = None
    required_observables: tuple[str, ...] = Field(default_factory=tuple)
    status: Literal["ok", "warning", "insufficient_observables", "invalid_input"] = "ok"
    notes: list[str] = Field(default_factory=list)


class StateSnapshot(BaseModel):
    """Reference bundle for a materialized execution state at a particular simulation step."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    state_ref: ArtifactRef
    schema_ref: ArtifactRef | None = None
    step: int | None = None
    format_version: str = "npz-v2"
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    entry_count: int | None = Field(default=None, ge=0)
    codec: str = "numpy-npz"
    notes: list[str] = Field(default_factory=list)


class TreasurySeed(BaseModel):
    """Treasury seed public type."""

    model_config = ConfigDict(extra="forbid")

    seed: int
    streams: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecConfig(BaseModel):
    """Minimal execution overrides accepted by legacy callers at run launch time."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["dev", "perf", "audit"] = "dev"
    max_steps: int | None = None
    deterministic: bool = True
    notes: list[str] = Field(default_factory=list)


class PatchOp(BaseModel):
    """Patch op public type."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    op: Literal["add", "set"]
    value_ref: ArtifactRef | None = None
    mask_ref: ArtifactRef | None = None
    mask_scope: Literal["global", "per_agent", "per_firm", "per_entity"] | None = None
    notes: list[str] = Field(default_factory=list)


class UpdateOp(BaseModel):
    """Update op public type."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    op: Literal["add", "set", "priority_set", "clamp", "masked"]
    value_ref: ArtifactRef | None = None
    mask_ref: ArtifactRef | None = None
    priority: int | None = None
    min_ref: ArtifactRef | None = None
    max_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class PatchMeta(BaseModel):
    """Patch meta public type."""

    model_config = ConfigDict(extra="forbid")

    source_node_id: str | None = None
    step: int | None = None
    mode: Literal["dev", "perf", "audit"] | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Patch(BaseModel):
    """Patch public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    meta: PatchMeta | None = None
    ops: list[UpdateOp] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PatchSet(BaseModel):
    """Patch set public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    patches: list[Patch] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StateDelta(BaseModel):
    """State delta public type."""

    model_config = ConfigDict(extra="forbid")

    base_ref: StateSnapshotRef | None = None
    patch_ref: ArtifactRef | None = None
    ops: list[PatchOp] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Metrics(BaseModel):
    """Scalar metrics emitted by a Foundry execution, keyed by metric identifier."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, float | int | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ModelOutputs(BaseModel):
    """Per-model outputs needed to recompute metrics under paired tests and resampling."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    y_pred: list[bool | int | float | str] | None = None
    y_score: list[float] | list[list[float]] | None = None
    per_example_loss: dict[str, list[float]] | None = None


class MetricObservationBundle(BaseModel):
    """Per-example observations required for paired metric validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    dataset_id: str
    task: Literal["binary", "multiclass", "multilabel", "regression"]
    sample_ids: list[str] = Field(default_factory=list)
    y_true: list[bool | int | float | str]
    models: dict[str, ModelOutputs] = Field(default_factory=dict)
    sample_weight: list[float] | None = None
    strata: dict[str, list[bool | int | float | str]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shapes(self) -> MetricObservationBundle:
        n_samples = len(self.y_true)
        if n_samples == 0:
            raise ValueError("MetricObservationBundle requires at least one observation")
        if self.sample_ids:
            if len(self.sample_ids) != n_samples:
                raise ValueError("sample_ids length must match y_true length")
        else:
            self.sample_ids = [f"row_{index}" for index in range(n_samples)]
        if self.sample_weight is not None and len(self.sample_weight) != n_samples:
            raise ValueError("sample_weight length must match y_true length")
        if self.strata is not None:
            for key, values in self.strata.items():
                if len(values) != n_samples:
                    raise ValueError(f"strata[{key!r}] length must match y_true length")
        if not self.models:
            raise ValueError("MetricObservationBundle requires at least one model output")
        for model_id, outputs in self.models.items():
            if outputs.y_pred is not None and len(outputs.y_pred) != n_samples:
                raise ValueError(f"models[{model_id!r}].y_pred length must match y_true")
            if outputs.y_score is not None and len(outputs.y_score) != n_samples:
                raise ValueError(f"models[{model_id!r}].y_score length must match y_true")
            if outputs.per_example_loss is not None:
                for metric_id, losses in outputs.per_example_loss.items():
                    if len(losses) != n_samples:
                        raise ValueError(
                            f"models[{model_id!r}].per_example_loss[{metric_id!r}] length "
                            "must match y_true"
                        )
        return self


class ConstraintViolation(BaseModel):
    """Constraint violation public type."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    severity: Literal["hard", "soft"]
    slot_id: str
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    expected: str
    actual: str
    violated: bool
    penalty: Decimal | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


class ConstraintReport(BaseModel):
    """Constraint-evaluation outcome summarizing hard and soft violations for a run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool
    hard_fail: bool = False
    constraint_mode: str = "hard_soft_v1"
    total_constraints: int = 0
    violations: list[ConstraintViolation] = Field(default_factory=list)
    penalty_total: Decimal | None = None
    notes: list[str] = Field(default_factory=list)


class SimulationResult(BaseModel):
    """Top-level execution artifact tying plans, metrics, traces, and optional reports together."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.3", pattern=r"^\d+\.\d+$")
    exec_plan_ref: ExecPlanRef
    metrics_ref: MetricsRef
    metric_observation_bundle_ref: MetricObservationBundleRef | None = None
    state_snapshot_ref: StateSnapshotRef | None = None
    environment_ref: EnvironmentManifestRef | None = None
    environment_fingerprint: str | None = None
    trace_slice_ref: TraceSliceRef | None = None
    uncertainty_envelopes: Mapping[str, UncertaintyEnvelopeRef] | None = None
    distributional_report_ref: DistributionalReportRef | None = None
    welfare_bundle_ref: WelfareBundleRef | None = None
    welfare_bound_refs: Mapping[str, WelfareBoundReportRef] | None = None
    metric_validation_report_ref: MetricValidationReportRef | None = None
    fairness_audit_report_ref: FairnessAuditReportRef | None = None
    propagation_config_ref: ArtifactRef | None = None
    propagation_report_ref: ArtifactRef | None = None
    feedback_result_ref: FeedbackResultRef | None = None
    identifiability_diagnostic_ref: IdentifiabilityDiagnosticRef | None = None
    notes: list[str] = Field(default_factory=list)
