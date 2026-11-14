from datetime import date

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.model_input_period_steps import ModelInputStepScope
from polisyos.core.contracts.model_input_step_coverage import (
    ModelInputStepCoverage,
    reconcile_model_input_step_coverage,
)
from polisyos.core.contracts.variable_binding import ModelInputScope


def _step_scope(
    step: int,
    year: int,
    *,
    port_id: str = "period_flow",
    geography_ref: str = "geography:usa",
    time_role: str = "observation_time",
) -> ModelInputStepScope:
    return ModelInputStepScope(
        port_id=port_id,
        step=step,
        scope=ModelInputScope(
            population_ref="population:all",
            geography_ref=geography_ref,
            jurisdiction_ref="jurisdiction:usa",
            period_start=date(year, 1, 1),
            period_end=date(year, 12, 31),
            time_role=time_role,
            period_basis="calendar_year",
        ),
    )


def _required_2020_2021() -> tuple[ModelInputStepScope, ...]:
    return (_step_scope(0, 2020), _step_scope(1, 2021))


def test_full_2020_and_2021_selection_is_complete() -> None:
    required = _required_2020_2021()

    coverage = reconcile_model_input_step_coverage(
        required_step_scopes=required,
        supplied_step_scopes=required,
    )

    assert coverage.required_step_scopes == required
    assert coverage.supplied_step_scopes == required
    assert coverage.missing_step_scopes == ()
    assert coverage.is_complete
    assert coverage.require_complete() is coverage


def test_2020_only_selection_retains_2021_as_missing() -> None:
    required = _required_2020_2021()

    coverage = reconcile_model_input_step_coverage(
        required_step_scopes=required,
        supplied_step_scopes=(required[0],),
    )

    assert coverage.missing_step_scopes == (required[1],)
    assert not coverage.is_complete
    with pytest.raises(ValueError, match="model_input_step_coverage_incomplete"):
        coverage.require_complete()


def test_empty_selection_marks_every_required_scope_missing() -> None:
    required = _required_2020_2021()

    coverage = reconcile_model_input_step_coverage(required_step_scopes=required)

    assert coverage.missing_step_scopes == required
    assert not coverage.is_complete


@pytest.mark.parametrize("field_name", ["required_step_scopes", "supplied_step_scopes"])
def test_duplicate_step_scope_rows_are_rejected(field_name: str) -> None:
    row = _step_scope(0, 2020)
    fields: dict[str, tuple[ModelInputStepScope, ...]] = {
        "required_step_scopes": (row,),
        "supplied_step_scopes": (),
    }
    fields[field_name] = (row, row)

    with pytest.raises(ValidationError, match=r"model_input_step_coverage_.*_duplicate"):
        ModelInputStepCoverage(**fields)


@pytest.mark.parametrize(
    ("field_name", "scope_label"),
    [
        ("required_step_scopes", "required"),
        ("supplied_step_scopes", "supplied"),
    ],
)
def test_step_scope_rows_must_be_sorted_by_port_and_step(field_name: str, scope_label: str) -> None:
    first = _step_scope(0, 2020)
    second = _step_scope(1, 2021)
    fields: dict[str, tuple[ModelInputStepScope, ...]] = {
        "required_step_scopes": (first, second),
        "supplied_step_scopes": (),
    }
    fields[field_name] = (second, first)

    with pytest.raises(
        ValidationError,
        match=f"model_input_step_coverage_{scope_label}_order_invalid",
    ):
        ModelInputStepCoverage(**fields)


@pytest.mark.parametrize(
    "extra_scope",
    [
        _step_scope(0, 2020, port_id="other_port"),
        _step_scope(2, 2022),
    ],
    ids=["foreign-port", "extra-step"],
)
def test_foreign_or_extra_supplied_scope_is_rejected(
    extra_scope: ModelInputStepScope,
) -> None:
    with pytest.raises(
        ValidationError,
        match="model_input_step_coverage_supplied_scope_extra",
    ):
        reconcile_model_input_step_coverage(
            required_step_scopes=(_step_scope(0, 2020),),
            supplied_step_scopes=(extra_scope,),
        )


@pytest.mark.parametrize(
    "mismatched_scope",
    [
        _step_scope(0, 2020, geography_ref="geography:canada"),
        _step_scope(0, 2020, time_role="valid_time"),
    ],
    ids=["geography", "time-role"],
)
def test_same_port_and_step_with_different_scope_is_rejected(
    mismatched_scope: ModelInputStepScope,
) -> None:
    with pytest.raises(
        ValidationError,
        match="model_input_step_coverage_supplied_scope_mismatch",
    ):
        reconcile_model_input_step_coverage(
            required_step_scopes=(_step_scope(0, 2020),),
            supplied_step_scopes=(mismatched_scope,),
        )


def test_sparse_step_numbers_do_not_imply_calendar_years() -> None:
    required = (_step_scope(5, 2020), _step_scope(6, 2021))

    coverage = reconcile_model_input_step_coverage(
        required_step_scopes=required,
        supplied_step_scopes=(required[0],),
    )

    assert coverage.missing_step_scopes == (required[1],)
    assert coverage.missing_step_scopes[0].step == 6
    assert coverage.missing_step_scopes[0].scope.period_start == date(2021, 1, 1)


def test_completeness_cannot_be_asserted_in_constructor() -> None:
    with pytest.raises(ValidationError, match="is_complete"):
        ModelInputStepCoverage(
            required_step_scopes=_required_2020_2021(),
            supplied_step_scopes=(_step_scope(0, 2020),),
            is_complete=True,
        )
