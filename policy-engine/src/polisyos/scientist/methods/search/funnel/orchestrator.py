"""Stateful multi-fidelity funnel orchestration runtime."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, TypeGuard
from uuid import uuid4

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.scientist.methods.search.contracts import EvaluationBundle
from polisyos.scientist.methods.search.funnel.types import (
    DegradationMode,
    FunnelCostOrigin,
    FunnelEvaluationStatus,
    FunnelExecutedWorkPacket,
    FunnelOutcome,
    FunnelStage,
    FunnelStageResult,
    FunnelTicket,
    FunnelTraceStep,
    TypedFailureCard,
    UncertaintyEnvelope,
)
from polisyos.scientist.methods.search.lessons import (
    LessonRegistry,
    lesson_from_failure_card,
    success_lesson_from_outcome,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAdmission,
    ObjectiveScoreStatus,
    SourceMetricObservation,
    _unestablished_score_assessment,
    recompute_source_government_balance,
    reconcile_objective_score_assessment,
    source_observation_input_refs,
)
from polisyos.scientist.methods.search.sentinels import (
    extract_sentinel_metadata,
    strip_internal_candidate_metadata,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker
from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context
from polisyos.scientist.methods.search.uncertainty import (
    load_search_uncertainty_observation,
    load_source_bound_risk_observation,
    persist_source_bound_risk_observation,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    ParetoSnapshot,
    PredictiveVOIScheduler,
    SimpleVOIScheduler,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState

logger = get_logger(__name__)

AdvancePolicy = Literal["stage_a", "full", "burn_in"]
_CONTINUABLE_ACTIONS = frozenset({"defer", "retry_cheaper"})
_CACHE_VOLATILE_CONTEXT_KEYS = frozenset(
    {
        "attempt",
        "created_at",
        "fetched_at",
        "generated_at",
        "ingested_at",
        "iteration",
        "evaluation_iteration",
        "generation_attempts",
        "request_id",
        "retrieved_at",
        "retry",
        "run_id",
        "session_id",
        "source_run_id",
        "span_id",
        "ticket_id",
        "timestamp",
        "trace_id",
        "updated_at",
    }
)
_CACHE_CONTEXT_IDENTITY_FRAGMENTS = (
    "access",
    "calibration",
    "config",
    "data",
    "dataset",
    "domain",
    "effective",
    "evaluation",
    "mode",
    "model",
    "purpose",
    "replica",
    "replicate",
    "role",
    "schema",
    "scope",
    "seed",
    "settings",
    "signature",
    "task_family",
    "tenant",
    "transfer",
)
_UNSERIALIZABLE_CACHE_VALUE = object()
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

    try:
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except TypeError:
        serialized = repr(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _stable_candidate_hash(candidate: dict[str, Any]) -> str:
    """Return a deterministic subject hash for orchestrator-local accounting."""

    return _stable_payload_hash(strip_internal_candidate_metadata(candidate))


def _is_volatile_cache_key(key: str) -> bool:
    normalized = key.casefold()
    return normalized in _CACHE_VOLATILE_CONTEXT_KEYS or normalized.endswith(
        ("_at", "_ts", "_timestamp")
    )


def _cache_identity_value(value: Any) -> Any:
    """Project stable context identity while excluding runtime handles and timestamps."""

    if isinstance(value, ArtifactRef):
        return artifact_ref_identity_key(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _cache_identity_value(value.value)
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _is_volatile_cache_key(key):
                continue
            item = _cache_identity_value(raw_value)
            if item is not _UNSERIALIZABLE_CACHE_VALUE:
                projected[key] = item
        return projected
    if isinstance(value, (list, tuple)):
        projected_items = []
        for item in value:
            projected = _cache_identity_value(item)
            if projected is _UNSERIALIZABLE_CACHE_VALUE:
                return _UNSERIALIZABLE_CACHE_VALUE
            projected_items.append(projected)
        return projected_items
    if isinstance(value, (set, frozenset)):
        projected_items = []
        for item in value:
            projected = _cache_identity_value(item)
            if projected is _UNSERIALIZABLE_CACHE_VALUE:
                return _UNSERIALIZABLE_CACHE_VALUE
            projected_items.append(projected)
        return sorted(projected_items, key=lambda item: repr(item))

    artifact_id = getattr(value, "artifact_id", None)
    if artifact_id is not None:
        return str(artifact_id)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _cache_identity_value(model_dump(mode="json"))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return _UNSERIALIZABLE_CACHE_VALUE
    return _UNSERIALIZABLE_CACHE_VALUE


def _stable_context_identity(context: Mapping[str, Any]) -> dict[str, Any]:
    identity: dict[str, Any] = {}
    for raw_key, raw_value in context.items():
        key = str(raw_key)
        normalized = key.casefold()
        if _is_volatile_cache_key(key):
            continue
        is_identity_key = any(
            fragment in normalized for fragment in _CACHE_CONTEXT_IDENTITY_FRAGMENTS
        ) or normalized.endswith(("_ref", "_refs", "_version", "_versions"))
        if not is_identity_key and not isinstance(
            raw_value,
            (str, int, float, bool, type(None)),
        ):
            continue
        projected = _cache_identity_value(raw_value)
        if projected is not _UNSERIALIZABLE_CACHE_VALUE:
            identity[key] = projected
    return identity


def _funnel_score_admission(result: FunnelStageResult) -> ObjectiveScoreAdmission:
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
    )


def _selected_funnel_score_status(result: FunnelStageResult) -> ObjectiveScoreStatus:
    """Return the status from the shared typed score admission result."""
    return _funnel_score_admission(result).status


def _reconcile_funnel_score(result: FunnelStageResult) -> FunnelStageResult:
    """Retain both the score basis and its source-recomputed admission state."""
    admission = _funnel_score_admission(result)
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

    feedback = dict(result.feedback)
    if result.objective_value is not None:
        feedback.setdefault("unbound_objective_diagnostic", result.objective_value)
    return replace(
        result,
        objective_value=None,
        is_promising=False,
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
    """Require one source-recomputed AVAILABLE score before any terminal complete."""
    if ticket.final_action != "complete" or not ticket.is_terminal:
        return
    result = ticket.last_result
    if result is None:
        ticket.final_action = "defer"
        return
    reconciled = _reconcile_funnel_score(result)
    result_level = max(ticket.stage_results)
    ticket.stage_results[result_level] = reconciled
    for step in reversed(ticket.trace):
        if step.fidelity_level == result_level and step.stage_name == result.stage_name:
            step.objective_value = reconciled.objective_value
            step.is_promising = reconciled.is_promising
            step.score_status = reconciled.score_status
            step.score_assessment = reconciled.score_assessment
            step.score_admission = reconciled.score_admission
            break
    admission = _funnel_score_admission(reconciled)
    if admission.status is ObjectiveScoreStatus.AVAILABLE:
        return
    ticket.final_action = "reject" if admission.status is ObjectiveScoreStatus.INVALID else "defer"


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
    ) -> FunnelTicket:
        """Submit a candidate to the orchestrator and return a reusable ticket."""

        candidate_hash = _stable_candidate_hash(candidate)
        sentinel_meta = extract_sentinel_metadata(candidate) or {}
        ticket_context = dict(context)
        if sentinel_meta:
            ticket_context.update(sentinel_meta)
            ticket_context["is_sentinel"] = True
        continuation_key = self._continuation_context_key(candidate, ticket_context)
        routing_mode = self._routing_mode(ticket_context)
        cache_key = self._ticket_cache_key(
            candidate,
            context,
            sentinel_meta=sentinel_meta,
            routing_mode=routing_mode,
        )
        cached_ticket = self._cached_ticket_for_key(cache_key, routing_mode=routing_mode)
        if cached_ticket is not None:
            ticket = cached_ticket
            ticket.submitted_via_cache = True
            for key, value in context.items():
                ticket.context.setdefault(key, value)
            for key, value in sentinel_meta.items():
                ticket.context.setdefault(key, value)
            if sentinel_meta:
                ticket.context["is_sentinel"] = True
            return ticket

        previous_ticket = self._latest_ticket(candidate_hash, continuation_key=continuation_key)
        ticket_id = str(uuid4())
        ticket = FunnelTicket(
            ticket_id=ticket_id,
            candidate_hash=candidate_hash,
            candidate=dict(candidate),
            context=ticket_context,
            next_level=self._first_level(),
            cache_key=cache_key,
            lineage=(ticket_id,),
        )
        if previous_ticket is not None:
            ticket.parent_ticket_id = previous_ticket.ticket_id
            ticket.lineage = (*previous_ticket.lineage, ticket_id)
            if self._can_reuse_continuation(
                previous_ticket,
                continuation_key,
                routing_mode=routing_mode,
            ):
                self._carry_forward_continuation(previous_ticket, ticket)
            elif (
                previous_ticket.is_terminal and previous_ticket.final_action in _CONTINUABLE_ACTIONS
            ):
                ticket.continuation_reason = "effective_context_changed"
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
        self._latest_ticket_by_candidate[candidate_hash] = ticket.ticket_id
        self._latest_ticket_by_context[continuation_key] = ticket.ticket_id
        self._ticket_cache[cache_key] = ticket.ticket_id
        return ticket

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
            result = _reconcile_funnel_score(
                stage.evaluate(
                    resolved_ticket.candidate,
                    self._build_stage_context(resolved_ticket),
                )
            )
            self._admit_executed_work_packet(resolved_ticket, result, next_level)
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
            self._maybe_record_voi_observation(resolved_ticket, result, next_level)

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
        _finalize_terminal_completion(resolved_ticket)
        ordered_results = [
            resolved_ticket.stage_results[level] for level in sorted(resolved_ticket.stage_results)
        ]
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

        outcome_stage_results = dict(resolved_ticket.stage_results)
        admitted_envelopes: list[UncertaintyEnvelope] = []
        observation_refs: list[ArtifactRef] = []
        intake_failures: list[str] = []
        store = resolved_ticket.context.get("store")
        basis_ref = resolved_ticket.context.get("uncertainty_basis_ref")
        subject_ref = resolved_ticket.context.get("policy_candidate_ref")
        for result in ordered_results:
            ref = result.uncertainty_observation_ref
            if (
                ref is None
                or store is None
                or not isinstance(basis_ref, ArtifactRef)
                or not isinstance(subject_ref, ArtifactRef)
            ):
                intake_failures.append(f"{result.stage_name}:producer_observation_missing")
                continue
            try:
                observation = load_search_uncertainty_observation(
                    store, ref, basis_ref, result.uncertainty_envelope, subject_ref
                )
            except (
                AttributeError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                intake_failures.append(f"{result.stage_name}:{exc}")
                continue
            admitted_envelopes.append(observation.envelope)
            observation_refs.append(ref)
        current_uncertainty = (
            UncertaintyEnvelope.merge_max(admitted_envelopes)
            if admitted_envelopes and not intake_failures
            else None
        )
        final_result = resolved_ticket.last_result
        if final_result is not None:
            feedback = dict(final_result.feedback or {})
            feedback["uncertainty_current"] = (
                None if current_uncertainty is None else current_uncertainty.model_dump(mode="json")
            )
            feedback["uncertainty_current_status"] = (
                "not_established" if current_uncertainty is None else "basis_bound_routing_only"
            )
            feedback["uncertainty_refinement_status"] = "producer_law_not_established"
            feedback["uncertainty_historical_max"] = uncertainty_envelope.model_dump(mode="json")
            final_result = replace(final_result, feedback=feedback)
            for level, result in outcome_stage_results.items():
                if result is resolved_ticket.last_result:
                    outcome_stage_results[level] = final_result
                    break

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
        return FunnelOutcome(
            ticket_id=resolved_ticket.ticket_id,
            candidate_hash=resolved_ticket.candidate_hash,
            trace=list(resolved_ticket.trace),
            stage_results=outcome_stage_results,
            final_result=final_result,
            failure_cards=failure_cards,
            uncertainty_envelope=uncertainty_envelope,
            compute_cost_usd=aggregate_cost_usd,
            compute_cost_origin=aggregate_cost_origin,
            degradation_mode=resolved_ticket.degradation_mode,
            final_action=resolved_ticket.final_action,
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
            evaluation_status=self._evaluation_status(resolved_ticket),
            current_uncertainty_envelope=current_uncertainty,
            uncertainty_observation_refs=_dedupe_artifact_refs(observation_refs),
            uncertainty_intake_failures=intake_failures,
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
        ) -> EvaluationBundle:
            ticket = self.submit(candidate, context)
            outcome = self.advance(ticket, policy="stage_a")
            result = self._result_for_level(ticket, self._stage_a_execution_target())
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

        return _stage_a

    def as_stage_b_callable(
        self,
    ) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
        """Return a SearchController-compatible Stage B callable."""

        def _stage_b(
            candidate: dict[str, Any],
            context: dict[str, Any],
        ) -> dict[str, Any]:
            sentinel_meta = extract_sentinel_metadata(candidate) or {}
            routing_mode = self._routing_mode(context)
            cache_key = self._ticket_cache_key(
                candidate,
                context,
                sentinel_meta=sentinel_meta,
                routing_mode=routing_mode,
            )
            cache_hit = (
                self._cached_ticket_for_key(
                    cache_key,
                    routing_mode=routing_mode,
                )
                is not None
            )
            ticket = self.submit(candidate, context)
            outcome = self.advance(ticket, policy="full")
            stage_result = outcome.final_result or self._empty_result(candidate)
            result = self._compatibility_result(outcome, stage_result)
            feedback = dict(result.feedback)
            feedback["funnel_action"] = outcome.final_action
            feedback["funnel_degradation_mode"] = outcome.degradation_mode
            feedback["funnel_cache"] = "hit" if cache_hit else "miss"
            return {
                "simulation_results": result.simulation_results,
                "feedback": feedback,
                "objective_value": result.objective_value,
                "is_promising": result.is_promising,
                "_funnel_result": stage_result,
                "_funnel_outcome": outcome,
            }

        return _stage_b

    def _ticket_cache_key(
        self,
        candidate: dict[str, Any],
        context: Mapping[str, Any],
        *,
        sentinel_meta: Mapping[str, Any],
        routing_mode: DegradationMode,
    ) -> str:
        return _stable_payload_hash(
            {
                "candidate": strip_internal_candidate_metadata(candidate),
                "context": _stable_context_identity(context),
                "routing_mode": routing_mode,
                "sentinel": _stable_context_identity(sentinel_meta),
            }
        )

    @staticmethod
    def _continuation_context_key(
        candidate: dict[str, Any],
        context: Mapping[str, Any],
    ) -> str:
        """Identify the effective evaluation context independently of routing mode."""

        return _stable_payload_hash(
            {
                "candidate": strip_internal_candidate_metadata(candidate),
                "context": _stable_context_identity(context),
            }
        )

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
            and self._continuation_context_key(ticket.candidate, ticket.context) == continuation_key
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

    def _result_for_level(
        self,
        ticket: FunnelTicket | str,
        target_level: int,
    ) -> FunnelStageResult | None:
        resolved_ticket = self._resolve_ticket(ticket)
        eligible_levels = [
            level for level in resolved_ticket.stage_results if level <= target_level
        ]
        if not eligible_levels:
            return None
        return resolved_ticket.stage_results[max(eligible_levels)]

    def _build_stage_context(
        self,
        ticket: FunnelTicket,
    ) -> dict[str, Any]:
        context = dict(ticket.context)
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
    ) -> None:
        """Fresh-read and bind a native work packet before projecting its reference."""
        from polisyos.core.artifacts import (
            input_ref_from_artifact_ref,
            load_core_json_artifact,
        )

        ref = result.executed_work_packet_ref
        if ref is None:
            return
        store = ticket.context.get("store")
        if store is None or not all(hasattr(store, name) for name in ("get_bytes", "get_manifest")):
            self._reject_work_packet(result, "artifact_store_unavailable")
            return

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
            packet = FunnelExecutedWorkPacket.model_validate(load_core_json_artifact(store, ref))
            packet_manifest = store.get_manifest(ref)
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
                    and packet.evaluation_attempt_id
                    == invocation.get("evaluation_attempt_id")
                    == bootstrap.get("evaluation_attempt_id")
                    and packet.requested_draw_count
                    == invocation.get("requested_draw_count")
                    == bootstrap.get("requested_draw_count")
                    and packet.requested_draw_source
                    == invocation.get("requested_draw_source")
                    == bootstrap.get("requested_draw_source")
                    and packet.effective_estimation_config_sha256
                    == invocation.get("effective_estimation_config_sha256")
                    == bootstrap.get("effective_estimation_config_sha256")
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
                return
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            self._reject_work_packet(result, "work_packet_unreadable_or_invalid")

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
    ) -> None:
        if (
            result.score_status is not ObjectiveScoreStatus.AVAILABLE
            or result.objective_value is None
            or result.score_assessment is None
            or _funnel_score_admission(result).status is not ObjectiveScoreStatus.AVAILABLE
            or not hasattr(self._voi_scheduler, "observe_stage_result")
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
        self._voi_scheduler.observe_stage_result(
            candidate_id=ticket.candidate_hash,
            task_family=transfer_context.task_family,
            domain=transfer_context.domain,
            tenant_hash=str(transfer_context.tenant_hash or ""),
            stage_level=stage_level,
            frontier_position=self._frontier.position_for(ticket.candidate_hash),
            cheap_signal=result.cheap_signal,
            actual_objective_value=result.objective_value,
            score_assessment=result.score_assessment,
            objective_source=result.simulation_results,
            actual_promising=result.is_promising,
            duration_seconds=result.duration_seconds,
            compute_cost_usd=result.compute_cost_usd,
            compute_cost_origin=result.compute_cost_origin,
            timeout_occurred=timeout_occurred,
            disagreement=disagreement,
            metadata={
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
        )

    def _maybe_update_voi_calibration_state(self) -> None:
        if self._correlation_tracker is None or not hasattr(
            self._voi_scheduler,
            "update_calibration_state",
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
        elif 4 in ticket.stage_results and ticket.stage_results[4].is_promising:
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
