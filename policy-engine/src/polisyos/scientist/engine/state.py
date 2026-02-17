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

    schema_version: str = Field("1.2", pattern=r"^\d+\.\d+$")
    run_id: str

    inputs: dict[str, ArtifactRef] = Field(default_factory=dict)
    artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    reports_index: dict[str, ArtifactRef] = Field(default_factory=dict)

    params: dict[str, JsonValue] = Field(default_factory=dict)
    budgets: dict[str, Decimal] = Field(default_factory=dict)
    last_checkpoint_ref: ArtifactRef | None = None

    observational_data_ref: ArtifactRef | None = None
    execution_plan_ref: ArtifactRef | None = None
    method_catalog_snapshot_ref: ArtifactRef | None = None
    preflight_report_ref: ArtifactRef | None = None
    evaluator_report_ref: ArtifactRef | None = None
    iteration_state_ref: ArtifactRef | None = None
    reproducibility_manifest_ref: ArtifactRef | None = None
    causal_method_fqn: str | None = None
    causal_method_params: dict[str, JsonValue] = Field(default_factory=dict)
    critic_knowledge_base_ref: ArtifactRef | None = None
    constitution_hash: str | None = Field(default=None, min_length=64, max_length=64)
