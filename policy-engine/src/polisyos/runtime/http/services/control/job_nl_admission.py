"""Natural-language control-job admission facet."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import nullcontext
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from polisyos.runtime.http.services.control.job_nl_context import _ControlNLJobContext
from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
)

from ..control_plane_store import ControlJobLeaseLostError
from .job_scope_admission import _NL_JOB_OWNER_CONTEXT_KEYS

if TYPE_CHECKING:
    from collections.abc import AbstractContextManager

    from polisyos.core import run
    from polisyos.runtime.quality.design_problem import DesignProblem

    from ..control_plane_store import (
        ControlJobExecutionAdmission,
        ControlJobExecutionScope,
        ControlJobRecord,
    )
    from .job_scope_admission import _ControlEvaluationSafetyResult


def _resolve_nl_job_execution_intent(
    *,
    intent_band: ExecutionIntentBand,
    execution_intent_binding: Mapping[str, Any],
    evaluation_safety: _ControlEvaluationSafetyResult | None,
) -> str:
    """Resolve the already-admitted execution band without changing its owner."""
    if intent_band is ExecutionIntentBand.EVAL_SAFETY_REQUIRED:
        if evaluation_safety is None:
            raise RuntimeError("nl_job_execution_intent_not_established")
        if evaluation_safety.execution_context is None:
            raise RuntimeError("eval_safety_execution_context_not_established")
        execution_intent = evaluation_safety.execution_context.evaluation_mode
        if execution_intent_binding.get("canonical_mode") != execution_intent:
            raise RuntimeError("nl_job_execution_intent_not_established")
    elif intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT:
        if execution_intent_binding.get("canonical_mode") != "simulate_only":
            raise RuntimeError("nl_job_execution_intent_not_established")
        execution_intent = "simulate_only"
    elif intent_band in {
        ExecutionIntentBand.CANDIDATE_ONLY,
        ExecutionIntentBand.DATA_TRUST_REQUIRED,
    }:
        if intent_band is ExecutionIntentBand.CANDIDATE_ONLY and (
            execution_intent_binding.get("canonical_mode") is not None
        ):
            raise RuntimeError("nl_job_execution_intent_not_established")
        if intent_band is ExecutionIntentBand.DATA_TRUST_REQUIRED and (
            execution_intent_binding.get("canonical_mode")
            not in {"retrospective", "measurement_audit"}
        ):
            raise RuntimeError("nl_job_execution_intent_not_established")
        execution_intent = "candidate_only"
    else:
        raise RuntimeError("nl_job_execution_intent_not_established")
    return execution_intent


def _candidate_simulation_is_current(
    *,
    candidate_simulation_context_binding: dict[str, object],
    admission_owner: object,
    configured_candidate_owner: bool,
    bound_tenant_id: str | None,
    bound_cell_id: str | None,
    job: ControlJobRecord,
) -> bool:
    """Recompute the selected profile/context under the live worker lease."""

    from polisyos.core.artifacts.manifest import (
        ArtifactRef,
        artifact_ref_identity_key,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationContextOffer,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        CycleSubstrateContextArtifactOwner,
        VerifiedNLJobScope,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
        is_supported_cycle_substrate_context_job_artifact,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem

    binding = candidate_simulation_context_binding
    handoff = binding.get("handoff")
    context_owner = binding.get("context_owner")
    context_ref = binding.get("context_ref")
    problem = binding.get("problem")
    verified_scope = binding.get("verified_nl_job_scope")
    admitted_offer = binding.get("offer")
    if (
        not configured_candidate_owner
        or type(admission_owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
        or type(handoff) is not CandidateSimulationContextHandoff
        or type(context_owner) is not CycleSubstrateContextArtifactOwner
        or type(context_ref) is not ArtifactRef
        or type(problem) is not DesignProblem
        or type(verified_scope) is not VerifiedNLJobScope
        or not verified_scope._was_issued_by_verified_nl_execution_owner
        or type(admitted_offer) is not CandidateSimulationContextOffer
    ):
        return False
    try:
        current_context_job = context_owner.resolve_for_current_job(
            context_ref,
            problem=problem,
            verified_nl_job_scope=verified_scope,
        )
    except ControlJobLeaseLostError:
        return False
    current_offer = admission_owner.admit_context(
        problem=problem,
        job_id=str(job.job_id),
        run_id=str(job.run_id),
        tenant_id=bound_tenant_id,
        cell_id=bound_cell_id,
    )
    if (
        type(current_offer) is not CandidateSimulationContextOffer
        or not is_supported_cycle_substrate_context_job_artifact(current_context_job)
    ):
        return False
    expected_problem_ref = cycle_job_design_problem_ref(problem)
    return (
        cycle_job_profile_selection_ref(problem) == handoff.profile.profile_selection_ref
        and current_offer.profile == admitted_offer.profile
        and current_offer.profile == handoff.profile
        and current_offer.profile_config_ref
        == admitted_offer.profile_config_ref
        == handoff.profile_config_ref
        == candidate_simulation_profile_ref(handoff.profile)
        and current_offer.context == admitted_offer.context
        and current_offer.context == handoff.context
        and current_offer.model_declaration
        == admitted_offer.model_declaration
        == handoff.model_declaration
        and current_offer.model_declaration_ref
        == admitted_offer.model_declaration_ref
        == handoff.model_declaration_ref
        and current_offer.ncm_ref == admitted_offer.ncm_ref == handoff.ncm_ref
        and current_context_job.design_problem_ref == expected_problem_ref
        and current_context_job.problem == problem
        and current_context_job.context == current_offer.context
        and current_context_job.job_id == handoff.job_id == str(job.job_id)
        and current_context_job.run_id == handoff.run_id == str(job.run_id)
        and current_context_job.tenant_id == handoff.tenant_id == bound_tenant_id
        and current_context_job.cell_id == handoff.cell_id == bound_cell_id
        and artifact_ref_identity_key(context_ref)
        == artifact_ref_identity_key(handoff.context_job_ref)
    )


class ControlNLJobAdmissionMixin:
    """Prepare typed inputs and currentness callbacks for NL job execution."""

    def _prepare_control_nl_job_context(
        self,
        *,
        job: ControlJobRecord,
        admission: ControlJobExecutionAdmission,
        execution_scope: ControlJobExecutionScope,
        payload: dict[str, Any],
        capability_manifest_ref: str,
        execution_intent_binding: dict[str, Any],
        core_run_id: str | None,
        core_run_context: run.RunContext | None,
        start_core_attempt_callback: Callable[[], tuple[str, run.RunContext]],
    ) -> _ControlNLJobContext | None:
        """Build all stages of the admitted NL worker context in order."""
        context = self._prepare_control_nl_job_intent(
            job=job,
            admission=admission,
            execution_scope=execution_scope,
            payload=payload,
            capability_manifest_ref=capability_manifest_ref,
            execution_intent_binding=execution_intent_binding,
            core_run_id=core_run_id,
            core_run_context=core_run_context,
            start_core_attempt_callback=start_core_attempt_callback,
        )
        if context is None:
            return None
        self._prepare_control_nl_candidate_context(context)
        self._prepare_control_nl_budget_context(context)
        return context

    def _prepare_control_nl_job_intent(
        self,
        *,
        job: ControlJobRecord,
        admission: ControlJobExecutionAdmission,
        execution_scope: ControlJobExecutionScope,
        payload: dict[str, Any],
        capability_manifest_ref: str,
        execution_intent_binding: dict[str, Any],
        core_run_id: str | None,
        core_run_context: run.RunContext | None,
        start_core_attempt_callback: Callable[[], tuple[str, run.RunContext]],
    ) -> _ControlNLJobContext | None:
        """Resolve policy intent, evaluation-safety admission, and compiler inputs."""
        context: _ControlNLJobContext | None = None

        def start_core_attempt_for_nl() -> tuple[str, run.RunContext]:
            nonlocal core_run_id, core_run_context
            core_run_id, core_run_context = start_core_attempt_callback()
            if context is not None:
                context.core_run_id = core_run_id
                context.core_run_context = core_run_context
            return core_run_id, core_run_context

        intent_band = ExecutionIntentBand(str(execution_intent_binding["intent_band"]))
        evaluation_safety = None
        if intent_band is ExecutionIntentBand.EVAL_SAFETY_REQUIRED:
            start_core_attempt_for_nl()
            evaluation_safety = self._admit_evaluation_safety_attempt(
                extension_payload=cast("Mapping[str, Any]", payload.get("context") or {}),
                job=job,
                payload=payload,
                execution_scope=execution_scope,
            )
            if evaluation_safety is not None and evaluation_safety.blocked:
                self._finish_blocked_evaluation_safety_attempt(
                    result=evaluation_safety,
                    job=job,
                    payload=payload,
                    execution_scope=execution_scope,
                    capability_manifest_ref=capability_manifest_ref,
                    core_run_id=core_run_id,
                    core_run_context=core_run_context,
                )
                return None
        execution_intent = _resolve_nl_job_execution_intent(
            intent_band=intent_band,
            execution_intent_binding=execution_intent_binding,
            evaluation_safety=evaluation_safety,
        )
        execution_intent_limitation = (
            "data_trust_owner_not_established"
            if intent_band is ExecutionIntentBand.DATA_TRUST_REQUIRED
            else None
        )
        model_rows = payload.get("llm_models")
        model_name = str(model_rows[0]) if isinstance(model_rows, list) and model_rows else ""
        if not model_name:
            raise RuntimeError("llm_model_unconfigured")
        raw_candidate_context = payload.get("context")
        candidate_context = (
            dict(raw_candidate_context) if isinstance(raw_candidate_context, Mapping) else {}
        )
        candidate_context = {
            key: value
            for key, value in candidate_context.items()
            if key not in _NL_JOB_OWNER_CONTEXT_KEYS
        }
        trusted_source_context: dict[str, object | None] = {
            "tenant_id": execution_scope.tenant_id,
            "cell_id": execution_scope.cell_id,
            "job_id": str(job.job_id),
            "run_id": str(job.run_id),
        }
        compiler_context: dict[str, object] = dict(candidate_context)
        # Persisted request context retains the submitted values. The
        # compiler sees only non-identity candidate inputs; scope IDs
        # enter through the replay-validated job/actor binding below.
        compiler_context["candidate_context"] = dict(candidate_context)
        compiler_context.update(
            {key: value for key, value in trusted_source_context.items() if value is not None}
        )
        profile_id = payload.get("target_world_scope_profile_id")
        context = _ControlNLJobContext(
            job=job,
            admission=admission,
            execution_scope=execution_scope,
            payload=payload,
            capability_manifest_ref=capability_manifest_ref,
            execution_intent_binding=execution_intent_binding,
            intent_band=intent_band,
            evaluation_safety=evaluation_safety,
            execution_intent=execution_intent,
            execution_intent_limitation=execution_intent_limitation,
            model_name=model_name,
            compiler_context=compiler_context,
            trusted_source_context=trusted_source_context,
            profile_id=profile_id,
            start_core_attempt_callback=start_core_attempt_callback,
            core_run_id=core_run_id,
            core_run_context=core_run_context,
        )
        return context

    def _prepare_control_nl_candidate_context(self, context: _ControlNLJobContext) -> None:
        """Bind candidate simulation callbacks to the admitted job and scope."""
        job = context.job
        execution_scope = context.execution_scope
        execution_intent_binding = context.execution_intent_binding
        intent_band = context.intent_band
        cycle_substrate_context_resolver = None
        candidate_simulation_context_binding = context.candidate_simulation_context_binding
        recursive_leaf_context_owner = None
        profile_id = context.profile_id
        admission_owner = self._cycle_substrate_context_admission_owner
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
        )

        configured_candidate_owner = (
            type(admission_owner) is ConfiguredCandidateSimulationContextAdmissionOwner
        )
        bound_tenant_id = execution_scope.tenant_id
        bound_cell_id = execution_scope.cell_id

        def assert_candidate_simulation_currentness() -> bool:
            return _candidate_simulation_is_current(
                candidate_simulation_context_binding=candidate_simulation_context_binding,
                admission_owner=admission_owner,
                configured_candidate_owner=configured_candidate_owner,
                bound_tenant_id=bound_tenant_id,
                bound_cell_id=bound_cell_id,
                job=job,
            )

        # Compilation calls the context resolver only after this
        # callback is passed downstream. Prebind one fail-closed
        # predicate so every admitted handoff reaches N6 paired.
        candidate_simulation_currentness_resolver = assert_candidate_simulation_currentness
        if (
            intent_band is ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT
            and admission_owner is not None
            and (configured_candidate_owner or (isinstance(profile_id, str) and profile_id.strip()))
            and isinstance(bound_tenant_id, str)
            and bound_tenant_id.strip()
            and isinstance(bound_cell_id, str)
            and bound_cell_id.strip()
            and job.run_id is not None
        ):
            from polisyos.runtime.quality.candidate_simulation import (
                CandidateSimulationContextHandoff,
                CandidateSimulationContextOffer,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                CycleSubstrateContext,
                CycleSubstrateContextArtifactOwner,
                VerifiedNLJobScope,
            )

            verified_nl_job_scope = execution_intent_binding.get("_verified_nl_job_scope")
            if (
                type(verified_nl_job_scope) is not VerifiedNLJobScope
                or not verified_nl_job_scope._was_issued_by_verified_nl_execution_owner
            ):
                raise RuntimeError("cycle_substrate_context_verified_worker_scope_not_established")
            context_artifact_owner = CycleSubstrateContextArtifactOwner(
                store=self._artifact_store,
                control_store=self._control_store,
            )
            if configured_candidate_owner:
                from polisyos.runtime.quality.recursive_generation_cycle import (
                    RecursiveLeafContextOwner,
                )

                recursive_leaf_context_owner = RecursiveLeafContextOwner(
                    store=self._artifact_store,
                    context_owner=context_artifact_owner,
                    admission_owner=admission_owner,
                    verified_nl_job_scope=verified_nl_job_scope,
                )

            def resolve_cycle_substrate_context(
                problem: DesignProblem,
            ) -> object | None:
                if configured_candidate_owner:
                    admitted = admission_owner.admit_context(
                        problem=problem,
                        job_id=job.job_id,
                        run_id=str(job.run_id),
                        tenant_id=bound_tenant_id,
                        cell_id=bound_cell_id,
                    )
                else:
                    admitted = admission_owner.admit_context(
                        target_world_scope_profile_id=profile_id,
                        problem=problem,
                        job_id=job.job_id,
                        run_id=str(job.run_id),
                        tenant_id=bound_tenant_id,
                        cell_id=bound_cell_id,
                    )
                if admitted is None:
                    return None
                offer = admitted if type(admitted) is CandidateSimulationContextOffer else None
                admitted_context = offer.context if offer is not None else admitted
                if type(admitted_context) is not CycleSubstrateContext:
                    raise RuntimeError("cycle_substrate_context_admission_owner_returned_untyped")
                context_owner = context_artifact_owner
                context_ref = context_owner.persist_for_current_job(
                    admitted_context,
                    problem=problem,
                    verified_nl_job_scope=verified_nl_job_scope,
                )
                replayed = context_owner.resolve_for_current_job(
                    context_ref,
                    problem=problem,
                    verified_nl_job_scope=verified_nl_job_scope,
                )
                if replayed.context.content_hash != admitted_context.content_hash:
                    raise RuntimeError("cycle_substrate_context_job_replay_changed_content")
                cycle_substrate_context_job_ref = str(context_ref.artifact_id)
                context.cycle_substrate_context_job_ref = cycle_substrate_context_job_ref
                context.cycle_substrate_context_job_selected_ref = context_ref
                if offer is not None:
                    handoff = CandidateSimulationContextHandoff(
                        context=replayed.context,
                        context_job_ref=context_ref,
                        profile=offer.profile,
                        profile_config_ref=offer.profile_config_ref,
                        job_id=job.job_id,
                        run_id=str(job.run_id),
                        tenant_id=bound_tenant_id,
                        cell_id=bound_cell_id,
                        model_declaration=offer.model_declaration,
                        model_declaration_ref=offer.model_declaration_ref,
                        ncm_ref=offer.ncm_ref,
                    )

                    candidate_simulation_context_binding.update(
                        {
                            "handoff": handoff,
                            "context_owner": context_owner,
                            "context_ref": context_ref,
                            "problem": problem,
                            "verified_nl_job_scope": verified_nl_job_scope,
                            "offer": offer,
                        }
                    )
                    # The executable Core interval begins once the
                    # configured context has passed store replay and
                    # current-job owner admission, before recursive N4/N5.
                    context.start_core_attempt()
                    return handoff
                context.start_core_attempt()
                return replayed.context

            cycle_substrate_context_resolver = resolve_cycle_substrate_context
        context.candidate_simulation_currentness_resolver = (
            candidate_simulation_currentness_resolver
        )
        context.cycle_substrate_context_resolver = cycle_substrate_context_resolver
        context.recursive_leaf_context_owner = recursive_leaf_context_owner

    def _prepare_control_nl_budget_context(self, context: _ControlNLJobContext) -> None:
        """Resolve recursive budget and producer settlement binding for the job."""
        job = context.job
        payload = context.payload
        execution_scope = context.execution_scope
        intent_band = context.intent_band
        from polisyos.runtime.http.services.control.generation_cycle import (
            _resolve_http_recursive_budget,
        )

        max_cycles, recursive_budget_resolution = _resolve_http_recursive_budget(
            payload.get("max_iterations")
        )
        raw_budget_usd = payload.get("run_budget_usd")
        budget_usd = Decimal("5" if raw_budget_usd is None else str(raw_budget_usd))
        if intent_band is ExecutionIntentBand.EVAL_SAFETY_REQUIRED:
            # Core's leading RUN_STARTED precedes its protected
            # Evaluation Safety computation.
            context.start_core_attempt()
        elif (
            intent_band
            in {
                ExecutionIntentBand.CANDIDATE_ONLY,
                ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
            }
            and execution_scope.status == "established"
            and execution_scope.tenant_id is not None
            and execution_scope.cell_id is not None
        ):
            # Candidate runs also need a Core-owned output root so
            # their persisted N4 source and producer events can be
            # served by the ordinary run readers.
            context.start_core_attempt()
        producer_run_binding_scope: AbstractContextManager[Any] = nullcontext()
        producer_settlement_store = self._llm_producer_settlement_store
        if (
            producer_settlement_store is not None
            and job.kind == "natural_language_run"
            and job.run_id is not None
            and execution_scope.status == "established"
            and execution_scope.tenant_id is not None
            and execution_scope.cell_id is not None
        ):
            producer_run_binding = BudgetLedgerProducerRunBinding(
                run_id=str(job.run_id),
                tenant_id=execution_scope.tenant_id,
                cell_id=execution_scope.cell_id,
                profile_id=job.effective_execution_profile,
                control_job_id=job.job_id,
            )
            producer_run_binding_scope = producer_settlement_store.producer_run_binding_scope(
                producer_run_binding
            )
        context.recursive_budget_resolution = recursive_budget_resolution
        context.max_cycles = max_cycles
        context.budget_usd = budget_usd
        context.producer_run_binding_scope = producer_run_binding_scope
