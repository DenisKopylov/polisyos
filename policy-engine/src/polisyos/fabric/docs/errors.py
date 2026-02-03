from __future__ import annotations


class DocPipelineError(Exception):
    """Base error for the Fabric docs pipeline."""


class DocValidationError(DocPipelineError):
    """Raised when pipeline inputs or invariants are invalid."""


class DocUnsupportedMimeError(DocPipelineError):
    """Raised when a MIME type is not supported by the pipeline."""


class DocNotReadyError(DocPipelineError):
    """Raised when required upstream artifacts are missing (e.g., normalized text)."""


__all__ = [
    "DocNotReadyError",
    "DocPipelineError",
    "DocUnsupportedMimeError",
    "DocValidationError",
]
