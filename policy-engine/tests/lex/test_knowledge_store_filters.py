from __future__ import annotations

import duckdb

from polisyos.lex.knowledge.store import LegalKnowledgeStore


def test_legal_knowledge_store_prefers_high_trust_layers(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_facts (
                fact_id VARCHAR,
                subject_id VARCHAR,
                subject_en VARCHAR,
                predicate VARCHAR,
                object_id VARCHAR,
                object_en VARCHAR,
                fact_text VARCHAR,
                confidence REAL,
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
                provision_citation VARCHAR
            )
            """
        )
        con.execute("CREATE TABLE lex_fact_grounded AS SELECT * FROM lex_facts WHERE 1 = 0")
        con.execute("CREATE TABLE lex_normative_facts AS SELECT * FROM lex_facts WHERE 1 = 0")
        con.execute(
            """
            CREATE TABLE lex_rule_thresholds (
                threshold_id VARCHAR,
                fact_id VARCHAR,
                metric VARCHAR
            )
            """
        )
        row = (
            "f1",
            "s1",
            "body",
            "requires",
            "o1",
            "permit",
            "Body requires permit",
            0.9,
            "obligation",
            "requires",
            "obligation",
            "",
            "",
            "",
            '[{"metric":"vat_rate"}]',
            "Орган зобов'язаний надати дозвіл.",
            "normative_fact",
            "exact_quote",
            "canonicalized",
            "resolved",
            "structured_legal_unit",
            "",
            "UA",
            "transport",
            "2024-01-01",
            "",
            "Mock law",
            "123",
            "стаття 1",
        )
        con.execute("INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
        con.execute("INSERT INTO lex_fact_grounded VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
        con.execute("INSERT INTO lex_normative_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
        con.execute("INSERT INTO lex_rule_thresholds VALUES ('t1', 'f1', 'vat_rate')")

    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        facts = store.text_search_facts("permit", domain="transport")
        assert len(facts) == 1
        assert facts[0].trust_tier == "normative_fact"

        constraints = store.find_constraints(domain="transport", jurisdiction="UA")
        assert len(constraints) == 1

        thresholds = store.search_facts_with_threshold("vat_rate", domain="transport")
        assert len(thresholds) == 1

        norms = store.get_applicable_norms(domain="transport", jurisdiction="UA", as_of="2024-02-01")
        assert len(norms) == 1
    finally:
        store.close()
