"""Calibrate predictive uncertainty envelopes for ML regression outputs."""
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

from .protocols import PredictionIntervalResult, PredictionResult


def _prediction_payload(state: Any) -> PredictionResult:
    if isinstance(state, PredictionResult):
        return state
    if isinstance(state, Mapping):
        nested = state.get("prediction_result")
        if isinstance(nested, PredictionResult):
            return nested
        nested_result = state.get("result")
        if isinstance(nested_result, PredictionResult):
            return nested_result
        if isinstance(nested, Mapping):
            return PredictionResult.model_validate(nested)
        if isinstance(nested_result, Mapping):
            return PredictionResult.model_validate(nested_result)
        return PredictionResult.model_validate(dict(state))
    raise TypeError("state must be PredictionResult or mapping")


@foundry_method(
    namespace="ml.uncertainty",
    version="1.0.0",
    tags={"ml", "uncertainty", "conformal-prediction"},
)
class ConformalPredictionEstimator:
    """Build split-conformal prediction intervals under exchangeability; avoid nonstationary test distributions without recalibration."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="conformal_prediction",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "prediction_result",
                    SlotType.SCALAR,
                    Unit("prediction", "json"),
                    contract_id=PredictionResult.contract_id,
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("prediction_interval", "json"),
                    contract_id=PredictionIntervalResult.contract_id,
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(ParameterSpec(name="alpha", default=0.1),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Split-conformal style residual intervals over an upstream prediction result.",
        tags=frozenset({"ml", "uncertainty", "conformal-prediction"}),
        when_to_use="Distribution-free prediction intervals with coverage guarantee; any black-box model",
        citations=(
            "Vovk, V., Gammerman, A. & Shafer, G. (2005). Algorithmic Learning in a Random World. Springer.",
            "Romano, Y., Patterson, E. & Candes, E. (2019). Conformalized quantile regression. NeurIPS, 32.",
        ),
        when_not_to_use="Need conditional coverage (use CQR); calibration set too small (<50 obs)",
        output_interpretation="Prediction set with 1-α marginal coverage guarantee. Width indicates uncertainty.",
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PredictionResult:
        if "prediction_result" in bound_inputs:
            return _prediction_payload(bound_inputs["prediction_result"])
        return _prediction_payload(fallback_state)

    @staticmethod
    def pure_step(state: PredictionResult, params: Mapping[str, Any]) -> dict[str, Any]:
        prediction_result = (
            state if isinstance(state, PredictionResult) else PredictionResult.model_validate(state)
        )
        if prediction_result.target is None:
            raise ValueError("conformal_prediction requires target values in PredictionResult")

        alpha = float(params.get("alpha", 0.1))
        alpha = min(max(alpha, 1e-6), 0.99)
        residual = np.abs(
            np.asarray(prediction_result.target, dtype=float)
            - np.asarray(prediction_result.predictions, dtype=float)
        )
        q_hat = float(np.quantile(residual, 1.0 - alpha, method="higher"))
        predictions = np.asarray(prediction_result.predictions, dtype=float)
        lower = predictions - q_hat
        upper = predictions + q_hat
        target = np.asarray(prediction_result.target, dtype=float)
        coverage = float(np.mean((target >= lower) & (target <= upper)))

        result = PredictionIntervalResult(
            method_name="conformal_prediction",
            predictions=predictions,
            lower=lower,
            upper=upper,
            coverage=coverage,
            alpha=alpha,
            metadata={
                "base_method": prediction_result.method_name,
                "residual_quantile": q_hat,
            },
        )
        return {
            "result": result,
            "uncertainty_envelope": prediction_result.to_uncertainty_envelope(),
        }


__all__ = ["ConformalPredictionEstimator"]
