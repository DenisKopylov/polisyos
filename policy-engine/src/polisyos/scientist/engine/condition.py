"""Conditional node execution based on runtime state.

Provides a safe expression DSL for evaluating conditions against
:class:`ExperimentState`. No ``eval()`` — only dot-path traversal with
comparison operators.

Expression grammar::

    expr        = path OPERATOR value
    path        = identifier ("." identifier)*
    OPERATOR    = "==" | "!=" | ">" | "<" | ">=" | "<=" | "in" | "not_in"
                | "is_set" | "is_empty"
    value       = BOOL | NULL | NUMBER | STRING
    BOOL        = "true" | "false"
    NULL        = "null"
    NUMBER      = ["-"] DIGIT+ ["." DIGIT+]
    STRING      = '"' ... '"' | "'" ... "'"

Unary operators (``is_set``, ``is_empty``) do not take a right-hand value.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.engine.state import ExperimentState

__all__ = [
    "NodeCondition",
    "evaluate_condition",
    "ConditionSyntaxError",
]


class ConditionSyntaxError(ValueError):
    """Raised when a condition expression cannot be parsed."""


class NodeCondition(BaseModel):
    """Optional condition attached to a :class:`NodeInvocation`.

    When the condition evaluates to ``False``:

    * ``on_false="skip"`` — the node is silently skipped (does **not** block
      downstream nodes).
    * ``on_false="fail"`` — the node is marked as failed (blocks downstream).
    """

    model_config = ConfigDict(extra="forbid")

    expr: str = Field(..., min_length=1, max_length=512)
    on_false: Literal["skip", "fail"] = "skip"


# ---------------------------------------------------------------------------
# Path resolution (mirrors idempotency._resolve_path)
# ---------------------------------------------------------------------------

def _resolve_path(state: ExperimentState, path: str) -> Any:
    """Resolve a dot-path against *state*, returning ``None`` for missing."""
    parts = path.split(".")
    current: Any = state
    for part in parts:
        if isinstance(current, BaseModel):
            current = getattr(current, part, None)
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_BINARY_OPS = frozenset({"==", "!=", ">", "<", ">=", "<=", "in", "not_in"})
_UNARY_OPS = frozenset({"is_set", "is_empty"})
_ALL_OPS = _BINARY_OPS | _UNARY_OPS

# Regex: captures a dot-path, then an operator, then an optional literal.
_TOKEN_RE = re.compile(
    r"^"
    r"(?P<path>[a-zA-Z_][a-zA-Z0-9_.]*)"
    r"\s+"
    r"(?P<op>" + "|".join(re.escape(op) for op in sorted(_ALL_OPS, key=len, reverse=True)) + r")"
    r"(?:\s+(?P<value>.+))?"
    r"$",
)


def _parse_literal(raw: str) -> Any:
    """Parse a literal value from the expression RHS."""
    raw = raw.strip()
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw == "null":
        return None

    # Quoted string
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        return raw[1:-1]

    # Number
    try:
        if "." in raw:
            return Decimal(raw)
        return int(raw)
    except (ValueError, InvalidOperation):
        pass

    # Bare string (unquoted) — treat as string literal
    return raw


# ---------------------------------------------------------------------------
# Comparisons
# ---------------------------------------------------------------------------

def _coerce_for_comparison(resolved: Any) -> Any:
    """Normalise resolved state values for comparison.

    * ``ArtifactRef`` ➜ its ``artifact_id`` string.
    * ``Decimal`` stays as-is.
    """
    if resolved is None:
        return None
    # ArtifactRef has an artifact_id attribute
    if hasattr(resolved, "artifact_id"):
        return getattr(resolved, "artifact_id")
    return resolved


def _eq(left: Any, right: Any) -> bool:
    # Allow comparing int ↔ Decimal transparently
    try:
        return left == right  # type: ignore[no-any-return]
    except TypeError:
        return False


def _compare(left: Any, op: str, right: Any) -> bool:
    left = _coerce_for_comparison(left)
    if op == "==":
        return _eq(left, right)
    if op == "!=":
        return not _eq(left, right)

    # Ordering ops require both sides to be comparable
    if left is None or right is None:
        return False
    try:
        if op == ">":
            return left > right  # type: ignore[operator]
        if op == "<":
            return left < right  # type: ignore[operator]
        if op == ">=":
            return left >= right  # type: ignore[operator]
        if op == "<=":
            return left <= right  # type: ignore[operator]
    except TypeError:
        return False

    # Membership
    if op == "in":
        if isinstance(right, (list, tuple, set, frozenset)):
            return left in right
        if isinstance(right, str):
            return str(left) in right
        return False
    if op == "not_in":
        if isinstance(right, (list, tuple, set, frozenset)):
            return left not in right
        if isinstance(right, str):
            return str(left) not in right
        return True

    raise ConditionSyntaxError(f"Unknown operator: {op}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_condition(expr: str, state: ExperimentState) -> bool:
    """Evaluate a condition expression against *state*.

    Returns ``True`` if the condition is satisfied, ``False`` otherwise.
    Raises :class:`ConditionSyntaxError` for malformed expressions.
    """
    expr = expr.strip()
    if not expr:
        raise ConditionSyntaxError("Empty condition expression")

    match = _TOKEN_RE.match(expr)
    if match is None:
        raise ConditionSyntaxError(f"Cannot parse condition: {expr!r}")

    path = match.group("path")
    op = match.group("op")
    raw_value = match.group("value")

    resolved = _resolve_path(state, path)

    # Unary operators
    if op == "is_set":
        return resolved is not None
    if op == "is_empty":
        if resolved is None:
            return True
        if isinstance(resolved, (str, list, dict)):
            return len(resolved) == 0
        return False

    # Binary operators require a RHS
    if raw_value is None:
        raise ConditionSyntaxError(
            f"Operator {op!r} requires a right-hand value in: {expr!r}"
        )

    literal = _parse_literal(raw_value)
    return _compare(resolved, op, literal)
