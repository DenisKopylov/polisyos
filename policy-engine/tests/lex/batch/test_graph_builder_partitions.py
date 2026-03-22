from __future__ import annotations

import json

import duckdb

from polisyos.lex.batch.graph_builder import build_graph


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
        assert metadata["target_hint"]["source"] == "doc_title_inference"
