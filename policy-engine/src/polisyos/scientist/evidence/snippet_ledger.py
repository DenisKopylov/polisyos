"""Snippet ledger helpers for stable source-span evidence."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scholar.search import validate_source_snippet_spans

if TYPE_CHECKING:
    from polisyos.scholar.search.models import SourceSnippet


class SnippetLedgerEntry(BaseModel):
    """Normalized ledger row for one source snippet."""

    model_config = ConfigDict(extra="forbid")

    snippet_id: str
    source_id: str
    url: str
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    text_sha256: str
    text_preview: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SnippetLedgerValidation(BaseModel):
    """Validation result for snippet id/span/source consistency."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def stable_snippet_id(
    *,
    source_id: str,
    start_char: int,
    end_char: int,
    text: str,
) -> str:
    """Build a deterministic snippet id from source id, span and text hash."""

    payload = f"{source_id}|{start_char}|{end_char}|{text}".encode()
    return f"snip.{hashlib.sha256(payload).hexdigest()[:24]}"


def build_snippet_ledger(snippets: list[SourceSnippet]) -> list[SnippetLedgerEntry]:
    """Build a deduplicated ledger of citation-ready snippets."""

    entries: list[SnippetLedgerEntry] = []
    seen: set[str] = set()
    for snippet in snippets:
        if snippet.snippet_id in seen:
            continue
        seen.add(snippet.snippet_id)
        text = snippet.text.strip()
        entries.append(
            SnippetLedgerEntry(
                snippet_id=snippet.snippet_id,
                source_id=snippet.source_id,
                url=str(snippet.url),
                start_char=snippet.start_char,
                end_char=snippet.end_char,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                text_preview=text[:240],
                metadata={
                    "query_node_id": snippet.query_node_id,
                    "perspective": snippet.perspective,
                    "relevance_score": snippet.relevance_score,
                },
            )
        )
    return entries


def validate_snippet_spans(
    snippets: list[SourceSnippet],
    *,
    source_text_by_id: dict[str, str] | None = None,
) -> SnippetLedgerValidation:
    """Validate snippet ids, spans, and exact source text alignment.

    Source resolution is owned by Scholar. This compatibility helper delegates
    the coordinate contract there and treats absent source text as a violation.
    """

    violations, warnings = validate_source_snippet_spans(
        snippets,
        source_text_by_id=source_text_by_id or {},
    )
    return SnippetLedgerValidation(
        passed=not violations,
        violations=violations,
        warnings=warnings,
    )


__all__ = [
    "SnippetLedgerEntry",
    "SnippetLedgerValidation",
    "build_snippet_ledger",
    "stable_snippet_id",
    "validate_snippet_spans",
]
