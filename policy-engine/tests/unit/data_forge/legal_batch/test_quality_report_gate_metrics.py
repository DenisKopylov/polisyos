from __future__ import annotations

import json
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.legal.batch.quality_report import (
    QualityGateThresholds,
    build_quality_report,
    evaluate_quality_gates,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_quality_report_includes_gate_metrics_and_treats_raw_audit_miss_as_warning(
    tmp_path: Path,
) -> None:
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
        [
            {
                "statements": [
                    {"source_quote_uk": "x", "source_quote_start": 0, "source_quote_end": 1}
                ]
            }
        ],
    )

    llm_gate_manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(llm_gate_manifest, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "metrics": {
                    "llm_candidate_total": 100,
                    "llm_sent_total": 20,
                    "llm_saved_pct": 80.0,
                    "llm_gap_fill_sent_total": 12,
                    "llm_gap_fill_added_statements_total": 7,
                    "baseline_vs_gap_fill_added_statements_total": 7,
                    "llm_gap_fill_timeout_fallback_total": 2,
                    "llm_gap_fill_empty_responses_total": 1,
                    "llm_gap_fill_gain_rate_pct": 58.333,
                    "timeout_retry_groups_total": 4,
                    "timeout_retry_success_total": 3,
                    "timeout_retry_failure_total": 1,
                    "deferred_reason_counts": {"deferred_no_llm": 2, "circuit_breaker_open": 1},
                    "top_gap_fill_subtypes": [
                        {"legal_unit_subtype": "core_normative_clause", "count": 8}
                    ],
                    "top_gap_fill_families": [{"family": "law", "count": 9}],
                    "top_timeout_gap_fill_families": [{"family": "appendix_heavy", "count": 2}],
                }
            },
            fh,
        )

    _write_jsonl(
        llm_gate_audit,
        [
            {
                "doc_id": "doc1",
                "provision_anchor": "art:1",
                "baseline_count": 0,
                "llm_count": 1,
                "miss": True,
            },
            {
                "doc_id": "doc1",
                "provision_anchor": "art:2",
                "baseline_count": 1,
                "llm_count": 1,
                "miss": False,
            },
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
    assert report["llm_gap_fill_sent_total"] == 12
    assert report["llm_gap_fill_added_statements_total"] == 7
    assert report["llm_gap_fill_timeout_fallback_total"] == 2
    assert report["timeout_retry_groups_total"] == 4
    assert report["timeout_retry_success_total"] == 3
    assert report["timeout_retry_failure_total"] == 1
    assert report["timeout_retry_success_rate_pct"] == 75.0
    assert report["deferred_reason_counts"]["deferred_no_llm"] == 2
    assert report["top_gap_fill_subtypes"][0]["legal_unit_subtype"] == "core_normative_clause"
    assert report["audit_sample_total"] == 2
    assert report["audit_miss_rate_pct"] == 50.0
    assert report["primary_clause_miss_rate_pct"] == 0.0

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
            min_audit_samples_for_rate=1,
            min_provision_docs_for_doc_rate=1,
            min_spo_rows_for_row_rate=1,
            min_statements_for_statement_rate=1,
        ),
    )
    assert gate.passed is True
    assert gate.failed_checks == []
    assert "audit_miss_rate_pct" in gate.warning_failed_checks


def test_missing_quote_gates_use_full_rows_across_all_breakdowns(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_results_dir = tmp_path / "spo_results"
    provision_anchor = "article:1/point:1"
    _write_jsonl(
        provisions_dir / "aa" / "lawdoc.jsonl",
        [
            {
                "kind": "point",
                "anchor_path": provision_anchor,
                "doc_type_category": "law",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_only",
                "text": "The authority shall publish the annual report.",
            }
        ],
    )
    statements = [
        {
            "statement_id": "only-marked-row",
            "source_quote_uk": "The authority shall publish the annual report.",
            "trust_tier": "normative_fact",
            "predicate": "requires",
        }
    ]
    statements.extend(
        {
            "statement_id": f"missing-{index}",
            "source_quote_uk": "",
            "trust_tier": "search_candidate",
            "predicate": "requires",
        }
        for index in range(99)
    )
    result_path = spo_results_dir / "aa" / "lawdoc.jsonl"

    def report_for_current_marker() -> dict:
        _write_jsonl(
            result_path,
            [
                {
                    "doc_id": "lawdoc",
                    "provision_anchor": provision_anchor,
                    "statements": statements,
                }
            ],
        )
        return build_quality_report(
            provisions_dir=provisions_dir,
            spo_results_dir=spo_results_dir,
        )

    thresholds = QualityGateThresholds(
        min_provision_docs_for_doc_rate=1,
        min_spo_rows_for_row_rate=1,
        min_statements_for_statement_rate=1,
        max_missing_quote_rate_pct=5.0,
        max_oov_action_rate_pct=100.0,
    )
    gate_results = []
    for marker_present in (True, False):
        if marker_present:
            statements[0]["trust_tier"] = "normative_fact"
        else:
            statements[0].pop("trust_tier")
        report = report_for_current_marker()
        assert report["statement_total"] == 100
        assert report["missing_quote_rate_pct"] == 99.0
        assert report["grounded_missing_quote_rate_pct"] == 0.0
        family = report["doc_family_breakdown"]["law"]
        subtype = report["legal_unit_subtype_breakdown"]["core_normative_clause"]
        assert family["missing_quote_rate_pct"] == 99.0
        assert subtype["missing_quote_rate_pct"] == 99.0
        gate = evaluate_quality_gates(report=report, thresholds=thresholds)
        assert "missing_quote_rate_pct" in gate.failed_checks
        assert "family:law:missing_quote_rate_pct" in gate.hotspot_failed_checks
        assert "subtype:core_normative_clause:missing_quote_rate_pct" in gate.hotspot_failed_checks
        gate_results.append((gate.passed, gate.failed_checks, gate.hotspot_failed_checks))

    assert gate_results[0] == gate_results[1]
