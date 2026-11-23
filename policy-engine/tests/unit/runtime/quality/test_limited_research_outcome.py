"""Discriminate completed research-model scope from unresolved claims."""

from __future__ import annotations

from dataclasses import replace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_V3_SCHEMA_VERSION,
    DesignProblem,
    EvidenceAcquisitionNeeds,
)
from polisyos.runtime.quality.generation_cycle import (
    SimulationPortObservation,
    load_joint_simulation_result,
    persist_joint_simulation_result,
)
from polisyos.runtime.quality.generic_simulation_admission import GenericN5ResolvedResult
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationHorizonController,
    JointSimulationResult,
    NCMConditionalComparatorProfile,
)
from polisyos.runtime.quality.limited_research_outcome import (
    _covers_research_question,
    issue_limited_research_outcome,
)
from polisyos.runtime.quality.world_model_record import (
    PolicySlotBinding,
    WorldModelRecord,
    world_model_record_content_hash,
)
from tests._helpers.controlled_candidate_profile import _problem
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request, _world_record


@pytest.fixture(scope="module")
def model_replay(tmp_path_factory: pytest.TempPathFactory) -> GenericN5ResolvedResult:
    """Reopen the retained same-seed no-op and intervention result from actual NCM."""

    world = _world_record()
    outcome_slot = PolicySlotBinding(
        slot_id="firm_survival",
        state_path="firm_survival",
        unit="synthetic_score",
        entity_scope="firm",
        temporal_granularity="month",
    )
    world = world.model_copy(update={"policy_slot_map": (*world.policy_slot_map, outcome_slot)})
    content_hash = world_model_record_content_hash(world)
    world = WorldModelRecord.model_validate(
        {
            **world.model_dump(mode="python"),
            "content_hash": content_hash,
            "world_model_record_id": f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        }
    )
    request = _request(record=world)
    request = request.model_copy(
        update={
            "intervention_atoms": request.intervention_atoms[:1],
            "horizon": HorizonSpec(start=0, end=0),
            "replications": 2,
            "evidence_state": {"income_delta": 0.0, "balance_delta": 0.0},
            "comparator_profile": NCMConditionalComparatorProfile(
                outcome_units={"firm_survival": "synthetic_score"}
            ),
        }
    )
    produced = JointSimulationHorizonController().run(request)
    store = FileSystemCAS(tmp_path_factory.mktemp("limited-research-cas"))
    result_ref = persist_joint_simulation_result(produced, store=store)
    result = load_joint_simulation_result(result_ref, store=store, expected_request=request)
    assert result.comparator_refs_verified
    joint = result.trajectory_for("joint", result.atom_ids)
    (point,) = joint.points
    assert point.effect["firm_survival"] == 2.0
    assert point.replication_sampling is not None
    assert tuple(
        sample.effects["firm_survival"] for sample in point.replication_sampling.samples
    ) == (
        2.0,
        2.0,
    )
    return GenericN5ResolvedResult(request=request, result=result)


@pytest.fixture
def research_question() -> DesignProblem:
    """Supply a model experiment with no mandatory empirical or decision claim."""

    problem = _problem("declared_single_model_question")
    question = DesignProblem.model_validate(
        {
            **problem.model_dump(mode="python"),
            "schema_version": DESIGN_PROBLEM_V3_SCHEMA_VERSION,
            "problem_statement": "Estimate the conditional model difference in firm survival.",
            "outcome_of_interest": {
                **problem.outcome_of_interest.model_dump(mode="python"),
                "estimand": "conditional_model_outcome_difference.v1",
                "conditioning_variables": ("income_delta", "balance_delta"),
                "measurement_unit": "synthetic_score",
            },
            "constraints": [],
            "evidence_acquisition_needs": EvidenceAcquisitionNeeds(),
        }
    )
    assert cycle_job_design_problem_ref(question) == gy_content_hash(
        question.model_dump(mode="json")
    )
    return question


def test_only_completed_research_scope_is_eligible(
    model_replay: GenericN5ResolvedResult, research_question: DesignProblem
) -> None:
    assert _covers_research_question(research_question, model_replay)

    mandatory = _problem()
    for change in (
        {"constraints": mandatory.constraints},
        {"evidence_acquisition_needs": mandatory.evidence_acquisition_needs},
        {
            "authority_profile": research_question.authority_profile.model_copy(
                update={"requested_authority_level": "production"}
            )
        },
    ):
        assert not _covers_research_question(
            research_question.model_copy(update=change), model_replay
        )

    long_request = model_replay.request.model_copy(update={"horizon": HorizonSpec(start=0, end=1)})
    assert not _covers_research_question(
        research_question, replace(model_replay, request=long_request)
    )

    joint = model_replay.result.trajectory_for("joint", model_replay.result.atom_ids)
    covered_without_sampling = joint.model_copy(
        update={"points": (joint.points[0].model_copy(update={"replication_sampling": None}),)}
    )
    result_without_sampling = model_replay.result.model_copy(
        update={
            "trajectories": tuple(
                covered_without_sampling if trajectory is joint else trajectory
                for trajectory in model_replay.result.trajectories
            )
        }
    )
    assert not _covers_research_question(
        research_question, replace(model_replay, result=result_without_sampling)
    )


@pytest.mark.parametrize("estimand", ["time_to_exit", "quantile", "average_treatment_effect"])
def test_same_retained_contrast_cannot_answer_another_estimand(
    model_replay: GenericN5ResolvedResult, research_question: DesignProblem, estimand: str
) -> None:
    assert _covers_research_question(research_question, model_replay)
    fields = research_question.model_dump(mode="python")
    fields["outcome_of_interest"]["estimand"] = estimand
    changed_question = DesignProblem.model_validate(fields)

    assert not _covers_research_question(changed_question, model_replay)


def test_same_retained_contrast_preserves_metric_direction_conditions_and_unit(
    model_replay: GenericN5ResolvedResult, research_question: DesignProblem
) -> None:
    assert _covers_research_question(research_question, model_replay)
    fields = research_question.model_dump(mode="python")
    fields["outcome_of_interest"]["direction"] = "minimize"
    assert not _covers_research_question(DesignProblem.model_validate(fields), model_replay)
    fields["objectives"][0]["direction"] = "minimize"
    assert not _covers_research_question(DesignProblem.model_validate(fields), model_replay)
    for key, change in (
        ("conditioning_variables", ("balance_delta",)),
        ("measurement_unit", "other_score"),
    ):
        fields = research_question.model_dump(mode="python")
        fields["outcome_of_interest"][key] = change
        assert not _covers_research_question(DesignProblem.model_validate(fields), model_replay)
    fields = research_question.model_dump(mode="python")
    fields["objectives"][0]["metric_id"] = "firm_survival_lower_quartile"
    fields["outcome_of_interest"]["metric_id"] = "firm_survival_lower_quartile"
    assert not _covers_research_question(DesignProblem.model_validate(fields), model_replay)


def test_real_number_does_not_replace_the_selected_owner(
    model_replay: GenericN5ResolvedResult, research_question: DesignProblem
) -> None:
    receipt = model_replay.result.receipt
    simulation = SimulationPortObservation(
        candidate_id="one-research-candidate",
        status="joint_simulated",
        simulation_ref=receipt.payload_hash,
        uncertainty_kind="K_sim",
        authority_blockers=("simulation_only_k_sim_not_world_evidence",),
    )
    assert _covers_research_question(research_question, model_replay)
    same_wire = JointSimulationResult.model_validate_json(model_replay.result.model_dump_json())
    assert same_wire.receipt == receipt
    assert not _covers_research_question(research_question, replace(model_replay, result=same_wire))
    assert (
        issue_limited_research_outcome(
            problem=research_question,
            candidate_atom_hash=model_replay.request.intervention_atoms[0].content_hash,
            cycle_index=0,
            simulation=simulation,
            handoff=None,
            verified_replay=model_replay,
            authority_blockers=simulation.authority_blockers,
        )
        is None
    )
