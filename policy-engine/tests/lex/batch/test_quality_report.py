from __future__ import annotations

import json
from pathlib import Path

from polisyos.lex.batch.quality_report import (
    QualityGateThresholds,
    build_quality_report,
    evaluate_quality_gates,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_quality_report_counts_core_metrics(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_results_dir = tmp_path / "spo_results"

    _write_jsonl(
        provisions_dir / "00" / "doc1.jsonl",
        [
            {"kind": "full_text", "anchor_path": "full/chunk:0001"},
            {"kind": "full_text", "anchor_path": "full/chunk:0002"},
        ],
    )
    _write_jsonl(
        provisions_dir / "00" / "doc2.jsonl",
        [
            {"kind": "article", "anchor_path": "art:1"},
            {"kind": "point", "anchor_path": "art:1/pt:1"},
            {"kind": "point", "anchor_path": "art:1/pt:1"},
        ],
    )

    _write_jsonl(
        spo_results_dir / "00" / "doc1.jsonl",
        [
            {
                "statements": [],
                "normalization_report_json": "{\"oov_action\": 1}",
            },
            {
                "statements": [
                    {
                        "source_quote_uk": "",
                        "source_quote_start": None,
                        "source_quote_end": None,
                    }
                ],
                "normalization_report_json": "{\"oov_action\": 0}",
            },
        ],
    )

    report = build_quality_report(
        provisions_dir=provisions_dir,
        spo_results_dir=spo_results_dir,
    )

    assert report["provision_docs_total"] == 2
    assert report["full_only_docs"] == 1
    assert report["duplicate_anchor_docs"] == 1
    assert report["spo_rows_total"] == 2
    assert report["empty_statement_rows"] == 1
    assert report["statement_total"] == 1
    assert report["missing_quote_statements"] == 1
    assert report["oov_action_total"] == 1

    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(
            max_full_only_docs_pct=30.0,
            max_empty_statement_rows_pct=30.0,
            max_oov_action_rate_pct=30.0,
            max_missing_quote_rate_pct=30.0,
            max_duplicate_anchor_rate_pct=30.0,
            min_provision_docs_for_doc_rate=1,
            min_spo_rows_for_row_rate=1,
            min_statements_for_statement_rate=1,
        ),
    )
    assert gate.passed is False
    assert "full_only_docs_pct" in gate.failed_checks


def test_quality_gates_skip_checks_for_small_samples() -> None:
    report = {
        "provision_docs_total": 1,
        "full_only_docs_pct": 100.0,
        "duplicate_anchor_rate_pct": 100.0,
        "spo_rows_total": 1,
        "empty_statement_rows_pct": 100.0,
        "statement_total": 1,
        "missing_quote_rate_pct": 100.0,
        "oov_action_rate_pct": 100.0,
    }

    gate = evaluate_quality_gates(report=report, thresholds=QualityGateThresholds())

    assert gate.passed is True
    assert gate.failed_checks == []
    assert set(gate.skipped_checks) == {
        "full_only_docs_pct",
        "duplicate_anchor_rate_pct",
        "empty_statement_rows_pct",
        "oov_action_rate_pct",
        "missing_quote_rate_pct",
        "audit_miss_rate_pct",
        "llm_saved_pct",
    }
