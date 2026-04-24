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
                    hallucination_flags_json VARCHAR,
                    fused_confidence DOUBLE,
                    quality_band VARCHAR,
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
        con.execute(
            "CREATE TABLE lex_rule_thresholds (threshold_id VARCHAR, fact_id VARCHAR, metric VARCHAR)"
        )
        con.execute("CREATE TABLE lex_entities (entity_id VARCHAR, mention_count INTEGER)")
        con.execute(
            """
            CREATE TABLE lex_reference_resolution_audit (
                ref_id VARCHAR,
                resolution_status VARCHAR
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
        con.execute(
            """
            CREATE TABLE lex_consistency_issues (
                issue_id VARCHAR,
                requires_manual_review BOOLEAN
            )
            """
        )

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
                "[]",
                0.91,
                "high_confidence_norm",
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
                "[]",
                0.89,
                "high_confidence_norm",
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
                "[]",
                0.87,
                "high_confidence_norm",
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
                '[{"metric":"minimum_amount","value_text":"10 відсотків","operator":">="}]',
                "Мінімальний розмір внеску становить 10 відсотків.",
                "",
                "exact_quote",
                "canonicalized",
                "resolved",
                "structured_legal_unit",
                "threshold",
                "[]",
                0.93,
                "high_confidence_norm",
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
        grounded_rows = [(*row[:14], "grounded_fact", *row[15:]) for row in base_rows]
        normative_rows = [(*row[:14], "normative_fact", *row[15:]) for row in base_rows]
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
        con.executemany(
            "INSERT INTO lex_entities VALUES (?, ?)",
            [
                ("ent_minfin", 4),
                ("ent_rada", 3),
                ("ent_kmu", 2),
                ("ent_single", 1),
            ],
        )
        con.executemany(
            "INSERT INTO lex_reference_resolution_audit VALUES (?, ?)",
            [
                ("ref_1", "resolved"),
                ("ref_2", "resolved"),
                ("ref_3", "resolved"),
                ("ref_4", "resolved"),
                ("ref_5", "resolved"),
                ("ref_6", "resolved"),
            ],
        )
        con.executemany(
            "INSERT INTO lex_amendments VALUES (?, ?, ?, ?)",
            [
                ("amd_1", "doc_amend", "doc_license", True),
                ("amd_2", "doc_amend_2", "doc_reporting", True),
                ("amd_3", "doc_amend_multi", "", False),
            ],
        )
        con.executemany(
            "INSERT INTO lex_doc_versions VALUES (?, ?, ?)",
            [
                ("doc_amend", "Про внесення змін до Закону України про ліцензування", "Закон"),
                ("doc_amend_2", "Про внесення змін до Постанови про звітність", "Постанова"),
                (
                    "doc_amend_multi",
                    "Про внесення змін до деяких законодавчих актів України",
                    "Закон",
                ),
            ],
        )
        con.executemany(
            "INSERT INTO lex_consistency_issues VALUES (?, ?)",
            [
                ("issue_1", False),
                ("issue_2", False),
                ("issue_3", True),
                ("issue_4", False),
                ("issue_5", False),
            ],
        )
        con.execute("CREATE TABLE lex_high_confidence_norms AS SELECT * FROM lex_normative_facts")


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
    assert outcome.metrics["benchmark_entity_dedup_ready_pct"] == 75.0
    assert outcome.metrics["benchmark_reference_resolution_ready_pct"] == 100.0
    assert outcome.metrics["benchmark_amendment_extraction_ready_pct"] == 100.0
    assert outcome.metrics["benchmark_amendment_target_resolution_pct"] == 100.0
    assert outcome.metrics["benchmark_amendment_target_row_resolution_pct"] == 100.0
    assert outcome.metrics["benchmark_single_target_amendment_docs_total"] == 2
    assert outcome.metrics["benchmark_hallucination_clean_pct"] == 100.0
    assert outcome.metrics["benchmark_consistency_resolution_ready_pct"] == 80.0

    payload = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "lex_benchmark"
    assert payload["sections"]["search"]["cases"]
    assert (
        payload["sections"]["quality_capabilities"]["sections"]["entity_resolution"][
            "entities_total"
        ]
        == 4
    )
    assert (
        payload["sections"]["quality_capabilities"]["sections"]["reference_resolution"][
            "references_total"
        ]
        == 6
    )
    assert (
        payload["sections"]["quality_capabilities"]["sections"]["amendments"]["amendments_total"]
        == 3
    )
    assert (
        payload["sections"]["quality_capabilities"]["sections"]["amendments"][
            "amendment_target_expected_total"
        ]
        == 2
    )
    assert (
        payload["sections"]["quality_capabilities"]["sections"]["amendments"][
            "single_target_amendment_docs_total"
        ]
        == 2
    )
    assert (
        payload["sections"]["quality_capabilities"]["sections"]["amendments"][
            "resolved_single_target_amendment_docs_total"
        ]
        == 2
    )
    assert (
        payload["sections"]["quality_capabilities"]["sections"]["consistency"]["issues_total"] == 5
    )
