"""Public ir citations module API."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, model_validator

from polisyos.ir.kernel.base import (
    ARTIFACT_ID_PATTERN,
    ID_PATTERN,
    KernelModel,
    reject_floats_deep,
)

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class AnchorKind(str, Enum):
    """Anchor kind public type."""

    ARTICLE = "article"
    SECTION = "section"
    CLAUSE = "clause"
    PARAGRAPH = "paragraph"
    PAGE = "page"
    TABLE = "table"
    FIGURE = "figure"
    HEADING = "heading"
    CHUNK = "chunk"
    OTHER = "other"


class FragmentLocator(KernelModel):
    """Declarative locator within a specific document version."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    anchor_kind: AnchorKind
    anchor_path: str | None = None
    offset_start: int | None = Field(None, ge=0)
    offset_end: int | None = Field(None, ge=0)
    page_start: int | None = Field(None, ge=0)
    page_end: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_locator(self) -> FragmentLocator:
        has_anchor = bool(self.anchor_path)
        has_offset = self.offset_start is not None or self.offset_end is not None
        has_page = self.page_start is not None or self.page_end is not None

        if has_offset and (self.offset_start is None or self.offset_end is None):
            raise ValueError("offset_start and offset_end must be provided together")
        if has_page and (self.page_start is None or self.page_end is None):
            raise ValueError("page_start and page_end must be provided together")
        if not (has_anchor or has_offset or has_page):
            raise ValueError("locator requires anchor_path, offsets, or page range")
        if self.offset_start is not None and self.offset_end is not None:
            if self.offset_end < self.offset_start:
                raise ValueError("offset_end must be >= offset_start")
        if self.page_start is not None and self.page_end is not None:
            if self.page_end < self.page_start:
                raise ValueError("page_end must be >= page_start")
        return self


class DocumentRef(KernelModel):
    """Document identity with optional version binding."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    doc_id: str = Field(..., pattern=ID_PATTERN)
    doc_version_id: str | None = Field(None, pattern=ID_PATTERN)
    doc_version_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)


class CitationRef(KernelModel):
    """Citation-grade reference to a specific document fragment."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    doc: DocumentRef
    fragment_id: str | None = Field(None, pattern=ID_PATTERN)
    locator: FragmentLocator | None = None
    text_hash: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    quote_hash: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    evidence_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    provenance_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    notes: list[str] = Field(default_factory=list)
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_citation(self) -> CitationRef:
        if self.fragment_id is None and self.locator is None:
            raise ValueError("citation requires fragment_id or locator")
        if self.locator is not None:
            if self.doc.doc_version_id is None and self.doc.doc_version_ref is None:
                raise ValueError("locator requires doc_version_id or doc_version_ref")
        return self


__all__ = [
    "AnchorKind",
    "CitationRef",
    "DocumentRef",
    "FragmentLocator",
]
