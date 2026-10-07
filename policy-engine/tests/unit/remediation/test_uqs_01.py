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
    CertificateKind,
    ComposedFlavour,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    build_composition_provenance,
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


def _inline_provenance_env(point: float, std: float) -> UncertaintyEnvelope:
    """Build an envelope whose only origin is IR's numeric inline fallback."""
    envelope = _normal_env(
        point,
        std,
        origin_id="",
        dependency="independent",
    )
    provenance = build_composition_provenance(
        input_envelopes=(envelope,),
        op="compress",
        stage_name="tests.uqs_01.inline",
        output_flavour=ComposedFlavour.ANALYTICAL,
        exactness=ExactnessKind.APPROXIMATION,
        certificate_kind=CertificateKind.WASSERSTEIN_1,
        certificate_radius=None,
        confidence_level=envelope.confidence_level,
        scope=("expectation", "interval", "quantile"),
    )
    return envelope.model_copy(update={"composition_provenance": provenance})


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
    assert result.sample_size is None


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
    assert result.metadata["effective_information_count"] is None
    assert result.sample_size is None


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
    assert result.metadata["effective_information_count"] is None


def test_unknown_dependency_does_not_narrow_or_remain_gate_eligible() -> None:
    """Unestablished dependence blocks precision-style narrowing and authority."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a", dependency="unknown")
    right = _normal_env(10.0, 1.0, origin_id="origin-b", dependency="independent")

    result = aggregate_envelopes(
        [left, right],
        method=AggregationStrategy.PRECISION_WEIGHTED,
    )

    assert result.confidence_interval == (
        min(left.ci_lower, right.ci_lower),
        max(left.ci_upper, right.ci_upper),
    )
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.gate_eligible is False
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"
    assert result.sample_size is None


@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
@pytest.mark.parametrize("dependency", [None, "maybe_independent"])
def test_unestablished_dependency_does_not_enable_formula(
    method: AggregationStrategy,
    dependency: str | None,
) -> None:
    """Missing or unrecognized independence evidence remains fail-closed."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a", dependency=dependency)
    right = _normal_env(10.0, 1.0, origin_id="origin-b", dependency=dependency)

    result = aggregate_envelopes([left, right], method=method)

    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.confidence_interval == (
        min(left.ci_lower, right.ci_lower),
        max(left.ci_upper, right.ci_upper),
    )
    assert result.gate_eligible is False
    assert result.sample_size is None
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"


@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
def test_unbound_origins_do_not_enable_formula(method: AggregationStrategy) -> None:
    """Independent labels cannot repair absent content-bound information units."""
    left = _normal_env(10.0, 1.0, origin_id="", dependency="independent")
    right = _normal_env(10.0, 1.0, origin_id="", dependency="independent")

    result = aggregate_envelopes([left, right], method=method)

    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.confidence_interval == (
        min(left.ci_lower, right.ci_lower),
        max(left.ci_upper, right.ci_upper),
    )
    assert result.gate_eligible is False
    assert result.sample_size is None
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"


@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
def test_numeric_inline_provenance_does_not_authorize_deduplication(
    method: AggregationStrategy,
) -> None:
    """IR's numeric-derived inline IDs cannot masquerade as origin identity."""
    left = _inline_provenance_env(10.0, 1.0)
    right = _inline_provenance_env(10.0, 1.0)

    result = aggregate_envelopes([left, right], method=method)

    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.gate_eligible is False
    assert result.sample_size is None
    assert result.metadata["source_count"] == 2
    assert result.metadata["duplicate_source_count"] == 0
    assert result.metadata["effective_information_count"] is None
