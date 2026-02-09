"""
Configuration models for schema inference.

Contains Pydantic models that control inference behavior and
user-provided hints to guide the inference process.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.connectors.contracts.schema import (
    GeoGranularity,
    SchemaType,
    SemanticType,
    TimeGranularity,
)

__all__ = [
    "InferenceConfig",
    "SchemaHints",
]


class InferenceConfig(BaseModel):
    """Configuration for schema inference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Sampling
    sample_rows: int = Field(default=1000, ge=100, le=100000)

    # Type inference thresholds
    null_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Above this null ratio, field is considered nullable",
    )
    category_threshold: int = Field(
        default=50,
        ge=2,
        le=1000,
        description="Below this unique count, infer CATEGORY",
    )
    category_ratio_threshold: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="Max ratio of unique values to total for CATEGORY",
    )

    # Float handling
    prefer_float32: bool = Field(
        default=True,
        description="Prefer FLOAT32 when inference detects floating-point data",
    )

    # Pattern detection
    datetime_patterns: tuple[str, ...] = (
        r"\d{4}-\d{2}-\d{2}",  # ISO date
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO datetime
        r"\d{2}/\d{2}/\d{4}",  # US date
        r"\d{2}\.\d{2}\.\d{4}",  # European date
    )

    # Confidence thresholds
    min_pattern_confidence: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Minimum match rate for pattern-based inference",
    )


class SchemaHints(BaseModel):
    """User-provided hints to guide inference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Explicit type overrides
    field_types: dict[str, SchemaType] = Field(default_factory=dict)
    field_units: dict[str, str] = Field(default_factory=dict)
    field_semantic_types: dict[str, SemanticType] = Field(default_factory=dict)

    # Structure hints
    primary_key: tuple[str, ...] = ()
    time_dimension: str | None = None
    geo_dimension: str | None = None

    # Granularity hints
    time_granularity: TimeGranularity | None = None
    geo_granularity: GeoGranularity | None = None

    # Fields to exclude
    exclude_fields: frozenset[str] = frozenset()
