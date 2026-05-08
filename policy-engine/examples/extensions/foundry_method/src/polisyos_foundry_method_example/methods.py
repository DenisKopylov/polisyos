"""Example method exposed through `polisyos.foundry_methods`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from polisyos.foundry.extensions import component_for_method
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodKind,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_UNIT = Unit("dimensionless", "1")


class WeightedAverageMethod:
    """Compute a deterministic weighted average from vector inputs."""

    signature = MethodSignature(
        name="weighted_average",
        namespace="example.summary",
        version="1.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, _UNIT, shape=("n",)),
                SlotSpec("weights", SlotType.VECTOR, _UNIT, shape=("n",)),
            }
        ),
        output_slots=frozenset({SlotSpec("mean", SlotType.SCALAR, _UNIT)}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        kind=MethodKind.PURE,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata = MethodMetadata(
        description="Deterministic weighted-average example method.",
        tags=frozenset({"example", "summary", "tabular", "estimation"}),
        when_to_use=(
            "Use for deterministic tabular summaries when values and non-zero weights are "
            "already aligned one-to-one."
        ),
        output_interpretation=(
            "mean is the weighted arithmetic average, so larger weights increase the "
            "contribution of their paired values."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, float]:
        del params
        values = np.asarray(state["values"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        denominator = float(weights.sum())
        if denominator == 0.0:
            raise ValueError("weights must sum to a non-zero value")
        return {"mean": float(np.dot(values, weights) / denominator)}


weighted_average_plugin = component_for_method(
    WeightedAverageMethod,
    domains=["example"],
    tags={"external-example"},
)

__all__ = ["WeightedAverageMethod", "weighted_average_plugin"]
