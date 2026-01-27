"""
Canonical data contract for metric-level type safety.

This module defines the source of truth for metric identity,
preventing hallucination of metric names, types, and units.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DataType(str, Enum):
    """Supported data types for metrics."""

    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    ARRAY = "array"
    JSON = "json"  # For nested structures


class PIITier(str, Enum):
    """
    Privacy tier classification.

    Determines access controls and aggregation requirements.
    """

    NONE = "none"  # Public data, no restrictions
    LOW = "low"  # Aggregatable, no individual exposure
    MEDIUM = "medium"  # Requires k-anonymization (k>=5)
    HIGH = "high"  # Restricted access, audit required
    CRITICAL = "critical"  # PII/PHI, explicit consent required


class Granularity(str, Enum):
    """Temporal or entity granularity of the metric."""

    TICK = "tick"  # Every simulation step
    DAILY = "daily"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    AGENT = "agent-level"  # Per-agent metric
    AGGREGATE = "aggregate"  # Economy-wide aggregate


# Regex pattern for valid metric IDs
METRIC_ID_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$"


class DataContract(BaseModel):
    """
    Canonical contract for a single metric.

    This is the "source of truth" for metric identity. The Scientist
    agent cannot request metrics by arbitrary name -- only by validated
    binding derived from this contract.

    Attributes:
        metric_id: Canonical unique identifier (e.g., "us.macro.gdp_nominal")
        display_name: Human-readable name for UI/reports
        description: Detailed description of what this metric represents
        dtype: Data type (int, float, string, etc.)
        unit: Unit of measurement (e.g., "USD", "ratio", "percent")
        granularity: Temporal/entity granularity
        dimensions: List of dimension columns (e.g., ["region", "sector"])
        valid_range: Optional (min, max) bounds for validation
        source_system: Origin system or file
        source_table: Source table name within the system
        source_column: Original column name in source
        jurisdiction: Legal jurisdiction for compliance (e.g., "US", "EU")
        pii_tier: Privacy classification
        aliases: Alternative names for search/disambiguation
        tags: Free-form tags for categorization
        deprecated: Whether this metric is deprecated
        superseded_by: Metric ID that replaces this one if deprecated
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,  # Immutable after creation
        str_strip_whitespace=True,
    )

    # Identity
    metric_id: Annotated[
        str,
        Field(
            pattern=METRIC_ID_PATTERN,
            description="Canonical unique identifier (lowercase, dot-separated)",
            examples=["us.macro.gdp_nominal", "agent.income.salary"],
        ),
    ]
    display_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Human-readable display name",
        ),
    ]
    description: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Detailed description of the metric",
        ),
    ]

    # Type information
    dtype: DataType
    unit: str | None = Field(
        default=None,
        max_length=50,
        description="Unit of measurement",
    )
    granularity: Granularity | None = None

    # Dimensions and validation
    dimensions: List[str] = Field(
        default_factory=list,
        description="Dimension columns for slicing",
    )
    valid_range: tuple[float, float] | None = Field(
        default=None,
        description="Optional (min, max) bounds for validation",
    )

    # Provenance
    source_system: str = Field(
        ...,
        description="Origin system or file path",
    )
    source_table: str | None = Field(
        default=None,
        description="Source table name",
    )
    source_column: str | None = Field(
        default=None,
        description="Original column name in source",
    )
    jurisdiction: str | None = Field(
        default=None,
        max_length=10,
        description="Legal jurisdiction code (ISO 3166-1)",
    )

    # Privacy
    pii_tier: PIITier = PIITier.NONE

    # Search & disambiguation
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternative names for search",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Free-form categorization tags",
    )

    # Lifecycle
    deprecated: bool = False
    superseded_by: str | None = Field(
        default=None,
        pattern=METRIC_ID_PATTERN,
        description="Replacement metric if deprecated",
    )

    @field_validator("aliases", mode="before")
    @classmethod
    def normalize_aliases(cls, v: List[str] | None) -> List[str]:
        """Normalize aliases to lowercase for consistent matching."""

        if v is None:
            return []
        return [alias.lower().strip() for alias in v if alias.strip()]

    @field_validator("valid_range", mode="before")
    @classmethod
    def validate_range(
        cls, v: tuple[float, float] | None
    ) -> tuple[float, float] | None:
        """Ensure min <= max in valid_range."""

        if v is not None:
            min_val, max_val = v
            if min_val > max_val:
                raise ValueError(
                    f"valid_range min ({min_val}) must be <= max ({max_val})"
                )
        return v

    def __hash__(self) -> int:
        """Hash based on metric_id for set/dict operations."""

        return hash(self.metric_id)


class DataContractCollection(BaseModel):
    """
    Collection of data contracts with metadata.

    Stored in data/curated/data_contracts.json
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="1.0",
        pattern=r"^\d+\.\d+$",
    )
    generated_at: str | None = None
    generated_by: str | None = Field(
        default=None,
        description="Tool that generated this collection",
    )
    contracts: List[DataContract] = Field(default_factory=list)

    @field_validator("contracts", mode="after")
    @classmethod
    def validate_unique_ids(cls, contracts: List[DataContract]) -> List[DataContract]:
        """Ensure all metric_ids are unique."""

        seen = set()
        for contract in contracts:
            if contract.metric_id in seen:
                raise ValueError(f"Duplicate metric_id: {contract.metric_id}")
            seen.add(contract.metric_id)
        return contracts
