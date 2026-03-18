"""CausalQualityReport — composite quality score for a causal analysis run.

Aggregates three orthogonal quality dimensions:
    - data_quality   (ESS, overlap, data provenance quality scores)
    - method_quality (fidelity tier, determinism, convergence)
    - robustness     (sensitivity analysis, falsification tests)

into a single composite score and letter grade used for audit, publication
readiness checks, and policy decision support.

Grade thresholds (composite score):
    A ≥ 0.85 — publication-ready
    B ≥ 0.70 — suitable for policy use with caveats
    C ≥ 0.55 — exploratory use only
    D ≥ 0.40 — major quality concerns
    F < 0.40 — unreliable
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_GRADE_THRESHOLDS = [
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
]


def _score_to_grade(score: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


class QualityDimension(BaseModel):
    """Score and breakdown for one quality dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    """Normalised score [0, 1]."""

    grade: str
    """Letter grade: A / B / C / D / F."""

    components: dict[str, float] = Field(default_factory=dict)
    """Individual component scores that were averaged into this dimension's score."""

    warnings: tuple[str, ...] = ()
    """Human-readable warnings about this dimension."""

    is_blocking: bool = False
    """True when score < 0.30 — this dimension blocks a passing composite grade."""


class CausalQualityReport(BaseModel):
    """Composite quality report for a single causal analysis run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    query_str: str = ""

    data_quality: QualityDimension
    method_quality: QualityDimension
    robustness: QualityDimension

    composite_score: float = Field(ge=0.0, le=1.0)
    """Weighted average of the three dimensions."""

    composite_grade: str
    """Letter grade for the composite score."""

    is_publication_ready: bool
    """True when composite ≥ 0.70 AND no dimension is blocking."""

    caveats: tuple[str, ...] = ()
    """Human-readable caveats for policy consumers."""

    weights: dict[str, float] = Field(
        default_factory=lambda: {"data": 0.35, "method": 0.35, "robustness": 0.30}
    )
    """Weights applied to data / method / robustness dimensions."""

    created_at: str = ""

    def to_summary(self) -> str:
        return (
            f"QualityReport[{self.run_id}] "
            f"composite={self.composite_score:.2f} ({self.composite_grade}) "
            f"data={self.data_quality.score:.2f} "
            f"method={self.method_quality.score:.2f} "
            f"robustness={self.robustness.score:.2f} "
            f"pub_ready={self.is_publication_ready}"
        )


__all__ = ["QualityDimension", "CausalQualityReport", "_score_to_grade"]
