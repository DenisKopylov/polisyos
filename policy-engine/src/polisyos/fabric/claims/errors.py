"""Public claims errors module API."""

from __future__ import annotations

from polisyos.core.errors import ErrorCategory, PolicyOSError


class ClaimPipelineError(PolicyOSError):
    """Base error for the Fabric claims pipeline."""

    default_stage = "fabric.claims"
    default_category = ErrorCategory.FATAL


class ClaimValidationError(ClaimPipelineError):
    """Raised when pipeline inputs or invariants are invalid."""

    default_category = ErrorCategory.VALIDATION


class ClaimNotReadyError(ClaimPipelineError):
    """Raised when required upstream artifacts are missing."""

    default_category = ErrorCategory.TRANSIENT


class ClaimUnsupportedExtractorError(ClaimPipelineError):
    """Raised when extractor_id is not registered."""

    default_category = ErrorCategory.VALIDATION


__all__ = [
    "ClaimNotReadyError",
    "ClaimPipelineError",
    "ClaimUnsupportedExtractorError",
    "ClaimValidationError",
]
