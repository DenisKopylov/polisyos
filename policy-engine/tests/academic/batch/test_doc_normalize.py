from __future__ import annotations

import asyncio
import json

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.doc_normalize import run_doc_normalize
from polisyos.academic.batch.fulltext_resolver import FullTextFetchResult


def _write_jsonl(path, rows) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_doc_normalize_writes_structured_substrate(tmp_path, monkeypatch) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.doc_infra_enable_pub2tei = False
    config.doc_infra_enable_grobid = False
    _write_jsonl(
        config.selected_global_works_path,
        [
            {
                "work_id": "W1",
                "work": {
                    "id": "W1",
                    "title": "Policy effects on farm yields",
                    "publication_year": 2024,
                    "has_fulltext": True,
                    "abstract": "Randomized field experiment on fertilizer and winter wheat yield.",
                },
                "topic_ids": ["T1"],
                "topic_display_names": ["Agriculture"],
            }
        ],
    )

    async def _fake_fetch(*args, **kwargs):  # type: ignore[no-untyped-def]
        return FullTextFetchResult(
            text=(
                "Abstract\nRandomized field experiment on fertilizer and yield.\n"
                "Methods\nWe randomized fertilizer access across villages.\n"
                "Results\nTable 1 shows coefficient = 0.18 (SE = 0.04) for winter wheat yield.\n"
                "Appendix A: robustness checks across regions.\n"
            ),
            source_kind="publisher_xml",
            source_url="https://example.org/fulltext",
            final_state="usable_fulltext",
        )

    monkeypatch.setattr(
        "polisyos.academic.batch.doc_normalize.fetch_full_text_result_for_work",
        _fake_fetch,
    )

    metrics = asyncio.run(run_doc_normalize(config))

    assert metrics["docs_total"] == 1
    assert metrics["usable_docs"] == 1
    ready_rows = [json.loads(line) for line in config.doc_ready_queue_path.read_text(encoding="utf-8").splitlines()]
    assert ready_rows[0]["work_id"] == "W1"
    assert ready_rows[0]["fulltext"]["source_kind"] == "publisher_xml"
    substrate_rows = [json.loads(line) for line in config.doc_substrate_path.read_text(encoding="utf-8").splitlines()]
    assert substrate_rows[0]["doc_family"] == "empirical_rct"
    routing_rows = [json.loads(line) for line in config.doc_routing_path.read_text(encoding="utf-8").splitlines()]
    routing_lanes = {row["lane"] for row in routing_rows[0]["routing"]}
    assert {"claim", "numeric", "context", "mechanism"} <= routing_lanes
    assert config.doc_json_path.exists()
    assert any(config.doc_tei_dir.iterdir())


def test_doc_normalize_uses_pub2tei_when_xml_source_is_available(tmp_path, monkeypatch) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_jsonl(
        config.selected_global_works_path,
        [
            {
                "work_id": "WXML",
                "work": {
                    "id": "WXML",
                    "title": "JATS-backed policy paper",
                    "publication_year": 2024,
                    "has_fulltext": True,
                    "abstract": "Policy paper.",
                },
                "topic_ids": ["T1"],
                "topic_display_names": ["Governance"],
            }
        ],
    )

    async def _fake_fetch(*args, **kwargs):  # type: ignore[no-untyped-def]
        return FullTextFetchResult(
            text="Introduction Policy text. Results coefficient = 0.2.",
            source_kind="publisher_xml",
            source_url="https://example.org/article.xml",
            final_state="usable_fulltext",
        )

    async def _fake_source(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "ok": True,
            "status": 200,
            "content_type": "application/xml",
            "bytes": b"<publisher-record><body><section><title>Results</title><p>Coefficient 0.2</p></section></body></publisher-record>",
            "text": "<publisher-record><body><section><title>Results</title><p>Coefficient 0.2</p></section></body></publisher-record>",
        }

    async def _fake_pub2tei(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "ok": True,
            "status": 200,
            "tei_text": "<TEI><text><body><div type='results'><head>Results</head><p>Coefficient 0.2 (SE 0.1)</p></div></body></text></TEI>",
            "error_class": "",
        }

    monkeypatch.setattr("polisyos.academic.batch.doc_normalize.fetch_full_text_result_for_work", _fake_fetch)
    monkeypatch.setattr("polisyos.academic.batch.doc_normalize._fetch_source_document", _fake_source)
    monkeypatch.setattr("polisyos.academic.batch.doc_normalize._call_pub2tei", _fake_pub2tei)

    metrics = asyncio.run(run_doc_normalize(config))

    assert metrics["pub2tei_docs"] == 1
    substrate_rows = [json.loads(line) for line in config.doc_substrate_path.read_text(encoding="utf-8").splitlines()]
    assert substrate_rows[0]["tei_source"] == "pub2tei"
    sections = [json.loads(line) for line in config.doc_sections_path.read_text(encoding="utf-8").splitlines()]
    assert sections[0]["section_name"] == "results"


def test_doc_normalize_uses_grobid_when_pdf_source_is_available(tmp_path, monkeypatch) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_jsonl(
        config.selected_global_works_path,
        [
            {
                "work_id": "WPDF",
                "work": {
                    "id": "WPDF",
                    "title": "PDF-backed empirical paper",
                    "publication_year": 2024,
                    "has_fulltext": True,
                    "abstract": "Empirical study.",
                },
                "topic_ids": ["T1"],
                "topic_display_names": ["Labor"],
            }
        ],
    )

    async def _fake_fetch(*args, **kwargs):  # type: ignore[no-untyped-def]
        return FullTextFetchResult(
            text="Results Table 1 coefficient = -0.3.",
            source_kind="publisher_pdf",
            source_url="https://example.org/article.pdf",
            final_state="usable_fulltext",
        )

    async def _fake_source(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "ok": True,
            "status": 200,
            "content_type": "application/pdf",
            "bytes": b"%PDF-1.4 fake",
            "text": "",
        }

    async def _fake_grobid(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "ok": True,
            "status": 200,
            "tei_text": "<TEI><text><body><figure type='table'><head>Table 1</head><p>Estimate -0.3 (Std. Error 0.1)</p></figure></body></text></TEI>",
            "error_class": "",
        }

    monkeypatch.setattr("polisyos.academic.batch.doc_normalize.fetch_full_text_result_for_work", _fake_fetch)
    monkeypatch.setattr("polisyos.academic.batch.doc_normalize._fetch_source_document", _fake_source)
    monkeypatch.setattr("polisyos.academic.batch.doc_normalize._call_grobid", _fake_grobid)

    metrics = asyncio.run(run_doc_normalize(config))

    assert metrics["grobid_docs"] == 1
    substrate_rows = [json.loads(line) for line in config.doc_substrate_path.read_text(encoding="utf-8").splitlines()]
    assert substrate_rows[0]["tei_source"] == "grobid"
    tables = [json.loads(line) for line in config.doc_tables_path.read_text(encoding="utf-8").splitlines()]
    assert tables[0]["structure_source"] == "tei_figure_table"
