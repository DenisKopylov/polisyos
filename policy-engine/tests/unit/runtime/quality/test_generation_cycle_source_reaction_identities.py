"""Exercise the real diagnostic producers for retained source reactions."""

from __future__ import annotations

from typing import NamedTuple

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality import generation_cycle as gc
from tests._helpers.controlled_candidate_profile import _budget, _problem


class _Chain(NamedTuple):
    counterexample: gc.CounterexampleRecord
    revision: gc.DesignRevisionRequest
    decision: gc.RefinementDecision
    iteration: gc.SearchIteration


def _basis(*, digest: str = "a", profile: str = "b") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + digest * 64,
        kind="runtime_quality.acquisition_evaluation_basis",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + profile * 64,
    )


def _chain(
    *,
    ref: ArtifactRef | None = None,
    case_id: str = "reaction_case",
    candidate_id: str = "candidate-a",
    cycle_index: int = 2,
    issue: str = "missing_measurement",
    reason: str = "current_budget_attention_limit",
) -> _Chain:
    problem = _problem(case_id)
    grounding = gc.CandidateGroundingObservation(
        candidate_id=candidate_id,
        status="grounding_gap",
        grounding_score=0.0,
        issue_codes=(issue,),
    )
    value = gc.ValuePortObservation(candidate_id=candidate_id)
    counterexample = gc._counterexample_record(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=candidate_id,
        grounding=grounding,
        value_port=value,
        source_reaction_ref=ref,
    )
    revision = gc._default_revision_request(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=candidate_id,
        terminal_kind="human_decision_required",
        counterexample=counterexample,
        grounding=grounding,
        value_port=value,
        source_reaction_ref=ref,
    )
    next_action = gc.LoopVOIDecision(
        candidate_id=candidate_id,
        terminal_kind="human_decision_required",
        scheduler_action="escalate",
        scheduler_reason=reason,
        priority=0.0,
        next_action="escalate",
        reason=reason,
    )
    decision = gc._refinement_decision(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=candidate_id,
        counterexample=counterexample,
        revision=revision,
        next_action=next_action,
        source_reaction_ref=ref,
    )
    iteration = gc._search_iteration(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=candidate_id,
        counterexample=counterexample,
        decision=decision,
        next_action=next_action,
        source_reaction_ref=ref,
    )
    return _Chain(counterexample, revision, decision, iteration)


def _identifiers(chain: _Chain) -> tuple[str | None, ...]:
    return (
        chain.counterexample.counterexample_id,
        chain.counterexample.counterexample_ref,
        chain.counterexample.diagnostic.diagnostic_id,
        chain.revision.revision_id,
        chain.decision.decision_id,
        chain.decision.decision_ref,
        chain.decision.value_of_information.estimate_id,
        chain.decision.governance_decision_class_ref,
        chain.iteration.iteration_id,
    )


def test_absent_source_reaction_preserves_legacy_identifiers_and_wire() -> None:
    chain = _chain()
    assert _identifiers(chain) == (
        "gy.n6.counterexample.reaction_case.003",
        "pdc://gy/n6/reaction_case/counterexample/003",
        "gy.n6.diagnostic.reaction_case.003",
        "gy.n6.revision.reaction_case.003",
        "gy.n6.refinement.reaction_case.003",
        "pdc://gy/n6/reaction_case/refinement/003",
        "gy_n6_voi_003",
        "governance://gy/n6/reaction_case/terminal/003",
        "gy.n6.iteration.reaction_case.003",
    )
    assert chain == _chain(ref=None)
    problem = _problem("reaction_case")
    grounding = gc.CandidateGroundingObservation(
        candidate_id="candidate-a",
        status="grounding_gap",
        grounding_score=0.0,
        issue_codes=("missing_measurement",),
    )
    omitted = gc._counterexample_record(
        problem=problem,
        cycle_index=2,
        candidate_id="candidate-a",
        grounding=grounding,
        value_port=gc.ValuePortObservation(candidate_id="candidate-a"),
    )
    assert omitted.model_dump(mode="json") == chain.counterexample.model_dump(mode="json")


@pytest.mark.parametrize("change", ["digest", "profile", "case", "candidate", "cycle"])
def test_entire_selected_basis_and_evaluation_coordinates_namespace_every_id(change: str) -> None:
    original = _chain(ref=_basis())
    changed = _chain(
        ref=_basis(digest="c")
        if change == "digest"
        else _basis(profile="c")
        if change == "profile"
        else _basis(),
        case_id="other_case" if change == "case" else "reaction_case",
        candidate_id="candidate-b" if change == "candidate" else "candidate-a",
        cycle_index=3 if change == "cycle" else 2,
    )
    assert all(
        left != right
        for left, right in zip(
            _identifiers(original),
            _identifiers(changed),
            strict=True,
        )
    )
    assert original == _chain(ref=_basis())


def test_current_diagnostics_and_revision_retain_actual_links_at_old_evaluation_cycle() -> None:
    historical = _chain()
    current = _chain(ref=_basis(), issue="current_budget_limit", reason="current_spend_changed")
    assert historical.counterexample.diagnostic.code != current.counterexample.diagnostic.code
    assert historical.decision.reason != current.decision.reason
    assert set(_identifiers(historical)).isdisjoint(_identifiers(current))
    assert current.revision.source_counterexample_ref == current.counterexample.counterexample_ref
    assert current.decision.consumed_counterexample_refs == [
        current.counterexample.counterexample_ref
    ]
    assert current.iteration.counterexample_refs == [current.counterexample.counterexample_ref]
    assert current.iteration.refinement_decision_ref == current.decision.decision_ref
    assert current.decision.governance_refs == [current.decision.governance_decision_class_ref]
    assert current.counterexample.case_id == historical.counterexample.case_id
    assert current.counterexample.candidate_ref == historical.counterexample.candidate_ref
    assert current.decision.budget_refs == historical.decision.budget_refs
    assert current.counterexample.diagnostic.authority_purpose == "shadow_search_refinement_only"
    assert current.iteration.status == "governance_required"
    # Only the internal adapter is constructed: no store, execution or cycle append.
    problem = _problem("reaction_case")
    grounding = gc.CandidateGroundingObservation(
        candidate_id="candidate-a",
        status="grounding_gap",
        grounding_score=0.0,
    )
    adapter = gc._cycle_record(
        problem=problem,
        cycle_index=2,
        candidate_ids=("candidate-a",),
        selected_candidate={"candidate_id": "candidate-a"},
        grounding=grounding,
        simulation=gc.SimulationPortObservation(
            candidate_id="candidate-a",
            status="simulation_pending_n5",
        ),
        value_port=gc.ValuePortObservation(candidate_id="candidate-a"),
        terminal_kind="human_decision_required",
        counterexample=current.counterexample,
        revision=current.revision,
        voi_decision=gc.LoopVOIDecision(
            candidate_id="candidate-a",
            terminal_kind="human_decision_required",
            scheduler_action="escalate",
            scheduler_reason="current_spend_changed",
            priority=0.0,
            next_action="escalate",
            reason="current_spend_changed",
        ),
        source_reaction_ref=_basis(),
    )
    assert adapter.cycle_index == 2
    assert adapter.counterexample == current.counterexample
    assert adapter.refinement_decision == current.decision
    assert adapter.search_iteration == current.iteration


@pytest.mark.parametrize(
    "update",
    [
        {"kind": "foreign.basis"},
        {"media_type": "text/plain"},
        {"manifest_profile_sha256": None},
        {"manifest_profile_sha256": "malformed"},
    ],
)
def test_diagnostic_namespace_refuses_foreign_or_unselected_basis(
    update: dict[str, str | None],
) -> None:
    with pytest.raises(gc.GenerationCycleError, match="source_reaction_ref_invalid"):
        _chain(ref=_basis().model_copy(update=update))


def test_actual_revise_owner_forwards_source_reaction_without_claiming_new_cycle() -> None:
    controller = gc.GenerationCycleController()
    candidate = {"candidate_id": "candidate-a"}
    state = {
        "problem": _problem("reaction_case"),
        "cycle_index": 2,
        "selected_candidate": candidate,
        "selected_grounding": gc.CandidateGroundingObservation(
            candidate_id="candidate-a",
            status="grounding_gap",
            grounding_score=0.0,
            issue_codes=("missing_measurement",),
        ),
        "rankings": {},
        "candidates": (candidate,),
        "simulation": gc.SimulationPortObservation(
            candidate_id="candidate-a",
            status="simulation_pending_n5",
        ),
        "value_port": gc.ValuePortObservation(candidate_id="candidate-a"),
        "budget_state": _budget("0"),
        "candidate_summaries": (),
    }
    legacy = controller._revise_node(state)["cycle"]
    current = controller._revise_node({**state, "source_reaction_ref": _basis()})["cycle"]
    legacy_chain = _Chain(
        legacy.counterexample,
        legacy.revision_request,
        legacy.refinement_decision,
        legacy.search_iteration,
    )
    current_chain = _Chain(
        current.counterexample,
        current.revision_request,
        current.refinement_decision,
        current.search_iteration,
    )
    assert all(
        left != right
        for left, right in zip(
            _identifiers(legacy_chain),
            _identifiers(current_chain),
            strict=True,
        )
        if left is not None or right is not None
    )
    assert current.cycle_index == legacy.cycle_index == 2
    assert current.selected_candidate_ref == legacy.selected_candidate_ref == "candidate-a"
    assert current.simulation == legacy.simulation == state["simulation"]
    assert current.voi_decision == legacy.voi_decision
    assert (
        current.revision_request.source_counterexample_ref
        == current.counterexample.counterexample_ref
    )
    assert current.refinement_decision.consumed_counterexample_refs == [
        current.counterexample.counterexample_ref,
    ]
    assert (
        current.search_iteration.refinement_decision_ref == current.refinement_decision.decision_ref
    )
