"""Error hierarchy for Lex ingestion, structuring, versioning, and evaluation stages.

All Lex exceptions inherit from ``LexError`` and preserve ``doc_source_id`` / ``doc_version_id``
when available so orchestration, diagnostics, and governance tooling can attribute failures to a
specific corpus object and pipeline stage.
"""
from __future__ import annotations

from typing import Any

from polisyos.core.errors import ErrorCategory, PolicyOSError


class LexError(PolicyOSError):
    """Base error for Lex corpus workflows."""

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
    """Validation failure raised by schema or semantic guards in Lex."""

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
    """Failure raised by Lex search or indexing subsystems."""

    default_stage = "index"


class LexNotReadyError(LexError):
    """Failure raised when required Lex assets are missing or incomplete."""

    default_stage = "not_ready"


__all__ = [
    "LexError",
    "LexIndexError",
    "LexIngestError",
    "LexNotReadyError",
    "LexStructureError",
    "LexValidationError",
    "LexVersioningError",
]
