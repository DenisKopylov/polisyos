from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..artifacts.environment import EnvironmentManifestRef
from ..artifacts.manifest import ArtifactRef


class PolicySurfaceIRRef(ArtifactRef):
    kind: Literal["ir.policy_surface"] = "ir.policy_surface"
    media_type: Literal["application/json"] = "application/json"


class ProgramGraphRef(ArtifactRef):
    kind: Literal["foundry.program_graph"] = "foundry.program_graph"
    media_type: Literal["application/json"] = "application/json"


class LoweredIRRef(ArtifactRef):
    kind: Literal["foundry.lowered_ir"] = "foundry.lowered_ir"
    media_type: Literal["application/json"] = "application/json"


class ExecPlanRef(ArtifactRef):
    kind: Literal["foundry.exec_plan"] = "foundry.exec_plan"
    media_type: Literal["application/json"] = "application/json"


class StateSnapshotRef(ArtifactRef):
    kind: Literal["foundry.state_snapshot"] = "foundry.state_snapshot"
    media_type: Literal["application/json"] = "application/json"


class TreasurySeedRef(ArtifactRef):
    kind: Literal["foundry.treasury_seed"] = "foundry.treasury_seed"
    media_type: Literal["application/json"] = "application/json"


class ExecConfigRef(ArtifactRef):
    kind: Literal["foundry.exec_config"] = "foundry.exec_config"
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
    kind: Literal["foundry.state_delta"] = "foundry.state_delta"
    media_type: Literal["application/json"] = "application/json"


class MetricsRef(ArtifactRef):
    kind: Literal["foundry.metrics"] = "foundry.metrics"
    media_type: Literal["application/json"] = "application/json"


class ConstraintReportRef(ArtifactRef):
    kind: Literal["foundry.constraint_report"] = "foundry.constraint_report"
    media_type: Literal["application/json"] = "application/json"


class CalibrationReportRef(ArtifactRef):
    kind: Literal["foundry.calibration_report"] = "foundry.calibration_report"
    media_type: Literal["application/json"] = "application/json"


class TraceSliceRef(ArtifactRef):
    kind: Literal["foundry.trace_slice"] = "foundry.trace_slice"
    media_type: Literal["application/jsonl"] = "application/jsonl"


class ProgramNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_kind: Literal["mechanism", "op"] = "mechanism"
    mechanism_type: str | None = None
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
        return self


class ProgramOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op_kind: Literal[
        "merge_state",
        "check_constraints",
        "read_view",
        "make_mask",
        "apply_mechanism",
    ]
    params: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


ProgramNode.model_rebuild()


class ProgramEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    relation: str = "depends_on"


class ProgramGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ir_ref: PolicySurfaceIRRef
    nodes: list[ProgramNode] = Field(default_factory=list)
    edges: list[ProgramEdge] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class LoweredMechanism(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mechanism_type: str
    params_ref: ArtifactRef | None = None
    target_ref: ArtifactRef | None = None


class LoweredIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ir_ref: PolicySurfaceIRRef
    mechanisms: list[LoweredMechanism] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ExecPlan(BaseModel):
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
    mode: Literal["dev", "perf", "audit"] = "dev"
    jit: bool = True
    max_steps: int | None = None
    notes: list[str] = Field(default_factory=list)


class StateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_ref: ArtifactRef
    schema_ref: ArtifactRef | None = None
    step: int | None = None
    notes: list[str] = Field(default_factory=list)


class TreasurySeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int
    streams: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["dev", "perf", "audit"] = "dev"
    max_steps: int | None = None
    deterministic: bool = True
    notes: list[str] = Field(default_factory=list)


class PatchOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    op: Literal["add", "set"]
    value_ref: ArtifactRef | None = None
    mask_ref: ArtifactRef | None = None
    mask_scope: Literal["global", "per_agent", "per_firm", "per_entity"] | None = None
    notes: list[str] = Field(default_factory=list)


class UpdateOp(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    source_node_id: str | None = None
    step: int | None = None
    mode: Literal["dev", "perf", "audit"] | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    meta: PatchMeta | None = None
    ops: list[UpdateOp] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PatchSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    patches: list[Patch] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StateDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_ref: StateSnapshotRef | None = None
    patch_ref: ArtifactRef | None = None
    ops: list[PatchOp] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, int | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
