"""Adapter for additive/component models such as GAMs and EBMs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

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


@runtime_checkable
class ComponentModel(Protocol):
    """Protocol for models that can expose exact component contributions."""

    def component_deltas(self, features: Mapping[str, float]) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class EBMComponentAdapter:
    """Return exact component deltas when the model exposes them."""

    method_id: str = "ebm_components"

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        if not isinstance(model, ComponentModel):
            raise TypeError("EBMComponentAdapter requires model.component_deltas(features)")
        components = {
            feature: float(model.component_deltas(x).get(feature, 0.0))
            for feature in context.feature_names
        }
        return RawExplanation(
            method_id=self.method_id,
            attributions=components,
            params={"component_source": "model.component_deltas"},
            assumptions={
                "model_class": "additive_component_model",
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
        return UncertaintyReport(diagnostic="exact_component_deltas")

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy=context.feature_dependence_policy,
            causal_claim_made=False,
            notes=("exact additive component deltas when supplied by model",),
        )
