"""Exports backend dispatch primitives that select executable runtime implementations."""

from .dispatcher import BackendDispatcher, BackendNotAvailableError

__all__ = [
    "BackendDispatcher",
    "BackendNotAvailableError",
]
