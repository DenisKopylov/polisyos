from __future__ import annotations

from pathlib import Path

from polisyos.datasets.knowledge.variable_alignment import (
    AlignmentMethod,
    align_meta_analytic,
    align_semantic,
    calibrate_alignment_confidence,
    score_variable_pair,
    load_seed_alignments,
    VariableAlignment,
)


def test_load_seed_alignments_contains_core_sources() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )
    alignments = load_seed_alignments(path)
    assert len(alignments) > 0
    dataset_ids = {item.dataset_id for item in alignments}
    assert "WB_WGI" in dataset_ids
    assert "WB_WDI" in dataset_ids
    assert "WVS_W7" in dataset_ids


def test_seed_alignments_use_exact_method_only_for_seed_table() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )
    alignments = load_seed_alignments(path)
    methods = {item.method for item in alignments}
    assert AlignmentMethod.EXACT in methods
    assert AlignmentMethod.SEMANTIC in methods or AlignmentMethod.META_ANALYTIC in methods


def test_semantic_alignment_returns_ranked_matches() -> None:
    matches = align_semantic(
        canonical_var="social_trust",
        dataset_id="WVS_W7",
        candidates=["social trust index", "institutional_quality", "trust_in_government"],
        threshold=0.2,
    )
    assert matches
    assert all(item.method is AlignmentMethod.SEMANTIC for item in matches)
    assert matches[0].dataset_var == "social trust index"
    assert matches[0].confidence >= matches[-1].confidence


def test_semantic_alignment_threshold_filters_out_noise() -> None:
    matches = align_semantic(
        canonical_var="gdp_per_capita",
        dataset_id="WB_WDI",
        candidates=["forest_area", "internet_users", "gdp_per_capita_ppp"],
        threshold=0.55,
    )
    assert len(matches) == 1
    assert matches[0].dataset_var == "gdp_per_capita_ppp"


def test_meta_analytic_alignment_uses_correlation_and_evidence_strength() -> None:
    matches = align_meta_analytic(
        canonical_var="institutional_quality",
        dataset_id="WB_WGI",
        candidates=[
            {
                "dataset_var": "rl_est",
                "correlation": 0.82,
                "evidence_strength": "meta_analysis",
                "n_studies": 18,
                "trust_score": 0.9,
            },
            {
                "dataset_var": "cc_est",
                "correlation": 0.78,
                "evidence_strength": "observational",
                "n_studies": 4,
                "trust_score": 0.6,
            },
        ],
        min_confidence=0.3,
    )
    assert len(matches) == 2
    assert matches[0].dataset_var == "rl_est"
    assert matches[0].confidence > matches[1].confidence
    assert all(item.method is AlignmentMethod.META_ANALYTIC for item in matches)


def test_meta_analytic_alignment_filters_low_confidence() -> None:
    matches = align_meta_analytic(
        canonical_var="informal_economy_share",
        dataset_id="WB_WDI",
        candidates=[{"dataset_var": "random_metric", "correlation": 0.05, "trust_score": 0.1}],
        min_confidence=0.35,
    )
    assert matches == []


def test_calibrate_alignment_confidence_normalizes_methods() -> None:
    exact = VariableAlignment(
        canonical_var="gdp_per_capita",
        dataset_var="NY.GDP.PCAP.CD",
        dataset_id="WB_WDI",
        method=AlignmentMethod.EXACT,
        confidence=0.7,
        evidence="seed",
    )
    semantic = VariableAlignment(
        canonical_var="social_trust",
        dataset_var="trust_in_neighbors",
        dataset_id="WVS_W7",
        method=AlignmentMethod.SEMANTIC,
        confidence=0.6,
        evidence="semantic",
    )
    meta = VariableAlignment(
        canonical_var="institutional_quality",
        dataset_var="rl_est",
        dataset_id="WB_WGI",
        method=AlignmentMethod.META_ANALYTIC,
        confidence=0.62,
        evidence="meta",
    )

    assert calibrate_alignment_confidence(exact) == 1.0
    assert calibrate_alignment_confidence(semantic) == 0.8
    assert calibrate_alignment_confidence(meta) == 0.62


def test_score_variable_pair_detects_exact_name_and_unit_match() -> None:
    score = score_variable_pair(
        left_name="employment_rate",
        right_name="employment_rate",
        left_definition="Share of employed population",
        right_definition="Share of employed population",
        left_unit="percent",
        right_unit="percent",
    )

    assert score.exact_name_match is True
    assert score.definition_score > 0.9
    assert score.unit_compatibility_score == 1.0
    assert score.overall_score >= 0.8


def test_score_variable_pair_uses_seed_support_for_proxy_like_codes() -> None:
    score = score_variable_pair(
        left_name="RL.EST",
        right_name="GE.EST",
        left_definition="Rule of law estimate",
        right_definition="Government effectiveness estimate",
    )

    assert "institutional_quality" in score.shared_canonical_vars
    assert score.seed_support_score == 1.0
    assert any(item.startswith("seed_canonical=") for item in score.evidence)
