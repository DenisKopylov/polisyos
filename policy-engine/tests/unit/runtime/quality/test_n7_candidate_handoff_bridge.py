"""N7 handoff bridge behavior against the controlled served-job owner path."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_initial_served_handoff_is_owner_resolved_before_n7_context_ref_use(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Initial N4 handoff resolution retains only its exact owner-read CAS ref.

    This exercises the served setup boundary only. The N7 transition property is
    covered separately by the acquired-world re-entry test.
    """

    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
    )
    from tests.unit.runtime.http import test_control_service_di as served_fixture

    observed_controllers: list[GenerationCycleController] = []
    original = GenerationCycleController._ensure_selected_candidate_source_profile

    def record_resolution(
        self: GenerationCycleController,
        problem: object,
        *,
        previous_problem: object | None = None,
    ) -> None:
        result = original(self, problem, previous_problem=previous_problem)
        if self._candidate_simulation_handoff is not None:
            observed_controllers.append(self)
        return result

    monkeypatch.setattr(
        GenerationCycleController,
        "_ensure_selected_candidate_source_profile",
        record_resolution,
    )
    fixture = await served_fixture._run_controlled_simulate_only_job_fixture(
        monkeypatch,
        tmp_path,
    )
    try:
        assert observed_controllers
        controller = observed_controllers[0]
        handoff = controller._candidate_simulation_handoff
        assert handoff is not None
        assert controller._candidate_cycle_context_job_ref == handoff.context_job_ref
        assert (
            controller._candidate_cycle_context_artifact_owner._store is controller._artifact_store
        )
        assert controller._candidate_cycle_verified_nl_job_scope._was_issued_by_verified_nl_execution_owner
        assert (
            controller._candidate_simulation_context_admission_owner
            is fixture.service._cycle_substrate_context_admission_owner
        )

        # Present-but-foreign job identity cannot fall through to a fresh profile
        # build or reuse the existing context marker.
        foreign_handoff = handoff.model_copy(update={"job_id": "foreign-job"})
        controller._candidate_simulation_handoff = foreign_handoff
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_scope_mismatch",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_handoff = handoff

        # A stale or unestablished lease is refused even when the handoff and
        # owner are still present.
        currentness = controller._candidate_simulation_currentness_resolver
        controller._candidate_simulation_currentness_resolver = lambda: False
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_currentness_not_established",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_currentness_resolver = currentness

        # A malformed supplied value is a refusal, not an absent handoff that
        # permits profile fallback.
        controller._candidate_simulation_handoff = {"job_id": handoff.job_id}
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_untyped",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_handoff = handoff

        # Remove the owner readback property while leaving the typed handoff and
        # claimed currentness callable present. Neither marker can admit a ref.
        from types import SimpleNamespace

        owner = controller._candidate_cycle_context_artifact_owner
        currentness = controller._candidate_simulation_currentness_resolver
        controller._candidate_simulation_currentness_resolver = lambda: True
        monkeypatch.setattr(
            owner,
            "resolve_for_current_job",
            lambda *args, **kwargs: SimpleNamespace(),
        )
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_owner_readback_mismatch",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_currentness_resolver = currentness
    finally:
        fixture.service.close()


def test_acquisition_worker_handoff_uses_live_control_admission_without_n5(
    tmp_path: Path,
) -> None:
    """Resolve an acquired-world context only under its real SQLite worker lease."""

    from pathlib import Path

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextHandoff,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
        GenerationCycleController,
        GenerationCycleError,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from tests.unit.runtime.http.test_control_plane_store import (
        _fence_leased_execution,
        _job_creation_event,
        _job_execution_scope,
        _make_store,
        _prepared_candidate_action_head,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import (
        _cycle_context,
        _design_problem,
        _registry,
        _world_record,
    )

    store = _make_store(tmp_path)
    publication = _prepared_candidate_action_head(job_id="candidate-action-n7-owner")
    execution_scope = {
        **_job_execution_scope(),
        "tenant_id": publication.tenant_id,
        "cell_id": publication.cell_id,
    }
    creation_event = {
        **_job_creation_event(execution_scope=execution_scope),
        "job_id": publication.job_id,
        "run_id": publication.run_id,
        "job_kind": "acquisition",
        "payload_ref": publication.payload_ref,
        "submitted_by": "denis",
        "policy_flags": {},
        "capability_manifest_ref": None,
    }
    job = store.create_job(
        job_id=publication.job_id,
        kind="acquisition",
        run_id=publication.run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=publication.payload_ref,
        submitted_by="denis",
        creation_event_payload=creation_event,
        prepared_acquisition_action_head=publication,
    )
    cas = FileSystemCAS(
        tmp_path / "candidate-action-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method", "learning_outcomes"),
    )
    context = _cycle_context(
        registry=registry,
        world_model_record=world,
        design_problem_ref=cycle_job_design_problem_ref(problem),
    )
    context_inputs = CandidateSimulationContextInputs(
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        world_model_record=world,
        intervention_substrate=context.intervention_substrate,
        candidate_levers=context.candidate_levers,
        transport_context=context.transport_context,
        source_pack_content_hash=context.source_pack_content_hash,
        substrate_input_content_hash=context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="teaching_method_set_to",
        parameter_id="intensity",
        target_world_slot="education.teaching_method",
        unit_id="synthetic_score",
        minimum=0,
        maximum=1,
    )
    profile_fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "n7-acquisition-worker-owner",
        "profile_selection_ref": cycle_job_profile_selection_ref(problem),
        "context_inputs": context_inputs,
        "rule": rule,
        "n5": CandidateScenarioN5Config(
            budget_ref="budget://n7-acquisition-worker-owner",
            horizon=HorizonSpec(start=0, end=0, step=1),
            baseline_state={
                "education.teaching_method": 0.0,
                "learning_outcomes": 0.0,
            },
            seed=7,
            replications=2,
        ),
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    profile_draft = CandidateSimulationScenarioProfile.model_construct(
        **profile_fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **profile_fields,
            "content_hash": gy_content_hash(
                profile_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    owner = CycleSubstrateContextArtifactOwner(store=cas, control_store=store)
    project_root = Path(__file__).resolve().parents[4]

    try:
        with tenant_scope(
            None,
            tenant_id=publication.tenant_id,
            cell_id=publication.cell_id,
        ):
            with _fence_leased_execution(store, job=job):
                admission = store.current_execution_job_admission()
                assert admission.job.job_id == publication.job_id
                assert admission.job.kind == "acquisition"
                assert admission.scope.tenant_id == publication.tenant_id
                assert admission.scope.cell_id == publication.cell_id
                assert publication.action_kind == (
                    "runtime.evidence.acquisition.candidate_experiment.execute"
                )
                head = store.get_acquisition_action_head(
                    tenant_id=publication.tenant_id,
                    cell_id=publication.cell_id,
                    run_id=publication.run_id,
                    source_job_id=publication.source_job_id,
                    route_id=publication.route_id,
                    action_generation=publication.action_generation,
                )
                assert head is not None
                assert head.job_id == publication.job_id
                context_ref = owner.persist_for_current_job(
                    context,
                    problem=problem,
                    return_selected_profile=True,
                )
                assert context_ref.manifest_profile_sha256 is not None
                handoff = CandidateSimulationContextHandoff(
                    context=context,
                    context_job_ref=context_ref,
                    profile=profile,
                    profile_config_ref=candidate_simulation_profile_ref(profile),
                    job_id=admission.job.job_id,
                    run_id=admission.job.run_id,
                    tenant_id=admission.scope.tenant_id,
                    cell_id=admission.scope.cell_id,
                )

                def currentness() -> bool:
                    live = store.current_execution_job_admission()
                    return (
                        live.job.job_id == admission.job.job_id
                        and live.job.run_id == admission.job.run_id
                        and live.attempt == admission.attempt
                        and live.scope == admission.scope
                    )

                controller = GenerationCycleController(
                    repo_root=project_root,
                    model_id="n7-acquisition-owner-fixture",
                    authority_scope="contract_testing",
                    artifact_store=cas,
                    cycle_substrate_context=context,
                    candidate_simulation_handoff=handoff,
                    candidate_simulation_currentness_resolver=currentness,
                )
                controller._candidate_source_reentry_context_binding = (owner, handoff)

                n5_inputs_before = cas.manifest_inventory_snapshot(
                    kind="runtime.quality.candidate_simulation_n5_input"
                ).entries
                n5_results_before = cas.manifest_inventory_snapshot(
                    kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND
                ).entries
                assert controller._resolve_candidate_simulation_context_handoff(problem) is True

                controller._candidate_source_reentry_context_binding = None
                with pytest.raises(
                    GenerationCycleError,
                    match="n7_candidate_simulation_context_owner_binding_missing",
                ):
                    controller._resolve_candidate_simulation_context_handoff(problem)

                controller._candidate_source_reentry_context_binding = (
                    CycleSubstrateContextArtifactOwner(
                        store=FileSystemCAS.open_existing_read_only(
                            tmp_path / "candidate-action-cas"
                        ),
                        control_store=store,
                    ),
                    handoff,
                )
                with pytest.raises(
                    GenerationCycleError,
                    match="n7_candidate_simulation_context_owner_binding_missing",
                ):
                    controller._resolve_candidate_simulation_context_handoff(problem)

                wrong_ref_payload = handoff.model_dump(mode="json")
                wrong_ref_payload["context_job_ref"]["artifact_id"] = "sha256:" + "f" * 64
                wrong_ref_handoff = CandidateSimulationContextHandoff.model_validate(
                    wrong_ref_payload
                )
                controller._candidate_simulation_handoff = wrong_ref_handoff
                controller._candidate_source_reentry_context_binding = (
                    owner,
                    wrong_ref_handoff,
                )
                with pytest.raises(
                    GenerationCycleError,
                    match="n7_candidate_simulation_handoff_owner_refused",
                ):
                    controller._resolve_candidate_simulation_context_handoff(problem)
                controller._candidate_simulation_handoff = handoff

                controller._candidate_source_reentry_context_binding = (
                    owner,
                    handoff.model_copy(update={"job_id": "foreign-job"}),
                )
                with pytest.raises(
                    GenerationCycleError,
                    match="n7_candidate_simulation_handoff_scope_mismatch",
                ):
                    controller._resolve_candidate_simulation_context_handoff(problem)

                controller._candidate_source_reentry_context_binding = (owner, handoff)
                controller._candidate_simulation_currentness_resolver = lambda: False
                with pytest.raises(
                    GenerationCycleError,
                    match="n7_candidate_simulation_handoff_currentness_not_established",
                ):
                    controller._resolve_candidate_simulation_context_handoff(problem)
                controller._candidate_simulation_currentness_resolver = currentness

                # A stale captured boolean cannot substitute for a live Control
                # lease. End the actual acquisition job while retaining the
                # typed pair, then let the real artifact owner refuse readback.
                store.complete_job(job_id=job.job_id, run_id=job.run_id)
            controller._candidate_simulation_currentness_resolver = lambda: True
            with pytest.raises(
                GenerationCycleError,
                match="n7_candidate_simulation_handoff_owner_refused",
            ):
                controller._resolve_candidate_simulation_context_handoff(problem)
            n5_inputs_after = cas.manifest_inventory_snapshot(
                kind="runtime.quality.candidate_simulation_n5_input"
            )
            n5_results_after = cas.manifest_inventory_snapshot(
                kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND
            )
            assert n5_inputs_after.verdict == "pass"
            assert n5_results_after.verdict == "pass"
            assert n5_inputs_after.entries == n5_inputs_before
            assert n5_results_after.entries == n5_results_before
    finally:
        store.close()
