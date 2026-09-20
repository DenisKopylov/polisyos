"""Public backtesting plan module API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MaskingStrategy(str, Enum):
    """How temporal backtests hide post-intervention observations from the evaluator."""

    DROP_POST = "drop_post"
    REPLACE_NAN = "replace_nan"
    TRUNCATE = "truncate"


class PredictionSource(str, Enum):
    """Prediction source public type."""

    PROVIDED = "provided"
    SCIENTIST = "scientist"
    NAIVE = "naive"


class ForecastProducerBinding(BaseModel):
    """Producer identity bound to a forecast profile artifact."""

    model_config = ConfigDict(extra="forbid")

    component: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ForecastProfileContract(BaseModel):
    """Typed contract authorizing a constant forecast trajectory."""

    model_config = ConfigDict(extra="forbid")

    profile: Literal["constant_forecast"]
    producer: ForecastProducerBinding
    estimand: Literal["outcome_trajectory"]
    horizon: int = Field(ge=1)
    time_index: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_time_index(self) -> ForecastProfileContract:
        if len(self.time_index) != self.horizon:
            raise ValueError("forecast profile time_index must match horizon")
        if len(set(self.time_index)) != len(self.time_index):
            raise ValueError("forecast profile time_index must be unique")
        return self


class HistoricalValidationPlan(BaseModel):
    """Backtest plan describing one historical validation scenario."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    plan_label: str = ""
    description: str = ""

    historical_data_ref: str | None = None
    historical_data_path: str | None = None

    intervention_date: str = ""
    intervention_step: int | None = Field(default=None, ge=0)
    pre_intervention_periods: int | None = Field(default=None, ge=0)
    post_intervention_periods: int | None = Field(default=None, ge=0)

    ground_truth_outcomes: dict[str, list[float]] = Field(default_factory=dict)
    target_metrics: list[str] = Field(default_factory=list)
    masking_strategy: MaskingStrategy = MaskingStrategy.DROP_POST

    prediction_source: PredictionSource = PredictionSource.NAIVE
    predicted_outcomes: dict[str, list[float]] | None = None
    prediction_intervals: dict[str, list[tuple[float, float]]] | None = None
    scientist_state: dict[str, Any] | None = None

    policy_spec_ref: str | None = None
    model_spec_ref: str | None = None
    jurisdiction: str = ""

    n_simulation_runs: int = Field(default=1, ge=1)
    random_seed: int | None = None
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_plan(self) -> HistoricalValidationPlan:
        if self.historical_data_ref is None and self.historical_data_path is None:
            raise ValueError("Either historical_data_ref or historical_data_path is required")
        if not self.ground_truth_outcomes:
            raise ValueError("ground_truth_outcomes cannot be empty")
        if not self.target_metrics:
            self.target_metrics = sorted(self.ground_truth_outcomes.keys())
        for metric in self.target_metrics:
            if metric not in self.ground_truth_outcomes:
                raise ValueError(f"target metric '{metric}' missing in ground_truth_outcomes")
        if self.prediction_source == PredictionSource.PROVIDED and not self.predicted_outcomes:
            raise ValueError("prediction_source=provided requires predicted_outcomes")
        return self


__all__ = [
    "ForecastProducerBinding",
    "ForecastProfileContract",
    "HistoricalValidationPlan",
    "MaskingStrategy",
    "PredictionSource",
]
