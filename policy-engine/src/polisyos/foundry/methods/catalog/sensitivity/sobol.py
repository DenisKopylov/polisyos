"""Public sensitivity sobol module API."""
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
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="sensitivity.global",
    version="1.0.0",
    tags={"sensitivity", "global", "sobol", "tabular"},
)
class SobolFirstOrderEstimator:
    """Sobol first order estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sobol_first_order",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outputs_a", SlotType.VECTOR, Unit("response", "value"), shape=("n_samples",)),
                SlotSpec("outputs_b", SlotType.VECTOR, Unit("response", "value"), shape=("n_samples",)),
                SlotSpec("mixed_outputs", SlotType.MATRIX, Unit("response", "value"), shape=("n_features", "n_samples")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="First-order Sobol sensitivity indices using Jansen's estimator.",
        tags=frozenset({"sensitivity", "global", "sobol", "tabular"}),
        when_to_use="Global sensitivity analysis for simulation/model; quantify how much each parameter drives output variance",
        when_not_to_use="Linear model (use linear SA); fewer than 100 model evaluations possible; correlated inputs (use HDMR)",
        typical_min_obs=None,
        output_interpretation="S1: first-order Sobol index (main effect). ST: total effect index (includes interactions). Sum of S1 ≤ 1.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        outputs_a = np.asarray(state["outputs_a"], dtype=float)
        outputs_b = np.asarray(state["outputs_b"], dtype=float)
        mixed_outputs = np.asarray(state["mixed_outputs"], dtype=float)
        if outputs_a.ndim != 1 or outputs_b.ndim != 1 or mixed_outputs.ndim != 2:
            raise ValueError("outputs_a/outputs_b must be 1D and mixed_outputs must be 2D")
        if outputs_a.shape != outputs_b.shape:
            raise ValueError("outputs_a and outputs_b must align")
        if mixed_outputs.shape[1] != outputs_a.shape[0]:
            raise ValueError("mixed_outputs second dimension must match sample length")
        variance = float(np.var(np.concatenate([outputs_a, outputs_b]), ddof=1))
        if variance <= 0.0:
            raise ValueError("variance must be positive for Sobol indices")
        first_order = 1.0 - np.mean((outputs_b[None, :] - mixed_outputs) ** 2, axis=1) / (2.0 * variance)
        return {
            "result": {
                "first_order_indices": np.clip(first_order, 0.0, 1.0).tolist(),
                "variance": variance,
            }
        }


__all__ = ["SobolFirstOrderEstimator"]
