"""Public fabric claims package API."""
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
    _CONFLICTS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency path
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
    "ClaimCandidate",
    "ClaimExtractOptions",
    "ClaimExtractResult",
    "ClaimNormalizeOptions",
    "ClaimNormalizeResult",
    "ClaimNotReadyError",
    "ClaimPipelineError",
    "ClaimUnsupportedExtractorError",
    "ClaimValidationError",
    "ChunkContext",
    "detect_conflicts",
    "extract_claims_from_doc",
    "normalize_claims",
    "resolve_conflicts",
]

if not _CONFLICTS_AVAILABLE:
    for _name in [
        "ConflictDetectOptions",
        "ConflictDetectResult",
        "ConflictResolveOptions",
        "ConflictResolveResult",
        "detect_conflicts",
        "resolve_conflicts",
    ]:
        if _name in __all__:
            __all__.remove(_name)
