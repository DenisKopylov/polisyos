"""Hashing helpers for reproducible pipeline artifacts."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA256 for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_jsonl(path: Path) -> str:
    """SHA256 over JSONL bytes, line-order sensitive."""
    return sha256_file(path)
