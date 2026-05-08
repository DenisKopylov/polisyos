"""Governance evidence payloads for Fabric data-quality reports."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from polisyos.core.canon import content_hash
from polisyos.fabric.quality.quality import QualityIndicators
from polisyos.fabric.numerics.finite import ensure_probability

from .report import DataQualityReport

SCHEMA_VERSION = "fabric.quality.evidence.v1"

__all__ = [
    "FabricQualityGovernanceEvidence",
    "build_fabric_quality_governance_evidence",
]


@dataclass(frozen=True)
class FabricQualityGovernanceEvidence:
    """Normalized payload propagated from Fabric quality into Scientist governance."""

    dataset_id: str
    schema_id: str
    validated_at: str
    score: float
    tier: str
    grade: str
    acceptable: bool
    needs_attention: bool
    quality_indicators: dict[str, Any] | None
    component_scores: Mapping[str, float] = field(default_factory=dict)
    freshness: Mapping[str, Any] = field(default_factory=dict)
    contract: Mapping[str, Any] | None = None
    source_id: str | None = None
    source_evidence_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", ensure_probability(self.score, what="quality score"))
        object.__setattr__(
            self,
            "component_scores",
            {
                str(name): ensure_probability(value, what=f"quality component {name}", clamp=True)
                for name, value in dict(self.component_scores).items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "evidence_type": "fabric_quality_governance",
            "dataset_id": self.dataset_id,
            "schema_id": self.schema_id,
            "source_id": self.source_id,
            "validated_at": self.validated_at,
            "score": self.score,
            "tier": self.tier,
            "grade": self.grade,
            "acceptable": self.acceptable,
            "needs_attention": self.needs_attention,
            "quality_indicators": self.quality_indicators,
            "component_scores": dict(self.component_scores),
            "freshness": dict(self.freshness),
            "contract": dict(self.contract) if self.contract is not None else None,
            "source_evidence_hash": self.source_evidence_hash,
        }
        payload["content_hash"] = content_hash(
            json.dumps(payload, sort_keys=True, default=str),
            prefix=True,
        )
        return payload


def build_fabric_quality_governance_evidence(
    report: DataQualityReport,
) -> FabricQualityGovernanceEvidence:
    """Build a stable Scientist-governance payload from a Fabric quality report."""

    source_evidence = report.to_evidence()
    quality_indicators = report.quality_indicators
    if isinstance(quality_indicators, QualityIndicators) or hasattr(quality_indicators, "to_dict"):
        indicators_payload = quality_indicators.to_dict()
    elif isinstance(quality_indicators, dict):
        indicators_payload = dict(quality_indicators)
    else:
        try:
            indicators_payload = QualityIndicators.from_quality_report(report).to_dict()
        except Exception:
            indicators_payload = None

    contract_payload = (
        report.quality_contract_result.to_dict()
        if report.quality_contract_result is not None
        else None
    )

    freshness = {
        "level": report.freshness_status.level.value,
        "is_fresh": report.freshness_status.is_fresh,
        "cache_age_seconds": report.freshness_status.cache_age_seconds,
        "data_age_seconds": report.freshness_status.data_age_seconds,
        "ttl_seconds": report.freshness_status.ttl_seconds,
        "message": report.freshness_status.message,
    }

    return FabricQualityGovernanceEvidence(
        dataset_id=report.dataset_id,
        schema_id=report.schema_id,
        source_id=report.source_id,
        validated_at=report.validated_at.isoformat(),
        score=report.score,
        tier=report.tier.value,
        grade=report.grade,
        acceptable=report.is_acceptable,
        needs_attention=report.needs_attention,
        quality_indicators=indicators_payload,
        component_scores=report.component_scores,
        freshness=freshness,
        contract=contract_payload,
        source_evidence_hash=str(source_evidence.get("content_hash") or ""),
    )
