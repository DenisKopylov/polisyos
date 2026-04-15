"""Stable Foundry contracts for compile-time graphs, execution plans, and simulation outputs."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..artifacts.environment import EnvironmentManifestRef
from ..artifacts.manifest import ArtifactRef
from .distributional import DistributionalReportRef
from .uncertainty import UncertaintyEnvelopeRef


class ProgramGraphRef(ArtifactRef):
    """Artifact reference for the compiled program graph a Foundry run will execute."""
    kind: Literal["foundry.program_graph"] = "foundry.program_graph"
    media_type: Literal["application/json"] = "application/json"


class LoweredIRRef(ArtifactRef):
    """Artifact reference for the lowered IR produced before execution planning."""
    kind: Literal["foundry.lowered_ir"] = "foundry.lowered_ir"
    media_type: Literal["application/json"] = "application/json"


class ExecPlanRef(ArtifactRef):
    """Artifact reference for the resolved Foundry execution plan and runtime posture."""
    kind: Literal["foundry.exec_plan"] = "foundry.exec_plan"
    media_type: Literal["application/json"] = "application/json"


class StateSnapshotRef(ArtifactRef):
    """Artifact reference for a persisted state snapshot emitted by a simulation."""
    kind: Literal["foundry.state_snapshot"] = "foundry.state_snapshot"
    media_type: Literal["application/json"] = "application/json"


class FoundryInputBindingsRef(ArtifactRef):
    """Artifact reference for the slot-binding bundle used to seed a Foundry execution."""
    kind: Literal["foundry.input_bindings"] = "foundry.input_bindings"
    media_type: Literal["application/json"] = "application/json"


class FoundryInputBindingReportRef(ArtifactRef):
    """Artifact reference for the report describing how external data was bound to slots."""
    kind: Literal["foundry.input_binding_report"] = "foundry.input_binding_report"
    media_type: Literal["application/json"] = "application/json"


class TreasurySeedRef(ArtifactRef):
    """Artifact reference for deterministic random-stream seeds used during execution."""
    kind: Literal["foundry.treasury_seed"] = "foundry.treasury_seed"
    media_type: Literal["application/json"] = "application/json"


class ExecConfigRef(ArtifactRef):
    """Artifact reference for the executor configuration applied to a simulation run."""
    kind: Literal["foundry.exec_config"] = "foundry.exec_config"
    media_type: Literal["application/json"] = "application/json"


class MethodArtifactRef(ArtifactRef):
    """Method artifact ref data model."""
    kind: Literal["foundry.method_artifact"] = "foundry.method_artifact"
    media_type: Literal["application/json"] = "application/json"


class ChainArtifactRef(ArtifactRef):
    """Chain artifact ref data model."""
    kind: Literal["foundry.chain_artifact"] = "foundry.chain_artifact"
    media_type: Literal["application/json"] = "application/json"


class ExecutionEvidenceRef(ArtifactRef):
    """Execution evidence ref data model."""
    kind: Literal["foundry.execution_evidence"] = "foundry.execution_evidence"
    media_type: Literal["application/json"] = "application/json"


class AgentPolicyRef(ArtifactRef):
    """
    Typed reference to an AgentPolicyArtifact in CAS.

    Used in simulation configs to reference trained policies without
    embedding full weights in configuration files.
    """

    kind: Literal["foundry.agent_policy"] = "foundry.agent_policy"
    media_type: Literal["application/octet-stream"] = "application/octet-stream"

    policy_type: str = Field(description="ActorCritic, MLP, etc.")
    determinism_tier: str = Field(
        description="strict_cpu, best_effort_gpu, nondeterministic"
    )
    training_steps: int = Field(ge=0, description="Steps when artifact was created")
    env_hash: str = Field(description="16-char environment fingerprint hash")


class StateDeltaRef(ArtifactRef):
    """Artifact reference for the patch set that transforms one state snapshot into the next."""
    kind: Literal["foundry.state_delta"] = "foundry.state_delta"
    media_type: Literal["application/json"] = "application/json"


class MetricsRef(ArtifactRef):
    """Artifact reference for the scalar metrics emitted by a Foundry execution."""
    kind: Literal["foundry.metrics"] = "foundry.metrics"
    media_type: Literal["application/json"] = "application/json"


class ConstraintReportRef(ArtifactRef):
    """Constraint report ref data model."""
    kind: Literal["foundry.constraint_report"] = "foundry.constraint_report"
    media_type: Literal["application/json"] = "application/json"


class CalibrationReportRef(ArtifactRef):
    """Artifact reference for calibration diagnostics emitted alongside simulation outputs."""
    kind: Literal["foundry.calibration_report"] = "foundry.calibration_report"
    media_type: Literal["application/json"] = "application/json"


class ParameterOverrideBundleRef(ArtifactRef):
    """Artifact reference for parameter overrides layered onto a baseline execution config."""
    kind: Literal["foundry.parameter_override_bundle"] = "foundry.parameter_override_bundle"
    media_type: Literal["application/json"] = "application/json"


class TraceSliceRef(ArtifactRef):
    """Artifact reference for the structured execution trace slice captured during a run."""
    kind: Literal["foundry.trace_slice"] = "foundry.trace_slice"
    media_type: Literal["application/jsonl"] = "application/jsonl"


class SimulationResultRef(ArtifactRef):
    """Artifact reference for the top-level simulation result bundle returned by Foundry."""
    kind: Literal["foundry.simulation_result"] = "foundry.simulation_result"
    media_type: Literal["application/json"] = "application/json"


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
    def validate_kind(self) -> "ProgramNode":
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
    compile_config: FoundryCompileConfig = Field(default_factory=FoundryCompileConfig)
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


class ParameterOverrideBundle(BaseModel):
    """Collection of parameter overrides plus provenance for who supplied each change."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sources: dict[str, list[str]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    """Input contract for running a compiled Foundry plan against bound evidence."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    exec_plan_ref: ExecPlanRef
    input_bindings_ref: FoundryInputBindingsRef

    registry_bundle_ref: ArtifactRef | None = None
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None
    exec_config: FoundryExecConfig = Field(default_factory=FoundryExecConfig)
    notes: list[str] = Field(default_factory=list)


class ExecuteResult(BaseModel):
    """Execution outcome pointing to the simulation result and any additional derived artifacts."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool

    simulation_result_ref: SimulationResultRef | None = None
    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
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

    values: dict[str, int | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


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

    exec_plan_ref: ExecPlanRef
    metrics_ref: MetricsRef
    state_snapshot_ref: StateSnapshotRef | None = None
    environment_ref: EnvironmentManifestRef | None = None
    environment_fingerprint: str | None = None
    trace_slice_ref: TraceSliceRef | None = None
    uncertainty_envelopes: Mapping[str, UncertaintyEnvelopeRef] | None = None
    distributional_report_ref: DistributionalReportRef | None = None
    propagation_config_ref: ArtifactRef | None = None
    propagation_report_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)
