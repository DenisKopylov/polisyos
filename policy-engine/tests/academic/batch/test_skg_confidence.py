from __future__ import annotations

from polisyos.academic.knowledge.skg_store import aggregate_edge_confidence


def test_aggregate_edge_confidence_golden_rct_vs_many_observational() -> None:
    rct_conf = aggregate_edge_confidence([("rct", 0.9)])
    observational_conf = aggregate_edge_confidence([("observational", 0.8)] * 9)

    assert rct_conf > observational_conf
    assert rct_conf == 0.9
    assert observational_conf < 0.7


def test_aggregate_edge_confidence_replication_bonus_saturates() -> None:
    conf_small = aggregate_edge_confidence([("observational", 0.6)] * 2)
    conf_large = aggregate_edge_confidence([("observational", 0.6)] * 64)

    assert conf_large >= conf_small
    assert conf_large <= 1.0
