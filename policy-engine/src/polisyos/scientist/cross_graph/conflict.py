"""Evidence conflict detection and resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from polisyos.ir.analytics.cross_graph import (
    CrossGraphDiagnostic,
    EvidenceNeed,
    EvidenceStatus,
)


class ConflictSeverity(str, Enum):
    """Conflict severity public type."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionStrategy(str, Enum):
    """Resolution strategy data model."""
    ACCEPT_MAJORITY = "accept_majority"
    ACCEPT_HIGHEST_QUALITY = "accept_highest_quality"
    ESCALATE = "escalate"
    MARK_MIXED = "mark_mixed"


@dataclass(frozen=True)
class EvidenceConflict:
    """A detected conflict between evidence sources."""

    need_id: str
    dimension: str
    conflicting_sources: list[str]
    severity: ConflictSeverity
    description: str


@dataclass(frozen=True)
class ConflictResolution:
    """Resolution decision for a conflict."""

    conflict: EvidenceConflict
    strategy: ResolutionStrategy
    resolved_status: str
    confidence_penalty: float
    rationale: str


class ConflictDetector:
    """Detects and resolves conflicts across evidence dimensions."""

    def detect(
        self,
        need: EvidenceNeed,
        dimension_results: dict[str, Any],
    ) -> list[EvidenceConflict]:
        """Detect conflicts between gatherer results for a need."""
        conflicts: list[EvidenceConflict] = []

        # Check legal vs evidence alignment
        legal = dimension_results.get("legal", {})
        academic = dimension_results.get("academic", {})

        legal_status = legal.get("status", "")
        academic_status = academic.get("status", "")

        if legal_status == "prohibited" and academic_status in ("supported", "mixed"):
            conflicts.append(EvidenceConflict(
                need_id=need.need_id,
                dimension="legal_vs_academic",
                conflicting_sources=["legal", "academic"],
                severity=ConflictSeverity.HIGH,
                description="Legal prohibits what academic evidence supports",
            ))

        if legal_status == "allowed" and academic_status == "unsupported":
            conflicts.append(EvidenceConflict(
                need_id=need.need_id,
                dimension="legal_vs_academic",
                conflicting_sources=["legal", "academic"],
                severity=ConflictSeverity.MEDIUM,
                description="Legally allowed but lacks academic support",
            ))

        # Dataset vs academic conflict
        dataset_status = dimension_results.get("dataset", {}).get("status", "")
        if dataset_status == "missing" and academic_status == "supported":
            conflicts.append(EvidenceConflict(
                need_id=need.need_id,
                dimension="dataset_vs_academic",
                conflicting_sources=["dataset", "academic"],
                severity=ConflictSeverity.MEDIUM,
                description="Academic evidence exists but dataset unavailable",
            ))

        return conflicts

    def resolve(
        self,
        conflict: EvidenceConflict,
        *,
        strategy: ResolutionStrategy | None = None,
    ) -> ConflictResolution:
        """Resolve a detected conflict."""
        if strategy is None:
            strategy = self._default_strategy(conflict)

        penalty = self._severity_penalty(conflict.severity)

        if strategy == ResolutionStrategy.ESCALATE:
            return ConflictResolution(
                conflict=conflict,
                strategy=strategy,
                resolved_status="requires_review",
                confidence_penalty=penalty,
                rationale="Conflict escalated for expert review",
            )

        if strategy == ResolutionStrategy.MARK_MIXED:
            return ConflictResolution(
                conflict=conflict,
                strategy=strategy,
                resolved_status="mixed",
                confidence_penalty=penalty * 0.5,
                rationale="Marked as mixed evidence",
            )

        return ConflictResolution(
            conflict=conflict,
            strategy=strategy,
            resolved_status="resolved",
            confidence_penalty=penalty * 0.3,
            rationale=f"Resolved via {strategy.value}",
        )

    @staticmethod
    def _default_strategy(conflict: EvidenceConflict) -> ResolutionStrategy:
        if conflict.severity == ConflictSeverity.CRITICAL:
            return ResolutionStrategy.ESCALATE
        if conflict.severity == ConflictSeverity.HIGH:
            return ResolutionStrategy.MARK_MIXED
        return ResolutionStrategy.ACCEPT_HIGHEST_QUALITY

    @staticmethod
    def _severity_penalty(severity: ConflictSeverity) -> float:
        return {
            ConflictSeverity.LOW: 0.05,
            ConflictSeverity.MEDIUM: 0.10,
            ConflictSeverity.HIGH: 0.20,
            ConflictSeverity.CRITICAL: 0.35,
        }.get(severity, 0.10)
