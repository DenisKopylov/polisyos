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
