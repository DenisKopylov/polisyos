"""Custom exceptions for search strategies."""

from __future__ import annotations

from polisyos.scientist.methods.search.contracts import GenerationNotice, GenerationTransition


class StrategyError(RuntimeError):
    """Base class for strategy-related failures."""


class StrategyExhaustedError(GenerationNotice, StrategyError):
    """Raised when a finite strategy has no more candidates."""

    def __init__(self, reason: str) -> None:
        super().__init__(GenerationTransition.EXHAUSTED, reason)


class StrategyAttemptLimitError(GenerationNotice, StrategyError):
    """A strategy spent its declared proposal budget without proving source exhaustion."""

    def __init__(self, reason: str) -> None:
        super().__init__(GenerationTransition.ATTEMPT_LIMIT, reason)


class OptionalDependencyUnavailableError(StrategyError):
    """Raised when strategy requires missing optional dependencies."""
