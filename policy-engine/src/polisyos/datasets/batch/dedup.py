"""Stage 3: Merge normalized files and deduplicate by source+agency+dataset_id."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.knowledge.types import DatasetRecord


class MergeStats(dict):
    """Simple dict-like stats container."""


def merge_and_dedup(config: DatasetBatchConfig) -> MergeStats:
    started_at = datetime.now(UTC).isoformat()
    merged: list[DatasetRecord] = []
    seen: dict[str, DatasetRecord] = {}
    duplicates: list[tuple[str, str, str, str, str, str]] = []

    normalized_files = sorted(config.normalized_dir.glob("*.jsonl"))
    for file_path in normalized_files:
        with open(file_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = DatasetRecord.model_validate_json(line)
                key = rec.dedup_key or f"{rec.source}|{rec.agency}|{rec.dataset_id}"
                if key in seen:
                    kept = seen[key]
                    duplicates.append((
                        key,
                        kept.id,
                        rec.id,
                        rec.source,
                        rec.agency,
                        rec.dataset_id,
                    ))
                    continue
                seen[key] = rec
                merged.append(rec)

    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        for rec in merged:
            fh.write(rec.model_dump_json() + "\n")

    with open(config.duplicates_report_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["dedup_key", "kept_id", "dropped_id", "source", "agency", "dataset_id"])
        writer.writerows(duplicates)

    stats = MergeStats(
        normalized_files=len(normalized_files),
        merged_records=len(merged),
        duplicates=len(duplicates),
    )

    write_stage_manifest(
        manifest_path=config.manifests_dir / "merge_dedup.json",
        stage="merge_dedup",
        status="ok",
        metrics=dict(stats),
        artifacts=[config.merged_records_path, config.duplicates_report_path],
        started_at=started_at,
    )
    return stats
