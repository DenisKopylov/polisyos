"""Natural-language control-job execution facet."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
from polisyos.runtime.http.services.control.generation_cycle import (
    N4CandidateProposalExecution,
    N4CandidateScenarioProposalOnlyExecution,
)
from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand

from .job_nl_publication import _n4_proposal_progress_with_budget

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )

    from .job_nl_context import _ControlNLJobContext


class ControlNLJobExecutionMixin:
    """Run admitted NL compilation and terminate handled candidate outcomes."""

    def _execute_control_nl_job(
        self, context: _ControlNLJobContext
    ) -> CompiledRecursiveGenerationCycleRun | None:
        """Compile one admitted NL job and persist any terminal candidate lane."""
        compiled = self._compile_control_nl_job(context)
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

    def _compile_control_nl_job(
        self, context: _ControlNLJobContext
    ) -> (
        CompiledRecursiveGenerationCycleRun
        | N4CandidateProposalExecution
        | N4CandidateScenarioProposalOnlyExecution
    ):
        """Run the already-admitted compiler inside its producer binding scope."""
        from polisyos.common import async_tools
        from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleBudget
        from polisyos.scientist import BudgetState

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
        candidate_simulation_currentness_resolver = (
            context.candidate_simulation_currentness_resolver
        )
        recursive_leaf_context_owner = context.recursive_leaf_context_owner
        evaluation_safety = context.evaluation_safety
        trusted_source_context = context.trusted_source_context
        producer_run_binding_scope = context.producer_run_binding_scope

        with producer_run_binding_scope:
            compiled = async_tools.run_coro_sync(
                self.compile_and_run_recursive_generation_cycle(
                    raw_request=str(payload.get("request") or ""),
                    context=compiler_context,
                    model_name=model_name,
                    execution_intent=execution_intent,
                    # simulate_only defaults to the N4 proposal lane. A
                    # configured typed profile owner may supply a
                    # problem-bound context after compilation; absent
                    # that owner or an admitted context, N4 remains a
                    # candidate limitation and never grants S8 authority.
                    n4_proposal_only=(intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT),
                    producer_run_id=(str(job.run_id) if job.run_id is not None else None),
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
        )

        run_id = str(job.run_id or "")
        source = None
        locator = None
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
                loaded = GenerationSourceRepository(
                    self._artifact_store
                ).load_candidate_proposal_projection_for_served_job(
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
            N4CandidateProposalSimulationDisposition,
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
        proposal_record = repository.load_candidate_proposal_for_served_job(
            proposal_locator,
            job_id=job.job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            raw_request=raw_request,
        )
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
        core_progress: dict[str, object] = {}
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
        self, context: _ControlNLJobContext, compiled: CompiledRecursiveGenerationCycleRun
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
        compiled_artifact_ref = self._put_json_artifact_ref(
            compiled.model_dump(mode="json"),
            kind="runtime.compiled_recursive_generation_cycle",
            schema_name=("polisyos.runtime.CompiledRecursiveGenerationCycleRun"),
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
