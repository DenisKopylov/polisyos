from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb
import pytest

from polisyos.data_forge.domains.legal.batch.postprocess import (
    export_normative_claims,
    ground_spo_quotes,
)
from polisyos.data_forge.domains.legal.contracts import SPOCandidate
from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationVerificationMissingError,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_ground_spo_quotes_keeps_search_only_headers_out_of_grounded_layer(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_dir = tmp_path / "spo_results"
    grounded_dir = tmp_path / "spo_grounded"

    _write_jsonl(
        provisions_dir / "ab" / "abdoc.jsonl",
        [
            {
                "anchor_path": "appendix:1/table:001/header:0001",
                "kind": "paragraph",
                "text": "Назва   Значення",
                "is_fallback_chunk": False,
                "struct_kind": "table_row",
                "section_role": "table_header",
                "fallback_allowed_for_reasoning": False,
            }
        ],
    )
    _write_jsonl(
        spo_dir / "ab" / "abdoc.jsonl",
        [
            {
                "doc_id": "abdoc",
                "provision_anchor": "appendix:1/table:001/header:0001",
                "provision_citation": "Заголовок таблиці 1",
                "statements": [
                    {
                        "subject_en": "body",
                        "subject_uk": "орган",
                        "predicate": "requires",
                        "object_en": "value",
                        "object_uk": "значення",
                        "fact_text": "Body requires value.",
                        "confidence": 0.95,
                        "norm_type": "obligation",
                        "source_quote_uk": "Назва   Значення",
                        "source_quote_start": 0,
                        "source_quote_end": 15,
                        "action_raw": "requires",
                        "action_canon": "requires",
                        "norm_type_raw": "obligation",
                        "norm_type_canon": "obligation",
                    }
                ],
            }
        ],
    )

    stats = ground_spo_quotes(
        spo_results_dir=spo_dir,
        provisions_dir=provisions_dir,
        output_dir=grounded_dir,
    )

    assert stats["statements_total"] == 1
    out_path = grounded_dir / "ab" / "abdoc.jsonl"
    with open(out_path, encoding="utf-8") as fh:
        row = json.loads(fh.readline())
    stmt = row["statements"][0]
    assert stmt["structure_quality"] == "fallback_search_only"
    assert stmt["trust_tier"] == "search_candidate"


def test_ground_spo_quotes_upgrades_recovered_offsets_to_exact_quote(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_dir = tmp_path / "spo_results"
    grounded_dir = tmp_path / "spo_grounded"

    _write_jsonl(
        provisions_dir / "ab" / "abdoc.jsonl",
        [
            {
                "anchor_path": "body:1/item:0001",
                "kind": "point",
                "text": "1. Орган зобов'язаний подати звіт до 1 січня.",
                "is_fallback_chunk": False,
                "struct_kind": "enumeration_item",
                "section_role": "normative_unit",
                "fallback_allowed_for_reasoning": True,
            }
        ],
    )
    _write_jsonl(
        spo_dir / "ab" / "abdoc.jsonl",
        [
            {
                "doc_id": "abdoc",
                "provision_anchor": "body:1/item:0001",
                "provision_citation": "Пункт переліку 1",
                "statements": [
                    {
                        "subject_en": "body",
                        "subject_uk": "орган",
                        "predicate": "requires",
                        "object_en": "report",
                        "object_uk": "звіт",
                        "fact_text": "Body requires report.",
                        "confidence": 0.95,
                        "norm_type": "obligation",
                        "source_quote_uk": "1. Орган зобов'язаний подати звіт до 1 січня.",
                        "source_quote_start": None,
                        "source_quote_end": None,
                        "grounding_status": "quote_without_offsets",
                        "action_raw": "requires",
                        "action_canon": "requires",
                        "norm_type_raw": "obligation",
                        "norm_type_canon": "obligation",
                    }
                ],
            }
        ],
    )

    ground_spo_quotes(
        spo_results_dir=spo_dir,
        provisions_dir=provisions_dir,
        output_dir=grounded_dir,
    )

    out_path = grounded_dir / "ab" / "abdoc.jsonl"
    with open(out_path, encoding="utf-8") as fh:
        row = json.loads(fh.readline())
    stmt = row["statements"][0]
    assert stmt["grounding_status"] == "exact_quote"
    assert stmt["source_quote_start"] == 0
    assert stmt["trust_tier"] == "search_candidate"


def test_ground_spo_quotes_requires_a_whole_source_bound_quote(tmp_path: Path) -> None:
    cases = [
        {
            "doc_id": "abexact",
            "provision": "The authority shall publish the annual report by March.",
            "quote": "The authority shall publish the annual report by March.",
            "offsets": (0, 55),
            "status": "exact_quote",
            "tier": "search_candidate",
            "span": (0, 55),
        },
        {
            "doc_id": "abfinder",
            "provision": "The authority shall publish the annual report by March.",
            "quote": "The authority shall publish the annual report by March.",
            "offsets": (None, None),
            "status": "exact_quote",
            "tier": "search_candidate",
            "span": (0, 55),
        },
        {
            "doc_id": "abforged",
            "provision": "The authority shall publish the annual report by March.",
            "quote": "This quotation is absent from the selected provision.",
            "offsets": (0, 1),
            "status": "quote_without_offsets",
            "tier": "search_candidate",
            "span": (None, None),
        },
        {
            "doc_id": "abnooffset",
            "provision": "The authority shall publish the annual report by March.",
            "quote": "This quotation is absent from the selected provision.",
            "offsets": (None, None),
            "status": "quote_without_offsets",
            "tier": "search_candidate",
            "span": (None, None),
        },
        {
            "doc_id": "aboutside",
            "provision": "The authority shall publish the annual report by March.",
            "quote": "This quotation is absent from the selected provision.",
            "offsets": (-9, 99_999),
            "status": "quote_without_offsets",
            "tier": "search_candidate",
            "span": (None, None),
        },
        {
            "doc_id": "abwrong",
            "provision": "Heading. The authority shall publish the annual report by March.",
            "quote": "The authority shall publish the annual report by March.",
            "offsets": (0, 1),
            "status": "exact_quote",
            "tier": "search_candidate",
            "span": (9, 64),
        },
        {
            "doc_id": "abprefix",
            "provision": "The authority shall publish the annual report before March.",
            "quote": "The authority shall publish the annual report by March.",
            "offsets": (None, None),
            "status": "quote_without_offsets",
            "tier": "search_candidate",
            "span": (None, None),
        },
        {
            "doc_id": "abspace",
            "provision": "The authority shall\tpublish the annual\nreport by March.",
            "quote": "The authority shall publish the annual report by March.",
            "offsets": (None, None),
            "status": "exact_quote",
            "tier": "search_candidate",
            "span": (0, 55),
        },
        {
            "doc_id": "abunicode",
            "provision": "Орган зобов\u2019язаний подати звіт до 1 січня.",
            "quote": "Орган зобов'язаний подати звіт до 1 січня.",
            "offsets": (None, None),
            "status": "exact_quote",
            "tier": "search_candidate",
            "span": (0, 42),
        },
    ]
    provisions_dir = tmp_path / "provisions"
    spo_dir = tmp_path / "spo_results"
    grounded_dir = tmp_path / "spo_grounded"

    for case in cases:
        anchor = "body:1/item:0001"
        _write_jsonl(
            provisions_dir / case["doc_id"][:2] / f"{case['doc_id']}.jsonl",
            [
                {
                    "anchor_path": anchor,
                    "kind": "point",
                    "text": case["provision"],
                    "is_fallback_chunk": False,
                    "struct_kind": "enumeration_item",
                    "section_role": "normative_unit",
                    "fallback_allowed_for_reasoning": True,
                }
            ],
        )
        statement = {
            "statement_id": case["doc_id"],
            "subject_en": "authority",
            "subject_uk": "Орган" if case["quote"].startswith("Орган") else "The authority",
            "predicate": "requires",
            "object_en": "report",
            "object_uk": "report",
            "fact_text": "The authority must publish the annual report.",
            "confidence": 0.99,
            "norm_type": "obligation",
            "norm_type_canon": "obligation",
            "action_canon": "requires",
            "canonical_status": "canonicalized",
            "source_quote_uk": case["quote"],
            "source_quote_start": case["offsets"][0],
            "source_quote_end": case["offsets"][1],
            "grounding_status": "exact_quote",
            "trust_tier": "normative_fact",
        }
        _write_jsonl(
            spo_dir / case["doc_id"][:2] / f"{case['doc_id']}.jsonl",
            [
                {
                    "doc_id": case["doc_id"],
                    "provision_anchor": anchor,
                    "provision_citation": "controlled test fixture; not legal authority",
                    "extraction_source": "rule_auto",
                    "statements": [statement],
                }
            ],
        )

    ground_spo_quotes(
        spo_results_dir=spo_dir,
        provisions_dir=provisions_dir,
        output_dir=grounded_dir,
    )
    for case in cases:
        out_path = grounded_dir / case["doc_id"][:2] / f"{case['doc_id']}.jsonl"
        with open(out_path, encoding="utf-8") as fh:
            statement = json.loads(fh.readline())["statements"][0]
        assert statement["grounding_status"] == case["status"]
        assert statement["trust_tier"] == case["tier"]
        assert (statement["source_quote_start"], statement["source_quote_end"]) == case["span"]


def test_quote_occurrence_does_not_promote_unverified_claim_relation(tmp_path: Path) -> None:
    provision_text = "The Ministry shall publish the annual budget report by March."
    anchor = "body:1/item:0001"
    statements = [
        {
            "statement_id": "aligned-claim",
            "confidence": 0.99,
            "subject_en": "The Ministry",
            "subject_uk": "Міністерство",
            "predicate": "requires",
            "object_en": "annual budget report",
            "object_uk": "річний бюджетний звіт",
            "fact_text": "The Ministry must publish the annual budget report by March.",
            "norm_type": "obligation",
            "action_canon": "requires",
            "norm_type_canon": "obligation",
            "source_quote_uk": provision_text,
            "trust_tier": "normative_fact",
        },
        {
            "statement_id": "unrelated-claim",
            "confidence": 0.99,
            "subject_en": "The Ministry",
            "subject_uk": "Міністерство",
            "predicate": "requires",
            "object_en": "farmland",
            "object_uk": "землю",
            "fact_text": "The Ministry must seize farmland.",
            "norm_type": "obligation",
            "action_canon": "requires",
            "norm_type_canon": "obligation",
            "source_quote_uk": provision_text,
            "trust_tier": "normative_fact",
        },
        {
            "statement_id": "opposite-modality-claim",
            "confidence": 0.99,
            "subject_en": "The Ministry",
            "subject_uk": "Міністерство",
            "predicate": "prohibits",
            "object_en": "publication of annual budget report",
            "object_uk": "оприлюднення річного бюджетного звіту",
            "fact_text": "The Ministry must not publish the annual budget report by March.",
            "norm_type": "prohibition",
            "action_canon": "prohibits",
            "norm_type_canon": "prohibition",
            "source_quote_uk": provision_text,
            "trust_tier": "normative_fact",
        },
        {
            "statement_id": "negated-claim",
            "confidence": 0.99,
            "subject_en": "The Ministry",
            "subject_uk": "Міністерство",
            "predicate": "requires",
            "object_en": "publication of annual budget report",
            "object_uk": "оприлюднення річного бюджетного звіту",
            "fact_text": "The Ministry is not required to publish the annual budget report.",
            "norm_type": "obligation",
            "action_canon": "requires",
            "norm_type_canon": "obligation",
            "source_quote_uk": provision_text,
            "trust_tier": "normative_fact",
        },
        {
            "statement_id": "whole-provision-fallback",
            "confidence": 0.99,
            "subject_en": "The Ministry",
            "subject_uk": "Міністерство",
            "predicate": "requires",
            "object_en": "farmland",
            "object_uk": "землю",
            "fact_text": "The Ministry must seize farmland.",
            "norm_type": "obligation",
            "action_canon": "requires",
            "norm_type_canon": "obligation",
            "source_quote_uk": "",
            "trust_tier": "normative_fact",
        },
    ]
    provisions_dir = tmp_path / "provisions"
    raw_dir = tmp_path / "spo_results"
    output_dir = tmp_path / "spo_grounded"
    _write_jsonl(
        provisions_dir / "ab" / "abdoc.jsonl",
        [
            {
                "anchor_path": anchor,
                "kind": "point",
                "text": provision_text,
                "is_fallback_chunk": False,
                "struct_kind": "enumeration_item",
                "section_role": "normative_unit",
                "fallback_allowed_for_reasoning": True,
            }
        ],
    )
    _write_jsonl(
        raw_dir / "ab" / "abdoc.jsonl",
        [
            {
                "doc_id": "abdoc",
                "provision_anchor": anchor,
                "provision_citation": "controlled fixture; not a legal authority claim",
                "extraction_source": "llm_candidate",
                "statements": statements,
            }
        ],
    )

    stats = ground_spo_quotes(
        spo_results_dir=raw_dir,
        provisions_dir=provisions_dir,
        output_dir=output_dir,
    )
    with (output_dir / "ab" / "abdoc.jsonl").open(encoding="utf-8") as source:
        grounded = json.loads(source.readline())["statements"]

    by_id = {row["statement_id"]: row for row in grounded}
    assert set(by_id) == {row["statement_id"] for row in statements}
    assert all(row["trust_tier"] == "search_candidate" for row in grounded)
    assert stats["statements_normative"] == 0
    for statement_id in (
        "aligned-claim",
        "unrelated-claim",
        "opposite-modality-claim",
        "negated-claim",
        "whole-provision-fallback",
    ):
        row = by_id[statement_id]
        assert row["grounding_status"] == "exact_quote"
        assert row["source_quote_uk"] == provision_text
        assert row["source_quote_start"] == 0
        assert row["source_quote_end"] == len(provision_text)


def test_spo_candidate_cannot_self_attest_a_trust_tier() -> None:
    candidate = SPOCandidate.model_validate(
        {
            "subject_en": "authority",
            "subject_uk": "орган",
            "predicate": "requires",
            "object_en": "report",
            "object_uk": "звіт",
            "fact_text": "The authority must publish a report.",
            "confidence": 0.99,
            "norm_type": "obligation",
            "norm_type_canon": "obligation",
            "canonical_status": "canonicalized",
            "source_quote_uk": "The authority shall publish a report.",
            "source_quote_start": 0,
            "source_quote_end": len("The authority shall publish a report."),
            "grounding_status": "exact_quote",
            "trust_tier": "normative_fact",
        }
    )

    assert candidate.grounding_status == "exact_quote"
    assert candidate.trust_tier == "search_candidate"


def test_normative_claim_export_refuses_before_writing_unverified_authority(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_normative_facts (
                fact_id VARCHAR, doc_id VARCHAR, provision_anchor VARCHAR,
                provision_citation VARCHAR, subject_id VARCHAR, subject_en VARCHAR,
                predicate VARCHAR, object_id VARCHAR, object_en VARCHAR,
                action_canon VARCHAR, norm_type_canon VARCHAR, trust_tier VARCHAR,
                jurisdiction VARCHAR, top_domain VARCHAR, effective_from VARCHAR,
                effective_to VARCHAR, source_quote_uk VARCHAR, source_quote_start INTEGER,
                source_quote_end INTEGER, doc_name VARCHAR, doc_reestr_code VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO lex_normative_facts VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "f1",
                "d1",
                "a1",
                "Art. 1",
                "s",
                "agency",
                "requires",
                "o",
                "report",
                "requires",
                "obligation",
                "normative_fact",
                "UA",
                "fiscal",
                "2024-01-01",
                "",
                "The agency shall report.",
                0,
                25,
                "Law",
                "UA:1",
            ],
        )
    output_dir = tmp_path / "claim_exports"

    with pytest.raises(LegalSourceRelationVerificationMissingError):
        export_normative_claims(db_path=db_path, output_dir=output_dir)

    assert not output_dir.exists()
