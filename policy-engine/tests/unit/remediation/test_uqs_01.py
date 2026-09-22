"""UQS-01 bounded B199/B200 witnesses for aggregation provenance."""

from __future__ import annotations

from statistics import NormalDist

import pytest

from polisyos.foundry.uncertainty.aggregator import (
    AggregationStrategy,
    aggregate_envelopes,
)
from polisyos.foundry.uncertainty.covariance import extract_std
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

pytestmark = pytest.mark.unit


def _normal_env(
    point: float,
    std: float,
    *,
    origin_id: str,
    confidence_level: float = 0.8,
    interval_semantics: IntervalSemantics = IntervalSemantics.CONFIDENCE_INTERVAL,
    dependency: str | None = "independent",
) -> UncertaintyEnvelope:
    """Build a Gaussian envelope with explicit provenance for aggregation tests."""
    z_value = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    metadata: dict[str, object] = {"envelope_id": origin_id}
    if dependency is not None:
        metadata["dependency"] = dependency
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z_value * std, point + z_value * std),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=interval_semantics,
        gate_eligible=True,
        metadata=metadata,
    )


def test_widest_preserves_declared_level_and_semantics_for_duplicate_origin() -> None:
    """Repeating an interval must not silently turn 0.8 into a 0.95 CI."""
    envelope = _normal_env(10.0, 1.0, origin_id="origin-a")

    result = aggregate_envelopes([envelope, envelope], method="widest")

    assert result.confidence_level == pytest.approx(0.8)
    assert result.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
    assert result.point_estimate == envelope.point_estimate
    assert result.confidence_interval == envelope.confidence_interval
    assert result.metadata["effective_information_count"] == 1


@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
def test_duplicate_origin_is_used_once_for_narrowing(method: AggregationStrategy) -> None:
    """Two references to one envelope cannot manufacture a second information unit."""
    envelope = _normal_env(10.0, 1.0, origin_id="origin-a")

    result = aggregate_envelopes([envelope, envelope], method=method)

    assert extract_std(result) == pytest.approx(1.0, abs=1e-9)
    assert result.metadata["source_count"] == 2
    assert result.metadata["effective_information_count"] == 1
    assert result.sample_size == 1


@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
def test_equal_values_with_different_origins_remain_distinct(method: AggregationStrategy) -> None:
    """Numeric equality is not provenance: two independent origins may narrow once."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a")
    right = _normal_env(10.0, 1.0, origin_id="origin-b")

    result = aggregate_envelopes([left, right], method=method)

    assert extract_std(result) == pytest.approx(1.0 / (2.0**0.5), abs=1e-9)
    assert result.metadata["source_count"] == 2
    assert result.metadata["effective_information_count"] == 2
    assert result.sample_size == 2


def test_conflicting_values_for_one_origin_fail_closed() -> None:
    """A provenance collision cannot be resolved by treating conflicting values as replicas."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a")
    right = _normal_env(12.0, 1.0, origin_id="origin-a")

    with pytest.raises(ValueError, match="conflicting envelopes for origin"):
        aggregate_envelopes(
            [left, right],
            method=AggregationStrategy.PRECISION_WEIGHTED,
        )


def test_mixed_confidence_and_credible_inputs_do_not_gain_statistical_label() -> None:
    """A widest hull over different statistical semantics becomes a non-gating bound."""
    confidence = _normal_env(10.0, 1.0, origin_id="origin-a")
    credible = _normal_env(
        10.0,
        1.0,
        origin_id="origin-b",
        interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
    )

    result = aggregate_envelopes([confidence, credible], method="widest")

    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.gate_eligible is False
    assert result.metadata["effective_information_count"] == 2


def test_unknown_dependency_does_not_narrow_or_remain_gate_eligible() -> None:
    """Unestablished dependence blocks precision-style narrowing and authority."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a", dependency="unknown")
    right = _normal_env(10.0, 1.0, origin_id="origin-b", dependency="independent")

    result = aggregate_envelopes(
        [left, right],
        method=AggregationStrategy.PRECISION_WEIGHTED,
    )

    assert extract_std(result) == pytest.approx(1.0, abs=1e-9)
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.gate_eligible is False
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"
