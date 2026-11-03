"""Exercise the real fenced NL owner and same-store candidate context."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_fenced_nl_owner_reopens_same_store_candidate_world_and_refuses_without_fence(
    tmp_path: Path,
) -> None:
    """A candidate context is owner-read only while its issued job fence is active."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.control import NaturalLanguageRunRequest
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        build_cycle_substrate_context,
        cycle_job_design_problem_ref,
    )
    from polisyos.runtime.quality.data_forge_binding import bind_measurement_root_execution_scope
    from polisyos.runtime.quality.design_problem import (
        DESIGN_PROBLEM_V3_SCHEMA_VERSION,
        DesignProblem,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
    )
    from polisyos.runtime.quality.world_model_record import load_world_model_record
    from tests._helpers.runtime_http import _build_control_service, _valid_intake_for_mode
    from tests._helpers.world_model_record import _build_record, _substrate_registry
    from tests.unit.remediation.test_acq_01 import _problem
    from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
    from tests.unit.runtime.http.test_control_service_di import _fixture_claims

    problem = _problem(domain="fiscal_credit")
    lever = problem.candidate_lever_space.candidate_levers[0].model_copy(
        update={"target_slot": "agents.income"}
    )
    problem = problem.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_V3_SCHEMA_VERSION,
            "jurisdiction_time": problem.jurisdiction_time.model_copy(update={"region": "UA-30"}),
            "candidate_lever_space": problem.candidate_lever_space.model_copy(
                update={"candidate_levers": [lever]}
            ),
        }
    )
    problem = DesignProblem.model_validate(problem.model_dump(mode="python"))
    assert cycle_job_design_problem_ref(problem) == gy_content_hash(problem.model_dump(mode="json"))
    tenant_id, cell_id = "tenant-fixture", "cell-fixture"
    store = FileSystemCAS(tmp_path / "cas").for_tenant(tenant_id, cell_id)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        service = _build_control_service(tmp_path / "s", artifact_store=store)
    try:
        request = NaturalLanguageRunRequest(
            request=problem.nl_provenance.raw_request,
            llm_model="simulated-qwen",
            context={
                "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                    mode="json"
                )
            },
            max_iterations=1,
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        lease = service._control_store.lease_next_job(
            worker_id="n7-context-fixture", lease_seconds=600
        )
        assert lease is not None and lease.job_id == launch.job_id
        with service._control_store.job_execution_fence(
            job_id=lease.job_id, worker_id=lease.lease_owner, attempt=lease.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                job, scope = admission.job, admission.scope
                payload = service._load_control_nl_job_payload(job)
                payload = service._payload_for_execution_scope(
                    payload, job=job, execution_scope=scope
                )
                manifest_ref, manifest = service._resolve_capability_manifest_for_execution(
                    job=job, admission=admission, execution_scope=scope
                )
                binding = service._bind_control_job_execution_intent(
                    job=job,
                    admission=admission,
                    execution_scope=scope,
                    payload=payload,
                    capability_manifest_ref=manifest_ref,
                    capability_manifest=manifest,
                )
                assert binding is not None
                verified = binding["_verified_nl_job_scope"]
                assert verified._was_issued_by_verified_nl_execution_owner
                measurement_binding = bind_measurement_root_execution_scope(
                    admission=admission, job=job, execution_scope=scope
                )
                assert measurement_binding.authority_eligible
                assert measurement_binding.admission is admission

                selected_store, world_build, _, _ = _build_record(
                    tmp_path / "w", artifact_store=store
                )
                assert selected_store is service._artifact_store is store
                world = load_world_model_record(store, world_build.record_ref)
                assert world == world_build.record
                registry = _substrate_registry()
                additional_denials = (
                    "unverified_measurement_requirement:catalog_quality_score_is_source_asserted",
                    "unverified_measurement_requirement:worldbank_indicator_id_may_be_request_fallback",
                )
                context = build_cycle_substrate_context(
                    design_problem_ref=cycle_job_design_problem_ref(problem),
                    domain=problem.domain,
                    substrate_registry=registry,
                    selected_registry_entry_hashes=tuple(
                        entry.entry_content_hash for entry in registry.entries
                    ),
                    world_model_record=world,
                    intervention_substrate=None,
                    candidate_levers=(),
                    transport_context=None,
                    source_pack_content_hash=None,
                    substrate_input_content_hash=None,
                    additional_authority_denials=additional_denials,
                )
                owner = CycleSubstrateContextArtifactOwner(
                    store=store, control_store=service._control_store
                )
                controller = GenerationCycleController(
                    authority_scope="contract_testing",
                    repo_root=tmp_path,
                    artifact_store=store,
                    cycle_substrate_context=context,
                    candidate_cycle_context_artifact_owner=owner,
                    candidate_cycle_verified_nl_job_scope=verified,
                    measurement_root_execution_binding=measurement_binding,
                )
                context_ref = controller._persist_resolve_and_bind_cycle_substrate_context(
                    context, previous_problem=problem, problem=problem
                )
                reopened = owner.resolve_for_current_job(
                    context_ref,
                    problem=problem,
                    repo_root=tmp_path,
                    verified_nl_job_scope=verified,
                )
                assert reopened.context == context
                assert set(additional_denials).issubset(reopened.context.may_not_use_for)
                assert {
                    "grounding_authority",
                    "transport_authority",
                    "promotion_authority",
                }.issubset(reopened.context.may_not_use_for)
                with pytest.raises(ValueError, match="cycle_substrate_content_hash_mismatch"):
                    type(context).model_validate(
                        {
                            **context.model_dump(mode="python"),
                            "may_not_use_for": tuple(
                                item
                                for item in context.may_not_use_for
                                if item != additional_denials[0]
                            ),
                        }
                    )
                assert reopened.context.world_model_record == world
                assert reopened.job_id == job.job_id and reopened.run_id == job.run_id
                assert reopened.tenant_id == tenant_id and reopened.cell_id == cell_id
                assert controller._candidate_cycle_context_job_ref == context_ref

                # Preserve the problem ID while changing its actual content.
                foreign_problem = problem.model_copy(
                    update={"problem_statement": problem.problem_statement + " Changed subject."}
                )
                with pytest.raises(
                    GenerationCycleError, match="generation_cycle_context_rebind_problem_mismatch"
                ):
                    controller._persist_resolve_and_bind_cycle_substrate_context(
                        context,
                        previous_problem=problem,
                        problem=foreign_problem,
                        context_job_ref=context_ref,
                    )

        # The same lease is still running: removing the handler fence must be
        # sufficient to refuse the otherwise unchanged scope and context.
        running = service._control_store.get_job(job.job_id)
        assert running is not None and running.state == "running"
        assert running.attempt == lease.attempt and running.lease_owner == lease.lease_owner
        with (
            tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
            pytest.raises(
                GenerationCycleError, match="generation_cycle_context_rebind_owner_refused"
            ),
        ):
            controller._persist_resolve_and_bind_cycle_substrate_context(
                context,
                previous_problem=problem,
                problem=problem,
                context_job_ref=context_ref,
            )

        # Restore the same live fence, prove owner readback returns, then make
        # the persisted job terminal while that handler fence is still bound.
        with (
            service._control_store.job_execution_fence(
                job_id=lease.job_id, worker_id=lease.lease_owner, attempt=lease.attempt
            ),
            service._install_execution_scope(scope),
        ):
            restored = owner.resolve_for_current_job(
                context_ref,
                problem=problem,
                repo_root=tmp_path,
                verified_nl_job_scope=verified,
            )
            assert restored.context == context
            service._control_store.complete_job(job_id=job.job_id, run_id=job.run_id)
            completed = service._control_store.get_job(job.job_id)
            assert completed is not None and completed.state == "completed"
            with pytest.raises(
                GenerationCycleError, match="generation_cycle_context_rebind_owner_refused"
            ):
                controller._persist_resolve_and_bind_cycle_substrate_context(
                    context,
                    previous_problem=problem,
                    problem=problem,
                    context_job_ref=context_ref,
                )
    finally:
        service.close()
