"""IR contracts for network-embedding faithfulness diagnostics."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingFidelityStatus(str, Enum):
    """Fail-closed operational status for embedding faithfulness."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class EmbeddingFidelityAction(str, Enum):
    """Recommended routing action for downstream causal consumers."""

    ALLOW_AS_ADJUSTMENT = "allow_as_adjustment"
    ALLOW_AS_NUISANCE_ONLY = "allow_as_nuisance_only"
    REQUIRE_RAW_GRAPH_SUMMARIES = "require_raw_graph_summaries"
    REQUIRE_BOUNDS = "require_bounds"
    BLOCK = "block"


class NetworkEmbeddingFidelityCertificate(BaseModel):
    """Typed certificate describing whether a network embedding is safe for causal use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    family: str = Field(min_length=1)
    status: EmbeddingFidelityStatus
    exact_faithfulness_claimed: bool = False
    target_ci_specs: list[dict[str, Any]] = Field(default_factory=list)
    recoverability_scores: dict[str, float] = Field(default_factory=dict)
    residual_dependence_scores: dict[str, float] = Field(default_factory=dict)
    adjusted_p_values: dict[str, float] | None = None
    collision_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    effect_drift_z: float | None = Field(default=None, ge=0.0)
    environment_stability: dict[str, float] = Field(default_factory=dict)
    effective_sample_size: float | None = Field(default=None, ge=0.0)
    assumptions: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    recommended_action: EmbeddingFidelityAction
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_adjustment_certified(self) -> bool:
        """Return whether the embedding can safely replace raw separators."""
        return (
            self.status is EmbeddingFidelityStatus.GREEN
            and self.recommended_action is EmbeddingFidelityAction.ALLOW_AS_ADJUSTMENT
        )


__all__ = [
    "EmbeddingFidelityAction",
    "EmbeddingFidelityStatus",
    "NetworkEmbeddingFidelityCertificate",
]
