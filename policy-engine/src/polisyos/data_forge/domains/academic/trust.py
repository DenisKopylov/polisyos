"""Trust scoring for academic works and parameter estimates."""

from __future__ import annotations

DESIGN_TIERS: dict[str, float] = {
    "meta_analysis": 1.0,
    "systematic_review": 0.95,
    "rct": 0.9,
    "iv": 0.8,
    "did": 0.75,
    "rdd": 0.75,
    "fe": 0.6,
    "ols": 0.4,
    "descriptive": 0.2,
    "": 0.3,
}

DESIGN_TIER_INT: dict[str, int] = {
    "meta_analysis": 5,
    "systematic_review": 5,
    "rct": 4,
    "iv": 3,
    "did": 3,
    "rdd": 3,
    "fe": 2,
    "ols": 1,
    "descriptive": 0,
    "": 0,
}


def compute_trust_score(
    *,
    study_design: str = "",
    cited_by_count: int = 0,
    publication_year: int = 2000,
    sample_size: int | None = None,
) -> float:
    """Compute a trust score in [0, 1] for an academic work/estimate.

    Weights:
      study_design_tier × 0.5
      + normalized_citations × 0.25
      + recency × 0.15
      + sample_size × 0.1
    """
    design_key = study_design.lower().replace("-", "_").replace(" ", "_")
    design_score = DESIGN_TIERS.get(design_key, 0.3)

    citation_score = min(cited_by_count / 500, 1.0) if cited_by_count > 0 else 0.0

    recency = max(0.0, (publication_year - 2000) / 25)
    recency = min(recency, 1.0)

    n = sample_size or 0
    sample_score = min(n / 10_000, 1.0) if n > 0 else 0.0

    score = design_score * 0.5 + citation_score * 0.25 + recency * 0.15 + sample_score * 0.1
    return min(max(score, 0.0), 1.0)


def design_tier_int(study_design: str) -> int:
    """Integer tier for a study design (0-5, higher = more rigorous)."""
    design_key = study_design.lower().replace("-", "_").replace(" ", "_")
    return DESIGN_TIER_INT.get(design_key, 0)
