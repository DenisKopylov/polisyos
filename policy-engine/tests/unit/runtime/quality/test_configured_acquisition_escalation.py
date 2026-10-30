"""Revision-stage requirement dispatch; full profile/planner admission stays separate."""

from __future__ import annotations

import copy

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import generation_cycle as owner
from tests._helpers.controlled_candidate_profile import _Atom, _budget, _Candidate, _problem


def _revision_case(handoff: str, *, mutation: str | None = None):
    problem = _problem("configured_cov_escalation")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    candidate = _Candidate(
        candidate_id="candidate-current-cov",
        atom=_Atom("candidate-current-cov", "sha256:" + "4" * 64, problem_frame_ref=problem_ref),
        diversity_key=("grant", "firms", "current-cov", "unit"),
    )
    grounding = owner._grounding_unavailable(
        candidate.candidate_id,
        issue_codes=("cgf_disposition_missing",),
        candidate_content_hash=candidate.atom.content_hash,
        design_problem_ref=problem_ref,
        authority_level=problem.authority_profile.requested_authority_level,
    )
    simulation = owner.SimulationPortObservation(
        candidate_id=candidate.candidate_id,
        status="joint_simulated",
        authority_blockers=("scenario_only", "n9_not_admitted"),
    )
    value = owner._configured_candidate_value_observation(candidate.candidate_id, simulation)

    def revision_policy(**values):
        revision = values["default_revision"]
        if mutation is None:
            return revision
        payload = copy.deepcopy(revision.strategy_payload)
        request = payload["acquisition_request"]
        if mutation == "absent":
            request.pop("requirement_gap")
        elif mutation == "wrong_candidate":
            request["requirement_gap"]["metadata"]["candidate_binding"]["candidate_id"] = "other"
        elif mutation == "wrong_producer_ref":
            request["requirement_gap"]["producer_output_ref"] = "sha256:" + "f" * 64
        elif mutation == "unknown_schema":
            request["requirement_gap"]["requirement_schema_version"] = "unknown.v999"
        elif mutation == "wrong_driver":
            request["driver"] = "not_the_current_owner_issue"
        else:
            raise AssertionError(mutation)
        return revision.model_copy(update={"strategy_payload": payload})

    controller = owner.GenerationCycleController(
        authority_scope="contract_testing", revision_policy=revision_policy
    )
    # Branch activation only: this unit does not admit a profile or claim an N5
    # execution. The producer gap and revision/subject binding below are real.
    if handoff == "candidate":
        controller._candidate_simulation_handoff = object()
    else:
        controller._generic_cycle_simulation_handoff = object()
    budget = _budget()
    schedule = controller._schedule_candidate_for_execution(
        candidate_id=candidate.candidate_id, proxy_score=0.0, voi_estimate=0.0, budget_state=budget
    )
    state = {
        "problem": problem,
        "cycle_index": 0,
        "selected_candidate": candidate,
        "selected_grounding": grounding,
        "rankings": {},
        "budget_state": budget,
        "candidates": (candidate,),
        "candidate_summaries": (),
        "simulation": simulation,
        "value_port": value,
        "execution_schedule": schedule,
        "stable_design_problem_ref": problem_ref,
    }
    return controller, state


@pytest.mark.parametrize("handoff", ["candidate", "generic"])
def test_current_producer_bound_cov_requirement_preserves_escalation(handoff):
    controller, state = _revision_case(handoff)
    result = controller._revise_node(state)
    cycle = result["cycle"]
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.voi_decision.next_action == "escalate"
    assert cycle.value_port == state["value_port"]
    assert cycle.value_port.status == "value_pending_n8"
    assert cycle.value_port.authority_blockers == ("candidate_scenario_n5_only",)
    assert cycle.grounding.current_valid is False
    gap, refusal = owner._n7_cycle_source_gap(
        state["problem"],
        cycle=cycle,
        acquisition_request=cycle.revision_request.strategy_payload["acquisition_request"],
    )
    assert refusal is None
    assert gap == state["selected_grounding"].acquisition_requirement


@pytest.mark.parametrize("handoff", ["candidate", "generic"])
@pytest.mark.parametrize(
    "mutation",
    ["absent", "wrong_candidate", "wrong_producer_ref", "unknown_schema", "wrong_driver"],
)
def test_unbound_requirement_cannot_bypass_configured_stop(handoff, mutation):
    controller, state = _revision_case(handoff, mutation=mutation)
    cycle = controller._revise_node(state)["cycle"]
    assert cycle.voi_decision.next_action == "blocked"
    assert cycle.value_port == state["value_port"]
    assert cycle.grounding.current_valid is False


@pytest.mark.parametrize("handoff", ["candidate", "generic"])
@pytest.mark.parametrize("substitution", ["report", "issues", "evidence", "authority"])
def test_coherent_foreign_cov_basis_cannot_override_current_observation(handoff, substitution):
    controller, state = _revision_case(handoff)
    current = state["selected_grounding"]
    selected = state["selected_candidate"]
    report_ref = current.report_ref
    issues = current.issue_codes
    evidence = current.evidence_refs
    level = state["problem"].authority_profile.requested_authority_level
    if substitution == "report":
        report_ref = "sha256:" + "f" * 64
    elif substitution == "issues":
        issues = (*issues, "a_different_owner_issue")
    elif substitution == "evidence":
        evidence = (*evidence, "sha256:" + "e" * 64)
    elif substitution == "authority":
        level = "governed" if str(level) != "governed" else "research"
    foreign = owner.grounding_coverage_requirement_gap(
        candidate_id=selected.candidate_id,
        candidate_content_hash=selected.atom.content_hash,
        design_problem_ref=state["stable_design_problem_ref"],
        issue_codes=issues,
        evidence_refs=evidence,
        authority_level=level,
        grounding_report_ref=report_ref,
    )
    assert (
        owner.AcquisitionRequirementGap.model_validate(foreign.model_dump(mode="json")) == foreign
    )
    # Replace both source and request coherently: the real revision producer
    # below copies this substituted source gap. The enclosing observed report,
    # issues, evidence and current problem authority remain the actual basis.
    state["selected_grounding"] = current.model_copy(update={"acquisition_requirement": foreign})
    cycle = controller._revise_node(state)["cycle"]
    request = cycle.revision_request.strategy_payload["acquisition_request"]
    assert request["requirement_gap"] == foreign.model_dump(mode="json")
    assert cycle.grounding.acquisition_requirement == foreign
    assert cycle.grounding.report_ref == current.report_ref
    assert cycle.grounding.issue_codes == current.issue_codes
    assert cycle.grounding.evidence_refs == current.evidence_refs
    assert request["driver"] in current.issue_codes
    assert cycle.voi_decision.next_action == "blocked"
    assert cycle.value_port == state["value_port"]
    gap, refusal = owner._n7_cycle_source_gap(
        state["problem"], cycle=cycle, acquisition_request=request
    )
    assert gap is None
    assert refusal == "unbound_requirement_input_refused"
