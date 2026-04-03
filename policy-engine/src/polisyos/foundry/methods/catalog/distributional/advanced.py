"""Public distributional advanced module API."""
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
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
            )
        }
    )


def _values_payload(state: Any, *, key: str = "values") -> np.ndarray:
    if isinstance(state, Mapping):
        values = state.get(key)
    else:
        values = state
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if arr.size == 0:
        raise ValueError(f"{key} must not be empty")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


@foundry_method(
    namespace="distributional.inequality",
    version="1.0.0",
    tags={"distributional", "inequality", "theil", "cross-section"},
)
class TheilIndexEstimator:
    """Theil index estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="theil",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Theil T index of inequality.",
        tags=frozenset({"distributional", "inequality", "theil", "cross-section"}),
        when_to_use="Decomposable inequality measure; between-group vs within-group decomposition",
        output_interpretation="Theil T: decomposable into within-group and between-group components. 0=equality.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("theil requires non-negative values")
        shifted = np.maximum(values, 1e-12)
        mean_value = float(np.mean(shifted))
        n = shifted.shape[0]
        ratio = shifted / mean_value
        theil_t = float(np.sum(ratio * np.log(ratio)) / n)
        return {
            "result": {
                "theil_index": theil_t,
                "mean": mean_value,
                "n": n,
            }
        }


@foundry_method(
    namespace="distributional.inequality",
    version="1.0.0",
    tags={"distributional", "inequality", "palma", "cross-section"},
)
class PalmaRatioEstimator:
    """Palma ratio estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="palma_ratio",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Palma ratio: income share of top 10% divided by bottom 40%.",
        tags=frozenset({"distributional", "inequality", "palma", "cross-section"}),
        when_to_use="Inequality focused on top-10%/bottom-40% comparison; robust to middle-income changes",
        output_interpretation="Top 10% share / bottom 40% share. Palma=1 means they have equal shares. Higher = more unequal.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("palma_ratio requires non-negative values")
        sorted_values = np.sort(values)
        n = sorted_values.shape[0]
        bottom_40_cutoff = int(np.ceil(n * 0.4))
        top_10_cutoff = int(np.floor(n * 0.9))
        bottom_40_sum = float(np.sum(sorted_values[:bottom_40_cutoff]))
        top_10_sum = float(np.sum(sorted_values[top_10_cutoff:]))
        if bottom_40_sum <= 0.0:
            palma = float("inf")
        else:
            palma = top_10_sum / bottom_40_sum
        return {
            "result": {
                "palma_ratio": palma,
                "top_10_share": top_10_sum / max(float(np.sum(sorted_values)), 1e-12),
                "bottom_40_share": bottom_40_sum / max(float(np.sum(sorted_values)), 1e-12),
                "n": n,
            }
        }


@foundry_method(
    namespace="distributional.inequality",
    version="1.0.0",
    tags={"distributional", "inequality", "generalized-gini", "cross-section"},
)
class GeneralizedGiniEstimator:
    """Generalized gini estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="generalized_gini",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="nu", default=2.0, bounds=(1.0, 10.0)),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Generalized Gini coefficient with inequality aversion parameter nu.",
        tags=frozenset({"distributional", "inequality", "generalized-gini", "cross-section"}),
        when_to_use="Income/wealth inequality measurement; welfare analysis; distributional impact of policy",
        output_interpretation="Gini=0 perfect equality, Gini=1 maximum inequality. Policy reduces inequality if post-policy Gini < baseline.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("generalized_gini requires non-negative values")
        nu = float(params.get("nu", 2.0))
        sorted_values = np.sort(values)
        n = sorted_values.shape[0]
        total = float(np.sum(sorted_values))
        if total <= 0.0:
            return {"result": {"generalized_gini": 0.0, "nu": nu, "n": n}}
        # G(nu) = 1 - (N^nu / sum((N - i + 0.5)^(nu-1) * x_i)) / (N * sum(x_i))
        # where i is 1-based rank in ascending order
        ranks = np.arange(1, n + 1, dtype=float)
        weights = (n - ranks + 0.5) ** (nu - 1.0)
        weighted_sum = float(np.sum(weights * sorted_values))
        normalizer = float(np.sum(weights))
        gg = 1.0 - (normalizer * total) / (n * total) if normalizer <= 0.0 else 1.0 - weighted_sum / (total * normalizer / n)
        # Simplified: G(nu) = 1 - (n^nu * sum(w_i * x_i)) / (n * total * sum(w_i))
        # but cleaner: use the weight-based formula directly
        gg = 1.0 - (n * weighted_sum) / (total * normalizer) if normalizer > 0.0 else 0.0
        return {
            "result": {
                "generalized_gini": float(max(0.0, min(1.0, gg))),
                "nu": nu,
                "n": n,
            }
        }


__all__ = [
    "GeneralizedGiniEstimator",
    "PalmaRatioEstimator",
    "TheilIndexEstimator",
]
