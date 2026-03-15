from __future__ import annotations

import asyncio
from pathlib import Path

from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.pipeline import run_batch_pipeline
from polisyos.lex.batch.provisions_io import write_provisions
from polisyos.lex.batch.xml_parser import NPACard, NPADocument


def _card(doc_id: str, name: str) -> NPACard:
    return NPACard(
        doc_id=doc_id,
        reestr_code=f"R-{doc_id}",
        date_acc="2026-01-01",
        reestr_date="2026-01-01",
        status="Чинний",
        doc_type="Закон",
        name=name,
        publisher=("ВРУ",),
        number="1",
        publication=(),
        keywords=(),
        reg_date="",
        reg_number="",
    )


class _FakeGonkaClient:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.model_id = "fake/model"

    async def __aenter__(self) -> "_FakeGonkaClient":
        return self

    async def __aexit__(self, *exc) -> None:  # noqa: ANN002
        return None

    def set_cache(self, cache: object | None) -> None:
        pass


async def _fake_extract_spo_for_documents(
    client,
    documents,
    provisions_by_doc,
    *,
    results_dir,
    task_batch_size=1000,
    request_batch_size=1,
    request_batch_chars=None,
    group_timeout_seconds=None,
    verify_mode="llm",
    extract_mode="full",
    overwrite_existing=True,
    extraction_source="llm",
    gate_meta_by_anchor=None,
    fallback_rows_by_anchor=None,
    result_sink=None,
):
    del client, results_dir, task_batch_size, request_batch_size, request_batch_chars
    del group_timeout_seconds, verify_mode, extract_mode, overwrite_existing
    del extraction_source, gate_meta_by_anchor, fallback_rows_by_anchor
    total = 0
    for doc in documents:
        for span in provisions_by_doc.get(doc.card.doc_id, []):
            total += 1
            if result_sink is not None:
                result_sink(
                    {
                        "doc_id": doc.card.doc_id,
                        "provision_anchor": span.anchor_path,
                        "statements": [{"predicate": "requires"}],
                    }
                )
    return total, set()


def _prepare_docs() -> list[NPADocument]:
    return [
        NPADocument(
            card=_card("doc_auto", "Акт про чинність"),
            text="Цей акт набирає чинності з дня офіційного опублікування.",
        ),
        NPADocument(
            card=_card("doc_deferred", "Проста вимога"),
            text="Уповноважений орган повинен забезпечити виконання вимог.",
        ),
        NPADocument(
            card=_card("doc_llm", "Складна норма"),
            text=(
                "Якщо виникає потреба, відповідно до статті 3 цього Закону "
                "орган може переглядати ставку 18% та/або застосовувати винятки."
            ),
        ),
    ]


def _prepare_provisions(base_dir: Path, docs: list[NPADocument]) -> None:
    import hashlib

    for doc in docs:
        text_hash = hashlib.sha256(doc.text.encode()).hexdigest()[:12]
        write_provisions(
            provisions_dir=base_dir,
            doc_id=doc.card.doc_id,
            provisions=[
                {
                    "kind": "article",
                    "number": "1",
                    "anchor_path": "art:1",
                    "citation_label": "Стаття 1",
                    "offset_start": 0,
                    "offset_end": len(doc.text),
                    "text": doc.text,
                    "parent_anchor": None,
                    "depth": 1,
                    "token_est": max(1, len(doc.text) // 4),
                    "text_hash": text_hash,
                    "is_fallback_chunk": False,
                }
            ],
        )


def _run_pipeline(monkeypatch, tmp_path: Path, *, gate_mode: str) -> int:
    docs = _prepare_docs()
    output_dir = tmp_path / f"run_{gate_mode}"
    output_dir.mkdir(parents=True, exist_ok=True)
    _prepare_provisions(output_dir / "provisions", docs)

    def _iter_documents(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        for doc in docs:
            yield doc

    monkeypatch.setattr("polisyos.lex.batch.xml_parser.iter_documents", _iter_documents)
    monkeypatch.setattr("polisyos.lex.batch.spo_extractor.GonkaClient", _FakeGonkaClient)
    monkeypatch.setattr(
        "polisyos.lex.batch.spo_extractor.extract_spo_for_documents",
        _fake_extract_spo_for_documents,
    )

    cfg = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=output_dir,
        stages=frozenset({"spo"}),
        gonka_api_key="fake-key",
        quality_gates_enabled=False,
        llm_gate_mode=gate_mode,
        llm_gate_audit_sample_rate=0.0,
        extract_domains_enabled=False,
        extract_references_enabled=False,
    )
    stats = asyncio.run(run_batch_pipeline(cfg))
    return int(stats.llm_gate_metrics.get("llm_sent_total", 0))


def test_pipeline_llm_gate_reduces_llm_calls(monkeypatch, tmp_path: Path) -> None:
    llm_sent_off = _run_pipeline(monkeypatch, tmp_path, gate_mode="off")
    llm_sent_balanced = _run_pipeline(monkeypatch, tmp_path, gate_mode="balanced")
    assert llm_sent_balanced < llm_sent_off
