"""Dynamic agent routing implementations.

Provides router classes that implement the :class:`AgentRouter` protocol
for runtime agent selection based on pipeline state signals.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from polisyos.common.logger import get_logger

from .protocols import AgentRole, RoutingState

logger = get_logger(__name__)

__all__ = [
    "AdaptiveRouter",
    "AgentFallbackChain",
    "FixedPipelineRouter",
    "ParallelAgentRunner",
]

# Default agent execution order
_DEFAULT_PIPELINE: list[AgentRole] = [
    AgentRole.PI,
    AgentRole.DRAFTER,
    AgentRole.FORMALIZER,
    AgentRole.CRITIC,
]


class FixedPipelineRouter:
    """Routes agents in the fixed PI -> Drafter -> Formalizer -> Critic order.

    This is the default baseline that preserves the current behaviour.
    """

    PIPELINE = _DEFAULT_PIPELINE

    def __init__(self, escalation_threshold: int = 3) -> None:
        self._escalation_threshold = escalation_threshold

    def select_next_agent(self, state: RoutingState) -> AgentRole:
        try:
            idx = self.PIPELINE.index(state.current_role)
        except ValueError:
            return AgentRole.DRAFTER  # safe fallback
        next_idx = min(idx + 1, len(self.PIPELINE) - 1)
        return self.PIPELINE[next_idx]

    def should_escalate(self, state: RoutingState) -> bool:
        return state.error_count >= self._escalation_threshold


class AdaptiveRouter:
    """Routes agents based on real-time state signals.

    Routing rules (evaluated in priority order):

    1. **High errors** — escalate to PI for re-planning.
    2. **Low confidence** past drafting — re-route to DRAFTER for revision.
    3. **Low budget** — skip FORMALIZER, jump DRAFTER -> CRITIC.
    4. **Default** — follow the fixed pipeline.

    Includes cycle detection via ``max_reroutes``.
    """

    def __init__(
        self,
        *,
        confidence_threshold: float = 0.3,
        error_threshold: int = 2,
        budget_skip_threshold: float = 0.2,
        max_reroutes: int = 3,
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._error_threshold = error_threshold
        self._budget_skip_threshold = budget_skip_threshold
        self._max_reroutes = max_reroutes
        self._fixed = FixedPipelineRouter()

    def select_next_agent(self, state: RoutingState) -> AgentRole:
        # Cycle detection: count how many times we've deviated from pipeline
        reroute_count = self._count_reroutes(state.history)
        if reroute_count >= self._max_reroutes:
            return self._fixed.select_next_agent(state)

        # Rule 1: High errors -> PI
        if state.error_count >= self._error_threshold:
            if state.current_role != AgentRole.PI:
                return AgentRole.PI

        # Rule 2: Low confidence after drafting -> back to DRAFTER
        if (
            state.confidence < self._confidence_threshold
            and state.current_role in (AgentRole.FORMALIZER, AgentRole.CRITIC)
        ):
            return AgentRole.DRAFTER

        # Rule 3: Low budget -> skip FORMALIZER
        if (
            state.budget_remaining_ratio < self._budget_skip_threshold
            and state.current_role == AgentRole.DRAFTER
        ):
            return AgentRole.CRITIC

        # Default pipeline
        return self._fixed.select_next_agent(state)

    def should_escalate(self, state: RoutingState) -> bool:
        return state.error_count >= self._error_threshold

    @staticmethod
    def _count_reroutes(history: tuple[AgentRole, ...]) -> int:
        """Count deviations from the standard pipeline order."""
        if len(history) < 2:
            return 0
        reroutes = 0
        for i in range(1, len(history)):
            prev_idx = _DEFAULT_PIPELINE.index(history[i - 1]) if history[i - 1] in _DEFAULT_PIPELINE else -1
            curr_idx = _DEFAULT_PIPELINE.index(history[i]) if history[i] in _DEFAULT_PIPELINE else -1
            if curr_idx <= prev_idx:
                reroutes += 1
        return reroutes


@dataclass
class AgentFallbackChain:
    """Cascading fallback chain for agent execution.

    Each entry is a ``(label, factory)`` pair.  The chain tries each factory
    in order; the first one that succeeds returns its result.  If all fail,
    a ``RuntimeError`` is raised.
    """

    agents: list[tuple[str, Callable[..., Any]]] = field(default_factory=list)

    async def execute(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Try each agent's *method* in order until one succeeds."""
        last_exc: BaseException | None = None
        for label, factory in self.agents:
            try:
                agent = factory() if callable(factory) else factory
                fn = getattr(agent, method, None)
                if fn is None:
                    continue
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            except Exception as exc:
                logger.warning("Fallback %s.%s failed: %s", label, method, exc)
                last_exc = exc
                continue

        msg = "All agent fallbacks exhausted"
        if last_exc is not None:
            msg = f"{msg} (last: {last_exc})"
        raise RuntimeError(msg)


class ParallelAgentRunner:
    """Run multiple agent calls concurrently and collect results."""

    async def run_parallel(
        self,
        calls: list[tuple[str, Callable[..., Any]]],
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """Execute *calls* concurrently.

        Each entry is ``(label, coroutine_factory)``.  Returns a list of
        results (or exceptions) in the same order.
        """
        async def _run(label: str, fn: Callable[..., Any]) -> Any:
            try:
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            except Exception as exc:
                logger.warning("Parallel agent %s failed: %s", label, exc)
                return exc

        return await asyncio.gather(*(_run(lbl, fn) for lbl, fn in calls))
