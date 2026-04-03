"""Declarative DAG contracts consumed by Scientist workflow executors.

Workflow modules assemble `WorkflowSpec` instances from `NodeInvocation`
records. These specs describe orchestration topology, required input binds,
retry/condition metadata, and execution policy while keeping business logic in
node implementations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.components import ComponentId
from polisyos.scientist.engine.condition import NodeCondition
from polisyos.scientist.engine.retry import RetryPolicy

ErrorPolicy = Literal["fail_fast", "continue"]
JsonPrimitive = str | int | bool | Decimal | None
JsonValue = JsonPrimitive | list[Any] | dict[str, Any]


class NodeInvocation(BaseModel):
    """Describe one node instance inside a workflow DAG.

    `alias` is the local dependency name used by downstream `depends_on`
    references, while `node_id` points at the registered component implementation.
    Optional `params`, `retry`, `timeout_s`, and `condition` override per-node
    behavior without changing the node class.

    Attributes:
        alias: Unique node alias within the workflow specification.
        node_id: Component identifier resolved by `NodeRegistry`.
        params: JSON-compatible overrides supplied to the node invocation.
        depends_on: Upstream node aliases that must finish before execution.
        retry: Optional retry policy for transient node failures.
        timeout_s: Optional per-node execution timeout in seconds.
        condition: Optional gate expression evaluated against current state.
    """
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    node_id: ComponentId
    params: dict[str, JsonValue] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, description="List of node aliases")
    retry: RetryPolicy | None = Field(default=None, description="Per-node retry policy")
    timeout_s: float | None = Field(default=None, ge=1.0, le=3600.0)
    condition: NodeCondition | None = Field(
        default=None,
        description="Optional condition — node skipped/failed when expression evaluates to False",
    )

    @field_validator("params", mode="before")
    @classmethod
    def _normalize_params(cls, value: Any) -> dict[str, JsonValue]:
        if not isinstance(value, dict):
            return {}
        return _normalize_json_mapping(value)


class WorkflowSpec(BaseModel):
    """Capture a full Scientist DAG and the binds required before execution.

    A workflow spec is immutable orchestration metadata: the executor validates
    dependency aliases, checks `required_binds` against `ExperimentState`, and
    applies `error_policy` when a node fails or skips.

    Attributes:
        schema_version: Version of the workflow-spec contract.
        workflow_id: Stable identifier used by `run_experiment()` and routing helpers.
        nodes: Ordered node declarations that form the DAG.
        required_binds: `ExperimentState` paths that must exist before execution.
        error_policy: Global failure handling policy for the executor.
        notes: Human-readable orchestration rationale rendered in docs and diagnostics.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    workflow_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")

    nodes: list[NodeInvocation] = Field(default_factory=list)
    required_binds: list[str] = Field(default_factory=list)
    error_policy: ErrorPolicy = "fail_fast"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_aliases(self) -> "WorkflowSpec":
        aliases = [n.alias for n in self.nodes]
        if len(set(aliases)) != len(aliases):
            raise ValueError("NodeInvocation.alias must be unique within workflow")
        return self


def _normalize_json_value(value: Any) -> JsonValue:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return _normalize_json_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]
    return value


def _normalize_json_mapping(payload: dict[str, Any]) -> dict[str, JsonValue]:
    normalized: dict[str, JsonValue] = {}
    for key, value in payload.items():
        normalized[str(key)] = _normalize_json_value(value)
    return normalized
