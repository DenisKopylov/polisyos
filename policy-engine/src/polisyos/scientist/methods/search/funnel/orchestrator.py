"""Stateful multi-fidelity funnel orchestration runtime."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol, TypeGuard, runtime_checkable
from uuid import uuid4

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir import TypedFailureCard
from polisyos.scientist.methods.search.contracts import EvaluationBundle
from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    DegradationMode,
    FunnelAttemptHistory,
    FunnelCostOrigin,
    FunnelEvaluationStatus,
    FunnelExecutedWorkPacket,
    FunnelOutcome,
    FunnelStage,
    FunnelStageResult,
    FunnelTicket,
    FunnelTraceStep,
    FunnelWorkPacketStatus,
    RoutingAction,
    UncertaintyEnvelope,
)
from polisyos.scientist.methods.search.lessons import (
    LessonRegistry,
    lesson_from_failure_card,
    success_lesson_from_outcome,
)
from polisyos.scientist.methods.search.objective import (
    _POLICY_RUNTIME_INVOCATION_FIELDS,
    ObjectiveScoreAdmission,
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    SourceMetricObservation,
    _policy_runtime_invocation_bindings_status,
    _unestablished_score_assessment,
    recompute_source_government_balance,
    reconcile_objective_score_assessment,
    source_observation_input_refs,
)

# isort: split
from polisyos.scientist.methods.search.contracts import CandidateProposal
from polisyos.scientist.methods.search.frontier import (
    candidate_payloads_equal,
    materialize_candidate_proposal,
    policy_candidate_hash,
)
from polisyos.scientist.methods.search.sentinels import extract_sentinel_metadata
from polisyos.scientist.methods.search.stages import CorrelationTracker
from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context
from polisyos.scientist.methods.search.uncertainty import (
    SearchOwnedAttemptAssociationResolver,
    SearchOwnedHistoricalAttemptAssociationResolver,
    SearchUncertaintyCurrentRead,
    SearchUncertaintyOwnerTaskContext,
    SearchUncertaintyTicketState,
    load_source_bound_risk_observation,
    persist_search_uncertainty_v2,
    persist_source_bound_risk_observation,
    produce_search_task_admission,
    resolve_search_uncertainty_store,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    ParetoSnapshot,
    PredictiveVOIScheduler,
    SchedulingDecision,
    SimpleVOIScheduler,
    VOICostOrigin,
    _policy_evaluation_vector_source_chain_matches_store,
    _VOIWorkPacketClaim,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState

logger = get_logger(__name__)


@runtime_checkable
class _VOIStageResultObserver(Protocol):
    """Describe the optional base stage-result observation callback."""

    def observe_stage_result(
        self,
        *,
        candidate_id: str,
        task_family: str = "policy",
        domain: str = "",
        tenant_hash: str = "",
        stage_level: int,
        frontier_position: str = "unknown",
        cheap_signal: CheapSignalVector | None = None,
        actual_objective_value: float | None,
        score_assessment: ObjectiveScoreAssessment | None = None,
        objective_source: Mapping[str, object] | None = None,
        actual_promising: bool,
        duration_seconds: float,
        compute_cost_usd: float | None,
        compute_cost_origin: VOICostOrigin,
        timeout_occurred: bool = False,
        disagreement: float | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None: ...


@runtime_checkable
class _VOICalibrationStateUpdater(Protocol):
    """Describe the optional calibration-state update callback."""

    def update_calibration_state(self, metrics: Mapping[str, object]) -> None: ...


AdvancePolicy = Literal["stage_a", "full", "burn_in"]
_CONTINUABLE_ACTIONS = frozenset({"defer", "retry_cheaper"})
_DEGRADATION_MODES: frozenset[DegradationMode] = frozenset(
    {
        "normal",
        "conservative_routing",
        "no_promotion",
        "reduced_judge",
        "freeze_frontier",
        "prior_free",
        "auto_cap",
    }
)


def _is_degradation_mode(value: object) -> TypeGuard[DegradationMode]:
    """Check that an untrusted routing value is one of the supported modes."""
    return value in _DEGRADATION_MODES


def _stable_payload_hash(payload: Any) -> str:
    """Return a deterministic short hash for orchestrator-local identities."""

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _stable_candidate_hash(candidate: dict[str, Any]) -> str:
    """Return a deterministic subject hash for orchestrator-local accounting."""

    return policy_candidate_hash(candidate)


class _BoundFunnelStageCallable:
    """Carry producer and attempt context to this funnel owner, not to a stage."""

    def __init__(
        self, owner: FunnelOrchestrator, owner_call: Callable[..., Any], stage: str
    ) -> None:
        self._owner = owner
        self._owner_call = owner_call
        self._stage = stage

    def __call__(self, candidate: dict[str, Any], context: dict[str, Any]) -> Any:
        return self._owner_call(candidate, context, None, None)

    def with_proposal(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
        proposal: CandidateProposal | None,
        prior_ticket_id: str | None,
    ) -> Any:
        return self._owner_call(candidate, context, proposal, prior_ticket_id)


def _candidate_identity(candidate: dict[str, Any], proposal: CandidateProposal | None) -> str:
    if proposal is not None:
        if not candidate_payloads_equal(materialize_candidate_proposal(proposal), candidate):
            raise ValueError("funnel_candidate_proposal_mismatch")
        return policy_candidate_hash(proposal)
    return policy_candidate_hash(candidate)


def _stable_context_identity(context: Mapping[str, Any]) -> dict[str, Any]:
    """Keep every JSON-native context input; opaque inputs disable reuse."""
    value = dict(context)
    # The same strict JSON-native owner is used for candidate and context.
    # Its return value is not authority; this call validates lossless encoding.
    policy_candidate_hash(value)
    return deepcopy(value)


def _funnel_score_admission(
    result: FunnelStageResult, *, owner_context: object | None = None
) -> ObjectiveScoreAdmission:
    """Recompute one selected score admission from the result's retained basis."""
    assessment = result.score_assessment
    if assessment is None and result.score_admission is not None:
        assessment = result.score_admission.reported_assessment
    return reconcile_objective_score_assessment(
        assessment,
        result.simulation_results,
        prior_admission=result.score_admission,
        reported_status=result.score_status,
        reported_value=result.objective_value,
        owner_context=owner_context,
    )


def _selected_funnel_score_status(result: FunnelStageResult) -> ObjectiveScoreStatus:
    """Return the status from the shared typed score admission result."""
    return _funnel_score_admission(result).status


def _reconcile_funnel_score(
    result: FunnelStageResult, *, owner_context: object | None = None
) -> FunnelStageResult:
    """Retain both the score basis and its source-recomputed admission state."""
    admission = _funnel_score_admission(result, owner_context=owner_context)
    assessment = admission.reported_assessment or result.score_assessment
    if admission.status is ObjectiveScoreStatus.AVAILABLE:
        return replace(
            result,
            objective_value=(
                None
                if admission.recomputed_assessment is None
                else admission.recomputed_assessment.value
            ),
            score_status=ObjectiveScoreStatus.AVAILABLE,
            score_assessment=assessment,
            score_admission=admission,
        )

    if admission.status is ObjectiveScoreStatus.NOT_ESTABLISHED and assessment is None:
        if result.objective_value is None:
            # Keep structural candidate work, but carry a typed unestablished result.
            return replace(
                result,
                score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
                score_assessment=None,
                score_admission=admission,
            )

    candidate_only_promise = result.is_promising and _candidate_score_limited(result)
    feedback = dict(result.feedback)
    if result.objective_value is not None:
        feedback.setdefault("unbound_objective_diagnostic", result.objective_value)
    return replace(
        result,
        objective_value=None,
        is_promising=candidate_only_promise,
        score_status=admission.status,
        score_assessment=assessment,
        score_admission=admission,
        feedback=feedback,
    )


def _candidate_score_limited(result: FunnelStageResult) -> bool:
    """Allow only a recomputed typed limitation to continue as candidate work."""
    admission = _funnel_score_admission(result)
    assessment = admission.reported_assessment
    if assessment is None or result.objective_value is not None:
        return False
    if result.score_admission is not None and result.score_admission.status is not admission.status:
        return False
    if admission.status is ObjectiveScoreStatus.UNAVAILABLE:
        return (
            admission.predicate_status == "recomputed"
            and admission.recomputed_assessment == assessment
        )
    return (
        admission.status is ObjectiveScoreStatus.NOT_ESTABLISHED
        and bool(assessment.limitation)
        and (
            (
                admission.predicate_status == "recomputed"
                and admission.recomputed_assessment == assessment
            )
            or (assessment.rule_spec is None and admission.predicate_status == "not_established")
        )
    )


def _finalize_terminal_completion(ticket: FunnelTicket) -> None:
    """Finalize executed state; reused history is finalized only in its projection."""
    if ticket.result_reuse_source_ticket_id is not None:
        return
    if ticket.final_action != "complete" or not ticket.is_terminal:
        return
    result = ticket.last_result
    if result is None:
        ticket.final_action = "defer"
        return
    reconciled = _reconcile_funnel_score(result)
    admission = _funnel_score_admission(reconciled)
    if admission.status is ObjectiveScoreStatus.AVAILABLE:
        terminal_result = reconciled
    else:
        ticket.final_action = (
            "reject" if admission.status is ObjectiveScoreStatus.INVALID else "defer"
        )
        terminal_result = replace(
            reconciled,
            is_promising=False,
            terminal_action=ticket.final_action,
        )

    result_level = max(ticket.stage_results)
    ticket.stage_results[result_level] = terminal_result
    for step in reversed(ticket.trace):
        if step.fidelity_level == result_level and step.stage_name == result.stage_name:
            step.objective_value = terminal_result.objective_value
            step.is_promising = terminal_result.is_promising
            step.score_status = terminal_result.score_status
            step.score_assessment = terminal_result.score_assessment
            step.score_admission = terminal_result.score_admission
            break


def _aggregate_funnel_cost(
    trace: Iterable[FunnelTraceStep],
) -> tuple[float | None, FunnelCostOrigin]:
    """Aggregate stage costs without turning an unknown stage into zero."""
    steps = list(trace)
    if not steps or any(
        step.compute_cost_usd is None or step.compute_cost_origin == "unknown" for step in steps
    ):
        return None, "unknown"
    total = sum(step.compute_cost_usd or 0.0 for step in steps)
    origin: FunnelCostOrigin = (
        "reported" if all(step.compute_cost_origin == "reported" for step in steps) else "estimated"
    )
    return total, origin


def _admit_search_uncertainty_task(
    *,
    funnel_ticket_id: str,
    owner_context: SearchUncertaintyOwnerTaskContext,
    context: Mapping[str, Any],
    owned_attempt_association_resolver: SearchOwnedAttemptAssociationResolver | None,
    owned_historical_attempt_association_resolver: (
        SearchOwnedHistoricalAttemptAssociationResolver | None
    ),
) -> tuple[str | None, int | None, ArtifactRef | None, str | None]:
    """Persist the actual pre-dispatch Search owner context and numeric-free obligation."""
    raw_store = context.get("store")
    if raw_store is None:
        return None, None, None, "artifact_store_missing"
    store = resolve_search_uncertainty_store(raw_store)
    if store is None:
        return None, None, None, "artifact_store_incompatible"
    try:
        state = SearchUncertaintyTicketState(
            store,
            owned_attempt_association_resolver=owned_attempt_association_resolver,
            owned_historical_attempt_association_resolver=(
                owned_historical_attempt_association_resolver
            ),
        )
        ticket_id = funnel_ticket_id
        owner_context_ref = persist_search_uncertainty_v2(store, owner_context)
        row = state.initialize(ticket_id)
        if row.task_admission_ref is not None:
            selected = state.read_current_snapshot(ticket_id)
            if (
                selected is not None
                and selected.task_admission is not None
                and selected.task_admission.owner_context_ref == owner_context_ref
            ):
                binding_ref = row.current_binding_ref
                return ticket_id, row.ticket_generation, binding_ref, None
            row = state.bump_ticket_generation(
                ticket_id,
                expected_generation=row.ticket_generation,
            )
        elif row.owner_context_ref is not None and row.owner_context_ref != owner_context_ref:
            row = state.bump_ticket_generation(
                ticket_id,
                expected_generation=row.ticket_generation,
            )
        generation = row.ticket_generation
        _, _, admission_ref, _ = produce_search_task_admission(
            store,
            owner_context,
            ticket_id=ticket_id,
            ticket_generation=generation,
            selected_at=datetime.now(UTC),
        )
        selected_row = state.record_task_admission(
            ticket_id=ticket_id,
            expected_generation=generation,
            expected_projection_revision=row.projection_revision,
            admission_ref=admission_ref,
        )
        binding_ref = state.publish_task_binding(
            ticket_id,
            expected_generation=selected_row.ticket_generation,
            expected_projection_revision=selected_row.projection_revision,
        )
        return ticket_id, selected_row.ticket_generation, binding_ref, None
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return None, None, None, f"task_admission:{type(exc).__name__}"


class FunnelOrchestrator:
    """Orchestrates candidates through a stateful multi-level funnel."""

    def __init__(
        self,
        stages: list[FunnelStage],
        max_level: int | None = None,
        *,
        stage_a_max_level: int = 2,
        voi_scheduler: SimpleVOIScheduler | PredictiveVOIScheduler | None = None,
        budget_state: BudgetState | None = None,
        frontier: ParetoSnapshot | None = None,
        correlation_tracker: CorrelationTracker | None = None,
        lesson_registry: LessonRegistry | None = None,
        search_uncertainty_attempt_association_resolver: (
            SearchOwnedAttemptAssociationResolver | None
        ) = None,
        search_uncertainty_historical_attempt_association_resolver: (
            SearchOwnedHistoricalAttemptAssociationResolver | None
        ) = None,
    ) -> None:
        self._stages = sorted(stages, key=lambda stage: stage.fidelity_level)
        self._max_level = max_level
        self._stage_levels = [stage.fidelity_level for stage in self._stages]
        if len(self._stage_levels) != len(set(self._stage_levels)):
            raise ValueError("FunnelOrchestrator requires unique fidelity levels")
        self._stages_by_level = {stage.fidelity_level: stage for stage in self._stages}
        self._stage_a_max_level = int(stage_a_max_level)
        self._budget_state = budget_state or BudgetState()
        self._frontier = frontier or ParetoSnapshot()
        self._correlation_tracker = correlation_tracker
        self._lesson_registry = lesson_registry
        self._search_uncertainty_attempt_association_resolver = (
            search_uncertainty_attempt_association_resolver
        )
        self._search_uncertainty_historical_attempt_association_resolver = (
            search_uncertainty_historical_attempt_association_resolver
        )
        stage_costs = {
            stage.fidelity_level: self._decimal_from_float(stage.estimated_cost_usd)
            for stage in self._stages
        }
        self._voi_scheduler = voi_scheduler or SimpleVOIScheduler(stage_costs=stage_costs)
        self._tickets: dict[str, FunnelTicket] = {}
        self._ticket_cache: dict[str, str] = {}
        self._latest_ticket_by_candidate: dict[str, str] = {}
        self._latest_ticket_by_context: dict[str, str] = {}

    @property
    def stages(self) -> list[FunnelStage]:
        return list(self._stages)

    def submit(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
        *,
        search_uncertainty_owner_context: SearchUncertaintyOwnerTaskContext | None = None,
        candidate_proposal: CandidateProposal | None = None,
        _prior_attempt_id: str | None = None,
    ) -> FunnelTicket:
        """Submit a candidate to the orchestrator and return a reusable ticket."""

        candidate_hash = _candidate_identity(candidate, candidate_proposal)
        sentinel_meta = extract_sentinel_metadata(candidate) or {}
        ticket_context = dict(context)
        prior_attempt_id = _prior_attempt_id
        prior_attempt = None
        if prior_attempt_id is not None:
            if not isinstance(prior_attempt_id, str) or prior_attempt_id not in self._tickets:
                raise ValueError("funnel_prior_attempt_unresolved")
            prior_attempt = self._tickets[prior_attempt_id]
            if not candidate_payloads_equal(prior_attempt.candidate, candidate):
                raise ValueError("funnel_prior_attempt_candidate_mismatch")
            if (
                _candidate_identity(prior_attempt.candidate, prior_attempt.candidate_proposal)
                != candidate_hash
            ):
                raise ValueError("funnel_prior_attempt_subject_mismatch")
        metric_projection_basis = ticket_context.pop("_funnel_method_metric_projection_basis", None)
        cache_context = dict(ticket_context)
        if metric_projection_basis is not None:
            cache_context["_funnel_method_metric_projection_basis"] = metric_projection_basis
        if search_uncertainty_owner_context is not None:
            cache_context["search_uncertainty_owner_context"] = (
                search_uncertainty_owner_context.model_dump(mode="json", exclude_none=False)
            )
        if sentinel_meta:
            ticket_context.update(sentinel_meta)
            ticket_context["is_sentinel"] = True
        routing_mode = self._routing_mode(ticket_context)
        try:
            cache_key = self._ticket_cache_key(
                candidate,
                cache_context,
                sentinel_meta=sentinel_meta,
                routing_mode=routing_mode,
            )
        except (TypeError, ValueError):
            # Opaque source handles cannot establish a reusable input basis.
            cache_key = f"uncacheable:{uuid4()}"
        # Reuse only the explicit live Stage A attempt handed back by this
        # owner to its matching Stage B call. A separate request must run the
        # current stage, lesson, correlation, uncertainty and access gates.
        # Immutable selected Foundry/AD01 source computation remains reusable
        # through its owner; a whole prior funnel result is not that source.
        if prior_attempt is not None and search_uncertainty_owner_context is None:
            try:
                same_context = _stable_context_identity(
                    self._ticket_effective_context(prior_attempt)
                ) == _stable_context_identity(cache_context)
            except (TypeError, ValueError):
                same_context = False
            if same_context:
                # The ticket is the same live split, but mutable lessons,
                # correlation, access and routing owners may have changed since
                # Stage A. Rerun the gates instead of carrying their old results.
                # Keep the physical trace and already-recorded attribution.
                prior_attempt.stage_results.clear()
                prior_attempt.current_level = None
                prior_attempt.next_level = self._first_level()
                prior_attempt.final_action = "advance"
                prior_attempt.is_terminal = False
                prior_attempt.last_scheduling_decision = None
                prior_attempt.terminal_basis = None
                prior_attempt.continuation_reason = "live_split_gates_rechecked"
                return prior_attempt
        ticket_id = str(uuid4())
        uncertainty_ticket_id: str | None = None
        uncertainty_generation: int | None = None
        uncertainty_binding_ref: ArtifactRef | None = None
        uncertainty_admission_failure: str | None = None
        if search_uncertainty_owner_context is not None:
            (
                uncertainty_ticket_id,
                uncertainty_generation,
                uncertainty_binding_ref,
                uncertainty_admission_failure,
            ) = _admit_search_uncertainty_task(
                funnel_ticket_id=ticket_id,
                owner_context=search_uncertainty_owner_context,
                context=ticket_context,
                owned_attempt_association_resolver=(
                    self._search_uncertainty_attempt_association_resolver
                ),
                owned_historical_attempt_association_resolver=(
                    self._search_uncertainty_historical_attempt_association_resolver
                ),
            )
        ticket = FunnelTicket(
            ticket_id=ticket_id,
            candidate_hash=candidate_hash,
            candidate=deepcopy(candidate),
            context=ticket_context,
            candidate_proposal=deepcopy(candidate_proposal),
            next_level=self._first_level(),
            cache_key=cache_key,
            lineage=(ticket_id,),
            search_uncertainty_ticket_id=uncertainty_ticket_id,
            search_uncertainty_generation=uncertainty_generation,
            search_uncertainty_task_binding_ref=uncertainty_binding_ref,
        )
        if uncertainty_admission_failure is not None:
            ticket.context["search_uncertainty_admission_failure"] = uncertainty_admission_failure
        ticket._set_method_metric_projection_basis(metric_projection_basis)
        if prior_attempt is not None:
            # This is a distinct physical attempt. Retain the actual preceding
            # ticket's trace regardless of unrelated cache/continuation lookup.
            ticket.parent_ticket_id = prior_attempt.ticket_id
            ticket.prior_attempt_ticket_id = prior_attempt.ticket_id
            ticket.lineage = (*prior_attempt.lineage, ticket_id)
        store = ticket.context.get("store")
        candidate_ref = ticket.context.get("policy_candidate_ref")
        welfare_ref = ticket.context.get("welfare_bundle_ref")
        if (
            store is not None
            and isinstance(candidate_ref, ArtifactRef)
            and isinstance(welfare_ref, ArtifactRef)
        ):
            try:
                ticket.context["welfare_candidate_observation_ref"] = (
                    persist_source_bound_risk_observation(
                        store,
                        candidate_ref=candidate_ref,
                        welfare_bundle_ref=welfare_ref,
                    )
                )
            except (
                AttributeError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                logger.info("Candidate welfare observation withheld: %s", type(exc).__name__)
        self._tickets[ticket.ticket_id] = ticket
        # The current request retains its ticket, but does not publish a
        # reusable aggregate decision for a later independent request.
        return ticket

    @staticmethod
    def _carry_forward_completed_result(source: FunnelTicket, ticket: FunnelTicket) -> None:
        """Retain result history after the new ticket's normal owner admission.

        Physical work and its evidence keep their original identities. A cache
        lookup creates no new observation, charge, lesson or correlation sample.
        """
        ticket.submitted_via_cache = True
        # Retain history without transferring its ephemeral score capability.
        # The single fresh projection admits selected work before replaying the
        # scalar with this request's current owner basis.
        ticket.stage_results = deepcopy(source.stage_results)
        ticket.trace = deepcopy(source.trace)
        ticket.current_level = source.current_level
        ticket.next_level = source.next_level
        ticket.final_action = source.final_action
        ticket.degradation_mode = source.degradation_mode
        ticket.is_terminal = True
        ticket.last_scheduling_decision = source.last_scheduling_decision
        ticket.lesson_refs = list(source.lesson_refs)
        ticket.correlation_recorded = True
        ticket.lessons_finalized = True
        ticket.continuation_reason = "compatible_result_reused"
        ticket.terminal_basis = source.terminal_basis
        ticket.result_reuse_source_ticket_id = (
            source.result_reuse_source_ticket_id or source.ticket_id
        )

    def advance(
        self,
        ticket: FunnelTicket | str,
        target_level: int | None = None,
        policy: AdvancePolicy | None = None,
    ) -> FunnelOutcome:
        """Advance an existing ticket to the requested target level or policy."""

        resolved_ticket = self._resolve_ticket(ticket)
        execution_target = self._resolve_target_level(target_level, policy)
        resolved_ticket.degradation_mode = self._routing_mode(resolved_ticket.context)
        burn_in_calibration = (
            policy == "burn_in"
            and str(resolved_ticket.context.get("burn_in_cohort", "")) == "calibration"
        )

        while not resolved_ticket.is_terminal:
            next_level = self._resolve_next_level(resolved_ticket)
            if next_level is None:
                self._mark_terminal(resolved_ticket)
                break
            if next_level > execution_target:
                break
            if resolved_ticket.degradation_mode == "freeze_frontier":
                resolved_ticket.final_action = "defer"
                resolved_ticket.is_terminal = True
                break

            if resolved_ticket.current_level in (2, 3) and resolved_ticket.next_level == next_level:
                scheduling_action = self._maybe_schedule_transition(
                    resolved_ticket,
                    execution_target=execution_target,
                    policy=policy,
                    trace_step=None,
                )
                if scheduling_action in {"reject", "defer", "retry_cheaper"}:
                    break

            stage = self._stages_by_level[next_level]
            stage_candidate = deepcopy(resolved_ticket.candidate)
            result = stage.evaluate(stage_candidate, self._build_stage_context(resolved_ticket))
            try:
                subject_unchanged = candidate_payloads_equal(
                    stage_candidate, resolved_ticket.candidate
                )
            except (TypeError, ValueError):
                subject_unchanged = False
            if not subject_unchanged:
                # Preserve the physical attempt and cost, but admit no score,
                # work packet, routing decision or changed subject as the input.
                resolved_ticket.trace.append(
                    FunnelTraceStep(
                        fidelity_level=next_level,
                        stage_name=result.stage_name,
                        objective_value=None,
                        is_promising=False,
                        duration_seconds=result.duration_seconds,
                        compute_cost_usd=result.compute_cost_usd,
                        compute_cost_origin=result.compute_cost_origin,
                        score_status=ObjectiveScoreStatus.INVALID,
                    )
                )
                resolved_ticket.final_action = "defer"
                resolved_ticket.is_terminal = True
                resolved_ticket.continuation_reason = "evaluated_subject_mutated"
                break
            result = _reconcile_funnel_score(result)
            work_packet_claim = self._admit_executed_work_packet(
                resolved_ticket, result, next_level
            )
            resolved_ticket.stage_results[next_level] = result
            resolved_ticket.current_level = next_level
            resolved_ticket.next_level = self._level_after(next_level)

            routing_decision = (
                result.cheap_signal.routing_decision() if result.cheap_signal is not None else None
            )
            trace_step = FunnelTraceStep(
                fidelity_level=next_level,
                stage_name=result.stage_name,
                objective_value=result.objective_value,
                is_promising=result.is_promising,
                duration_seconds=result.duration_seconds,
                compute_cost_usd=result.compute_cost_usd,
                compute_cost_origin=result.compute_cost_origin,
                score_status=result.score_status,
                score_assessment=result.score_assessment,
                score_admission=result.score_admission,
                executed_work_packet_ref=result.executed_work_packet_ref,
                executed_work_packet_status=result.executed_work_packet_status,
                routing_decision=routing_decision,
                failure_count=len(result.failure_cards),
                blocker_count=sum(1 for card in result.failure_cards if card.is_blocker),
            )
            resolved_ticket.trace.append(trace_step)
            self._maybe_record_voi_observation(
                resolved_ticket, result, next_level, work_packet_claim=work_packet_claim
            )

            score_limited = _candidate_score_limited(result)
            if result.has_blockers:
                logger.debug(
                    "Funnel stopped at %s: %d blocker(s)",
                    result.stage_name,
                    trace_step.blocker_count,
                )
                resolved_ticket.final_action = "reject"
                resolved_ticket.is_terminal = True
                break

            if result.terminal_action is not None:
                if result.terminal_action in {"advance", "defer"} and score_limited:
                    if self._level_after(next_level) is None:
                        resolved_ticket.final_action = "defer"
                        resolved_ticket.is_terminal = True
                        break
                    resolved_ticket.final_action = "advance"
                else:
                    resolved_ticket.final_action = result.terminal_action
                    if result.terminal_action != "advance":
                        resolved_ticket.is_terminal = True
                        break
            if not result.is_promising:
                if score_limited and result.terminal_action in {None, "advance", "defer"}:
                    if self._level_after(next_level) is None:
                        resolved_ticket.final_action = "defer"
                        resolved_ticket.is_terminal = True
                        break
                    resolved_ticket.final_action = "advance"
                    logger.debug(
                        "Funnel continues candidate-only after unscored %s evaluation",
                        result.stage_name,
                    )
                elif burn_in_calibration and next_level in (1, 2, 3):
                    logger.debug(
                        "Burn-in bypass at %s: continuing despite non-promising result.",
                        result.stage_name,
                    )
                    self._maybe_record_correlation(resolved_ticket)
                    continue
                elif not score_limited or result.terminal_action not in {None, "advance", "defer"}:
                    logger.debug(
                        "Funnel stopped at %s: not promising (obj=%s)",
                        result.stage_name,
                        result.objective_value,
                    )
                    resolved_ticket.final_action = "reject"
                    resolved_ticket.is_terminal = True
                    break
            if routing_decision == "reject":
                if burn_in_calibration and next_level in (1, 2, 3):
                    logger.debug(
                        "Burn-in bypass at %s: ignoring reject routing for calibration cohort.",
                        result.stage_name,
                    )
                    self._maybe_record_correlation(resolved_ticket)
                    continue
                rejected_result = FunnelStageResult(
                    policy_candidate=result.policy_candidate,
                    objective_value=result.objective_value,
                    is_promising=False,
                    stage_name=result.stage_name,
                    duration_seconds=result.duration_seconds,
                    timestamp=result.timestamp,
                    simulation_results=result.simulation_results,
                    feedback=result.feedback,
                    predicted_score=result.predicted_score,
                    actual_score=result.actual_score,
                    score_status=result.score_status,
                    score_assessment=result.score_assessment,
                    score_admission=result.score_admission,
                    uncertainty_envelope=result.uncertainty_envelope,
                    cheap_signal=result.cheap_signal,
                    failure_cards=result.failure_cards,
                    compute_cost_usd=result.compute_cost_usd,
                    compute_cost_origin=result.compute_cost_origin,
                    executed_work_packet_ref=result.executed_work_packet_ref,
                    executed_work_packet_status=result.executed_work_packet_status,
                    fidelity_level=result.fidelity_level,
                    audit_refs=list(result.audit_refs),
                    uncertainty_observation_ref=result.uncertainty_observation_ref,
                    actionable_side_information_ref=result.actionable_side_information_ref,
                    terminal_action=result.terminal_action,
                )
                resolved_ticket.stage_results[next_level] = rejected_result
                trace_step.is_promising = False
                resolved_ticket.final_action = "reject"
                resolved_ticket.is_terminal = True
                break

            if routing_decision == "fast_track" and resolved_ticket.degradation_mode == "normal":
                fast_track_level = self._fast_track_level(next_level, execution_target)
                if fast_track_level is not None:
                    resolved_ticket.next_level = fast_track_level

            scheduling_action = self._maybe_schedule_transition(
                resolved_ticket,
                execution_target=execution_target,
                policy=policy,
                trace_step=trace_step,
            )
            if scheduling_action in {"reject", "defer", "retry_cheaper"}:
                break

            if resolved_ticket.next_level is None:
                self._mark_terminal(resolved_ticket)
                break

            self._maybe_record_correlation(resolved_ticket)

        _finalize_terminal_completion(resolved_ticket)
        if (
            policy != "stage_a"
            and resolved_ticket.stage_results
            and execution_target < self._stage_levels[-1]
            and resolved_ticket.is_terminal
            and resolved_ticket.final_action == "complete"
        ):
            # A full request capped below the available funnel is complete as
            # control flow, but not an evaluated full-fidelity result.
            resolved_ticket.final_action = "defer"

        self._maybe_record_correlation(resolved_ticket)
        if (
            resolved_ticket.is_terminal
            and resolved_ticket.final_action in _CONTINUABLE_ACTIONS
            and resolved_ticket.terminal_basis is None
        ):
            resolved_ticket.terminal_basis = self._continuation_basis(resolved_ticket)
        self._maybe_record_lessons(resolved_ticket)
        return self.get_outcome(resolved_ticket)

    def get_outcome(
        self,
        ticket: FunnelTicket | str,
    ) -> FunnelOutcome:
        """Return the aggregated current outcome for a ticket."""

        resolved_ticket = self._resolve_ticket(ticket)
        projection_ticket = resolved_ticket
        if resolved_ticket.result_reuse_source_ticket_id is not None:
            # Fresh admission can change this request's decision, while the
            # retained execution trace remains the immutable source history.
            projection_ticket = replace(
                resolved_ticket,
                stage_results={
                    level: self._reconcile_reused_work_result(resolved_ticket, result, level)
                    for level, result in resolved_ticket.stage_results.items()
                },
                trace=[],
                result_reuse_source_ticket_id=None,
            )
        _finalize_terminal_completion(projection_ticket)
        outcome_stage_results = dict(projection_ticket.stage_results)
        ordered_results = [outcome_stage_results[level] for level in sorted(outcome_stage_results)]
        failure_cards: list[TypedFailureCard] = []
        envelopes: list[UncertaintyEnvelope] = []
        audit_refs: list[ArtifactRef] = []
        actionable_side_information_refs: list[ArtifactRef] = []
        for result in ordered_results:
            failure_cards.extend(result.failure_cards)
            envelopes.append(result.uncertainty_envelope)
            audit_refs.extend(result.audit_refs)
            if result.actionable_side_information_ref is not None:
                actionable_side_information_refs.append(result.actionable_side_information_ref)

        uncertainty_envelope = UncertaintyEnvelope.merge_max(envelopes)
        if not envelopes:
            uncertainty_envelope = UncertaintyEnvelope.unknown()

        observation_refs: list[ArtifactRef] = []
        intake_failures: list[str] = []
        store = resolved_ticket.context.get("store")
        subject_ref = resolved_ticket.context.get("policy_candidate_ref")
        current_read: SearchUncertaintyCurrentRead | None = None
        current_uncertainty: UncertaintyEnvelope | None = None
        search_ticket_id = resolved_ticket.search_uncertainty_ticket_id
        if store is not None and search_ticket_id is not None:
            search_store = resolve_search_uncertainty_store(store)
            if search_store is None:
                intake_failures.append("fresh_current_read:artifact_store_incompatible")
            else:
                try:
                    current_read = SearchUncertaintyTicketState(
                        search_store,
                        owned_attempt_association_resolver=(
                            self._search_uncertainty_attempt_association_resolver
                        ),
                        owned_historical_attempt_association_resolver=(
                            self._search_uncertainty_historical_attempt_association_resolver
                        ),
                    ).read_current_snapshot(search_ticket_id)
                except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                    intake_failures.append(f"fresh_current_read:{type(exc).__name__}")
            if current_read is None and search_store is not None:
                intake_failures.append("fresh_current_read:ticket_state_missing")
            elif current_read is not None and current_read.status == "not_established":
                intake_failures.append(
                    "fresh_current_read:"
                    + (current_read.reason_code or "owner_projection_not_selected")
                )
            elif current_read is not None and current_read.task_admission is None:
                intake_failures.append("task_admission_missing")
            elif (
                current_read is not None
                and current_read.task_admission is not None
                and current_read.task_admission.status == "not_established"
            ):
                intake_failures.extend(current_read.task_admission.missing_slices)
            elif current_read is not None and current_read.projection is not None:
                observation_refs.extend(current_read.projection.unassessed_observation_refs)
                observation_refs.extend(
                    successor.observation_ref
                    for obligation in current_read.projection.current_obligations
                    for successor in obligation.successors
                )
                if current_read.projection.active_unknown_obligation_ids:
                    intake_failures.append("native_method_assessment_pending")
                if current_read.projection.incomplete_obligation_ids:
                    intake_failures.append("same_generation_successor_conflict")
        else:
            intake_failures.append(
                resolved_ticket.context.get(
                    "search_uncertainty_admission_failure",
                    "pre_dispatch_owner_context_or_store_missing",
                )
            )
        if any(result.uncertainty_observation_ref is not None for result in ordered_results):
            intake_failures.append("legacy_v1_observations_route_only")
        final_level = max(outcome_stage_results) if outcome_stage_results else None
        final_result = outcome_stage_results[final_level] if final_level is not None else None
        if final_result is not None:
            feedback = dict(final_result.feedback or {})
            feedback["uncertainty_current"] = None
            feedback["uncertainty_current_status"] = (
                "not_established"
                if current_read is None or current_read.status != "available_as_of_task_epoch"
                else current_read.admission_status
            )
            feedback["search_uncertainty_current_read"] = (
                None
                if current_read is None
                else current_read.model_dump(mode="json", exclude_none=False)
            )
            feedback["uncertainty_historical_max"] = uncertainty_envelope.model_dump(mode="json")
            final_result = replace(final_result, feedback=feedback)
            if final_level is not None:
                outcome_stage_results[final_level] = final_result

        welfare_observation_ref = resolved_ticket.context.get("welfare_candidate_observation_ref")
        if (
            store is not None
            and isinstance(subject_ref, ArtifactRef)
            and isinstance(welfare_observation_ref, ArtifactRef)
        ):
            try:
                load_source_bound_risk_observation(store, welfare_observation_ref, subject_ref)
            except (
                AttributeError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                logger.info(
                    "Candidate welfare observation readback withheld: %s",
                    type(exc).__name__,
                )
            else:
                audit_refs.append(welfare_observation_ref)

        aggregate_cost_usd, aggregate_cost_origin = _aggregate_funnel_cost(resolved_ticket.trace)
        outcome_trace = list(resolved_ticket.trace)
        final_action = projection_ticket.final_action
        evaluation_status = self._evaluation_status(projection_ticket)
        if resolved_ticket.result_reuse_source_ticket_id is not None:
            # Retained stage prices describe the original execution, not a
            # measured charge (or measured zero) for this organizational request.
            aggregate_cost_usd, aggregate_cost_origin = None, "unknown"
            # Preserve actual source history, including its historical score and
            # work status. Fresh reuse admission is projected in stage_results.
            outcome_trace = deepcopy(resolved_ticket.trace)
            if any(result.executed_work_packet_status == "rejected" for result in ordered_results):
                final_action, evaluation_status = "defer", "partial"
        prior_history: list[FunnelAttemptHistory] = []
        history_status: Literal["complete", "verification_missing"] = "complete"
        seen_attempts = {resolved_ticket.ticket_id}
        previous_id = resolved_ticket.prior_attempt_ticket_id
        while previous_id is not None:
            previous = self._tickets.get(previous_id)
            if (
                previous_id in seen_attempts
                or previous is None
                or previous.candidate_hash != resolved_ticket.candidate_hash
            ):
                history_status = "verification_missing"
                break
            seen_attempts.add(previous_id)
            prior_history.append(
                FunnelAttemptHistory(ticket_id=previous_id, trace=deepcopy(previous.trace))
            )
            previous_id = previous.prior_attempt_ticket_id
        prior_history.reverse()
        return FunnelOutcome(
            ticket_id=resolved_ticket.ticket_id,
            candidate_hash=resolved_ticket.candidate_hash,
            trace=outcome_trace,
            stage_results=outcome_stage_results,
            final_result=final_result,
            failure_cards=failure_cards,
            uncertainty_envelope=uncertainty_envelope,
            compute_cost_usd=aggregate_cost_usd,
            compute_cost_origin=aggregate_cost_origin,
            degradation_mode=resolved_ticket.degradation_mode,
            final_action=final_action,
            completed=resolved_ticket.is_terminal,
            last_scheduling_decision=resolved_ticket.last_scheduling_decision,
            lesson_refs=list(resolved_ticket.lesson_refs),
            audit_refs=_dedupe_artifact_refs(audit_refs),
            actionable_side_information_refs=_dedupe_artifact_refs(
                actionable_side_information_refs
            ),
            parent_ticket_id=resolved_ticket.parent_ticket_id,
            lineage=resolved_ticket.lineage,
            continuation_reason=resolved_ticket.continuation_reason,
            result_reuse_source_ticket_id=resolved_ticket.result_reuse_source_ticket_id,
            prior_attempt_ticket_id=resolved_ticket.prior_attempt_ticket_id,
            prior_attempt_trace=(
                deepcopy(self._tickets[resolved_ticket.prior_attempt_ticket_id].trace)
                if resolved_ticket.prior_attempt_ticket_id in self._tickets
                else []
            ),
            prior_attempt_history=prior_history,
            prior_attempt_history_status=history_status,
            evaluation_status=evaluation_status,
            current_uncertainty_envelope=current_uncertainty,
            uncertainty_observation_refs=_dedupe_artifact_refs(observation_refs),
            uncertainty_intake_failures=intake_failures,
            search_uncertainty_current_read=current_read,
        )

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        """Backward-compatible convenience wrapper around submit+advance."""

        ticket = self.submit(candidate, context)
        outcome = self.advance(ticket, policy="full")
        result = outcome.final_result or self._empty_result(candidate)
        return self._compatibility_result(outcome, result)

    def as_stage_a_callable(
        self,
    ) -> Callable[[dict[str, Any], dict[str, Any]], EvaluationBundle]:
        """Return a SearchController-compatible Stage A callable."""

        def _stage_a(
            candidate: dict[str, Any],
            context: dict[str, Any],
            proposal: CandidateProposal | None,
            prior_ticket_id: str | None,
        ) -> EvaluationBundle:
            ticket = self.submit(
                candidate,
                context,
                candidate_proposal=proposal,
                _prior_attempt_id=prior_ticket_id,
            )
            outcome = self.advance(ticket, policy="stage_a")
            result = self._result_for_level(outcome, self._stage_a_execution_target())
            if result is None:
                result = outcome.final_result or self._empty_result(candidate)
            score_admission = _funnel_score_admission(result)
            selected_admission = score_admission.status
            score_assessment = score_admission.reported_assessment
            objective_value = (
                score_admission.recomputed_assessment.value
                if selected_admission is ObjectiveScoreStatus.AVAILABLE
                and score_admission.recomputed_assessment is not None
                else None
            )
            promising = (
                result.is_promising
                and selected_admission is ObjectiveScoreStatus.AVAILABLE
                and objective_value is not None
            )
            score_limited_continuation = (
                outcome.final_action == "advance"
                and outcome.evaluation_status == "partial"
                and _candidate_score_limited(result)
            )
            structural_continuation = (
                outcome.final_action == "advance"
                and outcome.evaluation_status == "partial"
                and result.score_assessment is None
                and result.objective_value is None
                and result.is_promising
            )
            candidate_continuation = score_limited_continuation or structural_continuation
            stage_a_passed = promising or candidate_continuation
            return EvaluationBundle(
                objective_value=objective_value,
                is_promising=promising,
                score_status=selected_admission,
                score_assessment=score_assessment,
                score_admission=score_admission,
                stage_a_passed=stage_a_passed,
                metadata={
                    "funnel_ticket_id": ticket.ticket_id,
                    "funnel_action": outcome.final_action,
                    "funnel_evaluation_status": outcome.evaluation_status,
                    "candidate_continuation": candidate_continuation,
                    "candidate_continuation_kind": (
                        "score_limited"
                        if score_limited_continuation
                        else "structural"
                        if structural_continuation
                        else None
                    ),
                },
            )

        return _BoundFunnelStageCallable(self, _stage_a, "stage_a")

    def as_stage_b_callable(
        self,
    ) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
        """Return a SearchController-compatible Stage B callable."""

        def _stage_b(
            candidate: dict[str, Any],
            context: dict[str, Any],
            proposal: CandidateProposal | None,
            prior_ticket_id: str | None,
        ) -> dict[str, Any]:
            ticket = self.submit(
                candidate,
                context,
                candidate_proposal=proposal,
                _prior_attempt_id=prior_ticket_id,
            )
            outcome = self.advance(ticket, policy="full")
            stage_result = outcome.final_result or self._empty_result(candidate)
            result = self._compatibility_result(outcome, stage_result)
            feedback = dict(result.feedback)
            feedback["funnel_action"] = outcome.final_action
            feedback["funnel_degradation_mode"] = outcome.degradation_mode
            feedback["funnel_cache"] = (
                "hit"
                if prior_ticket_id is not None and ticket.ticket_id == prior_ticket_id
                else "miss"
            )
            return {
                "simulation_results": result.simulation_results,
                "feedback": feedback,
                "objective_value": result.objective_value,
                "is_promising": result.is_promising,
                "_funnel_result": stage_result,
                "_funnel_outcome": outcome,
            }

        return _BoundFunnelStageCallable(self, _stage_b, "stage_b")

    def _ticket_cache_key(
        self,
        candidate: dict[str, Any],
        context: Mapping[str, Any],
        *,
        sentinel_meta: Mapping[str, Any],
        routing_mode: DegradationMode,
        candidate_proposal: CandidateProposal | None = None,
    ) -> str:
        return _stable_payload_hash(
            {
                "candidate": policy_candidate_hash(candidate),
                "context": _stable_context_identity(context),
                "routing_mode": routing_mode,
                "sentinel": _stable_context_identity(sentinel_meta),
            }
        )

    @staticmethod
    def _continuation_context_key(
        candidate: dict[str, Any],
        context: Mapping[str, Any],
        *,
        candidate_proposal: CandidateProposal | None = None,
    ) -> str:
        """Identify the effective evaluation context independently of routing mode."""

        return _stable_payload_hash(
            {
                "candidate": policy_candidate_hash(candidate),
                "context": _stable_context_identity(context),
            }
        )

    @staticmethod
    def _ticket_effective_context(ticket: FunnelTicket) -> dict[str, Any]:
        context = dict(ticket.context)
        basis = getattr(ticket, "_method_metric_projection_basis", None)
        if basis is not None:
            context["_funnel_method_metric_projection_basis"] = basis
        return context

    def _cached_ticket_for_key(
        self,
        cache_key: str,
        *,
        routing_mode: DegradationMode,
    ) -> FunnelTicket | None:
        cached_ticket_id = self._ticket_cache.get(cache_key)
        if cached_ticket_id is None:
            return None
        ticket = self._tickets[cached_ticket_id]
        try:
            current_key = self._ticket_cache_key(
                ticket.candidate,
                self._ticket_effective_context(ticket),
                sentinel_meta=extract_sentinel_metadata(ticket.candidate) or {},
                routing_mode=routing_mode,
                candidate_proposal=ticket.candidate_proposal,
            )
        except (TypeError, ValueError):
            return None
        if current_key != cache_key:
            return None
        if (
            ticket.is_terminal
            and ticket.final_action in _CONTINUABLE_ACTIONS
            and ticket.terminal_basis is not None
            and ticket.terminal_basis != self._continuation_basis(ticket, routing_mode=routing_mode)
        ):
            return None
        return ticket

    def _latest_ticket(
        self,
        candidate_hash: str,
        *,
        continuation_key: str | None = None,
    ) -> FunnelTicket | None:
        ticket_id = (
            self._latest_ticket_by_context.get(continuation_key)
            if continuation_key is not None
            else None
        )
        if ticket_id is None:
            ticket_id = self._latest_ticket_by_candidate.get(candidate_hash)
        if ticket_id is None:
            return None
        return self._tickets.get(ticket_id)

    def _can_reuse_continuation(
        self,
        ticket: FunnelTicket,
        continuation_key: str,
        *,
        routing_mode: DegradationMode,
    ) -> bool:
        return bool(
            ticket.is_terminal
            and ticket.final_action in _CONTINUABLE_ACTIONS
            and self._continuation_context_key(
                ticket.candidate,
                self._ticket_effective_context(ticket),
                candidate_proposal=ticket.candidate_proposal,
            )
            == continuation_key
            and ticket.terminal_basis is not None
            and ticket.terminal_basis != self._continuation_basis(ticket, routing_mode=routing_mode)
        )

    @staticmethod
    def _carry_forward_continuation(previous: FunnelTicket, successor: FunnelTicket) -> None:
        successor.stage_results = dict(previous.stage_results)
        successor.trace = list(previous.trace)
        successor.current_level = previous.current_level
        successor.next_level = previous.next_level
        successor.correlation_recorded = previous.correlation_recorded
        successor.final_action = "advance"
        successor.is_terminal = False
        successor.continuation_reason = "budget_basis_changed"

    def _budget_identity(self) -> dict[str, Any]:
        return {
            "limits": {
                key: {
                    "max_usd": str(limit.max_usd),
                    "soft_limit_usd": (
                        None if limit.soft_limit_usd is None else str(limit.soft_limit_usd)
                    ),
                }
                for key, limit in sorted(self._budget_state.limits.items())
            },
            "spent": {key: str(value) for key, value in sorted(self._budget_state.spent.items())},
            "reserved": {
                key: str(value) for key, value in sorted(self._budget_state.reserved.items())
            },
        }

    def _continuation_basis(
        self,
        ticket: FunnelTicket,
        *,
        routing_mode: DegradationMode | None = None,
    ) -> str:
        return _stable_payload_hash(
            {
                "budget": self._budget_identity(),
                "cache_key": ticket.cache_key,
                "next_level": ticket.next_level,
                "routing_mode": routing_mode or ticket.degradation_mode,
            }
        )

    def _maybe_schedule_transition(
        self,
        ticket: FunnelTicket,
        *,
        execution_target: int,
        policy: AdvancePolicy | None,
        trace_step: FunnelTraceStep | None,
    ) -> Literal["advance", "defer", "reject", "retry_cheaper"] | None:
        if (
            policy == "burn_in"
            or ticket.degradation_mode != "normal"
            or ticket.current_level not in (2, 3)
            or ticket.next_level is None
            or ticket.next_level > execution_target
            or ticket.last_result is None
            or ticket.last_result.cheap_signal is None
            or (
                ticket.last_scheduling_decision is not None
                and ticket.last_scheduling_decision.next_level == ticket.next_level
            )
        ):
            return None

        self._maybe_update_voi_calibration_state()
        scheduling = self._voi_scheduler.prioritize(
            [ticket],
            self._budget_state,
            self._frontier,
        )
        if not scheduling:
            return None
        decision = scheduling[0]
        ticket.last_scheduling_decision = decision
        decision_trace = trace_step
        if decision_trace is None and ticket.trace:
            decision_trace = ticket.trace[-1]
        if decision_trace is not None:
            decision_trace.voi_action = decision.recommended_action
            decision_trace.voi_priority = decision.priority
        if decision.recommended_action != "advance":
            ticket.final_action = decision.recommended_action
            ticket.is_terminal = True
        return decision.recommended_action

    def _resolve_ticket(self, ticket: FunnelTicket | str) -> FunnelTicket:
        if isinstance(ticket, FunnelTicket):
            return ticket
        return self._tickets[ticket]

    def _resolve_target_level(
        self,
        target_level: int | None,
        policy: AdvancePolicy | None,
    ) -> int:
        if target_level is not None:
            return min(int(target_level), self._resolved_max_level())
        if policy == "stage_a":
            return self._stage_a_execution_target()
        if policy == "burn_in":
            return min(4, self._resolved_max_level())
        return self._resolved_max_level()

    def _resolved_max_level(self) -> int:
        if not self._stage_levels:
            return 0
        last_stage_level = self._stage_levels[-1]
        if self._max_level is None:
            return last_stage_level
        return min(self._max_level, last_stage_level)

    def _stage_a_execution_target(self) -> int:
        return min(self._stage_a_max_level, self._resolved_max_level())

    def _first_level(self) -> int | None:
        if not self._stage_levels:
            return None
        first_level = self._stage_levels[0]
        if first_level > self._resolved_max_level():
            return None
        return first_level

    def _resolve_next_level(self, ticket: FunnelTicket) -> int | None:
        if ticket.next_level is not None and ticket.next_level not in ticket.stage_results:
            return ticket.next_level
        if ticket.current_level is None:
            return self._first_level()
        return self._level_after(ticket.current_level)

    def _level_after(self, level: int) -> int | None:
        for candidate_level in self._stage_levels:
            if candidate_level > level and candidate_level <= self._resolved_max_level():
                return candidate_level
        return None

    @staticmethod
    def _result_for_level(
        outcome: FunnelOutcome,
        target_level: int,
    ) -> FunnelStageResult | None:
        """Select the same eligible stage from the admitted current projection."""
        eligible_levels = [level for level in outcome.stage_results if level <= target_level]
        if not eligible_levels:
            return None
        return outcome.stage_results[max(eligible_levels)]

    def _build_stage_context(
        self,
        ticket: FunnelTicket,
    ) -> dict[str, Any]:
        context = dict(ticket.context)
        method_metric_basis = getattr(ticket, "_method_metric_projection_basis", None)
        if method_metric_basis is not None:
            context["_funnel_method_metric_projection_basis"] = method_metric_basis
        transfer_context = resolve_transfer_context(
            candidate=ticket.candidate,
            context=context,
            fallback_run_id=str(
                context.get("source_run_id") or context.get("run_id") or ticket.ticket_id
            ),
        )
        context["_funnel_ticket_id"] = ticket.ticket_id
        input_transfer_context = ticket.context.get("transfer_context")
        input_transfer_run_id = (
            input_transfer_context.get("run_id")
            if isinstance(input_transfer_context, Mapping)
            else getattr(input_transfer_context, "run_id", None)
        )
        source_run_id = (
            ticket.context.get("source_run_id")
            or ticket.context.get("run_id")
            or input_transfer_run_id
        )
        context["policy_runtime_work_identity"] = {
            "run_id": str(source_run_id) if source_run_id else None,
            "ticket_id": ticket.ticket_id,
            "candidate_hash": ticket.candidate_hash,
            "candidate_ref": context.get("policy_candidate_ref"),
        }
        context["transfer_context"] = transfer_context
        context["funnel_degradation_mode"] = ticket.degradation_mode
        for level, result in ticket.stage_results.items():
            context[f"_funnel_L{level}_result"] = result
        if self._lesson_registry is not None:
            context["lesson_registry"] = self._lesson_registry
        if self._correlation_tracker is not None:
            context["correlation_metrics"] = self._correlation_tracker.compute_metrics()
        return context

    def _admit_executed_work_packet(
        self,
        ticket: FunnelTicket,
        result: FunnelStageResult,
        stage_level: int,
    ) -> _VOIWorkPacketClaim | None:
        """Fresh-read and bind a native work packet before projecting its reference."""
        from polisyos.core.artifacts import (
            artifact_manifest_profile_sha256,
            input_ref_from_artifact_ref,
            load_core_json_artifact,
        )

        ref = result.executed_work_packet_ref
        if ref is None:
            if result.executed_work_packet_status == "available":
                self._reject_work_packet(result, "work_packet_reference_missing")
            return None
        if result.executed_work_packet_status != "available":
            self._reject_work_packet(result, "work_packet_status_not_available")
            return None
        store = ticket.context.get("store")
        if store is None or not all(hasattr(store, name) for name in ("get_bytes", "get_manifest")):
            self._reject_work_packet(result, "artifact_store_unavailable")
            return None

        transfer_context = ticket.context.get("transfer_context")
        transfer_run_id = (
            transfer_context.get("run_id")
            if isinstance(transfer_context, Mapping)
            else getattr(transfer_context, "run_id", None)
        )
        expected_run_id = (
            ticket.context.get("source_run_id") or ticket.context.get("run_id") or transfer_run_id
        )
        expected_candidate_ref = ticket.context.get("policy_candidate_ref")
        expected_candidate = ticket.context.get("policy_candidate_schema")
        try:
            packet_manifest = store.get_manifest(ref)
            if (
                ref.manifest_profile_sha256 is None
                or artifact_manifest_profile_sha256(packet_manifest) != ref.manifest_profile_sha256
            ):
                self._reject_work_packet(
                    result, "work_packet_selected_profile_missing_or_mismatched"
                )
                return None
            packet = FunnelExecutedWorkPacket.model_validate(load_core_json_artifact(store, ref))
            result_manifest = store.get_manifest(packet.source_result_ref)
            actual_candidate_bytes = store.get_bytes(packet.candidate_ref)
            candidate_payload = load_core_json_artifact(
                store, packet.candidate_ref, raw_payload_bytes=actual_candidate_bytes
            )
            expected_candidate_bytes = (
                to_canonical_bytes(expected_candidate, CanonSpec(forbid_floats=False))
                if expected_candidate is not None
                else None
            )
            source_result_payload = load_core_json_artifact(store, packet.source_result_ref)
            source_candidate_id = (
                candidate_payload.get("candidate_id")
                if isinstance(candidate_payload, Mapping)
                else None
            )
            if not isinstance(source_candidate_id, str) or not (
                _policy_evaluation_vector_source_chain_matches_store(
                    store,
                    packet.source_result_ref,
                    packet.candidate_ref,
                    source_candidate_id,
                )
            ):
                self._reject_work_packet(result, "work_packet_binding_mismatch")
                return None
            source_metadata = source_result_payload.get("metadata")
            source_measurement_payload = (
                source_metadata.get("policy_runtime_source_measurement")
                if isinstance(source_metadata, Mapping)
                else None
            )
            expected_source_measurement_payload = ticket.context.get(
                "policy_runtime_source_measurement"
            )
            source_measurement_matches = source_measurement_payload is None
            expected_result_inputs = [
                input_ref_from_artifact_ref(packet.candidate_ref, role="candidate")
            ]
            if source_measurement_payload is not None:
                source_measurement = SourceMetricObservation.model_validate(
                    source_measurement_payload
                )
                recomputed_source_measurement = recompute_source_government_balance(
                    store, source_measurement
                )
                expected_source_measurement = (
                    None
                    if expected_source_measurement_payload is None
                    else SourceMetricObservation.model_validate(expected_source_measurement_payload)
                )
                source_measurement_dump = source_measurement.model_dump(
                    mode="json", exclude_none=False
                )
                recomputed_source_measurement_dump = recomputed_source_measurement.model_dump(
                    mode="json", exclude_none=False
                )
                source_measurement_matches = (
                    expected_source_measurement is not None
                    and source_measurement_dump
                    == expected_source_measurement.model_dump(mode="json", exclude_none=False)
                    and source_measurement_dump == recomputed_source_measurement_dump
                )
                expected_result_inputs.extend(
                    input_ref_from_artifact_ref(source_ref, role=role)
                    for role, source_ref in source_observation_input_refs(source_measurement)
                )
            elif expected_source_measurement_payload is not None:
                source_measurement_matches = False
            expected_packet_inputs = sorted(
                (
                    item.role,
                    str(item.artifact_id),
                    item.manifest_profile_sha256 is None,
                    item.manifest_profile_sha256 or "",
                )
                for item in (
                    input_ref_from_artifact_ref(packet.candidate_ref, role="candidate"),
                    input_ref_from_artifact_ref(packet.source_result_ref, role="source_result"),
                )
            )
            packet_inputs = sorted(
                (
                    item.role,
                    str(item.artifact_id),
                    item.manifest_profile_sha256 is None,
                    item.manifest_profile_sha256 or "",
                )
                for item in packet_manifest.inputs
            )
            result_candidate_inputs = [
                item for item in result_manifest.inputs if item.role == "candidate"
            ]
            bootstrap = result.simulation_results.get("bootstrap", {})
            requested_draw_count = (
                bootstrap.get("requested_draw_count") if isinstance(bootstrap, Mapping) else None
            )
            if isinstance(requested_draw_count, bool) or not isinstance(requested_draw_count, int):
                requested_draw_count = None
            runtime_binding_matches = packet.schema_version == "1.1"
            if packet.schema_version == "1.1":
                source_metadata = source_result_payload.get("metadata")
                invocation = (
                    source_metadata.get("policy_runtime_invocation")
                    if isinstance(source_metadata, Mapping)
                    else None
                )
                fiscal_measurement = (
                    source_metadata.get("policy_runtime_fiscal_measurement")
                    if isinstance(source_metadata, Mapping)
                    else None
                )
                fiscal_aliases = (
                    "gov_balance",
                    "government_balance",
                    "budget_deficit",
                    "deficit",
                )
                expected_fiscal_measurement = {
                    "usable": result.simulation_results.get("budget_deficit_objective_usable"),
                    "normalized_value": result.simulation_results.get(
                        "budget_deficit_objective_value"
                    ),
                    "source_values": {
                        alias: result.simulation_results[alias]
                        for alias in fiscal_aliases
                        if alias in result.simulation_results
                    },
                }
                runtime_binding_matches = (
                    isinstance(bootstrap, Mapping)
                    and isinstance(invocation, Mapping)
                    and _policy_runtime_invocation_bindings_status(invocation, bootstrap)
                    is ObjectiveScoreStatus.AVAILABLE
                    and _policy_runtime_invocation_bindings_status(
                        invocation,
                        {name: getattr(packet, name) for name in _POLICY_RUNTIME_INVOCATION_FIELDS},
                    )
                    is ObjectiveScoreStatus.AVAILABLE
                    and isinstance(fiscal_measurement, Mapping)
                    and dict(fiscal_measurement) == expected_fiscal_measurement
                    and source_measurement_matches
                )
            expected_result_inputs = sorted(
                (
                    item.role,
                    str(item.artifact_id),
                    item.manifest_profile_sha256 is None,
                    item.manifest_profile_sha256 or "",
                )
                for item in expected_result_inputs
            )
            actual_result_inputs = sorted(
                (
                    item.role,
                    str(item.artifact_id),
                    item.manifest_profile_sha256 is None,
                    item.manifest_profile_sha256 or "",
                )
                for item in result_manifest.inputs
            )
            if (
                ref.kind != "scientist.search.funnel_native_work_packet"
                or packet_manifest.kind != "scientist.search.funnel_native_work_packet"
                or packet_manifest.artifact_schema is None
                or packet_manifest.artifact_schema.name
                != "polisyos.scientist.search.FunnelExecutedWorkPacket"
                or packet_manifest.artifact_schema.version != packet.schema_version
                or len(packet_manifest.inputs) != 2
                or packet.run_id != str(expected_run_id or "")
                or packet.ticket_id != ticket.ticket_id
                or packet.candidate_hash != ticket.candidate_hash
                or packet.stage_level != stage_level
                or packet.stage_name != result.stage_name
                or packet.fidelity != result.feedback.get("policy_runtime_fidelity")
                or packet.candidate_ref != expected_candidate_ref
                or expected_candidate_bytes is None
                or actual_candidate_bytes != expected_candidate_bytes
                or packet.source_result_ref.kind != "scientist.policy_evaluation_vector"
                or result_manifest.kind != "scientist.policy_evaluation_vector"
                or not isinstance(candidate_payload, Mapping)
                or not isinstance(source_result_payload, Mapping)
                or candidate_payload.get("candidate_id")
                != source_result_payload.get("candidate_id")
                or packet_inputs != expected_packet_inputs
                or actual_result_inputs != expected_result_inputs
                or result_candidate_inputs
                != [input_ref_from_artifact_ref(packet.candidate_ref, role="candidate")]
                or packet.requested_draw_count != requested_draw_count
                or not runtime_binding_matches
                or packet.input_signature
                != (
                    str(ticket.context.get("pinned_input_signature"))
                    if ticket.context.get("pinned_input_signature")
                    else None
                )
                or packet.backend_kind != result.feedback.get("policy_runtime_backend_kind")
            ):
                self._reject_work_packet(result, "work_packet_binding_mismatch")
                return None
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            self._reject_work_packet(result, "work_packet_unreadable_or_invalid")
            return None
        # Schema 1.0 predates the invocation tuple needed for a source-bound
        # observation. Keep its existing packet admission behavior, but do not
        # promote it into the stronger VOI work-packet qualification.
        if packet.schema_version != "1.1":
            return None
        return _VOIWorkPacketClaim(
            packet_ref=ref,
            packet_schema_version=packet.schema_version,
            run_id=packet.run_id,
            ticket_id=packet.ticket_id,
            candidate_hash=packet.candidate_hash,
            candidate_ref=packet.candidate_ref,
            source_result_ref=packet.source_result_ref,
            stage_level=packet.stage_level,
            stage_name=packet.stage_name,
            fidelity=packet.fidelity,
            evaluation_attempt_id=packet.evaluation_attempt_id,
        )

    def _reconcile_reused_work_result(
        self,
        ticket: FunnelTicket,
        source_result: FunnelStageResult,
        stage_level: int,
    ) -> FunnelStageResult:
        """Resolve retained work from current selected CAS without issuing new work.

        A retained packet belongs to its actual execution ticket and run. The
        current request only reuses that result; a copied feedback string or a
        fresh organizational ID cannot establish physical execution provenance.
        """
        from polisyos.core.artifacts import load_core_json_artifact

        result = deepcopy(source_result)
        reuse: dict[str, Any] = {
            "request_ticket_id": ticket.ticket_id,
            "result_source_ticket_id": ticket.result_reuse_source_ticket_id,
            "new_physical_work": False,
            "executed_work_status": "unavailable",
        }
        ref = result.executed_work_packet_ref
        try:
            if ref is None:
                # Use the same missing-reference rule as first execution. A
                # copied available marker cannot substitute for selected bytes.
                self._admit_executed_work_packet(ticket, result, stage_level)
                if result.executed_work_packet_status == "rejected":
                    raise ValueError("retained_work_reference_missing")
            elif not isinstance(ref, ArtifactRef):
                raise ValueError("retained_work_reference_invalid")
            else:
                store = ticket.context.get("store")
                packet = FunnelExecutedWorkPacket.model_validate(
                    load_core_json_artifact(store, ref)
                )
                execution_ticket = self._tickets.get(packet.ticket_id)
                if (
                    execution_ticket is None
                    or packet.ticket_id not in ticket.lineage[:-1]
                    or execution_ticket.candidate_hash != ticket.candidate_hash
                ):
                    raise ValueError("retained_work_execution_ticket_not_in_lineage")
                # Use the current store/access wrapper while retaining the
                # original executed invocation's run, ticket and input basis.
                current_source = replace(
                    execution_ticket,
                    context={**execution_ticket.context, "store": store},
                )
                self._admit_executed_work_packet(current_source, result, stage_level)
                if result.executed_work_packet_status != "available":
                    raise ValueError("retained_work_source_not_reconciled")
                reuse.update(
                    executed_work_status="available",
                    executed_work_packet_ref=ref.model_dump(mode="json"),
                    execution_ticket_id=packet.ticket_id,
                    execution_run_id=packet.run_id,
                    evaluation_attempt_id=packet.evaluation_attempt_id,
                    source_result_ref=packet.source_result_ref.model_dump(mode="json"),
                )
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
            self._reject_work_packet(result, "retained_work_source_not_reconciled")
            if not isinstance(ref, ArtifactRef):
                result.executed_work_packet_ref = None
            assessment = _unestablished_score_assessment("retained_work_source_not_reconciled")
            result = replace(
                result,
                objective_value=None,
                is_promising=False,
                score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
                score_assessment=assessment,
                score_admission=None,
                terminal_action="defer",
            )
            reuse["executed_work_status"] = "rejected"
        else:
            result = _reconcile_funnel_score(
                result,
                owner_context=getattr(ticket, "_method_metric_projection_basis", None),
            )
        result.feedback = dict(result.feedback)
        result.feedback["funnel_result_reuse"] = reuse
        result.feedback["policy_runtime_work_packet_status"] = result.executed_work_packet_status
        if isinstance(ref, ArtifactRef):
            result.feedback["policy_runtime_work_packet_ref"] = ref.model_dump(mode="json")
        else:
            result.feedback.pop("policy_runtime_work_packet_ref", None)
        return result

    @staticmethod
    def _reject_work_packet(result: FunnelStageResult, reason: str) -> None:
        result.executed_work_packet_status = "rejected"
        result.feedback = dict(result.feedback)
        result.feedback["policy_runtime_work_packet_status"] = "rejected"
        result.feedback["policy_runtime_work_packet_rejection_reason"] = reason

    def _routing_mode(self, context: Mapping[str, Any] | None = None) -> DegradationMode:
        if self._correlation_tracker is None:
            # A persisted calibration projection can be authoritative even
            # when no mutable tracker snapshot is available for this run.
            candidate_mode = context.get("funnel_degradation_mode") if context else None
            if _is_degradation_mode(candidate_mode):
                return candidate_mode
            candidate_metrics = context.get("correlation_metrics") if context else None
            if isinstance(candidate_metrics, Mapping):
                if bool(candidate_metrics.get("promotion_ban_active")):
                    return "no_promotion"
                candidate_mode = candidate_metrics.get("routing_mode")
                if _is_degradation_mode(candidate_mode):
                    return candidate_mode
            return "normal"
        if hasattr(self._correlation_tracker, "routing_mode"):
            mode = self._correlation_tracker.routing_mode()
            if _is_degradation_mode(mode):
                return mode
        metrics = self._correlation_tracker.compute_metrics()
        mode = metrics.get("routing_mode", "normal")
        if _is_degradation_mode(mode):
            return mode
        return "normal"

    def _fast_track_level(self, current_level: int, execution_target: int) -> int | None:
        for candidate_level in self._stage_levels:
            if candidate_level >= 4 and candidate_level <= execution_target:
                return candidate_level
        fallback_levels = [
            candidate_level
            for candidate_level in self._stage_levels
            if current_level < candidate_level <= execution_target
        ]
        if not fallback_levels:
            return None
        return fallback_levels[-1]

    def _mark_terminal(self, ticket: FunnelTicket) -> None:
        ticket.is_terminal = True
        if not ticket.stage_results:
            # The control flow completed, but no requested evaluation ran.  A
            # configuration/level cap is not a scientific approval or a zero
            # objective; leave an explicit path for a later continuation.
            ticket.final_action = "defer"
            return
        if (
            ticket.degradation_mode in {"no_promotion", "reduced_judge", "auto_cap"}
            and (ticket.current_level or 0) >= 5
        ):
            ticket.final_action = "defer_to_human"
            return
        if ticket.degradation_mode == "freeze_frontier":
            ticket.final_action = "defer"
            return
        ticket.final_action = "complete"

    @staticmethod
    def _empty_result(candidate: dict[str, Any]) -> FunnelStageResult:
        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=None,
            is_promising=False,
            score_status=ObjectiveScoreStatus.UNAVAILABLE,
            stage_name="funnel_empty",
            feedback={
                "verdict": "NOT_EVALUATED",
                "funnel_evaluation_status": "not_evaluated",
                "reason": "no stage executed",
            },
            uncertainty_envelope=UncertaintyEnvelope.unknown(),
            fidelity_level=0,
            terminal_action="defer",
        )

    @staticmethod
    def _evaluation_status(ticket: FunnelTicket) -> FunnelEvaluationStatus:
        if not ticket.stage_results:
            return "not_evaluated"
        if not ticket.is_terminal:
            return "partial"
        if ticket.final_action in _CONTINUABLE_ACTIONS or ticket.final_action == "defer_to_human":
            return "partial"
        return "evaluated"

    @staticmethod
    def _compatibility_result(
        outcome: FunnelOutcome,
        stage_result: FunnelStageResult,
    ) -> FunnelStageResult:
        """Project stage evidence into the aggregate compatibility decision."""

        score_admission: ObjectiveScoreAdmission | None = None
        selected_admission: ObjectiveScoreStatus | None = None
        if outcome.evaluation_status == "not_evaluated":
            compatibility_verdict = "NOT_EVALUATED"
            compatibility_promising = False
        elif outcome.evaluation_status != "evaluated":
            compatibility_verdict = "DEFER"
            compatibility_promising = False
        elif outcome.final_action == "reject":
            compatibility_verdict = "REJECT"
            compatibility_promising = False
        elif outcome.final_action in {"complete", "advance"}:
            score_admission = _funnel_score_admission(stage_result)
            selected_admission = score_admission.status
            if (
                stage_result.is_promising
                and selected_admission is ObjectiveScoreStatus.AVAILABLE
                and stage_result.objective_value is not None
            ):
                compatibility_verdict = "APPROVE"
                compatibility_promising = True
            else:
                compatibility_verdict = "DEFER"
                compatibility_promising = False
        else:
            compatibility_verdict = "DEFER"
            compatibility_promising = False

        feedback = dict(stage_result.feedback)
        if selected_admission is not None and compatibility_verdict == "DEFER":
            feedback["selected_objective_admission"] = selected_admission.value
        feedback["stage_verdict"] = feedback.get("verdict")
        feedback["verdict"] = compatibility_verdict
        feedback["funnel_action"] = outcome.final_action
        feedback["funnel_evaluation_status"] = outcome.evaluation_status
        compatibility_score_status = stage_result.score_status
        compatibility_score_assessment = stage_result.score_assessment
        compatibility_score_admission = stage_result.score_admission
        compatibility_objective_value = stage_result.objective_value
        if selected_admission is not None and score_admission is not None:
            compatibility_score_status = selected_admission
            compatibility_score_assessment = score_admission.reported_assessment
            compatibility_score_admission = score_admission
            if selected_admission is ObjectiveScoreStatus.AVAILABLE:
                compatibility_objective_value = (
                    None
                    if score_admission.recomputed_assessment is None
                    else score_admission.recomputed_assessment.value
                )
            else:
                compatibility_objective_value = None

        return FunnelStageResult(
            policy_candidate=stage_result.policy_candidate,
            objective_value=compatibility_objective_value,
            is_promising=compatibility_promising,
            score_status=compatibility_score_status,
            score_assessment=compatibility_score_assessment,
            score_admission=compatibility_score_admission,
            stage_name=stage_result.stage_name,
            duration_seconds=stage_result.duration_seconds,
            timestamp=stage_result.timestamp,
            simulation_results=stage_result.simulation_results,
            feedback=feedback,
            predicted_score=stage_result.predicted_score,
            actual_score=stage_result.actual_score,
            uncertainty_envelope=stage_result.uncertainty_envelope,
            cheap_signal=stage_result.cheap_signal,
            failure_cards=list(stage_result.failure_cards),
            compute_cost_usd=stage_result.compute_cost_usd,
            compute_cost_origin=stage_result.compute_cost_origin,
            executed_work_packet_ref=stage_result.executed_work_packet_ref,
            executed_work_packet_status=stage_result.executed_work_packet_status,
            fidelity_level=stage_result.fidelity_level,
            audit_refs=list(stage_result.audit_refs),
            actionable_side_information_ref=stage_result.actionable_side_information_ref,
            terminal_action=stage_result.terminal_action,
        )

    @staticmethod
    def _decimal_from_float(value: float) -> Decimal:
        return Decimal(str(value))

    def _maybe_record_correlation(self, ticket: FunnelTicket) -> None:
        if (
            self._correlation_tracker is None
            or ticket.correlation_recorded
            or not hasattr(self._correlation_tracker, "record")
        ):
            return
        stage_results = ticket.stage_results
        gate_result = stage_results.get(2)
        if gate_result is None:
            lower_levels = [level for level in stage_results if level < 4]
            if lower_levels:
                gate_result = stage_results[max(lower_levels)]
        truth_result = stage_results.get(4)
        if truth_result is None:
            truth_levels = [level for level in stage_results if level >= 4]
            if truth_levels:
                truth_result = stage_results[max(truth_levels)]
        if (
            gate_result is None
            or truth_result is None
            or gate_result.score_status is not ObjectiveScoreStatus.AVAILABLE
            or truth_result.score_status is not ObjectiveScoreStatus.AVAILABLE
            or gate_result.objective_value is None
            or truth_result.objective_value is None
        ):
            return
        self._correlation_tracker.record(
            gate_result,
            truth_result,
            ticket.candidate_hash,
            is_sentinel=bool(ticket.context.get("is_sentinel")),
            metadata={
                "sentinel_id": ticket.context.get("sentinel_id"),
                "ticket_id": ticket.ticket_id,
            },
        )
        ticket.correlation_recorded = True
        self._maybe_update_voi_calibration_state()

    def _maybe_record_voi_observation(
        self,
        ticket: FunnelTicket,
        result: FunnelStageResult,
        stage_level: int,
        *,
        work_packet_claim: _VOIWorkPacketClaim | None = None,
    ) -> None:
        if (
            result.score_status is not ObjectiveScoreStatus.AVAILABLE
            or result.objective_value is None
            or result.score_assessment is None
            or _funnel_score_admission(result).status is not ObjectiveScoreStatus.AVAILABLE
            or not isinstance(self._voi_scheduler, _VOIStageResultObserver)
        ):
            return
        transfer_context = resolve_transfer_context(
            candidate=ticket.candidate,
            context=ticket.context,
            fallback_run_id=str(
                ticket.context.get("source_run_id")
                or ticket.context.get("run_id")
                or ticket.ticket_id
            ),
        )
        timeout_occurred = bool(
            result.feedback.get("timed_out")
            or result.feedback.get("timeout")
            or result.feedback.get("timeout_occurred")
        )
        disagreement = None
        if result.cheap_signal is not None:
            disagreement = abs(
                float(result.cheap_signal.expected_value_proxy) - float(result.objective_value)
            )
        run_id = (
            ticket.context.get("source_run_id")
            or ticket.context.get("run_id")
            or transfer_context.run_id
        )
        observation_args: dict[str, Any] = {
            "candidate_id": ticket.candidate_hash,
            "task_family": transfer_context.task_family,
            "domain": transfer_context.domain,
            "tenant_hash": str(transfer_context.tenant_hash or ""),
            "stage_level": stage_level,
            "frontier_position": self._frontier.position_for(ticket.candidate_hash),
            "cheap_signal": result.cheap_signal,
            "actual_objective_value": result.objective_value,
            "score_assessment": result.score_assessment,
            "objective_source": result.simulation_results,
            "actual_promising": result.is_promising,
            "duration_seconds": result.duration_seconds,
            "compute_cost_usd": result.compute_cost_usd,
            "compute_cost_origin": result.compute_cost_origin,
            "timeout_occurred": timeout_occurred,
            "disagreement": disagreement,
            "metadata": {
                "ticket_id": ticket.ticket_id,
                "stage_name": result.stage_name,
                "fidelity_level": result.fidelity_level,
                "executed_work_packet_status": result.executed_work_packet_status,
                "executed_work_packet_ref": (
                    None
                    if result.executed_work_packet_ref is None
                    else result.executed_work_packet_ref.model_dump(mode="json")
                ),
            },
        }
        if isinstance(self._voi_scheduler, PredictiveVOIScheduler):
            observation_args.update(
                run_id=None if run_id is None else str(run_id),
                ticket_id=ticket.ticket_id,
                work_packet_claim=work_packet_claim,
            )
            self._voi_scheduler.observe_stage_result(**observation_args)
            return
        self._voi_scheduler.observe_stage_result(**observation_args)

    def _maybe_update_voi_calibration_state(self) -> None:
        if self._correlation_tracker is None or not isinstance(
            self._voi_scheduler, _VOICalibrationStateUpdater
        ):
            return
        self._voi_scheduler.update_calibration_state(self._correlation_tracker.compute_metrics())

    def _maybe_record_lessons(self, ticket: FunnelTicket) -> None:
        if self._lesson_registry is None or not ticket.is_terminal or ticket.lessons_finalized:
            return
        source_run_id = str(
            ticket.context.get("source_run_id") or ticket.context.get("run_id") or ticket.ticket_id
        )
        transfer_context = resolve_transfer_context(
            candidate=ticket.candidate,
            context=ticket.context,
            fallback_run_id=source_run_id,
        )
        source_run_id = transfer_context.run_id
        tags = self._candidate_tags(ticket.candidate)
        if ticket.final_action == "reject":
            for level, result in sorted(ticket.stage_results.items()):
                cards = list(result.failure_cards)
                if not cards and not result.is_promising:
                    cards.append(
                        TypedFailureCard(
                            judge_name=result.stage_name,
                            failure_type="non_promising_candidate",
                            severity="warning",
                            description=(
                                f"Candidate stopped at {result.stage_name} because it was not promising."
                            ),
                            metadata={"objective_value": result.objective_value},
                        )
                    )
                for card in cards:
                    lesson = lesson_from_failure_card(
                        card,
                        candidate_hash=ticket.candidate_hash,
                        stage_name=result.stage_name,
                        fidelity_level=level,
                        source_run_id=source_run_id,
                        tags=tags,
                        trace_refs=[f"{ticket.ticket_id}:L{level}"],
                        transfer_context=transfer_context,
                    )
                    ticket.lesson_refs.append(
                        self._lesson_registry.record_local(
                            lesson,
                            context=transfer_context,
                        )
                    )
        elif (
            ticket.final_action == "complete"
            and 4 in ticket.stage_results
            and ticket.stage_results[4].is_promising
            and (
                _funnel_score_admission(ticket.stage_results[4]).status
                is ObjectiveScoreStatus.AVAILABLE
            )
        ):
            outcome = self.get_outcome(ticket)
            lesson = success_lesson_from_outcome(
                outcome,
                source_run_id=source_run_id,
                tags=tags,
                trace_refs=[step.stage_name for step in ticket.trace],
                transfer_context=transfer_context,
            )
            ticket.lesson_refs.append(
                self._lesson_registry.record_local(
                    lesson,
                    context=transfer_context,
                )
            )
        ticket.lessons_finalized = True

    @staticmethod
    def _candidate_tags(candidate: dict[str, Any]) -> list[str]:
        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])
        objectives = semantic.get("objectives", [])
        tags = [
            *(iv.get("type", iv.get("intervention_type", "")) for iv in interventions),
            *(obj.get("name", obj.get("objective", "")) for obj in objectives),
        ]
        return sorted({tag for tag in tags if tag})


def _dedupe_artifact_refs(refs: Iterable[ArtifactRef]) -> list[ArtifactRef]:
    seen: set[str] = set()
    ordered: list[ArtifactRef] = []
    for ref in refs:
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        ordered.append(ref)
    return ordered
