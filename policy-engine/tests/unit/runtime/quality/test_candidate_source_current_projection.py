"""Candidate-basis history preserves prior facts without lending their authority."""

from __future__ import annotations

import pytest

from polisyos.runtime.quality import generation_cycle as cycle_module
from polisyos.runtime.quality.generation_cycle import (
    CandidateSourceCurrentProjection,
    GenerationCycleController,
    GenerationCycleRun,
    PendingN8ValuePort,
    project_candidate_source_current_occurrences,
    validate_generation_cycle_run_history,
)
from tests._helpers.controlled_candidate_profile import _budget, _CgfGenerationPort, _problem
from tests.unit.runtime.quality.test_candidate_source_reentry import (
    _AcquisitionRequiredGrounding,
    _intrinsic_v9_history,
)


@pytest.mark.asyncio
async def test_declared_candidate_basis_projects_old_occurrences_without_mutating_history() -> None:
    """A synthetic declared edge exercises projection, not acquisition-owner custody."""
    source = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        grounding_port=_AcquisitionRequiredGrounding(),
        value_port=PendingN8ValuePort(),
        authority_scope="contract_testing",
    ).run(_problem("candidate_basis_current_projection"), budget_state=_budget(), max_cycles=1)
    selected = next(
        row
        for row in source.candidate_summaries
        if row.candidate_id == source.cycles[0].selected_candidate_ref
    )
    historical = selected.model_copy(
        update={
            "front": "decision",
            "certified_by_n9": True,
            "value_status": "value_ready",
            "value_decision_grade": "high",
            "value_ref": "value://old-basis",
            "high_proxy": False,
            "low_grounding": False,
        }
    )
    other = historical.model_copy(
        update={"candidate_id": "other-prior-candidate", "content_hash": "sha256:" + "d" * 64}
    )
    quarantined = historical.model_copy(
        update={
            "candidate_id": "quarantined-prior-candidate",
            "content_hash": "sha256:" + "e" * 64,
            "front": "quarantine",
            "certified_by_n9": False,
        }
    )
    source = source.model_copy(
        update={
            "candidate_summaries": (historical, other, quarantined),
            "fronts": cycle_module._derive_fronts((historical, other, quarantined)),
        }
    )
    declared, _ = _intrinsic_v9_history(source)
    target = declared.candidate_summaries[-1].model_copy(
        update={
            "front": "research",
            "certified_by_n9": False,
            "value_status": "value_pending_n8",
            "value_decision_grade": None,
            "value_ref": None,
            "value_blockers": (),
            "adversarial_validation_status": "not_required",
        }
    )
    target = cycle_module._summary_with_value_observation(
        target,
        simulation=declared.cycles[-1].simulation,
        value_port=declared.cycles[-1].value_port,
        counterexample_ref=declared.cycles[-1].counterexample.counterexample_ref,
    )
    summaries = (*declared.candidate_summaries[:-1], target)
    fronts = cycle_module._derive_candidate_source_fronts(summaries, declared.basis_transitions)
    declared = GenerationCycleRun.model_validate(
        declared.model_copy(update={"candidate_summaries": summaries, "fronts": fronts}).model_dump(
            mode="json"
        )
    )
    assert declared.candidate_summaries[:3] == source.candidate_summaries
    issues = validate_generation_cycle_run_history(declared.model_dump(mode="json"))
    assert issues == (), issues

    rows = cycle_module._declared_candidate_source_current_occurrences(
        declared.candidate_summaries, declared.basis_transitions
    )
    by_id = {row.recorded.candidate_id: row for row in rows}
    assert by_id[selected.candidate_id].recorded == target
    assert by_id[selected.candidate_id].basis_status == "recorded_on_selected_basis"
    assert by_id[other.candidate_id].recorded == other
    assert by_id[other.candidate_id].basis_status == "prior_basis_not_revalidated"
    assert by_id[other.candidate_id].effective_front == "research"
    assert not by_id[other.candidate_id].effective_certified_by_n9
    assert by_id[other.candidate_id].effective_value_status == "value_pending_n8"
    assert by_id[other.candidate_id].effective_value_ref is None
    assert by_id[quarantined.candidate_id].effective_front == "quarantine"
    assert not fronts.decision.candidate_ids
    assert set(fronts.research.candidate_ids) == {selected.candidate_id, other.candidate_id}

    forged_front = declared.model_copy(update={"fronts": cycle_module._derive_fronts(summaries)})
    codes = {
        issue["code"]
        for issue in validate_generation_cycle_run_history(forged_front.model_dump(mode="json"))
    }
    assert "candidate_source_basis_current_front_mismatch" in codes

    for altered_rows in (
        (),
        (target.model_copy(update={"candidate_id": "foreign-target"}),),
        (target.model_copy(update={"content_hash": "sha256:" + "f" * 64}),),
        (target, target.model_copy(update={"content_hash": "sha256:" + "a" * 64})),
        (target.model_copy(update={"value_blockers": ("forged-value",)}),),
        (
            target,
            target.model_copy(update={"cycle_index": 2, "content_hash": "sha256:" + "9" * 64}),
        ),
    ):
        forged = declared.model_copy(
            update={"candidate_summaries": (*summaries[:-1], *altered_rows)}
        )
        codes = {
            issue["code"]
            for issue in validate_generation_cycle_run_history(forged.model_dump(mode="json"))
        }
        assert "candidate_source_basis_summary_binding_mismatch" in codes

    superseded = target.model_copy(
        update={
            "content_hash": "sha256:" + "c" * 64,
            "front": "decision",
            "certified_by_n9": True,
            "value_status": "value_ready",
            "value_ref": "value://forged-candidate-basis",
        }
    )
    forged_history = declared.model_copy(
        update={"candidate_summaries": (*summaries[:-1], superseded, target)}
    )
    codes = {
        issue["code"]
        for issue in validate_generation_cycle_run_history(forged_history.model_dump(mode="json"))
    }
    assert "candidate_source_basis_transition_claims_current_authority" in codes


def test_candidate_current_projection_rejects_caller_supplied_owner_and_rows() -> None:
    """A caller-shaped resolver cannot supply a verified source fold."""

    class FakeOwner:
        def resolve_current_route(self, *, run_id: str) -> object:
            raise AssertionError(f"untrusted resolver called: {run_id}")

    unavailable = project_candidate_source_current_occurrences(
        route_owner=FakeOwner(), run_id="run:fake"
    )
    assert unavailable.status == "not_established"
    assert unavailable.fronts is None and unavailable.occurrences == ()
    assert unavailable.issues == ({"code": "candidate_source_current_owner_not_established"},)
    with pytest.raises(ValueError, match="candidate_source_current_unavailable_binding_mismatch"):
        CandidateSourceCurrentProjection(
            status="not_established",
            generation_run_content_hash="sha256:" + "a" * 64,
            issues=({"code": "missing_owner"},),
        )
