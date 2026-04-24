"""Stage: materialize topic-selected OpenAlex works into raw snapshots."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.batch_common.manifest import write_raw_manifest, write_stage_manifest

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.academic.batch.config import AcademicBatchConfig


def _utc_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _latest_snapshot_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    dirs = sorted([p for p in root.iterdir() if p.is_dir()])
    return dirs[-1] if dirs else None


async def harvest_by_topic(config: AcademicBatchConfig) -> dict[str, list[dict]]:
    """Materialize topic-selected works into per-topic raw snapshots."""
    if not config.selected_topic_works_path.exists():
        raise FileNotFoundError(
            f"topic selection artifact missing: {config.selected_topic_works_path}. "
            "Run stage `topic_select` before `harvest`."
        )

    rows = _read_jsonl(config.selected_topic_works_path)
    grouped: dict[str, list[dict]] = defaultdict(list)
    topic_names: dict[str, str] = {}

    for row in rows:
        topic_id = str(row.get("topic_id") or "")
        if not topic_id:
            continue
        grouped[topic_id].append(row)
        if topic_id not in topic_names:
            topic_names[topic_id] = str(row.get("topic_display_name") or topic_id)

    out: dict[str, list[dict]] = {}
    for topic_id, topic_rows in grouped.items():
        topic_root = config.topic_raw_root(topic_id, topic_names.get(topic_id, ""))
        latest = _latest_snapshot_dir(topic_root)
        latest_payload = latest / "payload.jsonl" if latest else None

        if config.resume and latest_payload and latest_payload.exists():
            out[topic_id] = _read_jsonl(latest_payload)
            continue

        snapshot_dir = topic_root / _utc_slug()
        payload_path = snapshot_dir / "payload.jsonl"
        manifest_path = snapshot_dir / "manifest.json"

        _write_jsonl(payload_path, topic_rows)
        write_raw_manifest(
            manifest_path=manifest_path,
            source="openalex_topic_select",
            endpoint=str(config.selected_topic_works_path),
            payload_path=payload_path,
            count=len(topic_rows),
            filters={
                "run_id": config.run_id,
                "pass_name": config.pass_name,
                "topic_id": topic_id,
                "topic_display_name": topic_names.get(topic_id, ""),
                "target_per_topic": config.target_per_topic,
            },
            parser_version="4",
        )
        out[topic_id] = topic_rows

    return out


async def harvest_all(config: AcademicBatchConfig) -> dict[str, list[dict]]:
    """Harvest all configured sources and write stage manifest."""
    started_at = datetime.now(UTC).isoformat()
    all_rows = await harvest_by_topic(config)
    metrics = {
        "topics": len(all_rows),
        "records": sum(len(v) for v in all_rows.values()),
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "harvest.json",
        stage="harvest",
        status="ok",
        metrics=metrics,
        artifacts=[],
        started_at=started_at,
    )
    return all_rows
