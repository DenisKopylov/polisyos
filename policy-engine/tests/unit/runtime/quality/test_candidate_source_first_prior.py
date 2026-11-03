"""Candidate-only first-N5 source replay over a real deferred N4 source."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS
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
    GenerationCycleRecord,
    JointSimulationPort,
    N4GenerationPort,
    candidate_source_first_n5_deferred,
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
_DEFER_REASON = "budget_exhausted_for_next_level"


def _ref(kind: str, digit: str) -> ArtifactRef:
    """Build a typed adversarial ref for a negative control only."""

    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(digit * 64),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _expect_prior_refusal(call: Callable[[], object], code: str) -> ValueError:
    with pytest.raises(ValueError, match=code) as refusal:
        call()
    return refusal.value


@pytest.mark.asyncio
async def test_first_n5_prior_requires_real_selected_v3_and_exact_scheduler_defer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real N4/context bytes survive N6 defer, while forged/missing links fail closed.

    This is a contract-testing component witness. Its source producer, context
    owner, N6 scheduler, and CAS are real; its test currentness callback does
    not establish verified served-worker custody. The served route owns that
    separate proof.
    """

    from polisyos.runtime.quality.acquisition_world_growth import (
        resolve_first_candidate_n4_prior,
    )

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
    cell_id = "candidate-source-first-n5"
    job_id = "job-candidate-source-first-n5"
    run_id = "run-candidate-source-first-n5"
    store_root = tmp_path / "candidate-source-first-n5-cas"
    store = FileSystemCAS(
        store_root,
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
        reopened_context_job = context_owner.resolve_for_current_job(
            context_job_ref,
            problem=problem,
            repo_root=REPO_ROOT,
        )
        assert reopened_context_job.context == offer.context
        assert reopened_context_job.job_id == job_id
        assert reopened_context_job.run_id == run_id
        assert reopened_context_job.tenant_id == tenant_id
        assert reopened_context_job.cell_id == cell_id

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
    n4_port = N4GenerationPort(
        model_id=str(recording["model_id"]),
        llm_client=n4_contract.RecordedGenerationReplayClient(controlled_recording),
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
        # The component owner test does not mint a worker lease or claim custody.
        candidate_simulation_currentness_resolver=lambda: True,
        authority_scope="contract_testing",
    )

    n5_calls: list[object] = []

    def refuse_physical_n5(
        port: JointSimulationPort,
        *args: object,
        **kwargs: object,
    ) -> object:
        del port, args, kwargs
        n5_calls.append(object())
        raise AssertionError("scheduler-deferred first N5 reached physical N5")

    monkeypatch.setattr(JointSimulationPort, "__call__", refuse_physical_n5)

    stable_subject_ref = gy_content_hash(problem.model_dump(mode="json"))
    with _authenticated_tenant_scope(tenant_id=tenant_id, cell_id=cell_id):
        controller._begin_source_run(run_id)
        with n4_contract._recorded_runtime_environment(controlled_recording):
            proposal_run = await n4_port(problem, cycle_index=0)
        # This recorded gateway capture includes three drafter-multipass calls
        # and five formalizer calls, including their recorded retry errors.
        expected_call_trace = (
            (0, "draft", "success"),
            (1, "drafter_multipass", "success"),
            (2, "drafter_multipass", "error"),
            (3, "drafter_multipass", "success"),
            (4, "formalizer", "success"),
            (5, "formalizer", "success"),
            (6, "formalizer", "error"),
            (7, "formalizer", "success"),
            (8, "formalizer", "success"),
            (9, "critic", "success"),
        )
        assert (
            tuple(
                (call.call_index, call.role_hint, call.status)
                for call in proposal_run.proposal.llm_calls
            )
            == expected_call_trace
        )
        generation = controller._candidate_scenario_proposal_result(
            proposal_run,
            problem=problem,
            stable_subject_ref=stable_subject_ref,
            origin_source_ref=None,
        )
        assert generation.status == "generated"
        assert generation.source_ref is not None
        assert len(generation.candidates) == 1
        candidate = generation.candidates[0]
        source = GenerationSourceRepository(store).load_candidate_scenario_source_in_owner_scope(
            generation.source_ref,
            expected_run_id=run_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        assert type(source) is N4CandidateScenarioSourceRecordV3
        assert source.candidate == candidate
        assert source.problem == problem
        assert source.stable_subject_ref == stable_subject_ref
        assert source.context_job_ref == context_job_ref
        assert source.context_hash == offer.context.content_hash
        assert source.profile_selection_ref == profile.profile_selection_ref
        assert source.n5_status == "not_run"
        assert source.n8_status == "not_run"
        assert source.n9_status == "not_admitted"

        n5_kinds = (
            "runtime.quality.candidate_simulation_n5_input",
            "runtime.quality.candidate_simulation_execution",
            "runtime.quality.generic_cycle_simulation_n5_input",
            JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
        )
        n5_inventory_before = {
            kind: store.manifest_inventory_snapshot(kind=kind) for kind in n5_kinds
        }
        zero_budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))})
        grounded = controller._ground_node(
            {
                "problem": problem,
                "cycle_index": 0,
                "generation_result": generation,
                "generation_channel": "n4_owner",
                "candidates": generation.candidates,
                "rankings": {},
                "selected_candidate": candidate,
            }
        )
        blocked = controller._joint_value_node_impl(
            {
                **grounded,
                "budget_state": zero_budget,
            }
        )
        assert blocked["execution_schedule"].recommended_action == "defer"
        assert blocked["execution_schedule"].reason == _DEFER_REASON
        assert blocked["simulation"].status == "simulation_blocked"
        assert blocked["simulation"].authority_blockers == (_DEFER_REASON,)
        assert blocked["simulation"].diagnostics["port"] == "N6"
        assert blocked["simulation"].diagnostics["reason"] == _DEFER_REASON
        assert blocked["simulation"].diagnostics["scheduler_action"] == "defer"
        assert blocked["value_port"].status == "value_blocked"
        assert blocked["value_port"].authority_blockers == (_DEFER_REASON,)
        assert blocked["value_port"].reason == (
            "N6 VOI scheduler blocked the next stage: budget_exhausted_for_next_level."
        )
        revised = controller._revise_node(blocked)
        source_cycle = revised["cycle"]
        assert type(source_cycle) is GenerationCycleRecord
        assert source_cycle.terminal_kind == "acquisition_required"
        assert candidate_source_first_n5_deferred(source_cycle)
        assert source_cycle.simulation.diagnostics[
            "candidate_simulation_n4_source_selected_ref"
        ] == (generation.source_ref.model_dump(mode="json"))
        assert source_cycle.simulation.candidate_simulation_n5_input_ref is None
        assert source_cycle.simulation.simulation_result_ref is None
        assert n5_calls == []

        load_calls: list[ArtifactRef] = []
        real_source_load = GenerationSourceRepository.load_candidate_scenario_source_in_owner_scope

        def count_source_load(
            repository: GenerationSourceRepository,
            ref: ArtifactRef,
            **kwargs: Any,
        ) -> N4CandidateScenarioSourceRecordV3:
            load_calls.append(ref)
            return real_source_load(repository, ref, **kwargs)

        monkeypatch.setattr(
            GenerationSourceRepository,
            "load_candidate_scenario_source_in_owner_scope",
            count_source_load,
        )

        def resolve(
            cycle: GenerationCycleRecord = source_cycle,
            *,
            selected_problem: Any = problem,
            selected_subject_ref: str = stable_subject_ref,
        ) -> N4CandidateScenarioSourceRecordV3:
            return resolve_first_candidate_n4_prior(
                artifact_store=store,
                source_cycle=cycle,
                problem=selected_problem,
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                source_job_id=job_id,
                design_problem_ref=selected_subject_ref,
            )

        resolved = resolve()
        assert type(resolved) is N4CandidateScenarioSourceRecordV3
        assert resolved == source
        assert load_calls == [generation.source_ref]

        # Even a structurally valid defer cannot stand in for missing source
        # bytes. A separate empty CAS makes the selected source unavailable.
        missing_source_store = FileSystemCAS(
            tmp_path / "missing-candidate-source-cas",
            tenant_id=tenant_id,
            cell_id=cell_id,
            ownership_enforced=True,
        )
        reads_before = len(load_calls)
        with pytest.raises((OSError, ValueError)):
            resolve_first_candidate_n4_prior(
                artifact_store=missing_source_store,
                source_cycle=source_cycle,
                problem=problem,
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                source_job_id=job_id,
                design_problem_ref=stable_subject_ref,
            )
        assert len(load_calls) == reads_before + 1
        assert {
            kind: store.manifest_inventory_snapshot(kind=kind) for kind in n5_kinds
        } == n5_inventory_before
        assert n5_calls == []

        # Removing the selected profile view cannot infer a first-N5 branch.
        missing_diagnostics = dict(source_cycle.simulation.diagnostics)
        missing_diagnostics.pop("candidate_simulation_n4_source_selected_ref")
        missing_diagnostics.pop("candidate_simulation_n4_source_ref")
        missing_source_cycle = source_cycle.model_copy(
            update={
                "simulation": source_cycle.simulation.model_copy(
                    update={"diagnostics": missing_diagnostics}
                )
            }
        )
        assert not candidate_source_first_n5_deferred(missing_source_cycle)
        reads_before = len(load_calls)
        _expect_prior_refusal(resolve, "candidate_source_prior_n5_execution_not_established")
        assert len(load_calls) == reads_before

        # Wrong kind/profile selection must refuse before using source bytes.
        wrong_kind_ref = context_job_ref
        wrong_kind_diagnostics = dict(source_cycle.simulation.diagnostics)
        wrong_kind_diagnostics["candidate_simulation_n4_source_selected_ref"] = (
            wrong_kind_ref.model_dump(mode="json")
        )
        wrong_kind_diagnostics["candidate_simulation_n4_source_ref"] = str(
            wrong_kind_ref.artifact_id
        )
        wrong_kind_cycle = source_cycle.model_copy(
            update={
                "simulation": source_cycle.simulation.model_copy(
                    update={"diagnostics": wrong_kind_diagnostics}
                )
            }
        )
        assert not candidate_source_first_n5_deferred(wrong_kind_cycle)
        _expect_prior_refusal(
            lambda: resolve(wrong_kind_cycle),
            "candidate_source_prior_n5_execution_not_established",
        )
        assert len(load_calls) == reads_before

        # A selected ref with the same artifact ID but a foreign manifest
        # profile reaches the CAS reader and fails before any N5 artifact write.
        wrong_profile_ref = generation.source_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "e" * 64}
        )
        wrong_profile_diagnostics = dict(source_cycle.simulation.diagnostics)
        wrong_profile_diagnostics["candidate_simulation_n4_source_selected_ref"] = (
            wrong_profile_ref.model_dump(mode="json")
        )
        wrong_profile_cycle = source_cycle.model_copy(
            update={
                "simulation": source_cycle.simulation.model_copy(
                    update={"diagnostics": wrong_profile_diagnostics}
                )
            }
        )
        assert candidate_source_first_n5_deferred(wrong_profile_cycle)
        reads_before = len(load_calls)
        with pytest.raises((OSError, RuntimeError, TypeError, ValueError)):
            resolve(wrong_profile_cycle)
        assert len(load_calls) == reads_before + 1

        # A foreign problem or candidate cannot reuse the selected source.
        foreign_problem = problem.model_copy(
            update={"problem_statement": problem.problem_statement + " Foreign subject."}
        )
        reads_before = len(load_calls)
        _expect_prior_refusal(
            lambda: resolve(selected_problem=foreign_problem),
            "candidate_source_prior_n4_source_mismatch",
        )
        assert len(load_calls) == reads_before + 1

        foreign_candidate = "candidate:foreign-first-n5"
        foreign_simulation = source_cycle.simulation.model_copy(
            update={"candidate_id": foreign_candidate}
        )
        foreign_value = source_cycle.value_port.model_copy(
            update={"candidate_id": foreign_candidate}
        )
        foreign_candidate_cycle = source_cycle.model_copy(
            update={
                "selected_candidate_ref": foreign_candidate,
                "selected_candidate_content_hash": "sha256:" + "a" * 64,
                "simulation": foreign_simulation,
                "value_port": foreign_value,
            }
        )
        assert candidate_source_first_n5_deferred(foreign_candidate_cycle)
        reads_before = len(load_calls)
        _expect_prior_refusal(
            lambda: resolve(foreign_candidate_cycle),
            "candidate_source_prior_n4_source_mismatch",
        )
        assert len(load_calls) == reads_before + 1

        forged_n5_input = _ref("runtime.quality.candidate_simulation_n5_input", "9")
        forged_n5_result = _ref(JOINT_SIMULATION_RESULT_ARTIFACT_KIND, "8")
        generic_n5_input = _ref(
            "runtime.quality.generic_cycle_simulation_n5_input",
            "7",
        )
        forged_cases = (
            source_cycle.model_copy(
                update={
                    "simulation": source_cycle.simulation.model_copy(
                        update={"candidate_simulation_n5_input_ref": forged_n5_input}
                    )
                }
            ),
            source_cycle.model_copy(
                update={
                    "simulation": source_cycle.simulation.model_copy(
                        update={"simulation_result_ref": forged_n5_result}
                    )
                }
            ),
            source_cycle.model_copy(
                update={
                    "simulation": source_cycle.simulation.model_copy(
                        update={
                            "candidate_simulation_n5_input_ref": forged_n5_input,
                            "generic_n5_input_ref": generic_n5_input,
                        }
                    )
                }
            ),
        )
        for forged_cycle in forged_cases:
            assert not candidate_source_first_n5_deferred(forged_cycle)
            reads_before = len(load_calls)
            _expect_prior_refusal(
                lambda forged_cycle=forged_cycle: resolve(forged_cycle),
                "candidate_source_prior_n5_execution_not_established",
            )
            assert len(load_calls) == reads_before

        blocker_and_branch_controls = (
            source_cycle.model_copy(
                update={
                    "terminal_kind": "budget_exhausted",
                }
            ),
            source_cycle.model_copy(
                update={
                    "simulation": source_cycle.simulation.model_copy(
                        update={
                            "diagnostics": {
                                **source_cycle.simulation.diagnostics,
                                "port": "N5",
                            }
                        }
                    )
                }
            ),
            source_cycle.model_copy(
                update={
                    "simulation": source_cycle.simulation.model_copy(
                        update={
                            "diagnostics": {
                                **source_cycle.simulation.diagnostics,
                                "scheduler_action": "advance",
                            }
                        }
                    )
                }
            ),
            source_cycle.model_copy(
                update={
                    "simulation": source_cycle.simulation.model_copy(
                        update={"authority_blockers": ("forged_blocker",)}
                    )
                }
            ),
            source_cycle.model_copy(
                update={
                    "value_port": source_cycle.value_port.model_copy(
                        update={"authority_blockers": ("forged_blocker",)}
                    )
                }
            ),
        )
        for invalid_cycle in blocker_and_branch_controls:
            assert not candidate_source_first_n5_deferred(invalid_cycle)
            reads_before = len(load_calls)
            _expect_prior_refusal(
                lambda invalid_cycle=invalid_cycle: resolve(invalid_cycle),
                "candidate_source_prior_n5_execution_not_established",
            )
            assert len(load_calls) == reads_before

        assert n5_calls == []
        assert {
            kind: store.manifest_inventory_snapshot(kind=kind) for kind in n5_kinds
        } == n5_inventory_before
