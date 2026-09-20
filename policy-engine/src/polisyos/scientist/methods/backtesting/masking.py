"""Public backtesting masking module API."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, MaskingStrategy


class MaskingValidationError(PolicyOSError):
    """Raised when post-intervention masking cannot be applied safely."""

    default_stage = "scientist.backtesting.masking"
    default_category = ErrorCategory.VALIDATION


class OutcomeMasker:
    """Apply post-intervention masking for historical validation."""

    def mask(self, data: dict[str, Any], plan: HistoricalValidationPlan) -> dict[str, Any]:
        masked = copy.deepcopy(data)
        t0 = self._resolve_cutoff(masked, plan)
        if t0 is None:
            return masked

        time_index = masked.get("time_index")
        if time_index is not None and not isinstance(time_index, (list, tuple, np.ndarray)):
            raise MaskingValidationError(
                "Historical time_index must be a one-dimensional sequence",
                code="invalid_time_index_type",
                details={"type": type(time_index).__name__},
            )

        for metric in plan.target_metrics:
            if metric not in masked:
                raise MaskingValidationError(
                    f"Historical payload missing target metric {metric!r}",
                    code="missing_target_metric",
                    details={"metric": metric},
                )
            values = masked.get(metric)
            if not isinstance(values, (list, tuple, np.ndarray)):
                raise MaskingValidationError(
                    f"Target metric {metric!r} must be a 1D numeric sequence",
                    code="invalid_metric_type",
                    details={"metric": metric, "type": type(values).__name__},
                )
            try:
                arr = np.asarray(values, dtype=float)
            except (TypeError, ValueError) as exc:
                raise MaskingValidationError(
                    f"Target metric {metric!r} must be coercible to float values",
                    code="non_numeric_metric",
                    details={"metric": metric},
                ) from exc
            if arr.ndim != 1:
                raise MaskingValidationError(
                    f"Target metric {metric!r} must be one-dimensional",
                    code="invalid_metric_shape",
                    details={"metric": metric, "ndim": int(arr.ndim)},
                )
            if t0 >= arr.shape[0]:
                raise MaskingValidationError(
                    f"intervention_step {t0} is outside metric {metric!r} horizon",
                    code="intervention_step_out_of_range",
                    details={
                        "metric": metric,
                        "intervention_step": t0,
                        "length": int(arr.shape[0]),
                    },
                )
            if time_index is not None and len(time_index) != arr.shape[0]:
                raise MaskingValidationError(
                    f"time_index length does not match metric {metric!r}",
                    code="time_index_length_mismatch",
                    details={
                        "metric": metric,
                        "metric_length": int(arr.shape[0]),
                        "time_index_length": len(time_index),
                    },
                )
            if plan.masking_strategy in {MaskingStrategy.DROP_POST, MaskingStrategy.TRUNCATE}:
                masked[metric] = arr[:t0].tolist()
            elif plan.masking_strategy is MaskingStrategy.REPLACE_NAN:
                arr = arr.copy()
                arr[t0:] = np.nan
                masked[metric] = arr.tolist()

        if time_index is not None and plan.masking_strategy in {
            MaskingStrategy.DROP_POST,
            MaskingStrategy.TRUNCATE,
        }:
            masked["time_index"] = np.asarray(time_index)[:t0].tolist()

        masked.setdefault("_backtest_metadata", {})
        masked["_backtest_metadata"].update(
            {
                "masked": True,
                "intervention_step": t0,
                "masking_strategy": plan.masking_strategy.value,
            }
        )
        return masked

    @staticmethod
    def _resolve_cutoff(
        data: dict[str, Any], plan: HistoricalValidationPlan
    ) -> int | None:
        """Resolve the cutoff from the plan's declared temporal contract."""
        t0 = plan.intervention_step
        if t0 is None and plan.pre_intervention_periods is not None:
            t0 = plan.pre_intervention_periods

        if plan.intervention_date:
            time_index = data.get("time_index")
            date_matches: list[int] = []
            if isinstance(time_index, (list, tuple, np.ndarray)):
                for index, value in enumerate(time_index):
                    if value == plan.intervention_date or str(value) == plan.intervention_date:
                        date_matches.append(index)
            if len(date_matches) != 1:
                if t0 is None:
                    raise MaskingValidationError(
                        "intervention_date requires one matching time_index value",
                        code="intervention_date_unresolved",
                        details={
                            "intervention_date": plan.intervention_date,
                            "matches": date_matches,
                        },
                    )
            elif t0 is None:
                t0 = date_matches[0]
            elif t0 != date_matches[0]:
                raise MaskingValidationError(
                    "intervention_date and pre-intervention cutoff disagree",
                    code="intervention_cutoff_mismatch",
                    details={
                        "intervention_date": plan.intervention_date,
                        "date_cutoff": date_matches[0],
                        "declared_cutoff": t0,
                    },
                )

        return t0


__all__ = ["MaskingValidationError", "OutcomeMasker"]
