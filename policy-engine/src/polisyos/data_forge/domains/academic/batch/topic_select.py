"""Stage: topic-based OpenAlex selection (Pass 1)."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.data_forge.domains.academic.openalex.client import OpenAlexClient
from polisyos.data_forge.domains.academic.openalex.selector import (
    SelectedTopicWork,
    select_all_topics,
)
from polisyos.data_forge.domains.academic.openalex.topic_catalog import TopicEntry, load_topics
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _normalized_text(*values: object) -> str:
    parts = [str(value or "").strip().lower() for value in values if str(value or "").strip()]
    return " | ".join(parts)


def _reconstruct_abstract(inverted_index: object) -> str:
    if not isinstance(inverted_index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, pos_list in inverted_index.items():
        if not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            if isinstance(pos, int):
                positions.append((pos, str(word)))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def _load_demand_backlog(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else payload.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    rows.append(item)
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _work_searchable_text(item: SelectedTopicWork) -> str:
    work = item.work if isinstance(item.work, dict) else {}
    primary_location = work.get("primary_location")
    source = primary_location.get("source") if isinstance(primary_location, dict) else None
    return _normalized_text(
        work.get("title"),
        _reconstruct_abstract(work.get("abstract_inverted_index")),
        item.topic_display_name,
        item.topic_policy_block,
        item.topic_policy_subblock,
        source.get("display_name") if isinstance(source, dict) else "",
    )


def _backlog_match_score(text: str, backlog_row: dict[str, Any]) -> float:
    clean_text = str(text or "").strip().lower()
    if not clean_text:
        return 0.0
    terms = [
        str(term).strip().lower() for term in backlog_row.get("terms", []) if str(term).strip()
    ]
    if not terms:
        for key in ("cause", "effect", "parameter_name"):
            value = str(backlog_row.get(key) or "").strip().lower()
            if value:
                terms.append(value)
    if not terms:
        return 0.0
    matched = 0.0
    for term in terms:
        if term in clean_text:
            matched += 1.0
            continue
        tokens = [token for token in term.replace(".", " ").replace("_", " ").split() if token]
        if tokens and all(token in clean_text for token in tokens):
            matched += 0.8
    if matched <= 0.0:
        return 0.0
    priority = float(backlog_row.get("priority_weight") or 1.0)
    coverage = min(1.0, matched / max(1.0, len(terms)))
    return min(1.0, coverage * max(0.1, priority))


def _matches_priority_subblock(text: str, candidates: tuple[str, ...]) -> bool:
    if not text:
        return False
    normalized = str(text or "").strip().lower()
    for candidate in candidates:
        if not candidate:
            continue
        candidate_norm = candidate.strip().lower()
        candidate_tokens = [token for token in candidate_norm.replace("/", " ").split() if token]
        if candidate_norm in normalized:
            return True
        if candidate_tokens and all(token in normalized for token in candidate_tokens):
            return True
    return False


def _topic_bucket(config: AcademicBatchConfig, topic: TopicEntry) -> str:
    block = str(topic.policy_block or "").strip().lower()
    subblock = str(topic.policy_subblock or "").strip().lower()
    searchable = _normalized_text(
        topic.display_name,
        topic.description,
        topic.policy_block,
        topic.policy_subblock,
        topic.source_file,
    )
    if "policy core" in block or topic.score_core > 0:
        return "policy_core"
    if (
        "context" in block
        or topic.score_context > 0
        or _matches_priority_subblock(searchable, config.priority_context_subblocks)
    ):
        return "priority_context"
    if (
        "domain" in block
        or topic.score_domain > 0
        or _matches_priority_subblock(searchable, config.priority_domain_subblocks)
        or _matches_priority_subblock(subblock, config.priority_domain_subblocks)
    ):
        return "priority_domain"
    return "adaptive_reserve"


def _effective_target_per_topic(config: AcademicBatchConfig, topics: list[TopicEntry]) -> int:
    if not topics:
        return max(1, int(config.target_per_topic))
    budget_target = math.ceil((int(config.selected_unique_budget) / len(topics)) * 1.4)
    return max(1, int(config.target_per_topic), budget_target)


def _aggregate_global_candidates(
    config: AcademicBatchConfig,
    selected: list[SelectedTopicWork],
    topic_lookup: dict[str, TopicEntry],
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    demand_backlog = _load_demand_backlog(config.demand_backlog_path)
    by_work: dict[str, dict[str, Any]] = {}
    bucket_counts: dict[str, int] = defaultdict(int)
    demand_metrics: dict[str, int] = {
        "backlog_items": len(demand_backlog),
        "selected_with_backlog_signal": 0,
    }
    for item in selected:
        topic = topic_lookup.get(item.topic_id)
        bucket = _topic_bucket(
            config,
            topic
            if topic is not None
            else TopicEntry(
                topic_id=item.topic_id,
                display_name=item.topic_display_name,
                description="",
                works_count=0,
                cited_by_count=0,
                policy_block=item.topic_policy_block,
                policy_subblock=item.topic_policy_subblock,
                score_core=0,
                score_domain=0,
                score_context=0,
                source_file=item.source_file,
            ),
        )
        searchable_text = _work_searchable_text(item)
        matched_need_ids: list[str] = []
        demand_signal_score = 0.0
        if demand_backlog:
            for row in demand_backlog:
                score = _backlog_match_score(searchable_text, row)
                if score <= 0.0:
                    continue
                demand_signal_score = max(demand_signal_score, score)
                need_id = str(row.get("need_id") or "").strip()
                if need_id and need_id not in matched_need_ids:
                    matched_need_ids.append(need_id)
        adjusted_score = (
            float(item.selection_score) + float(config.demand_backlog_boost) * demand_signal_score
        )
        existing = by_work.get(item.work_id)
        if existing is None:
            by_work[item.work_id] = {
                "work_id": item.work_id,
                "work": item.work,
                "selection_score": float(item.selection_score),
                "priority_score": adjusted_score,
                "demand_signal_score": demand_signal_score,
                "best_rank": int(item.rank),
                "topic_ids": [item.topic_id],
                "topic_display_names": [item.topic_display_name],
                "policy_blocks": [item.topic_policy_block] if item.topic_policy_block else [],
                "policy_subblocks": [item.topic_policy_subblock]
                if item.topic_policy_subblock
                else [],
                "run_ids": [item.run_id],
                "source_files": [item.source_file] if item.source_file else [],
                "allocation_buckets": [bucket],
                "matched_need_ids": matched_need_ids,
                "selected_at": item.selected_at,
            }
            continue
        existing["selection_score"] = max(
            float(existing["selection_score"]), float(item.selection_score)
        )
        existing["priority_score"] = max(float(existing["priority_score"]), adjusted_score)
        existing["demand_signal_score"] = max(
            float(existing["demand_signal_score"]), demand_signal_score
        )
        existing["best_rank"] = min(int(existing["best_rank"]), int(item.rank))
        for key, value in (
            ("topic_ids", item.topic_id),
            ("topic_display_names", item.topic_display_name),
            ("policy_blocks", item.topic_policy_block),
            ("policy_subblocks", item.topic_policy_subblock),
            ("run_ids", item.run_id),
            ("source_files", item.source_file),
            ("allocation_buckets", bucket),
        ):
            if value and value not in existing[key]:
                existing[key].append(value)
        for need_id in matched_need_ids:
            if need_id not in existing["matched_need_ids"]:
                existing["matched_need_ids"].append(need_id)

    quota_plan = {
        "policy_core": round(config.selected_unique_budget * config.policy_core_quota_share),
        "priority_domain": round(
            config.selected_unique_budget * config.priority_domain_quota_share
        ),
        "priority_context": round(
            config.selected_unique_budget * config.priority_context_quota_share
        ),
    }
    quota_plan["adaptive_reserve"] = max(
        0,
        int(config.selected_unique_budget) - sum(quota_plan.values()),
    )
    taken: set[str] = set()
    selected_global: list[dict[str, Any]] = []
    for bucket_name in ("policy_core", "priority_domain", "priority_context"):
        ranked = sorted(
            (
                row
                for row in by_work.values()
                if bucket_name in row["allocation_buckets"] and row["work_id"] not in taken
            ),
            key=lambda row: (
                -float(row["priority_score"]),
                -float(row["selection_score"]),
                int(row["best_rank"]),
                str(row["work_id"]),
            ),
        )
        for row in ranked[: quota_plan[bucket_name]]:
            taken.add(str(row["work_id"]))
            bucket_counts[bucket_name] += 1
            if float(row.get("demand_signal_score") or 0.0) > 0.0:
                demand_metrics["selected_with_backlog_signal"] += 1
            selected_global.append({**row, "selected_bucket": bucket_name})

    reserve_needed = max(0, int(config.selected_unique_budget) - len(selected_global))
    if reserve_needed:
        reserve_ranked = sorted(
            (row for row in by_work.values() if row["work_id"] not in taken),
            key=lambda row: (
                -float(row["priority_score"]),
                -float(row["selection_score"]),
                int(row["best_rank"]),
                str(row["work_id"]),
            ),
        )
        for row in reserve_ranked[:reserve_needed]:
            taken.add(str(row["work_id"]))
            bucket_counts["adaptive_reserve"] += 1
            if float(row.get("demand_signal_score") or 0.0) > 0.0:
                demand_metrics["selected_with_backlog_signal"] += 1
            selected_global.append({**row, "selected_bucket": "adaptive_reserve"})
    return selected_global, dict(bucket_counts), demand_metrics


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
    topic_lookup = {topic.topic_id: topic for topic in topics}
    effective_target = _effective_target_per_topic(config, topics)

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
            target_per_topic=effective_target,
            per_page=config.openalex_per_page,
        )

    selected_rows = [s.to_dict() for s in selected]
    _write_jsonl(config.selected_topic_works_path, selected_rows)

    by_topic_count: defaultdict[str, int] = defaultdict(int)
    for item in selected:
        by_topic_count[item.topic_id] += 1
    selected_global_rows, bucket_counts, demand_metrics = _aggregate_global_candidates(
        config, selected, topic_lookup
    )

    _write_jsonl(config.selected_global_works_path, selected_global_rows)

    underfilled = sum(1 for t in topics if by_topic_count.get(t.topic_id, 0) < effective_target)

    metrics = {
        "topics": len(topics),
        "selected_rows": len(selected_rows),
        "selected_unique": len(selected_global_rows),
        "underfilled_topics": underfilled,
        "effective_target_per_topic": effective_target,
        "selected_budget": int(config.selected_unique_budget),
        "selected_policy_core": int(bucket_counts.get("policy_core", 0)),
        "selected_priority_domain": int(bucket_counts.get("priority_domain", 0)),
        "selected_priority_context": int(bucket_counts.get("priority_context", 0)),
        "selected_adaptive_reserve": int(bucket_counts.get("adaptive_reserve", 0)),
        "demand_backlog_items": int(demand_metrics.get("backlog_items", 0)),
        "selected_with_backlog_signal": int(demand_metrics.get("selected_with_backlog_signal", 0)),
    }

    write_stage_manifest(
        manifest_path=config.manifests_dir / "topic_select.json",
        stage="topic_select",
        status="ok",
        metrics=metrics,
        artifacts=[
            config.topics_catalog_path,
            config.selected_topic_works_path,
            config.selected_global_works_path,
        ],
        started_at=started_at,
    )
    return metrics
