from __future__ import annotations

import json
from typing import TYPE_CHECKING

from polisyos.lex.batch.quality_report import (
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
                "normalization_report_json": '{"oov_action": 1}',
            },
            {
                "statements": [
                    {
                        "predicate": "mentions",
                        "source_quote_uk": "",
                        "source_quote_start": None,
                        "source_quote_end": None,
                    }
                ],
                "normalization_report_json": '{"oov_action": 0}',
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


def test_quality_report_ignores_stale_row_level_oov_when_statements_are_canonicalized(
    tmp_path: Path,
) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_results_dir = tmp_path / "spo_results"

    _write_jsonl(
        provisions_dir / "00" / "doc1.jsonl",
        [
            {"kind": "article", "anchor_path": "art:1"},
        ],
    )
    _write_jsonl(
        spo_results_dir / "00" / "doc1.jsonl",
        [
            {
                "statements": [
                    {
                        "predicate": "встановлює",
                        "action_canon": "requires",
                        "source_quote_uk": "Орган встановлює вимоги.",
                        "source_quote_start": 0,
                        "source_quote_end": 25,
                    }
                ],
                "normalization_report_json": '{"oov_action": 4}',
            }
        ],
    )

    report = build_quality_report(
        provisions_dir=provisions_dir,
        spo_results_dir=spo_results_dir,
    )

    assert report["statement_total"] == 1
    assert report["oov_action_total"] == 0


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
        "audit_sample_total": 2,
        "audit_miss_rate_pct": 100.0,
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
        "primary_clause_miss_rate_pct",
        "audit_miss_rate_pct",
        "reference_resolution_coverage_pct",
    }


def test_quality_gates_block_on_primary_clause_miss_but_keep_raw_audit_miss_as_warning() -> None:
    report = {
        "provision_docs_total": 50,
        "full_only_docs_pct": 0.0,
        "duplicate_anchor_rate_pct": 0.0,
        "spo_rows_total": 200,
        "empty_statement_rows_pct": 0.0,
        "statement_total": 300,
        "missing_quote_rate_pct": 0.0,
        "grounded_statement_total": 300,
        "grounded_missing_quote_rate_pct": 0.0,
        "oov_action_rate_pct": 0.0,
        "audit_sample_total": 20,
        "audit_miss_rate_pct": 20.0,
        "primary_clause_miss_rate_pct": 0.0,
        "reference_rows_total": 20,
        "reference_resolution_coverage_pct": 100.0,
    }

    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(
            min_provision_docs_for_doc_rate=1,
            min_spo_rows_for_row_rate=1,
            min_statements_for_statement_rate=1,
            min_audit_samples_for_rate=1,
            min_reference_rows_for_rate=1,
        ),
    )

    assert gate.passed is True
    assert gate.failed_checks == []
    assert gate.warning_failed_checks == ["audit_miss_rate_pct"]

    report["primary_clause_miss_rate_pct"] = 20.0
    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(
            min_provision_docs_for_doc_rate=1,
            min_spo_rows_for_row_rate=1,
            min_statements_for_statement_rate=1,
            min_audit_samples_for_rate=1,
            min_reference_rows_for_rate=1,
        ),
    )

    assert gate.passed is False
    assert gate.failed_checks == ["primary_clause_miss_rate_pct"]
    assert gate.warning_failed_checks == ["audit_miss_rate_pct"]


def test_quality_report_prefers_grounded_missing_quote_rate(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions" / "ab"
    spo_dir = tmp_path / "spo_grounded" / "ab"
    provisions_dir.mkdir(parents=True)
    spo_dir.mkdir(parents=True)

    _write_jsonl(
        provisions_dir / "abdoc.jsonl",
        [
            {
                "anchor_path": "article:1",
                "kind": "article",
                "text": "Орган зобов'язаний надати дозвіл.",
            }
        ],
    )

    _write_jsonl(
        spo_dir / "abdoc.jsonl",
        [
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
                        "trust_tier": "grounded_fact",
                        "source_quote_uk": "Орган зобов'язаний надати дозвіл.",
                        "source_quote_start": 0,
                        "source_quote_end": 33,
                    },
                    {
                        "subject_en": "body",
                        "subject_uk": "орган",
                        "predicate": "defines",
                        "object_en": "context",
                        "object_uk": "контекст",
                        "fact_text": "Search-only candidate.",
                        "confidence": 0.2,
                        "norm_type": "definition",
                        "trust_tier": "search_candidate",
                        "source_quote_uk": "",
                        "source_quote_start": None,
                        "source_quote_end": None,
                    },
                ],
            }
        ],
    )

    report = build_quality_report(
        provisions_dir=tmp_path / "provisions",
        spo_results_dir=tmp_path / "spo_grounded",
    )

    assert report["missing_quote_rate_pct"] == 50.0
    assert report["grounded_missing_quote_rate_pct"] == 0.0

    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(
            min_provision_docs_for_doc_rate=1,
            min_spo_rows_for_row_rate=1,
            min_statements_for_statement_rate=1,
            max_missing_quote_rate_pct=5.0,
        ),
    )
    assert gate.passed is True


def test_quality_report_builds_family_breakdown_and_audit_categories(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_dir = tmp_path / "spo_grounded"
    refs_dir = tmp_path / "resolved_references"
    audit_path = tmp_path / "llm_gate_audit.jsonl"

    _write_jsonl(
        provisions_dir / "aa" / "lawdoc.jsonl",
        [
            {
                "kind": "article",
                "anchor_path": "article:1",
                "doc_type_category": "law",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
                "text": "Орган зобов'язаний подати звіт.",
            },
            {
                "kind": "point",
                "anchor_path": "article:1/point:1",
                "doc_type_category": "law",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
                "text": "Подати звіт до органу.",
            },
        ],
    )
    _write_jsonl(
        provisions_dir / "bb" / "orderdoc.jsonl",
        [
            {
                "kind": "table_row",
                "struct_kind": "table_row",
                "section_role": "table_clause",
                "appendix_id": "1",
                "table_id": "t1",
                "anchor_path": "appendix:1/table:1/row:1",
                "doc_type_category": "order",
                "legal_unit_subtype": "tariff_threshold_row",
                "route_class": "deterministic_only",
                "text": "Порогове значення 10%",
            }
        ],
    )
    _write_jsonl(
        spo_dir / "aa" / "lawdoc.jsonl",
        [
            {
                "extraction_source": "audit_llm",
                "provision_anchor": "article:1",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
                "statements": [
                    {
                        "predicate": "requires",
                        "action_canon": "requires",
                        "norm_type": "obligation",
                        "trust_tier": "grounded_fact",
                        "source_quote_uk": "Подати звіт до органу.",
                        "source_quote_start": 0,
                        "source_quote_end": 21,
                    }
                ],
            }
        ],
    )
    _write_jsonl(
        spo_dir / "bb" / "orderdoc.jsonl",
        [
            {
                "extraction_source": "llm_timeout_fallback",
                "provision_anchor": "appendix:1/table:1/row:1",
                "legal_unit_subtype": "tariff_threshold_row",
                "route_class": "deterministic_only",
                "statements": [],
            }
        ],
    )
    _write_jsonl(
        audit_path,
        [
            {
                "doc_id": "lawdoc",
                "quality_family": "law",
                "miss": True,
                "miss_categories": ["obligation", "reference_amendment"],
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
            }
        ],
    )
    _write_jsonl(
        refs_dir / "aa" / "lawdoc.jsonl",
        [
            {"anchor_path": "article:1", "resolution_status": "resolved"},
        ],
    )
    _write_jsonl(
        refs_dir / "bb" / "orderdoc.jsonl",
        [
            {"anchor_path": "appendix:1/table:1/row:1", "resolution_status": "unresolved"},
        ],
    )

    report = build_quality_report(
        provisions_dir=provisions_dir,
        spo_results_dir=spo_dir,
        llm_gate_audit_path=audit_path,
        resolved_references_dir=refs_dir,
    )

    assert report["audit_miss_category_counts"]["obligation"] == 1
    assert report["reference_resolution_coverage_pct"] == 50.0
    assert report["doc_family_breakdown"]["law"]["audit_miss_rate_pct"] == 100.0
    assert report["doc_family_breakdown"]["appendix_heavy"]["timeout_fallback_rate_pct"] == 100.0
    assert (
        report["legal_unit_subtype_breakdown"]["core_normative_clause"]["audit_miss_rate_pct"]
        == 100.0
    )
    assert (
        report["legal_unit_subtype_breakdown"]["tariff_threshold_row"]["empty_statement_rows_pct"]
        == 100.0
    )
    assert report["top_problem_subtypes"][0]["legal_unit_subtype"] in {
        "core_normative_clause",
        "tariff_threshold_row",
    }
    assert report["top_problem_families"][0]["family"] in {"law", "appendix_heavy"}
    assert (
        report["top_unresolved_subtype_families"][0]["legal_unit_subtype"] == "tariff_threshold_row"
    )


def test_quality_report_uses_doc_metadata_manifest_for_family_classification(
    tmp_path: Path,
) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_dir = tmp_path / "spo_grounded"
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir(parents=True)
    (manifests_dir / "doc_metadata.json").write_text(
        json.dumps(
            {
                "documents": {
                    "lawdoc": {
                        "doc_type_category": "law",
                        "name": "Закон України про тестовий обов'язок",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _write_jsonl(
        provisions_dir / "aa" / "lawdoc.jsonl",
        [
            {
                "kind": "article",
                "anchor_path": "article:1",
                "text": "Орган зобов'язаний подати звіт.",
            },
        ],
    )
    _write_jsonl(
        spo_dir / "aa" / "lawdoc.jsonl",
        [
            {
                "extraction_source": "rule_auto",
                "statements": [
                    {
                        "predicate": "requires",
                        "action_canon": "requires",
                        "trust_tier": "grounded_fact",
                        "source_quote_uk": "Орган зобов'язаний подати звіт.",
                        "source_quote_start": 0,
                        "source_quote_end": 31,
                    }
                ],
            }
        ],
    )

    report = build_quality_report(
        provisions_dir=provisions_dir,
        spo_results_dir=spo_dir,
    )

    assert "law" in report["doc_family_breakdown"]
    assert report["doc_family_breakdown"]["law"]["provision_docs_total"] == 1


def test_quality_gates_fail_on_family_outlier() -> None:
    report = {
        "provision_docs_total": 30,
        "full_only_docs_pct": 0.0,
        "duplicate_anchor_rate_pct": 0.0,
        "spo_rows_total": 100,
        "empty_statement_rows_pct": 5.0,
        "statement_total": 150,
        "missing_quote_rate_pct": 0.0,
        "grounded_statement_total": 120,
        "grounded_missing_quote_rate_pct": 0.0,
        "oov_action_rate_pct": 0.0,
        "audit_sample_total": 12,
        "audit_miss_rate_pct": 0.0,
        "llm_candidate_total": 10,
        "llm_saved_pct": 80.0,
        "doc_family_breakdown": {
            "law": {
                "provision_docs_total": 8,
                "full_only_docs_pct": 0.0,
                "duplicate_anchor_rate_pct": 0.0,
                "spo_rows_total": 20,
                "empty_statement_rows_pct": 40.0,
                "statement_total": 40,
                "missing_quote_rate_pct": 0.0,
                "grounded_statement_total": 20,
                "grounded_missing_quote_rate_pct": 0.0,
                "oov_action_rate_pct": 0.0,
                "audit_sample_total": 4,
                "audit_miss_rate_pct": 0.0,
            }
        },
    }

    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(),
    )

    assert gate.passed is True
    assert "family:law:empty_statement_rows_pct" in gate.hotspot_failed_checks


def test_quality_gates_skip_reference_gate_for_search_only_scaffold_subtype() -> None:
    report = {
        "provision_docs_total": 30,
        "full_only_docs_pct": 0.0,
        "duplicate_anchor_rate_pct": 0.0,
        "spo_rows_total": 100,
        "empty_statement_rows_pct": 5.0,
        "statement_total": 150,
        "missing_quote_rate_pct": 0.0,
        "grounded_statement_total": 120,
        "grounded_missing_quote_rate_pct": 0.0,
        "oov_action_rate_pct": 0.0,
        "audit_sample_total": 12,
        "audit_miss_rate_pct": 0.0,
        "reference_rows_total": 30,
        "reference_resolution_coverage_pct": 100.0,
        "legal_unit_subtype_breakdown": {
            "table_scaffold": {
                "provision_docs_total": 20,
                "spo_rows_total": 20,
                "statement_total": 0,
                "audit_sample_total": 0,
                "reference_rows_total": 20,
                "reference_resolution_coverage_pct": 10.0,
                "route_class_counts": {"search_only": 20},
            }
        },
    }

    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(),
    )

    assert gate.passed is True
    assert "subtype:table_scaffold:reference_resolution_coverage_pct" not in gate.failed_checks
    assert "subtype:table_scaffold:reference_resolution_coverage_pct" in gate.skipped_checks


def test_quality_report_splits_primary_and_secondary_clause_miss_metrics(tmp_path: Path) -> None:
    provisions_dir = tmp_path / "provisions"
    spo_dir = tmp_path / "spo_results"
    audit_path = tmp_path / "llm_gate_audit.jsonl"

    _write_jsonl(
        provisions_dir / "aa" / "doc1.jsonl",
        [
            {
                "kind": "article",
                "anchor_path": "article:1",
                "doc_type_category": "law",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
                "text": "Орган зобов'язаний подати звіт.",
            }
        ],
    )
    _write_jsonl(
        spo_dir / "aa" / "doc1.jsonl",
        [
            {
                "provision_anchor": "article:1",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
                "statements": [],
            }
        ],
    )
    _write_jsonl(
        audit_path,
        [
            {
                "doc_id": "doc1",
                "provision_anchor": "article:1",
                "quality_family": "law",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
                "miss": True,
                "miss_categories": ["obligation", "additional_statement"],
                "primary_clause_miss": True,
                "secondary_clause_miss": True,
            }
        ],
    )

    report = build_quality_report(
        provisions_dir=provisions_dir,
        spo_results_dir=spo_dir,
        llm_gate_audit_path=audit_path,
    )

    assert report["audit_miss_rate_pct"] == 100.0
    assert report["primary_clause_miss_rate_pct"] == 100.0
    assert report["secondary_clause_miss_rate_pct"] == 100.0
    assert report["doc_family_breakdown"]["law"]["primary_clause_miss_total"] == 1
    assert report["doc_family_breakdown"]["law"]["secondary_clause_miss_total"] == 1
