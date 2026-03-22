from __future__ import annotations

import pytest

from polisyos.academic.knowledge.skg_store import ArticleEvidence, aggregate_edge_confidence


def test_aggregate_edge_confidence_golden_rct_vs_many_observational() -> None:
    rct_conf = aggregate_edge_confidence([("rct", 0.9)])
    single_observational_conf = aggregate_edge_confidence([("observational", 0.8)])
    observational_conf = aggregate_edge_confidence([("observational", 0.8)] * 9)

    assert rct_conf > single_observational_conf
    assert observational_conf > single_observational_conf
    assert observational_conf > rct_conf
    assert rct_conf == pytest.approx(0.5355)


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
    fulltext = aggregate_edge_confidence([("observational", 0.8, 2024, 500, "fulltext", False, None)])
    abstract_only = aggregate_edge_confidence([("observational", 0.8, 2024, 500, "abstract_only", False, None)])

    assert abstract_only < fulltext
