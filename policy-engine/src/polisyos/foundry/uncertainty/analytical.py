"""Public uncertainty analytical module API."""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Mapping

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .covariance import extract_std
from .protocol import PropagationResult


class AnalyticalPropagator:
    """Analytical propagator public type."""
    @property
    def method(self) -> PropagationMethod:
        return PropagationMethod.ANALYTICAL

    @staticmethod
    def is_applicable(input_envelopes: Mapping[str, UncertaintyEnvelope]) -> bool:
        return all(
            env.distribution_family == DistributionFamily.NORMAL
            for env in input_envelopes.values()
        )

    @staticmethod
    def propagate_linear_combination(
        *,
        weights: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_id: str,
        confidence_level: float = 0.95,
    ) -> PropagationResult:
        mean = 0.0
        variance = 0.0
        names: list[str] = []
        for name, weight in weights.items():
            env = input_envelopes[name]
            std = extract_std(env)
            mean += float(weight) * float(env.point_estimate)
            variance += (float(weight) ** 2) * (std**2)
            names.append(name)

        std_out = math.sqrt(max(variance, 0.0))
        z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
        lo = mean - z * std_out
        hi = mean + z * std_out

        envelope = UncertaintyEnvelope(
            point_estimate=float(mean),
            confidence_interval=(float(lo), float(hi)),
            confidence_level=confidence_level,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.ANALYTICAL,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "formula": "linear_combination_normal",
                "weights": dict(weights),
                "output_std": float(std_out),
            },
        )

        return PropagationResult(
            metric_id=output_metric_id,
            envelope=envelope,
            input_envelopes_used=names,
            method_used=PropagationMethod.ANALYTICAL,
            diagnostics={"output_variance": float(variance), "output_std": float(std_out)},
        )
