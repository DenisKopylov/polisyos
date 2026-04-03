"""Public uncertainty aggregator module API."""
from __future__ import annotations

import math
from enum import Enum
from statistics import NormalDist
from typing import Sequence

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .covariance import extract_std


class AggregationStrategy(str, Enum):
    """Aggregation strategy data model."""
    WIDEST = "widest"
    PRECISION_WEIGHTED = "precision_weighted"
    BAYESIAN_COMBINATION = "bayesian_combination"


def aggregate_envelopes(
    envelopes: Sequence[UncertaintyEnvelope],
    *,
    method: str = "widest",
    confidence_level: float = 0.95,
) -> UncertaintyEnvelope:
    """Aggregate envelopes helper."""
    if not envelopes:
        raise ValueError("Cannot aggregate empty envelope list")
    if len(envelopes) == 1:
        return envelopes[0]

    if method == AggregationStrategy.PRECISION_WEIGHTED:
        return _precision_weighted(envelopes, confidence_level)
    if method == AggregationStrategy.BAYESIAN_COMBINATION:
        return _bayesian_combination(envelopes, confidence_level)
    if method == AggregationStrategy.WIDEST or method == "widest":
        return _widest(envelopes, confidence_level)

    raise ValueError(f"Unknown aggregation method: {method}")


# ------------------------------------------------------------------
# Widest (original implementation)
# ------------------------------------------------------------------

def _widest(
    envelopes: Sequence[UncertaintyEnvelope],
    confidence_level: float,
) -> UncertaintyEnvelope:
    point = sum(env.point_estimate for env in envelopes) / len(envelopes)
    lo = min(env.confidence_interval[0] for env in envelopes)
    hi = max(env.confidence_interval[1] for env in envelopes)

    any_heuristic = any(env.is_heuristic_ci for env in envelopes)
    any_non_stat = any(
        env.interval_semantics
        in {IntervalSemantics.DETERMINISTIC_BOUNDS, IntervalSemantics.HEURISTIC_RANGE}
        for env in envelopes
    )

    if any_heuristic:
        semantics = IntervalSemantics.HEURISTIC_RANGE
        level = None
        gate_eligible = False
    elif any_non_stat:
        semantics = IntervalSemantics.DETERMINISTIC_BOUNDS
        level = None
        gate_eligible = all(env.gate_eligible for env in envelopes)
    else:
        semantics = IntervalSemantics.CONFIDENCE_INTERVAL
        level = confidence_level
        gate_eligible = all(env.gate_eligible for env in envelopes)

    point = min(max(point, lo), hi)

    return UncertaintyEnvelope(
        point_estimate=float(point),
        confidence_interval=(float(lo), float(hi)),
        confidence_level=level,
        distribution_family=DistributionFamily.UNKNOWN,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=semantics,
        sample_size=len(envelopes),
        is_heuristic_ci=any_heuristic,
        gate_eligible=gate_eligible,
        metadata={
            "aggregation_method": "widest",
            "n_sources": len(envelopes),
            "sources": [env.source.value for env in envelopes],
        },
    )


# ------------------------------------------------------------------
# Precision-weighted (inverse-variance weighting)
# ------------------------------------------------------------------

def _precision_weighted(
    envelopes: Sequence[UncertaintyEnvelope],
    confidence_level: float,
) -> UncertaintyEnvelope:
    stds = [extract_std(env) for env in envelopes]
    if any(s < 1e-30 for s in stds):
        # Degenerate — fallback to widest
        return _widest(envelopes, confidence_level)

    precisions = [1.0 / (s * s) for s in stds]
    total_precision = sum(precisions)

    point = sum(
        p * float(env.point_estimate) for p, env in zip(precisions, envelopes)
    ) / total_precision
    combined_var = 1.0 / total_precision
    combined_std = math.sqrt(combined_var)

    z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    lo = point - z * combined_std
    hi = point + z * combined_std

    return UncertaintyEnvelope(
        point_estimate=float(point),
        confidence_interval=(float(lo), float(hi)),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        sample_size=len(envelopes),
        is_heuristic_ci=False,
        gate_eligible=all(env.gate_eligible for env in envelopes),
        metadata={
            "aggregation_method": "precision_weighted",
            "n_sources": len(envelopes),
            "combined_std": float(combined_std),
            "sources": [env.source.value for env in envelopes],
        },
    )


# ------------------------------------------------------------------
# Bayesian combination (Gaussian conjugate update)
# ------------------------------------------------------------------

def _bayesian_combination(
    envelopes: Sequence[UncertaintyEnvelope],
    confidence_level: float,
) -> UncertaintyEnvelope:
    stds = [extract_std(env) for env in envelopes]
    if any(s < 1e-30 for s in stds):
        return _widest(envelopes, confidence_level)

    # Sequential Bayesian update: prior = first envelope
    mu = float(envelopes[0].point_estimate)
    var = stds[0] ** 2

    for env, s in zip(envelopes[1:], stds[1:]):
        data_var = s * s
        new_var = 1.0 / (1.0 / var + 1.0 / data_var)
        mu = new_var * (mu / var + float(env.point_estimate) / data_var)
        var = new_var

    combined_std = math.sqrt(var)
    z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    lo = mu - z * combined_std
    hi = mu + z * combined_std

    return UncertaintyEnvelope(
        point_estimate=float(mu),
        confidence_interval=(float(lo), float(hi)),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
        sample_size=len(envelopes),
        is_heuristic_ci=False,
        gate_eligible=all(env.gate_eligible for env in envelopes),
        metadata={
            "aggregation_method": "bayesian_combination",
            "n_sources": len(envelopes),
            "posterior_std": float(combined_std),
            "sources": [env.source.value for env in envelopes],
        },
    )
