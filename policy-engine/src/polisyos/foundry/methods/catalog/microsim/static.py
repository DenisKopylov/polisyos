"""Public microsim static module API."""
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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload

from .protocols import MicrosimResult, SurveyMicroData


def _survey_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=SurveyMicroData,
        nested_keys=("survey_micro_data",),
    )


def _weighted_gini(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    x = values[order]
    w = weights[order]
    cumw = np.cumsum(w)
    cumxw = np.cumsum(x * w)
    if cumxw[-1] <= 1e-12:
        return 0.0
    relw = cumw / cumw[-1]
    relx = cumxw / cumxw[-1]
    area = np.trapezoid(relx, relw)
    return float(max(0.0, min(1.0, 1.0 - 2.0 * area)))


@foundry_method(
    namespace="microsim.static",
    version="1.0.0",
    tags={"microsim", "simulation", "survey"},
)
class StaticMicrosimEstimator:
    """Run a one-period microsimulation over household tax and transfer rules."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="static_microsim",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income",
                    SlotType.VECTOR,
                    Unit("income", "currency"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("weight", "survey"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("microsim", "json"),
                    contract_id=MicrosimResult.contract_id,
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="tax_allowance", default=12000.0),
            ParameterSpec(name="tax_rate", default=0.2),
            ParameterSpec(name="benefit_floor", default=8000.0),
            ParameterSpec(name="benefit_taper", default=0.25),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Static tax-benefit microsimulation with weighted distributional aggregates.",
        tags=frozenset({"microsim", "simulation", "survey"}),
        when_to_use="First-order (mechanical) distributional impact of policy reform on existing population; tax/benefit calculator",
        citations=(
            "Immervoll, H. et al. (2006). Microsimulation of personal income tax and transfer systems. International Journal of Microsimulation, 1(1), 1-13.",
            "Bourguignon, F. & Spadaro, A. (2006). Microsimulation as a tool for evaluating redistribution policies. Journal of Economic Inequality, 4(1), 77-106.",
        ),
        when_not_to_use="Need behavioral responses; dynamic effects matter (use dynamic microsim)",
        output_interpretation="Distribution of winners/losers. Change in Gini, poverty headcount. Budget cost at first round.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SurveyMicroData:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return SurveyMicroData.model_validate(payload)

    @staticmethod
    def pure_step(state: SurveyMicroData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, SurveyMicroData) else SurveyMicroData.model_validate(state)
        income = np.asarray(data.market_income, dtype=float)
        weights = np.asarray(data.weights, dtype=float)
        tax_allowance = float(params.get("tax_allowance", 12000.0))
        tax_rate = float(params.get("tax_rate", 0.2))
        benefit_floor = float(params.get("benefit_floor", 8000.0))
        benefit_taper = float(params.get("benefit_taper", 0.25))

        taxable_income = np.maximum(income - tax_allowance, 0.0)
        tax_liability = tax_rate * taxable_income
        benefit_income = np.maximum(benefit_floor - benefit_taper * income, 0.0)
        disposable_income = income - tax_liability + benefit_income

        weight_sum = max(float(np.sum(weights)), 1e-12)
        weighted_mean = float(np.sum(disposable_income * weights) / weight_sum)
        weighted_gini = _weighted_gini(disposable_income, weights)
        policy_revenue = float(np.sum((tax_liability - benefit_income) * weights))

        result = MicrosimResult(
            disposable_income=disposable_income,
            tax_liability=tax_liability,
            benefit_income=benefit_income,
            weighted_mean_disposable_income=weighted_mean,
            weighted_gini=weighted_gini,
            policy_revenue=policy_revenue,
            metadata={
                "tax_allowance": tax_allowance,
                "tax_rate": tax_rate,
                "benefit_floor": benefit_floor,
                "benefit_taper": benefit_taper,
            },
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


__all__ = ["StaticMicrosimEstimator"]
