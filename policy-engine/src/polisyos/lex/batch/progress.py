"""Checkpoint / resume tracker for the batch pipeline.

Uses a JSONL file to record per-document stage completion.
On restart, already-completed documents are skipped.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ProgressTracker:
    """JSONL-backed progress tracker with per-document granularity."""

    def __init__(self, progress_path: Path) -> None:
        self._path = progress_path
        # doc_id → {stage → timestamp}
        self._completed: dict[str, dict[str, str]] = {}
        # doc_id → {stage → content_hash}  (optional, for change detection)
        self._hashes: dict[str, dict[str, str]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_done(self, doc_id: str, stage: str) -> bool:
        """Check whether *doc_id* has completed *stage*."""
        return stage in self._completed.get(doc_id, {})

    def is_done_with_hash(self, doc_id: str, stage: str, content_hash: str) -> bool:
        """Check whether *doc_id* completed *stage* with the same content hash.

        Returns True only if the stage is done AND the stored hash matches.
        If no hash was stored (old progress entries), returns True (backward compat).
        """
        if not self.is_done(doc_id, stage):
            return False
        stored = self._hashes.get(doc_id, {}).get(stage)
        if stored is None:
            return True  # old entry without hash — treat as valid
        return stored == content_hash

    def mark_done(
        self,
        doc_id: str,
        stage: str,
        *,
        stats: dict | None = None,
        content_hash: str | None = None,
    ) -> None:
        """Record that *doc_id* finished *stage* and append to JSONL."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry: dict = {"doc_id": doc_id, "stage": stage, "ts": ts}
        if stats:
            entry["stats"] = stats
        if content_hash:
            entry["content_hash"] = content_hash

        self._completed.setdefault(doc_id, {})[stage] = ts
        if content_hash:
            self._hashes.setdefault(doc_id, {})[stage] = content_hash

        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def mark_stage_done(
        self,
        stage: str,
        stats: dict | None = None,
    ) -> None:
        """Record a global stage completion (not per-document)."""
        self.mark_done("__global__", stage, stats=stats)

    def is_stage_done(self, stage: str) -> bool:
        """Check whether a global stage is done."""
        return self.is_done("__global__", stage)

    def completed_count(self, stage: str) -> int:
        """Number of documents that completed *stage*."""
        return sum(
            1
            for doc_stages in self._completed.values()
            if stage in doc_stages
        )

    def summary(self) -> dict[str, int]:
        """Return {stage: count} across all documents."""
        stage_counts: dict[str, int] = {}
        for doc_stages in self._completed.values():
            for stage in doc_stages:
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
        return stage_counts

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                doc_id = entry.get("doc_id", "")
                stage = entry.get("stage", "")
                ts = entry.get("ts", "")
                content_hash = entry.get("content_hash")
                if doc_id and stage:
                    self._completed.setdefault(doc_id, {})[stage] = ts
                    if content_hash:
                        self._hashes.setdefault(doc_id, {})[stage] = content_hash

        total = sum(len(v) for v in self._completed.values())
        if total:
            logger.info(
                "Progress loaded: %d entries across %d documents",
                total,
                len(self._completed),
            )
