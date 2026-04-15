"""Cached alignment helpers shared by cross-graph compilation flows."""

from __future__ import annotations

from functools import lru_cache
from typing import TypeAlias

from polisyos.common.serialization import stable_json_dumps
from polisyos.ir.analytics.cross_graph import CanonicalConcept, CrossGraphDiagnostic

DiagnosticKey: TypeAlias = tuple[str, str, str | None, str, str]
_ConceptJoinSignature: TypeAlias = tuple[tuple[str, tuple[str, ...]], ...]


def alignment_tokens(values: list[str] | tuple[str, ...]) -> set[str]:
    """Return normalized token set for fuzzy ontology matching."""
    return set(_cached_alignment_tokens(tuple(str(value or "") for value in values)))


def concept_tokens(concept: CanonicalConcept) -> set[str]:
    """Return cached ontology tokens for one concept."""
    join_signature: _ConceptJoinSignature = tuple(
        (str(key), tuple(str(item) for item in values))
        for key, values in sorted(concept.join_keys.items())
    )
    return set(
        _cached_concept_tokens(
            concept.concept_id,
            concept.label,
            join_signature,
        )
    )


def diagnostic_key(diagnostic: CrossGraphDiagnostic) -> DiagnosticKey:
    """Return a stable dedupe key for diagnostics collected across need passes."""
    return (
        diagnostic.code,
        diagnostic.severity,
        diagnostic.need_id,
        diagnostic.message,
        stable_json_dumps(
            diagnostic.details,
            ensure_ascii=True,
            sort_keys=True,
        ),
    )


@lru_cache(maxsize=32768)
def _cached_alignment_tokens(values: tuple[str, ...]) -> tuple[str, ...]:
    tokens: set[str] = set()
    for value in values:
        raw = value.strip().lower()
        if not raw:
            continue
        normalized = (
            raw.replace(".", " ")
            .replace("-", " ")
            .replace("/", " ")
            .replace(":", " ")
        )
        for token in normalized.split():
            trimmed = token.strip("_")
            if len(trimmed) <= 1:
                continue
            tokens.add(trimmed)
    return tuple(sorted(tokens))


@lru_cache(maxsize=8192)
def _cached_concept_tokens(
    concept_id: str,
    label: str,
    join_signature: _ConceptJoinSignature,
) -> tuple[str, ...]:
    values: list[str] = [concept_id, label]
    for _, items in join_signature:
        values.extend(items)
    return _cached_alignment_tokens(tuple(values))


__all__ = [
    "DiagnosticKey",
    "alignment_tokens",
    "concept_tokens",
    "diagnostic_key",
]
