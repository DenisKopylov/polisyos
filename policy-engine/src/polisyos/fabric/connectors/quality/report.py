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

from polisyos.core.canon import content_hash
from polisyos.fabric.numerics.finite import ensure_non_negative_finite, ensure_probability
from polisyos.ir.connectors import QualityTier

from .statistics import (
    AnomalyReport,
    DatasetProfile,
    DriftReport,
    QualityContractResult,
    QualityTrendReport,
)


class FreshnessLevel(Enum):
    """Freshness classification levels."""

    FRESH = "fresh"  # Within expected TTL
    HEALTHY = "healthy"  # Slightly stale but acceptable
    STALE = "stale"  # Exceeds TTL, quality degraded
    EXPIRED = "expired"  # Critically outdated, unusable

    def __lt__(self, other: FreshnessLevel) -> bool:
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

    def __post_init__(self) -> None:
        for name in ("cache_age_seconds", "ttl_seconds"):
            ensure_non_negative_finite(getattr(self, name), what=name)
        if self.data_age_seconds is not None:
            ensure_non_negative_finite(self.data_age_seconds, what="data_age_seconds")

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
    applicable: bool = True
    confidence: float = 1.0
    not_applicable_reason: str | None = None

    def __post_init__(self) -> None:
        self.score = ensure_probability(self.score, what="completeness score")
        self.field_completeness = {
            field_name: ensure_probability(value, what=f"field completeness {field_name}")
            for field_name, value in self.field_completeness.items()
        }
        self.penalty = ensure_non_negative_finite(self.penalty, what="completeness penalty")
        self.confidence = ensure_probability(self.confidence, what="completeness confidence")
        if self.gaps_detected < 0:
            raise ValueError("gaps_detected must be >= 0")


@dataclass
class ConsistencyResult:
    """Result of consistency checks."""

    score: float
    violations: list[RuleViolation]
    penalty: float = 0.0
    hard_fail: bool = False

    def __post_init__(self) -> None:
        self.score = ensure_probability(self.score, what="consistency score")
        self.penalty = ensure_non_negative_finite(self.penalty, what="consistency penalty")


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
    avg_latency_ms: float | None = None
    source_id: str | None = None
    component_scores: dict[str, float] = field(default_factory=dict)
    dataset_profile: DatasetProfile | None = None
    anomaly_report: AnomalyReport | None = None
    drift_report: DriftReport | None = None
    quality_contract_result: QualityContractResult | None = None
    trend_report: QualityTrendReport | None = None

    def __post_init__(self) -> None:
        self.score = ensure_probability(self.score, what="quality score")
        self.completeness_score = ensure_probability(
            self.completeness_score,
            what="quality completeness_score",
        )
        self.consistency_score = ensure_probability(
            self.consistency_score,
            what="quality consistency_score",
        )
        self.row_count = int(ensure_non_negative_finite(self.row_count, what="row_count"))
        if self.sample_size is not None:
            self.sample_size = int(
                ensure_non_negative_finite(self.sample_size, what="sample_size")
            )
        if self.avg_latency_ms is not None:
            self.avg_latency_ms = ensure_non_negative_finite(
                self.avg_latency_ms,
                what="avg_latency_ms",
            )
        self.component_scores = {
            str(name): ensure_probability(value, what=f"quality component score {name}", clamp=True)
            for name, value in self.component_scores.items()
        }

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
                "anomaly_findings": len(self.anomaly_report.findings) if self.anomaly_report else 0,
                "drift_findings": len(self.drift_report.findings) if self.drift_report else 0,
                "contract_failures": (
                    self.quality_contract_result.failed_rules if self.quality_contract_result else 0
                ),
                "quality_indicators": (
                    self.quality_indicators.to_dict()
                    if hasattr(self.quality_indicators, "to_dict")
                    else self.quality_indicators
                    if isinstance(self.quality_indicators, dict)
                    else None
                ),
            },
            "content_hash": self._compute_hash(),
        }

    def _compute_hash(self) -> str:
        """Compute content hash for CAS storage."""
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
            "component_scores": dict(self.component_scores),
            "quality_indicators": (
                self.quality_indicators.to_dict()
                if hasattr(self.quality_indicators, "to_dict")
                else self.quality_indicators
                if isinstance(self.quality_indicators, dict)
                else None
            ),
            "anomaly_findings": (
                [finding.to_dict() for finding in self.anomaly_report.findings]
                if self.anomaly_report
                else []
            ),
            "drift_findings": (
                [finding.to_dict() for finding in self.drift_report.findings]
                if self.drift_report
                else []
            ),
        }

        content = json.dumps(payload, sort_keys=True)
        return content_hash(content, prefix=True)

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

        if self.dataset_profile is not None:
            lines.append(f"  Profile Score: {self.dataset_profile.profile_score:.2%}")

        if self.anomaly_report is not None and self.anomaly_report.findings:
            lines.append(
                f"  Anomalies: {len(self.anomaly_report.findings)} "
                f"(worst rate {self.anomaly_report.overall_anomaly_rate:.2%})"
            )

        if self.drift_report is not None and self.drift_report.findings:
            lines.append(
                f"  Drift Findings: {len(self.drift_report.findings)} "
                f"(score {self.drift_report.score:.2%})"
            )

        if self.quality_contract_result is not None and not self.quality_contract_result.passed:
            lines.append(
                "  Contract Failures: "
                f"{self.quality_contract_result.failed_rules}/"
                f"{self.quality_contract_result.evaluated_rules}"
            )

        if self.trend_report is not None and self.trend_report.score_delta is not None:
            lines.append(f"  Trend Delta: {self.trend_report.score_delta:+.3f}")

        if self.sampled:
            lines.append(f"  Note: Validated on sample of {self.sample_size}/{self.row_count} rows")

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
            "source_id": self.source_id,
            "component_scores": dict(self.component_scores),
            "dataset_profile": (
                self.dataset_profile.to_dict() if self.dataset_profile is not None else None
            ),
            "anomaly_report": (
                self.anomaly_report.to_dict() if self.anomaly_report is not None else None
            ),
            "drift_report": (
                self.drift_report.to_dict() if self.drift_report is not None else None
            ),
            "quality_contract_result": (
                self.quality_contract_result.to_dict()
                if self.quality_contract_result is not None
                else None
            ),
            "trend_report": (
                self.trend_report.to_dict() if self.trend_report is not None else None
            ),
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
