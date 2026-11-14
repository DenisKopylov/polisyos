from datetime import date

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.model_input_period_steps import (
    ModelInputPeriodStepProfile,
    ModelInputStepScope,
    derive_model_input_step_scopes,
)
from polisyos.core.contracts.variable_binding import ModelInputScope
from polisyos.ir.kernel import TimeSemantics
from polisyos.ir.model_layer.types import TimeFrequency


def _profile() -> ModelInputPeriodStepProfile:
    return ModelInputPeriodStepProfile()


def _scope_envelope(
    *, start: date = date(2020, 1, 1), end: date = date(2021, 12, 31), basis: str = "calendar_year"
) -> ModelInputScope:
    return ModelInputScope(
        population_ref="population:all",
        geography_ref="geography:usa",
        jurisdiction_ref="jurisdiction:usa",
        period_start=start,
        period_end=end,
        time_role="observation_time",
        period_basis=basis,
    )


def _annual_time() -> TimeSemantics:
    return TimeSemantics(
        frequency=TimeFrequency.YEAR,
        start_date="2020-01-01",
        step_count=2,
    )


def test_derive_step_scopes_uses_time_semantics_and_preserves_non_temporal_axes() -> None:
    scopes = derive_model_input_step_scopes(
        _profile(),
        port_id="period_flow",
        scope_envelope=_scope_envelope(),
        time_semantics=_annual_time(),
        steps=(0, 1),
    )

    assert scopes == (
        ModelInputStepScope(
            port_id="period_flow",
            step=0,
            scope=ModelInputScope(
                population_ref="population:all",
                geography_ref="geography:usa",
                jurisdiction_ref="jurisdiction:usa",
                period_start=date(2020, 1, 1),
                period_end=date(2020, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
        ),
        ModelInputStepScope(
            port_id="period_flow",
            step=1,
            scope=ModelInputScope(
                population_ref="population:all",
                geography_ref="geography:usa",
                jurisdiction_ref="jurisdiction:usa",
                period_start=date(2021, 1, 1),
                period_end=date(2021, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
        ),
    )


def test_partial_supplied_period_keeps_full_required_scope_denominator() -> None:
    scopes = derive_model_input_step_scopes(
        _profile(),
        port_id="period_flow",
        scope_envelope=_scope_envelope(),
        time_semantics=_annual_time(),
        steps=(0, 1),
    )
    supplied_steps = {0}
    missing = tuple(item for item in scopes if item.step not in supplied_steps)

    assert tuple(item.step for item in scopes) == (0, 1)
    assert tuple(item.step for item in missing) == (1,)
    assert missing[0].scope.period_start == date(2021, 1, 1)


@pytest.mark.parametrize("steps", [(0, 0), (0, 2), (1, 0), ()])
def test_steps_must_be_sorted_unique_and_contiguous(steps: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="model_input_step_scope_steps_invalid"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(),
            time_semantics=_annual_time(),
            steps=steps,
        )


def test_non_annual_or_non_calendar_year_model_is_refused() -> None:
    quarterly = TimeSemantics(
        frequency=TimeFrequency.QUARTER,
        start_date="2020-01-01",
        step_count=8,
    )
    with pytest.raises(ValueError, match="model_input_step_scope_frequency_unsupported"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(),
            time_semantics=quarterly,
            steps=(0, 1),
        )

    non_january_start = TimeSemantics(
        frequency=TimeFrequency.YEAR,
        start_date="2020-04-01",
        step_count=2,
    )
    with pytest.raises(ValueError, match="model_input_step_scope_calendar_alignment_unsupported"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(start=date(2020, 4, 1)),
            time_semantics=non_january_start,
            steps=(0, 1),
        )


def test_profile_refuses_unknown_or_rate_like_semantics() -> None:
    with pytest.raises(ValidationError):
        ModelInputPeriodStepProfile(profile_id="annual_calendar_year_rate.v1")


def test_scope_envelope_must_cover_each_derived_period_exactly() -> None:
    with pytest.raises(ValueError, match="model_input_step_scope_outside_envelope"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(end=date(2021, 6, 30)),
            time_semantics=_annual_time(),
            steps=(0, 1),
        )


def test_non_calendar_envelope_is_refused() -> None:
    with pytest.raises(ValueError, match="model_input_step_scope_basis_unsupported"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(basis="fiscal_year"),
            time_semantics=_annual_time(),
            steps=(0, 1),
        )
