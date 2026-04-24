"""Public store errors module API."""

from __future__ import annotations

from polisyos.core.errors import ErrorCategory, PolicyOSError


class WorldStoreError(PolicyOSError):
    """Base error for world store operations."""

    default_stage = "fabric.world.store"
    default_category = ErrorCategory.FATAL


class WorldValidationError(WorldStoreError):
    """Raised for validation failures in world store operations."""

    default_category = ErrorCategory.VALIDATION


class WorldIDError(WorldValidationError):
    """Raised when deterministic world id rules are violated."""


class WorldFactError(WorldValidationError):
    """Raised when emitted facts violate the World ABI."""


class WorldSegmentError(WorldStoreError):
    """Raised when segment IO or index operations fail."""

    default_category = ErrorCategory.TRANSIENT


__all__ = [
    "WorldFactError",
    "WorldIDError",
    "WorldSegmentError",
    "WorldStoreError",
    "WorldValidationError",
]
