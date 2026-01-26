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
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from polisyos.core.contracts.scientist import FailureCardRef
from polisyos.scientist.agent.failure_card import FailureCard, FailureSeverity, RemediationTarget

if TYPE_CHECKING:
    from polisyos.scientist.orchestrator.state import ExperimentState


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

    def get_delay(self, attempt: int) -> float:
        """Calculate backoff delay for given attempt number."""
        delay = self.base_delay_seconds * (self.backoff_multiplier ** (attempt - 1))
        return min(delay, self.max_delay_seconds)


class ReflexionOrchestrator:
    """
    Coordinates the Reflexion loop for self-healing workflows.
    """

    def __init__(self, config: Optional[ReflexionConfig] = None):
        self.config = config or ReflexionConfig()
        self._decision_log: List[Dict[str, Any]] = []

    def evaluate_failure(
        self,
        card: FailureCard,
        state: "ExperimentState",
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

        if card.remediation_target == RemediationTarget.DRAFTER:
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
        state: "ExperimentState",
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


# === State Update Helpers ===


def increment_retry_count(state: "ExperimentState") -> "ExperimentState":
    current = state.get("total_retry_count", 0)
    return {**state, "total_retry_count": current + 1}


def add_failure_to_history(
    state: "ExperimentState",
    card: FailureCard,
) -> "ExperimentState":
    history = list(state.get("failure_history", []))
    history.append(FailureCardRef.from_card(card).model_dump(mode="json"))
    return {**state, "failure_history": history}


def set_current_failure_card(
    state: "ExperimentState",
    card: Optional[FailureCard],
) -> "ExperimentState":
    return {**state, "current_failure_card": card.model_dump(mode="json") if card else None}


def clear_reflexion_state(state: "ExperimentState") -> "ExperimentState":
    return {
        **state,
        "current_failure_card": None,
    }
