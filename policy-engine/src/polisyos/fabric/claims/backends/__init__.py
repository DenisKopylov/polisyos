"""Built-in claim extractors used at the document-ingestion boundary."""

from __future__ import annotations

from polisyos.fabric.claims.extractor_registry import ClaimExtractorFn, get_extractor_registry

from ..errors import ClaimUnsupportedExtractorError
from . import explicit_lines_v1, lex_norm_regex_v1, regex_numeric_v1


def _ensure_legacy_registered() -> None:
    registry = get_extractor_registry()
    registry.register_legacy("explicit_lines_v1", explicit_lines_v1.extract)
    registry.register_legacy("lex.norm_extractor.regex_v1", lex_norm_regex_v1.extract)
    registry.register_legacy("regex_numeric_v1", regex_numeric_v1.extract)


def get_extractor(extractor_id: str) -> ClaimExtractorFn:
    """Return extractor."""
    _, extractor = resolve_extractor(extractor_id)
    return extractor


def resolve_extractor(extractor_id: str) -> tuple[str, ClaimExtractorFn]:
    """Resolve extractor."""
    _ensure_legacy_registered()
    return get_extractor_registry().resolve(extractor_id)


def list_extractors() -> list[str]:
    """List extractors."""
    _ensure_legacy_registered()
    return get_extractor_registry().list_extractors()


__all__ = [
    "ClaimExtractorFn",
    "ClaimUnsupportedExtractorError",
    "get_extractor",
    "list_extractors",
    "resolve_extractor",
]
