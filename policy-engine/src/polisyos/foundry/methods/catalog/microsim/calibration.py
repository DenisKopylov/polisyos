"""Public microsim calibration module API."""
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

from .protocols import ReweightingResult, SurveyMicroData


def _survey_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=SurveyMicroData,
        nested_keys=("survey_micro_data",),
    )


@foundry_method(
    namespace="microsim.calibration",
    version="1.0.0",
    tags={"microsim", "calibration", "survey"},
)
class ReweightingCalibrationEstimator:
    """Reweighting calibration estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="reweighting_calibration",
        namespace="placeholder",
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
                    Unit("calibration", "json"),
                    contract_id=ReweightingResult.contract_id,
                ),
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("weight", "survey"),
                    shape=("n_obs",),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="target_total_weight", default=None),
            ParameterSpec(name="target_mean_income", default=None),
            ParameterSpec(name="max_weight_ratio", default=5.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Linear calibration of survey weights to population totals and mean income.",
        tags=frozenset({"microsim", "calibration", "survey"}),
        when_to_use="Align microsimulation outputs to aggregate control totals; demographic projection calibration",
        citations=(
            "Deville, J. & Sarndal, C. (1992). Calibration estimators in survey sampling. Journal of the American Statistical Association, 87(418), 376-382.",
        ),
        when_not_to_use="Control totals are inconsistent or unavailable; non-linear calibration required",
        output_interpretation="Calibrated weights/probabilities. Check alignment tables: model vs target. RMSE across cells.",
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
        target_total = (
            float(np.sum(weights))
            if params.get("target_total_weight") in {None, "None"}
            else float(params["target_total_weight"])
        )
        current_mean = float(np.sum(weights * income) / max(np.sum(weights), 1e-12))
        target_mean = (
            current_mean
            if params.get("target_mean_income") in {None, "None"}
            else float(params["target_mean_income"])
        )

        s0 = float(np.sum(weights))
        s1 = float(np.sum(weights * income))
        s2 = float(np.sum(weights * income * income))
        rhs = np.array([target_total, target_total * target_mean], dtype=float)
        matrix = np.array([[s0, s1], [s1, s2]], dtype=float)
        a, b = np.linalg.pinv(matrix) @ rhs

        calibrated = weights * (a + b * income)
        calibrated = np.maximum(calibrated, 1e-8)
        max_ratio = max(1.0, float(params.get("max_weight_ratio", 5.0)))
        mean_weight = float(np.mean(calibrated))
        calibrated = np.clip(calibrated, 1e-8, max_ratio * mean_weight)
        calibrated *= target_total / max(np.sum(calibrated), 1e-12)

        achieved_total = float(np.sum(calibrated))
        achieved_mean = float(np.sum(calibrated * income) / max(achieved_total, 1e-12))
        target_moments = {
            "total_weight": target_total,
            "mean_income": target_mean,
        }
        achieved_moments = {
            "total_weight": achieved_total,
            "mean_income": achieved_mean,
        }
        gaps = {
            key: abs(target_moments[key] - achieved_moments[key]) for key in target_moments
        }
        result = ReweightingResult(
            calibrated_weights=calibrated,
            target_moments=target_moments,
            achieved_moments=achieved_moments,
            max_abs_gap=float(max(gaps.values())),
            metadata={"a": float(a), "b": float(b)},
        )
        return {
            "result": result,
            "weights": calibrated,
        }


__all__ = ["ReweightingCalibrationEstimator"]
