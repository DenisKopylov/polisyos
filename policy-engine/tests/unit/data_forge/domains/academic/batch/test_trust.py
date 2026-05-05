"""Tests for academic trust scoring."""

from __future__ import annotations

from polisyos.data_forge.domains.academic.trust import (
    DESIGN_TIERS,
    compute_trust_score,
    design_tier_int,
)


def test_trust_score_meta_analysis_high_citations() -> None:
    score = compute_trust_score(
        study_design="meta-analysis",
        cited_by_count=500,
        publication_year=2023,
    )
    # meta_analysis (1.0 * 0.5) + citations (1.0 * 0.25) + recency ((23/25) * 0.15)
    assert score > 0.85


def test_trust_score_ols_old_low_citations() -> None:
    score = compute_trust_score(
        study_design="ols",
        cited_by_count=5,
        publication_year=2001,
    )
    assert score < 0.3


def test_trust_score_with_sample_size() -> None:
    with_sample = compute_trust_score(
        study_design="rct",
        cited_by_count=100,
        publication_year=2020,
        sample_size=10000,
    )
    without_sample = compute_trust_score(
        study_design="rct",
        cited_by_count=100,
        publication_year=2020,
    )
    assert with_sample > without_sample


def test_trust_score_unknown_design() -> None:
    score = compute_trust_score(study_design="unknown_method")
    assert 0.0 <= score <= 1.0


def test_trust_score_boundaries() -> None:
    # Minimum possible
    score_min = compute_trust_score(
        study_design="",
        cited_by_count=0,
        publication_year=1990,
    )
    assert score_min >= 0.0

    # Maximum possible
    score_max = compute_trust_score(
        study_design="meta-analysis",
        cited_by_count=1000,
        publication_year=2025,
        sample_size=100000,
    )
    assert score_max <= 1.0


def test_design_tier_int_values() -> None:
    assert design_tier_int("meta-analysis") == 5
    assert design_tier_int("rct") == 4
    assert design_tier_int("ols") == 1
    assert design_tier_int("") == 0
    assert design_tier_int("unknown") == 0


def test_design_tiers_all_in_range() -> None:
    for design, score in DESIGN_TIERS.items():
        assert 0.0 <= score <= 1.0, f"{design}: {score}"
