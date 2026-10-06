from __future__ import annotations

import pytest

from polisyos.foundry.uncertainty.aggregator import AggregationStrategy, aggregate_envelopes
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal_env(
    point: float,
    std: float,
    *,
    origin_id: str | None = None,
    dependency: str | None = None,
) -> UncertaintyEnvelope:
    """Build an envelope; omitted admission metadata is a fail-closed control."""
    z = 1.96
    metadata: dict[str, object] = {}
    if origin_id is not None:
        metadata["envelope_id"] = origin_id
    if dependency is not None:
        metadata["dependency"] = dependency
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z * std, point + z * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata=metadata,
    )


class TestPrecisionWeighted:
    def test_precision_weighted_narrows_ci(self) -> None:
        """Combined CI should be narrower than any individual envelope."""
        env1 = _normal_env(
            10.0,
            2.0,
            origin_id="native-pw-narrows-left",
            dependency="independent",
        )
        env2 = _normal_env(
            10.5,
            3.0,
            origin_id="native-pw-narrows-right",
            dependency="independent",
        )

        result = aggregate_envelopes(
            [env1, env2],
            method=AggregationStrategy.PRECISION_WEIGHTED,
        )

        assert result.ci_width < env1.ci_width
        assert result.ci_width < env2.ci_width
        assert result.composition_provenance is not None
        assert result.composition_provenance.exactness == ExactnessKind.APPROXIMATION

    def test_precision_weighted_equal_variance_averages(self) -> None:
        """With equal variances, point estimate should be the simple average."""
        env1 = _normal_env(
            10.0,
            1.0,
            origin_id="native-pw-equal-left",
            dependency="independent",
        )
        env2 = _normal_env(
            12.0,
            1.0,
            origin_id="native-pw-equal-right",
            dependency="independent",
        )

        result = aggregate_envelopes(
            [env1, env2],
            method=AggregationStrategy.PRECISION_WEIGHTED,
        )

        assert result.point_estimate == pytest.approx(11.0, abs=0.01)
        assert result.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
        assert result.gate_eligible is False
        assert result.metadata["effective_information_count"] is None
        assert result.sample_size is None

    def test_precision_weighted_favors_precise(self) -> None:
        """Point estimate should be closer to the more precise (lower variance) source."""
        env_precise = _normal_env(
            10.0,
            0.5,
            origin_id="native-pw-favors-precise",
            dependency="independent",
        )
        env_imprecise = _normal_env(
            20.0,
            5.0,
            origin_id="native-pw-favors-imprecise",
            dependency="independent",
        )

        result = aggregate_envelopes(
            [env_precise, env_imprecise],
            method=AggregationStrategy.PRECISION_WEIGHTED,
        )

        assert abs(result.point_estimate - 10.0) < abs(result.point_estimate - 20.0)


class TestBayesianCombination:
    def test_bayesian_equivalent_to_precision_weighted_for_normals(self) -> None:
        """For independent normals, Bayesian and precision-weighted should agree."""
        envs = [
            _normal_env(
                10.0,
                2.0,
                origin_id="native-bayes-equivalent-left",
                dependency="independent",
            ),
            _normal_env(
                11.0,
                3.0,
                origin_id="native-bayes-equivalent-right",
                dependency="independent",
            ),
        ]

        pw = aggregate_envelopes(envs, method=AggregationStrategy.PRECISION_WEIGHTED)
        bc = aggregate_envelopes(envs, method=AggregationStrategy.BAYESIAN_COMBINATION)

        assert pw.point_estimate == pytest.approx(bc.point_estimate, abs=0.01)
        assert pw.ci_width == pytest.approx(bc.ci_width, abs=0.05)
        assert pw.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
        assert bc.interval_semantics is IntervalSemantics.CREDIBLE_INTERVAL
        assert pw.gate_eligible is False
        assert bc.gate_eligible is False
        assert pw.metadata["effective_information_count"] is None
        assert bc.metadata["effective_information_count"] is None

    def test_bayesian_interval_semantics(self) -> None:
        result = aggregate_envelopes(
            [
                _normal_env(
                    5.0,
                    1.0,
                    origin_id="native-bayes-interval-left",
                    dependency="independent",
                ),
                _normal_env(
                    6.0,
                    1.0,
                    origin_id="native-bayes-interval-right",
                    dependency="independent",
                ),
            ],
            method=AggregationStrategy.BAYESIAN_COMBINATION,
        )
        assert result.interval_semantics == IntervalSemantics.CREDIBLE_INTERVAL
        assert result.gate_eligible is False
        assert result.metadata["effective_information_count"] is None


class TestWidestBackwardCompat:
    def test_widest_backward_compat(self) -> None:
        """Unbound widest aggregation remains a fail-closed control."""
        env1 = _normal_env(10.0, 2.0)
        env2 = _normal_env(12.0, 1.0)

        result = aggregate_envelopes([env1, env2], method="widest")

        assert result.confidence_interval[0] == min(
            env1.confidence_interval[0],
            env2.confidence_interval[0],
        )
        assert result.confidence_interval[1] == max(
            env1.confidence_interval[1],
            env2.confidence_interval[1],
        )
        assert result.metadata["aggregation_method"] == "widest"
        assert result.gate_eligible is False
        assert result.metadata["effective_information_count"] is None
        assert result.sample_size is None

    def test_aggregated_ci_contains_all_points(self) -> None:
        """Property: widest CI must contain all source point estimates."""
        envs = [
            _normal_env(5.0, 1.0),
            _normal_env(10.0, 2.0),
            _normal_env(15.0, 0.5),
        ]

        result = aggregate_envelopes(envs, method="widest")

        for env in envs:
            assert result.confidence_interval[0] <= env.point_estimate
            assert result.confidence_interval[1] >= env.point_estimate

    def test_unknown_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown aggregation method"):
            aggregate_envelopes(
                [_normal_env(1.0, 1.0), _normal_env(2.0, 1.0)],
                method="magic",
            )


class TestAggregatorEdgeCases:
    def test_aggregate_single_envelope_passthrough(self) -> None:
        env = _normal_env(10.0, 2.0)
        result = aggregate_envelopes([env], method="widest")
        assert result is env

    def test_aggregate_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot aggregate empty"):
            aggregate_envelopes([], method="widest")

    def test_bayesian_combination_narrows_ci(self) -> None:
        env1 = _normal_env(
            10.0,
            2.0,
            origin_id="native-bayes-narrows-left",
            dependency="independent",
        )
        env2 = _normal_env(
            10.5,
            2.0,
            origin_id="native-bayes-narrows-right",
            dependency="independent",
        )
        result = aggregate_envelopes(
            [env1, env2],
            method=AggregationStrategy.BAYESIAN_COMBINATION,
        )
        assert result.ci_width < env1.ci_width
        assert result.ci_width < env2.ci_width

    def test_aggregate_mixed_heuristic_downgrades_semantics(self) -> None:
        normal = _normal_env(10.0, 2.0)
        heuristic = UncertaintyEnvelope(
            point_estimate=11.0,
            confidence_interval=(9.0, 13.0),
            confidence_level=None,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            gate_eligible=False,
            is_heuristic_ci=True,
        )
        result = aggregate_envelopes([normal, heuristic], method="widest")
        assert result.interval_semantics == IntervalSemantics.HEURISTIC_RANGE
