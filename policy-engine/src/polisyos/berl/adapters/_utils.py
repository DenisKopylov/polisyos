"""Shared adapter parsing helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.berl.adapters.protocol import ExplanationContext


class DeterministicUniform:
    """Small deterministic RNG for reproducible simulation, not security use."""

    def __init__(self, seed: int | None) -> None:
        self._state = (seed if seed is not None else 1) & 0x7FFFFFFF
        if self._state == 0:
            self._state = 1

    def uniform(self, lower: float, upper: float) -> float:
        """Return a reproducible value in [lower, upper]."""

        self._state = (1103515245 * self._state + 12345) & 0x7FFFFFFF
        unit = self._state / 0x7FFFFFFF
        return lower + ((upper - lower) * unit)


def float_param(context: ExplanationContext, name: str, default: float) -> float:
    """Read a finite float parameter from an ExplanationContext."""

    value = context.params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"context param {name!r} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"context param {name!r} must be finite")
    return result


def int_param(context: ExplanationContext, name: str, default: int) -> int:
    """Read an integer parameter from an ExplanationContext."""

    value = context.params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"context param {name!r} must be an integer")
    return value


def background_rows_from_context(
    context: ExplanationContext,
    x: Mapping[str, float],
) -> tuple[dict[str, float], ...]:
    """Return background rows from context params or fall back to the explained row."""

    raw_rows = context.params.get("background_rows")
    if raw_rows is None:
        return (_project_row(x, context.feature_names),)
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise ValueError("context param 'background_rows' must be a sequence of mappings")
    rows: list[dict[str, float]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise ValueError("each background row must be a mapping")
        rows.append(_project_row(raw_row, context.feature_names))
    if not rows:
        raise ValueError("background_rows must not be empty")
    return tuple(rows)


def _project_row(row: Mapping[str, object], feature_names: Sequence[str]) -> dict[str, float]:
    projected: dict[str, float] = {}
    for feature in feature_names:
        value = row.get(feature, 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"feature {feature!r} must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"feature {feature!r} must be finite")
        projected[feature] = numeric
    return projected
