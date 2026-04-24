"""Facade for document-to-claim extraction, normalization, and conflict handling."""

from __future__ import annotations

try:
    from .conflicts import (
        ConflictDetectOptions,
        ConflictDetectResult,
        ConflictResolveOptions,
        ConflictResolveResult,
        detect_conflicts,
        resolve_conflicts,
    )

    _CONFLICT_EXPORTS = (
        ConflictDetectOptions,
        ConflictDetectResult,
        ConflictResolveOptions,
        ConflictResolveResult,
        detect_conflicts,
        resolve_conflicts,
    )
    _CONFLICTS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency path
    _CONFLICT_EXPORTS = ()
    _CONFLICTS_AVAILABLE = False
from .errors import (
    ClaimNotReadyError,
    ClaimPipelineError,
    ClaimUnsupportedExtractorError,
    ClaimValidationError,
)
from .extraction import extract_claims_from_doc
from .normalize import normalize_claims
from .types import (
    ChunkContext,
    ClaimCandidate,
    ClaimExtractOptions,
    ClaimExtractResult,
    ClaimNormalizeOptions,
    ClaimNormalizeResult,
)

__all__ = [
    "ChunkContext",
    "ClaimCandidate",
    "ClaimExtractOptions",
    "ClaimExtractResult",
    "ClaimNormalizeOptions",
    "ClaimNormalizeResult",
    "ClaimNotReadyError",
    "ClaimPipelineError",
    "ClaimUnsupportedExtractorError",
    "ClaimValidationError",
    "extract_claims_from_doc",
    "normalize_claims",
]

if _CONFLICTS_AVAILABLE:
    __all__.extend(export.__name__ for export in _CONFLICT_EXPORTS)
