from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.ir.backtest import BacktestScenario, OutcomeComparison


class PredictionEvaluator:
    """Compare predicted trajectories against observed outcomes."""

    def evaluate(
        self,
        *,
        scenario_id: str,
        scenario_label: str,
        y_pred: dict[str, list[float]],
        y_true: dict[str, list[float]],
        intervals: dict[str, list[tuple[float, float]]] | None = None,
        confidence_level: float = 0.95,
        jurisdiction: str = "",
        intervention_date: str = "",
        data_source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BacktestScenario:
        del confidence_level  # confidence_level is represented by provided intervals
        comparisons: list[OutcomeComparison] = []
        squared_errors: list[float] = []
        absolute_errors: list[float] = []
        percentage_errors: list[float] = []
        within_ci_count = 0
        total_count = 0

        ci_map = intervals or {}

        for metric_name, true_vals in y_true.items():
            pred_vals = y_pred.get(metric_name, [])
            ci_vals = ci_map.get(metric_name, [])
            for idx, y_t in enumerate(true_vals):
                if idx >= len(pred_vals):
                    continue
                y_p = float(pred_vals[idx])
                y_true_val = float(y_t)
                abs_err = float(abs(y_p - y_true_val))
                rel_err = abs_err / abs(y_true_val) if abs(y_true_val) > 1e-12 else None

                lo = None
                hi = None
                within_ci = False
                if idx < len(ci_vals):
                    lo = float(ci_vals[idx][0])
                    hi = float(ci_vals[idx][1])
                    if lo > hi:
                        lo, hi = hi, lo
                    within_ci = bool(lo <= y_true_val <= hi)
                if within_ci:
                    within_ci_count += 1

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
                squared_errors.append(abs_err ** 2)
                absolute_errors.append(abs_err)
                if rel_err is not None:
                    percentage_errors.append(rel_err * 100.0)
                total_count += 1

        rmse = float(np.sqrt(np.mean(squared_errors))) if squared_errors else None
        mae = float(np.mean(absolute_errors)) if absolute_errors else None
        mape = float(np.mean(percentage_errors)) if percentage_errors else None
        coverage = (within_ci_count / total_count) if total_count > 0 else None

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
            metadata=metadata or {},
        )


__all__ = ["PredictionEvaluator"]
