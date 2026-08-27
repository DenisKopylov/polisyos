"""Lex-local error hierarchy and read-boundary error translation."""

from __future__ import annotations

from typing import Any

from polisyos.core.errors import ErrorCategory, PolicyOSError


class LexError(PolicyOSError):
    """Base exception for Lex runtime legal workflows."""

    default_stage = "lex"
    default_category = ErrorCategory.FATAL

    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory | str | None = None,
        stage: str | None = None,
        code: str | None = None,
        doc_source_id: str | None = None,
        doc_version_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            category=category,
            stage=stage or self.default_stage,
            code=code,
            details=details,
        )
        self.doc_source_id = doc_source_id
        self.doc_version_id = doc_version_id


class LexValidationError(LexError):
    """Validation failure raised by Lex semantic guards."""

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


_LEX_ERROR_BY_STAGE: dict[str, type[LexError]] = {
    "validation": LexValidationError,
    "ingest": LexIngestError,
    "structure": LexStructureError,
    "versioning": LexVersioningError,
    "index": LexIndexError,
    "not_ready": LexNotReadyError,
}


def translate_policy_error(error: PolicyOSError) -> LexError:
    """Copy a lower-layer ``PolicyOSError`` into Lex's public error hierarchy."""
    error_cls = _LEX_ERROR_BY_STAGE.get(error.stage, LexError)
    return error_cls(
        error.message,
        category=error.category,
        stage=error.stage,
        code=error.code,
        doc_source_id=getattr(error, "doc_source_id", None),
        doc_version_id=getattr(error, "doc_version_id", None),
        details=dict(error.details),
    )

__all__ = [
    "LexError",
    "LexIndexError",
    "LexIngestError",
    "LexNotReadyError",
    "LexStructureError",
    "LexValidationError",
    "LexVersioningError",
    "translate_policy_error",
]
