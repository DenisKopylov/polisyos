"""Public validation scoring module API."""
from __future__ import annotations

import math
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
    namespace="validation.probabilistic",
    version="1.0.0",
    tags={"validation", "probabilistic", "scoring", "tabular"},
)
class ProbabilisticScoringEstimator:
    """Score predictive distributions with probabilistic forecast metrics."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="normal_scores",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("observations", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
                SlotSpec("predictive_mean", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
                SlotSpec("predictive_std", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
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
        description="Average log score and CRPS for Gaussian predictive distributions.",
        tags=frozenset({"validation", "probabilistic", "scoring", "tabular"}),
        when_to_use="Evaluate probabilistic forecasts with Gaussian predictive distributions; assess sharpness and calibration jointly",
        output_interpretation="Mean log score (lower = better fit). Mean CRPS (lower = better; proper scoring rule combining calibration and sharpness).",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        observed = np.asarray(state["observations"], dtype=float)
        mean = np.asarray(state["predictive_mean"], dtype=float)
        std = np.maximum(np.asarray(state["predictive_std"], dtype=float), 1e-8)
        if observed.shape != mean.shape or observed.shape != std.shape:
            raise ValueError("observations, predictive_mean, and predictive_std must align")
        z = (observed - mean) / std
        log_scores = 0.5 * np.log(2.0 * np.pi * (std ** 2)) + 0.5 * (z ** 2)
        pdf = np.exp(-0.5 * z ** 2) / math.sqrt(2.0 * np.pi)
        cdf = 0.5 * (1.0 + np.vectorize(math.erf)(z / math.sqrt(2.0)))
        crps = std * (z * (2.0 * cdf - 1.0) + 2.0 * pdf - 1.0 / math.sqrt(np.pi))
        return {
            "result": {
                "mean_log_score": float(np.mean(log_scores)),
                "mean_crps": float(np.mean(crps)),
            }
        }


__all__ = ["ProbabilisticScoringEstimator"]
