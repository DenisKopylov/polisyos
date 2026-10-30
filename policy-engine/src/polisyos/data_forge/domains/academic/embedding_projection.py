"""Canonical source projection for academic work embedding generations."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

ACADEMIC_WORK_EMBEDDING_BASIS_KIND = "academic_work_embedding"
ACADEMIC_WORK_EMBEDDING_PROJECTION_RULE_VERSION = "policyos.academic_work_embedding_projection.v1"


def project_academic_work_embedding(row: Sequence[object]) -> tuple[str, str]:
    """Project an ``(id, title, abstract)`` row to the exact embedded text."""
    if len(row) != 3:
        raise ValueError("academic embedding rows must contain three projected columns")
    identifier, title, abstract = row
    text = f"{title or ''}. {cast('str', abstract or '')[:1200]}".strip()
    return str(identifier), text
