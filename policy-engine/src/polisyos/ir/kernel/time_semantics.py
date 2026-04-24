"""Public kernel time semantics module API."""

from __future__ import annotations

import calendar
from datetime import date

from pydantic import Field, model_validator

from ..types import TimeFrequency
from .base import KernelModel


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class TimeSemantics(KernelModel):
    """Time semantics public type."""

    frequency: TimeFrequency
    start_date: str
    step_count: int | None = Field(None, ge=1)
    end_date: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self) -> TimeSemantics:
        start = _parse_date(self.start_date)
        if self.end_date:
            end = _parse_date(self.end_date)
            if end < start:
                raise ValueError("end_date must be >= start_date")
        if self.step_count is None and self.end_date is None:
            raise ValueError("step_count or end_date must be provided")
        return self

    def date_for_step(self, step: int) -> date:
        if step < 0:
            raise ValueError("step must be >= 0")
        start = _parse_date(self.start_date)
        if self.frequency == TimeFrequency.MONTH:
            return _add_months(start, step)
        if self.frequency == TimeFrequency.QUARTER:
            return _add_months(start, step * 3)
        if self.frequency == TimeFrequency.YEAR:
            return _add_months(start, step * 12)
        raise ValueError(f"Unsupported frequency: {self.frequency}")
