from __future__ import annotations

from typing import Any


class LexError(Exception):
    """Base error for Lex corpus workflows."""

    default_stage = "lex"

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        doc_source_id: str | None = None,
        doc_version_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage or self.default_stage
        self.doc_source_id = doc_source_id
        self.doc_version_id = doc_version_id
        self.details = details or {}


class LexValidationError(LexError):
    default_stage = "validation"


class LexIngestError(LexError):
    default_stage = "ingest"


class LexStructureError(LexError):
    default_stage = "structure"


class LexVersioningError(LexError):
    default_stage = "versioning"


class LexIndexError(LexError):
    default_stage = "index"


class LexNotReadyError(LexError):
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
