"""Stateful multi-fidelity funnel orchestration runtime."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.budget import BudgetState
from polisyos.scientist.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
)
from polisyos.scientist.search.lessons import (
    LessonRegistry,
    lesson_from_failure_card,
    success_lesson_from_outcome,
)
from polisyos.scientist.search.sentinels import (
    extract_sentinel_metadata,
    strip_internal_candidate_metadata,
)
from polisyos.scientist.search.stages import CorrelationTracker
from polisyos.scientist.search.transfer_context import resolve_transfer_context
from polisyos.scientist.search.voi_scheduler import (
    ParetoSnapshot,
    PredictiveVOIScheduler,
    SchedulingDecision,
    SimpleVOIScheduler,
)

logger = get_logger(__name__)

RoutingAction = Literal[
    "advance",
    "defer",
    "reject",
    "retry_cheaper",
    "complete",
    "defer_to_human",
]
DegradationMode = Literal[
    "normal",
    "conservative_routing",
    "no_promotion",
    "reduced_judge",
    "freeze_frontier",
    "prior_free",
    "auto_cap",
]
AdvancePolicy = Literal["stage_a", "full", "burn_in"]


def _stable_candidate_hash(candidate: dict[str, Any]) -> str:
    """Return a deterministic hash for orchestrator-local caching."""

    try:
        payload = json.dumps(
            strip_internal_candidate_metadata(candidate),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except TypeError:
        payload = repr(candidate)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class FunnelTraceStep:
    """Trace record for one stage execution."""

    fidelity_level: int
    stage_name: str
    objective_value: float
    is_promising: bool
    duration_seconds: float
    compute_actual_usd: float
    routing_decision: str | None = None
    voi_action: str | None = None
    voi_priority: float | None = None
    failure_count: int = 0
    blocker_count: int = 0


@dataclass(slots=True)
class FunnelTicket:
    """Stateful handle for one candidate moving through the funnel."""

    ticket_id: str
    candidate_hash: str
    candidate: dict[str, Any]
    context: dict[str, Any]
    submitted_via_cache: bool = False
    stage_results: dict[int, FunnelStageResult] = field(default_factory=dict)
    trace: list[FunnelTraceStep] = field(default_factory=list)
    current_level: int | None = None
    next_level: int | None = None
    final_action: RoutingAction = "advance"
    degradation_mode: DegradationMode = "normal"
    is_terminal: bool = False
    last_scheduling_decision: SchedulingDecision | None = None
    lesson_refs: list[ArtifactRef] = field(default_factory=list)
    correlation_recorded: bool = False
    lessons_finalized: bool = False

    @property
    def last_result(self) -> FunnelStageResult | None:
        if not self.stage_results:
            return None
        return self.stage_results[max(self.stage_results)]


@dataclass(slots=True)
class FunnelOutcome:
    """Aggregated view of one ticket's funnel execution state."""

    ticket_id: str
    candidate_hash: str
    trace: list[FunnelTraceStep]
    stage_results: dict[int, FunnelStageResult]
    final_result: FunnelStageResult | None
    failure_cards: list[TypedFailureCard]
    uncertainty_envelope: UncertaintyEnvelope
    compute_actual_usd: float
    degradation_mode: DegradationMode
    final_action: RoutingAction
    completed: bool
    last_scheduling_decision: SchedulingDecision | None = None
    lesson_refs: list[ArtifactRef] = field(default_factory=list)
    audit_refs: list[ArtifactRef] = field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = field(default_factory=list)


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
        cached_ticket_id = self._ticket_cache.get(candidate_hash)
        sentinel_meta = extract_sentinel_metadata(candidate) or {}
        if cached_ticket_id is not None:
            ticket = self._tickets[cached_ticket_id]
            ticket.submitted_via_cache = True
            for key, value in context.items():
                ticket.context.setdefault(key, value)
            for key, value in sentinel_meta.items():
                ticket.context.setdefault(key, value)
            if sentinel_meta:
                ticket.context["is_sentinel"] = True
            return ticket

        ticket_context = dict(context)
        if sentinel_meta:
            ticket_context.update(sentinel_meta)
            ticket_context["is_sentinel"] = True
        ticket = FunnelTicket(
            ticket_id=str(uuid4()),
            candidate_hash=candidate_hash,
            candidate=dict(candidate),
            context=ticket_context,
            next_level=self._first_level(),
        )
        self._tickets[ticket.ticket_id] = ticket
        self._ticket_cache[candidate_hash] = ticket.ticket_id
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
        resolved_ticket.degradation_mode = self._routing_mode()
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

            stage = self._stages_by_level[next_level]
            result = stage.evaluate(
                resolved_ticket.candidate,
                self._build_stage_context(resolved_ticket),
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
                compute_actual_usd=result.compute_actual_usd,
                routing_decision=routing_decision,
                failure_count=len(result.failure_cards),
                blocker_count=sum(1 for card in result.failure_cards if card.is_blocker),
            )
            resolved_ticket.trace.append(trace_step)
            self._maybe_record_voi_observation(resolved_ticket, result, next_level)

            if result.terminal_action is not None:
                resolved_ticket.final_action = result.terminal_action
                if result.terminal_action != "advance":
                    resolved_ticket.is_terminal = True
                    break

            if result.has_blockers:
                logger.debug(
                    "Funnel stopped at %s: %d blocker(s)",
                    result.stage_name,
                    trace_step.blocker_count,
                )
                resolved_ticket.final_action = "reject"
                resolved_ticket.is_terminal = True
                break
            if not result.is_promising:
                if burn_in_calibration and next_level in (1, 2, 3):
                    logger.debug(
                        "Burn-in bypass at %s: continuing despite non-promising result.",
                        result.stage_name,
                    )
                    self._maybe_record_correlation(resolved_ticket)
                    continue
                logger.debug(
                    "Funnel stopped at %s: not promising (obj=%.4f)",
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
                    uncertainty_envelope=result.uncertainty_envelope,
                    cheap_signal=result.cheap_signal,
                    failure_cards=result.failure_cards,
                    compute_actual_usd=result.compute_actual_usd,
                    fidelity_level=result.fidelity_level,
                    audit_refs=list(result.audit_refs),
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

            if (
                next_level in (2, 3)
                and policy != "burn_in"
                and resolved_ticket.degradation_mode == "normal"
                and result.cheap_signal is not None
                and resolved_ticket.next_level is not None
                and resolved_ticket.next_level <= execution_target
            ):
                self._maybe_update_voi_calibration_state()
                scheduling = self._voi_scheduler.prioritize(
                    [resolved_ticket],
                    self._budget_state,
                    self._frontier,
                )
                if scheduling:
                    decision = scheduling[0]
                    resolved_ticket.last_scheduling_decision = decision
                    trace_step.voi_action = decision.recommended_action
                    trace_step.voi_priority = decision.priority
                    if decision.recommended_action == "reject":
                        resolved_ticket.final_action = "reject"
                        resolved_ticket.is_terminal = True
                        break
                    if decision.recommended_action == "defer":
                        resolved_ticket.final_action = "defer"
                        resolved_ticket.is_terminal = True
                        break
                    if decision.recommended_action == "retry_cheaper":
                        resolved_ticket.final_action = "retry_cheaper"
                        resolved_ticket.is_terminal = True
                        break

            if resolved_ticket.next_level is None:
                self._mark_terminal(resolved_ticket)
                break

            self._maybe_record_correlation(resolved_ticket)

        self._maybe_record_correlation(resolved_ticket)
        self._maybe_record_lessons(resolved_ticket)
        return self.get_outcome(resolved_ticket)

    def get_outcome(
        self,
        ticket: FunnelTicket | str,
    ) -> FunnelOutcome:
        """Return the aggregated current outcome for a ticket."""

        resolved_ticket = self._resolve_ticket(ticket)
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

        return FunnelOutcome(
            ticket_id=resolved_ticket.ticket_id,
            candidate_hash=resolved_ticket.candidate_hash,
            trace=list(resolved_ticket.trace),
            stage_results=dict(resolved_ticket.stage_results),
            final_result=resolved_ticket.last_result,
            failure_cards=failure_cards,
            uncertainty_envelope=uncertainty_envelope,
            compute_actual_usd=sum(step.compute_actual_usd for step in resolved_ticket.trace),
            degradation_mode=resolved_ticket.degradation_mode,
            final_action=resolved_ticket.final_action,
            completed=resolved_ticket.is_terminal,
            last_scheduling_decision=resolved_ticket.last_scheduling_decision,
            lesson_refs=list(resolved_ticket.lesson_refs),
            audit_refs=_dedupe_artifact_refs(audit_refs),
            actionable_side_information_refs=_dedupe_artifact_refs(
                actionable_side_information_refs
            ),
        )

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        """Backward-compatible convenience wrapper around submit+advance."""

        ticket = self.submit(candidate, context)
        outcome = self.advance(ticket, policy="full")
        return outcome.final_result or self._empty_result(candidate)

    def as_stage_a_callable(
        self,
    ) -> Callable[[dict[str, Any], dict[str, Any]], tuple[float, bool]]:
        """Return a SearchController-compatible Stage A callable."""

        def _stage_a(
            candidate: dict[str, Any],
            context: dict[str, Any],
        ) -> tuple[float, bool]:
            ticket = self.submit(candidate, context)
            outcome = self.advance(ticket, policy="stage_a")
            result = self._result_for_level(ticket, self._stage_a_execution_target())
            if result is None:
                result = outcome.final_result or self._empty_result(candidate)
            passed = result.is_promising and outcome.final_action in {"advance", "complete"}
            return result.objective_value, passed

        return _stage_a

    def as_stage_b_callable(
        self,
    ) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
        """Return a SearchController-compatible Stage B callable."""

        def _stage_b(
            candidate: dict[str, Any],
            context: dict[str, Any],
        ) -> dict[str, Any]:
            candidate_hash = _stable_candidate_hash(candidate)
            cache_hit = candidate_hash in self._ticket_cache
            ticket = self.submit(candidate, context)
            outcome = self.advance(ticket, policy="full")
            result = outcome.final_result or self._empty_result(candidate)
            feedback = dict(result.feedback)
            feedback.setdefault(
                "verdict",
                "APPROVE"
                if result.is_promising and outcome.final_action in {"complete", "advance"}
                else "REJECT",
            )
            feedback["funnel_action"] = outcome.final_action
            feedback["funnel_degradation_mode"] = outcome.degradation_mode
            feedback["funnel_cache"] = "hit" if cache_hit else "miss"
            return {
                "simulation_results": result.simulation_results,
                "feedback": feedback,
                "objective_value": result.objective_value,
                "is_promising": result.is_promising,
                "_funnel_result": result,
                "_funnel_outcome": outcome,
            }

        return _stage_b

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
            run_id=str(context.get("source_run_id") or context.get("run_id") or ticket.ticket_id),
        )
        context["_funnel_ticket_id"] = ticket.ticket_id
        context["transfer_context"] = transfer_context
        context["funnel_degradation_mode"] = ticket.degradation_mode
        for level, result in ticket.stage_results.items():
            context[f"_funnel_L{level}_result"] = result
        if self._lesson_registry is not None:
            context["lesson_registry"] = self._lesson_registry
        if self._correlation_tracker is not None:
            context["correlation_metrics"] = self._correlation_tracker.compute_metrics()
        return context

    def _routing_mode(self) -> DegradationMode:
        if self._correlation_tracker is None:
            return "normal"
        if hasattr(self._correlation_tracker, "routing_mode"):
            mode = self._correlation_tracker.routing_mode()
            if mode in {
                "normal",
                "conservative_routing",
                "no_promotion",
                "reduced_judge",
                "freeze_frontier",
                "prior_free",
                "auto_cap",
            }:
                return mode
        metrics = self._correlation_tracker.compute_metrics()
        mode = metrics.get("routing_mode", "normal")
        if mode in {
            "normal",
            "conservative_routing",
            "no_promotion",
            "reduced_judge",
            "freeze_frontier",
            "prior_free",
            "auto_cap",
        }:
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
            objective_value=0.0,
            is_promising=True,
            stage_name="funnel_empty",
            uncertainty_envelope=UncertaintyEnvelope.unknown(),
            fidelity_level=0,
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
        if gate_result is None or truth_result is None:
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
        if not hasattr(self._voi_scheduler, "observe_stage_result"):
            return
        transfer_context = resolve_transfer_context(
            candidate=ticket.candidate,
            context=ticket.context,
            run_id=str(
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
            actual_promising=result.is_promising,
            duration_seconds=result.duration_seconds,
            compute_cost_usd=result.compute_actual_usd,
            timeout_occurred=timeout_occurred,
            disagreement=disagreement,
            metadata={
                "ticket_id": ticket.ticket_id,
                "stage_name": result.stage_name,
                "fidelity_level": result.fidelity_level,
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
            run_id=source_run_id,
        )
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
