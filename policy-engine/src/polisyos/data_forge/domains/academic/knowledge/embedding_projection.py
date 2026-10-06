"""Shared academic work text projection for embedding producers and consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def work_embedding_text(row: Sequence[object]) -> str:
    """Project one canonical academic work row into its indexed text."""
    if len(row) != 3:
        raise ValueError("academic embedding row must contain ID, title, and abstract")
    title = row[1] or ""
    abstract = (row[2] or "")[:1200]
    return f"{title}. {abstract}".strip()


__all__ = ["work_embedding_text"]
