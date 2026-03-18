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
    return arr


# ---------------------------------------------------------------------------
# Cost-Benefit Analysis
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "cost-benefit", "structural"},
)
class CostBenefitAnalysisEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cost_benefit_analysis",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("benefits", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_periods",)),
                SlotSpec("costs", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_periods",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="discount_rate", default=0.03, bounds=(0.0, 1.0)),
            ParameterSpec(name="shadow_price_factor", default=1.0, bounds=(0.0, None)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Cost-benefit analysis with NPV, BCR, IRR, and payback period.",
        tags=frozenset({"policy", "welfare", "cost-benefit", "npv", "structural"}),
        citations=(
            "Boardman, A. et al. (2017). Cost-Benefit Analysis: Concepts and Practice.",
        ),
        equations={
            "npv": "NPV = sum_t (B_t - C_t) / (1 + r)^t",
            "bcr": "BCR = PV(benefits) / PV(costs)",
        },
        assumptions={
            "discount_rate": "Constant social discount rate across periods",
            "finite_periods": "Benefits and costs vectors must have same length",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Policy evaluation comparing all monetized costs and benefits; NPV of intervention",
        output_interpretation="NPV>0 = policy benefits exceed costs. BCR>1 = every $1 spent returns >$1 in benefits.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        benefits = np.asarray(state["benefits"], dtype=float)
        costs = np.asarray(state["costs"], dtype=float)
        if benefits.shape != costs.shape:
            raise ValueError("benefits and costs must have same length")

        discount_rate = float(params.get("discount_rate", 0.03))
        shadow = float(params.get("shadow_price_factor", 1.0))

        n = len(benefits)
        periods = np.arange(n, dtype=float)
        discount_factors = 1.0 / (1.0 + discount_rate) ** periods

        pv_benefits = float(np.sum(benefits * shadow * discount_factors))
        pv_costs = float(np.sum(costs * discount_factors))
        npv = pv_benefits - pv_costs
        bcr = pv_benefits / max(pv_costs, 1e-12)

        # IRR via bisection
        net_flows = benefits * shadow - costs
        irr = _compute_irr(net_flows)

        # Payback period
        cumulative = np.cumsum(net_flows)
        payback_indices = np.where(cumulative >= 0)[0]
        payback_period = int(payback_indices[0]) if len(payback_indices) > 0 else None

        return {
            "result": {
                "npv": npv,
                "bcr": bcr,
                "irr": irr,
                "payback_period": payback_period,
                "pv_benefits": pv_benefits,
                "pv_costs": pv_costs,
                "discount_rate": discount_rate,
                "n_periods": n,
            }
        }


def _compute_irr(cash_flows: np.ndarray, tol: float = 1e-8, max_iter: int = 200) -> float | None:
    """Compute IRR via bisection on NPV(r)=0."""
    def npv_at(r: float) -> float:
        t = np.arange(len(cash_flows), dtype=float)
        return float(np.sum(cash_flows / (1.0 + r) ** t))

    lo, hi = -0.5, 5.0
    npv_lo = npv_at(lo)
    npv_hi = npv_at(hi)
    if npv_lo * npv_hi > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        npv_mid = npv_at(mid)
        if abs(npv_mid) < tol:
            return float(mid)
        if npv_lo * npv_mid < 0:
            hi = mid
            npv_hi = npv_mid
        else:
            lo = mid
            npv_lo = npv_mid
    return float((lo + hi) / 2.0)


# ---------------------------------------------------------------------------
# Cost-Effectiveness Analysis
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "cost-effectiveness", "structural"},
)
class CostEffectivenessEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cost_effectiveness",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("costs", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_alternatives",)),
                SlotSpec("effects", SlotType.VECTOR, Unit("effect", "units"), shape=("n_alternatives",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="baseline_index", default=0),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Cost-effectiveness analysis with ICER and CE frontier.",
        tags=frozenset({"policy", "welfare", "cost-effectiveness", "icer", "structural"}),
        citations=(
            "Drummond, M. et al. (2015). Methods for the Economic Evaluation of Health Care Programmes.",
        ),
        equations={"icer": "ICER = (C_1 - C_0) / (E_1 - E_0)"},
        assumptions={"monotone_effects": "Higher effects are preferred"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Health/education policy; non-monetizable outcomes; QALY, DALY comparisons",
        output_interpretation="Cost-per-unit-outcome (e.g., cost per QALY gained). Lower = more cost-effective.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        costs = np.asarray(state["costs"], dtype=float)
        effects = np.asarray(state["effects"], dtype=float)
        if costs.shape != effects.shape or costs.ndim != 1:
            raise ValueError("costs and effects must be 1D with same length")

        baseline = int(params.get("baseline_index", 0))
        n = len(costs)

        # ICERs relative to baseline
        delta_c = costs - costs[baseline]
        delta_e = effects - effects[baseline]
        icers = np.full(n, np.nan)
        for i in range(n):
            if i != baseline and abs(delta_e[i]) > 1e-12:
                icers[i] = delta_c[i] / delta_e[i]

        # CE frontier: sort by effect, compute incremental ICERs
        order = np.argsort(effects)
        frontier_indices: list[int] = [int(order[0])]
        for idx in order[1:]:
            while len(frontier_indices) > 1:
                prev = frontier_indices[-1]
                prev2 = frontier_indices[-2]
                icer_new = (costs[idx] - costs[prev]) / max(effects[idx] - effects[prev], 1e-12)
                icer_old = (costs[prev] - costs[prev2]) / max(effects[prev] - effects[prev2], 1e-12)
                if icer_new <= icer_old:
                    frontier_indices.pop()
                else:
                    break
            frontier_indices.append(int(idx))

        return {
            "result": {
                "icers": [None if np.isnan(v) else float(v) for v in icers],
                "frontier_indices": frontier_indices,
                "costs": costs.tolist(),
                "effects": effects.tolist(),
                "baseline_index": baseline,
            }
        }


# ---------------------------------------------------------------------------
# Social Welfare Functions
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "utilitarian", "structural"},
)
class UtilitarianSWFEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="utilitarian_swf",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="weights", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Utilitarian social welfare function: W = sum of (weighted) utilities.",
        tags=frozenset({"policy", "welfare", "swf", "utilitarian", "structural"}),
        citations=("Bentham, J. (1789). An Introduction to the Principles of Morals and Legislation.",),
        equations={"swf": "W = sum_i w_i * u(x_i)"},
        assumptions={"additive": "Individual utilities are additively separable"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        weights_raw = params.get("weights")
        if weights_raw is not None:
            weights = np.asarray(weights_raw, dtype=float)
        else:
            weights = np.ones_like(values)
        welfare = float(np.sum(weights * values))
        return {
            "result": {
                "welfare": welfare,
                "mean_utility": float(np.mean(values)),
                "n_agents": len(values),
            }
        }


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "rawlsian", "structural"},
)
class RawlsianSWFEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="rawlsian_swf",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
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
        description="Rawlsian maximin social welfare function: W = min(u_i).",
        tags=frozenset({"policy", "welfare", "swf", "rawlsian", "maximin", "structural"}),
        citations=("Rawls, J. (1971). A Theory of Justice.",),
        equations={"swf": "W = min_i u(x_i)"},
        assumptions={"ordinal": "Only the worst-off individual matters"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        values = _values_payload(state)
        min_val = float(np.min(values))
        return {
            "result": {
                "welfare": min_val,
                "min_value": min_val,
                "min_index": int(np.argmin(values)),
                "n_agents": len(values),
            }
        }


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "atkinson", "structural"},
)
class AtkinsonSWFEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="atkinson_swf",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="epsilon", default=0.5, bounds=(0.0, 10.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Atkinson social welfare function with inequality aversion parameter.",
        tags=frozenset({"policy", "welfare", "swf", "atkinson", "structural"}),
        citations=("Atkinson, A.B. (1970). On the Measurement of Inequality.",),
        equations={
            "ede": "x_ede = (mean(x^(1-e)))^(1/(1-e)) for e != 1",
            "swf": "W = n * x_ede",
        },
        assumptions={"non_negative": "Values must be non-negative"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("atkinson_swf requires non-negative values")
        epsilon = float(params.get("epsilon", 0.5))
        shifted = np.maximum(values, 1e-12)
        n = len(values)
        if abs(epsilon - 1.0) < 1e-9:
            ede = float(np.exp(np.mean(np.log(shifted))))
        else:
            ede = float(np.mean(shifted ** (1.0 - epsilon)) ** (1.0 / (1.0 - epsilon)))
        welfare = n * ede
        return {
            "result": {
                "welfare": welfare,
                "ede_income": ede,
                "mean_income": float(np.mean(values)),
                "epsilon": epsilon,
                "n_agents": n,
            }
        }


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "sen", "structural"},
)
class SenCapabilityEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sen_capability",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
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
        description="Sen welfare index: W = mean * (1 - Gini).",
        tags=frozenset({"policy", "welfare", "swf", "sen", "capability", "structural"}),
        citations=("Sen, A. (1976). Real National Income. Review of Economic Studies.",),
        equations={"swf": "W = mu * (1 - G)"},
        assumptions={"non_negative": "Values must be non-negative"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("sen_capability requires non-negative values")
        mean_val = float(np.mean(values))
        n = len(values)
        sorted_v = np.sort(values)
        if mean_val <= 0.0:
            gini = 0.0
        else:
            indices = np.arange(1, n + 1, dtype=float)
            gini = float((2.0 * np.sum(indices * sorted_v) - (n + 1) * np.sum(sorted_v)) / (n * np.sum(sorted_v)))
            gini = max(0.0, min(1.0, gini))
        welfare = mean_val * (1.0 - gini)
        return {
            "result": {
                "welfare": welfare,
                "mean": mean_val,
                "gini": gini,
                "n_agents": n,
            }
        }


__all__ = [
    "AtkinsonSWFEstimator",
    "CostBenefitAnalysisEstimator",
    "CostEffectivenessEstimator",
    "RawlsianSWFEstimator",
    "SenCapabilityEstimator",
    "UtilitarianSWFEstimator",
]
