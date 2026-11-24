"""Public backtesting plan module API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.contracts import DataSnapshotRef


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


class KnownAheadCalendarFeature(BaseModel):
    """Recompute ISO weekdays over the declared daily forecast horizon."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    profile: Literal["iso_weekday.daily.v1"]
    output_field: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


class HistoricalReplaySourceSelection(BaseModel):
    """Select the exact historical source and an optional prepared prefix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_data_ref: ArtifactRef
    prepared_snapshot_ref: DataSnapshotRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _verify_selected_profiles(self) -> HistoricalReplaySourceSelection:
        if (
            self.source_data_ref.manifest_profile_sha256 is None
            or self.source_data_ref.media_type != "application/json"
        ):
            raise ValueError("historical replay source must select an exact JSON profile")
        prepared = self.prepared_snapshot_ref
        if prepared is not None and (
            prepared.manifest_profile_sha256 is None
            or prepared.kind != "fabric.data_snapshot"
            or prepared.media_type != "application/json"
        ):
            raise ValueError("prepared history must select an exact DataSnapshot profile")
        return self


class HistoricalValidationPlan(BaseModel):
    """Backtest plan describing one historical validation scenario."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    plan_label: str = ""
    description: str = ""

    historical_data_ref: str | None = None
    historical_data_path: str | None = None
    historical_replay_source: HistoricalReplaySourceSelection | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    intervention_date: str = ""
    intervention_step: int | None = Field(default=None, ge=0)
    pre_intervention_periods: int | None = Field(default=None, ge=0)
    post_intervention_periods: int | None = Field(default=None, ge=0)

    ground_truth_outcomes: dict[str, list[float]] = Field(default_factory=dict)
    target_metrics: list[str] = Field(default_factory=list)
    masking_strategy: MaskingStrategy = MaskingStrategy.DROP_POST
    known_ahead_calendar: KnownAheadCalendarFeature | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

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
    selected_training_role: str | None = Field(default=None, min_length=1)
    selected_validation_role: str | None = Field(default=None, min_length=1)
    selected_holdout_role: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_plan(self) -> HistoricalValidationPlan:
        source = self.historical_replay_source
        if source is None:
            if self.historical_data_ref is None and self.historical_data_path is None:
                raise ValueError("Either historical_data_ref or historical_data_path is required")
        else:
            if self.historical_data_path is not None or (
                self.historical_data_ref is not None
                and self.historical_data_ref != str(source.source_data_ref.artifact_id)
            ):
                raise ValueError("Historical replay source differs from another supplied source")
            if (
                source.prepared_snapshot_ref is not None
                and self.prediction_source is not PredictionSource.SCIENTIST
            ):
                raise ValueError("Prepared history requires Scientist replay")
        if not self.ground_truth_outcomes:
            raise ValueError("ground_truth_outcomes cannot be empty")
        if not self.target_metrics:
            self.target_metrics = sorted(self.ground_truth_outcomes.keys())
        for metric in self.target_metrics:
            if metric not in self.ground_truth_outcomes:
                raise ValueError(f"target metric '{metric}' missing in ground_truth_outcomes")
        if self.known_ahead_calendar is not None and self.known_ahead_calendar.output_field in {
            "time_index",
            "_backtest_metadata",
            *self.target_metrics,
        }:
            raise ValueError("known-ahead calendar field conflicts with a historical field")
        if self.prediction_source == PredictionSource.PROVIDED and not self.predicted_outcomes:
            raise ValueError("prediction_source=provided requires predicted_outcomes")
        if (self.selected_training_role is None) != (self.selected_holdout_role is None):
            raise ValueError("selected training and holdout roles must be supplied together")
        if self.selected_validation_role is not None and (
            self.selected_training_role is None or self.selected_holdout_role is None
        ):
            raise ValueError("validation role requires the complete three-role request")
        selected = {
            "selected_training_role": self.selected_training_role,
            "selected_validation_role": self.selected_validation_role,
            "selected_holdout_role": self.selected_holdout_role,
        }
        supplied = [value for value in selected.values() if value is not None]
        if len(set(supplied)) != len(supplied):
            raise ValueError("selected split roles must be distinct")
        for key, role in selected.items():
            metadata_role = self.metadata.get(key)
            if metadata_role is not None and role is None:
                raise ValueError(f"{key} metadata requires a typed role request")
            if role is not None and metadata_role is not None and metadata_role != role:
                raise ValueError(f"{key} metadata does not match the typed role request")
        return self


__all__ = [
    "ForecastProducerBinding",
    "ForecastProfileContract",
    "HistoricalReplaySourceSelection",
    "HistoricalValidationPlan",
    "KnownAheadCalendarFeature",
    "MaskingStrategy",
    "PredictionSource",
]
