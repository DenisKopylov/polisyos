from __future__ import annotations

import json

import duckdb

from polisyos.lex.batch.doc_identity import build_doc_resolution_index
from polisyos.lex.batch.graph_builder import _infer_amendment_target_from_title, build_graph


def test_build_graph_creates_fact_partitions_and_reference_edges(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "ab"
    provisions_dir = tmp_path / "provisions" / "ab"
    refs_dir = tmp_path / "resolved_references" / "ab"
    domains_dir = tmp_path / "domains" / "ab"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)
    refs_dir.mkdir(parents=True)
    domains_dir.mkdir(parents=True)

    with open(provisions_dir / "abdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Орган зобов'язаний надати дозвіл.",
                    "offset_start": 0,
                    "offset_end": 33,
                    "token_est": 10,
                    "text_hash": "hash123",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(spo_dir / "abdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "abdoc",
                    "provision_anchor": "article:1",
                    "provision_citation": "стаття 1",
                    "statements": [
                        {
                            "subject_en": "body",
                            "subject_uk": "орган",
                            "predicate": "requires",
                            "object_en": "permit",
                            "object_uk": "дозвіл",
                            "fact_text": "Body requires permit.",
                            "confidence": 0.9,
                            "norm_type": "obligation",
                            "action_canon": "requires",
                            "norm_type_canon": "obligation",
                            "source_quote_uk": "Орган зобов'язаний надати дозвіл.",
                            "source_quote_start": 0,
                            "source_quote_end": 33,
                            "trust_tier": "normative_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "unresolved",
                            "structure_quality": "structured_legal_unit",
                            "links": [
                                {
                                    "relation_type": "references",
                                    "target_doc_id": "target-doc",
                                    "target_anchor": "article:2",
                                    "ref_text_uk": "стаття 2",
                                }
                            ],
                        }
                    ],
                    "extraction_source": "rule_auto",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(refs_dir / "abdoc.jsonl", "w", encoding="utf-8") as fh:
        payload = {
            "reference_edge_id": "ref-edge-1",
            "doc_id": "abdoc",
            "source_doc_family_id": "family-1",
            "anchor_path": "article:1",
            "target_raw": "стаття 2",
            "target_doc_id": "target-doc",
            "target_doc_family_id": "family-2",
            "target_doc_reestr_code": "124",
            "target_doc_number": "321-IX",
            "target_doc_type": "Закон України",
            "target_doc_date_acc": "2024-02-01",
            "target_doc_status": "active",
            "target_anchor": "article:2",
            "relation_type": "references",
            "matched_by": "self_reference",
            "resolution_confidence": 0.95,
            "resolution_status": "resolved",
            "target_version_id": "target-doc",
        }
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    with open(domains_dir / "abdoc.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "doc_id": "abdoc",
                "top_domain": "transport",
                "scores": [{"domain": "transport", "score": 0.9, "hits": 2}],
            },
            fh,
            ensure_ascii=False,
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=tmp_path / "resolved_references",
        domains_dir=tmp_path / "domains",
        doc_metadata={
            "abdoc": {
                "reestr_code": "123",
                "name": "Test law",
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "321-IX",
                "publisher": ["Верховна Рада України"],
            },
            "abdoc_v2": {
                "reestr_code": "124",
                "name": "Test law",
                "doc_type": "Закон",
                "date_acc": "2024-03-01",
                "status": "active",
                "number": "321-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=100,
    )

    assert stats.facts == 1
    assert stats.normative_facts == 1
    assert stats.reference_edges == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM lex_normative_facts").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM lex_fact_grounded").fetchone()[0] == 1
        assert con.execute("SELECT top_domain FROM lex_facts").fetchone()[0] == "transport"
        assert con.execute("SELECT reference_resolution_status FROM lex_facts").fetchone()[0] == "resolved"
        assert con.execute("SELECT COUNT(*) FROM lex_reference_edges").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM lex_doc_versions").fetchone()[0] == 2
        assert con.execute("SELECT matched_by FROM lex_reference_edges").fetchone()[0] == "self_reference"
        lineage = con.execute(
            """
            SELECT version_rank, previous_version_id, next_version_id, is_latest
            FROM lex_doc_versions
            WHERE doc_id = 'abdoc'
            """
        ).fetchone()
        assert lineage == (1, None, "abdoc_v2", False)


def test_build_graph_rewrites_fact_id_collisions_for_distinct_statements(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "dc"
    provisions_dir = tmp_path / "provisions" / "dc"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "dcdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "art:14/pt:27",
                    "citation_label": "стаття 14 пункт 27",
                    "kind": "point",
                    "text": "Центральна виборча комісія забезпечує окружні виборчі комісії зразками підписних листів.",
                    "offset_start": 0,
                    "offset_end": 96,
                    "token_est": 24,
                    "text_hash": "hash-27",
                    "is_fallback_chunk": False,
                    "struct_kind": "point",
                    "section_role": "normative_unit",
                    "lineage_path": "art:14/pt:27",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(spo_dir / "dcdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "dcdoc",
                    "provision_anchor": "art:14/pt:27",
                    "provision_citation": "стаття 14 пункт 27",
                    "statements": [
                        {
                            "statement_id": "stmt-27",
                            "subject_en": "Central Election Commission",
                            "subject_uk": "Центральна виборча комісія",
                            "predicate": "ensures",
                            "object_en": "district election commissions",
                            "object_uk": "окружні виборчі комісії",
                            "fact_text": "The Central Election Commission ensures district election commissions with signature sheet templates.",
                            "confidence": 0.81,
                            "norm_type": "delegation",
                            "action_canon": "requires",
                            "norm_type_canon": "delegation",
                            "source_quote_uk": "Центральна виборча комісія забезпечує окружні виборчі комісії зразками підписних листів.",
                            "source_quote_start": 39,
                            "source_quote_end": 85,
                            "trust_tier": "grounded_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "unresolved",
                            "structure_quality": "structured_legal_unit",
                            "links": [],
                        },
                        {
                            "statement_id": "stmt-27",
                            "subject_en": "Central Election Commission",
                            "subject_uk": "Центральна виборча комісія",
                            "predicate": "ensures",
                            "object_en": "district election commissions",
                            "object_uk": "окружні виборчі комісії",
                            "fact_text": "The Central Election Commission ensures district election commissions with signature sheet templates.",
                            "confidence": 0.81,
                            "norm_type": "procedure",
                            "action_canon": "requires",
                            "norm_type_canon": "procedure",
                            "source_quote_uk": "Центральна виборча комісія забезпечує окружні виборчі комісії зразками підписних листів.",
                            "source_quote_start": 39,
                            "source_quote_end": 85,
                            "trust_tier": "grounded_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "unresolved",
                            "structure_quality": "structured_legal_unit",
                            "links": [],
                        },
                    ],
                    "extraction_source": "llm",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "dcdoc": {
                "reestr_code": "777",
                "name": "Election procedure",
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
            }
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.facts == 2
    assert stats.grounded_facts == 2

    with duckdb.connect(str(db_path), read_only=True) as con:
        rows = con.execute(
            """
            SELECT fact_id, norm_type_canon
            FROM lex_facts
            ORDER BY norm_type_canon
            """
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] != rows[1][0]
        assert [row[1] for row in rows] == ["delegation", "procedure"]


def test_build_graph_populates_amendments_with_target_from_resolved_references(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "am"
    provisions_dir = tmp_path / "provisions" / "am"
    refs_dir = tmp_path / "resolved_references" / "am"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)
    refs_dir.mkdir(parents=True)

    with open(provisions_dir / "amdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "У статті 5 слова «старий текст» замінити словами «новий текст».",
                    "offset_start": 0,
                    "offset_end": 66,
                    "token_est": 12,
                    "text_hash": "hash-amend",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(refs_dir / "amdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "reference_edge_id": "am-edge-1",
                    "doc_id": "amdoc",
                    "source_doc_family_id": "family-am",
                    "anchor_path": "article:1",
                    "target_raw": "Закон України Про базовий акт від 01.01.2024 № 1234-IX",
                    "target_doc_id": "base-law",
                    "selected_target_doc_id": "base-law",
                    "target_doc_family_id": "family-base",
                    "target_doc_reestr_code": "124",
                    "target_doc_number": "1234-IX",
                    "target_doc_type": "Закон України",
                    "target_doc_date_acc": "2024-01-01",
                    "target_doc_status": "active",
                    "target_anchor": "article:5",
                    "relation_type": "amends",
                    "matched_by": "number_date",
                    "resolution_confidence": 0.97,
                    "resolution_status": "partial",
                    "target_version_id": "base-law",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=tmp_path / "resolved_references",
        domains_dir=None,
        doc_metadata={
            "amdoc": {
                "reestr_code": "900",
                "name": "Law on amendments",
                "doc_type": "Закон",
                "date_acc": "2024-05-01",
                "status": "active",
                "number": "900-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law": {
                "reestr_code": "124",
                "name": "Base law",
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amending_doc_id, amended_doc_id, amendment_type, target_anchor, detected_by, metadata
            FROM lex_amendments
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "amdoc"
        assert row[1] == "base-law"
        assert row[2] == "replace_text"
        assert row[3] == "article:5"
        assert row[4] == "pattern+refs"
        metadata = json.loads(row[5])
        assert metadata["target_hint"]["relation_type"] == "amends"
        assert metadata["target_hint"]["target_doc_id"] == "base-law"


def test_build_graph_infers_amendment_target_from_doc_title_when_refs_missing(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "ti"
    provisions_dir = tmp_path / "provisions" / "ti"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "titledoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "У статті 5 слова «старий текст» замінити словами «новий текст».",
                    "offset_start": 0,
                    "offset_end": 66,
                    "token_est": 12,
                    "text_hash": "hash-title-amend",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "titledoc": {
                "reestr_code": "901",
                "name": 'Про внесення змін до Закону України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-05-02",
                "status": "active",
                "number": "901-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law": {
                "reestr_code": "124",
                "name": 'Закон України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id, detected_by, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'titledoc'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "base-law"
        assert row[1] == "pattern+title"
        metadata = json.loads(row[2])
        assert metadata["target_hint"]["source"].startswith("doc_title_")


def test_build_graph_infers_amendment_target_from_doc_title_with_changes_and_supplements(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "ts"
    provisions_dir = tmp_path / "provisions" / "ts"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "titleplus.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Доповнити статтю 5 новою частиною.",
                    "offset_start": 0,
                    "offset_end": 35,
                    "token_est": 8,
                    "text_hash": "hash-title-plus",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "titleplus": {
                "reestr_code": "903",
                "name": 'Про внесення змін і доповнень до Закону України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-05-04",
                "status": "active",
                "number": "903-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law": {
                "reestr_code": "124",
                "name": 'Закон України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id, detected_by, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'titleplus'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "base-law"
        assert row[1] == "pattern+title"
        metadata = json.loads(row[2])
        assert metadata["target_hint"]["source"].startswith("doc_title_")


def test_build_graph_infers_amendment_target_from_doc_title_even_when_refs_are_self_only(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "tr"
    provisions_dir = tmp_path / "provisions" / "tr"
    refs_dir = tmp_path / "resolved_references" / "tr"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)
    refs_dir.mkdir(parents=True)

    with open(provisions_dir / "titleself.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "У статті 5 слова «старий текст» замінити словами «новий текст».",
                    "offset_start": 0,
                    "offset_end": 66,
                    "token_est": 12,
                    "text_hash": "hash-title-self",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(refs_dir / "titleself.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "titleself",
                    "selected_target_doc_id": "titleself",
                    "target_doc_id": "titleself",
                    "resolution_status": "resolved",
                    "relation_type": "references",
                    "resolution_confidence": 0.99,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=tmp_path / "resolved_references",
        domains_dir=None,
        doc_metadata={
            "titleself": {
                "reestr_code": "902",
                "name": 'Про внесення змін до Закону України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-05-03",
                "status": "active",
                "number": "902-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law": {
                "reestr_code": "124",
                "name": 'Закон України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id, detected_by, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'titleself'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "base-law"
        assert row[1] == "pattern+title"
        metadata = json.loads(row[2])
        assert metadata["target_hint"]["source"].startswith("doc_title_")


def test_build_graph_infers_amendment_target_from_title_number_and_date(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "td"
    provisions_dir = tmp_path / "provisions" / "td"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "titlenum.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Доповнити статтю 5 новою частиною.",
                    "offset_start": 0,
                    "offset_end": 35,
                    "token_est": 8,
                    "text_hash": "hash-title-number-date",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "titlenum": {
                "reestr_code": "904",
                "name": "Про внесення змін до Закону України від 01.01.2024 № 1234-IX",
                "doc_type": "Закон",
                "date_acc": "2024-05-05",
                "status": "active",
                "number": "904-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law": {
                "reestr_code": "124",
                "name": "Закон України про базовий акт",
                "doc_type": "Закон",
                "date_acc": "01.01.2024",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id, detected_by, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'titlenum'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "base-law"
        assert row[1] == "pattern+title"
        metadata = json.loads(row[2])
        assert metadata["target_hint"]["source"] == "doc_title_number_date"


def test_build_graph_infers_amendment_target_from_textual_month_number_and_date(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "tm"
    provisions_dir = tmp_path / "provisions" / "tm"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "titletextual.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Доповнити статтю 5 новою частиною.",
                    "offset_start": 0,
                    "offset_end": 35,
                    "token_est": 8,
                    "text_hash": "hash-title-textual-number-date",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "titletextual": {
                "reestr_code": "905",
                "name": "Про внесення змін до постанови Кабінету Міністрів України від 20 липня 1996 р. N 767",
                "doc_type": "Постанова",
                "date_acc": "16.02.1998",
                "status": "active",
                "number": "176",
                "publisher": ["Кабінет Міністрів України"],
            },
            "base-resolution": {
                "reestr_code": "125",
                "name": "Про базову постанову",
                "doc_type": "Постанова",
                "date_acc": "20.07.1996",
                "status": "active",
                "number": "767",
                "publisher": ["Кабінет Міністрів України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'titletextual'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "base-resolution"
        metadata = json.loads(row[1])
        assert metadata["target_hint"]["source"] in {
            "doc_title_textual_number_date",
            "doc_title_textual_number_date_family_latest",
        }


def test_build_graph_drops_calendar_year_threshold_garbage(tmp_path) -> None:
    spo_dir = tmp_path / "spo_grounded" / "yr"
    provisions_dir = tmp_path / "provisions" / "yr"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "yrdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "body:1/item:0001",
                    "citation_label": "пункт 1",
                    "kind": "point",
                    "text": "1. Визнати таким, що не відповідає Конституції України, Закон від 22 квітня 1993 року N 290.",
                    "offset_start": 0,
                    "offset_end": 97,
                    "token_est": 20,
                    "text_hash": "hash-year-threshold",
                    "is_fallback_chunk": False,
                    "struct_kind": "point",
                    "section_role": "normative_unit",
                    "lineage_path": "body:1/item:0001",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(spo_dir / "yrdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "yrdoc",
                    "provision_anchor": "body:1/item:0001",
                    "provision_citation": "пункт 1",
                    "legal_unit_subtype": "core_normative_clause",
                    "statements": [
                        {
                            "subject_en": "Decision title",
                            "subject_uk": "Рішення у справі за конституційним поданням Президента України",
                            "predicate": "sets_threshold",
                            "object_en": "1993 year",
                            "object_uk": "1993 year",
                            "fact_text": "Decision sets threshold 1993 year",
                            "confidence": 0.9,
                            "norm_type": "obligation",
                            "action_canon": "sets_threshold",
                            "norm_type_canon": "obligation",
                            "source_quote_uk": "Закон від 22 квітня 1993 року N 290.",
                            "source_quote_start": 58,
                            "source_quote_end": 96,
                            "trust_tier": "normative_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "not_applicable",
                            "structure_quality": "structured_legal_unit",
                            "thresholds": [
                                {
                                    "metric": "duration",
                                    "operator": "gte",
                                    "value_decimal": "1993",
                                    "value_text": "1993",
                                    "unit": "year",
                                    "applies_to": "1993 year",
                                }
                            ],
                            "links": [],
                        }
                    ],
                    "extraction_source": "rule_auto",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_grounded",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "yrdoc": {
                "reestr_code": "yr-1",
                "name": "Рішення у справі за конституційним поданням Президента України",
                "doc_type": "Рішення",
                "date_acc": "1998-03-03",
                "status": "active",
                "publisher": ["Конституційний Суд України"],
            }
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.facts == 0

    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM lex_rule_thresholds").fetchone()[0] == 0


def test_build_graph_replaces_synthetic_subject_with_publisher_and_cleans_flags(tmp_path) -> None:
    spo_dir = tmp_path / "spo_grounded" / "sy"
    provisions_dir = tmp_path / "provisions" / "sy"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "sydoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "body:1/item:0001",
                    "citation_label": "пункт 1",
                    "kind": "point",
                    "text": "1. Затвердити Порядок розгляду питань та проходження документів.",
                    "offset_start": 0,
                    "offset_end": 68,
                    "token_est": 10,
                    "text_hash": "hash-synth-subject",
                    "is_fallback_chunk": False,
                    "struct_kind": "point",
                    "section_role": "normative_unit",
                    "lineage_path": "body:1/item:0001",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(spo_dir / "sydoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "sydoc",
                    "provision_anchor": "body:1/item:0001",
                    "provision_citation": "пункт 1",
                    "legal_unit_subtype": "approval_bundle",
                    "statements": [
                        {
                            "subject_en": "issuing body",
                            "subject_uk": "орган, що прийняв акт",
                            "predicate": "approves",
                            "object_en": "review procedure",
                            "object_uk": "Порядок розгляду питань та проходження документів",
                            "fact_text": "Issuing body approves review procedure",
                            "confidence": 0.9,
                            "norm_type": "obligation",
                            "action_canon": "approves",
                            "norm_type_canon": "obligation",
                            "source_quote_uk": "1. Затвердити Порядок розгляду питань та проходження документів.",
                            "source_quote_start": 0,
                            "source_quote_end": 68,
                            "trust_tier": "normative_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "not_applicable",
                            "structure_quality": "structured_legal_unit",
                            "hallucination_flags_json": json.dumps(
                                [
                                    {
                                        "type": "ungrounded_subject",
                                        "severity": "medium",
                                        "detail": "synthetic subject placeholder",
                                    },
                                    {
                                        "type": "norm_type_mismatch",
                                        "severity": "medium",
                                        "detail": "no modal marker",
                                    },
                                ],
                                ensure_ascii=False,
                            ),
                            "links": [],
                        }
                    ],
                    "extraction_source": "rule_auto",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_grounded",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "sydoc": {
                "reestr_code": "sy-1",
                "name": "Про затвердження Порядку розгляду питань",
                "doc_type": "Рішення",
                "date_acc": "1997-05-21",
                "status": "active",
                "publisher": ["Державна комісія з питань впровадження електронних систем"],
            }
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.facts == 1
    assert stats.normative_facts == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT subject_uk, hallucination_flags_json
            FROM lex_normative_facts
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "Державна комісія з питань впровадження електронних систем"
        assert row[1] == "[]"


def test_build_graph_prefers_base_act_over_other_amendment_titles(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "tb"
    provisions_dir = tmp_path / "provisions" / "tb"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "titlebase.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Внесення змін до Закону України.",
                    "offset_start": 0,
                    "offset_end": 33,
                    "token_est": 6,
                    "text_hash": "hash-title-base",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "titlebase": {
                "reestr_code": "904",
                "name": 'Про внесення змін до Закону України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-05-05",
                "status": "active",
                "number": "904-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law": {
                "reestr_code": "124",
                "name": 'Закон України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
            "competing-amendment": {
                "reestr_code": "125",
                "name": 'Про внесення змін до Закону України "Про базовий акт" щодо окремих питань',
                "doc_type": "Закон",
                "date_acc": "2024-03-01",
                "status": "active",
                "number": "1235-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id
            FROM lex_amendments
            WHERE amending_doc_id = 'titlebase'
            """
        ).fetchone()
        assert row == ("base-law",)


def test_amendment_title_ignores_blank_title_candidates_and_prefers_exact_base() -> None:
    doc_metadata = {
        "source-doc": {
            "name": 'Про внесення змін до Закону України "Про базовий акт"',
            "doc_type": "Закон",
            "date_acc": "2024-05-05",
        },
        "base-law": {
            "name": "Про базовий акт",
            "doc_type": "Закон",
            "date_acc": "2024-01-01",
        },
        "derivative-law": {
            "name": 'Про зупинення дії Закону України "Про базовий акт"',
            "doc_type": "Закон",
            "date_acc": "2024-02-01",
        },
        "blank-doc": {
            "name": "",
            "doc_type": "Закон",
            "date_acc": "2023-12-01",
        },
    }

    inferred = _infer_amendment_target_from_title(
        source_doc_id="source-doc",
        doc_meta=doc_metadata["source-doc"],
        doc_index=build_doc_resolution_index(doc_metadata),
    )

    assert inferred is not None
    assert inferred.doc_id == "base-law"


def test_amendment_title_infers_instruction_target_from_genitive_stem() -> None:
    doc_metadata = {
        "source-doc": {
            "name": 'Про внесення змін і доповнень до Інструкції Національного банку України N 4 "Про організацію роботи з готівкового обігу установами банків України", затвердженої постановою Правління Національного банку України від 20.06.95 р. N 149',
            "doc_type": "Постанова",
            "date_acc": "1997-10-13",
        },
        "instruction-doc": {
            "name": 'Інструкція Національного банку України N 4 "Про організацію роботи з готівкового обігу установами банків України"',
            "doc_type": "Інструкція",
            "date_acc": "1995-06-20",
        },
    }

    inferred = _infer_amendment_target_from_title(
        source_doc_id="source-doc",
        doc_meta=doc_metadata["source-doc"],
        doc_index=build_doc_resolution_index(doc_metadata),
    )

    assert inferred is not None
    assert inferred.doc_id == "instruction-doc"


def test_build_graph_infers_amendment_target_from_source_text_using_resolution_metadata(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "sr"
    provisions_dir = tmp_path / "provisions" / "sr"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "srcdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": 'У статті 5 Закону України "Про базовий акт" слова «старий текст» замінити словами «новий текст».',
                    "offset_start": 0,
                    "offset_end": 102,
                    "token_est": 16,
                    "text_hash": "hash-source-amend",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "srcdoc": {
                "reestr_code": "902",
                "name": "Про внесення змін до деяких законодавчих актів України",
                "doc_type": "Закон",
                "date_acc": "2024-05-03",
                "status": "active",
                "number": "902-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        resolution_doc_metadata={
            "base-law-v1": {
                "reestr_code": "124",
                "name": 'Закон України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2023-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law-v2": {
                "reestr_code": "124",
                "name": 'Закон України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id, detected_by, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'srcdoc'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "base-law-v2"
        assert row[1] == "pattern+source_text"
        metadata = json.loads(row[2])
        assert metadata["target_hint"]["source"] == "source_text_inference_family_latest"


def test_build_graph_skips_unresolved_amendment_signals_for_non_amendment_docs(tmp_path) -> None:
    provisions_dir = tmp_path / "provisions" / "na"
    spo_dir = tmp_path / "spo_results" / "na"
    provisions_dir.mkdir(parents=True)
    spo_dir.mkdir(parents=True)

    with open(provisions_dir / "baseact.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:2",
                    "citation_label": "стаття 2",
                    "kind": "article",
                    "text": "Доповнено пунктом 2.6.",
                    "offset_start": 0,
                    "offset_end": 22,
                    "token_est": 4,
                    "text_hash": "hash-base-amend-signal",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:2",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "baseact": {
                "reestr_code": "678/1997",
                "name": "Про податок на додану вартість",
                "doc_type": "Закон України",
                "date_acc": "03.04.1997",
                "status": "Втратив чинність",
                "number": "168/97-ВР",
                "publisher": ["Верховна Рада України"],
            }
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 0
    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM lex_amendments").fetchone()[0] == 0


def test_build_graph_deduplicates_nested_single_target_amendments(tmp_path) -> None:
    provisions_dir = tmp_path / "provisions" / "sd"
    spo_dir = tmp_path / "spo_results" / "sd"
    provisions_dir.mkdir(parents=True)
    spo_dir.mkdir(parents=True)

    repeated = {
        "citation_label": "стаття 1",
        "kind": "article",
        "text": "У статті 5 слова «старий текст» замінити словами «новий текст».",
        "offset_start": 0,
        "offset_end": 66,
        "token_est": 12,
        "text_hash": "hash-dup-amend",
        "is_fallback_chunk": False,
        "struct_kind": "article",
        "section_role": "normative_unit",
        "fallback_allowed_for_reasoning": True,
    }
    with open(provisions_dir / "singleamend.jsonl", "w", encoding="utf-8") as fh:
        fh.write(json.dumps({**repeated, "anchor_path": "article:1", "lineage_path": "article:1"}, ensure_ascii=False) + "\n")
        fh.write(json.dumps({**repeated, "anchor_path": "article:1/para:1", "lineage_path": "article:1/para:1"}, ensure_ascii=False) + "\n")

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "singleamend": {
                "reestr_code": "901",
                "name": 'Про внесення змін до Закону України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-05-02",
                "status": "active",
                "number": "901-IX",
                "publisher": ["Верховна Рада України"],
            },
            "base-law": {
                "reestr_code": "124",
                "name": 'Закон України "Про базовий акт"',
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
                "number": "1234-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 1
    with duckdb.connect(str(db_path), read_only=True) as con:
        rows = con.execute(
            """
            SELECT COUNT(*), MIN(target_resolution_expected), MAX(amended_doc_id)
            FROM lex_amendments
            WHERE amending_doc_id = 'singleamend'
            """
        ).fetchone()
        assert rows == (1, True, "base-law")


def test_build_graph_marks_multi_target_amendments_as_not_expected_for_target_resolution(tmp_path) -> None:
    provisions_dir = tmp_path / "provisions" / "mt"
    spo_dir = tmp_path / "spo_results" / "mt"
    provisions_dir.mkdir(parents=True)
    spo_dir.mkdir(parents=True)

    with open(provisions_dir / "multiamend.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Доповнити статтю 5 новою частиною.",
                    "offset_start": 0,
                    "offset_end": 35,
                    "token_est": 8,
                    "text_hash": "hash-multi-target-amend",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "multiamend": {
                "reestr_code": "902",
                "name": "Про внесення змін до деяких законодавчих актів України",
                "doc_type": "Закон",
                "date_acc": "2024-05-03",
                "status": "active",
                "number": "902-IX",
                "publisher": ["Верховна Рада України"],
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    assert stats.amendments_with_target == 0
    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amended_doc_id, target_resolution_expected, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'multiamend'
            """
        ).fetchone()
        assert row is not None
        assert row[0] in (None, "")
        assert row[1] is False
        metadata = json.loads(row[2])
        assert metadata["doc_scope_kind"] == "multi_target_title"
        assert metadata["target_resolution_expected"] is False


def test_build_graph_does_not_fallback_to_date_acc_for_fact_temporal(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "tt"
    provisions_dir = tmp_path / "provisions" / "tt"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)

    with open(provisions_dir / "ttdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Орган зобов'язаний надати дозвіл.",
                    "offset_start": 0,
                    "offset_end": 33,
                    "token_est": 10,
                    "text_hash": "hash-tt",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(spo_dir / "ttdoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "ttdoc",
                    "provision_anchor": "article:1",
                    "provision_citation": "стаття 1",
                    "statements": [
                        {
                            "subject_en": "body",
                            "subject_uk": "орган",
                            "predicate": "requires",
                            "object_en": "permit",
                            "object_uk": "дозвіл",
                            "fact_text": "Body requires permit.",
                            "confidence": 0.9,
                            "norm_type": "obligation",
                            "action_canon": "requires",
                            "norm_type_canon": "obligation",
                            "trust_tier": "normative_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "unresolved",
                            "structure_quality": "structured_legal_unit",
                            "links": [],
                        }
                    ],
                    "extraction_source": "rule_auto",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "ttdoc": {
                "reestr_code": "555",
                "name": "Test act",
                "doc_type": "Закон",
                "date_acc": "2024-01-15",
                "status": "Чинний",
            }
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT effective_from, temporal_resolution_status
            FROM lex_facts
            WHERE doc_id = 'ttdoc'
            """
        ).fetchone()
        assert row == ("", "partial")
        doc_row = con.execute(
            """
            SELECT published_at, temporal_state, temporal_resolution_status
            FROM lex_doc_temporal
            WHERE doc_id = 'ttdoc'
            """
        ).fetchone()
        assert doc_row == ("", "current", "partial")


def test_build_graph_derives_clause_rows_and_reference_links_from_existing_artifacts(tmp_path) -> None:
    spo_dir = tmp_path / "spo_results" / "cl"
    provisions_dir = tmp_path / "provisions" / "cl"
    refs_dir = tmp_path / "resolved_references" / "cl"
    spo_dir.mkdir(parents=True)
    provisions_dir.mkdir(parents=True)
    refs_dir.mkdir(parents=True)

    with open(provisions_dir / "cldoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:3",
                    "citation_label": "стаття 3",
                    "kind": "article",
                    "text": "У разі потреби орган може звернутися до статті 5 цього Закону.",
                    "offset_start": 0,
                    "offset_end": 67,
                    "token_est": 12,
                    "text_hash": "hash-cl",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:3",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(spo_dir / "cldoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "cldoc",
                    "provision_anchor": "article:3",
                    "provision_citation": "стаття 3",
                    "legal_unit_subtype": "core_normative_clause",
                    "legal_unit_micro_subtype": "condition_tail",
                    "statements": [
                        {
                            "subject_en": "body",
                            "subject_uk": "орган",
                            "predicate": "grants",
                            "object_en": "request",
                            "object_uk": "звернення",
                            "fact_text": "Орган може звернутися.",
                            "confidence": 0.82,
                            "norm_type": "permission",
                            "action_canon": "grants",
                            "norm_type_canon": "permission",
                            "source_quote_uk": "У разі потреби орган може звернутися до статті 5 цього Закону.",
                            "source_quote_start": 0,
                            "source_quote_end": 67,
                            "trust_tier": "normative_fact",
                            "grounding_status": "exact_quote",
                            "canonical_status": "canonicalized",
                            "reference_resolution_status": "unresolved",
                            "structure_quality": "structured_legal_unit",
                            "links": [],
                        }
                    ],
                    "extraction_source": "rule_auto",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(refs_dir / "cldoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "cldoc",
                    "anchor_path": "article:3",
                    "target_raw": "стаття 5 цього Закону",
                    "target_doc_id": "target-doc",
                    "target_anchor": "article:5",
                    "relation_type": "references",
                    "resolution_confidence": 0.91,
                    "resolution_status": "resolved",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=tmp_path / "resolved_references",
        domains_dir=None,
        doc_metadata={
            "cldoc": {
                "reestr_code": "777",
                "name": "Test law",
                "doc_type": "Закон",
                "date_acc": "2024-01-01",
                "status": "active",
            }
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM lex_rule_clauses").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM lex_rule_links").fetchone()[0] == 1
        clause_row = con.execute("SELECT clause_type, text_uk FROM lex_rule_clauses").fetchone()
        assert clause_row[0] == "condition"
        assert "У разі потреби" in clause_row[1]


def test_build_graph_emits_general_amendment_fallback_for_title_only_amendment_doc(tmp_path) -> None:
    provisions_dir = tmp_path / "provisions" / "ga"
    spo_dir = tmp_path / "spo_results" / "ga"
    provisions_dir.mkdir(parents=True)
    spo_dir.mkdir(parents=True)

    with open(provisions_dir / "gadoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "anchor_path": "article:1",
                    "citation_label": "стаття 1",
                    "kind": "article",
                    "text": "Цей Закон набирає чинності з дня опублікування.",
                    "offset_start": 0,
                    "offset_end": 51,
                    "token_est": 10,
                    "text_hash": "hash-ga",
                    "is_fallback_chunk": False,
                    "struct_kind": "article",
                    "section_role": "normative_unit",
                    "lineage_path": "article:1",
                    "fallback_allowed_for_reasoning": True,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    with open(spo_dir / "gadoc.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "doc_id": "gadoc",
                    "provision_anchor": "article:1",
                    "provision_citation": "стаття 1",
                    "statements": [],
                    "extraction_source": "rule_auto",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    stats = build_graph(
        spo_results_dir=tmp_path / "spo_results",
        provisions_dir=tmp_path / "provisions",
        references_dir=None,
        domains_dir=None,
        doc_metadata={
            "gadoc": {
                "reestr_code": "888",
                "name": "Про внесення змін до Закону України \"Про освіту\"",
                "doc_type": "Закон",
                "date_acc": "2024-02-01",
                "status": "active",
            },
            "base-edu": {
                "reestr_code": "889",
                "name": "Про освіту",
                "doc_type": "Закон",
                "date_acc": "2020-01-01",
                "status": "active",
            },
        },
        db_path=db_path,
        insert_batch_size=10,
    )

    assert stats.amendments == 1
    with duckdb.connect(str(db_path), read_only=True) as con:
        row = con.execute(
            """
            SELECT amendment_type, metadata
            FROM lex_amendments
            WHERE amending_doc_id = 'gadoc'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "general_amendment"
        metadata = json.loads(row[1])
        assert metadata["fallback_generated"] is True
