"""Tests for run_tool_loop and parse_tool_calls_from_response."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from polisyos.scientist.agent.tools.registry import ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition
from polisyos.scientist.agent.tools.tool_loop import (
    ParsedToolCall,
    ToolLoopResult,
    parse_tool_calls_from_response,
    run_tool_loop,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class MockToolCallAttr:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class MockUsage:
    total_tokens: int = 100


@dataclass
class MockResponse:
    content: str = ""
    usage: MockUsage = field(default_factory=MockUsage)
    tool_calls: list[MockToolCallAttr] | None = None
    raw: dict[str, Any] | None = None


def _make_registry_with_echo() -> ToolRegistry:
    registry = ToolRegistry()
    defn = ToolDefinition(
        name="echo",
        description="Echo the input",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )
    registry.register(defn, lambda text="": {"echoed": text})
    return registry


# ---------------------------------------------------------------------------
# parse_tool_calls_from_response
# ---------------------------------------------------------------------------

class TestParseToolCalls:
    def test_from_tool_calls_attr(self):
        response = MockResponse(
            tool_calls=[
                MockToolCallAttr(id="tc-1", name="echo", arguments={"text": "hi"}),
            ],
        )
        calls = parse_tool_calls_from_response(response)
        assert len(calls) == 1
        assert calls[0].name == "echo"
        assert calls[0].arguments == {"text": "hi"}

    def test_from_raw_dict(self):
        response = MockResponse(
            tool_calls=None,
            raw={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "tc-2",
                                    "function": {
                                        "name": "echo",
                                        "arguments": '{"text": "raw"}',
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        )
        calls = parse_tool_calls_from_response(response)
        assert len(calls) == 1
        assert calls[0].name == "echo"
        assert calls[0].arguments == {"text": "raw"}

    def test_no_tool_calls(self):
        response = MockResponse(content="just text")
        calls = parse_tool_calls_from_response(response)
        assert calls == []

    def test_malformed_arguments_json(self):
        response = MockResponse(
            tool_calls=None,
            raw={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "tc-3",
                                    "function": {
                                        "name": "echo",
                                        "arguments": "not-json",
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        )
        calls = parse_tool_calls_from_response(response)
        assert len(calls) == 1
        assert calls[0].arguments == {}


# ---------------------------------------------------------------------------
# run_tool_loop
# ---------------------------------------------------------------------------

class TestRunToolLoop:
    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_immediately(self):
        client = AsyncMock()
        client.generate.return_value = MockResponse(content="final answer")

        registry = _make_registry_with_echo()
        result = await run_tool_loop(
            client=client,
            system="You are helpful",
            user="What is 2+2?",
            tool_registry=registry,
            max_iterations=5,
        )
        assert isinstance(result, ToolLoopResult)
        assert result.content == "final answer"
        assert result.tool_calls_made == []
        assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_single_tool_call_then_final(self):
        """LLM calls echo tool once, then responds with final answer."""
        client = AsyncMock()

        # First response: tool call
        first_response = MockResponse(
            content="",
            tool_calls=[
                MockToolCallAttr(id="tc-1", name="echo", arguments={"text": "hello"}),
            ],
        )
        # Second response: final answer
        second_response = MockResponse(content="The echo said hello")

        client.generate.side_effect = [first_response, second_response]

        registry = _make_registry_with_echo()
        result = await run_tool_loop(
            client=client,
            system="sys",
            user="call echo",
            tool_registry=registry,
        )

        assert result.content == "The echo said hello"
        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].tool_name == "echo"
        assert result.tool_calls_made[0].error is None
        assert result.iterations == 2

    @pytest.mark.asyncio
    async def test_max_iterations_guard(self):
        """Should stop after max_iterations even if LLM keeps requesting tools."""
        client = AsyncMock()
        # Always return a tool call
        client.generate.return_value = MockResponse(
            content="",
            tool_calls=[
                MockToolCallAttr(id="tc-1", name="echo", arguments={"text": "loop"}),
            ],
        )

        registry = _make_registry_with_echo()
        result = await run_tool_loop(
            client=client,
            system="sys",
            user="loop forever",
            tool_registry=registry,
            max_iterations=3,
        )

        assert result.iterations == 3
        assert len(result.tool_calls_made) == 3

    @pytest.mark.asyncio
    async def test_unknown_tool_error_recorded(self):
        """Unknown tool names should result in error ToolCallResult."""
        client = AsyncMock()

        first_response = MockResponse(
            content="",
            tool_calls=[
                MockToolCallAttr(id="tc-1", name="nonexistent_tool", arguments={}),
            ],
        )
        second_response = MockResponse(content="done")
        client.generate.side_effect = [first_response, second_response]

        registry = _make_registry_with_echo()
        result = await run_tool_loop(
            client=client,
            system="sys",
            user="call unknown",
            tool_registry=registry,
        )

        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].error is not None
        assert "unknown tool" in result.tool_calls_made[0].error

    @pytest.mark.asyncio
    async def test_audit_log_events(self):
        """Audit log should record TOOL_INVOKED and TOOL_COMPLETED."""
        client = AsyncMock()

        first_response = MockResponse(
            content="",
            tool_calls=[
                MockToolCallAttr(id="tc-1", name="echo", arguments={"text": "hi"}),
            ],
        )
        second_response = MockResponse(content="done")
        client.generate.side_effect = [first_response, second_response]

        audit = MagicMock()
        registry = _make_registry_with_echo()
        result = await run_tool_loop(
            client=client,
            system="sys",
            user="call echo",
            tool_registry=registry,
            audit_log=audit,
        )

        actions = [c.kwargs.get("action") or c[1].get("action", "") for c in audit.append.call_args_list]
        assert "TOOL_INVOKED" in actions
        assert "TOOL_COMPLETED" in actions

    @pytest.mark.asyncio
    async def test_token_tracking(self):
        client = AsyncMock()
        client.generate.return_value = MockResponse(
            content="done", usage=MockUsage(total_tokens=150),
        )

        registry = _make_registry_with_echo()
        result = await run_tool_loop(
            client=client,
            system="sys",
            user="test",
            tool_registry=registry,
        )
        assert result.total_tokens == 150

    @pytest.mark.asyncio
    async def test_budget_enforcer_integration(self):
        """When a budget_enforcer is provided, it should be used instead of client."""
        budget_enforcer = AsyncMock()
        budget_enforcer.generate.return_value = MockResponse(content="budgeted response")

        client = AsyncMock()  # Should NOT be called
        registry = _make_registry_with_echo()

        result = await run_tool_loop(
            client=client,
            system="sys",
            user="test",
            tool_registry=registry,
            budget_enforcer=budget_enforcer,
        )

        budget_enforcer.generate.assert_awaited_once()
        client.generate.assert_not_awaited()
        assert result.content == "budgeted response"
