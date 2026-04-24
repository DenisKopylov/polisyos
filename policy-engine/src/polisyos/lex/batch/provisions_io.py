"""Disk helpers for Stage 2 provisions.

Each document is stored as JSONL with 2-char shard prefix:
    {provisions_dir}/{doc_id[:2]}/{doc_id}.jsonl
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _shard_prefix(doc_id: str) -> str:
    """First 2 chars of doc_id, lowercased — used as subdirectory name."""
    return (doc_id[:2] if len(doc_id) >= 2 else doc_id or "_").lower()


def provision_file_path(provisions_dir: Path, doc_id: str) -> Path:
    """Return a stable per-document provisions file path (sharded)."""
    return provisions_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"


def write_provisions(
    *,
    provisions_dir: Path,
    doc_id: str,
    provisions: list[dict],
) -> Path:
    """Write provisions for one document (overwrite mode)."""
    out_path = provision_file_path(provisions_dir, doc_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in provisions:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out_path


def read_provisions(
    *,
    provisions_dir: Path,
    doc_id: str,
) -> list[dict]:
    """Read provisions for one document, returning [] if missing."""
    in_path = provision_file_path(provisions_dir, doc_id)
    if not in_path.exists():
        return []

    rows: list[dict] = []
    with open(in_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def provision_text_by_anchor(
    *,
    provisions_dir: Path,
    doc_id: str,
) -> dict[str, str]:
    """Load {anchor_path: text} map for one document."""
    rows = read_provisions(provisions_dir=provisions_dir, doc_id=doc_id)
    out: dict[str, str] = {}
    for row in rows:
        anchor = str(row.get("anchor_path", "")).strip()
        if not anchor:
            continue
        out[anchor] = str(row.get("text", ""))
    return out
