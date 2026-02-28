from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ContextProfileInferenceLevel(str, Enum):
    INFERRED_BASIC = "inferred_basic"
    ENRICHED = "enriched"
    MANUAL = "manual"


class ContextProfile(BaseModel):
    """Context profile for transport-aware literature reuse."""

    model_config = ConfigDict(extra="forbid")

    context_id: str = ""
    context_label: str = ""
    countries: list[str] = Field(default_factory=list)
    income_level: str = "unknown"
    publication_year: int | None = None
    institutional_quality: float | None = None
    inference_level: ContextProfileInferenceLevel = ContextProfileInferenceLevel.INFERRED_BASIC
    data_sources: list[str] = Field(default_factory=list)

    def distance_to(self, other: "ContextProfile") -> float:
        """Simple context distance in [0,1] used for ranking and weighting."""
        distance = 0.0
        if self.context_id and other.context_id and self.context_id != other.context_id:
            distance += 0.35
        if self.income_level and other.income_level and self.income_level != other.income_level:
            distance += 0.25
        if self.publication_year and other.publication_year:
            delta = abs(self.publication_year - other.publication_year)
            distance += min(delta / 30.0, 0.25)
        return min(distance, 1.0)


__all__ = ["ContextProfile", "ContextProfileInferenceLevel"]
