from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir.citations import (
    AnchorKind,
    CitationRef,
    DocumentRef,
    FragmentLocator,
)


def test_citation_accepts_fragment_id_only() -> None:
    citation = CitationRef(
        doc=DocumentRef(doc_id="lex.test_doc"),
        fragment_id="frag_1",
    )
    assert citation.fragment_id == "frag_1"


def test_citation_accepts_locator_only_with_version() -> None:
    citation = CitationRef(
        doc=DocumentRef(doc_id="lex.test_doc", doc_version_id="docv_1"),
        locator=FragmentLocator(
            anchor_kind=AnchorKind.ARTICLE,
            anchor_path="Art. 1",
        ),
    )
    assert citation.locator is not None


def test_locator_requires_location_method() -> None:
    with pytest.raises(ValidationError):
        FragmentLocator(anchor_kind=AnchorKind.SECTION)


def test_locator_rejects_invalid_offsets() -> None:
    with pytest.raises(ValidationError):
        FragmentLocator(
            anchor_kind=AnchorKind.SECTION,
            offset_start=10,
            offset_end=5,
        )


def test_locator_rejects_invalid_page_range() -> None:
    with pytest.raises(ValidationError):
        FragmentLocator(
            anchor_kind=AnchorKind.PAGE,
            page_start=5,
            page_end=2,
        )


def test_citation_rejects_float_props() -> None:
    with pytest.raises(ValidationError):
        CitationRef(
            doc=DocumentRef(doc_id="lex.test_doc"),
            fragment_id="frag_2",
            props={"score": 0.5},
        )
