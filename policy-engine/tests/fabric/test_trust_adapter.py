from __future__ import annotations

from decimal import Decimal

from polisyos.core.contracts.fabric import UncertaintyBounds
from polisyos.fabric.trust import two_pass_compare_with_envelope
from polisyos.fabric.trust_adapter import envelope_from_trust_bounds
from polisyos.ir.analytics.uncertainty import DistributionFamily, IntervalSemantics, UncertaintySource


def test_envelope_from_bounds_default_distribution() -> None:
    bounds = UncertaintyBounds(
        value=Decimal("50.0"),
        lower=Decimal("45.0"),
        upper=Decimal("55.0"),
    )
    env = envelope_from_trust_bounds(bounds)
    assert env.point_estimate == 50.0
    assert env.confidence_interval == (45.0, 55.0)
    assert env.source == UncertaintySource.TRUST
    assert env.interval_semantics == IntervalSemantics.DETERMINISTIC_BOUNDS
    assert env.distribution_family == DistributionFamily.UNKNOWN


def test_two_pass_compare_with_envelope() -> None:
    bounds, env = two_pass_compare_with_envelope(optimistic_value=10.0, pessimistic_value=6.0)
    assert float(bounds.value) == 8.0
    assert env.point_estimate == 8.0
    assert env.confidence_interval == (6.0, 10.0)


def test_envelope_from_bounds_triangular_assumption() -> None:
    bounds = UncertaintyBounds(
        value=Decimal("12.0"),
        lower=Decimal("10.0"),
        upper=Decimal("14.0"),
    )
    env = envelope_from_trust_bounds(bounds, assume_triangular=True)
    assert env.distribution_family == DistributionFamily.TRIANGULAR
    assert env.metadata["distribution_assumption"] == "triangular_optional"
