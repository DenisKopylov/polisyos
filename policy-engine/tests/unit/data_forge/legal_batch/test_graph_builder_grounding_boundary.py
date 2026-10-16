from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb

from polisyos.data_forge.domains.legal.batch.graph_builder import build_graph
from polisyos.data_forge.domains.legal.batch.provisions_io import write_provisions

if TYPE_CHECKING:
    from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _statement(
    *,
    statement_id: str,
    quote: str,
    start: int | None,
    end: int | None,
    subject_en: str = "authority",
    subject_uk: str = "The authority",
    predicate: str = "requires",
    object_en: str = "annual_report",
    object_uk: str = "annual report",
    fact_text: str = "The authority must publish the annual report.",
    norm_type: str = "obligation",
    action_canon: str = "requires",
    norm_type_canon: str = "obligation",
) -> dict[str, object]:
    return {
        "statement_id": statement_id,
        "subject_en": subject_en,
        "subject_uk": subject_uk,
        "predicate": predicate,
        "object_en": object_en,
        "object_uk": object_uk,
        "fact_text": fact_text,
        "confidence": 0.99,
        "norm_type": norm_type,
        "norm_type_canon": norm_type_canon,
        "action_canon": action_canon,
        "canonical_status": "canonicalized",
        "source_quote_uk": quote,
        "source_quote_start": start,
        "source_quote_end": end,
        "grounding_status": "exact_quote",
        "trust_tier": "normative_fact",
    }


def test_graph_builder_recomputes_grounding_for_raw_direct_intake(tmp_path: Path) -> None:
    doc_id = "abdoc"
    anchor = "body:1/item:0001"
    provision_text = "The authority shall publish the annual report before March."
    exact_quote = provision_text
    absent_quote = "This quotation is absent from the selected provision."
    prefix_only_quote = "The authority shall publish the annual report by March."
    provisions_dir = tmp_path / "provisions"
    spo_dir = tmp_path / "raw_spo"
    db_path = tmp_path / "lex.duckdb"
    write_provisions(
        provisions_dir=provisions_dir,
        doc_id=doc_id,
        provisions=[
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
        spo_dir / doc_id[:2] / f"{doc_id}.jsonl",
        [
            {
                "doc_id": doc_id,
                "provision_anchor": anchor,
                "provision_citation": "controlled test fixture; not legal authority",
                "extraction_source": "rule_auto",
                "statements": [
                    _statement(
                        statement_id="unmatched-forged-offset",
                        quote=absent_quote,
                        start=0,
                        end=1,
                    ),
                    _statement(
                        statement_id="aligned-exact",
                        quote=exact_quote,
                        start=None,
                        end=None,
                    ),
                    _statement(
                        statement_id="unrelated-exact",
                        quote=exact_quote,
                        start=None,
                        end=None,
                        subject_en="agency",
                        subject_uk="агентство",
                        object_en="farmland",
                        object_uk="землю",
                        fact_text="The agency must seize farmland.",
                    ),
                    _statement(
                        statement_id="opposite-modality-exact",
                        quote=exact_quote,
                        start=None,
                        end=None,
                        predicate="prohibits",
                        object_en="publication of annual report",
                        object_uk="оприлюднення річного звіту",
                        fact_text="The authority must not publish the annual report before March.",
                        norm_type="prohibition",
                        action_canon="prohibits",
                        norm_type_canon="prohibition",
                    ),
                    _statement(
                        statement_id="negated-exact",
                        quote=exact_quote,
                        start=None,
                        end=None,
                        fact_text="The authority is not required to publish the annual report.",
                    ),
                    _statement(
                        statement_id="whole-provision-fallback",
                        quote="",
                        start=None,
                        end=None,
                        subject_en="agency",
                        subject_uk="агентство",
                        object_en="farmland",
                        object_uk="землю",
                        fact_text="The agency must seize farmland.",
                    ),
                    _statement(
                        statement_id="prefix-only-match",
                        quote=prefix_only_quote,
                        start=None,
                        end=None,
                    ),
                ],
            },
            {
                "doc_id": doc_id,
                "provision_anchor": "body:9/item:0009",
                "provision_citation": "unresolved source context",
                "extraction_source": "rule_auto",
                "statements": [
                    _statement(
                        statement_id="missing-source-forged-offset",
                        quote="This quotation has no selected provision.",
                        start=0,
                        end=1,
                    )
                ],
            },
        ],
    )

    build_graph(
        spo_results_dir=spo_dir,
        provisions_dir=provisions_dir,
        references_dir=None,
        domains_dir=None,
        doc_metadata={},
        db_path=db_path,
    )

    with duckdb.connect(str(db_path), read_only=True) as con:
        rows = con.execute(
            """
            SELECT statement_id, trust_tier, grounding_status,
                   source_quote_start, source_quote_end
            FROM lex_facts
            ORDER BY statement_id
            """
        ).fetchall()
        normative_count = con.execute("SELECT COUNT(*) FROM lex_normative_facts").fetchone()[0]
        candidate_count = con.execute("SELECT COUNT(*) FROM lex_fact_candidates").fetchone()[0]

    rows_by_id = {row[0]: row[1:] for row in rows}
    assert rows_by_id == {
        "aligned-exact": ("search_candidate", "exact_quote", 0, len(exact_quote)),
        "missing-source-forged-offset": (
            "search_candidate",
            "quote_without_offsets",
            None,
            None,
        ),
        "negated-exact": ("search_candidate", "exact_quote", 0, len(exact_quote)),
        "opposite-modality-exact": ("search_candidate", "exact_quote", 0, len(exact_quote)),
        "prefix-only-match": ("search_candidate", "quote_without_offsets", None, None),
        "unmatched-forged-offset": ("search_candidate", "quote_without_offsets", None, None),
        "unrelated-exact": ("search_candidate", "exact_quote", 0, len(exact_quote)),
        "whole-provision-fallback": ("search_candidate", "exact_quote", 0, len(exact_quote)),
    }
    assert normative_count == 0
    assert candidate_count == len(rows_by_id)
