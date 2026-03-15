"""SQLite-backed cache for LLM SPO extraction responses.

Key = SHA256(provision_text + doc_type + model_id).  Stores the raw JSON
response string so that repeated runs (with identical provision text + model)
skip the LLM call entirely.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger

logger = get_logger(__name__)


def _cache_key(provision_text: str, doc_type: str, model_id: str) -> str:
    raw = f"{provision_text}\x00{doc_type}\x00{model_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SPOCache:
    """Thread-safe SQLite cache for LLM extraction responses."""

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(cache_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS spo_cache ("
            "  key TEXT PRIMARY KEY,"
            "  response TEXT NOT NULL,"
            "  ts REAL NOT NULL"
            ")"
        )
        self._conn.commit()
        self._hits = 0
        self._misses = 0

    def get(self, provision_text: str, doc_type: str, model_id: str) -> dict[str, Any] | None:
        key = _cache_key(provision_text, doc_type, model_id)
        row = self._conn.execute(
            "SELECT response FROM spo_cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            self._misses += 1
            return None
        self._hits += 1
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            self._misses += 1
            return None

    def put(self, provision_text: str, doc_type: str, model_id: str, response: dict[str, Any]) -> None:
        key = _cache_key(provision_text, doc_type, model_id)
        self._conn.execute(
            "INSERT OR REPLACE INTO spo_cache (key, response, ts) VALUES (?, ?, ?)",
            (key, json.dumps(response, ensure_ascii=False), time.time()),
        )
        self._conn.commit()

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}

    def close(self) -> None:
        self._conn.close()
