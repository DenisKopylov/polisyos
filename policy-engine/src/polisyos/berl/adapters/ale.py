"""Accumulated-local-effects local-bin adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.berl.adapters._utils import background_rows_from_context, int_param
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
class ALEAdapter:
    """Estimate local-bin finite-difference effects over empirical background rows."""

    method_id: str = "ale_local_bin"
    default_bin_count: int = 10

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        background_rows = background_rows_from_context(context, x)
        bin_count = int_param(context, "ale_bin_count", self.default_bin_count)
        if bin_count <= 1:
            raise ValueError("ale_bin_count must be greater than 1")
        attributions: dict[str, float] = {}
        params: dict[str, object] = {"bin_count": bin_count, "background_n": len(background_rows)}
        for feature in context.feature_names:
            values = sorted(row[feature] for row in background_rows)
            lower, upper = _local_bin(values, float(x.get(feature, 0.0)), bin_count=bin_count)
            width = upper - lower
            if width == 0.0:
                attributions[feature] = 0.0
                params[f"{feature}_bin"] = [lower, upper]
                continue
            eligible = [row for row in background_rows if lower <= row[feature] <= upper]
            if not eligible:
                eligible = list(background_rows)
            finite_differences: list[float] = []
            for row in eligible:
                lower_row = dict(row)
                upper_row = dict(row)
                lower_row[feature] = lower
                upper_row[feature] = upper
                finite_differences.append(float(model(upper_row)) - float(model(lower_row)))
            attributions[feature] = (sum(finite_differences) / len(finite_differences)) / width
            params[f"{feature}_bin"] = [lower, upper]

        return RawExplanation(
            method_id=self.method_id,
            attributions=attributions,
            params=params,
            assumptions={
                "output_scale": context.output_scale,
                "perturbation_distribution": context.perturbation_distribution,
                "feature_dependence_policy": context.feature_dependence_policy,
                "causal_claim_made": False,
                "scope": "local_bin_effect_evidence",
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
        return UncertaintyReport(diagnostic="ale_finite_difference_no_estimator_interval")

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy=context.feature_dependence_policy,
            causal_claim_made=False,
            notes=("local-bin ALE evidence; not a causal individual explanation",),
        )


def _local_bin(values: list[float], x_value: float, *, bin_count: int) -> tuple[float, float]:
    if not values:
        return (x_value, x_value)
    if len(values) == 1:
        return (values[0], values[0])
    sorted_values = values
    index = min(
        range(len(sorted_values)),
        key=lambda position: abs(sorted_values[position] - x_value),
    )
    raw_width = max(1, len(sorted_values) // bin_count)
    lower_index = max(0, index - raw_width // 2)
    upper_index = min(len(sorted_values) - 1, lower_index + raw_width)
    if lower_index == upper_index and upper_index < len(sorted_values) - 1:
        upper_index += 1
    return sorted_values[lower_index], sorted_values[upper_index]
