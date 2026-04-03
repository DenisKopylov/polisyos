"""Blueprint artifact minimality contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_serializer, model_validator


class ArtifactFunction(str, Enum):
    """Artifact function public type."""
    ROUTING = "routing"
    PROMOTION_GATING = "promotion_gating"
    REPLAY_AUDIT = "replay_audit"
    CROSS_RUN_LEARNING = "cross_run_learning"


class ArtifactMinimalityMixin(BaseModel):
    """Artifact minimality mixin public type."""
    artifact_functions: set[ArtifactFunction] = Field(default_factory=set)

    @model_validator(mode="after")
    def _validate_artifact_functions(self):
        if not self.artifact_functions:
            raise ValueError("artifact_functions must include at least one minimality function")
        return self

    @field_serializer("artifact_functions", when_used="always")
    def _serialize_artifact_functions(
        self,
        value: set[ArtifactFunction],
    ) -> list[str]:
        return sorted(
            item.value if isinstance(item, ArtifactFunction) else str(item)
            for item in value
        )


def artifact_functions_field(*functions: ArtifactFunction) -> set[ArtifactFunction]:
    """Artifact functions field helper."""
    return set(functions)


__all__ = [
    "ArtifactFunction",
    "ArtifactMinimalityMixin",
    "artifact_functions_field",
]
