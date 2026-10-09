"""Lossless HTTP projection of Lex owner search results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import contracts as core_contracts  # noqa: TC001 - Pydantic runtime type
from polisyos.lex.knowledge import LegalFactResult


class LexSearchResultItem(LegalFactResult):
    """Expose every owner truth field without promoting search hits to authority."""


class LexSearchResponse(BaseModel):
    """Return ranked Lex facts with the actual retrieval mode and refusal reason."""

    model_config = ConfigDict(extra="forbid")

    meta: core_contracts.ApiMeta
    query: str
    results: list[LexSearchResultItem] = Field(default_factory=list)
    total: int = 0
    search_mode: Literal["text", "vector"]
    vector_refusal_code: str | None = Field(...)


__all__ = ["LexSearchResponse", "LexSearchResultItem"]
