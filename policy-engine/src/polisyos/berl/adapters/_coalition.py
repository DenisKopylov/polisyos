"""Shared exact Shapley enumeration for BERL coalition-value providers."""

from __future__ import annotations

import math
from itertools import combinations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def exact_shapley_attributions(
    feature_names: tuple[str, ...],
    coalition_value: Callable[[frozenset[str]], float],
) -> dict[str, float]:
    """Enumerate exact Shapley values from one owner-supplied coalition function.

    Args:
        feature_names: Unique feature identifiers in the explanation order.
        coalition_value: Function defining the value of each feature coalition.

    Returns:
        The exact finite-player Shapley attribution for each feature.

    Raises:
        ValueError: If feature identifiers are not unique.
    """

    if len(set(feature_names)) != len(feature_names):
        raise ValueError("feature names must be unique for coalition enumeration")
    feature_count = len(feature_names)
    if feature_count == 0:
        return {}
    factorial_n = math.factorial(feature_count)
    attributions: dict[str, float] = {}
    for feature in feature_names:
        others = tuple(candidate for candidate in feature_names if candidate != feature)
        total = 0.0
        for size in range(feature_count):
            weight = math.factorial(size) * math.factorial(feature_count - size - 1) / factorial_n
            for subset in combinations(others, size):
                coalition = frozenset(subset)
                total += weight * (
                    coalition_value(coalition | {feature}) - coalition_value(coalition)
                )
        attributions[feature] = total
    return attributions
