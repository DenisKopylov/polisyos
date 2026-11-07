from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationContextHandoff,
    CandidateSimulationContextOffer,
)
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
    CycleSubstrateContextArtifactOwner,
)
from polisyos.runtime.quality.generation_cycle import (
    JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
    GenerationCycleController,
    JointSimulationPort,
    N4GenerationPort,
)
from polisyos.runtime.quality.generation_source import (
    GenerationSourceRepository,
    N4CandidateScenarioSourceRecordV3,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests._helpers.controlled_candidate_profile import (
    _configured_procurement_profile,
    _controlled_procurement_recording,
    _current_compiler_problem,
)
from tests.unit.runtime.quality.test_cycle_substrate import (
    _authenticated_tenant_scope,
    _TestCurrentJobExecutionOwner,
)
from tools.quality.validation import check_layer3_gy_design_generation_contract as n4_contract

REPO_ROOT = Path(__file__).resolve().parents[4]
_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"


@pytest.mark.asyncio
async def test_zero_budget_n6_retains_real_selected_n4_source_without_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real configured N4 source remains addressable when N6 refuses N5."""
    recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == _RECORDING_ID
    )
    original_problem = _current_compiler_problem(recording)
    controlled_recording = _controlled_procurement_recording(
        recording,
        outcome_variable=original_problem.outcome_of_interest.target_variable,
    )
    problem = _current_compiler_problem(controlled_recording)
    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "candidate-n4-zero-budget"
    job_id = "job-candidate-n4-zero-budget"
    run_id = "run-candidate-n4-zero-budget"
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(
        cas_root,
        tenant_id=tenant_id,
        cell_id=cell_id,
        ownership_enforced=True,
    )
    profile, declaration = _configured_procurement_profile(
        recorded_problem=problem,
        artifact_store=store,
        tenant_id=tenant_id,
        cell_id=cell_id,
        tmp_path=tmp_path / "configured-profile",
        repo_root=REPO_ROOT,
    )
    admission_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(profile,),
        model_declarations=(declaration,),
        store=store,
    )
    context_owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=_TestCurrentJobExecutionOwner(job_id, run_id),
    )

    with _authenticated_tenant_scope(tenant_id=tenant_id, cell_id=cell_id):
        offer = admission_owner.admit_context(
            problem=problem,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        assert type(offer) is CandidateSimulationContextOffer
        context_job_ref = context_owner.persist_for_current_job(
            offer.context,
            problem=problem,
            repo_root=REPO_ROOT,
        )

    handoff = CandidateSimulationContextHandoff(
        context=offer.context,
        context_job_ref=context_job_ref,
        profile=offer.profile,
        profile_config_ref=offer.profile_config_ref,
        job_id=job_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        model_declaration=offer.model_declaration,
        model_declaration_ref=offer.model_declaration_ref,
        ncm_ref=offer.ncm_ref,
    )
    replay_client = n4_contract.RecordedGenerationReplayClient(controlled_recording)
    n4_port = N4GenerationPort(
        model_id=str(recording["model_id"]),
        llm_client=replay_client,
        repo_root=REPO_ROOT,
        cycle_substrate_context=offer.context,
        candidate_simulation_handoff=handoff,
    )
    controller = GenerationCycleController(
        generation_port=n4_port,
        repo_root=REPO_ROOT,
        cycle_substrate_context=offer.context,
        artifact_store=store,
        candidate_simulation_handoff=handoff,
        # This direct owner-path test does not construct or claim a verified NL
        # worker lease. It exercises the scheduler boundary after source write.
        candidate_simulation_currentness_resolver=lambda: True,
        authority_scope="contract_testing",
    )

    n5_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def reject_physical_n5_call(
        port: JointSimulationPort,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        del port
        n5_calls.append((args, kwargs))
        raise AssertionError("zero-budget N6 must stop before physical N5")

    monkeypatch.setattr(JointSimulationPort, "__call__", reject_physical_n5_call)

    with _authenticated_tenant_scope(tenant_id=tenant_id, cell_id=cell_id):
        # Keep the contract-testing grounding ledger inside this test's scratch
        # root while leaving the actual N4 owner bound to the product sources.
        with monkeypatch.context() as scratch_root:
            scratch_root.setattr(controller, "_repo_root", tmp_path)
            controller._begin_source_run(run_id)
        with n4_contract._recorded_runtime_environment(controlled_recording):
            proposal_run = await n4_port(problem, cycle_index=0)
        recorded_responses = controlled_recording["responses"]
        assert isinstance(recorded_responses, list)
        expected_n4_calls = tuple(
            (response["call_index"], response["role_hint"])
            for response in recorded_responses
            if isinstance(response, dict)
        )
        assert len(expected_n4_calls) == len(recorded_responses) == 10
        assert (
            tuple((call.call_index, call.role_hint) for call in proposal_run.proposal.llm_calls)
            == expected_n4_calls
        )
        assert replay_client._cursor == len(expected_n4_calls)
        generation = controller._candidate_scenario_proposal_result(
            proposal_run,
            problem=problem,
            stable_subject_ref=gy_content_hash(problem.model_dump(mode="json")),
            origin_source_ref=None,
        )
        assert generation.status == "generated"
        assert generation.source_ref is not None
        assert len(generation.candidates) == 1

        candidate = generation.candidates[0]
        blocked = controller._joint_value_node_impl(
            {
                "selected_candidate": candidate,
                "problem": problem,
                "cycle_index": 0,
                "rankings": {},
                "budget_state": BudgetState(
                    limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))}
                ),
                "generation_result": generation,
            }
        )

        simulation = blocked["simulation"]
        value = blocked["value_port"]
        schedule = blocked["execution_schedule"]
        assert schedule.recommended_action == "defer"
        assert schedule.reason == "budget_exhausted_for_next_level"
        assert simulation.status == "simulation_blocked"
        assert simulation.authority_blockers == ("budget_exhausted_for_next_level",)
        assert simulation.diagnostics["port"] == "N6"
        assert simulation.diagnostics["reason"] == "budget_exhausted_for_next_level"
        assert simulation.diagnostics["scheduler_action"] == "defer"
        assert value.status == "value_blocked"
        assert value.authority_blockers == ("budget_exhausted_for_next_level",)
        assert n5_calls == []

        selected_ref_payload = simulation.diagnostics["candidate_simulation_n4_source_selected_ref"]
        assert selected_ref_payload == generation.source_ref.model_dump(mode="json")
        selected_ref = ArtifactRef.model_validate(selected_ref_payload)
        assert selected_ref.manifest_profile_sha256 is not None
        assert artifact_ref_identity_key(selected_ref) == artifact_ref_identity_key(
            generation.source_ref
        )
        assert simulation.diagnostics["candidate_simulation_n4_source_ref"] == str(
            selected_ref.artifact_id
        )

        # The source itself remains N4-only; a fresh read-only CAS handle must
        # resolve the exact selected profile view carried by the N6 refusal.
        fresh_store = FileSystemCAS.open_existing_read_only(cas_root)
        fresh_selected_ref = artifact_ref_for_manifest(fresh_store.get_manifest(selected_ref))
        assert artifact_ref_identity_key(fresh_selected_ref) == artifact_ref_identity_key(
            selected_ref
        )
        reopened = GenerationSourceRepository(fresh_store).load_candidate_scenario_source_for_n5(
            fresh_selected_ref,
            expected_run_id=run_id,
            expected_job_id=job_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        assert type(reopened) is N4CandidateScenarioSourceRecordV3
        assert reopened.status == "candidate_unverified"
        assert reopened.problem == problem
        assert reopened.proposal == proposal_run.proposal
        assert reopened.candidate == candidate
        assert reopened.context_hash == offer.context.content_hash
        assert artifact_ref_identity_key(reopened.context_job_ref) == artifact_ref_identity_key(
            context_job_ref
        )
        assert reopened.n5_status == "not_run"
        assert reopened.n8_status == "not_run"
        assert reopened.n9_status == "not_admitted"
        assert reopened.s8_status == "blocked"

        for field in (
            "simulation_ref",
            "simulation_result_ref",
            "cycle_substrate_context_job_ref",
            "candidate_simulation_n4_source_ref",
            "candidate_simulation_context_job_ref",
            "candidate_simulation_n5_input_ref",
            "candidate_simulation_profile_config_ref",
            "candidate_simulation_profile_selection_ref",
            "generic_n4_source_ref",
            "generic_context_job_ref",
            "generic_profile_ref",
            "generic_n5_input_ref",
            "generic_n5_execution_ref",
        ):
            assert getattr(simulation, field) is None, field

        forbidden_n5_kinds = {
            "runtime.quality.candidate_simulation_n5_input",
            "runtime.quality.candidate_simulation_execution",
            JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
        }
        written_kinds = {
            store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()
        }
        assert written_kinds.isdisjoint(forbidden_n5_kinds)
