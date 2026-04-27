"""Permutation-importance adapter for global comparison evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.berl.adapters._utils import background_rows_from_context
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
class PermutationImportanceAdapter:
    """Deterministic leave-column-shift importance over background rows."""

    method_id: str = "permutation_importance"

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        del x
        rows = background_rows_from_context(context, {})
        baseline = [float(model(row)) for row in rows]
        attributions: dict[str, float] = {}
        for feature in context.feature_names:
            shifted_outputs: list[float] = []
            for index, row in enumerate(rows):
                shifted = dict(row)
                shifted[feature] = rows[(index + 1) % len(rows)][feature]
                shifted_outputs.append(float(model(shifted)))
            attributions[feature] = sum(
                abs(left - right)
                for left, right in zip(baseline, shifted_outputs, strict=True)
            ) / len(rows)
        return RawExplanation(
            method_id=self.method_id,
            attributions=attributions,
            params={"background_n": len(rows), "permutation": "deterministic_one_step_shift"},
            assumptions={
                "scope": "global_comparison_evidence",
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
        return UncertaintyReport(diagnostic="deterministic_permutation_no_estimator_interval")

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy=context.feature_dependence_policy,
            causal_claim_made=False,
            notes=("global comparison evidence, not a direct local explanation",),
        )
