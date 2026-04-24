"""Public docs errors module API."""

from __future__ import annotations

from polisyos.core.errors import ErrorCategory, PolicyOSError


class DocPipelineError(PolicyOSError):
    """Base error for the Fabric docs pipeline."""

    default_stage = "fabric.docs"
    default_category = ErrorCategory.FATAL


class DocValidationError(DocPipelineError):
    """Raised when pipeline inputs or invariants are invalid."""

    default_category = ErrorCategory.VALIDATION


class DocUnsupportedMimeError(DocPipelineError):
    """Raised when a MIME type is not supported by the pipeline."""

    default_category = ErrorCategory.VALIDATION


class DocNotReadyError(DocPipelineError):
    """Raised when required upstream artifacts are missing (e.g., normalized text)."""

    default_category = ErrorCategory.TRANSIENT


__all__ = [
    "DocNotReadyError",
    "DocPipelineError",
    "DocUnsupportedMimeError",
    "DocValidationError",
]
