"""Public sensitivity specification module API."""
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


@foundry_method(
    namespace="sensitivity.specification",
    version="1.0.0",
    tags={"sensitivity", "specification", "multiverse", "robustness", "tabular"},
)
class SpecificationCurveEstimator:
    """Specification curve estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="specification_curve",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("estimates", SlotType.VECTOR, Unit("effect", "value"), shape=("n_specs",)),
                SlotSpec("standard_errors", SlotType.VECTOR, Unit("se", "value"), shape=("n_specs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="significance_level", default=0.05, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Specification curve analysis: summarize estimate distribution across specifications.",
        tags=frozenset({"sensitivity", "specification", "multiverse", "robustness", "tabular"}),
        citations=(
            "Simonsohn, U., Simmons, J.P. & Nelson, L.D. (2020). Specification curve analysis. Nature Human Behaviour.",
        ),
        equations={"curve": "Sort estimates; report median, IQR, share significant, sign consistency"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Assess robustness of regression result across researcher specification choices (controls, samples, functional forms)",
        output_interpretation="Distribution of estimates across specifications. Robust if majority of specs yield same-sign significant result.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            from polisyos.ir.observation.contract_compilers import SpecificationCurveInput

            if isinstance(state, SpecificationCurveInput):
                state = state.model_dump(mode="python")
            else:
                raise TypeError("state must be a mapping or SpecificationCurveInput")
        estimates = np.asarray(state["estimates"], dtype=float)
        se = np.asarray(state["standard_errors"], dtype=float)
        if estimates.shape != se.shape or estimates.ndim != 1:
            raise ValueError("estimates and standard_errors must be 1D with same length")

        alpha = float(params.get("significance_level", 0.05))
        z_crit = 1.96 if abs(alpha - 0.05) < 1e-6 else float(-np.log(alpha / 2))  # rough approximation

        n_specs = len(estimates)
        sorted_idx = np.argsort(estimates)
        sorted_est = estimates[sorted_idx]

        # Significance
        t_stats = np.abs(estimates / np.maximum(se, 1e-12))
        is_significant = t_stats > z_crit
        share_significant = float(np.mean(is_significant))

        # Sign consistency
        n_positive = int(np.sum(estimates > 0))
        n_negative = int(np.sum(estimates < 0))
        sign_consistency = max(n_positive, n_negative) / max(n_specs, 1)

        # Confidence intervals
        ci_lower = estimates - z_crit * se
        ci_upper = estimates + z_crit * se

        return {
            "result": {
                "median_estimate": float(np.median(estimates)),
                "mean_estimate": float(np.mean(estimates)),
                "std_estimate": float(np.std(estimates, ddof=1)) if n_specs > 1 else 0.0,
                "min_estimate": float(np.min(estimates)),
                "max_estimate": float(np.max(estimates)),
                "iqr": float(np.percentile(estimates, 75) - np.percentile(estimates, 25)),
                "share_significant": share_significant,
                "share_positive": float(n_positive / max(n_specs, 1)),
                "sign_consistency": float(sign_consistency),
                "n_specifications": n_specs,
                "sorted_estimates": sorted_est.tolist(),
            }
        }


__all__ = ["SpecificationCurveEstimator"]
