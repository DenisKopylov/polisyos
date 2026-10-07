"""Compare replay predictions against held-out outcomes and produce backtest scenarios."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from polisyos.ir.analytics.backtest import BacktestScenario, OutcomeComparison


class PredictionEvaluator:
    """Compute per-metric replay errors and interval coverage for one scenario."""

    def evaluate(
        self,
        *,
        scenario_id: str,
        scenario_label: str,
        y_pred: dict[str, list[float]],
        y_true: dict[str, list[float]],
        intervals: dict[str, list[tuple[float, float]]] | None = None,
        confidence_level: float | None = 0.95,
        jurisdiction: str = "",
        intervention_date: str = "",
        data_source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BacktestScenario:
        """Build a `BacktestScenario` from predicted and ground-truth trajectories.

        Args:
            scenario_id: Stable scenario identifier used in the final report.
            scenario_label: Human-readable scenario name.
            y_pred: Predicted metric trajectories keyed by metric name.
            y_true: Ground-truth trajectories keyed by metric name.
            intervals: Optional per-step confidence intervals aligned with `y_pred`.
            confidence_level: Nominal confidence level requested for the intervals;
                ``None`` is reserved for non-statistical persisted bounds.
            jurisdiction: Scenario jurisdiction metadata.
            intervention_date: Historical intervention cutoff used by masking.
            data_source: Source path/ref metadata.
            metadata: Optional extra scenario metadata.

        Returns:
            `BacktestScenario` with per-point comparisons and aggregate RMSE/MAE/
            MAPE/coverage metrics.
        """
        if confidence_level is not None:
            confidence_level = float(confidence_level)
            if not math.isfinite(confidence_level) or not 0.0 < confidence_level < 1.0:
                raise ValueError("confidence_level must be finite and between 0 and 1")

        comparisons: list[OutcomeComparison] = []
        squared_errors: list[float] = []
        absolute_errors: list[float] = []
        percentage_errors: list[float] = []
        missing_cells: list[tuple[str, int]] = []
        invalid_cells: list[tuple[str, int]] = []
        requested_count = 0
        observed_count = 0
        compared_count = 0
        missing_count = 0
        invalid_count = 0
        interval_requested_count = 0
        interval_available_count = 0
        interval_evaluated_count = 0
        interval_hit_count = 0

        ci_map = intervals or {}
        interval_contract_declared = bool(ci_map)

        for metric_name, true_vals in y_true.items():
            pred_raw = y_pred.get(metric_name, [])
            pred_vals = pred_raw if isinstance(pred_raw, (list, tuple)) else []
            ci_raw = ci_map.get(metric_name, [])
            ci_vals = ci_raw if isinstance(ci_raw, (list, tuple)) else []
            for idx, y_t_raw in enumerate(true_vals):
                requested_count += 1
                try:
                    observed_count += int(math.isfinite(float(y_t_raw)))
                except (TypeError, ValueError, OverflowError):
                    pass
                if interval_contract_declared:
                    interval_requested_count += 1
                if idx >= len(pred_vals):
                    missing_count += 1
                    missing_cells.append((metric_name, idx))
                    continue

                try:
                    y_p = float(pred_vals[idx])
                    y_true_val = float(y_t_raw)
                except (TypeError, ValueError, OverflowError):
                    invalid_count += 1
                    invalid_cells.append((metric_name, idx))
                    continue
                if not math.isfinite(y_p) or not math.isfinite(y_true_val):
                    invalid_count += 1
                    invalid_cells.append((metric_name, idx))
                    continue

                abs_err = float(abs(y_p - y_true_val))
                rel_err = abs_err / abs(y_true_val) if abs(y_true_val) > 1e-12 else None
                squared_error = abs_err**2
                if not math.isfinite(abs_err) or not math.isfinite(squared_error):
                    invalid_count += 1
                    invalid_cells.append((metric_name, idx))
                    continue
                if rel_err is not None and not math.isfinite(rel_err):
                    rel_err = None
                percentage_error = rel_err * 100.0 if rel_err is not None else None
                if percentage_error is not None and not math.isfinite(percentage_error):
                    rel_err = None
                    percentage_error = None

                lo = None
                hi = None
                within_ci: bool | None = None
                if idx < len(ci_vals):
                    try:
                        lo = float(ci_vals[idx][0])
                        hi = float(ci_vals[idx][1])
                    except (TypeError, ValueError, IndexError, OverflowError):
                        lo = None
                        hi = None
                    if (
                        lo is not None
                        and hi is not None
                        and math.isfinite(lo)
                        and math.isfinite(hi)
                    ):
                        if lo > hi:
                            lo, hi = hi, lo
                        interval_available_count += 1
                        interval_evaluated_count += 1
                        within_ci = bool(lo <= y_true_val <= hi)
                        if within_ci:
                            interval_hit_count += 1
                    else:
                        lo = None
                        hi = None

                comparisons.append(
                    OutcomeComparison(
                        metric_name=metric_name,
                        y_pred=y_p,
                        y_true=y_true_val,
                        absolute_error=abs_err,
                        relative_error=rel_err,
                        within_ci=within_ci,
                        ci_lower=lo,
                        ci_upper=hi,
                    )
                )
                squared_errors.append(squared_error)
                absolute_errors.append(abs_err)
                if percentage_error is not None:
                    percentage_errors.append(percentage_error)
                compared_count += 1

        rmse = float(np.sqrt(np.mean(squared_errors))) if squared_errors else None
        mae = float(np.mean(absolute_errors)) if absolute_errors else None
        mape = float(np.mean(percentage_errors)) if percentage_errors else None
        coverage = (
            interval_hit_count / interval_evaluated_count if interval_evaluated_count > 0 else None
        )
        interval_availability = (
            interval_available_count / interval_requested_count
            if interval_requested_count > 0
            else None
        )
        interval_hit_rate = (
            interval_hit_count / interval_evaluated_count if interval_evaluated_count > 0 else None
        )
        metadata_payload = dict(metadata or {})
        metadata_payload["evaluation_status"] = "evaluated" if compared_count else "not_evaluated"
        metadata_payload["comparison_denominator"] = {
            "requested": requested_count,
            "eligible": compared_count,
            "observed": observed_count,
            "unit": "metric_time_cell",
            "basis": "recomputed",
        }
        interval_type = metadata_payload.get("interval_type")
        if interval_type is not None and not isinstance(interval_type, str):
            interval_type = str(interval_type)

        return BacktestScenario(
            scenario_id=scenario_id,
            scenario_label=scenario_label,
            jurisdiction=jurisdiction,
            intervention_date=intervention_date,
            data_source=data_source,
            outcome_comparisons=comparisons,
            rmse=rmse,
            mae=mae,
            mape=mape,
            coverage_probability=coverage,
            requested_count=requested_count,
            compared_count=compared_count,
            missing_count=missing_count,
            invalid_count=invalid_count,
            missing_cells=missing_cells,
            invalid_cells=invalid_cells,
            interval_requested_count=interval_requested_count,
            interval_available_count=interval_available_count,
            interval_evaluated_count=interval_evaluated_count,
            interval_hit_count=interval_hit_count,
            interval_availability=interval_availability,
            interval_hit_rate=interval_hit_rate,
            nominal_confidence_level=confidence_level,
            interval_type=interval_type,
            squared_error_sum=float(sum(squared_errors)),
            absolute_error_sum=float(sum(absolute_errors)),
            percentage_error_sum=float(sum(percentage_errors)),
            percentage_error_count=len(percentage_errors),
            metadata=metadata_payload,
        )


__all__ = ["PredictionEvaluator"]
