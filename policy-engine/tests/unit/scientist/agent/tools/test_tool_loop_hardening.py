"""Tests for WS6.1 — Tool Loop Hardening."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from polisyos.scientist.agent.tools.dependency_graph import ToolDependencyGraph
from polisyos.scientist.agent.tools.registry import ToolCallResult, ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition
from polisyos.scientist.agent.tools.tool_circuit_breaker import ToolCircuitBreakerRegistry
from polisyos.scientist.agent.tools.tool_loop import (
    _tool_backoff_delay,
    run_tool_loop,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tool(name: str = "test_tool", timeout_s: float = 30.0) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Test tool {name}",
        parameters={"type": "object", "properties": {}},
        timeout_s=timeout_s,
    )


def _make_registry(*tools_and_handlers) -> ToolRegistry:
    reg = ToolRegistry()
    for defn, handler in tools_and_handlers:
        reg.register(defn, handler)
    return reg


@dataclass
class FakeLLMResponse:
    content: str = ""
    tool_calls: list[Any] | None = None
    usage: Any = None
    raw: dict | None = None


@dataclass
class FakeToolCall:
    id: str = "tc1"
    name: str = "test_tool"
    arguments: dict[str, Any] | None = None

    def __post_init__(self):
        if self.arguments is None:
            self.arguments = {}


# ---------------------------------------------------------------------------
# ToolDefinition.timeout_s
# ---------------------------------------------------------------------------


class TestToolDefinitionTimeout:
    def test_default_timeout(self):
        t = _make_tool()
        assert t.timeout_s == 30.0

    def test_custom_timeout(self):
        t = _make_tool(timeout_s=60.0)
        assert t.timeout_s == 60.0

    def test_timeout_bounds(self):
        with pytest.raises(ValidationError):
            _make_tool(timeout_s=0.5)
        with pytest.raises(ValidationError):
            _make_tool(timeout_s=700.0)


# ---------------------------------------------------------------------------
# ToolRegistry with timeout + circuit breaker
# ---------------------------------------------------------------------------


class TestRegistryTimeout:
    @pytest.mark.asyncio
    async def test_async_timeout_triggers(self):
        async def slow_handler():
            await asyncio.sleep(10)
            return "done"

        defn = _make_tool(timeout_s=1.0)
        reg = _make_registry((defn, slow_handler))
        result = await reg.aexecute("test_tool", {})
        assert result.error is not None
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_async_no_timeout_when_fast(self):
        async def fast_handler():
            return "quick"

        defn = _make_tool(timeout_s=5.0)
        reg = _make_registry((defn, fast_handler))
        result = await reg.aexecute("test_tool", {})
        assert result.error is None
        assert result.result == "quick"


class TestToolLoopFaultIsolation:
    @pytest.mark.asyncio
    async def test_one_exploding_tool_does_not_drop_sibling_result(self):
        class FaultyRegistry(ToolRegistry):
            async def aexecute(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
                if name == "boom":
                    raise RuntimeError("kaboom")
                await asyncio.sleep(0)
                return ToolCallResult(
                    tool_name=name,
                    arguments=arguments,
                    result={"ok": name},
                )

        registry = FaultyRegistry()
        registry.register(_make_tool("ok"), lambda: "unused")
        registry.register(_make_tool("boom"), lambda: "unused")

        client = AsyncMock()
        client.generate.side_effect = [
            FakeLLMResponse(
                content="",
                tool_calls=[
                    FakeToolCall(id="tc-ok", name="ok"),
                    FakeToolCall(id="tc-boom", name="boom"),
                ],
            ),
            FakeLLMResponse(content="final"),
        ]

        result = await run_tool_loop(
            client=client,
            system="sys",
            user="run tools",
            tool_registry=registry,
        )

        by_name = {item.tool_name: item for item in result.tool_calls_made}
        assert result.content == "final"
        assert by_name["ok"].result == {"ok": "ok"}
        assert by_name["boom"].error_type == "task_exception"
        assert "kaboom" in str(by_name["boom"].error)


class TestRegistryCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        call_count = 0

        async def failing_handler():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        cb_registry = ToolCircuitBreakerRegistry(failure_threshold=3, recovery_timeout_s=60.0)
        defn = _make_tool()
        reg = ToolRegistry(circuit_breakers=cb_registry)
        reg.register(defn, failing_handler)

        # 3 failures
        for _ in range(3):
            await reg.aexecute("test_tool", {})

        # Next call should be blocked by circuit breaker
        result = await reg.aexecute("test_tool", {})
        assert result.error is not None
        assert "circuit_breaker_open" in result.error

    def test_sync_circuit_breaker(self):
        cb_registry = ToolCircuitBreakerRegistry(failure_threshold=2)
        defn = _make_tool()
        reg = ToolRegistry(circuit_breakers=cb_registry)
        reg.register(defn, lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        reg.execute("test_tool", {})
        reg.execute("test_tool", {})
        result = reg.execute("test_tool", {})
        assert "circuit_breaker_open" in result.error


# ---------------------------------------------------------------------------
# ToolCircuitBreakerRegistry
# ---------------------------------------------------------------------------


class TestToolCircuitBreakerRegistry:
    def test_lazy_creation(self):
        cb = ToolCircuitBreakerRegistry()
        assert cb.allow_request("new_tool") is True
        breaker = cb.get_breaker("new_tool")
        assert breaker.state == "closed"

    def test_isolation_between_tools(self):
        cb = ToolCircuitBreakerRegistry(failure_threshold=2)
        for _ in range(2):
            cb.record_failure("tool_a")
        assert cb.allow_request("tool_a") is False
        assert cb.allow_request("tool_b") is True

    def test_reset_all(self):
        cb = ToolCircuitBreakerRegistry(failure_threshold=1)
        cb.record_failure("a")
        cb.record_failure("b")
        assert cb.allow_request("a") is False
        cb.reset_all()
        assert cb.allow_request("a") is True
        assert cb.allow_request("b") is True


# ---------------------------------------------------------------------------
# Backoff delay
# ---------------------------------------------------------------------------


class TestBackoffDelay:
    def test_first_failure_bounded(self):
        for _ in range(100):
            d = _tool_backoff_delay(1)
            assert 0 <= d <= 1.0

    def test_increasing_with_failures(self):
        # Higher failure count -> higher max possible delay
        samples_1 = [_tool_backoff_delay(1) for _ in range(100)]
        samples_3 = [_tool_backoff_delay(3) for _ in range(100)]
        assert max(samples_1) <= 1.0
        assert max(samples_3) <= 4.0  # 1 * 2^2 = 4

    def test_capped_at_30(self):
        for _ in range(100):
            d = _tool_backoff_delay(10)
            assert d <= 30.0


# ---------------------------------------------------------------------------
# Dependency Graph
# ---------------------------------------------------------------------------


class TestToolDependencyGraph:
    def test_empty_graph(self):
        g = ToolDependencyGraph()
        assert g.execution_order(["a", "b"]) == ["a", "b"]

    def test_ordering(self):
        g = ToolDependencyGraph(edges={"b": ["a"], "c": ["b"]})
        order = g.execution_order(["c", "a", "b"])
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_can_execute_checks_deps(self):
        g = ToolDependencyGraph(edges={"b": ["a"]})
        assert g.can_execute("b", set()) is False
        assert g.can_execute("b", {"a"}) is True
        assert g.can_execute("a", set()) is True

    def test_partial_deps_in_request(self):
        g = ToolDependencyGraph(edges={"b": ["a", "x"]})
        # x not in requested -> ignored, only a matters
        order = g.execution_order(["b", "a"])
        assert order.index("a") < order.index("b")

    def test_cycle_raises(self):
        g = ToolDependencyGraph(edges={"a": ["b"], "b": ["a"]})
        with pytest.raises(ValueError, match="cyclic tool dependencies detected"):
            g.execution_order(["a", "b"])
