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


def run_qc(config: BatchConfig, *, fail_fast: bool = True) -> QCReport:
    checks: list[QCCheck] = []
    metrics: dict[str, float | int] = {}

    db_exists = config.db_path.exists()
    checks.append(QCCheck(name="db_exists", passed=db_exists, value=int(db_exists), threshold=1))

    entities = facts = provisions = 0
    if db_exists:
        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            entities = int(con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()[0])
            facts = int(con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()[0])
            provisions = int(con.execute("SELECT COUNT(*) FROM lex_provisions").fetchone()[0])
        finally:
            con.close()

    metrics["entities"] = entities
    metrics["facts"] = facts
    metrics["provisions"] = provisions
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
