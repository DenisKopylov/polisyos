"""Scholar producer bindings for Policy Design Case spine consumers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def build_scholar_spine_evidence_binding(
    *,
    literature_refs: Sequence[Any] | None = None,
    spine_context: Mapping[str, Any] | None = None,
    blocker_refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Return Scholar's spine-consumer fields for literature evidence."""

    from polisyos.runtime.quality.semantic_binding import build_producer_spine_binding_fields

    return {
        "schema_version": "policyos.scholar.spine_evidence_binding.v1",
        **build_producer_spine_binding_fields(
            component="scholar",
            spine_context=spine_context,
            candidate_refs=tuple(literature_refs or ()),
            blocker_refs=tuple(blocker_refs or ()),
        ),
    }


__all__ = ["build_scholar_spine_evidence_binding"]
