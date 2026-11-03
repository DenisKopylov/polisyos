"""Independent arithmetic controls for conservative uncertainty aggregation."""

from __future__ import annotations

import itertools
import math
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from polisyos.foundry.uncertainty.aggregator import aggregate_envelopes
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _envelope(point: float, lower: float, upper: float) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
        point_estimate=point,
        confidence_interval=(lower, upper),
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        distribution_family=DistributionFamily.UNKNOWN,
        source=UncertaintySource.CALIBRATION,
        gate_eligible=False,
    )


@pytest.mark.parametrize(
    ("points", "bounds"),
    [
        ((1e308, 1e308), ((9e307, 1.1e308), (9e307, 1.1e308))),
        ((1e308, -1e308), ((9e307, 1.1e308), (-1.1e308, -9e307))),
        ((1.0, 3.0), ((0.0, 2.0), (2.0, 4.0))),
        (
            (1e308, -1e308, 3 * math.ulp(0.0)),
            ((9e307, 1.1e308), (-1.1e308, -9e307), (0.0, 3 * math.ulp(0.0))),
        ),
    ],
)
def test_widest_uses_exact_binary64_mean_without_intermediate_overflow(
    points: tuple[float, ...], bounds: tuple[tuple[float, float], ...]
) -> None:
    """No input permutation or full repetition may shift the arithmetic mean."""
    exact = sum((Fraction.from_float(p) for p in points), Fraction()) / len(points)
    expected = float(exact)
    with localcontext() as context:
        context.prec = 1200
        decimal = sum((Decimal.from_float(p) for p in points), Decimal()) / len(points)
    assert float(decimal) == expected

    inputs = [_envelope(point, *bound) for point, bound in zip(points, bounds, strict=True)]
    for ordered in itertools.permutations(inputs):
        for copies in (1, 2):
            result = aggregate_envelopes(ordered * copies, method="widest")
            assert result.point_estimate == expected
            assert result.gate_eligible is False
            assert result.metadata["effective_information_count"] is None
