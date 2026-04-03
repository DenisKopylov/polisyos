"""Public distributional poverty advanced module API."""
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


@foundry_method(
    namespace="distributional.poverty",
    version="1.0.0",
    tags={"distributional", "poverty", "multidimensional", "alkire-foster", "cross-section"},
)
class MultidimensionalPovertyEstimator:
    """Multidimensional poverty estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="multidimensional",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "deprivation_matrix",
                    SlotType.MATRIX,
                    Unit("deprivation", "binary"),
                    shape=("n_agents", "n_dimensions"),
                ),
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("weight", "proportion"),
                    shape=("n_dimensions",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="k_threshold", default=0.33, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Alkire-Foster multidimensional poverty index (MPI): H * A = M0.",
        tags=frozenset({"distributional", "poverty", "multidimensional", "alkire-foster", "cross-section"}),
        when_to_use="Multidimensional poverty measurement across health, education, living standards; UNDP MPI-style analysis",
        output_interpretation="M0 = H * A: headcount ratio times average intensity. Higher = more multidimensional poverty. Policy improves if post-policy M0 decreases.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide deprivation_matrix and weights")
        deprivation_matrix = np.asarray(state["deprivation_matrix"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        if deprivation_matrix.ndim != 2:
            raise ValueError("deprivation_matrix must be 2D (n_agents x n_dimensions)")
        if weights.ndim != 1:
            raise ValueError("weights must be a 1D vector")
        n_agents, n_dims = deprivation_matrix.shape
        if weights.shape[0] != n_dims:
            raise ValueError("weights length must match number of dimensions")
        if n_agents == 0:
            raise ValueError("deprivation_matrix must not be empty")

        k_threshold = float(params.get("k_threshold", 0.33))

        # Normalize weights to sum to 1
        weight_sum = float(np.sum(weights))
        if weight_sum <= 0.0:
            raise ValueError("weights must sum to a positive value")
        w = weights / weight_sum

        # Weighted deprivation score per agent
        deprivation_scores = deprivation_matrix @ w  # shape: (n_agents,)

        # Identify poor: those whose weighted deprivation score >= k
        is_poor = deprivation_scores >= k_threshold

        # Headcount ratio H
        headcount = float(np.mean(is_poor))

        # Intensity A: average deprivation score among the poor
        if np.any(is_poor):
            intensity = float(np.mean(deprivation_scores[is_poor]))
        else:
            intensity = 0.0

        # Adjusted headcount M0 = H * A
        m0 = headcount * intensity

        return {
            "result": {
                "m0": m0,
                "headcount_ratio": headcount,
                "intensity": intensity,
                "k_threshold": k_threshold,
                "n_agents": n_agents,
                "n_dimensions": n_dims,
                "n_poor": int(np.sum(is_poor)),
            }
        }


__all__ = [
    "MultidimensionalPovertyEstimator",
]
