"""Natural-language control-job execution facet."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts import ArtifactRef, ArtifactTenantContextInfo
from polisyos.runtime.http.services.control.generation_cycle import (
    N4CandidateProposalExecution,
    N4CandidateScenarioProposalOnlyExecution,
)
from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand

from .job_nl_publication import _n4_proposal_progress_with_budget

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationExecutionV5
    from polisyos.runtime.quality.generation_cycle import _GenerationCycleN5Completion

    from .job_nl_context import _ControlNLJobContext


class ControlNLJobExecutionMixin:
    """Run admitted NL compilation and terminate handled candidate outcomes."""

    def _persist_current_nl_owner_projection(self, context: _ControlNLJobContext) -> None:
        """Persist the current NL worker owner before any branch can terminate."""
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobExecutionAdmissionError,
            ControlJobLeaseLostError,
        )
        from polisyos.runtime.quality.phase_barriers import (
            _execution_owner_binding_from_admission,
            _validated_execution_owner_binding,
        )

        try:
            admission = self._control_store.current_execution_job_admission()
        except (ControlJobExecutionAdmissionError, ControlJobLeaseLostError) as exc:
            raise ControlJobLeaseLostError("control_job_terminal_admission_not_current") from exc

        original = context.admission
        if (
            admission.job.job_id != original.job.job_id
            or admission.job.job_id != context.job.job_id
            or admission.job.run_id != original.job.run_id
            or admission.job.run_id != context.job.run_id
            or admission.job.requested_execution_profile != original.job.requested_execution_profile
            or admission.job.requested_execution_profile != context.job.requested_execution_profile
            or admission.job.effective_execution_profile != original.job.effective_execution_profile
            or admission.job.effective_execution_profile != context.job.effective_execution_profile
            or admission.attempt != original.attempt
            or admission.attempt != context.job.attempt
            or admission.job.lease_owner != original.job.lease_owner
            or admission.job.lease_owner != context.job.lease_owner
            or admission.scope != original.scope
            or admission.scope != context.execution_scope
        ):
            raise ControlJobLeaseLostError("control_job_terminal_owner_binding_not_current")

        owner_binding = _execution_owner_binding_from_admission(
            admission,
            expected_job_id=context.job.job_id,
            expected_run_id=str(context.job.run_id or ""),
            expected_effective_profile=context.job.effective_execution_profile,
            expected_scope={
                "tenant_id": context.execution_scope.tenant_id,
                "cell_id": context.execution_scope.cell_id,
            },
        )
        if owner_binding is None:
            # Unknown scope can remain candidate-grade. Carry no invented owner.
            return

        progress = admission.job.progress
        persisted_owner = _validated_execution_owner_binding(
            progress.get("execution_owner_binding"),
            expected=owner_binding,
        )
        if persisted_owner is not None:
            return
        if "execution_owner_binding" in progress:
            raise ControlJobLeaseLostError("control_job_terminal_owner_binding_not_current")

        owner_progress = dict(progress)
        owner_progress["state"] = "running"
        owner_progress["execution_owner_binding"] = owner_binding
        self._control_store.update_progress_state(
            job_id=context.job.job_id,
            state="running",
            progress=owner_progress,
            expected_lease_owner=admission.job.lease_owner,
            expected_attempt=admission.attempt,
        )

        try:
            current = self._control_store.current_execution_job_admission()
        except (ControlJobExecutionAdmissionError, ControlJobLeaseLostError) as exc:
            raise ControlJobLeaseLostError("control_job_terminal_admission_not_current") from exc
        current_owner = _execution_owner_binding_from_admission(
            current,
            expected_job_id=context.job.job_id,
            expected_run_id=str(context.job.run_id or ""),
            expected_effective_profile=context.job.effective_execution_profile,
            expected_scope={
                "tenant_id": context.execution_scope.tenant_id,
                "cell_id": context.execution_scope.cell_id,
            },
        )
        persisted_owner = _validated_execution_owner_binding(
            current.job.progress.get("execution_owner_binding"),
            expected=owner_binding,
        )
        if (
            current_owner != owner_binding
            or current.attempt != admission.attempt
            or current.job.lease_owner != admission.job.lease_owner
            or persisted_owner != owner_binding
        ):
            raise ControlJobLeaseLostError("control_job_terminal_owner_binding_not_current")

    def _execute_control_nl_job(
        self, context: _ControlNLJobContext
    ) -> CompiledRecursiveGenerationCycleRun | None:
        """Compile one admitted NL job and persist any terminal candidate lane."""
        self._persist_current_nl_owner_projection(context)
        try:
            compiled = self._compile_control_nl_job(context)
        except Exception as error:
            from .job_attempt_publication import _clear_original_error_candidate_progress

            _clear_original_error_candidate_progress(error)
            try:
                self._preserve_failed_nl_candidate_n5(context, error=error)
            except Exception as preservation_error:
                # Preservation cannot replace the real execution failure.
                import logging

                logging.getLogger(__name__).debug(
                    "Failed N5 output preservation was not established: %s", preservation_error
                )
                from polisyos.runtime.quality.generation_cycle import (
                    _completed_n5_failure_from_exception,
                )

                from .job_attempt_publication import _attach_original_error_candidate_progress

                try:
                    if _completed_n5_failure_from_exception(error) is not None:
                        # Expose the failed preservation without leaking foreign
                        # artifact diagnostics or substituting it for the primary.
                        _attach_original_error_candidate_progress(
                            error,
                            job=context.job,
                            execution_scope=context.execution_scope,
                            progress={
                                "state": "failed",
                                "phase": "generation_cycle_partial_preservation",
                                "runtime_state": "candidate_only",
                                "run_id": context.job.run_id,
                                "job_id": context.job.job_id,
                                "attempt": context.job.attempt,
                                "partial_candidate_simulation": {
                                    "artifact_status": "not_established",
                                    "limitation_code": "partial_n5_preservation_not_established",
                                    "publication_authority": False,
                                },
                                "failure": {
                                    "code": str(
                                        getattr(error, "code", None)
                                        or "generation_cycle_late_stage_failed"
                                    ),
                                    "exception_type": type(error).__name__,
                                    "message": str(error),
                                },
                            },
                        )
                except Exception as diagnostic_error:
                    logging.getLogger(__name__).debug(
                        "Could not attach candidate failure diagnostic: %s", diagnostic_error
                    )
            raise
        if isinstance(compiled, N4CandidateScenarioProposalOnlyExecution):
            self._complete_nl_scenario_proposal_only(context, compiled)
            return None
        if isinstance(compiled, N4CandidateProposalExecution):
            self._complete_nl_candidate_proposal(context, compiled)
            return None
        if context.intent_band in {
            ExecutionIntentBand.CANDIDATE_ONLY,
            ExecutionIntentBand.DATA_TRUST_REQUIRED,
        }:
            self._complete_nl_candidate_only_result(context)
            return None
        if context.intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT:
            self._complete_nl_simulation_result(context, compiled)
            return None
        return compiled

    def _reopen_owned_candidate_n5_completion(
        self,
        context: _ControlNLJobContext,
        *,
        completion: _GenerationCycleN5Completion,
    ) -> tuple[CandidateSimulationExecutionV5, tuple[ArtifactRef, ...]]:
        """Reconcile enclosing facts with the canonical scoped V5 artifact owner."""
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationExecutionV5,
            CandidateSimulationN5InputV5,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            VerifiedNLJobScope,
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository,
            N4CandidateScenarioSourceRecordV2,
            N4CandidateScenarioSourceRecordV3,
        )

        job, scope = context.job, context.execution_scope
        verified = completion.verified_scope
        if (
            type(verified) is not VerifiedNLJobScope
            or not verified._was_issued_by_verified_nl_execution_owner
            or context.verified_nl_job_scope is None
            or verified != context.verified_nl_job_scope
            or (verified.job_id, verified.run_id, verified.tenant_id, verified.cell_id)
            != (job.job_id, job.run_id, scope.tenant_id, scope.cell_id)
            or verified.attempt != job.attempt
            or verified.worker_id != job.lease_owner
            or completion.problem.nl_provenance.raw_request
            != str(context.payload.get("request") or "")
            or context.core_run_context is None
            or context.core_run_id is None
        ):
            raise ValueError("generation_cycle_partial_n5_scope_not_established")
        self._persist_current_nl_owner_projection(context)
        repository = GenerationSourceRepository(self._artifact_store)
        expected_scope = {
            "expected_run_id": str(job.run_id),
            "expected_job_id": job.job_id,
            "expected_tenant_id": scope.tenant_id,
            "expected_cell_id": scope.cell_id,
        }
        resolved = repository._read_candidate_simulation_v5_numerical_output(
            ref=completion.execution_ref, **expected_scope
        )
        execution, input_record = resolved.execution, resolved.input_record
        if (
            type(execution) is not CandidateSimulationExecutionV5
            or type(input_record) is not CandidateSimulationN5InputV5
            or execution.n5_input_ref != completion.input_ref
            or execution.n4_source_ref != completion.n4_source_ref
            or execution.context_job_ref != completion.context_job_ref
            or execution.n5_result_ref != completion.result_ref
            or execution.original_candidate_id != completion.candidate_id
            or execution.original_candidate_hash != completion.candidate_hash
            or execution.world_model_record_hash != completion.world_model_record_hash
            or execution.problem_ref != cycle_job_design_problem_ref(completion.problem)
            or input_record.materialization.problem_ref != execution.problem_ref
        ):
            raise ValueError("generation_cycle_partial_n5_execution_join_mismatch")
        source = resolved.source
        if (
            type(source)
            not in {N4CandidateScenarioSourceRecordV2, N4CandidateScenarioSourceRecordV3}
            or source.problem != completion.problem
            or source.candidate is None
            or source.candidate.candidate_id != completion.candidate_id
            or source.candidate.atom.content_hash != completion.candidate_hash
            or source.profile != input_record.profile
        ):
            raise ValueError("generation_cycle_partial_n5_source_join_mismatch")
        retained_refs = (
            completion.execution_ref,
            completion.input_ref,
            completion.n4_source_ref,
            completion.result_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in retained_refs):
            raise ValueError("generation_cycle_partial_n5_selected_view_missing")
        return execution, retained_refs

    def _preserve_failed_nl_candidate_n5(
        self, context: _ControlNLJobContext, *, error: Exception
    ) -> None:
        """Reopen owned N5 bytes before linking them to the same failed attempt."""
        from polisyos.runtime.quality.generation_cycle import (
            _completed_n5_failure_from_exception,
        )

        from .job_attempt_publication import _attach_original_error_candidate_progress

        packet = _completed_n5_failure_from_exception(error)
        if packet is None:
            return
        completion = packet.completion
        job, scope = context.job, context.execution_scope
        execution, retained_refs = self._reopen_owned_candidate_n5_completion(
            context, completion=completion
        )
        outputs = list(context.core_run_context.run_manifest.outputs)
        for ref in retained_refs:
            if ref not in outputs:
                outputs.append(ref)
        original_failure: dict[str, object] = {
            "code": str(getattr(error, "code", None) or "generation_cycle_late_stage_failed"),
            "exception_type": type(error).__name__,
            "message": str(error),
            "stage": packet.failed_stage,
        }
        if error.__cause__ is not None:
            original_failure["cause"] = {
                "exception_type": type(error.__cause__).__name__,
                "message": str(error.__cause__),
            }
        manifest_ref = self._finish_generation_run_context(
            job=job,
            execution_scope=scope,
            core_run_id=context.core_run_id,
            context=context.core_run_context,
            outputs=outputs,
            status="error",
            errors=[original_failure],
        )
        progress = {
            "state": "failed",
            "phase": "generation_cycle_" + packet.failed_stage,
            "runtime_state": "candidate_only",
            "authority_result": "candidate_only",
            "run_id": job.run_id,
            "job_id": job.job_id,
            "attempt": job.attempt,
            "core_terminal_status": "error",
            **self._core_run_progress_fields(
                job=job, core_run_id=context.core_run_id, manifest_ref=manifest_ref
            ),
            "partial_candidate_simulation": {
                "artifact_status": "resolved",
                "authority_purpose": "candidate_scenario_n5_only",
                "cycle_index": completion.cycle_index,
                "candidate_id": completion.candidate_id,
                "candidate_hash": completion.candidate_hash,
                "problem_ref": execution.problem_ref,
                "world_model_record_hash": completion.world_model_record_hash,
                "completed_stage": "n5_simulation",
                "failed_stage": packet.failed_stage,
                "cycle_completed": False,
                "publication_authority": False,
                "n5_input_ref": completion.input_ref.model_dump(mode="json"),
                "execution_ref": completion.execution_ref.model_dump(mode="json"),
                "n4_source_ref": completion.n4_source_ref.model_dump(mode="json"),
                "context_job_ref": completion.context_job_ref.model_dump(mode="json"),
                "simulation_result_ref": completion.result_ref.model_dump(mode="json"),
            },
            "failure": {
                "code": str(getattr(error, "code", None) or "generation_cycle_late_stage_failed"),
                "exception_type": type(error).__name__,
                "message": str(error),
                "layer": "generation_cycle",
                "phase": packet.failed_stage,
                "run_id": job.run_id,
                "job_id": job.job_id,
                "attempt": job.attempt,
            },
        }
        _attach_original_error_candidate_progress(
            error, progress=progress, job=job, execution_scope=scope
        )

    def _completed_candidate_n5_output_refs(
        self,
        context: _ControlNLJobContext,
        compiled: CompiledRecursiveGenerationCycleRun,
    ) -> tuple[ArtifactRef, ...]:
        """Reopen completed configured V5 leaves before explicit Core publication.

        Historical unbound simulations retain their existing compiled surface;
        they do not acquire selected, same-owner output membership from an ID.
        """
        from polisyos.core.artifacts import ArtifactRef, read_core_manifest_profile
        from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
        from polisyos.runtime.quality.generation_cycle import _GenerationCycleN5Completion
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository
        from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleNode

        refs: list[ArtifactRef] = []
        repository = GenerationSourceRepository(self._artifact_store)
        scope = context.execution_scope
        for node in compiled.recursive_run.nodes:
            if type(node) is not RecursiveCycleNode or node.cycle_run is None:
                continue
            for cycle in node.cycle_run.cycles:
                simulation = cycle.simulation
                input_ref = simulation.candidate_simulation_n5_input_ref
                if simulation.status != "joint_simulated" or input_ref is None:
                    continue
                manifest = read_core_manifest_profile(self._artifact_store, input_ref)[0]
                schema = manifest.artifact_schema
                if schema is None or (schema.name, schema.version) != (
                    "policyos.runtime.candidate_simulation.n5_input.v5",
                    "5.0",
                ):
                    continue
                source_ref = simulation.candidate_simulation_n4_source_ref
                context_ref = simulation.candidate_simulation_context_job_ref
                if (
                    source_ref is None
                    or context_ref is None
                    or simulation.simulation_result_ref is None
                    or simulation.world_model_record is None
                    or context.verified_nl_job_scope is None
                    or scope.tenant_id is None
                    or scope.cell_id is None
                ):
                    raise ValueError("compiled_candidate_n5_output_binding_missing")
                source = repository.load_candidate_scenario_source_for_n5(
                    source_ref,
                    expected_run_id=str(context.job.run_id),
                    expected_job_id=context.job.job_id,
                    expected_tenant_id=scope.tenant_id,
                    expected_cell_id=scope.cell_id,
                )
                if cycle_job_design_problem_ref(source.problem) != (
                    cycle.design_problem_basis_ref or cycle.design_problem_ref
                ):
                    raise ValueError("compiled_candidate_n5_problem_basis_mismatch")
                completion = _GenerationCycleN5Completion(
                    verified_scope=context.verified_nl_job_scope,
                    problem=source.problem,
                    cycle_index=cycle.cycle_index,
                    candidate_id=cycle.selected_candidate_ref,
                    candidate_hash=cycle.selected_candidate_content_hash,
                    world_model_record_hash=simulation.world_model_record.content_hash,
                    n4_source_ref=source_ref,
                    context_job_ref=context_ref,
                    input_ref=input_ref,
                    execution_ref=ArtifactRef.model_validate(
                        simulation.diagnostics.get("candidate_simulation_execution_selected_ref")
                    ),
                    result_ref=simulation.simulation_result_ref,
                )
                execution, selected = self._reopen_owned_candidate_n5_completion(
                    context, completion=completion
                )
                if (
                    execution.n5_result_content_hash != simulation.simulation_ref
                    or execution.world_model_record_hash != simulation.k_world_ref_before
                    or execution.world_model_record_hash != simulation.k_world_ref_after
                    or execution.profile_config_ref
                    != simulation.candidate_simulation_profile_config_ref
                    or source.profile.profile_selection_ref
                    != simulation.candidate_simulation_profile_selection_ref
                ):
                    raise ValueError("compiled_candidate_n5_enclosing_simulation_mismatch")
                for ref in selected:
                    if ref not in refs:
                        refs.append(ref)
        return tuple(refs)

    def _compile_control_nl_job(
        self, context: _ControlNLJobContext
    ) -> (
        CompiledRecursiveGenerationCycleRun
        | N4CandidateProposalExecution
        | N4CandidateScenarioProposalOnlyExecution
    ):
        """Run the already-admitted compiler inside its producer binding scope."""
        from polisyos.common import async_tools
        from polisyos.core.contracts.control import DataSourceBinding
        from polisyos.runtime.http.resilience import run_guarded_dependency_operation
        from polisyos.runtime.http.services.control.nl_pipeline import (
            NaturalLanguagePipelineRefusalError,
            _nl_snapshot_cache_reuse_binding,
        )
        from polisyos.runtime.http.services.control.producer_basis import (
            _ControlJobProducerIntent,
            control_job_producer_basis_scope,
        )
        from polisyos.runtime.quality.recursive_generation_cycle import (
            RecursiveCycleBudget,
        )
        from polisyos.scientist import BudgetState
        from polisyos.scientist.orchestration.llm.factory import (
            _gateway_cache_reuse_scope,
        )

        if (
            context.execution_scope.status != "established"
            or context.execution_scope.actor_authenticated is not True
            or context.producer_run_binding is None
            or context.core_run_context is None
        ):
            raise NaturalLanguagePipelineRefusalError(
                "nl_producer_ownership_not_established",
                "LLM work requires an admitted tenant/cell producer owner. "
                "Resubmit through an authenticated scoped route.",
            )

        job = context.job
        payload = context.payload
        execution_intent = context.execution_intent
        intent_band = context.intent_band
        model_name = context.model_name
        compiler_context = context.compiler_context
        profile_id = context.profile_id
        recursive_budget_resolution = context.recursive_budget_resolution
        max_cycles = context.max_cycles
        budget_usd = context.budget_usd
        cycle_substrate_context_resolver = context.cycle_substrate_context_resolver
        generic_cycle_simulation_handoff_resolver = (
            context.generic_cycle_simulation_handoff_resolver
        )
        generic_cycle_simulation_currentness_resolver = (
            context.generic_cycle_simulation_currentness_resolver
        )
        verified_nl_job_scope = context.verified_nl_job_scope
        candidate_simulation_currentness_resolver = (
            context.candidate_simulation_currentness_resolver
        )
        recursive_leaf_context_owner = context.recursive_leaf_context_owner
        evaluation_safety = context.evaluation_safety
        trusted_source_context = context.trusted_source_context
        producer_run_binding_scope = context.producer_run_binding_scope
        producer_run_binding = context.producer_run_binding

        from polisyos.runtime.quality.data_forge_binding import (
            bind_measurement_root_execution_scope,
        )

        measurement_root_execution_binding = bind_measurement_root_execution_scope(
            admission=context.admission,
            job=context.job,
            execution_scope=context.execution_scope,
        )
        cache_authorizer = getattr(self, "_llm_cache_reuse_authorizer", None)
        raw_data_source = payload.get("data_source")
        data_source = (
            DataSourceBinding.model_validate(raw_data_source)
            if raw_data_source is not None
            else None
        )
        cache_principal, cache_context = _nl_snapshot_cache_reuse_binding(
            data_source=data_source,
            execution_scope=context.execution_scope,
            artifact_store=self._artifact_store,
            authorizer=cache_authorizer,
        )

        def bounded_operation[T](operation: Callable[[], T]) -> T:
            return run_guarded_dependency_operation(self._control_store, operation)

        def validate_current_admission() -> None:
            bounded_operation(
                lambda: self._control_store.verify_llm_producer_admission(
                    expected=context.admission
                )
            )

        def persist_producer_intent(source: _ControlJobProducerIntent) -> ArtifactRef:
            actual_binding = source.begin_receipt.run_binding
            if actual_binding is None:
                raise ValueError("producer_basis_actual_binding_missing")
            return self._put_json_artifact_ref(
                source.model_dump(mode="json"),
                kind=source.ARTIFACT_KIND,
                schema_name=source.ARTIFACT_SCHEMA_NAME,
                schema_version=source.ARTIFACT_SCHEMA_VERSION,
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=actual_binding.tenant_id,
                    cell_id=actual_binding.cell_id,
                ),
            )

        def readback_producer_intent(event_id: str) -> object:
            return bounded_operation(
                lambda: self._llm_producer_settlement_store.resolve_producer_event_safe(event_id)
            )

        joint_request_payload_ref = None
        if payload.get("joint_interaction_candidate_intent") == "authored_joint_components.v1":
            created = self._control_store.get_job_created_event_payload(job.job_id)
            raw_ref = created.get("nl_request_payload_artifact_ref")
            if not isinstance(raw_ref, dict):
                raise ValueError("authored_joint_request_selected_queue_missing")
            joint_request_payload_ref = ArtifactRef.model_validate(raw_ref)
            if str(joint_request_payload_ref.artifact_id) != job.payload_ref:
                raise ValueError("authored_joint_request_selected_queue_mismatch")
        producer_basis_scope = control_job_producer_basis_scope(
            context=context.core_run_context,
            run_binding=context.producer_run_binding,
            attempt=context.admission.attempt,
            persist=persist_producer_intent,
            readback=readback_producer_intent,
        )
        with (
            producer_run_binding_scope,
            producer_basis_scope as producer_basis,
            _gateway_cache_reuse_scope(
                authorizer=cache_authorizer,
                principal=cache_principal,
                context=cache_context,
                cache=getattr(self, "_llm_prompt_cache", None),
                run_id=str(job.run_id),
                settlement_store=self._llm_producer_settlement_store,
                reuse_guard=bounded_operation,
                validate_admission=validate_current_admission,
                intent_observer=producer_basis.observe,
                on_close=producer_basis.close_admission,
            ),
        ):
            compiled = async_tools.run_coro_sync(
                self.compile_and_run_recursive_generation_cycle(
                    raw_request=str(payload.get("request") or ""),
                    context=compiler_context,
                    model_name=model_name,
                    execution_intent=execution_intent,
                    joint_interaction_candidate_intent=payload.get(
                        "joint_interaction_candidate_intent"
                    ),
                    joint_interaction_request_payload_ref=joint_request_payload_ref,
                    # A configured generic handoff owner selects the N4/N5 route;
                    # without one, simulate_only stays on the N4 proposal-only lane.
                    n4_proposal_only=(
                        intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT
                        and generic_cycle_simulation_handoff_resolver is None
                    ),
                    n4_proposal_only_origin="derived_legacy_default",
                    producer_run_id=(str(job.run_id) if job.run_id is not None else None),
                    producer_run_binding=producer_run_binding,
                    compiler_gateway=None,
                    budget_state=BudgetState.model_validate(
                        {
                            "limits": {
                                "run": {"key": "run", "max_usd": budget_usd},
                            }
                        }
                    ),
                    recursive_budget=RecursiveCycleBudget(
                        max_depth=0,
                        max_nodes=1,
                        min_cycles_per_leaf=1,
                        max_cycles_per_leaf=max_cycles,
                    ),
                    recursive_budget_resolution=recursive_budget_resolution,
                    target_world_scope_profile_id=(
                        profile_id if isinstance(profile_id, str) else None
                    ),
                    cycle_substrate_context_resolver=cycle_substrate_context_resolver,
                    generic_cycle_simulation_handoff_resolver=(
                        generic_cycle_simulation_handoff_resolver
                    ),
                    generic_cycle_simulation_currentness_resolver=(
                        generic_cycle_simulation_currentness_resolver
                    ),
                    verified_nl_job_scope=verified_nl_job_scope,
                    candidate_simulation_currentness_resolver=(
                        candidate_simulation_currentness_resolver
                    ),
                    recursive_leaf_context_owner=recursive_leaf_context_owner,
                    root_evaluation_context=(
                        evaluation_safety.execution_context
                        if evaluation_safety is not None
                        else None
                    ),
                    trusted_source_context=trusted_source_context,
                    measurement_root_execution_binding=measurement_root_execution_binding,
                ),
                timeout_seconds=max(120.0, 120.0 * max_cycles),
            )
        return compiled

    def _complete_nl_scenario_proposal_only(
        self,
        context: _ControlNLJobContext,
        compiled: N4CandidateScenarioProposalOnlyExecution,
    ) -> None:
        """Persist and complete a scenario proposal-only outcome."""
        job = context.job
        payload = context.payload
        execution_scope = context.execution_scope
        capability_manifest_ref = context.capability_manifest_ref
        intent_band = context.intent_band
        execution_intent_limitation = context.execution_intent_limitation
        recursive_budget_resolution = context.recursive_budget_resolution
        candidate_simulation_currentness_resolver = (
            context.candidate_simulation_currentness_resolver
        )
        core_run_id = context.core_run_id
        core_run_context = context.core_run_context
        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository,
            N4CandidateScenarioSourceLocator,
            N4CandidateScenarioSourceRecordV1,
            N4CandidateScenarioSourceRecordV2,
            N4CandidateScenarioSourceRecordV3,
            _generation_source_read_result,
        )

        run_id = str(job.run_id or "")
        source = None
        locator = None
        generation_source_read_provenance: dict[str, object] = {}
        source_ref = compiled.source_ref
        currentness_status = "not_established"
        limitation_code = compiled.limitation_code
        if source_ref is not None:
            if (
                execution_scope.tenant_id is None
                or execution_scope.cell_id is None
                or candidate_simulation_currentness_resolver is None
            ):
                currentness_status = "not_established"
                limitation_code = "candidate_scenario_worker_lease_not_current"
            else:
                locator = N4CandidateScenarioSourceLocator(artifact_ref=source_ref)
                repository = GenerationSourceRepository(self._artifact_store)
                with repository.capture_read_provenance() as read_trace:
                    loaded = repository.load_candidate_proposal_projection_for_served_job(
                        locator,
                        job_id=job.job_id,
                        run_id=run_id,
                        tenant_id=execution_scope.tenant_id,
                        cell_id=execution_scope.cell_id,
                        raw_request=str(payload.get("request") or ""),
                        expected_design_problem=compiled.design_problem,
                    )
                if type(loaded) not in (
                    N4CandidateScenarioSourceRecordV1,
                    N4CandidateScenarioSourceRecordV2,
                    N4CandidateScenarioSourceRecordV3,
                ):
                    raise RuntimeError("n4_candidate_scenario_projection_owner_mismatch")
                source = loaded
                read_result = _generation_source_read_result(source, read_trace)
                if read_result is None:
                    raise RuntimeError("generation_source_read_provenance_missing")
                generation_source_read_provenance = read_result.progress_projection()
                if (
                    generation_source_read_provenance["selected_artifact_id"]
                    != str(source_ref.artifact_id)
                    or generation_source_read_provenance["selected_manifest_profile_sha256"]
                    != source_ref.manifest_profile_sha256
                ):
                    raise RuntimeError("generation_source_read_selection_mismatch")
                current = candidate_simulation_currentness_resolver() is True
                currentness_status = "current" if current else "not_current"
                if current:
                    limitation_code = source.candidate_limitation_code or compiled.limitation_code
                else:
                    limitation_code = "candidate_scenario_worker_lease_not_current"
        else:
            currentness_status = "not_established"
            limitation_code = "candidate_scenario_source_persistence_not_established"

        proposal_limiter = (
            source.candidate_limitation_code if source is not None else compiled.limitation_code
        )
        core_progress: dict[str, object] = {}
        if core_run_context is not None:
            if core_run_id is None:
                raise RuntimeError("n4_candidate_scenario_core_identity_not_established")
            if source_ref is None:
                core_manifest_ref = self._finish_generation_run_context(
                    job=job,
                    execution_scope=execution_scope,
                    core_run_id=core_run_id,
                    context=core_run_context,
                    outputs=[],
                    status="error",
                    errors=[{"code": ("candidate_scenario_source_persistence_not_established")}],
                )
                core_progress = {
                    "core_terminal_status": "error",
                    **self._core_run_progress_fields(
                        job=job,
                        core_run_id=core_run_id,
                        manifest_ref=core_manifest_ref,
                    ),
                }
            else:
                core_manifest_ref = self._publish_generation_run(
                    job=job,
                    payload=payload,
                    execution_scope=execution_scope,
                    core_run_id=core_run_id,
                    run_context=core_run_context,
                    proposal_ref=source_ref,
                )
                core_progress = self._core_run_progress_fields(
                    job=job,
                    core_run_id=core_run_id,
                    manifest_ref=core_manifest_ref,
                )
        progress = {
            "state": "completed",
            "phase": "natural_language_run",
            "status": (
                "candidate_limited"
                if source is not None and currentness_status == "current"
                else "not_established"
            ),
            "execution_band": "candidate",
            "candidate_computation_status": (
                "completed"
                if source is not None and currentness_status == "current"
                else "not_established"
            ),
            "execution_intent_band": intent_band.value,
            "execution_intent_limitation_code": (execution_intent_limitation),
            "limitation_code": limitation_code,
            "candidate_proposal_limitation_code": proposal_limiter,
            "candidate_context_currentness_status": currentness_status,
            "proposal_persistence_status": (
                "persisted" if source_ref is not None else "not_established"
            ),
            "stage": "n4_proposal_only",
            "n4_status": ("candidate_limited" if source is not None else "not_established"),
            "run_id": run_id,
            "candidate_proposal_ref": (
                locator.model_dump(mode="json") if locator is not None else None
            ),
            **(
                {"generation_source_read_provenance": generation_source_read_provenance}
                if generation_source_read_provenance
                else {}
            ),
            "simulation_status": "not_run",
            "simulation_limitation_code": proposal_limiter,
            "n5_status": "not_run",
            "n8_status": "not_run",
            "n9_status": "not_admitted",
            "s8_status": "blocked",
            **core_progress,
        }
        artifact_refs = [str(capability_manifest_ref)]
        if source_ref is not None:
            artifact_refs.append(str(source_ref.artifact_id))
        core_manifest_ref_id = core_progress.get("manifest_ref")
        if isinstance(core_manifest_ref_id, str):
            artifact_refs.append(core_manifest_ref_id)
        diagnostic_emission = self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after="completed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "capability_manifest_ref": str(capability_manifest_ref),
                "candidate_proposal_ref": progress["candidate_proposal_ref"],
                **(
                    {"generation_source_read_provenance": generation_source_read_provenance}
                    if generation_source_read_provenance
                    else {}
                ),
                "execution_band": "candidate",
                "execution_intent_band": intent_band.value,
                "execution_intent_limitation_code": (execution_intent_limitation),
                "limitation_code": limitation_code,
                "downstream_stages": {
                    "n5": "not_run",
                    "n8": "not_run",
                    "n9": "not_admitted",
                    "s8": "blocked",
                },
            },
            artifact_refs=artifact_refs,
        )
        progress["runtime_diagnostic_event_status"] = diagnostic_emission.status
        progress["diagnostic_event_scope_status"] = diagnostic_emission.scope_status
        if diagnostic_emission.event_id is not None:
            progress["diagnostic_event_ids"] = [diagnostic_emission.event_id]
        if diagnostic_emission.limitation_code is not None:
            progress["runtime_diagnostic_event_limitation_code"] = (
                diagnostic_emission.limitation_code
            )
        progress = _n4_proposal_progress_with_budget(
            progress,
            recursive_budget_resolution.model_dump(mode="json"),
        )
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=run_id,
            capability_manifest_ref=str(capability_manifest_ref),
            progress=progress,
        )
        return

    def _complete_nl_candidate_proposal(
        self,
        context: _ControlNLJobContext,
        compiled: N4CandidateProposalExecution,
    ) -> None:
        """Persist and complete an N4 candidate proposal outcome."""
        job = context.job
        payload = context.payload
        execution_scope = context.execution_scope
        capability_manifest_ref = context.capability_manifest_ref
        intent_band = context.intent_band
        execution_intent_limitation = context.execution_intent_limitation
        recursive_budget_resolution = context.recursive_budget_resolution
        core_run_id = context.core_run_id
        core_run_context = context.core_run_context
        from polisyos.runtime.quality.design_generation import (
            DesignGenerationOrganRun,
        )

        target_scope_progress = {
            "target_world_scope_profile_id": (compiled.target_world_scope_profile_id),
            "target_world_scope_status": compiled.target_world_scope_status,
            "target_world_scope_profile_status": (compiled.target_world_scope_profile_status),
            "target_world_scope_authority": "not_established",
            "target_world_scope_currentness": "not_established",
            "target_world_model_record_ref": (compiled.target_world_model_record_ref),
        }
        if compiled.target_world_scope_profile_limitation_code is not None:
            target_scope_progress["target_world_scope_profile_limitation_code"] = (
                compiled.target_world_scope_profile_limitation_code
            )

        proposal_result = compiled.proposal
        if isinstance(proposal_result, DesignGenerationOrganRun):
            generation_status = proposal_result.result.status
            limitation_code_by_status = {
                "generation_unavailable": "n4_generation_unavailable",
                "preflight_rejected": "n4_model_preflight_rejected",
            }
            limitation_code = limitation_code_by_status.get(generation_status)
            if limitation_code is None:
                raise RuntimeError("n4_candidate_proposal_terminal_status_invalid")

            core_progress: dict[str, object] = {}
            if core_run_context is not None and core_run_id is not None:
                core_manifest_ref = self._finish_generation_run_context(
                    job=job,
                    execution_scope=execution_scope,
                    core_run_id=core_run_id,
                    context=core_run_context,
                    outputs=[],
                    status="error",
                    errors=[{"code": limitation_code}],
                )
                core_progress = self._core_run_progress_fields(
                    job=job,
                    core_run_id=core_run_id,
                    manifest_ref=core_manifest_ref,
                )

            run_id = str(job.run_id or "")
            diagnostic_emission = self._emit_runtime_diagnostic_event(
                execution_scope=execution_scope,
                job_id=job.job_id,
                run_id=run_id,
                execution_profile=job.effective_execution_profile,
                phase="job_execution",
                event_type=("polisyos.runtime.diagnostic.phase_transition.v1"),
                state_before="running",
                state_after="completed",
                payload=payload,
                event_payload={
                    "job_kind": job.kind,
                    "capability_manifest_ref": str(capability_manifest_ref),
                    "execution_band": "candidate",
                    "candidate_computation_status": ("not_established"),
                    "execution_intent_band": intent_band.value,
                    "execution_intent_limitation_code": (execution_intent_limitation),
                    "limitation_code": limitation_code,
                    "n4_status": generation_status,
                    "downstream_stages": {
                        "n5": "not_run",
                        "n8": "not_run",
                        "n9": "not_run",
                        "s8": "not_run",
                    },
                },
                artifact_refs=[str(capability_manifest_ref)],
            )
            simulation_failure = (
                {
                    "simulation_status": "not_run",
                    "simulation_limitation_code": limitation_code,
                }
                if intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT
                else {}
            )
            progress = {
                "state": "completed",
                "phase": "natural_language_run",
                "status": "not_established",
                "execution_band": "candidate",
                "candidate_computation_status": "not_established",
                "execution_intent_band": intent_band.value,
                "execution_intent_limitation_code": execution_intent_limitation,
                "proposal_persistence_status": "not_run",
                "limitation_code": limitation_code,
                "stage": "n4_proposal_only",
                "n4_status": generation_status,
                "run_id": run_id,
                "candidate_proposal_ref": None,
                "runtime_diagnostic_event_status": diagnostic_emission.status,
                "diagnostic_event_scope_status": diagnostic_emission.scope_status,
                "n5_status": "not_run",
                "n8_status": "not_run",
                "n9_status": "not_run",
                "s8_status": "not_run",
                **core_progress,
                **simulation_failure,
                **target_scope_progress,
            }
            if diagnostic_emission.event_id is not None:
                progress["diagnostic_event_ids"] = [diagnostic_emission.event_id]
            if diagnostic_emission.limitation_code is not None:
                progress["runtime_diagnostic_event_limitation_code"] = (
                    diagnostic_emission.limitation_code
                )
            progress = _n4_proposal_progress_with_budget(
                progress,
                recursive_budget_resolution.model_dump(mode="json"),
            )
            self._control_store.complete_job(
                job_id=job.job_id,
                run_id=run_id,
                capability_manifest_ref=str(capability_manifest_ref),
                progress=progress,
            )
            return

        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository,
            N4CandidateProposalLocator,
            N4CandidateProposalRecordV3,
            N4CandidateProposalSimulationDisposition,
            _generation_source_read_result,
        )

        run_id = str(job.run_id or "")
        raw_request = str(payload.get("request") or "")
        tenant_id = execution_scope.tenant_id
        cell_id = execution_scope.cell_id
        if tenant_id is None or cell_id is None:
            scope_limiter = "candidate_proposal_owner_scope_not_established"
            progress = {
                "state": "completed",
                "phase": "natural_language_run",
                "status": "not_established",
                "execution_band": "candidate",
                "candidate_computation_status": "completed",
                "proposal_persistence_status": "not_established",
                "limitation_code": scope_limiter,
                "runtime_diagnostic_event_status": "not_established",
                "runtime_diagnostic_event_limitation_code": (
                    "diagnostic_event_owner_scope_not_established"
                ),
                "execution_intent_band": intent_band.value,
                "execution_intent_limitation_code": execution_intent_limitation,
                "run_id": run_id,
                "candidate_proposal_ref": None,
                "n5_status": "not_run",
                "n8_status": "not_run",
                "n9_status": "not_run",
                "s8_status": "not_run",
                **target_scope_progress,
            }
            progress = _n4_proposal_progress_with_budget(
                progress,
                recursive_budget_resolution.model_dump(mode="json"),
            )
            self._control_store.complete_job(
                job_id=job.job_id,
                run_id=run_id,
                capability_manifest_ref=str(capability_manifest_ref),
                progress=progress,
            )
            return
        repository = GenerationSourceRepository(self._artifact_store)
        simulation_disposition = (
            N4CandidateProposalSimulationDisposition()
            if intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT
            else None
        )
        proposal_ref = repository.persist_candidate_proposal(
            job_id=job.job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            raw_request=raw_request,
            problem=compiled.design_problem,
            proposal=proposal_result,
            simulation_disposition=simulation_disposition,
            nl_preflight_cost_events=compiled.nl_preflight_cost_events,
            n4_generation_cost_events=compiled.n4_generation_cost_events,
            core_run_id=core_run_id,
            control_job_attempt=(job.attempt if core_run_id is not None else None),
        )
        proposal_locator = N4CandidateProposalLocator(artifact_ref=proposal_ref)
        with repository.capture_read_provenance() as read_trace:
            proposal_record = repository.load_candidate_proposal_for_served_job(
                proposal_locator,
                job_id=job.job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                raw_request=raw_request,
            )
        if type(proposal_record) is not N4CandidateProposalRecordV3:
            raise RuntimeError("n4_candidate_proposal_current_cost_source_missing")
        read_result = _generation_source_read_result(proposal_record, read_trace)
        if read_result is None:
            raise RuntimeError("generation_source_read_provenance_missing")
        generation_source_read_provenance = read_result.progress_projection()
        if (
            generation_source_read_provenance["selected_artifact_id"]
            != str(proposal_ref.artifact_id)
            or generation_source_read_provenance["selected_manifest_profile_sha256"]
            != proposal_ref.manifest_profile_sha256
        ):
            raise RuntimeError("generation_source_read_selection_mismatch")
        simulation_disposition_record = getattr(proposal_record, "simulation_disposition", None)
        if (
            intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT
            and simulation_disposition_record is None
        ):
            raise RuntimeError("simulate_only_n4_proposal_disposition_missing")
        if (
            intent_band is not ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT
            and simulation_disposition_record is not None
        ):
            raise RuntimeError("non_simulation_job_received_simulation_disposition")
        core_progress = {}
        if core_run_context is not None and core_run_id is not None:
            core_manifest_ref = self._publish_generation_run(
                job=job,
                payload=payload,
                execution_scope=execution_scope,
                core_run_id=core_run_id,
                run_context=core_run_context,
                proposal_ref=proposal_ref,
            )
            core_progress = self._core_run_progress_fields(
                job=job,
                core_run_id=core_run_id,
                manifest_ref=core_manifest_ref,
            )
        progress = {
            "state": "completed",
            "phase": "natural_language_run",
            "status": (
                "not_established"
                if execution_intent_limitation is not None
                else proposal_record.status
            ),
            "execution_band": proposal_record.execution_band,
            "limitation_code": (execution_intent_limitation or proposal_record.limitation_code),
            "candidate_proposal_limitation_code": proposal_record.limitation_code,
            "candidate_computation_status": "completed",
            "stage": proposal_record.stage,
            "run_id": run_id,
            "candidate_proposal_ref": proposal_locator.model_dump(mode="json"),
            "generation_source_read_provenance": generation_source_read_provenance,
            "execution_intent_band": intent_band.value,
            "execution_intent_limitation_code": execution_intent_limitation,
            "n5_status": proposal_record.n5_status,
            "n8_status": proposal_record.n8_status,
            "n9_status": proposal_record.n9_status,
            "s8_status": proposal_record.s8_status,
            **core_progress,
            **target_scope_progress,
        }
        if simulation_disposition_record is not None:
            progress["simulation_status"] = simulation_disposition_record.status
            progress["simulation_limitation_code"] = simulation_disposition_record.reason_code
        progress = _n4_proposal_progress_with_budget(
            progress,
            recursive_budget_resolution.model_dump(mode="json"),
        )
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=run_id,
            capability_manifest_ref=str(capability_manifest_ref),
            progress=progress,
        )
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after="completed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "capability_manifest_ref": str(capability_manifest_ref),
                "candidate_proposal_ref": proposal_locator.model_dump(mode="json"),
                "generation_source_read_provenance": generation_source_read_provenance,
                "execution_band": proposal_record.execution_band,
                "execution_intent_band": intent_band.value,
                "execution_intent_limitation_code": execution_intent_limitation,
                "limitation_code": proposal_record.limitation_code,
                "downstream_stages": {
                    "n5": proposal_record.n5_status,
                    "n8": proposal_record.n8_status,
                    "n9": proposal_record.n9_status,
                    "s8": proposal_record.s8_status,
                },
            },
            artifact_refs=[
                str(capability_manifest_ref),
                str(proposal_ref.artifact_id),
            ],
        )
        return

    def _complete_nl_candidate_only_result(self, context: _ControlNLJobContext) -> None:
        """Reject an unexpected recursive result for candidate-only intent."""
        job = context.job
        payload = context.payload
        execution_scope = context.execution_scope
        capability_manifest_ref = context.capability_manifest_ref
        intent_band = context.intent_band
        limitation = "candidate_only_compiled_result_not_admitted"
        run_id = str(job.run_id or "")
        diagnostic_emission = self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after="completed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "capability_manifest_ref": str(capability_manifest_ref),
                "execution_band": "candidate",
                "candidate_computation_status": "not_established",
                "execution_intent_band": intent_band.value,
                "execution_intent_limitation_code": limitation,
                "limitation_code": limitation,
                "n4_status": "not_established",
                "downstream_stages": {
                    "n5": "not_run",
                    "n8": "not_run",
                    "n9": "not_run",
                    "s8": "not_run",
                    "publication": "not_run",
                },
            },
            artifact_refs=[str(capability_manifest_ref)],
        )
        progress = {
            "state": "completed",
            "phase": "natural_language_run",
            "status": "not_established",
            "execution_band": "candidate",
            "candidate_computation_status": "not_established",
            "execution_intent_band": intent_band.value,
            "execution_intent_limitation_code": limitation,
            "limitation_code": limitation,
            "stage": "candidate_only_result_rejected",
            "n4_status": "not_established",
            "run_id": run_id,
            "candidate_proposal_ref": None,
            "runtime_diagnostic_event_status": diagnostic_emission.status,
            "diagnostic_event_scope_status": diagnostic_emission.scope_status,
            "n5_status": "not_run",
            "n8_status": "not_run",
            "n9_status": "not_run",
            "s8_status": "not_run",
            "publication_status": "not_run",
        }
        if diagnostic_emission.event_id is not None:
            progress["diagnostic_event_ids"] = [diagnostic_emission.event_id]
        if diagnostic_emission.limitation_code is not None:
            progress["runtime_diagnostic_event_limitation_code"] = (
                diagnostic_emission.limitation_code
            )
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=run_id,
            capability_manifest_ref=str(capability_manifest_ref),
            progress=progress,
        )
        return

    def _complete_nl_simulation_result(
        self,
        context: _ControlNLJobContext,
        compiled: CompiledRecursiveGenerationCycleRun,
    ) -> None:
        """Persist the simulate-only compiled result without normative publication."""
        job = context.job
        payload = context.payload
        execution_scope = context.execution_scope
        capability_manifest_ref = context.capability_manifest_ref
        intent_band = context.intent_band
        core_run_id = context.core_run_id
        core_run_context = context.core_run_context
        cycle_substrate_context_job_ref = context.cycle_substrate_context_job_ref
        cycle_substrate_context_job_selected_ref = context.cycle_substrate_context_job_selected_ref
        candidate_outputs = self._completed_candidate_n5_output_refs(context, compiled)
        compiled_artifact_ref = self._put_json_artifact_ref(
            compiled.model_dump(mode="json"),
            kind="runtime.compiled_recursive_generation_cycle",
            schema_name=("polisyos.runtime.CompiledRecursiveGenerationCycleRun"),
            inputs=list(candidate_outputs),
            input_roles=tuple("completed_candidate_simulation" for _ in candidate_outputs),
            tenant_context=(
                ArtifactTenantContextInfo(
                    tenant_id=execution_scope.tenant_id,
                    cell_id=execution_scope.cell_id,
                )
                if execution_scope.status == "established" and execution_scope.tenant_id is not None
                else None
            ),
        )
        run_id = str(job.run_id or "")
        core_progress: dict[str, object] = {}
        if core_run_context is not None and core_run_id is not None:
            core_manifest_ref = self._publish_generation_run(
                job=job,
                payload=payload,
                execution_scope=execution_scope,
                core_run_id=core_run_id,
                run_context=core_run_context,
                compiled_run_ref=compiled_artifact_ref,
                candidate_output_refs=candidate_outputs,
            )
            core_progress = self._core_run_progress_fields(
                job=job,
                core_run_id=core_run_id,
                manifest_ref=core_manifest_ref,
            )
        compiled_ref = str(compiled_artifact_ref.artifact_id)
        progress = {
            "state": "completed",
            "phase": "natural_language_run",
            "status": "simulation_only",
            "execution_band": "candidate",
            "candidate_computation_status": "completed",
            "execution_intent_band": intent_band.value,
            "execution_intent_limitation_code": None,
            "compiled_recursive_generation_cycle_ref": compiled_ref,
            "normative_disposition_status": "not_run",
            "s8_status": "not_run",
            "publication_status": "not_run",
            "run_id": run_id,
            **core_progress,
            "compiled_recursive_generation_cycle_artifact_ref": (
                compiled_artifact_ref.model_dump(mode="json")
            ),
            **(
                {
                    "cycle_substrate_context_job_ref": (cycle_substrate_context_job_ref),
                    "cycle_substrate_context_job_selected_ref": (
                        cycle_substrate_context_job_selected_ref.model_dump(mode="json")
                    ),
                }
                if (
                    cycle_substrate_context_job_ref is not None
                    and cycle_substrate_context_job_selected_ref is not None
                )
                else {}
            ),
        }
        if compiled.recursive_budget_resolution is not None:
            progress["recursive_budget_resolution"] = (
                compiled.recursive_budget_resolution.model_dump(mode="json")
            )
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=run_id,
            capability_manifest_ref=str(capability_manifest_ref),
            progress=progress,
        )
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type=("polisyos.runtime.diagnostic.phase_transition.v1"),
            state_before="running",
            state_after="completed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "execution_band": "candidate",
                "execution_intent_band": intent_band.value,
                "candidate_computation_status": "completed",
                "normative_disposition_status": "not_run",
                "s8_status": "not_run",
                "publication_status": "not_run",
                "projection_authority": "runtime_event_only",
            },
            artifact_refs=[
                str(capability_manifest_ref),
                *([str(core_progress["manifest_ref"])] if core_progress else []),
                compiled_ref,
                *(
                    [cycle_substrate_context_job_ref]
                    if cycle_substrate_context_job_ref is not None
                    else []
                ),
            ],
        )
        return
