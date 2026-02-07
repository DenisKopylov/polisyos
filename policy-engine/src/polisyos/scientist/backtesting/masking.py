from __future__ import annotations

import copy
from typing import Any

import numpy as np

from polisyos.scientist.backtesting.plan import HistoricalValidationPlan, MaskingStrategy


class OutcomeMasker:
    """Apply post-intervention masking for historical validation."""

    def mask(self, data: dict[str, Any], plan: HistoricalValidationPlan) -> dict[str, Any]:
        masked = copy.deepcopy(data)
        t0 = plan.intervention_step
        if t0 is None:
            return masked

        for metric in plan.target_metrics:
            values = masked.get(metric)
            if not isinstance(values, (list, tuple, np.ndarray)):
                continue
            arr = np.asarray(values, dtype=float)
            if arr.ndim != 1:
                continue
            if t0 >= arr.shape[0]:
                continue
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


__all__ = ["OutcomeMasker"]
