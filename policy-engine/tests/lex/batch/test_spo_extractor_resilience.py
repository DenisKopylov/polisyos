from __future__ import annotations

import asyncio
import json
from pathlib import Path

from polisyos.lex.batch.spo_extractor import _group_request_items, extract_spo_for_documents
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPACard, NPADocument


class _FakeClient:
    model_id = "fake/model"


def _doc(doc_id: str, text: str) -> NPADocument:
    return NPADocument(
        card=NPACard(
            doc_id=doc_id,
            reestr_code=f"R-{doc_id}",
            date_acc="2026-01-01",
            reestr_date="2026-01-01",
            status="Чинний",
            doc_type="Закон",
            name=f"Doc {doc_id}",
            publisher=("ВРУ",),
            number="1",
            publication=(),
            keywords=(),
            reg_date="",
            reg_number="",
        ),
        text=text,
    )


def _span(anchor: str, text: str) -> ProvisionSpan:
    return ProvisionSpan(
        kind="article",
        number="1",
        anchor_path=anchor,
        citation_label=anchor,
        offset_start=0,
        offset_end=len(text),
        text=text,
        is_fallback_chunk=False,
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
    )


def test_group_request_items_respects_char_budget() -> None:
    doc = _doc("doc-a", "base")
    items = [
        (doc, _span("art:1", "x" * 1200)),
        (doc, _span("art:2", "y" * 1200)),
        (doc, _span("art:3", "z" * 1200)),
    ]

    groups = _group_request_items(
        items,
        request_batch_size=4,
        request_batch_chars=1800,
    )

    assert [len(group) for group in groups] == [1, 1, 1]


def test_extract_spo_for_documents_uses_timeout_fallback(monkeypatch, tmp_path: Path) -> None:
    doc = _doc("doc-a", "Орган повинен виконати вимогу.")
    span = _span("art:1", "Орган повинен виконати вимогу.")

    async def _slow_group(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        await asyncio.sleep(0.05)
        return []

    monkeypatch.setattr("polisyos.lex.batch.spo_extractor._extract_provision_group", _slow_group)

    results_dir = tmp_path / "spo_results"
    total, failed = asyncio.run(
        extract_spo_for_documents(
            _FakeClient(),
            [doc],
            {doc.card.doc_id: [span]},
            results_dir=results_dir,
            request_batch_size=1,
            request_batch_chars=1200,
            group_timeout_seconds=0.01,
            fallback_rows_by_anchor={
                doc.card.doc_id: {
                    span.anchor_path: {
                        "doc_id": doc.card.doc_id,
                        "provision_anchor": span.anchor_path,
                        "provision_citation": span.citation_label,
                        "statements": [{"predicate": "requires"}],
                        "low_confidence": True,
                        "low_confidence_reasons": ["llm_fallback_pending"],
                        "extraction_source": "llm_timeout_fallback",
                    }
                }
            },
        )
    )

    out_path = results_dir / doc.card.doc_id[:2].lower() / f"{doc.card.doc_id}.jsonl"
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert total == 1
    assert failed == set()
    assert len(rows) == 1
    assert rows[0]["extraction_source"] == "llm_timeout_fallback"
    assert "llm_group_timeout_fallback" in rows[0]["low_confidence_reasons"]
