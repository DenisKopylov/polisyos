"""Public validation diagnostics module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

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
from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationCurveBin,
    CalibrationDiagnosticIssue,
    CalibrationDiagnosticsReport,
    CalibrationMetrics,
    CalibrationTestResult,
)
from polisyos.ir.analytics.query_validation_report import ValidationSeverity


def _result_slot(contract_id: str | None = None) -> frozenset[SlotSpec]:
    return frozenset(
        {SlotSpec("result", SlotType.SCALAR, Unit("result", "json"), contract_id=contract_id)}
    )


@foundry_method(
    namespace="validation.model",
    version="1.0.0",
    tags={"validation", "model", "cross-validation", "tabular"},
)
class CrossValidationEstimator:
    """Run cross-validation over a method and return fold-level diagnostics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cross_validation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "fold_scores", SlotType.VECTOR, Unit("score", "value"), shape=("n_folds",)
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
    """Backtest time-ordered models with walk-forward validation windows."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="walk_forward",
        namespace="",
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
        rmse = float(np.sqrt(np.mean(errors**2)))
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
    """Assess calibration quality between predicted and observed outcomes."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="calibration_diagnostic",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "predicted_probs",
                    SlotType.VECTOR,
                    Unit("probability", "value"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "observed_outcomes",
                    SlotType.VECTOR,
                    Unit("outcome", "binary"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_result_slot(CalibrationDiagnosticsReport.contract_id),
        parameters=(ParameterSpec(name="n_bins", default=10),),
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
        declared_truthfulness_tier="approximate_calibrated",
        truthfulness_scope="predictive_calibration",
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
        if np.any((probs < 0.0) | (probs > 1.0)):
            raise ValueError("predicted_probs must lie in [0, 1]")
        if np.any((outcomes < 0.0) | (outcomes > 1.0)):
            raise ValueError("observed_outcomes must lie in [0, 1]")

        n_bins = int(params.get("n_bins", 10))
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)

        bin_mean_pred: list[float | None] = []
        bin_mean_obs: list[float | None] = []
        bin_counts: list[int] = []
        curve_bins: list[CalibrationCurveBin] = []

        for i in range(n_bins):
            if i < n_bins - 1:
                mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1])
            else:
                mask = (probs >= bin_edges[i]) & (probs <= bin_edges[i + 1])
            count = int(np.sum(mask))
            bin_counts.append(count)
            if count > 0:
                mean_pred = float(np.mean(probs[mask]))
                mean_obs = float(np.mean(outcomes[mask]))
                abs_gap = abs(mean_pred - mean_obs)
                bin_mean_pred.append(mean_pred)
                bin_mean_obs.append(mean_obs)
                curve_bins.append(
                    CalibrationCurveBin(
                        lower=float(bin_edges[i]),
                        upper=float(bin_edges[i + 1]),
                        count=count,
                        mean_predicted=mean_pred,
                        mean_observed=mean_obs,
                        absolute_gap=abs_gap,
                    )
                )
            else:
                bin_mean_pred.append(None)
                bin_mean_obs.append(None)
                curve_bins.append(
                    CalibrationCurveBin(
                        lower=float(bin_edges[i]),
                        upper=float(bin_edges[i + 1]),
                        count=0,
                    )
                )

        # Brier score
        brier = float(np.mean((probs - outcomes) ** 2))

        # Expected Calibration Error (ECE)
        ece = 0.0
        n = len(probs)
        for i in range(n_bins):
            if bin_counts[i] > 0 and bin_mean_pred[i] is not None and bin_mean_obs[i] is not None:
                ece += bin_counts[i] / n * abs(bin_mean_pred[i] - bin_mean_obs[i])

        warnings: list[str] = []
        issues: list[CalibrationDiagnosticIssue] = []
        if n < max(30, n_bins * 3):
            warnings.append("coarse_holdout_only")
            issues.append(
                CalibrationDiagnosticIssue(
                    code="CALIB_LOW_SAMPLE",
                    message="Holdout sample is small for stable calibration diagnostics.",
                    severity=ValidationSeverity.WARNING,
                    path="metrics.n_obs",
                    actual=n,
                    expected=max(30, n_bins * 3),
                )
            )
        if ece > 0.10:
            warnings.append("ece_above_fail_threshold")
        elif ece > 0.05:
            warnings.append("ece_above_target_threshold")

        metrics = CalibrationMetrics(
            n_obs=n,
            event_count=int(np.sum(outcomes)),
            prevalence=float(np.mean(outcomes)) if n else None,
            mean_predicted_score=float(np.mean(probs)) if n else None,
            mean_observed_rate=float(np.mean(outcomes)) if n else None,
            brier=brier,
            ece=float(ece),
            mce=float(
                max(
                    (
                        abs(float(pred) - float(obs))
                        for pred, obs in zip(bin_mean_pred, bin_mean_obs, strict=True)
                        if pred is not None and obs is not None
                    ),
                    default=0.0,
                )
            ),
        )
        report = CalibrationDiagnosticsReport(
            task="binary",
            target_type="probability",
            metrics=metrics,
            curves={"uniform_bins": tuple(curve_bins)},
            tests=(
                CalibrationTestResult(
                    test_id="holdout_ece_gate",
                    statistic=float(ece),
                    passed=bool(ece <= 0.05 and n >= 30),
                    assumptions_ok=bool(n >= 30),
                    notes=("Uses holdout ECE thresholding as a conservative calibration gate.",),
                ),
            ),
            issues=tuple(issues),
            warnings=tuple(dict.fromkeys(warnings)),
            primary_curve="uniform_bins",
            recommended_action=(
                "recalibrate_or_collect_more_holdout"
                if ece > 0.05 or n < 30
                else "calibration_accept"
            ),
            metadata={
                "n_bins": n_bins,
                "bin_mean_predicted": bin_mean_pred,
                "bin_mean_observed": bin_mean_obs,
                "bin_counts": bin_counts,
            },
        )
        report = report.model_copy(
            update={"truthfulness_receipt": report.to_truthfulness_receipt()}
        )
        return {
            "result": report,
        }


__all__ = [
    "CalibrationDiagnosticEstimator",
    "CrossValidationEstimator",
    "WalkForwardEstimator",
]
