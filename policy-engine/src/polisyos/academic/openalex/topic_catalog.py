"""Topic catalog loader from `relevant_topics_domain_files` CSV slices."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TopicEntry:
    """Capture one OpenAlex topic row that domain/block selection workflows can rank or filter."""
    topic_id: str
    display_name: str
    description: str
    works_count: int
    cited_by_count: int
    policy_block: str
    policy_subblock: str
    score_core: int
    score_domain: int
    score_context: int
    source_file: str


def discover_topic_files(topics_dir: Path) -> list[Path]:
    """List topic CSV files, excluding summary/index files."""
    files = sorted(topics_dir.glob("relevant_topics_*.csv"))
    out: list[Path] = []
    for path in files:
        name = path.name
        if "thematic_summary" in name or "domain_files_index" in name:
            continue
        out.append(path)
    return out


def load_topics(topics_dir: Path, *, limit: int | None = None) -> list[TopicEntry]:
    """Load all topic rows from domain/block CSV files."""
    entries: list[TopicEntry] = []
    for file_path in discover_topic_files(topics_dir):
        with open(file_path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw_id = str(row.get("id", "")).strip()
                if not raw_id:
                    continue
                topic_id = raw_id.rsplit("/", 1)[-1]
                entries.append(
                    TopicEntry(
                        topic_id=topic_id,
                        display_name=str(row.get("display_name", "") or ""),
                        description=str(row.get("description", "") or ""),
                        works_count=_safe_int(row.get("works_count")),
                        cited_by_count=_safe_int(row.get("cited_by_count")),
                        policy_block=str(row.get("policy_block", "") or ""),
                        policy_subblock=str(row.get("policy_subblock", "") or ""),
                        score_core=_safe_int(row.get("score_core")),
                        score_domain=_safe_int(row.get("score_domain")),
                        score_context=_safe_int(row.get("score_context")),
                        source_file=file_path.name,
                    )
                )
                if limit is not None and len(entries) >= max(0, int(limit)):
                    return entries
    return entries


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
