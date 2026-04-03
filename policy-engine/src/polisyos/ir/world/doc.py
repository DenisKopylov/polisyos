"""Public world doc module API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Annotated

from polisyos.ir.citations import FragmentLocator
from polisyos.ir.kernel.base import (
    ARTIFACT_ID_PATTERN,
    ID_PATTERN,
    KernelModel,
    reject_floats_deep,
)

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class DocMeta(KernelModel):
    """Doc meta public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    doc_source_id: str = Field(..., pattern=ID_PATTERN)
    doc_version_id: str = Field(..., pattern=ID_PATTERN)
    canonical_url: str | None = None
    official_id: str | None = None
    retrieved_at: datetime
    mime: str
    license: str
    jurisdiction: str | None = None
    language: str | None = None
    raw_ref: str = Field(..., pattern=ARTIFACT_ID_PATTERN)
    normalized_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    structure_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    chunks_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_identity(self) -> "DocMeta":
        if (self.canonical_url is None) == (self.official_id is None):
            raise ValueError("exactly one of canonical_url or official_id is required")
        return self


class DocFragment(KernelModel):
    """Doc fragment public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    fragment_id: str = Field(..., pattern=ID_PATTERN)
    doc_version_id: str = Field(..., pattern=ID_PATTERN)
    locator: FragmentLocator
    text_hash: str = Field(..., pattern=ARTIFACT_ID_PATTERN)
    quote_preview: str | None = None
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )


__all__ = [
    "DocFragment",
    "DocMeta",
]
