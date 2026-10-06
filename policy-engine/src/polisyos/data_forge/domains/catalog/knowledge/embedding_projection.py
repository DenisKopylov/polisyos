"""Shared dataset text projection for embedding producers and consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def dataset_embedding_text(row: Sequence[object]) -> str:
    """Project one canonical dataset row into the indexed text representation."""
    if len(row) != 5:
        raise ValueError("dataset embedding row must contain ID and four text fields")
    title = row[1] or ""
    description = (row[2] or "")[:500]
    keywords = list(row[3] or [])
    variables = list(row[4] or [])
    return (
        f"{title} {description} {' '.join(keywords[:20])} "
        f"{' '.join(variables[:20])}"
    ).strip()


__all__ = ["dataset_embedding_text"]
