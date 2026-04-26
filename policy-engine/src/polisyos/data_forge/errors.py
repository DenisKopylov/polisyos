"""Shared Data Forge exception types."""

from __future__ import annotations


class DataForgeError(Exception):
    """Base exception for Data Forge foundation code."""


class DataForgeValidationError(DataForgeError, ValueError):
    """Raised when a Data Forge contract is malformed."""


class SchemaCompatibilityError(DataForgeValidationError):
    """Raised when a schema change lacks an allowed evolution rule."""


class SnapshotCommitError(DataForgeError):
    """Raised when a snapshot transaction cannot be safely committed."""


__all__ = [
    "DataForgeError",
    "DataForgeValidationError",
    "SchemaCompatibilityError",
    "SnapshotCommitError",
]
