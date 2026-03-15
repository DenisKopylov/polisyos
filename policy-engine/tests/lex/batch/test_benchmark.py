from __future__ import annotations

import json

import duckdb

from polisyos.lex.batch.benchmark import run_benchmark
from polisyos.lex.batch.config import BatchConfig


def _seed_benchmark_db(db_path) -> None:
    with duckdb.connect(str(db_path)) as con:
        for table_name in ("lex_facts", "lex_fact_grounded", "lex_normative_facts"):
            con.execute(
                f"""
                CREATE TABLE {table_name} (
                    fact_id VARCHAR,
                    subject_en VARCHAR,
                    predicate VARCHAR,
                    object_en VARCHAR,
                    fact_text VARCHAR,
                    confidence DOUBLE,
                    norm_type VARCHAR,
                    action_canon VARCHAR,
                    norm_type_canon VARCHAR,
                    condition_text_uk VARCHAR,
                    exception_text_uk VARCHAR,
                    procedure_text_uk VARCHAR,
                    thresholds_json VARCHAR,
                    source_quote_uk VARCHAR,
                    trust_tier VARCHAR,
                    grounding_status VARCHAR,
                    canonical_status VARCHAR,
                    reference_resolution_status VARCHAR,
                    structure_quality VARCHAR,
                    constraint_type_canon VARCHAR,
                    jurisdiction VARCHAR,
                    top_domain VARCHAR,
                    effective_from VARCHAR,
                    effective_to VARCHAR,
                    doc_name VARCHAR,
                    doc_reestr_code VARCHAR,
                    provision_citation VARCHAR,
                    doc_id VARCHAR
                )
                """
            )
        con.execute("CREATE TABLE lex_doc_domains (doc_id VARCHAR, domain VARCHAR)")
        con.execute("CREATE TABLE lex_rule_thresholds (threshold_id VARCHAR, fact_id VARCHAR, metric VARCHAR)")

        base_rows = [
            (
                "fact_license",
                "authority",
                "requires",
                "license",
                "Ліцензія та дозвіл подаються до органу погодження.",
                0.9,
                "obligation",
                "requires",
                "obligation",
                "",
                "",
                "",
                "[]",
                "Ліцензія та дозвіл подаються до органу погодження.",
                "",
                "exact_quote",
                "canonicalized",
                "resolved",
                "structured_legal_unit",
                "",
                "UA",
                "licensing",
                "",
                "",
                "Закон про ліцензування",
                "UA-LIC",
                "стаття 1",
                "doc_license",
            ),
            (
                "fact_reporting",
                "body",
                "requires",
                "report",
                "Суб'єкт повинен подати звіт до уповноваженого органу.",
                0.9,
                "obligation",
                "requires",
                "obligation",
                "",
                "",
                "",
                "[]",
                "Суб'єкт повинен подати звіт до уповноваженого органу.",
                "",
                "exact_quote",
                "canonicalized",
                "resolved",
                "structured_legal_unit",
                "",
                "UA",
                "reporting",
                "",
                "",
                "Постанова про звітність",
                "UA-REP",
                "пункт 2",
                "doc_reporting",
            ),
            (
                "fact_entry",
                "act",
                "enters_into_force",
                "publication",
                "Акт набирає чинності з дня офіційного опублікування.",
                0.9,
                "entry_into_force",
                "enters_into_force",
                "entry_into_force",
                "",
                "",
                "з дня офіційного опублікування",
                "[]",
                "Акт набирає чинності з дня офіційного опублікування.",
                "",
                "exact_quote",
                "canonicalized",
                "resolved",
                "structured_legal_unit",
                "",
                "UA",
                "public_sector",
                "",
                "",
                "Указ про порядок набрання чинності",
                "UA-ENTRY",
                "стаття 3",
                "doc_entry",
            ),
            (
                "fact_threshold",
                "act",
                "sets_threshold",
                "minimum amount",
                "Мінімальний розмір внеску становить 10 відсотків.",
                0.92,
                "obligation",
                "sets_threshold",
                "obligation",
                "",
                "",
                "",
                "[{\"metric\":\"minimum_amount\",\"value_text\":\"10 відсотків\",\"operator\":\">=\"}]",
                "Мінімальний розмір внеску становить 10 відсотків.",
                "",
                "exact_quote",
                "canonicalized",
                "resolved",
                "structured_legal_unit",
                "threshold",
                "UA",
                "public_sector",
                "",
                "",
                "Наказ про внесок",
                "UA-THR",
                "додаток 1",
                "doc_threshold",
            ),
        ]
        grounded_rows = [row[:14] + ("grounded_fact",) + row[15:] for row in base_rows]
        normative_rows = [row[:14] + ("normative_fact",) + row[15:] for row in base_rows]
        for table_name, rows in (
            ("lex_facts", grounded_rows),
            ("lex_fact_grounded", grounded_rows),
            ("lex_normative_facts", normative_rows),
        ):
            con.executemany(
                f"INSERT INTO {table_name} VALUES ({','.join(['?'] * len(rows[0]))})",
                rows,
            )
        con.executemany(
            "INSERT INTO lex_doc_domains VALUES (?, ?)",
            [
                ("doc_license", "licensing"),
                ("doc_reporting", "reporting"),
                ("doc_entry", "public_sector"),
                ("doc_threshold", "public_sector"),
            ],
        )
        con.execute(
            "INSERT INTO lex_rule_thresholds VALUES ('thr_1', 'fact_threshold', 'minimum_amount')"
        )


def test_run_benchmark_writes_report_and_metrics(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    _seed_benchmark_db(db_path)

    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path,
        stages=frozenset({"benchmark"}),
    )

    outcome = run_benchmark(config)

    assert outcome.report_path.exists()
    assert outcome.metrics["benchmark_search_top5_relevance_pct"] >= 75.0
    assert outcome.metrics["benchmark_constraints_ready_pct"] == 100.0
    assert outcome.metrics["benchmark_cross_graph_non_unknown_pct"] == 100.0

    payload = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "lex_benchmark"
    assert payload["sections"]["search"]["cases"]
