from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _vector(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


@foundry_method(
    namespace="survey.weighting",
    version="1.0.0",
    tags={"survey", "weighting", "horvitz-thompson"},
)
class HorvitzThompsonEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="horvitz_thompson",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
                SlotSpec(
                    "inclusion_probabilities",
                    SlotType.VECTOR,
                    Unit("probability", "mass"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Horvitz-Thompson estimator for weighted totals and means.",
        tags=frozenset({"survey", "weighting", "horvitz-thompson"}),
        when_to_use="Estimate population totals/means from complex sample; HT for design-based; GREG for model-assisted",
        output_interpretation="Calibrated estimates with SE. GREG uses auxiliary population totals to improve efficiency vs HT.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        values = _vector(state, "values")
        inclusion = _vector(state, "inclusion_probabilities")
        if values.shape != inclusion.shape:
            raise ValueError("values and inclusion_probabilities must have the same shape")
        if np.any((inclusion <= 0.0) | (inclusion > 1.0)):
            raise ValueError("inclusion_probabilities must lie in (0, 1]")
        weights = 1.0 / inclusion
        total_estimate = float(np.sum(values * weights))
        mean_estimate = float(total_estimate / max(np.sum(weights), 1e-12))
        return {
            "result": {
                "total_estimate": total_estimate,
                "mean_estimate": mean_estimate,
                "weights": weights.tolist(),
            }
        }


@foundry_method(
    namespace="survey.weighting",
    version="1.0.0",
    tags={"survey", "weighting", "raking"},
)
class RakingEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="raking",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("sample_weights", SlotType.VECTOR, Unit("weight", "mass"), shape=("n_obs",)),
                SlotSpec("category_matrix", SlotType.MATRIX, Unit("indicator", "flag"), shape=("n_obs", "n_margins")),
                SlotSpec("target_totals", SlotType.VECTOR, Unit("value", "amount"), shape=("n_margins",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iterations", default=50),
            ParameterSpec(name="tolerance", default=1e-6),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Iterative proportional fitting for binary survey margins.",
        tags=frozenset({"survey", "weighting", "raking"}),
        when_to_use="Adjust survey weights so sample margins match known population totals; correct for non-response",
        output_interpretation="Calibrated weights. Weighted marginal distributions match census/register. Check effective sample size (ESS).",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        weights = _vector(state, "sample_weights").copy()
        category_matrix = np.asarray(state["category_matrix"], dtype=float)
        target_totals = _vector(state, "target_totals")
        if category_matrix.ndim != 2:
            raise ValueError("category_matrix must be 2D")
        if category_matrix.shape[0] != weights.shape[0]:
            raise ValueError("category_matrix rows must match sample_weights length")
        if category_matrix.shape[1] != target_totals.shape[0]:
            raise ValueError("target_totals length must match category_matrix columns")
        max_iterations = max(1, int(params.get("max_iterations", 50)))
        tolerance = max(0.0, float(params.get("tolerance", 1e-6)))

        converged = False
        for _ in range(max_iterations):
            max_gap = 0.0
            for margin_idx in range(category_matrix.shape[1]):
                mask = category_matrix[:, margin_idx] > 0.0
                current_total = float(np.sum(weights[mask]))
                target_total = float(target_totals[margin_idx])
                if not mask.any() or current_total <= 0.0:
                    continue
                factor = target_total / current_total
                weights[mask] *= factor
                max_gap = max(max_gap, abs(target_total - current_total))
            if max_gap <= tolerance:
                converged = True
                break

        achieved_totals = (category_matrix > 0.0).T @ weights
        return {
            "result": {
                "calibrated_weights": weights.tolist(),
                "achieved_totals": achieved_totals.tolist(),
                "target_totals": target_totals.tolist(),
                "converged": converged,
            }
        }


@foundry_method(
    namespace="survey.weighting",
    version="1.0.0",
    tags={"survey", "weighting", "propensity"},
)
class PropensityWeightingEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="propensity",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("propensity_scores", SlotType.VECTOR, Unit("probability", "mass"), shape=("n_obs",)),
                SlotSpec("treatment_indicator", SlotType.VECTOR, Unit("binary", "flag"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="stabilized", default=True),
            ParameterSpec(name="clip_min", default=0.01),
            ParameterSpec(name="clip_max", default=0.99),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Inverse propensity weighting for treatment and control populations.",
        tags=frozenset({"survey", "weighting", "propensity"}),
        when_to_use="Correct for non-random selection using propensity scores; observational study weighting",
        typical_min_obs=100,
        output_interpretation="Inverse probability weights. Check weight distribution (trim extreme weights). Weighted covariate balance.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        propensity = _vector(state, "propensity_scores")
        treatment = _vector(state, "treatment_indicator")
        if propensity.shape != treatment.shape:
            raise ValueError("propensity_scores and treatment_indicator must align")
        clip_min = float(params.get("clip_min", 0.01))
        clip_max = float(params.get("clip_max", 0.99))
        propensity = np.clip(propensity, clip_min, clip_max)
        treated_share = float(np.mean(treatment))
        stabilized = bool(params.get("stabilized", True))
        if stabilized:
            weights = np.where(
                treatment > 0.5,
                treated_share / propensity,
                (1.0 - treated_share) / (1.0 - propensity),
            )
        else:
            weights = np.where(
                treatment > 0.5,
                1.0 / propensity,
                1.0 / (1.0 - propensity),
            )
        return {
            "result": {
                "weights": weights.tolist(),
                "treated_share": treated_share,
                "stabilized": stabilized,
            }
        }


__all__ = [
    "HorvitzThompsonEstimator",
    "PropensityWeightingEstimator",
    "RakingEstimator",
]
