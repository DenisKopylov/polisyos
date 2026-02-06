from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef

JsonPrimitive = str | int | bool | Decimal | None
JsonValue = JsonPrimitive | list[Any] | dict[str, Any]
JsonScalar = JsonPrimitive


class ExperimentState(BaseModel):
    """Minimal experiment state for Scientist workflows."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str

    inputs: dict[str, ArtifactRef] = Field(default_factory=dict)
    artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    reports_index: dict[str, ArtifactRef] = Field(default_factory=dict)

    params: dict[str, JsonValue] = Field(default_factory=dict)
    budgets: dict[str, Decimal] = Field(default_factory=dict)
