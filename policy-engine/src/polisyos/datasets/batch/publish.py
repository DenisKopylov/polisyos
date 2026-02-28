"""Stage 8: publish dataset pipeline artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from polisyos.batch_common.manifest import write_publish_manifest, write_stage_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig


def run_publish(config: DatasetBatchConfig) -> Path:
    """Write publish manifest with final dataset artifacts and checksums."""
    started_at = datetime.now(UTC).isoformat()

    artifacts = [
        config.db_path,
        config.index_dir / "ds_dataset_embeddings.npz",
        config.index_dir / "ds_dataset_index.hnsw",
        config.merged_records_path,
        config.duplicates_report_path,
        config.qc_report_path,
    ]
    existing = [path for path in artifacts if path.exists()]

    manifest_path = write_publish_manifest(
        manifest_path=config.publish_manifest_path,
        pipeline="datasets",
        artifacts=existing,
        qc_report_path=config.qc_report_path if config.qc_report_path.exists() else None,
        extra={
            "snapshot_root": str(config.snapshot_root),
            "component_dir": str(config.component_dir),
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
