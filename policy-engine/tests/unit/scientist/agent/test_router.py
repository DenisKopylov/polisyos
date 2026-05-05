"""Tests for WS6.3 — Dynamic Agent Routing."""

from __future__ import annotations

import pytest
from polisyos.scientist.agent.protocols import AgentRole, AgentRouter, RoutingState
from polisyos.scientist.agent.router import (
    AdaptiveRouter,
    AgentFallbackChain,
    FixedPipelineRouter,
    ParallelAgentRunner,
)

# ---------------------------------------------------------------------------
# RoutingState
# ---------------------------------------------------------------------------


class TestRoutingState:
    def test_frozen(self):
        state = RoutingState(
            current_role=AgentRole.DRAFTER,
            iteration=1,
            error_count=0,
            confidence=0.8,
            budget_remaining_ratio=0.5,
        )
        with pytest.raises(AttributeError):
            state.confidence = 0.9  # type: ignore[misc]

    def test_default_history(self):
        state = RoutingState(
            current_role=AgentRole.PI,
            iteration=0,
            error_count=0,
            confidence=1.0,
            budget_remaining_ratio=1.0,
        )
        assert state.history == ()


# ---------------------------------------------------------------------------
# AgentRouter protocol compliance
# ---------------------------------------------------------------------------


class TestAgentRouterProtocol:
    def test_fixed_router_implements_protocol(self):
        assert isinstance(FixedPipelineRouter(), AgentRouter)

    def test_adaptive_router_implements_protocol(self):
        assert isinstance(AdaptiveRouter(), AgentRouter)


# ---------------------------------------------------------------------------
# FixedPipelineRouter
# ---------------------------------------------------------------------------


class TestFixedPipelineRouter:
    def test_follows_pipeline_order(self):
        r = FixedPipelineRouter()
        state = RoutingState(
            current_role=AgentRole.PI,
            iteration=0,
            error_count=0,
            confidence=0.5,
            budget_remaining_ratio=0.5,
        )
        assert r.select_next_agent(state) == AgentRole.DRAFTER

    def test_drafter_to_formalizer(self):
        r = FixedPipelineRouter()
        state = RoutingState(
            current_role=AgentRole.DRAFTER,
            iteration=1,
            error_count=0,
            confidence=0.5,
            budget_remaining_ratio=0.5,
        )
        assert r.select_next_agent(state) == AgentRole.FORMALIZER

    def test_critic_stays_at_end(self):
        r = FixedPipelineRouter()
        state = RoutingState(
            current_role=AgentRole.CRITIC,
            iteration=3,
            error_count=0,
            confidence=0.5,
            budget_remaining_ratio=0.5,
        )
        assert r.select_next_agent(state) == AgentRole.CRITIC

    def test_escalation_threshold(self):
        r = FixedPipelineRouter(escalation_threshold=3)
        state_low = RoutingState(
            current_role=AgentRole.DRAFTER,
            iteration=1,
            error_count=2,
            confidence=0.5,
            budget_remaining_ratio=0.5,
        )
        assert r.should_escalate(state_low) is False

        state_high = RoutingState(
            current_role=AgentRole.DRAFTER,
            iteration=1,
            error_count=3,
            confidence=0.5,
            budget_remaining_ratio=0.5,
        )
        assert r.should_escalate(state_high) is True


# ---------------------------------------------------------------------------
# AdaptiveRouter
# ---------------------------------------------------------------------------


class TestAdaptiveRouter:
    def test_low_confidence_reroutes_to_drafter(self):
        r = AdaptiveRouter(confidence_threshold=0.3)
        state = RoutingState(
            current_role=AgentRole.FORMALIZER,
            iteration=2,
            error_count=0,
            confidence=0.1,
            budget_remaining_ratio=0.5,
        )
        assert r.select_next_agent(state) == AgentRole.DRAFTER

    def test_high_errors_escalate_to_pi(self):
        r = AdaptiveRouter(error_threshold=2)
        state = RoutingState(
            current_role=AgentRole.DRAFTER,
            iteration=1,
            error_count=3,
            confidence=0.5,
            budget_remaining_ratio=0.5,
        )
        assert r.select_next_agent(state) == AgentRole.PI

    def test_low_budget_skips_formalizer(self):
        r = AdaptiveRouter(budget_skip_threshold=0.2)
        state = RoutingState(
            current_role=AgentRole.DRAFTER,
            iteration=1,
            error_count=0,
            confidence=0.5,
            budget_remaining_ratio=0.1,
        )
        assert r.select_next_agent(state) == AgentRole.CRITIC

    def test_normal_state_follows_pipeline(self):
        r = AdaptiveRouter()
        state = RoutingState(
            current_role=AgentRole.PI,
            iteration=0,
            error_count=0,
            confidence=0.8,
            budget_remaining_ratio=0.9,
        )
        assert r.select_next_agent(state) == AgentRole.DRAFTER

    def test_cycle_detection_falls_back(self):
        r = AdaptiveRouter(confidence_threshold=0.5, max_reroutes=2)
        # History showing 2 reroutes already
        history = (
            AgentRole.PI,
            AgentRole.DRAFTER,
            AgentRole.PI,  # reroute 1
            AgentRole.DRAFTER,
            AgentRole.PI,  # reroute 2
        )
        state = RoutingState(
            current_role=AgentRole.FORMALIZER,
            iteration=5,
            error_count=0,
            confidence=0.1,
            budget_remaining_ratio=0.5,
            history=history,
        )
        # Should fall back to fixed pipeline despite low confidence
        assert r.select_next_agent(state) == AgentRole.CRITIC

    def test_should_escalate(self):
        r = AdaptiveRouter(error_threshold=2)
        state = RoutingState(
            current_role=AgentRole.DRAFTER,
            iteration=1,
            error_count=2,
            confidence=0.5,
            budget_remaining_ratio=0.5,
        )
        assert r.should_escalate(state) is True


# ---------------------------------------------------------------------------
# AgentFallbackChain
# ---------------------------------------------------------------------------


class TestAgentFallbackChain:
    @pytest.mark.asyncio
    async def test_first_succeeds(self):
        chain = AgentFallbackChain(
            agents=[
                ("primary", lambda: type("A", (), {"draft_policy": lambda *a, **kw: "result_1"})()),
            ]
        )
        result = await chain.execute("draft_policy")
        assert result == "result_1"

    @pytest.mark.asyncio
    async def test_cascades_on_failure(self):
        def fail_factory():
            obj = type("A", (), {})()
            obj.draft_policy = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fail"))
            return obj

        def ok_factory():
            return type("A", (), {"draft_policy": lambda *a, **kw: "fallback_result"})()

        chain = AgentFallbackChain(
            agents=[
                ("primary", fail_factory),
                ("fallback", ok_factory),
            ]
        )
        result = await chain.execute("draft_policy")
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_all_fail_raises(self):
        def fail_factory():
            obj = type("A", (), {})()
            obj.draft_policy = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fail"))
            return obj

        chain = AgentFallbackChain(agents=[("a", fail_factory), ("b", fail_factory)])
        with pytest.raises(RuntimeError, match="All agent fallbacks exhausted"):
            await chain.execute("draft_policy")

    @pytest.mark.asyncio
    async def test_assertion_is_not_swallowed(self):
        def fail_factory():
            obj = type("A", (), {})()
            obj.draft_policy = lambda *a, **kw: (_ for _ in ()).throw(
                AssertionError("fallback invariant failed")
            )
            return obj

        chain = AgentFallbackChain(agents=[("a", fail_factory)])
        with pytest.raises(AssertionError, match="fallback invariant failed"):
            await chain.execute("draft_policy")

    @pytest.mark.asyncio
    async def test_async_handler(self):
        async def async_draft(*a, **kw):
            return "async_result"

        chain = AgentFallbackChain(
            agents=[
                ("primary", lambda: type("A", (), {"draft_policy": async_draft})()),
            ]
        )
        result = await chain.execute("draft_policy")
        assert result == "async_result"


# ---------------------------------------------------------------------------
# ParallelAgentRunner
# ---------------------------------------------------------------------------


class TestParallelAgentRunner:
    @pytest.mark.asyncio
    async def test_runs_concurrently(self):
        results = []

        async def agent_a():
            results.append("a")
            return "result_a"

        async def agent_b():
            results.append("b")
            return "result_b"

        runner = ParallelAgentRunner()
        out = await runner.run_parallel([("a", agent_a), ("b", agent_b)])
        assert len(out) == 2
        assert set(results) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_exception_returned_not_raised(self):
        async def fail_agent():
            raise ValueError("oops")

        async def ok_agent():
            return "ok"

        runner = ParallelAgentRunner()
        out = await runner.run_parallel([("fail", fail_agent), ("ok", ok_agent)])
        assert isinstance(out[0], ValueError)
        assert out[1] == "ok"

    @pytest.mark.asyncio
    async def test_parallel_assertion_is_not_swallowed(self):
        def fail_agent():
            raise AssertionError("parallel invariant failed")

        runner = ParallelAgentRunner()
        with pytest.raises(AssertionError, match="parallel invariant failed"):
            await runner.run_parallel([("fail", fail_agent)])
