"""
Inference result model.

Contains the InferenceResult Pydantic model that wraps a DataSchema
together with per-field confidence scores and diagnostics.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.connectors.contracts.schema import DataSchema

__all__ = [
    "InferenceResult",
]


class InferenceResult(BaseModel):
    """Result of schema inference with confidence scores."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    inferred_schema: DataSchema = Field(alias="schema")

    # Confidence scores per field
    field_confidences: dict[str, float] = Field(default_factory=dict)

    # Warnings and suggestions
    warnings: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()

    # Inference metadata
    sample_size: int = 0
    inference_time_ms: float = 0.0

    @property
    def schema(self) -> DataSchema:
        """Backwards-compatible accessor for callers using ``result.schema``."""
        return self.inferred_schema

    @property
    def overall_confidence(self) -> float:
        """Average confidence across all fields."""
        if not self.field_confidences:
            return 0.0
        return sum(self.field_confidences.values()) / len(self.field_confidences)
