from __future__ import annotations


class ClaimPipelineError(Exception):
    """Base error for the Fabric claims pipeline."""


class ClaimValidationError(ClaimPipelineError):
    """Raised when pipeline inputs or invariants are invalid."""


class ClaimNotReadyError(ClaimPipelineError):
    """Raised when required upstream artifacts are missing."""


class ClaimUnsupportedExtractorError(ClaimPipelineError):
    """Raised when extractor_id is not registered."""


__all__ = [
    "ClaimNotReadyError",
    "ClaimPipelineError",
    "ClaimUnsupportedExtractorError",
    "ClaimValidationError",
]
