"""Lossless HTTP projection of Lex owner search results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import contracts as core_contracts  # noqa: TC001 - Pydantic runtime type
from polisyos.lex.knowledge import LegalFactResult


class LexSearchResultItem(LegalFactResult):
    """Expose every owner truth field without promoting search hits to authority."""


class LexSearchResponse(BaseModel):
    """Return ranked Lex facts through the lossless HTTP boundary projection."""

    model_config = ConfigDict(extra="forbid")

    meta: core_contracts.ApiMeta
    query: str
    results: list[LexSearchResultItem] = Field(default_factory=list)
    total: int = 0


__all__ = ["LexSearchResponse", "LexSearchResultItem"]
