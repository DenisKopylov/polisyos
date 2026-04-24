"""Tests for ToolRegistry."""

from __future__ import annotations

import pytest

from polisyos.scientist.agent.tools.registry import ToolCallResult, ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition


def _echo_handler(**kwargs):
    return {"echo": kwargs}


async def _async_echo_handler(**kwargs):
    return {"async_echo": kwargs}


def _failing_handler(**kwargs):
    raise ValueError("intentional error")


def _make_definition(
    name: str = "echo_tool",
    *,
    description: str | None = None,
    response_verbosity: str = "detailed",
    response_max_chars: int | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description or f"Tool {name}",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        response_verbosity=response_verbosity,
        response_max_chars=response_max_chars,
    )


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        defn = _make_definition()
        registry.register(defn, _echo_handler)
        found_defn, found_handler = registry.get("echo_tool")
        assert found_defn.name == "echo_tool"
        assert found_handler is _echo_handler

    def test_get_unknown_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_list_definitions(self):
        registry = ToolRegistry()
        registry.register(_make_definition("tool_a"), _echo_handler)
        registry.register(_make_definition("tool_b"), _echo_handler)
        defs = registry.list_definitions()
        names = {d.name for d in defs}
        assert names == {"tool_a", "tool_b"}

    def test_to_openai_tools(self):
        registry = ToolRegistry()
        registry.register(_make_definition(), _echo_handler)
        tools = registry.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "echo_tool"

    def test_select_definitions_prefers_query_relevant_tools(self):
        registry = ToolRegistry()
        registry.register(
            _make_definition(
                "billing_lookup",
                description="Inspect invoices and account balances",
            ),
            _echo_handler,
        )
        registry.register(
            _make_definition(
                "scholar_web_search",
                description="Search fresh web sources and cited policy pages",
            ),
            _echo_handler,
        )
        registry.register(
            _make_definition(
                "simulation_runner",
                description="Run Monte Carlo experiments",
            ),
            _echo_handler,
        )

        selected = registry.select_definitions(
            query_text="Need fresh web search for policy evidence",
            max_tools=2,
        )

        assert [definition.name for definition in selected] == [
            "scholar_web_search",
            "billing_lookup",
        ]

    def test_execute_success(self):
        registry = ToolRegistry()
        registry.register(_make_definition(), _echo_handler)
        result = registry.execute("echo_tool", {"text": "hello"})
        assert isinstance(result, ToolCallResult)
        assert result.error is None
        assert result.result == {"echo": {"text": "hello"}}
        assert result.duration_ms >= 0

    def test_execute_failure(self):
        registry = ToolRegistry()
        registry.register(_make_definition("fail_tool"), _failing_handler)
        result = registry.execute("fail_tool", {"text": "x"})
        assert result.error is not None
        assert "intentional error" in result.error

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent", {})
        assert result.error is not None
        assert "unknown tool" in result.error
        assert result.error_type == "unknown_tool"

    def test_execute_invalid_arguments_returns_structured_error(self):
        registry = ToolRegistry()
        registry.register(_make_definition(), _echo_handler)
        result = registry.execute("echo_tool", {})
        assert result.error_type == "invalid_arguments"
        assert result.error is not None
        assert "$.text is required" in result.error
        assert result.error_details is not None
        assert result.error_details["violations"][0]["path"] == "$.text"

    def test_execute_applies_concise_tool_response_policy(self):
        registry = ToolRegistry()
        registry.register(
            _make_definition(
                "search_tool",
                response_verbosity="concise",
            ),
            lambda text: {
                "summary": "x" * 1000,
                "items": [
                    {
                        "title": f"title-{idx}",
                        "snippet": "s" * 1000,
                    }
                    for idx in range(10)
                ],
            },
        )

        result = registry.execute("search_tool", {"text": "fresh"})

        assert result.error is None
        assert result.result["summary"].endswith("...")
        assert len(result.result["summary"]) <= 600
        assert result.result["items"]["total_count"] == 10
        assert result.result["items"]["omitted_count"] == 2

    def test_execute_applies_response_caps(self):
        registry = ToolRegistry()
        registry.register(
            _make_definition(
                "long_tool",
                response_max_chars=96,
            ),
            lambda text: "x" * 300,
        )

        result = registry.execute("long_tool", {"text": "fresh"})

        assert result.error is None
        assert isinstance(result.result, str)
        assert result.result.endswith("...")
        assert len(result.result) == 96

    @pytest.mark.asyncio
    async def test_aexecute_sync_handler(self):
        registry = ToolRegistry()
        registry.register(_make_definition(), _echo_handler)
        result = await registry.aexecute("echo_tool", {"text": "async"})
        assert result.error is None
        assert result.result == {"echo": {"text": "async"}}

    @pytest.mark.asyncio
    async def test_aexecute_async_handler(self):
        registry = ToolRegistry()
        registry.register(_make_definition("async_tool"), _async_echo_handler)
        result = await registry.aexecute("async_tool", {"text": "async"})
        assert result.error is None
        assert result.result == {"async_echo": {"text": "async"}}

    @pytest.mark.asyncio
    async def test_aexecute_failure(self):
        registry = ToolRegistry()
        registry.register(_make_definition("fail_tool"), _failing_handler)
        result = await registry.aexecute("fail_tool", {"text": "x"})
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_aexecute_unknown_tool(self):
        registry = ToolRegistry()
        result = await registry.aexecute("nonexistent", {})
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_aexecute_unknown_tool_with_non_object_arguments_is_structured(self):
        registry = ToolRegistry()
        result = await registry.aexecute("nonexistent", ["bad"])
        assert result.error_type == "unknown_tool"
        assert result.arguments == {}

    @pytest.mark.asyncio
    async def test_aexecute_rejects_non_object_arguments(self):
        registry = ToolRegistry()
        registry.register(_make_definition(), _async_echo_handler)
        result = await registry.aexecute("echo_tool", ["bad"])
        assert result.error_type == "invalid_arguments"
        assert result.error_details is not None
        assert result.error_details["violations"][0]["path"] == "$"


class TestToolCallResult:
    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            ToolCallResult(tool_name="x", arguments={}, unknown="y")

    def test_serialization(self):
        result = ToolCallResult(
            tool_name="echo_tool",
            arguments={"text": "hello"},
            result={"echo": {"text": "hello"}},
            duration_ms=42,
        )
        data = result.model_dump()
        assert data["tool_name"] == "echo_tool"
        assert data["duration_ms"] == 42
        assert data["error"] is None
