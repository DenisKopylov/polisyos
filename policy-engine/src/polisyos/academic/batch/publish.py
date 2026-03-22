"""Stage 8: publish academic pipeline artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.benchmark import READINESS_THRESHOLDS
from polisyos.batch_common.manifest import write_publish_manifest, write_stage_manifest


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def _stage_metrics(path: Path) -> dict[str, object]:
    payload = _load_json(path)
    metrics = payload.get("metrics")
    return dict(metrics) if isinstance(metrics, dict) else {}


def _write_pipeline_readiness_manifest(config: AcademicBatchConfig) -> tuple[Path, dict[str, bool]]:
    qc_payload = _load_json(config.qc_report_path)
    benchmark_payload = _load_json(config.benchmark_report_path)
    qc_metrics = qc_payload.get("metrics") if isinstance(qc_payload.get("metrics"), dict) else {}
    benchmark_metrics = (
        benchmark_payload.get("metrics")
        if isinstance(benchmark_payload.get("metrics"), dict)
        else {}
    )
    resolve_metrics = _stage_metrics(config.manifests_dir / "resolve_extract.json")

    provider_timeouts = int(resolve_metrics.get("provider_timeout_count", 0) or 0)
    watchdog_timeouts = int(resolve_metrics.get("watchdog_timeout_count", 0) or 0)
    resolve_records = int(resolve_metrics.get("records", 0) or 0)
    timeout_share_pct = (
        ((provider_timeouts + watchdog_timeouts) / max(1, resolve_records)) * 100.0
        if resolve_records
        else 0.0
    )

    readiness = {
        "canonical_runtime_ready": float(qc_metrics.get("runtime_demanded_canonical_resolution_rate_pct", 0.0) or 0.0) >= 90.0,
        "parameter_utility_ready": float(benchmark_metrics.get("parameter_supported_ratio", 0.0) or 0.0)
        >= READINESS_THRESHOLDS["parameter_supported_ratio"],
        "causal_prior_utility_ready": float(benchmark_metrics.get("causal_supported_ratio", 0.0) or 0.0)
        >= READINESS_THRESHOLDS["causal_supported_ratio"],
        "cross_graph_utility_ready": float(benchmark_metrics.get("causal_supported_plus_mixed_ratio", 0.0) or 0.0)
        >= READINESS_THRESHOLDS["causal_supported_plus_mixed_ratio"],
        "transport_utility_ready": float(benchmark_metrics.get("non_default_transport_evidence_ratio", 0.0) or 0.0)
        >= READINESS_THRESHOLDS["non_default_transport_evidence_ratio"],
        "scholar_retrieval_ready": float(benchmark_metrics.get("scholar_query_coverage_ratio", 0.0) or 0.0)
        >= READINESS_THRESHOLDS["scholar_query_coverage_ratio"],
        "operational_stability_ready": timeout_share_pct <= 25.0,
    }
    readiness["consumer_ready"] = all(readiness.values())

    payload = {
        "kind": "academic_pipeline_readiness",
        "snapshot_root": str(config.snapshot_root),
        "component_dir": str(config.component_dir),
        "thresholds": {
            **READINESS_THRESHOLDS,
            "runtime_demanded_canonical_resolution_rate_pct": 90.0,
            "timeout_share_pct": 25.0,
        },
        "readiness": readiness,
        "benchmark_metrics": {
            key: benchmark_metrics.get(key, 0.0)
            for key in (
                "parameter_supported_ratio",
                "causal_supported_ratio",
                "causal_supported_plus_mixed_ratio",
                "scholar_query_coverage_ratio",
                "non_default_transport_evidence_ratio",
                "family_edge_coverage_ratio",
                "runtime_demanded_canonical_resolution_rate_pct",
            )
        },
        "qc_metrics": {
            key: qc_metrics.get(key, 0.0)
            for key in (
                "runtime_demanded_canonical_resolution_rate_pct",
                "global_canonical_resolution_rate_pct",
                "simulation_ready_numeric_count",
                "family_edge_count",
                "retracted_contamination_count",
                "json_validation_failures",
            )
        },
        "operational_stability": {
            "resolve_records": resolve_records,
            "provider_timeout_count": provider_timeouts,
            "watchdog_timeout_count": watchdog_timeouts,
            "timeout_share_pct": round(timeout_share_pct, 3),
        },
        "artifacts": {
            "benchmark_report": str(config.benchmark_report_path) if config.benchmark_report_path.exists() else "",
            "qc_report": str(config.qc_report_path) if config.qc_report_path.exists() else "",
            "runtime_demand_backlog": str(config.runtime_demand_backlog_path)
            if config.runtime_demand_backlog_path.exists()
            else "",
        },
    }
    config.readiness_report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.readiness_report_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return config.readiness_report_path, readiness


def run_publish(config: AcademicBatchConfig) -> Path:
    """Write publish manifest for academic pipeline outputs."""
    started_at = datetime.now(UTC).isoformat()
    readiness_report_path, readiness = _write_pipeline_readiness_manifest(config)
    artifacts = [
        config.db_path,
        config.index_dir / "ac_work_embeddings.npz",
        config.index_dir / "ac_work_index.hnsw",
        config.merged_records_path,
        config.topic_links_path,
        config.duplicates_report_path,
        config.topics_catalog_path,
        config.selected_topic_works_path,
        config.selected_global_works_path,
        config.fulltext_resolved_path,
        config.resolve_extract_progress_path,
        config.resolve_extract_attempts_path,
        config.resolve_extract_results_path,
        config.resolve_extract_final_results_path,
        config.resolve_extract_final_works_path,
        config.resolve_extract_errors_path,
        config.fulltext_fetch_log_path,
        config.llm_request_log_path,
        config.raw_claim_candidates_path,
        config.published_claims_path,
        config.raw_claim_candidates_final_path,
        config.published_claims_final_path,
        config.context_attributes_path,
        config.context_attributes_clean_path,
        config.moderation_edges_path,
        config.moderation_edges_clean_path,
        config.simulation_ready_numeric_path,
        config.article_extraction_results_path,
        config.claim_adjudication_passes_path,
        config.claim_adjudications_path,
        config.claim_consensus_report_path,
        config.canonical_review_queue_path,
        config.edge_synthesis_report_path,
        config.runtime_demand_backlog_path,
        readiness_report_path,
        config.llm_gate_manifest_path,
        config.llm_gate_audit_path,
        config.qc_report_path,
    ]
    existing = [path for path in artifacts if path.exists()]

    manifest_path = write_publish_manifest(
        manifest_path=config.publish_manifest_path,
        pipeline="academic",
        artifacts=existing,
        qc_report_path=config.qc_report_path if config.qc_report_path.exists() else None,
        extra={
            "snapshot_root": str(config.snapshot_root),
            "component_dir": str(config.component_dir),
            "run_id": config.run_id,
            "pass_name": config.pass_name,
            "runtime_demand_backlog": str(config.runtime_demand_backlog_path)
            if config.runtime_demand_backlog_path.exists()
            else "",
            "readiness_report": str(readiness_report_path),
            "readiness": readiness,
        },
    )

    write_stage_manifest(
        manifest_path=config.manifests_dir / "publish.json",
        stage="publish",
        status="ok",
        metrics={"artifacts": len(existing)},
        artifacts=[manifest_path],
        started_at=started_at,
    )
    return manifest_path
