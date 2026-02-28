"""Stage: merge parsed files and deduplicate by OpenAlex work id."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.knowledge.types import SourceTopicRef, WorkRecord


class MergeStats(dict):
    """Dict-like merge stats."""


def _iter_input_files(config: AcademicBatchConfig) -> list:
    extracted = sorted(config.extracted_dir.glob("*.jsonl"))
    if extracted:
        return extracted
    return sorted(config.parsed_dir.glob("*.jsonl"))


def _merge_records(base: WorkRecord, incoming: WorkRecord) -> WorkRecord:
    """Merge duplicate records preserving topic links and stronger extraction."""
    # Topic refs union by topic_id
    by_topic: dict[str, SourceTopicRef] = {t.topic_id: t for t in base.source_topics}
    for t in incoming.source_topics:
        existing = by_topic.get(t.topic_id)
        if existing is None or t.selection_score > existing.selection_score:
            by_topic[t.topic_id] = t

    # Prefer enriched extraction payloads and better confidence
    if incoming.extraction_mode == "llm_enriched" and base.extraction_mode != "llm_enriched":
        chosen_estimates = incoming.estimates
        chosen_claims = incoming.causal_claims
        chosen_bounds = incoming.boundary_conditions
        extraction_mode = incoming.extraction_mode
    else:
        chosen_estimates = base.estimates or incoming.estimates
        chosen_claims = base.causal_claims or incoming.causal_claims
        chosen_bounds = base.boundary_conditions or incoming.boundary_conditions
        extraction_mode = base.extraction_mode

    merged = base.model_copy(
        update={
            "source_topics": sorted(by_topic.values(), key=lambda x: x.topic_id),
            "trust_score": max(base.trust_score, incoming.trust_score),
            "extraction_confidence": max(base.extraction_confidence, incoming.extraction_confidence),
            "extraction_mode": extraction_mode,
            "estimates": chosen_estimates,
            "causal_claims": chosen_claims,
            "boundary_conditions": chosen_bounds,
        }
    )
    return merged


def merge_and_dedup(config: AcademicBatchConfig) -> MergeStats:
    started_at = datetime.now(UTC).isoformat()
    merged: list[WorkRecord] = []
    seen: dict[str, WorkRecord] = {}
    duplicates: list[tuple[str, str]] = []

    parsed_files = _iter_input_files(config)
    for file_path in parsed_files:
        with open(file_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = WorkRecord.model_validate_json(line)
                key = rec.id
                if key in seen:
                    duplicates.append((key, file_path.name))
                    seen[key] = _merge_records(seen[key], rec)
                    continue
                seen[key] = rec

    merged = list(seen.values())

    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        for rec in merged:
            fh.write(rec.model_dump_json() + "\n")

    with open(config.topic_links_path, "w", encoding="utf-8") as fh:
        for rec in merged:
            for t in rec.source_topics:
                fh.write(
                    json.dumps(
                        {
                            "run_id": rec.metadata.get("run_id", config.run_id),
                            "pass_name": rec.metadata.get("pass_name", config.pass_name),
                            "work_id": rec.id,
                            "topic_id": t.topic_id,
                            "topic_display_name": t.topic_display_name,
                            "policy_block": t.policy_block,
                            "policy_subblock": t.policy_subblock,
                            "rank": t.rank,
                            "selection_score": t.selection_score,
                            "batch_origin": t.batch_origin,
                            "selected_at": t.selected_at,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    with open(config.duplicates_report_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["work_id", "source_file"])
        writer.writerows(duplicates)

    topic_links = sum(len(r.source_topics) for r in merged)

    stats = MergeStats(
        parsed_files=len(parsed_files),
        merged_records=len(merged),
        duplicates=len(duplicates),
        topic_links=topic_links,
    )

    write_stage_manifest(
        manifest_path=config.manifests_dir / "merge_dedup.json",
        stage="merge_dedup",
        status="ok",
        metrics=dict(stats),
        artifacts=[config.merged_records_path, config.topic_links_path, config.duplicates_report_path],
        started_at=started_at,
    )
    return stats
