"""Public contract marker for Lex NormPack plugins."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LexNormPackPlugin(Protocol):
    """Component-style plugin that creates a Lex NormPack provider."""

    @property
    def metadata(self) -> object:
        ...

    def create(self) -> object:
        ...


__all__ = ["LexNormPackPlugin"]
