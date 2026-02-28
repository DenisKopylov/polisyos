"""Stage: topic-based OpenAlex selection (Pass 1)."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.openalex.client import OpenAlexClient
from polisyos.academic.openalex.selector import SelectedTopicWork, select_all_topics
from polisyos.academic.openalex.topic_catalog import TopicEntry, load_topics


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


async def run_topic_select(config: AcademicBatchConfig) -> dict[str, int]:
    """Select top works per topic and persist selection artifacts."""
    started_at = datetime.now(UTC).isoformat()

    assert config.topics_dir is not None
    topics: list[TopicEntry] = load_topics(config.topics_dir, limit=config.topic_limit)

    topic_rows = [
        {
            "topic_id": t.topic_id,
            "display_name": t.display_name,
            "description": t.description,
            "works_count": t.works_count,
            "cited_by_count": t.cited_by_count,
            "policy_block": t.policy_block,
            "policy_subblock": t.policy_subblock,
            "score_core": t.score_core,
            "score_domain": t.score_domain,
            "score_context": t.score_context,
            "source_file": t.source_file,
        }
        for t in topics
    ]
    _write_jsonl(config.topics_catalog_path, topic_rows)

    async with OpenAlexClient(
        email=config.openalex_email,
        max_rps=config.openalex_max_rps,
        max_concurrent=config.openalex_max_concurrent,
        timeout_seconds=config.openalex_timeout_seconds,
        max_retries=config.openalex_max_retries,
        backoff_seconds=config.openalex_backoff_seconds,
    ) as client:
        selected = await select_all_topics(
            client,
            topics=topics,
            run_id=config.run_id,
            target_per_topic=config.target_per_topic,
            per_page=config.openalex_per_page,
        )

    selected_rows = [s.to_dict() for s in selected]
    _write_jsonl(config.selected_topic_works_path, selected_rows)

    by_work: dict[str, dict] = {}
    by_topic_count: defaultdict[str, int] = defaultdict(int)
    for item in selected:
        by_topic_count[item.topic_id] += 1
        existing = by_work.get(item.work_id)
        if existing is None:
            by_work[item.work_id] = {
                "work_id": item.work_id,
                "work": item.work,
                "topic_ids": [item.topic_id],
                "topic_display_names": [item.topic_display_name],
                "run_ids": [item.run_id],
            }
        else:
            if item.topic_id not in existing["topic_ids"]:
                existing["topic_ids"].append(item.topic_id)
            if item.topic_display_name not in existing["topic_display_names"]:
                existing["topic_display_names"].append(item.topic_display_name)
            if item.run_id not in existing["run_ids"]:
                existing["run_ids"].append(item.run_id)

    _write_jsonl(config.selected_global_works_path, list(by_work.values()))

    underfilled = sum(1 for t in topics if by_topic_count.get(t.topic_id, 0) < config.target_per_topic)

    metrics = {
        "topics": len(topics),
        "selected_rows": len(selected_rows),
        "selected_unique": len(by_work),
        "underfilled_topics": underfilled,
    }

    write_stage_manifest(
        manifest_path=config.manifests_dir / "topic_select.json",
        stage="topic_select",
        status="ok",
        metrics=metrics,
        artifacts=[config.topics_catalog_path, config.selected_topic_works_path, config.selected_global_works_path],
        started_at=started_at,
    )
    return metrics
