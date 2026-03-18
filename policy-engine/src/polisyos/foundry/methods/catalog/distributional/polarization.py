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
    namespace="distributional.polarization",
    version="1.0.0",
    tags={"distributional", "polarization", "esteban-ray", "cross-section"},
)
class EstebanRayEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="esteban_ray",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="alpha", default=1.5, bounds=(0.0, 2.0)),
            ParameterSpec(name="n_groups", default=5),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Esteban-Ray polarization index for grouped distributions.",
        tags=frozenset({"distributional", "polarization", "esteban-ray", "cross-section"}),
        when_to_use="Measuring societal polarization (income, political); detecting bimodal or multi-polar distributions",
        output_interpretation="Higher polarization value = more polarized distribution. Distinct from inequality: a middle-class society can have low inequality but high polarization.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        alpha = float(params.get("alpha", 1.5))
        n_groups = int(params.get("n_groups", 5))

        sorted_values = np.sort(values)
        n = sorted_values.shape[0]

        # Assign to equal-sized groups (quantile bins)
        group_indices = np.minimum(
            (np.arange(n, dtype=float) * n_groups / n).astype(int),
            n_groups - 1,
        )

        # Compute group means and population shares
        group_means = np.zeros(n_groups, dtype=float)
        group_shares = np.zeros(n_groups, dtype=float)
        for g in range(n_groups):
            mask = group_indices == g
            count = int(np.sum(mask))
            if count > 0:
                group_means[g] = float(np.mean(sorted_values[mask]))
                group_shares[g] = count / n

        # ER polarization: P = K * sum_i sum_j pi_i^(1+alpha) * pi_j * |y_i - y_j|
        polarization = 0.0
        for i in range(n_groups):
            for j in range(n_groups):
                polarization += (
                    group_shares[i] ** (1.0 + alpha)
                    * group_shares[j]
                    * abs(group_means[i] - group_means[j])
                )

        return {
            "result": {
                "polarization": float(polarization),
                "alpha": alpha,
                "n_groups": n_groups,
                "group_means": group_means.tolist(),
                "group_shares": group_shares.tolist(),
                "n": n,
            }
        }


@foundry_method(
    namespace="distributional.polarization",
    version="1.0.0",
    tags={"distributional", "polarization", "duclos-esteban-ray", "cross-section"},
)
class DuclosEstebanRayEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="duclos_esteban_ray",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="alpha", default=0.5, bounds=(0.25, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Duclos-Esteban-Ray polarization for continuous distributions using kernel density.",
        tags=frozenset({"distributional", "polarization", "duclos-esteban-ray", "cross-section"}),
        when_to_use="Continuous-distribution polarization measurement; when discrete groupings are inappropriate",
        output_interpretation="Higher polarization value = more polarized continuous distribution. Sensitive to bimodality and clusters at extreme values.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        alpha = float(params.get("alpha", 0.5))

        sorted_values = np.sort(values)
        n = sorted_values.shape[0]

        # Silverman bandwidth
        std = float(np.std(sorted_values, ddof=1)) if n > 1 else 1.0
        iqr = float(np.percentile(sorted_values, 75) - np.percentile(sorted_values, 25))
        bandwidth = 0.9 * min(std, iqr / 1.34) * n ** (-0.2) if iqr > 0.0 else 0.9 * max(std, 1e-6) * n ** (-0.2)
        bandwidth = max(bandwidth, 1e-12)

        # Kernel density estimation at each observation point (Gaussian kernel)
        # f(x_i) = (1/n*h) * sum_j K((x_i - x_j) / h)
        diffs = sorted_values[:, None] - sorted_values[None, :]  # (n, n)
        kernel_vals = np.exp(-0.5 * (diffs / bandwidth) ** 2) / (bandwidth * np.sqrt(2.0 * np.pi))
        density = np.mean(kernel_vals, axis=1)  # (n,)

        # DER: P(alpha) = integral f(y)^alpha * a(y) * f(y) dy
        # where a(y) = integral |y - x| f(x) dx
        # Approximate with sample averages:
        # a(y_i) = (1/n) * sum_j |y_i - y_j|
        abs_diffs = np.abs(diffs)
        alienation = np.mean(abs_diffs, axis=1)  # (n,)

        # P = (1/n) * sum_i f(y_i)^alpha * alienation(y_i)
        polarization = float(np.mean(density ** alpha * alienation))

        return {
            "result": {
                "polarization": polarization,
                "alpha": alpha,
                "bandwidth": bandwidth,
                "mean_density": float(np.mean(density)),
                "mean_alienation": float(np.mean(alienation)),
                "n": n,
            }
        }


__all__ = [
    "DuclosEstebanRayEstimator",
    "EstebanRayEstimator",
]
