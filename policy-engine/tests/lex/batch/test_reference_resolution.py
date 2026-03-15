from __future__ import annotations

import json

from polisyos.lex.batch.postprocess import resolve_references
from polisyos.lex.batch.reference_extractor import extract_references


def test_extract_references_preserves_full_target_and_structured_hints() -> None:
    text = (
        "Внести зміни до Закону України Про дорожній рух від 01.01.2024 № 1234-IX. "
        "Відповідно до статті 5 цього Закону застосовуються загальні правила."
    )

    hits = extract_references(text=text, doc_id="srcdoc", anchor_path="article:1")

    assert hits
    external = next(hit for hit in hits if hit.ref_type == "law_number")
    assert "Закону України" in external.target_raw
    assert external.target_number == "1234-IX"
    assert external.target_date == "01.01.2024"
    assert external.target_doc_type == "law"
    assert external.relation_hint == "amends"

    internal = next(hit for hit in hits if hit.ref_type == "self_reference")
    assert "статті 5 цього Закону" in internal.target_raw
    assert internal.relation_hint == "references"


def test_resolve_references_supports_number_date_and_self_reference(tmp_path) -> None:
    refs_dir = tmp_path / "refs" / "ab"
    out_dir = tmp_path / "resolved"
    refs_dir.mkdir(parents=True)

    reference_rows = [
        {
            "doc_id": "srcdoc",
            "anchor_path": "article:1",
            "source_span_start": 0,
            "source_span_end": 40,
            "target_raw": "Закон України Про дорожній рух від 01.01.2024 № 1234-IX",
            "type": "law_number",
            "confidence": 0.95,
            "target_number": "1234-IX",
            "target_date": "01.01.2024",
            "target_doc_type": "law",
            "relation_hint": "amends",
        },
        {
            "doc_id": "srcdoc",
            "anchor_path": "article:1",
            "source_span_start": 41,
            "source_span_end": 70,
            "target_raw": "статті 2 цього Закону",
            "type": "self_reference",
            "confidence": 0.98,
            "target_doc_type": "self_reference",
            "relation_hint": "references",
        },
    ]

    with open(refs_dir / "srcdoc.jsonl", "w", encoding="utf-8") as fh:
        for row in reference_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats = resolve_references(
        references_dir=tmp_path / "refs",
        output_dir=out_dir,
        doc_metadata={
            "srcdoc": {
                "reestr_code": "SRC-1",
                "name": "Закон України Про зміни",
                "doc_type": "Закон України",
                "date_acc": "2024-05-01",
                "status": "active",
                "number": "2000-IX",
                "publisher": ["Верховна Рада України"],
            },
            "law123": {
                "reestr_code": "LAW-123",
                "name": "Закон України Про дорожній рух",
                "doc_type": "Закон України",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
            "law123_old": {
                "reestr_code": "LAW-122",
                "name": "Закон України Про дорожній рух",
                "doc_type": "Закон України",
                "date_acc": "2023-01-01",
                "status": "inactive",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
    )

    assert stats["rows_total"] == 2
    assert stats["rows_resolved"] == 2

    resolved_path = out_dir / "ab" / "srcdoc.jsonl"
    rows = [json.loads(line) for line in resolved_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2

    external = next(row for row in rows if row["type"] == "law_number")
    assert external["target_doc_id"] == "law123"
    assert external["matched_by"] == "number_date"
    assert external["relation_type"] == "amends"
    assert external["resolution_status"] == "partial"
    assert external["target_doc_family_id"]

    internal = next(row for row in rows if row["type"] == "self_reference")
    assert internal["target_doc_id"] == "srcdoc"
    assert internal["target_anchor"] == "article:2"
    assert internal["resolution_status"] == "resolved"
