"""Lossless HTTP projection of Lex owner search results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.runtime import ApiMeta  # noqa: TC001 - Pydantic resolves at runtime.
from polisyos.lex.knowledge.types import LegalFactResult


class LexSearchResultItem(LegalFactResult):
    """Expose every owner truth field without promoting search hits to authority."""


class LexSearchResponse(BaseModel):
    """Return ranked Lex facts through the lossless HTTP boundary projection."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    query: str
    results: list[LexSearchResultItem] = Field(default_factory=list)
    total: int = 0


__all__ = ["LexSearchResponse", "LexSearchResultItem"]
