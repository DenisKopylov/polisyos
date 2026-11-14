"""Actual selected-model clock and origin checks for temporal input subjects."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactID, FileSystemCAS
from polisyos.core.contracts.model_input_requirements import (
    load_model_input_obligation_set,
)
from polisyos.core.contracts.semantic_step_binding import resolve_model_input_step_scope
from polisyos.core.contracts.variable_binding import ModelInputScope
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.ir.kernel.time_semantics import TimeFrequency, TimeSemantics
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context,
    _interface,
    _preflight,
)


def _two_year_preflight(tmp_path: Path):
    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        period_step_profile=True,
        time_semantics=TimeSemantics(
            frequency=TimeFrequency.YEAR,
            start_date="2020-01-01",
            step_count=2,
        ),
        scope=ModelInputScope(
            population_ref="population:government",
            geography_ref="UA",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2020, 1, 1),
            period_end=date(2021, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
    )
    try:
        preflight = _preflight(case, _interface(case), _context(case), steps=(0, 1))
    except BaseException:
        case.close()
        raise
    return case, preflight


def test_temporal_step_subject_reopens_full_original_set_and_clock(tmp_path: Path) -> None:
    case, preflight = _two_year_preflight(tmp_path)
    try:
        fresh_store = FileSystemCAS(case.store.root)
        selected_set, members = load_model_input_obligation_set(
            fresh_store, preflight.obligation_set_ref
        )
        (obligation_ref,) = selected_set.obligation_refs
        assert members[0].dependencies[0].required_steps == (0, 1)
        scopes = selected_set.required_step_scopes
        assert scopes is not None
        resolved = tuple(
            resolve_model_input_step_scope(
                fresh_store,
                obligation_set_ref=preflight.obligation_set_ref,
                model_input_obligation_ref=obligation_ref,
                step_scope=scope,
            )
            for scope in scopes
        )
        assert tuple((row.step, row.scope.period_start.year) for row in resolved) == (
            (0, 2020),
            (1, 2021),
        )
        assert members[0].port.scope.period_end == date(2021, 12, 31)
        assert resolved[0].scope.period_end == date(2020, 12, 31)
    finally:
        case.close()


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("foreign_obligation", "model_input_step_selection_origin_not_member"),
        ("foreign_port", "model_input_step_selection_origin_port_mismatch"),
        ("outside_step", "model_input_step_selection_step_not_required"),
        ("foreign_geography", "model_input_step_selection_scope_mismatch"),
        ("envelope_as_scope", "model_input_step_selection_scope_mismatch"),
    ],
)
def test_temporal_step_subject_refuses_coordinate_or_origin_grafts(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    case, preflight = _two_year_preflight(tmp_path)
    try:
        fresh_store = FileSystemCAS(case.store.root)
        selected_set, members = load_model_input_obligation_set(
            fresh_store, preflight.obligation_set_ref
        )
        (obligation_ref,) = selected_set.obligation_refs
        assert selected_set.required_step_scopes is not None
        scope = selected_set.required_step_scopes[0]
        if mutation == "foreign_obligation":
            obligation_ref = obligation_ref.model_copy(
                update={"artifact_id": ArtifactID.from_sha256_hex("f" * 64)}
            )
        elif mutation == "foreign_port":
            scope = scope.model_copy(update={"port_id": "foreign.value"})
        elif mutation == "outside_step":
            scope = scope.model_copy(update={"step": 2})
        elif mutation == "foreign_geography":
            scope = scope.model_copy(
                update={"scope": scope.scope.model_copy(update={"geography_ref": "foreign"})}
            )
        else:
            scope = scope.model_copy(update={"scope": members[0].port.scope})
        with pytest.raises(ValueError, match=f"^{expected}$"):
            resolve_model_input_step_scope(
                fresh_store,
                obligation_set_ref=preflight.obligation_set_ref,
                model_input_obligation_ref=obligation_ref,
                step_scope=scope,
            )
    finally:
        case.close()
