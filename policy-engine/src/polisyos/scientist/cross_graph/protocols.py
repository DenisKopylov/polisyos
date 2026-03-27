"""Protocols for pluggable evidence gatherers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from polisyos.ir.analytics.cross_graph import (
    CanonicalConcept,
    CrossGraphDiagnostic,
    EvidenceNeed,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
)


@dataclass(frozen=True)
class GathererResult:
    """Standardized result from any evidence gatherer."""

    status: str  # status value from the relevant enum
    confidence: float
    diagnostics: list[CrossGraphDiagnostic]
    provenance_refs: list[str]
    metadata: dict[str, Any]


class EvidenceGatherer(Protocol):
    """Protocol for modular evidence gatherers.

    Each gatherer is responsible for a single assessment dimension
    (legal, academic, dataset, transport).
    """

    @property
    def dimension(self) -> str:
        """Identifier for this gatherer's assessment dimension."""
        ...

    def assess(
        self,
        need: EvidenceNeed,
        *,
        concepts: list[CanonicalConcept],
        context: dict[str, Any],
    ) -> GathererResult:
        """Assess a single evidence need.

        Parameters
        ----------
        need:
            The evidence need to assess.
        concepts:
            Resolved canonical concepts for this need.
        context:
            Runtime context (jurisdiction, target_year, adapters, etc.).
        """
        ...


class OntologyResolver(Protocol):
    """Protocol for resolving ontology bridges."""

    def resolve(
        self,
        need: EvidenceNeed,
        *,
        ontology: list[CanonicalConcept],
    ) -> tuple[list[CanonicalConcept], list[Any], list[CrossGraphDiagnostic]]:
        """Resolve matching concepts and bridges for a need."""
        ...


class ConfidenceAggregator(Protocol):
    """Protocol for aggregating per-dimension confidence into overall score."""

    def aggregate(
        self,
        dimension_scores: dict[str, float],
        *,
        requires_expert_review: bool,
    ) -> float:
        ...
