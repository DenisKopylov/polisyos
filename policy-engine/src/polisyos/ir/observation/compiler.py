"""Declare neutral calibration partitions and negative-control specifications.

This module owns the serializable split/window declarations used to partition
observation panels. Foundry owns calibration-target, placebo, and tensor
materialization in :mod:`polisyos.foundry.calibration.measurement`.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.contracts import ObservationPanel, ObservationRecord
from polisyos.ir.observation.measurement import (
    RegimeCalendar,
    SchemaRegimeRegistry,
    ShockCalendar,
)

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


def _month_add(year: int, month: int, delta_months: int) -> tuple[int, int]:
    total_months = (year * 12 + (month - 1)) + delta_months
    new_year, new_month_zero = divmod(total_months, 12)
    return new_year, new_month_zero + 1


def _shift_period(value: date, time_grain: TimeFrequency, periods: int) -> date:
    if time_grain == TimeFrequency.MONTH:
        year, month = _month_add(value.year, value.month, periods)
        return date(year, month, 1)
    if time_grain == TimeFrequency.QUARTER:
        year, month = _month_add(value.year, value.month, periods * 3)
        return date(year, month, 1)
    if time_grain == TimeFrequency.YEAR:
        return date(value.year + periods, 1, 1)
    raise ValueError(f"Unsupported time grain: {time_grain}")


class CalibrationSplitLabel(str, Enum):
    """Named partition used when building measurement-aware calibration targets."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    HOLDOUT = "holdout"


class CalibrationSplitWindow(KernelModel):
    """Date window assigned to one calibration split label."""

    label: CalibrationSplitLabel
    start_date: date | None = None
    end_date: date | None = None
    reason: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_window(self) -> CalibrationSplitWindow:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be >= start_date")
        return self

    def contains(self, period_start: date, period_end: date) -> bool:
        if self.start_date is not None and period_end < self.start_date:
            return False
        return not (self.end_date is not None and period_start > self.end_date)


class CalibrationSplitPlan(KernelModel):
    """Full partition plan for train, validation, test, and holdout periods."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    windows: list[CalibrationSplitWindow] = Field(default_factory=list)

    def label_for_period(self, period_start: date, period_end: date) -> CalibrationSplitLabel:
        for window in self.windows:
            if window.contains(period_start, period_end):
                return window.label
        return CalibrationSplitLabel.HOLDOUT

    @classmethod
    def default(
        cls,
        *,
        time_grain: TimeFrequency,
        records: list[ObservationRecord],
        holdout_windows: list[CalibrationSplitWindow] | None = None,
    ) -> CalibrationSplitPlan:
        if not records:
            return cls(windows=[])
        latest_start = max(record.period_start for record in records)
        trailing_periods = {
            TimeFrequency.MONTH: 11,
            TimeFrequency.QUARTER: 3,
            TimeFrequency.YEAR: 1,
        }[time_grain]
        test_start = date(2025, 1, 1)
        if latest_start < test_start:
            test_start = _shift_period(latest_start, time_grain, -trailing_periods)
        windows = list(holdout_windows or [])
        windows.extend(
            [
                CalibrationSplitWindow(
                    label=CalibrationSplitLabel.TRAIN,
                    end_date=date(2023, 12, 31),
                    reason="train_pre_2024",
                ),
                CalibrationSplitWindow(
                    label=CalibrationSplitLabel.VALIDATION,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    reason="validation_2024",
                ),
                CalibrationSplitWindow(
                    label=CalibrationSplitLabel.TEST,
                    start_date=test_start,
                    reason="test_2025_or_trailing_12m",
                ),
            ]
        )
        return cls(windows=windows)


class NegativeControlSpec(KernelModel):
    """Specification describing a generated placebo target for falsification."""

    source_target_id: str = Field(..., min_length=1, max_length=180)
    placebo_target_id: str = Field(..., min_length=1, max_length=180)
    shift_periods: int = Field(..., ge=1)
    source_time_axis: tuple[str, ...] = Field(default_factory=tuple)
    placebo_time_axis: tuple[str, ...] = Field(default_factory=tuple)
    notes: list[str] = Field(default_factory=list)


class CalibrationSplitter:
    """Assign observation periods to calibration splits with boundary awareness.

    The splitter can consult schema-regime, regime-calendar, and shock-calendar
    registries so unstable boundary windows are automatically pushed into the
    holdout partition.
    """

    def __init__(
        self,
        *,
        split_plan: CalibrationSplitPlan | None = None,
        schema_regime_registry: SchemaRegimeRegistry | None = None,
        regime_calendar: RegimeCalendar | None = None,
        shock_calendar: ShockCalendar | None = None,
    ) -> None:
        self._split_plan = split_plan
        self._schema_regime_registry = schema_regime_registry
        self._regime_calendar = regime_calendar
        self._shock_calendar = shock_calendar

    def plan_for_panel(self, panel: ObservationPanel) -> CalibrationSplitPlan:
        if self._split_plan is not None:
            return self._split_plan
        return CalibrationSplitPlan.default(time_grain=panel.time_grain, records=panel.records)

    def label_record(
        self, record: ObservationRecord, *, split_plan: CalibrationSplitPlan
    ) -> CalibrationSplitLabel:
        label = split_plan.label_for_period(record.period_start, record.period_end)
        if label in {
            CalibrationSplitLabel.TRAIN,
            CalibrationSplitLabel.VALIDATION,
        } and self._is_boundary(record):
            return CalibrationSplitLabel.HOLDOUT
        return label

    def _is_boundary(self, record: ObservationRecord) -> bool:
        if self._schema_regime_registry is not None:
            if self._schema_regime_registry.is_boundary(
                schema_regime_id=record.schema_regime_id,
                period_start=record.period_start,
                period_end=record.period_end,
                time_grain=record.time_grain,
            ):
                return True
        if self._regime_calendar is not None and self._regime_calendar.is_boundary(
            regime_id=record.regime_id,
            period_start=record.period_start,
            period_end=record.period_end,
            time_grain=record.time_grain,
        ):
            return True
        if self._shock_calendar is not None and self._shock_calendar.is_boundary(
            period_start=record.period_start,
            period_end=record.period_end,
            time_grain=record.time_grain,
            regime_id=record.regime_id,
        ):
            return True
        return bool(record.shock_mask)


__all__ = [
    "CalibrationSplitLabel",
    "CalibrationSplitPlan",
    "CalibrationSplitWindow",
    "CalibrationSplitter",
    "NegativeControlSpec",
]
