from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.backtesting.masking import (
    MaskingValidationError,
    OutcomeMasker,
)
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalValidationPlan,
    MaskingStrategy,
    PredictionSource,
)


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


def test_scientist_view_excludes_features_without_an_as_of_basis(tmp_path) -> None:
    plan = _plan(tmp_path, prediction_source=PredictionSource.SCIENTIST)
    data = {
        "metric": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["t0", "t1", "t2", "t3"],
        "derived_income": [451.0, 451.0],
        "future_outcome": [1.0, 2.0, 90_000.0, 90_100.0],
    }

    masked = OutcomeMasker().mask(data, plan)

    assert masked["metric"] == [1.0, 2.0]
    assert masked["time_index"] == ["t0", "t1"]
    assert "derived_income" not in masked
    assert "future_outcome" not in masked
    assert data["derived_income"] == [451.0, 451.0]
    assert data["metric"] == [1.0, 2.0, 900.0, 901.0]


def test_scientist_view_recomputes_typed_known_ahead_calendar(tmp_path) -> None:
    plan = _plan(
        tmp_path,
        prediction_source=PredictionSource.SCIENTIST,
        intervention_date="2024-01-05",
        post_intervention_periods=4,
        known_ahead_calendar={"profile": "iso_weekday.daily.v1", "output_field": "weekday"},
    )
    data = {
        "metric": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["2024-01-03", "2024-01-04", "2024-01-05", "UNAVAILABLE"],
        "weekday": [451.0, 451.0],
    }

    masked = OutcomeMasker().mask(data, plan)

    assert masked["weekday"] == [5, 6, 7, 1]
    assert data["weekday"] == [451.0, 451.0]
    assert masked["time_index"] == ["2024-01-03", "2024-01-04"]
    assert masked["_backtest_metadata"]["known_ahead_calendar"] == {
        "profile": "iso_weekday.daily.v1",
        "output_field": "weekday",
        "origin": "2024-01-05",
        "horizon": 4,
    }


def test_scientist_replace_nan_preserves_shape_without_future_coordinates(tmp_path) -> None:
    plan = _plan(
        tmp_path,
        prediction_source=PredictionSource.SCIENTIST,
        masking_strategy=MaskingStrategy.REPLACE_NAN,
    )
    data = {
        "metric": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["t0", "t1", "t2", "t3"],
    }

    masked = OutcomeMasker().mask(data, plan)

    assert masked["metric"][:2] == [1.0, 2.0]
    assert all(math.isnan(value) for value in masked["metric"][2:])
    assert masked["time_index"] == ["t0", "t1", None, None]
    assert data["time_index"] == ["t0", "t1", "t2", "t3"]


@pytest.mark.parametrize(
    "time_index",
    [
        ["t0", "t1", "t3", "t4"],
        ["t0", "t1", "t2", "t2"],
    ],
    ids=["missing_date", "duplicate_date"],
)
def test_masking_rejects_unresolved_or_ambiguous_intervention_date(
    tmp_path,
    time_index,
) -> None:
    plan = _plan(tmp_path, intervention_step=2, intervention_date="t2")

    with pytest.raises(MaskingValidationError, match="intervention_date"):
        OutcomeMasker().mask(
            {"metric": [1.0, 2.0, 900.0, 901.0], "time_index": time_index},
            plan,
        )


def test_masking_rejects_disagreeing_step_and_pre_periods(tmp_path) -> None:
    plan = _plan(tmp_path, intervention_step=1, pre_intervention_periods=2)

    with pytest.raises(MaskingValidationError) as exc_info:
        OutcomeMasker().mask(
            {"metric": [1.0, 2.0, 900.0, 901.0]},
            plan,
        )

    assert exc_info.value.code == "intervention_cutoff_mismatch"
