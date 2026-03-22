from __future__ import annotations

import duckdb

from polisyos.lex.batch.consistency_checker import detect_consistency_issues
from polisyos.lex.batch.entity_resolver import EntityResolver, normalize_entity_name


def test_entity_resolver_preserves_small_corpus_fuzzy_match() -> None:
    resolver = EntityResolver()

    canonical_id = resolver.resolve(
        name_en="Ministry of Finance of Ukraine",
        name_uk="Міністерство фінансів України",
        entity_type="institution",
    )
    fuzzy_id = resolver.resolve(
        name_en="Ministry of Finances of Ukraine",
        name_uk="",
        entity_type="institution",
    )

    assert fuzzy_id == canonical_id


def test_entity_resolver_caps_fuzzy_bucket_candidates() -> None:
    resolver = EntityResolver()
    for idx in range(600):
        resolver.resolve(
            name_en=f"Alpha Ministry Variant {idx:04d}",
            name_uk="",
            entity_type="institution",
        )

    candidates = resolver._fuzzy_candidates(normalize_entity_name("Alpha Ministry Variant 9999"))

    assert candidates
    assert len(candidates) <= resolver._FUZZY_MAX_BUCKET_CANDIDATES


def test_detect_consistency_issues_uses_correct_column_offsets() -> None:
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE lex_normative_facts (
            fact_id VARCHAR,
            subject_en VARCHAR,
            object_en VARCHAR,
            norm_type_canon VARCHAR,
            norm_type VARCHAR,
            action_canon VARCHAR,
            predicate VARCHAR,
            doc_id VARCHAR,
            doc_type VARCHAR,
            doc_date_acc VARCHAR,
            provision_anchor VARCHAR,
            jurisdiction VARCHAR,
            doc_status VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE lex_doc_versions (
            doc_id VARCHAR,
            is_latest BOOLEAN,
            doc_status VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE lex_consistency_issues (
            issue_id VARCHAR,
            type VARCHAR,
            fact_id_1 VARCHAR,
            fact_id_2 VARCHAR,
            doc_id_1 VARCHAR,
            doc_id_2 VARCHAR,
            subject_en VARCHAR,
            object_en VARCHAR,
            norm_type_1 VARCHAR,
            norm_type_2 VARCHAR,
            severity VARCHAR,
            resolution_principle VARCHAR,
            prevailing_doc_id VARCHAR,
            resolution_confidence DOUBLE,
            requires_manual_review BOOLEAN,
            anchor_1 VARCHAR,
            anchor_2 VARCHAR
        )
        """
    )

    con.execute(
        """
        INSERT INTO lex_normative_facts VALUES
        ('f1', 'Ministry of Finance', 'permit', 'obligation', 'obligation', 'issue_permit', 'issue_permit', 'doc-law', 'Закон', '2024-01-01', 'art:5', 'UA', 'чинний'),
        ('f2', 'Ministry of Finance', 'permit', 'prohibition', 'prohibition', 'issue_permit', 'issue_permit', 'doc-order', 'Наказ', '2023-01-01', 'art:7', 'UA', 'чинний')
        """
    )
    con.execute(
        """
        INSERT INTO lex_doc_versions VALUES
        ('doc-law', TRUE, 'чинний'),
        ('doc-order', TRUE, 'чинний')
        """
    )

    count = detect_consistency_issues(con, jurisdiction="UA")

    assert count == 1
    row = con.execute(
        """
        SELECT doc_id_1, doc_id_2, resolution_principle, prevailing_doc_id, anchor_1, anchor_2
        FROM lex_consistency_issues
        """
    ).fetchone()
    assert row == ("doc-law", "doc-order", "lex_superior", "doc-law", "art:5", "art:7")

