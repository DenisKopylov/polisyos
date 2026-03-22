"""QC stage for Lex pipeline outputs."""

from __future__ import annotations

from pathlib import Path
import json

import duckdb

from polisyos.batch_common.qc import QCCheck, QCReport, evaluate_fail_fast, write_qc_report
from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.benchmark import READINESS_THRESHOLDS
from polisyos.lex.batch.quality_report import (
    QualityGateThresholds,
    build_quality_report,
    evaluate_quality_gates,
)


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return bool(
        con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()[0]
    )


def _column_exists(con: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = ? AND column_name = ?
            """,
            [table_name, column_name],
        ).fetchone()[0]
    )


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator * 100.0) / denominator


def run_qc(config: BatchConfig, *, fail_fast: bool = True) -> QCReport:
    checks: list[QCCheck] = []
    metrics: dict[str, float | int] = {}

    db_exists = config.db_path.exists()
    checks.append(QCCheck(name="db_exists", passed=db_exists, value=int(db_exists), threshold=1))

    entities = facts = provisions = 0
    high_confidence_norms = 0
    pattern_feedback_queue_total = 0
    unresolved_contradictions = 0
    amendments_total = 0
    amendments_with_target = 0
    amendment_docs_extracted = 0
    amendment_candidate_docs = 0
    amendment_extraction_coverage_pct = 0.0
    amendment_target_resolution_pct = 0.0
    amendment_metric_available = False
    low_confidence_normative_pct = 0.0
    hallucination_rate_pct = 0.0
    low_confidence_normative_total = 0
    low_confidence_normative_available = False
    hallucination_total_checked = 0
    hallucination_metric_available = False
    consistency_metric_available = False
    if db_exists:
        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            if _table_exists(con, "lex_entities"):
                entities = int(con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()[0])
            if _table_exists(con, "lex_facts"):
                facts = int(con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()[0])
            if _table_exists(con, "lex_provisions"):
                provisions = int(con.execute("SELECT COUNT(*) FROM lex_provisions").fetchone()[0])
            if _table_exists(con, "lex_high_confidence_norms"):
                high_confidence_norms = int(con.execute("SELECT COUNT(*) FROM lex_high_confidence_norms").fetchone()[0])
            if _table_exists(con, "lex_pattern_feedback_queue"):
                pattern_feedback_queue_total = int(
                    con.execute("SELECT COUNT(*) FROM lex_pattern_feedback_queue").fetchone()[0]
                )
            if _table_exists(con, "lex_consistency_issues"):
                consistency_metric_available = True
                unresolved_sql = "SELECT COUNT(*) FROM lex_consistency_issues"
                if _column_exists(con, "lex_consistency_issues", "requires_manual_review"):
                    unresolved_sql += " WHERE COALESCE(requires_manual_review, TRUE) = TRUE"
                unresolved_contradictions = int(con.execute(unresolved_sql).fetchone()[0])
            if _table_exists(con, "lex_amendments"):
                amendment_metric_available = True
                amendments_total = int(con.execute("SELECT COUNT(*) FROM lex_amendments").fetchone()[0])
                amendments_with_target = int(
                    con.execute(
                        """
                        SELECT COUNT(*) FROM lex_amendments
                        WHERE TRIM(COALESCE(amended_doc_id, '')) != ''
                        """
                    ).fetchone()[0]
                )
                amendment_docs_extracted = int(
                    con.execute("SELECT COUNT(DISTINCT amending_doc_id) FROM lex_amendments").fetchone()[0]
                )
            if _table_exists(con, "lex_doc_versions"):
                amendment_candidate_docs = int(
                    con.execute(
                        """
                        SELECT COUNT(DISTINCT doc_id)
                        FROM lex_doc_versions
                        WHERE lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%внесення змін%'
                           OR lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%зміни до%'
                           OR lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%доповнен%'
                           OR lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%змін%'
                        """
                    ).fetchone()[0]
                )
            amendment_extraction_coverage_pct = _safe_pct(amendment_docs_extracted, amendment_candidate_docs)
            amendment_target_resolution_pct = _safe_pct(amendments_with_target, amendments_total)

            normative_table = ""
            normative_where = ""
            if _table_exists(con, "lex_normative_facts"):
                normative_table = "lex_normative_facts"
            elif _table_exists(con, "lex_facts") and _column_exists(con, "lex_facts", "trust_tier"):
                normative_table = "lex_facts"
                normative_where = " WHERE LOWER(COALESCE(trust_tier, '')) = 'normative_fact'"

            if normative_table and _column_exists(con, normative_table, "fused_confidence"):
                low_confidence_normative_available = True
                low_confidence_normative_total = int(
                    con.execute(f"SELECT COUNT(*) FROM {normative_table}{normative_where}").fetchone()[0]
                )
                low_confidence_normative = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {normative_table}
                        {normative_where}
                        {" AND " if normative_where else " WHERE "}
                        COALESCE(fused_confidence, 0.0) < 0.5
                        """
                    ).fetchone()[0]
                )
                low_confidence_normative_pct = _safe_pct(
                    low_confidence_normative,
                    low_confidence_normative_total,
                )

            hallucination_table = normative_table or ("lex_facts" if _table_exists(con, "lex_facts") else "")
            hallucination_where = normative_where if hallucination_table == normative_table else ""
            if hallucination_table and _column_exists(con, hallucination_table, "hallucination_flags_json"):
                hallucination_metric_available = True
                hallucination_total_checked = int(
                    con.execute(f"SELECT COUNT(*) FROM {hallucination_table}{hallucination_where}").fetchone()[0]
                )
                hallucination_flagged = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {hallucination_table}
                        {hallucination_where}
                        {" AND " if hallucination_where else " WHERE "}
                        TRIM(COALESCE(hallucination_flags_json, '')) NOT IN ('', '[]')
                        """
                    ).fetchone()[0]
                )
                hallucination_rate_pct = _safe_pct(
                    hallucination_flagged,
                    hallucination_total_checked,
                )
        finally:
            con.close()

    metrics["entities"] = entities
    metrics["facts"] = facts
    metrics["provisions"] = provisions
    metrics["high_confidence_norms"] = high_confidence_norms
    metrics["pattern_feedback_queue_total"] = pattern_feedback_queue_total
    metrics["unresolved_contradictions"] = unresolved_contradictions
    metrics["amendments_total"] = amendments_total
    metrics["amendments_with_target_total"] = amendments_with_target
    metrics["amendment_docs_extracted"] = amendment_docs_extracted
    metrics["amendment_candidate_docs"] = amendment_candidate_docs
    metrics["amendment_extraction_coverage_pct"] = round(amendment_extraction_coverage_pct, 3)
    metrics["amendment_target_resolution_pct"] = round(amendment_target_resolution_pct, 3)
    metrics["low_confidence_normative_facts_pct"] = round(low_confidence_normative_pct, 3)
    metrics["hallucination_rate_pct"] = round(hallucination_rate_pct, 3)
    checks.append(QCCheck(name="provisions_nonzero", passed=provisions > 0, value=provisions, threshold=1))

    # Quality gates on SPO extraction files.
    spo_results_dir = (
        config.grounded_spo_dir
        if config.grounded_spo_dir.exists() and any(config.grounded_spo_dir.glob("**/*.jsonl"))
        else config.spo_results_dir
    )
    gate_report = build_quality_report(
        provisions_dir=config.provisions_dir,
        spo_results_dir=spo_results_dir,
        llm_gate_manifest_path=config.llm_gate_manifest_path,
        llm_gate_audit_path=config.llm_gate_audit_path,
    )
    gate = evaluate_quality_gates(
        report=gate_report,
        thresholds=QualityGateThresholds(
            max_full_only_docs_pct=config.quality_max_full_only_docs_pct,
            max_empty_statement_rows_pct=config.quality_max_empty_statement_rows_pct,
            max_oov_action_rate_pct=config.quality_max_oov_action_rate_pct,
            max_missing_quote_rate_pct=config.quality_max_missing_quote_rate_pct,
            max_duplicate_anchor_rate_pct=config.quality_max_duplicate_anchor_rate_pct,
            max_audit_miss_rate_pct=config.quality_max_audit_miss_rate_pct,
            min_reference_resolution_coverage_pct=config.quality_min_reference_resolution_coverage_pct,
            min_llm_saved_pct=config.quality_min_llm_saved_pct,
            min_audit_samples_for_rate=config.quality_min_audit_samples_for_rate,
            min_provision_docs_for_doc_rate=config.quality_min_provision_docs_for_doc_rate,
            min_spo_rows_for_row_rate=config.quality_min_spo_rows_for_row_rate,
            min_statements_for_statement_rate=config.quality_min_statements_for_statement_rate,
            min_reference_rows_for_rate=config.quality_min_reference_rows_for_rate,
        ),
    )
    checks.append(
        QCCheck(
            name="spo_quality_gate",
            passed=gate.passed,
            severity="critical",
            value=0 if gate.passed else len(gate.failed_checks),
            threshold=0,
            message=", ".join(gate.failed_checks),
            status="failed" if gate.failed_checks else ("unstable" if gate.skipped_checks else "passed"),
        )
    )
    checks.append(
        QCCheck(
            name="llm_saved_pct",
            passed=float(gate.report.get("llm_saved_pct", 0.0) or 0.0) >= config.quality_min_llm_saved_pct,
            severity="warning",
            value=float(gate.report.get("llm_saved_pct", 0.0) or 0.0),
            threshold=config.quality_min_llm_saved_pct,
        )
    )
    checks.append(
        QCCheck(
            name="hallucination_rate_pct",
            passed=(
                hallucination_rate_pct <= config.quality_max_hallucination_rate_pct
                if hallucination_metric_available and hallucination_total_checked > 0
                else True
            ),
            severity="critical" if hallucination_metric_available and hallucination_total_checked > 0 else "warning",
            value=round(hallucination_rate_pct, 3),
            threshold=config.quality_max_hallucination_rate_pct,
            message=(
                ""
                if hallucination_metric_available and hallucination_total_checked > 0
                else "unstable: hallucination metric unavailable"
            ),
            status=(
                "passed"
                if hallucination_metric_available and hallucination_total_checked > 0 and hallucination_rate_pct <= config.quality_max_hallucination_rate_pct
                else (
                    "failed"
                    if hallucination_metric_available and hallucination_total_checked > 0
                    else "unstable"
                )
            ),
        )
    )
    checks.append(
        QCCheck(
            name="low_confidence_normative_facts_pct",
            passed=(
                low_confidence_normative_pct <= config.quality_max_low_confidence_normative_pct
                if low_confidence_normative_available and low_confidence_normative_total > 0
                else True
            ),
            severity="warning",
            value=round(low_confidence_normative_pct, 3),
            threshold=config.quality_max_low_confidence_normative_pct,
            message=(
                ""
                if low_confidence_normative_available and low_confidence_normative_total > 0
                else "unstable: fused confidence unavailable"
            ),
            status=(
                "passed"
                if low_confidence_normative_available and low_confidence_normative_total > 0 and low_confidence_normative_pct <= config.quality_max_low_confidence_normative_pct
                else (
                    "failed"
                    if low_confidence_normative_available and low_confidence_normative_total > 0
                    else "unstable"
                )
            ),
        )
    )
    checks.append(
        QCCheck(
            name="unresolved_contradictions",
            passed=(
                unresolved_contradictions <= config.quality_max_unresolved_contradictions
                if consistency_metric_available
                else True
            ),
            severity="warning",
            value=unresolved_contradictions,
            threshold=config.quality_max_unresolved_contradictions,
            message="" if consistency_metric_available else "unstable: consistency table unavailable",
            status=(
                "passed"
                if consistency_metric_available and unresolved_contradictions <= config.quality_max_unresolved_contradictions
                else ("failed" if consistency_metric_available else "unstable")
            ),
        )
    )
    checks.append(
        QCCheck(
            name="amendment_extraction_coverage_pct",
            passed=(
                amendment_extraction_coverage_pct >= config.quality_min_amendment_extraction_coverage_pct
                if amendment_metric_available and amendment_candidate_docs > 0
                else True
            ),
            severity="warning",
            value=round(amendment_extraction_coverage_pct, 3),
            threshold=config.quality_min_amendment_extraction_coverage_pct,
            message=(
                ""
                if amendment_metric_available and amendment_candidate_docs > 0
                else "unstable: amendment coverage metric unavailable"
            ),
            status=(
                "passed"
                if amendment_metric_available and amendment_candidate_docs > 0 and amendment_extraction_coverage_pct >= config.quality_min_amendment_extraction_coverage_pct
                else (
                    "failed"
                    if amendment_metric_available and amendment_candidate_docs > 0
                    else "unstable"
                )
            ),
        )
    )
    checks.append(
        QCCheck(
            name="amendment_target_resolution_pct",
            passed=(
                amendment_target_resolution_pct >= config.quality_min_amendment_target_resolution_pct
                if amendment_metric_available and amendments_total > 0
                else True
            ),
            severity="warning",
            value=round(amendment_target_resolution_pct, 3),
            threshold=config.quality_min_amendment_target_resolution_pct,
            message=(
                ""
                if amendment_metric_available and amendments_total > 0
                else "unstable: amendment target metric unavailable"
            ),
            status=(
                "passed"
                if amendment_metric_available and amendments_total > 0 and amendment_target_resolution_pct >= config.quality_min_amendment_target_resolution_pct
                else (
                    "failed"
                    if amendment_metric_available and amendments_total > 0
                    else "unstable"
                )
            ),
        )
    )

    for metric in (
        "full_only_docs_pct",
        "empty_statement_rows_pct",
        "oov_action_rate_pct",
        "missing_quote_rate_pct",
        "duplicate_anchor_rate_pct",
        "reference_resolution_coverage_pct",
        "llm_candidate_total",
        "llm_sent_total",
        "llm_saved_pct",
        "audit_sample_total",
        "audit_miss_rate_pct",
        "doc_family_breakdown",
        "top_problem_families",
        "legal_unit_subtype_breakdown",
        "top_problem_subtypes",
        "top_unresolved_subtype_families",
        "timeout_retry_groups_total",
        "timeout_retry_success_total",
        "timeout_retry_failure_total",
        "timeout_retry_success_rate_pct",
        "deferred_reason_counts",
    ):
        if metric not in gate.report:
            continue
        value = gate.report.get(metric)
        if isinstance(value, (int, float)):
            metrics[metric] = float(value)
        else:
            metrics[metric] = value
    metrics["quality_gate_failed_checks"] = gate.failed_checks
    metrics["quality_gate_warning_failed_checks"] = gate.warning_failed_checks
    metrics["quality_gate_skipped_checks"] = gate.skipped_checks

    reference_rows_total = int(gate.report.get("reference_rows_total", 0) or 0)
    reference_coverage = float(gate.report.get("reference_resolution_coverage_pct", 0.0) or 0.0)
    checks.append(
        QCCheck(
            name="reference_resolution_coverage_pct",
            passed=(reference_coverage >= config.quality_min_reference_resolution_coverage_pct) if reference_rows_total >= config.quality_min_reference_rows_for_rate else True,
            severity="critical" if reference_rows_total >= config.quality_min_reference_rows_for_rate else "warning",
            value=reference_coverage,
            threshold=config.quality_min_reference_resolution_coverage_pct,
            message=(
                ""
                if reference_rows_total >= config.quality_min_reference_rows_for_rate
                else f"unstable: reference_rows_total={reference_rows_total} < min={config.quality_min_reference_rows_for_rate}"
            ),
            status=(
                "unstable"
                if reference_rows_total < config.quality_min_reference_rows_for_rate
                else (
                    "passed"
                    if reference_coverage >= config.quality_min_reference_resolution_coverage_pct
                    else "failed"
                )
            ),
        )
    )

    if config.benchmark_report_path.exists():
        with open(config.benchmark_report_path, "r", encoding="utf-8") as fh:
            benchmark_payload = json.load(fh)
        benchmark_metrics = benchmark_payload.get("metrics", {})
        benchmark_readiness = benchmark_payload.get("readiness", {})
        if isinstance(benchmark_metrics, dict):
            metrics["benchmark_metrics"] = benchmark_metrics
            readiness_totals = {
                "benchmark_search_top5_relevance_pct": "benchmark_search_cases_total",
                "benchmark_constraints_ready_pct": "benchmark_constraints_domains_total",
                "benchmark_cross_graph_non_unknown_pct": "benchmark_cross_graph_cases_total",
                "benchmark_normpack_ready_pct": "benchmark_normpack_cases_total",
            }
            for metric_name, threshold in READINESS_THRESHOLDS.items():
                if metric_name in benchmark_metrics:
                    metric_value = float(benchmark_metrics.get(metric_name, 0.0) or 0.0)
                    total_name = readiness_totals.get(metric_name, metric_name.replace("_pct", "_total"))
                    total = int(benchmark_metrics.get(total_name, 0) or 0)
                    checks.append(
                        QCCheck(
                            name=metric_name,
                            passed=(metric_value >= threshold) if total > 0 else True,
                            severity="critical" if total > 0 else "warning",
                            value=metric_value,
                            threshold=threshold,
                            message="" if total > 0 else f"unstable: {total_name}=0",
                            status=(
                                "unstable"
                                if total <= 0
                                else ("passed" if metric_value >= threshold else "failed")
                            ),
                        )
                    )
        checks.append(
            QCCheck(
                name="benchmark_readiness",
                passed=bool(benchmark_readiness.get("passed", False)),
                severity="critical",
                value=int(bool(benchmark_readiness.get("passed", False))),
                threshold=1,
                message=", ".join(benchmark_readiness.get("failed_checks", [])),
                status="passed" if bool(benchmark_readiness.get("passed", False)) else "failed",
            )
        )

    # Local embedding artifact presence.
    artifact_names = (
        "lex_entity_embeddings.npz",
        "lex_entity_index.hnsw",
        "lex_fact_embeddings.npz",
        "lex_fact_index.hnsw",
        "lex_provision_embeddings.npz",
        "lex_provision_index.hnsw",
    )
    missing = [name for name in artifact_names if not (config.output_dir / name).exists()]
    checks.append(
        QCCheck(
            name="embedding_artifacts_present",
            passed=not missing,
            value=len(missing),
            threshold=0,
            message=", ".join(missing),
        )
    )

    report = QCReport(scope="lex", checks=checks, metrics=metrics)
    report_path = config.output_dir / "qc_report.json"
    write_qc_report(report_path, report)
    evaluate_fail_fast(report, fail_fast=fail_fast)
    return report
