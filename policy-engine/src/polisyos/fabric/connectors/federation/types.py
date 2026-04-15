"""
Federation types and data contracts for multi-source composition.

Defines the core data structures used by the federation layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.fabric.connectors.base import FetchRequest
from polisyos.fabric.connectors.contracts.schema import DataSchema
from polisyos.fabric.connectors.quality.report import DataQualityReport
from polisyos.fabric.finite import ensure_probability
from polisyos.fabric.temporal import utc_now
from polisyos.ir.connectors import ConnectorMetadataSpec, TrustLevel

if TYPE_CHECKING:
    from polisyos.core.contracts.fabric import EvidenceBundle


class CompositionStrategy(str, Enum):
    """Strategies for combining data from multiple sources."""

    UNION = "union"  # Temporal splicing: append rows from different periods
    JOIN = "join"  # Column enrichment: merge on keys
    OVERLAY = "overlay"  # Coalesce: A base, B fills nulls
    CONSENSUS = "consensus"  # Statistical aggregation: mean/median/mode


class ConflictPolicy(str, Enum):
    """Policies for resolving conflicts when multiple sources overlap."""

    TRUST_HIGHEST = "trust_highest"  # Prefer higher TrustLevel
    MOST_RECENT = "most_recent"  # Prefer freshest timestamp
    MANUAL_PRIORITY = "manual_priority"  # User-defined source ranking
    MEDIAN = "median"  # Statistical consensus across sources
    FIRST_AVAILABLE = "first_available"  # First non-null value wins


class AuditLevel(str, Enum):
    """Controls the level of merge logging produced by federation."""

    FULL = "full"
    SUMMARY = "summary"
    NONE = "none"


@dataclass(frozen=True)
class CompositionRequest:
    """Request to compose data from multiple sources."""

    dataset_pattern: str  # e.g., "ukraine.gdp"
    strategy: CompositionStrategy
    conflict_policy: ConflictPolicy

    # For UNION strategy
    time_dimension: str | None = None

    # For JOIN strategy
    join_keys: list[str] | None = None
    join_how: Literal["inner", "left", "outer"] = "outer"

    # For OVERLAY strategy
    primary_source: str | None = None

    # For CONSENSUS strategy
    aggregation_func: Literal["mean", "median", "mode"] | None = "median"

    # Source preferences
    manual_priorities: dict[str, int] | None = None  # connector_id -> priority

    # Constraints
    min_trust_level: TrustLevel = TrustLevel.LOW
    max_staleness: timedelta | None = None

    # Schema hints
    key_columns: list[str] | None = None
    schema: DataSchema | None = None

    # Audit and determinism
    audit_level: AuditLevel = AuditLevel.SUMMARY
    audit_sample_size: int = 50
    audit_max_entries: int = 5_000
    audit_seed: str | None = None
    strict_conflicts: bool = False
    tie_breaker_seed: str | None = None

    # Column-level overrides
    column_policies: dict[str, ConflictPolicy] | None = None
    column_aggregation_funcs: dict[str, Literal["mean", "median", "mode"]] | None = None

    # Planner hints
    max_primary_sources: int | None = None
    max_fallback_sources: int = 2


@dataclass(frozen=True)
class CoverageProfile:
    """Coverage hints for a dataset from a specific connector."""

    dataset_id: str
    time_range: tuple[datetime | None, datetime | None] = (None, None)
    columns: frozenset[str] = frozenset()
    key_columns: tuple[str, ...] = ()
    time_dimension: str | None = None
    completeness: dict[str, float] = field(default_factory=dict)
    row_count: int | None = None

    def has_time_range(self) -> bool:
        return self.time_range[0] is not None or self.time_range[1] is not None


@dataclass
class SourceMetadata:
    """Metadata about a source used in composition."""

    connector_id: str
    metadata: ConnectorMetadataSpec
    fetched_at: datetime
    row_count: int
    quality_report: DataQualityReport | None = None
    last_updated: datetime | None = None
    observed_latency_ms: float | None = None
    coverage: CoverageProfile | None = None


@dataclass
class MergeLogEntry:
    """Log entry for a single conflict resolution decision."""

    # Location
    row_index: int | None = None
    row_key: dict[str, Any] | None = None
    column: str | None = None
    conflict_type: str = "value_mismatch"  # overlap, duplicate_column, etc.

    # Sources involved
    source_a_id: str = ""
    source_a_value: Any = None
    source_a_trust: TrustLevel = TrustLevel.UNVERIFIED

    source_b_id: str = ""
    source_b_value: Any = None
    source_b_trust: TrustLevel = TrustLevel.UNVERIFIED

    # Resolution
    chosen_source: str = ""
    chosen_value: Any = None
    resolution_reason: str = ""
    resolution_policy: str | None = None

    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        row_key = None
        if self.row_key:
            row_key = {k: str(self.row_key[k]) for k in sorted(self.row_key)}
        return {
            "row_index": self.row_index,
            "row_key": row_key,
            "column": self.column,
            "conflict_type": self.conflict_type,
            "source_a": {
                "id": self.source_a_id,
                "value": str(self.source_a_value),
                "trust": self.source_a_trust.name,
            },
            "source_b": {
                "id": self.source_b_id,
                "value": str(self.source_b_value),
                "trust": self.source_b_trust.name,
            },
            "resolution": {
                "chosen_source": self.chosen_source,
                "chosen_value": str(self.chosen_value),
                "reason": self.resolution_reason,
                "policy": self.resolution_policy,
            },
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class MergeLogSummary:
    """Aggregated summary of conflict resolutions."""

    total_conflicts: int = 0
    by_policy: dict[str, int] = field(default_factory=dict)
    by_conflict_type: dict[str, int] = field(default_factory=dict)
    by_column: dict[str, int] = field(default_factory=dict)
    by_source_pair: dict[str, int] = field(default_factory=dict)
    sample_entries: list[MergeLogEntry] = field(default_factory=list)
    sample_seed: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompositionResult:
    """Result of multi-source data composition."""

    data: pd.DataFrame
    strategy: CompositionStrategy
    sources_used: list[SourceMetadata]

    # Provenance
    evidence_bundle: EvidenceBundle | None = None
    merge_log: list[MergeLogEntry] = field(default_factory=list)
    merge_summary: MergeLogSummary | None = None

    # Quality
    quality_report: DataQualityReport | None = None

    # Metadata
    composed_at: datetime = field(default_factory=utc_now)
    execution_time_ms: float = 0.0

    def summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        return {
            "strategy": self.strategy.value,
            "num_sources": len(self.sources_used),
            "num_rows": len(self.data),
            "num_columns": len(self.data.columns),
            "num_conflicts": len(self.merge_log),
            "execution_time_ms": self.execution_time_ms,
            "sources": [s.connector_id for s in self.sources_used],
        }


@dataclass
class ConflictCandidate:
    """A candidate value in a conflict resolution scenario."""

    source_id: str
    value: Any
    metadata: SourceMetadata
    row_index: int | None = None
    row_key: dict[str, Any] | None = None
    column: str | None = None


@dataclass
class ConflictContext:
    """Context for resolving a conflict."""

    request: CompositionRequest
    row_index: int | None = None
    row_key: dict[str, Any] | None = None
    column: str | None = None
    conflict_type: str = "value_mismatch"


@dataclass
class ConflictResolution:
    """Result of conflict resolution."""

    chosen_candidate: ConflictCandidate
    reasoning: str
    all_candidates: list[ConflictCandidate] = field(default_factory=list)
    log_entry: MergeLogEntry | None = None


class RankingWeights(BaseModel):
    """Weights for multi-factor source ranking."""

    model_config = ConfigDict(frozen=True)

    trust: float = Field(default=0.4, ge=0.0, le=1.0)
    completeness: float = Field(default=0.3, ge=0.0, le=1.0)
    freshness: float = Field(default=0.2, ge=0.0, le=1.0)
    latency: float = Field(default=0.1, ge=0.0, le=1.0)

    @field_validator("trust", "completeness", "freshness", "latency", mode="after")
    @classmethod
    def _validate_finite_weight(cls, value: float) -> float:
        return ensure_probability(value, what="ranking weight")

    def validate_sum(self) -> None:
        """Ensure weights sum to approximately 1.0."""
        total = self.trust + self.completeness + self.freshness + self.latency
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total}")


@dataclass
class RankedSource:
    """A connector ranked by relevance to a composition request."""

    connector_id: str
    metadata: ConnectorMetadataSpec
    relevance_score: float  # 0.0-1.0
    score_components: dict[str, float]  # trust, completeness, freshness, latency
    quality_report: DataQualityReport | None = None
    coverage: CoverageProfile | None = None


@dataclass
class PlannedSource:
    """A source to fetch as part of an execution plan."""

    connector_id: str
    metadata: ConnectorMetadataSpec
    fetch_request: FetchRequest

    # Ranking
    relevance_score: float
    score_components: dict[str, float]

    # Coverage hints
    coverage: CoverageProfile | None = None

    # Optimization hints
    expected_row_count: int | None = None
    expected_latency_ms: float | None = None


@dataclass
class ExecutionPlan:
    """Plan for executing a multi-source composition."""

    request: CompositionRequest

    # Ordered list of sources to fetch
    primary_sources: list[PlannedSource]
    fallback_sources: list[PlannedSource] = field(default_factory=list)

    # Optimization hints
    can_parallelize: bool = True
    estimated_cost_ms: float | None = None

    # Provenance
    planning_timestamp: datetime = field(default_factory=utc_now)
    planner_version: str = "1.0"

    def total_sources(self) -> int:
        """Get total number of sources (primary + fallback)."""
        return len(self.primary_sources) + len(self.fallback_sources)


# Custom exceptions
class FederationError(Exception):
    """Base exception for federation errors."""


class SchemaIncompatibilityError(FederationError):
    """Raised when source schemas are incompatible for composition."""


class ConflictResolutionError(FederationError):
    """Raised when a conflict cannot be resolved."""


class PlanningError(FederationError):
    """Raised when execution plan cannot be generated."""
