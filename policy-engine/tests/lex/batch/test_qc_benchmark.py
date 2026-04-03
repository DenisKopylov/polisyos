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


def test_qc_reports_quality_hardening_metrics_when_new_tables_exist(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE lex_entities (entity_id VARCHAR)")
        con.execute("CREATE TABLE lex_facts (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_provisions (provision_id VARCHAR)")
        con.execute("CREATE TABLE lex_high_confidence_norms (fact_id VARCHAR)")
        con.execute(
            """
            CREATE TABLE lex_normative_facts (
                fact_id VARCHAR,
                fused_confidence REAL,
                hallucination_flags_json VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_consistency_issues (
                issue_id VARCHAR,
                requires_manual_review BOOLEAN
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_amendments (
                amendment_id VARCHAR,
                amending_doc_id VARCHAR,
                amended_doc_id VARCHAR,
                target_resolution_expected BOOLEAN
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_doc_versions (
                doc_id VARCHAR,
                doc_name VARCHAR,
                doc_type VARCHAR
            )
            """
        )
        con.execute("CREATE TABLE lex_pattern_feedback_queue (feedback_id VARCHAR)")
        con.execute("INSERT INTO lex_entities VALUES ('e1')")
        con.execute("INSERT INTO lex_facts VALUES ('f1')")
        con.execute("INSERT INTO lex_provisions VALUES ('p1')")
        con.execute("INSERT INTO lex_high_confidence_norms VALUES ('f1')")
        con.execute("INSERT INTO lex_normative_facts VALUES ('n1', 0.91, '[]')")
        con.execute("INSERT INTO lex_normative_facts VALUES ('n2', 0.20, '[]')")
        con.execute("INSERT INTO lex_consistency_issues VALUES ('c1', TRUE)")
        con.execute("INSERT INTO lex_amendments VALUES ('a1', 'doc-amend', 'doc-base', TRUE)")
        con.execute("INSERT INTO lex_amendments VALUES ('a2', 'doc-multi', '', FALSE)")
        con.execute("INSERT INTO lex_doc_versions VALUES ('doc-amend', 'Про внесення змін до Закону України', 'Закон')")
        con.execute("INSERT INTO lex_doc_versions VALUES ('doc-multi', 'Про внесення змін до деяких законодавчих актів України', 'Закон')")
        con.execute("INSERT INTO lex_pattern_feedback_queue VALUES ('q1')")

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

    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path,
        stages=frozenset({"qc"}),
        quality_min_provision_docs_for_doc_rate=1,
        quality_min_spo_rows_for_row_rate=1,
        quality_min_statements_for_statement_rate=1,
        quality_max_low_confidence_normative_pct=60.0,
        quality_max_unresolved_contradictions=2,
    )
    report = run_qc(config, fail_fast=False)

    metrics = report.metrics
    assert metrics["high_confidence_norms"] == 1
    assert metrics["pattern_feedback_queue_total"] == 1
    assert metrics["unresolved_contradictions"] == 1
    assert metrics["amendments_total"] == 2
    assert metrics["amendments_with_target_total"] == 1
    assert metrics["amendment_target_expected_total"] == 1
    assert metrics["amendment_target_row_resolution_pct"] == 100.0
    assert metrics["amendment_extraction_coverage_pct"] == 100.0
    assert metrics["amendment_target_resolution_pct"] == 100.0
    assert metrics["expected_single_target_amendment_docs_total"] == 1
    assert metrics["resolved_single_target_amendment_docs_total"] == 1
    assert metrics["single_target_title_docs_total"] == 0
    assert metrics["single_target_title_resolution_pct"] == 0.0
    assert metrics["low_confidence_normative_facts_pct"] == 50.0
    assert metrics["hallucination_rate_pct"] == 0.0

    checks = {check.name: check for check in report.checks}
    assert checks["hallucination_blocking_rate_pct"].passed is True
    assert checks["hallucination_rate_pct"].passed is True
    assert checks["low_confidence_normative_facts_pct"].passed is True
    assert checks["unresolved_contradictions"].passed is True
    assert checks["amendment_extraction_coverage_pct"].passed is True
    assert checks["amendment_target_resolution_pct"].passed is True


def test_qc_treats_status_semantics_current_docs_as_known_and_embeddings_optional(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE lex_entities (entity_id VARCHAR)")
        con.execute("CREATE TABLE lex_facts (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_provisions (provision_id VARCHAR)")
        con.execute(
            """
            CREATE TABLE lex_doc_temporal (
                doc_id VARCHAR,
                temporal_state VARCHAR,
                temporal_resolution_status VARCHAR,
                temporal_source_kind VARCHAR
            )
            """
        )
        con.execute("INSERT INTO lex_entities VALUES ('e1')")
        con.execute("INSERT INTO lex_facts VALUES ('f1')")
        con.execute("INSERT INTO lex_provisions VALUES ('p1')")
        con.execute(
            """
            INSERT INTO lex_doc_temporal VALUES
            ('doc-1', 'current', 'partial', 'status_semantics'),
            ('doc-2', 'historical', 'partial', 'status_semantics')
            """
        )

    (tmp_path / "provisions" / "aa").mkdir(parents=True, exist_ok=True)
    (tmp_path / "spo_results" / "aa").mkdir(parents=True, exist_ok=True)
    (tmp_path / "provisions" / "aa" / "doc1.jsonl").write_text(
        json.dumps({"kind": "article", "anchor_path": "art:1", "doc_type_category": "law"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "spo_results" / "aa" / "doc1.jsonl").write_text(
        json.dumps({"statements": [{"predicate": "requires", "source_quote_uk": "цитата", "source_quote_start": 0, "source_quote_end": 6}]}) + "\n",
        encoding="utf-8",
    )

    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path,
        stages=frozenset({"qc"}),
        publish_require_embeddings=False,
        quality_min_provision_docs_for_doc_rate=1,
        quality_min_spo_rows_for_row_rate=1,
        quality_min_statements_for_statement_rate=1,
    )
    report = run_qc(config, fail_fast=False)

    checks = {check.name: check for check in report.checks}
    assert report.metrics["current_like_doc_temporal_unknown_pct"] == 0.0
    assert checks["current_like_doc_temporal_unknown_pct"].passed is True
    assert checks["embedding_artifacts_present"].passed is True
