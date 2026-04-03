"""Public scholar errors module API."""
from __future__ import annotations

from typing import Any

from polisyos.core.errors import ErrorCategory, PolicyOSError


class ScholarError(PolicyOSError):
    """Base error for Scholar enrichment pipeline."""

    default_stage = "scholar"
    default_category = ErrorCategory.FATAL

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        source_identity: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            stage=stage or self.default_stage,
            category=self.default_category,
            details=details,
        )
        self.source_identity = source_identity


class ScholarValidationError(ScholarError):
    """Scholar validation error exception."""
    default_stage = "validation"
    default_category = ErrorCategory.VALIDATION


class ScholarDiscoverError(ScholarError):
    """Scholar discover error exception."""
    default_stage = "discover"


class ScholarAcquireError(ScholarError):
    """Scholar acquire error exception."""
    default_stage = "acquire"


class ScholarDocsError(ScholarError):
    """Scholar docs error exception."""
    default_stage = "docs"


class ScholarClaimsError(ScholarError):
    """Scholar claims error exception."""
    default_stage = "claims"


class ScholarReconcileError(ScholarError):
    """Scholar reconcile error exception."""
    default_stage = "reconcile"


class ScholarBundleError(ScholarError):
    """Scholar bundle error exception."""
    default_stage = "bundle"


__all__ = [
    "ScholarAcquireError",
    "ScholarBundleError",
    "ScholarClaimsError",
    "ScholarDiscoverError",
    "ScholarDocsError",
    "ScholarError",
    "ScholarReconcileError",
    "ScholarValidationError",
]
