"""Public errors base module API."""
from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class ErrorCategory(str, Enum):
    """High-level error category for unified handling."""

    TRANSIENT = "transient"
    FATAL = "fatal"
    VALIDATION = "validation"


class PolicyOSError(Exception):
    """
    Base exception for PolisyOS modules.

    Provides consistent metadata across subsystems so errors can be routed,
    logged, and classified without per-module adapters.
    """

    default_category = ErrorCategory.FATAL
    default_stage = "core"

    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory | str | None = None,
        stage: str | None = None,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = self._coerce_category(category) if category is not None else self.default_category
        self.stage = stage or self.default_stage
        self.code = code
        self.details: Mapping[str, Any] = MappingProxyType(dict(details or {}))

    @staticmethod
    def _coerce_category(value: ErrorCategory | str) -> ErrorCategory:
        if isinstance(value, ErrorCategory):
            return value
        raw = str(value).strip().lower()
        try:
            return ErrorCategory(raw)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported error category '{value}'. "
                f"Expected one of: {[item.value for item in ErrorCategory]}"
            ) from exc

    @property
    def is_transient(self) -> bool:
        return self.category == ErrorCategory.TRANSIENT

    @property
    def is_fatal(self) -> bool:
        return self.category == ErrorCategory.FATAL

    @property
    def is_validation(self) -> bool:
        return self.category == ErrorCategory.VALIDATION

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "stage": self.stage,
            "code": self.code,
            "details": dict(self.details),
        }
