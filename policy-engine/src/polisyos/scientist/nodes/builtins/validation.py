"""Typed parameter validation utilities for builtin nodes."""

from __future__ import annotations

from typing import Any

from polisyos.scientist.orchestration.engine.protocol import NodeError


class NodeParamError(Exception):
    """Raised by validators; converted to NodeError at the call site."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_CODE = "node.validation_error"


class NodeParamValidator:
    """Static helpers for extracting and validating node parameters.

    Each method raises ``NodeParamError`` on failure, which the caller
    can convert into a ``NodeOutcome(status="fail", error=...)``.
    """

    @staticmethod
    def require_str(
        params: dict[str, Any],
        key: str,
        *,
        min_length: int = 1,
    ) -> str:
        """Require a non-empty string parameter."""
        value = params.get(key)
        if not isinstance(value, str) or len(value.strip()) < min_length:
            raise NodeParamError(
                _CODE,
                f"Required string parameter '{key}' missing or too short "
                f"(min_length={min_length}).",
            )
        return value.strip()

    @staticmethod
    def require_int(
        params: dict[str, Any],
        key: str,
        *,
        ge: int | None = None,
        le: int | None = None,
    ) -> int:
        """Require an integer parameter within optional bounds."""
        value = params.get(key)
        if value is None:
            raise NodeParamError(_CODE, f"Required integer parameter '{key}' is missing.")
        try:
            result = int(value)
        except (TypeError, ValueError):
            raise NodeParamError(
                _CODE, f"Parameter '{key}' must be an integer, got {type(value).__name__}."
            )
        if ge is not None and result < ge:
            raise NodeParamError(_CODE, f"Parameter '{key}' must be >= {ge}, got {result}.")
        if le is not None and result > le:
            raise NodeParamError(_CODE, f"Parameter '{key}' must be <= {le}, got {result}.")
        return result

    @staticmethod
    def require_float(
        params: dict[str, Any],
        key: str,
        *,
        ge: float | None = None,
        le: float | None = None,
    ) -> float:
        """Require a float parameter within optional bounds."""
        value = params.get(key)
        if value is None:
            raise NodeParamError(_CODE, f"Required float parameter '{key}' is missing.")
        try:
            result = float(value)
        except (TypeError, ValueError):
            raise NodeParamError(
                _CODE, f"Parameter '{key}' must be numeric, got {type(value).__name__}."
            )
        if ge is not None and result < ge:
            raise NodeParamError(_CODE, f"Parameter '{key}' must be >= {ge}, got {result}.")
        if le is not None and result > le:
            raise NodeParamError(_CODE, f"Parameter '{key}' must be <= {le}, got {result}.")
        return result

    @staticmethod
    def optional_str(
        params: dict[str, Any],
        key: str,
        default: str = "",
    ) -> str:
        """Return a string parameter or *default* if absent."""
        value = params.get(key)
        if isinstance(value, str):
            return value.strip()
        return default

    @staticmethod
    def optional_float(
        params: dict[str, Any],
        key: str,
        default: float = 0.0,
    ) -> float:
        """Return a float parameter or *default* if absent."""
        value = params.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def optional_int(
        params: dict[str, Any],
        key: str,
        default: int = 0,
    ) -> int:
        """Return an int parameter or *default* if absent."""
        value = params.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def require_list(
        params: dict[str, Any],
        key: str,
        *,
        min_length: int = 0,
    ) -> list[Any]:
        """Require a list parameter."""
        value = params.get(key)
        if not isinstance(value, list):
            raise NodeParamError(
                _CODE,
                f"Required list parameter '{key}' missing or not a list.",
            )
        if len(value) < min_length:
            raise NodeParamError(
                _CODE,
                f"List parameter '{key}' must have at least {min_length} items.",
            )
        return value

    @staticmethod
    def to_node_error(exc: NodeParamError) -> NodeError:
        """Convert a ``NodeParamError`` to a ``NodeError`` model."""
        return NodeError(code=exc.code, message=str(exc))


__all__ = [
    "NodeParamError",
    "NodeParamValidator",
]
