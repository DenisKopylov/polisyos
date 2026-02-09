from __future__ import annotations

from typing import Sequence

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def aggregate_envelopes(
    envelopes: Sequence[UncertaintyEnvelope],
    *,
    method: str = "widest",
    confidence_level: float = 0.95,
) -> UncertaintyEnvelope:
    if not envelopes:
        raise ValueError("Cannot aggregate empty envelope list")
    if len(envelopes) == 1:
        return envelopes[0]

    if method != "widest":
        raise ValueError(f"Unknown aggregation method: {method}")

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
            "aggregation_method": method,
            "n_sources": len(envelopes),
            "sources": [env.source.value for env in envelopes],
        },
    )
