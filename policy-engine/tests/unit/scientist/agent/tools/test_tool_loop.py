"""Tests for run_tool_loop and parse_tool_calls_from_response."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.agent.persistent_memory import PersistentMemoryStore
from polisyos.scientist.agent.reflexion_evaluator import (
    ReflexionEvaluatorConfig,
    RubricReflexionEvaluator,
)
from polisyos.scientist.agent.tools.dependency_graph import ToolDependencyGraph
from polisyos.scientist.agent.tools.registry import ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition
from polisyos.scientist.agent.tools.tool_loop import (
    ToolLoopCompactionConfig,
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


class _FakeArtifactStore:
    def __init__(self) -> None:
        self._payloads: dict[str, bytes] = {}
        self._counter = 0

    def put_json(self, data, options=None):
        del options
        self._counter += 1
        artifact_id = f"sha256:{self._counter:064d}"
        self._payloads[artifact_id] = json.dumps(data, default=str).encode()
        return ArtifactRef(
            artifact_id=artifact_id,
            kind="test",
            media_type="application/json",
        )

    def get_bytes(self, artifact_id):
        return self._payloads[str(artifact_id)]


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
        degraded_events: list[dict[str, Any]] = []
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
        calls = parse_tool_calls_from_response(
            response,
            degraded_events=degraded_events,
        )
        assert len(calls) == 1
        assert calls[0].arguments == {}
        assert degraded_events
        assert degraded_events[0]["component"] == "agent.tool_loop"
        assert degraded_events[0]["operation"] == "parse_tool_calls"
        assert degraded_events[0]["reason"] == "tool_arguments_parse_failed"


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
    async def test_two_round_transcript_preserves_assistant_and_tool_messages(self):
        client = AsyncMock()
        client.generate.side_effect = [
            MockResponse(
                content="",
                tool_calls=[
                    MockToolCallAttr(
                        id="tc-1",
                        name="echo",
                        arguments={"text": "hello"},
                    ),
                ],
            ),
            MockResponse(content="final answer"),
        ]

        result = await run_tool_loop(
            client=client,
            system="system prompt",
            user="call echo",
            tool_registry=_make_registry_with_echo(),
        )

        assert result.content == "final answer"
        assert client.generate.await_count == 2
        first_call_kwargs = client.generate.await_args_list[0].kwargs
        second_call_kwargs = client.generate.await_args_list[1].kwargs

        assert first_call_kwargs["messages"] == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "call echo"},
        ]

        transcript = second_call_kwargs["messages"]
        assert transcript[0] == {"role": "system", "content": "system prompt"}
        assert transcript[1] == {"role": "user", "content": "call echo"}
        assert transcript[2]["role"] == "assistant"
        assert transcript[2]["tool_calls"][0]["id"] == "tc-1"
        assert transcript[2]["tool_calls"][0]["function"]["name"] == "echo"
        assert transcript[3]["role"] == "tool"
        assert transcript[3]["tool_call_id"] == "tc-1"
        assert transcript[3]["content"] == '{"echoed": "hello"}'

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

        actions = [
            c.kwargs.get("action") or c[1].get("action", "") for c in audit.append.call_args_list
        ]
        assert "TOOL_INVOKED" in actions
        assert "TOOL_COMPLETED" in actions
        assert result.degraded_events == []

    @pytest.mark.asyncio
    async def test_token_tracking(self):
        client = AsyncMock()
        client.generate.return_value = MockResponse(
            content="done",
            usage=MockUsage(total_tokens=150),
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
        assert result.degraded_events == []

    @pytest.mark.asyncio
    async def test_budget_probe_failure_is_reported_as_degraded_event(self):
        class _BudgetEnforcer:
            def __init__(self) -> None:
                self.generate = AsyncMock(return_value=MockResponse(content="ok"))

            def remaining_budget(self):
                raise RuntimeError("ledger unavailable")

        result = await run_tool_loop(
            client=AsyncMock(),
            system="sys",
            user="test",
            tool_registry=_make_registry_with_echo(),
            budget_enforcer=_BudgetEnforcer(),
        )

        assert result.content == "ok"
        assert result.degraded_events
        assert result.degraded_events[0]["component"] == "agent.tool_loop"
        assert result.degraded_events[0]["operation"] == "remaining_budget"
        assert result.degraded_events[0]["reason"] == "initial_budget_probe_failed"

    @pytest.mark.asyncio
    async def test_persistent_memory_recall_failure_is_reported_as_degraded_event(self):
        class _BrokenMemory:
            def query(self, query):
                del query
                raise RuntimeError("memory unavailable")

        client = AsyncMock()
        client.generate.return_value = MockResponse(content="final answer")

        result = await run_tool_loop(
            client=client,
            system="sys",
            user="Explain subsidy tradeoffs",
            tool_registry=_make_registry_with_echo(),
            persistent_memory=_BrokenMemory(),
        )

        assert result.content == "final answer"
        assert result.retrieved_memories == []
        assert result.degraded_events
        assert result.degraded_events[0]["component"] == "agent.tool_loop"
        assert result.degraded_events[0]["operation"] == "persistent_memory_recall"
        assert result.degraded_events[0]["reason"] == "memory_injection_failed"

    @pytest.mark.asyncio
    async def test_adaptive_budget_cap_can_stop_loop_before_next_llm_call(self):
        class _BudgetEnforcer:
            def __init__(self) -> None:
                self.generate = AsyncMock(
                    side_effect=[
                        MockResponse(
                            content="",
                            tool_calls=[
                                MockToolCallAttr(id="tc-1", name="echo", arguments={"text": "hi"}),
                            ],
                        ),
                        MockResponse(content="should not be reached"),
                    ]
                )
                self._remaining = iter([2.0, 0.4])

            def remaining_budget(self):
                return next(self._remaining)

        budget_enforcer = _BudgetEnforcer()
        result = await run_tool_loop(
            client=AsyncMock(),
            system="sys",
            user="call echo",
            tool_registry=_make_registry_with_echo(),
            budget_enforcer=budget_enforcer,
            max_iterations=4,
        )

        assert result.iterations == 1
        assert len(result.tool_calls_made) == 1
        assert budget_enforcer.generate.await_count == 1

    @pytest.mark.asyncio
    async def test_independent_tools_execute_in_parallel_with_stable_message_order(self):
        client = AsyncMock()
        client.generate.side_effect = [
            MockResponse(
                content="",
                tool_calls=[
                    MockToolCallAttr(id="tc-1", name="slow_one", arguments={}),
                    MockToolCallAttr(id="tc-2", name="slow_two", arguments={}),
                ],
            ),
            MockResponse(content="done"),
        ]

        registry = ToolRegistry()
        state = {"active": 0, "max_active": 0}

        async def _run_tool(name: str) -> dict[str, str]:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
            await asyncio.sleep(0.05)
            state["active"] -= 1
            return {"tool": name}

        def _make_async_tool(name: str):
            async def _tool() -> dict[str, str]:
                return await _run_tool(name)

            return _tool

        for name in ("slow_one", "slow_two"):
            registry.register(
                ToolDefinition(
                    name=name,
                    description="slow tool",
                    parameters={"type": "object", "properties": {}},
                ),
                _make_async_tool(name),
            )

        result = await run_tool_loop(
            client=client,
            system="sys",
            user="run both",
            tool_registry=registry,
        )

        assert result.content == "done"
        assert state["max_active"] >= 2
        transcript = client.generate.await_args_list[1].kwargs["messages"]
        tool_messages = [item for item in transcript if item.get("role") == "tool"]
        assert [item["tool_call_id"] for item in tool_messages] == ["tc-1", "tc-2"]

    @pytest.mark.asyncio
    async def test_dependent_tools_stay_sequential_across_layers(self):
        client = AsyncMock()
        client.generate.side_effect = [
            MockResponse(
                content="",
                tool_calls=[
                    MockToolCallAttr(id="tc-1", name="first_tool", arguments={}),
                    MockToolCallAttr(id="tc-2", name="second_tool", arguments={}),
                ],
            ),
            MockResponse(content="done"),
        ]

        registry = ToolRegistry()
        state = {"active": 0, "max_active": 0}

        async def _run_tool(name: str) -> dict[str, str]:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
            await asyncio.sleep(0.03)
            state["active"] -= 1
            return {"tool": name}

        def _make_async_tool(name: str):
            async def _tool() -> dict[str, str]:
                return await _run_tool(name)

            return _tool

        for name in ("first_tool", "second_tool"):
            registry.register(
                ToolDefinition(
                    name=name,
                    description="tool",
                    parameters={"type": "object", "properties": {}},
                ),
                _make_async_tool(name),
            )

        result = await run_tool_loop(
            client=client,
            system="sys",
            user="run dependency chain",
            tool_registry=registry,
            tool_dependencies=ToolDependencyGraph(edges={"second_tool": ["first_tool"]}),
        )

        assert result.content == "done"
        assert state["max_active"] == 1

    @pytest.mark.asyncio
    async def test_reflexion_evaluator_retries_weak_no_tool_answer(self):
        client = AsyncMock()
        client.generate.side_effect = [
            MockResponse(content="done"),
            MockResponse(
                content=(
                    "A grounded subsidy answer with budget and compliance "
                    "discussion. https://example.org/report"
                )
            ),
        ]

        evaluator = RubricReflexionEvaluator(
            ReflexionEvaluatorConfig(
                min_quality_score=0.2,
                min_grounding_score=0.1,
                min_schema_score=0.5,
                min_overall_score=0.25,
                min_improvement_delta=0.01,
            )
        )
        result = await run_tool_loop(
            client=client,
            system="sys",
            user="Explain subsidy tradeoffs",
            tool_registry=_make_registry_with_echo(),
            max_iterations=3,
            reflexion_evaluator=evaluator,
        )

        assert result.content.startswith("A grounded subsidy answer")
        assert result.iterations == 2
        assert result.converged is True
        assert result.convergence_reason == "rubric_passed"
        assert len(result.evaluation_history) == 2
        second_call_messages = client.generate.await_args_list[1].kwargs["messages"]
        assert "REFLEXION EVALUATOR FEEDBACK" in second_call_messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_reflexion_memory_is_injected_into_system_prompt(self):
        client = AsyncMock()
        client.generate.return_value = MockResponse(content="final answer")

        memory = PersistentMemoryStore(_FakeArtifactStore())
        memory.store_reflexion_memory(
            problem_statement="Explain subsidy tradeoffs",
            reflection="Use domain-specific citations and avoid malformed search args.",
            trajectory_summary="Previous no-tool answer was under-grounded.",
            source_run_id="run-old",
            error_code="LOW_GROUNDING",
            tool_error_patterns=["scholar_web_search:invalid_arguments"],
        )

        result = await run_tool_loop(
            client=client,
            system="sys",
            user="Explain subsidy tradeoffs",
            tool_registry=_make_registry_with_echo(),
            persistent_memory=memory,
        )

        assert result.retrieved_memories
        first_call_messages = client.generate.await_args_list[0].kwargs["messages"]
        assert "PRIOR KNOWLEDGE" in first_call_messages[0]["content"]
        assert "avoid malformed search args" in first_call_messages[0]["content"]

    @pytest.mark.asyncio
    async def test_tool_discovery_limits_large_registry_to_query_relevant_tools(self):
        client = AsyncMock()
        client.generate.return_value = MockResponse(content="final answer")

        registry = ToolRegistry()
        for index in range(16):
            registry.register(
                ToolDefinition(
                    name=f"utility_tool_{index}",
                    description="Generic internal maintenance tool",
                    parameters={"type": "object", "properties": {}},
                ),
                lambda **kwargs: kwargs,
            )
        registry.register(
            ToolDefinition(
                name="scholar_web_search",
                description="Search fresh web policy evidence and cited sources",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            ),
            lambda query="": {"query": query},
        )

        result = await run_tool_loop(
            client=client,
            system="sys",
            user="Need fresh web search for climate policy evidence",
            tool_registry=registry,
            tool_discovery_threshold=8,
            tool_discovery_max_tools=3,
        )

        assert result.content == "final answer"
        tools = client.generate.await_args.kwargs["tools"]
        tool_names = [item["function"]["name"] for item in tools]
        assert len(tools) == 3
        assert "scholar_web_search" in tool_names

    @pytest.mark.asyncio
    async def test_compaction_preserves_user_prompt_and_recent_tool_results_without_system(self):
        client = AsyncMock()
        client.generate.side_effect = [
            MockResponse(
                content="",
                tool_calls=[
                    MockToolCallAttr(id="tc-old", name="echo", arguments={"text": "first"}),
                ],
            ),
            MockResponse(
                content="",
                tool_calls=[
                    MockToolCallAttr(id="tc-new", name="echo", arguments={"text": "second"}),
                ],
            ),
            MockResponse(content="final answer"),
        ]

        result = await run_tool_loop(
            client=client,
            system="",
            user="call echo twice",
            tool_registry=_make_registry_with_echo(),
            max_iterations=4,
            compaction_config=ToolLoopCompactionConfig(
                max_messages=6,
                max_transcript_chars=1,
                keep_recent_tool_results=1,
                compacted_tool_result_chars=40,
                compacted_assistant_chars=40,
            ),
        )

        assert result.content == "final answer"
        third_call_messages = client.generate.await_args_list[2].kwargs["messages"]
        assert len(third_call_messages) <= 6
        assert third_call_messages[0]["role"] == "system"
        assert "TOOL TRANSCRIPT COMPACTION NOTICE" in third_call_messages[0]["content"]
        assert third_call_messages[1] == {
            "role": "user",
            "content": "call echo twice",
        }

        tool_messages = [
            message for message in third_call_messages if message.get("role") == "tool"
        ]
        assert json.loads(tool_messages[0]["content"])["compacted_tool_result"] is True
        assert json.loads(tool_messages[-1]["content"]) == {"echoed": "second"}
