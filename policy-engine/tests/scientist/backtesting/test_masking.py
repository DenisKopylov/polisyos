from __future__ import annotations

import pytest

from polisyos.scientist.backtesting.masking import (
    MaskingValidationError,
    OutcomeMasker,
)
from polisyos.scientist.backtesting.plan import HistoricalValidationPlan


def _plan(tmp_path, **overrides) -> HistoricalValidationPlan:
    history_path = tmp_path / "history.json"
    history_path.write_text("{}", encoding="utf-8")
    payload = {
        "plan_id": "masking",
        "historical_data_path": str(history_path),
        "intervention_step": 2,
        "ground_truth_outcomes": {"metric": [1.0, 2.0]},
        "target_metrics": ["metric"],
    }
    payload.update(overrides)
    return HistoricalValidationPlan(**payload)


def test_masking_raises_when_target_metric_is_missing(tmp_path) -> None:
    plan = _plan(tmp_path)

    with pytest.raises(MaskingValidationError, match="missing target metric"):
        OutcomeMasker().mask({}, plan)


def test_masking_raises_when_intervention_step_exceeds_metric_horizon(tmp_path) -> None:
    plan = _plan(tmp_path, intervention_step=5)

    with pytest.raises(MaskingValidationError, match="outside metric"):
        OutcomeMasker().mask({"metric": [1.0, 2.0, 3.0]}, plan)
