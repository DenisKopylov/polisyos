from __future__ import annotations

import json

import duckdb

from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.qc import run_qc


def test_qc_skips_benchmark_metric_without_cases(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE lex_entities (entity_id VARCHAR)")
        con.execute("CREATE TABLE lex_facts (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_provisions (provision_id VARCHAR)")
        con.execute("INSERT INTO lex_entities VALUES ('e1')")
        con.execute("INSERT INTO lex_facts VALUES ('f1')")
        con.execute("INSERT INTO lex_provisions VALUES ('p1')")

    (tmp_path / "provisions" / "aa").mkdir(parents=True, exist_ok=True)
    (tmp_path / "spo_results" / "aa").mkdir(parents=True, exist_ok=True)
    (tmp_path / "provisions" / "aa" / "doc1.jsonl").write_text(
        json.dumps({"kind": "article", "anchor_path": "art:1", "doc_type_category": "law"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "spo_results" / "aa" / "doc1.jsonl").write_text(
        json.dumps(
            {
                "statements": [
                    {
                        "predicate": "requires",
                        "source_quote_uk": "цитата",
                        "source_quote_start": 0,
                        "source_quote_end": 6,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "benchmark_report.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "benchmark_search_cases_total": 4,
                    "benchmark_search_top5_relevance_pct": 100.0,
                    "benchmark_normpack_cases_total": 0,
                    "benchmark_normpack_ready_pct": 0.0,
                },
                "readiness": {"passed": True, "failed_checks": []},
            }
        ),
        encoding="utf-8",
    )

    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path,
        stages=frozenset({"qc"}),
        quality_min_provision_docs_for_doc_rate=1,
        quality_min_spo_rows_for_row_rate=1,
        quality_min_statements_for_statement_rate=1,
    )
    report = run_qc(config, fail_fast=False)

    failed_names = [check.name for check in report.checks if not check.passed and check.severity == "critical"]
    assert "benchmark_normpack_ready_pct" not in failed_names
    assert "benchmark_readiness" not in failed_names
