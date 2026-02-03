from __future__ import annotations


class WorldStoreError(Exception):
    """Base error for world store operations."""


class WorldValidationError(WorldStoreError):
    """Raised for validation failures in world store operations."""


class WorldIDError(WorldValidationError):
    """Raised when deterministic world id rules are violated."""


class WorldFactError(WorldValidationError):
    """Raised when emitted facts violate the World ABI."""


class WorldSegmentError(WorldStoreError):
    """Raised when segment IO or index operations fail."""


__all__ = [
    "WorldFactError",
    "WorldIDError",
    "WorldSegmentError",
    "WorldStoreError",
    "WorldValidationError",
]
