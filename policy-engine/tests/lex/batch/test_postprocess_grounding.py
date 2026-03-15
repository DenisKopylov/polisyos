from __future__ import annotations

import json
from pathlib import Path

from polisyos.lex.batch.postprocess import ground_spo_quotes


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
    with open(out_path, "r", encoding="utf-8") as fh:
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
    with open(out_path, "r", encoding="utf-8") as fh:
        row = json.loads(fh.readline())
    stmt = row["statements"][0]
    assert stmt["grounding_status"] == "exact_quote"
    assert stmt["source_quote_start"] == 0
    assert stmt["trust_tier"] == "normative_fact"
