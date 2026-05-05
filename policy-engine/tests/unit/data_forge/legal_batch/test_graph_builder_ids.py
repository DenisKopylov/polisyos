from __future__ import annotations

from polisyos.data_forge.domains.legal.batch.graph_builder import _fact_id, _provision_id


def test_fact_id_uses_statement_and_quote_offsets() -> None:
    a = _fact_id("doc-1", "art:1", "stmt-a", 10, 30)
    b = _fact_id("doc-1", "art:1", "stmt-a", 11, 30)
    c = _fact_id("doc-1", "art:1", "stmt-b", 10, 30)
    assert a != b
    assert a != c


def test_provision_id_uses_offsets_and_text_hash() -> None:
    a = _provision_id("doc-1", "art:1", 0, 100, "hash-1")
    b = _provision_id("doc-1", "art:1", 0, 101, "hash-1")
    c = _provision_id("doc-1", "art:1", 0, 100, "hash-2")
    assert a != b
    assert a != c
