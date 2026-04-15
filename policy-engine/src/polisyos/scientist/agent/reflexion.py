"""
ReflexionOrchestrator: Self-healing workflow coordinator.

Implements the Reflexion pattern for autonomous error recovery:
1. Detect failure (via FailureCard)
2. Evaluate recoverability
3. Route to appropriate handler
4. Inject context and retry
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from polisyos.common.logger import get_logger
from polisyos.core.contracts.scientist import FailureCardRef
from polisyos.scientist.agent.failure_card import FailureCard, FailureSeverity, RemediationTarget
from polisyos.scientist.agent.persistent_memory import (
    MemoryEntry,
    PersistentMemoryStore,
    problem_signature,
)
from polisyos.scientist.agent.reflexion_evaluator import (
    ReflexionScorecard,
    RubricReflexionEvaluator,
    build_reflexion_summary_text,
)
from polisyos.scientist.autotune.reflexion import (
    ReflexionReplayRecorder,
    load_reflexion_routing_config,
    route_recoverable_failure,
)

logger = get_logger(__name__)


class ReflexionDecision(str, Enum):
    """Decision outcomes from the Reflexion evaluator."""

    RETURN_TO_FORMALIZER = "return_to_formalizer"
    RETURN_TO_DRAFTER = "return_to_drafter"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    ABORT_WITH_REPORT = "abort_with_report"
    PASS_THROUGH = "pass_through"


@dataclass
class ReflexionConfig:
    """Configuration for the Reflexion loop."""

    max_iterations: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    escalation_threshold: int = 2
    enable_async_delay: bool = True
    ping_pong_switches: int = 2
    min_retry_score: float = 0.70
    min_retry_improvement: float = 0.01
    memory_recall_limit: int = 5
    memory_min_confidence: float = 0.0

    def get_delay(self, attempt: int) -> float:
        """Calculate backoff delay for given attempt number."""
        delay = self.base_delay_seconds * (self.backoff_multiplier ** (attempt - 1))
        return min(delay, self.max_delay_seconds)


class ReflexionOrchestrator:
    """
    Coordinates the Reflexion loop for self-healing workflows.
    """

    def __init__(
        self,
        config: Optional[ReflexionConfig] = None,
        *,
        persistent_memory: PersistentMemoryStore | None = None,
        evaluator: RubricReflexionEvaluator | None = None,
    ):
        self.config = config or ReflexionConfig()
        self._decision_log: List[Dict[str, Any]] = []
        self._replay_recorder = ReflexionReplayRecorder()
        self._persistent_memory = persistent_memory
        self._evaluator = evaluator or RubricReflexionEvaluator()
        self._evaluation_log: list[ReflexionScorecard] = []

    def evaluate_failure(
        self,
        card: FailureCard,
        state: dict[str, Any],
    ) -> ReflexionDecision:
        """
        Evaluate a failure and decide the next action.
        """
        logger.info(
            "Evaluating failure: {} (attempt {}/{})".format(
                card.error_code, card.attempt_number, card.max_iterations
            )
        )

        if card.severity == FailureSeverity.FATAL:
            logger.warning(f"Fatal error detected: {card.error_code}")
            return self._log_decision(card, ReflexionDecision.ABORT_WITH_REPORT, "fatal_severity")

        if card.severity == FailureSeverity.NEEDS_HUMAN:
            logger.info(f"Human intervention required: {card.error_code}")
            return self._log_decision(card, ReflexionDecision.ESCALATE_TO_HUMAN, "needs_human")

        if not card.can_retry:
            logger.warning(
                "Retry budget exhausted ({}/{})".format(
                    card.attempt_number, card.max_iterations
                )
            )
            return self._log_decision(card, ReflexionDecision.ABORT_WITH_REPORT, "budget_exhausted")

        if self._llm_budget_exhausted(state):
            logger.warning("Global LLM budget exhausted")
            return self._log_decision(
                card, ReflexionDecision.ABORT_WITH_REPORT, "llm_budget_exhausted"
            )

        autotune_config = load_reflexion_routing_config(context={"state": state})
        autotuned_route = route_recoverable_failure(card, config=autotune_config)
        if autotuned_route is not None:
            decision = ReflexionDecision(autotuned_route)
        elif card.remediation_target == RemediationTarget.DRAFTER:
            decision = ReflexionDecision.RETURN_TO_DRAFTER
        elif card.remediation_target == RemediationTarget.HUMAN:
            decision = ReflexionDecision.ESCALATE_TO_HUMAN
        elif card.remediation_target == RemediationTarget.NONE:
            decision = ReflexionDecision.ABORT_WITH_REPORT
        else:
            decision = ReflexionDecision.RETURN_TO_FORMALIZER

        if self._is_ping_pong(card, decision):
            logger.warning("Ping-pong detected between Drafter and Formalizer")
            return self._log_decision(card, ReflexionDecision.ESCALATE_TO_HUMAN, "ping_pong")

        return self._log_decision(
            card,
            decision,
            "conceptual_issue" if decision == ReflexionDecision.RETURN_TO_DRAFTER else "technical_issue",
        )

    def _log_decision(
        self,
        card: FailureCard,
        decision: ReflexionDecision,
        reason: str,
    ) -> ReflexionDecision:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": card.run_id,
            "card_id": str(card.card_id),
            "error_code": card.error_code,
            "decision": decision.value,
            "reason": reason,
            "attempt": card.attempt_number,
        }
        self._decision_log.append(entry)
        return decision

    def prepare_retry_context(
        self,
        card: FailureCard,
        state: dict[str, Any],
        include_history: bool = True,
    ) -> Dict[str, Any]:
        context = {
            "failure_context": card.to_prompt_context(include_history=include_history),
            "attempt_number": card.attempt_number + 1,
            "max_iterations": card.max_iterations,
            "remaining_attempts": card.max_iterations - card.attempt_number,
        }

        if state.get("user_request"):
            context["original_request"] = state["user_request"]

        if card.failed_artifact_ref:
            context["failed_artifact_ref"] = card.failed_artifact_ref

        if include_history and card.attempt_number > 1:
            failure_refs = state.get("failure_history", [])
            context["previous_failure_summary"] = self._summarize_history(failure_refs)

        remembered = self._recall_prior_reflections(card, state)
        if remembered:
            context["prior_reflections"] = self._format_prior_reflections(remembered)
            context["problem_signature"] = problem_signature(
                str(
                    state.get("user_request")
                    or state.get("problem_statement")
                    or card.violation_summary
                )
            )

        return context

    def _summarize_history(self, refs: List[Any]) -> str:
        if not refs:
            return "No previous failures."

        lines = [f"Previous attempts ({len(refs)}):"]
        recent = refs[-3:]
        for i, ref in enumerate(recent, 1):
            if isinstance(ref, FailureCardRef):
                entry = ref
            else:
                entry = FailureCardRef.model_validate(ref)
            lines.append(f"  {i}. {entry.error_code} (attempt {entry.attempt_number})")

        return "\n".join(lines)

    async def apply_backoff(self, attempt: int) -> None:
        if not self.config.enable_async_delay:
            return

        delay = self.config.get_delay(attempt)
        logger.debug(
            "Applying backoff delay: {:.2f}s before attempt {}".format(delay, attempt + 1)
        )
        await asyncio.sleep(delay)

    def should_suggest_escalation(self, card: FailureCard) -> bool:
        return card.attempt_number >= self.config.escalation_threshold

    def get_decision_log(self) -> List[Dict[str, Any]]:
        return self._decision_log.copy()

    def reset_decision_log(self) -> None:
        self._decision_log.clear()
        self._evaluation_log.clear()

    def evaluate_candidate(
        self,
        *,
        objective: str,
        output_text: str,
        output_data: dict[str, Any] | None = None,
        citations: list[dict[str, Any]] | None = None,
        tool_results: list[Any] | None = None,
        expected_output_schema: dict[str, Any] | None = None,
    ) -> ReflexionScorecard:
        """Evaluate a retry candidate with the rubric evaluator."""
        scorecard = self._evaluator.evaluate_candidate(
            objective=objective,
            output_text=output_text,
            output_data=output_data or {},
            citations=citations or [],
            tool_results=tool_results or [],
            expected_output_schema=expected_output_schema or {},
        )
        self._evaluation_log.append(scorecard)
        return scorecard

    def should_stop_optimization(
        self,
        scorecard: ReflexionScorecard,
    ) -> tuple[bool, str]:
        """Use score/evidence deltas instead of tool-call count as the stop policy."""
        if scorecard.passed and scorecard.overall_score >= self.config.min_retry_score:
            return True, "rubric_passed"
        if len(self._evaluation_log) >= 2:
            previous = self._evaluation_log[-2]
            score_delta = scorecard.overall_score - previous.overall_score
            evidence_delta = scorecard.evidence_count - previous.evidence_count
            if (
                score_delta < self.config.min_retry_improvement
                and evidence_delta <= 0
            ):
                return True, "score_plateau"
        return False, ""

    def record_retry_outcome(
        self,
        card: FailureCard,
        decision: ReflexionDecision,
        success: bool,
        *,
        unsafe_for_nonhuman: bool = False,
        alternative_outcomes: Dict[str, bool] | None = None,
        metadata: dict[str, Any] | None = None,
        evaluation: ReflexionScorecard | None = None,
        problem_statement: str | None = None,
        trajectory_summary: str | None = None,
        tool_error_patterns: list[str] | None = None,
    ) -> None:
        outcomes = dict(alternative_outcomes or {})
        outcomes[decision.value] = bool(success)
        case_id = f"{card.run_id}:{card.card_id}:{card.attempt_number}"
        self._replay_recorder.record_case(
            case_id=case_id,
            card=card,
            decision_outcomes=outcomes,
            unsafe_for_nonhuman=unsafe_for_nonhuman,
            metadata={
                **(metadata or {}),
                **(
                    {
                        "evaluation": evaluation.model_dump(mode="json"),
                        "problem_signature": problem_signature(
                            problem_statement or card.violation_summary
                        ),
                    }
                    if evaluation is not None
                    else {}
                ),
            },
        )
        if self._persistent_memory is None or evaluation is None:
            return

        problem_text = problem_statement or card.violation_summary
        summary = trajectory_summary or card.to_prompt_context(include_history=True)
        self._persistent_memory.store_reflexion_memory(
            problem_statement=problem_text,
            reflection=build_reflexion_summary_text(
                objective=problem_text,
                scorecard=evaluation,
                failure_summary=card.violation_summary,
                remediation=card.remediation_advice,
                tool_error_patterns=tool_error_patterns
                or evaluation.tool_error_patterns,
            ),
            trajectory_summary=summary,
            source_run_id=card.run_id,
            source_node_alias="reflexion",
            error_code=card.error_code,
            tool_error_patterns=tool_error_patterns
            or evaluation.tool_error_patterns,
            confidence=max(0.1, min(1.0, evaluation.overall_score)),
        )

    def get_replay_records(self) -> List[Dict[str, Any]]:
        return self._replay_recorder.records()

    def get_evaluation_log(self) -> list[ReflexionScorecard]:
        """Return a copy of the score/evidence evaluation history."""
        return list(self._evaluation_log)

    def write_replay_dataset(self, **kwargs: Any):
        return self._replay_recorder.write_dataset(**kwargs)

    def _llm_budget_exhausted(self, state: "ExperimentState") -> bool:
        budget = state.get("budget") or {}
        usage = state.get("budget_usage") or {}

        max_calls = budget.get("max_llm_calls")
        if max_calls is None:
            max_calls = budget.get("max_llm_calls", 0)
        calls_used = usage.get("llm_calls")
        if calls_used is None:
            calls_used = usage.get("llm_calls_used")
        if calls_used is None:
            calls_used = budget.get("llm_calls_used", 0)

        if not max_calls:
            return False
        return calls_used >= max_calls

    def _is_ping_pong(self, card: FailureCard, decision: ReflexionDecision) -> bool:
        if decision not in (
            ReflexionDecision.RETURN_TO_DRAFTER,
            ReflexionDecision.RETURN_TO_FORMALIZER,
        ):
            return False

        relevant = [
            entry["decision"]
            for entry in self._decision_log
            if entry.get("run_id") == card.run_id
            and entry.get("decision")
            in (
                ReflexionDecision.RETURN_TO_DRAFTER.value,
                ReflexionDecision.RETURN_TO_FORMALIZER.value,
            )
        ]
        relevant.append(decision.value)
        if len(relevant) < 4:
            return False

        recent = relevant[-4:]
        switch_count = 0
        for prev, current in zip(recent, recent[1:]):
            if prev != current:
                switch_count += 1
        return switch_count > self.config.ping_pong_switches

    def _recall_prior_reflections(
        self,
        card: FailureCard,
        state: dict[str, Any],
    ) -> list[MemoryEntry]:
        if self._persistent_memory is None:
            return []
        problem_statement = str(
            state.get("user_request")
            or state.get("problem_statement")
            or card.violation_summary
        )
        tool_error_patterns = _tool_error_patterns_from_card(card)
        try:
            return self._persistent_memory.recall_reflexion_memories(
                problem_statement=problem_statement,
                error_code=card.error_code,
                tool_error_patterns=tool_error_patterns,
                max_results=self.config.memory_recall_limit,
                min_confidence=self.config.memory_min_confidence,
            )
        except Exception:
            logger.debug("Failed to recall reflexion memories")
            return []

    def _format_prior_reflections(self, entries: list[MemoryEntry]) -> str:
        if not entries:
            return ""
        lines = ["## PRIOR REFLEXION MEMORY"]
        for entry in entries[: self.config.memory_recall_limit]:
            lines.append(f"- {entry.content}")
        return "\n".join(lines)


# === State Update Helpers ===


def increment_retry_count(state: "ExperimentState") -> "ExperimentState":
    """Increment retry count helper."""
    current = state.get("total_retry_count", 0)
    return {**state, "total_retry_count": current + 1}


def add_failure_to_history(
    state: "ExperimentState",
    card: FailureCard,
) -> "ExperimentState":
    """Add failure to history helper."""
    history = list(state.get("failure_history", []))
    history.append(FailureCardRef.from_card(card).model_dump(mode="json"))
    return {**state, "failure_history": history}


def set_current_failure_card(
    state: "ExperimentState",
    card: Optional[FailureCard],
) -> "ExperimentState":
    """Set current failure card helper."""
    return {**state, "current_failure_card": card.model_dump(mode="json") if card else None}


def clear_reflexion_state(state: "ExperimentState") -> "ExperimentState":
    """Clear reflexion state helper."""
    return {
        **state,
        "current_failure_card": None,
    }


def _tool_error_patterns_from_card(card: FailureCard) -> list[str]:
    details = card.technical_details or {}
    patterns: list[str] = []
    raw_patterns = details.get("tool_error_patterns")
    if isinstance(raw_patterns, list):
        patterns.extend(str(item) for item in raw_patterns if item)
    tool_name = details.get("tool_name")
    error_type = details.get("error_type")
    if tool_name or error_type:
        patterns.append(
            f"{str(tool_name or 'unknown_tool').strip().lower()}:"
            f"{str(error_type or 'tool_error').strip().lower()}"
        )
    return sorted(dict.fromkeys(patterns))
