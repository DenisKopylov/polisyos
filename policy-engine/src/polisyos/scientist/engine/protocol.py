"""Runtime protocol types for Scientist nodes, outcomes, and state contracts."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import ComponentMetadata
from polisyos.scientist.engine.state import ExperimentState

if TYPE_CHECKING:
    from polisyos.scientist.engine.context import ExecutionContext

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

    @model_validator(mode="after")
    def _validate_error(self) -> "NodeOutcome":
        if self.status == "fail" and self.error is None:
            raise ValueError("NodeOutcome.error must be set when status=fail")
        if self.status != "fail" and self.error is not None:
            raise ValueError("NodeOutcome.error must be null unless status=fail")
        return self


class NodeSpec(BaseModel):
    """Declarative node contract that tells the DAG runtime what state a node touches."""
    model_config = ConfigDict(extra="forbid")

    metadata: ComponentMetadata
    state_reads: list[str] = Field(default_factory=list)
    state_writes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list, description="Logical artifact keys")


@runtime_checkable
class Node(Protocol):
    """Protocol for executable DAG nodes that declare contracts and return `NodeOutcome`."""
    @property
    def spec(self) -> NodeSpec:  # pragma: no cover - protocol signature
        ...

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:  # pragma: no cover - protocol signature
        ...
