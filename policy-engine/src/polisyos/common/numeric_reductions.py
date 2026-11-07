"""Finite binary64 point reductions over CPython's exact-sum mean owner.

These functions compute numerical points. They do not establish source identity,
measurement independence, units, or scientific authority.
"""

from __future__ import annotations

import math
from statistics import StatisticsError, mean
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

__all__ = ["finite_binary64_mean", "finite_binary64_midpoint"]


def _finite_values(values: Iterable[float]) -> Iterator[float]:
    for value in values:
        try:
            point = float(value)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("Point reductions require finite binary64 inputs") from exc
        if not math.isfinite(point):
            raise ValueError("Point reductions require finite binary64 inputs")
        yield point


def finite_binary64_mean(values: Iterable[float]) -> float:
    """Return the correctly rounded mean of finite binary64 inputs.

    Each input is converted to a Python float before the existing
    :func:`statistics.mean` reduction. Its exact integer-ratio summation avoids
    intermediate float overflow and cancellation or subnormal loss.

    Args:
        values: A nonempty iterable of values admitted as finite Python floats.

    Returns:
        The finite binary64 mean, rounded once by the standard-library owner.

    Raises:
        ValueError: If inputs are empty, nonfinite or not representable as
            binary64, or the result is nonfinite.
    """
    try:
        result = float(mean(_finite_values(values)))
    except StatisticsError as exc:
        raise ValueError("Point reductions require at least one finite input") from exc
    if not math.isfinite(result):
        raise ValueError("Point reduction produced a nonfinite result")
    return result


def finite_binary64_midpoint(left: float, right: float) -> float:
    """Return the finite, correctly rounded midpoint without float-sum overflow.

    Args:
        left: First finite binary64 point.
        right: Second finite binary64 point.

    Returns:
        The same standard-library mean of the two admitted points.

    Raises:
        ValueError: If either input is not a finite binary64 value.
    """
    return finite_binary64_mean((left, right))
