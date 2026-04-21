"""Calibrate predictive uncertainty envelopes for ML regression outputs."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
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


def _weighted_quantile(values: np.ndarray, quantile: float, weights: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float).reshape(-1)
    w = np.asarray(weights, dtype=float).reshape(-1)
    if arr.shape[0] != w.shape[0]:
        raise ValueError("importance_weights must match residual length")
    if arr.shape[0] == 0:
        raise ValueError("weighted quantile requires at least one value")
    if not np.all(np.isfinite(w)) or np.any(w < 0.0):
        raise ValueError("importance_weights must be finite and non-negative")
    weight_sum = float(np.sum(w))
    if weight_sum <= 0.0:
        raise ValueError("importance_weights must sum to a positive value")
    q = min(max(float(quantile), 0.0), 1.0)
    order = np.argsort(arr)
    sorted_values = arr[order]
    sorted_weights = w[order]
    cdf = np.cumsum(sorted_weights) / weight_sum
    idx = int(np.searchsorted(cdf, q, side="left"))
    idx = min(max(idx, 0), sorted_values.shape[0] - 1)
    return float(sorted_values[idx])


def _effective_sample_size(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float).reshape(-1)
    denom = float(np.sum(w**2))
    total = float(np.sum(w))
    if total <= 0.0 or denom <= 0.0:
        return 0.0
    return (total * total) / denom


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
        namespace="",
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
        parameters=(
            ParameterSpec(name="alpha", default=0.1),
            ParameterSpec(name="shift_mode", default="standard"),
            ParameterSpec(name="importance_weights", default=None),
            ParameterSpec(name="min_effective_sample_size", default=10.0),
        ),
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
        declared_truthfulness_tier="exact",
        truthfulness_scope="marginal_coverage",
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
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must be in (0, 1)")
        shift_mode = str(params.get("shift_mode", "standard")).strip().lower() or "standard"
        if shift_mode not in {"standard", "weighted", "adaptive"}:
            raise ValueError("shift_mode must be one of: standard, weighted, adaptive")
        residual = np.abs(
            np.asarray(prediction_result.target, dtype=float)
            - np.asarray(prediction_result.predictions, dtype=float)
        )
        importance_weights = params.get("importance_weights")
        if importance_weights is None:
            importance_weights = prediction_result.metadata.get("importance_weights")

        ess: float | None = None
        q_hat: float
        if shift_mode == "standard":
            q_hat = float(np.quantile(residual, 1.0 - alpha, method="higher"))
        else:
            if importance_weights is None:
                raise ValueError(
                    "shift-aware conformal prediction requires importance_weights in params "
                    "or PredictionResult.metadata"
                )
            weights = np.asarray(importance_weights, dtype=float).reshape(-1)
            if weights.shape[0] != residual.shape[0]:
                raise ValueError("importance_weights must align with prediction residuals")
            if not np.all(np.isfinite(weights)) or np.any(weights < 0.0):
                raise ValueError("importance_weights must be finite and non-negative")
            if shift_mode == "adaptive":
                positive = weights[weights > 0.0]
                if positive.size == 0:
                    raise ValueError("adaptive shift mode requires at least one positive importance weight")
                lower_clip = float(np.quantile(positive, 0.05))
                upper_clip = float(np.quantile(positive, 0.95))
                weights = np.clip(weights, lower_clip, upper_clip)
            if float(np.sum(weights)) <= 0.0:
                raise ValueError("importance_weights must sum to a positive value")
            ess = _effective_sample_size(weights)
            min_ess = max(float(params.get("min_effective_sample_size", 10.0)), 1.0)
            if ess < min_ess:
                raise ValueError(
                    f"shift-aware conformal effective sample size {ess:.3f} is below "
                    f"min_effective_sample_size={min_ess:.3f}"
                )
            q_hat = _weighted_quantile(residual, 1.0 - alpha, weights)
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
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT,
                truthfulness_scope=TruthfulnessScope.MARGINAL_COVERAGE,
                diagnostics={
                    "observed_coverage": coverage,
                    "alpha": alpha,
                    "effective_sample_size": ess,
                    "shift_mode": shift_mode,
                },
            ),
            metadata={
                "base_method": prediction_result.method_name,
                "residual_quantile": q_hat,
                "shift_mode": shift_mode,
                "effective_sample_size": ess,
                "distribution_shift_adjusted": shift_mode != "standard",
            },
        )
        return {
            "result": result,
            "uncertainty_envelope": prediction_result.to_uncertainty_envelope(),
        }


__all__ = ["ConformalPredictionEstimator"]
