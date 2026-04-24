"""Public claims citations module API."""

from __future__ import annotations

from polisyos.ir.citations import CitationRef, DocumentRef
from polisyos.ir.world.doc import DocMeta


def minimal_doc_citation(meta: DocMeta, *, fragment_id: str) -> CitationRef:
    """Minimal doc citation helper."""
    return CitationRef(
        doc=DocumentRef(doc_id=meta.doc_source_id, doc_version_id=meta.doc_version_id),
        fragment_id=fragment_id,
        locator=None,
        text_hash=None,
        quote_hash=None,
        evidence_ref=None,
        provenance_ref=None,
        notes=[],
        props={},
    )


__all__ = ["minimal_doc_citation"]
