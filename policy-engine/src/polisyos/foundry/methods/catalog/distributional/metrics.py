"""Public distributional metrics module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.analysis.distributional import compute_gini
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


def _distributional_output_slot() -> frozenset[SlotSpec]:
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
    namespace="distributional.inequality",
    version="1.0.0",
    tags={"distributional", "inequality", "lorenz", "cross-section"},
)
class LorenzCurveEstimator:
    """Trace Lorenz-curve coordinates for inequality diagnostics and downstream plotting."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="lorenz_curve",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_distributional_output_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Lorenz curve and cumulative shares for a non-negative distribution.",
        tags=frozenset({"distributional", "inequality", "lorenz", "cross-section"}),
        when_to_use="Visual and formal inequality assessment; stochastic dominance tests",
        output_interpretation="Lorenz curve below 45-degree line = inequality. Closer to diagonal = more equal distribution.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("lorenz_curve requires non-negative values")
        sorted_values = np.sort(values)
        cumulative = np.cumsum(sorted_values, dtype=float)
        total = float(cumulative[-1])
        population_share = np.linspace(0.0, 1.0, sorted_values.shape[0] + 1, dtype=float)
        if total <= 0.0:
            value_share = np.zeros(sorted_values.shape[0] + 1, dtype=float)
        else:
            value_share = np.concatenate([[0.0], cumulative / total])
        return {
            "result": {
                "population_share": population_share.tolist(),
                "value_share": value_share.tolist(),
                "gini": compute_gini(values),
                "mean": float(np.mean(values)),
            }
        }


@foundry_method(
    namespace="distributional.inequality",
    version="1.0.0",
    tags={"distributional", "inequality", "atkinson", "cross-section"},
)
class AtkinsonIndexEstimator:
    """Estimate Atkinson inequality indices when welfare aversion matters."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="atkinson",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_distributional_output_slot(),
        parameters=(ParameterSpec(name="epsilon", default=0.5),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Atkinson inequality index with configurable inequality aversion.",
        tags=frozenset({"distributional", "inequality", "atkinson", "cross-section"}),
        when_to_use="Inequality with explicit social welfare function; need inequality-aversion parameter epsilon",
        output_interpretation="Atkinson index: welfare-equivalent income loss from inequality. A=0 no inequality, A=1 maximal.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("atkinson requires non-negative values")
        mean_value = float(np.mean(values))
        if mean_value <= 0.0:
            return {"result": {"atkinson_index": 0.0, "equally_distributed_equivalent": 0.0}}
        epsilon = float(params.get("epsilon", 0.5))
        shifted = np.maximum(values, 1e-12)
        if abs(epsilon - 1.0) < 1e-9:
            ede = float(np.exp(np.mean(np.log(shifted))))
        else:
            ede = float(np.mean(shifted ** (1.0 - epsilon)) ** (1.0 / (1.0 - epsilon)))
        return {
            "result": {
                "atkinson_index": float(max(0.0, 1.0 - ede / mean_value)),
                "equally_distributed_equivalent": ede,
                "epsilon": epsilon,
            }
        }


@foundry_method(
    namespace="distributional.inequality",
    version="1.0.0",
    tags={"distributional", "inequality", "generalized-entropy", "cross-section"},
)
class GeneralizedEntropyEstimator:
    """Estimate generalized-entropy indices for decomposable inequality audits."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="generalized_entropy",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_distributional_output_slot(),
        parameters=(ParameterSpec(name="alpha", default=1.0),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Generalized entropy inequality family including Theil T/L special cases.",
        tags=frozenset({"distributional", "inequality", "generalized-entropy", "cross-section"}),
        when_to_use="Decomposable inequality measure; between-group vs within-group decomposition",
        output_interpretation="Theil T: decomposable into within-group and between-group components. 0=equality.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        shifted = np.maximum(values, 1e-12)
        mean_value = float(np.mean(shifted))
        alpha = float(params.get("alpha", 1.0))
        ratio = shifted / max(mean_value, 1e-12)
        if abs(alpha) < 1e-9:
            ge = float(np.mean(np.log(1.0 / ratio)))
        elif abs(alpha - 1.0) < 1e-9:
            ge = float(np.mean(ratio * np.log(ratio)))
        else:
            ge = float((np.mean(ratio**alpha) - 1.0) / (alpha * (alpha - 1.0)))
        return {"result": {"generalized_entropy": ge, "alpha": alpha}}


@foundry_method(
    namespace="distributional.poverty",
    version="1.0.0",
    tags={"distributional", "poverty", "fgt", "cross-section"},
)
class FGTPovertyEstimator:
    """Estimate Foster-Greer-Thorbecke poverty gaps for poverty-oriented policy comparisons."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fgt",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
                SlotSpec("poverty_line", SlotType.SCALAR, Unit("value", "amount")),
            }
        ),
        output_slots=_distributional_output_slot(),
        parameters=(ParameterSpec(name="alpha", default=0.0),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Foster-Greer-Thorbecke poverty measures.",
        tags=frozenset({"distributional", "poverty", "fgt", "cross-section"}),
        when_to_use="Poverty measurement with poverty line; headcount, gap, severity (P0, P1, P2)",
        output_interpretation="P0=headcount ratio, P1=poverty gap, P2=poverty severity. Policy reduces poverty if post-policy P0/P1/P2 decrease.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide values and poverty_line")
        values = _values_payload(state, key="values")
        poverty_line = float(state["poverty_line"])
        if poverty_line <= 0.0:
            raise ValueError("poverty_line must be positive")
        alpha = max(0.0, float(params.get("alpha", 0.0)))
        poverty_gap = np.clip((poverty_line - values) / poverty_line, 0.0, None)
        headcount = float(np.mean(poverty_gap > 0))
        fgt = float(np.mean(poverty_gap**alpha))
        return {
            "result": {
                "fgt": fgt,
                "headcount_ratio": headcount,
                "poverty_gap_index": float(np.mean(poverty_gap)),
                "alpha": alpha,
                "poverty_line": poverty_line,
            }
        }


__all__ = [
    "AtkinsonIndexEstimator",
    "FGTPovertyEstimator",
    "GeneralizedEntropyEstimator",
    "LorenzCurveEstimator",
]
