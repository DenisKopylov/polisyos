"""QC stage for Lex pipeline outputs."""

from __future__ import annotations

from pathlib import Path

import duckdb

from polisyos.batch_common.qc import QCCheck, QCReport, evaluate_fail_fast, write_qc_report
from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.quality_report import QualityGateThresholds, build_quality_report, evaluate_quality_gates


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
    gate_report = build_quality_report(
        provisions_dir=config.provisions_dir,
        spo_results_dir=config.spo_results_dir,
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
            min_llm_saved_pct=config.quality_min_llm_saved_pct,
            min_provision_docs_for_doc_rate=config.quality_min_provision_docs_for_doc_rate,
            min_spo_rows_for_row_rate=config.quality_min_spo_rows_for_row_rate,
            min_statements_for_statement_rate=config.quality_min_statements_for_statement_rate,
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
        "llm_candidate_total",
        "llm_sent_total",
        "llm_saved_pct",
        "audit_sample_total",
        "audit_miss_rate_pct",
    ):
        if metric in gate.report:
            metrics[metric] = float(gate.report.get(metric, 0.0) or 0.0)

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
