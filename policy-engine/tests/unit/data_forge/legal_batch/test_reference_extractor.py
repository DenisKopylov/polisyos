from __future__ import annotations

from polisyos.data_forge.domains.legal.batch.reference_extractor import extract_references


def test_extract_references_detects_common_legal_patterns() -> None:
    text = (
        "Відповідно до статті 3 Закону України Про державний бюджет, "
        "а також Закон України від 12.10.2020 № 123-IX, "
        "та постанови КМУ від 01.01.2021 № 10."
    )
    hits = extract_references(text=text, doc_id="doc1", anchor_path="art:1/pt:1")
    assert len(hits) >= 2
    types = {hit.ref_type for hit in hits}
    assert "law_number" in types
    assert "cabinet_resolution" in types
