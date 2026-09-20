from __future__ import annotations

import pytest
from polisyos.scientist.methods.backtesting.masking import (
    MaskingValidationError,
    OutcomeMasker,
)
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan


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


def test_masking_uses_declared_pre_intervention_periods_when_step_is_missing(tmp_path) -> None:
    plan = _plan(
        tmp_path,
        intervention_step=None,
        intervention_date="t2",
        pre_intervention_periods=2,
    )
    data = {
        "metric": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["t0", "t1", "t2", "t3"],
    }

    masked = OutcomeMasker().mask(data, plan)

    assert masked["metric"] == [1.0, 2.0]
    assert masked["time_index"] == ["t0", "t1"]
    assert data["metric"] == [1.0, 2.0, 900.0, 901.0]
