from __future__ import annotations

import json
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.legal.batch.pipeline import PipelineStats
from polisyos.data_forge.domains.legal.batch.smoke import (
    SMOKE_PROFILES,
    SmokeCandidate,
    build_smoke_report,
    select_smoke_candidates,
    write_smoke_plan,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_select_smoke_candidates_prefers_diversity_and_cues() -> None:
    candidates = [
        SmokeCandidate("doc1", "Law 1", "Закон України", "law", "чинний", (), 1000, ("article",)),
        SmokeCandidate(
            "doc2", "Law 2", "Закон України", "law", "чинний", (), 900, ("appendix", "table")
        ),
        SmokeCandidate("doc3", "Order", "Наказ", "order", "чинний", (), 850, ("list",)),
        SmokeCandidate(
            "doc4", "Resolution", "Постанова КМУ", "cabinet_resolution", "чинний", (), 800, ()
        ),
        SmokeCandidate(
            "doc5", "Regulation", "Положення", "regulation", "чинний", (), 780, ("appendix",)
        ),
        SmokeCandidate("doc6", "Decision", "Рішення", "decision", "чинний", (), 700, ()),
    ]

    selected = select_smoke_candidates(candidates, sample_docs=4)
    selected_ids = [candidate.doc_id for candidate, _ in selected]

    assert len(selected_ids) == 4
    assert "doc2" in selected_ids
    assert len({candidate.doc_type_category for candidate, _ in selected}) >= 3


def test_build_smoke_report_summarizes_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "lex"
    selected = [
        (
            SmokeCandidate(
                "abdoc",
                "Test Law",
                "Закон України",
                "law",
                "чинний",
                ("Верховна Рада України",),
                1200,
                ("article", "appendix"),
            ),
            "cue_rich",
        )
    ]
    plan_path = write_smoke_plan(
        output_dir=output_dir,
        profile=SMOKE_PROFILES["fast"],
        selected=selected,
        scan_total=10,
    )

    _write_jsonl(
        output_dir / "provisions" / "ab" / "abdoc.jsonl",
        [
            {"anchor_path": "article:1", "kind": "article", "text": "Текст 1"},
            {
                "anchor_path": "full/chunk:0001",
                "kind": "full_chunk",
                "is_fallback_chunk": True,
                "fallback_allowed_for_reasoning": False,
                "text": "fallback",
            },
        ],
    )
    _write_jsonl(
        output_dir / "spo_results" / "ab" / "abdoc.jsonl",
        [
            {"statements": [], "extraction_source": "llm_timeout_fallback"},
            {"statements": [{"fact_text": "candidate"}]},
        ],
    )
    _write_jsonl(
        output_dir / "spo_grounded" / "ab" / "abdoc.jsonl",
        [
            {
                "statements": [
                    {
                        "trust_tier": "grounded_fact",
                        "source_quote_uk": "Текст 1",
                        "source_quote_start": 0,
                        "source_quote_end": 6,
                    },
                    {
                        "trust_tier": "normative_fact",
                        "source_quote_uk": "Текст 1",
                        "source_quote_start": 0,
                        "source_quote_end": 6,
                    },
                ]
            }
        ],
    )
    _write_jsonl(
        output_dir / "references" / "ab" / "abdoc.jsonl",
        [{"target_raw": "Закон України від 01.01.2024 № 1"}],
    )
    _write_jsonl(
        output_dir / "resolved_references" / "ab" / "abdoc.jsonl",
        [{"target_doc_id": "target1"}],
    )
    (output_dir / "publish").mkdir(parents=True, exist_ok=True)
    with open(output_dir / "publish" / "consumer_readiness.json", "w", encoding="utf-8") as fh:
        json.dump({"kind": "consumer_readiness", "ready": True}, fh)

    report_path, summary_path = build_smoke_report(
        output_dir=output_dir,
        profile=SMOKE_PROFILES["fast"],
        plan_path=plan_path,
        stats=PipelineStats(
            total_docs=1,
            total_provisions=2,
            total_spo=2,
            grounded_facts=1,
            normative_facts=1,
            reference_edges=1,
            quality_passed=True,
            elapsed_seconds=1.5,
        ),
    )

    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)

    assert report["sample_plan"]["selected_total"] == 1
    assert report["document_summary"]["with_grounded_facts"] == 1
    assert report["document_summary"]["with_resolved_refs"] == 1
    assert report["document_summary"]["with_timeout_fallbacks"] == 1
    assert "llm_timeout_fallback" in report["top_problem_docs"][0]["flags"]
    assert summary_path.exists()
