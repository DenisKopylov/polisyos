"""LIME-style local surrogate adapter with held-out BERL validation support."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from polisyos.berl.adapters._linear import fit_weighted_ridge
from polisyos.berl.adapters._utils import DeterministicUniform, float_param, int_param
from polisyos.berl.adapters.protocol import (
    AssumptionReport,
    ExplanationContext,
    RawExplanation,
    ScalarModel,
    UncertaintyReport,
)
from polisyos.berl.metrics.infidelity import additive_reconstruct_delta


@dataclass(frozen=True, slots=True)
class LIMEAdapter:
    """Fit a local weighted linear reconstruction model around one row."""

    method_id: str = "lime"
    default_sample_count: int = 256
    default_kernel_width: float = 1.0
    default_radius: float = 0.25
    default_ridge_alpha: float = 1.0e-6

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        sample_count = int_param(context, "lime_sample_count", self.default_sample_count)
        kernel_width = float_param(context, "lime_kernel_width", self.default_kernel_width)
        radius = float_param(context, "lime_radius", self.default_radius)
        ridge_alpha = float_param(context, "lime_ridge_alpha", self.default_ridge_alpha)
        if sample_count <= 0:
            raise ValueError("lime_sample_count must be positive")
        if kernel_width <= 0.0:
            raise ValueError("lime_kernel_width must be positive")
        if radius <= 0.0:
            raise ValueError("lime_radius must be positive")

        rng = DeterministicUniform(context.random_seed)
        original_output = float(model(x))
        rows: list[dict[str, float]] = []
        targets: list[float] = []
        weights: list[float] = []
        for _ in range(sample_count):
            perturbed = dict(x)
            delta_row: dict[str, float] = {}
            squared_norm = 0.0
            for feature in context.feature_names:
                delta = rng.uniform(-radius, radius)
                perturbed[feature] = float(x.get(feature, 0.0)) + delta
                representation_delta = -delta
                delta_row[feature] = representation_delta
                squared_norm += representation_delta * representation_delta
            rows.append(delta_row)
            targets.append(original_output - float(model(perturbed)))
            weights.append(math.exp(-squared_norm / (kernel_width * kernel_width)))

        attributions, standard_errors = fit_weighted_ridge(
            feature_names=context.feature_names,
            rows=rows,
            targets=targets,
            weights=weights,
            alpha=ridge_alpha,
        )
        intervals = {
            feature: (
                value - 1.96 * standard_errors[feature],
                value + 1.96 * standard_errors[feature],
            )
            for feature, value in attributions.items()
        }
        return RawExplanation(
            method_id=self.method_id,
            attributions=attributions,
            params={
                "kernel_width": kernel_width,
                "sample_count": sample_count,
                "radius": radius,
                "ridge_alpha": ridge_alpha,
                "sampling_distribution": "uniform_numeric_ball",
                "seed": context.random_seed,
            },
            assumptions={
                "output_scale": context.output_scale,
                "perturbation_distribution": context.perturbation_distribution,
                "feature_dependence_policy": context.feature_dependence_policy,
                "causal_claim_made": False,
            },
            estimator_uncertainty=UncertaintyReport(
                standard_errors=standard_errors,
                confidence_intervals=intervals,
                diagnostic="weighted_ridge_local_surrogate",
            ).as_payload(),
        )

    def reconstruct_delta(
        self,
        explanation: RawExplanation,
        perturbation: Mapping[str, float],
    ) -> float:
        return additive_reconstruct_delta(explanation.attributions, perturbation)

    def estimator_uncertainty(self, explanation: RawExplanation) -> UncertaintyReport:
        se_payload = explanation.estimator_uncertainty.get("standard_errors", {})
        ci_payload = explanation.estimator_uncertainty.get("confidence_intervals", {})
        standard_errors = {
            str(feature): float(value)
            for feature, value in se_payload.items()
        } if isinstance(se_payload, Mapping) else {}
        intervals: dict[str, tuple[float, float]] = {}
        if isinstance(ci_payload, Mapping):
            for feature, raw_interval in ci_payload.items():
                if isinstance(raw_interval, (list, tuple)) and len(raw_interval) == 2:
                    intervals[str(feature)] = (float(raw_interval[0]), float(raw_interval[1]))
        return UncertaintyReport(
            standard_errors=standard_errors,
            confidence_intervals=intervals,
            diagnostic="weighted_ridge_local_surrogate",
        )

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy=context.feature_dependence_policy,
            causal_claim_made=False,
            notes=("perturbation-dependent weighted local surrogate",),
        )
