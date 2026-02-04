from __future__ import annotations

from typing import Protocol

from polisyos.ir.world.doc import DocMeta

from ..errors import ClaimUnsupportedExtractorError
from ..types import ChunkContext, ClaimCandidate, ClaimExtractOptions
from . import explicit_lines_v1, lex_norm_regex_v1, regex_numeric_v1


class ClaimExtractorFn(Protocol):
    def __call__(
        self,
        *,
        ctx: ChunkContext,
        meta: DocMeta,
        normalized_text: str,
        options: ClaimExtractOptions,
    ) -> list[ClaimCandidate]: ...

_EXTRACTOR_REGISTRY: dict[str, ClaimExtractorFn] = {
    "explicit_lines_v1": explicit_lines_v1.extract,
    "lex.norm_extractor.regex_v1": lex_norm_regex_v1.extract,
    "regex_numeric_v1": regex_numeric_v1.extract,
}


def get_extractor(extractor_id: str) -> ClaimExtractorFn:
    extractor = _EXTRACTOR_REGISTRY.get(extractor_id)
    if extractor is None:
        raise ClaimUnsupportedExtractorError(f"unsupported extractor_id: {extractor_id}")
    return extractor


def list_extractors() -> list[str]:
    return sorted(_EXTRACTOR_REGISTRY)


__all__ = [
    "ClaimExtractorFn",
    "get_extractor",
    "list_extractors",
]
