from __future__ import annotations

import asyncio
import json
import hashlib
from pathlib import Path

import duckdb

from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.pipeline import run_batch_pipeline
from polisyos.lex.batch.provisions_io import _shard_prefix, write_provisions
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


def _write_single_provision(provisions_dir: Path, doc_id: str, text: str, *, anchor: str = "article:1", citation: str = "Стаття 1") -> None:
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
    write_provisions(
        provisions_dir=provisions_dir,
        doc_id=doc_id,
        provisions=[
            {
                "kind": "article",
                "number": "1",
                "anchor_path": anchor,
                "citation_label": citation,
                "offset_start": 0,
                "offset_end": len(text),
                "text": text,
                "parent_anchor": None,
                "depth": 1,
                "token_est": max(1, len(text) // 4),
                "text_hash": text_hash,
                "is_fallback_chunk": False,
                "struct_kind": "article",
                "section_role": "normative_unit",
                "lineage_path": anchor,
                "fallback_allowed_for_reasoning": True,
                "legal_unit_subtype": "core_normative_clause",
                "legal_unit_micro_subtype": "main_deontic",
                "route_class": "deterministic_then_llm_retry",
                "empty_spo_retry_eligible": True,
                "audit_miss_prone": True,
                "reference_bearing": False,
                "threshold_bearing": False,
            }
        ],
    )


def _write_spo_row(spo_dir: Path, doc_id: str, *, subject_en: str, subject_uk: str, object_en: str, object_uk: str, text: str) -> None:
    shard_dir = spo_dir / _shard_prefix(doc_id)
    shard_dir.mkdir(parents=True, exist_ok=True)
    with open(shard_dir / f"{doc_id}.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "provision_anchor": "article:1",
                    "provision_citation": "Стаття 1",
                    "statements": [
                        {
                            "subject_en": subject_en,
                            "subject_uk": subject_uk,
                            "predicate": "requires",
                            "object_en": object_en,
                            "object_uk": object_uk,
                            "fact_text": text,
                            "confidence": 0.92,
                            "norm_type": "obligation",
                            "action_canon": "requires",
                            "norm_type_canon": "obligation",
                            "source_quote_uk": text,
                            "source_quote_start": 0,
                            "source_quote_end": len(text),
                            "trust_tier": "normative_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "unresolved",
                            "structure_quality": "structured_legal_unit",
                        }
                    ],
                    "extraction_source": "llm",
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _write_reference_hit(references_dir: Path, doc_id: str, target_raw: str) -> None:
    shard_dir = references_dir / _shard_prefix(doc_id)
    shard_dir.mkdir(parents=True, exist_ok=True)
    with open(shard_dir / f"{doc_id}.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "anchor_path": "article:1",
                    "source_span_start": 0,
                    "source_span_end": len(target_raw),
                    "target_raw": target_raw,
                    "type": "law_number",
                    "confidence": 0.97,
                    "target_number": "1234-IX",
                    "target_date": "01.01.2024",
                    "target_doc_type": "law",
                    "relation_hint": "amends",
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def test_pipeline_resolve_refs_and_graph_integrates_entities_references_and_amendments(monkeypatch, tmp_path: Path) -> None:
    docs = [
        NPADocument(
            card=NPACard(
                doc_id="base_law",
                reestr_code="R-base",
                date_acc="2024-01-01",
                reestr_date="2024-01-01",
                status="Чинний",
                doc_type="Закон",
                name='Закон України "Про базовий акт"',
                publisher=("ВРУ",),
                number="1234-IX",
                publication=(),
                keywords=(),
                reg_date="",
                reg_number="",
            ),
            text="Міністерство фінансів України повинно подати звіт.",
        ),
        NPADocument(
            card=NPACard(
                doc_id="alias_law",
                reestr_code="R-alias",
                date_acc="2024-02-01",
                reestr_date="2024-02-01",
                status="Чинний",
                doc_type="Постанова",
                name="Постанова про розкриття даних",
                publisher=("КМУ",),
                number="55",
                publication=(),
                keywords=(),
                reg_date="",
                reg_number="",
            ),
            text="Мінфін повинен оприлюднити дані.",
        ),
        NPADocument(
            card=NPACard(
                doc_id="amend_law",
                reestr_code="R-amend",
                date_acc="2024-03-01",
                reestr_date="2024-03-01",
                status="Чинний",
                doc_type="Закон",
                name='Про внесення змін до Закону України "Про базовий акт"',
                publisher=("ВРУ",),
                number="900-IX",
                publication=(),
                keywords=(),
                reg_date="",
                reg_number="",
            ),
            text=(
                'Внести зміни до Закону України "Про базовий акт" від 01.01.2024 № 1234-IX: '
                'у статті 5 слова "старий текст" замінити словами "новий текст".'
            ),
        ),
    ]

    provisions_dir = tmp_path / "run_pipeline_graph" / "provisions"
    spo_dir = tmp_path / "run_pipeline_graph" / "spo_results"
    references_dir = tmp_path / "run_pipeline_graph" / "references"
    provisions_dir.mkdir(parents=True, exist_ok=True)
    spo_dir.mkdir(parents=True, exist_ok=True)
    references_dir.mkdir(parents=True, exist_ok=True)

    # Write doc_metadata manifest so resolve_refs/graph stages can load it
    # without requiring a full XML parse (mirrors production resume workflow).
    manifests_dir = tmp_path / "run_pipeline_graph" / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    doc_meta_payload = {
        "kind": "lex_doc_metadata",
        "documents_total": len(docs),
        "documents": {
            doc.card.doc_id: {
                "reestr_code": doc.card.reestr_code,
                "name": doc.card.name,
                "doc_type": doc.card.doc_type,
                "date_acc": doc.card.date_acc,
                "reestr_date": doc.card.reestr_date,
                "status": doc.card.status,
                "publisher": list(doc.card.publisher),
                "number": doc.card.number,
            }
            for doc in docs
        },
    }
    (manifests_dir / "doc_metadata.json").write_text(
        json.dumps(doc_meta_payload, ensure_ascii=False), encoding="utf-8"
    )

    _write_single_provision(provisions_dir, "base_law", docs[0].text)
    _write_single_provision(provisions_dir, "alias_law", docs[1].text)
    _write_single_provision(provisions_dir, "amend_law", docs[2].text)
    _write_spo_row(
        spo_dir,
        "base_law",
        subject_en="Ministry of Finance of Ukraine",
        subject_uk="Міністерство фінансів України",
        object_en="report",
        object_uk="звіт",
        text="Міністерство фінансів України повинно подати звіт.",
    )
    _write_spo_row(
        spo_dir,
        "alias_law",
        subject_en="MinFin",
        subject_uk="Мінфін",
        object_en="data disclosure",
        object_uk="оприлюднення даних",
        text="Мінфін повинен оприлюднити дані.",
    )
    _write_reference_hit(
        references_dir,
        "amend_law",
        'Закон України "Про базовий акт" від 01.01.2024 № 1234-IX',
    )

    def _iter_documents(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        for doc in docs:
            yield doc

    monkeypatch.setattr("polisyos.lex.batch.xml_parser.iter_documents", _iter_documents)

    output_dir = tmp_path / "run_pipeline_graph"
    cfg = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=output_dir,
        stages=frozenset({"resolve_refs", "graph"}),
        quality_gates_enabled=False,
        extract_domains_enabled=False,
        extract_references_enabled=True,
    )
    stats = asyncio.run(run_batch_pipeline(cfg))

    assert int(stats.llm_gate_metrics.get("reference_resolution_audit_total", 0)) >= 1
    assert int(stats.llm_gate_metrics.get("amendments_total", 0)) >= 1
    assert int(stats.llm_gate_metrics.get("amendments_with_target_total", 0)) >= 1
    telemetry = json.loads(cfg.telemetry_path.read_text(encoding="utf-8"))
    assert telemetry["llm_gate_metrics"]["reference_resolution_audit_total"] >= 1
    assert telemetry["llm_gate_metrics"]["amendments_total"] >= 1

    with duckdb.connect(str(cfg.db_path), read_only=True) as con:
        reference_row = con.execute(
            """
            SELECT selected_target_doc_id, resolution_method, resolution_status
            FROM lex_reference_resolution_audit
            WHERE source_doc_id = 'amend_law'
            """
        ).fetchone()
        assert reference_row == ("base_law", "number_date", "partial")

        amendment_row = con.execute(
            """
            SELECT amended_doc_id, detected_by, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'amend_law'
            """
        ).fetchone()
        assert amendment_row is not None
        assert amendment_row[0] == "base_law"
        assert amendment_row[1] == "pattern+refs"
        amendment_meta = json.loads(amendment_row[2])
        assert amendment_meta["target_hint"]["target_doc_id"] == "base_law"

        entity_row = con.execute(
            """
            SELECT mention_count, aliases_en, aliases_uk
            FROM lex_entities
            WHERE entity_id = 'inst_minfin_ua'
            """
        ).fetchone()
        assert entity_row is not None
        assert entity_row[0] >= 2
        assert "MinFin" in (entity_row[1] or "")
        assert "Мінфін" in (entity_row[2] or "")
