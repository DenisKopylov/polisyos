"""Stage 3: Merge normalized files and deduplicate by source+agency+dataset_id."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig


class MergeStats(dict):
    """Simple dict-like stats container."""


def _dedup_quality_score(record: DatasetRecord) -> float:
    """Score a record for dedup winner selection (higher = better)."""
    score = 0.0
    # Has a meaningful description
    score += 0.25 * (1.0 if record.description and len(record.description) > 10 else 0.0)
    # Has metric bindings
    score += 0.25 * min(len(record.polisyos_metrics) / 3, 1.0)
    # Execution readiness
    readiness = getattr(record.quality, "execution_readiness_score", 0.0) or 0.0
    score += 0.20 * readiness
    # Has freshness info
    has_freshness = bool(record.coverage.time_end) if record.coverage else False
    score += 0.15 * (1.0 if has_freshness else 0.0)
    # Distribution richness
    score += 0.10 * min(len(record.distributions) / 3, 1.0)
    # Metrics methods richness
    methods = getattr(record, "polisyos_metrics_methods", {}) or {}
    score += 0.05 * min(len(methods) / 2, 1.0)
    return score


def merge_and_dedup(config: DatasetBatchConfig) -> MergeStats:
    """Merge and dedup helper."""
    started_at = datetime.now(UTC).isoformat()
    merged: list[DatasetRecord] = []
    seen: dict[str, DatasetRecord] = {}
    duplicates: list[tuple[str, str, str, str, str, str]] = []
    quality_upgrades = 0

    normalized_files = sorted(config.normalized_dir.glob("*.jsonl"))
    for file_path in normalized_files:
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = DatasetRecord.model_validate_json(line)
                key = rec.dedup_key or f"{rec.source}|{rec.agency}|{rec.dataset_id}"
                if key in seen:
                    existing = seen[key]
                    # Quality-ranked: challenger wins if higher quality score
                    if _dedup_quality_score(rec) > _dedup_quality_score(existing):
                        # Replace existing with higher-quality challenger
                        merged[merged.index(existing)] = rec
                        seen[key] = rec
                        duplicates.append(
                            (
                                key,
                                rec.id,
                                existing.id,
                                existing.source,
                                existing.agency,
                                existing.dataset_id,
                            )
                        )
                        quality_upgrades += 1
                    else:
                        duplicates.append(
                            (
                                key,
                                existing.id,
                                rec.id,
                                rec.source,
                                rec.agency,
                                rec.dataset_id,
                            )
                        )
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
        quality_upgrades=quality_upgrades,
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
