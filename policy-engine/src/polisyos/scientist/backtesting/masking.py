"""Public backtesting masking module API."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.scientist.backtesting.plan import HistoricalValidationPlan, MaskingStrategy


class MaskingValidationError(PolicyOSError):
    """Raised when post-intervention masking cannot be applied safely."""

    default_stage = "scientist.backtesting.masking"
    default_category = ErrorCategory.VALIDATION


class OutcomeMasker:
    """Apply post-intervention masking for historical validation."""

    def mask(self, data: dict[str, Any], plan: HistoricalValidationPlan) -> dict[str, Any]:
        masked = copy.deepcopy(data)
        t0 = plan.intervention_step
        if t0 is None:
            return masked

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
            if plan.masking_strategy in {MaskingStrategy.DROP_POST, MaskingStrategy.TRUNCATE}:
                masked[metric] = arr[:t0].tolist()
            elif plan.masking_strategy is MaskingStrategy.REPLACE_NAN:
                arr = arr.copy()
                arr[t0:] = np.nan
                masked[metric] = arr.tolist()

        masked.setdefault("_backtest_metadata", {})
        masked["_backtest_metadata"].update(
            {
                "masked": True,
                "intervention_step": t0,
                "masking_strategy": plan.masking_strategy.value,
            }
        )
        return masked


__all__ = ["MaskingValidationError", "OutcomeMasker"]
