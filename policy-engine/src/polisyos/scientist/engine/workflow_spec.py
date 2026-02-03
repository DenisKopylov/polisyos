from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.components import ComponentId

ErrorPolicy = Literal["fail_fast", "continue"]


class NodeInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    node_id: ComponentId
    params: dict[str, str | int | bool | Decimal] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, description="List of node aliases")


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
