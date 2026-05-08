"""Finite numeric validation helpers for Fabric boundaries."""

from __future__ import annotations

import math

__all__ = [
    "ensure_finite_float",
    "ensure_non_negative_finite",
    "ensure_probability",
    "finite_or_none",
    "is_finite_number",
]


def ensure_finite_float(value: object, *, what: str) -> float:
    """Return ``value`` as a finite float or raise ``ValueError``."""
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} must be a finite number") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{what} must be finite")
    return numeric


def finite_or_none(value: object, *, what: str) -> float | None:
    """Return ``None`` or a finite float."""
    if value is None:
        return None
    return ensure_finite_float(value, what=what)


def ensure_non_negative_finite(value: object, *, what: str) -> float:
    """Return a finite float greater than or equal to zero."""
    numeric = ensure_finite_float(value, what=what)
    if numeric < 0.0:
        raise ValueError(f"{what} must be >= 0")
    return numeric


def ensure_probability(value: object, *, what: str, clamp: bool = False) -> float:
    """Return a finite normalized score in ``[0, 1]``."""
    numeric = ensure_finite_float(value, what=what)
    if 0.0 <= numeric <= 1.0:
        return numeric
    if clamp:
        return min(1.0, max(0.0, numeric))
    raise ValueError(f"{what} must be in [0, 1]")


def is_finite_number(value: object) -> bool:
    """Return True when ``value`` can be interpreted as a finite float."""
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
