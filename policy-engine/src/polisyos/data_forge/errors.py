"""Shared Data Forge exception types."""

from __future__ import annotations

from typing import Any

from polisyos.core.errors import ErrorCategory, PolicyOSError


class DataForgeError(Exception):
    """Base exception for Data Forge foundation code."""


class DataForgeValidationError(DataForgeError, ValueError):
    """Raised when a Data Forge contract is malformed."""


class SchemaCompatibilityError(DataForgeValidationError):
    """Raised when a schema change lacks an allowed evolution rule."""


class SnapshotCommitError(DataForgeError):
    """Raised when a snapshot transaction cannot be safely committed."""


class LexError(PolicyOSError):
    """Compatibility error base for legal corpus workflows owned by Data Forge."""

    default_stage = "lex"
    default_category = ErrorCategory.FATAL

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        doc_source_id: str | None = None,
        doc_version_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            stage=stage or self.default_stage,
            category=self.default_category,
            details=details,
        )
        self.doc_source_id = doc_source_id
        self.doc_version_id = doc_version_id


class LexValidationError(LexError):
    """Validation failure raised by legal corpus semantic guards."""

    default_stage = "validation"
    default_category = ErrorCategory.VALIDATION


class LexIngestError(LexError):
    """Failure raised while ingesting raw legal source material."""

    default_stage = "ingest"


class LexStructureError(LexError):
    """Failure raised while structuring provisions from legal text."""

    default_stage = "structure"


class LexVersioningError(LexError):
    """Failure raised while indexing or resolving document versions."""

    default_stage = "versioning"


class LexIndexError(LexError):
    """Failure raised by legal corpus index operations."""

    default_stage = "index"


class LexNotReadyError(LexError):
    """Failure raised when required legal assets are missing or incomplete."""

    default_stage = "not_ready"


__all__ = [
    "DataForgeError",
    "DataForgeValidationError",
    "LexError",
    "LexIndexError",
    "LexIngestError",
    "LexNotReadyError",
    "LexStructureError",
    "LexValidationError",
    "LexVersioningError",
    "SchemaCompatibilityError",
    "SnapshotCommitError",
]
