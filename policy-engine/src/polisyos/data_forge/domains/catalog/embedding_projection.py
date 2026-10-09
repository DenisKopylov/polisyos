"""Canonical material projection used by the catalog embedding generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

CATALOG_DATASET_EMBEDDING_BASIS_KIND = "catalog_dataset_embedding"
CATALOG_DATASET_EMBEDDING_PROJECTION_RULE_VERSION = (
    "policyos.catalog_dataset_embedding_projection.v1"
)


def project_catalog_dataset_embedding(row: Sequence[object]) -> tuple[str, str]:
    """Project one canonical dataset row to its embedding ID and exact text.

    The row shape is ``(id, title, description, keywords, variables)``. This is
    the shared material projection used by the producer and currentness readers.
    """
    if len(row) != 5:
        raise ValueError("catalog embedding rows must contain five projected columns")
    identifier, title, description, keywords, variables = row
    normalized_title = title or ""
    normalized_description = (description or "")[:500]
    normalized_keywords = cast("list[str]", list(keywords or []))
    normalized_variables = cast("list[str]", list(variables or []))
    text = (
        f"{normalized_title} {normalized_description} "
        f"{' '.join(normalized_keywords[:20])} {' '.join(normalized_variables[:20])}"
    ).strip()
    return str(identifier), text
