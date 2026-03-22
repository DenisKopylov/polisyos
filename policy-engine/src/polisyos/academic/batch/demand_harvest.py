"""Demand-first harvesting: fetch OpenAlex works for unsupported benchmark needs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.openalex.client import OpenAlexClient, OpenAlexRequest
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


def _load_backlog(path: Path, *, min_priority: float) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        status = str(item.get("evidence_status") or "")
        if status not in {"unsupported", "mixed"}:
            continue
        if float(item.get("priority_weight") or 0.0) < min_priority:
            continue
        items.append(item)
    items.sort(key=lambda x: -float(x.get("priority_weight") or 0.0))
    return items


def _build_filter_expr(cause: str, effect: str) -> str:
    """Build OpenAlex filter expression from cause/effect terms."""
    cause_terms = cause.replace(".", " ").replace("_", " ").strip()
    effect_terms = effect.replace(".", " ").replace("_", " ").strip()
    search_query = f"{cause_terms} {effect_terms}"
    return (
        f"default.search:{search_query},"
        f"type:article,"
        f"has_abstract:true,"
        f"publication_year:>2005"
    )


async def run_demand_harvest(config: AcademicBatchConfig) -> dict[str, int]:
    """Harvest OpenAlex works for unsupported benchmark demand items."""
    started_at = datetime.now(UTC).isoformat()

    if not config.demand_harvest_enabled:
        logger.info("demand_harvest: disabled, skipping")
        return {"demand_harvest_skipped": 1}

    backlog = _load_backlog(
        config.runtime_demand_backlog_path,
        min_priority=config.demand_harvest_min_priority_weight,
    )
    if not backlog:
        logger.info("demand_harvest: no actionable backlog items")
        return {"demand_harvest_items": 0, "demand_harvest_works": 0}

    logger.info("demand_harvest: processing %d backlog items", len(backlog))
    harvested_works: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    async with OpenAlexClient(
        email=config.openalex_email,
        max_rps=config.openalex_max_rps,
        max_concurrent=config.openalex_max_concurrent,
        timeout_seconds=config.openalex_timeout_seconds,
        max_retries=config.openalex_max_retries,
        backoff_seconds=config.openalex_backoff_seconds,
    ) as client:
        for item in backlog:
            cause = str(item.get("cause") or item.get("raw_name") or "")
            effect = str(item.get("effect") or "")
            if not cause:
                continue

            filter_expr = _build_filter_expr(cause, effect)
            req = OpenAlexRequest(
                filter_expr=filter_expr,
                sort="cited_by_count:desc",
                per_page=min(200, config.demand_harvest_max_works_per_need),
            )

            try:
                response = await client.list_works(req)
            except Exception:
                logger.warning("demand_harvest: failed to fetch for %s -> %s", cause, effect, exc_info=True)
                continue

            results = response.get("results") or []
            count = 0
            for work in results:
                work_id = str(work.get("id") or "")
                if not work_id or work_id in seen_ids:
                    continue
                seen_ids.add(work_id)
                work["demand_source"] = "targeted_backlog"
                work["demand_cause"] = cause
                work["demand_effect"] = effect
                work["demand_need_id"] = str(item.get("need_id") or "")
                harvested_works.append(work)
                count += 1
                if count >= config.demand_harvest_max_works_per_need:
                    break

            logger.info(
                "demand_harvest: %s -> %s yielded %d works",
                cause, effect, count,
            )

    config.demand_harvest_works_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.demand_harvest_works_path, "w", encoding="utf-8") as fh:
        for work in harvested_works:
            fh.write(json.dumps(work, ensure_ascii=False) + "\n")

    metrics = {
        "demand_harvest_items": len(backlog),
        "demand_harvest_works": len(harvested_works),
        "demand_harvest_unique_ids": len(seen_ids),
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "demand_harvest.json",
        stage="demand_harvest",
        status="ok",
        metrics=metrics,
        artifacts=[config.demand_harvest_works_path],
        started_at=started_at,
    )
    logger.info("demand_harvest: harvested %d works for %d needs", len(harvested_works), len(backlog))
    return metrics


__all__ = ["run_demand_harvest"]
