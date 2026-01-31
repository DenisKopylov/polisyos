"""
Data quality report structures and evidence integration.

Defines the output format for quality validation and helpers for
summaries and evidence payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from polisyos.ir.connectors import QualityTier


class FreshnessLevel(Enum):
    """Freshness classification levels."""

    FRESH = "fresh"  # Within expected TTL
    HEALTHY = "healthy"  # Slightly stale but acceptable
    STALE = "stale"  # Exceeds TTL, quality degraded
    EXPIRED = "expired"  # Critically outdated, unusable

    def __lt__(self, other: "FreshnessLevel") -> bool:
        order = [
            FreshnessLevel.EXPIRED,
            FreshnessLevel.STALE,
            FreshnessLevel.HEALTHY,
            FreshnessLevel.FRESH,
        ]
        return order.index(self) < order.index(other)


@dataclass(frozen=True)
class FreshnessStatus:
    """Result of freshness check."""

    level: FreshnessLevel
    cache_age_seconds: int
    data_age_seconds: int | None
    ttl_seconds: int
    schedule: str
    last_updated: datetime | None
    fetched_at: datetime
    message: str

    @property
    def is_fresh(self) -> bool:
        return self.level in (FreshnessLevel.FRESH, FreshnessLevel.HEALTHY)


@dataclass(frozen=True)
class RuleViolation:
    """Single quality rule violation."""

    rule_type: str
    field_name: str | None
    severity: str
    message: str
    expected: Any
    actual: Any
    sample_values: list[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "field_name": self.field_name,
            "severity": self.severity,
            "message": self.message,
            "expected": str(self.expected),
            "actual": str(self.actual),
            "sample_values": self.sample_values,
        }


@dataclass
class CompletenessResult:
    """Result of completeness analysis."""

    score: float
    field_completeness: dict[str, float]
    violations: list[RuleViolation]
    gaps_detected: int = 0
    penalty: float = 0.0
    hard_fail: bool = False


@dataclass
class ConsistencyResult:
    """Result of consistency checks."""

    score: float
    violations: list[RuleViolation]
    penalty: float = 0.0
    hard_fail: bool = False


@dataclass
class DataQualityReport:
    """
    Comprehensive quality validation report.

    Integrates with:
    - QualityIndicators (existing system)
    - QualityGatePass (governance)
    - EvidenceBundle (audit trail)
    """

    # Identification
    dataset_id: str
    schema_id: str
    validated_at: datetime

    # Scoring
    score: float
    tier: QualityTier
    grade: str

    # Components
    freshness_status: FreshnessStatus
    completeness_score: float
    consistency_score: float

    # Issues
    violations: list[RuleViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Integration with existing system
    quality_indicators: Any = None

    # Metadata
    row_count: int = 0
    sampled: bool = False
    sample_size: int | None = None

    def to_evidence(self) -> dict[str, Any]:
        """
        Convert quality report to evidence payload.

        The caller can attach this payload to an EvidenceBundle
        or persist it separately.
        """
        return {
            "evidence_type": "quality_validation",
            "source_id": self.dataset_id,
            "version": self.validated_at.isoformat(),
            "metadata": {
                "score": round(self.score, 4),
                "tier": self.tier.value,
                "grade": self.grade,
                "violations": len(self.violations),
                "sampled": self.sampled,
                "freshness_level": self.freshness_status.level.value,
                "completeness_score": round(self.completeness_score, 4),
                "consistency_score": round(self.consistency_score, 4),
            },
            "content_hash": self._compute_hash(),
        }

    def _compute_hash(self) -> str:
        """Compute content hash for CAS storage."""
        import hashlib
        import json

        payload = {
            "dataset_id": self.dataset_id,
            "validated_at": self.validated_at.isoformat(),
            "score": round(self.score, 4),
            "tier": self.tier.value,
            "violations": [
                {
                    "rule_type": v.rule_type,
                    "field_name": v.field_name,
                    "severity": v.severity,
                }
                for v in self.violations
            ],
        }

        content = json.dumps(payload, sort_keys=True)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Quality Report: {self.dataset_id}",
            f"  Score: {self.score:.2f} ({self.grade}) - {self.tier.value.upper()}",
            f"  Freshness: {self.freshness_status.level.value.upper()}",
            f"  Completeness: {self.completeness_score:.2%}",
            f"  Consistency: {self.consistency_score:.2%}",
        ]

        if self.violations:
            lines.append(f"  Violations: {len(self.violations)}")
            for v in self.violations[:3]:
                lines.append(f"    - {v.message}")
            if len(self.violations) > 3:
                lines.append(f"    ... and {len(self.violations) - 3} more")

        if self.sampled:
            lines.append(
                f"  Note: Validated on sample of {self.sample_size}/{self.row_count} rows"
            )

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        return {
            "dataset_id": self.dataset_id,
            "schema_id": self.schema_id,
            "validated_at": self.validated_at.isoformat(),
            "score": self.score,
            "tier": self.tier.value,
            "grade": self.grade,
            "freshness": {
                "level": self.freshness_status.level.value,
                "cache_age_seconds": self.freshness_status.cache_age_seconds,
                "data_age_seconds": self.freshness_status.data_age_seconds,
                "message": self.freshness_status.message,
            },
            "completeness_score": self.completeness_score,
            "consistency_score": self.consistency_score,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
            "row_count": self.row_count,
            "sampled": self.sampled,
            "sample_size": self.sample_size,
        }

    @property
    def is_acceptable(self) -> bool:
        return self.tier in (
            QualityTier.PLATINUM,
            QualityTier.GOLD,
            QualityTier.SILVER,
        )

    @property
    def needs_attention(self) -> bool:
        return self.tier == QualityTier.BRONZE or any(
            v.severity == "error" for v in self.violations
        )
