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


def test_quality_report_includes_gate_metrics_and_fails_on_audit_miss(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_results_dir = tmp_path / "spo_results"
    llm_gate_manifest = tmp_path / "manifests" / "llm_gate.json"
    llm_gate_audit = tmp_path / "llm_gate_audit.jsonl"

    _write_jsonl(
        provisions_dir / "aa" / "doc1.jsonl",
        [{"kind": "article", "anchor_path": "art:1"}],
    )
    _write_jsonl(
        spo_results_dir / "aa" / "doc1.jsonl",
        [{"statements": [{"source_quote_uk": "x", "source_quote_start": 0, "source_quote_end": 1}]}],
    )

    llm_gate_manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(llm_gate_manifest, "w", encoding="utf-8") as fh:
        json.dump({"metrics": {"llm_candidate_total": 100, "llm_sent_total": 20, "llm_saved_pct": 80.0}}, fh)

    _write_jsonl(
        llm_gate_audit,
        [
            {"doc_id": "doc1", "provision_anchor": "art:1", "baseline_count": 0, "llm_count": 1, "miss": True},
            {"doc_id": "doc1", "provision_anchor": "art:2", "baseline_count": 1, "llm_count": 1, "miss": False},
        ],
    )

    report = build_quality_report(
        provisions_dir=provisions_dir,
        spo_results_dir=spo_results_dir,
        llm_gate_manifest_path=llm_gate_manifest,
        llm_gate_audit_path=llm_gate_audit,
    )
    assert report["llm_candidate_total"] == 100
    assert report["llm_sent_total"] == 20
    assert report["audit_sample_total"] == 2
    assert report["audit_miss_rate_pct"] == 50.0

    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(
            max_full_only_docs_pct=100.0,
            max_empty_statement_rows_pct=100.0,
            max_oov_action_rate_pct=100.0,
            max_missing_quote_rate_pct=100.0,
            max_duplicate_anchor_rate_pct=100.0,
            max_audit_miss_rate_pct=3.0,
            min_llm_saved_pct=50.0,
            min_provision_docs_for_doc_rate=1,
            min_spo_rows_for_row_rate=1,
            min_statements_for_statement_rate=1,
        ),
    )
    assert gate.passed is False
    assert "audit_miss_rate_pct" in gate.failed_checks

