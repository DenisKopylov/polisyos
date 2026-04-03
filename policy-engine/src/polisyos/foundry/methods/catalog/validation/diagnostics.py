"""Public validation diagnostics module API."""
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


@foundry_method(
    namespace="validation.model",
    version="1.0.0",
    tags={"validation", "model", "cross-validation", "tabular"},
)
class CrossValidationEstimator:
    """Cross validation estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cross_validation",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("fold_scores", SlotType.VECTOR, Unit("score", "value"), shape=("n_folds",)),
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
        description="Cross-validation score aggregation: mean, std, and CI across folds.",
        tags=frozenset({"validation", "model", "cross-validation", "tabular"}),
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Estimate out-of-sample predictive performance; compare models; tune hyperparameters",
        output_interpretation="CV score (RMSE, AUC, log-loss). Lower RMSE/higher AUC = better. Variance across folds = stability.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        scores = np.asarray(state["fold_scores"], dtype=float)
        if scores.ndim != 1 or scores.size == 0:
            raise ValueError("fold_scores must be a non-empty 1D vector")

        n = len(scores)
        mean_score = float(np.mean(scores))
        std_score = float(np.std(scores, ddof=1)) if n > 1 else 0.0
        se = std_score / np.sqrt(n)

        return {
            "result": {
                "mean_score": mean_score,
                "std_score": std_score,
                "ci_lower": mean_score - 1.96 * se,
                "ci_upper": mean_score + 1.96 * se,
                "min_score": float(np.min(scores)),
                "max_score": float(np.max(scores)),
                "n_folds": n,
            }
        }


@foundry_method(
    namespace="validation.model",
    version="1.0.0",
    tags={"validation", "model", "walk-forward", "time-series", "tabular"},
)
class WalkForwardEstimator:
    """Walk forward estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="walk_forward",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("actuals", SlotType.VECTOR, Unit("value", "amount"), shape=("n_steps",)),
                SlotSpec("forecasts", SlotType.VECTOR, Unit("value", "amount"), shape=("n_steps",)),
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
        description="Walk-forward validation metrics for time-series forecasts.",
        tags=frozenset({"validation", "model", "walk-forward", "time-series", "tabular"}),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Time series model validation respecting temporal ordering; detect concept drift",
        output_interpretation="Walk-forward test error. Stable error over time = good temporal generalization.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        actuals = np.asarray(state["actuals"], dtype=float)
        forecasts = np.asarray(state["forecasts"], dtype=float)
        if actuals.shape != forecasts.shape or actuals.ndim != 1:
            raise ValueError("actuals and forecasts must be 1D with same length")

        errors = actuals - forecasts
        abs_errors = np.abs(errors)
        n = len(actuals)

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        # MAPE (guarded against zero actuals)
        nonzero = np.abs(actuals) > 1e-12
        if np.any(nonzero):
            mape = float(np.mean(abs_errors[nonzero] / np.abs(actuals[nonzero])))
        else:
            mape = float("inf")

        # Direction accuracy
        if n > 1:
            actual_dir = np.sign(np.diff(actuals))
            forecast_dir = np.sign(np.diff(forecasts))
            direction_accuracy = float(np.mean(actual_dir == forecast_dir))
        else:
            direction_accuracy = 0.0

        return {
            "result": {
                "mae": mae,
                "rmse": rmse,
                "mape": mape,
                "direction_accuracy": direction_accuracy,
                "mean_error": float(np.mean(errors)),
                "n_steps": n,
            }
        }


@foundry_method(
    namespace="validation.calibration",
    version="1.0.0",
    tags={"validation", "calibration", "diagnostic", "tabular"},
)
class CalibrationDiagnosticEstimator:
    """Calibration diagnostic estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="calibration_diagnostic",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("predicted_probs", SlotType.VECTOR, Unit("probability", "value"), shape=("n_obs",)),
                SlotSpec("observed_outcomes", SlotType.VECTOR, Unit("outcome", "binary"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_bins", default=10),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Calibration diagnostic: reliability diagram data and Brier score.",
        tags=frozenset({"validation", "calibration", "diagnostic", "brier", "tabular"}),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Check if predicted probabilities match observed frequencies; assess probabilistic forecast reliability",
        output_interpretation="Reliability diagram: calibrated if on diagonal. ECE (Expected Calibration Error) < 0.05 is well-calibrated.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        probs = np.asarray(state["predicted_probs"], dtype=float)
        outcomes = np.asarray(state["observed_outcomes"], dtype=float)
        if probs.shape != outcomes.shape or probs.ndim != 1:
            raise ValueError("predicted_probs and observed_outcomes must be 1D with same length")

        n_bins = int(params.get("n_bins", 10))
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)

        bin_mean_pred: list[float | None] = []
        bin_mean_obs: list[float | None] = []
        bin_counts: list[int] = []

        for i in range(n_bins):
            if i < n_bins - 1:
                mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1])
            else:
                mask = (probs >= bin_edges[i]) & (probs <= bin_edges[i + 1])
            count = int(np.sum(mask))
            bin_counts.append(count)
            if count > 0:
                bin_mean_pred.append(float(np.mean(probs[mask])))
                bin_mean_obs.append(float(np.mean(outcomes[mask])))
            else:
                bin_mean_pred.append(None)
                bin_mean_obs.append(None)

        # Brier score
        brier = float(np.mean((probs - outcomes) ** 2))

        # Expected Calibration Error (ECE)
        ece = 0.0
        n = len(probs)
        for i in range(n_bins):
            if bin_counts[i] > 0 and bin_mean_pred[i] is not None and bin_mean_obs[i] is not None:
                ece += bin_counts[i] / n * abs(bin_mean_pred[i] - bin_mean_obs[i])

        return {
            "result": {
                "brier_score": brier,
                "ece": float(ece),
                "bin_mean_predicted": bin_mean_pred,
                "bin_mean_observed": bin_mean_obs,
                "bin_counts": bin_counts,
                "n_obs": n,
            }
        }


__all__ = [
    "CalibrationDiagnosticEstimator",
    "CrossValidationEstimator",
    "WalkForwardEstimator",
]
