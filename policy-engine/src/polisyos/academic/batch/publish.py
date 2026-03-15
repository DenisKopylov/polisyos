"""Stage 8: publish academic pipeline artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.batch_common.manifest import write_publish_manifest, write_stage_manifest


def run_publish(config: AcademicBatchConfig) -> Path:
    """Write publish manifest for academic pipeline outputs."""
    started_at = datetime.now(UTC).isoformat()
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
