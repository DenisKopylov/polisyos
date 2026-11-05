"""Query-coordinate propagation through the two N4 atom producers."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import design_generation as dg
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationScenarioProfile
from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
    DesignProblem,
    OutcomeOfInterest,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _problem_with_query_coordinates(
    problem: DesignProblem,
    *,
    conditioning_variables: tuple[str, ...],
    measurement_unit: str | None,
) -> DesignProblem:
    """Create a validated problem variant carrying only declared query coordinates."""
    outcome_fields = problem.outcome_of_interest.model_dump(mode="python")
    outcome_fields.update(
        {
            "conditioning_variables": conditioning_variables,
            "measurement_unit": measurement_unit,
        }
    )
    outcome = OutcomeOfInterest.model_validate(outcome_fields)
    problem_fields = problem.model_dump(mode="python")
    problem_fields["outcome_of_interest"] = outcome
    return DesignProblem.model_validate(problem_fields)


def _profile_for_problem(
    profile: CandidateSimulationScenarioProfile,
    *,
    problem: DesignProblem,
) -> CandidateSimulationScenarioProfile:
    """Retain selected owner inputs while binding the profile to this problem variant."""
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

    payload = profile.model_dump(mode="json")
    payload["profile_selection_ref"] = cycle_job_profile_selection_ref(problem)
    payload.pop("content_hash")
    payload["content_hash"] = gy_content_hash(payload)
    return CandidateSimulationScenarioProfile.model_validate(payload)


def _context_for_problem(
    profile: CandidateSimulationScenarioProfile,
    *,
    problem: DesignProblem,
) -> Any:
    """Bind the selected profile's verified owner inputs to one exact problem ref."""
    inputs = profile.context_inputs
    return build_cycle_substrate_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        domain=problem.domain,
        substrate_registry=inputs.substrate_registry,
        selected_registry_entry_hashes=inputs.selected_registry_entry_hashes,
        world_model_record=inputs.world_model_record,
        intervention_substrate=inputs.intervention_substrate,
        candidate_levers=inputs.candidate_levers,
        transport_context=inputs.transport_context,
        source_pack_content_hash=inputs.source_pack_content_hash,
        substrate_input_content_hash=inputs.substrate_input_content_hash,
    )


def _assert_atom_query_coordinates(
    atom: dg.InterventionAtomBinding,
    *,
    outcome_variable: str,
    conditioning_variables: tuple[str, ...],
    measurement_unit: str | None,
) -> None:
    estimand = atom.intended_downstream_estimand
    assert estimand.outcome_variables == (outcome_variable,)
    assert estimand.conditioning_set == conditioning_variables
    assert estimand.unit_id == measurement_unit
    assert atom.status == "candidate_unverified"


async def _record_candidate_scenario_proposal(
    problem: DesignProblem,
    context: Any,
    recording: dict[str, Any],
    *,
    repo_root: Path,
) -> dg.N4CandidateProposalSource:
    """Run canonical N4 against a supplied fixture-owned source root."""
    from tools.quality.validation import check_layer3_gy_design_generation_contract as contract

    replay = contract.RecordedGenerationReplayClient(copy.deepcopy(recording))
    with contract._recorded_runtime_environment(recording):
        result = await dg.generate_design_candidate_scenario_proposal_under_a(
            problem,
            model_id=str(recording["model_id"]),
            llm_client=replay,
            repo_root=repo_root,
            cycle_substrate_context=context,
        )
    assert type(result) is dg.N4CandidateScenarioProposalRun
    responses = recording["responses"]
    assert isinstance(responses, list)
    assert replay._cursor == len(result.proposal.llm_calls) == len(responses)
    assert tuple(
        (call.call_index, call.role_hint, call.status) for call in result.proposal.llm_calls
    ) == tuple(
        (response["call_index"], response["role_hint"], response["status"])
        for response in responses
        if isinstance(response, dict)
    )
    return result.proposal


@pytest.mark.asyncio
async def test_n4_producers_emit_declared_query_coordinates_and_preserve_legacy_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actual proposal and CGF atom producers preserve coordinates without promoting them."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality import credal_reference
    from polisyos.runtime.quality.intervention_atom_binding import (
        build_intervention_atom_binding as actual_atom_builder,
    )
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        current_catalog_serving_source,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        bind_candidate_cycle_kref_builder_root,
        build_candidate_cycle_catalog_serving_source,
        build_candidate_cycle_substrate_route_inputs,
        install_candidate_cycle_l6_source_root_reader,
    )
    from tests._helpers.controlled_candidate_profile import (
        _configured_procurement_profile,
        _controlled_procurement_recording,
        _current_compiler_problem,
        _seed_controlled_selected_skg_source,
    )
    from tests._helpers.generic_n4_served_replay import _declared_generic_component_knobs
    from tests.unit.runtime.quality.test_design_generation import _candidate_scenario_recording

    source_recording = _candidate_scenario_recording()
    original_problem = _current_compiler_problem(source_recording)
    recording = _controlled_procurement_recording(
        source_recording,
        outcome_variable=original_problem.outcome_of_interest.target_variable,
    )
    legacy_problem = _current_compiler_problem(recording)

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "n4-query-coordinate-producers"
    store = FileSystemCAS(
        tmp_path / "cas",
        tenant_id=tenant_id,
        cell_id=cell_id,
        ownership_enforced=True,
    )
    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "compact-procurement-source",
        include_owner_slot_manifest=True,
        owner_knob_dictionary=_declared_generic_component_knobs("controlled_overlay"),
    )
    source_root = source_inputs.root
    assert source_root.is_relative_to(tmp_path.resolve())
    assert source_root != REPO_ROOT.resolve()
    _catalog_selection, catalog_source = build_candidate_cycle_catalog_serving_source(source_root)
    l6_source_reads, bind_l6_source, assert_l6_reader = (
        install_candidate_cycle_l6_source_root_reader(
            monkeypatch,
            code_root=REPO_ROOT,
            source_owner_root=source_root,
        )
    )
    selected_skg = _seed_controlled_selected_skg_source(
        tmp_path,
        source_root=source_root,
        recorded_problem=legacy_problem,
    )
    with catalog_serving_source_scope(catalog_source):
        profile, _declaration = _configured_procurement_profile(
            recorded_problem=legacy_problem,
            artifact_store=store,
            tenant_id=tenant_id,
            cell_id=cell_id,
            tmp_path=tmp_path / "configured-profile",
            source_root=source_root,
            selected_skg_source=selected_skg,
            repo_root=source_root,
            basis_repo_root=source_root,
        )
    l6_source_witness = bind_l6_source(profile.context_inputs.intervention_substrate)
    assert l6_source_witness["source_owner_root"] == str(source_root)
    assert l6_source_reads
    assert_l6_reader()
    actual_kref_roots: list[str] = []
    selected_kref_builder = bind_candidate_cycle_kref_builder_root(
        credal_reference.build_credal_reference,
        expected_repo_root=source_root,
        observed_repo_roots=actual_kref_roots,
        mismatch_code="n4_query_coordinate_kref_source_root_mismatch",
    )

    def build_selected_kref(repo_root: Path, *args: Any, **kwargs: Any) -> Any:
        if current_catalog_serving_source() is not catalog_source:
            raise AssertionError("n4_query_coordinate_catalog_source_not_selected")
        return selected_kref_builder(repo_root, *args, **kwargs)

    monkeypatch.setattr(credal_reference, "build_credal_reference", build_selected_kref)
    monkeypatch.setattr(dg, "build_credal_reference", build_selected_kref)
    selected_world = profile.context_inputs.world_model_record
    outcome_binding = selected_world.slot_binding(
        legacy_problem.outcome_of_interest.target_variable
    )
    assert outcome_binding is not None
    assert outcome_binding.unit is not None
    selected_unit = outcome_binding.unit

    conditioning_variables = ("government.balance",)
    coordinate_problem = _problem_with_query_coordinates(
        legacy_problem,
        conditioning_variables=conditioning_variables,
        measurement_unit=selected_unit,
    )
    assert (
        coordinate_problem.outcome_of_interest.query_coordinate_status
        == "candidate_proposed_unverified"
    )
    coordinate_profile = _profile_for_problem(profile, problem=coordinate_problem)
    coordinate_context = _context_for_problem(coordinate_profile, problem=coordinate_problem)
    assert type(coordinate_context.world_model_record) is type(selected_world)
    assert coordinate_context.world_model_record == selected_world
    assert coordinate_context.world_model_record.content_hash == selected_world.content_hash
    assert coordinate_context.design_problem_ref == gy_content_hash(
        coordinate_problem.model_dump(mode="json")
    )

    with catalog_serving_source_scope(catalog_source):
        coordinate_proposal = await _record_candidate_scenario_proposal(
            coordinate_problem,
            coordinate_context,
            recording,
            repo_root=source_root,
        )
        proposal_candidate = dg.build_candidate_scenario_proposal_candidate(
            coordinate_proposal,
            problem=coordinate_problem,
            profile=coordinate_profile,
            context=coordinate_context,
            repo_root=source_root,
        )
        assert proposal_candidate is not None
        _assert_atom_query_coordinates(
            proposal_candidate.atom,
            outcome_variable=coordinate_problem.outcome_of_interest.target_variable,
            conditioning_variables=conditioning_variables,
            measurement_unit=selected_unit,
        )

        actual_reference = build_selected_kref(
            source_root,
            world_model_record=selected_world,
        )
        shadow_source_capture = dg._N4SourceCapture()
        shadow_candidates, _dispositions = dg._content_bound_candidates(
            design_problem=coordinate_problem,
            design_problem_ref=coordinate_proposal.design_problem_ref,
            bundle=coordinate_proposal.trinity_bundle,
            model_id=coordinate_proposal.model_id,
            draft_path=coordinate_proposal.drafter_path,
            formalizer_path=coordinate_proposal.formalizer_path,
            critic_path=coordinate_proposal.critic_path,
            critique_verdict=str(coordinate_proposal.critique.verdict),
            calls=coordinate_proposal.llm_calls,
            repo_root=source_root,
            world_model_record_ref=selected_world.world_model_record_id,
            reference=actual_reference,
            cycle_substrate_context=coordinate_context,
            source_capture=shadow_source_capture,
        )
    assert actual_kref_roots == [str(source_root)]
    assert all(read["bundle"]["source_owner_root"] == str(source_root) for read in l6_source_reads)
    assert_l6_reader()
    assert shadow_source_capture.candidates
    shadow_candidate = next(
        candidate
        for candidate in shadow_candidates
        if candidate.atom.intervention_id == shadow_source_capture.candidates[0].intervention_id
    )
    _assert_atom_query_coordinates(
        shadow_candidate.atom,
        outcome_variable=coordinate_problem.outcome_of_interest.target_variable,
        conditioning_variables=conditioning_variables,
        measurement_unit=selected_unit,
    )

    legacy_context = _context_for_problem(profile, problem=legacy_problem)
    with catalog_serving_source_scope(catalog_source):
        legacy_proposal = await _record_candidate_scenario_proposal(
            legacy_problem,
            legacy_context,
            recording,
            repo_root=source_root,
        )
        legacy_candidate = dg.build_candidate_scenario_proposal_candidate(
            legacy_proposal,
            problem=legacy_problem,
            profile=profile,
            context=legacy_context,
            repo_root=source_root,
        )
    assert legacy_candidate is not None
    _assert_atom_query_coordinates(
        legacy_candidate.atom,
        outcome_variable=legacy_problem.outcome_of_interest.target_variable,
        conditioning_variables=(),
        measurement_unit=None,
    )
    legacy_problem_bytes = json.dumps(
        legacy_problem.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert b'"conditioning_variables"' not in legacy_problem_bytes
    assert b'"measurement_unit"' not in legacy_problem_bytes
    assert b'"query_coordinate_status"' not in legacy_problem_bytes
    legacy_estimand_payload = legacy_candidate.atom.intended_downstream_estimand.model_dump(
        mode="json"
    )
    assert legacy_estimand_payload["conditioning_set"] == []
    assert legacy_estimand_payload["unit_id"] is None

    conflicting_problem = _problem_with_query_coordinates(
        legacy_problem,
        conditioning_variables=conditioning_variables,
        measurement_unit=f"{selected_unit}_conflict",
    )
    conflicting_profile = _profile_for_problem(profile, problem=conflicting_problem)
    conflicting_context = _context_for_problem(conflicting_profile, problem=conflicting_problem)
    with catalog_serving_source_scope(catalog_source):
        conflicting_proposal = await _record_candidate_scenario_proposal(
            conflicting_problem,
            conflicting_context,
            recording,
            repo_root=source_root,
        )
    atom_builder_calls: list[dict[str, Any]] = []

    def record_actual_atom_builder(**kwargs: Any) -> Any:
        atom_builder_calls.append(kwargs)
        return actual_atom_builder(**kwargs)

    monkeypatch.setattr(
        "polisyos.runtime.quality.intervention_atom_binding.build_intervention_atom_binding",
        record_actual_atom_builder,
    )
    with pytest.raises(dg.DesignGenerationError) as conflict:
        dg.build_candidate_scenario_proposal_candidate(
            conflicting_proposal,
            problem=conflicting_problem,
            profile=conflicting_profile,
            context=conflicting_context,
            repo_root=source_root,
        )
    assert conflict.value.code == "n4_outcome_measurement_unit_mismatch"
    assert atom_builder_calls == []

    source = shadow_source_capture.candidates[0]
    intervention = next(
        item
        for item in coordinate_proposal.trinity_bundle.policy_spec.interventions
        if item.intervention_id == source.intervention_id
    )
    with pytest.raises(dg.DesignGenerationError) as shadow_conflict:
        dg._shadow_candidate_from_grounding(
            design_problem=conflicting_problem,
            design_problem_ref=gy_content_hash(conflicting_problem.model_dump(mode="json")),
            intervention=intervention,
            model_id=coordinate_proposal.model_id,
            draft_path=coordinate_proposal.drafter_path,
            formalizer_path=coordinate_proposal.formalizer_path,
            critic_path=coordinate_proposal.critic_path,
            critique_verdict=str(coordinate_proposal.critique.verdict),
            bundle_ref=gy_content_hash(coordinate_proposal.trinity_bundle.model_dump(mode="json")),
            policy_spec_ref=gy_content_hash(
                coordinate_proposal.trinity_bundle.policy_spec.model_dump(mode="json")
            ),
            prompt_hashes=tuple(call.prompt_hash for call in coordinate_proposal.llm_calls),
            raw_responses=tuple(
                call.raw_llm_response
                for call in coordinate_proposal.llm_calls
                if call.raw_llm_response
            ),
            cg1=source.grounding_relation_certificate,
            cg2=source.grounding_decision_certificate,
            resolved_world_model_record_ref=selected_world.world_model_record_id,
            world_record=selected_world,
        )
    assert shadow_conflict.value.code == "n4_outcome_measurement_unit_mismatch"
    assert atom_builder_calls == []


def test_unknown_selected_outcome_unit_stays_unestablished() -> None:
    """A candidate declaration cannot supply a missing selected WMR unit."""
    from tests._helpers.controlled_candidate_profile import _problem
    from tests.unit.runtime.quality.test_generation_cycle import _cyc01_owner_bound_n5_case

    declared_problem = _problem("n4_query_coordinate_unknown_unit")
    declared_problem = DesignProblem.model_validate(
        {
            **declared_problem.model_dump(mode="python"),
            "schema_version": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
        }
    )
    declared_problem = _problem_with_query_coordinates(
        declared_problem,
        conditioning_variables=("government.balance",),
        measurement_unit="synthetic_score",
    )
    problem, context, _candidate = _cyc01_owner_bound_n5_case(problem_seed=declared_problem)
    outcome_binding = context.world_model_record.slot_binding(
        problem.outcome_of_interest.target_variable
    )
    assert outcome_binding is not None
    assert outcome_binding.unit is None
    assert dg._declared_outcome_unit_from_world(problem, context.world_model_record) is None
