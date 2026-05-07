"""Custom exceptions for search strategies."""

from __future__ import annotations


class StrategyError(RuntimeError):
    """Base class for strategy-related failures."""


class StrategyExhaustedError(StrategyError):
    """Raised when a finite strategy has no more candidates."""


class OptionalDependencyUnavailableError(StrategyError):
    """Raised when strategy requires missing optional dependencies."""
