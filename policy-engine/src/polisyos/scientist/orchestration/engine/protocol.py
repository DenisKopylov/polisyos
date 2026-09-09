"""Runtime protocol types for Scientist nodes, outcomes, and state contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import ComponentMetadata
from polisyos.core.contracts.skip_blockers import SkippedNodeBlocker
from polisyos.scientist.orchestration.engine.state import ExperimentState

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

NodeStatus = Literal["ok", "skip", "fail"]


class NodeError(BaseModel):
    """Node error exception."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Must be canonical-json friendly (no float).",
    )


class NodeEvent(BaseModel):
    """Structured node event emitted for tracing, diagnostics, and operator-facing logs."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["debug", "info", "warn", "error"] = "info"
    code: str | None = None
    message: str
    attrs: dict[str, str | int | bool] = Field(default_factory=dict)


class NodeOutcome(BaseModel):
    """Node outcome public type."""

    model_config = ConfigDict(extra="forbid")

    status: NodeStatus
    state: ExperimentState
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    events: list[NodeEvent] = Field(default_factory=list)
    error: NodeError | None = None
    skip_blocker: SkippedNodeBlocker | None = None

    @model_validator(mode="after")
    def _validate_error(self) -> NodeOutcome:
        if self.status == "fail" and self.error is None:
            raise ValueError("NodeOutcome.error must be set when status=fail")
        if self.status != "fail" and self.error is not None:
            raise ValueError("NodeOutcome.error must be null unless status=fail")
        if self.status != "skip" and self.skip_blocker is not None:
            raise ValueError("NodeOutcome.skip_blocker must be null unless status=skip")
        return self


class NodeSpec(BaseModel):
    """Declarative node contract that tells the DAG runtime what state a node touches."""

    model_config = ConfigDict(extra="forbid")

    metadata: ComponentMetadata
    state_reads: list[str] = Field(default_factory=list)
    state_writes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list, description="Logical artifact keys")


class NodeOutputRule(BaseModel):
    """Availability of a declared output; ordinary outputs remain required."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    output_key: str = Field(min_length=1)
    availability: Literal["required", "owner_verified_refusal"] = "required"
    verifier_rule_ref: str | None = None

    @model_validator(mode="after")
    def _validate_verifier(self) -> NodeOutputRule:
        if self.availability == "owner_verified_refusal" and not self.verifier_rule_ref:
            raise ValueError("conditional_output_verifier_required")
        if self.availability == "required" and self.verifier_rule_ref is not None:
            raise ValueError("required_output_has_no_refusal_verifier")
        return self


class OutputAwareNodeSpec(NodeSpec):
    """Explicit governed output contract without changing ordinary NodeSpec bytes."""

    output_rules: tuple[NodeOutputRule, ...]

    @model_validator(mode="after")
    def _validate_population(self) -> OutputAwareNodeSpec:
        keys = [rule.output_key for rule in self.output_rules]
        if len(keys) != len(set(keys)) or len(self.produces) != len(set(self.produces)):
            raise ValueError("output_contract_duplicate_key")
        if set(keys) != set(self.produces):
            raise ValueError("output_contract_population_mismatch")
        return self


class NodeOutputDisposition(BaseModel):
    """One current positive output or a separate current refusal artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    output_key: str = Field(min_length=1)
    disposition: Literal["produced", "refused"]
    artifact_ref: ArtifactRef


class NodeOutputRefusal(BaseModel):
    """Conditional refusal evidence; this typed object alone grants no admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.scientist.node_output_refusal.v1"] = (
        "polisyos.scientist.node_output_refusal.v1"
    )
    node_id: str
    output_key: str
    verifier_rule_ref: str
    reason_code: str
    premise_presence: Literal["absent", "present_null", "value"]
    input_state_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    node_spec_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_refs: tuple[ArtifactRef, ...]
    premise: dict[str, Any]


class OutputAwareNodeOutcome(NodeOutcome):
    """Current output disposition ledger, separate from positive state ports."""

    outcome_schema_version: Literal["polisyos.scientist.output_aware_node_outcome.v1"] = (
        "polisyos.scientist.output_aware_node_outcome.v1"
    )
    output_dispositions: tuple[NodeOutputDisposition, ...]
    supporting_artifacts: dict[str, ArtifactRef] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_disposition_keys(self) -> OutputAwareNodeOutcome:
        keys = [row.output_key for row in self.output_dispositions]
        if len(keys) != len(set(keys)):
            raise ValueError("output_disposition_duplicate_key")
        return self


def decode_node_outcome(value: object) -> NodeOutcome:
    """Decode a complete outcome without discarding an offered output contract.

    Existing in-memory outcomes retain their identity. Serialized subtype fields
    select strict subtype validation even when another required field is absent,
    null, or malformed. Ordinary outcomes keep their established wire shape.
    """
    if isinstance(value, NodeOutcome):
        return value
    extension_fields = OutputAwareNodeOutcome.model_fields.keys() - NodeOutcome.model_fields.keys()
    if isinstance(value, dict) and extension_fields.intersection(value):
        return OutputAwareNodeOutcome.model_validate(value)
    return NodeOutcome.model_validate(value)


@runtime_checkable
class Node(Protocol):
    """Protocol for executable DAG nodes that declare contracts and return `NodeOutcome`."""

    @property
    def spec(self) -> NodeSpec:  # pragma: no cover - protocol signature
        ...

    def execute(
        self, ctx: ExecutionContext, state: ExperimentState
    ) -> NodeOutcome:  # pragma: no cover - protocol signature
        ...
