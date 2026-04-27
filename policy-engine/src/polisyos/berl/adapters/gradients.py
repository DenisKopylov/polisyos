"""Gradient-style local explanation adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.berl.adapters.protocol import (
    AssumptionReport,
    ExplanationContext,
    RawExplanation,
    ScalarModel,
    UncertaintyReport,
)
from polisyos.berl.metrics.infidelity import additive_reconstruct_delta

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class FiniteDifferenceGradientAdapter:
    """Finite-difference local linear adapter for scalar black-box functions."""

    epsilon: float = 1.0e-5
    method_id: str = "finite_difference_gradient"

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        if self.epsilon <= 0.0:
            raise ValueError("epsilon must be positive")
        attributions: dict[str, float] = {}
        for feature in context.feature_names:
            center = float(x.get(feature, 0.0))
            forward = dict(x)
            backward = dict(x)
            forward[feature] = center + self.epsilon
            backward[feature] = center - self.epsilon
            attributions[feature] = (float(model(forward)) - float(model(backward))) / (
                2.0 * self.epsilon
            )
        return RawExplanation(
            method_id=self.method_id,
            attributions=attributions,
            params={"epsilon": self.epsilon},
            assumptions={
                "model_class": "locally_smooth_scalar_model",
                "output_scale": context.output_scale,
                "perturbation_distribution": context.perturbation_distribution,
                "feature_dependence_policy": context.feature_dependence_policy,
                "causal_claim_made": False,
            },
        )

    def reconstruct_delta(
        self,
        explanation: RawExplanation,
        perturbation: Mapping[str, float],
    ) -> float:
        return additive_reconstruct_delta(explanation.attributions, perturbation)

    def estimator_uncertainty(self, explanation: RawExplanation) -> UncertaintyReport:
        del explanation
        return UncertaintyReport(diagnostic="finite_difference_no_estimator_interval")

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy=context.feature_dependence_policy,
            causal_claim_made=False,
            notes=("local linearization of a scalar model",),
        )
