"""UQS-01 bounded B199/B200 witnesses for aggregation provenance."""

from __future__ import annotations

from statistics import NormalDist

import pytest

from polisyos.foundry.uncertainty.aggregator import (
    AggregationStrategy,
    aggregate_envelopes,
)
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


def test_repeated_self_asserted_origin_remains_an_unresolved_hull() -> None:
    """An in-memory origin label cannot prove that two entries are one source."""
    envelope = _normal_env(10.0, 1.0, origin_id="origin-a")

    result = aggregate_envelopes([envelope, envelope], method="widest")

    assert result.confidence_level is None
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.point_estimate == envelope.point_estimate
    assert result.confidence_interval == envelope.confidence_interval
    assert result.gate_eligible is False
    assert result.metadata["source_count"] == 2
    assert result.metadata["duplicate_source_count"] == 0
    assert result.metadata["effective_information_count"] is None
    assert result.sample_size is None


@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
def test_repeated_origin_label_does_not_enable_narrowing(method: AggregationStrategy) -> None:
    """A self-asserted duplicate cannot authorize precision or Bayesian narrowing."""
    envelope = _normal_env(10.0, 1.0, origin_id="origin-a")

    result = aggregate_envelopes([envelope, envelope], method=method)

    assert result.confidence_interval == envelope.confidence_interval
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.gate_eligible is False
    assert result.metadata["source_count"] == 2
    assert result.metadata["duplicate_source_count"] == 0
    assert result.metadata["effective_information_count"] is None
    assert result.sample_size is None


@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
def test_distinct_origins_without_resolved_relation_do_not_enable_formula(
    method: AggregationStrategy,
) -> None:
    """Different content origins do not prove that their measurements are independent."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a")
    right = _normal_env(10.0, 1.0, origin_id="origin-b")

    result = aggregate_envelopes([left, right], method=method)

    assert result.confidence_interval == (
        min(left.ci_lower, right.ci_lower),
        max(left.ci_upper, right.ci_upper),
    )
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.gate_eligible is False
    assert result.metadata["source_count"] == 2
    assert result.metadata["effective_information_count"] is None
    assert result.sample_size is None


@pytest.mark.parametrize(
    "asserted_relation",
    [
        {"dependency": "independent"},
        {"independence": True},
        {"dependency": True},
        {"dependency": "independent", "independence": True},
    ],
)
@pytest.mark.parametrize(
    "method",
    [AggregationStrategy.PRECISION_WEIGHTED, AggregationStrategy.BAYESIAN_COMBINATION],
)
def test_caller_asserted_independence_does_not_enable_formula(
    asserted_relation: dict[str, object],
    method: AggregationStrategy,
) -> None:
    """A metadata label is not a resolved producer-bound measurement relation."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a", dependency=None).model_copy(
        update={"metadata": {"envelope_id": "origin-a", **asserted_relation}}
    )
    right = _normal_env(10.0, 1.0, origin_id="origin-b", dependency=None).model_copy(
        update={"metadata": {"envelope_id": "origin-b", **asserted_relation}}
    )

    result = aggregate_envelopes([left, right], method=method)

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


def test_same_fake_origin_with_different_values_is_retained_as_unresolved() -> None:
    """A string collision cannot reject or collapse valid, separately supplied inputs."""
    left = _normal_env(10.0, 1.0, origin_id="origin-a")
    right = _normal_env(12.0, 1.0, origin_id="origin-a")

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
    assert result.metadata["source_count"] == 2
    assert result.metadata["duplicate_source_count"] == 0
    assert result.metadata["effective_information_count"] is None


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
