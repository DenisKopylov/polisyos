"""Public distributional mobility module API."""
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
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "transition", "cross-section"},
)
class MobilityMatrixEstimator:
    """Estimate transition matrices that summarize movement across income ranks."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="transition_matrix",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "origin_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "destination_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="n_classes", default=5),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Transition probability matrix from paired origin/destination class data.",
        tags=frozenset({"distributional", "mobility", "transition", "cross-section"}),
        when_to_use="Social mobility analysis; estimating probability of moving between income or occupational classes across generations or time",
        output_interpretation="Row i, column j = probability of moving from class i to class j. High diagonal = low mobility.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide origin_classes and destination_classes")
        origin = np.asarray(state["origin_classes"], dtype=int)
        destination = np.asarray(state["destination_classes"], dtype=int)
        if origin.ndim != 1 or destination.ndim != 1:
            raise ValueError("origin_classes and destination_classes must be 1D")
        if origin.shape[0] != destination.shape[0]:
            raise ValueError("origin_classes and destination_classes must have same length")
        if origin.shape[0] == 0:
            raise ValueError("class arrays must not be empty")

        n_classes = int(params.get("n_classes", 5))

        # Build count matrix
        count_matrix = np.zeros((n_classes, n_classes), dtype=float)
        for o, d in zip(origin, destination):
            if 0 <= o < n_classes and 0 <= d < n_classes:
                count_matrix[o, d] += 1.0

        # Normalize rows to get transition probabilities
        row_sums = count_matrix.sum(axis=1, keepdims=True)
        row_sums = np.maximum(row_sums, 1e-12)
        transition_matrix = count_matrix / row_sums

        # Mobility rates
        n_obs = origin.shape[0]
        valid_mask = (origin >= 0) & (origin < n_classes) & (destination >= 0) & (destination < n_classes)
        valid_origin = origin[valid_mask]
        valid_dest = destination[valid_mask]
        n_valid = int(valid_mask.sum())

        if n_valid > 0:
            immobility_rate = float(np.mean(valid_origin == valid_dest))
            upward_mobility_rate = float(np.mean(valid_dest > valid_origin))
            downward_mobility_rate = float(np.mean(valid_dest < valid_origin))
        else:
            immobility_rate = 0.0
            upward_mobility_rate = 0.0
            downward_mobility_rate = 0.0

        return {
            "result": {
                "transition_matrix": transition_matrix.tolist(),
                "upward_mobility_rate": upward_mobility_rate,
                "downward_mobility_rate": downward_mobility_rate,
                "immobility_rate": immobility_rate,
                "n_classes": n_classes,
                "n_obs": n_obs,
            }
        }


@foundry_method(
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "intergenerational", "ige", "cross-section"},
)
class IntergenerationalElasticityEstimator:
    """Estimate parent-child income elasticity for intergenerational mobility audits."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="intergenerational_elasticity",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "parent_values",
                    SlotType.VECTOR,
                    Unit("income", "amount"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "child_values",
                    SlotType.VECTOR,
                    Unit("income", "amount"),
                    shape=("n_obs",),
                ),
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
        description="Intergenerational elasticity (IGE): log-log OLS of child on parent income.",
        tags=frozenset({"distributional", "mobility", "intergenerational", "ige", "cross-section"}),
        when_to_use="Intergenerational income mobility; quantifying persistence of economic status across generations",
        output_interpretation="IGE near 0 = high mobility (child income independent of parent). IGE near 1 = low mobility (strong persistence).",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        if not isinstance(state, Mapping):
            raise TypeError("state must provide parent_values and child_values")
        parent = np.asarray(state["parent_values"], dtype=float)
        child = np.asarray(state["child_values"], dtype=float)
        if parent.ndim != 1 or child.ndim != 1:
            raise ValueError("parent_values and child_values must be 1D")
        if parent.shape[0] != child.shape[0]:
            raise ValueError("parent_values and child_values must have same length")
        if parent.shape[0] < 2:
            raise ValueError("need at least 2 observations")
        if np.any(parent <= 0) or np.any(child <= 0):
            raise ValueError("all values must be positive for log transformation")

        log_parent = np.log(parent)
        log_child = np.log(child)

        # OLS: log(child) = alpha + beta * log(parent)
        n = log_parent.shape[0]
        x_mean = float(np.mean(log_parent))
        y_mean = float(np.mean(log_child))
        x_centered = log_parent - x_mean
        y_centered = log_child - y_mean

        ss_xx = float(np.sum(x_centered ** 2))
        ss_xy = float(np.sum(x_centered * y_centered))
        ss_yy = float(np.sum(y_centered ** 2))

        if ss_xx < 1e-12:
            raise ValueError("parent_values have zero variance")

        beta = ss_xy / ss_xx
        alpha = y_mean - beta * x_mean

        # R-squared
        if ss_yy < 1e-12:
            r_squared = 1.0
        else:
            r_squared = (ss_xy ** 2) / (ss_xx * ss_yy)

        return {
            "result": {
                "ige": float(beta),
                "intercept": float(alpha),
                "r_squared": float(max(0.0, min(1.0, r_squared))),
                "n": n,
            }
        }


__all__ = [
    "IntergenerationalElasticityEstimator",
    "MobilityMatrixEstimator",
]
