"""
Federation layer for multi-source data composition.

Provides intelligent composition of data from multiple sources with conflict
resolution, source ranking, and provenance tracking.
"""

from polisyos.fabric.connectors.federation.composer import DataComposer
from polisyos.fabric.connectors.federation.evidence_aggregation import (
    build_composite_evidence_bundle,
)
from polisyos.fabric.connectors.federation.planner import FederationPlanner
from polisyos.fabric.connectors.federation.ranker import SourceRanker
from polisyos.fabric.connectors.federation.resolver import ConflictResolver
from polisyos.fabric.connectors.federation.types import (
    AuditLevel,
    CompositionRequest,
    CompositionResult,
    CompositionStrategy,
    ConflictCandidate,
    ConflictContext,
    ConflictPolicy,
    ConflictResolution,
    CoverageProfile,
    ExecutionPlan,
    FederationError,
    MergeLogEntry,
    MergeLogSummary,
    PlannedSource,
    PlanningError,
    RankedSource,
    RankingWeights,
    SchemaIncompatibilityError,
    SourceMetadata,
)

__all__ = [
    # Strategies and policies
    "CompositionStrategy",
    "ConflictPolicy",
    "AuditLevel",
    # Request and result
    "CompositionRequest",
    "CompositionResult",
    # Core components
    "DataComposer",
    "ConflictResolver",
    "SourceRanker",
    "FederationPlanner",
    # Planning
    "ExecutionPlan",
    "PlannedSource",
    "RankedSource",
    "RankingWeights",
    # Conflict resolution
    "ConflictCandidate",
    "ConflictContext",
    "ConflictResolution",
    "MergeLogEntry",
    "MergeLogSummary",
    # Evidence
    "build_composite_evidence_bundle",
    # Metadata
    "SourceMetadata",
    "CoverageProfile",
    # Exceptions
    "FederationError",
    "SchemaIncompatibilityError",
    "PlanningError",
]

__version__ = "1.0.0"
