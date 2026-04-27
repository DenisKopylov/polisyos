"""Pure-Python exact KernelSHAP-style adapter for small tabular feature sets."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations

from polisyos.berl.adapters._utils import background_rows_from_context, int_param
from polisyos.berl.adapters.protocol import (
    AssumptionReport,
    ExplanationContext,
    RawExplanation,
    ScalarModel,
    UncertaintyReport,
)
from polisyos.berl.metrics.infidelity import additive_reconstruct_delta


@dataclass(frozen=True, slots=True)
class KernelSHAPAdapter:
    """Exact Shapley adapter over an empirical interventional background."""

    method_id: str = "kernel_shap"
    max_exact_features: int = 10

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        feature_names = context.feature_names
        max_features = int_param(context, "max_exact_shap_features", self.max_exact_features)
        if len(feature_names) > max_features:
            raise ValueError(
                "exact KernelSHAP is exponential; reduce features or set max_exact_shap_features"
            )
        background_rows = background_rows_from_context(context, x)
        values_cache: dict[frozenset[str], float] = {}

        def value(coalition: frozenset[str]) -> float:
            if coalition in values_cache:
                return values_cache[coalition]
            outputs: list[float] = []
            for background in background_rows:
                row = dict(background)
                for feature in coalition:
                    row[feature] = float(x.get(feature, 0.0))
                outputs.append(float(model(row)))
            result = sum(outputs) / len(outputs)
            values_cache[coalition] = result
            return result

        feature_count = len(feature_names)
        factorial_n = math.factorial(feature_count)
        baseline_values = {
            feature: sum(row[feature] for row in background_rows) / len(background_rows)
            for feature in feature_names
        }
        explained_values = {feature: float(x.get(feature, 0.0)) for feature in feature_names}
        attributions: dict[str, float] = {}
        for feature in feature_names:
            others = tuple(candidate for candidate in feature_names if candidate != feature)
            total = 0.0
            for size in range(feature_count):
                weight = (
                    math.factorial(size)
                    * math.factorial(feature_count - size - 1)
                    / factorial_n
                )
                for subset in combinations(others, size):
                    coalition = frozenset(subset)
                    total += weight * (
                        value(coalition | {feature}) - value(coalition)
                    )
            attributions[feature] = total

        return RawExplanation(
            method_id=self.method_id,
            attributions=attributions,
            params={
                "background_n": len(background_rows),
                "baseline_values": baseline_values,
                "explained_values": explained_values,
                "feature_removal": context.feature_dependence_policy,
                "exact_enumeration": True,
            },
            assumptions={
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
        baseline_values = _float_mapping_param(explanation.params.get("baseline_values"))
        explained_values = _float_mapping_param(explanation.params.get("explained_values"))
        if not baseline_values or not explained_values:
            return additive_reconstruct_delta(explanation.attributions, perturbation)
        total = 0.0
        for feature, contribution in explanation.attributions.items():
            denominator = explained_values.get(feature, 0.0) - baseline_values.get(feature, 0.0)
            delta = float(perturbation.get(feature, 0.0))
            if abs(denominator) < 1.0e-12:
                fraction_removed = 1.0 if abs(delta) > 0.0 else 0.0
            else:
                fraction_removed = delta / denominator
            total += contribution * fraction_removed
        return total

    def estimator_uncertainty(self, explanation: RawExplanation) -> UncertaintyReport:
        del explanation
        return UncertaintyReport(diagnostic="exact_empirical_enumeration_no_estimator_interval")

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy=context.feature_dependence_policy,
            causal_claim_made=False,
            notes=("exact Shapley enumeration over empirical background rows",),
        )


def _float_mapping_param(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): float(raw_value) for key, raw_value in value.items()}
