from __future__ import annotations

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import KernelModel


class ScheduleSpec(KernelModel):
    start_step: int = Field(..., ge=0)
    end_step: int | None = Field(None, ge=0)
    duration_steps: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ScheduleSpec":
        if self.end_step is None and self.duration_steps is None:
            raise ValueError("end_step or duration_steps must be provided")
        if self.end_step is not None and self.end_step < self.start_step:
            raise ValueError("end_step must be >= start_step")
        if self.end_step is not None and self.duration_steps is not None:
            expected = self.end_step - self.start_step + 1
            if expected != self.duration_steps:
                raise ValueError("end_step and duration_steps mismatch")
        return self


def schedule_range(schedule: ScheduleSpec) -> tuple[int, int]:
    start = schedule.start_step
    if schedule.end_step is None:
        end = start + int(schedule.duration_steps or 0) - 1
    else:
        end = schedule.end_step
    return start, end


__all__ = ["ScheduleSpec", "schedule_range"]
