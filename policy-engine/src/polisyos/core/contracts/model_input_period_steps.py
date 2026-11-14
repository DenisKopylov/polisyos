"""Typed calendar-period scopes for step-selected model inputs."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.variable_binding import ModelInputScope
from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.model_layer.types import TimeFrequency


class ModelInputPeriodStepProfile(BaseModel):
    """The bounded temporal semantics selected by an opt-in model input port."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.2"] = "1.2"
    profile_id: Literal["annual_calendar_year_period_total.v1"] = (
        "annual_calendar_year_period_total.v1"
    )


class ModelInputStepScope(BaseModel):
    """One exact model-input scope recomputed for a selected execution step."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    port_id: str = Field(min_length=1, strict=True)
    step: Annotated[int, Field(ge=0, strict=True)]
    scope: ModelInputScope


def derive_model_input_step_scopes(
    profile: ModelInputPeriodStepProfile,
    *,
    port_id: str,
    scope_envelope: ModelInputScope,
    time_semantics: TimeSemantics,
    steps: tuple[int, ...],
) -> tuple[ModelInputStepScope, ...]:
    """Derive exact annual period-total scopes from the selected model clock.

    This profile deliberately supports only contiguous calendar-year steps.
    The port's original scope is treated as a coverage envelope only when the
    explicit profile is selected; callers must retain the port declaration
    unchanged and use these recomputed scopes for per-step source matching.
    """
    if profile.profile_id != "annual_calendar_year_period_total.v1":
        raise ValueError("model_input_step_scope_profile_unsupported")
    if time_semantics.frequency != TimeFrequency.YEAR:
        raise ValueError("model_input_step_scope_frequency_unsupported")
    if scope_envelope.period_basis != "calendar_year":
        raise ValueError("model_input_step_scope_basis_unsupported")
    if (
        not steps
        or any(type(step) is not int or step < 0 for step in steps)
        or tuple(sorted(set(steps))) != steps
        or steps != tuple(range(steps[0], steps[-1] + 1))
    ):
        raise ValueError("model_input_step_scope_steps_invalid")

    derived: list[ModelInputStepScope] = []
    for step in steps:
        if time_semantics.step_count is not None and step >= time_semantics.step_count:
            raise ValueError("model_input_step_scope_step_outside_horizon")
        start = time_semantics.date_for_step(step)
        next_start = time_semantics.date_for_step(step + 1)
        end = date.fromordinal(next_start.toordinal() - 1)
        if (
            start.month != 1
            or start.day != 1
            or next_start.month != 1
            or next_start.day != 1
            or end.month != 12
            or end.day != 31
        ):
            raise ValueError("model_input_step_scope_calendar_alignment_unsupported")
        if time_semantics.end_date is not None and end > date.fromisoformat(
            time_semantics.end_date
        ):
            raise ValueError("model_input_step_scope_step_outside_horizon")
        if (
            start < scope_envelope.period_start
            or end > scope_envelope.period_end
        ):
            raise ValueError("model_input_step_scope_outside_envelope")
        exact_scope = ModelInputScope.model_validate(
            {
                **scope_envelope.model_dump(mode="python"),
                "period_start": start,
                "period_end": end,
            }
        )
        derived.append(ModelInputStepScope(port_id=port_id, step=step, scope=exact_scope))
    return tuple(derived)
