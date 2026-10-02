from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.resilience import (
    guard_runtime_cas,
    guard_runtime_control_store,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.cycle_substrate import (
    CycleSubstrateContextArtifactOwner,
    CycleSubstrateContextOwnerError,
    VerifiedNLJobScope,
)
from tests.unit.runtime.quality.test_cycle_substrate import (
    _authenticated_tenant_scope,
    _cycle_context,
    _design_problem,
    _registry,
    _world_record,
)


def test_cycle_substrate_context_owner_uses_guarded_current_job_execution(
    tmp_path: Any,
) -> None:
    """The persisted served-job lease, not supplied IDs, binds context replay."""

    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        registry=registry,
        world_model_record=world,
    )
    raw_control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )
    control_store = guard_runtime_control_store(raw_control_store)
    raw_artifact_store = FileSystemCAS(
        tmp_path / "cycle-context-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    artifact_store = guard_runtime_cas(raw_artifact_store)
    owner = CycleSubstrateContextArtifactOwner(
        store=artifact_store,
        control_store=control_store,
    )

    def _create_and_lease(job_id: str, run_id: str, worker_id: str) -> Any:
        control_store.create_job(
            job_id=job_id,
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="research",
            effective_execution_profile="research",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref="payload:" + job_id,
            submitted_by="test-worker",
        )
        leased = control_store.lease_next_job(
            worker_id=worker_id,
            lease_seconds=60,
        )
        assert leased is not None and leased.job_id == job_id
        return leased

    lease_a = _create_and_lease("job-a", "run-a", "worker-a")
    lease_b = _create_and_lease("job-b", "run-b", "worker-b")
    try:
        with _authenticated_tenant_scope(
            tenant_id="tenant-context-owner", cell_id="cell-context-owner"
        ):
            with control_store.job_execution_fence(
                job_id=lease_a.job_id,
                worker_id=lease_a.lease_owner,
                attempt=lease_a.attempt,
            ):
                ref_a = owner.persist_for_current_job(context, problem=problem)
                resolved_a = owner.resolve_for_current_job(ref_a, problem=problem)
                assert resolved_a.profile_admission_status == "not_established"
                assert resolved_a.s8_status == "blocked"

                changed_problem = problem.model_copy(
                    update={
                        "problem_statement": (
                            problem.problem_statement + " Preserve the same display identity."
                        )
                    }
                )
                with pytest.raises(
                    CycleSubstrateContextOwnerError,
                    match="cycle_substrate_context_job_binding_mismatch",
                ):
                    owner.resolve_for_current_job(ref_a, problem=changed_problem)

            with control_store.job_execution_fence(
                job_id=lease_b.job_id,
                worker_id=lease_b.lease_owner,
                attempt=lease_b.attempt,
            ):
                # The consumer cannot replay A by presenting A's IDs: the API
                # derives identity from B's current persisted execution fence.
                with pytest.raises(
                    CycleSubstrateContextOwnerError,
                    match="cycle_substrate_context_job_binding_mismatch",
                ):
                    owner.resolve_for_current_job(ref_a, problem=problem)
                ref_b = owner.persist_for_current_job(context, problem=problem)
                resolved_b = owner.resolve_for_current_job(ref_b, problem=problem)

        assert resolved_a.job_id == lease_a.job_id
        assert resolved_a.run_id == lease_a.run_id
        assert resolved_b.job_id == lease_b.job_id
        assert resolved_b.run_id == lease_b.run_id
    finally:
        artifact_store.close()
        control_store.close()


def test_cycle_substrate_context_owner_rejects_matching_marker_scope_without_issuance(
    tmp_path: Any,
) -> None:
    """Matching scope fields cannot substitute for issuance by the verified NL owner."""
    from polisyos.core.security import get_current_access_scope_or_none, tenant_scope

    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        registry=registry,
        world_model_record=world,
    )
    raw_control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )
    control_store = guard_runtime_control_store(raw_control_store)
    raw_artifact_store = FileSystemCAS(
        tmp_path / "cycle-context-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    artifact_store = guard_runtime_cas(raw_artifact_store)
    owner = CycleSubstrateContextArtifactOwner(
        store=artifact_store,
        control_store=control_store,
    )
    tenant_id = "tenant-verified-simulate-only"
    cell_id = "cell-verified-simulate-only"
    control_store.create_job(
        job_id="job-verified-simulate-only",
        kind="natural_language_run",
        run_id="run-verified-simulate-only",
        pipeline_id=None,
        requested_execution_profile="research",
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref="payload:verified-simulate-only",
        submitted_by="fixture-actor",
    )
    leased = control_store.lease_next_job(
        worker_id="worker-verified-simulate-only",
        lease_seconds=60,
    )
    assert leased is not None
    scope_values = {
        "job_id": leased.job_id,
        "run_id": str(leased.run_id),
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "worker_id": str(leased.lease_owner),
        "attempt": leased.attempt,
        "admission_status": "established",
        "intent_band": "simulate_only_attempt",
        "canonical_mode": "simulate_only",
        "route_id": "POST /api/v1/control/runs/nl",
        "route_action": "control.launch_nl_run",
        "admission_surface": "served_route",
        "actor_subject": "fixture-actor",
        "actor_authenticated": True,
        "intent_digest": "sha256:" + "a" * 64,
    }
    forged_scope = VerifiedNLJobScope(**scope_values)
    assert not forged_scope._was_issued_by_verified_nl_execution_owner
    try:
        with (
            tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
            control_store.job_execution_fence(
                job_id=leased.job_id,
                worker_id=str(leased.lease_owner),
                attempt=leased.attempt,
            ),
        ):
            assert get_current_access_scope_or_none() is None
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="cycle_substrate_context_job_verified_scope_mismatch",
            ):
                owner.persist_for_current_job(
                    context,
                    problem=problem,
                    verified_nl_job_scope=forged_scope,
                )

        with (
            _authenticated_tenant_scope(tenant_id=tenant_id, cell_id=cell_id),
            control_store.job_execution_fence(
                job_id=leased.job_id,
                worker_id=str(leased.lease_owner),
                attempt=leased.attempt,
            ),
        ):
            ref = owner.persist_for_current_job(context, problem=problem)

        with (
            tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
            control_store.job_execution_fence(
                job_id=leased.job_id,
                worker_id=str(leased.lease_owner),
                attempt=leased.attempt,
            ),
        ):
            assert get_current_access_scope_or_none() is None
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="cycle_substrate_context_job_verified_scope_mismatch",
            ):
                owner.resolve_for_current_job(
                    ref,
                    problem=problem,
                    verified_nl_job_scope=forged_scope,
                )
    finally:
        artifact_store.close()
        control_store.close()


def test_candidate_handoff_requires_complete_model_binding_and_exact_ncm_membership(
    tmp_path: Any,
) -> None:
    """The persisted worker handoff carries the owner-selected NCM identity."""
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import candidate_ncm_spec_from_declaration
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextHandoff,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        _cycle_job_v1_design_problem_ref,
        _cycle_job_v1_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from polisyos.runtime.quality.world_model_record import (
        derive_candidate_scenario_world_model_record,
    )

    problem = _design_problem()
    registry = _registry("education")
    base_context = _cycle_context(
        design_problem_ref=_cycle_job_v1_design_problem_ref(problem),
        registry=registry,
    )
    inputs = CandidateSimulationContextInputs(
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        world_model_record=base_context.world_model_record,
        intervention_substrate=base_context.intervention_substrate,
        candidate_levers=base_context.candidate_levers,
        transport_context=base_context.transport_context,
        source_pack_content_hash=base_context.source_pack_content_hash,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="teaching_method_set_to",
        parameter_id="intensity",
        target_world_slot="education.teaching_method",
        unit_id="synthetic_score",
        minimum=0,
        maximum=1,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://handoff/controlled-candidate",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={
            "education.teaching_method": 0.0,
            "learning_outcomes": 0.0,
        },
        seed=7,
        replications=2,
    )
    profile_fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "handoff-controlled-candidate",
        "profile_selection_ref": _cycle_job_v1_profile_selection_ref(problem),
        "context_inputs": inputs,
        "rule": rule,
        "n5": n5,
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
    declaration_fields = {
        "schema_version": (
            "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"
        ),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": "learning_outcomes",
        "target_unit_id": rule.unit_id,
        "outcome_unit_id": rule.unit_id,
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": 0.5,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    tenant_id = "tenant-candidate-handoff"
    cell_id = "cell-candidate-handoff"
    job_id = "job-candidate-handoff"
    run_id = "run-candidate-handoff"
    store = FileSystemCAS(
        tmp_path / "candidate-handoff-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    repository = GenerationSourceRepository(store)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        declaration_ref = repository.persist_candidate_model_declaration(
            declaration=declaration,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        ncm_ref = repository.persist_candidate_ncm_selected_view(
            ncm_spec=candidate_ncm_spec_from_declaration(declaration),
            declaration_ref=declaration_ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            profile_content_hash=profile.content_hash,
        )
    context = _cycle_context(
        design_problem_ref=_cycle_job_v1_design_problem_ref(problem),
        registry=registry,
        world_model_record=derive_candidate_scenario_world_model_record(
            base_context.world_model_record,
            ncm_artifact_ref=ncm_ref,
            declaration_content_hash=declaration.content_hash,
        ),
    )
    payload = {
        "context": context,
        "context_job_ref": ArtifactRef(
            artifact_id="sha256:" + "c" * 64,
            kind="runtime.quality.cycle_substrate_context_job",
            media_type="application/json",
        ),
        "profile": profile,
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "job_id": job_id,
        "run_id": run_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "model_declaration": declaration,
        "model_declaration_ref": declaration_ref,
        "ncm_ref": ncm_ref,
    }

    handoff = CandidateSimulationContextHandoff.model_validate(payload)
    assert handoff.ncm_ref == ncm_ref
    assert handoff.ncm_ref.manifest_profile_sha256 is not None
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        assert store.get_manifest(ncm_ref).inputs[0].artifact_id == declaration_ref.artifact_id

    with pytest.raises(ValueError, match="model_binding_incomplete"):
        CandidateSimulationContextHandoff.model_validate(
            {**payload, "ncm_ref": None}
        )

    foreign_ref = ncm_ref.model_copy(update={"artifact_id": "sha256:" + "d" * 64})
    with pytest.raises(ValueError, match="selected_ref_mismatch"):
        CandidateSimulationContextHandoff.model_validate(
            {**payload, "ncm_ref": foreign_ref}
        )
