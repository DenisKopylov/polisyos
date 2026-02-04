from __future__ import annotations

from typing import Any


class ScholarError(Exception):
    """Base error for Scholar enrichment pipeline."""

    default_stage = "scholar"

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        source_identity: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage or self.default_stage
        self.source_identity = source_identity
        self.details = details or {}


class ScholarValidationError(ScholarError):
    default_stage = "validation"


class ScholarDiscoverError(ScholarError):
    default_stage = "discover"


class ScholarAcquireError(ScholarError):
    default_stage = "acquire"


class ScholarDocsError(ScholarError):
    default_stage = "docs"


class ScholarClaimsError(ScholarError):
    default_stage = "claims"


class ScholarReconcileError(ScholarError):
    default_stage = "reconcile"


class ScholarBundleError(ScholarError):
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
