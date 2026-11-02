"""Independent exact-rational oracles for the shared binary64 point owner."""

from __future__ import annotations

import math
import sys
from fractions import Fraction
from itertools import permutations

import pytest

from polisyos.common.numeric_reductions import finite_binary64_mean, finite_binary64_midpoint


def _expected(values: tuple[float, ...]) -> float:
    return float(sum(map(Fraction.from_float, values), Fraction()) / len(values))


@pytest.mark.parametrize(
    "values",
    [
        (1e308, 1e308),
        (sys.float_info.max, sys.float_info.max),
        (-sys.float_info.max, sys.float_info.max),
        (10.0, 14.0),
        (math.ulp(0.0), 2 * math.ulp(0.0)),
        (-math.ulp(0.0), -2 * math.ulp(0.0)),
        (1e308, -1e308, 3 * math.ulp(0.0)),
    ],
)
def test_mean_matches_independent_rational_rounding_for_every_permutation(values):
    for ordered in permutations(values):
        result = finite_binary64_mean(iter(ordered))
        assert math.isfinite(result)
        assert result.hex() == _expected(values).hex()
        if len(ordered) == 2:
            assert finite_binary64_midpoint(*ordered).hex() == _expected(values).hex()


@pytest.mark.parametrize("values", [(), (float("inf"),), (float("nan"),), (10**400,)])
def test_mean_rejects_empty_and_unrepresentable_points(values):
    with pytest.raises(ValueError, match=r"finite|binary64"):
        finite_binary64_mean(values)
