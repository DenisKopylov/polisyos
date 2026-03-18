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

from .protocols import (
    BehavioralResponseResult,
    DynamicMicrosimResult,
    ImputationResult,
    SurveyMicroData,
    TaxBenefitResult,
)


def _survey_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=SurveyMicroData,
        nested_keys=("survey_micro_data",),
    )


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / max(np.sum(weights), 1e-12))


@foundry_method(
    namespace="microsim.policy",
    version="1.0.0",
    tags={"microsim", "tax-benefit", "survey"},
)
class TaxBenefitCalculatorEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tax_benefit_calculator",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("tax_benefit", "json"),
                    contract_id=TaxBenefitResult.contract_id,
                ),
                SlotSpec("disposable_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
                SlotSpec("tax_liability", SlotType.VECTOR, Unit("tax", "currency"), shape=("n_obs",)),
                SlotSpec("benefit_income", SlotType.VECTOR, Unit("benefit", "currency"), shape=("n_obs",)),
                SlotSpec("effective_tax_rate", SlotType.VECTOR, Unit("rate", "share"), shape=("n_obs",)),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="allowance", default=10000.0),
            ParameterSpec(name="threshold_1", default=25000.0),
            ParameterSpec(name="threshold_2", default=60000.0),
            ParameterSpec(name="rate_1", default=0.1),
            ParameterSpec(name="rate_2", default=0.2),
            ParameterSpec(name="rate_3", default=0.32),
            ParameterSpec(name="benefit_floor", default=9000.0),
            ParameterSpec(name="benefit_taper", default=0.2),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Tax-benefit calculator producing liabilities, transfers, disposable income, and tax rates.",
        tags=frozenset({"microsim", "tax-benefit", "survey"}),
        when_to_use="First-order (mechanical) distributional impact of policy reform on existing population; tax/benefit calculator",
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
        allowance = float(params.get("allowance", 10000.0))
        threshold_1 = float(params.get("threshold_1", 25000.0))
        threshold_2 = float(params.get("threshold_2", 60000.0))
        rate_1 = float(params.get("rate_1", 0.1))
        rate_2 = float(params.get("rate_2", 0.2))
        rate_3 = float(params.get("rate_3", 0.32))
        benefit_floor = float(params.get("benefit_floor", 9000.0))
        benefit_taper = float(params.get("benefit_taper", 0.2))

        taxable = np.maximum(income - allowance, 0.0)
        band1 = np.minimum(taxable, np.maximum(threshold_1 - allowance, 0.0))
        band2 = np.minimum(np.maximum(taxable - band1, 0.0), np.maximum(threshold_2 - threshold_1, 0.0))
        band3 = np.maximum(taxable - band1 - band2, 0.0)
        tax_liability = rate_1 * band1 + rate_2 * band2 + rate_3 * band3
        benefit_income = np.maximum(benefit_floor - benefit_taper * income, 0.0)
        disposable_income = income - tax_liability + benefit_income

        marginal_tax_rate = np.where(
            income <= allowance,
            0.0,
            np.where(income <= threshold_1, rate_1, np.where(income <= threshold_2, rate_2, rate_3)),
        )
        effective_tax_rate = np.where(
            income > 1e-9,
            (tax_liability - benefit_income) / income,
            0.0,
        )
        result = TaxBenefitResult(
            disposable_income=disposable_income,
            tax_liability=tax_liability,
            benefit_income=benefit_income,
            marginal_tax_rate=marginal_tax_rate,
            effective_tax_rate=effective_tax_rate,
            weighted_mean_disposable_income=_weighted_mean(disposable_income, weights),
            policy_revenue=float(np.sum((tax_liability - benefit_income) * weights)),
            metadata={"allowance": allowance, "threshold_1": threshold_1, "threshold_2": threshold_2},
        )
        return {
            "result": result,
            "disposable_income": disposable_income,
            "tax_liability": tax_liability,
            "benefit_income": benefit_income,
            "effective_tax_rate": effective_tax_rate,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="microsim.behavior",
    version="1.0.0",
    tags={"microsim", "behavioral-response", "survey"},
)
class BehavioralResponseEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="behavioral_response",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
                SlotSpec("effective_tax_rate", SlotType.VECTOR, Unit("rate", "share"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("behavior", "json"),
                    contract_id=BehavioralResponseResult.contract_id,
                ),
                SlotSpec("market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(ParameterSpec(name="elasticity", default=0.2),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Behavioral income response to tax wedges using a labor-supply elasticity rule.",
        tags=frozenset({"microsim", "behavioral-response", "survey"}),
        when_to_use="Policy with significant labor supply or consumption behavioral responses; structural microsim",
        when_not_to_use="Behavioral responses negligible; elasticity estimates unavailable or highly uncertain",
        output_interpretation="Behavioral + first-round effects. Elasticities determine magnitude of behavioral response.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("behavioral_response expects mapping input")
        income = np.asarray(state["market_income"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        if "effective_tax_rate" not in state:
            raise ValueError("behavioral_response requires effective_tax_rate input")
        effective_tax_rate = np.asarray(state["effective_tax_rate"], dtype=float)
        elasticity = float(params.get("elasticity", 0.2))
        net_rate = np.clip(1.0 - effective_tax_rate, 1e-3, None)
        baseline = float(np.mean(net_rate))
        adjusted_income = income * np.power(net_rate / max(baseline, 1e-3), elasticity)
        change = adjusted_income - income
        result = BehavioralResponseResult(
            adjusted_market_income=adjusted_income,
            labor_supply_change=change,
            weighted_mean_income=_weighted_mean(adjusted_income, weights),
            elasticity=elasticity,
            metadata={"baseline_net_rate": baseline},
        )
        return {
            "result": result,
            "market_income": adjusted_income,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="microsim.imputation",
    version="1.0.0",
    tags={"microsim", "imputation", "survey"},
)
class ImputationModelEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="imputation_model",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("imputation", "json"),
                    contract_id=ImputationResult.contract_id,
                ),
                SlotSpec("market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
            }
        ),
        parameters=(ParameterSpec(name="n_estimators", default=100),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Supervised imputation of missing market income using tabular household features.",
        tags=frozenset({"microsim", "imputation", "survey"}),
        when_to_use="Missing income/covariate imputation in survey microdata prior to microsimulation",
        when_not_to_use="Very high missing rates (>50%); missingness is informative and cannot be modeled",
        output_interpretation="Imputed values replace missing entries. RMSE on observed training data indicates quality. Missing share shows scope of imputation.",
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
        missing_mask = ~np.isfinite(income)
        if not missing_mask.any():
            result = ImputationResult(
                imputed_market_income=income,
                missing_share=0.0,
                rmse_train=0.0,
                metadata={"strategy": "identity"},
            )
            return {"result": result, "market_income": income}

        observed_mask = ~missing_mask
        imputed = np.asarray(income, dtype=float).copy()
        rmse_train: float | None = None
        if data.features is not None and np.sum(observed_mask) >= 8:
            from sklearn.ensemble import RandomForestRegressor

            model = RandomForestRegressor(
                n_estimators=max(50, int(params.get("n_estimators", 100))),
                random_state=int(params.get("__seed__", 0)),
            )
            x = np.asarray(data.features, dtype=float)
            model.fit(x[observed_mask], income[observed_mask])
            imputed[missing_mask] = model.predict(x[missing_mask])
            train_pred = model.predict(x[observed_mask])
            rmse_train = float(np.sqrt(np.mean((train_pred - income[observed_mask]) ** 2)))
            strategy = "random_forest"
        else:
            fill_value = float(np.nanmedian(income))
            imputed[missing_mask] = fill_value
            strategy = "median"

        result = ImputationResult(
            imputed_market_income=imputed,
            missing_share=float(np.mean(missing_mask)),
            rmse_train=rmse_train,
            metadata={"strategy": strategy},
        )
        return {
            "result": result,
            "market_income": imputed,
        }


@foundry_method(
    namespace="microsim.dynamic",
    version="1.0.0",
    tags={"microsim", "dynamic", "survey"},
)
class DynamicMicrosimEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dynamic_microsim",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("dynamic_microsim", "json"),
                    contract_id=DynamicMicrosimResult.contract_id,
                ),
                SlotSpec("market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="horizon", default=5),
            ParameterSpec(name="n_periods", default=None),
            ParameterSpec(name="drift", default=0.02),
            ParameterSpec(name="volatility", default=0.05),
            ParameterSpec(name="tax_rate", default=0.2),
            ParameterSpec(name="benefit_floor", default=8000.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Dynamic microsimulation of income evolution and fiscal outcomes over a finite horizon.",
        tags=frozenset({"microsim", "dynamic", "survey"}),
        when_to_use="Long-run distributional effects; cohort pension reform; lifetime income redistribution",
        when_not_to_use="Short-run first-order analysis sufficient; no longitudinal data available",
        output_interpretation="Lifetime income/wealth distributions. Generational accounting. Cohort-specific winners/losers.",
        typical_min_obs=1000,
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
        rng = params.get("__rng__")
        if rng is None or not hasattr(rng, "normal"):
            rng = np.random.default_rng(int(params.get("__seed__", 0)))
        horizon_raw = params.get("n_periods", params.get("horizon", 5))
        if horizon_raw is None:
            horizon_raw = params.get("horizon", 5)
        horizon = max(1, int(horizon_raw))
        drift = float(params.get("drift", 0.02))
        volatility = float(params.get("volatility", 0.05))
        tax_rate = float(params.get("tax_rate", 0.2))
        benefit_floor = float(params.get("benefit_floor", 8000.0))

        current = income.copy()
        mean_income_path: list[float] = []
        policy_revenue_path: list[float] = []
        for _ in range(horizon):
            shocks = rng.normal(loc=0.0, scale=volatility, size=current.shape[0])
            growth = np.maximum(1.0 + drift + shocks, 0.2)
            current = np.maximum(current * growth, 0.0)
            benefits = np.maximum(benefit_floor - 0.15 * current, 0.0)
            taxes = tax_rate * np.maximum(current - benefit_floor, 0.0)
            mean_income_path.append(_weighted_mean(current, weights))
            policy_revenue_path.append(float(np.sum((taxes - benefits) * weights)))

        final_benefits = np.maximum(benefit_floor - 0.15 * current, 0.0)
        final_taxes = tax_rate * np.maximum(current - benefit_floor, 0.0)
        disposable_income = current - final_taxes + final_benefits
        result = DynamicMicrosimResult(
            final_market_income=current,
            disposable_income=disposable_income,
            mean_income_path=mean_income_path,
            policy_revenue_path=policy_revenue_path,
            weighted_mean_final_income=_weighted_mean(current, weights),
            metadata={"horizon": horizon, "drift": drift, "volatility": volatility},
        )
        return {
            "result": result,
            "market_income": current,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


__all__ = [
    "BehavioralResponseEstimator",
    "DynamicMicrosimEstimator",
    "ImputationModelEstimator",
    "TaxBenefitCalculatorEstimator",
]
