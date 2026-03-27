"""Temporal trajectory evaluation helpers for benchmark suites."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from polisyos.foundry.methods.catalog.causal.structural_time_series import TemporalTrajectoryResult
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import TemporalCompileError
from polisyos.ir.analytics.backtest import BacktestReport, BacktestScenario
from polisyos.ir.analytics.dynamic_regime import TemporalPathRepresentation

from .evaluator import PredictionEvaluator


_REJECTION_ALLOWED_REASON_CODES = {
    "invalid_intervention_contract_ref",
    "intervention_out_of_support",
    "intervention_policy_mismatch",
    "intervention_regime_mismatch",
    "missing_intervention_contract",
    "query_mode_conflict",
    "research_gated_sampling_scheme",
    "research_gated_backend",
    "time_scale_mismatch",
    "unsupported_target_functional",
    "unsupported_backend_target",
    "unsupported_dynamic_intervention",
    "unsupported_intervention_regime_consistency",
    "unsupported_panel_intervention",
    "time_grid_mismatch",
    "horizon_out_of_range",
}


@dataclass(frozen=True)
class TemporalThresholds:
    max_path_rmse: float | None = None
    max_path_mae: float | None = None
    max_endpoint_abs_error: float | None = None
    max_integral_effect_abs_error: float | None = None
    min_band_coverage: float | None = None


@dataclass(frozen=True)
class TemporalEvaluationResult:
    scenario: BacktestScenario
    pointwise_metrics: dict[str, float]
    functional_metrics: dict[str, float]
    uncertainty_metrics: dict[str, float]
    diagnostics_checks: dict[str, Any]
    gating_checks: dict[str, Any]
    thresholds: dict[str, float]
    acceptance_checks: dict[str, bool]
    expected_outcome: str
    actual_outcome: str
    matches_expected_outcome: bool
    passes: bool
    reason_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_temporal_trajectory(
    *,
    scenario_id: str,
    scenario_label: str,
    trajectory: TemporalTrajectoryResult,
    expected_effect_path: Sequence[float],
    expected_integral_effect: float | None = None,
    thresholds: TemporalThresholds | Mapping[str, float] | None = None,
    expected_outcome: str = "pass",
    extra_acceptance_checks: Mapping[str, bool] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> TemporalEvaluationResult:
    """Evaluate a temporal trajectory against an expected effect path."""

    threshold_spec = _coerce_thresholds(thresholds)
    time_grid = np.asarray(trajectory.plan.time_grid, dtype=float)
    predicted = np.asarray(trajectory.effect_path, dtype=float)
    expected = _coerce_path(expected_effect_path, expected_length=predicted.shape[0])
    lower = _coerce_path(trajectory.confidence_band_lower, expected_length=predicted.shape[0])
    upper = _coerce_path(trajectory.confidence_band_upper, expected_length=predicted.shape[0])

    evaluator = PredictionEvaluator()
    scenario = evaluator.evaluate(
        scenario_id=scenario_id,
        scenario_label=scenario_label,
        y_pred={"effect_path": predicted.tolist()},
        y_true={"effect_path": expected.tolist()},
        intervals={"effect_path": list(zip(lower.tolist(), upper.tolist()))},
        metadata={},
    )

    path_rmse = float(scenario.rmse or 0.0)
    path_mae = float(scenario.mae or 0.0)
    endpoint_abs_error = float(abs(predicted[-1] - expected[-1]))
    expected_integral = (
        float(expected_integral_effect)
        if expected_integral_effect is not None
        else _integral(expected, time_grid)
    )
    actual_integral = float(trajectory.integral_effect)
    integral_effect_abs_error = float(abs(actual_integral - expected_integral))
    band_coverage = float(scenario.coverage_probability or 0.0)

    pointwise_metrics = {
        "path_rmse": path_rmse,
        "path_mae": path_mae,
        "endpoint_abs_error": endpoint_abs_error,
    }
    functional_metrics = {
        "integral_effect_abs_error": integral_effect_abs_error,
        "expected_integral_effect": expected_integral,
        "actual_integral_effect": actual_integral,
    }
    uncertainty_metrics = {
        "band_coverage": band_coverage,
    }
    diagnostics_checks = _evaluate_diagnostics(trajectory)

    acceptance_checks: dict[str, bool] = {}
    if threshold_spec.max_path_rmse is not None:
        acceptance_checks["path_rmse"] = path_rmse <= threshold_spec.max_path_rmse
    if threshold_spec.max_path_mae is not None:
        acceptance_checks["path_mae"] = path_mae <= threshold_spec.max_path_mae
    if threshold_spec.max_endpoint_abs_error is not None:
        acceptance_checks["endpoint_abs_error"] = (
            endpoint_abs_error <= threshold_spec.max_endpoint_abs_error
        )
    if threshold_spec.max_integral_effect_abs_error is not None:
        acceptance_checks["integral_effect_abs_error"] = (
            integral_effect_abs_error <= threshold_spec.max_integral_effect_abs_error
        )
    if threshold_spec.min_band_coverage is not None:
        acceptance_checks["band_coverage"] = band_coverage >= threshold_spec.min_band_coverage
    acceptance_checks["diagnostics_complete"] = bool(diagnostics_checks["complete"])
    for name, value in (extra_acceptance_checks or {}).items():
        acceptance_checks[str(name)] = bool(value)

    passes = all(acceptance_checks.values()) if acceptance_checks else True
    actual_outcome = "pass"
    if not diagnostics_checks["complete"]:
        actual_outcome = "diagnostic_failure"
    elif not passes:
        actual_outcome = "threshold_failure"
    matches_expected_outcome = actual_outcome == expected_outcome

    gating_checks = {
        "safe_rejection": False,
        "fallback_required": trajectory.plan.fallback_mode.value != "none",
        "fallback_success": bool(
            trajectory.plan.fallback_mode.value == "none"
            or (
                trajectory.plan.fallback_mode.value == "discrete_time"
                and bool(diagnostics_checks["complete"])
                and np.isfinite(predicted).all()
            )
        ),
        "diagnostics_handled": bool(diagnostics_checks["complete"])
        or (
            expected_outcome == "diagnostic_failure"
            and actual_outcome == "diagnostic_failure"
        ),
        "runtime_eligible": bool(
            trajectory.effect_bundle.runtime_eligible
            if trajectory.effect_bundle is not None
            else trajectory.path_representation
            not in {
                TemporalPathRepresentation.NEURAL_CDE,
                TemporalPathRepresentation.NEURAL_SDE,
            }
        ),
        "runtime_support_status": (
            trajectory.effect_bundle.runtime_support_status.value
            if trajectory.effect_bundle is not None
            else (
                "degraded"
                if trajectory.path_representation is TemporalPathRepresentation.DISCRETE_REPLAY
                else trajectory.plan.query.runtime_support_status.value
            )
        ),
    }

    scenario.metadata.update(
        {
            "temporal_metrics": {
                **pointwise_metrics,
                **functional_metrics,
                **uncertainty_metrics,
            },
            "diagnostics_checks": diagnostics_checks,
            "gating_checks": gating_checks,
            "thresholds": _thresholds_to_dict(threshold_spec),
            "acceptance_checks": acceptance_checks,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "time_grid": time_grid.tolist(),
            "backend_target": trajectory.plan.backend_target.value,
            "fallback_mode": trajectory.plan.fallback_mode.value,
            "reason_code": None,
            **dict(metadata or {}),
        }
    )

    return TemporalEvaluationResult(
        scenario=scenario,
        pointwise_metrics=pointwise_metrics,
        functional_metrics=functional_metrics,
        uncertainty_metrics=uncertainty_metrics,
        diagnostics_checks=diagnostics_checks,
        gating_checks=gating_checks,
        thresholds=_thresholds_to_dict(threshold_spec),
        acceptance_checks=acceptance_checks,
        expected_outcome=expected_outcome,
        actual_outcome=actual_outcome,
        matches_expected_outcome=matches_expected_outcome,
        passes=passes,
        reason_code=None,
        metadata=dict(metadata or {}),
    )


def evaluate_temporal_safe_rejection(
    *,
    scenario_id: str,
    scenario_label: str,
    error: Exception,
    expected_reason_code: str,
    metadata: Mapping[str, Any] | None = None,
) -> TemporalEvaluationResult:
    """Evaluate whether a temporal query was rejected safely and machine-readably."""

    reason_code = ""
    details: dict[str, Any] = {}
    if isinstance(error, TemporalCompileError):
        reason_code = str(error.reason_code)
        details = dict(error.details)

    machine_readable = bool(reason_code)
    safe_rejection = bool(machine_readable and reason_code == expected_reason_code)
    diagnostics_checks = {
        "has_reason_code": machine_readable,
        "details_present": bool(details or machine_readable),
        "complete": machine_readable,
        "missing_fields": [] if machine_readable else ["reason_code"],
    }
    gating_checks = {
        "safe_rejection": safe_rejection,
        "fallback_required": False,
        "fallback_success": True,
        "diagnostics_handled": safe_rejection,
        "runtime_eligible": False,
    }
    actual_outcome = "safe_rejection" if safe_rejection else "unexpected_rejection"
    scenario = BacktestScenario(
        scenario_id=scenario_id,
        scenario_label=scenario_label,
        metadata={
            "temporal_metrics": {},
            "diagnostics_checks": diagnostics_checks,
            "gating_checks": gating_checks,
            "expected_outcome": "safe_rejection",
            "actual_outcome": actual_outcome,
            "reason_code": reason_code or type(error).__name__,
            "rejection_details": details,
            **dict(metadata or {}),
        },
    )
    return TemporalEvaluationResult(
        scenario=scenario,
        pointwise_metrics={},
        functional_metrics={},
        uncertainty_metrics={},
        diagnostics_checks=diagnostics_checks,
        gating_checks=gating_checks,
        thresholds={},
        acceptance_checks={"safe_rejection": safe_rejection},
        expected_outcome="safe_rejection",
        actual_outcome=actual_outcome,
        matches_expected_outcome=(actual_outcome == "safe_rejection"),
        passes=safe_rejection,
        reason_code=reason_code or None,
        metadata=dict(metadata or {}),
    )


def summarize_temporal_evaluations(
    evaluations: Sequence[TemporalEvaluationResult],
) -> dict[str, Any]:
    """Aggregate temporal evaluation outcomes for suite-level scorecards."""

    n_total = len(evaluations)
    n_passed = sum(1 for item in evaluations if item.matches_expected_outcome)
    safe_rejection_cases = [item for item in evaluations if item.expected_outcome == "safe_rejection"]
    fallback_cases = [item for item in evaluations if item.gating_checks.get("fallback_required")]

    path_rmse_values = [item.pointwise_metrics["path_rmse"] for item in evaluations if "path_rmse" in item.pointwise_metrics]
    path_mae_values = [item.pointwise_metrics["path_mae"] for item in evaluations if "path_mae" in item.pointwise_metrics]
    endpoint_values = [
        item.pointwise_metrics["endpoint_abs_error"]
        for item in evaluations
        if "endpoint_abs_error" in item.pointwise_metrics
    ]
    integral_values = [
        item.functional_metrics["integral_effect_abs_error"]
        for item in evaluations
        if "integral_effect_abs_error" in item.functional_metrics
    ]
    coverage_values = [
        item.uncertainty_metrics["band_coverage"]
        for item in evaluations
        if "band_coverage" in item.uncertainty_metrics
    ]

    diagnostics_presence_rate = _mean(
        [1.0 if item.gating_checks.get("diagnostics_handled") else 0.0 for item in evaluations]
    )
    safe_rejection_rate = _mean(
        [1.0 if item.gating_checks.get("safe_rejection") else 0.0 for item in safe_rejection_cases]
    )
    fallback_success_rate = _mean(
        [1.0 if item.gating_checks.get("fallback_success") else 0.0 for item in fallback_cases]
    )
    passes_all = n_total > 0 and n_total == n_passed

    return {
        "n_total": n_total,
        "n_passed": n_passed,
        "pass_rate": (n_passed / n_total) if n_total else 0.0,
        "path_rmse_mean": _mean(path_rmse_values),
        "path_mae_mean": _mean(path_mae_values),
        "endpoint_abs_error_mean": _mean(endpoint_values),
        "integral_effect_abs_error_mean": _mean(integral_values),
        "band_coverage_mean": _mean(coverage_values),
        "diagnostics_presence_rate": diagnostics_presence_rate,
        "safe_rejection_rate": safe_rejection_rate,
        "fallback_success_rate": fallback_success_rate,
        "n_safe_rejection_cases": len(safe_rejection_cases),
        "n_fallback_cases": len(fallback_cases),
        "passes_all": passes_all,
    }


def build_temporal_backtest_report(
    *,
    report_id: str,
    evaluations: Sequence[TemporalEvaluationResult],
    metadata: Mapping[str, Any] | None = None,
) -> BacktestReport:
    """Pack temporal evaluation scenarios into the standard BacktestReport contract."""

    scenarios = [item.scenario for item in evaluations]
    summary = summarize_temporal_evaluations(evaluations)
    overall_rmse = _mean([scenario.rmse for scenario in scenarios if scenario.rmse is not None])
    overall_mae = _mean([scenario.mae for scenario in scenarios if scenario.mae is not None])
    overall_mape = _mean([scenario.mape for scenario in scenarios if scenario.mape is not None])
    overall_coverage = _mean(
        [
            scenario.coverage_probability
            for scenario in scenarios
            if scenario.coverage_probability is not None
        ]
    )
    return BacktestReport(
        report_id=report_id,
        scenarios=scenarios,
        overall_rmse=overall_rmse,
        overall_mae=overall_mae,
        overall_mape=overall_mape,
        overall_coverage_probability=overall_coverage,
        n_scenarios=len(scenarios),
        n_metrics_evaluated=sum(len(scenario.outcome_comparisons) for scenario in scenarios),
        metadata={
            "temporal_summary": summary,
            **dict(metadata or {}),
        },
    )


def allowed_temporal_rejection_reason_codes() -> tuple[str, ...]:
    return tuple(sorted(_REJECTION_ALLOWED_REASON_CODES))


def _coerce_thresholds(
    value: TemporalThresholds | Mapping[str, float] | None,
) -> TemporalThresholds:
    if value is None:
        return TemporalThresholds()
    if isinstance(value, TemporalThresholds):
        return value
    return TemporalThresholds(**{str(key): value[key] for key in value})


def _coerce_path(values: Sequence[float], *, expected_length: int) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError("expected a one-dimensional temporal path")
    if array.shape[0] != expected_length:
        raise ValueError(
            f"expected temporal path length {expected_length}, got {array.shape[0]}"
        )
    if not np.isfinite(array).all():
        raise ValueError("temporal paths must contain finite values")
    return array


def _evaluate_diagnostics(trajectory: TemporalTrajectoryResult) -> dict[str, Any]:
    diagnostics = dict(trajectory.diagnostics)
    missing_fields: list[str] = []

    solver_family = str(diagnostics.get("solver_family") or trajectory.solver_family).strip()
    if not solver_family:
        missing_fields.append("solver_family")

    dt_value = diagnostics.get("dt")
    try:
        dt_finite = np.isfinite(float(dt_value))
    except Exception:
        dt_finite = False
    if not dt_finite:
        missing_fields.append("dt")

    fallback_mode = str(
        diagnostics.get("fallback_mode") or trajectory.plan.fallback_mode.value
    ).strip()
    if not fallback_mode:
        missing_fields.append("fallback_mode")

    has_discretization_error = False
    discretization_error = diagnostics.get("discretization_error", trajectory.discretization_error)
    try:
        has_discretization_error = np.isfinite(float(discretization_error))
    except Exception:
        has_discretization_error = False
    explicit_note = any(
        str(
            diagnostics.get(
                field,
                trajectory.discretization_note if field == "discretization_note" else "",
            )
        ).strip()
        for field in (
            "discretization_note",
            "discretization_disclosure_note",
            "explicit_note",
        )
    )
    if not (has_discretization_error or explicit_note):
        missing_fields.append("discretization_error_or_note")

    return {
        "solver_family_present": bool(solver_family),
        "dt_present": bool(dt_finite),
        "fallback_mode_present": bool(fallback_mode),
        "discretization_disclosed": bool(has_discretization_error or explicit_note),
        "complete": not missing_fields,
        "missing_fields": missing_fields,
    }


def _thresholds_to_dict(value: TemporalThresholds) -> dict[str, float]:
    output: dict[str, float] = {}
    for field_name in (
        "max_path_rmse",
        "max_path_mae",
        "max_endpoint_abs_error",
        "max_integral_effect_abs_error",
        "min_band_coverage",
    ):
        field_value = getattr(value, field_name)
        if field_value is not None:
            output[field_name] = float(field_value)
    return output


def _mean(values: Sequence[float | None], *, default: float = 0.0) -> float:
    clean = np.asarray([float(value) for value in values if value is not None], dtype=float)
    if clean.size == 0:
        return float(default)
    return float(np.mean(clean))


def _integral(values: np.ndarray, time_grid: np.ndarray) -> float:
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(values, time_grid))
    return float(np.trapz(values, time_grid))


__all__ = [
    "TemporalEvaluationResult",
    "TemporalThresholds",
    "allowed_temporal_rejection_reason_codes",
    "build_temporal_backtest_report",
    "evaluate_temporal_safe_rejection",
    "evaluate_temporal_trajectory",
    "summarize_temporal_evaluations",
]
