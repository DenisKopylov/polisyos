from __future__ import annotations

import pytest

from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    EVIDENCE_WEIGHTS,
    ArticleEvidence,
    aggregate_edge_confidence,
    decode_edge_evidence_strength,
    encode_edge_evidence_strength,
    weighted_direction_summary,
)
from polisyos.ir.analytics.literature import ClaimVocabularyAxisStatus, EvidenceStrength


def test_aggregate_edge_confidence_golden_rct_vs_many_observational() -> None:
    rct_conf = aggregate_edge_confidence([("rct", 0.9)])
    single_observational_conf = aggregate_edge_confidence([("observational", 0.8)])
    observational_conf = aggregate_edge_confidence([("observational", 0.8)] * 9)

    assert rct_conf > single_observational_conf
    assert observational_conf > single_observational_conf
    assert observational_conf > rct_conf
    assert rct_conf == pytest.approx(0.55)


def test_aggregate_edge_confidence_replication_bonus_saturates() -> None:
    conf_small = aggregate_edge_confidence([("observational", 0.6)] * 2)
    conf_large = aggregate_edge_confidence([("observational", 0.6)] * 64)

    assert conf_large >= conf_small
    assert conf_large <= 1.0


def test_aggregate_edge_confidence_filters_retracted_evidence() -> None:
    active = ArticleEvidence("rct", 0.82, publication_year=2024, retracted=False)
    retracted = ArticleEvidence("rct", 0.99, publication_year=2025, retracted=True)

    assert aggregate_edge_confidence([active, retracted]) == aggregate_edge_confidence([active])


def test_aggregate_edge_confidence_applies_temporal_and_sample_weighting() -> None:
    recent_large = aggregate_edge_confidence(
        [("quasi_natural", 0.8, 2024, 5000, "fulltext", False, None)]
    )
    old_small = aggregate_edge_confidence(
        [("quasi_natural", 0.8, 2000, 50, "fulltext", False, None)]
    )

    assert recent_large > old_small


def test_aggregate_edge_confidence_penalizes_abstract_only() -> None:
    fulltext = aggregate_edge_confidence(
        [("observational", 0.8, 2024, 500, "fulltext", False, None)]
    )
    abstract_only = aggregate_edge_confidence(
        [("observational", 0.8, 2024, 500, "abstract_only", False, None)]
    )

    assert abstract_only < fulltext


def test_declared_absence_contributes_zero_edge_confidence() -> None:
    """Catch a persisted absence token falling through to the unknown weight."""

    absent = ArticleEvidence(
        ClaimVocabularyAxisStatus.NOT_ESTABLISHED.value,
        1.0,
        publication_year=9999,
        sample_size=5000,
    )

    assert aggregate_edge_confidence([absent]) == 0.0


def test_declared_absence_does_not_change_established_edge_confidence() -> None:
    """Catch absence adding either noisy-OR weight or a replication bonus."""

    established = ArticleEvidence(
        "observational",
        0.8,
        publication_year=9999,
        sample_size=5000,
    )
    absent = ArticleEvidence(
        ClaimVocabularyAxisStatus.NOT_ESTABLISHED.value,
        1.0,
        publication_year=9999,
        sample_size=5000,
    )

    assert aggregate_edge_confidence([established, absent]) == aggregate_edge_confidence(
        [established]
    )


@pytest.mark.parametrize(("publication_year", "sample_size"), [(9999, 5000), (None, None)])
def test_unknown_contributes_zero_without_relabeling(publication_year, sample_size) -> None:
    """Catch a recorded unknown judgment still adding 0.15 or 0.08925 confidence."""

    unknown = ArticleEvidence(
        "unknown",
        1.0,
        publication_year=publication_year,
        sample_size=sample_size,
    )

    assert aggregate_edge_confidence([unknown]) == 0.0
    assert unknown.strength == "unknown"
    assert decode_edge_evidence_strength(unknown.strength) == (
        EvidenceStrength.UNKNOWN,
        ClaimVocabularyAxisStatus.CANDIDATE,
    )


def test_zero_base_unknown_cannot_earn_replication_bonus(monkeypatch) -> None:
    """Catch the 0.06 rescue that survives changing only the base constant."""
    monkeypatch.setitem(EVIDENCE_WEIGHTS, "unknown", 0.0)
    assert aggregate_edge_confidence([("unknown", 1.0)] * 2) == 0.0


def test_mixed_edge_batch_counts_only_contributing_evidence() -> None:
    """Catch unknown or absence entering noisy-OR or its replication population."""
    absent = encode_edge_evidence_strength(None, status=ClaimVocabularyAxisStatus.NOT_ESTABLISHED)
    theory = ArticleEvidence("theoretical", 1.0, publication_year=9999, sample_size=5000)
    unknown = ArticleEvidence("unknown", 1.0, publication_year=9999, sample_size=5000)
    batches = [[theory], [unknown, unknown], [(absent, 1.0)], [theory, unknown, (absent, 1.0)]]

    assert [aggregate_edge_confidence(rows) for rows in batches] == pytest.approx(
        [0.15, 0.0, 0.0, 0.15]
    )
    assert decode_edge_evidence_strength(absent) == (
        None,
        ClaimVocabularyAxisStatus.NOT_ESTABLISHED,
    )


def test_established_zero_effective_weight_keeps_floor_and_replication() -> None:
    """Catch filtering on effective weight instead of the licensed base population."""
    rct = ArticleEvidence("rct", 0.0)
    assert aggregate_edge_confidence([rct]) == pytest.approx(0.55)
    assert aggregate_edge_confidence([rct, rct]) == pytest.approx(0.61)


def test_unknown_dissent_does_not_create_contest() -> None:
    """Catch zero-contribution unknown still changing direction or disagreement."""
    summary = weighted_direction_summary(
        {
            "positive": [ArticleEvidence("theoretical", 1.0, 9999, 5000)],
            "negative": [ArticleEvidence("unknown", 1.0, 9999, 5000)] * 2,
        }
    )
    assert summary.direction_weights == {"positive": 0.15, "negative": 0.0}
    assert summary.dominant_direction == "positive"
    assert summary.agreement_score == 1.0
    assert not summary.is_contested
    assert summary.strongest_dissent_strength == ""


def test_unrecognized_edge_label_does_not_inherit_unknown_weight(monkeypatch) -> None:
    """Keep malformed evidence distinct even under a counterfactual unknown policy."""
    monkeypatch.setitem(EVIDENCE_WEIGHTS, "unknown", 0.15)
    summary = weighted_direction_summary({"positive": [ArticleEvidence("alien", 1.0, 9999, 5000)]})
    assert summary.direction_weights == {"positive": 0.0}
    assert aggregate_edge_confidence([("alien", 1.0)] * 2) == 0.0
