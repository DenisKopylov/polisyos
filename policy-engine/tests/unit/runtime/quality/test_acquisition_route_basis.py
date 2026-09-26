from types import SimpleNamespace

import pytest

from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteClosureError,
    _resolve_source_cycle_problem_basis,
)
from polisyos.runtime.quality.generation_cycle import _problem_ref
from tests.unit.runtime.quality import test_generation_cycle as fixtures


def _chain():
    subject = fixtures._problem("r13_basis_subject")
    revised = subject.model_copy(
        update={
            "runtime_hints": {
                **subject.runtime_hints,
                "r13_revision": "basis-B",
            }
        }
    )
    subject_ref = _problem_ref(subject)
    basis_ref = _problem_ref(revised)
    prior = SimpleNamespace(
        cycle_index=0,
        design_problem_ref=subject_ref,
        design_problem_basis_ref=subject_ref,
        revision_request=SimpleNamespace(revised_problem=revised),
    )
    current = SimpleNamespace(
        cycle_index=1,
        design_problem_ref=subject_ref,
        design_problem_basis_ref=basis_ref,
        revision_request=SimpleNamespace(revised_problem=revised),
    )
    run = SimpleNamespace(design_problem_ref=subject_ref, cycles=(prior, current))
    return subject, revised, subject_ref, basis_ref, prior, current, run


def test_source_basis_is_recomputed_from_same_run_predecessor():
    subject, revised, subject_ref, basis_ref, _prior, current, run = _chain()
    resolved = _resolve_source_cycle_problem_basis(
        generation_run=run,
        source_cycle=current,
        design_problem=subject,
        design_problem_ref=subject_ref,
    )
    assert resolved == revised
    assert _problem_ref(resolved) == basis_ref
    assert subject_ref != basis_ref


def test_mutating_revised_basis_while_subject_and_source_markers_stay_fixed_is_red():
    subject, revised, subject_ref, basis_ref, prior, current, _run = _chain()
    changed = revised.model_copy(
        update={
            "runtime_hints": {
                **revised.runtime_hints,
                "r13_basis_removal_probe": "changed",
            }
        }
    )
    changed_prior = SimpleNamespace(
        cycle_index=prior.cycle_index,
        design_problem_ref=prior.design_problem_ref,
        design_problem_basis_ref=prior.design_problem_basis_ref,
        revision_request=SimpleNamespace(revised_problem=changed),
    )
    changed_run = SimpleNamespace(
        design_problem_ref=subject_ref,
        cycles=(changed_prior, current),
    )
    assert changed_run.design_problem_ref == subject_ref
    assert current.design_problem_ref == subject_ref
    assert current.design_problem_basis_ref == basis_ref
    with pytest.raises(AcquisitionRouteClosureError, match="source_cycle_basis_chain_invalid"):
        _resolve_source_cycle_problem_basis(
            generation_run=changed_run,
            source_cycle=current,
            design_problem=subject,
            design_problem_ref=subject_ref,
        )


def test_missing_predecessor_is_not_guessed_from_next_revision_request():
    subject, _revised, subject_ref, _basis_ref, _prior, current, _run = _chain()
    run_without_prior = SimpleNamespace(
        design_problem_ref=subject_ref,
        cycles=(current,),
    )
    with pytest.raises(
        AcquisitionRouteClosureError,
        match="source_cycle_basis_predecessor_missing",
    ):
        _resolve_source_cycle_problem_basis(
            generation_run=run_without_prior,
            source_cycle=current,
            design_problem=subject,
            design_problem_ref=subject_ref,
        )
